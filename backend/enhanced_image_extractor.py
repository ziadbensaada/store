import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from typing import Optional, List, Dict, Any, Union
import feedparser
from datetime import datetime, timedelta
import os
import json
import re
import time
from urllib.parse import urlparse, urljoin

# Try to import Selenium (optional)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Selenium not available. Some JavaScript-rendered content may not be accessible.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class EnhancedImageExtractor:
    """
    Enhanced image extractor that handles both RSS feeds and direct article URLs
    with multiple fallback strategies for finding the best image.
    """
    
    def __init__(self, use_selenium: bool = False):
        self.session = self._create_session()
        self.timeout = 15
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.selenium_driver = None
        
        if self.use_selenium:
            self._init_selenium()
            
    def _init_selenium(self):
        """Initialize Selenium WebDriver if not already initialized."""
        if self.selenium_driver is None and self.use_selenium:
            try:
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-notifications')
                
                # Set user agent to mimic a real browser
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                options.add_argument(f'user-agent={user_agent}')
                
                # Initialize the Chrome driver
                self.selenium_driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )
                self.selenium_driver.set_page_load_timeout(30)
                logger.info("Selenium WebDriver initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize Selenium: {e}")
                self.use_selenium = False
                self.selenium_driver = None
    
    def _create_session(self):
        """Create a requests session with proper headers and retry logic."""
        session = requests.Session()
        
        # Common headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Referer': 'https://www.google.com/'
        }
        
        session.headers.update(headers)
        return session
    
    def extract_image(self, url: str, is_rss_feed: bool = False) -> Optional[str]:
        """
        Extract the best image from a given URL or RSS feed.
        
        Args:
            url: The URL to extract image from (article URL or RSS feed)
            is_rss_feed: Whether the URL is an RSS feed
            
        Returns:
            Optional[str]: The URL of the extracted image, or None if not found
        """
        if is_rss_feed:
            return self._extract_image_from_rss_feed(url)
        else:
            return self._extract_image_from_article(url)
    
    def _extract_image_from_rss_feed(self, feed_url: str) -> Optional[str]:
        """Extract an image from an RSS feed."""
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url)
            
            if hasattr(feed, 'bozo_exception'):
                logger.error(f"Error parsing feed: {feed.bozo_exception}")
                return None
            
            # Try to get image from feed metadata
            if hasattr(feed.feed, 'image') and hasattr(feed.feed.image, 'href'):
                return feed.feed.image.href
                
            # Try to get image from first entry
            if feed.entries:
                entry = feed.entries[0]
                
                # Check for media content
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if hasattr(media, 'get') and media.get('type', '').startswith('image/'):
                            return media.get('url')
                
                # Check for media thumbnails
                if hasattr(entry, 'media_thumbnail'):
                    thumbs = entry.media_thumbnail if isinstance(entry.media_thumbnail, list) else [entry.media_thumbnail]
                    for thumb in thumbs:
                        if hasattr(thumb, 'get') and thumb.get('url'):
                            return thumb.get('url')
                
                # Check for enclosures
                if hasattr(entry, 'enclosures'):
                    for enc in entry.enclosures:
                        if hasattr(enc, 'get') and enc.get('type', '').startswith('image/'):
                            return enc.get('href')
                
                # If no image found in RSS entry, try to fetch from article
                if hasattr(entry, 'link'):
                    return self._extract_image_from_article(entry.link)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting image from RSS feed {feed_url}: {e}")
            return None
    
    def _extract_image_from_article(self, url: str) -> Optional[str]:
        """Extract the best image from an article URL with multiple fallback strategies."""
        try:
            logger.info(f"🔍 Extracting image from: {url}")
            
            # Set a desktop user agent to get the full site version
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # For Business Insider specifically, we need to mimic a real browser more closely
            if 'businessinsider.com' in url:
                headers.update({
                    'sec-ch-ua': '"Chromium";v="91", " Not;A Brand";v="99"',
                    'sec-ch-ua-mobile': '?0',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'TE': 'trailers'
                })
            
            # Check if we should use Selenium for this URL
            use_selenium_for_url = self.use_selenium and ('businessinsider.com' in url or 'forbes.com' in url or 'medium.com' in url)
            
            if use_selenium_for_url:
                logger.info(f"Using Selenium to render JavaScript for URL: {url}")
                try:
                    # Use Selenium to get the page
                    self.selenium_driver.get(url)
                    
                    # Wait for the page to load
                    WebDriverWait(self.selenium_driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    
                    # Wait a bit more for any lazy-loaded content
                    time.sleep(2)
                    
                    # Get the page source after JavaScript execution
                    html_content = self.selenium_driver.page_source
                    
                    # Parse the HTML with BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Save the rendered HTML for debugging
                    with open('debug_response_rendered.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info("Saved rendered response to debug_response_rendered.html")
                    
                except Exception as e:
                    logger.error(f"Error using Selenium: {e}")
                    # Fall back to regular requests
                    response = self._fetch_with_requests(url, headers)
                    soup = BeautifulSoup(response.text, 'html.parser')
            else:
                # Use regular requests for non-JavaScript sites
                response = self._fetch_with_requests(url, headers)
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. First try: Open Graph image (most reliable for news sites)
            og_image = None
            
            # Try different variations of the property name
            for prop in ['property', 'name', 'itemprop']:
                og_image = soup.find('meta', attrs={prop: lambda x: x and any(img_tag in x.lower() for img_tag in ['og:image', 'twitter:image', 'image'])})
                if og_image and og_image.get('content'):
                    img_url = self._make_url_absolute(url, og_image['content'].strip())
                    if self._is_valid_image(img_url):
                        logger.info(f"✅ Found Open Graph image: {img_url}")
                        return img_url
            
            # Try direct meta content
            for meta in soup.find_all('meta'):
                if any(x in str(meta).lower() for x in ['og:image', 'twitter:image']) and meta.get('content'):
                    img_url = self._make_url_absolute(url, meta['content'].strip())
                    if self._is_valid_image(img_url):
                        logger.info(f"✅ Found meta image: {img_url}")
                        return img_url
            
            # 2. Try Twitter card image
            twitter_image = soup.find('meta', attrs={'name': lambda x: x and 'twitter:image' in x.lower()})
            if twitter_image and twitter_image.get('content'):
                img_url = self._make_url_absolute(url, twitter_image['content'].strip())
                if self._is_valid_image(img_url):
                    logger.info(f"✅ Found Twitter image: {img_url}")
                    return img_url
            
            # 3. Look for article:image
            article_image = soup.find('meta', property=lambda x: x and 'article:image' in x.lower())
            if article_image and article_image.get('content'):
                img_url = self._make_url_absolute(url, article_image['content'].strip())
                if self._is_valid_image(img_url):
                    logger.info(f"✅ Found article image: {img_url}")
                    return img_url
            
            # 4. Look for JSON-LD data which often contains high-quality images
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    # Clean the JSON string first
                    json_str = script.string
                    if not json_str:
                        continue
                        
                    # Handle common JSON issues
                    json_str = re.sub(r'\n', ' ', json_str)  # Remove newlines
                    json_str = re.sub(r'\\/', '/', json_str)  # Fix escaped slashes
                    
                    # Try to parse the JSON
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Try to fix common JSON issues
                        json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
                        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas in objects
                        data = json.loads(json_str)
                    
                    # Handle both arrays and single objects
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    
                    # Check for image in various JSON-LD formats
                    def extract_from_dict(d, keys):
                        for key in keys:
                            if key in d:
                                if isinstance(d[key], str):
                                    return d[key].strip()
                                elif isinstance(d[key], dict) and 'url' in d[key]:
                                    return d[key]['url'].strip()
                                elif isinstance(d[key], list) and d[key]:
                                    return d[key][0].get('url', '').strip()
                        return None
                    
                    # Check common image locations in JSON-LD
                    image_url = None
                    
                    # Check main image fields
                    for img_field in ['image', 'thumbnail', 'thumbnailUrl', 'url', 'contentUrl']:
                        if img_field in data:
                            if isinstance(data[img_field], str):
                                image_url = data[img_field].strip()
                                break
                            elif isinstance(data[img_field], dict) and 'url' in data[img_field]:
                                image_url = data[img_field]['url'].strip()
                                break
                            elif isinstance(data[img_field], list) and data[img_field]:
                                if isinstance(data[img_field][0], str):
                                    image_url = data[img_field][0].strip()
                                    break
                                elif isinstance(data[img_field][0], dict):
                                    image_url = extract_from_dict(data[img_field][0], ['url', 'contentUrl'])
                                    if image_url:
                                        break
                    
                    # If we found an image URL, process it
                    if image_url:
                        img_url = self._make_url_absolute(url, image_url)
                        if self._is_valid_image(img_url):
                            logger.info(f"✅ Found JSON-LD image: {img_url}")
                            return img_url
                    
                    # Check for embedded images in the content
                    if 'articleBody' in data and isinstance(data['articleBody'], str):
                        # Look for image URLs in the article body
                        img_matches = re.findall(r'src=[\'"]([^\'"]+\.(?:jpg|jpeg|png|webp))[\'"]', data['articleBody'], re.IGNORECASE)
                        for img_match in img_matches:
                            img_url = self._make_url_absolute(url, img_match)
                            if self._is_valid_image(img_url):
                                logger.info(f"✅ Found image in article body: {img_url}")
                                return img_url
                except (json.JSONDecodeError, AttributeError, TypeError) as e:
                    logger.debug(f"Error parsing JSON-LD: {e}")
                    continue
            
            # 5. Look for the main article image using multiple strategies
            images = []
            
            # First, try to find the main image in the article header
            header_image = soup.select_one('header img, .article-header img, .post-header img')
            if header_image:
                src = (header_image.get('src') or 
                      header_image.get('data-src') or 
                      header_image.get('data-lazy-src') or
                      header_image.get('data-original-src') or
                      header_image.get('data-lazy-load'))
                if src:
                    img_url = self._make_url_absolute(url, src)
                    if self._is_valid_image(img_url):
                        logger.info(f"✅ Found header image: {img_url}")
                        return img_url
            
            # Business Insider specific selectors
            bi_selectors = [
                'div.photo-gallery-image-container img',
                'div.gallery-image-container img',
                'div.slideshow-slide-container img',
                'div.image-layout-image-wrapper img',
                'div.lazy-image-container img',
                'div.inset-image img',
                'div.article-image img',
                'figure.media img',
                'div.media img',
                'div.article-body img',
                'div.article-content img',
                'div.post-content img',
                'div.entry-content img',
                'div.article img',
                'article img',
                'main img',
                'figure img',
                'picture source',
                'img[class*="lazy"]',
                'img[loading="lazy"]',
                'img[data-src]',
                'img[data-lazy-src]',
                'img[data-srcset]',
                'img[data-original]',
                'img[data-fallback-src]',
                'img[class*="hero"]',
                'img[class*="featured"]',
                'img[class*="main"]',
                'div[data-testid*="image"] img',
                'div[class*="image"] img',
                'div[class*="media"] img',
                'div[class*="hero"] img',
                'div[class*="featured"] img',
                'div[class*="main-image"] img',
                'div[class*="article-header"] img',
                'div[class*="post-thumbnail"] img'
            ]
            
            # General news site selectors
            common_selectors = [
                'article img',
                'main img',
                '.article-image img',
                '.post-image img',
                '.entry-content img',
                '.article__content img',
                '.article-body img',
                '.content img',
                'figure img',
                'picture source',
                'div[data-testid="article-image"] img',
                'div[class*="hero"] img',
                'div[class*="featured"] img',
                'div[class*="main-image"] img',
                'div[class*="article-header"] img',
                'img[class*="hero"]',
                'img[class*="featured"]',
                'img[class*="main"]',
                'img[loading="lazy"]',
                'img[data-src]',
                'img[data-lazy-src]',
                'img[data-srcset]',
                'img[data-original]',
                'img[data-fallback-src]',
                'img[class*="lazy"]'
            ]
            
            # Use Business Insider specific selectors if it's a BI URL
            is_business_insider = 'businessinsider.com' in url
            selectors = bi_selectors if is_business_insider else common_selectors
            
            # For Business Insider, also try to extract from JSON-LD in the page
            if is_business_insider:
                # Look for script tags with JSON-LD data
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, list):
                            data = data[0]
                        
                        # Check for image in the JSON-LD structure
                        image_url = None
                        if 'image' in data:
                            if isinstance(data['image'], str):
                                image_url = data['image']
                            elif isinstance(data['image'], dict) and 'url' in data['image']:
                                image_url = data['image']['url']
                            elif isinstance(data['image'], list) and data['image']:
                                if isinstance(data['image'][0], str):
                                    image_url = data['image'][0]
                                elif isinstance(data['image'][0], dict) and 'url' in data['image'][0]:
                                    image_url = data['image'][0]['url']
                        
                        if image_url:
                            img_url = self._make_url_absolute(url, image_url)
                            if self._is_valid_image(img_url):
                                logger.info(f"✅ Found JSON-LD image: {img_url}")
                                return img_url
                                
                    except (json.JSONDecodeError, AttributeError, TypeError) as e:
                        logger.debug(f"Error parsing JSON-LD: {e}")
                        continue
            
            # Process common selectors
            for selector in selectors:
                for img in soup.select(selector):
                    src = (img.get('src') or 
                          img.get('data-src') or 
                          img.get('data-lazy-src') or 
                          img.get('data-original') or
                          img.get('data-fallback-src') or
                          (img.get('srcset', '').split(',')[0].split()[0] if img.get('srcset') else None))
                    
                    if not src:
                        continue
                        
                    # Skip data URIs and SVGs
                    if src.startswith('data:') or src.lower().endswith('.svg'):
                        continue
                    
                    # Make the URL absolute
                    full_url = self._make_url_absolute(url, src.strip())
                    if not full_url:
                        continue
                    
                    # Skip common tracking/analytics images
                    if any(x in full_url.lower() for x in ['pixel', 'track', 'analytics', 'beacon', 'spacer', 'transparent', '1x1', 'pixel.png', 'pixel.jpg']):
                        continue
                    
                    # Get image dimensions (if available)
                    width = max(
                        int(img.get('width', 0) or 0),
                        int(img.get('data-width', 0) or 0)
                    )
                    height = max(
                        int(img.get('height', 0) or 0),
                        int(img.get('data-height', 0) or 0)
                    )
                    
                    # If dimensions aren't in attributes, check CSS
                    if width <= 0 or height <= 0:
                        style = img.get('style', '')
                        import re
                        width_match = re.search(r'width\s*:\s*(\d+)px', style)
                        height_match = re.search(r'height\s*:\s*(\d+)px', style)
                        if width_match:
                            width = int(width_match.group(1))
                        if height_match:
                            height = int(height_match.group(1))
                    
                    # Skip small images, icons, and tracking pixels
                    min_dimension = 200  # Minimum dimension for a content image
                    if width > 0 and height > 0 and (width < min_dimension and height < min_dimension):
                        continue
                    
                    # Calculate area (used for sorting)
                    area = width * height
                    
                    # Check if this looks like a content image
                    parent = img.find_parent()
                    parent_classes = ' '.join(parent.get('class', []) if parent else [])
                    parent_id = parent.get('id', '') if parent else ''
                    
                    # Skip images that are likely not content
                    skip_keywords = ['ad', 'banner', 'logo', 'icon', 'button', 'thumbnail', 'avatar', 'share', 'social', 'comment', 'author', 'widget']
                    if any(x in parent_classes.lower() for x in skip_keywords) or \
                       any(x in parent_id.lower() for x in skip_keywords) or \
                       any(x in img.get('class', []) for x in skip_keywords) or \
                       any(x in img.get('id', '').lower() for x in skip_keywords):
                        continue
                    
                    # Add to images list with score based on size and position
                    # Higher score is better
                    position_score = 1.0
                    
                    # Images earlier in the document are more likely to be the main image
                    position = images.index((area, full_url)) if (area, full_url) in images else len(images)
                    position_score = max(0.1, 1.0 - (position * 0.05))  # Reduce score by 5% per position
                    
                    # Calculate final score (area * position_score)
                    score = area * position_score
                    
                    # Add to images list if not already present
                    if (area, full_url) not in images:
                        images.append((score, full_url))
                        logger.debug(f"📷 Found potential image: {full_url} (Score: {score:.1f}, {width}x{height})")
            
            # Sort images by score (highest first)
            images.sort(reverse=True, key=lambda x: x[0])
            
            # Return the best image if we found any
            if images:
                best_img = images[0][1]
                logger.info(f"✅ Selected best image: {best_img}")
                return best_img
            
        except Exception as e:
            logger.error(f"Error extracting image from article {url}: {e}")
            return None
    
    def _fetch_with_requests(self, url: str, headers: dict):
        """Fetch URL using requests library."""
        logger.info(f"Fetching URL with requests: {url}")
        response = self.session.get(
            url, 
            headers=headers,
            timeout=30,  # Increased timeout for slower sites
            allow_redirects=True,
            verify=True
        )
        
        # Log response details
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Content type: {response.headers.get('content-type')}")
        logger.info(f"Content length: {len(response.text)} bytes")
        
        response.raise_for_status()
        
        # Log first 1000 characters of response for debugging
        logger.debug(f"Response preview: {response.text[:1000]}...")
        
        # Save the full response to a file for inspection
        with open('debug_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        logger.info("Saved full response to debug_response.html")
        
        return response

    def _make_url_absolute(self, base_url: str, url: str) -> Optional[str]:
        """
        Convert a relative URL to an absolute URL with additional cleanup.
        
        Args:
            base_url: The base URL to resolve against
            url: The URL to make absolute (can be relative or absolute)
            
        Returns:
            The absolute URL or None if invalid
        """
        if not url or not url.strip():
            return None
            
        # Clean the URL
        url = url.strip()
        
        # Handle common issues in URLs
        if ' ' in url:
            url = url.split(' ')[0]  # Take the first part if there are spaces
        
        # Remove any URL parameters that might cause issues
        url = url.split('?')[0].split('#')[0]
        
        # If it's already an absolute URL, clean and return it
        if url.startswith(('http://', 'https://')):
            # Clean up any double slashes in the path
            parsed = urlparse(url)
            path = re.sub(r'/{2,}', '/', parsed.path)
            return f"{parsed.scheme}://{parsed.netloc}{path}"
        
        # Handle protocol-relative URLs
        if url.startswith('//'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}:{url}"
        
        # Handle root-relative URLs
        if url.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
            
        # Handle relative URLs
        try:
            absolute_url = urljoin(base_url, url)
            # Clean up the final URL
            parsed = urlparse(absolute_url)
            path = re.sub(r'/{2,}', '/', parsed.path)
            return f"{parsed.scheme}://{parsed.netloc}{path}"
        except Exception as e:
            logger.error(f"Error making URL absolute (base: {base_url}, url: {url}): {e}")
            return None
    
    def _is_valid_image(self, url: str) -> bool:
        """
        Check if a URL points to a valid image.
        
        Args:
            url: The image URL to check
            
        Returns:
            bool: True if the URL appears to be a valid image
        """
        if not url or url.startswith('data:image'):
            return False
            
        # Skip common non-image URLs
        skip_extensions = ['.svg', '.gif', '.webp', '.ico']
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False
            
        # Skip tracking/analytics images
        skip_keywords = ['pixel', 'track', 'analytics', 'beacon', 'spacer', 'transparent', '1x1', 'pixel.png', 'pixel.jpg']
        if any(keyword in url.lower() for keyword in skip_keywords):
            return False
            
        # Check if the URL points to an actual image
        try:
            # Try HEAD request first to avoid downloading the whole image
            response = self.session.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200 and 'image/' in response.headers.get('content-type', ''):
                return True
                
            # If HEAD fails, try GET with stream to only download headers
            response = self.session.get(url, stream=True, timeout=10)
            if response.status_code == 200 and 'image/' in response.headers.get('content-type', ''):
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Error checking image accessibility for {url}: {e}")
            return False
        if any(indicator in url for indicator in image_indicators):
            return True
            
        return False
    
    def _is_image_accessible(self, url: str) -> bool:
        """Check if an image URL is accessible."""
        if not url:
            return False
            
        try:
            # First try HEAD request
            response = self.session.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200 and 'image/' in response.headers.get('content-type', ''):
                return True
                
            # If HEAD fails, try GET with stream to only download headers
            response = self.session.get(url, stream=True, timeout=10)
            if response.status_code == 200 and 'image/' in response.headers.get('content-type', ''):
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Error checking image accessibility for {url}: {e}")
            return False

    def __del__(self):
        """Clean up resources when the object is destroyed."""
        if hasattr(self, 'selenium_driver') and self.selenium_driver:
            try:
                self.selenium_driver.quit()
                logger.info("Selenium WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing Selenium WebDriver: {e}")

def test_extractor():
    """Test the EnhancedImageExtractor with example URLs."""
    import sys
    
    extractor = EnhancedImageExtractor()
    
    if len(sys.argv) > 1:
        # Use the URL provided as command line argument
        test_url = sys.argv[1]
        print(f"\nTesting URL: {test_url}")
        is_rss = test_url.endswith('.xml') or 'rss' in test_url.lower()
        image_url = extractor.extract_image(test_url, is_rss_feed=is_rss)
        print(f"\nExtracted image: {image_url}")
    else:
        # Default test cases if no URL provided
        # Test with RSS feed
        rss_url = "http://feeds.bbci.co.uk/news/rss.xml"
        print(f"\nTesting RSS feed: {rss_url}")
        image_url = extractor.extract_image(rss_url, is_rss_feed=True)
        print(f"Extracted image: {image_url}")
        
        # Test with article URL
        article_url = "https://www.bbc.com/news/world-us-canada-68903712"
        print(f"\nTesting article: {article_url}")
        image_url = extractor.extract_image(article_url, is_rss_feed=False)
        print(f"Extracted image: {image_url}")

if __name__ == "__main__":
    test_extractor()
