import sqlite3

# Connect to the database
conn = sqlite3.connect('app.db')

# Create a cursor
c = conn.cursor()

# Create users table
c.execute('''CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                sex TEXT,
                goals TEXT,
                dailydiary_api_key TEXT,
                dreamdiary_api_key TEXT,
                chatgpt_daily_diary_coachname TEXT,
                chatgpt_dream_diary_coachname TEXT)''')

# Create configurations table
c.execute('''CREATE TABLE configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                daily_diary_prompt TEXT,
                dream_diary_prompt TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id))''')

# Create daily diary table with entry_number column
c.execute('''CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date DATE,
                entry_number INTEGER,
                user_message TEXT,
                ai_response TEXT,
                daily_people_names TEXT,
                tags TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id))''')

# Create dream diary table
c.execute('''CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date DATE,
                entry_number INTEGER,
                title TEXT,
                cast TEXT,
                location TEXT,
                period TEXT,
                emotion TEXT,
                plot TEXT,
                symbols_and_imagery TEXT,
                insight TEXT,
                action TEXT,
                other TEXT,
                summary TEXT,
                interpretation TEXT,
                image_prompt TEXT,
                image_url TEXT,
                dream_people_names TEXT,
                tags TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id))''')

# Commit changes and close connection
conn.commit()
conn.close()
