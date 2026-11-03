from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from supportflow_ai.domain.classification import ClassificationPrediction


@dataclass(frozen=True, slots=True)
class ClassificationCommand:
    request_id: UUID
    ticket_id: UUID
    ticket_revision: int
    input_hash: str
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    request_id: UUID
    ticket_id: UUID
    ticket_revision: int
    input_hash: str
    prediction: ClassificationPrediction
