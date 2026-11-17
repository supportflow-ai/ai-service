from __future__ import annotations

from typing import Protocol

from supportflow_ai.domain.classification import ClassificationPrediction


class TicketClassifier(Protocol):
    @property
    def name(self) -> str:
        """Tên provider trong cấu hình (`rule`, `noop`, ...)."""
        ...

    @property
    def ready(self) -> bool:
        """`True` khi provider phục vụ được; `/health/ready` trả 503 khi `False`.

        Provider dùng artifact phải tải và kiểm SHA lúc khởi động, không giả lập dự đoán khi lỗi.
        """
        ...

    @property
    def model_version(self) -> str | None:
        """Phiên bản artifact mô hình để truy vết; `None` khi provider không dùng artifact."""
        ...

    async def classify(self, *, title: str, description: str) -> ClassificationPrediction: ...
