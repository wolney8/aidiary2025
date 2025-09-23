#!/usr/bin/env python3
"""
Step 3: Update API endpoints to handle title field
Update entry creation, retrieval, and update endpoints
"""

import os
import sys
from datetime import datetime

def create_step3_backup():
    """Create backup of routes file before modification."""
    
    routes_file = "/Users/will_work/Scripts/PythonScripts/aidiary2025/aidiary2025/server/routes/entries.py"
    backup_file = f"{routes_file}.backup_step3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        with open(routes_file, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        
        print(f"✅ Created backup: {os.path.basename(backup_file)}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create backup: {str(e)}")
        return False

def main():
    """Step 3 preparation and backup."""
    
    print("🔄 Step 3: Preparing to update API endpoints")
    print(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    print("📋 Step 3 will update:")
    print("   - GET /daily: Include title in returned data")
    print("   - GET /daily/<id>: Include title in returned data") 
    print("   - POST /daily: Accept title in request data")
    print("   - PUT /daily/<id>: Allow title updates")
    print("   - All endpoints: Handle title field properly")
    
    print("\n🛡️ Creating backup of routes file...")
    if create_step3_backup():
        print("✅ Backup created successfully!")
        print("\n🚀 Ready to proceed with API updates")
        return True
    else:
        print("❌ Backup failed. Aborting Step 3.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)