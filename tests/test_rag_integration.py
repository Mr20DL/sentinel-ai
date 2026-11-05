import os
import uuid

import pytest

from src.adapters.neon_db import PostgresIncidentRepository
from src.composition import build_embedding_adapter, load_database_url

pytestmark = pytest.mark.skipif(
    os.getenv("SENTINEL_RAG_INTEGRATION") != "1",
    reason="set SENTINEL_RAG_INTEGRATION=1 to run real Neon/pgvector tests",
)


def test_real_neon_pgvector_roundtrip():
    if not os.getenv("DATABASE_URL") or not os.getenv("GEMINI_API_KEY"):
        pytest.skip("DATABASE_URL and GEMINI_API_KEY are required")

    embedder = build_embedding_adapter()
    if embedder is None:
        pytest.skip("SENTINEL_EMBEDDING_PROVIDER must be gemini")

    service_name = f"integration-{uuid.uuid4().hex}"
    summary = "2026-10-01: Connection pool exhausted after a traffic spike."
    repository = PostgresIncidentRepository(load_database_url(), embedder)
    repository.ensure_schema()
    try:
        repository.seed_incidents({service_name: [summary]})
        results = repository.search_incidents(
            service_name, "database connection pool failure", limit=1
        )
        assert results == [summary]
    finally:
        repository.delete_incidents(service_name)
