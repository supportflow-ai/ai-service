from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class TextEmbedder(Protocol):
    @property
    def name(self) -> str: ...

    async def embed(self, *, text: str) -> Sequence[float]: ...
