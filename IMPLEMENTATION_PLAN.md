# X Daily Digest - Implementation Plan

> A personal X/Twitter digest that emails you all tweets from accounts you follow, grouped by author, delivered daily.

---

## 📋 Summary of Requirements

| Requirement | Decision |
|-------------|----------|
| Grouping | By author (all tweets from @user1, then @user2, etc.) |
| Content | Original tweets + replies (no retweets) |
| Media | Embedded images & video thumbnails |
| Email provider | Resend.com (free tier) |
| Schedule | Daily at 09:00 UTC (configurable) |
| Account source | Auto-fetch followed accounts (capped at 49) |
| Failure handling | Send separate failure notification email |
| Email style | Minimal, clean, easy to read |

---

## 🎯 API Optimization Strategy

### The Problem
X API Free tier allows only **100 reads/month**. A naive approach (1 call per account) would use ~51 reads per run = **1,530 reads/month for daily digests** ❌

### The Solution: Search Batching
Instead of fetching each user's timeline separately, use the **Recent Search endpoint** with `from:` operators to batch multiple users into a single query.

```
Query: "from:user1 OR from:user2 OR from:user3 ... OR from:user25"
```

### API Usage Breakdown

| Operation | Frequency | Reads |
|-----------|-----------|-------|
| Fetch following list | Once at setup, then monthly refresh | 1/month |
| Search tweets (batch 1: users 1-25) | Per digest | 1 |
| Search tweets (batch 2: users 26-49) | Per digest | 1 |
| **Total per digest** | | **2-3 reads** |

### Monthly Budget

| Schedule | Reads/Month | Free Tier (100) |
|----------|-------------|-----------------|
| Daily | 2 × 30 + 1 = **61 reads** | ✅ 39 buffer |
| Weekly | 2 × 4 + 1 = **9 reads** | ✅ 91 buffer |

---

## 🏗️ Project Structure

```
twitter-to-email/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point - orchestrates the entire flow
│   ├── twitter_client.py    # X API interactions (search batching)
│   ├── email_builder.py     # HTML email template generation
│   ├── email_sender.py      # Resend API integration
│   └── config.py            # Environment variables & settings
├── data/
│   └── following_cache.json # Cached following list (refreshed monthly)
├── templates/
│   └── digest.html          # Jinja2 email template
├── tests/
│   ├── __init__.py
│   ├── test_twitter_client.py
│   ├── test_email_builder.py
│   └── test_email_sender.py
├── .env.example             # Template for environment variables
├── .gitignore
├── requirements.txt
├── railway.json             # Railway deployment config
└── README.md
```

---

## 🔧 Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.11+ |
| X API Client | Tweepy | 4.14+ |
| Email Service | Resend | (Python SDK) |
| Templating | Jinja2 | 3.x |
| HTTP Client | httpx | (for media fetching) |
| Env Management | python-dotenv | (local dev) |
| Hosting | Railway.app | Hobby tier (free) |

---

## 🔑 Environment Variables

Create these in Railway dashboard (or `.env` for local dev):

```bash
# X/Twitter API Credentials (from developer.twitter.com)
BEARER_TOKEN=your_bearer_token
API_KEY=your_api_key
API_SECRET=your_api_secret
ACCESS_TOKEN=your_access_token
ACCESS_TOKEN_SECRET=your_access_token_secret

# Resend Email
RESEND_API_KEY=re_xxxxxxxxxxxx

# Email Configuration
EMAIL_FROM=onboarding@resend.dev    # or your verified domain
EMAIL_TO=your.email@gmail.com

# App Settings
DIGEST_DAYS=1                        # 1 = daily, 7 = weekly
MAX_ACCOUNTS=49                      # Hard cap for free tier
TIMEZONE=UTC                         # For display in email
FOLLOWING_CACHE_DAYS=30              # How often to refresh following list
```

---

## 📦 Dependencies (`requirements.txt`)

```
tweepy>=4.14.0
resend>=0.7.0
jinja2>=3.1.0
python-dotenv>=1.0.0
httpx>=0.25.0
pytz>=2024.1
```

---

## 🧩 Module Breakdown

### 1. `config.py` - Configuration Management

**Responsibilities:**
- Load environment variables
- Validate required settings
- Provide typed access to config values

```python
from dataclasses import dataclass
from os import environ
from dotenv import load_dotenv

@dataclass
class Config:
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
        load_dotenv()
        return cls(
            bearer_token=environ["BEARER_TOKEN"],
            api_key=environ["API_KEY"],
            api_secret=environ["API_SECRET"],
            access_token=environ["ACCESS_TOKEN"],
            access_token_secret=environ["ACCESS_TOKEN_SECRET"],
            resend_api_key=environ["RESEND_API_KEY"],
            email_from=environ["EMAIL_FROM"],
            email_to=environ["EMAIL_TO"],
            digest_days=int(environ.get("DIGEST_DAYS", "1")),
            max_accounts=int(environ.get("MAX_ACCOUNTS", "49")),
            timezone=environ.get("TIMEZONE", "UTC"),
            following_cache_days=int(environ.get("FOLLOWING_CACHE_DAYS", "30")),
        )
    
    def validate(self) -> None:
        """Raises ValueError if config is invalid."""
        required = [
            self.bearer_token, self.api_key, self.api_secret,
            self.access_token, self.access_token_secret,
            self.resend_api_key, self.email_from, self.email_to
        ]
        if not all(required):
            raise ValueError("Missing required environment variables")
```

---

### 2. `twitter_client.py` - X API Integration (Search Batching)

**Responsibilities:**
- Authenticate with X API using OAuth 2.0 Bearer Token
- Fetch and cache list of followed accounts
- Fetch tweets using batched search queries
- Filter to original tweets + replies only (exclude retweets)

```python
import json
import tweepy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class User:
    id: str
    username: str
    name: str
    profile_image_url: str

@dataclass  
class Tweet:
    id: str
    text: str
    created_at: datetime
    author: User
    media: List[dict]  # [{url, type, preview_image_url}, ...]
    url: str  # Direct link to tweet

class TwitterClient:
    CACHE_FILE = Path("data/following_cache.json")
    USERS_PER_QUERY = 25  # Safe limit for query length
    
    def __init__(self, config):
        self.config = config
        self.client = tweepy.Client(
            bearer_token=config.bearer_token,
            consumer_key=config.api_key,
            consumer_secret=config.api_secret,
            access_token=config.access_token,
            access_token_secret=config.access_token_secret,
            wait_on_rate_limit=True
        )
    
    def get_following(self, force_refresh: bool = False) -> List[User]:
        """
        Get list of accounts the user follows.
        Uses cached data if available and fresh, otherwise fetches from API.
        Cost: 1 read (only when cache is stale or missing)
        """
        # Check cache first
        if not force_refresh and self._is_cache_valid():
            print("📂 Using cached following list")
            return self._load_cache()
        
        print("🔄 Fetching fresh following list from API...")
        
        # Get authenticated user's ID
        me = self.client.get_me()
        user_id = me.data.id
        
        # Fetch following list (1 API call, up to 1000 users)
        response = self.client.get_users_following(
            id=user_id,
            max_results=min(self.config.max_accounts, 1000),
            user_fields=["profile_image_url"]
        )
        
        users = []
        for user_data in response.data[:self.config.max_accounts]:
            users.append(User(
                id=user_data.id,
                username=user_data.username,
                name=user_data.name,
                profile_image_url=user_data.profile_image_url or ""
            ))
        
        # Save to cache
        self._save_cache(users)
        print(f"✅ Cached {len(users)} followed accounts")
        
        return users
    
    def search_tweets_batch(
        self, 
        usernames: List[str], 
        since_days: int = 1
    ) -> List[Tweet]:
        """
        Search for tweets from multiple users in a single API call.
        Query: "from:user1 OR from:user2 OR ... -is:retweet"
        Cost: 1 read per batch
        """
        if not usernames:
            return []
        
        # Build query: "from:user1 OR from:user2 ... -is:retweet"
        from_clauses = " OR ".join([f"from:{u}" for u in usernames])
        query = f"({from_clauses}) -is:retweet"
        
        # Calculate start time
        start_time = datetime.utcnow() - timedelta(days=since_days)
        
        print(f"🔍 Searching tweets from {len(usernames)} users...")
        
        # Execute search with expansions for media
        response = self.client.search_recent_tweets(
            query=query,
            start_time=start_time,
            max_results=100,
            expansions=["author_id", "attachments.media_keys"],
            tweet_fields=["created_at", "text", "entities", "public_metrics"],
            media_fields=["url", "preview_image_url", "type"],
            user_fields=["profile_image_url"]
        )
        
        if not response.data:
            return []
        
        # Build lookup dictionaries for expansions
        users_lookup = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users_lookup[user.id] = User(
                    id=user.id,
                    username=user.username,
                    name=user.name,
                    profile_image_url=user.profile_image_url or ""
                )
        
        media_lookup = {}
        if response.includes and "media" in response.includes:
            for media in response.includes["media"]:
                media_lookup[media.media_key] = {
                    "url": getattr(media, "url", None) or getattr(media, "preview_image_url", ""),
                    "type": media.type,
                    "preview_image_url": getattr(media, "preview_image_url", "")
                }
        
        # Parse tweets
        tweets = []
        for tweet_data in response.data:
            # Get author
            author = users_lookup.get(tweet_data.author_id)
            if not author:
                continue
            
            # Get media attachments
            media = []
            if hasattr(tweet_data, "attachments") and tweet_data.attachments:
                media_keys = tweet_data.attachments.get("media_keys", [])
                for key in media_keys:
                    if key in media_lookup:
                        media.append(media_lookup[key])
            
            tweets.append(Tweet(
                id=tweet_data.id,
                text=tweet_data.text,
                created_at=tweet_data.created_at,
                author=author,
                media=media,
                url=f"https://x.com/{author.username}/status/{tweet_data.id}"
            ))
        
        return tweets
    
    def fetch_all_tweets(self, since_days: int = 1) -> Dict[User, List[Tweet]]:
        """
        Fetch all tweets from followed accounts using batched search.
        Cost: ~2-3 reads total (regardless of account count)
        """
        # Get following list (from cache or 1 API call)
        following = self.get_following()
        usernames = [u.username for u in following]
        
        # Create user lookup by username
        user_lookup = {u.username.lower(): u for u in following}
        
        # Batch usernames into groups of USERS_PER_QUERY
        all_tweets = []
        for i in range(0, len(usernames), self.USERS_PER_QUERY):
            batch = usernames[i:i + self.USERS_PER_QUERY]
            batch_num = (i // self.USERS_PER_QUERY) + 1
            total_batches = (len(usernames) + self.USERS_PER_QUERY - 1) // self.USERS_PER_QUERY
            print(f"📦 Batch {batch_num}/{total_batches}: {len(batch)} users")
            
            tweets = self.search_tweets_batch(batch, since_days)
            all_tweets.extend(tweets)
        
        # Group tweets by author
        tweets_by_author: Dict[User, List[Tweet]] = {}
        for tweet in all_tweets:
            # Use the cached user object for consistency
            author_key = user_lookup.get(tweet.author.username.lower(), tweet.author)
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
            reverse=True
        )
        
        return {author: tweets_by_author[author] for author in sorted_authors}
    
    def _is_cache_valid(self) -> bool:
        """Check if cache exists and is not expired."""
        if not self.CACHE_FILE.exists():
            return False
        
        try:
            with open(self.CACHE_FILE) as f:
                data = json.load(f)
            
            cached_at = datetime.fromisoformat(data["cached_at"])
            max_age = timedelta(days=self.config.following_cache_days)
            return datetime.utcnow() - cached_at < max_age
        except (json.JSONDecodeError, KeyError):
            return False
    
    def _load_cache(self) -> List[User]:
        """Load following list from cache file."""
        with open(self.CACHE_FILE) as f:
            data = json.load(f)
        
        return [
            User(
                id=u["id"],
                username=u["username"],
                name=u["name"],
                profile_image_url=u["profile_image_url"]
            )
            for u in data["users"]
        ]
    
    def _save_cache(self, users: List[User]) -> None:
        """Save following list to cache file."""
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "cached_at": datetime.utcnow().isoformat(),
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "name": u.name,
                    "profile_image_url": u.profile_image_url
                }
                for u in users
            ]
        }
        
        with open(self.CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
```

---

### 3. `email_builder.py` - HTML Email Generation

**Responsibilities:**
- Load and render Jinja2 template
- Format tweets with proper styling
- Embed media (images as `<img>` tags, videos as thumbnail + link)
- Generate plain-text fallback

```python
import re
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
import pytz

@dataclass
class EmailContent:
    subject: str
    html_body: str
    text_body: str

class EmailBuilder:
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters["linkify"] = self._linkify
        self.env.filters["format_time"] = self._format_time
    
    def build_digest(
        self,
        tweets_by_author: Dict,  # Dict[User, List[Tweet]]
        date_range: Tuple[datetime, datetime],
        timezone: str = "UTC"
    ) -> EmailContent:
        """Build complete email content from tweets."""
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
            timezone=timezone
        )
        
        # Generate plain text fallback
        text_body = self._generate_text_fallback(tweets_by_author, total_tweets, date_range)
        
        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )
    
    def _linkify(self, text: str) -> str:
        """Convert @mentions, #hashtags, and URLs to links."""
        # URLs
        text = re.sub(
            r'(https?://\S+)',
            r'<a href="\1">\1</a>',
            text
        )
        # @mentions
        text = re.sub(
            r'@(\w+)',
            r'<a href="https://x.com/\1">@\1</a>',
            text
        )
        # #hashtags
        text = re.sub(
            r'#(\w+)',
            r'<a href="https://x.com/hashtag/\1">#\1</a>',
            text
        )
        return text
    
    def _format_time(self, dt: datetime, timezone: str = "UTC") -> str:
        """Format datetime for display."""
        tz = pytz.timezone(timezone)
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%b %d, %I:%M %p")
    
    def _generate_text_fallback(
        self,
        tweets_by_author: Dict,
        total_tweets: int,
        date_range: Tuple[datetime, datetime]
    ) -> str:
        """Generate plain text version of email."""
        lines = [
            f"Your X Digest - {total_tweets} tweets",
            f"{date_range[0].strftime('%b %d')} - {date_range[1].strftime('%b %d')}",
            "=" * 50,
            ""
        ]
        
        for author, tweets in tweets_by_author.items():
            lines.append(f"\n{author.name} (@{author.username}) - {len(tweets)} tweets")
            lines.append("-" * 40)
            
            for tweet in tweets:
                lines.append(f"\n{tweet.text}")
                lines.append(f"  → {tweet.url}")
                lines.append(f"  {tweet.created_at.strftime('%b %d, %I:%M %p')}")
            
            lines.append("")
        
        return "\n".join(lines)
```

---

### 4. `email_sender.py` - Resend Integration

**Responsibilities:**
- Send digest email via Resend API
- Send failure notification if digest fails
- Handle delivery errors gracefully

```python
import resend
from datetime import datetime

class EmailSender:
    def __init__(self, config):
        self.config = config
        resend.api_key = config.resend_api_key
    
    def send_digest(self, email_content) -> bool:
        """
        Send the digest email via Resend.
        Returns True on success, False on failure.
        """
        try:
            resend.Emails.send({
                "from": self.config.email_from,
                "to": self.config.email_to,
                "subject": email_content.subject,
                "html": email_content.html_body,
                "text": email_content.text_body
            })
            return True
        except Exception as e:
            print(f"❌ Email send failed: {e}")
            return False
    
    def send_failure_notification(self, error: Exception) -> None:
        """Send a simple failure notification email."""
        try:
            date_str = datetime.utcnow().strftime("%b %d")
            resend.Emails.send({
                "from": self.config.email_from,
                "to": self.config.email_to,
                "subject": f"❌ X Digest failed – {date_str}",
                "text": f"""Your X digest failed to generate.

Error: {str(error)}

Please check the Railway logs for more details.
"""
            })
        except Exception as e:
            print(f"❌ Failed to send failure notification: {e}")
```

---

### 5. `main.py` - Entry Point / Orchestrator

**Responsibilities:**
- Load config and validate
- Orchestrate the full flow
- Handle top-level errors
- Log progress for Railway dashboard

```python
from datetime import datetime, timedelta
from src.config import Config
from src.twitter_client import TwitterClient
from src.email_builder import EmailBuilder
from src.email_sender import EmailSender

def main():
    print("🚀 Starting X digest generation...")
    print(f"⏰ Current time: {datetime.utcnow().isoformat()} UTC")
    
    # 1. Load and validate config
    config = Config.from_env()
    config.validate()
    print(f"✅ Config loaded (digest_days={config.digest_days})")
    
    # 2. Initialize clients
    twitter = TwitterClient(config)
    email_builder = EmailBuilder()
    email_sender = EmailSender(config)
    
    try:
        # 3. Fetch tweets (using search batching - ~2-3 API calls)
        print(f"📥 Fetching tweets from last {config.digest_days} day(s)...")
        tweets_by_author = twitter.fetch_all_tweets(since_days=config.digest_days)
        
        total_tweets = sum(len(t) for t in tweets_by_author.values())
        total_authors = len(tweets_by_author)
        print(f"✅ Found {total_tweets} tweets from {total_authors} accounts")
        
        if total_tweets == 0:
            print("ℹ️ No tweets found in the time range. Skipping email.")
            return
        
        # 4. Build email
        print("📝 Building email digest...")
        now = datetime.utcnow()
        email_content = email_builder.build_digest(
            tweets_by_author,
            date_range=(now - timedelta(days=config.digest_days), now),
            timezone=config.timezone
        )
        
        # 5. Send email
        print("📧 Sending email...")
        success = email_sender.send_digest(email_content)
        
        if success:
            print("✅ Digest sent successfully!")
        else:
            raise Exception("Email delivery failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        email_sender.send_failure_notification(e)
        raise  # Re-raise so Railway marks job as failed

if __name__ == "__main__":
    main()
```

---

## 📧 Email Template (`templates/digest.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your X Digest</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.5;
      color: #1a1a1a;
      background: #f5f5f5;
      padding: 20px;
    }
    
    .container {
      max-width: 600px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
    }
    
    header {
      background: #000000;
      color: #ffffff;
      padding: 24px;
      text-align: center;
    }
    
    header h1 {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 8px;
    }
    
    header p {
      font-size: 14px;
      opacity: 0.8;
    }
    
    .author-section {
      border-bottom: 1px solid #e5e5e5;
      padding: 20px 24px;
    }
    
    .author-section:last-of-type {
      border-bottom: none;
    }
    
    .author-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }
    
    .author-avatar {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      object-fit: cover;
    }
    
    .author-info {
      flex: 1;
    }
    
    .author-name {
      font-weight: 600;
      font-size: 16px;
    }
    
    .author-username {
      color: #666;
      font-size: 14px;
    }
    
    .tweet-count {
      background: #f0f0f0;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 12px;
      color: #666;
    }
    
    .tweet {
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid #f0f0f0;
    }
    
    .tweet:last-child {
      margin-bottom: 0;
      padding-bottom: 0;
      border-bottom: none;
    }
    
    .tweet-text {
      font-size: 15px;
      margin-bottom: 12px;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    
    .tweet-text a {
      color: #1d9bf0;
      text-decoration: none;
    }
    
    .tweet-text a:hover {
      text-decoration: underline;
    }
    
    .tweet-media {
      max-width: 100%;
      border-radius: 8px;
      margin-bottom: 12px;
    }
    
    .tweet-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
      color: #666;
    }
    
    .tweet-meta a {
      color: #1d9bf0;
      text-decoration: none;
    }
    
    .tweet-meta a:hover {
      text-decoration: underline;
    }
    
    footer {
      background: #fafafa;
      padding: 16px 24px;
      text-align: center;
      font-size: 12px;
      color: #999;
    }
    
    footer a {
      color: #666;
    }
    
    @media (max-width: 480px) {
      body { padding: 10px; }
      header, .author-section { padding: 16px; }
      .author-avatar { width: 40px; height: 40px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Your X Digest</h1>
      <p>{{ date_range[0].strftime('%b %d') }} – {{ date_range[1].strftime('%b %d, %Y') }} · {{ total_tweets }} tweets</p>
    </header>
    
    {% for author, tweets in tweets_by_author.items() %}
    <section class="author-section">
      <div class="author-header">
        {% if author.profile_image_url %}
        <img src="{{ author.profile_image_url }}" alt="{{ author.name }}" class="author-avatar">
        {% endif %}
        <div class="author-info">
          <div class="author-name">{{ author.name }}</div>
          <div class="author-username">@{{ author.username }}</div>
        </div>
        <span class="tweet-count">{{ tweets|length }} tweet{% if tweets|length != 1 %}s{% endif %}</span>
      </div>
      
      {% for tweet in tweets %}
      <div class="tweet">
        <p class="tweet-text">{{ tweet.text | linkify | safe }}</p>
        {% for media in tweet.media %}
          {% if media.url %}
          <img src="{{ media.url }}" alt="Tweet media" class="tweet-media">
          {% elif media.preview_image_url %}
          <img src="{{ media.preview_image_url }}" alt="Video thumbnail" class="tweet-media">
          {% endif %}
        {% endfor %}
        <div class="tweet-meta">
          <time>{{ tweet.created_at | format_time }}</time>
          <a href="{{ tweet.url }}">View on X →</a>
        </div>
      </div>
      {% endfor %}
    </section>
    {% endfor %}
    
    <footer>
      <p>Generated automatically by your X Digest bot</p>
    </footer>
  </div>
</body>
</html>
```

---

## 🚀 Implementation Phases

### Phase 1: Project Setup (20 min)
- [ ] Create directory structure (`src/`, `data/`, `templates/`, `tests/`)
- [ ] Create `requirements.txt`
- [ ] Create `.env.example`
- [ ] Create `.gitignore` (include `.env`, `data/`, `__pycache__/`)
- [ ] Create `src/__init__.py`
- [ ] Implement `src/config.py`

### Phase 2: Twitter Client with Search Batching (1 hour)
- [ ] Implement `TwitterClient` class
- [ ] Implement `get_following()` with caching
- [ ] Implement `search_tweets_batch()` with `from:` query
- [ ] Implement `fetch_all_tweets()` orchestrator
- [ ] Test with real API credentials locally

### Phase 3: Email Builder (1 hour)
- [ ] Create `templates/digest.html` template
- [ ] Implement `EmailBuilder` class
- [ ] Implement linkification filters
- [ ] Test template rendering with sample data

### Phase 4: Email Sender (20 min)
- [ ] Create Resend account and get API key
- [ ] Implement `EmailSender` class
- [ ] Implement failure notification
- [ ] Test email delivery

### Phase 5: Integration (20 min)
- [ ] Implement `main.py` orchestrator
- [ ] End-to-end local test
- [ ] Verify API read count (~2-3 per run)

### Phase 6: Railway Deployment (30 min)
- [ ] Create Railway project
- [ ] Configure environment variables
- [ ] Create `railway.json` with daily cron
- [ ] Deploy and verify first run
- [ ] Monitor logs

**Total estimated time: ~3.5 hours**

---

## 🚂 Railway Configuration

### `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python -m src.main",
    "cronSchedule": "0 9 * * *"
  }
}
```

**Cron Options:**
- Daily at 09:00 UTC: `0 9 * * *`
- Weekly (Monday): `0 9 * * 1`

---

## 📊 API Usage Summary

| Operation | When | Reads Used |
|-----------|------|------------|
| Fetch following list | First run + monthly refresh | 1 |
| Search batch 1 (users 1-25) | Every digest | 1 |
| Search batch 2 (users 26-49) | Every digest | 1 |
| **Daily total** | | **2-3** |
| **Monthly total (daily schedule)** | 30 days | **~61 reads** |
| **Free tier limit** | | **100 reads** |
| **Buffer remaining** | | **~39 reads** |

---

## 🔐 Files to .gitignore

```gitignore
# Environment
.env

# Cache
data/

# Python
__pycache__/
*.pyc
.pytest_cache/

# IDE
.vscode/
.idea/
```

---

## 🧪 Testing Checklist

- [ ] API authentication works
- [ ] Following list is fetched and cached correctly
- [ ] Search batching returns tweets from all users
- [ ] Tweets are grouped by author correctly
- [ ] Media URLs are extracted properly
- [ ] Email renders correctly (desktop + mobile)
- [ ] Failure notification sends when errors occur
- [ ] Cache refreshes after `FOLLOWING_CACHE_DAYS`

---

## 🎯 Success Criteria

- [ ] Daily email arrives at expected time
- [ ] All followed accounts' tweets appear (up to 49)
- [ ] Uses ≤3 API reads per run
- [ ] Monthly usage stays under 100 reads
- [ ] Clean, readable design on mobile
- [ ] Zero manual intervention required

---

## 🚦 Ready to Build?

This optimized plan uses **~61 reads/month** for daily digests, well within the **100 read free tier limit**.

Next step: **Phase 1 - Project Setup**
