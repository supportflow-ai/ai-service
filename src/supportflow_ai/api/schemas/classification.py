from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, model_validator

CategoryValue = Literal[
    "ACC", "NET", "VPN", "MAIL", "SW", "HW", "PRINT", "ACCESS", "EQUIP", "SEC", "OTHER"
]
LevelValue = Literal["Low", "Medium", "High"]
FieldValue = Literal["category", "impact", "urgency"]


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_alias=True, validate_by_name=False)

    request_id: UUID = Field(alias="requestId")
    ticket_id: UUID = Field(alias="ticketId")
    ticket_revision: int = Field(alias="ticketRevision", ge=0, strict=True)
    input_hash: str = Field(alias="inputHash", pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ClassificationSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: FieldValue
    value: str
    score: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_field_value(self) -> ClassificationSuggestion:
        categories = {
            "ACC", "NET", "VPN", "MAIL", "SW", "HW", "PRINT", "ACCESS", "EQUIP", "SEC", "OTHER"
        }
        levels = {"Low", "Medium", "High"}

        if self.field == "category" and self.value not in categories:
            raise ValueError("Unknown category.")
        if self.field in {"impact", "urgency"} and self.value not in levels:
            raise ValueError("Unknown impact/urgency value.")
        return self


class ClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_alias=True, validate_by_name=False)

    request_id: UUID = Field(alias="requestId")
    ticket_id: UUID = Field(alias="ticketId")
    ticket_revision: int = Field(alias="ticketRevision", ge=0, strict=True)
    input_hash: str = Field(alias="inputHash", pattern=r"^[a-f0-9]{64}$")
    suggestions: list[ClassificationSuggestion] = Field(max_length=3)

    @model_validator(mode="after")
    def validate_unique_fields(self) -> ClassificationResponse:
        fields = [item.field for item in self.suggestions]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate suggestion fields are not allowed.")
        return self
