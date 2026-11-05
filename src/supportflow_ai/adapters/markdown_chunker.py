from __future__ import annotations

from bisect import bisect_right

from markdown_it import MarkdownIt

from supportflow_ai.domain.knowledge import (
    MAX_CHUNKS,
    PROFILE,
    InvalidIndexRequestError,
    MarkdownChunk,
    normalize,
)
from supportflow_ai.ports.knowledge import TextTokenizer


class DeterministicMarkdownChunker:
    """Prefer complete Markdown blocks; split oversized blocks without rewriting their text.

    Offsets are Unicode scalar positions in LF-normalized source; lines are 1-based inclusive.
    The prefix/title count towards the embedding model's budget. No silent truncation.
    """

    def __init__(self, tokenizer: TextTokenizer) -> None:
        self.tokenizer = tokenizer
        self.parser = MarkdownIt("commonmark").enable("table")

    def embedding_text(self, title: str, chunk: str) -> str:
        title = normalize(title)
        offsets = self.tokenizer.offsets(title)
        if len(offsets) > PROFILE.title_tokens:
            title = title[:offsets[PROFILE.title_tokens - 1][1]]
        return f"passage: {title}\n\n{chunk}"

    def chunk(self, title: str, content: str) -> list[MarkdownChunk]:
        source = normalize(content)
        if not source.strip():
            raise InvalidIndexRequestError("empty_content")
        line_offsets = [0]
        # CommonMark line maps count LF, not Unicode separators handled by str.splitlines().
        for i, char in enumerate(source):
            if char == "\n":
                line_offsets.append(i + 1)
        if line_offsets[-1] != len(source):
            line_offsets.append(len(source))
        boundaries: set[int] = {len(source)}
        headings: list[tuple[int, tuple[str, ...]]] = []
        path: list[tuple[int, str]] = []
        tokens = self.parser.parse(source)
        for i, token in enumerate(tokens):
            if token.map and token.level == 0:
                boundaries.add(line_offsets[token.map[1]])
                if token.type == "heading_open":
                    level = int(token.tag[1:])
                    while path and path[-1][0] >= level:
                        path.pop()
                    path.append((level, tokens[i + 1].content))
                    headings.append((line_offsets[token.map[0]], tuple(h[1] for h in path)))

        chunks: list[MarkdownChunk] = []
        start = 0
        previous_end = 0
        while start < len(source) and source[start:].strip():
            offsets = self.tokenizer.offsets(source[start:])
            if not offsets:
                raise InvalidIndexRequestError("unencodable_content")
            token_end = start + offsets[min(PROFILE.chunk_tokens, len(offsets)) - 1][1]
            if len(offsets) <= PROFILE.chunk_tokens:
                token_end = len(source)
            candidates = [end for end in boundaries if max(start, previous_end) < end <= token_end]
            end = max(candidates, default=token_end)
            # Some tokenizers split a scalar into overlapping byte tokens. Use source slices,
            # then verify the actual complete model input rather than trusting token arithmetic.
            while end > start and self.tokenizer.count(
                self.embedding_text(title, source[start:end])
            ) > PROFILE.max_input_tokens:
                end -= 1
            if end <= start:
                raise InvalidIndexRequestError("input_budget_exhausted")
            text = source[start:end]
            if not text.strip():
                start = end
                continue
            heading_path = next((p for pos, p in reversed(headings) if pos <= start), ())
            chunks.append(MarkdownChunk(
                index=len(chunks), text=text, start_char=start, end_char=end,
                start_line=bisect_right(line_offsets, start),
                end_line=bisect_right(line_offsets, max(start, end - 1)),
                heading_path=heading_path, token_count=self.tokenizer.count(
                    self.embedding_text(title, text)
                ),
            ))
            if len(chunks) > MAX_CHUNKS:
                raise InvalidIndexRequestError("too_many_chunks")
            if end == len(source):
                break
            previous_end = end
            used_offsets = self.tokenizer.offsets(text)
            # Do not let an overlap consume a whole short block or prevent forward progress.
            overlap = min(PROFILE.overlap_tokens, len(used_offsets) // 4)
            next_start = start + used_offsets[-overlap][0] if overlap else end
            start = next_start if start < next_start < end else end
        return chunks
