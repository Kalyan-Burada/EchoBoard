"""
crnn_model.py
Deep Learning Handwriting Recognition Model:
CRNN Architecture = Convolutional Feature Extractor (CNN)
                  + Recurrent Sequence Modeling (Bidirectional LSTM)
                  + Transcription Layer (Linear + CTC Decoder)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class CRNN(nn.Module):
    """
    CRNN (Convolutional Recurrent Neural Network) for text & handwriting recognition.
    
    Architecture:
      1. CNN Backbone: Extracts spatial visual feature maps from board text image crops.
      2. Map-to-Sequence: Collapses height dimension and orders feature vectors sequentially along width (time).
      3. Recurrent Layer: 2-layer Bidirectional LSTM to capture contextual relationships between characters.
      4. Fully-Connected Head: Predicts character class probabilities for each time step.
    """
    def __init__(self, img_channels=1, num_classes=100, hidden_size=256, rnn_layers=2):
        super(CRNN, self).__init__()
        self.num_classes = num_classes

        # -------------------------------------------------------------
        # 1. Convolutional Feature Extractor (CNN)
        # -------------------------------------------------------------
        # Input shape: (Batch, img_channels, H=32, W)
        self.cnn = nn.Sequential(
            # Block 1: 32 -> 16
            nn.Conv2d(img_channels, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),

            # Block 2: 16 -> 8
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),

            # Block 3: 8 -> 8
            nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            # Downsample only along height to preserve horizontal sequence resolution
            nn.MaxPool2d(kernel_size=(2, 1), stride=(2, 1)),

            # Block 4: 4 -> 4
            nn.Conv2d(256, 512, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(2, 1), stride=(2, 1)),

            # Block 5: 2 -> 1
            nn.Conv2d(512, 512, kernel_size=(2, 1), stride=1, padding=0),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
        )

        # -------------------------------------------------------------
        # 2. Recurrent Sequence Modeling (Bidirectional LSTM)
        # -------------------------------------------------------------
        self.rnn = nn.LSTM(
            input_size=512,
            hidden_size=hidden_size,
            num_layers=rnn_layers,
            bidirectional=True,
            batch_first=True,
            dropout=0.2 if rnn_layers > 1 else 0.0,
        )

        # -------------------------------------------------------------
        # 3. Transcription Layer
        # -------------------------------------------------------------
        # Bidirectional LSTM produces 2 * hidden_size output features
        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        """
        Forward pass.
        Args:
            x: Tensor of shape (Batch, Channels, Height=32, Width)
        Returns:
            log_probs: Tensor of shape (Time, Batch, num_classes) for CTCLoss
        """
        # 1. Extract visual features
        features = self.cnn(x)  # (B, 512, 1, W')

        # 2. Reshape for RNN: (B, 512, W') -> (B, W', 512)
        features = features.squeeze(2).permute(0, 2, 1)

        # 3. Process sequence with BiLSTM: (B, W', 2*hidden_size)
        rnn_out, _ = self.rnn(features)

        # 4. Project to vocabulary classes: (B, W', num_classes)
        logits = self.fc(rnn_out)

        # 5. Compute Log-Softmax along class dimension
        # CTCLoss expects (Time, Batch, Classes)
        log_probs = F.log_softmax(logits, dim=-1).permute(1, 0, 2)

        return log_probs
