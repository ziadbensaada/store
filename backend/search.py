from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime, timedelta
import sys
import os
import logging
from sentiment_analysis import analyze_sentiment
from summarizer import generate_overall_summary

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
            
        logger.info(f"Analyzing sentiment for article: {article_id}")
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

@router.post("/search")
async def search_articles(search_query: SearchQuery):
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
