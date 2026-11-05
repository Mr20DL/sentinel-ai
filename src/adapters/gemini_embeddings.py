import math

import httpx

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class EmbeddingError(RuntimeError):
    """Raised when the embedding provider cannot produce a valid vector."""


class GeminiEmbeddingAdapter:
    """Gemini embeddings adapter using the REST API and explicit dimensions."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-2",
        dimensions: int = 384,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")
        if dimensions <= 0:
            raise ValueError("embedding dimensions must be greater than zero")
        if timeout <= 0:
            raise ValueError("embedding timeout must be greater than zero")

        self._api_key = api_key.strip()
        self._model = model.strip()
        self._dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text, "RETRIEVAL_DOCUMENT") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_QUERY")

    def _embed(self, text: str, task_type: str) -> list[float]:
        config: dict[str, object] = {"outputDimensionality": self._dimensions}
        if self._model.startswith("gemini-embedding-2"):
            text = self._with_task_instruction(text, task_type)
        else:
            config["taskType"] = task_type
        payload = {
            "content": {"parts": [{"text": text}]},
            "embedContentConfig": config,
        }
        try:
            response = self._client.post(
                f"{self._base_url}/models/{self._model}:embedContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingError("Gemini embedding request failed") from exc

        return self._parse_vector(body)

    @staticmethod
    def _with_task_instruction(text: str, task_type: str) -> str:
        if task_type == "RETRIEVAL_QUERY":
            return f"task: search result | query: {text}"
        return f"title: none | text: {text}"

    def _parse_vector(self, body: object) -> list[float]:
        if not isinstance(body, dict):
            raise EmbeddingError("Gemini embedding response is not an object")
        embedding = body.get("embedding")
        if not isinstance(embedding, dict):
            raise EmbeddingError("Gemini embedding response has no embedding")
        values = embedding.get("values")
        if not isinstance(values, list):
            raise EmbeddingError("Gemini embedding response has no values")

        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Gemini embedding contains non-numeric values") from exc

        if len(vector) != self._dimensions:
            raise EmbeddingError(
                "Gemini embedding dimension mismatch: "
                f"expected {self._dimensions}, got {len(vector)}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise EmbeddingError("Gemini embedding contains a non-finite value")
        return vector
