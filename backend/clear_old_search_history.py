#!/usr/bin/env python3
"""
Script to clear old search history entries that only have 10 articles
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def clear_old_search_history():
    """Clear search history entries that only have 10 articles"""
    
    try:
        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            print("❌ MONGODB_URI not found in environment variables")
            return
        
        # Use a default database name
        db_name = "news_scraper_db"
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        print(f"🔗 Connecting to database: {db_name}")
        
        # Get the search history collection
        search_history_collection = db.search_history
        
        print("🔍 Checking search history entries...")
        
        # Find entries that have exactly 10 articles (old limited entries)
        old_entries = list(search_history_collection.find({"articles": {"$size": 10}}))
        
        if not old_entries:
            print("✅ No old limited entries found. All entries should now show full results.")
            return
        
        print(f"📊 Found {len(old_entries)} entries with only 10 articles:")
        for entry in old_entries:
            print(f"   - Query: '{entry.get('query', 'N/A')}' | Articles: {len(entry.get('articles', []))} | Date: {entry.get('timestamp', 'N/A')}")
        
        # Ask for confirmation
        response = input(f"\n❓ Do you want to delete these {len(old_entries)} old entries? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            # Delete the old entries
            result = search_history_collection.delete_many({"articles": {"$size": 10}})
            print(f"✅ Successfully deleted {result.deleted_count} old search history entries")
            print("🔄 New searches will now show all articles instead of just 10")
        else:
            print("❌ Operation cancelled. Old entries remain in database.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    clear_old_search_history()
