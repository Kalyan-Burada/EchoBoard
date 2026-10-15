"""
build_crops.py
Build the labelled crop dataset for the region classifier.

Runs the box proposer over every board, cuts each proposed region out, and
files it under crops/<class>/. Classes come from the board's own annotations:
when every text annotation on an image is the same class, each crop from it
inherits that class, so no manual labelling is needed. Images mixing classes
are skipped - there is no reliable way to say which crop is which.

USAGE
    python scripts/build_crops.py --source local \
        --folders boards boards_2 boards_3 boards_4 --out crops
    python scripts/build_crops.py --out crops          # from Supabase
"""

import argparse
import json
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))
sys.path.insert(0, script_dir)

from propose_boxes import propose, TEXT_LIKE, CLASS_MAP  # noqa: E402

PAD = 0.04          # fraction of box size added as margin, so strokes are not clipped


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["supabase", "local"], default="supabase")
    parser.add_argument("--folders", nargs="*",
                        default=["boards", "boards_2", "boards_3", "boards_4"])
    parser.add_argument("--out", default="crops")
    parser.add_argument("--min-size", type=int, default=24,
                        help="skip crops smaller than this in either dimension")
    args = parser.parse_args()

    import cv2
    import numpy as np

    records = []
    if args.source == "supabase":
        import database as db
        import storage
        db.init_db(); storage.init_storage()
        for row in db.get_dataset_images(limit=100000):
            data = storage.get_image(row.get("image_path", ""))
            if not data:
                continue
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            classes = {a.get("class") for a in (row.get("annotations") or [])
                       if a.get("class") in TEXT_LIKE and (a.get("text") or "").strip()}
            records.append((row["image_id"], img, classes))
    else:
        for folder in args.folders:
            path = os.path.join(folder, "labels.json")
            labels = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img = cv2.imread(os.path.join(folder, name))
                if img is None:
                    continue
                entry = labels.get(name, {})
                classes = {"Text"} if entry.get("lines") else set()
                classes |= {r.get("class", "Text") for r in entry.get("regions", [])
                            if r.get("class") in TEXT_LIKE and (r.get("text") or "").strip()}
                classes = {c for c in classes if c in TEXT_LIKE}
                records.append((f"{folder}/{name}", img, classes))

    print("=== EchoBoard crop builder ===")
    print(f"  images: {len(records)}")

    written, skipped_mixed, skipped_small = 0, 0, 0
    per_class = {}
    manifest = []

    for image_id, img, classes in records:
        if len(classes) != 1:
            skipped_mixed += 1
            continue
        label = CLASS_MAP.get(next(iter(classes)), "Text")
        h, w = img.shape[:2]
        boxes = propose(img)
        out_dir = os.path.join(args.out, label)
        os.makedirs(out_dir, exist_ok=True)

        for i, (x1, y1, x2, y2) in enumerate(boxes, start=1):
            px, py = int((x2 - x1) * PAD), int((y2 - y1) * PAD)
            cx1, cy1 = max(0, x1 - px), max(0, y1 - py)
            cx2, cy2 = min(w, x2 + px), min(h, y2 + py)
            crop = img[cy1:cy2, cx1:cx2]
            if crop.shape[0] < args.min_size or crop.shape[1] < args.min_size:
                skipped_small += 1
                continue
            safe = image_id.replace("/", "_").rsplit(".", 1)[0]
            name = f"{safe}_r{i:02d}.jpg"
            cv2.imwrite(os.path.join(out_dir, name), crop)
            # source board recorded so training can split by board, not by crop
            manifest.append({"file": f"{label}/{name}", "class": label,
                             "source_image": image_id,
                             "box": [cx1, cy1, cx2, cy2]})
            per_class[label] = per_class.get(label, 0) + 1
            written += 1

    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    print(f"\n  crops written       : {written}")
    for label in sorted(per_class):
        print(f"    {label:<10} {per_class[label]:>4}")
    print(f"  skipped (mixed class): {skipped_mixed} images")
    print(f"  skipped (too small)  : {skipped_small} crops")
    print(f"  manifest             : {os.path.join(args.out, 'manifest.json')}")
    print(f"\n  To add classes the auto-labeller cannot reach (Diagram, Heading),")
    print(f"  make {args.out}/Diagram/ and move crops into it by hand, then re-run")
    print(f"  training - it reads whatever folders exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
