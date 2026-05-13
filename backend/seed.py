import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snake.db')


def create_tables():
    """Create the users table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            high_score INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


if __name__ == '__main__':
    create_tables()
    print("Database tables created successfully.")
