"""
train_quality_cnn.py
Train the ECHD capture-quality CNN.

WHAT IT LEARNS
--------------
A multi-label classifier over whole board images. For each capture it predicts
three independent barriers that make a board image hard or impossible to read:

    occluded       a hand, phone, duster or person covers part of the board
    blurry         motion blur or defocus (derived from blur_score)
    poor_lighting  flash glare or underexposure (derived from lighting_score)

Multi-label, not multi-class: one capture can be blurry AND occluded, or
have no barrier at all. The head is three independent sigmoids trained with
BCEWithLogitsLoss.

WHY THIS TASK
-------------
It is the quality gate the EchoBoard pipeline is missing. Keyframe extraction
and bulk ingest currently accept whatever the camera produced; this model
scores each capture so unusable frames can be flagged before they reach the
annotation queue, and so a training split can exclude them. It is also the
task the current dataset actually supports: barrier labels exist for all 132
images, while handwriting recognition would need far more distinct text.

LABELS
------
Taken from the dataset metadata, not hand-made for training:

    occluded       dataset_images.occluded          (annotator judgement)
    blurry         blur_score < --blur-threshold    (measured, Laplacian variance)
    poor_lighting  lighting_score < --light-threshold

LEAKAGE CONTROL
---------------
The dataset deliberately contains several captures of the same board under
different conditions. Splitting those at random would put the same board in
train and test, and the reported accuracy would be meaningless. Images are
therefore grouped by their annotation text (identical transcription == same
board content) and split with GroupShuffleSplit, so every capture of one
board lands wholly in one split.

USAGE
-----
    # from Supabase (default) - downloads images to a local cache once
    python scripts/train_quality_cnn.py --epochs 30

    # from local folders, no network needed
    python scripts/train_quality_cnn.py --source local \
        --folders boards boards_2 boards_3 boards_4

Outputs land in --out-dir (default: runs/quality_cnn/):
    best_model.pt     weights with the best validation macro-F1
    metrics.json      per-label precision/recall/F1 on the held-out test split
    history.png       loss and F1 curves
    predictions.csv   per-image test predictions vs. ground truth
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_dir, "backend"))

LABELS = ["occluded", "blurry", "poor_lighting"]


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------
def _group_key(text, fallback):
    """
    Group captures of the same board together.

    Identical transcription means the same board content, so all its captures
    must share a split. Falls back to a per-image key when there is no text.
    """
    normalised = " ".join((text or "").lower().split())
    if not normalised:
        return f"ungrouped::{fallback}"
    return hashlib.md5(normalised.encode()).hexdigest()[:12]


def collect_from_supabase(cache_dir, blur_threshold, light_threshold):
    """Pull metadata from Supabase and cache the image bytes locally."""
    import database as db
    import storage

    db.init_db()
    storage.init_storage()

    os.makedirs(cache_dir, exist_ok=True)
    samples = []
    rows = db.get_dataset_images(limit=100000)
    print(f"  {len(rows)} rows in the dataset")

    for row in rows:
        quality = row.get("quality_metadata") or {}
        blur = quality.get("blur_score")
        light = quality.get("lighting_score")
        if blur is None or light is None:
            continue

        local = os.path.join(cache_dir, f"{row['image_id']}.jpg")
        if not os.path.exists(local):
            data = storage.get_image(row.get("image_path", ""))
            if not data:
                print(f"  WARNING: no image bytes for {row['image_id']}, skipping")
                continue
            with open(local, "wb") as fh:
                fh.write(data)

        text = " ".join(
            a.get("text", "") for a in (row.get("annotations") or [])
            if a.get("class") != "FullBoard"
        )
        samples.append({
            "path": local,
            "id": row["image_id"],
            "group": _group_key(text, row["image_id"]),
            "labels": [
                1.0 if quality.get("occluded") else 0.0,
                1.0 if blur < blur_threshold else 0.0,
                1.0 if light < light_threshold else 0.0,
            ],
        })
    return samples


def collect_from_local(folders, blur_threshold, light_threshold):
    """Read images + labels.json straight from the ingest folders."""
    import cv2

    samples = []
    for folder in folders:
        labels_path = os.path.join(folder, "labels.json")
        labels = {}
        if os.path.isfile(labels_path):
            with open(labels_path, encoding="utf-8") as fh:
                labels = json.load(fh)

        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(folder, name)
            entry = labels.get(name, {})

            img = cv2.imread(path)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            light = entry.get("lighting_score", 60)

            text = " ".join(
                [str(l) for l in entry.get("lines", [])]
                + [r.get("text", "") for r in entry.get("regions", [])]
            )
            samples.append({
                "path": path,
                "id": f"{os.path.basename(folder)}/{name}",
                "group": _group_key(text, f"{folder}/{name}"),
                "labels": [
                    1.0 if entry.get("occluded") else 0.0,
                    1.0 if blur < blur_threshold else 0.0,
                    1.0 if light < light_threshold else 0.0,
                ],
            })
    return samples


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["supabase", "local"], default="supabase")
    parser.add_argument("--folders", nargs="*", default=["boards", "boards_2",
                                                         "boards_3", "boards_4"])
    parser.add_argument("--cache-dir", default="runs/cache")
    parser.add_argument("--out-dir", default="runs/quality_cnn")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--blur-threshold", type=float, default=25.0,
                        help="blur_score below this counts as blurry")
    parser.add_argument("--light-threshold", type=float, default=50.0,
                        help="lighting_score below this counts as poor lighting")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--backbone", default="resnet18",
                        choices=["resnet18", "resnet34"])
    parser.add_argument("--no-pretrained", action="store_true",
                        help="Train from random init instead of ImageNet weights. "
                             "Only for offline runs — accuracy will be much worse "
                             "on a dataset this size.")
    args = parser.parse_args()

    import numpy as np
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import models, transforms
    from PIL import Image
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import precision_recall_fscore_support, accuracy_score

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    print("=== EchoBoard capture-quality CNN ===")
    print(f"  source: {args.source}")

    if args.source == "supabase":
        samples = collect_from_supabase(args.cache_dir, args.blur_threshold,
                                        args.light_threshold)
    else:
        samples = collect_from_local(args.folders, args.blur_threshold,
                                     args.light_threshold)

    if len(samples) < 20:
        print(f"\n  Only {len(samples)} usable samples — too few to train.")
        return 1

    y = np.array([s["labels"] for s in samples], dtype=np.float32)
    groups = np.array([s["group"] for s in samples])
    print(f"\n  samples: {len(samples)} | distinct board groups: {len(set(groups))}")
    for i, name in enumerate(LABELS):
        pos = int(y[:, i].sum())
        print(f"    {name:<14} positive: {pos:>4} / {len(samples)} "
              f"({100*pos/len(samples):.0f}%)")

    # --- group-aware split: no board content spans two splits ---------------
    idx = np.arange(len(samples))
    gss = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=args.seed)
    train_val_idx, test_idx = next(gss.split(idx, groups=groups))
    inner = GroupShuffleSplit(n_splits=1,
                              test_size=args.val_size / (1 - args.test_size),
                              random_state=args.seed)
    tr_rel, va_rel = next(inner.split(train_val_idx, groups=groups[train_val_idx]))
    train_idx, val_idx = train_val_idx[tr_rel], train_val_idx[va_rel]

    overlap = (set(groups[train_idx]) | set(groups[val_idx])) & set(groups[test_idx])
    assert not overlap, f"group leak between train/val and test: {overlap}"
    print(f"  split: train {len(train_idx)} | val {len(val_idx)} | test {len(test_idx)}"
          "  (grouped — no board appears in two splits)")

    mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    train_tf = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomAffine(degrees=7, translate=(0.05, 0.05), scale=(0.92, 1.08)),
        transforms.ColorJitter(brightness=0.25, contrast=0.25),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    class BoardDataset(Dataset):
        def __init__(self, indices, tf):
            self.indices, self.tf = indices, tf

        def __len__(self):
            return len(self.indices)

        def __getitem__(self, i):
            s = samples[self.indices[i]]
            img = Image.open(s["path"]).convert("RGB")
            return self.tf(img), torch.tensor(s["labels"]), s["id"]

    loaders = {
        "train": DataLoader(BoardDataset(train_idx, train_tf),
                            batch_size=args.batch_size, shuffle=True, num_workers=2),
        "val": DataLoader(BoardDataset(val_idx, eval_tf),
                          batch_size=args.batch_size, num_workers=2),
        "test": DataLoader(BoardDataset(test_idx, eval_tf),
                           batch_size=args.batch_size, num_workers=2),
    }

    # --- model: ImageNet-pretrained backbone, new 3-logit head --------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    builder = getattr(models, args.backbone)
    weights = None if args.no_pretrained else "IMAGENET1K_V1"
    model = builder(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, len(LABELS))
    model = model.to(device)
    kind = "random init" if args.no_pretrained else "ImageNet pretrained"
    print(f"  model: {args.backbone} ({kind}) on {device}")

    # Positive weighting keeps the rare barriers from being ignored.
    pos = y[train_idx].sum(axis=0)
    neg = len(train_idx) - pos
    pos_weight = torch.tensor(np.clip(neg / np.maximum(pos, 1), 1.0, 10.0),
                              dtype=torch.float32, device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)

    def run_eval(loader):
        model.eval()
        probs, trues, ids, total = [], [], [], 0.0
        with torch.no_grad():
            for xb, yb, bid in loader:
                xb, yb = xb.to(device), yb.to(device)
                out = model(xb)
                total += criterion(out, yb).item() * xb.size(0)
                probs.append(torch.sigmoid(out).cpu().numpy())
                trues.append(yb.cpu().numpy())
                ids.extend(bid)
        return (np.concatenate(probs), np.concatenate(trues), ids,
                total / max(len(loader.dataset), 1))

    os.makedirs(args.out_dir, exist_ok=True)
    history, best_f1 = [], -1.0
    print("\n  epoch   train_loss   val_loss   val_macroF1")
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb, _ in loaders["train"]:
            xb, yb = xb.to(device), yb.to(device)
            optimiser.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimiser.step()
            running += loss.item() * xb.size(0)
        train_loss = running / max(len(train_idx), 1)

        vp, vt, _, val_loss = run_eval(loaders["val"])
        _, _, f1, _ = precision_recall_fscore_support(
            vt, (vp > 0.5).astype(int), average="macro", zero_division=0)
        scheduler.step()
        history.append({"epoch": epoch, "train_loss": train_loss,
                        "val_loss": val_loss, "val_macro_f1": float(f1)})
        marker = ""
        if f1 > best_f1:
            best_f1, marker = f1, "  <- best"
            torch.save({"state_dict": model.state_dict(), "labels": LABELS,
                        "backbone": args.backbone, "image_size": args.image_size,
                        "thresholds": {"blur": args.blur_threshold,
                                       "light": args.light_threshold}},
                       os.path.join(args.out_dir, "best_model.pt"))
        print(f"  {epoch:>5}   {train_loss:>10.4f}   {val_loss:>8.4f}   "
              f"{f1:>11.3f}{marker}")

    # --- final evaluation on the held-out test split ------------------------
    ckpt = torch.load(os.path.join(args.out_dir, "best_model.pt"), map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    probs, trues, ids, _ = run_eval(loaders["test"])
    preds = (probs > 0.5).astype(int)

    precision, recall, f1s, support = precision_recall_fscore_support(
        trues, preds, average=None, zero_division=0, labels=range(len(LABELS)))
    macro = precision_recall_fscore_support(trues, preds, average="macro",
                                            zero_division=0)

    print("\n=== Test results (held-out boards, never seen in training) ===")
    print(f"  {'label':<16}{'precision':>10}{'recall':>9}{'f1':>8}{'support':>9}")
    for i, name in enumerate(LABELS):
        print(f"  {name:<16}{precision[i]:>10.3f}{recall[i]:>9.3f}"
              f"{f1s[i]:>8.3f}{int(support[i]):>9}")
    print(f"  {'macro avg':<16}{macro[0]:>10.3f}{macro[1]:>9.3f}{macro[2]:>8.3f}")
    exact = accuracy_score(trues, preds)
    print(f"\n  exact-match accuracy (all 3 labels right): {exact:.3f}")

    metrics = {
        "samples": len(samples),
        "groups": len(set(groups)),
        "split": {"train": len(train_idx), "val": len(val_idx), "test": len(test_idx)},
        "thresholds": {"blur": args.blur_threshold, "light": args.light_threshold},
        "per_label": {
            name: {"precision": float(precision[i]), "recall": float(recall[i]),
                   "f1": float(f1s[i]), "support": int(support[i])}
            for i, name in enumerate(LABELS)},
        "macro": {"precision": float(macro[0]), "recall": float(macro[1]),
                  "f1": float(macro[2])},
        "exact_match_accuracy": float(exact),
        "history": history,
    }
    with open(os.path.join(args.out_dir, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)

    with open(os.path.join(args.out_dir, "predictions.csv"), "w") as fh:
        fh.write("image_id," + ",".join(f"true_{l},pred_{l},prob_{l}" for l in LABELS) + "\n")
        for j, image_id in enumerate(ids):
            cells = []
            for i in range(len(LABELS)):
                cells += [str(int(trues[j][i])), str(int(preds[j][i])),
                          f"{probs[j][i]:.3f}"]
            fh.write(f"{image_id}," + ",".join(cells) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
        ep = [h["epoch"] for h in history]
        ax1.plot(ep, [h["train_loss"] for h in history], label="train")
        ax1.plot(ep, [h["val_loss"] for h in history], label="val")
        ax1.set_xlabel("epoch"); ax1.set_ylabel("loss"); ax1.legend()
        ax1.set_title("Loss")
        ax2.plot(ep, [h["val_macro_f1"] for h in history], color="green")
        ax2.set_xlabel("epoch"); ax2.set_ylabel("macro F1")
        ax2.set_title("Validation macro F1")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out_dir, "history.png"), dpi=120)
    except Exception as exc:
        print(f"  (skipped history.png: {exc})")

    print(f"\n  artifacts written to {args.out_dir}/")
    print("    best_model.pt  metrics.json  predictions.csv  history.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
