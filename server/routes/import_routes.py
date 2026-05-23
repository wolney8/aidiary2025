"""
Import Routes - Backend API for Excel/CSV import functionality
Handles file upload, validation, processing, and history tracking
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from services.import_service import import_service
import sqlite3
from datetime import datetime
import tempfile
import os

import_bp = Blueprint('import', __name__)

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@import_bp.route('/import/template/<entry_type>', methods=['GET'])
@jwt_required()
def get_import_template(entry_type):
    """Get import template for specified entry type."""
    try:
        if entry_type not in ['daily', 'dream']:
            return jsonify({'error': 'Invalid entry type. Must be daily or dream'}), 400
        
        template = import_service.get_import_template(entry_type)
        return jsonify(template), 200
        
    except Exception as e:
        current_app.logger.error(f"Template generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate template'}), 500

@import_bp.route('/import/validate', methods=['POST'])
@jwt_required()
def validate_import_file():
    """Validate import file without processing."""
    try:
        if 'file' not in request.files:
            return jsonify({'valid': False, 'message': 'No file provided'}), 400
        
        file = request.files['file']
        entry_type = request.form.get('entry_type', 'daily')  # Get entry_type from form data
        
        is_valid, error_message = import_service.validate_file(file)
        
        if not is_valid:
            return jsonify({'valid': False, 'message': error_message}), 400
        
        # Additional validation: try to parse the file
        file.seek(0)  # Reset file pointer
        success, entries_data, parse_error = import_service.parse_import_file(file, entry_type)
        
        if not success:
            return jsonify({'valid': False, 'message': parse_error}), 400
        
        return jsonify({
            'valid': True, 
            'message': f'File is valid. Found {len(entries_data)} entries ready for import.'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"File validation failed: {str(e)}")
        return jsonify({'valid': False, 'message': f'Validation error: {str(e)}'}), 500

@import_bp.route('/import/upload', methods=['POST'])
@jwt_required()
def upload_import_file():
    """Process and import entries from uploaded file."""
    try:
        user_id = get_jwt_identity()
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        entry_type = request.form.get('entry_type', 'daily')
        
        # Validate file
        is_valid, error_message = import_service.validate_file(file)
        if not is_valid:
            return jsonify({'success': False, 'error': error_message}), 400
        
        # Parse file
        file.seek(0)
        success, entries_data, parse_error = import_service.parse_import_file(file, entry_type)
        if not success:
            return jsonify({'success': False, 'error': parse_error}), 400
        
        # Process entries and save to database
        conn = get_db()
        try:
            import_stats = _process_entries(conn, user_id, entries_data, entry_type)
            
            # Record import history
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO import_history 
                (user_id, filename, entries_imported, entries_skipped, import_date, entry_type, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                secure_filename(file.filename),
                import_stats['imported'],
                import_stats['skipped'],
                datetime.utcnow().isoformat(),
                entry_type,
                request.content_length or 0
            ))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'entries_imported': import_stats['imported'],
                'entries_skipped': import_stats['skipped'],
                'errors': import_stats['errors'],
                'warnings': import_stats['warnings']
            }), 200
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
            
    except Exception as e:
        current_app.logger.error(f"Import processing failed: {str(e)}")
        return jsonify({'success': False, 'error': f'Import failed: {str(e)}'}), 500

@import_bp.route('/import/history', methods=['GET'])
@jwt_required()
def get_import_history():
    """Get import history for current user."""
    try:
        user_id = get_jwt_identity()
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, filename, entries_imported, entries_skipped, import_date, entry_type, file_size
                FROM import_history
                WHERE user_id = ?
                ORDER BY import_date DESC
                LIMIT 50
            ''', (user_id,))
            
            imports = cursor.fetchall()
            
            history_data = []
            for imp in imports:
                history_data.append({
                    'id': imp['id'],
                    'filename': imp['filename'],
                    'entries_imported': imp['entries_imported'],
                    'entries_skipped': imp['entries_skipped'],
                    'import_date': imp['import_date'],
                    'entry_type': imp['entry_type'],
                    'file_size': imp['file_size']
                })
            
            return jsonify(history_data), 200
            
        finally:
            conn.close()
            
    except Exception as e:
        current_app.logger.error(f"Import history retrieval failed: {str(e)}")
        return jsonify({'error': 'Failed to retrieve import history'}), 500

def _process_entries(conn, user_id, entries_data, entry_type):
    """Process and save entries to database with duplicate checking."""
    stats = {
        'imported': 0,
        'skipped': 0,
        'errors': [],
        'warnings': []
    }
    
    cursor = conn.cursor()
    
    for entry_data in entries_data:
        try:
            # Check for existing entry on same date
            if entry_type == 'daily':
                cursor.execute('''
                    SELECT id FROM dailydiary_entries 
                    WHERE user_id = ? AND entry_date = ?
                ''', (user_id, entry_data['date']))
                existing = cursor.fetchone()
                
                if existing:
                    stats['skipped'] += 1
                    stats['warnings'].append(f"Skipped duplicate daily entry for {entry_data['date']}")
                    continue
                
                # Create new daily entry
                cursor.execute('''
                    INSERT INTO dailydiary_entries 
                    (user_id, entry_date, user_message, ai_response, daily_people_names, daily_places, tags, import_date, imported)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    entry_data['date'],
                    entry_data['user_message'],
                    entry_data.get('ai_response'),
                    entry_data.get('daily_people_names', ''),
                    entry_data.get('daily_places', ''),
                    entry_data.get('tags', ''),
                    datetime.utcnow().isoformat(),
                    True
                ))
                
            else:  # dream entry
                cursor.execute('''
                    SELECT id FROM dreamdiary_entries 
                    WHERE user_id = ? AND entry_date = ?
                ''', (user_id, entry_data['date']))
                existing = cursor.fetchone()
                
                if existing:
                    stats['skipped'] += 1
                    stats['warnings'].append(f"Skipped duplicate dream entry for {entry_data['date']}")
                    continue
                
                # Create new dream entry
                cursor.execute('''
                    INSERT INTO dreamdiary_entries 
                    (user_id, entry_date, title, cast, location, period, emotion, plot, symbols_and_imagery, insight, action, other, summary, interpretation, image_prompt, image_url, dream_people_names, dream_places, tags, import_date, imported)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    entry_data['date'],
                    entry_data.get('title', ''),
                    entry_data.get('cast', ''),
                    entry_data.get('location', ''),
                    entry_data.get('period', ''),
                    entry_data.get('emotion', ''),
                    entry_data['plot'],
                    entry_data.get('symbols_and_imagery', ''),
                    entry_data.get('insight', ''),
                    entry_data.get('action', ''),
                    entry_data.get('other', ''),
                    entry_data.get('summary', ''),
                    entry_data.get('interpretation', ''),
                    entry_data.get('image_prompt', ''),
                    entry_data.get('image_url', ''),
                    entry_data.get('dream_people_names', ''),
                    entry_data.get('dream_places', ''),
                    entry_data.get('tags', ''),
                    datetime.utcnow().isoformat(),
                    True
                ))
            
            stats['imported'] += 1
            
        except Exception as e:
            stats['errors'].append(f"Failed to import entry for {entry_data.get('date', 'unknown date')}: {str(e)}")
    
    conn.commit()
    return stats