from typing import Dict, Literal, Optional, Union

from pydantic import BaseModel, Field


class ExtractionResultItem(BaseModel):
    """Individual extraction result"""

    value: Union[str, float, bool, None]
    confidence: Optional[float] = Field(None, ge=0, le=1)


class ExtractionResponse(BaseModel):
    """Response model for extraction"""

    file_name: str = Field(alias="fileName")
    extracted_data: Dict[str, ExtractionResultItem] = Field(alias="extractedData")
    status: Literal["success", "error"]
    message: str

    class Config:
        populate_by_name = True
