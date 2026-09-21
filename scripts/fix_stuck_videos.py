"""
fix_stuck_videos.py
Clear videos left with processing=True in Supabase.

A video row stays flagged as processing if the backend was interrupted
mid-extraction (a crash, a restart, or a closed terminal). The dashboard
then shows it as permanently in-progress. This script clears the flag
without touching the extracted keyframes or their metadata.

Usage:
    python scripts/fix_stuck_videos.py             # clear stuck flags
    python scripts/fix_stuck_videos.py --dry-run   # report only
"""

import argparse
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))

import database as db  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List stuck videos without modifying them.",
    )
    args = parser.parse_args()

    print("=== EchoBoard stuck-video repair ===")

    try:
        db.init_db()
    except db.DatabaseConfigError as exc:
        print(f"\n  Database is not usable:\n  {exc}")
        return 1

    client = db.get_client()
    stuck = (
        client.table(db.TABLE_VIDEOS)
        .select("*")
        .eq("processing", True)
        .execute()
        .data
        or []
    )
    print(f"\nFound {len(stuck)} video(s) flagged processing=True.")

    for video in stuck:
        label = video.get("filename") or video["id"]
        if args.dry_run:
            print(f"  would clear: {label}")
            continue
        db.set_video_processing(video["id"], False)
        print(f"  cleared: {label}")

    videos = client.table(db.TABLE_VIDEOS).select("*").execute().data or []
    print(f"\nAll videos ({len(videos)}):")
    for video in videos:
        print(
            f"  {video.get('filename', '')} | processing={video.get('processing')} "
            f"| fps={video.get('fps', 0)} | total_frames={video.get('total_frames', 0)}"
        )

    stats = db.get_stats()
    print(f"\nTotal dataset images: {stats['total_images']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
