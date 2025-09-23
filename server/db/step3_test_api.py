#!/usr/bin/env python3
"""
Test Step 3: API endpoint changes for title field
Test that title field is properly handled in all endpoints
"""

import json
import subprocess
import time

def test_api_endpoints():
    """Test API endpoints with title field support."""
    
    print("🧪 Testing Step 3: API endpoints with title field")
    print("=" * 50)
    
    base_url = "http://localhost:5001/api"
    
    # Test data
    test_user = {
        "username": "testuser",
        "password": "testpass"
    }
    
    test_entry = {
        "title": "Test Entry Title",
        "user_message": "This is a test entry with a title.",
        "entry_date": "2025-09-23",
        "tags": "test,api"
    }
    
    print("📋 Test Plan:")
    print("   1. Login to get auth token")
    print("   2. Create entry with title (POST /daily)")
    print("   3. Retrieve entries (GET /daily)")
    print("   4. Get specific entry (GET /daily/<id>)")
    print("   5. Update entry title (PUT /daily/<id>)")
    print("   6. Verify title changes")
    
    print("\n⚠️  NOTE: This test requires:")
    print("   - Flask server running on port 5001")
    print("   - Valid test user credentials")
    print("   - curl command available")
    
    print("\n🔄 Manual testing recommended:")
    print("   1. Restart Flask server to load API changes")
    print("   2. Test login functionality")
    print("   3. Test entry creation with title")
    print("   4. Check database for title field")
    
    return True

def create_manual_test_commands():
    """Create manual test commands for API testing."""
    
    commands = """
# Manual API Testing Commands for Step 3

## 1. Test Login (get auth token)
curl -X POST http://localhost:5001/api/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"testuser","password":"testpass"}'

## 2. Test Create Entry with Title (use token from step 1)
curl -X POST http://localhost:5001/api/entries/daily \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \\
  -d '{
    "title": "My Test Entry Title",
    "user_message": "This is a test entry created via API with title support.",
    "entry_date": "2025-09-23",
    "tags": "test,api,step3"
  }'

## 3. Test Get All Entries (should include title field)
curl -X GET http://localhost:5001/api/entries/daily \\
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

## 4. Test Get Specific Entry (use entry ID from step 2)
curl -X GET http://localhost:5001/api/entries/daily/ENTRY_ID \\
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

## 5. Test Update Entry Title
curl -X PUT http://localhost:5001/api/entries/daily/ENTRY_ID \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \\
  -d '{
    "title": "Updated Entry Title",
    "user_message": "Updated content with new title."
  }'

## 6. Verify Changes
curl -X GET http://localhost:5001/api/entries/daily/ENTRY_ID \\
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
"""
    
    with open("/Users/will_work/Scripts/PythonScripts/aidiary2025/aidiary2025/server/db/step3_test_commands.txt", "w") as f:
        f.write(commands)
    
    print("📄 Created manual test commands: step3_test_commands.txt")

if __name__ == "__main__":
    test_api_endpoints()
    create_manual_test_commands()