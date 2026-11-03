from __future__ import annotations

from supportflow_ai.ports.embedder import TextEmbedder


class GenerateEmbedding:
    """Internal capability scaffold.

    No public embedding HTTP endpoint is exposed yet because the backend currently has
    no canonical external embedding contract equivalent to classification v1.
    """

    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder

    async def execute(self, text: str) -> tuple[float, ...]:
        if not text.strip():
            raise ValueError("text must not be blank")
        return tuple(await self._embedder.embed(text=text))
