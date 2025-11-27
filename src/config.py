"""Configuration management for X Daily Digest."""

from dataclasses import dataclass
from os import environ
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    bearer_token: str
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    resend_api_key: str
    email_from: str
    email_to: str
    digest_days: int = 1
    max_accounts: int = 49
    timezone: str = "UTC"
    following_cache_days: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        load_dotenv()

        return cls(
            bearer_token=environ.get("BEARER_TOKEN", ""),
            api_key=environ.get("API_KEY", ""),
            api_secret=environ.get("API_SECRET", ""),
            access_token=environ.get("ACCESS_TOKEN", ""),
            access_token_secret=environ.get("ACCESS_TOKEN_SECRET", ""),
            resend_api_key=environ.get("RESEND_API_KEY", ""),
            email_from=environ.get("EMAIL_FROM", ""),
            email_to=environ.get("EMAIL_TO", ""),
            digest_days=int(environ.get("DIGEST_DAYS", "1")),
            max_accounts=int(environ.get("MAX_ACCOUNTS", "49")),
            timezone=environ.get("TIMEZONE", "UTC"),
            following_cache_days=int(environ.get("FOLLOWING_CACHE_DAYS", "30")),
        )

    def validate(self) -> None:
        """Validate that all required configuration is present.
        
        Raises:
            ValueError: If any required configuration is missing.
        """
        missing = []

        if not self.bearer_token:
            missing.append("BEARER_TOKEN")
        if not self.api_key:
            missing.append("API_KEY")
        if not self.api_secret:
            missing.append("API_SECRET")
        if not self.access_token:
            missing.append("ACCESS_TOKEN")
        if not self.access_token_secret:
            missing.append("ACCESS_TOKEN_SECRET")
        if not self.resend_api_key:
            missing.append("RESEND_API_KEY")
        if not self.email_from:
            missing.append("EMAIL_FROM")
        if not self.email_to:
            missing.append("EMAIL_TO")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

