class InMemoryRepository:
    """Repositorio en memoria para desarrollo, tests y fallback sin DATABASE_URL."""

    DEFAULT_INCIDENTS: dict[str, list[str]] = {
        "payment-service": [
            "2026-09-01: Connection failure to payment gateway API resolved by restarting pool.",
            "2026-06-15: High latency in payment-service caused by DB connection exhaustion.",
            "2025-11-02: Partial outage after deploy; rolled back and enlarged connection pool.",
        ],
        "checkout-service": [
            "2026-08-20: Checkout timeouts after third-party rate-limit; cache warmed in front.",
        ],
        "anti-fraud-service": [
            "2026-07-10: Anti-fraud latency spike correlated with batch model re-scoring.",
        ],
    }

    def __init__(self, incidents: dict[str, list[str]] | None = None) -> None:
        self._incidents = incidents or dict(self.DEFAULT_INCIDENTS)

    def search_incidents(
        self, service_name: str, query: str, limit: int = 5
    ) -> list[str]:
        return self._incidents.get(service_name, [])[:limit]