import feedparser
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import urllib.parse
from urllib.parse import urlparse
import time
import re
import json
import os
import hashlib
from pathlib import Path
from pymongo import MongoClient

# Ensure cache directory exists
os.makedirs('cache/rss_cache', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = Path("./cache/rss_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = timedelta(hours=24)  # Cache for 24 hours

# User agent for requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Headers to mimic a browser
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',
    'Referer': 'https://www.google.com/'
}

def validate_image_url_robust(url: str) -> bool:
    """
    Robust image URL validation with comprehensive checks
    """
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    if not url or len(url) < 5:
        return False
    
    # Allow data URIs and valid HTTP(S) URLs
    if url.lower().startswith('data:image/'):
        return True
    
    # Check for valid URL schemes
    if not (url.startswith(('http://', 'https://', '//', '/', './'))):
        return False
    
    # Skip obvious non-image URLs
    url_lower = url.lower()
    skip_patterns = [
        'favicon', 'logo-small', 'icon-', 'sprite', 'blank.', 'spacer.',
        'pixel.', '1x1.', 'tracking', 'beacon', 'counter', 'stats',
        'ads/', 'advertisement', 'google', 'facebook.com', 'twitter.com',
        'share-', 'social-', 'print-', 'email-'
    ]
    
    if any(pattern in url_lower for pattern in skip_patterns):
        return False
    
    # Check for image extensions (very permissive)
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
    path = urllib.parse.urlparse(url).path.lower()
    
    # If it has an image extension, it's likely an image
    if any(path.endswith(ext) for ext in image_extensions):
        return True
    
    # Check for image-related URL patterns
    image_indicators = [
        '/image', '/img', '/photo', '/pic', '/media', '/upload',
        'image=', 'img=', 'photo=', 'src=', 'thumbnail', 'thumb',
        'gallery', 'cdn.', 'static.', 'assets/', 'content/',
        'wp-content', 'images.', 'pics.', 'media.'
    ]
    
    if any(indicator in url_lower for indicator in image_indicators):
        return True
    
    # For URLs with query parameters that suggest image manipulation
    if '?' in url and any(param in url_lower for param in ['w=', 'h=', 'width=', 'height=', 'size=', 'format=']):
        return True
    
    return False

def make_absolute_url_robust(image_url: str, base_url: str) -> Optional[str]:
    """
    Convert relative URLs to absolute URLs with comprehensive handling
    """
    if not image_url or not base_url:
        return None
    
    try:
        image_url = image_url.strip()
        
        # Already absolute URL
        if image_url.startswith(('http://', 'https://')):
            return image_url
        
        # Data URI
        if image_url.startswith('data:'):
            return image_url
        
        # Protocol-relative URL
        if image_url.startswith('//'):
            parsed_base = urllib.parse.urlparse(base_url)
            return f"{parsed_base.scheme}:{image_url}"
        
        # Root-relative URL
        if image_url.startswith('/'):
            parsed_base = urllib.parse.urlparse(base_url)
            return f"{parsed_base.scheme}://{parsed_base.netloc}{image_url}"
        
        # Relative URL
        return urllib.parse.urljoin(base_url, image_url)
        
    except Exception as e:
        logger.error(f"Error making URL absolute: {e}")
        return image_url

def extract_images_from_html(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    Extract all possible images from HTML with multiple strategies
    """
    images = []
    
    # Strategy 1: Find all img tags with various attributes
    img_attributes = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-url', 
                     'data-image', 'data-img', 'data-large', 'data-full', 'data-zoom']
    
    for img in soup.find_all('img'):
        for attr in img_attributes:
            if img.get(attr):
                img_url = img[attr].strip()
                if img_url and validate_image_url_robust(img_url):
                    absolute_url = make_absolute_url_robust(img_url, base_url)
                    if absolute_url:
                        images.append(absolute_url)
    
    # Strategy 2: Find images in picture elements
    for picture in soup.find_all('picture'):
        for source in picture.find_all('source'):
            if source.get('srcset'):
                # Parse srcset attribute
                srcset = source.get('srcset')
                urls = [url.strip().split()[0] for url in srcset.split(',')]
                for url in urls:
                    if validate_image_url_robust(url):
                        absolute_url = make_absolute_url_robust(url, base_url)
                        if absolute_url:
                            images.append(absolute_url)
    
    # Strategy 3: Find images in style attributes (background images)
    for element in soup.find_all(attrs={'style': True}):
        style = element.get('style', '')
        bg_matches = re.findall(r'background-image:\s*url\(["\']?([^"\')\s]+)["\']?\)', style)
        for match in bg_matches:
            if validate_image_url_robust(match):
                absolute_url = make_absolute_url_robust(match, base_url)
                if absolute_url:
                    images.append(absolute_url)
    
    return images

def test_image_accessibility(url: str) -> bool:
    """
    Test if an image URL is actually accessible
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache'
        }
        
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        
        # Check if response is successful
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            if content_type.startswith('image/'):
                return True
        
        # If HEAD fails, try GET with limited content
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            return content_type.startswith('image/')
            
    except Exception:
        pass
    
    return False

def extract_image_from_article_robust(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    ROBUST image extraction with multiple fallback strategies and accessibility testing
    """
    if not soup:
        logger.warning("No BeautifulSoup object provided for image extraction")
        return None
    logger.info(f"🔍 Starting ROBUST image extraction from: {base_url}")
    
    def clean_image_url(url: str) -> str:
        """Clean and normalize image URL"""
        if not url or not isinstance(url, str):
            return None
            
        url = url.strip()
        if not url:
            return None
            
        # Handle data URIs
        if url.startswith('data:image'):
            return url
            
        # Remove URL parameters that might cause issues, but keep important ones
        parsed = urlparse(url)
        query_params = []
        if parsed.query:
            # Keep important parameters that might be needed for image loading
            for param in parsed.query.split('&'):
                if any(p in param.lower() for p in ['width=', 'height=', 'quality=', 'crop=', 'fit=']):
                    query_params.append(param)
        
        # Reconstruct URL with only important parameters
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if query_params:
            clean_url += f"?{'&'.join(query_params)}"
            
        return clean_url if clean_url.startswith(('http://', 'https://', 'data:image')) else None

    def test_image_url(url: str) -> bool:
        """Test if image URL is accessible with multiple fallbacks"""
        if not url:
            return False
            
        # Skip data URIs as they're already in the document
        if url.startswith('data:image'):
            return True
            
        try:
            # First try HEAD request
            response = requests.head(
                url, 
                timeout=5, 
                allow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            # If HEAD is not allowed, try GET with stream
            if response.status_code == 405 or response.status_code >= 500:
                response = requests.get(
                    url,
                    stream=True,
                    timeout=10,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
                    }
                )
                # Read just enough to verify it's an image
                chunk = next(response.iter_content(1024), None)
                if not chunk:
                    return False
                    
            content_type = response.headers.get('content-type', '').lower()
            return response.status_code == 200 and 'image' in content_type
            
        except Exception as e:
            logger.debug(f"Error testing image URL {url}: {str(e)}")
            return False
    
    # Priority 1: Meta tags (most reliable)
    meta_selectors = [
        ('meta[property="og:image"]', 'content'),
        ('meta[property="og:image:url"]', 'content'),
        ('meta[name="twitter:image"]', 'content'),
        ('meta[name="twitter:image:src"]', 'content'),
        ('meta[itemprop="image"]', 'content'),
        ('meta[name="thumbnail"]', 'content'),
        ('link[rel="image_src"]', 'href'),
        ('meta[property="og:image:secure_url"]', 'content'),
        ('link[rel="apple-touch-icon"]', 'href'),
        ('link[rel="icon"]', 'href'),
        ('meta[name="msapplication-TileImage"]', 'content')
    ]
    
    # Check for meta tags first
    for selector, attr in meta_selectors:
        try:
            elements = soup.select(selector)  # Use select() to find all matching elements
            for element in elements:
                if element and element.get(attr):
                    img_url = element[attr].strip()
                    if not img_url:
                        continue
                        
                    logger.info(f"🔍 Found meta image: {img_url}")
                    
                    # Clean and validate URL
                    clean_url = clean_image_url(img_url)
                    if not clean_url:
                        clean_url = make_absolute_url_robust(img_url, base_url)
                    
                    if clean_url and test_image_url(clean_url):
                        logger.info(f"✅ Using validated meta image: {clean_url}")
                        return clean_url
                        
        except Exception as e:
            logger.debug(f"Error processing meta selector {selector}: {str(e)}")
            continue
    
    # Priority 2: Article content images
    article_selectors = [
        'article', 'main', '[role="main"]', '.article', '.post',
        '.entry-content', '.article-content', '.content', '.story',
        '#article', '#main', '#content', '.post-content',
        '.article-body', '.post-body', '.entry', '.blog-post',
        '.news-article', '.news_content', '.article__content',
        '.article-text', '.articleBody', '.article-content-inner'
    ]
    
    # Add more specific content areas from common CMS platforms
    cms_specific = [
        '.td-post-content',  # Newspaper theme
        '.tdb_single_content',  # Newspaper theme v2
        '.td-post-featured-image',  # Newspaper featured image
        '.tdb-single-content',  # Newspaper content
        '.tdb-block-inner',  # Newspaper blocks
        '.tdb-single-featured-image',  # Newspaper featured image v2
        '.td_block_wrap',  # Newspaper blocks wrapper
        '.elementor-widget-theme-post-content',  # Elementor
        '.elementor-widget-theme-post-featured-image',  # Elementor featured image
        '.elementor-image',  # Elementor images
        '.wp-block-image',  # Gutenberg blocks
        '.wp-block-embed',  # Gutenberg embeds
        '.content-inner',  # Many themes
        '.postarea',  # Common in many themes
        '.post-content',  # Common in many themes
        '.entry-content'  # Common in many themes
    ]
    
    article_selectors.extend(cms_specific)
    
    # Try article content areas
    for selector in article_selectors:
        try:
            articles = soup.select(selector)  # Get all matching elements
            for article in articles:
                if not article:
                    continue
                    
                logger.info(f"🔍 Searching in: {selector}")
                
                # First try to find a featured image
                featured_images = article.select('img.wp-post-image, .post-thumbnail img, .featured-image img, .post-image img, .entry-thumbnail img')
                for img in featured_images:
                    img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if img_url:
                        clean_url = clean_image_url(img_url)
                        if clean_url and test_image_url(clean_url):
                            logger.info(f"✅ Using featured image: {clean_url}")
                            return clean_url
                
                # Then look for all images in the article
                images = extract_images_from_html(article, base_url)
                
                # Test images in order and return the first accessible one
                for img_url in images:
                    clean_url = clean_image_url(img_url)
                    if clean_url and test_image_url(clean_url):
                        logger.info(f"✅ Using article image: {clean_url}")
                        return clean_url
                        
        except Exception as e:
            logger.debug(f"Error processing article selector {selector}: {str(e)}")
            continue
    
    # Priority 3: Look for OpenGraph/Twitter meta tags in the head
    try:
        head = soup.find('head')
        if head:
            # Look for OpenGraph image
            og_image = head.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image['content'].strip()
                clean_url = clean_image_url(img_url) or make_absolute_url_robust(img_url, base_url)
                if clean_url and test_image_url(clean_url):
                    logger.info(f"✅ Using OpenGraph image: {clean_url}")
                    return clean_url
            
            # Look for Twitter card image
            twitter_image = head.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                img_url = twitter_image['content'].strip()
                clean_url = clean_image_url(img_url) or make_absolute_url_robust(img_url, base_url)
                if clean_url and test_image_url(clean_url):
                    logger.info(f"✅ Using Twitter card image: {clean_url}")
                    return clean_url
                    
    except Exception as e:
        logger.debug(f"Error checking head meta tags: {str(e)}")
    
    # Priority 4: All page images (broader search)
    logger.info("🔍 Searching all page images...")
    try:
        all_images = extract_images_from_html(soup, base_url)
        
        # First pass: Look for large images that might be content images
        for img_url in all_images:
            # Skip if URL suggests it's an icon or small image
            url_lower = img_url.lower()
            if any(skip in url_lower for skip in ['icon', 'logo', 'favicon', 'sprite', 'button', 'bg_', '_bg', 'header', 'footer']):
                continue
                
            clean_url = clean_image_url(img_url)
            if clean_url and test_image_url(clean_url):
                # Check image dimensions if possible
                try:
                    response = requests.head(clean_url, timeout=5, allow_redirects=True)
                    if 'content-length' in response.headers:
                        size = int(response.headers['content-length'])
                        if size < 5000:  # Skip very small images
                            continue
                    logger.info(f"✅ Using large page image: {clean_url}")
                    return clean_url
                except:
                    logger.info(f"✅ Using page image (size unknown): {clean_url}")
                    return clean_url
        
        # Second pass: Try any remaining images
        for img_url in all_images:
            clean_url = clean_image_url(img_url)
            if clean_url and test_image_url(clean_url):
                logger.info(f"✅ Using fallback page image: {clean_url}")
                return clean_url
                
    except Exception as e:
        logger.debug(f"Error processing all page images: {str(e)}")
    
    # Priority 5: JSON-LD structured data
    try:
        # Look for JSON-LD script tags
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                # Handle both single object and array of objects
                if isinstance(data, list):
                    for item in data:
                        result = extract_image_from_ld_json(item)
                        if result:
                            return result
                else:
                    result = extract_image_from_ld_json(data)
                    if result:
                        return result
            except (json.JSONDecodeError, AttributeError) as e:
                logger.debug(f"Error parsing JSON-LD: {str(e)}")
                continue
    except Exception as e:
        logger.debug(f"Error processing JSON-LD: {str(e)}")
        
    # Helper function to extract image from JSON-LD data
    def extract_image_from_ld_json(data):
        """Extract image URL from JSON-LD data"""
        if not isinstance(data, dict):
            return None
            
        # Check for image property
        image = data.get('image')
        if image:
            if isinstance(image, str):
                clean_url = clean_image_url(image)
                if clean_url and test_image_url(clean_url):
                    logger.info(f"✅ Using JSON-LD image: {clean_url}")
                    return clean_url
            elif isinstance(image, dict) and image.get('url'):
                clean_url = clean_image_url(image['url'])
                if clean_url and test_image_url(clean_url):
                    logger.info(f"✅ Using JSON-LD image from dict: {clean_url}")
                    return clean_url
            elif isinstance(image, list) and len(image) > 0:
                for img in image:
                    if isinstance(img, str):
                        clean_url = clean_image_url(img)
                        if clean_url and test_image_url(clean_url):
                            logger.info(f"✅ Using JSON-LD image from list: {clean_url}")
                            return clean_url
                    elif isinstance(img, dict) and img.get('url'):
                        clean_url = clean_image_url(img['url'])
                        if clean_url and test_image_url(clean_url):
                            logger.info(f"✅ Using JSON-LD image from list dict: {clean_url}")
                            return clean_url
        
        # Check for thumbnailUrl
        thumbnail = data.get('thumbnailUrl')
        if thumbnail:
            clean_url = clean_image_url(thumbnail)
            if clean_url and test_image_url(clean_url):
                logger.info(f"✅ Using JSON-LD thumbnail: {clean_url}")
                return clean_url
        
        # Check for logo
        logo = data.get('logo')
        if logo and isinstance(logo, dict):
            logo_url = logo.get('url') or logo.get('contentUrl')
            if logo_url:
                clean_url = clean_image_url(logo_url)
                if clean_url and test_image_url(clean_url):
                    logger.info(f"✅ Using JSON-LD logo: {clean_url}")
                    return clean_url
        
        # Recursively check nested objects
        for value in data.values():
            if isinstance(value, (dict, list)):
                result = extract_image_from_ld_json(value)
                if result:
                    return result
        
        return None
    try:
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'image' in data:
                    img_url = clean_image_url(data['image'])
                    if img_url and test_image_url(img_url):
                        logger.info(f"Found image in JSON-LD: {img_url}")
                        return img_url
            except:
                continue
    except Exception as e:
        logger.warning(f"Error parsing JSON-LD: {e}")
    
    # 2. Try to find the first large image in the article
    try:
        # Look for images in article content
        article = soup.find('article') or soup.find('div', class_=lambda x: x and any(c in str(x).lower() for c in ['article', 'content', 'main']))
        if article:
            # First, try to find images with size hints
            for img in article.find_all('img', src=True):
                img_url = clean_image_url(img.get('src'))
                if not img_url:
                    continue
                    
                # Check for size hints in the image or its parent
                width = img.get('width', '')
                height = img.get('height', '')
                style = img.get('style', '')
                parent = img.find_parent()
                parent_style = parent.get('style', '') if parent else ''
                
                # If image has reasonable size or is in a container with size
                if (width and int(width.replace('px', '')) > 300) or \
                   (height and int(height.replace('px', '')) > 200) or \
                   'width:' in style.lower() or 'width:' in parent_style.lower():
                    if test_image_url(img_url):
                        logger.info(f"Found large image in article: {img_url}")
                        return img_url
            
            # If no large images found, try any image in the article
            for img in article.find_all('img', src=True):
                img_url = clean_image_url(img.get('src'))
                if img_url and test_image_url(img_url):
                    logger.info(f"Found fallback image in article: {img_url}")
                    return img_url
                    
            # Try background images in the article
            for element in article.find_all(style=True):
                style = element.get('style', '')
                if 'background-image:' in style:
                    try:
                        img_url = style.split('url(')[1].split(')')[0].strip('\'"')
                        img_url = clean_image_url(img_url)
                        if img_url and test_image_url(img_url):
                            logger.info(f"Found background image: {img_url}")
                            return img_url
                    except:
                        continue
    except Exception as e:
        logger.warning(f"Error finding image in article content: {e}")
    
    logger.warning("❌ No accessible image found after all fallbacks")
    return None

def extract_image_from_rss_robust(entry) -> Optional[str]:
    """
    ROBUST RSS image extraction with comprehensive fallback strategies
    """
    logger.info("🔍 Starting ROBUST RSS image extraction...")
    
    # Get base URL for relative paths
    base_url = ''
    if hasattr(entry, 'link'):
        base_url = entry.link
    elif hasattr(entry, 'id'):
        base_url = entry.id
    
    # Priority 1: Direct image URL in common fields
    image_fields = ['image', 'image_url', 'thumbnail', 'thumbnail_url', 'media:content', 'media:thumbnail']
    for field in image_fields:
        if hasattr(entry, field):
            url = getattr(entry, field, '').strip()
            if url and validate_image_url_robust(url):
                full_url = make_absolute_url_robust(url, base_url)
                if full_url and test_image_accessibility(full_url):
                    logger.info(f"✅ Using direct image from {field}: {full_url}")
                    return full_url
    
    # Priority 2: Media content (various formats)
    media_sources = []
    if hasattr(entry, 'media_content'):
        if isinstance(entry.media_content, list):
            media_sources.extend(entry.media_content)
        elif hasattr(entry.media_content, 'get'):
            media_sources.append(entry.media_content)
    
    for media in media_sources:
        try:
            media_type = media.get('type', '').lower()
            url = (media.get('url') or '').strip()
            if not url:
                continue
                
            # Handle different media types
            if media_type.startswith('image/') or any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                full_url = make_absolute_url_robust(url, base_url)
                if full_url and test_image_accessibility(full_url):
                    logger.info(f"✅ Using media content image: {full_url}")
                    return full_url
        except Exception as e:
            logger.debug(f"Error processing media content: {e}")
    
    # Priority 3: Media thumbnails
    thumbnails = []
    if hasattr(entry, 'media_thumbnail'):
        if isinstance(entry.media_thumbnail, list):
            thumbnails.extend(entry.media_thumbnail)
        else:
            thumbnails.append(entry.media_thumbnail)
    
    for thumb in thumbnails:
        try:
            if isinstance(thumb, dict):
                url = thumb.get('url', '').strip()
            else:
                url = str(thumb).strip()
                
            if url:
                full_url = make_absolute_url_robust(url, base_url)
                if full_url and test_image_accessibility(full_url):
                    logger.info(f"✅ Using media thumbnail: {full_url}")
                    return full_url
        except Exception as e:
            logger.debug(f"Error processing thumbnail: {e}")
    
    # Priority 4: Enclosures (podcast images, etc.)
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            try:
                enc_type = (enc.get('type') or '').lower()
                url = (enc.get('href') or '').strip()
                if not url:
                    continue
                    
                # Check if it's likely an image
                is_image = (enc_type.startswith('image/') or 
                          any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']))
                
                if is_image:
                    full_url = make_absolute_url_robust(url, base_url)
                    if full_url and test_image_accessibility(full_url):
                        logger.info(f"✅ Using enclosure image: {full_url}")
                        return full_url
            except Exception as e:
                logger.debug(f"Error processing enclosure: {e}")
    
    # Priority 5: Parse HTML content for images
    html_sources = []
    
    # Get all possible content fields
    content_fields = ['content', 'description', 'summary', 'subtitle', 'title']
    for field in content_fields:
        if hasattr(entry, field):
            field_value = getattr(entry, field, '')
            if isinstance(field_value, list) and field_value:
                for item in field_value:
                    if hasattr(item, 'value'):
                        html_sources.append(str(item.value))
            elif field_value:
                html_sources.append(str(field_value))
    
    # Also check for itunes:image
    if hasattr(entry, 'itunes_image'):
        if hasattr(entry.itunes_image, 'href'):
            html_sources.append(f'<img src="{entry.itunes_image.href}">')
    
    # Process all HTML content
    for html_content in html_sources:
        if not html_content:
            continue
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # First try to find OpenGraph/Twitter meta tags
            meta_image = soup.find('meta', property='og:image') or \
                        soup.find('meta', attrs={'name': 'twitter:image'}) or \
                        soup.find('meta', attrs={'name': 'thumbnail'})
                        
            if meta_image and meta_image.get('content'):
                url = meta_image.get('content', '').strip()
                full_url = make_absolute_url_robust(url, base_url)
                if full_url and test_image_accessibility(full_url):
                    logger.info(f"✅ Using meta tag image: {full_url}")
                    return full_url
            
            # Then look for all images
            images = extract_images_from_html(soup, base_url)
            
            # Sort by likely importance (larger images first)
            def get_image_priority(img_url):
                url_lower = img_url.lower()
                if any(x in url_lower for x in ['logo', 'icon', 'avatar', 'favicon']):
                    return 0
                if any(x in url_lower for x in ['featured', 'hero', 'main', 'cover']):
                    return 2
                return 1
                
            images.sort(key=get_image_priority, reverse=True)
            
            # Test each image
            for img_url in images:
                full_url = make_absolute_url_robust(img_url, base_url)
                if full_url and test_image_accessibility(full_url):
                    logger.info(f"✅ Using HTML content image: {full_url}")
                    return full_url
                    
        except Exception as e:
            logger.debug(f"Error processing HTML content: {e}")
    
    # Priority 6: Check for links that might point to images
    if hasattr(entry, 'links') and entry.links:
        for link in entry.links:
            try:
                if hasattr(link, 'href'):
                    url = link.href.strip()
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        full_url = make_absolute_url_robust(url, base_url)
                        if full_url and test_image_accessibility(full_url):
                            logger.info(f"✅ Using linked image: {full_url}")
                            return full_url
            except Exception as e:
                logger.debug(f"Error processing link: {e}")
    
    logger.warning("❌ No accessible RSS image found")
    return None
    return None

# Update your main extraction function
def extract_article_content_with_robust_images(url: str) -> Optional[dict]:
    """
    Enhanced article extraction with ROBUST image detection
    """
    logger.info(f"\n{'='*80}\nProcessing URL with ROBUST image extraction: {url}\n{'='*80}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title = ""
        title_selectors = [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'title',
            'h1'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text(strip=True)
                if title:
                    break
        
        # Extract content (your existing logic)
        for element in soup(["script", "style", "nav", "footer", "header", "iframe", "form", "button"]):
            element.decompose()
        
        article_body = None
        selectors = [
            'article', 'main', 'div.article', 'div.article-content',
            'div.post-content', 'div.entry-content', 'div.content'
        ]
        
        for selector in selectors:
            article_body = soup.select_one(selector)
            if article_body:
                break
        
        if not article_body:
            article_body = soup.body
        
        content = article_body.get_text(separator='\n', strip=True) if article_body else ""
        
        # ROBUST IMAGE EXTRACTION
        image_url = extract_image_from_article_robust(soup, url)
        
        return {
            'title': title,
            'content': content,
            'url': url,
            'image_url': image_url,
            'source': urllib.parse.urlparse(url).netloc
        }
        
    except Exception as e:
        logger.error(f"Failed to extract content from {url}: {str(e)}")
        return None

def get_cache_key(query: str, feed_url: str) -> str:
    """Generate a cache key for the query and feed URL"""
    key_str = f"{query.lower()}:{feed_url}"
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def load_from_cache(cache_key: str) -> Optional[List[Dict]]:
    """Load data from cache if it exists and is not expired"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None
        
    try:
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime > CACHE_TTL:
            return None
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error reading cache file {cache_file}: {e}")
        return None

def save_to_cache(cache_key: str, data: List[Dict]) -> None:
    """Save data to cache"""
    try:
        cache_file = CACHE_DIR / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error writing to cache file {cache_file}: {e}")

# Database connection
try:
    DB_URI = os.getenv('MONGODB_URI')
    if not DB_URI:
        raise ValueError("MONGODB_URI environment variable is not set")
        
    client = MongoClient(
        DB_URI,
        serverSelectionTimeoutMS=5000,  # 5 second timeout
        socketTimeoutMS=30000,
        connectTimeoutMS=10000,
        retryWrites=True,
        w='majority'
    )
    
    # Test the connection
    client.admin.command('ping')
    logger.info("✅ Successfully connected to MongoDB")
    
    db = client.get_database('news_scraper_db')
    rss_feeds_collection = db['rss_feeds']
    
except Exception as e:
    logger.error(f"❌ Failed to connect to MongoDB: {str(e)}")
    logger.warning("⚠️ Running in limited mode - RSS feed timestamps won't be updated")
    # Create a dummy client to prevent further errors
    class DummyMongoClient:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):
            return None
    
    client = DummyMongoClient()
    db = client
    rss_feeds_collection = DummyMongoClient()

def get_active_rss_feeds():
    """Fetch active RSS feeds from the database"""
    try:
        # Import here to avoid circular imports
        from models import get_rss_feeds
        
        # Get all active feeds from database
        feeds = get_rss_feeds(active_only=True)
        if not feeds:
            logger.warning("No active RSS feeds found in database")
            return []
            
        logger.info(f"Fetched {len(feeds)} active RSS feeds from database")
        return [feed['url'] for feed in feeds]
        
    except Exception as e:
        logger.error(f"Error fetching RSS feeds from database: {e}")
        # Return empty list instead of falling back to hardcoded feeds
        # This ensures we don't use outdated hardcoded feeds
        return []

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    return ' '.join(text.split())

def clean_url(url: str) -> str:
    """Clean and decode URL if needed"""
    try:
        return urllib.parse.unquote(url)
    except:
        return url

def get_article_image(soup, base_url):
    """
    Enhanced and reliable image extraction for articles with multiple fallback strategies.
    Returns the first valid image URL found, or None if no suitable image is found.
    
    Args:
        soup: BeautifulSoup object of the page
        base_url: Base URL for resolving relative URLs
        
    Returns:
        str: Absolute URL of the best image found, or None
    """
    logger.debug("\n" + "="*50 + "\nSTARTING IMAGE EXTRACTION\n" + "="*50)
    logger.debug(f"Base URL: {base_url}")
    logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
    
    # Save HTML for debugging
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    def is_image_valid(img_url):
        """Check if image URL is valid and likely to be a content image"""
        if not img_url or not isinstance(img_url, str):
            logger.debug(f"Invalid image URL (empty or not string): {img_url}")
            return False
            
        # Skip common placeholder or tracking images (but be less restrictive)
        skip_terms = ['pixel', 'track', 'logo', 'icon', 'sprite', 'spacer', 'blank', 'placeholder']
        for term in skip_terms:
            if term in img_url.lower():
                logger.debug(f"Skipping image with term '{term}': {img_url}")
                return False
            
        # Check common image extensions (be more permissive)
        img_exts = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg']
        has_extension = any(ext in img_url.lower() for ext in img_exts)
        has_image_path = any(term in img_url.lower() for term in ['/img/', '/images/', '/media/', 'image/'])
        
        if not has_extension and not has_image_path:
            logger.debug(f"No image extension or path found in URL: {img_url}")
            return False
            
        logger.debug(f"Valid image URL found: {img_url}")
        return True
            
        return True
    
    def get_image_from_meta(soup, attrs, attr_name):
        """Helper to get image from meta tags"""
        elements = soup.find_all('meta', attrs=attrs)
        for element in elements:
            if element.get(attr_name):
                try:
                    img_url = element[attr_name].strip()
                    logger.debug(f"Found potential image in meta {attrs}: {img_url}")
                    if is_image_valid(img_url):
                        abs_url = make_absolute_url(img_url, base_url)
                        if abs_url:
                            logger.debug(f"Trying absolute URL: {abs_url}")
                            if validate_image_url_robust(abs_url):
                                return abs_url
                except Exception as e:
                    logger.debug(f"Error processing meta tag: {e}")
                    continue
        return None
    
    def get_best_image_from_imgs(imgs):
        """Find the best image from a list of img tags"""
        if not imgs:
            return None
            
        # Score images based on size and position
        best_img = None
        best_score = -1
        
        for img in imgs:
            if not img.get('src'):
                continue
                
            img_url = img['src'].strip()
            if not is_image_valid(img_url):
                continue
                
            # Calculate score
            score = 0
            
            # Favor larger images
            width = int(img.get('width', 0) or 0)
            height = int(img.get('height', 0) or 0)
            size_score = width * height
            
            # Check for common content image patterns
            parent_classes = ' '.join(img.find_parent().get('class', [])) if img.find_parent() else ''
            img_classes = ' '.join(img.get('class', []))
            
            # Boost score for content-related classes
            content_terms = ['content', 'article', 'post', 'main', 'body', 'hero', 'featured']
            if any(term in parent_classes.lower() or term in img_classes.lower() for term in content_terms):
                score += 1000
                
            # Boost for larger images (but not too large which might be banners)
            if 200 < width < 1200 and 200 < height < 1200:
                score += size_score / 1000
                
            # Check if this is the new best image
            if score > best_score:
                best_score = score
                best_img = img
                
        return best_img['src'] if best_img else None
    
    # 1. Try Open Graph and Twitter meta tags first
    meta_sources = [
        {'property': 'og:image'},
        {'name': 'twitter:image'},
        {'property': 'og:image:secure_url'},
        {'itemprop': 'image'},
        {'name': 'thumbnail'},
        {'property': 'og:image:url'},
        {'name': 'msapplication-TileImage'},
        {'name': 'twitter:image:src'},
        {'property': 'og:image:secure'},
        # Add more common meta tags
        {'name': 'image'},
        {'property': 'image'},
        {'name': 'og:image:url'},
        {'name': 'og:image'},
        {'property': 'twitter:image'},
        {'name': 'twitter:image:src'},
        {'property': 'twitter:image:src'},
        # Add more variations
        {'name': 'thumbnailUrl'},
        {'property': 'thumbnail'},
        {'name': 'og:image:image'}
    ]
    
    # Also check link tags
    link_sources = [
        {'rel': 'image_src'},
        {'rel': 'apple-touch-icon'},
        {'rel': 'icon'},
        {'rel': 'shortcut icon'}
    ]
    
    # Try meta tags first
    for meta in meta_sources:
        img_url = get_image_from_meta(soup, meta, 'content')
        if img_url:
            logger.debug(f"✅ Found image via meta {meta}: {img_url}")
            return img_url
    
    # Try link tags
    for link in link_sources:
        try:
            element = soup.find('link', attrs=link)
            if element and element.get('href'):
                img_url = element['href'].strip()
                logger.debug(f"Found potential image in link {link}: {img_url}")
                if is_image_valid(img_url):
                    abs_url = make_absolute_url(img_url, base_url)
                    if abs_url and validate_image_url_robust(abs_url):
                        logger.debug(f"✅ Found image via link {link}: {abs_url}")
                        return abs_url
        except Exception as e:
            logger.debug(f"Error processing link tag: {e}")
            continue
    
    # 2. Try to find any image in the article content
    article = soup.find('article') or soup.find('div', class_=lambda x: x and any(cls in (x or '').lower() for cls in ['article', 'post', 'content', 'main', 'entry', 'story', 'news', 'body']))
    if not article:
        # Try to find any div that might contain article content
        article = soup.find('div', id=lambda x: x and any(cls in x.lower() for cls in ['content', 'main', 'article', 'post', 'story', 'news', 'body']))
    
    content = article if article else soup
    
    # Look for all images in the content
    imgs = content.find_all('img')
    logger.debug(f"Found {len(imgs)} potential images in content")
    
    # If no images found in article, try to find any image in the page
    if not imgs:
        imgs = soup.find_all('img')
        logger.debug(f"No images in article, found {len(imgs)} images in entire page")
        for img in imgs:
            try:
                if not img.get('src'):
                    continue
                    
                img_url = img['src'].strip()
                if not is_image_valid(img_url):
                    # Try data-src or other common lazy-loading attributes
                    for attr in ['data-src', 'data-lazy-src', 'data-original', 'data-srcset']:
                        if img.get(attr):
                            img_url = img[attr].split(' ')[0].strip()  # Handle srcset
                            if is_image_valid(img_url):
                                break
                    else:
                        continue
                
                abs_url = make_absolute_url(img_url, base_url)
                if abs_url and validate_image_url_robust(abs_url):
                    # Check image dimensions if available
                    width = int(img.get('width', 0) or 0)
                    height = int(img.get('height', 0) or 0)
                    
                    # Prefer larger images but not too large (likely banners)
                    if 200 < width < 2000 and 200 < height < 2000:
                        logger.debug(f"✅ Found content image: {abs_url} ({width}x{height})")
                        return abs_url
                    
                    # If no dimensions, still consider it
                    if width == 0 and height == 0:
                        logger.debug(f"✅ Found content image (no dimensions): {abs_url}")
                        return abs_url
                        
            except Exception as e:
                logger.debug(f"Error processing image: {e}")
                continue
    
    # 3. Try to find any image in the page
    all_imgs = soup.find_all('img')
    logger.debug(f"Found {len(all_imgs)} total images on page")
    
    # Log first 5 images for debugging
    for i, img in enumerate(all_imgs[:5]):
        src = img.get('src', 'no-src')
        classes = ' '.join(img.get('class', [])) if img.get('class') else 'no-class'
        logger.debug(f"Image {i+1}: src='{src}', classes='{classes}'")
        for img in all_imgs:
            try:
                if not img.get('src'):
                    continue
                    
                img_url = img['src'].strip()
                if not is_image_valid(img_url):
                    continue
                    
                abs_url = make_absolute_url(img_url, base_url)
                if abs_url and validate_image_url_robust(abs_url):
                    logger.debug(f"✅ Found page image: {abs_url}")
                    return abs_url
                    
            except Exception as e:
                logger.debug(f"Error processing page image: {e}")
                continue
    
    # 4. Try to find background images in CSS
    try:
        for element in soup.find_all(style=True):
            style = element['style']
            if 'background' in style and 'url(' in style:
                # Extract URL from background style
                start = style.find('url(') + 4
                end = style.find(')', start)
                if start > 3 and end > start:
                    img_url = style[start:end].strip('"\'')
                    if is_image_valid(img_url):
                        abs_url = make_absolute_url(img_url, base_url)
                        if abs_url and validate_image_url_robust(abs_url):
                            logger.debug(f"✅ Found background image: {abs_url}")
                            return abs_url
    except Exception as e:
        logger.debug(f"Error finding background images: {e}")
    
    # 5. Last resort: Try to find any image in the head section
    try:
        head = soup.find('head')
        if head:
            # Look for meta tags with image URLs
            for meta in head.find_all('meta', content=True):
                content = meta['content'].strip()
                if is_image_valid(content):
                    abs_url = make_absolute_url(content, base_url)
                    if abs_url and validate_image_url_robust(abs_url):
                        logger.debug(f"✅ Found image in head meta: {abs_url}")
                        return abs_url
    except Exception as e:
        logger.debug(f"Error checking head section: {e}")
    
    # Log all image sources for debugging
    logger.debug("\n" + "="*50 + "\nALL IMAGE SOURCES FOUND:\n" + "="*50)
    for i, img in enumerate(soup.find_all('img')[:20]):  # Limit to first 20 to avoid huge logs
        src = img.get('src', 'no-src')
        classes = ' '.join(img.get('class', [])) if img.get('class') else 'no-class'
        parent = img.parent.name if img.parent else 'no-parent'
        logger.debug(f"{i+1}. src='{src}' | classes='{classes}' | parent='{parent}'")
    
    logger.debug("\n" + "="*50 + "\nNO SUITABLE IMAGE FOUND\n" + "="*50)
    return None

def make_absolute_url(image_url, base_url):
    """
    Convert relative URLs to absolute URLs with detailed logging
    """
    logger.debug(f"Making URL absolute. Base: {base_url}, Relative: {image_url}")
    
    if not image_url:
        logger.debug("❌ No image URL provided")
        return None
        
    # Clean up the URL
    image_url = image_url.strip()
    
    # If it's already an absolute URL, return as is
    if image_url.startswith(('http://', 'https://')):
        logger.debug(f"✅ Already absolute URL: {image_url}")
        return image_url
        
    # Handle protocol-relative URLs
    if image_url.startswith('//'):
        parsed = urllib.parse.urlparse(base_url)
        result = f"{parsed.scheme}:{image_url}"
        logger.debug(f"✅ Converted protocol-relative URL to: {result}")
        return result
        
    # Handle root-relative URLs
    if image_url.startswith('/'):
        parsed = urllib.parse.urlparse(base_url)
        result = f"{parsed.scheme}://{parsed.netloc}{image_url}"
        logger.debug(f"✅ Converted root-relative URL to: {result}")
        return result
        
    # Handle relative URLs
    try:
        result = urllib.parse.urljoin(base_url, image_url)
        logger.debug(f"✅ Converted relative URL to: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Error making URL absolute: {str(e)}\nBase URL: {base_url}\nImage URL: {image_url}")
        return image_url

def _extract_publish_date(self, soup, result):
    """
    Extract the publish date from various meta tags and content patterns
    
    Args:
        soup: BeautifulSoup object of the page
        result: Dictionary to store the extracted date
    """
    # Common date selectors in order of preference
    date_selectors = [
        # Meta tags
        ('meta', {'property': 'article:published_time'}),
        ('meta', {'property': 'og:published_time'}),
        ('meta', {'name': 'pubdate'}),
        ('meta', {'name': 'publish_date'}),
        ('meta', {'name': 'date'}),
        ('meta', {'itemprop': 'datePublished'}),
        ('meta', {'name': 'DC.date.issued'}),
        
        # Time elements
        ('time', {'datetime': True}),
        ('time', {'pubdate': True}),
        ('span', {'class': 'date'}),
        ('div', {'class': 'date'}),
        ('span', {'class': 'published'}),
        ('div', {'class': 'published'}),
        ('span', {'class': 'timestamp'}),
        ('div', {'class': 'timestamp'}),
    ]
    
    # Try to extract date from meta tags first
    for tag, attrs in date_selectors[:7]:  # Just the meta tags
        element = soup.find(tag, attrs)
        if element and element.get('content'):
            date_str = element['content'].strip()
            try:
                # Try to parse the date string
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                result['publish_date'] = date_obj.isoformat()
                logger.info(f"Found publish date in meta: {result['publish_date']}")
                return
            except (ValueError, AttributeError):
                continue
    
    # If no meta date found, try to find date in content
    for tag, attrs in date_selectors[7:]:  # The rest of the selectors
        element = soup.find(tag, attrs)
        if element and element.get_text(strip=True):
            date_str = element.get_text(strip=True)
            # Try to parse common date formats
            date_formats = [
                '%Y-%m-%dT%H:%M:%S%z',  # ISO 8601 with timezone
                '%Y-%m-%dT%H:%M:%S',     # ISO 8601 without timezone
                '%Y-%m-%d',              # Simple date
                '%B %d, %Y',             # Month day, Year
                '%b %d, %Y',             # Abbreviated month
                '%d %B %Y',              # Day Month Year
                '%d %b %Y',              # Day Abbreviated Month Year
                '%m/%d/%Y',              # MM/DD/YYYY
                '%d/%m/%Y',              # DD/MM/YYYY
                '%Y/%m/%d',              # YYYY/MM/DD
            ]
            
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    result['publish_date'] = date_obj.isoformat()
                    logger.info(f"Found publish date in content: {result['publish_date']}")
                    return
                except ValueError:
                    continue
    
    # If still no date found, use current time as fallback
    if 'publish_date' not in result:
        result['publish_date'] = datetime.utcnow().isoformat() + 'Z'
        logger.warning("No publish date found, using current time")

def _clean_article(self, article):
    """
    Clean up the article content by removing unnecessary elements
    
    Args:
        article: BeautifulSoup element containing the article content
    """
    # Remove script and style elements
    for element in article(['script', 'style', 'noscript', 'iframe', 'object', 'embed', 'video', 'audio']):
        element.decompose()
    
    # Remove common non-content elements
    for element in article.find_all(['nav', 'header', 'footer', 'aside', 'menu', 'form', 'button', 'input', 'select', 'textarea']):
        element.decompose()
    
    # Remove elements with common non-content classes
    non_content_classes = [
        'nav', 'navbar', 'header', 'footer', 'sidebar', 'menu', 'ad', 'ads', 'advertisement',
        'social', 'share', 'comments', 'related', 'recommended', 'popular', 'trending',
        'newsletter', 'subscribe', 'signup', 'login', 'search', 'pagination', 'breadcrumb',
        'cookie', 'banner', 'modal', 'popup', 'overlay', 'tooltip', 'notification',
        'hidden', 'hidden-xs', 'hidden-sm', 'hidden-md', 'hidden-lg', 'sr-only', 'visually-hidden'
    ]
    
    for class_name in non_content_classes:
        for element in article.find_all(class_=lambda x: x and any(cn in x.lower() for cn in class_name.split(' '))):
            element.decompose()
    
    # Remove empty elements
    for element in article.find_all(True):
        if not element.get_text(strip=True) and not element.find(['img', 'svg']):
            element.decompose()

def extract_article_content(url: str) -> Optional[Dict[str, str]]:
    """
    Extract article content and first image using BeautifulSoup with improved image extraction
    and better error handling and logging.
    
    Args:
        url: The URL of the article to extract content from
        
    Returns:
        Optional[Dict[str, str]]: A dictionary containing the extracted article data,
        or None if extraction failed
    """
    logger.info(f"\n{'='*80}\nProcessing URL: {url}\n{'='*80}")
    
    # Initialize result with default values
    result = {
        'title': '',
        'content': '',
        'url': clean_url(url),  # Clean the URL first
        'image_url': None,
        'publish_date': None,
        'source': '',
        'author': None,
        'keywords': [],
        'description': ''
    }
    
    try:
        # Extract domain for source
        domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
        result['source'] = domain.capitalize()
        
        # Enhanced headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Create a session with retry mechanism and timeout
        session = requests.Session()
        session.headers.update(headers)
        
        # Configure retry strategy
        retry_strategy = requests.adapters.HTTPAdapter(
            max_retries=3,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        session.mount("http://", retry_strategy)
        session.mount("https://", retry_strategy)
        logger.info(f"Fetching URL: {url}")
        response = session.get(url, timeout=15)
        response.raise_for_status()
        
        # Check if the response is HTML
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            logger.error(f"Unexpected content type: {content_type}")
            return None
            
        # Parse the HTML content with lxml parser for better performance
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Extract title from meta tags or title tag
        title = None
        title_tags = [
            ('meta', {'property': 'og:title'}),
            ('meta', {'name': 'title'}),
            ('title', {})
        ]
        
        for tag, attrs in title_tags:
            if not title:
                element = soup.find(tag, attrs)
                if element and element.get('content'):
                    title = element['content'].strip()
                elif element and element.text:
                    title = element.text.strip()
        
        if title:
            result['title'] = clean_text(title)
        
        # Extract description from meta tags
        description = None
        desc_tags = [
            ('meta', {'property': 'og:description'}),
            ('meta', {'name': 'description'}),
            ('meta', {'name': 'twitter:description'})
        ]
        
        for tag, attrs in desc_tags:
            if not description:
                element = soup.find(tag, attrs)
                if element and element.get('content'):
                    description = element['content'].strip()
        
        if description:
            result['description'] = clean_text(description)
        
        # Try to find the main article content using common selectors
        article = None
        content_selectors = [
            'article',
            'main',
            'div.article',
            'div.article-body',
            'div.article__body',
            'div.article-content',
            'div.article__content',
            'div.article-content__content',
            'div.post',
            'div.post__content',
            'div.entry',
            'div.entry__content',
            'div.story',
            'div.story__content',
            'div.content',
            'div.main-content',
            'div.main',
            'div#content',
            'div#main',
            'div#article',
            'div#article-body'
        ]
        
        # Try each selector until we find a match
        for selector in content_selectors:
            if not article:
                article = soup.select_one(selector)
                if article:
                    logger.info(f"Found content using selector: {selector}")
        
        # If no specific content found, try to find the main content area with text density analysis
        if not article:
            logger.info("Trying text density analysis...")
            candidates = []
            
            # Look for potential content containers
            for elem in soup.find_all(['article', 'div', 'section', 'main']):
                # Skip elements with little text
                text = elem.get_text(strip=True)
                if len(text) < 100:
                    continue
                
                # Skip navigation and other non-content elements
                if any(x in elem.get('class', []) for x in ['nav', 'header', 'footer', 'sidebar', 'menu']):
                    continue
                    
                # Calculate text to HTML ratio
                text_length = len(text)
                html_length = len(str(elem))
                
                if html_length > 0 and text_length > 0:
                    density = text_length / html_length
                    if density > 0.1:  # Reasonable text density threshold
                        # Score based on density and text length
                        score = density * (text_length ** 0.5)
                        candidates.append((score, elem))
            
            if candidates:
                candidates.sort(reverse=True, key=lambda x: x[0])
                article = candidates[0][1]
                logger.info(f"Found content using text density analysis (score: {candidates[0][0]:.2f})")
        
        # Fall back to body if no better content found
        if not article:
            logger.warning("Falling back to body tag for content")
            article = soup.body
            
        if not article:
            logger.error("Could not find main content area")
            return None
        
        # Clean up the article content
        self._clean_article(article)
        
        # Extract text content
        paragraphs = []
        
        # First try to get structured paragraphs
        for p in article.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = p.get_text(strip=True)
            if text and len(text) > 10:  # Skip very short paragraphs
                # Add extra newlines before headings
                if p.name.startswith('h') and paragraphs:
                    paragraphs.append('')
                paragraphs.append(text)
        
        # If no structured content found, fall back to full text
        if not paragraphs:
            text = article.get_text(separator='\n', strip=True)
            paragraphs = [p for p in text.split('\n') if p.strip()]
        
        # Clean and join paragraphs
        result['content'] = '\n\n'.join(clean_text(p) for p in paragraphs if p.strip())
        
        # Extract image using our enhanced function
        image_url = get_article_image(soup, url)
        if image_url:
            logger.info(f"✅ Found article image: {image_url}")
            result['image_url'] = image_url
        else:
            logger.warning("⚠️ No suitable image found for the article")
            # If no image found, try a more direct approach
            img = soup.find('img')
            if img and img.get('src'):
                image_url = make_absolute_url(img['src'].strip(), url)
        
        # Extract publish date using our helper method
        self._extract_publish_date(soup, result)
        
        # Extract author if available
        author = None
        author_selectors = [
            ('meta', {'name': 'author'}),
            ('meta', {'property': 'article:author'}),
            ('meta', {'property': 'og:site_name'}),
            ('a', {'rel': 'author'}),
            ('span', {'class': 'author'}),
            ('div', {'class': 'author'}),
            ('span', {'class': 'byline'}),
            ('div', {'class': 'byline'})
        ]
        
        for tag, attrs in author_selectors:
            if not author:
                element = soup.find(tag, attrs)
                if element:
                    if element.get('content'):
                        author = element['content'].strip()
                    elif element.text.strip():
                        author = element.text.strip()
        
        if author:
            result['author'] = clean_text(author)
        
        # Extract keywords if available
        keywords = []
        keyword_elements = soup.find_all('meta', attrs={'name': 'keywords'})
        for element in keyword_elements:
            if element.get('content'):
                keywords.extend([k.strip() for k in element['content'].split(',') if k.strip()])
        
        if keywords:
            result['keywords'] = list(set(keywords))  # Remove duplicates
        
        # Extract source from URL domain
        if 'source' not in result or not result['source']:
            try:
                domain = urllib.parse.urlparse(url).netloc
                if domain.startswith('www.'):
                    domain = domain[4:]
                result['source'] = domain
            except Exception as e:
                logger.warning(f"Could not extract source from URL: {e}")
        
        # Final cleanup and validation
        for key in ['title', 'content', 'description']:
            if key in result and result[key]:
                result[key] = clean_text(result[key])
        
        # Ensure required fields have values with proper defaults
        result.setdefault('title', 'Untitled Article')
        result.setdefault('content', 'No content available.')
        result.setdefault('source', 'Unknown Source')
        
        # Ensure publish date is set (handled by _extract_publish_date)
        if 'publish_date' not in result:
            result['publish_date'] = datetime.utcnow().isoformat() + 'Z'
            logger.warning("No publish date found, using current time")

        return {
            'title': result['title'],
            'content': result['content'],
            'publish_date': result['publish_date'],
            'url': url,
            'source': result['source'],
            'image_url': result.get('image_url')
        }
        
    except Exception as e:
        logger.error(f"Failed to extract content from {url}: {str(e)}")
        return None

def create_name_pattern(name: str) -> Tuple[re.Pattern, List[str]]:
    """
    Create a strict regex pattern for exact name matching.
    Only matches the exact name or common variations with initials.
    """
    name = name.strip('"\'').strip()
    if not name:
        return None, []
    
    # Convert to lowercase for case-insensitive matching
    exact_phrase = name.lower()
    name_parts = [p for p in exact_phrase.split() if p.strip()]
    
    if not name_parts:
        return None, []
    
    # Only create patterns for the exact phrase and its variations
    patterns = []
    
    # 1. Exact full name with word boundaries
    full_name = ' '.join(name_parts)
    patterns.append(r'(?<!\w)' + re.escape(full_name) + r'(?!\w)')
    
    # 2. Reversed name order (only for multi-word names)
    if len(name_parts) > 1:
        reversed_name = ' '.join(reversed(name_parts))
        patterns.append(r'(?<!\w)' + re.escape(reversed_name) + r'(?!\w)')
        
        # 3. First name + last initial (e.g., "Amine R.")
        first_last_initial = f"{name_parts[0]} {name_parts[-1][0]}."
        patterns.append(r'(?<!\w)' + re.escape(first_last_initial) + r'(?!\w)')
        
        # 4. First initial + last name (e.g., "A. Raghib")
        first_initial_last = f"{name_parts[0][0]}. {name_parts[-1]}"
        patterns.append(r'(?<!\w)' + re.escape(first_initial_last) + r'(?!\w)')
    
    # Combine all patterns with OR
    pattern = '(?i)(?:' + '|'.join(patterns) + ')'
    
    # For search terms, use the exact phrase and common variations
    search_terms = [' '.join(name_parts)]
    if len(name_parts) > 1:
        search_terms.extend([
            ' '.join(reversed(name_parts)),
            f"{name_parts[0]} {name_parts[-1][0]}.",
            f"{name_parts[0][0]}. {name_parts[-1]}"
        ])
    
    logger.info("\n=== NAME SEARCH PATTERNS ===")
    logger.info(f"Original name: {name}")
    logger.info(f"Search terms: {search_terms}")
    logger.info(f"Regex pattern: {pattern}")
    
    try:
        return re.compile(pattern), search_terms
    except re.error as e:
        logger.error(f"Error compiling regex pattern: {e}")
        return None, search_terms

def search_rss_feeds(query: str, max_articles: int = 20) -> List[Dict[str, str]]:
    """Search for articles across all active RSS feeds with exact name matching"""
    # Create name pattern and get search terms
    name_pattern, search_terms = create_name_pattern(query)
    
    if not name_pattern:
        return []
        
    articles = []
    processed_urls = set()
    
    # Check cache first
    cache_key = hashlib.md5(f"rss_search_{query}".encode()).hexdigest()
    if cached_results := load_from_cache(cache_key):
        logger.info(f"Using cached results for query: {query}")
        return cached_results[:max_articles]
    
    # Get active RSS feeds from database
    active_feeds = get_active_rss_feeds()
    logger.info(f"Found {len(active_feeds)} active RSS feeds to search")
    
    for feed_url in active_feeds:
        if len(articles) >= max_articles:
            break
            
        try:
            logger.info(f"Searching in feed: {feed_url}")
            feed = feedparser.parse(feed_url, request_headers=HEADERS, agent=USER_AGENT)
            if hasattr(feed, 'bozo_exception'):
                logger.warning(f"Error parsing feed {feed_url}: {feed.bozo_exception}")
                continue
                
            # Update last_checked timestamp in database
            try:
                rss_feeds_collection.update_one(
                    {"url": feed_url},
                    {"$set": {"last_checked": datetime.utcnow()}},
                    upsert=False
                )
            except Exception as e:
                logger.warning(f"Could not update last_checked for {feed_url}: {e}")
            
            entries = feed.entries[:20]  # Limit entries to process per feed
            
            for entry in entries:
                if len(articles) >= max_articles:
                    break
                    
                try:
                    url = clean_url(entry.get('link', ''))
                    if not url or url in processed_urls:
                        continue
                        
                    # Get entry content for searching
                    title = entry.get('title', '').lower()
                    description = entry.get('description', '').lower()
                    content = ''
                    if hasattr(entry, 'content'):
                        content = ' '.join([c.get('value', '').lower() for c in entry.content if hasattr(c, 'value')])
                    
                    # Combine all text for searching (lowercase for case-insensitive matching)
                    search_text = f"{title} {description} {content}".lower()
                    
                    # Skip this article if it doesn't match the name pattern
                    if not name_pattern or not name_pattern.search(search_text):
                        continue
                        
                    # If we get here, we have a match
                    match = name_pattern.search(search_text)
                    logger.info(f"✅ MATCH FOUND: '{match.group(0)}' in {entry.get('title', 'Untitled')}")
                    
                    try:
                        # Initialize article data with basic info
                        entry_data = {
                            'title': clean_text(entry.get('title', '')),
                            'url': url,
                            'publish_date': '',
                            'content': clean_text(entry.get('description', '')),
                            'source': clean_text(feed.get('feed', {}).get('title', urllib.parse.urlparse(feed_url).netloc)),
                            'author': clean_text(entry.get('author', 'Unknown')),
                            'image_url': None
                        }
                        
                        # Try to extract image from RSS entry first
                        rss_image = extract_image_from_rss_robust(entry)
                        if rss_image:
                            entry_data['image_url'] = clean_url(rss_image)
                            logger.info(f"📸 Found RSS image: {entry_data['image_url']}")
                        
                        # Set publish date from entry if available
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                entry_data['publish_date'] = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d')
                            except Exception as e:
                                logger.warning(f"Error parsing publish date: {e}")
                        
                        # If no date from published_parsed, try other date fields
                        if not entry_data['publish_date']:
                            for date_field in ['updated', 'published', 'pubDate', 'dc:date']:
                                if hasattr(entry, date_field):
                                    entry_data['publish_date'] = clean_text(str(getattr(entry, date_field)))
                                    break
                        
                        # Try to extract full article content and image if we don't have enough content
                        if len(entry_data['content']) < 200:  # If content is too short
                            try:
                                article_data = extract_article_content(url)
                                if article_data:
                                    # Update entry data with extracted content
                                    if article_data.get('content'):
                                        entry_data['content'] = clean_text(article_data['content'])
                                    
                                    # Use extracted image if we don't have one from RSS
                                    if article_data.get('image_url') and not entry_data.get('image_url'):
                                        entry_data['image_url'] = clean_url(article_data['image_url'])
                                        logger.info(f"📸 Added extracted image: {entry_data['image_url']}")
                                    
                                    # Update publish date if we don't have one
                                    if article_data.get('publish_date') and not entry_data.get('publish_date'):
                                        entry_data['publish_date'] = article_data['publish_date']
                            except Exception as e:
                                logger.warning(f"Error extracting article content from {url}: {e}")
                        
                        # Ensure we have some content
                        if not entry_data.get('content'):
                            entry_data['content'] = clean_text(entry.get('description', f"No content available. Please visit the source: {url}"))
                        
                        # Clean up the image URL if it exists
                        if entry_data.get('image_url'):
                            entry_data['image_url'] = clean_url(entry_data['image_url'])
                            
                            # Convert relative URLs to absolute
                            if entry_data['image_url'].startswith('//'):
                                entry_data['image_url'] = f'https:{entry_data["image_url"]}'
                            elif entry_data['image_url'].startswith('/'):
                                parsed_uri = urllib.parse.urlparse(url)
                                entry_data['image_url'] = f"{parsed_uri.scheme}://{parsed_uri.netloc}{entry_data['image_url']}"
                        
                        # Add the entry data to articles list
                        articles.append(entry_data)
                        processed_urls.add(url)
                        
                        logger.info(f"✅ Added article: {entry_data.get('title')} - Image: {entry_data.get('image_url', 'No image')}")
                        
                    except Exception as e:
                        logger.error(f"Error processing article {url}: {e}", exc_info=True)
                        
                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error processing feed {feed_url}: {e}")
            # Update error status in database
            try:
                rss_feeds_collection.update_one(
                    {"url": feed_url},
                    {"$set": {"last_error": str(e), "last_checked": datetime.utcnow()}},
                    upsert=False
                )
            except Exception as db_error:
                logger.warning(f"Could not update error status for {feed_url}: {db_error}")
            continue
    
    # Cache the results
    if articles:
        save_to_cache(cache_key, articles)
    
    return articles

def get_news_about(query: str, max_articles: int = 50, start_date: str = None, end_date: str = None) -> List[Dict[str, str]]:
    """
    Get news articles about a person or company with date range filtering
    
    Args:
        query: Name of the person or company to search for
        max_articles: Maximum number of articles to return
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        
    Returns:
        List of article dictionaries with title, content, url, publish_date, image_url, and source
    """
    logger.info(f"Searching for news about: {query}")
    if start_date and end_date:
        logger.info(f"Date range: {start_date} to {end_date}")
    
    # Generate cache key based on query and date range
    date_range = f"{start_date or ''}_{end_date or ''}"
    cache_key = get_cache_key(f"{query}_{date_range}", "news_about")
    
    # Try to load from cache first
    cached_results = load_from_cache(cache_key)
    if cached_results:
        logger.info(f"Using cached results for query: {query} (date range: {date_range})")
        return cached_results[:max_articles]
    
    all_articles = []
    
    # Search RSS feeds
    logger.info("Searching RSS feeds...")
    rss_articles = search_rss_feeds(query, max_articles)
    all_articles.extend(rss_articles)
    
    # Try to fetch from NewsAPI if available
    try:
        from news_fetcher import fetch_news as fetch_news_api
        logger.info("Trying NewsAPI...")
        api_articles = fetch_news_api(query, max_articles)
        
        # Convert the format to match our structure
        for article in api_articles:
            all_articles.append({
                'title': article['title'],
                'content': article['content'],
                'url': article['url'],
                'publish_date': article['publish_date'],
                'source': urllib.parse.urlparse(article['url']).netloc,
                'image_url': article.get('image_url')
            })
    except Exception as e:
        logger.warning(f"Error fetching from NewsAPI: {str(e)}")
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_articles = []
    
    for article in all_articles:
        if article['url'] not in seen_urls:
            seen_urls.add(article['url'])
            
            # Convert publish_date to datetime for comparison if it exists
            article_date = None
            if article.get('publish_date'):
                try:
                    article_date = datetime.strptime(article['publish_date'].split('T')[0], '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
            
            # Apply date filtering if dates are provided
            include_article = True
            if start_date and article_date:
                if article_date < datetime.strptime(start_date, '%Y-%m-%d'):
                    include_article = False
            if end_date and article_date:
                if article_date > datetime.strptime(end_date, '%Y-%m-%d'):
                    include_article = False
            
            if include_article:
                unique_articles.append(article)
    
    # Sort by date (newest first)
    unique_articles.sort(
        key=lambda x: (
            datetime.strptime(x.get('publish_date', '1970-01-01').split('T')[0], '%Y-%m-%d') 
            if x.get('publish_date') 
            else datetime.min
        ),
        reverse=True
    )
    
    # Cache the results if we have any
    if unique_articles:
        try:
            save_to_cache(cache_key, unique_articles)
        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")
    
    # Return the requested number of articles
    return unique_articles[:max_articles][:max_articles]

if __name__ == "__main__":
    # Example usage
    name = input("Enter a person or company name: ")
    print(f"\nSearching for news about: {name}\n")
    
    start_time = time.time()
    articles = get_news_about(name, max_articles=10)
    
    print(f"\nFound {len(articles)} articles in {time.time() - start_time:.2f} seconds\n")
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   URL: {article['url']}")
        print(f"   Date: {article.get('publish_date', 'Unknown date')}")
        print(f"   Source: {article.get('source', 'Unknown')}")
        print(f"   Image: {article.get('image_url', 'No image')}")
        print(f"   Content: {article['content'][:150]}...\n")