#!/usr/bin/env python3
"""
Debug script to examine search history entries structure
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_search_history():
    """Debug search history entries structure"""
    
    try:
        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            print("❌ MONGODB_URI not found in environment variables")
            return
        
        db_name = "news_scraper_db"
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        print(f"🔗 Connected to database: {db_name}")
        
        # List all collections
        collections = db.list_collection_names()
        print(f"📚 Collections in database: {collections}")
        print()
        
        # Check if search_history collection exists
        if 'search_history' in collections:
            search_history_collection = db.search_history
            print("✅ Found search_history collection")
            
            # Get all entries
            all_entries = list(search_history_collection.find({}))
            print(f"📊 Total entries in search_history: {len(all_entries)}")
            
            if all_entries:
                print()
                for i, entry in enumerate(all_entries[:3]):  # Show first 3 entries
                    print(f"--- Entry {i+1} ---")
                    print(f"ID: {entry.get('_id')}")
                    print(f"Query: {entry.get('query')}")
                    print(f"User ID: {entry.get('user_id')}")
                    print(f"Results count: {entry.get('results_count')}")
                    
                    articles = entry.get('articles', [])
                    print(f"Articles array length: {len(articles)}")
                    print(f"Articles array type: {type(articles)}")
                    
                    if articles:
                        print(f"First article: {articles[0] if len(articles) > 0 else 'None'}")
                        print(f"Last article: {articles[-1] if len(articles) > 0 else 'None'}")
                    
                    print()
            else:
                print("❌ No entries found in search_history collection")
        else:
            print("❌ search_history collection not found")
            
        # Check other possible collection names
        for collection_name in collections:
            if 'search' in collection_name.lower() or 'history' in collection_name.lower():
                print(f"🔍 Checking collection: {collection_name}")
                collection = db[collection_name]
                count = collection.count_documents({})
                print(f"   Documents: {count}")
                if count > 0:
                    sample = collection.find_one({})
                    print(f"   Sample keys: {list(sample.keys()) if sample else 'None'}")
                print()
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    debug_search_history()
