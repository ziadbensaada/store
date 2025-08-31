### NewsAPI

import requests
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Replace with your NewsAPI key
NEWS_API_KEY = "ec4790b1f2b7416597f4d70ef0524aa5"

def fetch_news(company_name, num_articles=10):
    """
    Fetches news articles related to a given company using NewsAPI.
    
    Args:
        company_name (str): Name of the company to search for.
        num_articles (int): Number of articles to fetch (default: 10).
    
    Returns:
        list: A list of dictionaries containing article details (title, full content, url, etc.).
    """
    # Define the NewsAPI endpoint
    url = "https://newsapi.org/v2/everything"
    
    # Define query parameters
    params = {
        "q": company_name,  # Search query (company name)
        "pageSize": num_articles,  # Number of articles to fetch
        "language": "en",  # Language of articles
        "sortBy": "relevancy",  # Sort by relevance
        "apiKey": NEWS_API_KEY,  # Your NewsAPI key
    }
    
    try:
        # Make the API request
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Parse the JSON response
        data = response.json()
        
        # Check if the request was successful
        if data.get("status") != "ok":
            logging.error(f"NewsAPI request failed: {data.get('message', 'Unknown error')}")
            return []
        
        # Extract relevant article details
        articles = []
        for article in data.get("articles", []):
            # Scrape the full content of the article
            full_content = scrape_full_article(article.get("url", ""))
            
            articles.append({
                "title": article.get("title", "No title"),
                "content": full_content,  # Replace description with full content
                "url": article.get("url", "No URL"),
                "publish_date": article.get("publishedAt", "No date"),
            })
        
        logging.info(f"Fetched {len(articles)} articles for '{company_name}'.")
        return articles
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching news articles: {e}")
        return []


def scrape_full_article(url):
    """
    Scrapes the full content of a news article from its URL.
    
    Args:
        url (str): URL of the news article.
    
    Returns:
        str: Full content of the article.
    """
    try:
        # Fetch the article page
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract the main article content
        # Look for common tags used for article content
        article_content = ""
        for tag in soup.find_all(["p", "div", "article"]):  # Add more tags if needed
            if tag.name == "p" or "article" in tag.get("class", []):
                article_content += tag.get_text() + "\n"
        
        return article_content.strip()
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error scraping article content: {e}")
        return ""


# Example usage
if __name__ == "__main__":
    company = input("Enter a company name: ")
    articles = fetch_news(company)
    
    print(f"Fetched {len(articles)} articles for '{company}':")
    for i, article in enumerate(articles, 1):
        print(f"\nArticle {i}:")
        print(f"Title: {article['title']}")
        print(f"URL: {article['url']}")
        print(f"Published At: {article['publish_date']}")
        print(f"Full Content: {article['content']}")
        