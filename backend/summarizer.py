import os
import logging
import time
import json
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
from functools import lru_cache
from groq import Groq
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Cache configuration
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 86400  # 24 hours in seconds

# Initialize Groq client
try:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")
    client = Groq(api_key=api_key)
except Exception as e:
    logger.error(f"Failed to initialize Groq client: {str(e)}")
    raise

def get_cache_key(*args: Any) -> str:
    """Generate a cache key from function arguments."""
    key = "_".join(str(arg) for arg in args)
    return hashlib.md5(key.encode('utf-8')).hexdigest()

def load_from_cache(cache_key: str) -> Optional[Dict]:
    """Load data from cache file if it exists and is not expired."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None
        
    try:
        mtime = cache_file.stat().st_mtime
        if time.time() - mtime > CACHE_TTL:
            return None
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error reading cache file {cache_file}: {e}")
        return None

def save_to_cache(cache_key: str, data: Dict) -> None:
    """Save data to cache file."""
    try:
        cache_file = CACHE_DIR / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'data': data,
                'timestamp': time.time()
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error writing to cache file {cache_file}: {e}")

@lru_cache(maxsize=128)
def _get_cached_summary(company: str, article_urls: tuple) -> Optional[str]:
    """
    Internal cached function that checks the cache for an existing summary.
    Returns the cached summary if found, None otherwise.
    """
    cache_key = get_cache_key('overall_summary', company, *article_urls)
    cached = load_from_cache(cache_key)
    return cached.get('data') if cached and 'data' in cached else None

def generate_overall_summary(company: str, articles: List[Dict[str, str]]) -> Optional[str]:
    """
    Generate an overall summary by combining individual summaries and sentiment scores using an LLM API.
    Uses both in-memory and file-based caching to improve performance.
    
    Args:
        company (str): Name of the company
        articles (List[Dict[str, str]]): List of articles, each containing 'summary' and 'sentiment_score'
        
    Returns:
        Optional[str]: Generated summary or None if there was an error
    """
    if not articles:
        return None
        
    # Create a sorted tuple of article URLs for caching
    article_urls = tuple(sorted(a.get('url', '') for a in articles))
    
    # Try to get from cache first
    cached_summary = _get_cached_summary(company, article_urls)
    if cached_summary:
        logger.info(f"Using cached summary for {company}")
        return cached_summary
        
    logger.info(f"Generating new summary for {company} (not found in cache)")
    
    # Create a mapping of URLs to article data
    article_map = {a.get('url', ''): a for a in articles}
    
    # Generate the summary using Groq API
    try:
        # Prepare the prompt
        prompt = f"""You are a financial analyst. Provide a comprehensive summary of the following news articles about {company}.
        Consider the sentiment of each article and highlight key points, trends, and any significant events mentioned.
        Focus on facts and avoid speculation. Keep the summary under 200 words.
        
        Articles:
        """
        
        # Add each article's summary and sentiment to the prompt
        for i, url in enumerate(article_urls, 1):
            article = article_map.get(url, {})
            prompt += f"{i}. Summary: {article.get('summary', '')}\n"
            if 'sentiment_score' in article:
                prompt += f"   Sentiment: {article['sentiment_score']}\n"
            prompt += "\n"
        
        # Make the API call with retry logic
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Add delay between API calls to respect rate limits
                if attempt > 0:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    
                response = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that provides concise and accurate summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                
                summary = response.choices[0].message.content
                
                # Save to cache if we got a valid summary
                if summary and isinstance(summary, str) and len(summary.strip()) > 0:
                    try:
                        cache_key = get_cache_key('overall_summary', company, *article_urls)
                        save_to_cache(cache_key, summary)
                    except Exception as e:
                        logger.warning(f"Failed to save to cache: {e}")
                return summary
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate summary after {max_retries} attempts: {str(e)}")
                    return None
                wait_time = retry_delay * (attempt + 1) * 2  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    # Example articles for testing
    test_articles = [
        {
            "title": "Test Article 1",
            "summary": "This is a test article about the company.",
            "sentiment_score": 0.8,
            "url": "http://example.com/1"
        },
        {
            "title": "Test Article 2",
            "summary": "Another test article with different content.",
            "sentiment_score": 0.2,
            "url": "http://example.com/2"
        }
    ]
    
    # Generate and print a summary
    summary = generate_overall_summary("Test Company", test_articles)
    if summary:
        print("Generated Summary:")
        print(summary)
    else:
        print("Failed to generate summary.")