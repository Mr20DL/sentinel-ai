from typing import Protocol


class EmbeddingPort(Protocol):
    """Contrato para convertir texto en vectores para recuperacion semantica."""

    @property
    def dimensions(self) -> int:
        """Dimension fija del vector que produce el adaptador."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para documentos historicos."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Genera el embedding de la consulta del evento actual."""
        ...
