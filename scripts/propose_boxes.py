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

# Detector class vocabulary (the six categories in the project spec). The
# order defines the numeric class id written to YOLO label files.
DETECTOR_CLASSES = ["Text", "Heading", "Formula", "Equation", "Diagram", "Table"]

# Dataset annotation classes -> detector classes. Rule and Illegible have no
# detector equivalent and are skipped.
CLASS_MAP = {
    "Text": "Text",
    "Header": "Heading",
    "Equation": "Equation",
    "Code": "Text",
    "Diagram": "Diagram",
}


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

    fragments = [f for f in fragments if _is_board_content(image_bgr, f)]
    blocks = group_into_lines(fragments, w, h)

    # Sloped writing merges into multi-line blocks; cut those back into lines
    # so each proposal is something a CRNN can actually read.
    lines = []
    for block in blocks:
        lines.extend(split_into_lines(binary, block, image_height=h))
    lines.sort(key=lambda b: (round(b[1] / max(h * 0.06, 1)), b[0]))
    return lines


def _is_board_content(image_bgr, box, warm_hue=(5, 35), saturation_limit=70):
    """
    False when a box is a warm-coloured object rather than chalk on a board.

    The tophat finds thin bright strokes, and a sunlit door frame, a desk edge
    or a window reveal all qualify: bright, narrow, high local contrast. They
    differ in colour, not in shape -- chalk is near-grey, so it has very low
    saturation whatever the board's own tint, while wood and skin are strongly
    saturated in the orange band. Judging by the bright pixels only keeps the
    dark board around a stroke from diluting the measurement.
    """
    import cv2
    import numpy as np

    x1, y1, x2, y2 = box
    crop = image_bgr[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return True

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    bright = value >= max(60, int(np.percentile(value, 85)))
    if bright.sum() < 20:
        return True

    hue = hsv[:, :, 0][bright]
    saturation = hsv[:, :, 1][bright]
    warm = ((hue >= warm_hue[0]) & (hue <= warm_hue[1])).mean()
    return not (warm > 0.6 and float(np.median(saturation)) > saturation_limit)


def split_into_lines(binary, box, min_gap_frac=0.06, min_height_frac=0.012,
                     min_block_frac=0.2, image_height=None):
    """
    Cut a block that holds several written lines into one box per line.

    group_into_lines merges fragments whose vertical ranges overlap, which is
    right for a level line but wrong for writing that slopes: each line
    overlaps the next, so three lines collapse into one block. A CRNN
    transcribes a single line at a time, so a block has to be cut back apart
    before it can be read.

    The cut is made on the horizontal projection of the ink: rows holding ink
    form bands, and a run of empty rows between them is a line break. Each
    band is then tightened to the columns that actually hold ink, so a short
    line does not inherit the block's full width.
    """
    import numpy as np

    x1, y1, x2, y2 = box
    region = binary[max(0, y1):y2, max(0, x1):x2]
    if region.size == 0:
        return [list(box)]

    # A block too short to hold two lines is a word or a single character, and
    # the blank row inside a '2' or an '=' reads exactly like a line break on
    # the projection. Leaving short blocks whole is the only way to tell the
    # two apart without knowing the writing's size.
    if image_height and (y2 - y1) < image_height * min_block_frac:
        return [list(box)]

    rows = (region > 0).sum(axis=1)
    if not rows.any():
        return [list(box)]

    # The blank run that marks a line break is a fraction of the block, not
    # of a line: lines sit closer together than a quarter of the block they
    # form, so a larger threshold never cuts anything.
    # A row counts as ink when it carries a real share of the busiest row,
    # which ignores the stray pixels thresholding leaves between lines.
    ink = rows > max(1, rows.max() * 0.08)
    height = y2 - y1
    min_gap = max(3, int(height * min_gap_frac))
    min_height = max(3, int((image_height or height) * min_height_frac))

    bands, start = [], None
    gap = 0
    for index, has_ink in enumerate(ink):
        if has_ink:
            if start is None:
                start = index
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                bands.append((start, index - gap + 1))
                start, gap = None, 0
    if start is not None:
        bands.append((start, len(ink)))

    bands = [(a, b) for a, b in bands if b - a >= min_height]
    if len(bands) < 2:
        return [list(box)]

    # A band far shorter than the tallest is a broken-off stroke, not a line
    # of its own -- splitting it out would undo the fragment merge. Absorb it
    # into the band it sits closest to.
    tallest = max(b - a for a, b in bands)
    lines_only = [(a, b) for a, b in bands if (b - a) >= tallest * 0.4]
    for a, b in bands:
        if (b - a) >= tallest * 0.4:
            continue
        index = min(range(len(lines_only)),
                    key=lambda i: min(abs(lines_only[i][0] - b),
                                      abs(a - lines_only[i][1])))
        host = lines_only[index]
        lines_only[index] = (min(host[0], a), max(host[1], b))
    bands = sorted(lines_only)
    if len(bands) < 2:
        return [list(box)]

    lines = []
    for top, bottom in bands:
        columns = (region[top:bottom] > 0).sum(axis=0)
        filled = np.where(columns > 0)[0]
        if filled.size == 0:
            continue
        lines.append([x1 + int(filled[0]), y1 + top,
                      x1 + int(filled[-1]) + 1, y1 + bottom])
    return lines or [list(box)]


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

    boxes = merge_overlapping(boxes)
    boxes = [b for b in boxes
             if (b[2] - b[0]) > width * 0.05 and (b[3] - b[1]) > height * 0.02]
    # Reading order: rows top-to-bottom, left-to-right within a row.
    boxes.sort(key=lambda b: (round(b[1] / max(height * 0.06, 1)), b[0]))
    return boxes

def merge_overlapping(boxes, containment=0.6, min_intersection=0.15):
    """
    Absorb fragments that overlap a box they belong to.

    group_into_lines joins fragments that sit side by side on a line, but
    thresholding also splits a single stroke vertically -- the lower curve of
    a tall letter breaks away and lands partly inside the box for its own
    line. Those fragments overlap in both axes, which distinct lines of
    writing almost never do, so an overlap test separates the two cases.

    Merged when either box is mostly contained in the other, or when the
    intersection is a meaningful share of the smaller box. Repeats until
    nothing more merges.
    """
    boxes = [list(b) for b in boxes]
    merging = True
    while merging:
        merging = False
        merged, used = [], [False] * len(boxes)
        for i, box in enumerate(boxes):
            if used[i]:
                continue
            current, used[i] = list(box), True
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                other = boxes[j]
                dx = min(current[2], other[2]) - max(current[0], other[0])
                dy = min(current[3], other[3]) - max(current[1], other[1])
                if dx <= 0 or dy <= 0:
                    continue
                intersection = dx * dy
                area_current = (current[2] - current[0]) * (current[3] - current[1])
                area_other = (other[2] - other[0]) * (other[3] - other[1])
                smaller = min(area_current, area_other)
                if smaller <= 0:
                    continue
                share = intersection / smaller
                if share < min_intersection and share < containment:
                    continue
                current = [min(current[0], other[0]), min(current[1], other[1]),
                           max(current[2], other[2]), max(current[3], other[3])]
                used[j], merging = True, True
            merged.append(current)
        boxes = merged
    return boxes


def to_normalised(box, width, height):
    """[x_min,y_min,x_max,y_max] -> [x_center,y_center,w,h] normalised."""
    x1, y1, x2, y2 = box
    return [round(((x1 + x2) / 2) / width, 6), round(((y1 + y2) / 2) / height, 6),
            round((x2 - x1) / width, 6), round((y2 - y1) / height, 6)]


def write_yolo_labels(out_dir, image_name, image_bgr, boxes, annotation_classes):
    """
    Write a YOLO label file beside a copy of the image.

    LabelImg and most annotation tools open a folder and load any label file
    matching the image name, so exporting here means every image opens with
    its boxes already drawn — correcting them is far faster than drawing
    from scratch.

    Format per line: <class_id> <x_center> <y_center> <width> <height>,
    all normalised to [0, 1].
    """
    import cv2

    os.makedirs(out_dir, exist_ok=True)
    cv2.imwrite(os.path.join(out_dir, image_name), image_bgr)

    h, w = image_bgr.shape[:2]
    stem = os.path.splitext(image_name)[0]
    with open(os.path.join(out_dir, f"{stem}.txt"), "w") as fh:
        for i, box in enumerate(boxes):
            # Use the matching annotation's class when we have one, else Text:
            # the class is the cheapest thing to fix in the editor.
            name = annotation_classes[i] if i < len(annotation_classes) else "Text"
            name = CLASS_MAP.get(name, "Text")
            class_id = DETECTOR_CLASSES.index(name)
            xc, yc, bw, bh = to_normalised(box, w, h)
            fh.write(f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")

    classes_path = os.path.join(out_dir, "classes.txt")
    if not os.path.exists(classes_path):
        with open(classes_path, "w") as fh:
            fh.write("\n".join(DETECTOR_CLASSES) + "\n")


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
    parser.add_argument("--export-yolo", metavar="DIR", default=None,
                        help="Also write images + YOLO label files to DIR, so an "
                             "editor such as labelImg opens them with boxes "
                             "already drawn for correction.")
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
        if args.export_yolo:
            write_yolo_labels(args.export_yolo, safe if safe.endswith((".jpg", ".png"))
                              else f"{safe}.jpg", img, boxes,
                              [a.get("class", "Text") for a in targets])
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
    if args.export_yolo:
        print(f"  YOLO export          : {args.export_yolo}/  "
              f"(open with: labelImg {args.export_yolo})")
    print("\n  Proposals are a starting point. Review the previews, correct what is")
    print("  wrong, and only then treat the boxes as ground truth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
