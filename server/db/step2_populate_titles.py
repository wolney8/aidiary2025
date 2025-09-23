#!/usr/bin/env python3
"""
Step 2: Populate title column for existing daily diary entries
Generate date-based titles like "Entry for October 7, 2024"
"""

import sqlite3
import sys
from datetime import datetime

def format_date_title(date_str):
    """Convert date string to readable title format."""
    try:
        # Parse the date (assuming YYYY-MM-DD format)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Format as "Entry for Month Day, Year"
        formatted_date = date_obj.strftime('%B %d, %Y')
        return f"Entry for {formatted_date}"
        
    except Exception as e:
        # Fallback for any date parsing issues
        return f"Entry for {date_str}"

def populate_titles(db_path="app.db", test_mode=False):
    """Populate title column for existing entries."""
    
    print(f"🔄 Step 2: Populating titles for existing entries")
    print(f"📅 Migration time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🗄️  Database: {db_path}")
    print(f"🧪 Test mode: {'ON' if test_mode else 'OFF'}")
    print("=" * 60)
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check that title column exists
        cursor.execute("PRAGMA table_info(dailydiary_entries);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'title' not in column_names:
            print("❌ Error: Title column does not exist! Run Step 1 first.")
            conn.close()
            return False
        
        # Get entries without titles (NULL or empty)
        cursor.execute("""
            SELECT id, entry_date, user_message 
            FROM dailydiary_entries 
            WHERE title IS NULL OR title = ''
            ORDER BY entry_date DESC
        """)
        
        entries_to_update = cursor.fetchall()
        total_entries = len(entries_to_update)
        
        print(f"📊 Found {total_entries} entries without titles")
        
        if total_entries == 0:
            print("✅ All entries already have titles! Nothing to do.")
            conn.close()
            return True
        
        # Show sample of what will be updated
        print("\n📋 Sample entries that will be updated:")
        for i, (entry_id, date, message) in enumerate(entries_to_update[:5]):
            title = format_date_title(str(date))
            message_preview = (message[:40] + '...') if message and len(message) > 40 else message
            print(f"   ID {entry_id}: '{title}' | {message_preview}")
        
        if total_entries > 5:
            print(f"   ... and {total_entries - 5} more entries")
        
        # In test mode, only update a few entries
        if test_mode:
            entries_to_update = entries_to_update[:3]
            print(f"\n🧪 TEST MODE: Only updating first {len(entries_to_update)} entries")
        
        # Ask for confirmation if not in test mode
        if not test_mode and total_entries > 10:
            print(f"\n⚠️  About to update {total_entries} entries. This will:")
            print("   - Add date-based titles to all entries without titles")
            print("   - NOT modify existing user_message content")
            print("   - NOT affect entries that already have titles")
            
        # Update entries
        updated_count = 0
        print(f"\n🔄 Updating titles...")
        
        for entry_id, date, message in entries_to_update:
            title = format_date_title(str(date))
            
            cursor.execute("""
                UPDATE dailydiary_entries 
                SET title = ? 
                WHERE id = ?
            """, (title, entry_id))
            
            updated_count += 1
            
            # Show progress for large updates
            if updated_count % 20 == 0 or updated_count <= 10:
                print(f"   ✅ Updated {updated_count}/{len(entries_to_update)} entries...")
        
        # Commit changes
        conn.commit()
        
        print(f"\n✅ Successfully updated {updated_count} entries!")
        
        # Verify the updates
        cursor.execute("""
            SELECT COUNT(*) FROM dailydiary_entries 
            WHERE title IS NULL OR title = ''
        """)
        remaining_null = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dailydiary_entries")
        total_entries_db = cursor.fetchone()[0]
        
        print(f"📊 Verification:")
        print(f"   Total entries in database: {total_entries_db}")
        print(f"   Entries without titles: {remaining_null}")
        print(f"   Entries with titles: {total_entries_db - remaining_null}")
        
        # Show sample of updated entries
        cursor.execute("""
            SELECT id, entry_date, title, user_message 
            FROM dailydiary_entries 
            WHERE title IS NOT NULL AND title != ''
            ORDER BY entry_date DESC 
            LIMIT 3
        """)
        
        sample_updated = cursor.fetchall()
        print(f"\n📄 Sample updated entries:")
        for entry_id, date, title, message in sample_updated:
            message_preview = (message[:30] + '...') if message and len(message) > 30 else message
            print(f"   ID {entry_id} ({date}): '{title}' | {message_preview}")
        
        conn.close()
        
        if test_mode:
            print(f"\n🧪 TEST MODE COMPLETED - Only {updated_count} entries updated for testing")
        else:
            print(f"\n✅ Step 2 completed successfully!")
        
        print("📋 Next: Run verification script to confirm database integrity")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    # Parse command line arguments
    db_path = "app.db"
    test_mode = False
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            test_mode = True
        else:
            db_path = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == "--test":
        test_mode = True
    
    success = populate_titles(db_path, test_mode)
    sys.exit(0 if success else 1)