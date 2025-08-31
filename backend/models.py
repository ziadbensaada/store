import os
from datetime import datetime
from pymongo import MongoClient, IndexModel, ASCENDING
from pymongo.errors import DuplicateKeyError
import bcrypt
from dotenv import load_dotenv
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

# Load environment variables

from pathlib import Path

# Get the directory where this script is located
script_dir = Path(__file__).parent
print(f"Script directory: {script_dir}")
print(f"Files in script directory: {os.listdir(script_dir)}")

# Load .env file from the same directory as this script
env_path = script_dir / '.env'
print(f"Loading .env file from: {env_path}")

# Check if .env file exists and is readable
if not env_path.exists():
    print("❌ Error: .env file does not exist at the expected location")
    print(f"Current directory: {os.getcwd()}")
    print(f"Directory contents: {os.listdir(script_dir)}")
else:
    print(f"✅ .env file exists at: {env_path}")
    try:
        with open(env_path, 'r') as f:
            print("🔒 .env file contents (first 3 lines):")
            for i, line in enumerate(f):
                if i < 3:  # Only show first 3 lines for security
                    print(f"   {line.strip()}")
                if i == 2 and len(f.readlines()) > 3:
                    print("   ... (more lines not shown for security)")
                    break
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")

# Load environment variables
load_dotenv(env_path, override=True)

# Debug: Print environment variables
print("Environment variables loaded:", os.environ.get('MONGODB_URI') is not None)
if os.environ.get('MONGODB_URI'):
    print("MongoDB URI found in environment variables")
else:
    print("MongoDB URI NOT found in environment variables")

# Available domains for user interests
AVAILABLE_DOMAINS = [
    'Technology', 'Business', 'Science', 'Health',
    'Entertainment', 'Sports', 'Politics', 'Education',
    'Environment', 'Finance', 'Travel', 'Food', 'Fashion'
]

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGODB_URI)
db = client['news_scraper_db']
users_collection = db['users']
search_history_collection = db['search_history']
rss_feeds_collection = db['rss_feeds']

# Create indexes for RSS feeds
rss_feeds_collection.create_index([("url", ASCENDING)], unique=True)
rss_feeds_collection.create_index([("is_active", ASCENDING)])

# Create indexes
users_collection.create_index('username', unique=True)
users_collection.create_index('email', unique=True)

def get_user(username: str):
    """Retrieve a user by username."""
    return users_collection.find_one({"$or": [{"username": username}, {"email": username}]})

def verify_user(username: str, password: str):
    """Verify user credentials.
    
    Args:
        username: Username or email of the user
        password: Plain text password
        
    Returns:
        dict: User document if authentication succeeds, None otherwise
    """
    try:
        user = get_user(username)
        if not user:
            print(f"User not found: {username}")
            return None
            
        if not isinstance(user.get('password'), bytes):
            print("Invalid password format in database")
            return None
            
        if bcrypt.checkpw(password.encode('utf-8'), user['password']):
            print(f"User authenticated: {username}")
            # Ensure we have all required fields with defaults
            user_data = {
                '_id': user['_id'],
                'username': user['username'],
                'email': user.get('email', ''),
                'role': user.get('role', 'user'),
                'interests': user.get('interests', []),
                'is_active': user.get('is_active', True),
                'created_at': user.get('created_at', datetime.utcnow())
            }
            return user_data
        else:
            print(f"Invalid password for user: {username}")
            return None
            
    except Exception as e:
        print(f"Error in verify_user: {str(e)}")
        return None

def create_user(username: str, email: str, password: str, role: str = 'user', interests: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Create a new user with hashed password and optional interests.
    
    Args:
        username: Unique username
        email: User's email
        password: Plain text password
        role: User role (default: 'user')
        interests: List of domain interests (default: [])
        
    Returns:
        tuple: (user_id, error_message) - user_id is None if creation failed
    """
    try:
        # Check if username or email already exists
        if users_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
            return None, "Username or email already exists"
            
        # Validate interests if provided
        if interests:
            invalid_interests = [i for i in interests if i not in AVAILABLE_DOMAINS]
            if invalid_interests:
                return None, f"Invalid interests: {', '.join(invalid_interests)}. Must be one of: {', '.join(AVAILABLE_DOMAINS)}"
        
        # Hash the password
        password_bytes = password.encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        
        # Create user document
        user = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "role": role,
            "interests": interests if interests else [],
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        }
        
        # Insert into database
        result = users_collection.insert_one(user)
        print(f"User created: {username}")
        return str(result.inserted_id), None
        
    except DuplicateKeyError:
        return None, "Username or email already exists"
    except Exception as e:
        print(f"Error creating user {username}: {str(e)}")
        return None, str(e)

def log_search(user_id: str, query: str, results_count: int, articles: list = None):
    """Log a search query with optional article details.
    
    Args:
        user_id: ID of the user who performed the search
        query: Search query
        results_count: Number of results returned
        articles: List of article dictionaries with full details (optional)
    """
    try:
        search_log = {
            "user_id": user_id,
            "query": query,
            "results_count": results_count,
            "timestamp": datetime.utcnow(),
            "articles": []
        }
        
        # Add article details if provided
        if articles:
            # Clean up articles to store only necessary fields and make them JSON serializable
            for article in articles:
                # Create a clean article object with only the fields we want to store
                clean_article = {
                    'title': article.get('title', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', ''),
                    'publish_date': article.get('publish_date', ''),
                    'summary': article.get('summary', ''),
                    'content': article.get('content', ''),
                    'sentiment': article.get('sentiment', {})
                }
                # Convert datetime objects to string if they exist
                if 'publish_date' in article and hasattr(article['publish_date'], 'isoformat'):
                    clean_article['publish_date'] = article['publish_date'].isoformat()
                
                search_log['articles'].append(clean_article)
        
        search_history_collection.insert_one(search_log)
        return True
    except Exception as e:
        print(f"Error logging search: {str(e)}")
        return False

def get_search_history(user_id: str, limit: int = 10):
    """Retrieve search history for a user.
    
    Args:
        user_id: ID of the user
        limit: Maximum number of history entries to return
        
    Returns:
        list: List of search history entries, most recent first
    """
    try:
        return list(search_history_collection
                  .find({"user_id": user_id})
                  .sort("timestamp", -1)
                  .limit(limit))
    except Exception as e:
        print(f"Error fetching search history: {str(e)}")
        return []

def create_admin_user():
    """Create an admin user if one doesn't exist."""
    try:
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        
        # Check if admin user already exists
        if not users_collection.find_one({"username": admin_username}):
            user_id, error = create_user(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                role='admin',
                interests=['Technology', 'Business']  # Default interests for admin
            )
            if user_id:
                print(f"Admin user created with username: {admin_username}")
            else:
                print(f"Failed to create admin user: {error}")
        else:
            print("Admin user already exists")
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")

# RSS Feed Management
def add_rss_feed(url: str, is_active: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """Add a new RSS feed to the database.
    
    Args:
        url: URL of the RSS feed
        is_active: Whether the feed should be active
        
    Returns:
        tuple: (feed_id, error_message) - feed_id is None if creation failed
    """
    try:
        # Clean and validate URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            return None, "Invalid URL. Must start with http:// or https://"
            
        # Check if URL already exists
        if rss_feeds_collection.find_one({"url": url}):
            return None, "This RSS feed URL already exists"
            
        feed = {
            "url": url,
            "is_active": bool(is_active),
            "created_at": datetime.utcnow(),
            "last_checked": None,
            "last_error": None
        }
        
        result = rss_feeds_collection.insert_one(feed)
        return str(result.inserted_id), None
        
    except Exception as e:
        return None, str(e)

def update_rss_feed(feed_id: str, **updates) -> Tuple[bool, Optional[str]]:
    """Update an existing RSS feed.
    
    Args:
        feed_id: ID of the feed to update
        **updates: Fields to update (url, is_active)
        
    Returns:
        tuple: (success, error_message)
    """
    try:
        if not updates:
            return False, "No updates provided"
            
        # Clean up updates
        if 'url' in updates:
            updates['url'] = updates['url'].strip()
            if not updates['url'].startswith(('http://', 'https://')):
                return False, "Invalid URL. Must start with http:// or https://"
                
            # Check if URL is already used by another feed
            existing = rss_feeds_collection.find_one({
                "url": updates['url'],
                "_id": {"$ne": ObjectId(feed_id)}
            })
            if existing:
                return False, "This URL is already used by another feed"
            
        result = rss_feeds_collection.update_one(
            {"_id": ObjectId(feed_id)},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            return False, "Feed not found"
            
        return True, None
        
    except Exception as e:
        return False, str(e)

def delete_rss_feed(feed_id: str) -> Tuple[bool, Optional[str]]:
    """Delete an RSS feed.
    
    Args:
        feed_id: ID of the feed to delete
        
    Returns:
        tuple: (success, error_message)
    """
    try:
        result = rss_feeds_collection.delete_one({"_id": ObjectId(feed_id)})
        if result.deleted_count == 0:
            return False, "Feed not found"
        return True, None
    except Exception as e:
        return False, str(e)

def get_rss_feeds(active_only: bool = False) -> List[Dict[str, Any]]:
    """Get all RSS feeds.
    
    Args:
        active_only: If True, return only active feeds
        
    Returns:
        list: List of feed dictionaries with URL and active status
    """
    try:
        query = {"is_active": True} if active_only else {}
        feeds = list(rss_feeds_collection.find(query, {"url": 1, "is_active": 1, "_id": 1}))
        
        # Convert ObjectId to string for JSON serialization
        for feed in feeds:
            feed['_id'] = str(feed['_id'])
            
        return feeds
    except Exception as e:
        print(f"Error getting RSS feeds: {str(e)}")
        return []

# Create admin user on module import
create_admin_user()
