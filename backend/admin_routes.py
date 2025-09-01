from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from models import users_collection, rss_feeds_collection, search_history_collection

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGODB_URI)
db = client['news_scraper_db']

# Helper function to verify admin access
async def get_current_admin(token: str = Depends(oauth2_scheme)):
    from auth import SECRET_KEY, ALGORITHM
    import jwt
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Get user from database
        user = users_collection.find_one({"username": username})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Check if user is admin
        if user.get('role') != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
            
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error authenticating user"
        )

# User Management Endpoints
@router.get("/users/")
async def get_users(
    skip: int = 0, 
    limit: int = 100,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all users (admin only)"""
    users = []
    for user in users_collection.find().skip(skip).limit(limit):
        user["_id"] = str(user["_id"])
        users.append(user)
    return users

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"
    interests: List[str] = []
    is_active: bool = True

@router.post("/users/", response_model=Dict[str, Any])
async def create_user(
    user_data: UserCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new user (admin only)"""
    # Check if user already exists
    if users_collection.find_one({"$or": [{"username": user_data.username}, {"email": user_data.email}]}):
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Hash password (in a real app, use proper password hashing)
    hashed_password = f"hashed_{user_data.password}"  # Replace with proper hashing
    
    # Create user
    user = {
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": hashed_password,
        "role": user_data.role,
        "interests": user_data.interests,
        "is_active": user_data.is_active,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = users_collection.insert_one(user)
    user["_id"] = str(result.inserted_id)
    return user

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    interests: Optional[List[str]] = None
    is_active: Optional[bool] = None

@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update a user (admin only)"""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
        
    # Get existing user
    existing_user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {"updated_at": datetime.utcnow()}
    
    if user_data.username is not None:
        # Check if username is already taken by another user
        existing = users_collection.find_one({
            "username": user_data.username, 
            "_id": {"$ne": ObjectId(user_id)}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        update_data["username"] = user_data.username
    
    if user_data.email is not None:
        # Check if email is already registered by another user
        existing = users_collection.find_one({
            "email": user_data.email, 
            "_id": {"$ne": ObjectId(user_id)}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        update_data["email"] = user_data.email
    
    if user_data.password is not None:
        # Hash the new password (in a real app, use proper password hashing)
        update_data["hashed_password"] = f"hashed_{user_data.password}"
    
    if user_data.role is not None:
        update_data["role"] = user_data.role
    
    if user_data.interests is not None:
        update_data["interests"] = user_data.interests
        
    if user_data.is_active is not None:
        update_data["is_active"] = user_data.is_active
    
    # Update the user
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return the updated user
    updated_user = users_collection.find_one({"_id": ObjectId(user_id)})
    updated_user["_id"] = str(updated_user["_id"])
    return updated_user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a user (admin only)"""
    # Don't allow deleting the admin user
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("username") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete the admin user")
    
    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}

# RSS Feed Models
class RSSFeedBase(BaseModel):
    url: str
    name: Optional[str] = None
    is_active: bool = True
    fetch_interval: int = 3600  # Default to 1 hour
    last_fetched: Optional[datetime] = None
    last_error: Optional[str] = None

class RSSFeedCreate(RSSFeedBase):
    pass

class RSSFeedUpdate(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    fetch_interval: Optional[int] = None
    last_error: Optional[str] = None

# RSS Feed Management Endpoints
@router.get("/rss/feeds", response_model=List[Dict[str, Any]])
async def get_rss_feeds(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all RSS feeds (admin only)"""
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    
    feeds = []
    for feed in rss_feeds_collection.find(query).skip(skip).limit(limit):
        feed["_id"] = str(feed["_id"])
        feeds.append(feed)
    
    return feeds

@router.post("/rss/feeds", response_model=Dict[str, Any])
async def add_rss_feed(
    feed_data: RSSFeedCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Add a new RSS feed (admin only)"""
    # Check if feed already exists
    if rss_feeds_collection.find_one({"url": feed_data.url}):
        raise HTTPException(status_code=400, detail="RSS feed with this URL already exists")
    
    feed = {
        "url": feed_data.url,
        "name": feed_data.name or feed_data.url,
        "is_active": feed_data.is_active,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_fetched": feed_data.last_fetched,
        "fetch_interval": feed_data.fetch_interval,
        "last_error": feed_data.last_error
    }
    
    result = rss_feeds_collection.insert_one(feed)
    feed["_id"] = str(result.inserted_id)
    return feed

@router.put("/rss/feeds/{feed_id}", response_model=Dict[str, Any])
async def update_rss_feed(
    feed_id: str,
    feed_data: RSSFeedUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update an RSS feed (admin only)"""
    if not ObjectId.is_valid(feed_id):
        raise HTTPException(status_code=400, detail="Invalid feed ID format")
    
    # Get existing feed
    existing_feed = rss_feeds_collection.find_one({"_id": ObjectId(feed_id)})
    if not existing_feed:
        raise HTTPException(status_code=404, detail="RSS feed not found")
    
    update_data = {"updated_at": datetime.utcnow()}
    
    # Update fields if provided in the request
    if feed_data.url is not None:
        # Check if URL is already used by another feed
        existing = rss_feeds_collection.find_one({
            "url": feed_data.url, 
            "_id": {"$ne": ObjectId(feed_id)}
        })
        if existing:
            raise HTTPException(status_code=400, detail="URL already in use by another feed")
        update_data["url"] = feed_data.url
    
    if feed_data.name is not None:
        update_data["name"] = feed_data.name
    
    if feed_data.is_active is not None:
        update_data["is_active"] = feed_data.is_active
    
    if feed_data.fetch_interval is not None:
        update_data["fetch_interval"] = feed_data.fetch_interval
    
    if feed_data.last_error is not None:
        update_data["last_error"] = feed_data.last_error
    
    # Update the feed in the database
    result = rss_feeds_collection.update_one(
        {"_id": ObjectId(feed_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="RSS feed not found")
    
    # Return the updated feed
    feed = rss_feeds_collection.find_one({"_id": ObjectId(feed_id)})
    feed["_id"] = str(feed["_id"])
    return feed

@router.delete("/rss/feeds/{feed_id}", response_model=Dict[str, str])
async def delete_rss_feed(
    feed_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete an RSS feed (admin only)"""
    if not ObjectId.is_valid(feed_id):
        raise HTTPException(status_code=400, detail="Invalid feed ID format")
    
    result = rss_feeds_collection.delete_one({"_id": ObjectId(feed_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="RSS feed not found")
    
    return {"message": "RSS feed deleted successfully"}

class RefreshRSSResponse(BaseModel):
    message: str
    feeds_updated: int
    feeds_failed: int = 0
    errors: Optional[Dict[str, str]] = None

@router.post("/rss/refresh", response_model=RefreshRSSResponse)
async def refresh_rss_feeds(
    feed_id: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Refresh RSS feeds (admin only)
    
    - If feed_id is provided, only refresh that specific feed
    - If no feed_id is provided, refresh all active feeds
    """
    from feedparser import parse as feedparser_parse
    import feedparser
    
    # Set a custom user agent to avoid being blocked
    feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    updated_count = 0
    failed_count = 0
    errors = {}
    
    try:
        if feed_id:
            # Refresh a single feed
            if not ObjectId.is_valid(feed_id):
                raise HTTPException(status_code=400, detail="Invalid feed ID format")
                
            feed = rss_feeds_collection.find_one({"_id": ObjectId(feed_id)})
            if not feed:
                raise HTTPException(status_code=404, detail="RSS feed not found")
                
            # Parse the feed
            parsed_feed = feedparser_parse(feed['url'])
            
            if parsed_feed.bozo:  # Check for parsing errors
                error_msg = str(parsed_feed.bozo_exception)
                errors[feed_id] = f"Error parsing feed: {error_msg}"
                # Update the feed with the error
                rss_feeds_collection.update_one(
                    {"_id": ObjectId(feed_id)},
                    {
                        "$set": {
                            "last_error": error_msg,
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
                failed_count += 1
            else:
                # Update the feed with success status
                rss_feeds_collection.update_one(
                    {"_id": ObjectId(feed_id)},
                    {
                        "$set": {
                            "last_fetched": datetime.utcnow(),
                            "last_error": None,
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
                updated_count += 1
        else:
            # Refresh all active feeds
            active_feeds = rss_feeds_collection.find({"is_active": True})
            
            for feed in active_feeds:
                feed_id = str(feed['_id'])
                try:
                    # Parse the feed
                    parsed_feed = feedparser_parse(feed['url'])
                    
                    if parsed_feed.bozo:  # Check for parsing errors
                        error_msg = str(parsed_feed.bozo_exception)
                        errors[feed_id] = f"Error parsing feed: {error_msg}"
                        # Update the feed with the error
                        rss_feeds_collection.update_one(
                            {"_id": ObjectId(feed_id)},
                            {
                                "$set": {
                                    "last_error": error_msg,
                                    "last_updated": datetime.utcnow()
                                }
                            }
                        )
                        failed_count += 1
                    else:
                        # Update the feed with success status
                        rss_feeds_collection.update_one(
                            {"_id": ObjectId(feed_id)},
                            {
                                "$set": {
                                    "last_fetched": datetime.utcnow(),
                                    "last_error": None,
                                    "last_updated": datetime.utcnow()
                                }
                            }
                        )
                        updated_count += 1
                        
                except Exception as e:
                    errors[feed_id] = str(e)
                    failed_count += 1
        
        return {
            "message": "RSS feeds refresh completed",
            "feeds_updated": updated_count,
            "feeds_failed": failed_count,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing RSS feeds: {str(e)}"
        )

# Search History Endpoints
@router.get("/search/history")
async def get_search_history(
    skip: int = 0,
    limit: int = 100,
    query: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get search history (admin only)"""
    search_query = {}
    
    if query:
        search_query["query"] = {"$regex": query, "$options": "i"}
    
    if user_id:
        search_query["user_id"] = user_id
    
    if start_date or end_date:
        date_query = {}
        try:
            if start_date:
                # Parse the date string and convert to datetime
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                date_query["$gte"] = start_dt
            if end_date:
                # Parse the date string and convert to datetime, add one day to include the entire end date
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt + timedelta(days=1)
                date_query["$lt"] = end_dt
            search_query["timestamp"] = date_query
        except ValueError as e:
            # If date parsing fails, log the error but don't filter by date
            print(f"Date parsing error: {e}. Dates: start_date={start_date}, end_date={end_date}")
            # Continue without date filtering
    
    # Get total count for pagination
    total = search_history_collection.count_documents(search_query)
    
    # Get all users first for efficient lookups
    all_users = {}
    for user in users_collection.find({}):
        all_users[str(user['_id'])] = {
            'username': user.get('username', 'Unknown User'),
            'role': user.get('role', 'user')
        }
    
    # Get paginated results
    history = []
    for item in search_history_collection.find(search_query).sort("timestamp", -1).skip(skip).limit(limit):
        user_id = str(item.get("user_id", ""))
        
        # Debug logging
        print(f"Processing search history item: {item.get('_id')}")
        print(f"User ID: {user_id}")
        print(f"Item data: {item}")
        
        # Get username from the item first
        username = item.get("username")
        print(f"Username from item: {username}")
        
        # If username not found in item, try to get it from users collection
        if not username:
            print("Username not found in item, checking users collection...")
            if user_id == "admin":
                username = "admin"
            elif user_id in all_users:
                user_data = all_users[user_id]
                username = user_data.get('username', 'Unknown User')
                print(f"Found user in all_users: {username}")
            else:
                print(f"User ID {user_id} not found in all_users")
                username = "Unknown User"
        
        # Prepare user info
        user_info = None
        if user_id == "admin":
            user_info = {"username": "admin", "role": "admin"}
        elif user_id in all_users:
            user_data = all_users[user_id]
            user_info = {
                "username": user_data.get('username', 'Unknown User'),
                "role": user_data.get('role', 'user')
            }
        else:
            # If user not found, create a basic user info with the username we have
            user_info = {"username": username, "role": "user"}
            
        print(f"Final username: {username}")
        print(f"Final user_info: {user_info}")
        
        # Transform the item to match frontend expectations
        transformed_item = {
            "_id": str(item["_id"]),
            "query": item.get("query", ""),
            "userId": user_id,
            "username": username,
            "user": user_info or {"username": username, "role": "user" if user_id != "admin" else "admin"},
            "timestamp": item.get("timestamp"),
            "results": item.get("articles", []),
            "results_count": item.get("results_count", 0),
            "articles": item.get("articles", [])
        }
        history.append(transformed_item)
    
    return {
        "data": history,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.delete("/search/history/{history_id}")
async def delete_search_history(
    history_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a specific search history item (admin only)"""
    try:
        # Validate ObjectId
        from bson import ObjectId
        if not ObjectId.is_valid(history_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid history ID format"
            )
        
        # Check if the item exists
        item = search_history_collection.find_one({"_id": ObjectId(history_id)})
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Search history item not found"
            )
        
        # Delete the item
        result = search_history_collection.delete_one({"_id": ObjectId(history_id)})
        
        if result.deleted_count == 1:
            return {"message": "Search history item deleted successfully"}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete search history item"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting search history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.delete("/search/history")
async def delete_multiple_search_history(
    history_ids: List[str],
    current_admin: dict = Depends(get_current_admin)
):
    """Delete multiple search history items (admin only)"""
    try:
        from bson import ObjectId
        
        # Validate all ObjectIds
        valid_ids = []
        for history_id in history_ids:
            if ObjectId.is_valid(history_id):
                valid_ids.append(ObjectId(history_id))
            else:
                logger.warning(f"Invalid ObjectId format: {history_id}")
        
        if not valid_ids:
            raise HTTPException(
                status_code=400,
                detail="No valid history IDs provided"
            )
        
        # Delete the items
        result = search_history_collection.delete_many({"_id": {"$in": valid_ids}})
        
        return {
            "message": f"Successfully deleted {result.deleted_count} search history items",
            "deleted_count": result.deleted_count
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting multiple search history items: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/search/analytics")
async def get_search_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get search analytics (admin only)"""
    match_query = {}
    
    if start_date or end_date:
        date_query = {}
        try:
            if start_date:
                # Parse the date string and convert to datetime
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                date_query["$gte"] = start_dt
            if end_date:
                # Parse the date string and convert to datetime, add one day to include the entire end date
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt + timedelta(days=1)
                date_query["$lt"] = end_dt
            match_query["timestamp"] = date_query
        except ValueError as e:
            # If date parsing fails, log the error but don't filter by date
            print(f"Date parsing error: {e}. Dates: start_date={start_date}, end_date={end_date}")
            # Continue without date filtering
    
    # Get total searches
    total_searches = search_history_collection.count_documents(match_query)
    
    # Get searches by day
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$timestamp"
                }
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    searches_by_day = list(search_history_collection.aggregate(pipeline))
    
    # Get top queries
    top_queries = list(search_history_collection.aggregate([
        {"$match": match_query},
        {"$group": {
            "_id": {"$toLower": "$query"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]))
    
    return {
        "total_searches": total_searches,
        "searches_by_day": searches_by_day,
        "top_queries": top_queries
    }
