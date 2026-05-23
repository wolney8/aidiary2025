#!/usr/bin/env python3
"""
Database verification script for title migration
Checks database integrity before and after migration
"""

import sqlite3
import sys
from datetime import datetime

def verify_database(db_path="app.db"):
    """Verify database structure and data integrity."""
    
    print(f"🔍 Verifying database: {db_path}")
    print(f"📅 Verification time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if database can be opened
        print("✅ Database connection: OK")
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📋 Tables found: {', '.join(tables)}")
        
        # Check dailydiary_entries structure
        cursor.execute("PRAGMA table_info(dailydiary_entries);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        print(f"📊 dailydiary_entries columns: {', '.join(column_names)}")
        
        # Check if title column exists
        has_title = 'title' in column_names
        print(f"🏷️  Title column exists: {'✅ YES' if has_title else '❌ NO'}")
        
        # Count entries
        cursor.execute("SELECT COUNT(*) FROM dailydiary_entries;")
        daily_count = cursor.fetchone()[0]
        print(f"📝 Daily entries count: {daily_count}")
        
        cursor.execute("SELECT COUNT(*) FROM dreamdiary_entries;")
        dream_count = cursor.fetchone()[0]
        print(f"🌙 Dream entries count: {dream_count}")
        
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]
        print(f"👥 Users count: {user_count}")
        
        # Sample some daily entries to check data integrity
        cursor.execute("SELECT id, entry_date, user_message FROM dailydiary_entries LIMIT 3;")
        samples = cursor.fetchall()
        print("\n📄 Sample entries:")
        for sample in samples:
            entry_id, date, message = sample
            message_preview = (message[:50] + '...') if message and len(message) > 50 else message
            print(f"   ID {entry_id} ({date}): {message_preview}")
        
        conn.close()
        print("\n✅ Database verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    verify_database(db_path)