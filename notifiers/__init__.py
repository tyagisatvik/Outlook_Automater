from .base_notifier import Notifier
from .console_notifier import ConsoleNotifier

def get_telegram_notifier(config, logger):
	from .telegram_notifier import TelegramNotifier
	return TelegramNotifier(config, logger)

__all__ = ["Notifier", "ConsoleNotifier", "get_telegram_notifier"]
