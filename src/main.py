"""Main entry point for X Daily Digest."""

import sys
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from src.config import Config
from src.email_builder import EmailBuilder
from src.email_sender import EmailSender
from src.twitter_client import TwitterClient
from src.subscribers import SubscriberStore, Subscriber


def fetch_subscribers_from_api(config: Config) -> List[Subscriber]:
    """Fetch subscribers from the web server API."""
    url = f"{config.web_server_url.rstrip('/')}/api/subscribers"
    params = {"api_key": config.internal_api_key}
    
    print(f"📡 Fetching subscribers from {config.web_server_url}...")
    
    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        subscribers = [
            Subscriber(
                twitter_handle=s["twitter_handle"],
                email=s["email"],
                subscribed_at="",  # Not needed for processing
                active=True,
            )
            for s in data.get("subscribers", [])
        ]
        print(f"✅ Fetched {len(subscribers)} subscriber(s) from API")
        return subscribers
        
    except httpx.RequestError as e:
        print(f"❌ Failed to fetch subscribers from API: {e}")
        raise


def process_subscriber(
    subscriber: Subscriber,
    config: Config,
    email_builder: EmailBuilder,
) -> bool:
    """
    Process a single subscriber: fetch tweets and send digest.
    
    Args:
        subscriber: The subscriber to process
        config: Application configuration
        email_builder: Email builder instance
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*50}")
    print(f"📧 Processing: {subscriber.email}")
    print(f"   Twitter handle: @{subscriber.twitter_handle}")
    
    try:
        # Create Twitter client for this subscriber's handle
        twitter = TwitterClient(config, username_override=subscriber.twitter_handle)
        
        # Create email sender for this subscriber
        email_sender = EmailSender(config, recipient_override=subscriber.email)
        
        # Fetch tweets
        print(f"📥 Fetching tweets from last {config.digest_days} day(s)...")
        tweets_by_author = twitter.fetch_all_tweets(since_days=config.digest_days)
        
        total_tweets = sum(len(t) for t in tweets_by_author.values())
        total_authors = len(tweets_by_author)
        
        print(f"✅ Found {total_tweets} tweets from {total_authors} accounts")
        
        if total_tweets == 0:
            print(f"ℹ️  No tweets found for @{subscriber.twitter_handle}. Skipping email.")
            return True  # Not a failure, just nothing to send
        
        # Build email
        print("📝 Building email digest...")
        now = datetime.now(timezone.utc)
        email_content = email_builder.build_digest(
            tweets_by_author,
            date_range=(now - timedelta(days=config.digest_days), now),
            timezone=config.timezone,
            recipient_email=subscriber.email,
            base_url=config.base_url,
        )
        print(f"   Subject: {email_content.subject}")
        
        # Send email
        print("📧 Sending email...")
        success = email_sender.send_digest(email_content)
        
        if success:
            print(f"✅ Digest sent to {subscriber.email}")
            return True
        else:
            print(f"❌ Failed to send digest to {subscriber.email}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {subscriber.email}: {e}")
        return False


def main() -> None:
    """Run the X digest generation and email sending for all subscribers."""
    print("🚀 Starting X digest generation...")
    print(f"⏰ Current time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)

    # 1. Load and validate config
    config = Config.from_env()
    config.validate()
    print(f"✅ Config loaded")
    print(f"   • Digest period: {config.digest_days} day(s)")
    print(f"   • Max accounts per user: {config.max_accounts}")
    print(f"   • Timezone: {config.timezone}")

    # 2. Load subscribers (from API if configured, otherwise from local file)
    if config.web_server_url and config.internal_api_key:
        subscribers = fetch_subscribers_from_api(config)
    else:
        print("📁 Loading subscribers from local file...")
        subscriber_store = SubscriberStore(data_dir=config.data_dir)
        subscribers = subscriber_store.get_all_active()
    
    if not subscribers:
        print("\n⚠️  No active subscribers found.")
        print("   People can subscribe at your web app URL.")
        print("=" * 50)
        print("✅ Digest generation complete (no subscribers)")
        sys.exit(0)
    
    print(f"\n👥 Found {len(subscribers)} active subscriber(s)")
    
    # 3. Initialize shared components
    email_builder = EmailBuilder()
    
    # 4. Process each subscriber
    successful = 0
    failed = 0
    
    for subscriber in subscribers:
        try:
            if process_subscriber(subscriber, config, email_builder):
                successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Unexpected error for {subscriber.email}: {e}")
            failed += 1
    
    # 5. Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print(f"   • Total subscribers: {len(subscribers)}")
    print(f"   • Successful: {successful}")
    print(f"   • Failed: {failed}")
    print("=" * 50)
    
    if failed > 0:
        print(f"⚠️  {failed} digest(s) failed to send")
        sys.exit(1)
    else:
        print("✅ All digests sent successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
