import feedparser
import requests
from bs4 import BeautifulSoup
import logging
import time
from urllib.parse import urlparse, urljoin
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Referer': 'https://www.google.com/'
        })
    
    def fetch_url(self, url, max_retries=3):
        """Fetch URL with retries and error handling"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts: {e}")
                    return None
                logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying...")
                time.sleep(1)
        return None
    
    def extract_from_rss(self, feed_url):
        """Extract images from RSS feed entries"""
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing RSS feed: {feed_url}")
        logger.info("="*80)
        
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url, request_headers=self.session.headers)
            
            if hasattr(feed, 'bozo_exception'):
                logger.error(f"Error parsing feed: {feed.bozo_exception}")
                return []
            
            logger.info(f"Found {len(feed.entries)} entries in feed")
            
            results = []
            # Test first 2 entries
            for i, entry in enumerate(feed.entries[:2]):
                logger.info(f"\n--- Entry {i+1} ---")
                logger.info(f"Title: {entry.get('title', 'No title')}")
                
                # Get entry URL
                url = entry.get('link', '')
                if not url:
                    logger.warning("No URL found for entry")
                    continue
                
                # Try to extract image from RSS entry
                image_url = self.extract_image_from_rss_entry(entry, url)
                
                # If no image found in RSS, try to fetch from article
                if not image_url:
                    logger.info("No image found in RSS entry, trying to fetch from article...")
                    image_url = self.extract_from_article(url)
                
                results.append({
                    'title': entry.get('title', ''),
                    'url': url,
                    'image_url': image_url
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing feed: {e}", exc_info=True)
            return []
    
    def extract_image_from_rss_entry(self, entry, base_url):
        """Extract image URL from RSS entry"""
        logger.info("\nChecking RSS entry for images...")
        
        # Check common image fields
        image_fields = [
            'media_content', 'media_thumbnail', 'enclosures',
            'image', 'image_url', 'thumbnail', 'thumbnail_url'
        ]
        
        for field in image_fields:
            if field in entry:
                logger.info(f"Found field: {field}")
                value = entry[field]
                
                # Handle different field types
                if field == 'media_content' and isinstance(value, list):
                    for media in value:
                        if media.get('type', '').startswith('image/'):
                            url = media.get('url')
                            if url:
                                logger.info(f"Found media content image: {url}")
                                return self.make_absolute_url(url, base_url)
                
                elif field == 'media_thumbnail' and value:
                    if isinstance(value, list):
                        for thumb in value:
                            url = thumb.get('url') if hasattr(thumb, 'get') else str(thumb)
                            if url:
                                logger.info(f"Found media thumbnail: {url}")
                                return self.make_absolute_url(url, base_url)
                    else:
                        url = value.get('url') if hasattr(value, 'get') else str(value)
                        if url:
                            logger.info(f"Found media thumbnail: {url}")
                            return self.make_absolute_url(url, base_url)
                
                elif field == 'enclosures' and value:
                    for enc in value:
                        if enc.get('type', '').startswith('image/'):
                            url = enc.get('href') or enc.get('url')
                            if url:
                                logger.info(f"Found enclosure image: {url}")
                                return self.make_absolute_url(url, base_url)
                
                # Handle direct URL fields
                elif field in ['image', 'image_url', 'thumbnail', 'thumbnail_url']:
                    if value and isinstance(value, str):
                        logger.info(f"Found {field}: {value}")
                        return self.make_absolute_url(value, base_url)
        
        logger.info("No image found in RSS entry")
        return None
    
    def extract_from_article(self, url):
        """Extract image from article page"""
        logger.info(f"\nExtracting image from article: {url}")
        
        response = self.fetch_url(url)
        if not response or not response.ok:
            logger.error(f"Failed to fetch article: {url}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']
            logger.info(f"Found Open Graph image: {image_url}")
            return self.make_absolute_url(image_url, url)
        
        # Try Twitter card image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image['content']
            logger.info(f"Found Twitter card image: {image_url}")
            return self.make_absolute_url(image_url, url)
        
        # Try to find article image by common class names
        image_selectors = [
            'img.article-image', 'img.hero-image', 'img.featured-image',
            'img.wp-post-image', 'figure.image img', 'div.media img',
            'div.article-body img', 'div.entry-content img', 'div.article img'
        ]
        
        for selector in image_selectors:
            img = soup.select_one(selector)
            if img and img.get('src'):
                src = img['src']
                if self.is_valid_image_url(src):
                    logger.info(f"Found article image with selector '{selector}': {src}")
                    return self.make_absolute_url(src, url)
        
        # If no image found with selectors, try to find the largest image in the article
        max_size = 0
        best_image = None
        
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not self.is_valid_image_url(src):
                continue
                
            # Get image dimensions if available
            width = 0
            height = 0
            
            if img.get('width') and img['width'].isdigit():
                width = int(img['width'])
            if img.get('height') and img['height'].isdigit():
                height = int(img['height'])
            
            # Calculate size score (prioritize larger images)
            size = width * height
            if size > max_size:
                max_size = size
                best_image = src
        
        if best_image:
            logger.info(f"Found largest image in article: {best_image} (size score: {max_size})")
            return self.make_absolute_url(best_image, url)
        
        logger.info("No suitable image found in article")
        return None
    
    def is_valid_image_url(self, url):
        """Check if URL looks like a valid image URL"""
        if not url or not isinstance(url, str):
            return False
        
        url = url.lower()
        
        # Skip data URIs and empty URLs
        if not url or url.startswith('data:image'):
            return False
        
        # Check for common image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
        if any(ext in url for ext in image_extensions):
            return True
        
        # Check for common image path patterns
        image_indicators = ['/image', '/img', '/media', '/upload', 'image=', 'img=']
        if any(indicator in url for indicator in image_indicators):
            return True
        
        return False
    
    def make_absolute_url(self, url, base_url):
        """Convert relative URL to absolute"""
        if not url:
            return None
            
        # Skip if already absolute
        if url.startswith(('http://', 'https://')):
            return url
            
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return f'https:{url}'
            
        # Handle root-relative URLs
        if url.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
            
        # Handle relative URLs
        return urljoin(base_url, url)

if __name__ == "__main__":
    import sys
    
    extractor = ImageExtractor()
    
    if len(sys.argv) > 1:
        # Test with provided URL (RSS feed or article)
        url = sys.argv[1]
        if url.endswith(('.rss', '.xml')) or 'rss' in url.lower():
            results = extractor.extract_from_rss(url)
        else:
            image_url = extractor.extract_from_article(url)
            results = [{'url': url, 'image_url': image_url}]
    else:
        # Test with default RSS feeds
        test_feeds = [
            "http://feeds.bbci.co.uk/news/rss.xml",
            "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/technology/rss.xml",
            "https://www.theguardian.com/technology/rss"
        ]
        
        results = []
        for feed_url in test_feeds:
            results.extend(extractor.extract_from_rss(feed_url))
    
    # Print results
    print("\n" + "="*80)
    print("EXTRACTION RESULTS:")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"Title: {result.get('title', 'No title')}")
        print(f"URL: {result.get('url', 'No URL')}")
        print(f"Image URL: {result.get('image_url', 'No image found')}")
