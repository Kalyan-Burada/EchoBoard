"""Fix stuck videos that have processing=True in MongoDB."""
import sys, os
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, 'backend'))
from database import get_db
from bson import ObjectId

db = get_db()

# Find all stuck videos
stuck = list(db.videos.find({"processing": True}))
print(f"Found {len(stuck)} stuck videos with processing=True")

# Fix them one by one
for v in stuck:
    db.videos.update_one(
        {"_id": v["_id"]},
        {"$set": {"processing": False}}
    )
    print(f"  Fixed: {v['filename']}")

# Verify
remaining = db.videos.count_documents({"processing": True})
print(f"\nRemaining stuck: {remaining}")

# Show all videos
all_videos = list(db.videos.find())
print(f"\nAll videos ({len(all_videos)}):")
for v in all_videos:
    print(f"  {v['filename']} | processing={v.get('processing', False)} | fps={v.get('fps',0)} | total_frames={v.get('total_frames',0)}")

# Show dataset images count
total_images = db.dataset_images.count_documents({})
print(f"\nTotal dataset images: {total_images}")
