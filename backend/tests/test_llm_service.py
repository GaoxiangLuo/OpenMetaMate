"""Tests for LLM provider failover and the Claude fallback path."""

import asyncio

import anthropic
import httpx
import httpx2
import openai
import pytest

from app.core.exceptions import ExtractionError
from app.services import llm_service
from app.services.llm_service import (
    CLAUDE_FIELDS_PER_REQUEST,
    GPT_5_SYSTEM_PROMPT,
    GPT_6_SYSTEM_PROMPT,
    LLMService,
    _claude_output_schema,
    _deep_merge,
    _should_failover,
)
from app.services.pydantic_model_generator import coding_scheme_items_to_pydantic_model

TEXT = "<<PAGE 1>>\nA study of 228 students.\n<<END PAGE 1>>"


def _scheme(count: int) -> list[dict]:
    return [
        {"name": f"Group {i % 3}/Field {i}", "description": "d", "include_in_extraction": True}
        for i in range(count)
    ]


def _openai_error(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.test"))
    error_class = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        429: openai.RateLimitError,
        500: openai.InternalServerError,
    }[status]
    return error_class("boom", response=response, body=None)


def _service(*clients) -> LLMService:
    """Build a service around stub clients without reading settings."""
    service = object.__new__(LLMService)
    service.model = "gpt-6-luna"
    service.providers = [(f"provider {i}", client) for i, client in enumerate(clients)]
    return service


OPENAI_CLIENT = openai.AsyncOpenAI(api_key="test")
CLAUDE_CLIENT = anthropic.AsyncAnthropic(api_key="test")


@pytest.mark.parametrize("status,expected", [(401, True), (403, True), (429, True), (500, True)])
def test_should_failover_on_key_and_server_errors(status: int, expected: bool) -> None:
    assert _should_failover(_openai_error(status)) is expected


def test_should_not_failover_on_bad_request_or_timeout() -> None:
    request = httpx.Request("POST", "https://api.test")
    assert _should_failover(_openai_error(400)) is False
    assert _should_failover(openai.APITimeoutError(request=request)) is False
    assert _should_failover(ValueError("not an API error")) is False


def test_should_failover_on_connection_and_claude_errors() -> None:
    assert _should_failover(openai.APIConnectionError(request=httpx.Request("POST", "https://x")))
    response = httpx2.Response(429, request=httpx2.Request("POST", "https://api.test"))
    assert _should_failover(anthropic.RateLimitError("boom", response=response, body=None))


def test_gpt6_prompt_drops_checklist_instruction() -> None:
    assert "checklist" in GPT_5_SYSTEM_PROMPT
    assert "checklist" not in GPT_6_SYSTEM_PROMPT


def test_claude_output_schema_requires_every_field_without_nullable_groups() -> None:
    model = coding_scheme_items_to_pydantic_model(_scheme(6))
    schema = _claude_output_schema(model)

    groups = [schema] + [
        definition
        for name, definition in schema["$defs"].items()
        if name not in ("LLMExtractionField", "LLMCitation")
    ]
    assert len(groups) == 4  # root + three groups
    for group in groups:
        assert group["required"] == list(group["properties"])
        assert group["additionalProperties"] is False
        assert all("anyOf" not in prop for prop in group["properties"].values())


def test_deep_merge_combines_nested_groups() -> None:
    merged = _deep_merge({"a": {"x": 1}, "b": 1}, {"a": {"y": 2}, "c": 3})
    assert merged == {"a": {"x": 1, "y": 2}, "b": 1, "c": 3}


def test_extract_fails_over_to_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def openai_call(self, client, name, model, text):
        calls.append(name)
        raise _openai_error(429)

    async def claude_call(self, client, name, model, scheme, text):
        calls.append(name)
        return {"ok": True}

    monkeypatch.setattr(LLMService, "_call_llm", openai_call)
    monkeypatch.setattr(LLMService, "_call_claude", claude_call)

    service = _service(OPENAI_CLIENT, OPENAI_CLIENT, CLAUDE_CLIENT)
    result = asyncio.run(service.extract_with_schema(TEXT, _scheme(2)))

    assert result == {"ok": True}
    assert calls == ["provider 0", "provider 1", "provider 2"]


def test_extract_does_not_fail_over_on_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def openai_call(self, client, name, model, text):
        calls.append(name)
        raise _openai_error(400)

    monkeypatch.setattr(LLMService, "_call_llm", openai_call)

    service = _service(OPENAI_CLIENT, OPENAI_CLIENT)
    with pytest.raises(ExtractionError):
        asyncio.run(service.extract_with_schema(TEXT, _scheme(2)))
    assert calls == ["provider 0"]


def test_extract_reports_every_failure_when_all_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def openai_call(self, client, name, model, text):
        raise _openai_error(429)

    monkeypatch.setattr(LLMService, "_call_llm", openai_call)

    service = _service(OPENAI_CLIENT, OPENAI_CLIENT)
    with pytest.raises(ExtractionError, match="All LLM APIs failed.*provider 0.*provider 1"):
        asyncio.run(service.extract_with_schema(TEXT, _scheme(2)))


def test_call_claude_batches_fields_and_merges_results(monkeypatch: pytest.MonkeyPatch) -> None:
    batch_sizes = []

    async def claude_request(self, client, batch, text):
        batch_sizes.append(len(batch))
        partial: dict = {}
        for item in batch:
            group, field = (part.lower().replace(" ", "_") for part in item["name"].split("/"))
            partial.setdefault(group, {})[field] = {"value": "x", "answer_type": "Grounded"}
        return partial

    monkeypatch.setattr(LLMService, "_claude_request", claude_request)

    count = CLAUDE_FIELDS_PER_REQUEST * 2 + 5
    scheme = _scheme(count) + [{"name": "Group 0/Skipped", "include_in_extraction": False}]
    model = coding_scheme_items_to_pydantic_model(scheme)
    result = asyncio.run(_service()._call_claude(CLAUDE_CLIENT, "claude", model, scheme, TEXT))

    assert sorted(batch_sizes) == [5, CLAUDE_FIELDS_PER_REQUEST, CLAUDE_FIELDS_PER_REQUEST]
    fields = [field for group in result.values() for field in group.values()]
    assert sum(field is not None for field in fields) == count
    assert result["group_0"]["field_0"]["value"] == "x"
    assert "skipped" not in result["group_0"]


def test_gpt6_model_uses_gpt6_prompt() -> None:
    captured = {}

    class Responses:
        async def parse(self, **payload):
            captured.update(payload)
            return type("Response", (), {"output_parsed": None, "parsed": None})()

    class Completions:
        async def parse(self, **payload):
            message = type("Message", (), {"parsed": None})()
            return type("Completion", (), {"choices": [type("Choice", (), {"message": message})]})()

    client = type(
        "Client",
        (),
        {"responses": Responses(), "chat": type("Chat", (), {"completions": Completions()})()},
    )()
    model = coding_scheme_items_to_pydantic_model(_scheme(1))
    asyncio.run(_service()._call_llm(client, "primary", model, TEXT))

    assert captured["input"][0]["content"] == llm_service.GPT_6_SYSTEM_PROMPT
    assert captured["reasoning"] == {"effort": "none"}
