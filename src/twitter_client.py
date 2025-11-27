"""Twitter/X API client with search batching optimization."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import tweepy

from src.config import Config


@dataclass
class User:
    """Represents a Twitter/X user."""

    id: str
    username: str
    name: str
    profile_image_url: str


@dataclass
class Tweet:
    """Represents a tweet with its metadata."""

    id: str
    text: str
    created_at: datetime
    author: User
    media: List[dict]  # [{url, type, preview_image_url}, ...]
    url: str  # Direct link to tweet


class TwitterClient:
    """
    Twitter/X API client optimized for low API usage.
    
    Uses search batching to fetch tweets from multiple users in a single request,
    reducing API calls from ~50 per run to ~2-3 per run.
    """

    USERNAMES_FILE = Path("usernames.txt")
    USERS_PER_QUERY = 20  # Conservative limit to stay within query length limits

    def __init__(self, config: Config):
        self.config = config
        self.client = tweepy.Client(
            bearer_token=config.bearer_token,
            consumer_key=config.api_key,
            consumer_secret=config.api_secret,
            access_token=config.access_token,
            access_token_secret=config.access_token_secret,
            wait_on_rate_limit=True,
        )

    def get_usernames_from_file(self) -> List[str]:
        """
        Load usernames from usernames.txt file.
        
        Returns:
            List of usernames (without @ symbol).
        """
        if not self.USERNAMES_FILE.exists():
            raise FileNotFoundError(
                f"Please create {self.USERNAMES_FILE} with a list of usernames to track.\n"
                "Add one username per line (without the @ symbol)."
            )
        
        usernames = []
        with open(self.USERNAMES_FILE) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Remove @ if present
                username = line.lstrip("@")
                if username:
                    usernames.append(username)
        
        if not usernames:
            raise ValueError(
                f"{self.USERNAMES_FILE} is empty. Add usernames to track (one per line)."
            )
        
        # Respect max_accounts limit
        if len(usernames) > self.config.max_accounts:
            print(f"⚠️ Limiting to first {self.config.max_accounts} usernames")
            usernames = usernames[:self.config.max_accounts]
        
        return usernames

    def search_tweets_batch(
        self,
        usernames: List[str],
        since_days: int = 1,
    ) -> List[Tweet]:
        """
        Search for tweets from multiple users in a single API call.
        
        Uses query: "(from:user1 OR from:user2 OR ...) -is:retweet"
        
        Args:
            usernames: List of Twitter usernames to search.
            since_days: Number of days to look back.
            
        Returns:
            List of Tweet objects.
            
        Cost: 1 read per batch
        """
        if not usernames:
            return []

        # Build query: "(from:user1 OR from:user2 ...) -is:retweet"
        from_clauses = " OR ".join([f"from:{u}" for u in usernames])
        query = f"({from_clauses}) -is:retweet"

        # Calculate start time
        start_time = datetime.now(timezone.utc) - timedelta(days=since_days)

        print(f"🔍 Searching tweets from {len(usernames)} users...")

        try:
            # Execute search with expansions for media
            response = self.client.search_recent_tweets(
                query=query,
                start_time=start_time,
                max_results=100,
                expansions=["author_id", "attachments.media_keys"],
                tweet_fields=["created_at", "text", "entities", "public_metrics"],
                media_fields=["url", "preview_image_url", "type"],
                user_fields=["profile_image_url"],
            )
        except tweepy.TweepyException as e:
            print(f"⚠️ Search failed: {e}")
            return []

        if not response.data:
            return []

        # Build lookup dictionaries for expansions
        users_lookup: Dict[str, User] = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users_lookup[str(user.id)] = User(
                    id=str(user.id),
                    username=user.username,
                    name=user.name,
                    profile_image_url=getattr(user, "profile_image_url", "") or "",
                )

        media_lookup: Dict[str, dict] = {}
        if response.includes and "media" in response.includes:
            for media in response.includes["media"]:
                media_lookup[media.media_key] = {
                    "url": getattr(media, "url", None)
                    or getattr(media, "preview_image_url", ""),
                    "type": media.type,
                    "preview_image_url": getattr(media, "preview_image_url", ""),
                }

        # Parse tweets
        tweets = []
        for tweet_data in response.data:
            # Get author
            author = users_lookup.get(str(tweet_data.author_id))
            if not author:
                continue

            # Get media attachments
            media = []
            if hasattr(tweet_data, "attachments") and tweet_data.attachments:
                media_keys = tweet_data.attachments.get("media_keys", [])
                for key in media_keys:
                    if key in media_lookup:
                        media.append(media_lookup[key])

            tweets.append(
                Tweet(
                    id=str(tweet_data.id),
                    text=tweet_data.text,
                    created_at=tweet_data.created_at,
                    author=author,
                    media=media,
                    url=f"https://x.com/{author.username}/status/{tweet_data.id}",
                )
            )

        return tweets

    def fetch_all_tweets(self, since_days: int = 1) -> Dict[User, List[Tweet]]:
        """
        Fetch all tweets from tracked accounts using batched search.
        
        Args:
            since_days: Number of days to look back for tweets.
            
        Returns:
            Dictionary mapping User objects to their list of tweets,
            sorted by most recent tweet first.
            
        Cost: ~2-3 reads total (regardless of account count)
        """
        # Load usernames from file
        usernames = self.get_usernames_from_file()
        print(f"📋 Loaded {len(usernames)} usernames from {self.USERNAMES_FILE}")

        # We'll build the user lookup as we fetch tweets
        user_lookup: Dict[str, User] = {}

        # Batch usernames into groups of USERS_PER_QUERY
        all_tweets: List[Tweet] = []
        total_batches = (len(usernames) + self.USERS_PER_QUERY - 1) // self.USERS_PER_QUERY

        for i in range(0, len(usernames), self.USERS_PER_QUERY):
            batch = usernames[i : i + self.USERS_PER_QUERY]
            batch_num = (i // self.USERS_PER_QUERY) + 1
            print(f"📦 Batch {batch_num}/{total_batches}: {len(batch)} users")

            tweets = self.search_tweets_batch(batch, since_days)
            all_tweets.extend(tweets)
            print(f"   Found {len(tweets)} tweets")

        # Group tweets by author
        tweets_by_author: Dict[User, List[Tweet]] = {}
        for tweet in all_tweets:
            # Build user lookup as we go
            username_lower = tweet.author.username.lower()
            if username_lower not in user_lookup:
                user_lookup[username_lower] = tweet.author
            
            author_key = user_lookup[username_lower]
            if author_key not in tweets_by_author:
                tweets_by_author[author_key] = []
            tweets_by_author[author_key].append(tweet)

        # Sort tweets within each author by date (newest first)
        for author in tweets_by_author:
            tweets_by_author[author].sort(key=lambda t: t.created_at, reverse=True)

        # Sort authors by most recent tweet
        sorted_authors = sorted(
            tweets_by_author.keys(),
            key=lambda a: tweets_by_author[a][0].created_at
            if tweets_by_author[a]
            else datetime.min,
            reverse=True,
        )

        return {author: tweets_by_author[author] for author in sorted_authors}

