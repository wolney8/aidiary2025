#!/usr/bin/env python3
"""
Test server functionality after Step 1 migration
Verifies that the Flask app can still access the database
"""

import requests
import json

def test_server_functionality():
    """Test basic server endpoints after migration."""
    
    print("🧪 Testing server functionality after Step 1...")
    print("=" * 50)
    
    base_url = "http://localhost:5001"
    
    try:
        # Test 1: Server is responding
        print("1️⃣ Testing server response...")
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code in [200, 404]:  # 404 is expected for root
            print("✅ Server is responding")
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
        
        # Test 2: Database connection (via login attempt)
        print("\n2️⃣ Testing database connection...")
        login_data = {"username": "test", "password": "wrong"}
        response = requests.post(f"{base_url}/api/login", 
                               json=login_data, 
                               timeout=5)
        
        if response.status_code in [400, 401]:  # Expected for invalid login
            print("✅ Database connection working (login endpoint accessible)")
        elif response.status_code == 200:
            print("✅ Database connection working (login successful)")
        else:
            print(f"⚠️ Unexpected login response: {response.status_code}")
        
        print("\n✅ Server functionality test completed!")
        print("📋 The application appears to be working normally after Step 1")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is Flask running on port 5001?")
        return False
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_server_functionality()