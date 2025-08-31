import feedparser
import requests
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def extract_image_from_rss_robust(entry):
    """Simplified version of the image extraction function"""
    logger.info("\n=== Starting image extraction ===")
    
    # Get base URL for relative paths
    base_url = entry.get('link', '')
    logger.info(f"Base URL: {base_url}")
    
    # Check direct image fields
    image_fields = ['image', 'image_url', 'thumbnail', 'thumbnail_url', 'media:content', 'media:thumbnail']
    for field in image_fields:
        if field in entry:
            logger.info(f"Found field '{field}': {entry[field]}")
            if isinstance(entry[field], dict) and 'url' in entry[field]:
                url = entry[field]['url']
            else:
                url = entry[field]
            logger.info(f"Potential image URL from {field}: {url}")
            return url
    
    # Check media content
    if 'media_content' in entry:
        logger.info("Found media_content field")
        for media in entry.media_content:
            if 'url' in media and media.get('type', '').startswith('image/'):
                logger.info(f"Found media content image: {media['url']}")
                return media['url']
    
    logger.warning("No image found in RSS entry")
    return None

def test_rss_feed(feed_url):
    """Test RSS feed parsing and image extraction"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing RSS feed: {feed_url}")
    logger.info("="*80)
    
    try:
        # Parse the feed
        feed = feedparser.parse(feed_url)
        
        if hasattr(feed, 'bozo_exception'):
            logger.error(f"Error parsing feed: {feed.bozo_exception}")
            return
        
        logger.info(f"Found {len(feed.entries)} entries in feed")
        
        # Test first 2 entries
        for i, entry in enumerate(feed.entries[:2]):
            logger.info(f"\n--- Entry {i+1} ---")
            logger.info(f"Title: {entry.get('title', 'No title')}")
            logger.info(f"Link: {entry.get('link', 'No link')}")
            
            # Dump all entry fields for inspection
            logger.info("\nEntry fields:")
            for key in entry.keys():
                logger.info(f"  {key}: {entry[key]}")
            
            # Test image extraction
            image_url = extract_image_from_rss_robust(entry)
            logger.info(f"\nExtracted image URL: {image_url}")
            
    except Exception as e:
        logger.error(f"Error testing feed: {e}", exc_info=True)

if __name__ == "__main__":
    # Test with CNN RSS feed
    test_rss_feed("http://rss.cnn.com/rss/edition.rss")
