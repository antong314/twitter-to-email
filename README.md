# X Daily Digest

A personal X/Twitter digest that emails you all tweets from accounts you follow, grouped by author, delivered daily.

## Features

- 📧 **Daily email digest** of all tweets from people you follow
- 👥 **Grouped by author** for easy reading
- 🖼️ **Media included** (images and video thumbnails)
- 🔄 **Auto-sync followings** - just follow/unfollow on X, no manual lists
- 💰 **Cheap** - ~$0.01/day using twitterapi.io
- 🚀 **Railway deployment** ready with cron scheduling

## How It Works

1. Fetches your followings list from your X account
2. Searches for recent tweets from those accounts
3. Groups them by author and builds a beautiful HTML email
4. Sends it to your inbox via Resend

## Quick Start (Recommended)

### 1. Get twitterapi.io API Key

1. Go to [twitterapi.io](https://twitterapi.io)
2. Sign up and get your API key (starts with free credits)
3. Cost: ~$0.15 per 1,000 tweets (pennies per day)

### 2. Get Resend API Key

1. Sign up at [resend.com](https://resend.com)
2. Create an API key
3. (Optional) Verify your domain for custom sender addresses

### 3. Configure Environment Variables

Create a `.env` file:

```bash
# twitterapi.io (required)
TWITTERAPI_IO_KEY=your_api_key_here
TWITTER_USERNAME=your_twitter_username  # without the @

# Email (required)
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=onboarding@resend.dev
EMAIL_TO=your.email@gmail.com

# Optional settings
DIGEST_DAYS=1              # 1 = daily, 7 = weekly
MAX_ACCOUNTS=49            # Max accounts to include
TIMEZONE=America/New_York  # For timestamp display
```

### 4. Install & Run

```bash
# Install dependencies
uv sync

# Run
uv run python -m src.main
```

That's it! The app automatically fetches who you follow on X.

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway project → "Deploy from GitHub"
3. Add environment variables in Railway dashboard:
   - `TWITTERAPI_IO_KEY`
   - `TWITTER_USERNAME`
   - `RESEND_API_KEY`
   - `EMAIL_FROM`
   - `EMAIL_TO`
4. The app will run daily at 9:00 AM UTC (4:00 AM EST)

### Change Schedule

Edit `railway.json`:

```json
{
  "deploy": {
    "cronSchedule": "0 9 * * *"
  }
}
```

Examples:
- Daily at 9am UTC: `0 9 * * *`
- Daily at 12pm UTC (7am EST): `0 12 * * *`
- Weekly on Monday: `0 9 * * 1`

---

## Alternative: Legacy X API Setup

If you prefer using the official X API instead of twitterapi.io, you can use the legacy backend. Note: This requires maintaining a manual `usernames.txt` file since the free tier doesn't include the followings endpoint.

### X API Credentials

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a project and app
3. Generate credentials:
   - Bearer Token
   - API Key & Secret
   - Access Token & Secret

### Environment Variables (Legacy)

```bash
# Legacy X API credentials (used if TWITTERAPI_IO_KEY not set)
BEARER_TOKEN=your_bearer_token
API_KEY=your_api_key
API_SECRET=your_api_secret
ACCESS_TOKEN=your_access_token
ACCESS_TOKEN_SECRET=your_access_token_secret

# Email settings
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=onboarding@resend.dev
EMAIL_TO=your.email@gmail.com
```

### Manual Username List

Create `usernames.txt` with accounts to track:

```
elonmusk
naval
paulg
```

---

## Project Structure

```
twitter-to-email/
├── src/
│   ├── main.py           # Entry point
│   ├── config.py         # Environment config
│   ├── twitter_client.py # Twitter API clients (twitterapi.io + legacy)
│   ├── email_builder.py  # HTML email generation
│   └── email_sender.py   # Resend integration
├── templates/
│   └── digest.html       # Email template
├── pyproject.toml        # Dependencies
├── railway.json          # Railway deployment config
└── .env                  # Your configuration (not committed)
```

## Costs

### twitterapi.io (Recommended)
| What | Cost |
|------|------|
| Fetch followings | ~$0.00015/call |
| Fetch tweets | ~$0.15/1k tweets |
| **Daily total** | **~$0.01/day** |
| **Monthly total** | **~$0.30/month** |

### Official X API
- Free tier: 100 reads/month (works for daily digests)
- Basic tier: $100/month

## Troubleshooting

### "Missing required environment variables"
Make sure `TWITTERAPI_IO_KEY` and `TWITTER_USERNAME` are set (or all legacy X API credentials).

### "Could not fetch followings"
- Verify your `TWITTER_USERNAME` is correct (without the @)
- Check your `TWITTERAPI_IO_KEY` is valid

### "Rate limited"
The app automatically retries with backoff. If it persists, wait a few minutes.

### "No tweets found"
- Check if your followed accounts have posted recently
- Try increasing `DIGEST_DAYS` to 7

## License

MIT
