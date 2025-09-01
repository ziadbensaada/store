#!/usr/bin/env python3
"""
Test script to verify news API functionality and image extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_fetcher3 import get_news_about

def test_news_api():
    """Test the news API to see if images are being extracted"""
    
    print("Testing news API with image extraction...")
    
    try:
        # Test with a different query to avoid cache
        query = "climate change"
        print(f"Searching for: {query}")
        
        articles = get_news_about(query, max_articles=5)
        
        print(f"Found {len(articles)} articles")
        
        for i, article in enumerate(articles):
            print(f"\n--- Article {i+1} ---")
            print(f"Title: {article.get('title', 'No title')}")
            print(f"Source: {article.get('source', 'No source')}")
            print(f"URL: {article.get('url', 'No URL')}")
            print(f"Image URL: {article.get('image_url', 'No image')}")
            print(f"Content length: {len(article.get('content', ''))}")
            
            # Check if image URL looks valid
            image_url = article.get('image_url')
            if image_url:
                if image_url.startswith(('http://', 'https://')):
                    print("✅ Image URL is absolute")
                elif image_url.startswith('//'):
                    print("✅ Image URL is protocol-relative")
                elif image_url.startswith('/'):
                    print("✅ Image URL is root-relative")
                else:
                    print("⚠️ Image URL might be relative")
            else:
                print("❌ No image URL found")
        
    except Exception as e:
        print(f"Error testing news API: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_news_api()
