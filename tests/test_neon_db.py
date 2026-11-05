import pytest

from src.adapters.neon_db import PostgresIncidentRepository


class _StubEmbedder:
    dimensions = 3

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [0.1, 0.2, 0.3]


class _FakeCursor:
    def __init__(self, rows=None, row=None, rowcount: int = 0) -> None:
        self.calls: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[tuple]]] = []
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def execute(self, sql: str, params=None) -> None:
        self.calls.append((sql, params))

    def executemany(self, sql: str, records: list[tuple]) -> None:
        self.executemany_calls.append((sql, records))
        self.rowcount = len(records)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self.cursor_instance = cursor

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


def _repository(cursor: _FakeCursor, embedder=None):
    return PostgresIncidentRepository(
        "postgresql://example/test",
        embedder or _StubEmbedder(),
        connection_factory=lambda: _FakeConnection(cursor),
    )


def test_search_incidents_uses_vector_similarity_and_service_filter():
    cursor = _FakeCursor(rows=[("incident A",), ("incident B",)])
    embedder = _StubEmbedder()

    result = _repository(cursor, embedder).search_incidents(
        "payment-service", "database connection failure", limit=2
    )

    assert result == ["incident A", "incident B"]
    assert embedder.query_calls == ["database connection failure"]
    sql, params = cursor.calls[0]
    assert "<=>" in sql
    assert "WHERE service_name = %s" in sql
    assert params == ("payment-service", "[0.1,0.2,0.3]", 2)


def test_search_incidents_returns_empty_for_non_positive_limit():
    cursor = _FakeCursor()
    embedder = _StubEmbedder()

    result = _repository(cursor, embedder).search_incidents("payment-service", "query", limit=0)

    assert result == []
    assert cursor.calls == []
    assert embedder.query_calls == []


def test_ensure_schema_creates_vector_extension_table_and_index():
    cursor = _FakeCursor()

    _repository(cursor).ensure_schema()

    statements = [sql for sql, _ in cursor.calls]
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in statements)
    assert any("embedding vector(3)" in sql for sql in statements)
    assert any("USING hnsw" in sql for sql in statements)
    assert any("incidents_service_name_idx" in sql for sql in statements)


def test_seed_incidents_upserts_embeddings():
    cursor = _FakeCursor()
    embedder = _StubEmbedder()

    inserted = _repository(cursor, embedder).seed_incidents(
        {"payment-service": ["first", "second"]}
    )

    assert inserted == 2
    assert embedder.document_calls == [["first", "second"]]
    sql, records = cursor.executemany_calls[0]
    assert "ON CONFLICT (service_name, summary)" in sql
    assert records == [
        ("payment-service", "first", "[0.1,0.2,0.3]"),
        ("payment-service", "second", "[0.1,0.2,0.3]"),
    ]


def test_count_incidents_returns_scalar():
    cursor = _FakeCursor(row=(5,))

    assert _repository(cursor).count_incidents() == 5


def test_delete_incidents_returns_affected_rows():
    cursor = _FakeCursor(rowcount=2)

    assert _repository(cursor).delete_incidents("payment-service") == 2


def test_repository_rejects_empty_database_url():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        PostgresIncidentRepository("", _StubEmbedder())


def test_repository_rejects_dimension_mismatch():
    with pytest.raises(ValueError, match="dimensions"):
        PostgresIncidentRepository(
            "postgresql://example/test",
            _StubEmbedder(),
            dimensions=4,
        )
