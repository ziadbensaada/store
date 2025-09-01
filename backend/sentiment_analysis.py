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
    
    system_prompt = """You are a financial news analyst. Return ONLY valid JSON with this exact format:

{
    "Score": 0.75,
    "Sentiment": "Positive",
    "Summary": "Brief summary here",
    "Keywords": ["keyword1", "keyword2", "keyword3"],
    "Reasoning": "Brief reasoning here"
}

CRITICAL JSON RULES:
- Score must be a number between -1.0 and 1.0 (no + sign, no quotes)
- Sentiment must be exactly "Positive", "Neutral", or "Negative" (with quotes)
- All strings must be in double quotes
- No trailing commas
- No extra text before or after JSON

ANALYSIS RULES:
- Problem-Solution Context: Articles about problems a company solves are often POSITIVE
- Innovation/Progress: New developments and tech advances are usually POSITIVE  
- Market Position: Company strength and competitive advantage are POSITIVE
- Challenges as Opportunities: Challenges the company can handle are often POSITIVE

SCORING:
- 0.8 to 1.0: Extremely positive (major breakthrough, strong advantage)
- 0.4 to 0.7: Positive (innovation, problem-solving, market strength)
- 0.1 to 0.3: Slightly positive (minor positive developments)
- -0.1 to 0.1: Neutral (no clear company impact)
- -0.1 to -0.3: Slightly negative (minor concerns)
- -0.4 to -0.7: Negative (significant problems, disadvantages)
- -0.8 to -1.0: Extremely negative (major failures, serious issues)

Focus on COMPANY impact. Return ONLY the JSON object."""

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
                # Try fallback sentiment analysis
                logger.info("Attempting fallback sentiment analysis...")
                return fallback_sentiment_analysis(company, article_content)
            
            if 'rate_limit' in str(e).lower() or '429' in str(e):
                wait_time = retry_delay * (attempt + 1) * 2  # Exponential backoff
                logger.warning(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
    
    # If we get here, all retries failed
    return None

def fallback_sentiment_analysis(company: str, article_content: str) -> Optional[Dict[str, str]]:
    """
    Fallback sentiment analysis using traditional NLP techniques
    """
    try:
        import re
        from collections import Counter
        
        # Clean and prepare text
        text = article_content.lower()
        
        # Define sentiment word lists with context awareness
        positive_words = {
            'innovation', 'breakthrough', 'advance', 'improve', 'growth', 'profit', 'success',
            'launch', 'release', 'announce', 'develop', 'create', 'build', 'expand',
            'leadership', 'market leader', 'competitive', 'advantage', 'solution', 'solve',
            'technology', 'digital', 'ai', 'artificial intelligence', 'machine learning',
            'efficiency', 'performance', 'quality', 'award', 'recognition', 'partnership',
            'investment', 'funding', 'revenue', 'sales', 'customer', 'user', 'adoption'
        }
        
        negative_words = {
            'failure', 'loss', 'decline', 'decrease', 'problem', 'issue', 'error',
            'bug', 'crash', 'hack', 'breach', 'security', 'privacy', 'lawsuit',
            'fine', 'penalty', 'regulation', 'ban', 'restrict', 'limit', 'delay',
            'cancel', 'shutdown', 'bankruptcy', 'layoff', 'fired', 'resign', 'quit'
        }
        
        # Context-aware positive patterns (problems that are opportunities)
        positive_patterns = [
            r'solve.*problem', r'address.*challenge', r'overcome.*obstacle',
            r'innovative.*solution', r'breakthrough.*technology', r'leading.*industry',
            r'market.*leader', r'competitive.*advantage', r'strategic.*partnership'
        ]
        
        # Count positive and negative words
        words = re.findall(r'\b\w+\b', text)
        word_count = Counter(words)
        
        positive_score = sum(word_count[word] for word in positive_words if word in word_count)
        negative_score = sum(word_count[word] for word in negative_words if word in word_count)
        
        # Check for positive patterns
        pattern_score = 0
        for pattern in positive_patterns:
            if re.search(pattern, text):
                pattern_score += 2  # Give extra weight to context-aware positives
        
        # Calculate final score
        total_score = positive_score + pattern_score - negative_score
        
        # Normalize score to [-1, 1] range
        if total_score > 0:
            normalized_score = min(0.8, total_score / 10)  # Cap at 0.8 for fallback
        elif total_score < 0:
            normalized_score = max(-0.8, total_score / 10)  # Cap at -0.8 for fallback
        else:
            normalized_score = 0.0
        
        # Determine sentiment
        if normalized_score > 0.1:
            sentiment = "Positive"
        elif normalized_score < -0.1:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
        
        # Generate summary
        if normalized_score > 0.3:
            summary = f"Article shows positive developments for {company} with focus on innovation and market strength."
        elif normalized_score > 0:
            summary = f"Article has positive elements for {company} with some promising developments."
        elif normalized_score < -0.3:
            summary = f"Article contains concerning elements for {company} that may impact performance."
        elif normalized_score < 0:
            summary = f"Article has some negative aspects for {company} but overall impact is limited."
        else:
            summary = f"Article appears neutral for {company} with no clear positive or negative impact."
        
        # Extract keywords
        keywords = [word for word, count in word_count.most_common(10) 
                   if len(word) > 3 and word not in ['the', 'and', 'for', 'with', 'this', 'that']]
        keywords = keywords[:5]  # Limit to 5 keywords
        
        return {
            "Score": round(normalized_score, 2),
            "Sentiment": sentiment,
            "Summary": summary,
            "Keywords": keywords,
            "Reasoning": f"Fallback analysis based on word frequency and pattern matching. Positive words: {positive_score}, Negative words: {negative_score}, Pattern bonus: {pattern_score}"
        }
        
    except Exception as e:
        logger.error(f"Fallback sentiment analysis failed: {str(e)}")
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