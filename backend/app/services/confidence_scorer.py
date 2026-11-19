"""Confidence scores for extracted values, from OpenAI's Decisions API.

After extraction, the document is sent once more together with one yes/no question per
extracted value: "is this value correct for this field?", or for Boolean fields "should this
field be True?". The decision model generates no text; it returns a probability per question,
from which the confidence shown to the user is derived.

The extraction's own reasoning is deliberately not shown to the decision model: in testing it
raised the score of wrong values as much as right ones.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.requests import CodingSchemeItem
from app.models.responses import ExtractionResultItem
from app.services.llm_service import LLMService, _should_failover

logger = logging.getLogger(__name__)

DECISIONS_PATH = "/decisions"
MAX_QUESTIONS_PER_REQUEST = 400
# Kept short so a slow scorer cannot hold up a finished extraction for long
REQUEST_TIMEOUT_SECONDS = 45.0

SCORER_INSTRUCTIONS = """You are checking values that were extracted from the document below \
for an educational systematic review. Each question names a field, gives its definition and \
the value that was extracted, or asks how the field should be coded. Judge each one \
according to the document.

Rules the extraction followed:
1. If participant age is not explicit, it may be inferred from grade level, but the grade \
itself is never reported as age.
2. If both original and post-attrition sample sizes are present, the post-attrition value \
is the correct one.
3. Boolean multi-label options are independent (e.g., grade 3 and grade 4 can both be true).
"""


ExtractedValue = Union[str, float, bool, None]


def _format_value(value: ExtractedValue) -> str:
    """Render an extracted value the way a reviewer would read it."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _as_boolean(value: ExtractedValue) -> Optional[bool]:
    """Return the extracted answer of a Boolean field, or None when it is not true/false."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def asks_field_directly(item: CodingSchemeItem, value: ExtractedValue) -> bool:
    """Boolean fields are asked directly instead of having their extracted answer checked.

    "Is the answer False correct?" is a double negative the decision model handles poorly.
    Asking whether the field should be True and reading the answer from that side gave fewer
    false alarms in validation.
    """
    return item.data_type == "Boolean" and _as_boolean(value) is not None


def build_question(index: int, item: CodingSchemeItem, value: ExtractedValue) -> Dict:
    """Build the yes/no question that scores one extracted value."""
    header = f"Field: {item.name}\nDefinition: {item.description}\n"
    if asks_field_directly(item, value):
        claim = "According to the document and this definition, the field should be coded True."
    else:
        claim = (
            f"Extracted value: {_format_value(value)}\n"
            "The extracted value is correct for this field: it is either stated in the "
            "document or follows from the document by the calculation or coding rule in the "
            "definition."
        )
    return {"type": "predicate", "name": f"q{index}", "instructions": header + claim}


def to_confidence(item: CodingSchemeItem, value: ExtractedValue, probability: float) -> float:
    """Turn the model's probability into confidence in the extracted value."""
    # A direct Boolean question returns P(True); an extracted False is supported by 1 - P
    if asks_field_directly(item, value) and _as_boolean(value) is False:
        probability = 1 - probability
    return round(float(probability), 3)


class ConfidenceScorer:
    """Scores extracted values with a decision model. Never raises: no score on failure."""

    def __init__(self, clients: Sequence[Tuple[str, Any]], model: str):
        self.clients = list(clients)
        self.model = model

    @classmethod
    def from_llm_service(cls, llm_service: LLMService) -> "ConfidenceScorer":
        """Reuse the OpenAI keys of the extraction service, in the same failover order."""
        if not settings.decision_scoring_enabled():
            return cls([], settings.DECISION_MODEL)
        clients = [
            (name, client)
            for name, client in llm_service.providers
            if isinstance(client, AsyncOpenAI)
        ]
        return cls(clients, settings.DECISION_MODEL)

    @property
    def enabled(self) -> bool:
        return bool(self.clients and self.model)

    async def score(
        self,
        text: str,
        coding_scheme: Sequence[CodingSchemeItem],
        extracted_data: Dict[str, ExtractionResultItem],
    ) -> Dict[str, float]:
        """Return a confidence between 0 and 1 for each found value, keyed by field name.

        Fields that are "Not Found" are not sent. Fields the model declines to answer, and
        every field when the call fails, are left out of the result.
        """
        if not self.enabled:
            return {}

        targets: List[CodingSchemeItem] = []
        for item in coding_scheme:
            result = extracted_data.get(item.name)
            if result is not None and result.answer_type != "Not Found":
                targets.append(item)
        if not targets:
            return {}

        questions = [
            build_question(index, item, extracted_data[item.name].value)
            for index, item in enumerate(targets)
        ]

        start_time = time.time()
        try:
            answers = await self._ask(text, questions)
        except Exception as e:
            logger.warning(f"⚠️ [STAGE 5/6] Confidence scoring skipped: {e}")
            return {}

        scores: Dict[str, float] = {}
        for index, item in enumerate(targets):
            probability = answers.get(f"q{index}")
            if isinstance(probability, (int, float)) and 0 <= probability <= 1:
                value = extracted_data[item.name].value
                scores[item.name] = to_confidence(item, value, probability)

        logger.info(
            f"✅ [STAGE 5/6] Confidence scored for {len(scores)}/{len(targets)} values "
            f"in {time.time() - start_time:.1f}s"
        )
        return scores

    async def _ask(self, text: str, questions: List[Dict]) -> Dict[str, Any]:
        """Send the questions, trying the next key when the failure is key-specific."""
        for index, (name, client) in enumerate(self.clients):
            try:
                return await self._request(client, text, questions)
            except Exception as e:
                is_last = index == len(self.clients) - 1
                if is_last or not _should_failover(e):
                    raise
                logger.info(f"🔄 [STAGE 5/6] Confidence scoring failed on {name}, trying next key")
        return {}

    async def _request(self, client: Any, text: str, questions: List[Dict]) -> Dict[str, Any]:
        """Call the Decisions API and return probabilities keyed by question name."""
        # The pinned SDK has no decisions resource, so the request goes through the
        # client's generic POST, which still applies its auth, base URL and error types.
        bounded = client.with_options(timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)
        probabilities: Dict[str, Any] = {}
        for offset in range(0, len(questions), MAX_QUESTIONS_PER_REQUEST):
            body = {
                "model": self.model,
                "input": [
                    {"role": "developer", "content": SCORER_INSTRUCTIONS},
                    {"role": "user", "content": text},
                ],
                "questions": questions[offset : offset + MAX_QUESTIONS_PER_REQUEST],
            }
            response = await bounded.post(DECISIONS_PATH, body=body, cast_to=httpx.Response)
            for answer in response.json().get("answers", []):
                # A refused question comes back without a probability
                if answer.get("type") == "predicate":
                    probabilities[answer.get("name")] = answer.get("probability")
        return probabilities
