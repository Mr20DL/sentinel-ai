import json

import httpx
import pytest

from src.adapters.gemini_embeddings import EmbeddingError, GeminiEmbeddingAdapter


def _adapter(handler) -> GeminiEmbeddingAdapter:
    return GeminiEmbeddingAdapter(
        api_key="test-key",
        dimensions=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_gemini_embed_query_uses_instruction_and_dimensions():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers["x-goog-api-key"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2, 0.3]}})

    vector = _adapter(handler).embed_query("database connection failure")

    assert vector == [0.1, 0.2, 0.3]
    assert captured["url"].endswith("/models/gemini-embedding-2:embedContent")
    assert captured["api_key"] == "test-key"
    assert captured["body"]["content"]["parts"][0]["text"] == (
        "task: search result | query: database connection failure"
    )
    assert captured["body"]["embedContentConfig"] == {"outputDimensionality": 3}


def test_gemini_embed_documents_uses_document_instruction():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2, 0.3]}})

    vectors = _adapter(handler).embed_documents(["first", "second"])

    assert len(vectors) == 2
    assert captured["body"]["content"]["parts"][0]["text"] == ("title: none | text: second")
    assert "taskType" not in captured["body"]["embedContentConfig"]


def test_gemini_embedding_001_uses_task_type():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2, 0.3]}})

    adapter = GeminiEmbeddingAdapter(
        api_key="test-key",
        model="gemini-embedding-001",
        dimensions=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    adapter.embed_query("query")

    assert captured["body"]["content"]["parts"][0]["text"] == "query"
    assert captured["body"]["embedContentConfig"] == {
        "outputDimensionality": 3,
        "taskType": "RETRIEVAL_QUERY",
    }


def test_gemini_embedding_requires_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiEmbeddingAdapter(api_key="", dimensions=3)


def test_gemini_embedding_rejects_wrong_dimensions():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": {"values": [0.1, 0.2]}})

    with pytest.raises(EmbeddingError, match="dimension mismatch"):
        _adapter(handler).embed_query("query")


def test_gemini_embedding_rejects_non_numeric_values():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": {"values": [0.1, "bad", 0.3]}})

    with pytest.raises(EmbeddingError, match="non-numeric"):
        _adapter(handler).embed_query("query")


def test_gemini_embedding_wraps_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    with pytest.raises(EmbeddingError, match="request failed"):
        _adapter(handler).embed_query("query")
