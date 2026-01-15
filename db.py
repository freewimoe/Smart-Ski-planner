"""
Database module for Smart Ski Vacation Planner
Extended schema for Level 2 functionality
"""

import sqlite3
import bcrypt
import json
from typing import Dict, List, Optional
DB_FILE = "user_data.db"

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    """Initialize the SQLite database with extended schema for Level 2."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # User Table (Level 1)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Saved Trips Table (Level 1)
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_lat REAL,
            start_lon REAL,
            destination_name TEXT,
            trip_date TEXT,
            end_date TEXT,
            adults INTEGER DEFAULT 2,
            children INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # User Preferences (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            skill_level TEXT DEFAULT 'intermediate',
            budget_level TEXT DEFAULT 'medium',
            max_distance_km INTEGER DEFAULT 500,
            prefer_apres_ski BOOLEAN DEFAULT 0,
            prefer_family BOOLEAN DEFAULT 0,
            prefer_snow_guarantee BOOLEAN DEFAULT 1,
            prefer_terrain_park BOOLEAN DEFAULT 0,
            prefer_cross_country BOOLEAN DEFAULT 0,
            min_slopes_km INTEGER DEFAULT 50,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Favorites (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resort_name TEXT NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, resort_name),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Trip Notes (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS trip_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            note_text TEXT NOT NULL,
            note_type TEXT DEFAULT 'general',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trip_id) REFERENCES saved_trips(id) ON DELETE CASCADE
        )
    ''')

    # User Reviews (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resort_name TEXT NOT NULL,
            overall_rating INTEGER CHECK(overall_rating BETWEEN 1 AND 5),
            snow_rating INTEGER CHECK(snow_rating BETWEEN 1 AND 5),
            lift_rating INTEGER CHECK(lift_rating BETWEEN 1 AND 5),
            food_rating INTEGER CHECK(food_rating BETWEEN 1 AND 5),
            value_rating INTEGER CHECK(value_rating BETWEEN 1 AND 5),
            review_title TEXT,
            review_text TEXT,
            visited_date DATE,
            would_recommend BOOLEAN DEFAULT 1,
            pros TEXT,
            cons TEXT,
            helpful_votes INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Review Votes (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_votes (
            user_id INTEGER NOT NULL,
            review_id INTEGER NOT NULL,
            is_helpful BOOLEAN NOT NULL,
            voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, review_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(review_id) REFERENCES user_reviews(id) ON DELETE CASCADE
        )
    ''')

    # Trip Checklist (Level 2 - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS trip_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            item_text TEXT NOT NULL,
            category TEXT DEFAULT 'equipment',
            is_checked BOOLEAN DEFAULT 0,
            priority INTEGER DEFAULT 2,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trip_id) REFERENCES saved_trips(id) ON DELETE CASCADE
        )
    ''')

    # Indexes for performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_reviews_resort ON user_reviews(resort_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_notes_trip ON trip_notes(trip_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_checklist_trip ON trip_checklist(trip_id)')

    conn.commit()
    conn.close()


# =============================================================================
# USER AUTHENTICATION (Level 1)
# =============================================================================

def register_user(username: str, password: str) -> bool:
    """Register a new user with hashed password."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                  (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login_user(username: str, password: str) -> Optional[int]:
    """Verify user credentials and return user ID if valid."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()

    if user:
        stored_hash = user[1]
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return user[0]
    return None


# =============================================================================
# SAVED TRIPS (Level 1 + Extended)
# =============================================================================

def save_trip(user_id: int, start_lat: float, start_lon: float,
              destination: str, date, end_date=None,
              adults: int = 2, children: int = 0) -> int:
    """Save a trip and return the trip ID."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO saved_trips (user_id, start_lat, start_lon, destination_name,
                                 trip_date, end_date, adults, children)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, start_lat, start_lon, destination, str(date),
          str(end_date) if end_date else None, adults, children))
    trip_id = c.lastrowid
    conn.commit()
    conn.close()
    return trip_id


def get_user_trips(user_id: int) -> List[tuple]:
    """Get all saved trips for a user."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT destination_name, trip_date, timestamp
                 FROM saved_trips WHERE user_id = ?
                 ORDER BY timestamp DESC''', (user_id,))
    trips = c.fetchall()
    conn.close()
    return trips


def get_trip_details(trip_id: int) -> Optional[Dict]:
    """Get full details for a specific trip."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT * FROM saved_trips WHERE id = ?''', (trip_id,))
    row = c.fetchone()
    conn.close()

    if row:
        columns = ['id', 'user_id', 'start_lat', 'start_lon', 'destination_name',
                   'trip_date', 'end_date', 'adults', 'children', 'timestamp']
        return dict(zip(columns, row))
    return None


def delete_trip(trip_id: int, user_id: int) -> bool:
    """Delete a trip (only if owned by user)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM saved_trips WHERE id = ? AND user_id = ?',
              (trip_id, user_id))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# USER PREFERENCES (Level 2 - NEW)
# =============================================================================

def save_user_preferences(user_id: int, preferences: Dict) -> bool:
    """Save or update user preferences."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Build dynamic upsert query
    columns = list(preferences.keys())
    placeholders = ', '.join(['?'] * len(columns))
    updates = ', '.join([f"{k} = ?" for k in columns])

    try:
        c.execute(f'''
            INSERT INTO user_preferences (user_id, {', '.join(columns)})
            VALUES (?, {placeholders})
            ON CONFLICT(user_id) DO UPDATE SET {updates}, updated_at = CURRENT_TIMESTAMP
        ''', [user_id] + list(preferences.values()) + list(preferences.values()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving preferences: {e}")
        return False
    finally:
        conn.close()


def get_user_preferences(user_id: int) -> Optional[Dict]:
    """Load user preferences."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        columns = ['user_id', 'skill_level', 'budget_level', 'max_distance_km',
                   'prefer_apres_ski', 'prefer_family', 'prefer_snow_guarantee',
                   'prefer_terrain_park', 'prefer_cross_country', 'min_slopes_km',
                   'updated_at']
        prefs = dict(zip(columns, row))
        # Convert boolean integers to actual booleans
        for key in ['prefer_apres_ski', 'prefer_family', 'prefer_snow_guarantee',
                    'prefer_terrain_park', 'prefer_cross_country']:
            prefs[key] = bool(prefs.get(key, 0))
        return prefs
    return None


def get_default_preferences() -> Dict:
    """Return default preference values."""
    return {
        'skill_level': 'intermediate',
        'budget_level': 'medium',
        'max_distance_km': 500,
        'prefer_apres_ski': False,
        'prefer_family': False,
        'prefer_snow_guarantee': True,
        'prefer_terrain_park': False,
        'prefer_cross_country': False,
        'min_slopes_km': 50
    }


# =============================================================================
# FAVORITES (Level 2 - NEW)
# =============================================================================

def add_favorite(user_id: int, resort_name: str) -> bool:
    """Add a resort to user's favorites."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO favorites (user_id, resort_name) VALUES (?, ?)',
                  (user_id, resort_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Already favorited
    finally:
        conn.close()


def remove_favorite(user_id: int, resort_name: str) -> bool:
    """Remove a resort from user's favorites."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM favorites WHERE user_id = ? AND resort_name = ?',
              (user_id, resort_name))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_user_favorites(user_id: int) -> List[str]:
    """Get all favorite resort names for a user."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT resort_name FROM favorites WHERE user_id = ? ORDER BY added_at DESC',
              (user_id,))
    favorites = [row[0] for row in c.fetchall()]
    conn.close()
    return favorites


def is_favorite(user_id: int, resort_name: str) -> bool:
    """Check if a resort is in user's favorites."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM favorites WHERE user_id = ? AND resort_name = ?',
              (user_id, resort_name))
    result = c.fetchone() is not None
    conn.close()
    return result


# =============================================================================
# TRIP NOTES (Level 2 - NEW)
# =============================================================================

def add_trip_note(trip_id: int, note_text: str, note_type: str = 'general') -> int:
    """Add a note to a trip."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO trip_notes (trip_id, note_text, note_type)
                 VALUES (?, ?, ?)''', (trip_id, note_text, note_type))
    note_id = c.lastrowid
    conn.commit()
    conn.close()
    return note_id


def get_trip_notes(trip_id: int) -> List[Dict]:
    """Get all notes for a trip."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT id, note_text, note_type, created_at
                 FROM trip_notes WHERE trip_id = ? ORDER BY created_at DESC''',
              (trip_id,))
    notes = [{'id': r[0], 'text': r[1], 'type': r[2], 'created_at': r[3]}
             for r in c.fetchall()]
    conn.close()
    return notes


def update_trip_note(note_id: int, note_text: str) -> bool:
    """Update an existing note."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE trip_notes SET note_text = ?, updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?''', (note_text, note_id))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def delete_trip_note(note_id: int) -> bool:
    """Delete a note."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM trip_notes WHERE id = ?', (note_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# USER REVIEWS (Level 2 - NEW)
# =============================================================================

def submit_review(user_id: int, resort_name: str, ratings: Dict,
                  review_text: str, **kwargs) -> int:
    """Create or update a review for a resort."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Check if review already exists
    c.execute('SELECT id FROM user_reviews WHERE user_id = ? AND resort_name = ?',
              (user_id, resort_name))
    existing = c.fetchone()

    pros = json.dumps(kwargs.get('pros', []))
    cons = json.dumps(kwargs.get('cons', []))

    if existing:
        # Update existing review
        c.execute('''UPDATE user_reviews SET
                    overall_rating = ?, snow_rating = ?, lift_rating = ?,
                    food_rating = ?, value_rating = ?, review_title = ?,
                    review_text = ?, visited_date = ?, would_recommend = ?,
                    pros = ?, cons = ?
                    WHERE id = ?''',
                  (ratings.get('overall'), ratings.get('snow'), ratings.get('lift'),
                   ratings.get('food'), ratings.get('value'), kwargs.get('title'),
                   review_text, kwargs.get('visited_date'), kwargs.get('recommend', True),
                   pros, cons, existing[0]))
        review_id = existing[0]
    else:
        # Insert new review
        c.execute('''INSERT INTO user_reviews
                    (user_id, resort_name, overall_rating, snow_rating, lift_rating,
                     food_rating, value_rating, review_title, review_text,
                     visited_date, would_recommend, pros, cons)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, resort_name, ratings.get('overall'), ratings.get('snow'),
                   ratings.get('lift'), ratings.get('food'), ratings.get('value'),
                   kwargs.get('title'), review_text, kwargs.get('visited_date'),
                   kwargs.get('recommend', True), pros, cons))
        review_id = c.lastrowid

    conn.commit()
    conn.close()
    return review_id


def get_resort_reviews(resort_name: str, limit: int = 10) -> List[Dict]:
    """Get reviews for a resort."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT r.*, u.username
                 FROM user_reviews r
                 JOIN users u ON r.user_id = u.id
                 WHERE r.resort_name = ?
                 ORDER BY r.helpful_votes DESC, r.created_at DESC
                 LIMIT ?''', (resort_name, limit))

    columns = ['id', 'user_id', 'resort_name', 'overall_rating', 'snow_rating',
               'lift_rating', 'food_rating', 'value_rating', 'review_title',
               'review_text', 'visited_date', 'would_recommend', 'pros', 'cons',
               'helpful_votes', 'created_at', 'username']

    reviews = []
    for row in c.fetchall():
        review = dict(zip(columns, row))
        review['pros'] = json.loads(review['pros']) if review['pros'] else []
        review['cons'] = json.loads(review['cons']) if review['cons'] else []
        review['would_recommend'] = bool(review['would_recommend'])
        reviews.append(review)

    conn.close()
    return reviews


def get_resort_rating_summary(resort_name: str) -> Dict:
    """Calculate average ratings for a resort."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT
                    COUNT(*) as count,
                    AVG(overall_rating) as avg_overall,
                    AVG(snow_rating) as avg_snow,
                    AVG(lift_rating) as avg_lift,
                    AVG(food_rating) as avg_food,
                    AVG(value_rating) as avg_value,
                    SUM(would_recommend) * 100.0 / COUNT(*) as recommend_pct
                 FROM user_reviews WHERE resort_name = ?''', (resort_name,))
    row = c.fetchone()
    conn.close()

    if row and row[0] > 0:
        return {
            'count': row[0],
            'overall': round(row[1], 1) if row[1] else 0,
            'snow': round(row[2], 1) if row[2] else 0,
            'lift': round(row[3], 1) if row[3] else 0,
            'food': round(row[4], 1) if row[4] else 0,
            'value': round(row[5], 1) if row[5] else 0,
            'recommend_pct': round(row[6], 0) if row[6] else 0
        }
    return {'count': 0}


def vote_review_helpful(user_id: int, review_id: int, is_helpful: bool) -> bool:
    """Vote a review as helpful or not."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    try:
        # Upsert vote
        c.execute('''INSERT INTO review_votes (user_id, review_id, is_helpful)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, review_id) DO UPDATE SET
                    is_helpful = ?, voted_at = CURRENT_TIMESTAMP''',
                  (user_id, review_id, is_helpful, is_helpful))

        # Update helpful count on review
        c.execute('''UPDATE user_reviews SET helpful_votes = (
                        SELECT COALESCE(SUM(CASE WHEN is_helpful THEN 1 ELSE -1 END), 0)
                        FROM review_votes WHERE review_id = ?
                    ) WHERE id = ?''', (review_id, review_id))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error voting: {e}")
        return False
    finally:
        conn.close()


# =============================================================================
# TRIP CHECKLIST (Level 2 - NEW)
# =============================================================================

DEFAULT_CHECKLIST = {
    'equipment': ['Ski/Snowboard', 'Skischuhe/Boots', 'Helm', 'Skibrille', 'Handschuhe'],
    'clothing': ['Skijacke', 'Skihose', 'Thermounterwaesche', 'Skisocken', 'Muetze'],
    'documents': ['Ausweis', 'Krankenversicherungskarte', 'Skipass-Reservierung', 'Hotelbestaetigung'],
    'other': ['Sonnencreme', 'Lippenbalsam', 'Erste-Hilfe-Set', 'Ladegeraete']
}


def initialize_trip_checklist(trip_id: int) -> None:
    """Create default checklist for a trip."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    for category, items in DEFAULT_CHECKLIST.items():
        for item in items:
            c.execute('''INSERT INTO trip_checklist (trip_id, item_text, category)
                        VALUES (?, ?, ?)''', (trip_id, item, category))

    conn.commit()
    conn.close()


def get_trip_checklist(trip_id: int) -> Dict[str, List[Dict]]:
    """Get checklist grouped by category."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT id, item_text, category, is_checked, priority
                 FROM trip_checklist WHERE trip_id = ?
                 ORDER BY category, priority, item_text''', (trip_id,))

    checklist = {}
    for row in c.fetchall():
        cat = row[2]
        if cat not in checklist:
            checklist[cat] = []
        checklist[cat].append({
            'id': row[0],
            'text': row[1],
            'checked': bool(row[3]),
            'priority': row[4]
        })

    conn.close()
    return checklist


def toggle_checklist_item(item_id: int) -> bool:
    """Toggle checked status of a checklist item."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE trip_checklist SET is_checked = NOT is_checked WHERE id = ?',
              (item_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def add_checklist_item(trip_id: int, item_text: str,
                       category: str = 'other', priority: int = 2) -> int:
    """Add a custom item to a trip's checklist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO trip_checklist (trip_id, item_text, category, priority)
                 VALUES (?, ?, ?, ?)''', (trip_id, item_text, category, priority))
    item_id = c.lastrowid
    conn.commit()
    conn.close()
    return item_id


def delete_checklist_item(item_id: int) -> bool:
    """Delete a checklist item."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM trip_checklist WHERE id = ?', (item_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0
