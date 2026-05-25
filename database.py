"""
database.py
───────────
Creates the SQLite database and all tables.
Handles all connections.

The database lives in a single file: data/kite_ledger.db
That file is the entire database — tables, data, and all.
"""

import sqlite3
import os

DB_PATH = "data/kite_ledger.db"

os.makedirs("data", exist_ok=True)


def get_connection():
    """Return a connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables():
    """Create all tables if they don't exist yet."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS instructors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            phone           TEXT,
            commission_rate REAL NOT NULL DEFAULT 0.30,
            active          INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS students (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            email        TEXT,
            phone        TEXT,
            weight_kg    REAL,
            skill_level  TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waivers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   INTEGER NOT NULL,
            signed_at    TEXT NOT NULL,
            expires_at   TEXT NOT NULL,
            drive_url    TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id)
);

        CREATE TABLE IF NOT EXISTS classes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      INTEGER NOT NULL,
            instructor_id   INTEGER NOT NULL,
            date            TEXT NOT NULL,
            duration_min    INTEGER,
            wind_speed_kn   REAL,
            status          TEXT DEFAULT 'completed',
    FOREIGN KEY (student_id)    REFERENCES students(id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
);

        CREATE TABLE IF NOT EXISTS billing (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id         INTEGER NOT NULL,
            amount_brl       REAL NOT NULL,
            commission_brl   REAL NOT NULL,
            status           TEXT DEFAULT 'pending',
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        );
    """)

    conn.commit()
    conn.close()
    print("[✓] Tables created")

if __name__ == "__main__":
    create_tables()