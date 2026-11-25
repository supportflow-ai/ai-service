"""Nơi duy nhất chọn và dựng provider theo cấu hình (Ports & Adapters).

Thêm provider mới: triển khai port trong `adapters/`, rồi đăng ký ở đây. `main.py` chỉ gọi
các hàm dựng này, không tự import adapter.
"""

from __future__ import annotations

from supportflow_ai.adapters.classifiers.noop import NoOpClassifier
from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.application.embedding.index import PrepareKnowledgeIndex
from supportflow_ai.config import Settings
from supportflow_ai.ports.classifier import TicketClassifier


def build_classifier(settings: Settings) -> TicketClassifier:
    if settings.classifier_provider == "rule":
        return RuleBasedClassifier()
    if settings.classifier_provider == "noop":
        return NoOpClassifier()
    if settings.classifier_provider == "ml":
        # Import muộn: chỉ nạp khi provider ml được chọn. Artifact lỗi thì provider chưa sẵn sàng.
        from supportflow_ai.adapters.classifiers.ml.provider import MlClassifier

        return MlClassifier(
            model_dir=settings.classifier_model_dir,
            allow_dev_stub=settings.allow_dev_stub,
            max_concurrency=settings.classifier_max_concurrency,
            max_queue=settings.classifier_max_queue,
            queue_timeout_s=settings.classifier_queue_timeout_s,
        )
    # Không rơi về NoOp im lặng: giá trị lạ là lỗi cấu hình.
    raise ValueError(f"Unknown classifier provider: {settings.classifier_provider!r}")


def build_knowledge_index_preparer(settings: Settings) -> PrepareKnowledgeIndex | None:
    """Trả `None` khi embedding chưa bật; route và health khi đó trả 503 có kiểm soát."""
    if settings.embedding_provider != "local-e5":
        return None
    # Import muộn: chỉ image `embeddings` có sentence-transformers và torch.
    from supportflow_ai.adapters.embedders.local_e5 import LocalE5Embedder
    from supportflow_ai.adapters.markdown_chunker import DeterministicMarkdownChunker

    embedder = LocalE5Embedder(settings.embedding_cache_dir)
    return PrepareKnowledgeIndex(DeterministicMarkdownChunker(embedder), embedder)
