# X Daily Digest

A personal X/Twitter digest that emails you all tweets from accounts you follow, grouped by author, delivered daily.

## Features

- 📧 **Daily email digest** of all tweets from people you follow
- 👥 **Grouped by author** for easy reading
- 🖼️ **Media included** (images and video thumbnails)
- 🔄 **Auto-sync followings** - just follow/unfollow on X, no manual lists
- 💰 **Cheap** - ~$0.01/day using twitterapi.io
- 🚀 **Railway deployment** ready with cron scheduling
- 🌐 **Landing page** for collecting subscribers
- 👥 **Multi-user support** - handle multiple subscribers

## Architecture

This is a monorepo with two services:

1. **Web Service** - FastAPI server for landing page & subscriptions
2. **Cron Service** - Daily digest generator that emails all subscribers

## Quick Start (Local Development)

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

# Email (required)
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=digest@yourdomain.com

# App settings (optional)
DIGEST_DAYS=1              # 1 = daily, 7 = weekly
MAX_ACCOUNTS=49            # Max accounts to include per subscriber
TIMEZONE=America/New_York  # For timestamp display
BASE_URL=http://localhost:8000  # For unsubscribe links
```

### 4. Install & Run

```bash
# Install dependencies
uv sync

# Run web server (landing page)
uv run uvicorn src.web_server:app --reload --port 8000

# Run cron job manually (in another terminal)
uv run python -m src.main
```

Visit http://localhost:8000 to see the landing page and subscribe.

---

## Deploy to Railway (Two Services)

Railway supports monorepo deployments where multiple services share the same codebase.

### Step 1: Push to GitHub

Push this repo to your GitHub account.

### Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository

### Step 3: Create Web Service

The first service is created automatically. Configure it:

1. Click on the service → **Settings**
2. Change the name to `web` (optional)
3. Under **Deploy** → **Start Command**, set:
   ```
   ~/.local/bin/uv run uvicorn src.web_server:app --host 0.0.0.0 --port $PORT
   ```
4. Under **Networking**, click **"Generate Domain"** to get a public URL
5. Add environment variables (see below)

### Step 4: Create Cron Service

1. In your project, click **"+ New"** → **"GitHub Repo"**
2. Select the **same repository** again
3. Click on the new service → **Settings**
4. Change the name to `cron`
5. Under **Deploy** → **Start Command**, set:
   ```
   ~/.local/bin/uv run python -m src.main
   ```
6. Under **Deploy** → **Cron Schedule**, set:
   ```
   0 9 * * *
   ```
   (This runs daily at 9:00 AM UTC)
7. Add the same environment variables

### Step 5: Environment Variables

Add these to **both services** (use Railway's shared variables feature):

| Variable | Required | Description |
|----------|----------|-------------|
| `TWITTERAPI_IO_KEY` | ✅ | Your twitterapi.io API key |
| `RESEND_API_KEY` | ✅ | Your Resend API key |
| `EMAIL_FROM` | ✅ | Sender email (e.g., `digest@yourdomain.com`) |
| `BASE_URL` | ✅ | Your web service URL (e.g., `https://web-production-xxxx.up.railway.app`) |
| `DIGEST_DAYS` | ❌ | Days to include (default: 1) |
| `MAX_ACCOUNTS` | ❌ | Max accounts per user (default: 49) |
| `TIMEZONE` | ❌ | Timezone for display (default: UTC) |

### Step 6: Set Up Shared Variables (Recommended)

To avoid duplicating variables:

1. In your Railway project, click **"+ New"** → **"Shared Variable"**
2. Add each variable once
3. Reference them in both services using `${{shared.VARIABLE_NAME}}`

### Cron Schedule Examples

| Schedule | Cron Expression |
|----------|-----------------|
| Daily at 9am UTC | `0 9 * * *` |
| Daily at 7am EST | `0 12 * * *` |
| Daily at 6am PST | `0 14 * * *` |
| Weekly on Monday 9am | `0 9 * * 1` |

---

## Data Storage

Currently, subscribers are stored in a JSON file (`data/subscribers.json`).

⚠️ **Important for Railway**: Railway's filesystem is ephemeral - data is lost on each deploy. For production, consider:

1. **Railway Volume** - Attach a persistent volume to the web service
2. **Database** - Use Railway's PostgreSQL addon (requires code changes)
3. **External Storage** - Use a managed database service

For small-scale personal use, you can manually backup/restore the JSON file.

---

## Project Structure

```
twitter-to-email/
├── src/
│   ├── main.py           # Cron job entry point
│   ├── config.py         # Environment config
│   ├── twitter_client.py # Twitter API clients
│   ├── email_builder.py  # HTML email generation
│   ├── email_sender.py   # Resend integration
│   ├── subscribers.py    # Subscriber storage
│   └── web_server.py     # FastAPI web server
├── web/
│   ├── static/           # CSS, images
│   └── templates/        # Landing page, success, unsubscribe
├── templates/
│   └── digest.html       # Email template
├── data/
│   └── subscribers.json  # Subscriber database (gitignored)
├── pyproject.toml        # Dependencies
├── railway.json          # Railway build config
└── .env                  # Your configuration (gitignored)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Landing page |
| `/subscribe` | POST | Subscribe (form: email, handle) |
| `/unsubscribe?email=...` | GET | Unsubscribe |
| `/health` | GET | Health check with subscriber count |

## Costs

### twitterapi.io (Recommended)
| What | Cost |
|------|------|
| Fetch followings | ~$0.00015/call |
| Fetch tweets | ~$0.15/1k tweets |
| **Per subscriber/day** | **~$0.01** |

### Railway
- Hobby plan: $5/month (includes enough for both services)
- Usage-based pricing for compute

### Resend
- Free tier: 3,000 emails/month
- Pro: $20/month for 50,000 emails

## Troubleshooting

### "Missing required environment variables"
Make sure `TWITTERAPI_IO_KEY` is set.

### "Could not fetch followings"
- Verify the Twitter handle is correct (without the @)
- Check your `TWITTERAPI_IO_KEY` is valid

### "Rate limited"
The app automatically retries with backoff. If it persists, wait a few minutes.

### "No tweets found"
- Check if the followed accounts have posted recently
- Try increasing `DIGEST_DAYS` to 7

### Unsubscribe links not working
- Make sure `BASE_URL` is set to your Railway web service URL
- Include the full URL with `https://`

## License

MIT
