"""
database.py
EchoBoard Dataset Creation Module — MongoDB Atlas & Local SQLite Fallback

Manages the ECHD (EchoBoard Classroom Handwriting Dataset) metadata.
This module stores ONLY metadata — no OCR results, no predictions, no labels.

Collections / Tables:
  - dataset_images  : One record per keyframe image in the dataset
  - videos          : Source video metadata (for processing pipeline)
  - counters        : Sequential ECHD ID generator

The annotation_status field starts as "Pending" and is updated by a
separate Annotation Module (not this module).
"""

import os
import base64
import certifi
import sqlite3
import uuid
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONNECTION CONFIG — Loaded from .env file
# ---------------------------------------------------------------------------
MONGO_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DATABASE_NAME", "EchoBoardDB")

# Global flag and local SQLite config
USE_SQLITE = False
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(os.path.dirname(BASE_DIR), "echoboard_local.db")

_client = None
_id_lock = threading.Lock()   # Thread-safe ECHD ID generation


def get_db():
    """Return the MongoDB database handle, creating the client on first call."""
    global _client
    if _client is None:
        from pymongo import MongoClient
        _client = MongoClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=20000,
        )
    return _client[DB_NAME]


def get_sqlite_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db():
    """Create all SQLite tables for the dataset creation module."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Videos table (source video tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            filename TEXT,
            uploaded_at TEXT,
            duration_sec REAL,
            total_frames INTEGER,
            fps REAL,
            processing INTEGER DEFAULT 0
        )
    """)

    # Dataset images table (core ECHD metadata)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_images (
            id TEXT PRIMARY KEY,
            image_id TEXT UNIQUE NOT NULL,
            sequence_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            board_type TEXT DEFAULT 'Blackboard',
            writer_id TEXT DEFAULT 'unknown',
            frame_index INTEGER,
            timestamp_ms INTEGER,
            image_path TEXT NOT NULL,
            annotation_status TEXT DEFAULT 'Pending',
            dataset_version TEXT DEFAULT 'ECHD_v1',
            created_at TEXT,
            uploaded_by TEXT DEFAULT 'system',
            upload_time TEXT,
            video_id TEXT,
            change_score REAL
        )
    """)

    # Counters table (for sequential ECHD ID generation)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)

    # Initialize the ECHD counter if it doesn't exist
    cursor.execute(
        "INSERT OR IGNORE INTO counters (name, value) VALUES ('echd_image_id', 0)"
    )

    # Dataset versions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_versions (
            version TEXT PRIMARY KEY,
            created_at TEXT,
            description TEXT,
            image_count INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def init_db():
    """
    Initialize database connections and create indexes/tables.
    Tries MongoDB Atlas first, falls back to SQLite if unreachable.
    """
    global USE_SQLITE

    if not MONGO_URI:
        print("  MONGODB_URI not set — using local SQLite database.")
        USE_SQLITE = True
        init_sqlite_db()
        return

    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        test_client = MongoClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
        )
        test_client.list_database_names()

        # MongoDB is reachable — create indexes
        db = get_db()
        db.dataset_images.create_index([("image_id", ASCENDING)], unique=True)
        db.dataset_images.create_index([("sequence_id", ASCENDING)])
        db.dataset_images.create_index([("subject", ASCENDING)])
        db.dataset_images.create_index([("annotation_status", ASCENDING)])
        db.dataset_images.create_index([("dataset_version", ASCENDING)])
        db.dataset_images.create_index([("writer_id", ASCENDING)])
        db.videos.create_index([("uploaded_at", DESCENDING)])

        # Ensure counters collection has an ECHD counter
        if db.counters.find_one({"_id": "echd_image_id"}) is None:
            db.counters.insert_one({"_id": "echd_image_id", "seq": 0})

        print(f"  Database: MongoDB Atlas — '{DB_NAME}'")
        USE_SQLITE = False
    except Exception as e:
        print(f"\n  WARNING: Could not connect to MongoDB Atlas. Error: {e}")
        print(f"  Falling back to local SQLite database: {DB_FILE}\n")
        USE_SQLITE = True
        init_sqlite_db()


# ---------------------------------------------------------------------------
# Sequential ECHD ID Generation (thread-safe, no duplicates)
# ---------------------------------------------------------------------------
def _next_echd_id() -> str:
    """
    Generate the next sequential ECHD image ID.
    Format: ECHD000001, ECHD000002, ...
    Thread-safe — guaranteed unique across concurrent uploads.
    """
    global USE_SQLITE
    with _id_lock:
        if not USE_SQLITE:
            try:
                import pymongo.errors as mongo_errors
                db = get_db()
                result = db.counters.find_one_and_update(
                    {"_id": "echd_image_id"},
                    {"$inc": {"seq": 1}},
                    return_document=True,
                )
                return f"ECHD{result['seq']:06d}"
            except Exception as e:
                print(f"  MongoDB counter failed: {e}. Switching to SQLite.")
                USE_SQLITE = True
                init_sqlite_db()

        # SQLite fallback
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE counters SET value = value + 1 WHERE name = 'echd_image_id'"
        )
        cursor.execute(
            "SELECT value FROM counters WHERE name = 'echd_image_id'"
        )
        val = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return f"ECHD{val:06d}"


# ---------------------------------------------------------------------------
# Video CRUD (source video tracking for the processing pipeline)
# ---------------------------------------------------------------------------
def insert_video(filename, duration_sec, total_frames, fps, processing=False):
    """Insert a new source video record and return its ID as a string."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            import pymongo.errors as mongo_errors
            db = get_db()
            result = db.videos.insert_one({
                "filename": filename,
                "uploaded_at": datetime.utcnow().isoformat(),
                "duration_sec": duration_sec,
                "total_frames": total_frames,
                "fps": fps,
                "processing": processing,
            })
            return str(result.inserted_id)
        except Exception as e:
            print(f"  MongoDB write failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    video_id = uuid.uuid4().hex[:24]
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO videos (id, filename, uploaded_at, duration_sec, total_frames, fps, processing) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (video_id, filename, datetime.utcnow().isoformat(), duration_sec, total_frames, fps, 1 if processing else 0)
    )
    conn.commit()
    conn.close()
    return video_id


def get_all_videos():
    """Return all videos as a list of dicts, newest first."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            from pymongo import DESCENDING
            db = get_db()
            rows = db.videos.find().sort("uploaded_at", DESCENDING)
            videos = []
            for v in rows:
                videos.append({
                    "id": str(v["_id"]),
                    "filename": v["filename"],
                    "uploaded_at": v["uploaded_at"],
                    "duration_sec": v["duration_sec"],
                    "total_frames": v["total_frames"],
                    "fps": v["fps"],
                    "processing": v.get("processing", False),
                })
            return videos
        except Exception as e:
            print(f"  MongoDB query failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    videos = []
    for r in rows:
        videos.append({
            "id": r["id"],
            "filename": r["filename"],
            "uploaded_at": r["uploaded_at"],
            "duration_sec": r["duration_sec"],
            "total_frames": r["total_frames"],
            "fps": r["fps"],
            "processing": bool(r["processing"]),
        })
    conn.close()
    return videos


def get_video_by_id(video_id):
    """Return a single video dict, or None."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            from bson import ObjectId
            db = get_db()
            v = db.videos.find_one({"_id": ObjectId(video_id)})
            if not v:
                return None
            return {
                "id": str(v["_id"]),
                "filename": v["filename"],
                "uploaded_at": v["uploaded_at"],
                "duration_sec": v["duration_sec"],
                "total_frames": v["total_frames"],
                "fps": v["fps"],
                "processing": v.get("processing", False),
            }
        except Exception as e:
            print(f"  MongoDB query failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    v = cursor.fetchone()
    if not v:
        conn.close()
        return None
    res = {
        "id": v["id"],
        "filename": v["filename"],
        "uploaded_at": v["uploaded_at"],
        "duration_sec": v["duration_sec"],
        "total_frames": v["total_frames"],
        "fps": v["fps"],
        "processing": bool(v["processing"]),
    }
    conn.close()
    return res


def update_video(video_id, duration_sec, total_frames, fps, processing=False):
    """Update video duration and frame counts after progressive processing."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            from bson import ObjectId
            db = get_db()
            db.videos.update_one(
                {"_id": ObjectId(video_id)},
                {"$set": {
                    "duration_sec": duration_sec,
                    "total_frames": total_frames,
                    "fps": fps,
                    "processing": processing,
                }}
            )
            return
        except Exception as e:
            print(f"  MongoDB update failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE videos SET duration_sec = ?, total_frames = ?, fps = ?, processing = ? WHERE id = ?",
        (duration_sec, total_frames, fps, 1 if processing else 0, video_id)
    )
    conn.commit()
    conn.close()


def delete_video(video_id):
    """Delete a video and all its associated dataset images."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            from bson import ObjectId
            db = get_db()
            db.dataset_images.delete_many({"video_id": video_id})
            db.videos.delete_one({"_id": ObjectId(video_id)})
            return
        except Exception as e:
            print(f"  MongoDB delete failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dataset_images WHERE video_id = ?", (video_id,))
    cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Dataset Image CRUD (core ECHD metadata)
# ---------------------------------------------------------------------------
def insert_dataset_image(
    sequence_id: str,
    subject: str,
    board_type: str,
    writer_id: str,
    frame_index: int,
    timestamp_ms: int,
    image_path: str,
    dataset_version: str = "ECHD_v1",
    uploaded_by: str = "system",
    video_id: str = None,
    change_score: float = 0.0,
) -> dict:
    """
    Insert a new dataset image record into the database.
    Automatically generates a sequential ECHD image ID.
    annotation_status is always set to "Pending".

    Returns the inserted record as a dict.
    """
    global USE_SQLITE
    image_id = _next_echd_id()
    now = datetime.utcnow().isoformat()

    doc = {
        "image_id": image_id,
        "sequence_id": sequence_id,
        "subject": subject,
        "board_type": board_type,
        "writer_id": writer_id,
        "frame_index": frame_index,
        "timestamp_ms": timestamp_ms,
        "image_path": image_path,
        "annotation_status": "Pending",
        "dataset_version": dataset_version,
        "created_at": now,
        "uploaded_by": uploaded_by,
        "upload_time": now,
        "video_id": video_id or "",
        "change_score": change_score,
    }

    if not USE_SQLITE:
        try:
            db = get_db()
            result = db.dataset_images.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            return doc
        except Exception as e:
            print(f"  MongoDB write failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    doc_id = uuid.uuid4().hex[:24]
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO dataset_images
           (id, image_id, sequence_id, subject, board_type, writer_id,
            frame_index, timestamp_ms, image_path, annotation_status,
            dataset_version, created_at, uploaded_by, upload_time, video_id, change_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, image_id, sequence_id, subject, board_type, writer_id,
         frame_index, timestamp_ms, image_path, "Pending",
         dataset_version, now, uploaded_by, now, video_id or "", change_score)
    )
    conn.commit()
    conn.close()
    doc["id"] = doc_id
    return doc


def get_dataset_images(
    subject: str = None,
    sequence_id: str = None,
    writer_id: str = None,
    annotation_status: str = None,
    dataset_version: str = None,
    video_id: str = None,
    limit: int = 200,
) -> list:
    """Return dataset image records, filtered by optional criteria."""
    global USE_SQLITE

    if not USE_SQLITE:
        try:
            from pymongo import ASCENDING
            db = get_db()
            query = {}
            if subject:
                query["subject"] = subject
            if sequence_id:
                query["sequence_id"] = sequence_id
            if writer_id:
                query["writer_id"] = writer_id
            if annotation_status:
                query["annotation_status"] = annotation_status
            if dataset_version:
                query["dataset_version"] = dataset_version
            if video_id:
                query["video_id"] = video_id

            rows = db.dataset_images.find(query).sort("created_at", ASCENDING).limit(limit)
            results = []
            for r in rows:
                results.append({
                    "id": str(r["_id"]),
                    "image_id": r["image_id"],
                    "sequence_id": r["sequence_id"],
                    "subject": r["subject"],
                    "board_type": r["board_type"],
                    "writer_id": r["writer_id"],
                    "frame_index": r["frame_index"],
                    "timestamp_ms": r["timestamp_ms"],
                    "image_path": r["image_path"],
                    "annotation_status": r["annotation_status"],
                    "dataset_version": r["dataset_version"],
                    "created_at": r["created_at"],
                    "uploaded_by": r.get("uploaded_by", "system"),
                    "upload_time": r.get("upload_time", ""),
                    "video_id": r.get("video_id", ""),
                    "change_score": r.get("change_score", 0.0),
                })
            return results
        except Exception as e:
            print(f"  MongoDB query failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    sql = "SELECT * FROM dataset_images WHERE 1=1"
    params = []
    if subject:
        sql += " AND subject = ?"
        params.append(subject)
    if sequence_id:
        sql += " AND sequence_id = ?"
        params.append(sequence_id)
    if writer_id:
        sql += " AND writer_id = ?"
        params.append(writer_id)
    if annotation_status:
        sql += " AND annotation_status = ?"
        params.append(annotation_status)
    if dataset_version:
        sql += " AND dataset_version = ?"
        params.append(dataset_version)
    if video_id:
        sql += " AND video_id = ?"
        params.append(video_id)
    sql += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "image_id": r["image_id"],
            "sequence_id": r["sequence_id"],
            "subject": r["subject"],
            "board_type": r["board_type"],
            "writer_id": r["writer_id"],
            "frame_index": r["frame_index"],
            "timestamp_ms": r["timestamp_ms"],
            "image_path": r["image_path"],
            "annotation_status": r["annotation_status"],
            "dataset_version": r["dataset_version"],
            "created_at": r["created_at"],
            "uploaded_by": r["uploaded_by"],
            "upload_time": r["upload_time"],
            "video_id": r["video_id"],
            "change_score": r["change_score"],
        })
    conn.close()
    return results


def get_dataset_image_by_id(image_id: str) -> dict:
    """Return a single dataset image record by its ECHD image_id, or None."""
    global USE_SQLITE

    if not USE_SQLITE:
        try:
            db = get_db()
            r = db.dataset_images.find_one({"image_id": image_id})
            if not r:
                return None
            return {
                "id": str(r["_id"]),
                "image_id": r["image_id"],
                "sequence_id": r["sequence_id"],
                "subject": r["subject"],
                "board_type": r["board_type"],
                "writer_id": r["writer_id"],
                "frame_index": r["frame_index"],
                "timestamp_ms": r["timestamp_ms"],
                "image_path": r["image_path"],
                "annotation_status": r["annotation_status"],
                "dataset_version": r["dataset_version"],
                "created_at": r["created_at"],
                "uploaded_by": r.get("uploaded_by", "system"),
                "upload_time": r.get("upload_time", ""),
                "video_id": r.get("video_id", ""),
                "change_score": r.get("change_score", 0.0),
            }
        except Exception as e:
            print(f"  MongoDB query failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dataset_images WHERE image_id = ?", (image_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "image_id": r["image_id"],
        "sequence_id": r["sequence_id"],
        "subject": r["subject"],
        "board_type": r["board_type"],
        "writer_id": r["writer_id"],
        "frame_index": r["frame_index"],
        "timestamp_ms": r["timestamp_ms"],
        "image_path": r["image_path"],
        "annotation_status": r["annotation_status"],
        "dataset_version": r["dataset_version"],
        "created_at": r["created_at"],
        "uploaded_by": r["uploaded_by"],
        "upload_time": r["upload_time"],
        "video_id": r["video_id"],
        "change_score": r["change_score"],
    }


def delete_dataset_image(image_id: str):
    """Delete a dataset image record by its ECHD image_id."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            db = get_db()
            db.dataset_images.delete_one({"image_id": image_id})
            return
        except Exception as e:
            print(f"  MongoDB delete failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dataset_images WHERE image_id = ?", (image_id,))
    conn.commit()
    conn.close()


def get_images_for_video(video_id: str) -> list:
    """Return all dataset image records associated with a video."""
    return get_dataset_images(video_id=video_id, limit=10000)


# ---------------------------------------------------------------------------
# Dataset Version Management
# ---------------------------------------------------------------------------
def get_current_version() -> str:
    """Return the latest dataset version string."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            db = get_db()
            versions = list(db.dataset_versions.find().sort("created_at", -1).limit(1))
            if versions:
                return versions[0]["version"]
            return "ECHD_v1"
        except Exception:
            pass

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM dataset_versions ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return "ECHD_v1"


def create_new_version(description: str = "") -> str:
    """
    Create a new dataset version. Never overwrites previous versions.
    Returns the new version string (e.g. ECHD_v2, ECHD_v3, ...).
    """
    global USE_SQLITE
    current = get_current_version()
    # Extract version number and increment
    try:
        num = int(current.split("_v")[1])
    except (IndexError, ValueError):
        num = 1
    new_version = f"ECHD_v{num + 1}"
    now = datetime.utcnow().isoformat()

    # Count images in current version
    images = get_dataset_images(dataset_version=current, limit=100000)
    image_count = len(images)

    if not USE_SQLITE:
        try:
            db = get_db()
            db.dataset_versions.insert_one({
                "version": new_version,
                "created_at": now,
                "description": description,
                "image_count": image_count,
            })
            return new_version
        except Exception as e:
            print(f"  MongoDB version create failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dataset_versions (version, created_at, description, image_count) VALUES (?, ?, ?, ?)",
        (new_version, now, description, image_count)
    )
    conn.commit()
    conn.close()
    return new_version


def get_all_versions() -> list:
    """Return all dataset versions."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            db = get_db()
            rows = db.dataset_versions.find().sort("created_at", -1)
            return [{"version": r["version"], "created_at": r["created_at"],
                      "description": r.get("description", ""),
                      "image_count": r.get("image_count", 0)} for r in rows]
        except Exception:
            pass

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dataset_versions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"version": r["version"], "created_at": r["created_at"],
             "description": r["description"],
             "image_count": r["image_count"]} for r in rows]


# ---------------------------------------------------------------------------
# Dashboard Statistics
# ---------------------------------------------------------------------------
def get_stats() -> dict:
    """Return dashboard statistics for the dataset creation module."""
    global USE_SQLITE
    if not USE_SQLITE:
        try:
            db = get_db()
            total_images = db.dataset_images.count_documents({})
            pending = db.dataset_images.count_documents({"annotation_status": "Pending"})
            completed = db.dataset_images.count_documents({"annotation_status": "Completed"})
            total_videos = db.videos.count_documents({})
            subjects = db.dataset_images.distinct("subject")
            writers = db.dataset_images.distinct("writer_id")
            return {
                "total_videos": total_videos,
                "total_images": total_images,
                "pending_annotations": pending,
                "completed_annotations": completed,
                "subjects": subjects,
                "writers": writers,
                "current_version": get_current_version(),
            }
        except Exception as e:
            print(f"  MongoDB stats failed: {e}. Switching to SQLite.")
            USE_SQLITE = True
            init_sqlite_db()

    # SQLite fallback
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM videos")
    total_videos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dataset_images")
    total_images = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dataset_images WHERE annotation_status = 'Pending'")
    pending = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dataset_images WHERE annotation_status = 'Completed'")
    completed = cursor.fetchone()[0]
    cursor.execute("SELECT DISTINCT subject FROM dataset_images")
    subjects = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT writer_id FROM dataset_images")
    writers = [r[0] for r in cursor.fetchall()]
    conn.close()
    return {
        "total_videos": total_videos,
        "total_images": total_images,
        "pending_annotations": pending,
        "completed_annotations": completed,
        "subjects": subjects,
        "writers": writers,
        "current_version": get_current_version(),
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("Database initialization successful!")
    print(f"Using SQLite: {USE_SQLITE}")
    stats = get_stats()
    print(f"  Videos:     {stats['total_videos']}")
    print(f"  Images:     {stats['total_images']}")
    print(f"  Pending:    {stats['pending_annotations']}")
    print(f"  Version:    {stats['current_version']}")
