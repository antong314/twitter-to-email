"""Quick script to test Twitter API authentication."""

import tweepy
from dotenv import load_dotenv
from os import environ

load_dotenv()

print("🔍 Checking credentials...\n")

# Check what's loaded
bearer = environ.get("BEARER_TOKEN", "")
api_key = environ.get("API_KEY", "")
api_secret = environ.get("API_SECRET", "")
access_token = environ.get("ACCESS_TOKEN", "")
access_secret = environ.get("ACCESS_TOKEN_SECRET", "")

print(f"BEARER_TOKEN:        {'✅ Set' if bearer else '❌ Missing'} ({len(bearer)} chars)")
print(f"API_KEY:             {'✅ Set' if api_key else '❌ Missing'} ({len(api_key)} chars)")
print(f"API_SECRET:          {'✅ Set' if api_secret else '❌ Missing'} ({len(api_secret)} chars)")
print(f"ACCESS_TOKEN:        {'✅ Set' if access_token else '❌ Missing'} ({len(access_token)} chars)")
print(f"ACCESS_TOKEN_SECRET: {'✅ Set' if access_secret else '❌ Missing'} ({len(access_secret)} chars)")

print("\n" + "=" * 50)
print("🧪 Testing API connection...\n")

try:
    client = tweepy.Client(
        bearer_token=bearer,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    
    # Test 1: Get authenticated user (uses OAuth 1.0a)
    print("Test 1: Getting authenticated user...")
    me = client.get_me()
    if me.data:
        print(f"  ✅ Success! Logged in as: @{me.data.username}")
    else:
        print("  ❌ Failed - no user data returned")
        
except tweepy.Forbidden as e:
    print(f"  ❌ 403 Forbidden: {e}")
    print("\n⚠️  This usually means:")
    print("   1. Your app is NOT inside a Project (check Developer Portal)")
    print("   2. You need to regenerate keys AFTER attaching to a Project")
    print("   3. Your Free tier may not have access to this endpoint")
    
except tweepy.Unauthorized as e:
    print(f"  ❌ 401 Unauthorized: {e}")
    print("\n⚠️  Your credentials are invalid. Regenerate them in Developer Portal.")
    
except Exception as e:
    print(f"  ❌ Error: {type(e).__name__}: {e}")

# Test 2: Get following list (this is what's failing)
print("\nTest 2: Getting following list...")
try:
    client = tweepy.Client(
        bearer_token=bearer,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    me = client.get_me()
    if me.data:
        response = client.get_users_following(id=me.data.id, max_results=10)
        if response.data:
            print(f"  ✅ Success! You follow {len(response.data)} users (showing first 10)")
            for user in response.data[:3]:
                print(f"      - @{user.username}")
        else:
            print("  ⚠️ No following data returned")
except tweepy.Forbidden as e:
    print(f"  ❌ 403 Forbidden on get_users_following")
    print(f"     Error: {e}")
    print("\n  💡 This endpoint may not be available on Free tier!")
    print("     The Free tier (100 reads/month) may not include 'following' endpoint.")
except Exception as e:
    print(f"  ❌ Error: {type(e).__name__}: {e}")

# Test 3: Try search (our batching approach)
print("\nTest 3: Testing search endpoint (our main approach)...")
try:
    client = tweepy.Client(bearer_token=bearer)
    response = client.search_recent_tweets(
        query="from:elonmusk -is:retweet",
        max_results=10
    )
    if response.data:
        print(f"  ✅ Success! Search works. Found {len(response.data)} tweets")
    else:
        print("  ⚠️ Search returned no results (but endpoint works)")
except tweepy.Forbidden as e:
    print(f"  ❌ 403 Forbidden on search")
    print(f"     Error: {e}")
except Exception as e:
    print(f"  ❌ Error: {type(e).__name__}: {e}")

