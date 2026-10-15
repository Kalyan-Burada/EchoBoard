"""
detect_regions.py
Run the full region pipeline on an image: find regions, classify each one.

Localisation comes from propose_boxes (classical CV, no training); the class
and confidence come from the trained region classifier. Together they give
the "where + what" the pipeline needs.

Prints a table to the terminal, writes JSON, and optionally saves an
annotated copy of the image with boxes drawn and labelled.

USAGE
    python scripts/detect_regions.py path/to/board.jpg
    python scripts/detect_regions.py board.jpg --save-annotated out.jpg --json out.json
    python scripts/detect_regions.py --image-id IMG0042        # pull from Supabase
"""

import argparse
import json
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))
sys.path.insert(0, script_dir)

from propose_boxes import propose, to_normalised  # noqa: E402

PAD = 0.04
# Stable colour per class so the terminal, the saved image and the dashboard agree.
COLOURS = {
    "Text": (107, 107, 255), "Heading": (196, 205, 78), "Formula": (61, 217, 255),
    "Equation": (119, 203, 107), "Diagram": (255, 108, 166), "Table": (69, 159, 255),
}


def load_model(model_path, device):
    import torch
    from torchvision import models
    import torch.nn as nn

    checkpoint = torch.load(model_path, map_location=device)
    classes = checkpoint["classes"]
    builder = getattr(models, checkpoint.get("backbone", "resnet50"))
    model = builder(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval().to(device)
    return model, classes, checkpoint.get("image_size", 224)


def detect(image_bgr, model, classes, image_size, device, min_confidence=0.0):
    """Return a list of region dicts for one image."""
    import cv2
    import torch
    from torchvision import transforms
    from PIL import Image

    h, w = image_bgr.shape[:2]
    boxes = propose(image_bgr)
    if not boxes:
        return []

    tf = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    batch = []
    for x1, y1, x2, y2 in boxes:
        px, py = int((x2 - x1) * PAD), int((y2 - y1) * PAD)
        crop = image_bgr[max(0, y1 - py):min(h, y2 + py),
                         max(0, x1 - px):min(w, x2 + px)]
        if crop.size == 0:
            crop = image_bgr[y1:y2, x1:x2]
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        batch.append(tf(Image.fromarray(rgb)))

    with torch.no_grad():
        logits = model(torch.stack(batch).to(device))
        probabilities = torch.softmax(logits, dim=1).cpu().numpy()

    regions = []
    for box, probs in zip(boxes, probabilities):
        index = int(probs.argmax())
        confidence = float(probs[index])
        if confidence < min_confidence:
            continue
        regions.append({
            "bbox_pixel": [int(v) for v in box],
            "bbox_norm": to_normalised(box, w, h),
            "class": classes[index],
            "confidence": round(confidence, 4),
            # Only written content goes on to the CRNN; diagrams and tables
            # are stored as image regions.
            "route": "crnn" if classes[index] in
                     {"Text", "Heading", "Formula", "Equation"} else "store",
        })
    regions.sort(key=lambda r: (r["bbox_pixel"][1], r["bbox_pixel"][0]))
    return regions


def annotate(image_bgr, regions, path):
    import cv2
    canvas = image_bgr.copy()
    for i, region in enumerate(regions, start=1):
        x1, y1, x2, y2 = region["bbox_pixel"]
        colour = COLOURS.get(region["class"], (0, 255, 0))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 3)
        caption = f'{i}. {region["class"]} {region["confidence"]:.2f}'
        (tw, th), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(canvas, (x1, max(0, y1 - th - 10)), (x1 + tw + 8, y1), colour, -1)
        cv2.putText(canvas, caption, (x1 + 4, max(th, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.imwrite(path, canvas)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", nargs="?", help="path to a board image")
    parser.add_argument("--image-id", help="fetch this ECHD image from Supabase instead")
    parser.add_argument("--model", default="runs/region_cnn/best_model.pt")
    parser.add_argument("--save-annotated", default=None)
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--min-confidence", type=float, default=0.0)
    args = parser.parse_args()

    if not args.image and not args.image_id:
        parser.error("give an image path or --image-id")
    if not os.path.isfile(args.model):
        print(f"  Model not found: {args.model}\n"
              "  Train it first: python scripts/train_region_cnn.py --crops-dir crops")
        return 1

    import cv2
    import numpy as np
    import torch

    if args.image_id:
        import database as db
        import storage
        db.init_db(); storage.init_storage()
        record = db.get_dataset_image_by_id(args.image_id)
        if not record:
            print(f"  No dataset image {args.image_id}")
            return 1
        data = storage.get_image(record["image_path"])
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        source = args.image_id
    else:
        image = cv2.imread(args.image)
        source = args.image

    if image is None:
        print(f"  Could not read image: {source}")
        return 1

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, classes, image_size = load_model(args.model, device)
    regions = detect(image, model, classes, image_size, device, args.min_confidence)

    h, w = image.shape[:2]
    print(f"\n=== EchoBoard region detection ===")
    print(f"  image   : {source}  ({w}x{h})")
    print(f"  classes : {', '.join(classes)}")
    print(f"  regions : {len(regions)}\n")
    if regions:
        print(f"  {'#':>3}  {'class':<10}{'conf':>7}  {'bbox [x1,y1,x2,y2]':<28}{'route':<8}")
        print(f"  {'-'*3}  {'-'*10}{'-'*7}  {'-'*28}{'-'*8}")
        for i, r in enumerate(regions, start=1):
            box = str(r["bbox_pixel"])
            print(f"  {i:>3}  {r['class']:<10}{r['confidence']:>7.2f}  {box:<28}{r['route']:<8}")
    else:
        print("  no regions found")

    payload = {"image": source, "width": w, "height": h,
               "classes": classes, "regions": regions}
    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  json      -> {args.json_out}")
    if args.save_annotated:
        annotate(image, regions, args.save_annotated)
        print(f"  annotated -> {args.save_annotated}")
    if not args.json_out and not args.save_annotated:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
