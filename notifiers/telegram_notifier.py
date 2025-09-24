from __future__ import annotations

from typing import Optional
import requests

from .base_notifier import Notifier


class TelegramNotifier(Notifier):
    def __init__(self, config, logger) -> None:
        self.config = config
        self.logger = logger
        self.token: Optional[str] = self.config.telegram_bot_token
        self.chat_id: Optional[str] = self.config.telegram_chat_id
        if not self.token:
            self.logger.warning("TELEGRAM_BOT_TOKEN is not set; Telegram notifications will fail.")
        if not self.chat_id:
            self.logger.warning("TELEGRAM_CHAT_ID is not set; Telegram notifications will fail.")

    def send(self, message: str) -> None:
        if not self.token or not self.chat_id:
            self.logger.error("Telegram notifier is not properly configured (token or chat_id missing).")
            return
        try:
            self.logger.info("Sending Telegram notification...")
            # Telegram messages have a length limit; truncate to be safe
            safe_message = message if len(message) <= 3800 else message[:3800] + "\n… (truncated)"
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = requests.post(url, data={
                "chat_id": self.chat_id,
                "text": safe_message,
                "disable_web_page_preview": True,
                # Avoid parse errors due to special chars; keep plain text
            }, timeout=15)
            if resp.status_code != 200 or not resp.json().get("ok", False):
                self.logger.error("Telegram API error: %s", resp.text)
            else:
                self.logger.info("Telegram notification sent successfully.")
        except Exception as e:
            self.logger.exception("Failed to send Telegram message: %s", e)
