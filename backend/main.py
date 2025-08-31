from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PersonaTracker API")

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

# Import and include routes
from auth import router as auth_router
from search import router as search_router
from audio import router as audio_router

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(search_router, prefix="/api", tags=["Search"])
app.include_router(audio_router, prefix="/api", tags=["Audio"])

# Serve static files (audio)
app.mount("/static", StaticFiles(directory="static"), name="static")