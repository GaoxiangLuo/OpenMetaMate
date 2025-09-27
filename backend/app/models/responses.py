from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Citation(BaseModel):
    """Citation metadata that anchors an extraction back to the PDF."""

    model_config = ConfigDict(populate_by_name=True)

    page_number: int = Field(
        alias="pageNumber",
        ge=1,
        description="1-indexed page number that contains the supporting evidence.",
    )
    citation_type: Literal["Exact Quote", "Inference"] = Field(
        alias="type",
        description="Indicates whether the citation is an exact quote or an inference.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Short explanation required when the citation type is Inference.",
    )

    @model_validator(mode="after")
    def _validate_reasoning(self) -> "Citation":
        if self.citation_type == "Inference" and not self.reasoning:
            raise ValueError("Inference citations must include reasoning text.")
        return self


class ExtractionResultItem(BaseModel):
    """Individual extraction result enriched with provenance data."""

    model_config = ConfigDict(populate_by_name=True)

    value: Union[str, float, bool, None] = Field(
        default=None,
        description="Extracted value for the coding scheme item or null when unavailable.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Optional confidence score between 0 and 1 for the extracted value.",
    )
    answer_type: Literal["Grounded", "Inference", "Not Found"] = Field(
        alias="answerType",
        description="Describes whether the answer is grounded in the text, inferred, or not found.",
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Supporting citations linking the answer to specific pages in the PDF.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional explanation provided by the LLM when the answer required inference.",
    )

    @model_validator(mode="after")
    def _enforce_invariants(self) -> "ExtractionResultItem":
        if self.answer_type == "Not Found":
            if self.citations:
                raise ValueError("Citations must be empty when answerType is 'Not Found'.")
            self.reasoning = None
            self.value = "Not Found"
            self.confidence = None
        else:
            if not self.citations:
                raise ValueError(
                    "At least one citation is required when answerType is not 'Not Found'."
                )
        return self


class ExtractionResponse(BaseModel):
    """Response model for extraction requests."""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(
        alias="fileName",
        description="Original name of the processed PDF file.",
    )
    extracted_data: Dict[str, ExtractionResultItem] = Field(
        alias="extractedData",
        description="Mapping of coding scheme labels to their extracted results.",
    )
    status: Literal["success", "error"] = Field(
        description="Indicates whether the extraction succeeded or failed.",
    )
    message: str = Field(
        description="Human-readable summary describing the outcome of the extraction.",
    )
