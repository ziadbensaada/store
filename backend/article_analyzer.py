from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel
from .sentiment_analysis import analyze_sentiment
from .summarizer import generate_overall_summary
import logging

router = APIRouter(prefix="/api/articles", tags=["Article Analysis"])
logger = logging.getLogger(__name__)

class Article(BaseModel):
    id: str
    title: str
    content: str
    url: str
    published_at: Optional[str] = None

class AnalysisResult(BaseModel):
    article_id: str
    title: str
    sentiment: Dict[str, str]
    summary: str

@router.post("/analyze", response_model=List[AnalysisResult])
async def analyze_articles(articles: List[Article]):
    """
    Analyze sentiment and generate summaries for a list of articles
    """
    results = []
    
    for article in articles:
        try:
            # Analyze sentiment
            sentiment = analyze_sentiment(article.title, article.content)
            
            # Generate summary (using title and first 2000 chars of content)
            summary = await generate_overall_summary(
                company=article.title,
                articles=[{"content": article.content[:2000], "sentiment": ""}]
            )
            
            results.append(AnalysisResult(
                article_id=article.id,
                title=article.title,
                sentiment={
                    "score": sentiment.get("Score", "0"),
                    "label": sentiment.get("Sentiment", "neutral"),
                    "keywords": sentiment.get("Keywords", "")
                },
                summary=summary or "No summary available"
            ))
            
        except Exception as e:
            logger.error(f"Error analyzing article {article.id}: {str(e)}")
            results.append(AnalysisResult(
                article_id=article.id,
                title=article.title,
                sentiment={"score": "0", "label": "error", "keywords": ""},
                summary=f"Error analyzing article: {str(e)}"
            ))
    
    return results
