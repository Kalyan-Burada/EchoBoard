"""
yolo_to_labelstudio.py
Convert a YOLO label folder into a Label Studio import file with the boxes
attached as predictions.

Importing the images alone would open every board with a blank canvas, losing
the proposals from propose_boxes.py. Label Studio shows boxes that arrive as
"predictions", so this emits one task per image with its proposed boxes
pre-drawn, ready to drag, delete or relabel.

Label Studio measures boxes in PERCENT of image size from the top-left
corner, while YOLO uses normalised centre coordinates, so the geometry is
converted here.

USAGE
    python scripts/yolo_to_labelstudio.py --yolo-dir dataset_yolo \
        --out dataset_yolo/labelstudio_tasks.json

Then, in a terminal where Label Studio is NOT already running:

    export LOCAL_FILES_SERVING_ENABLED=true
    export LOCAL_FILES_DOCUMENT_ROOT=/absolute/path/to/dataset_yolo
    label-studio start

and in the UI: create a project, choose the Object Detection with Bounding
Boxes template, paste the labelling config this script prints, then import
labelstudio_tasks.json.
"""

import argparse
import json
import os
import sys


def build_config(classes):
    """Label Studio labelling config for these classes."""
    colours = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#A66CFF", "#FF9F45"]
    labels = "\n".join(
        f'    <Label value="{name}" background="{colours[i % len(colours)]}"/>'
        for i, name in enumerate(classes))
    return (f'<View>\n  <Image name="image" value="$image"/>\n'
            f'  <RectangleLabels name="label" toName="image">\n{labels}\n'
            f'  </RectangleLabels>\n</View>')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yolo-dir", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--config-out", default=None,
                        help="Where to write the labelling config (default: "
                             "<yolo-dir>/labelstudio_config.xml)")
    args = parser.parse_args()

    yolo_dir = os.path.abspath(args.yolo_dir)
    out_path = args.out or os.path.join(yolo_dir, "labelstudio_tasks.json")
    config_path = args.config_out or os.path.join(yolo_dir, "labelstudio_config.xml")

    classes_file = os.path.join(yolo_dir, "classes.txt")
    if not os.path.isfile(classes_file):
        print(f"  classes.txt not found in {yolo_dir} — run propose_boxes.py "
              "with --export-yolo first.")
        return 1
    with open(classes_file) as fh:
        classes = [line.strip() for line in fh if line.strip()]

    try:
        from PIL import Image
    except ImportError:
        print("  Pillow is required: pip install pillow")
        return 1

    images = sorted(f for f in os.listdir(yolo_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png")))
    tasks, total_boxes, skipped = [], 0, 0

    for name in images:
        label_file = os.path.join(yolo_dir, os.path.splitext(name)[0] + ".txt")
        if not os.path.isfile(label_file):
            skipped += 1
            continue

        with Image.open(os.path.join(yolo_dir, name)) as img:
            width, height = img.size

        results = []
        for line in open(label_file):
            parts = line.split()
            if len(parts) != 5:
                continue
            class_id = int(parts[0])
            xc, yc, bw, bh = (float(v) for v in parts[1:])
            # YOLO centre-normalised -> Label Studio top-left percentages.
            results.append({
                "from_name": "label", "to_name": "image",
                "type": "rectanglelabels",
                "original_width": width, "original_height": height,
                "image_rotation": 0,
                "value": {
                    "x": max(0.0, (xc - bw / 2) * 100),
                    "y": max(0.0, (yc - bh / 2) * 100),
                    "width": bw * 100,
                    "height": bh * 100,
                    "rotation": 0,
                    "rectanglelabels": [classes[class_id]
                                        if class_id < len(classes) else classes[0]],
                },
            })
        total_boxes += len(results)

        tasks.append({
            "data": {"image": f"/data/local-files/?d={name}"},
            "predictions": [{"model_version": "propose_boxes",
                             "result": results}],
        })

    with open(out_path, "w") as fh:
        json.dump(tasks, fh, indent=1)
    with open(config_path, "w") as fh:
        fh.write(build_config(classes) + "\n")

    print("=== YOLO -> Label Studio ===")
    print(f"  tasks written        : {len(tasks)}")
    print(f"  boxes as predictions : {total_boxes}")
    print(f"  images without labels: {skipped}")
    print(f"  tasks file           : {out_path}")
    print(f"  labelling config     : {config_path}")
    print("\n  Start Label Studio with local files enabled:")
    print("    export LOCAL_FILES_SERVING_ENABLED=true")
    print(f"    export LOCAL_FILES_DOCUMENT_ROOT={yolo_dir}")
    print("    label-studio start")
    print("\n  Then: new project -> Labeling Setup -> paste the config above ->")
    print(f"  Import -> {os.path.basename(out_path)}")
    print("\n  Boxes appear as predictions. Click 'Create' on a task to turn them")
    print("  into editable annotations, then correct and submit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
