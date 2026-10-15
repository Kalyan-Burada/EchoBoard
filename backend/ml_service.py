"""
backend/ml_service.py
Service for running inference with the trained Deep Learning models:
1. CRNN Recognizer: CNN + Bi-LSTM + CTC for handwritten text transcription
2. CNN Classifier: ResNet-50 for Equation vs Text classification
"""

import os
import sys
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "ml"))

# Model paths
CRNN_MODEL_PATH = os.path.join(REPO_ROOT, "ml", "best_crnn_model.pt")
CRNN_ALT_PATH = os.path.join(os.path.dirname(REPO_ROOT), "best_crnn_model.pt")
CNN_MODEL_PATH = os.path.join(os.path.dirname(REPO_ROOT), "best_model.pt")
CNN_ALT_PATH = os.path.join(REPO_ROOT, "best_model.pt")


class CRNNRecognizer:
    def __init__(self, checkpoint_path=None):
        if checkpoint_path is None:
            if os.path.exists(CRNN_MODEL_PATH):
                checkpoint_path = CRNN_MODEL_PATH
            elif os.path.exists(CRNN_ALT_PATH):
                checkpoint_path = CRNN_ALT_PATH
            else:
                checkpoint_path = None

        self.available = False
        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                from crnn_model import CRNN
                from dataset_loader import TextVocabulary

                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                checkpoint = torch.load(checkpoint_path, map_location=self.device)

                vocab_dict = checkpoint["vocab"]
                self.vocab = TextVocabulary.__new__(TextVocabulary)
                self.vocab.blank_idx = 0
                self.vocab.char2idx = vocab_dict["char2idx"]
                self.vocab.idx2char = {int(k): v for k, v in vocab_dict["idx2char"].items()}

                config = checkpoint.get("config", {})
                self.target_height = config.get("target_height", 32)
                self.target_width = config.get("target_width", 384)

                self.model = CRNN(
                    img_channels=config.get("img_channels", 1),
                    num_classes=config.get("num_classes", len(self.vocab)),
                    hidden_size=config.get("hidden_size", 256),
                    rnn_layers=config.get("rnn_layers", 2),
                )
                self.model.load_state_dict(checkpoint["model_state_dict"])
                self.model.to(self.device)
                self.model.eval()
                self.available = True
                print(f"[ML Service] Loaded CRNN model from {checkpoint_path} (Device: {self.device})")
            except Exception as e:
                print(f"[ML Service] Error initializing CRNN model: {e}")

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
        tensor = np.expand_dims(tensor, axis=0)  # (1, H, W)
        img_tensor = torch.from_numpy(tensor).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            log_probs = self.model(img_tensor)  # (T, 1, C)
            preds = log_probs.permute(1, 0, 2).argmax(dim=-1)[0].cpu().numpy()
            text = self.vocab.decode(preds)
        return text.strip()

    def predict(self, img_bgr_or_gray):
        if not self.available or img_bgr_or_gray is None or img_bgr_or_gray.size == 0:
            return ""

        try:
            if len(img_bgr_or_gray.shape) == 3:
                gray = cv2.cvtColor(img_bgr_or_gray, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_bgr_or_gray

            h, w = gray.shape[:2]
            if h < 10 or w < 10:
                return ""

            # Check for multiple stacked lines if crop is tall
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
        except Exception as e:
            print(f"[ML Service] CRNN prediction failed: {e}")
            return ""


class CNNClassifier:
    def __init__(self, checkpoint_path=None):
        if checkpoint_path is None:
            if os.path.exists(CNN_MODEL_PATH):
                checkpoint_path = CNN_MODEL_PATH
            elif os.path.exists(CNN_ALT_PATH):
                checkpoint_path = CNN_ALT_PATH
            else:
                checkpoint_path = None

        self.available = False
        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                import torchvision.models as models
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                checkpoint = torch.load(checkpoint_path, map_location=self.device)

                self.classes = checkpoint.get("classes", ["Equation", "Text"])
                self.image_size = checkpoint.get("image_size", 224)

                # ResNet-50
                model = models.resnet50(weights=None)
                in_features = model.fc.in_features
                model.fc = nn.Linear(in_features, len(self.classes))
                model.load_state_dict(checkpoint["state_dict"])
                model.to(self.device)
                model.eval()

                self.model = model
                self.available = True
                print(f"[ML Service] Loaded CNN (ResNet-50) classifier from {checkpoint_path} ({self.classes})")
            except Exception as e:
                print(f"[ML Service] Error initializing CNN model: {e}")

    def predict(self, img_bgr):
        if not self.available:
            return "Text", 0.5

        try:
            if len(img_bgr.shape) == 2:
                rgb = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2RGB)
            else:
                rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

            resized = cv2.resize(rgb, (self.image_size, self.image_size))
            tensor = resized.astype(np.float32) / 255.0

            # Normalize ImageNet
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            tensor = (tensor - mean) / std
            tensor = np.transpose(tensor, (2, 0, 1))  # (3, H, W)
            tensor = torch.from_numpy(tensor).float().unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = F.softmax(logits, dim=1).cpu().numpy()[0]
                pred_idx = int(np.argmax(probs))
                confidence = float(probs[pred_idx])
                pred_class = self.classes[pred_idx]

            return pred_class, confidence
        except Exception as e:
            print(f"[ML Service] CNN prediction failed: {e}")
            return "Text", 0.5


# Singleton instances
_crnn_recognizer = None
_cnn_classifier = None


def get_crnn_recognizer():
    global _crnn_recognizer
    if _crnn_recognizer is None:
        _crnn_recognizer = CRNNRecognizer()
    return _crnn_recognizer


def get_cnn_classifier():
    global _cnn_classifier
    if _cnn_classifier is None:
        _cnn_classifier = CNNClassifier()
    return _cnn_classifier


def process_image_with_ml(image_bytes: bytes):
    """
    Run full AI pipeline:
    1. CNN: Classify whether image is 'Equation' or 'Text'
    2. CRNN: Transcribe handwritten text characters
    3. RapidOCR fallback if CRNN returns blank
    """
    if not image_bytes:
        return {"text": "", "class": "Text", "confidence": 0.0, "source": "none"}

    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"text": "", "class": "Text", "confidence": 0.0, "source": "none"}

    cnn = get_cnn_classifier()
    pred_class, conf = cnn.predict(img)

    crnn = get_crnn_recognizer()
    crnn_text = crnn.predict(img)

    final_text = crnn_text
    source = "CRNN"

    # If CRNN returns empty, fallback to RapidOCR
    if not final_text:
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr_engine = RapidOCR()
            res, _ = ocr_engine(img)
            if res:
                lines = [str(line[1]).strip() for line in res if len(line) >= 2 and line[1]]
                final_text = "\n".join(lines)
                source = "RapidOCR_fallback"
        except Exception:
            pass

    return {
        "text": final_text or "No text recognized",
        "class": pred_class,
        "confidence": conf,
        "source": source,
    }
