"""
ingest_folder.py
Bulk-ingest a folder of board images into the ECHD dataset.

Walks a directory, stores each image in Supabase Storage, registers its
metadata (including provenance and measured quality), and optionally
attaches annotations supplied in a labels JSON file.

This is the batch alternative to uploading through the dashboard: it does
not time out on large folders, it is resumable (already-ingested images are
skipped), and it records the provenance fields the browser upload leaves
empty.

Labels file format — a JSON object keyed by image filename:

    {
      "board_001.jpg": {
        "lines": ["Newton's Laws", "F = ma"],
        "regions": [
          {"class": "Header",   "text": "Newton's Laws", "confidence": 0.9},
          {"class": "Equation", "text": "F = ma", "latex": "F = ma"}
        ],
        "lighting_score": 70,
        "occluded": false,
        "duplicate": false
      }
    }

Use "lines" for a simple line-per-entry transcription, or "regions" for
full control over class/bbox/latex/confidence. Both may be given. Every
annotation is written with reviewed=false: machine-produced labels are a
first pass for a human to verify in the dashboard, never ground truth.

An entry may also override the run-wide provenance for that one image with
"subject", "board_type" or "writer_id" — useful when a folder mixes
blackboard photos with whiteboard video frames, or several writers.

Usage:
    python scripts/ingest_folder.py ./boards \
        --subject Physics --writer-id teacher_a \
        --sequence-id physics_lec1 --labels labels.json

    python scripts/ingest_folder.py ./boards --subject Physics --dry-run
"""

import argparse
import json
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))

import database as db  # noqa: E402
import storage  # noqa: E402

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def measure(path):
    """Return (width, height, blur_score). Blur is variance of the Laplacian."""
    try:
        import cv2

        img = cv2.imread(path)
        if img is None:
            return 0, 0, 0.0
        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return width, height, round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
    except Exception:
        return 0, 0, 0.0


def collect(folder):
    found = []
    for root, _dirs, files in os.walk(folder):
        for name in sorted(files):
            if name.lower().endswith(IMAGE_EXTENSIONS):
                found.append(os.path.join(root, name))
    return found


def build_annotations(label):
    """Turn a labels-file entry into annotation dicts."""
    annotations = []
    for line in label.get("lines") or []:
        if str(line).strip():
            annotations.append({
                "class": "Text",
                "text": str(line),
                "confidence": label.get("confidence", 0.9),
            })
    for region in label.get("regions") or []:
        annotations.append({
            "class": region.get("class", "Text"),
            "text": region.get("text", ""),
            "bbox": region.get("bbox") or [],
            "latex": region.get("latex", ""),
            "confidence": region.get("confidence", label.get("confidence", 0.9)),
        })
    # A whole-board transcription is a useful single training target
    # alongside the per-line ones.
    lines = [str(l) for l in (label.get("lines") or []) if str(l).strip()]
    if len(lines) > 1:
        annotations.append({
            "class": "FullBoard",
            "text": " ".join(lines),
            "confidence": label.get("confidence", 0.9),
        })
    return annotations


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="Directory of images to ingest.")
    parser.add_argument("--subject", default="General")
    parser.add_argument("--board-type", default="Blackboard")
    parser.add_argument("--writer-id", default="unknown")
    parser.add_argument("--sequence-id", default=None,
                        help="Defaults to the folder name.")
    parser.add_argument("--labels", default=None,
                        help="JSON file mapping filename -> annotations.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be ingested, write nothing.")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print(f"  Not a directory: {args.folder}")
        return 1

    sequence_id = args.sequence_id or os.path.basename(
        os.path.normpath(args.folder)
    ).strip().lower().replace(" ", "_") or "uploads"

    labels = {}
    if args.labels:
        if not os.path.isfile(args.labels):
            print(f"  Labels file not found: {args.labels}")
            return 1
        with open(args.labels, encoding="utf-8") as fh:
            labels = json.load(fh)

    images = collect(args.folder)
    print(f"=== EchoBoard folder ingest ===")
    print(f"  folder:      {args.folder}")
    print(f"  images:      {len(images)}")
    print(f"  subject:     {args.subject}")
    print(f"  board_type:  {args.board_type}")
    print(f"  writer_id:   {args.writer_id}")
    print(f"  sequence_id: {sequence_id}")
    print(f"  labels:      {args.labels or '(none)'}")

    if args.dry_run:
        for path in images:
            width, height, blur = measure(path)
            label = labels.get(os.path.basename(path), {})
            n = len(build_annotations(label))
            print(f"  would ingest {os.path.basename(path)} "
                  f"{width}x{height} blur={blur} annotations={n}")
        print(f"\n  dry run: {len(images)} image(s), nothing written.")
        return 0

    try:
        db.init_db()
        storage.init_storage()
    except (db.DatabaseConfigError, storage.StorageConfigError) as exc:
        print(f"\n  Not usable:\n  {exc}")
        return 1

    # Resume support: skip images already registered for this sequence.
    existing = {
        row.get("image_name")
        for row in db.get_dataset_images(limit=100000, sequence_id=sequence_id)
    }

    ingested = skipped = failed = 0
    safe_subject = "".join(
        c if c.isalnum() or c in " _-" else "_" for c in args.subject
    ).strip().lower().replace(" ", "_") or "general"

    for index, path in enumerate(images, start=1):
        basename = os.path.basename(path)
        fname = f"board_{index:04d}{os.path.splitext(basename)[1].lower()}"

        if fname in existing:
            skipped += 1
            continue

        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if not data:
                print(f"  skip (empty): {basename}")
                skipped += 1
                continue

            width, height, blur = measure(path)
            object_path = storage.store_image(data, safe_subject, sequence_id, fname)

            label = labels.get(basename, {})
            # A folder can mix media: per-image overrides keep a whiteboard
            # video frame from being recorded as a blackboard photo.
            record = db.insert_dataset_image(
                image_name=fname,
                image_path=object_path,
                width=width,
                height=height,
                format_type=os.path.splitext(fname)[1].lstrip(".").lower(),
                size_kb=max(1, len(data) // 1024),
                sequence_id=sequence_id,
                subject=label.get("subject", args.subject),
                board_type=label.get("board_type", args.board_type),
                writer_id=label.get("writer_id", args.writer_id),
                uploaded_by=args.writer_id,
                frame_index=index,
            )
            image_id = record["image_id"]

            annotations = build_annotations(label)
            if annotations:
                # reviewed=False: these are machine labels awaiting a human.
                db.insert_annotations(image_id, annotations, mark_reviewed=False)

            db.update_image_quality(
                image_id,
                blur_score=blur,
                lighting_score=label.get("lighting_score"),
                duplicate=label.get("duplicate"),
                occluded=label.get("occluded"),
                selected=(not label["duplicate"]) if "duplicate" in label else None,
            )

            summary = (label.get("lines") or [""])[0][:34]
            print(f"  {image_id}  {basename} -> {object_path}  "
                  f"{width}x{height} blur={blur:.0f} ann={len(annotations)}"
                  + (f'  "{summary}..."' if summary else ""))
            ingested += 1
        except Exception as exc:
            print(f"  FAILED: {basename} ({exc})")
            failed += 1

    print("\n=== Ingest complete ===")
    print(f"  ingested: {ingested}")
    print(f"  skipped:  {skipped}")
    print(f"  failed:   {failed}")
    if ingested:
        print(f"\n  {db.get_stats()}")
        print("\n  Annotations are marked reviewed=false. Verify them in the")
        print("  dashboard's Dataset Explorer before training on them.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
