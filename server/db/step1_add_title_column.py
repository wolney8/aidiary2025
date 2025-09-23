#!/usr/bin/env python3
"""
Step 1: Add title column to dailydiary_entries table
Safe, non-breaking database schema modification
"""

import sqlite3
import sys
from datetime import datetime

def add_title_column(db_path="app.db"):
    """Add title column to dailydiary_entries table."""
    
    print(f"🔄 Step 1: Adding title column to database")
    print(f"📅 Migration time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🗄️  Database: {db_path}")
    print("=" * 50)
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if title column already exists
        cursor.execute("PRAGMA table_info(dailydiary_entries);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'title' in column_names:
            print("⚠️  Title column already exists! Skipping migration.")
            conn.close()
            return True
        
        print(f"📊 Current columns: {', '.join(column_names)}")
        
        # Add title column (allowing NULL values for existing entries)
        print("➕ Adding title column...")
        cursor.execute("ALTER TABLE dailydiary_entries ADD COLUMN title TEXT;")
        
        # Commit the change
        conn.commit()
        print("✅ Title column added successfully!")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(dailydiary_entries);")
        new_columns = cursor.fetchall()
        new_column_names = [col[1] for col in new_columns]
        
        if 'title' in new_column_names:
            print("✅ Verification: Title column exists!")
            print(f"📊 Updated columns: {', '.join(new_column_names)}")
        else:
            print("❌ Verification failed: Title column not found!")
            conn.close()
            return False
        
        # Check that existing data is intact
        cursor.execute("SELECT COUNT(*) FROM dailydiary_entries;")
        entry_count = cursor.fetchone()[0]
        print(f"📝 Entry count after migration: {entry_count}")
        
        # Sample a few entries to ensure data integrity
        cursor.execute("SELECT id, entry_date, user_message, title FROM dailydiary_entries LIMIT 3;")
        samples = cursor.fetchall()
        print("\n📄 Sample entries after migration:")
        for sample in samples:
            entry_id, date, message, title = sample
            message_preview = (message[:30] + '...') if message and len(message) > 30 else message
            title_status = title if title else "(NULL - as expected)"
            print(f"   ID {entry_id} ({date}): Title='{title_status}', Message='{message_preview}'")
        
        conn.close()
        print("\n✅ Step 1 completed successfully!")
        print("📋 Next: Run verification script to confirm database integrity")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    success = add_title_column(db_path)
    sys.exit(0 if success else 1)