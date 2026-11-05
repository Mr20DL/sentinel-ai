import json
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import psycopg

from src.ports.embeddings import EmbeddingPort

_SEARCH_SQL = """
SELECT summary
FROM incidents
WHERE service_name = %s
ORDER BY embedding <=> %s::vector
LIMIT %s
"""

_UPSERT_SQL = """
INSERT INTO incidents (service_name, summary, embedding)
VALUES (%s, %s, %s::vector)
ON CONFLICT (service_name, summary)
DO UPDATE SET embedding = EXCLUDED.embedding
"""

_COUNT_SQL = "SELECT COUNT(*) FROM incidents"

_DELETE_SQL = "DELETE FROM incidents WHERE service_name = %s"


class PostgresIncidentRepository:
    """Neon PostgreSQL + pgvector adapter for semantic incident retrieval."""

    def __init__(
        self,
        database_url: str,
        embedder: EmbeddingPort,
        dimensions: int | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not database_url.strip():
            raise ValueError("DATABASE_URL is required for PostgresIncidentRepository")

        self._database_url = database_url.strip()
        self._embedder = embedder
        self._dimensions = dimensions or embedder.dimensions
        if self._dimensions != embedder.dimensions:
            raise ValueError("repository dimensions must match the embedding adapter")
        self._connect = connection_factory or (lambda: psycopg.connect(self._database_url))

    def ensure_schema(self) -> None:
        statements = (
            "CREATE EXTENSION IF NOT EXISTS vector",
            f"""
            CREATE TABLE IF NOT EXISTS incidents (
                id BIGSERIAL PRIMARY KEY,
                service_name TEXT NOT NULL,
                summary TEXT NOT NULL,
                embedding vector({self._dimensions}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE (service_name, summary)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS incidents_service_name_idx
            ON incidents (service_name)
            """,
            """
            CREATE INDEX IF NOT EXISTS incidents_embedding_hnsw_idx
            ON incidents USING hnsw (embedding vector_cosine_ops)
            """,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def seed_incidents(self, incidents: Mapping[str, Sequence[str]]) -> int:
        records: list[tuple[str, str, str]] = []
        for service_name, summaries in incidents.items():
            texts = list(summaries)
            vectors = self._embedder.embed_documents(texts)
            if len(vectors) != len(texts):
                raise RuntimeError("embedding adapter returned an unexpected batch size")
            for summary, vector in zip(texts, vectors, strict=True):
                records.append((service_name, summary, self._vector_literal(vector)))

        if not records:
            return 0

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(_UPSERT_SQL, records)
        return len(records)

    def search_incidents(self, service_name: str, query: str, limit: int = 5) -> list[str]:
        if limit <= 0:
            return []
        vector = self._vector_literal(self._embedder.embed_query(query))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(_SEARCH_SQL, (service_name, vector, limit))
                rows = cursor.fetchall()
        return [str(row[0]) for row in rows]

    def count_incidents(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(_COUNT_SQL)
                row = cursor.fetchone()
        return int(row[0]) if row else 0

    def delete_incidents(self, service_name: str) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(_DELETE_SQL, (service_name,))
                return int(cursor.rowcount)

    def _vector_literal(self, vector: Sequence[float]) -> str:
        values = [float(value) for value in vector]
        if len(values) != self._dimensions:
            raise ValueError(
                f"embedding dimension mismatch: expected {self._dimensions}, got {len(values)}"
            )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("embedding contains a non-finite value")
        return json.dumps(values, separators=(",", ":"))
