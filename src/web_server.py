"""Web server for X Digest landing page and subscription handling."""

import base64
import os

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
import httpx
import resend

from src.config import Config
from src.subscribers import SubscriberStore, Subscriber
from src.email_sender import EmailSender

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


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.post("/contact")
async def contact_submit(request: Request, email: str = Form(...), message: str = Form(...)):
    """Handle contact form submission."""
    # Send email to admin
    email_sender = EmailSender(config)
    
    subject = f"New Contact Message from {email}"
    body = f"""
From: {email}
Message:

{message}
"""
    # Send to the admin email (using EMAIL_TO from config)
    # This was previously hardcoded but now respects the ENV configuration
    admin_email = config.email_to
    
    email_sender.send_notification(
        subject=subject,
        body=body,
        to=admin_email
    )
    
    return templates.TemplateResponse(
        "contact.html", 
        {"request": request, "success": True}
    )


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


@app.get("/api/subscribers")
async def get_subscribers(api_key: str = ""):
    """
    Get all active subscribers.
    
    Protected by API_KEY to prevent public access.
    """
    expected_key = config.internal_api_key
    if not expected_key or api_key != expected_key:
        return {"error": "Unauthorized"}, 401
    
    subscribers = subscriber_store.get_all_active()
    return {
        "subscribers": [
            {
                "email": s.email,
                "twitter_handle": s.twitter_handle,
            }
            for s in subscribers
        ]
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


@app.post("/webhook/inbound")
async def inbound_email_webhook(request: Request):
    """
    Handle inbound email webhook from Resend.
    
    Receives emails sent to Resend and forwards them to EMAIL_TO address.
    Configure this endpoint in Resend Dashboard under Webhooks.
    
    See: https://github.com/resend/resend-python/blob/main/examples/receiving_email.py
    """
    try:
        event = await request.json()
    except Exception as e:
        print(f"❌ Failed to parse webhook payload: {e}")
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)
    
    # Only process email.received events
    event_type = event.get("type")
    if event_type != "email.received":
        print(f"ℹ️ Ignoring webhook event: {event_type}")
        return JSONResponse({"status": "ignored", "event_type": event_type})
    
    data = event.get("data", {})
    email_id = data.get("email_id")
    
    if not email_id:
        print("❌ No email_id in webhook payload")
        return JSONResponse({"status": "error", "message": "No email_id"}, status_code=400)
    
    # Initialize Resend with API key
    resend.api_key = config.resend_api_key
    
    try:
        # Fetch the full email content using Emails.Receiving.get()
        # See: https://github.com/resend/resend-python/blob/main/examples/receiving_email.py
        received_email = resend.Emails.Receiving.get(email_id=email_id)
    except Exception as e:
        print(f"❌ Failed to fetch email content: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    
    # Build the forwarded email using data from the received email
    original_from = received_email.get("from", data.get("from", "Unknown"))
    original_to = received_email.get("to", data.get("to", []))
    original_subject = received_email.get("subject", data.get("subject", "No Subject"))
    
    # Create a descriptive subject showing where the email was originally sent
    to_list = original_to if isinstance(original_to, list) else [original_to]
    to_address = to_list[0] if to_list else "unknown"
    subject = f"[Fwd: {to_address}] {original_subject}"
    
    # Get email content
    html_content = received_email.get("html") or ""
    text_content = received_email.get("text") or ""
    
    # Build HTML body with original email info
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <p style="margin: 5px 0;"><strong>From:</strong> {original_from}</p>
            <p style="margin: 5px 0;"><strong>To:</strong> {', '.join(to_list) if isinstance(to_list, list) else to_list}</p>
            <p style="margin: 5px 0;"><strong>Subject:</strong> {original_subject}</p>
        </div>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <div>
            {html_content or text_content or '(No content)'}
        </div>
    </div>
    """
    
    # Handle attachments if any - fetch download URLs
    attachments = []
    received_attachments = received_email.get("attachments", [])
    for att in received_attachments:
        try:
            # Get attachment details with download URL
            att_details = resend.Emails.Receiving.Attachments.get(
                email_id=email_id,
                attachment_id=att["id"]
            )
            # Fetch the actual attachment content
            async with httpx.AsyncClient() as client:
                response = await client.get(att_details["download_url"])
                if response.status_code == 200:
                    attachments.append({
                        "filename": att.get("filename", "attachment"),
                        "content": base64.b64encode(response.content).decode("utf-8"),
                        "content_type": att.get("content_type", "application/octet-stream"),
                    })
        except Exception as e:
            print(f"⚠️ Failed to fetch attachment {att.get('filename', 'unknown')}: {e}")
    
    # Forward the email via Resend
    forward_to = config.email_to
    if not forward_to:
        print("❌ EMAIL_TO not configured")
        return JSONResponse({"status": "error", "message": "EMAIL_TO not configured"}, status_code=500)
    
    params = {
        "from": config.email_from,
        "to": [forward_to],
        "subject": subject,
        "html": html_body,
    }
    
    # Add plain text fallback
    if text_content:
        to_str = ', '.join(to_list) if isinstance(to_list, list) else to_list
        params["text"] = f"From: {original_from}\nTo: {to_str}\nSubject: {original_subject}\n\n---\n\n{text_content}"
    
    if attachments:
        params["attachments"] = attachments
    
    try:
        response = resend.Emails.send(params)
        print(f"📬 Email forwarded successfully (ID: {response.get('id', 'unknown')})")
        return JSONResponse({"status": "forwarded", "email_id": response.get("id")})
    except Exception as e:
        print(f"❌ Failed to forward email: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
