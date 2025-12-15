"""Twitter/X API client with search batching optimization.

Supports two backends:
1. twitterapi.io (preferred) - simpler, cheaper, just needs TWITTERAPI_IO_KEY
2. Official X API via Tweepy (legacy) - requires 5 credentials
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol

import httpx
import tweepy

from src.config import Config


# =============================================================================
# Shared Data Classes
# =============================================================================

@dataclass(frozen=True)
class User:
    """Represents a Twitter/X user."""

    id: str
    username: str
    name: str
    profile_image_url: str


@dataclass(frozen=True)
class Tweet:
    """Represents a tweet with its metadata."""

    id: str
    text: str
    created_at: datetime
    author: User
    media: List[dict]  # [{url, type, preview_image_url}, ...]
    url: str  # Direct link to tweet


# =============================================================================
# Abstract Base / Protocol
# =============================================================================

class TwitterClientProtocol(Protocol):
    """Protocol defining the interface for Twitter clients."""
    
    def fetch_all_tweets(self, since_days: int = 1) -> Dict[User, List[Tweet]]:
        """Fetch all tweets from tracked accounts."""
        ...


# =============================================================================
# twitterapi.io Implementation (Preferred)
# =============================================================================

class TwitterApiIoClient:
    """
    Twitter client using twitterapi.io - simpler and cheaper than official API.
    
    Pricing: $0.15/1k tweets, $0.18/1k profiles
    Auth: Just one API key in x-api-key header
    
    Automatically fetches followings list from the specified Twitter account.
    """
    
    BASE_URL = "https://api.twitterapi.io"
    MAX_RETRIES = 5
    RETRY_DELAY = 3.0  # seconds between retries, will be multiplied for backoff
    
    def __init__(self, config: Config, username_override: Optional[str] = None):
        self.config = config
        self.api_key = config.twitterapi_io_key
        # Use override if provided, otherwise fall back to config
        self.twitter_username = username_override or config.twitter_username
        self.headers = {"x-api-key": self.api_key}
    
    def _request_with_retry(
        self,
        url: str,
        params: dict,
        max_retries: int = None,
    ) -> Optional[dict]:
        """
        Make an HTTP GET request with retry logic for rate limits.
        
        Returns:
            JSON response dict, or None if all retries failed.
        """
        max_retries = max_retries or self.MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                response = httpx.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30.0,
                )
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    print(f"⏳ Rate limited, waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)
                    print(f"⏳ Rate limited, waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"⚠️ HTTP error: {e}")
                    return None
                    
            except httpx.RequestError as e:
                print(f"⚠️ Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return None
        
        print(f"⚠️ Max retries ({max_retries}) exceeded")
        return None
    
    def get_followings(self) -> List[str]:
        """
        Fetch list of usernames you follow from twitterapi.io.
        
        Cost: ~$0.00015 per call (negligible for daily runs).
        """
        print(f"🔄 Fetching followings for @{self.twitter_username}...")
        
        usernames = []
        cursor = ""
        page = 0
        
        while True:
            page += 1
            data = self._request_with_retry(
                f"{self.BASE_URL}/twitter/user/followings",
                params={
                    "userName": self.twitter_username,
                    "cursor": cursor,
                },
            )
            
            if data is None:
                print(f"⚠️ Failed to fetch followings page {page}")
                break
            
            if data.get("status") == "error":
                print(f"⚠️ API error: {data.get('message', 'Unknown error')}")
                break
            
            followings = data.get("followings", [])
            for user in followings:
                username = user.get("userName")
                if username:
                    usernames.append(username)
            
            if page == 1:
                print(f"   Found {len(followings)} accounts you follow")
            else:
                print(f"   Page {page}: {len(followings)} users (total: {len(usernames)})")
            
            if not data.get("has_next_page"):
                break
            
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
            
            # Delay between pages
            time.sleep(1.0)
        
        if not usernames:
            raise ValueError(
                f"Could not fetch followings for @{self.twitter_username}. "
                "Check your TWITTER_USERNAME and TWITTERAPI_IO_KEY."
            )
        
        # Respect max_accounts limit
        if len(usernames) > self.config.max_accounts:
            print(f"⚠️ Limiting to first {self.config.max_accounts} accounts")
            usernames = usernames[:self.config.max_accounts]
        
        return usernames
    
    def _parse_tweet(self, tweet_data: dict) -> Optional[Tweet]:
        """Parse a tweet from twitterapi.io response format."""
        try:
            author_data = tweet_data.get("author", {})
            
            # Skip if author data is missing
            if not author_data.get("userName"):
                return None
            
            author = User(
                id=str(author_data.get("id", "")),
                username=author_data.get("userName", ""),
                name=author_data.get("name", ""),
                profile_image_url=author_data.get("profilePicture", "") or "",
            )
            
            # Parse created_at - format: "Fri Nov 29 00:17:53 +0000 2024" or ISO
            created_at_str = tweet_data.get("createdAt", "")
            try:
                # Try ISO format first
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                # Try Twitter's format: "Fri Nov 29 00:17:53 +0000 2024"
                try:
                    created_at = datetime.strptime(
                        created_at_str, "%a %b %d %H:%M:%S %z %Y"
                    )
                except ValueError:
                    created_at = datetime.now(timezone.utc)
            
            # Extract media from extendedEntities or entities
            media = []
            extended = tweet_data.get("extendedEntities", {})
            if extended and "media" in extended:
                for m in extended["media"]:
                    media.append({
                        "url": m.get("media_url_https") or m.get("url", ""),
                        "type": m.get("type", "photo"),
                        "preview_image_url": m.get("media_url_https", ""),
                    })
            
            tweet_id = str(tweet_data.get("id", ""))
            
            return Tweet(
                id=tweet_id,
                text=tweet_data.get("text", ""),
                created_at=created_at,
                author=author,
                media=media,
                url=tweet_data.get("url") or f"https://x.com/{author.username}/status/{tweet_id}",
            )
        except Exception as e:
            print(f"⚠️ Error parsing tweet: {e}")
            return None
    
    def _fetch_user_tweets(
        self,
        username: str,
        since: datetime,
        include_replies: bool = False,
    ) -> List[Tweet]:
        """Fetch tweets for a single user."""
        tweets = []
        cursor = ""
        
        while True:
            data = self._request_with_retry(
                f"{self.BASE_URL}/twitter/user/last_tweets",
                params={
                    "userName": username,
                    "includeReplies": str(include_replies).lower(),
                    "cursor": cursor,
                },
            )
            
            if data is None:
                print(f"⚠️ Failed to fetch tweets for {username}")
                break
            
            if data.get("status") == "error":
                print(f"⚠️ API error for {username}: {data.get('message', 'Unknown error')}")
                break
            
            for tweet_data in data.get("tweets", []):
                tweet = self._parse_tweet(tweet_data)
                if tweet:
                    # Filter by date
                    if tweet.created_at >= since:
                        tweets.append(tweet)
                    else:
                        # Tweets are sorted by date, so we can stop
                        return tweets
            
            # Check for more pages
            if not data.get("has_next_page"):
                break
            
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
        
        return tweets
    
    def search_tweets_batch(
        self,
        usernames: List[str],
        since_days: int = 1,
    ) -> List[Tweet]:
        """
        Search for tweets from multiple users using Advanced Search.
        
        Uses query: "(from:user1 OR from:user2 OR ...) -filter:replies"
        """
        if not usernames:
            return []
        
        # Build query
        from_clauses = " OR ".join([f"from:{u}" for u in usernames])
        query = f"({from_clauses}) -filter:replies"
        
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        since_str = since.strftime("%Y-%m-%d_%H:%M:%S_UTC")
        query += f" since:{since_str}"
        
        print(f"🔍 Searching tweets from {len(usernames)} users...")
        
        tweets = []
        cursor = ""
        pages_fetched = 0
        max_pages = 10  # Safety limit
        
        while pages_fetched < max_pages:
            data = self._request_with_retry(
                f"{self.BASE_URL}/twitter/tweet/advanced_search",
                params={
                    "query": query,
                    "queryType": "Latest",
                    "cursor": cursor,
                },
            )
            
            if data is None:
                print(f"⚠️ Search request failed after retries")
                break
            
            page_tweets = data.get("tweets", [])
            for tweet_data in page_tweets:
                tweet = self._parse_tweet(tweet_data)
                if tweet:
                    tweets.append(tweet)
            
            pages_fetched += 1
            
            if not data.get("has_next_page") or not page_tweets:
                break
            
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
            
            # Delay between pages to avoid rate limits
            time.sleep(2.0)
        
        return tweets
    
    def fetch_all_tweets(self, since_days: int = 1) -> Dict[User, List[Tweet]]:
        """
        Fetch all tweets from tracked accounts.
        
        Uses batched Advanced Search for efficiency.
        Automatically fetches followings from your Twitter account.
        """
        print(f"🌐 Using twitterapi.io backend")
        usernames = self.get_followings()
        print(f"👥 Tracking {len(usernames)} accounts")
        
        # Use batch search (more efficient)
        BATCH_SIZE = 20  # Keep queries reasonable length
        all_tweets: List[Tweet] = []
        total_batches = (len(usernames) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in range(0, len(usernames), BATCH_SIZE):
            batch = usernames[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            print(f"📦 Batch {batch_num}/{total_batches}: {len(batch)} users")
            
            tweets = self.search_tweets_batch(batch, since_days)
            all_tweets.extend(tweets)
            print(f"   Found {len(tweets)} tweets")
            
            # Delay between batches to avoid rate limits
            if batch_num < total_batches:
                time.sleep(3.0)
        
        # Group tweets by author
        tweets_by_author: Dict[User, List[Tweet]] = {}
        user_lookup: Dict[str, User] = {}
        
        for tweet in all_tweets:
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
            key=lambda a: tweets_by_author[a][0].created_at if tweets_by_author[a] else datetime.min,
            reverse=True,
        )
        
        return {author: tweets_by_author[author] for author in sorted_authors}


# =============================================================================
# Legacy X API Implementation (via Tweepy)
# =============================================================================


class TweepyTwitterClient:
    """
    Legacy Twitter/X API client using Tweepy and official X API.
    
    Uses search batching to fetch tweets from multiple users in a single request,
    reducing API calls from ~50 per run to ~2-3 per run.
    
    Note: This is the fallback when TWITTERAPI_IO_KEY is not set.
    Requires 5 credentials: BEARER_TOKEN, API_KEY, API_SECRET, 
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET.
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
        print(f"🌐 Using legacy X API (Tweepy) backend")

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


# =============================================================================
# Factory Function
# =============================================================================

def create_twitter_client(
    config: Config,
    username_override: Optional[str] = None,
) -> TwitterClientProtocol:
    """
    Create the appropriate Twitter client based on configuration.
    
    Uses twitterapi.io if TWITTERAPI_IO_KEY is set (preferred),
    otherwise falls back to legacy X API via Tweepy.
    
    Args:
        config: Application configuration
        username_override: Optional Twitter username to use instead of config.twitter_username
        
    Returns:
        Twitter client instance (either TwitterApiIoClient or TweepyTwitterClient)
    """
    if config.use_twitterapi_io:
        return TwitterApiIoClient(config, username_override=username_override)
    else:
        return TweepyTwitterClient(config)


# Backward-compatible alias - use factory function
def TwitterClient(
    config: Config,
    username_override: Optional[str] = None,
) -> TwitterClientProtocol:
    """
    Create a Twitter client (backward-compatible alias for create_twitter_client).
    
    Automatically selects the best available backend:
    - twitterapi.io if TWITTERAPI_IO_KEY is set (cheaper, simpler)
    - Legacy X API via Tweepy otherwise
    """
    return create_twitter_client(config, username_override=username_override)
