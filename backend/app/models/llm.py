"""Pydantic models that define the structured response schema expected from the LLM."""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class LLMCitation(BaseModel):
    """Citation emitted by the LLM for a specific extraction field."""

    model_config = ConfigDict(populate_by_name=True)

    page_number: Optional[int] = Field(
        default=None,
        description="1-indexed page number referenced in the annotated prompt text.",
    )
    citation_type: Optional[Literal["Exact Quote", "Inference"]] = Field(
        default=None,
        description="Whether the citation refers to an exact quote or an inferred answer.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Short justification for inference citations; leave null for exact quotes.",
    )


class LLMExtractionField(BaseModel):
    """Structured response for each coding scheme field produced by the LLM."""

    model_config = ConfigDict(populate_by_name=True)

    value: Optional[Union[str, float, bool]] = Field(
        default=None,
        description="Value extracted directly from the document for the requested field.",
    )
    answer_type: Optional[Literal["Grounded", "Inference", "Not Found"]] = Field(
        default=None,
        description="Indicates if the answer is grounded in the text, inferred, or not present.",
    )
    citations: List[LLMCitation] = Field(
        default_factory=list,
        description="References that point to the page numbers where supporting evidence appears.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Optional self-reported confidence score between 0 and 1.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional free-form reasoning explaining how the value was determined.",
    )
