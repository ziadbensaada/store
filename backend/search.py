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

def analyze_article_sentiment(article: Dict, query: str) -> Dict:
    """Analyze sentiment for a single article"""
    try:
        content = f"{article.get('title', '')} {article.get('content', '')}"
        if not content.strip():
            return {"score": 0, "label": "neutral"}
            
        # Use the sentiment analysis module
        sentiment = analyze_sentiment(query, content)
        if not sentiment:
            return {"score": 0, "label": "neutral"}
            
        # Map the sentiment score to a label
        score = float(sentiment.get("Score", 0))
        if score >= 0.1:
            label = "positive"
        elif score <= -0.1:
            label = "negative"
        else:
            label = "neutral"
            
        return {
            "score": score,
            "label": label,
            "summary": sentiment.get("Summary", ""),
            "keywords": sentiment.get("Keywords", [])
        }
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {str(e)}")
        return {"score": 0, "label": "neutral"}

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
    """
    Search for articles using the news_fetcher3 module with sentiment analysis.
    If no query is provided but user_interests are available, fetch recommended articles.
    """
    try:
        # Initialize articles list
        articles = []
        
        # If we have a query, search for it
        if search_query.query:
            articles = get_news_about(
                query=search_query.query,
                max_articles=search_query.max_articles,
                start_date=search_query.start_date,
                end_date=search_query.end_date
            )
            logger.info(f"Found {len(articles)} articles for query: {search_query.query}")
        # If no query but we have user interests, get recommended articles
        elif search_query.user_interests:
            articles = get_recommended_articles(
                interests=search_query.user_interests,
                max_articles=search_query.max_articles
            )
            logger.info(f"Found {len(articles)} recommended articles based on user interests")
        
        if not articles:
            return {
                "total_count": 0,
                "articles": [],
                "overall_sentiment": "neutral",
                "overall_score": 0,
                "summary": "No articles found. Please try a different search or check back later."
            }
        
        # Process articles with sentiment analysis
        processed_articles = []
        for article in articles:
            try:
                # Use the query or the first interest for sentiment analysis
                query_for_sentiment = search_query.query or (search_query.user_interests[0] if search_query.user_interests else "")
                sentiment = analyze_article_sentiment(article, query_for_sentiment)
                processed_articles.append({
                    **article,
                    "sentiment": sentiment
                })
            except Exception as e:
                logger.error(f"Error processing article: {str(e)}")
                continue
        
        # Calculate overall sentiment
        if processed_articles:
            scores = [a["sentiment"]["score"] for a in processed_articles if a.get("sentiment")]
            overall_score = sum(scores) / len(scores) if scores else 0
            if overall_score >= 0.1:
                overall_sentiment = "positive"
            elif overall_score <= -0.1:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
        else:
            overall_score = 0
            overall_sentiment = "neutral"
            
        # Generate summary
        if search_query.query:
            summary = generate_overall_summary(
                search_query.query,
                [a["content"] for a in processed_articles if a.get("content")]
            ) or f"Found {len(processed_articles)} articles about {search_query.query}"
        elif search_query.user_interests:
            summary = f"Found {len(processed_articles)} articles based on your interests: {', '.join(search_query.user_interests)}"
        
        return {
            "total_count": len(processed_articles),
            "articles": processed_articles,
            "overall_sentiment": overall_sentiment,
            "overall_score": overall_score,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
