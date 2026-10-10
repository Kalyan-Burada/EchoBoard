"""
export_dataset.py
Fast Multithreaded Dataset Exporter:
Downloads all ECHD dataset images and annotations from Supabase concurrently
into a local cache directory for PyTorch training and evaluation.
"""

import os
import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

import backend.database as db
import backend.storage as storage

DATASET_DIR = os.path.join(REPO_ROOT, "dataset_cache")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")


def _download_single(record):
    image_id = record.get("image_id")
    image_path = record.get("image_path")
    annotations = record.get("annotations", [])
    text = annotations[0].get("text", "") if annotations else ""
    annotation_class = annotations[0].get("class", "Text") if annotations else "Text"

    if not text or not text.strip():
        return None

    safe_fname = f"{image_id}_{os.path.basename(image_path)}"
    local_img_path = os.path.join(IMAGES_DIR, safe_fname)

    if not os.path.exists(local_img_path):
        img_bytes = storage.get_image(image_path)
        if img_bytes:
            with open(local_img_path, "wb") as f:
                f.write(img_bytes)
        else:
            return None

    return {
        "image_id": image_id,
        "image_path": os.path.relpath(local_img_path, DATASET_DIR).replace("\\", "/"),
        "text": text.strip(),
        "class": annotation_class,
        "subject": record.get("subject", "General"),
        "board_type": record.get("board_type", "Blackboard"),
    }


def export_echd_dataset():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    db.init_db()
    storage.init_storage()

    print("Fetching dataset records from Supabase...")
    records = db.get_dataset_images(limit=10000)
    print(f"Total dataset records: {len(records)}")

    dataset_samples = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(_download_single, r) for r in records]
        for f in tqdm(as_completed(futures), total=len(futures), desc="Caching images"):
            res = f.result()
            if res is not None:
                dataset_samples.append(res)

    # Sort deterministically by image_id
    dataset_samples.sort(key=lambda x: x["image_id"])

    manifest_path = os.path.join(DATASET_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(dataset_samples, f, indent=2)

    print(f"\nSuccessfully cached {len(dataset_samples)} annotated images to {DATASET_DIR}")
    print(f"Manifest saved to {manifest_path}")
    return dataset_samples


if __name__ == "__main__":
    export_echd_dataset()
