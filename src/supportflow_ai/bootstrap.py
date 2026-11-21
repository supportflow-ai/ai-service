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
    return NoOpClassifier()


def build_knowledge_index_preparer(settings: Settings) -> PrepareKnowledgeIndex | None:
    """Trả `None` khi embedding chưa bật; route và health khi đó trả 503 có kiểm soát."""
    if settings.embedding_provider != "local-e5":
        return None
    # Import muộn: chỉ image `embeddings` có sentence-transformers và torch.
    from supportflow_ai.adapters.embedders.local_e5 import LocalE5Embedder
    from supportflow_ai.adapters.markdown_chunker import DeterministicMarkdownChunker

    embedder = LocalE5Embedder(settings.embedding_cache_dir)
    return PrepareKnowledgeIndex(DeterministicMarkdownChunker(embedder), embedder)
