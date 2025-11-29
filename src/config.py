"""Configuration management for X Daily Digest."""

from dataclasses import dataclass
from os import environ
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Twitter API credentials (legacy X API - used if twitterapi_io_key not set)
    bearer_token: str
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    
    # twitterapi.io credentials (preferred - simpler and cheaper)
    twitterapi_io_key: str
    twitter_username: str  # Your Twitter username to fetch followings from
    
    # Email settings
    resend_api_key: str
    email_from: str
    email_to: str
    
    # App settings
    digest_days: int = 1
    max_accounts: int = 49
    timezone: str = "UTC"
    following_cache_days: int = 30
    
    @property
    def use_twitterapi_io(self) -> bool:
        """Check if twitterapi.io should be used (preferred backend)."""
        return bool(self.twitterapi_io_key)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        load_dotenv()

        return cls(
            # Legacy X API credentials
            bearer_token=environ.get("BEARER_TOKEN", ""),
            api_key=environ.get("API_KEY", ""),
            api_secret=environ.get("API_SECRET", ""),
            access_token=environ.get("ACCESS_TOKEN", ""),
            access_token_secret=environ.get("ACCESS_TOKEN_SECRET", ""),
            # twitterapi.io key (preferred)
            twitterapi_io_key=environ.get("TWITTERAPI_IO_KEY", ""),
            twitter_username=environ.get("TWITTER_USERNAME", ""),
            # Email settings
            resend_api_key=environ.get("RESEND_API_KEY", ""),
            email_from=environ.get("EMAIL_FROM", ""),
            email_to=environ.get("EMAIL_TO", ""),
            # App settings
            digest_days=int(environ.get("DIGEST_DAYS", "1")),
            max_accounts=int(environ.get("MAX_ACCOUNTS", "49")),
            timezone=environ.get("TIMEZONE", "UTC"),
            following_cache_days=int(environ.get("FOLLOWING_CACHE_DAYS", "30")),
        )

    def validate(self) -> None:
        """Validate that all required configuration is present.
        
        Either TWITTERAPI_IO_KEY must be set (preferred), or all legacy X API
        credentials must be set.
        
        Raises:
            ValueError: If any required configuration is missing.
        """
        missing = []

        # Check Twitter API credentials
        # Either twitterapi.io key OR all legacy credentials must be present
        if self.twitterapi_io_key:
            # Using twitterapi.io - need username to fetch followings
            if not self.twitter_username:
                missing.append("TWITTER_USERNAME (required with TWITTERAPI_IO_KEY)")
        else:
            # Fall back to legacy X API - all credentials required
            legacy_missing = []
            if not self.bearer_token:
                legacy_missing.append("BEARER_TOKEN")
            if not self.api_key:
                legacy_missing.append("API_KEY")
            if not self.api_secret:
                legacy_missing.append("API_SECRET")
            if not self.access_token:
                legacy_missing.append("ACCESS_TOKEN")
            if not self.access_token_secret:
                legacy_missing.append("ACCESS_TOKEN_SECRET")
            
            if legacy_missing:
                missing.append(
                    f"TWITTERAPI_IO_KEY (preferred) or legacy X API credentials: "
                    f"{', '.join(legacy_missing)}"
                )

        # Email settings always required
        if not self.resend_api_key:
            missing.append("RESEND_API_KEY")
        if not self.email_from:
            missing.append("EMAIL_FROM")
        if not self.email_to:
            missing.append("EMAIL_TO")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

