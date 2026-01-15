import sqlite3
import bcrypt
import os

DB_FILE = "user_data.db"

def init_db():
    """Initialize the SQLite database with users and searches tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # User Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Saved Searches/Trips Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_lat REAL,
            start_lon REAL,
            destination_name TEXT,
            trip_date TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    
    if user:
        stored_hash = user[1]
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return user[0] # Return ID
    return None

def save_trip(user_id, start_lat, start_lon, destination, date):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO saved_trips (user_id, start_lat, start_lon, destination_name, trip_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, start_lat, start_lon, destination, str(date)))
    conn.commit()
    conn.close()

def get_user_trips(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT destination_name, trip_date, timestamp FROM saved_trips WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
    trips = c.fetchall()
    conn.close()
    return trips
