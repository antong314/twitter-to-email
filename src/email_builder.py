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
        recipient_email: str = "",
        base_url: str = "",
    ) -> EmailContent:
        """
        Build complete email content from tweets.
        
        Args:
            tweets_by_author: Dictionary mapping users to their tweets.
            date_range: Tuple of (start_date, end_date) for the digest period.
            timezone: Timezone for displaying timestamps.
            recipient_email: Email address of the recipient (for unsubscribe link).
            base_url: Base URL of the web app (for unsubscribe link).
            
        Returns:
            EmailContent with subject, HTML body, and plain text body.
        """
        total_tweets = sum(len(tweets) for tweets in tweets_by_author.values())

        # Generate subject
        end_date = date_range[1].strftime("%b %d")
        subject = f"Your X digest – {total_tweets} tweets ({end_date})"
        
        # Build unsubscribe URL
        from urllib.parse import quote
        if base_url and recipient_email:
            # Remove trailing slash from base_url if present
            base_url_clean = base_url.rstrip('/')
            unsubscribe_url = f"{base_url_clean}/unsubscribe?email={quote(recipient_email)}"
        else:
            unsubscribe_url = ""

        # Render HTML template
        template = self.env.get_template("digest.html")
        html_body = template.render(
            tweets_by_author=tweets_by_author,
            total_tweets=total_tweets,
            date_range=date_range,
            timezone=timezone,
            unsubscribe_url=unsubscribe_url,
        )

        # Generate plain text fallback
        text_body = self._generate_text_fallback(
            tweets_by_author, total_tweets, date_range, timezone, unsubscribe_url
        )

        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    def _linkify(self, text: str, entities: dict = None) -> str:
        """
        Convert @mentions, #hashtags, and URLs to clickable links using Twitter entity data.
        
        When entities are provided, uses indices to properly replace t.co URLs with display URLs.
        Falls back to regex-based linking if entities are not available.
        
        Args:
            text: Raw tweet text.
            entities: Optional dict with urls, user_mentions, hashtags from Twitter API.
            
        Returns:
            HTML string with links.
        """
        if not entities or not any(entities.values()):
            # Fallback to regex-based linking if no entities
            return self._linkify_regex(text)
        
        # Collect all entities with their replacement info
        # Format: [(start, end, replacement_html), ...]
        replacements = []
        
        # Process URLs - replace t.co with display_url
        for url_entity in entities.get("urls", []):
            indices = url_entity.get("indices", [])
            if len(indices) >= 2:
                start, end = indices[0], indices[1]
                # Use display_url for link text, expanded_url for href
                display = url_entity.get("display_url") or url_entity.get("url", "")
                href = url_entity.get("expanded_url") or url_entity.get("url", "")
                replacement = f'<a href="{href}" style="color: #1d9bf0; text-decoration: none;">{display}</a>'
                replacements.append((start, end, replacement))
        
        # Process @mentions
        for mention in entities.get("user_mentions", []):
            indices = mention.get("indices", [])
            if len(indices) >= 2:
                start, end = indices[0], indices[1]
                # Twitter v2 API uses "username", v1 uses "screen_name"
                username = mention.get("username") or mention.get("screen_name", "")
                if username:
                    replacement = f'<a href="https://x.com/{username}" style="color: #1d9bf0; text-decoration: none;">@{username}</a>'
                    replacements.append((start, end, replacement))
        
        # Process #hashtags
        for hashtag in entities.get("hashtags", []):
            indices = hashtag.get("indices", [])
            if len(indices) >= 2:
                start, end = indices[0], indices[1]
                # Twitter v2 API uses "tag", v1 uses "text"
                tag = hashtag.get("tag") or hashtag.get("text", "")
                if tag:
                    replacement = f'<a href="https://x.com/hashtag/{tag}" style="color: #1d9bf0; text-decoration: none;">#{tag}</a>'
                    replacements.append((start, end, replacement))
        
        # Sort replacements by start index in REVERSE order
        # This is critical - we must replace from end to start to preserve indices
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        # Apply replacements
        result = text
        for start, end, replacement in replacements:
            result = result[:start] + replacement + result[end:]
        
        return result
    
    def _linkify_regex(self, text: str) -> str:
        """
        Fallback regex-based linking when entities are not available.
        
        Uses a single-pass approach to avoid regex interference between replacements.
        
        Args:
            text: Raw tweet text.
            
        Returns:
            HTML string with links.
        """
        LINK_STYLE = "color: #1d9bf0; text-decoration: none;"
        
        # Collect all matches with their positions for single-pass replacement
        replacements = []
        
        # Find URLs
        for match in re.finditer(r"https?://[^\s<>\"']+", text):
            url = match.group()
            replacement = f'<a href="{url}" style="{LINK_STYLE}">{url}</a>'
            replacements.append((match.start(), match.end(), replacement))
        
        # Find @mentions (not preceded by alphanumeric to avoid email-like patterns)
        for match in re.finditer(r"(?<![a-zA-Z0-9])@(\w+)", text):
            username = match.group(1)
            replacement = f'<a href="https://x.com/{username}" style="{LINK_STYLE}">@{username}</a>'
            replacements.append((match.start(), match.end(), replacement))
        
        # Find #hashtags (only at word boundaries, not inside other content)
        for match in re.finditer(r"(?<![a-zA-Z0-9])#(\w+)", text):
            # Skip if this looks like a hex color (6 hex chars)
            tag = match.group(1)
            if re.match(r"^[0-9a-fA-F]{6}$", tag):
                continue  # Skip hex colors like #1d9bf0
            replacement = f'<a href="https://x.com/hashtag/{tag}" style="{LINK_STYLE}">#{tag}</a>'
            replacements.append((match.start(), match.end(), replacement))
        
        # Sort by start position in reverse order
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        # Apply replacements from end to start
        result = text
        for start, end, replacement in replacements:
            result = result[:start] + replacement + result[end:]
        
        return result

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
        unsubscribe_url: str = "",
    ) -> str:
        """
        Generate plain text version of the email.
        
        Args:
            tweets_by_author: Dictionary mapping users to their tweets.
            total_tweets: Total number of tweets.
            date_range: Tuple of (start_date, end_date).
            timezone: Timezone for timestamps.
            unsubscribe_url: URL to unsubscribe.
            
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
        
        if unsubscribe_url:
            lines.append("")
            lines.append(f"Unsubscribe: {unsubscribe_url}")

        return "\n".join(lines)

