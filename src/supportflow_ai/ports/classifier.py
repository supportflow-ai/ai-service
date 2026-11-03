from __future__ import annotations

from typing import Protocol

from supportflow_ai.domain.classification import ClassificationPrediction


class TicketClassifier(Protocol):
    @property
    def name(self) -> str: ...

    async def classify(self, *, title: str, description: str) -> ClassificationPrediction: ...
