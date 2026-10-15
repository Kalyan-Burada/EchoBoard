"""
run_crnn_ablation.py
Ablation study for the CRNN handwriting recogniser.

Each configuration removes or alters exactly one component of the model in
ml/crnn_model.py and retrains from scratch. Everything else is held fixed:
the same dataset, the same split seed, the same epoch budget, the same
optimiser. The difference against the baseline is therefore attributable to
the component that changed.

The convolutional encoder is shared by every configuration and is taken
directly from CRNN, so what is being ablated is the real model rather than a
reimplementation of it.

Configurations
    baseline        2-layer bidirectional LSTM, hidden size 256
    no_rnn          recurrent stage removed; encoder columns projected
                    straight to character logits
    unidirectional  forward-only LSTM, so no right-to-left context
    hidden_128      recurrent width halved
    one_layer       recurrent depth reduced from two layers to one
    greedy_decode   evaluated from the baseline weights with best-path
                    decoding instead of beam search

USAGE
    python ml/run_crnn_ablation.py --epochs 12
    python ml/run_crnn_ablation.py --only baseline no_rnn --epochs 12
    python ml/run_crnn_ablation.py --table-only
"""

import argparse
import json
import math
import os
import random
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ml"))

DATASET_DIR = os.path.join(REPO_ROOT, "dataset_cache")
MANIFEST_PATH = os.path.join(DATASET_DIR, "manifest.json")

CONFIGURATIONS = {
    "baseline":       ("Full model: 2-layer BiLSTM, hidden 256", {}),
    "no_rnn":         ("Recurrent stage removed entirely",
                       {"no_rnn": True}),
    "unidirectional": ("Forward-only LSTM; backward context removed",
                       {"bidirectional": False}),
    "hidden_128":     ("Recurrent width halved, 256 to 128",
                       {"hidden_size": 128}),
    "one_layer":      ("Recurrent depth reduced, 2 layers to 1",
                       {"rnn_layers": 1}),
}


def build_model(num_classes, hidden_size=256, rnn_layers=2,
                bidirectional=True, no_rnn=False):
    """
    Build a variant of the project CRNN.

    The encoder is reused unchanged from CRNN so that every configuration
    sees identical visual features; only the sequence stage is altered.
    """
    import torch.nn as nn
    import torch.nn.functional as F
    from crnn_model import CRNN

    base = CRNN(img_channels=1, num_classes=num_classes,
                hidden_size=hidden_size, rnn_layers=rnn_layers)

    class Variant(nn.Module):
        def __init__(self):
            super().__init__()
            self.cnn = base.cnn
            self.no_rnn = no_rnn
            if no_rnn:
                # Without a recurrent stage each encoder column is classified
                # on its own, with no access to its neighbours.
                self.rnn = None
                self.fc = nn.Linear(512, num_classes)
            else:
                self.rnn = nn.LSTM(input_size=512, hidden_size=hidden_size,
                                   num_layers=rnn_layers,
                                   bidirectional=bidirectional,
                                   batch_first=True,
                                   dropout=0.2 if rnn_layers > 1 else 0.0)
                self.fc = nn.Linear(hidden_size * (2 if bidirectional else 1),
                                    num_classes)

        def forward(self, x):
            features = self.cnn(x).squeeze(2).permute(0, 2, 1)   # B, W', 512
            if self.rnn is not None:
                features, _ = self.rnn(features)
            logits = self.fc(features)
            # CTCLoss expects (Time, Batch, Classes).
            return F.log_softmax(logits, dim=-1).permute(1, 0, 2)

    return Variant()


def edit_distance(a, b):
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def greedy_decode(frame_indices, vocab):
    """Best-path decoding: collapse repeats, then drop blanks."""
    out, previous = [], -1
    for index in frame_indices:
        if index != previous and index != 0:
            out.append(vocab.idx2char.get(index, ""))
        previous = index
    return "".join(out)


def beam_decode(log_probs_tc, vocab, width=10):
    """
    CTC prefix beam search over one sample.

    log_probs_tc is (Time, Classes). Beams are keyed by the emitted prefix;
    blank and non-blank probabilities are tracked separately so that repeated
    characters are not collapsed incorrectly.
    """
    import numpy as np
    NEG = -1e30

    def logaddexp(a, b):
        if a == NEG:
            return b
        if b == NEG:
            return a
        return max(a, b) + math.log1p(math.exp(-abs(a - b)))

    beams = {(): (0.0, NEG)}            # prefix -> (log p blank, log p non-blank)
    frames, classes = log_probs_tc.shape
    for t in range(frames):
        frame = log_probs_tc[t]
        # Only the most probable symbols can realistically extend a beam.
        candidates = np.argsort(frame)[-min(width * 2, classes):]
        updated = {}
        for prefix, (p_blank, p_non_blank) in beams.items():
            total = logaddexp(p_blank, p_non_blank)
            for c in candidates:
                p = float(frame[c])
                if c == 0:
                    nb, nnb = updated.get(prefix, (NEG, NEG))
                    updated[prefix] = (logaddexp(nb, total + p), nnb)
                    continue
                last = prefix[-1] if prefix else None
                if c == last:
                    # Repeat without a blank between extends the same symbol.
                    nb, nnb = updated.get(prefix, (NEG, NEG))
                    updated[prefix] = (nb, logaddexp(nnb, p_non_blank + p))
                    extended = prefix + (int(c),)
                    nb2, nnb2 = updated.get(extended, (NEG, NEG))
                    updated[extended] = (nb2, logaddexp(nnb2, p_blank + p))
                else:
                    extended = prefix + (int(c),)
                    nb2, nnb2 = updated.get(extended, (NEG, NEG))
                    updated[extended] = (nb2, logaddexp(nnb2, total + p))
        beams = dict(sorted(updated.items(),
                            key=lambda kv: logaddexp(*kv[1]),
                            reverse=True)[:width])
    best = max(beams.items(), key=lambda kv: logaddexp(*kv[1]))[0]
    return "".join(vocab.idx2char.get(i, "") for i in best)


def evaluate(model, loader, vocab, device, decoder="greedy", beam_width=10):
    import numpy as np
    import torch

    model.eval()
    errors = characters = exact = total = 0
    samples = []
    with torch.no_grad():
        for batch in loader:
            images = batch["images"].to(device)
            log_probs = model(images)                      # T, B, C
            array = log_probs.permute(1, 0, 2).cpu().numpy()   # B, T, C
            for row, truth in zip(array, batch["raw_texts"]):
                if decoder == "beam":
                    guess = beam_decode(row, vocab, beam_width)
                else:
                    guess = greedy_decode(list(row.argmax(axis=1)), vocab)
                errors += edit_distance(guess, truth)
                characters += max(1, len(truth))
                exact += int(guess == truth)
                total += 1
                if len(samples) < 4:
                    samples.append((truth, guess))
    return {"cer": errors / max(1, characters),
            "exact_match": exact / max(1, total),
            "samples": samples}


def run_one(tag, description, overrides, args, data, results_path):
    import numpy as np
    import torch
    import torch.nn as nn

    vocab, train_loader, val_loader = data
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(len(vocab), **overrides).to(device)
    parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)

    criterion = nn.CTCLoss(blank=0, zero_infinity=True)
    optimiser = torch.optim.Adam(model.parameters(), lr=args.lr)

    print(f"  parameters: {parameters:,} | chance loss ~ "
          f"ln({len(vocab)}) = {math.log(len(vocab)):.3f}")
    print(f"  {'epoch':>5} {'train_loss':>11} {'val_CER':>9}")

    best, history = float("inf"), []
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train(); running = count = 0
        for batch in train_loader:
            images = batch["images"].to(device)
            log_probs = model(images)                       # T, B, C
            input_lengths = torch.full((images.size(0),), log_probs.size(0),
                                       dtype=torch.long)
            loss = criterion(log_probs, batch["targets"],
                             input_lengths, batch["target_lengths"])
            optimiser.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimiser.step()
            running += loss.item() * images.size(0); count += images.size(0)

        train_loss = running / max(1, count)
        metrics = evaluate(model, val_loader, vocab, device, "greedy")
        history.append({"epoch": epoch, "train_loss": train_loss,
                        "val_cer": metrics["cer"]})
        mark = ""
        if metrics["cer"] < best:
            best, mark = metrics["cer"], "  <- best"
            torch.save({"state_dict": model.state_dict(), "tag": tag},
                       os.path.join(args.out_dir, f"{tag}.pt"))
        print(f"  {epoch:>5} {train_loss:>11.4f} {metrics['cer']:>9.3f}{mark}",
              flush=True)

    checkpoint = torch.load(os.path.join(args.out_dir, f"{tag}.pt"),
                            map_location=device)
    model.load_state_dict(checkpoint["state_dict"])
    greedy = evaluate(model, val_loader, vocab, device, "greedy")
    record = {
        "tag": tag, "description": description,
        "parameters": parameters, "epochs": args.epochs, "seed": args.seed,
        "cer": greedy["cer"], "exact_match": greedy["exact_match"],
        "final_train_loss": history[-1]["train_loss"] if history else None,
        "best_val_cer": best,
        "minutes": round((time.time() - started) / 60, 1),
        "samples": greedy["samples"],
        "decoder": "greedy",
    }
    with open(results_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    # Decoding is a property of inference, so beam search is measured on the
    # baseline weights rather than by retraining.
    if tag == "baseline":
        beam = evaluate(model, val_loader, vocab, device, "beam",
                        args.beam_width)
        with open(results_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                **record, "tag": "beam_decode", "decoder": f"beam_{args.beam_width}",
                "description": f"Beam search decoding, width {args.beam_width}",
                "cer": beam["cer"], "exact_match": beam["exact_match"],
                "samples": beam["samples"]}) + "\n")
        print(f"  beam search (width {args.beam_width}): "
              f"CER {beam['cer']:.3f}  exact {beam['exact_match']:.3f}")

    print(f"  -> CER {greedy['cer']:.3f}  exact match {greedy['exact_match']:.3f}"
          f"  ({record['minutes']} min)")
    for truth, guess in greedy["samples"][:2]:
        print(f"     truth: {truth!r}\n     pred : {guess!r}")


def build_table(results_path):
    if not os.path.isfile(results_path):
        print(f"  no results at {results_path}")
        return
    runs = [json.loads(line) for line in open(results_path, encoding="utf-8")
            if line.strip()]
    by_tag = {r["tag"]: r for r in runs}
    base = by_tag.get("baseline")

    print(f"\n{'configuration':<17}{'CER':>8}{'delta':>9}{'exact':>9}"
          f"{'params':>12}  description")
    print("-" * 104)
    for tag in list(CONFIGURATIONS) + ["beam_decode"]:
        run = by_tag.get(tag)
        if not run:
            print(f"{tag:<17}{'-':>8}{'-':>9}{'-':>9}{'-':>12}  (not run)")
            continue
        delta = ("" if tag == "baseline" or not base
                 else f"{run['cer'] - base['cer']:+.3f}")
        print(f"{tag:<17}{run['cer']:>8.3f}{delta:>9}{run['exact_match']:>9.3f}"
              f"{run['parameters']:>12,}  {run['description'][:40]}")

    out = os.path.splitext(results_path)[0] + "_table.json"
    json.dump({"runs": by_tag}, open(out, "w"), indent=2)
    print(f"\n  table written to {out}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max-samples", type=int, default=0,
                        help="cap the dataset size; 0 uses everything")
    parser.add_argument("--beam-width", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default=os.path.join("runs", "crnn_ablation"))
    parser.add_argument("--results", default=None)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--table-only", action="store_true")
    args = parser.parse_args()

    results_path = args.results or os.path.join(args.out_dir, "results.jsonl")
    if args.table_only:
        build_table(results_path)
        return 0

    if not os.path.isfile(MANIFEST_PATH):
        print(f"  No dataset at {MANIFEST_PATH}\n"
              "  Generate it first: python ml/generate_academic_dataset.py 4000")
        return 1

    os.makedirs(args.out_dir, exist_ok=True)

    from torch.utils.data import DataLoader
    from dataset_loader import TextVocabulary, ECHDDataset, crnn_collate_fn

    samples = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    vocab = TextVocabulary("".join(s["text"] for s in samples))

    shuffled = list(samples)
    random.Random(args.seed).shuffle(shuffled)
    if args.max_samples:
        shuffled = shuffled[:args.max_samples]
    split = max(5, int(len(shuffled) * 0.15))
    val_samples, train_samples = shuffled[:split], shuffled[split:]

    train_loader = DataLoader(
        ECHDDataset(train_samples, DATASET_DIR, vocab, is_train=True,
                    target_height=32, target_width=384),
        batch_size=args.batch_size, shuffle=True, collate_fn=crnn_collate_fn)
    val_loader = DataLoader(
        ECHDDataset(val_samples, DATASET_DIR, vocab, is_train=False,
                    target_height=32, target_width=384),
        batch_size=args.batch_size, shuffle=False, collate_fn=crnn_collate_fn)

    tags = args.only or list(CONFIGURATIONS)
    unknown = [t for t in tags if t not in CONFIGURATIONS]
    if unknown:
        print(f"  unknown configuration(s): {unknown}")
        print(f"  available: {', '.join(CONFIGURATIONS)}")
        return 1

    print("=== EchoBoard CRNN ablation study ===")
    print(f"  dataset   : {len(shuffled)} samples "
          f"({len(train_samples)} train / {len(val_samples)} validation)")
    print(f"  vocabulary: {len(vocab)} classes including the CTC blank")
    print(f"  epochs    : {args.epochs} (identical for every configuration)")
    print(f"  results   : {results_path}")

    started = time.time()
    data = (vocab, train_loader, val_loader)
    for position, tag in enumerate(tags, start=1):
        description, overrides = CONFIGURATIONS[tag]
        print(f"\n[{position}/{len(tags)}] {tag} - {description}")
        try:
            run_one(tag, description, overrides, args, data, results_path)
        except Exception as exc:
            print(f"  !! {tag} failed: {exc}")

    print(f"\n  total wall time: {(time.time() - started) / 60:.1f} min")
    build_table(results_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
