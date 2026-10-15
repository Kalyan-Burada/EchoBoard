# EchoBoard Classroom Handwriting Dataset (ECHD) — Dataset Documentation & Data Dictionary

## 1. Dataset Overview
* **Dataset Name:** EchoBoard Classroom Handwriting Dataset (ECHD)
* **Version:** 1.0 (ECHD_v1)
* **Format:** Compressed Archive (`.zip`), JSON (`metadata.json`), CSV (`annotations.csv`), and JPEG/PNG Images.
* **Domain:** Computer Vision / Document Analysis / Handwritten Text Recognition (HTR) / Scene Text Recognition (STR).
* **Media Types:** Classroom Blackboards (Chalk) and Whiteboards (Dry-erase Marker).

ECHD is an educational scene-text dataset extracted from classroom lecture recordings and high-resolution board captures. It addresses the real-world domain gap between clean, flat-scanned document handwriting and natural classroom lecture boards (which feature chalk dust, marker fading, directional lighting, occlusions, and varied handwriting styles).

---

## 2. Directory & Archive Structure

When uncompressed, the dataset archive is organized as follows:

```
echoboard_dataset/
├── images/
│   ├── IMG0001_board_0001.jpg
│   ├── IMG0002_board_0002.jpg
│   └── ...
├── metadata.json       # Complete hierarchical JSON records with full provenance
├── annotations.csv     # Flat tabular CSV for rapid integration with PyTorch/TensorFlow DataLoader
└── README.md           # Dataset summary and attribution
```

---

## 3. Data Dictionary

### 3.1 `annotations.csv`
A flattened representation suited for standard tabular parsing and model data-loaders.

| Column Name | Data Type | Description | Example Values |
|---|---|---|---|
| `image_id` | String | Unique sample identifier | `"IMG0001"`, `"IMG0042"` |
| `image_path` | String | Relative filepath to the image within the archive | `"images/IMG0001_board_0001.jpg"` |
| `subject` | String | Academic subject or lecture topic | `"Mathematics"`, `"Physics"`, `"General"` |
| `board_type` | String | Substrate type of the board | `"Blackboard"`, `"Whiteboard"` |
| `writer_id` | String | Anonymized lecturer/instructor identifier (used for writer-independent splits) | `"teacher_a"`, `"prof_01"` |
| `sequence_id` | String | Lecture session or video sequence ID | `"physics_lec1"` |
| `video_id` | String | Source video UUID (if extracted from video) | `"7c9e6679-7425-40de-944b-..."` |
| `frame_index` | Integer | Frame index in original video stream | `120`, `450` |
| `timestamp_ms`| Integer | Timestamp in milliseconds within source video | `4800` |
| `width` | Integer | Image width in pixels | `1920`, `1280` |
| `height` | Integer | Image height in pixels | `1080`, `720` |
| `annotation_class` | String | Semantic class of the text content | `"Text"`, `"Equation"`, `"Header"` |
| `annotation_text` | String | Ground truth transcription (case and punctuation preserved) | `"F = ma"`, `"Linear Algebra"` |
| `reviewed` | Boolean | Verification flag (`true` indicates human review) | `true`, `false` |
| `dataset_version` | String | ECHD schema version identifier | `"ECHD_v1"` |

---

### 3.2 `metadata.json`
The complete structured record containing extended quality scores and bounding regions:

```json
{
  "dataset": "EchoBoard Classroom Handwriting Dataset (ECHD)",
  "exported_at": "2026-10-14T23:30:00Z",
  "image_count": 5000,
  "images": [
    {
      "image_id": "IMG0001",
      "image_path": "images/IMG0001_board_0001.jpg",
      "sequence_id": "physics_lec1",
      "subject": "Physics",
      "board_type": "Blackboard",
      "writer_id": "teacher_a",
      "video_id": "7c9e6679-7425-40de-944b-9e45e54d80d2",
      "frame_index": 120,
      "timestamp_ms": 4800,
      "change_score": 0.42,
      "dataset_version": "ECHD_v1",
      "image_metadata": {
        "width": 1920,
        "height": 1080,
        "format": "jpg",
        "size_kb": 143
      },
      "annotations": [
        {
          "annotation_id": "ANN0001",
          "class": "Equation",
          "bbox": [120, 240, 520, 310],
          "text": "F = ma",
          "latex": "F = ma",
          "confidence": 1.0
        }
      ],
      "quality_metadata": {
        "blur_score": 0.05,
        "lighting_score": 75.0,
        "duplicate": false,
        "occluded": false,
        "selected": true
      },
      "processing_status": {
        "ocr_completed": true,
        "annotation_completed": true,
        "reviewed": true
      }
    }
  ]
}
```

---

## 4. Train / Validation / Test Splitting Recommendation
To avoid **data leakage**, do NOT partition samples uniformly at random across consecutive frames:
1. **Writer-Independent Split (Recommended):** Partition based on `writer_id`. Use distinct writers exclusively for testing to evaluate model generalization to unseen handwriting styles.
2. **Session-Independent Split:** Partition based on `sequence_id` or `video_id` so that multiple frames of the same board presentation are kept in the same split.
3. **Quality Filtering:** Restrict primary evaluation to samples where `reviewed == True` and `quality_metadata.occluded == False`.

---

## 5. Usage with PyTorch

```python
import pandas as pd
from PIL import Image
from torch.utils.data import Dataset

class ECHDDataset(Dataset):
    def __init__(self, csv_file, root_dir, transform=None, reviewed_only=True):
        self.df = pd.read_csv(csv_file)
        if reviewed_only:
            self.df = self.df[self.df["reviewed"] == True]
        self.root_dir = root_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = f"{self.root_dir}/{row['image_path']}"
        image = Image.open(img_path).convert("RGB")
        text = str(row["annotation_text"])

        if self.transform:
            image = self.transform(image)

        return image, text
```
