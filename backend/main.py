from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(
    title="PersonaTracker API",
    description="API for PersonaTracker application with admin interface",
    version="1.0.0"
)

# Templates directory
templates = Jinja2Templates(directory="templates")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # 10 minutes
)

# Basic health check endpoint
@app.get("/")
async def root():
    return {"status": "PersonaTracker API is running"}

# Admin interface
@app.get("/admin")
async def admin_interface(request: Request):
    """Serve the admin interface"""
    # In a production environment, you would want to secure this route
    # and ensure only admin users can access it
    admin_html = os.path.join("admin", "index.html")
    
    if os.path.exists(admin_html):
        return FileResponse(admin_html)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin interface not found. Make sure the admin interface is built."
        )

# Import and include routes
from auth import router as auth_router
from search import router as search_router
from audio import router as audio_router
from admin_routes import router as admin_router

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(search_router, prefix="/api", tags=["Search"])
app.include_router(audio_router, prefix="/api", tags=["Audio"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])

# Serve static files (audio and admin interface)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve admin static files if the admin directory exists
if os.path.exists("admin"):
    app.mount("/admin", StaticFiles(directory="admin"), name="admin")