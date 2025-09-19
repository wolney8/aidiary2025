from utils import extract_date_from_filename, move_file
from datetime import datetime
from daily_file_ingestion import ingest_word_doc
import os
from flask import redirect, url_for, session # type: ignore
from app.models.models import User, DailyDiaryEntry, db

DIRECTORY_TO_SCAN = 'dailydiary_auto_ingest/'

def daily_auto_ingest_files():
    if 'username' not in session:
        print("Error: No user logged in. Aborting ingestion.")
        return redirect(url_for('user_controller.login'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        print(f"Error: No user found for username {session['username']}. Aborting ingestion.")
        return
    
    user_id = user.id

    for filename in os.listdir(DIRECTORY_TO_SCAN):
        if filename.endswith('.docx'):
            file_path = os.path.join(DIRECTORY_TO_SCAN, filename)
            
            # Use the utility function to extract date
            entry_date = extract_date_from_filename(filename) or datetime.today().date()

            # Ingest the document
            try:
                ingest_word_doc(user_id, file_path, entry_date)
                print(f">>> [ Daily_auto_ingest.py - daily_auto_ingest_files ] - Pulled in File: {filename}")
                
                # Use the utility function to move the file
                move_file(file_path, 'uploads/')
            except Exception as e:
                print(f">>> [ Daily_auto_ingest.py - daily_auto_ingest_files ] - Error processing {filename}: {e}")

if __name__ == '__main__':
    daily_auto_ingest_files()
