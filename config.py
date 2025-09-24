import os
from dotenv import load_dotenv


class Config:
    def __init__(self) -> None:
        load_dotenv()

        # AI & Email
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.microsoft_client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.microsoft_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.microsoft_tenant_id = os.getenv("MICROSOFT_TENANT_ID")
        self.target_email_address = os.getenv("TARGET_EMAIL_ADDRESS")
        
        # Auth mode: 'app' (client credentials) or 'delegated' (interactive)
        self.auth_mode = os.getenv("AUTH_MODE", "delegated").strip().lower()

        # Notifier
        self.notifier_type = os.getenv("NOTIFIER_TYPE", "console").strip().lower()

        # Telegram
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # Processing limits (default to 10 as requested)
        # 0 or empty means process all available (be mindful of large inboxes)
        try:
            self.max_emails = int(os.getenv("MAX_EMAILS", "10").strip() or "10")
        except Exception:
            self.max_emails = 10

    def validate(self) -> None:
        """Validates required fields based on the chosen authentication and notifier modes."""
        missing = []
        if not self.google_api_key:
            missing.append("GOOGLE_API_KEY")
        if not self.microsoft_client_id:
            missing.append("MICROSOFT_CLIENT_ID")
        if not self.microsoft_tenant_id:
            missing.append("MICROSOFT_TENANT_ID")

        # Client secret is only needed for 'app' mode
        if self.auth_mode == "app":
            if not self.microsoft_client_secret:
                missing.append("MICROSOFT_CLIENT_SECRET")
            if not self.target_email_address:
                missing.append("TARGET_EMAIL_ADDRESS")

        if self.notifier_type == "telegram":
            if not self.telegram_bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.telegram_chat_id:
                missing.append("TELEGRAM_CHAT_ID")

        if missing:
            raise ValueError(f"Missing required configuration values: {', '.join(missing)}")
