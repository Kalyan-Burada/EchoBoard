"""
database.py
EchoBoard - MongoDB Atlas Database Layer

Stores every captured "board keyframe" (a moment where the board content
changed and then settled) along with metadata and the keyframe image itself
(base64-encoded) in MongoDB Atlas.

Setup:
  1. Create a free cluster at https://cloud.mongodb.com
  2. Create a database user (username + password)
  3. Whitelist your IP (or use 0.0.0.0/0 for development)
  4. Copy your connection string and set MONGO_URI below or as an env variable

Uses pymongo for the connection. All images are stored as base64 strings
inside the document, so no local file storage is needed for persistence.
"""

import os
import base64
import certifi
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# CONNECTION CONFIG — Loaded from .env file
# ---------------------------------------------------------------------------
MONGO_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DATABASE_NAME", "EchoBoardDB")

if not MONGO_URI:
    raise RuntimeError(
        "MONGODB_URI not set! Create a .env file with your MongoDB Atlas connection string."
    )

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------
_client = None


def get_db():
    """Return the MongoDB database handle, creating the client on first call."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    return _client[DB_NAME]


def init_db():
    """Create indexes for fast queries. Safe to call every run."""
    db = get_db()

    # Index for timeline queries per video
    db.keyframes.create_index(
        [("video_id", ASCENDING), ("timestamp_sec", ASCENDING)]
    )
    # Index for text search on OCR content
    db.keyframes.create_index([("ocr_text", ASCENDING)])
    # Index for sorting videos by upload date
    db.videos.create_index([("uploaded_at", DESCENDING)])

    print(f"Connected to MongoDB Atlas — database: '{DB_NAME}'")


# ---------------------------------------------------------------------------
# Video CRUD
# ---------------------------------------------------------------------------
def insert_video(filename, duration_sec, total_frames, fps):
    """Insert a new video record and return its ID as a string."""
    db = get_db()
    result = db.videos.insert_one({
        "filename": filename,
        "uploaded_at": datetime.utcnow().isoformat(),
        "duration_sec": duration_sec,
        "total_frames": total_frames,
        "fps": fps,
    })
    return str(result.inserted_id)


def get_all_videos():
    """Return all videos as a list of dicts, newest first."""
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
        })
    return videos


# ---------------------------------------------------------------------------
# Keyframe CRUD
# ---------------------------------------------------------------------------
def insert_keyframe(video_id, frame_number, timestamp_sec, image_path,
                    change_score, ocr_text=""):
    """
    Insert a keyframe document into MongoDB.
    Reads the image file from disk, encodes it as base64, and stores it
    inside the document so no local file storage is needed for persistence.
    """
    db = get_db()

    # Read the image file and encode as base64 for cloud storage
    image_b64 = ""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

    result = db.keyframes.insert_one({
        "video_id": video_id,
        "frame_number": frame_number,
        "timestamp_sec": timestamp_sec,
        "image_b64": image_b64,
        "change_score": change_score,
        "ocr_text": ocr_text or "",
        "created_at": datetime.utcnow().isoformat(),
    })
    return str(result.inserted_id)


def get_keyframes_for_video(video_id):
    """
    Return all keyframes for a given video, sorted by timestamp.
    Each keyframe dict includes 'image_bytes' (decoded from base64)
    ready for direct display in Streamlit.
    """
    db = get_db()
    rows = db.keyframes.find(
        {"video_id": video_id}
    ).sort("timestamp_sec", ASCENDING)

    keyframes = []
    for kf in rows:
        entry = {
            "id": str(kf["_id"]),
            "video_id": kf["video_id"],
            "frame_number": kf["frame_number"],
            "timestamp_sec": kf["timestamp_sec"],
            "change_score": kf.get("change_score"),
            "ocr_text": kf.get("ocr_text", ""),
            "created_at": kf.get("created_at", ""),
        }
        # Decode base64 image to bytes for Streamlit display
        if kf.get("image_b64"):
            entry["image_bytes"] = base64.b64decode(kf["image_b64"])
        keyframes.append(entry)
    return keyframes


def search_keyframes(query):
    """
    Search keyframes by OCR text (case-insensitive regex match).
    Returns results with the parent video's filename attached.
    """
    db = get_db()
    rows = db.keyframes.find({
        "ocr_text": {"$regex": query, "$options": "i"}
    }).sort("timestamp_sec", ASCENDING)

    results = []
    video_cache = {}  # cache video lookups to avoid repeated queries
    for kf in rows:
        vid = kf["video_id"]
        if vid not in video_cache:
            v = db.videos.find_one({"_id": ObjectId(vid)})
            video_cache[vid] = v["filename"] if v else "Unknown"

        entry = {
            "id": str(kf["_id"]),
            "video_filename": video_cache[vid],
            "timestamp_sec": kf["timestamp_sec"],
            "frame_number": kf.get("frame_number"),
            "ocr_text": kf.get("ocr_text", ""),
        }
        if kf.get("image_b64"):
            entry["image_bytes"] = base64.b64decode(kf["image_b64"])
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Single-record lookups, deletion, stats (used by FastAPI)
# ---------------------------------------------------------------------------
def get_video_by_id(video_id):
    """Return a single video dict, or None."""
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
    }


def get_keyframe_by_id(kf_id):
    """Return a single keyframe dict (with image_bytes), or None."""
    db = get_db()
    kf = db.keyframes.find_one({"_id": ObjectId(kf_id)})
    if not kf:
        return None
    entry = {
        "id": str(kf["_id"]),
        "video_id": kf["video_id"],
        "frame_number": kf["frame_number"],
        "timestamp_sec": kf["timestamp_sec"],
        "change_score": kf.get("change_score"),
        "ocr_text": kf.get("ocr_text", ""),
    }
    if kf.get("image_b64"):
        entry["image_bytes"] = base64.b64decode(kf["image_b64"])
    return entry


def delete_video(video_id):
    """Delete a video and all its keyframes."""
    db = get_db()
    db.keyframes.delete_many({"video_id": video_id})
    db.videos.delete_one({"_id": ObjectId(video_id)})


def get_stats():
    """Return dashboard statistics."""
    db = get_db()
    return {
        "total_videos": db.videos.count_documents({}),
        "total_keyframes": db.keyframes.count_documents({}),
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("MongoDB Atlas connection successful!")
    # Quick connectivity check
    db = get_db()
    print(f"  Videos collection count:    {db.videos.count_documents({})}")
    print(f"  Keyframes collection count: {db.keyframes.count_documents({})}")
