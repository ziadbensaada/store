import feedparser
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_rss_feed(feed_url):
    """Check if we can parse an RSS feed and extract basic information"""
    print(f"\n{'='*80}")
    print(f"Checking RSS feed: {feed_url}")
    print("="*80)
    
    try:
        # Parse the feed
        feed = feedparser.parse(feed_url)
        
        # Check for parsing errors
        if hasattr(feed, 'bozo') and feed.bozo:
            print(f"Error parsing feed: {feed.bozo_exception}")
            return
        
        # Print basic feed info
        print(f"Feed title: {feed.feed.get('title', 'No title')}")
        print(f"Feed description: {feed.feed.get('description', 'No description')}")
        print(f"Number of entries: {len(feed.entries)}")
        
        # Print first entry details
        if feed.entries:
            print("\nFirst entry:")
            entry = feed.entries[0]
            print(f"Title: {entry.get('title', 'No title')}")
            print(f"Link: {entry.get('link', 'No link')}")
            print(f"Published: {entry.get('published', 'No date')}")
            
            # Check for media content
            if hasattr(entry, 'media_content'):
                print("\nMedia content found:")
                for media in entry.media_content:
                    print(f"  - {media.get('url', 'No URL')} (type: {media.get('type', 'unknown')})")
            
            # Check for media thumbnails
            if hasattr(entry, 'media_thumbnail'):
                print("\nMedia thumbnails found:")
                if isinstance(entry.media_thumbnail, list):
                    for thumb in entry.media_thumbnail:
                        print(f"  - {thumb.get('url', 'No URL')}")
                else:
                    print(f"  - {entry.media_thumbnail.get('url', 'No URL')}")
            
            # Check for enclosures
            if hasattr(entry, 'enclosures'):
                print("\nEnclosures found:")
                for enc in entry.enclosures:
                    print(f"  - {enc.get('href', 'No URL')} (type: {enc.get('type', 'unknown')})")
            
            # Print all available fields in the entry
            print("\nAll available fields in the entry:")
            for key in entry.keys():
                print(f"  - {key}")
        
    except Exception as e:
        print(f"Error checking feed: {e}")

if __name__ == "__main__":
    # Test with a few different RSS feeds
    test_feeds = [
        "http://rss.cnn.com/rss/edition.rss",
        "http://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
    ]
    
    for feed_url in test_feeds:
        check_rss_feed(feed_url)
    
    print("\nTest completed!")
