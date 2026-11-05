from collections.abc import Sequence
from typing import Protocol

from supportflow_ai.domain.knowledge import MarkdownChunk


class TextTokenizer(Protocol):
    def offsets(self, text: str) -> Sequence[tuple[int, int]]: ...

    def count(self, text: str) -> int: ...


class MarkdownChunker(Protocol):
    def chunk(self, title: str, content: str) -> Sequence[MarkdownChunk]: ...

    def embedding_text(self, title: str, chunk: str) -> str: ...


class BatchEmbedder(Protocol):
    @property
    def ready(self) -> bool: ...

    def embed_many(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...
