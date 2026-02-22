import sqlite3
import os
import json

DB_FILE = "health_companion.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Biometrics Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS biometrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        weight_lb DECIMAL(5, 2),
        bmi DECIMAL(4, 1),
        metabolic_age INT,
        bmr_kcal INT,
        body_fat_percentage DECIMAL(4, 1),
        subcutaneous_fat_percentage DECIMAL(4, 1),
        visceral_fat_rating INT,
        skeletal_muscle_percentage DECIMAL(4, 1),
        muscle_mass_lb DECIMAL(5, 2),
        fat_free_body_weight_lb DECIMAL(5, 2),
        bone_mass_lb DECIMAL(4, 2),
        body_water_percentage DECIMAL(4, 1),
        protein_percentage DECIMAL(4, 1),
        status_tags TEXT -- JSON string
    )
    ''')

    # 2. Meals Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        items TEXT,
        calories INT,
        notes TEXT
    )
    ''')
    
    # 3. Report Schedules Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS report_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_prompt TEXT NOT NULL, 
        cron_schedule TEXT NOT NULL,
        last_run_at DATETIME,
        is_active BOOLEAN DEFAULT TRUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 4. Reports Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        content TEXT
    )
    ''')

    # 5. User Goals Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_FILE}")

def drop_tables():
    """Drops all tables for clean testing."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS biometrics')
    cursor.execute('DROP TABLE IF EXISTS meals')
    cursor.execute('DROP TABLE IF EXISTS report_schedules')
    cursor.execute('DROP TABLE IF EXISTS reports')
    cursor.execute('DROP TABLE IF EXISTS user_goals')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
