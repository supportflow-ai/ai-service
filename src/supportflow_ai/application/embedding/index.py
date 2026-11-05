from __future__ import annotations

import math
import threading
from collections.abc import Sequence
from dataclasses import asdict
from numbers import Real
from uuid import UUID

from supportflow_ai.domain.errors import InvalidProviderOutputError, ProviderUnavailableError
from supportflow_ai.domain.knowledge import (
    MAX_CONTENT_BYTES,
    PROFILE,
    InvalidIndexRequestError,
    chunk_id,
    normalize,
    sha256,
    snapshot_hash,
)
from supportflow_ai.ports.knowledge import BatchEmbedder, MarkdownChunker


class PrepareKnowledgeIndex:
    def __init__(self, chunker: MarkdownChunker, embedder: BatchEmbedder) -> None:
        self.chunker = chunker
        self.embedder = embedder
        self._capacity = threading.BoundedSemaphore(1)

    @property
    def ready(self) -> bool:
        return self.embedder.ready

    def execute(
        self, *, request_id: UUID, article_id: UUID, article_version_id: UUID,
        version_number: int, source_hash: str, profile_id: str, title: str, content: str,
    ) -> dict:
        if profile_id != PROFILE.id or source_hash != snapshot_hash(title, content):
            raise InvalidIndexRequestError("snapshot_or_profile_mismatch")
        if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
            raise InvalidIndexRequestError("content_too_large")
        if not self._capacity.acquire(blocking=False):
            raise ProviderUnavailableError("embedding_busy")
        try:
            chunks = self.chunker.chunk(title, content)
            vectors = self.embedder.embed_many([
                self.chunker.embedding_text(title, chunk.text) for chunk in chunks
            ])
            if not isinstance(vectors, Sequence) or len(vectors) != len(chunks) or not chunks:
                raise InvalidProviderOutputError("embedding_count_mismatch")
            result = []
            for chunk, vector in zip(chunks, vectors, strict=True):
                if not isinstance(vector, Sequence) or len(vector) != PROFILE.dimension or any(
                    isinstance(value, bool) or not isinstance(value, Real)
                    or not math.isfinite(value) or abs(value) > 1.00001 for value in vector
                ):
                    raise InvalidProviderOutputError("invalid_embedding_vector")
                norm = math.sqrt(sum(float(value) ** 2 for value in vector))
                if not 0.999 <= norm <= 1.001:
                    raise InvalidProviderOutputError("embedding_not_normalized")
                text_hash = sha256(chunk.text)
                result.append({
                    "chunkId": chunk_id(
                        str(article_version_id), source_hash, chunk.index, text_hash,
                    ),
                    "index": chunk.index, "text": chunk.text, "textHash": text_hash,
                    "startChar": chunk.start_char, "endChar": chunk.end_char,
                    "startLine": chunk.start_line, "endLine": chunk.end_line,
                    "headingPath": list(chunk.heading_path), "tokenCount": chunk.token_count,
                    "embedding": [float(value) for value in vector],
                })
            return {
                "requestId": str(request_id), "articleId": str(article_id),
                "articleVersionId": str(article_version_id), "versionNumber": version_number,
                "sourceHash": source_hash, "profileId": PROFILE.id,
                "profileHash": PROFILE.fingerprint, "profile": asdict(PROFILE),
                "normalizedContentHash": sha256(normalize(content)), "chunks": result,
            }
        finally:
            self._capacity.release()
