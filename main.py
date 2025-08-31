from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime, timedelta
import logging

# Import your existing modules
from news_fetcher3 import get_news_about
from sentiment_analysis import analyze_sentiment
from summarizer import generate_overall_summary
from tts import translate_and_generate_audio
from auth_ui import authenticate_user, create_user, verify_token
from models import log_search, get_user_by_id

app = FastAPI(title="PersonaTracker API", version="1.0.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    interests: Optional[List[str]] = []

class SearchRequest(BaseModel):
    query: str
    search_type: str = "Person"  # Person or Company
    max_articles: int = 30
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class ArticleResponse(BaseModel):
    title: str
    content: str
    url: str
    publish_date: Optional[str]
    source: str
    image_url: Optional[str]
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    keywords: Optional[List[str]] = []

class SearchResponse(BaseModel):
    articles: List[ArticleResponse]
    total_count: int
    overall_sentiment: Optional[str] = None
    overall_score: Optional[float] = None
    summary: Optional[str] = None
    audio_url: Optional[str] = None

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Authentication endpoints
@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    try:
        user = authenticate_user(request.username, request.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Generate access token (implement this in your auth module)
        access_token = create_access_token(user['_id'])
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/api/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    try:
        user = create_user(
            username=request.username,
            password=request.password,
            email=request.email,
            interests=request.interests
        )
        if not user:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        access_token = create_access_token(user['_id'])
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# Main search endpoint
@app.post("/api/search", response_model=SearchResponse)
async def search_news(
    request: SearchRequest, 
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Fetch articles
        articles = get_news_about(
            query=request.query,
            max_articles=request.max_articles,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        if not articles:
            return SearchResponse(articles=[], total_count=0)
        
        # Process articles with sentiment analysis
        processed_articles = []
        sentiment_results = []
        
        for article in articles:
            try:
                # Analyze sentiment
                sentiment_result = analyze_sentiment(
                    article.get('content', ''),
                    article.get('title', '')
                )
                
                article_response = ArticleResponse(
                    title=article['title'],
                    content=article['content'],
                    url=article['url'],
                    publish_date=article.get('publish_date'),
                    source=article.get('source', 'Unknown'),
                    image_url=article.get('image_url'),
                    sentiment_score=float(sentiment_result.get('Score', 0)) if sentiment_result else None,
                    sentiment_label=sentiment_result.get('Sentiment') if sentiment_result else None,
                    keywords=sentiment_result.get('Keywords', []) if sentiment_result else []
                )
                
                processed_articles.append(article_response)
                if sentiment_result:
                    sentiment_results.append(sentiment_result)
                    
            except Exception as e:
                logger.error(f"Error processing article: {str(e)}")
                # Add article without sentiment analysis
                processed_articles.append(ArticleResponse(
                    title=article['title'],
                    content=article['content'],
                    url=article['url'],
                    publish_date=article.get('publish_date'),
                    source=article.get('source', 'Unknown'),
                    image_url=article.get('image_url')
                ))
        
        # Calculate overall sentiment
        overall_score = None
        overall_sentiment = None
        summary = None
        
        if sentiment_results:
            scores = [float(r.get('Score', 0)) for r in sentiment_results]
            overall_score = sum(scores) / len(scores)
            overall_sentiment = "Positive" if overall_score > 0 else "Negative" if overall_score < 0 else "Neutral"
            
            # Generate summary
            articles_for_summary = [
                {
                    "summary": r.get('Summary', ''),
                    "sentiment_score": float(r.get('Score', 0)),
                    "topics": r.get('Keywords', [])
                }
                for r in sentiment_results
            ]
            summary = generate_overall_summary(request.query, articles_for_summary)
        
        # Log search in background
        background_tasks.add_task(
            log_search,
            user_id=str(current_user['_id']),
            query=request.query,
            results_count=len(processed_articles),
            articles=[article.dict() for article in processed_articles]
        )
        
        return SearchResponse(
            articles=processed_articles,
            total_count=len(processed_articles),
            overall_sentiment=overall_sentiment,
            overall_score=overall_score,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

# Generate audio summary endpoint
@app.post("/api/audio-summary")
async def generate_audio_summary(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    try:
        summary_text = request.get('text', '')
        if not summary_text:
            raise HTTPException(status_code=400, detail="No text provided")
        
        audio_file = await translate_and_generate_audio(summary_text, "en")
        
        if audio_file:
            return {"audio_url": f"/api/audio/{audio_file}"}
        else:
            raise HTTPException(status_code=500, detail="Audio generation failed")
            
    except Exception as e:
        logger.error(f"Audio generation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Audio generation failed")

# Static file serving for audio files
from fastapi.staticfiles import StaticFiles
app.mount("/api/audio", StaticFiles(directory="audio_files"), name="audio")

# Admin endpoints (if user is admin)
@app.get("/api/admin/stats")
async def get_admin_stats(current_user: dict = Depends(get_current_user)):
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Implement admin statistics logic
    return {"message": "Admin stats endpoint"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)