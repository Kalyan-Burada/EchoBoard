"""
sync_local_to_minio.py
Utility script to synchronize all locally stored dataset images to the remote MinIO bucket.
Run this script once your Tailscale connection is active to upload folders like lecture_007.
"""
import os
import sys

# Ensure backend folder is in path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, 'backend'))

import storage
from minio import Minio

def main():
    print("=== EchoBoard Dataset Sync to MinIO ===")
    
    # 1. Connect to MinIO
    try:
        print(f"Connecting to MinIO at {storage.MINIO_ENDPOINT}...")
        client = storage._get_minio_client()
        
        # Test connection
        if not client.bucket_exists(storage.MINIO_BUCKET):
            client.make_bucket(storage.MINIO_BUCKET)
            print(f"Created bucket '{storage.MINIO_BUCKET}'")
        else:
            print(f"Successfully connected to bucket '{storage.MINIO_BUCKET}'!")
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to MinIO ({e}).")
        print("Please check your Tailscale connection and ensure your teammate's MinIO server is running.")
        return

    # 2. Scan local dataset
    local_dir = storage.LOCAL_DATASET_DIR
    if not os.path.exists(local_dir):
        print(f"No local images found in {local_dir}")
        return

    print(f"\nScanning local files in {local_dir}...")
    local_files = []
    for root, _, files in os.walk(local_dir):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, local_dir).replace(os.sep, '/')
                local_files.append((rel_path, full_path))

    print(f"Found {len(local_files)} local images.")

    # 3. Upload to MinIO
    uploaded_count = 0
    skipped_count = 0
    for rel_path, full_path in local_files:
        try:
            # Check if file already exists in MinIO to avoid re-uploading
            try:
                client.stat_object(storage.MINIO_BUCKET, rel_path)
                skipped_count += 1
                continue
            except Exception:
                # File doesn't exist, proceed to upload
                pass
            
            print(f"Uploading: {rel_path} ...", end="", flush=True)
            with open(full_path, "rb") as f_data:
                data_bytes = f_data.read()
                import io
                client.put_object(
                    storage.MINIO_BUCKET,
                    rel_path,
                    io.BytesIO(data_bytes),
                    length=len(data_bytes),
                    content_type="image/jpeg" if not rel_path.endswith('.png') else "image/png"
                )
            print(" ✅ Uploaded")
            uploaded_count += 1
        except Exception as upload_err:
            print(f" ❌ Failed ({upload_err})")

    print(f"\n=== Sync Complete ===")
    print(f"Successfully uploaded: {uploaded_count}")
    print(f"Already in MinIO (skipped): {skipped_count}")

if __name__ == "__main__":
    main()
