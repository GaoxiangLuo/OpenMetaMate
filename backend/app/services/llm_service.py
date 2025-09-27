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
        )
        self.model = settings.LLM_MODEL
        logger.info(f"🤖 LLM Service initialized with model: {self.model}")

    async def extract_with_schema(
        self, text: str, coding_scheme: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract data using LLM with dynamic Pydantic model"""

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

        try:
            logger.debug(f"📡 Sending request to LLM (text length: {len(text)} chars)")

            completion = await self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format=pydantic_model,
                temperature=settings.TEMPERATURE,
                seed=settings.SEED,
            )

            parsed_message = completion.choices[0].message.parsed
            if parsed_message:
                result = parsed_message.model_dump(mode="python")
                logger.debug("✅ LLM extraction successful with structured output")
                return result

            logger.warning("⚠️ No parsed result from LLM")
            return {}

        except RateLimitError as e:
            logger.error(f"🚫 Rate limit error from LLM API: {e}")
            raise ExtractionError(f"API rate limit exceeded: {e}")

        except APITimeoutError as e:
            logger.error(f"⏱️ Timeout error from LLM API: {e}")
            raise ExtractionError(f"API request timed out: {e}")

        except APIError as e:
            logger.error(f"🔴 API error from LLM: {e}")
            raise ExtractionError(f"LLM API error: {e}")

        except Exception as e:
            logger.error(f"💥 Unexpected error during LLM extraction: {e}", exc_info=True)
            raise ExtractionError(f"Unexpected extraction error: {e}")
