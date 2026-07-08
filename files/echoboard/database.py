"""
database.py
EchoBoard - Database layer

Stores every captured "board keyframe" (a moment where the board content
changed and then settled) along with metadata needed to search and replay
a lesson later.

Uses SQLite because it needs zero setup (no server, no credentials) and is
perfect for an MVP / college project. It can be swapped for Postgres later
without changing the rest of the app, since all access goes through the
functions in this file.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "echoboard.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't already exist. Safe to call every run."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            duration_sec REAL,
            total_frames INTEGER,
            fps REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS keyframes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_number INTEGER NOT NULL,
            timestamp_sec REAL NOT NULL,
            image_path TEXT NOT NULL,
            change_score REAL,
            ocr_text TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    """)

    # Helpful index for fast timeline queries per video
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_keyframes_video
        ON keyframes (video_id, timestamp_sec)
    """)

    conn.commit()
    conn.close()


def insert_video(filename, duration_sec, total_frames, fps):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO videos (filename, uploaded_at, duration_sec, total_frames, fps)
           VALUES (?, ?, ?, ?, ?)""",
        (filename, datetime.utcnow().isoformat(), duration_sec, total_frames, fps),
    )
    conn.commit()
    video_id = cur.lastrowid
    conn.close()
    return video_id


def insert_keyframe(video_id, frame_number, timestamp_sec, image_path, change_score, ocr_text=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO keyframes
           (video_id, frame_number, timestamp_sec, image_path, change_score, ocr_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (video_id, frame_number, timestamp_sec, image_path, change_score,
         ocr_text, datetime.utcnow().isoformat()),
    )
    conn.commit()
    kf_id = cur.lastrowid
    conn.close()
    return kf_id


def get_all_videos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM videos ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_keyframes_for_video(video_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM keyframes WHERE video_id = ? ORDER BY timestamp_sec ASC",
        (video_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_keyframes(query):
    """Basic text search across stored OCR text (once OCR is plugged in)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT keyframes.*, videos.filename AS video_filename
           FROM keyframes JOIN videos ON keyframes.video_id = videos.id
           WHERE keyframes.ocr_text LIKE ?
           ORDER BY keyframes.timestamp_sec ASC""",
        (f"%{query}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
