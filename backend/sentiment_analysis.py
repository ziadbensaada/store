# sentiment_analysis.py
import os
import json
import logging
from typing import Dict, Optional
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Groq client
try:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")
    client = Groq(api_key=api_key)
except Exception as e:
    logger.error(f"Failed to initialize Groq client: {str(e)}")
    raise

def analyze_sentiment(company: str, article_content: str) -> Optional[Dict[str, str]]:
    """
    Analyze sentiment of a news article for a specific company using Groq Cloud
    
    Args:
        company (str): Name of the company
        article_content (str): Full text content of the news article
        
    Returns:
        Dict[str, str]: Analysis result with keys: Score, Sentiment, Summary, Keywords
        None: If analysis fails
    """
    import time
    
    # Truncate article content to reduce token usage (first 2000 characters)
    max_article_length = 2000
    if len(article_content) > max_article_length:
        article_content = article_content[:max_article_length] + "... [truncated]"
    
    system_prompt = """You are a sentiment analysis model and summarizer. The user will give the company name and news article as input. 
You have to analyze the news concerning the company to generate the output. You need to determine whether the news affects the company positively or negatively. 
The output should be in JSON format:
{
    "Score": , 
    "Sentiment": , 
    "Summary": , 
    "Keywords": 
}
- Score must be in range [-1,+1] with 2 decimal places
- Sentiment must be Positive/Neutral/Negative based on score
- Summary should be 2-3 lines focusing on company impact
- Keywords should be 3-5 most important topics
- If the article is not relevant to the company, return neutral sentiment (0.0) and mention in the summary."""

    user_input = f"Company: {company}\nNews Article (truncated if too long):\n{article_content}"

    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Add delay between API calls to respect rate limits
            if attempt > 0:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Using the latest stable model from Groq
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.3,
                max_tokens=512,  # Reduced to save tokens
                response_format={"type": "json_object"}  # Ensure JSON output
            )
            
            response_text = completion.choices[0].message.content
            
            # Validate and parse JSON response
            result = json.loads(response_text)
            
            # Validate required fields
            required_fields = {"Score", "Sentiment", "Summary", "Keywords"}
            if not all(field in result for field in required_fields):
                raise ValueError("Missing required fields in response")
                
            # Validate score range
            score = float(result["Score"])
            if not -1 <= score <= 1:
                raise ValueError("Score out of valid range [-1, 1]")
                
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Analysis failed after {max_retries} attempts: {str(e)}")
                return None
            
            if 'rate_limit' in str(e).lower() or '429' in str(e):
                wait_time = retry_delay * (attempt + 1) * 2  # Exponential backoff
                logger.warning(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
    
    # If we get here, all retries failed
    return None
        
    return None

# Example usage
if __name__ == "__main__":
    # Test with sample data
    test_company = input("Enter a company name: ")
    test_article = input("Enter a sample news article: ")
    
    result = analyze_sentiment(test_company, test_article)
    if result:
        print("Analysis Result:")
        print(f"Score: {result['Score']}")
        print(f"Sentiment: {result['Sentiment']}")
        print(f"Summary: {result['Summary']}")
        print(f"Keywords: {', '.join(result['Keywords'])}")
    else:
        print("Failed to analyze sentiment")