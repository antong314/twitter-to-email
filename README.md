# X Daily Digest

A personal X/Twitter digest that emails you all tweets from accounts you follow, grouped by author, delivered daily.

## Features

- 📧 **Daily email digest** of all tweets from people you follow
- 👥 **Grouped by author** for easy reading
- 🖼️ **Media included** (images and video thumbnails)
- 🆓 **Free tier friendly** - uses only ~2-3 API reads per run
- 🚀 **Railway deployment** ready with cron scheduling
- ⚡ **Search batching** optimization to stay within API limits

## How It Works

Instead of making one API call per followed account (which would exceed free tier limits), this app uses the **Recent Search API** with batched `from:` queries:

```
Query: "(from:user1 OR from:user2 OR ... OR from:user25) -is:retweet"
```

This reduces API usage from ~50 reads/run to **~2-3 reads/run**.

### API Usage

| Schedule | Reads/Month | Free Tier (100) |
|----------|-------------|-----------------|
| Daily    | ~61         | ✅ 39 buffer    |
| Weekly   | ~9          | ✅ 91 buffer    |

## Setup

### 1. Get X/Twitter API Credentials

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a project and app
3. Generate these credentials:
   - Bearer Token
   - API Key & Secret
   - Access Token & Secret

### 2. Get Resend API Key

1. Sign up at [resend.com](https://resend.com)
2. Create an API key
3. (Optional) Verify your domain for custom sender addresses

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

```bash
BEARER_TOKEN=your_bearer_token
API_KEY=your_api_key
API_SECRET=your_api_secret
ACCESS_TOKEN=your_access_token
ACCESS_TOKEN_SECRET=your_access_token_secret
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=onboarding@resend.dev
EMAIL_TO=your.email@gmail.com
```

Optional settings:

```bash
DIGEST_DAYS=1              # 1 = daily, 7 = weekly
MAX_ACCOUNTS=49            # Max followed accounts to include
TIMEZONE=UTC               # For timestamp display
FOLLOWING_CACHE_DAYS=30    # How often to refresh following list
```

### 4. Install Dependencies

Using [UV](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

### 5. Run Locally

Using UV:

```bash
uv run python -m src.main
```

Or directly:

```bash
python -m src.main
```

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway project → "Deploy from GitHub"
3. Add environment variables in Railway dashboard
4. The app will run daily at 09:00 UTC (configurable in `railway.json`)

### Cron Schedule

Edit `railway.json` to change the schedule:

```json
{
  "deploy": {
    "cronSchedule": "0 9 * * *"
  }
}
```

Examples:
- Daily at 9am UTC: `0 9 * * *`
- Weekly on Monday: `0 9 * * 1`
- Every 12 hours: `0 */12 * * *`

## Project Structure

```
twitter-to-email/
├── src/
│   ├── main.py           # Entry point
│   ├── config.py         # Environment config
│   ├── twitter_client.py # X API with search batching
│   ├── email_builder.py  # HTML email generation
│   └── email_sender.py   # Resend integration
├── data/
│   └── following_cache.json  # Cached following list
├── templates/
│   └── digest.html       # Email template
├── requirements.txt
├── railway.json          # Railway deployment config
└── .env.example
```

## Troubleshooting

### "Missing required environment variables"

Make sure all required variables are set in your `.env` file or Railway dashboard.

### "No tweets found"

- Check if your followed accounts have posted in the last day
- Try increasing `DIGEST_DAYS` to 7 for weekly

### "Search failed"

- Verify your API credentials are correct
- Check if you've exceeded API rate limits
- The free tier allows 100 reads/month

## License

MIT
