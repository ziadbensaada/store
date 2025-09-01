from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime, timedelta
import sys
import os
import logging
from bson import ObjectId
from models import search_history_collection
from sentiment_analysis import analyze_sentiment
from summarizer import generate_overall_summary
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import news_fetcher3
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from news_fetcher3 import get_news_about

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[Dict]:
    """Get the current user from the JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("user_id")
        if username is None:
            raise credentials_exception
        return {"user_id": user_id, "username": username}
    except JWTError:
        return None

class SearchQuery(BaseModel):
    query: str
    search_type: str = "Person"
    max_articles: int = 30
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    user_interests: Optional[List[str]] = None

router = APIRouter()

def analyze_article_sentiment(article_id: str, query: str, content: str) -> Dict:
    """Analyze sentiment for a single article manually"""
    try:
        if not content.strip():
            return {
                "article_id": article_id,
                "score": 0, 
                "label": "neutral",
                "summary": "",
                "keywords": []
            }
            
        logger.info(f"Analyzing sentiment for article: {article_id} with query: {query}")
        # Use the query as the company name for sentiment analysis
        sentiment = analyze_sentiment(query, content)
        if not sentiment:
            return {
                "article_id": article_id,
                "score": 0, 
                "label": "neutral",
                "summary": "",
                "keywords": []
            }
            
        # Map the sentiment score to a label
        score = float(sentiment.get("Score", 0))
        if score >= 0.1:
            label = "positive"
        elif score <= -0.1:
            label = "negative"
        else:
            label = "neutral"
            
        return {
            "article_id": article_id,
            "score": score,
            "label": label,
            "summary": sentiment.get("Summary", ""),
            "keywords": sentiment.get("Keywords", [])
        }
    except Exception as e:
        logger.error(f"Error analyzing sentiment for article {article_id}: {str(e)}")
        return {
            "article_id": article_id,
            "score": 0, 
            "label": "error",
            "error": str(e)
        }

def get_recommended_articles(interests: List[str], max_articles: int = 10) -> List[Dict]:
    """Get recommended articles based on user interests"""
    if not interests:
        return []
        
    recommended = []
    articles_per_interest = max(1, max_articles // len(interests))
    
    for interest in interests:
        try:
            logger.info(f"Fetching recommended articles for interest: {interest}")
            articles = get_news_about(
                query=interest,
                max_articles=articles_per_interest,
                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d')
            )
            
            if not articles:
                logger.warning(f"No articles found for interest: {interest}")
                continue
                
            recommended.extend(articles)
            logger.info(f"Found {len(articles)} articles for interest: {interest}")
            
            # If we've got enough articles, we can stop early
            if len(recommended) >= max_articles:
                recommended = recommended[:max_articles]
                break
                
        except Exception as e:
            logger.error(f"Error fetching articles for interest '{interest}': {str(e)}")
            continue
    
    logger.info(f"Total recommended articles found: {len(recommended)}")
    return recommended

async def log_search(user_id: str, query: str, results_count: int, articles: List[Dict] = None, current_user: Dict = None):
    """Log a search query to the database"""
    try:
        # Get username from current_user if available, otherwise use user_id
        username = None
        if current_user and isinstance(current_user, dict):
            username = current_user.get('username')
        
        # If we still don't have a username, try to get it from the users collection
        if not username and user_id and user_id != "admin":
            from bson import ObjectId
            try:
                user = users_collection.find_one({"_id": ObjectId(user_id)})
                if user:
                    username = user.get('username')
            except:
                pass
        
        # If still no username, use the user_id as a fallback
        if not username:
            username = str(user_id) if user_id else "Unknown User"
        
        search_log = {
            "user_id": user_id,
            "username": username,  # Store the resolved username
            "query": query,
            "timestamp": datetime.utcnow(),
            "results_count": results_count,
            "articles": []
        }
        
        if articles:
            # Store basic article info (not the full content to save space)
            for article in articles:  # Store all articles, not just first 10
                clean_article = {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                    "published_at": article.get("published_at", ""),
                    "sentiment": article.get("sentiment", {})
                }
                search_log["articles"].append(clean_article)
        
        # Insert the search log
        result = search_history_collection.insert_one(search_log)
        logger.info(f"Logged search with ID: {result.inserted_id}")
        return True
    except Exception as e:
        logger.error(f"Error logging search: {str(e)}")
        return False

@router.post("/search")
async def search_articles(
    search_query: SearchQuery, 
    request: Request,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    try:
        logger.info(f"Received search request: {search_query}")
        
        # Get articles based on search query or user interests
        if search_query.query:
            logger.info(f"Performing search for query: {search_query.query}")
            articles = get_news_about(
                query=search_query.query,
                max_articles=search_query.max_articles,
                start_date=search_query.start_date,
                end_date=search_query.end_date
            )
            logger.info(f"Found {len(articles)} articles for query: {search_query.query}")
        else:
            logger.info("No search query provided, getting recommended articles")
            articles = get_recommended_articles(
                interests=search_query.user_interests or [],
                max_articles=search_query.max_articles
            )
            logger.info(f"Found {len(articles)} recommended articles")
        
        # Add article IDs if not present
        for i, article in enumerate(articles):
            if 'id' not in article:
                article['id'] = f'article_{i}_{hash(article.get("url", ""))}'
        
        # Log the search if user is authenticated
        if current_user and search_query.query:
            # For admin users, use "admin" as user_id, otherwise use the user's ID
            user_id = "admin" if current_user.get("username") == "admin" else current_user["user_id"]
            await log_search(
                user_id=user_id,
                query=search_query.query,
                results_count=len(articles),
                articles=articles,
                current_user=current_user  # Pass the current user to include username
            )
        
        return {
            "query": search_query.query,
            "articles": articles,
            "total_count": len(articles)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

class SentimentAnalysisRequest(BaseModel):
    content: str
    query: str

@router.post("/analyze-sentiment/{article_id}")
async def analyze_sentiment_endpoint(article_id: str, request: SentimentAnalysisRequest):
    """Endpoint to analyze sentiment for a single article"""
    try:
        logger.info(f"Analyzing sentiment for article: {article_id}")
        logger.info(f"Content length: {len(request.content)} chars, Query: {request.query}")
        
        if not request.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content cannot be empty"
            )
            
        result = analyze_article_sentiment(article_id, request.query, request.content)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze sentiment: {str(e)}"
        )
