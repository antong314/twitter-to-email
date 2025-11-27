"""Email builder for X Daily Digest."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pytz
from jinja2 import Environment, FileSystemLoader

from src.twitter_client import Tweet, User


@dataclass
class EmailContent:
    """Container for email content."""

    subject: str
    html_body: str
    text_body: str


class EmailBuilder:
    """Builds HTML and plain-text email content from tweets."""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )
        self.env.filters["linkify"] = self._linkify
        self.env.filters["format_time"] = self._format_time

    def build_digest(
        self,
        tweets_by_author: Dict[User, List[Tweet]],
        date_range: Tuple[datetime, datetime],
        timezone: str = "UTC",
    ) -> EmailContent:
        """
        Build complete email content from tweets.
        
        Args:
            tweets_by_author: Dictionary mapping users to their tweets.
            date_range: Tuple of (start_date, end_date) for the digest period.
            timezone: Timezone for displaying timestamps.
            
        Returns:
            EmailContent with subject, HTML body, and plain text body.
        """
        total_tweets = sum(len(tweets) for tweets in tweets_by_author.values())

        # Generate subject
        end_date = date_range[1].strftime("%b %d")
        subject = f"Your X digest – {total_tweets} tweets ({end_date})"

        # Render HTML template
        template = self.env.get_template("digest.html")
        html_body = template.render(
            tweets_by_author=tweets_by_author,
            total_tweets=total_tweets,
            date_range=date_range,
            timezone=timezone,
        )

        # Generate plain text fallback
        text_body = self._generate_text_fallback(
            tweets_by_author, total_tweets, date_range, timezone
        )

        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    def _linkify(self, text: str) -> str:
        """
        Convert @mentions, #hashtags, and URLs to clickable links.
        
        Args:
            text: Raw tweet text.
            
        Returns:
            HTML string with links.
        """
        # Escape HTML first (but we need to be careful since Jinja2 auto-escapes)
        # URLs - match http/https URLs
        text = re.sub(
            r"(https?://[^\s<>\"']+)",
            r'<a href="\1" style="color: #1d9bf0; text-decoration: none;">\1</a>',
            text,
        )
        # @mentions
        text = re.sub(
            r"@(\w+)",
            r'<a href="https://x.com/\1" style="color: #1d9bf0; text-decoration: none;">@\1</a>',
            text,
        )
        # #hashtags
        text = re.sub(
            r"#(\w+)",
            r'<a href="https://x.com/hashtag/\1" style="color: #1d9bf0; text-decoration: none;">#\1</a>',
            text,
        )
        return text

    def _format_time(self, dt: datetime, timezone: str = "UTC") -> str:
        """
        Format datetime for display in the specified timezone.
        
        Args:
            dt: Datetime object (assumed UTC).
            timezone: Target timezone name.
            
        Returns:
            Formatted time string.
        """
        try:
            tz = pytz.timezone(timezone)
            # Ensure dt is timezone-aware
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            local_dt = dt.astimezone(tz)
            return local_dt.strftime("%b %d, %I:%M %p")
        except Exception:
            # Fallback to UTC if timezone is invalid
            return dt.strftime("%b %d, %I:%M %p UTC")

    def _generate_text_fallback(
        self,
        tweets_by_author: Dict[User, List[Tweet]],
        total_tweets: int,
        date_range: Tuple[datetime, datetime],
        timezone: str = "UTC",
    ) -> str:
        """
        Generate plain text version of the email.
        
        Args:
            tweets_by_author: Dictionary mapping users to their tweets.
            total_tweets: Total number of tweets.
            date_range: Tuple of (start_date, end_date).
            timezone: Timezone for timestamps.
            
        Returns:
            Plain text email content.
        """
        lines = [
            f"Your X Digest - {total_tweets} tweets",
            f"{date_range[0].strftime('%b %d')} - {date_range[1].strftime('%b %d, %Y')}",
            "=" * 50,
            "",
        ]

        for author, tweets in tweets_by_author.items():
            lines.append(f"\n{author.name} (@{author.username}) - {len(tweets)} tweets")
            lines.append("-" * 40)

            for tweet in tweets:
                # Clean up tweet text (remove extra whitespace)
                clean_text = " ".join(tweet.text.split())
                lines.append(f"\n{clean_text}")
                lines.append(f"  → {tweet.url}")
                lines.append(f"  {self._format_time(tweet.created_at, timezone)}")

            lines.append("")

        lines.append("-" * 50)
        lines.append("Generated automatically by your X Digest bot")

        return "\n".join(lines)

