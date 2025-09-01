#!/usr/bin/env python3
"""
Test script to verify image extraction functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from news_fetcher3 import extract_image_permissive, extract_image_from_rss_robust
import feedparser

def test_image_extraction():
    """Test image extraction with a sample RSS feed"""
    
    # Test with a sample RSS feed that should have images
    test_feed_url = "https://feeds.bbci.co.uk/news/rss.xml"
    
    print(f"Testing image extraction with: {test_feed_url}")
    
    try:
        # Parse the RSS feed
        feed = feedparser.parse(test_feed_url)
        
        if hasattr(feed, 'bozo_exception') and feed.bozo_exception:
            print(f"Error parsing feed: {feed.bozo_exception}")
            return
        
        print(f"Found {len(feed.entries)} entries")
        
        # Test the first few entries
        for i, entry in enumerate(feed.entries[:3]):
            print(f"\n--- Entry {i+1}: {entry.get('title', 'No title')} ---")
            
            # Test robust extraction
            robust_image = extract_image_from_rss_robust(entry)
            print(f"Robust extraction: {robust_image}")
            
            # Test permissive extraction
            permissive_image = extract_image_permissive(entry, entry.get('link', ''))
            print(f"Permissive extraction: {permissive_image}")
            
            # Show available fields
            print("Available fields:")
            for attr in dir(entry):
                if not attr.startswith('_'):
                    try:
                        value = getattr(entry, attr)
                        if value and not callable(value):
                            print(f"  {attr}: {type(value)} - {str(value)[:100]}")
                    except:
                        pass
        
    except Exception as e:
        print(f"Error testing image extraction: {e}")

if __name__ == "__main__":
    test_image_extraction()
