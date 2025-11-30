from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="X Digest")

# Get the absolute path to the web directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(WEB_DIR, "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(WEB_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/subscribe")
async def subscribe(email: str = Form(...), handle: str = Form(...)):
    # Placeholder for subscription logic
    return {"message": f"Subscribed {email} for handle {handle}"}

