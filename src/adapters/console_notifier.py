from src.ports.notifier import NotifierPort


class ConsoleNotifier:
    """Notificador en consola para desarrollo; luego Slack/e-mail/webhook."""

    def send(self, channel: str, message: str) -> None:
        print(f"[Notifier:{channel}] {message}")