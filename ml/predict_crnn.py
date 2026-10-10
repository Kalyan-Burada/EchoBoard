"""
predict_crnn.py
Inference script to transcribe board handwriting images using the trained CRNN model.
"""

import os
import sys
import torch
import cv2

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

    def predict(self, image_input):
        """
        Recognize text from an image path or numpy array.
        """
        if isinstance(image_input, str):
            img_tensor = preprocess_image(
                image_input,
                target_height=self.target_height,
                target_width=self.target_width,
                is_train=False,
            )
        else:
            # Assume numpy array
            h, w = image_input.shape[:2]
            scale = self.target_height / float(h)
            new_w = max(1, int(w * scale))
            if len(image_input.shape) == 3:
                gray = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_input

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

            if new_w > self.target_width:
                resized = cv2.resize(gray, (self.target_width, self.target_height), interpolation=cv2.INTER_AREA)
            else:
                resized = cv2.resize(gray, (new_w, self.target_height), interpolation=cv2.INTER_LINEAR)
                padded = np.zeros((self.target_height, self.target_width), dtype=np.uint8)
                padded[:, :new_w] = resized
                resized = padded

            tensor = (resized.astype(np.float32) / 127.5) - 1.0
            tensor = np.expand_dims(tensor, axis=0)
            img_tensor = torch.from_numpy(tensor).float()

        img_tensor = img_tensor.unsqueeze(0).to(self.device)

        with torch.no_grad():
            log_probs = self.model(img_tensor)  # (T, 1, C)
            preds = log_probs.permute(1, 0, 2).argmax(dim=-1)[0].cpu().numpy()
            recognized_text = self.vocab.decode(preds)

        return recognized_text


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        recognizer = CRNNRecognizer()
        res = recognizer.predict(img_path)
        print(f"\nRecognized Text:\n{res}")
    else:
        print("Usage: python predict_crnn.py <image_path>")
