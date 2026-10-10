"""
train_crnn.py
Optimized Training Pipeline for CRNN Handwriting Recognition Model on ECHD dataset.
"""

import os
import sys
import json
import random
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ml"))

from export_dataset import export_echd_dataset
from crnn_model import CRNN
from dataset_loader import TextVocabulary, ECHDDataset, crnn_collate_fn

DATASET_DIR = os.path.join(REPO_ROOT, "dataset_cache")
MANIFEST_PATH = os.path.join(DATASET_DIR, "manifest.json")
CHECKPOINT_DIR = os.path.join(REPO_ROOT, "checkpoints")
VOCAB_PATH = os.path.join(REPO_ROOT, "ml", "vocab.json")
SAVE_MODEL_PATH = os.path.join(REPO_ROOT, "ml", "best_crnn_model.pt")
ROOT_MODEL_PATH = os.path.join(os.path.dirname(REPO_ROOT), "best_crnn_model.pt")


def compute_cer(predicted, ground_truth):
    if len(ground_truth) == 0:
        return 1.0 if len(predicted) > 0 else 0.0

    dp = [[0] * (len(ground_truth) + 1) for _ in range(len(predicted) + 1)]
    for i in range(len(predicted) + 1):
        dp[i][0] = i
    for j in range(len(ground_truth) + 1):
        dp[0][j] = j

    for i in range(1, len(predicted) + 1):
        for j in range(1, len(ground_truth) + 1):
            cost = 0 if predicted[i - 1] == ground_truth[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost
            )
    return dp[len(predicted)][len(ground_truth)] / float(len(ground_truth))


def init_weights(m):
    if isinstance(m, nn.Conv2d):
        nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
        if m.bias is not None:
            nn.init.zeros_(m.bias)
    elif isinstance(m, nn.BatchNorm2d):
        nn.init.ones_(m.weight)
        nn.init.zeros_(m.bias)
    elif isinstance(m, nn.Linear):
        nn.init.xavier_normal_(m.weight)
        if m.bias is not None:
            nn.init.zeros_(m.bias)


def train():
    print("=" * 65)
    print("    ECHD Handwriting Recognition Model Training (CRNN)")
    print("=" * 65)

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    if not os.path.exists(MANIFEST_PATH):
        print("Dataset cache not found. Downloading from Supabase...")
        samples = export_echd_dataset()
    else:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            samples = json.load(f)
        print(f"Loaded {len(samples)} samples from local manifest.")

    all_text = "".join([s["text"] for s in samples])
    vocab = TextVocabulary(all_text)
    vocab.save(VOCAB_PATH)
    print(f"Vocabulary: {len(vocab)} classes (including CTC blank)")

    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    shuffled = list(samples)
    random.shuffle(shuffled)

    val_size = max(5, int(len(shuffled) * 0.15))
    train_samples = shuffled[val_size:]
    val_samples = shuffled[:val_size]

    print(f"Split: {len(train_samples)} training samples, {len(val_samples)} validation samples")

    # DataLoader with batch_size = 8
    train_dataset = ECHDDataset(train_samples, DATASET_DIR, vocab, is_train=True, target_height=32, target_width=384)
    val_dataset = ECHDDataset(val_samples, DATASET_DIR, vocab, is_train=False, target_height=32, target_width=384)

    batch_size = 32
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        collate_fn=crnn_collate_fn, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        collate_fn=crnn_collate_fn, num_workers=0
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    model = CRNN(img_channels=1, num_classes=len(vocab), hidden_size=256, rnn_layers=2)
    model.apply(init_weights)
    model.to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"CRNN Model Parameters: {total_params:,}")

    criterion = nn.CTCLoss(blank=0, zero_infinity=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, betas=(0.9, 0.999), eps=1e-8)
    epochs = 30
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=8, min_lr=1e-5)

    best_val_loss = float("inf")
    best_cer = float("inf")
    best_acc = 0.0

    from tqdm import tqdm
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch:02d}/{epochs:02d}", leave=False, dynamic_ncols=True)
        for batch in pbar:
            images = batch["images"].to(device)
            targets = batch["targets"].to(device)
            target_lengths = batch["target_lengths"].to(device)

            optimizer.zero_grad()

            log_probs = model(images)  # (T, B, C)
            T, B, C = log_probs.shape
            input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

            loss = criterion(log_probs, targets, input_lengths, target_lengths)

            if torch.isnan(loss) or torch.isinf(loss):
                continue

            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

            train_loss += loss.item() * B
            pbar.set_postfix({"loss": f"{loss.item():.3f}"})

        train_loss /= len(train_dataset)

        # Validation
        model.eval()
        val_loss = 0.0
        total_cer = 0.0
        exact_matches = 0
        predictions_sample = []

        with torch.no_grad():
            for batch in val_loader:
                images = batch["images"].to(device)
                targets = batch["targets"].to(device)
                target_lengths = batch["target_lengths"].to(device)
                raw_texts = batch["raw_texts"]

                log_probs = model(images)
                T, B, C = log_probs.shape
                input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

                loss = criterion(log_probs, targets, input_lengths, target_lengths)
                if not torch.isnan(loss) and not torch.isinf(loss):
                    val_loss += loss.item() * B

                preds = log_probs.permute(1, 0, 2).argmax(dim=-1).cpu().numpy()
                for b_idx in range(B):
                    pred_str = vocab.decode(preds[b_idx])
                    gt_str = raw_texts[b_idx]
                    cer = compute_cer(pred_str, gt_str)
                    total_cer += cer
                    if pred_str.strip().lower() == gt_str.strip().lower():
                        exact_matches += 1
                    if len(predictions_sample) < 3:
                        predictions_sample.append((gt_str, pred_str, cer))

        val_loss /= len(val_dataset)
        avg_cer = total_cer / len(val_dataset)
        acc = (exact_matches / len(val_dataset)) * 100.0
        scheduler.step(val_loss)

        # Print every single epoch live in terminal with sample prediction
        print(f"Epoch [{epoch:02d}/{epochs:02d}] "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
              f"Avg CER: {avg_cer:.3f} | Accuracy: {acc:.1f}%", flush=True)
        if predictions_sample:
            sample_gt, sample_pred, sample_cer = predictions_sample[0]
            print(f"   Sample GT:   \"{sample_gt}\"", flush=True)
            print(f"   Sample Pred: \"{sample_pred}\" (CER: {sample_cer:.2f})", flush=True)

        if val_loss < best_val_loss or avg_cer < best_cer:
            best_cer = min(best_cer, avg_cer)
            best_val_loss = val_loss
            best_acc = max(best_acc, acc)

            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "vocab": {
                    "char2idx": vocab.char2idx,
                    "idx2char": vocab.idx2char
                },
                "config": {
                    "img_channels": 1,
                    "num_classes": len(vocab),
                    "hidden_size": 256,
                    "rnn_layers": 2,
                    "target_height": 32,
                    "target_width": 384,
                },
                "metrics": {
                    "val_loss": val_loss,
                    "val_cer": avg_cer,
                    "accuracy": acc,
                }
            }
            torch.save(checkpoint, SAVE_MODEL_PATH)
            torch.save(checkpoint, ROOT_MODEL_PATH)

    print("=" * 65)
    print(f"[SUCCESS] Training Complete! Best Validation Loss: {best_val_loss:.4f}")
    print(f"Checkpoints saved:\n   - {SAVE_MODEL_PATH}\n   - {ROOT_MODEL_PATH}")
    print("=" * 65)


if __name__ == "__main__":
    train()
