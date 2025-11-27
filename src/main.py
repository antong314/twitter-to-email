"""Main entry point for X Daily Digest."""

from datetime import datetime, timedelta, timezone

from src.config import Config
from src.email_builder import EmailBuilder
from src.email_sender import EmailSender
from src.twitter_client import TwitterClient


def main() -> None:
    """Run the X digest generation and email sending."""
    print("🚀 Starting X digest generation...")
    print(f"⏰ Current time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)

    # 1. Load and validate config
    config = Config.from_env()
    config.validate()
    print(f"✅ Config loaded")
    print(f"   • Digest period: {config.digest_days} day(s)")
    print(f"   • Max accounts: {config.max_accounts}")
    print(f"   • Timezone: {config.timezone}")
    print(f"   • Email to: {config.email_to}")

    # 2. Initialize clients
    twitter = TwitterClient(config)
    email_builder = EmailBuilder()
    email_sender = EmailSender(config)

    try:
        # 3. Fetch tweets (using search batching - ~2-3 API calls)
        print()
        print(f"📥 Fetching tweets from last {config.digest_days} day(s)...")
        tweets_by_author = twitter.fetch_all_tweets(since_days=config.digest_days)

        total_tweets = sum(len(t) for t in tweets_by_author.values())
        total_authors = len(tweets_by_author)

        print()
        print(f"✅ Found {total_tweets} tweets from {total_authors} accounts")

        if total_tweets == 0:
            print("ℹ️  No tweets found in the time range. Skipping email.")
            print("=" * 50)
            print("✅ Digest generation complete (no email sent)")
            return

        # 4. Build email
        print()
        print("📝 Building email digest...")
        now = datetime.now(timezone.utc)
        email_content = email_builder.build_digest(
            tweets_by_author,
            date_range=(now - timedelta(days=config.digest_days), now),
            timezone=config.timezone,
        )
        print(f"   Subject: {email_content.subject}")

        # 5. Send email
        print()
        print("📧 Sending email...")
        success = email_sender.send_digest(email_content)

        if success:
            print()
            print("=" * 50)
            print("✅ Digest sent successfully!")
        else:
            raise Exception("Email delivery failed")

    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        print("=" * 50)
        print("Attempting to send failure notification...")
        email_sender.send_failure_notification(e)
        raise  # Re-raise so Railway marks job as failed


if __name__ == "__main__":
    main()

