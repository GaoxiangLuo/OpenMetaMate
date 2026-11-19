"""Tests for the decision-model confidence scorer."""

import asyncio

import httpx
import openai

from app.api.routes.extraction import (
    apply_confidence_scores,
    build_extraction_item,
    should_score_confidence,
)
from app.core.config import settings
from app.models.requests import CodingSchemeItem
from app.models.responses import Citation, ExtractionResultItem
from app.services.confidence_scorer import (
    MAX_QUESTIONS_PER_REQUEST,
    ConfidenceScorer,
    build_question,
)
from app.services.llm_service import LLMService

TEXT = "<<PAGE 1>>\nA study of 228 students.\n<<END PAGE 1>>"


class StubClient:
    """Stands in for AsyncOpenAI: records request bodies and replays answers or errors."""

    def __init__(self, answer=None, error: Exception | None = None):
        self.answer = answer or (lambda question: 0.9)
        self.error = error
        self.bodies: list[dict] = []
        self.options: dict = {}

    def with_options(self, **options):
        self.options = options
        return self

    async def post(self, path: str, *, body: dict, cast_to):
        self.bodies.append(body)
        if self.error:
            raise self.error
        answers = []
        for question in body["questions"]:
            result = self.answer(question)
            if result is None:
                answers.append({"type": "refusal", "name": question["name"]})
            else:
                answers.append(
                    {"type": "predicate", "name": question["name"], "probability": result}
                )
        return httpx.Response(200, json={"model": body["model"], "answers": answers})


def _rate_limit_error() -> openai.RateLimitError:
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.test"))
    return openai.RateLimitError("boom", response=response, body=None)


def _bad_request_error() -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.test"))
    return openai.BadRequestError("boom", response=response, body=None)


def _scheme(*specs: tuple[str, str]) -> list[CodingSchemeItem]:
    return [
        CodingSchemeItem(
            id=str(i),
            name=name,
            dataType=data_type,
            description=f"about {name}",
            includeInExtraction=True,
        )
        for i, (name, data_type) in enumerate(specs)
    ]


def _found(value) -> ExtractionResultItem:
    return ExtractionResultItem(
        value=value,
        answer_type="Grounded",
        citations=[Citation(page_number=1, citation_type="Exact Quote")],
    )


def _not_found() -> ExtractionResultItem:
    return ExtractionResultItem(value="Not Found", answer_type="Not Found", citations=[])


def _scorer(*clients) -> ConfidenceScorer:
    return ConfidenceScorer([(f"key {i}", c) for i, c in enumerate(clients)], "gpt-6-luna")


def _score(scorer: ConfidenceScorer, scheme, data) -> dict[str, float]:
    return asyncio.run(scorer.score(TEXT, scheme, data))


def test_question_states_field_definition_and_value() -> None:
    item = _scheme(("Sample/Size", "Numeric"))[0]
    question = build_question(3, item, 228.0)
    assert question["type"] == "predicate"
    assert question["name"] == "q3"
    assert "Field: Sample/Size" in question["instructions"]
    assert "Definition: about Sample/Size" in question["instructions"]
    # Whole numbers read as integers, the way they appear in the paper
    assert "Extracted value: 228\n" in question["instructions"]


def test_text_question_states_the_extracted_value() -> None:
    text = _scheme(("Design", "Text"))[0]
    assert "Extracted value: RCT\n" in build_question(1, text, " RCT ")["instructions"]


def test_boolean_question_asks_the_field_directly() -> None:
    boolean = _scheme(("Randomized", "Boolean"))[0]
    for value in (True, False):
        instructions = build_question(0, boolean, value)["instructions"]
        assert "the field should be coded True" in instructions
        # The extracted answer is not shown, so the question is the same either way
        assert "Extracted value" not in instructions


def test_boolean_false_confidence_is_the_complement() -> None:
    scheme = _scheme(("Randomized", "Boolean"), ("Blinded", "Boolean"), ("Design", "Text"))
    data = {"Randomized": _found(True), "Blinded": _found(False), "Design": _found("RCT")}
    # The model says each field is 80% likely to be True (or the text value 80% likely right)
    scores = _score(_scorer(StubClient(answer=lambda q: 0.8)), scheme, data)
    assert scores == {"Randomized": 0.8, "Blinded": 0.2, "Design": 0.8}


def test_boolean_field_with_non_boolean_value_is_checked_like_text() -> None:
    boolean = _scheme(("Randomized", "Boolean"))[0]
    instructions = build_question(0, boolean, "unclear")["instructions"]
    assert "Extracted value: unclear\n" in instructions
    scores = _score(
        _scorer(StubClient(answer=lambda q: 0.3)), [boolean], {"Randomized": _found("unclear")}
    )
    assert scores == {"Randomized": 0.3}


def test_boolean_given_as_text_is_still_asked_directly() -> None:
    boolean = _scheme(("Randomized", "Boolean"))[0]
    scores = _score(
        _scorer(StubClient(answer=lambda q: 0.9)), [boolean], {"Randomized": _found("False")}
    )
    assert scores == {"Randomized": 0.1}


def test_scores_map_back_to_field_names_in_one_request() -> None:
    scheme = _scheme(("Sample/Size", "Numeric"), ("Randomized", "Boolean"), ("Design", "Text"))
    data = {"Sample/Size": _found(228.0), "Randomized": _found(True), "Design": _found("RCT")}
    by_field = {"Sample/Size": 0.97, "Randomized": 0.42, "Design": 1}
    client = StubClient(
        answer=lambda q: next(
            v for k, v in by_field.items() if f"Field: {k}\n" in q["instructions"]
        )
    )

    scores = _score(_scorer(client), scheme, data)

    assert scores == {"Sample/Size": 0.97, "Randomized": 0.42, "Design": 1.0}
    assert len(client.bodies) == 1
    body = client.bodies[0]
    assert body["model"] == "gpt-6-luna"
    assert body["input"][-1] == {"role": "user", "content": TEXT}
    assert [q["name"] for q in body["questions"]] == ["q0", "q1", "q2"]
    assert client.options["max_retries"] == 0


def test_not_found_fields_are_not_sent() -> None:
    scheme = _scheme(("Sample/Size", "Numeric"), ("Design", "Text"))
    data = {"Sample/Size": _not_found(), "Design": _found("RCT")}
    client = StubClient()

    scores = _score(_scorer(client), scheme, data)

    assert scores == {"Design": 0.9}
    assert len(client.bodies[0]["questions"]) == 1


def test_no_request_when_nothing_was_found() -> None:
    scheme = _scheme(("Design", "Text"))
    client = StubClient()
    assert _score(_scorer(client), scheme, {"Design": _not_found()}) == {}
    assert client.bodies == []


def test_refused_question_gets_no_score() -> None:
    scheme = _scheme(("Sample/Size", "Numeric"), ("Design", "Text"))
    data = {"Sample/Size": _found(228.0), "Design": _found("RCT")}
    client = StubClient(answer=lambda q: None if "Design" in q["instructions"] else 0.8)
    assert _score(_scorer(client), scheme, data) == {"Sample/Size": 0.8}


def test_out_of_range_probability_is_dropped() -> None:
    scheme = _scheme(("Design", "Text"))
    client = StubClient(answer=lambda q: 1.7)
    assert _score(_scorer(client), scheme, {"Design": _found("RCT")}) == {}


def test_api_error_returns_no_scores_instead_of_raising() -> None:
    scheme = _scheme(("Design", "Text"))
    client = StubClient(error=_bad_request_error())
    assert _score(_scorer(client), scheme, {"Design": _found("RCT")}) == {}


def test_rate_limited_key_fails_over_to_backup_key() -> None:
    scheme = _scheme(("Design", "Text"))
    primary, backup = StubClient(error=_rate_limit_error()), StubClient()
    scores = _score(_scorer(primary, backup), scheme, {"Design": _found("RCT")})
    assert scores == {"Design": 0.9}
    assert len(primary.bodies) == len(backup.bodies) == 1


def test_bad_request_does_not_try_the_backup_key() -> None:
    scheme = _scheme(("Design", "Text"))
    primary, backup = StubClient(error=_bad_request_error()), StubClient()
    assert _score(_scorer(primary, backup), scheme, {"Design": _found("RCT")}) == {}
    assert backup.bodies == []


def test_more_than_400_fields_are_split_across_requests() -> None:
    count = MAX_QUESTIONS_PER_REQUEST + 5
    scheme = _scheme(*[(f"Field {i}", "Text") for i in range(count)])
    data = {item.name: _found("x") for item in scheme}
    client = StubClient()

    scores = _score(_scorer(client), scheme, data)

    assert len(scores) == count
    assert [len(b["questions"]) for b in client.bodies] == [MAX_QUESTIONS_PER_REQUEST, 5]


def test_scorer_without_clients_is_disabled() -> None:
    scorer = _scorer()
    assert scorer.enabled is False
    assert _score(scorer, _scheme(("Design", "Text")), {"Design": _found("RCT")}) == {}


def _llm_service() -> LLMService:
    service = object.__new__(LLMService)
    service.model = "gpt-6-luna"
    service.providers = [("primary API", openai.AsyncOpenAI(api_key="test"))]
    return service


def test_scoring_is_off_for_non_openai_hosts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DECISION_MODEL", "gpt-6-luna")
    monkeypatch.setattr(settings, "LLM_API_URL", "https://openrouter.ai/api/v1")
    assert ConfidenceScorer.from_llm_service(_llm_service()).enabled is False

    monkeypatch.setattr(settings, "LLM_API_URL", "https://api.openai.com/v1")
    assert ConfidenceScorer.from_llm_service(_llm_service()).enabled is True


def test_empty_decision_model_turns_scoring_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(settings, "DECISION_MODEL", "")
    assert ConfidenceScorer.from_llm_service(_llm_service()).enabled is False


def test_chunked_documents_are_not_scored() -> None:
    scorer = _scorer(StubClient())
    assert should_score_confidence(scorer, ["whole document"]) is True
    assert should_score_confidence(scorer, ["part 1", "part 2"]) is False
    assert should_score_confidence(_scorer(), ["whole document"]) is False


def test_apply_scores_leaves_unscored_and_not_found_items_empty() -> None:
    data = {"A": _found("x"), "B": _found("y"), "C": _not_found()}
    apply_confidence_scores(data, {"A": 0.61, "C": 0.9, "Missing": 0.5})
    assert data["A"].confidence == 0.61
    assert data["B"].confidence is None
    assert data["C"].confidence is None


def test_extraction_item_has_no_confidence_before_scoring() -> None:
    raw = {
        "value": "RCT",
        "answer_type": "Grounded",
        "citations": [{"page_number": 1, "type": "Exact Quote"}],
        # A model that still volunteers a number is ignored: only the scorer sets confidence
        "confidence": 0.99,
    }
    item = build_extraction_item(raw, fallback_label="Design")
    assert item.value == "RCT"
    assert item.confidence is None
