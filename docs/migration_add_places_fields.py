#!/usr/bin/env python3
"""
Database migration script to add places fields to existing entries tables.
This adds daily_places and dream_places columns for storing extracted location data.
"""
import sqlite3
import os

def migrate_database():
    """Add places fields to existing database tables."""
    
    # Get database path
    db_path = os.getenv('DB_PATH', './server/db/app.db')
    if not os.path.exists(db_path):
        # Try alternative path
        db_path = './app.db'
    
    print(f"Migrating database at: {db_path}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Check if columns already exist
        c.execute("PRAGMA table_info(dailydiary_entries)")
        daily_columns = [column[1] for column in c.fetchall()]
        
        c.execute("PRAGMA table_info(dreamdiary_entries)")
        dream_columns = [column[1] for column in c.fetchall()]
        
        # Add daily_places column if it doesn't exist
        if 'daily_places' not in daily_columns:
            print("Adding daily_places column to dailydiary_entries table...")
            c.execute('ALTER TABLE dailydiary_entries ADD COLUMN daily_places TEXT')
            print("✓ Added daily_places column")
        else:
            print("daily_places column already exists")
            
        # Add dream_places column if it doesn't exist
        if 'dream_places' not in dream_columns:
            print("Adding dream_places column to dreamdiary_entries table...")
            c.execute('ALTER TABLE dreamdiary_entries ADD COLUMN dream_places TEXT')
            print("✓ Added dream_places column")
        else:
            print("dream_places column already exists")
            
        # Commit changes
        conn.commit()
        print("✓ Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    finally:
        if conn:
            conn.close()
            
    return True

if __name__ == "__main__":
    migrate_database()