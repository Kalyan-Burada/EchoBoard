# EchoBoard

*Every Lesson Preserved. Every Concept Searchable.*

EchoBoard builds the **EchoBoard Classroom Handwriting Dataset (ECHD)**: a
structured dataset of classroom board images extracted automatically from
lecture recordings.

Rather than storing hours of raw video, EchoBoard detects the moments when
the writing on a board has *settled* — finished being written and not yet
erased — and keeps those frames as dataset images with full provenance
metadata. The result is a compact, searchable, annotatable corpus suitable
for training handwriting-recognition models.

This repository is the **dataset creation module**. It covers ingestion,
keyframe extraction, storage, metadata registration, annotation and export.
Downstream recognition models (YOLO, MobileNet, Bi-LSTM) are later phases
and are not implemented here.

---

## Architecture

```
  dashboard/                     React 19 + Vite + Tailwind
        │  REST over HTTP
        ▼
  backend/api.py                 FastAPI (uvicorn, port 8000)
        ├── video_processor.py   OpenCV keyframe detection, yt-dlp ingest
        ├── storage.py           S3-compatible object storage (images)
        └── database.py          MongoDB Atlas (ECHD metadata)
```

State lives entirely in two managed cloud services — MongoDB Atlas for
metadata and an S3-compatible bucket for image bytes. The backend itself is
stateless, so **every collaborator runs their own local copy against the
same shared data.** No one has to host a server or keep a terminal open for
anyone else. See **[docs/SHARED_SETUP.md](docs/SHARED_SETUP.md)**.

---

## How the capture algorithm works

The extraction stage (`backend/video_processor.py`) is the substantive part
of the pipeline. For each sampled frame it:

1. Converts to grayscale and applies a **morphological filter**, suppressing
   noise and transient occlusions such as the lecturer's hand or body.
2. Computes a **frame-difference score** — the fraction of pixels that
   changed against the previous frame, thresholded to discard sensor noise.
3. Tracks consecutive **"calm" frames**, where motion falls below
   `motion_threshold`. Sustained calm means writing has stopped.
4. Once `stable_frames_required` calm frames accumulate, compares the
   candidate against the **last saved keyframe**. It is only kept if at
   least `new_content_threshold` of the image differs — this is what
   prevents near-duplicate captures of the same board state.

Tunable parameters, with defaults:

| Parameter | Default | Meaning |
|---|---|---|
| `sample_every_n_frames` | 3 | Frame sampling stride (throughput vs. precision) |
| `motion_threshold` | 0.03 | Below this changed-pixel fraction, the frame is "calm" |
| `stable_frames_required` | 4 | Calm frames needed before capture |
| `new_content_threshold` | 0.05 | Minimum novelty vs. the last saved keyframe |

Raise `motion_threshold` for shaky handheld footage; lower
`new_content_threshold` to capture incremental additions to a board.

---

## Pipeline stages

| Stage | Responsibility |
|---|---|
| 1–3 | Video ingest (file upload or URL via yt-dlp) and keyframe extraction |
| 4 | Direct upload of individual board images |
| 5 | Original images stored byte-for-byte in object storage — no compression or cropping |
| 6 | Metadata registered in MongoDB under the ECHD schema |
| 7 | Annotation queue, including OCR-assisted auto-annotation and human verification |
| 9–12 | Dataset versioning and ZIP export |

---

## Setup

For the shared two-person configuration, follow
**[docs/SHARED_SETUP.md](docs/SHARED_SETUP.md)** — it covers the Atlas
cluster, the storage bucket, and credential sharing. The short version:

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # fill in MongoDB + bucket credentials
```

Run the backend and the dashboard in separate terminals:

```bash
python -m uvicorn backend.api:app --reload --port 8000    # or: scripts\run_backend.bat
cd dashboard && npm install && npm run dev
```

The dashboard is served at <http://localhost:5173> and the API docs at
<http://localhost:8000/docs>.

### Configuration

All backend settings are read from `.env`; see
[`.env.example`](.env.example) for the annotated list. The essentials:

| Variable | Purpose |
|---|---|
| `MONGODB_URI`, `DATABASE_NAME` | Metadata store |
| `STORAGE_BACKEND` | `s3` for shared work, `local` for offline development |
| `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION`, `S3_SECURE` | Object storage |
| `CORS_ORIGINS` | Allowed dashboard origins (defaults to localhost) |

Frontend settings live in [`dashboard/.env.example`](dashboard/.env.example);
`VITE_API_BASE` points the dashboard at a backend other than localhost.

`.env` files are gitignored and must never be committed.

---

## API reference

Interactive documentation is generated at `/docs` when the backend is
running. Principal endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/stats` | Dataset counts for the dashboard |
| `POST` | `/api/upload/video` | Upload a video file and extract keyframes |
| `POST` | `/api/upload/url` | Ingest from a URL via yt-dlp (background task) |
| `POST` | `/api/upload/images` | Upload board images directly |
| `GET` | `/api/videos`, `/api/videos/{id}/keyframes` | Video and keyframe listings |
| `POST` | `/api/videos/{id}/stop` | Halt in-progress processing |
| `GET` | `/api/dataset/images` | Browse dataset images |
| `POST` | `/api/dataset/images/{id}/ocr` | OCR-assisted auto-annotation |
| `PUT` | `/api/dataset/images/{id}/annotation` | Save a verified annotation |
| `GET` | `/api/download/dataset` | Export the full dataset as a ZIP |

---

## Repository layout

```
backend/
  api.py               FastAPI application and all REST endpoints
  video_processor.py   Keyframe detection engine
  storage.py           Object storage layer (S3-compatible or local)
  database.py          MongoDB Atlas layer, ECHD schema
dashboard/
  src/components/      Upload panel, dataset explorer, annotation UI
  src/api.js           Typed API client for the backend
scripts/
  run_backend.bat            Windows convenience launcher
  sync_local_to_bucket.py    Migrate local images into the shared bucket
  fix_stuck_videos.py        Clear videos left with processing=True
docs/
  SHARED_SETUP.md      Multi-collaborator setup guide
```

---

## Security

The API has **no authentication**, and CORS is limited to localhost origins
by default. Both are appropriate while each collaborator runs the backend
on their own machine, which is the supported deployment model. Do not
expose port 8000 publicly or widen `CORS_ORIGINS` without adding
authentication: every endpoint — including image deletion and full-dataset
export — would otherwise be reachable by anyone with the URL.

---

## Roadmap

- Board region detection (YOLO) to crop board area from the wider frame
- Handwriting recognition (MobileNet + Bi-LSTM + CTC) replacing OCR assistance
- Concept-level indexing and semantic search across lessons
- Inter-annotator agreement metrics for the verification workflow

---

## License

See [LICENSE](LICENSE).
