import requests
import json

# Test the search history endpoint
def test_search_history():
    try:
        # Test without authentication first to see the structure
        response = requests.get("http://localhost:5000/api/admin/search/history")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("✅ Endpoint is working but requires authentication (expected)")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_search_history()
