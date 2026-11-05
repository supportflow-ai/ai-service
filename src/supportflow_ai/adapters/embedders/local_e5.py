from __future__ import annotations

import threading
from collections.abc import Sequence

from supportflow_ai.domain.errors import ProviderUnavailableError
from supportflow_ai.domain.knowledge import PROFILE


class LocalE5Embedder:
    """Pinned, CPU-only runtime. Artifacts must be provisioned before service startup."""

    def __init__(self, cache_folder: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            PROFILE.model, revision=PROFILE.model_revision, device="cpu",
            cache_folder=cache_folder, local_files_only=True, trust_remote_code=False,
        )
        if self.model.get_sentence_embedding_dimension() != PROFILE.dimension:
            raise ValueError("embedding_dimension_mismatch")
        self.model.max_seq_length = 512
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return True

    def offsets(self, text: str) -> list[tuple[int, int]]:
        result = self.model.tokenizer(
            text, add_special_tokens=False, return_offsets_mapping=True, truncation=False,
        )
        return [(a, b) for a, b in result["offset_mapping"] if b > a]

    def count(self, text: str) -> int:
        return len(self.model.tokenizer(text, truncation=False)["input_ids"])

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        if any(self.count(text) > PROFILE.max_input_tokens for text in texts):
            raise ValueError("embedding_input_too_long")
        with self._lock:
            try:
                return self.model.encode(
                    list(texts), batch_size=8, normalize_embeddings=True,
                    show_progress_bar=False, convert_to_numpy=True,
                ).tolist()
            except Exception as exc:
                raise ProviderUnavailableError("embedding_inference_failed") from exc
