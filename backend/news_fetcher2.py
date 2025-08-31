### Bing News RSS Scrape with BeautifulSoup

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import urllib.parse
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
HEADERS = {'User-Agent': USER_AGENT}

def clean_url(url: str) -> str:
    """Clean and decode URL if needed"""
    try:
        return urllib.parse.unquote(url)
    except:
        return url

def extract_article_content(url: str) -> Optional[Dict[str, str]]:
    """Extract article content using BeautifulSoup with fallback mechanisms"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find main content using common semantic tags
        article_body = soup.find('article') or \
                       soup.find('div', class_=lambda x: x and 'article-body' in x) or \
                       soup.find('div', class_=lambda x: x and 'content' in x)
        
        # Fallback to body if specific content not found
        content = article_body.get_text(separator='\n', strip=True) if article_body else soup.body.get_text(separator='\n', strip=True)
        
        # Extract title
        title = soup.title.string.strip() if soup.title else ""
        
        # Extract publish date (try multiple common meta tags)
        publish_date = None
        date_selectors = [
            {'selector': 'meta[property="article:published_time"]', 'attr': 'content'},
            {'selector': 'meta[name="pubdate"]', 'attr': 'content'},
            {'selector': 'time[datetime]', 'attr': 'datetime'},
            {'selector': '.date-published', 'attr': 'text'}
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector['selector'])
            if element:
                publish_date = element.get(selector['attr'])
                if publish_date:
                    try:
                        publish_date = datetime.fromisoformat(publish_date.split('T')[0]).strftime('%Y-%m-%d')
                    except:
                        publish_date = None
                    break

        return {
            'title': title,
            'content': content,
            'publish_date': publish_date,
            'url': url
        }
        
    except Exception as e:
        logger.error(f"Failed to extract content from {url}: {str(e)}")
        return None

def get_news_articles(company_name: str) -> List[Dict[str, str]]:
    """
    Fetch 10 valid news articles with proper content about a company
    """
    search_url = f"https://www.bing.com/news/search?q={urllib.parse.quote(company_name)}&format=rss"
    articles = []
    processed_urls = set()
    
    try:
        logger.info(f"Starting search for '{company_name}'")
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        logger.info(f"Found {len(items)} initial articles in RSS feed")
        
        # Process items until we get 10 valid articles
        for item in items:
            if len(articles) >= 10:
                break
                
            url = clean_url(item.link.text if item.link else "")
            if not url or url in processed_urls:
                continue
                
            processed_urls.add(url)
            logger.info(f"Processing: {url}")
            
            article_data = extract_article_content(url)
            if not article_data or not article_data.get('content'):
                logger.warning(f"Skipping article with missing content: {url}")
                continue
                
            # Add RSS fallback data
            article_data.update({
                'rss_title': item.title.text if item.title else "",
                'rss_summary': item.description.text if item.description else "",
                'source': item.source.text if item.source else ""
            })
            
            # Use RSS title if missing
            if not article_data['title']:
                article_data['title'] = article_data['rss_title']
            
            articles.append(article_data)
            logger.info(f"Successfully added article: {article_data['title'][:50]}...")
            
        # If we didn't get enough articles from first page
        if len(articles) < 10:
            logger.warning(f"Only found {len(articles)} valid articles in first page")
            
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
    
    return articles[:10]

if __name__ == "__main__":
    company = input("Enter a company name: ")
    start_time = time.time()
    
    articles = get_news_articles(company)
    
    logger.info(f"\nSuccessfully retrieved {len(articles)} articles in {time.time()-start_time:.1f}s:")
    for i, article in enumerate(articles, 1):
        print(f"\nArticle {i}:")
        print(f"Title: {article['title']}")
        print(f"URL: {article['url']}")
        print(f"Published: {article['publish_date'] or 'Unknown date'}")
        print(f"Content sample: {article['content'][:200]}...")
        print("-" * 80)