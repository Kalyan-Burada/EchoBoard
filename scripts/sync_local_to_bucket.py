"""
sync_local_to_bucket.py
Migrate locally stored dataset images into the shared S3-compatible bucket.

Use this once after switching STORAGE_BACKEND from 'local' to 's3': any
images previously written to dataset/echoboard-dataset/ are uploaded to the
shared bucket so collaborators can read them. Objects that already exist in
the bucket are skipped, so the script is safe to re-run.

Usage:
    python scripts/sync_local_to_bucket.py             # upload missing images
    python scripts/sync_local_to_bucket.py --dry-run   # report only
"""

import argparse
import io
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))

import storage  # noqa: E402


def collect_local_images(local_dir):
    """Return (object_path, absolute_path) pairs for every local image."""
    found = []
    for root, _dirs, files in os.walk(local_dir):
        for name in files:
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, local_dir).replace(os.sep, "/")
                found.append((rel_path, full_path))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be uploaded without writing to the bucket.",
    )
    args = parser.parse_args()

    print("=== EchoBoard local-to-bucket sync ===")

    if storage.STORAGE_BACKEND != "s3":
        print(
            f"\n  STORAGE_BACKEND is '{storage.STORAGE_BACKEND}', not 's3'.\n"
            "  Set STORAGE_BACKEND=s3 in .env before syncing.\n"
            "  See docs/SHARED_SETUP.md."
        )
        return 1

    try:
        storage.init_storage()
    except storage.StorageConfigError as exc:
        print(f"\n  Storage is not usable:\n  {exc}")
        return 1

    local_dir = storage.LOCAL_DATASET_DIR
    if not os.path.isdir(local_dir):
        print(f"\n  No local dataset directory at {local_dir} — nothing to sync.")
        return 0

    print(f"\nScanning {local_dir} ...")
    local_files = collect_local_images(local_dir)
    print(f"Found {len(local_files)} local image(s).")

    client = storage._get_s3_client()
    bucket = storage.S3_BUCKET

    uploaded = skipped = failed = 0
    for object_path, full_path in local_files:
        try:
            client.stat_object(bucket, object_path)
            skipped += 1
            continue
        except Exception:
            pass  # Object is absent; upload it below.

        if args.dry_run:
            print(f"  would upload: {object_path}")
            uploaded += 1
            continue

        try:
            with open(full_path, "rb") as fh:
                data = fh.read()
            client.put_object(
                bucket,
                object_path,
                io.BytesIO(data),
                length=len(data),
                content_type=storage._content_type(object_path),
            )
            print(f"  uploaded: {object_path}")
            uploaded += 1
        except Exception as exc:
            print(f"  FAILED:   {object_path} ({exc})")
            failed += 1

    verb = "would upload" if args.dry_run else "uploaded"
    print("\n=== Sync complete ===")
    print(f"  {verb}:            {uploaded}")
    print(f"  already in bucket: {skipped}")
    print(f"  failed:            {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
