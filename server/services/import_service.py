"""
Import Service - Excel/CSV import functionality
Secure bulk import for diary and dream entries with validation
Enhanced NLTK processing for intelligent tag extraction
"""
import os
import tempfile
import re
from werkzeug.utils import secure_filename
from typing import Dict, List, Tuple, Optional, Set
from flask import current_app
from datetime import datetime, timedelta
from collections import Counter

# Try to import optional dependencies
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import nltk
    NLTK_AVAILABLE = True
    
    # Download required NLTK data if available
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        nltk.download('averaged_perceptron_tagger')

    try:
        nltk.data.find('corpora/names')
    except LookupError:
        nltk.download('names')

    try:
        nltk.data.find('chunkers/maxent_ne_chunker')
    except LookupError:
        nltk.download('maxent_ne_chunker')

    try:
        nltk.data.find('corpora/words')
    except LookupError:
        nltk.download('words')
        
except ImportError:
    NLTK_AVAILABLE = False

class ImportService:
    """Service for handling Excel/CSV imports with security validation."""
    
    def __init__(self):
        self.max_file_size = int(os.getenv('MAX_IMPORT_FILE_SIZE', '10485760'))  # 10MB
        self.allowed_extensions = os.getenv('ALLOWED_IMPORT_EXTENSIONS', 'xlsx,xls,csv').split(',')
        self.temp_dir = os.getenv('IMPORT_TEMP_DIR', 'temp/imports')
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def validate_file(self, file) -> Tuple[bool, str]:
        """
        Validate uploaded file for security and format compliance.
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not file:
            return False, "No file provided"
        
        if file.filename == '':
            return False, "No file selected"
        
        # Check file extension
        if not self._allowed_file(file.filename):
            return False, f"File type not allowed. Supported: {', '.join(self.allowed_extensions)}"
        
        # Check file size (if available)
        if hasattr(file, 'content_length') and file.content_length:
            if file.content_length > self.max_file_size:
                return False, f"File too large. Maximum size: {self.max_file_size / 1024 / 1024:.1f}MB"
        
        return True, ""
    
    def _allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def parse_import_file(self, file, entry_type: str = 'daily') -> Tuple[bool, List[Dict], str]:
        """
        Parse Excel/CSV file and extract entry data.
        
        Args:
            file: The uploaded file object
            entry_type: 'daily' or 'dream' - determines expected columns
            
        Returns:
            Tuple[bool, List[Dict], str]: (success, entries_data, error_message)
        """
        if not PANDAS_AVAILABLE:
            return False, [], "Pandas not available. Please install: pip install pandas openpyxl"
            
        try:
            # Secure filename and save temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join(self.temp_dir, filename)
            file.save(temp_path)
            
            # Parse based on file type
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(temp_path)
            else:
                df = pd.read_excel(temp_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            # Validate and transform data
            entries_data = self._transform_dataframe(df, entry_type)
            
            return True, entries_data, ""
            
        except Exception as e:
            # Clean up on error
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return False, [], f"Error parsing file: {str(e)}"
    
    def _transform_dataframe(self, df, entry_type: str) -> List[Dict]:
        """
        Transform DataFrame to entry format with enhanced validation.
        Maps columns by position (not name) since headers are user-friendly.
        
        Args:
            df: Pandas DataFrame from the uploaded file
            entry_type: 'daily' or 'dream' - determines expected columns
        """
        entries = []
        
        # Define expected column count and required positions based on entry type
        if entry_type == 'daily':
            expected_columns = 5
            required_positions = [0, 1]  # Date and Diary Entry are required
            column_mappings = {
                0: 'entry_date',
                1: 'user_message', 
                2: 'ai_response',
                3: 'daily_people_names',
                4: 'tags'
            }
        elif entry_type == 'dream':
            expected_columns = 16
            required_positions = [0, 6]  # Date and Dream Story/Plot are required
            column_mappings = {
                0: 'entry_date',
                1: 'title',
                2: 'cast',
                3: 'location',
                4: 'period',
                5: 'emotion',
                6: 'plot',
                7: 'symbols_and_imagery',
                8: 'insight',
                9: 'action',
                10: 'other',
                11: 'summary',
                12: 'interpretation',
                13: 'image_prompt',
                14: 'image_url',
                15: 'dream_people_names',
                16: 'tags'
            }
        else:
            raise ValueError(f"Unknown entry type: {entry_type}")
        
        # Validate column count
        if len(df.columns) != expected_columns:
            raise ValueError(f"Expected {expected_columns} columns, but found {len(df.columns)}. Please use the original template without modifying headers.")
        
        # Validation tracking
        validation_errors = []
        duplicate_dates = set()
        
        for index, row in df.iterrows():
            try:
                # Check required columns are not empty
                for pos in required_positions:
                    if pd.isna(row.iloc[pos]) or str(row.iloc[pos]).strip() == '':
                        column_name = list(column_mappings.keys())[pos] if pos < len(column_mappings) else f"Column {pos+1}"
                        raise ValueError(f"Required column '{column_name}' is empty")
                
                # Parse and validate entry_date (always position 0)
                entry_date = self._parse_date(str(row.iloc[0]))
                
                # Validate date range
                self._validate_date_range(entry_date, index + 2)
                
                # Check for duplicates within import
                if entry_date in duplicate_dates:
                    validation_errors.append(f"Row {index + 2}: Duplicate entry for {entry_date}")
                duplicate_dates.add(entry_date)
                
                # Build entry data based on type using column positions
                entry = {
                    'date': entry_date,
                    'type': entry_type,
                    'import_row': index + 2  # For error tracking
                }
                
                if entry_type == 'daily':
                    # Map daily columns by position
                    entry.update({
                        'user_message': self._sanitise_content(str(row.iloc[1])),
                        'ai_response': self._sanitise_content(str(row.iloc[2])) if not pd.isna(row.iloc[2]) else None,
                        'daily_people_names': self._sanitise_content(str(row.iloc[3])) if not pd.isna(row.iloc[3]) else '',
                        'tags': self._parse_tags(str(row.iloc[4])) if not pd.isna(row.iloc[4]) else '',
                        'daily_places': self._extract_places(str(row.iloc[1])),  # Auto-extract from user_message
                    })
                    
                elif entry_type == 'dream':
                    # Map dream columns by position
                    entry.update({
                        'title': self._sanitise_content(str(row.iloc[1])) if not pd.isna(row.iloc[1]) else '',
                        'cast': self._sanitise_content(str(row.iloc[2])) if not pd.isna(row.iloc[2]) else '',
                        'location': self._sanitise_content(str(row.iloc[3])) if not pd.isna(row.iloc[3]) else '',
                        'period': self._sanitise_content(str(row.iloc[4])) if not pd.isna(row.iloc[4]) else '',
                        'emotion': self._sanitise_content(str(row.iloc[5])) if not pd.isna(row.iloc[5]) else '',
                        'plot': self._sanitise_content(str(row.iloc[6])),
                        'symbols_and_imagery': self._sanitise_content(str(row.iloc[7])) if not pd.isna(row.iloc[7]) else '',
                        'insight': self._sanitise_content(str(row.iloc[8])) if not pd.isna(row.iloc[8]) else '',
                        'action': self._sanitise_content(str(row.iloc[9])) if not pd.isna(row.iloc[9]) else '',
                        'other': self._sanitise_content(str(row.iloc[10])) if not pd.isna(row.iloc[10]) else '',
                        'summary': self._sanitise_content(str(row.iloc[11])) if not pd.isna(row.iloc[11]) else '',
                        'interpretation': self._sanitise_content(str(row.iloc[12])) if not pd.isna(row.iloc[12]) else '',
                        'image_prompt': self._sanitise_content(str(row.iloc[13])) if not pd.isna(row.iloc[13]) else '',
                        'image_url': self._sanitise_content(str(row.iloc[14])) if not pd.isna(row.iloc[14]) else '',
                        'dream_people_names': self._sanitise_content(str(row.iloc[15])) if not pd.isna(row.iloc[15]) else '',
                        'tags': self._parse_tags(str(row.iloc[16])) if not pd.isna(row.iloc[16]) else '',
                        'dream_places': self._extract_places(str(row.iloc[6])),  # Auto-extract from plot
                    })
                
                entries.append(entry)
                
            except ValueError as e:
                validation_errors.append(f"Row {index + 2}: {str(e)}")
        
        # If we have validation errors, include them in the response
        if validation_errors:
            raise ValueError(f"Import validation failed:\n" + "\n".join(validation_errors[:10]))  # Limit to first 10 errors
        
        return entries
    
    def _parse_date(self, date_value) -> str:
        """Parse and validate date format."""
        try:
            if pd.isna(date_value):
                raise ValueError("Date cannot be empty")
            
            # Convert to pandas datetime and format as ISO string
            date_obj = pd.to_datetime(date_value)
            return date_obj.strftime('%Y-%m-%d')
            
        except Exception:
            raise ValueError(f"Invalid date format: {date_value}")
    
    def _validate_entry_type(self, entry_type) -> str:
        """Validate entry type against allowed values."""
        valid_types = ['daily', 'dream']
        entry_type = str(entry_type).lower().strip()
        
        if entry_type not in valid_types:
            raise ValueError(f"Invalid entry type: {entry_type}. Must be one of: {', '.join(valid_types)}")
        
        return entry_type
    
    def _sanitise_content(self, content: str) -> str:
        """Sanitise content to prevent XSS and script injection."""
        if not content:
            return ""
        
        # Basic sanitisation - remove potential script tags and malicious content
        content = str(content).strip()
        dangerous_patterns = ['<script', '</script>', 'javascript:', 'onload=', 'onerror=']
        
        for pattern in dangerous_patterns:
            content = content.replace(pattern, '')
        
        return content
    
    def _parse_tags(self, tags_value) -> str:
        """Parse tags from import data."""
        if pd.isna(tags_value) or not tags_value:
            return ""
        
        # Convert comma-separated tags to cleaned string
        tags = str(tags_value).split(',')
        cleaned_tags = [tag.strip() for tag in tags if tag.strip()]
        
        return ', '.join(cleaned_tags)
    
    def _validate_content_quality(self, content: str, row_number: int) -> None:
        """Validate content quality and length."""
        if len(content.strip()) < 10:
            raise ValueError(f"Content too short (minimum 10 characters)")
        
        if len(content) > 10000:  # 10k character limit
            raise ValueError(f"Content too long (maximum 10,000 characters)")
        
        # Check for suspicious patterns
        if content.count('\n') > 100:  # Too many line breaks
            raise ValueError(f"Content appears malformed (excessive line breaks)")
    
    def _validate_date_range(self, entry_date: str, row_number: int) -> None:
        """Validate date is within reasonable range."""
        try:
            date_obj = datetime.strptime(entry_date, '%Y-%m-%d')
            today = datetime.now()
            
            # Check if date is too far in future (max 1 year)
            if date_obj > today + timedelta(days=365):
                raise ValueError(f"Date too far in future: {entry_date}")
            
            # Check if date is too far in past (max 50 years)
            if date_obj < today - timedelta(days=365 * 50):
                raise ValueError(f"Date too far in past: {entry_date}")
                
        except ValueError as e:
            if "time data" in str(e):
                raise ValueError(f"Invalid date format: {entry_date}")
            raise
    
    def _extract_intelligent_tags(self, content: str) -> List[str]:
        """
        Extract intelligent tags using NLTK processing.
        Identifies emotions, activities, themes, and concepts.
        """
        if not NLTK_AVAILABLE:
            return self._extract_simple_tags(content)
            
        try:
            from nltk import word_tokenize, pos_tag, ne_chunk
            from nltk.chunk import tree2conlltags
            
            # Tokenize and tag
            tokens = word_tokenize(content.lower())
            pos_tags = pos_tag(tokens)
            
            # Extract meaningful tags
            tags = set()
            
            # 1. Emotion words
            emotion_words = {
                'happy', 'sad', 'angry', 'excited', 'worried', 'calm', 'stressed',
                'grateful', 'frustrated', 'hopeful', 'anxious', 'peaceful', 'overwhelmed',
                'joy', 'fear', 'love', 'hate', 'pride', 'shame', 'guilt', 'relief'
            }
            
            # 2. Activity/theme words
            activity_words = {
                'work', 'exercise', 'travel', 'family', 'friends', 'cooking', 'reading',
                'music', 'art', 'nature', 'meditation', 'therapy', 'learning', 'growth',
                'relationship', 'career', 'health', 'finance', 'hobby', 'creativity'
            }
            
            # Find emotion and activity tags
            for word, pos in pos_tags:
                if word in emotion_words:
                    tags.add(word)
                if word in activity_words:
                    tags.add(word)
                
                # Add significant nouns and adjectives
                if pos in ['NN', 'NNS', 'JJ'] and len(word) > 3:
                    # Filter common words
                    if word not in {'this', 'that', 'with', 'have', 'been', 'they', 'them', 'were', 'said'}:
                        if self._is_meaningful_word(word):
                            tags.add(word)
            
            return list(tags)[:10]  # Limit to top 10 tags
            
        except Exception as e:
            # Fallback to simple keyword extraction if NLTK fails
            return self._extract_simple_tags(content)
    
    def _extract_people_names(self, content: str) -> str:
        """Extract people names using NLTK named entity recognition."""
        if not NLTK_AVAILABLE:
            return self._extract_simple_names(content)
            
        try:
            from nltk import word_tokenize, pos_tag, ne_chunk
            from nltk.chunk import tree2conlltags
            
            tokens = word_tokenize(content)
            pos_tags = pos_tag(tokens)
            chunks = ne_chunk(pos_tags)
            
            people_names = set()
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    name = ' '.join([token for token, pos in chunk.leaves()])
                    people_names.add(name)
            
            return ', '.join(people_names)
            
        except Exception:
            # Fallback: look for capitalised words that might be names
            return self._extract_simple_names(content)
    
    def _extract_simple_names(self, content: str) -> str:
        """Fallback method for name extraction without NLTK."""
        import re
        potential_names = re.findall(r'\b[A-Z][a-z]+\b', content)
        # Filter common words that aren't names
        common_words = {'I', 'The', 'This', 'That', 'Today', 'Tomorrow', 'Yesterday'}
        names = [name for name in potential_names if name not in common_words]
        return ', '.join(set(names)[:5])  # Limit to 5 names
    
    def _extract_places(self, content: str) -> str:
        """Extract place names using NLTK named entity recognition."""
        if not NLTK_AVAILABLE:
            return self._extract_simple_places(content)
            
        try:
            from nltk import word_tokenize, pos_tag, ne_chunk
            
            tokens = word_tokenize(content)
            pos_tags = pos_tag(tokens)
            chunks = ne_chunk(pos_tags)
            
            places = set()
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() in ['GPE', 'LOCATION']:
                    place = ' '.join([token for token, pos in chunk.leaves()])
                    places.add(place)
            
            return ', '.join(places)
            
        except Exception:
            # Fallback: look for location keywords
            return self._extract_simple_places(content)
    
    def _extract_simple_places(self, content: str) -> str:
        """Fallback method for place extraction without NLTK."""
        location_keywords = {
            'home', 'work', 'office', 'school', 'hospital', 'park', 'beach', 'mountain',
            'city', 'town', 'country', 'restaurant', 'cafe', 'shop', 'mall', 'gym'
        }
        
        words = content.lower().split()
        found_places = [word for word in words if word in location_keywords]
        return ', '.join(set(found_places)[:5])
    
    def _is_meaningful_word(self, word: str) -> bool:
        """Check if word is meaningful for tagging."""
        # Filter out common stop words and short words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'through', 'again'
        }
        
        return (len(word) >= 4 and 
                word not in stop_words and 
                word.isalpha() and 
                not word.isdigit())
    
    def _extract_simple_tags(self, content: str) -> List[str]:
        """Fallback simple tag extraction."""
        # Simple keyword-based extraction
        keywords = {
            'grateful', 'happy', 'sad', 'work', 'family', 'exercise', 'travel',
            'stressed', 'calm', 'excited', 'worried', 'nature', 'reading', 'music'
        }
        
        content_lower = content.lower()
        found_tags = [keyword for keyword in keywords if keyword in content_lower]
        return found_tags[:5]
    
    def _merge_tags(self, content_tags: List[str], manual_tags: str) -> str:
        """Merge NLTK-extracted tags with manually provided tags."""
        all_tags = set(content_tags)
        
        if manual_tags:
            manual_tag_list = [tag.strip() for tag in manual_tags.split(',') if tag.strip()]
            all_tags.update(manual_tag_list)
        
        return ', '.join(sorted(all_tags)[:15])  # Limit to 15 total tags
    
    def get_import_template(self, entry_type: str = 'daily') -> Dict:
        """
        Generate import template structure for download.
        
        Returns:
            Dict: Template structure with headers and example data
        """
        instructions = "IMPORTANT: Do not modify or delete the header row. The import process relies on the exact column order. Fields marked with * are required."
        
        if entry_type == 'daily':
            return {
                'instructions': instructions,
                'headers': [
                    'Date (YYYY-MM-DD) *',  # entry_date - REQUIRED
                    'Diary Entry *',        # user_message - REQUIRED
                    'AI Response',          # ai_response - OPTIONAL
                    'Names or places (separated by commas)',  # daily_people_names - OPTIONAL
                    'Tags (separated by commas)'  # tags - OPTIONAL
                ],
                'example_data': [
                    [
                        '2025-11-17',
                        'Today I had a productive morning meeting with Sarah and worked on the new project. Feeling motivated about the upcoming deadline.',
                        'It sounds like you had a positive and productive start to your day. The meeting with Sarah seems to have energized you for the project work ahead.',
                        'Sarah',
                        'work, productivity, motivation'
                    ],
                    [
                        '2025-11-16',
                        'Spent the evening at home reading and reflecting on my goals. The weather was perfect for staying in.',
                        'A peaceful evening of self-reflection and reading. It\'s important to take time for personal growth and relaxation.',
                        '',
                        'reflection, reading, goals, relaxation'
                    ]
                ]
            }
        elif entry_type == 'dream':
            return {
                'instructions': instructions,
                'headers': [
                    'Date (YYYY-MM-DD) *',      # entry_date - REQUIRED
                    'Dream Title',              # title - OPTIONAL
                    'Characters in Dream',      # cast - OPTIONAL
                    'Dream Location/Setting',   # location - OPTIONAL
                    'Time Period',              # period - OPTIONAL
                    'Emotions Felt',            # emotion - OPTIONAL
                    'Dream Story/Plot *',       # plot - REQUIRED
                    'Symbols or Imagery',       # symbols_and_imagery - OPTIONAL
                    'Personal Insight',         # insight - OPTIONAL
                    'Actions Taken',            # action - OPTIONAL
                    'Other Notes',              # other - OPTIONAL
                    'Dream Summary',            # summary - OPTIONAL
                    'Interpretation/Analysis',  # interpretation - OPTIONAL
                    'Image Description',        # image_prompt - OPTIONAL
                    'Image URL',                # image_url - OPTIONAL
                    'Names or places (separated by commas)',  # dream_people_names - OPTIONAL
                    'Tags (separated by commas)'  # tags - OPTIONAL
                ],
                'example_data': [
                    [
                        '2025-11-17',
                        'Flying Over Mountains',
                        'Myself, childhood friend Alex',
                        'Mountain range, small village below',
                        'Modern day',
                        'Freedom, exhilaration, slight fear',
                        'I was flying over beautiful mountains, soaring effortlessly. Alex was on the ground waving up at me. The air was crisp and the view was breathtaking.',
                        'Mountains representing challenges, wings symbolizing freedom, village representing safety and home',
                        'This dream represents overcoming obstacles and achieving personal freedom. The mountains show life\'s challenges that I can rise above.',
                        'I need to take more risks in my career and trust my abilities.',
                        'The flying felt incredibly realistic, like I could actually feel the wind on my face.',
                        'A dream about overcoming fears and achieving personal freedom through flight.',
                        'Flying dreams often symbolize a desire for freedom or escape from constraints. The presence of your childhood friend suggests a connection to your past self.',
                        'A person flying majestically over snow-capped mountains at sunset, wings spread wide, with a small village visible in the valley below',
                        'https://example.com/flying-dream-image.jpg',
                        'Alex',
                        'flying, freedom, mountains, childhood, overcoming fears'
                    ],
                    [
                        '2025-11-16',
                        'Lost in Old House',
                        'Myself, grandmother (deceased)',
                        'Childhood home, upstairs hallway',
                        '1980s (childhood)',
                        'Confusion, nostalgia, slight anxiety',
                        'I was back in my childhood home but it was much larger than I remembered. I kept getting lost in the hallways trying to find my room. My grandmother appeared and helped guide me.',
                        'House representing self/family, hallways symbolizing life paths, grandmother representing guidance and wisdom',
                        'This dream reflects feelings of being lost in life and needing guidance. The childhood home suggests a return to roots for clarity.',
                        'I should reach out to family more and reconnect with my past.',
                        'The house seemed to shift and change as I walked through it, like the walls were moving.',
                        'A confusing dream about being lost in a familiar childhood home and receiving guidance from a deceased relative.',
                        'Being lost in your childhood home often represents feeling directionless in life. The guidance from your grandmother suggests you have inner wisdom to draw upon.',
                        'A person wandering through a long, confusing hallway in an old house, with doors leading to unknown rooms',
                        'https://example.com/lost-house-dream-image.jpg',
                        'Grandmother',
                        'lost, childhood, guidance, family, confusion'
                    ]
                ]
            }
        else:
            raise ValueError(f"Unknown template type: {entry_type}")

# Global import service instance
import_service = ImportService()