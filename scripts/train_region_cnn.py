"""
train_region_cnn.py
Train the ResNet-50 region classifier on the crop dataset.

Takes a crop of a board region and predicts its content category. Paired with
propose_boxes.py at inference time this gives the full "where + what" the
pipeline needs, without the detector needing box ground truth.

Reads whatever class folders exist under --crops-dir, so adding a Diagram/
folder by hand and re-running extends the model to that class.

Crops are split by SOURCE BOARD, not by crop: several crops from one board
share handwriting, lighting and content, so splitting them at random would
leak and inflate accuracy.

USAGE
    python scripts/train_region_cnn.py --crops-dir crops --epochs 25
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crops-dir", default="crops")
    parser.add_argument("--out-dir", default="runs/region_cnn")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--backbone", default="resnet50",
                        choices=["resnet18", "resnet34", "resnet50"])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrained", action="store_true",
                        help="random init; offline only, markedly worse")
    args = parser.parse_args()

    import numpy as np
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import models, transforms
    from PIL import Image
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import (precision_recall_fscore_support, accuracy_score,
                                 confusion_matrix)

    torch.manual_seed(args.seed); np.random.seed(args.seed)

    manifest_path = os.path.join(args.crops_dir, "manifest.json")
    manifest = {}
    if os.path.isfile(manifest_path):
        manifest = {m["file"]: m["source_image"] for m in json.load(open(manifest_path))}

    classes = sorted(d for d in os.listdir(args.crops_dir)
                     if os.path.isdir(os.path.join(args.crops_dir, d)))
    if len(classes) < 2:
        print(f"  Need at least 2 class folders in {args.crops_dir}, found {classes}")
        return 1

    samples = []
    for ci, name in enumerate(classes):
        folder = os.path.join(args.crops_dir, name)
        for f in sorted(os.listdir(folder)):
            if not f.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            rel = f"{name}/{f}"
            # group = source board, so crops of one board stay in one split
            group = manifest.get(rel) or f.rsplit("_r", 1)[0]
            samples.append({"path": os.path.join(folder, f), "y": ci, "group": group})

    y = np.array([s["y"] for s in samples])
    groups = np.array([s["group"] for s in samples])
    print("=== EchoBoard region classifier ===")
    print(f"  crops: {len(samples)} | classes: {classes} | source boards: {len(set(groups))}")
    for ci, name in enumerate(classes):
        print(f"    {name:<10} {int((y == ci).sum()):>4}")

    idx = np.arange(len(samples))
    gss = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=args.seed)
    tv, test_idx = next(gss.split(idx, groups=groups))
    inner = GroupShuffleSplit(n_splits=1,
                              test_size=args.val_size / (1 - args.test_size),
                              random_state=args.seed)
    tr_rel, va_rel = next(inner.split(tv, groups=groups[tv]))
    train_idx, val_idx = tv[tr_rel], tv[va_rel]
    leak = (set(groups[train_idx]) | set(groups[val_idx])) & set(groups[test_idx])
    assert not leak, f"board leak between splits: {leak}"
    print(f"  split: train {len(train_idx)} | val {len(val_idx)} | test {len(test_idx)}"
          "  (grouped by source board)")

    mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    train_tf = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.RandomAffine(degrees=4, translate=(0.03, 0.03), scale=(0.95, 1.05)),
        transforms.ColorJitter(brightness=0.3, contrast=0.3),
        transforms.ToTensor(), transforms.Normalize(mean, std)])
    eval_tf = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(), transforms.Normalize(mean, std)])

    class Crops(Dataset):
        def __init__(self, indices, tf): self.indices, self.tf = indices, tf
        def __len__(self): return len(self.indices)
        def __getitem__(self, i):
            s = samples[self.indices[i]]
            return self.tf(Image.open(s["path"]).convert("RGB")), s["y"]

    loaders = {k: DataLoader(Crops(v, train_tf if k == "train" else eval_tf),
                             batch_size=args.batch_size, shuffle=(k == "train"),
                             num_workers=2)
               for k, v in [("train", train_idx), ("val", val_idx), ("test", test_idx)]}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = getattr(models, args.backbone)(
        weights=None if args.no_pretrained else "IMAGENET1K_V2"
        if args.backbone == "resnet50" else "IMAGENET1K_V1")
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model = model.to(device)
    print(f"  model: {args.backbone} "
          f"({'random init' if args.no_pretrained else 'ImageNet pretrained'}) on {device}")

    counts = np.bincount(y[train_idx], minlength=len(classes)).astype(float)
    weights = torch.tensor(counts.sum() / np.maximum(counts, 1),
                           dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)

    def evaluate(loader):
        model.eval(); preds, trues, loss = [], [], 0.0
        with torch.no_grad():
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                out = model(xb)
                loss += criterion(out, yb).item() * xb.size(0)
                preds.append(out.argmax(1).cpu().numpy()); trues.append(yb.cpu().numpy())
        import numpy as _np
        return (_np.concatenate(preds), _np.concatenate(trues),
                loss / max(len(loader.dataset), 1))

    os.makedirs(args.out_dir, exist_ok=True)
    best, history = -1.0, []
    print("\n  epoch   train_loss   val_loss   val_macroF1")
    for epoch in range(1, args.epochs + 1):
        model.train(); running = 0.0
        for xb, yb in loaders["train"]:
            xb, yb = xb.to(device), yb.to(device)
            optimiser.zero_grad()
            loss = criterion(model(xb), yb); loss.backward(); optimiser.step()
            running += loss.item() * xb.size(0)
        tl = running / max(len(train_idx), 1)
        vp, vt, vl = evaluate(loaders["val"])
        f1 = precision_recall_fscore_support(vt, vp, average="macro", zero_division=0)[2]
        scheduler.step()
        history.append({"epoch": epoch, "train_loss": tl, "val_loss": vl,
                        "val_macro_f1": float(f1)})
        mark = ""
        if f1 > best:
            best, mark = f1, "  <- best"
            torch.save({"state_dict": model.state_dict(), "classes": classes,
                        "backbone": args.backbone, "image_size": args.image_size},
                       os.path.join(args.out_dir, "best_model.pt"))
        print(f"  {epoch:>5}   {tl:>10.4f}   {vl:>8.4f}   {f1:>11.3f}{mark}")

    ckpt = torch.load(os.path.join(args.out_dir, "best_model.pt"), map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    preds, trues, _ = evaluate(loaders["test"])
    p, r, f1s, sup = precision_recall_fscore_support(
        trues, preds, average=None, zero_division=0, labels=range(len(classes)))
    macro = precision_recall_fscore_support(trues, preds, average="macro", zero_division=0)

    print("\n=== Test results (held-out boards) ===")
    print(f"  {'class':<12}{'precision':>10}{'recall':>9}{'f1':>8}{'support':>9}")
    for i, name in enumerate(classes):
        print(f"  {name:<12}{p[i]:>10.3f}{r[i]:>9.3f}{f1s[i]:>8.3f}{int(sup[i]):>9}")
    print(f"  {'macro avg':<12}{macro[0]:>10.3f}{macro[1]:>9.3f}{macro[2]:>8.3f}")
    acc = accuracy_score(trues, preds)
    print(f"\n  accuracy: {acc:.3f}")
    print("\n  confusion matrix (rows = true, cols = predicted)")
    cm = confusion_matrix(trues, preds, labels=range(len(classes)))
    print("            " + "".join(f"{c[:8]:>9}" for c in classes))
    for i, name in enumerate(classes):
        print(f"  {name:<10}" + "".join(f"{v:>9}" for v in cm[i]))

    json.dump({"classes": classes, "crops": len(samples),
               "split": {"train": len(train_idx), "val": len(val_idx),
                         "test": len(test_idx)},
               "per_class": {n: {"precision": float(p[i]), "recall": float(r[i]),
                                 "f1": float(f1s[i]), "support": int(sup[i])}
                             for i, n in enumerate(classes)},
               "macro": {"precision": float(macro[0]), "recall": float(macro[1]),
                         "f1": float(macro[2])},
               "accuracy": float(acc),
               "confusion_matrix": cm.tolist(), "history": history},
              open(os.path.join(args.out_dir, "metrics.json"), "w"), indent=2)
    print(f"\n  artifacts: {args.out_dir}/best_model.pt  metrics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
