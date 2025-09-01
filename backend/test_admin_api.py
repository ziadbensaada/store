#!/usr/bin/env python3
"""
Test script to verify admin search history API endpoint
"""

import requests
import json

def test_admin_search_history():
    """Test the admin search history endpoint"""
    
    # Test URL (adjust if your backend is running on a different port)
    base_url = "http://127.0.0.1:5000"
    endpoint = f"{base_url}/api/admin/search/history"
    
    # Test headers (you'll need to get a valid admin token)
    headers = {
        "Authorization": "Bearer YOUR_ADMIN_TOKEN_HERE",
        "Content-Type": "application/json"
    }
    
    print("Testing Admin Search History API")
    print("=" * 50)
    print(f"Endpoint: {endpoint}")
    print()
    
    try:
        # Test without authentication first
        print("1. Testing without authentication (should fail):")
        response = requests.get(endpoint)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        print()
        
        # Test with authentication (if you have a token)
        print("2. Testing with authentication:")
        print("   Note: You need to provide a valid admin token in the script")
        print("   To get a token, login as admin in your frontend and check the browser console")
        print()
        
        # If you have a token, uncomment and test:
        # response = requests.get(endpoint, headers=headers)
        # print(f"   Status: {response.status_code}")
        # if response.status_code == 200:
        #     data = response.json()
        #     print(f"   Total results: {data.get('total', 0)}")
        #     print(f"   First result: {json.dumps(data.get('data', [])[0] if data.get('data') else {}, indent=2)}")
        # else:
        #     print(f"   Error: {response.text}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure your backend is running on port 5000")
        print("   Run: python -m uvicorn main:app --reload --host 127.0.0.1 --port 5000")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    print("To test with authentication:")
    print("1. Start your backend server")
    print("2. Login as admin in your frontend")
    print("3. Open browser console and find the admin token")
    print("4. Update the script with the token and run again")

if __name__ == "__main__":
    test_admin_search_history()
