"""Application Configuration using Pydantic Settings"""
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(..., min_length=32)

    # Database
    DATABASE_URL: str = Field(...)

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Microsoft Graph API
    MICROSOFT_CLIENT_ID: str = Field(...)
    MICROSOFT_CLIENT_SECRET: Optional[str] = Field(default=None)
    MICROSOFT_TENANT_ID: str = Field(...)
    MICROSOFT_REDIRECT_URI: str = Field(default="http://localhost:8000/api/auth/callback")
    TARGET_EMAIL_ADDRESS: Optional[str] = Field(default=None)

    # AI Services
    GOOGLE_API_KEY: str = Field(...)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)

    # AI Model Selection
    SUMMARIZER_MODEL: str = Field(default="gemini-1.5-flash")
    ACTIONS_MODEL: str = Field(default="gpt-4")
    REPLIES_MODEL: str = Field(default="claude-3-sonnet-20240229")

    # Email Processing
    MAX_EMAILS: int = Field(default=10, ge=1, le=1000)
    MAX_EMAILS_PER_BATCH: int = Field(default=50, ge=1, le=100)
    PROCESSING_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=300)

    # Cache Settings (in seconds)
    CACHE_TTL_AI_RESPONSES: int = Field(default=86400)  # 24 hours
    CACHE_TTL_GRAPH_API: int = Field(default=3600)  # 1 hour

    # Legacy Settings (backward compatibility with old config.py)
    AUTH_MODE: str = Field(default="delegated")
    SUMMARIZER_MODE: str = Field(default="gemini")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    NOTIFIER_TYPE: str = Field(default="console")
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None)
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None)

    @field_validator("AUTH_MODE")
    @classmethod
    def validate_auth_mode(cls, v: str) -> str:
        """Validate auth mode is either 'app' or 'delegated'"""
        v = v.strip().lower()
        if v not in ["app", "delegated"]:
            raise ValueError("AUTH_MODE must be 'app' or 'delegated'")
        return v

    @field_validator("NOTIFIER_TYPE")
    @classmethod
    def validate_notifier_type(cls, v: str) -> str:
        """Validate notifier type"""
        v = v.strip().lower()
        if v not in ["console", "telegram"]:
            raise ValueError("NOTIFIER_TYPE must be 'console' or 'telegram'")
        return v

    def validate_app_mode_requirements(self) -> None:
        """Validate requirements for 'app' auth mode"""
        if self.AUTH_MODE == "app":
            if not self.MICROSOFT_CLIENT_SECRET:
                raise ValueError("MICROSOFT_CLIENT_SECRET required for 'app' auth mode")
            if not self.TARGET_EMAIL_ADDRESS:
                raise ValueError("TARGET_EMAIL_ADDRESS required for 'app' auth mode")

    def validate_telegram_requirements(self) -> None:
        """Validate requirements for telegram notifier"""
        if self.NOTIFIER_TYPE == "telegram":
            if not self.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN required for telegram notifier")
            if not self.TELEGRAM_CHAT_ID:
                raise ValueError("TELEGRAM_CHAT_ID required for telegram notifier")

    def validate_all(self) -> None:
        """Run all custom validations"""
        self.validate_app_mode_requirements()
        self.validate_telegram_requirements()


# Global settings instance
settings = Settings()
