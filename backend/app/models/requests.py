from typing import Literal

from pydantic import BaseModel, Field


class CodingSchemeItem(BaseModel):
    """Individual coding scheme item"""

    id: str
    name: str
    data_type: Literal["Text", "Numeric", "Boolean"] = Field(alias="dataType")
    description: str
    include_in_extraction: bool = Field(alias="includeInExtraction")

    class Config:
        populate_by_name = True
