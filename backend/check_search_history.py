from pymongo import MongoClient
from pprint import pprint
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URI)
db = client['news_scraper_db']
search_history = db['search_history']

# Get the latest 5 search history entries
print("Latest 5 search history entries:")
for doc in search_history.find().sort("timestamp", -1).limit(5):
    print("-" * 50)
    print(f"ID: {doc.get('_id')}")
    print(f"User ID: {doc.get('user_id')}")
    print(f"Query: {doc.get('query')}")
    print(f"Timestamp: {doc.get('timestamp')}")
    print(f"Results count: {doc.get('results_count', 0)}")
    print(f"Articles: {len(doc.get('articles', []))} articles")
    print("-" * 50)
    print()

# Print the count of documents in the collection
print(f"\nTotal documents in search_history: {search_history.count_documents({})}")
