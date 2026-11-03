from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class Category(StrEnum):
    ACC = "ACC"
    NET = "NET"
    VPN = "VPN"
    MAIL = "MAIL"
    SW = "SW"
    HW = "HW"
    PRINT = "PRINT"
    ACCESS = "ACCESS"
    EQUIP = "EQUIP"
    SEC = "SEC"
    OTHER = "OTHER"


class Impact(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Urgency(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class SuggestionField(StrEnum):
    CATEGORY = "category"
    IMPACT = "impact"
    URGENCY = "urgency"


AllowedValue = Category | Impact | Urgency


@dataclass(frozen=True, slots=True)
class Suggestion:
    field: SuggestionField
    value: AllowedValue
    score: float | None = None

    def __post_init__(self) -> None:
        expected_type = {
            SuggestionField.CATEGORY: Category,
            SuggestionField.IMPACT: Impact,
            SuggestionField.URGENCY: Urgency,
        }[self.field]
        if not isinstance(self.value, expected_type):
            raise ValueError(f"{self.field} requires {expected_type.__name__}.")
        if self.score is not None and (not isfinite(self.score) or not 0.0 <= self.score <= 1.0):
            raise ValueError("score must be finite and in [0, 1].")


@dataclass(frozen=True, slots=True)
class ClassificationPrediction:
    suggestions: tuple[Suggestion, ...]

    def __post_init__(self) -> None:
        if len(self.suggestions) > 3:
            raise ValueError("Contract v1 allows at most three suggestions.")
        fields = [item.field for item in self.suggestions]
        if len(fields) != len(set(fields)):
            raise ValueError("Contract v1 allows at most one suggestion per field.")
