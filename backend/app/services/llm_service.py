import logging
from typing import Any, Dict, List

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.core.exceptions import ExtractionError
from app.services.pydantic_model_generator import (
    coding_scheme_items_to_pydantic_model,
    flatten_json,
)

logger = logging.getLogger(__name__)

# System prompt from original implementation
SYSTEM_PROMPT = """You are an expert at identifying data elements for educational systematic reviews and meta-analyses in the text.

Only extract relevant data elements from the text based on the description of each element.

If you cannot find the relevant data element in the text, do not extract it and leave it as null since the all elements defined in pydantic model are optional.

Additional requirements:

1. If the age of participant is NOT present, infer age from grade-level if possible, but don't use grade-level directly as age.

2. If the study reports sample size after attrition, use the number after attrition is accounted for, instead of the original sample size.

3. Many boolean type extraction are multi-label classification. For example, the population could involve both grade 3 and grade 4 students. In this case, the grade 3 and 4 should both be true while others are false. Use the context among extraction elements.
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

            # Extract the parsed result
            if completion.choices[0].message.parsed:
                result = completion.choices[0].message.parsed.model_dump(mode="json")
                # Flatten the nested structure
                flattened_result = flatten_json(result)

                extracted_fields = len([v for v in flattened_result.values() if v is not None])
                logger.debug(f"✅ LLM extraction successful: {extracted_fields} fields extracted")

                return flattened_result
            else:
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
