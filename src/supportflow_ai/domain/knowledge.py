from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IndexProfile:
    id: str = "kb-e5-small-384-v1"
    provider: str = "sentence-transformers-cpu"
    model: str = "intfloat/multilingual-e5-small"
    model_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    dimension: int = 384
    tokenizer_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    chunker_version: str = "markdown-blocks-v1"
    normalization: str = "lf-v1"
    chunk_tokens: int = 384
    overlap_tokens: int = 32
    title_tokens: int = 48
    max_input_tokens: int = 480
    input_template: str = "passage: {title}\n\n{chunk}"

    @property
    def fingerprint(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")))


PROFILE = IndexProfile()
MAX_CONTENT_BYTES = 131_072
MAX_CHUNKS = 256


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    # Preserve code indentation, Markdown hard breaks and Unicode verbatim.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def snapshot_hash(title: str, content: str) -> str:
    # Length prefixes refer to UTF-8 bytes, not language-specific character counts.
    title_bytes, content_bytes = title.encode("utf-8"), content.encode("utf-8")
    payload = (
        str(len(title_bytes)).encode("ascii") + b":" + title_bytes
        + str(len(content_bytes)).encode("ascii") + b":" + content_bytes
    )
    return hashlib.sha256(payload).hexdigest()


def chunk_id(version_id: str, source_hash: str, index: int, text_hash: str) -> str:
    return sha256(f"{version_id}\n{source_hash}\n{PROFILE.fingerprint}\n{index}\n{text_hash}")


@dataclass(frozen=True)
class MarkdownChunk:
    index: int
    text: str
    start_char: int
    end_char: int
    start_line: int
    end_line: int
    heading_path: tuple[str, ...]
    token_count: int


class InvalidIndexRequestError(ValueError):
    """A snapshot/profile cannot be indexed under this contract."""
