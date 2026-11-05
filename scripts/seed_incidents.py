from src.adapters.in_memory_repository import InMemoryRepository
from src.adapters.neon_db import PostgresIncidentRepository
from src.composition import build_embedding_adapter, load_database_url


def main() -> None:
    embedder = build_embedding_adapter()
    if embedder is None:
        raise SystemExit(
            "Set SENTINEL_EMBEDDING_PROVIDER=gemini and GEMINI_API_KEY before seeding."
        )

    repository = PostgresIncidentRepository(load_database_url(), embedder)
    repository.ensure_schema()
    seeded = repository.seed_incidents(InMemoryRepository.DEFAULT_INCIDENTS)
    total = repository.count_incidents()
    print(f"Seeded {seeded} incidents. Total rows: {total}")


if __name__ == "__main__":
    main()
