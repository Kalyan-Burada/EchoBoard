"""
eval_report.py
Validates the newly trained CRNN model and outputs performance metrics and inference samples.
"""

import os
import sys
import json
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ml"))

from predict_crnn import CRNNRecognizer

def main():
    model_path = os.path.join(os.path.dirname(REPO_ROOT), "best_crnn_model.pt")
    ckpt = torch.load(model_path, map_location="cpu")

    print("=" * 65)
    print("      ECHD CRNN MODEL TRAINING & EVALUATION REPORT")
    print("=" * 65)
    print(f"Model File:          {model_path}")
    print(f"File Size:           {os.path.getsize(model_path) / (1024*1024):.2f} MB")
    print(f"Total Epochs:        {ckpt.get('epoch')}")
    metrics = ckpt.get("metrics", {})
    print(f"Validation Loss:     {metrics.get('val_loss', 0):.4f}")
    print(f"Validation CER:      {metrics.get('val_cer', 0):.4f} (Character Error Rate)")
    print(f"Exact Match Acc:     {metrics.get('accuracy', 0):.2f}%")
    print(f"Vocabulary Size:     {len(ckpt.get('vocab', {}).get('char2idx', {})) + 1} classes")
    print("=" * 65)

    recognizer = CRNNRecognizer(model_path)
    manifest_path = os.path.join(REPO_ROOT, "dataset_cache", "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    print("\nSAMPLE PREDICTIONS ON DATASET IMAGES:")
    for s in samples[:10]:
        img_p = os.path.join(REPO_ROOT, "dataset_cache", s["image_path"])
        pred = recognizer.predict(img_p)
        print(f"  [{s['image_id']}] GT:   \"{s['text']}\"")
        print(f"         PRED: \"{pred}\"")

if __name__ == "__main__":
    main()
