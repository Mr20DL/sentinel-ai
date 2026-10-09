from typing import Protocol


class NotifierPort(Protocol):
    """Contrato para notificación de anomalías/runbooks a canales externos."""

    def send(self, channel: str, message: str) -> None:
        """Envía un mensaje a un canal (Slack, e-mail, webhook, etc.)."""
        ...