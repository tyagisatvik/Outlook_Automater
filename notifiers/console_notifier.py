from __future__ import annotations

from .base_notifier import Notifier


class ConsoleNotifier(Notifier):
    def __init__(self, logger) -> None:
        self.logger = logger

    def send(self, message: str) -> None:
        self.logger.info("Console notifier output below:\n%s", message)
        print("\n===== Notification Digest =====\n")
        print(message)
        print("\n===== End Digest =====\n")
