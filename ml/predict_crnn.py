"""
predict_crnn.py
Inference script to transcribe board handwriting images using the trained CRNN model.
"""

import os
import sys
import torch
import cv2
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ml"))

from crnn_model import CRNN
from dataset_loader import TextVocabulary, preprocess_image

MODEL_PATH = os.path.join(REPO_ROOT, "ml", "best_crnn_model.pt")
ALT_MODEL_PATH = os.path.join(os.path.dirname(REPO_ROOT), "best_crnn_model.pt")


class CRNNRecognizer:
    def __init__(self, checkpoint_path=None):
        if checkpoint_path is None:
            checkpoint_path = MODEL_PATH if os.path.exists(MODEL_PATH) else ALT_MODEL_PATH

        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Model checkpoint not found at {checkpoint_path}")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(checkpoint_path, map_location=self.device)

        # Load vocabulary
        vocab_dict = checkpoint["vocab"]
        self.vocab = TextVocabulary.__new__(TextVocabulary)
        self.vocab.blank_idx = 0
        self.vocab.char2idx = vocab_dict["char2idx"]
        self.vocab.idx2char = {int(k): v for k, v in vocab_dict["idx2char"].items()}

        # Config
        config = checkpoint.get("config", {})
        self.target_height = config.get("target_height", 32)
        self.target_width = config.get("target_width", 384)

        # Build Model
        self.model = CRNN(
            img_channels=config.get("img_channels", 1),
            num_classes=config.get("num_classes", len(self.vocab)),
            hidden_size=config.get("hidden_size", 256),
            rnn_layers=config.get("rnn_layers", 2),
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        print(f"Loaded trained CRNN model from {checkpoint_path} ({len(self.vocab)} classes, device: {self.device})")

    def _predict_single_line(self, gray):
        h, w = gray.shape[:2]
        if h == 0 or w == 0:
            return ""
        scale = self.target_height / float(h)
        new_w = max(1, int(w * scale))

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        if new_w > self.target_width:
            resized = cv2.resize(gray, (self.target_width, self.target_height), interpolation=cv2.INTER_AREA)
        else:
            resized = cv2.resize(gray, (new_w, self.target_height), interpolation=cv2.INTER_LINEAR)
            bg_val = int(np.median(resized[:, -max(1, min(5, new_w)):]))
            padded = np.full((self.target_height, self.target_width), bg_val, dtype=np.uint8)
            padded[:, :new_w] = resized
            resized = padded

        tensor = (resized.astype(np.float32) / 127.5) - 1.0
        tensor = np.expand_dims(tensor, axis=0)
        img_tensor = torch.from_numpy(tensor).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            log_probs = self.model(img_tensor)  # (T, 1, C)
            preds = log_probs.permute(1, 0, 2).argmax(dim=-1)[0].cpu().numpy()
            text = self.vocab.decode(preds)
        return text.strip()

    def predict(self, image_input):
        """
        Recognize text from an image path or numpy array.
        """
        if isinstance(image_input, str):
            img_bgr = cv2.imread(image_input)
            if img_bgr is None:
                return ""
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        else:
            if len(image_input.shape) == 3:
                gray = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_input

        h, w = gray.shape[:2]
        if h < 10 or w < 10:
            return ""

        # Multi-line check for tall crops
        if h >= 65 and (h / float(w) > 0.35):
            grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            profile = np.sum(np.abs(grad_y), axis=1)
            profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 15), 3).flatten()

            valleys = []
            min_lh = 24
            mean_p = float(np.mean(profile))
            for y in range(min_lh, h - min_lh):
                if profile[y] < mean_p * 0.45 and profile[y] == min(profile[max(0, y - 8):min(h, y + 8)]):
                    if not valleys or (y - valleys[-1] >= min_lh):
                        valleys.append(y)

            if valleys:
                cuts = [0] + valleys + [h]
                line_texts = []
                for i in range(len(cuts) - 1):
                    strip = gray[cuts[i]:cuts[i + 1], :]
                    if strip.shape[0] >= 12:
                        t = self._predict_single_line(strip)
                        if t:
                            line_texts.append(t)
                if line_texts:
                    return "\n".join(line_texts)

        return self._predict_single_line(gray)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        recognizer = CRNNRecognizer()
        res = recognizer.predict(img_path)
        print(f"\nRecognized Text:\n{res}")
    else:
        print("Usage: python predict_crnn.py <image_path>")
