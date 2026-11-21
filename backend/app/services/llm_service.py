import asyncio
import logging
import time
from typing import Any, Dict, List, Tuple, Union

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import ExtractionError
from app.services.pydantic_model_generator import coding_scheme_items_to_pydantic_model

logger = logging.getLogger(__name__)

# System prompt from original implementation
SYSTEM_PROMPT = """You are an expert analyst extracting structured data for educational systematic reviews and meta-analyses.

The user will provide a document rendered as text with explicit page markers. Each page is wrapped like this:
<<PAGE 12>>
...page content...
<<END PAGE 12>>

The integer in the marker always reflects the physical page index reported by the PDF reader. Never substitute page numbers found in the body text or renumber pages yourself. When you reference supporting evidence, you must use the integer from the surrounding page marker.

For every coding scheme field, return an object with:
- value: the extracted answer or null when unavailable.
- answer_type: "Grounded", "Inference", or "Not Found".
- citations: list of objects with page_number (integer) and type ("Exact Quote" or "Inference"). Provide reasoning for inference citations.
- reasoning: optional explanation when additional context is helpful.

Leave fields null when they are not present, and set answer_type to "Not Found" with an empty citations list. Prefer "Grounded" when you can reference a specific page marker. Only infer when necessary and explain the inference succinctly.

Additional domain reminders:
1. If participant age is not explicit, infer from grade level when possible but never report the grade itself as age.
2. If both original and post-attrition sample sizes are present, report the post-attrition value.
3. Treat boolean multi-label options independently (e.g., grade 3 and grade 4 can both be true).
"""

GPT_5_SYSTEM_PROMPT = """Developer: # Role
You are an expert analyst specializing in extracting structured data for educational systematic reviews and meta-analyses.

Begin with a concise checklist (3-7 bullets) of what you will do; keep items conceptual, not implementation-level.

# Input Format
The user will provide documents rendered as plaintext, segmented with explicit page markers:
```
<<PAGE 12>>
...page content...
<<END PAGE 12>>
```
- The integer in the marker always represents the physical page index as reported by the PDF reader.
- Never substitute or interpret page numbers found within the body text, and never renumber pages.
- When referencing supporting evidence, always use the integer from the respective PAGE marker.

# Extraction Output for Each Coding Scheme Field
Return an object with:
- `value`: The extracted answer, or null if unavailable.
- `answer_type`: One of "Grounded" (specifically referenced), "Inference" (reasoned from context), or "Not Found".
- `citations`: List of objects, each containing:
    - `page_number` (integer, from the PAGE marker)
    - `type` (either "Exact Quote" or "Inference"). Provide reasoning for any inference citations.
- `reasoning` (optional): Additional explanation for context, especially when valuable for understanding.

After each extraction, validate that the output strictly adheres to the required object structure and logic; if issues are detected, self-correct and retry.

- If a field is absent, set `value` to null, `answer_type` to "Not Found", and leave `citations` empty.
- Prefer "Grounded" answers when a specific PAGE marker can be referenced.
- Only use "Inference" when direct evidence is lacking; briefly explain the basis for inference.

# Domain Reminders
1. If participant age is not stated, infer from grade level when possible but never report the grade itself as age.
2. If both original and post-attrition sample sizes are provided, report the post-attrition figure.
3. For boolean multi-label fields (e.g., grade 3 and grade 4), treat each option as separately true or false.
"""


_CHECKLIST_INSTRUCTION = """Begin with a concise checklist (3-7 bullets) of what you will do; keep items conceptual, not implementation-level.

"""
# GPT-6 follows the checklist instruction literally and writes the bullets ahead of the
# JSON, which breaks structured output parsing, so its prompt drops that instruction.
GPT_6_SYSTEM_PROMPT = GPT_5_SYSTEM_PROMPT.replace(_CHECKLIST_INSTRUCTION, "")

CLAUDE_MAX_TOKENS = 64_000
# Claude's structured outputs refuse to compile schemas beyond roughly 30 coding scheme
# fields ("Schema is too complex for compilation"), so larger schemes are split across
# several requests whose results are merged back into one object.
CLAUDE_FIELDS_PER_REQUEST = 20


def _claude_output_schema(pydantic_model) -> Dict[str, Any]:
    """Build the structured output JSON schema sent to Claude for an extraction model.

    Every coding scheme field is Optional in the Pydantic model, which makes each one a
    nullable union in JSON schema, and Claude caps a request at 16 union parameters. The
    groups are rewritten to require every field as a plain object; "Not Found" is still
    expressed inside the field object itself.
    """
    schema = pydantic_model.model_json_schema()
    fixed = {"LLMExtractionField", "LLMCitation"}
    groups = [schema] + [d for name, d in schema.get("$defs", {}).items() if name not in fixed]

    for group in groups:
        properties = group.get("properties", {})
        for name, prop in properties.items():
            non_null = [o for o in prop.get("anyOf", []) if o.get("type") != "null"]
            if len(non_null) == 1:
                properties[name] = {
                    **non_null[0],
                    **{k: v for k, v in prop.items() if k == "description"},
                }
        group["required"] = list(properties)

    return anthropic.transform_schema(schema)


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """Merge nested group dictionaries from one partial extraction into another."""
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _should_failover(error: Exception) -> bool:
    """Return True when the next provider in the chain has a chance of succeeding."""
    if isinstance(error, (openai.APITimeoutError, anthropic.APITimeoutError)):
        return False  # each attempt already waited the full timeout
    if isinstance(error, (openai.APIConnectionError, anthropic.APIConnectionError)):
        return True
    if isinstance(error, (openai.APIStatusError, anthropic.APIStatusError)):
        # Key-specific failures (bad/blocked key, rate limit, quota) and server errors
        return error.status_code in (401, 403, 429) or error.status_code >= 500
    return False


class LLMService:
    """LLM integration service with structured output and provider failover"""

    def __init__(self):
        if not settings.LLM_API_KEY:
            logger.error("🔑❌ LLM API key not configured")
            raise ValueError("LLM API key is required")

        self.model = settings.LLM_MODEL
        # Ordered failover chain: every LLM_API_URL key first, then Claude
        self.providers: List[Tuple[str, Union[AsyncOpenAI, AsyncAnthropic]]] = []

        openai_keys = (
            ("primary API", settings.LLM_API_KEY),
            ("backup API", settings.BACKUP_LLM_API_KEY),
        )
        for name, api_key in openai_keys:
            if not api_key:
                continue
            client = AsyncOpenAI(
                base_url=settings.LLM_API_URL,  # Same URL and model, different key
                api_key=api_key,
                timeout=300.0,  # 5 minute timeout for LLM API calls (complex PDFs need time)
                max_retries=2,  # Retry failed requests twice for transient errors
            )
            self.providers.append((name, client))

        if settings.CLAUDE_API_KEY:
            claude_client = AsyncAnthropic(
                api_key=settings.CLAUDE_API_KEY, timeout=300.0, max_retries=2
            )
            name = f"Claude API ({settings.CLAUDE_MODEL})"
            self.providers.append((name, claude_client))

        logger.info(
            f"🤖 LLM Service initialized with model: {self.model} (timeout: 300s, retries: 2)"
        )
        if len(self.providers) > 1:
            chain = " → ".join(name for name, _ in self.providers)
            logger.info(f"🔄 Automatic failover enabled: {chain}")
        else:
            logger.info("⚠️ Backup API not configured - no automatic failover")

    async def _call_llm(
        self, client: AsyncOpenAI, provider_name: str, pydantic_model, text: str
    ) -> Dict[str, Any]:
        """Call the OpenAI-compatible API with the given client"""
        start_time = time.time()

        use_responses_api = settings.use_responses_api(self.model)
        if self.model.lower().startswith("gpt-6"):
            system_prompt = GPT_6_SYSTEM_PROMPT
        elif use_responses_api:
            system_prompt = GPT_5_SYSTEM_PROMPT
        else:
            system_prompt = SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        temperature = settings.resolve_temperature(self.model)
        parsed_message = None

        responses_resource = getattr(client, "responses", None)
        if use_responses_api and responses_resource is not None:
            response_payload = {
                "model": self.model,
                "input": messages,
                "text_format": pydantic_model,
                "text": {"verbosity": "low"},
                "reasoning": {"effort": "none"},
            }

            if temperature is not None:
                response_payload["temperature"] = temperature

            parse_callable = getattr(responses_resource, "parse", None)
            if parse_callable is None:
                logger.warning(
                    "⚠️ Responses API client detected without parse(); falling back to chat completions"
                )
            else:
                response = await parse_callable(**response_payload)
                parsed_message = getattr(response, "output_parsed", None)
                if parsed_message is None:
                    parsed_message = getattr(response, "parsed", None)

        if parsed_message is None:
            if use_responses_api and responses_resource is None:
                logger.warning(
                    "⚠️ Responses API not available in current OpenAI client; falling back to chat completions"
                )

            request_payload = {
                "model": self.model,
                "messages": messages,
                "response_format": pydantic_model,
                "seed": settings.SEED,
            }

            if temperature is not None:
                request_payload["temperature"] = temperature

            completion = await client.chat.completions.parse(**request_payload)
            parsed_message = completion.choices[0].message.parsed

        duration = time.time() - start_time

        if parsed_message:
            result = parsed_message.model_dump(mode="python")
            logger.info(
                f"✅ [STAGE 4/6] LLM extraction completed ({provider_name}) in {duration:.1f}s"
            )
            return result

        logger.warning(f"⚠️ No parsed result from LLM ({provider_name})")
        return {}

    async def _call_claude(
        self,
        client: AsyncAnthropic,
        provider_name: str,
        pydantic_model,
        coding_scheme: List[Dict[str, Any]],
        text: str,
    ) -> Dict[str, Any]:
        """Call the Claude API (native Messages API with structured output)"""
        start_time = time.time()

        included = [
            item
            for item in coding_scheme
            if item.get("include_in_extraction", item.get("includeInExtraction", False))
        ]
        size = CLAUDE_FIELDS_PER_REQUEST
        batches = [included[i : i + size] for i in range(0, len(included), size)]
        parts = await asyncio.gather(
            *(self._claude_request(client, batch, text) for batch in batches)
        )

        merged: Dict[str, Any] = {}
        for part in parts:
            _deep_merge(merged, part)
        if not merged:
            logger.warning(f"⚠️ No parsed result from LLM ({provider_name})")
            return {}

        result = pydantic_model.model_validate(merged).model_dump(mode="python")
        duration = time.time() - start_time
        logger.info(
            f"✅ [STAGE 4/6] LLM extraction completed ({provider_name}, "
            f"{len(batches)} request(s)) in {duration:.1f}s"
        )
        return result

    async def _claude_request(
        self, client: AsyncAnthropic, batch: List[Dict[str, Any]], text: str
    ) -> Dict[str, Any]:
        """Extract one batch of coding scheme fields with Claude"""
        batch_model = coding_scheme_items_to_pydantic_model(batch)
        if batch_model is None:
            raise ExtractionError("Failed to create extraction model from coding scheme")

        # Streamed so long extractions are not cut off by an idle HTTP connection
        async with client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            thinking={"type": "disabled"},
            output_config={
                "format": {"type": "json_schema", "schema": _claude_output_schema(batch_model)}
            },
        ) as stream:
            message = await stream.get_final_message()

        if message.stop_reason == "refusal":
            raise ExtractionError("Claude declined to process this document")
        if message.stop_reason == "max_tokens":
            raise ExtractionError("Claude response was cut off before the extraction finished")

        output_text = "".join(b.text for b in message.content if b.type == "text")
        if not output_text:
            return {}
        return batch_model.model_validate_json(output_text).model_dump(mode="python")

    async def extract_with_schema(
        self, text: str, coding_scheme: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract data using LLM with dynamic Pydantic model and automatic failover"""

        if not text or not text.strip():
            logger.warning("⚠️ Empty text provided for extraction")
            return {}

        if not coding_scheme:
            logger.warning("⚠️ Empty coding scheme provided")
            return {}

        pydantic_model = coding_scheme_items_to_pydantic_model(coding_scheme)
        if pydantic_model is None:
            logger.error("❌ Failed to create Pydantic model from coding scheme")
            raise ExtractionError("Failed to create extraction model from coding scheme")

        failures: List[str] = []
        for index, (name, client) in enumerate(self.providers):
            try:
                logger.info(f"🤖 [STAGE 4/6] Starting LLM extraction ({name})...")
                if isinstance(client, AsyncAnthropic):
                    return await self._call_claude(
                        client, name, pydantic_model, coding_scheme, text
                    )
                return await self._call_llm(client, name, pydantic_model, text)

            except ExtractionError:
                raise

            except (openai.APITimeoutError, anthropic.APITimeoutError) as e:
                logger.error(f"❌ [STAGE 4/6] {name} timeout: {e}")
                raise ExtractionError(f"API request timed out: {e}")

            except Exception as e:
                is_last = index == len(self.providers) - 1
                if isinstance(e, (openai.RateLimitError, anthropic.RateLimitError)):
                    summary = "API rate limit exceeded (429)"
                else:
                    summary = f"LLM API error: {e}"
                logger.error(f"❌ [STAGE 4/6] {name} failed: {summary}", exc_info=is_last)
                failures.append(f"{name}: {summary}")

                if not _should_failover(e):
                    raise ExtractionError(summary)
                if is_last:
                    if len(failures) == 1:
                        logger.error("❌ [STAGE 4/6] No backup API configured - cannot retry")
                        raise ExtractionError(summary)
                    raise ExtractionError(f"All LLM APIs failed. {'; '.join(failures)}")

                logger.info(f"🔄 [STAGE 4/6] Retrying with {self.providers[index + 1][0]}...")

        raise ExtractionError("No LLM API configured")
