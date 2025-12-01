"""Web server for X Digest landing page and subscription handling."""

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
import os

from src.config import Config
from src.subscribers import SubscriberStore, Subscriber

app = FastAPI(title="X Digest")

# Force HTTPS in production (when behind a proxy like Railway)
if os.environ.get("RAILWAY_ENVIRONMENT"):
    app.add_middleware(HTTPSRedirectMiddleware)

# Load config
config = Config.from_env()

# Get the absolute path to the web directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(WEB_DIR, "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(WEB_DIR, "templates"))

# Subscriber storage (uses DATA_DIR from config)
subscriber_store = SubscriberStore(data_dir=config.data_dir)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/subscribe")
async def subscribe(request: Request, email: str = Form(...), handle: str = Form(...)):
    """
    Handle new subscription.
    
    Saves the subscriber to JSON storage and shows a success page.
    """
    # Create and save subscriber
    subscriber = Subscriber.create(twitter_handle=handle, email=email)
    is_new = subscriber_store.add(subscriber)
    
    # Return success page
    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "email": email,
            "handle": subscriber.twitter_handle,
            "is_new": is_new,
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "subscribers": subscriber_store.count_active(),
    }


@app.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(request: Request, email: str):
    """
    Handle unsubscribe request.
    
    Deactivates the subscriber and shows confirmation page.
    """
    # Deactivate subscriber
    was_subscribed = subscriber_store.deactivate(email)
    
    return templates.TemplateResponse(
        "unsubscribe.html",
        {
            "request": request,
            "email": email,
            "was_subscribed": was_subscribed,
        }
    )
