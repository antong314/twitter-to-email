### Detailed Functionality of Your Personal X Weekly Digest App  
(Exactly what it does, step by step – perfect for your Railway deployment and for your own understanding)

| Phase | What the app actually does | Details & Why it matters |
|-------|----------------------------|--------------------------|
| **1. Wake-up (every Monday 09:00 UTC)** | Railway Cron triggers the service → container starts | Zero manual work; always runs on schedule |
| **2. Authenticate with X** | Uses your 5 permanent tokens (Bearer + API Key/Secret + Access Token/Secret) via Tweepy Client | 100% official OAuth 1.0a User Context – fully allowed and stable |
| **3. Fetch your current follows list** | Calls `GET /2/users/me` → `GET /2/users/:id/following` (max_results=1000) | Even if you unfollow/follow someone during the week, next Monday’s digest is always up-to-date. Takes 1 request, <2 seconds |
| **4. Cap at 49 accounts** | Hard limit in code: only the first 49 usernames are processed (you said <50) | Guarantees you stay far below Free-tier limits even if you suddenly follow 200 people |
| **5. Pull every tweet from the last 7 days** | For each of the ≤49 accounts: <br>→ `GET /2/users/:id/tweets` with `start_time = now - 7 days` and `max_results=100` <br>→ Includes replies and retweets if the author tweeted them (exactly what you see in your timeline) | One request per account → max 49 requests. Each request returns up to the last 100 tweets (way more than anyone posts in a week). Tweepy automatically waits ~15–18 seconds between calls on Free tier → total ~12–15 minutes |
| **6. De-duplicate & sort** | Removes duplicate tweet IDs (in case someone appears twice, e.g., you follow them and they’re in a list) <br>Sorts chronologically descending (newest first) or grouped by author – your choice | Clean, pleasant reading experience |
| **7. Build the email** | Generates a beautiful, mobile-friendly HTML email: <br>• Subject: “Your weekly X digest – 37 new tweets” <br>• Header with date range <br>• Tweets grouped by author (or flat timeline) <br>• Each tweet: full text, username, timestamp, direct link, media thumbnails if present <br>• “View on X” button for every tweet <br>• Unsubscribe / pause footer (no-op link is fine for personal use) | Looks professional, not a raw dump |
| **8. Send the email** | Via Resend.com (recommended) or SMTP <br>From: digest@yourdomain.com (or your Gmail) <br>To: only your personal email address | Delivery is instant and reliable. Resend free tier = 3 000 emails/month → forever free |
| **9. Clean up & shut down** | Deletes all fetched tweets from memory <br>Container exits → Railway spins it down | Zero data retained, fully privacy-compliant |
| **10. Failure handling (optional but smart)** | If anything errors (rare), send yourself a short failure email with the exception text | You always know if a digest was skipped |

### What the user (you) experiences
- Every Monday morning: one single email in your inbox.
- Zero login, zero clicking, zero scrolling on X required.
- You see literally every tweet your <50 accounts posted in the past week, including replies and quote tweets.
- Takes you 3–10 minutes to read instead of hours of doomscrolling.
- If someone tweeted 50 times and someone else tweeted once, both appear proportionally.

This is the cleanest, most compliant, lowest-maintenance version possible in 2025 for exactly your use case (<50 follows).  
It will keep working reliably for years on Railway’s free tier with zero changes needed.

Ready when you are – just say “go” and I’ll give you the complete ready-to-deploy repo (with HTML template, railway.json, requirements.txt, etc.). You’ll be live in <30 minutes.