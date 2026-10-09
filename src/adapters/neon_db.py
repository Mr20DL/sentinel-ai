import os

from src.ports.repository import IncidentRepositoryPort


class PostgresIncidentRepository:
    """Implementación PostgreSQL serverless (Neon) — requisito "cloud-native" (ADR-0003).

    Uso previsto en la Fase 3: recuperación RAG sobre pgvector.
    Requiere la variable de entorno DATABASE_URL (ver .env.example).
    """

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or os.getenv("DATABASE_URL")

    def search_incidents(self, service_name: str, limit: int = 5) -> list[str]:
        if not self._database_url:
            raise RuntimeError(
                "DATABASE_URL not configured; use InMemoryRepository in development."
            )
        raise NotImplementedError(
            "RAG retrieval over pgvector pending (Fase 3). Use InMemoryRepository."
        )