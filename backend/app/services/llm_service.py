import logging
from typing import Any, Dict, List

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

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
- confidence: optional float between 0 and 1.
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
- `confidence` (optional): Float between 0 and 1.
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


class LLMService:
    """LLM integration service with structured output"""

    def __init__(self):
        # Initialize async LLM client with only the API key
        if not settings.LLM_API_KEY:
            logger.error("🔑❌ LLM API key not configured")
            raise ValueError("LLM API key is required")

        self.client = AsyncOpenAI(
            base_url=settings.LLM_API_URL,
            api_key=settings.LLM_API_KEY,
            timeout=300.0,  # 5 minute timeout for LLM API calls (complex PDFs need time)
            max_retries=2,  # Retry failed requests twice for transient errors
        )
        self.model = settings.LLM_MODEL

        # Initialize backup client if backup API key is configured
        self.backup_client = None
        if settings.BACKUP_LLM_API_KEY:
            self.backup_client = AsyncOpenAI(
                base_url=settings.LLM_API_URL,  # Same URL and model, different key
                api_key=settings.BACKUP_LLM_API_KEY,
                timeout=300.0,
                max_retries=2,
            )
            logger.info(
                f"🤖 LLM Service initialized with model: {self.model} (timeout: 300s, retries: 2)"
            )
            logger.info("🔄 Backup API enabled for automatic failover")
        else:
            logger.info(
                f"🤖 LLM Service initialized with model: {self.model} (timeout: 300s, retries: 2)"
            )
            logger.info("⚠️ Backup API not configured - no automatic failover")

    async def _call_llm(
        self, client: AsyncOpenAI, pydantic_model, messages, provider_name: str
    ) -> Dict[str, Any]:
        """Helper method to call LLM API with given client"""
        import time

        start_time = time.time()

        temperature = settings.resolve_temperature(self.model)
        use_responses_api = settings.use_responses_api(self.model)
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

        system_prompt = (
            GPT_5_SYSTEM_PROMPT if settings.use_responses_api(self.model) else SYSTEM_PROMPT
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        # Try primary API first
        try:
            logger.info("🤖 [STAGE 4/6] Starting LLM extraction (primary API)...")
            return await self._call_llm(self.client, pydantic_model, messages, "primary API")

        except RateLimitError as e:
            # 429 error - try backup API if available
            logger.error("❌ [STAGE 4/6] Primary LLM API failed: Rate limit error (429)")

            if self.backup_client:
                logger.info("🔄 [STAGE 4/6] Retrying with backup API...")
                try:
                    return await self._call_llm(
                        self.backup_client, pydantic_model, messages, "backup API"
                    )
                except Exception as backup_error:
                    logger.error(f"❌ [STAGE 4/6] Backup API also failed: {backup_error}")
                    raise ExtractionError(
                        f"Both primary and backup APIs failed. Primary: Rate limit. Backup: {backup_error}"
                    )
            else:
                logger.error("❌ [STAGE 4/6] No backup API configured - cannot retry")
                raise ExtractionError(f"API rate limit exceeded: {e}")

        except APITimeoutError as e:
            logger.error(f"❌ [STAGE 4/6] Primary API timeout: {e}")
            raise ExtractionError(f"API request timed out: {e}")

        except APIError as e:
            # Server errors (5xx) - try backup if available
            error_message = str(e)
            if "50" in error_message:  # 500-599 server errors
                logger.error(f"❌ [STAGE 4/6] Primary API server error: {e}")

                if self.backup_client:
                    logger.info("🔄 [STAGE 4/6] Retrying with backup API...")
                    try:
                        return await self._call_llm(
                            self.backup_client, pydantic_model, messages, "backup API"
                        )
                    except Exception as backup_error:
                        logger.error(f"❌ [STAGE 4/6] Backup API also failed: {backup_error}")
                        raise ExtractionError(
                            f"Both primary and backup APIs failed. Primary: {e}. Backup: {backup_error}"
                        )
                else:
                    logger.error("❌ [STAGE 4/6] No backup API configured - cannot retry")
                    raise ExtractionError(f"LLM API error: {e}")
            else:
                # Client error (4xx) - don't retry with backup
                logger.error(f"❌ [STAGE 4/6] Primary API client error: {e}")
                raise ExtractionError(f"LLM API error: {e}")

        except Exception as e:
            logger.error(
                f"❌ [STAGE 4/6] Unexpected error during LLM extraction: {e}", exc_info=True
            )
            raise ExtractionError(f"Unexpected extraction error: {e}")
