"""
propose_boxes.py
Propose bounding boxes for board images so they can be corrected, not drawn.

Training a detector needs ground-truth boxes, and the dataset has none. Drawing
~400 boxes by hand is slow; this proposes them automatically with classical
computer vision (no model required), writes them into annotations.bbox, and
renders a preview image per board so each proposal can be eyeballed and fixed
in the dashboard.

The proposals are a starting point, not ground truth. Anything written here
leaves the image reviewed=false.

HOW IT PROPOSES
---------------
Chalk on a board is bright strokes on a dark, noisy surface, so:
  1. a white tophat transform keeps thin bright strokes and discards large
     bright areas, so erased smear and lamp glare are removed - a plain Otsu
     threshold keeps the smear and swamps the writing
  2. threshold at the 99th percentile of the residual: only chalk survives
  3. horizontal dilation glues characters into word blobs; contours are
     filtered by size and ink density
  4. fragments on the same line are merged into one box, then sorted into
     reading order (top-to-bottom, left-to-right)

MATCHING TO ANNOTATIONS
-----------------------
Boxes are only written automatically when the number of proposals equals the
number of text-like annotations on that image, so proposal N maps to
annotation N in reading order. When the counts disagree the proposals are
still saved to the preview and the JSON report, but nothing is written to the
database - guessing a mapping would put wrong coordinates on real labels.

USAGE
    python scripts/propose_boxes.py --dry-run
    python scripts/propose_boxes.py --preview-dir runs/boxes
    python scripts/propose_boxes.py --source local --folders boards boards_2
"""

import argparse
import json
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))

# Annotation classes that correspond to a localisable block of writing.
TEXT_LIKE = {"Text", "Header", "Equation", "Code"}


def propose(image_bgr):
    """Return [x_min, y_min, x_max, y_max] line proposals in reading order."""
    import cv2
    import numpy as np

    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # White tophat keeps thin bright strokes (chalk) and removes large bright
    # areas (erased smear, lamp glare). A plain Otsu threshold cannot separate
    # those: smear is brighter than the board but dimmer than a stroke, so it
    # survives global thresholding and swamps the real writing.
    k = max(15, int(min(h, w) * 0.025)) | 1
    tophat = cv2.morphologyEx(
        gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    tophat = cv2.normalize(tophat, None, 0, 255, cv2.NORM_MINMAX)

    # Only the brightest residual is chalk.
    threshold = max(30, int(np.percentile(tophat, 99.0)))
    _, binary = cv2.threshold(tophat, threshold, 255, cv2.THRESH_BINARY)
    binary = cv2.morphologyEx(
        binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    # Glue neighbouring characters into word blobs.
    kernel_w = max(20, w // 28) | 1
    kernel_h = max(3, h // 150) | 1
    glued = cv2.dilate(
        binary, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h)), 2)

    contours, _ = cv2.findContours(glued, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame = float(h * w)
    fragments = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if not (0.0015 * frame <= bw * bh <= 0.6 * frame):
            continue
        if (binary[y:y + bh, x:x + bw] > 0).mean() < 0.015:
            continue           # a box with almost no ink is board texture
        fragments.append([x, y, x + bw, y + bh])

    return group_into_lines(fragments, w, h)


def group_into_lines(boxes, width, height, v_overlap=0.35, h_gap_frac=0.10):
    """
    Merge fragments that belong to the same written line.

    Character-level blobs are merged when their vertical ranges overlap and
    they sit close horizontally, so one equation becomes one box rather than
    eight. Repeats until nothing more merges.
    """
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    merging = True
    while merging:
        merging = False
        grouped, used = [], [False] * len(boxes)
        for i, box in enumerate(boxes):
            if used[i]:
                continue
            current, used[i] = list(box), True
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                other = boxes[j]
                overlap = max(0, min(current[3], other[3]) - max(current[1], other[1]))
                min_height = min(current[3] - current[1], other[3] - other[1])
                if min_height <= 0 or overlap / min_height < v_overlap:
                    continue
                gap = max(other[0] - current[2], current[0] - other[2])
                if gap > width * h_gap_frac:
                    continue
                current = [min(current[0], other[0]), min(current[1], other[1]),
                           max(current[2], other[2]), max(current[3], other[3])]
                used[j], merging = True, True
            grouped.append(current)
        boxes = grouped

    boxes = [b for b in boxes
             if (b[2] - b[0]) > width * 0.05 and (b[3] - b[1]) > height * 0.02]
    # Reading order: rows top-to-bottom, left-to-right within a row.
    boxes.sort(key=lambda b: (round(b[1] / max(height * 0.06, 1)), b[0]))
    return boxes


def to_normalised(box, width, height):
    """[x_min,y_min,x_max,y_max] -> [x_center,y_center,w,h] normalised."""
    x1, y1, x2, y2 = box
    return [round(((x1 + x2) / 2) / width, 6), round(((y1 + y2) / 2) / height, 6),
            round((x2 - x1) / width, 6), round((y2 - y1) / height, 6)]


def draw_preview(image_bgr, boxes, path):
    import cv2
    canvas = image_bgr.copy()
    for i, (x1, y1, x2, y2) in enumerate(boxes, start=1):
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(canvas, str(i), (x1 + 4, max(y1 + 26, 26)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    cv2.imwrite(path, canvas)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["supabase", "local"], default="supabase")
    parser.add_argument("--folders", nargs="*",
                        default=["boards", "boards_2", "boards_3", "boards_4"])
    parser.add_argument("--preview-dir", default="runs/boxes")
    parser.add_argument("--report", default="runs/boxes/proposals.json")
    parser.add_argument("--limit", type=int, default=0, help="0 = all images")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Propose and preview, write nothing to the database.")
    args = parser.parse_args()

    import cv2
    import numpy as np

    os.makedirs(args.preview_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)

    print("=== EchoBoard bounding-box proposer ===")
    records, report = [], []

    if args.source == "supabase":
        import database as db
        import storage
        db.init_db()
        storage.init_storage()
        rows = db.get_dataset_images(limit=100000)
        if args.limit:
            rows = rows[:args.limit]
        for row in rows:
            data = storage.get_image(row.get("image_path", ""))
            if not data:
                continue
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            records.append({"id": row["image_id"], "image": img,
                            "annotations": row.get("annotations") or []})
    else:
        for folder in args.folders:
            labels_path = os.path.join(folder, "labels.json")
            labels = json.load(open(labels_path, encoding="utf-8")) \
                if os.path.isfile(labels_path) else {}
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img = cv2.imread(os.path.join(folder, name))
                if img is None:
                    continue
                entry = labels.get(name, {})
                anns = [{"class": "Text", "text": t} for t in entry.get("lines", [])]
                anns += [{"class": r.get("class", "Text"), "text": r.get("text", "")}
                         for r in entry.get("regions", [])]
                records.append({"id": f"{folder}/{name}", "image": img,
                                "annotations": anns})
                if args.limit and len(records) >= args.limit:
                    break

    print(f"  images: {len(records)}")
    written = matched = mismatched = 0

    for record in records:
        img = record["image"]
        h, w = img.shape[:2]
        boxes = propose(img)
        targets = [a for a in record["annotations"]
                   if a.get("class") in TEXT_LIKE and (a.get("text") or "").strip()]

        fits = len(boxes) == len(targets) and len(boxes) > 0
        status = "matched" if fits else "count-mismatch"
        if fits:
            matched += 1
        else:
            mismatched += 1

        safe = record["id"].replace("/", "_")
        if not args.no_preview:
            draw_preview(img, boxes, os.path.join(args.preview_dir, f"{safe}.jpg"))

        report.append({
            "image_id": record["id"], "width": w, "height": h,
            "proposals": len(boxes), "text_annotations": len(targets),
            "status": status,
            "boxes_pixel": boxes,
            "boxes_norm": [to_normalised(b, w, h) for b in boxes],
        })

        if fits and not args.dry_run and args.source == "supabase":
            import database as db
            client = db.get_client()
            ordered = sorted(record["annotations"],
                             key=lambda a: a.get("annotation_id") or "")
            ordered = [a for a in ordered if a.get("class") in TEXT_LIKE
                       and (a.get("text") or "").strip()]
            for annotation, box in zip(ordered, boxes):
                client.table(db.TABLE_ANNOTATIONS).update(
                    {"bbox": {"pixel": box, "norm": to_normalised(box, w, h)}}
                ).eq("annotation_id", annotation["annotation_id"]).execute()
                written += 1

        print(f"  {record['id']:<28} {len(boxes):>3} proposals / "
              f"{len(targets):>3} annotations  {status}")

    with open(args.report, "w") as fh:
        json.dump(report, fh, indent=1)

    print("\n=== Summary ===")
    print(f"  images processed     : {len(records)}")
    print(f"  counts matched       : {matched}")
    print(f"  counts mismatched    : {mismatched}  (no boxes written - review these)")
    if args.dry_run:
        print("  dry run: nothing written to the database")
    else:
        print(f"  bboxes written       : {written}")
    print(f"  report               : {args.report}")
    if not args.no_preview:
        print(f"  previews             : {args.preview_dir}/")
    print("\n  Proposals are a starting point. Review the previews, correct what is")
    print("  wrong, and only then treat the boxes as ground truth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
