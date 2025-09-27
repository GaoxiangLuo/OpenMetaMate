from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CodingSchemeItem(BaseModel):
    """Individual coding scheme item describing a single data element."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique identifier for the coding scheme item.")
    name: str = Field(description="Human readable label for the data element.")
    data_type: Literal["Text", "Numeric", "Boolean"] = Field(
        alias="dataType",
        description="Data type that the extraction should produce for this element.",
    )
    description: str = Field(
        description="Guidance shown to the LLM describing what to extract for this element.",
    )
    include_in_extraction: bool = Field(
        alias="includeInExtraction",
        description="Flag indicating whether the element should be extracted in the current run.",
    )
