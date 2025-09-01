from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
print(f"Connecting to MongoDB at: {MONGODB_URI}")

client = MongoClient(MONGODB_URI)
db = client['news_scraper_db']

# List all collections
collections = db.list_collection_names()
print("\nCollections in database:", collections)

# Check search_history collection
if 'search_history' in collections:
    search_history = db['search_history']
    count = search_history.count_documents({})
    print(f"\nTotal documents in search_history: {count}")
    
    # Get one document to check its structure
    if count > 0:
        doc = search_history.find_one()
        print("\nSample document structure:")
        for key, value in doc.items():
            print(f"{key}: {type(value).__name__}")
            
        # Check for indexes
        indexes = list(search_history.index_information())
        print("\nIndexes:", indexes)
    else:
        print("No documents found in search_history collection")
else:
    print("\nsearch_history collection does not exist")
