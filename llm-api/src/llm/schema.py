"""The contract. Written before the model was ever called."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["billing", "bug", "feature", "other"]
Urgency = Literal["low", "normal", "high"]


class TriageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")   # a surprise extra field is a failure

    category: Category
    urgency: Urgency
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)
