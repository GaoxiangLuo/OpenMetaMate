"""Unit tests for API response models enforcing extraction invariants."""

import pytest
from pydantic import ValidationError

from app.models.responses import Citation, ExtractionResultItem


def test_citation_requires_reasoning_for_inference() -> None:
    """Inference citations must include a reasoning string."""

    with pytest.raises(ValidationError):
        Citation(page_number=1, citation_type="Inference")

    citation = Citation(
        page_number=2,
        citation_type="Inference",
        reasoning="Inference derived from study overview on this page.",
    )
    assert citation.reasoning is not None


def test_not_found_item_disallows_citations() -> None:
    """Extraction items marked as not found cannot include citations."""

    with pytest.raises(ValidationError):
        ExtractionResultItem(
            value="Not Found",
            confidence=None,
            answer_type="Not Found",
            citations=[
                Citation(
                    page_number=1,
                    citation_type="Exact Quote",
                )
            ],
        )


def test_grounded_answer_requires_citation() -> None:
    """Grounded answers must include at least one citation."""

    citation = Citation(
        page_number=3,
        citation_type="Exact Quote",
    )
    item = ExtractionResultItem(
        value="Sample size of 120",
        confidence=0.84,
        answer_type="Grounded",
        citations=[citation],
    )
    assert item.answer_type == "Grounded"
    assert item.citations[0].page_number == 3
