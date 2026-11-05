import json
import math
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from supportflow_ai.adapters.markdown_chunker import DeterministicMarkdownChunker
from supportflow_ai.application.embedding.index import PrepareKnowledgeIndex
from supportflow_ai.config import Settings
from supportflow_ai.domain.errors import ProviderUnavailableError
from supportflow_ai.domain.knowledge import PROFILE, normalize, snapshot_hash
from supportflow_ai.main import create_app


class CharacterTokenizer:
    """Network-free test tokenizer; never selected by production configuration."""

    def offsets(self, text):
        return [(i, i + 1) for i in range(len(text))]

    def count(self, text):
        return len(text) + 2


class FakeEmbedder:
    ready = True

    def embed_many(self, texts):
        self.inputs = texts
        return [[1.0] + [0.0] * (PROFILE.dimension - 1) for _ in texts]


def preparer(embedder=None):
    return PrepareKnowledgeIndex(DeterministicMarkdownChunker(CharacterTokenizer()),
                                 embedder or FakeEmbedder())


def payload(content="# VPN\n\nKhởi động lại kết nối VPN.\n", title="Hướng dẫn VPN"):
    return {
        "requestId": "00000000-0000-0000-0000-000000000001",
        "articleId": "00000000-0000-0000-0000-000000000002",
        "articleVersionId": "00000000-0000-0000-0000-000000000003",
        "versionNumber": 1, "profileId": PROFILE.id,
        "sourceHash": snapshot_hash(title, content), "title": title, "content": content,
    }


def client(service=None, **settings):
    return TestClient(create_app(
        Settings(auth_enabled=False, classifier_provider="rule", **settings),
        index_preparer=service or preparer(),
    ))


@pytest.mark.parametrize("content", [
    "# Tiếng Việt 😀\r\n\r\nDòng có dấu.  \r\nDòng hai.\r\n",
    "# Mã nguồn\n\n```python\n# không phải heading\n  print('hi')  \n```\n",
    "# Bảng\n\n| Cột A | Cột B |\n| --- | --- |\n| Một | Hai |\n",
    "# Dài\n\n" + "tiếng Việt 😀 " * 200,
    "# One\n\nShort.\n\n## Two\n\n" + "x" * 1000,
])
def test_chunking_is_deterministic_preserves_source_and_covers_every_nonblank_character(content):
    chunker = DeterministicMarkdownChunker(CharacterTokenizer())
    chunks = chunker.chunk("Tiêu đề", content)
    assert chunks == chunker.chunk("Tiêu đề", content)
    source = normalize(content)
    covered = set()
    previous_end = 0
    for chunk in chunks:
        assert chunk.text == source[chunk.start_char:chunk.end_char]
        assert chunk.end_char > previous_end
        assert chunk.token_count <= PROFILE.max_input_tokens
        covered.update(range(chunk.start_char, chunk.end_char))
        previous_end = chunk.end_char
    assert all(i in covered for i, char in enumerate(source) if not char.isspace())


def test_heading_inside_code_fence_is_not_metadata_and_hard_breaks_survive():
    chunks = DeterministicMarkdownChunker(CharacterTokenizer()).chunk(
        "Title", "# Heading\n\n```md\n# literal  \n```\n",
    )
    assert chunks[0].heading_path == ("Heading",)
    assert "# literal  \n" in chunks[0].text


def test_index_response_has_traceable_stable_chunks_and_echoes_snapshot():
    with client() as http:
        request = payload()
        first = http.post("/v1/knowledge-indexes:prepare", json=request)
        second = http.post("/v1/knowledge-indexes:prepare", json=request)
    assert first.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    for key in ("requestId", "articleId", "articleVersionId", "versionNumber", "sourceHash"):
        assert result[key] == request[key]
    assert result["profileHash"] == PROFILE.fingerprint
    assert len(result["chunks"][0]["embedding"]) == 384
    assert result["chunks"][0]["headingPath"] == ["VPN"]


@pytest.mark.parametrize("change", [
    {"versionNumber": True}, {"versionNumber": "1"}, {"versionNumber": 0},
    {"sourceHash": "a" * 64}, {"profileId": "unknown"}, {"content": "   "},
    {"extra": 1}, {"articleVersionId": "not-uuid"}, {"content": "\ud800"},
])
def test_invalid_requests_are_rejected(change):
    with client() as http:
        response = http.post("/v1/knowledge-indexes:prepare",
                             content=json.dumps({**payload(), **change}),
                             headers={"Content-Type": "application/json"})
        assert response.status_code == 400


@pytest.mark.parametrize("vector", [[], [0.0] * 383, [0.0] * 384,
                                     [math.nan] * 384, [math.inf] * 384, [True] * 384])
def test_invalid_vectors_are_rejected_before_persistence(vector):
    class BadEmbedder(FakeEmbedder):
        def embed_many(self, texts):
            return [vector for _ in texts]

    with client(preparer(BadEmbedder())) as http:
        response = http.post("/v1/knowledge-indexes:prepare", json=payload())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "invalid_provider_output"


def test_count_mismatch_is_rejected():
    class BadEmbedder(FakeEmbedder):
        def embed_many(self, texts):
            return []

    with client(preparer(BadEmbedder())) as http:
        assert http.post("/v1/knowledge-indexes:prepare", json=payload()).status_code == 503


def test_auth_and_body_limit_apply_to_knowledge_route():
    token = "s2s-" + "x" * 40
    app = create_app(Settings(service_token=token), index_preparer=preparer())
    with TestClient(app) as http:
        assert http.post("/v1/knowledge-indexes:prepare", json=payload()).status_code == 401
        assert http.post("/v1/knowledge-indexes:prepare", json=payload(),
                         headers={"Authorization": f"Bearer {token}"}).status_code == 200
        response = http.post("/v1/knowledge-indexes:prepare", content=b"x" * 1_048_577)
        assert response.status_code == 413


def test_unconfigured_embedding_is_not_successful_empty_vector():
    with TestClient(create_app(Settings(auth_enabled=False, classifier_provider="rule"))) as http:
        assert http.get("/health/embedding").status_code == 503
        assert http.post("/v1/knowledge-indexes:prepare", json=payload()).status_code == 503


def test_busy_provider_fails_fast_and_capacity_is_released_on_error():
    service = preparer()
    args = dict(request_id=UUID(int=1), article_id=UUID(int=2), article_version_id=UUID(int=3),
                version_number=1, source_hash=snapshot_hash("Title", "Content"),
                profile_id=PROFILE.id, title="Title", content="Content")
    service._capacity.acquire()
    with pytest.raises(ProviderUnavailableError):
        service.execute(**args)
    service._capacity.release()
    assert service.execute(**args)["chunks"]


def test_raw_snapshot_hash_distinguishes_line_endings_but_chunk_text_normalizes_them():
    assert snapshot_hash("T", "a\r\nb") != snapshot_hash("T", "a\nb")
    chunker = DeterministicMarkdownChunker(CharacterTokenizer())
    assert chunker.chunk("T", "a\r\nb") == chunker.chunk("T", "a\nb")


def test_unicode_separators_do_not_shift_markdown_line_metadata():
    content = "# Heading\n\n" + "Text\u2028more\u0085text\u2029end " * 50 + "\n\n## Next\nEnd."
    chunks = DeterministicMarkdownChunker(CharacterTokenizer()).chunk("Title", content)
    for chunk in chunks:
        assert chunk.start_line == content[:chunk.start_char].count("\n") + 1
        assert chunk.end_line == content[:chunk.end_char - 1].count("\n") + 1
        assert chunk.text == content[chunk.start_char:chunk.end_char]


@pytest.mark.parametrize("result", [None, [None], [42], ["not-a-vector"]])
def test_malformed_provider_shapes_return_controlled_error(result):
    class BrokenEmbedder:
        ready = True

        def embed_many(self, texts):
            return result

    with client(preparer(BrokenEmbedder())) as http:
        assert http.post("/v1/knowledge-indexes:prepare", json=payload()).status_code == 503
