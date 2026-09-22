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
        ├── storage.py           Supabase Storage (image files)
        └── database.py          Supabase Postgres (ECHD metadata)
```

State lives entirely in one managed **Supabase** project: PostgreSQL for
metadata and Supabase Storage for the image bytes. The backend itself is
stateless, so **every collaborator runs their own local copy against the
same shared project.** No one has to host a server or keep a terminal open
for anyone else. See **[docs/SHARED_SETUP.md](docs/SHARED_SETUP.md)**.

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
| 5 | Original images stored byte-for-byte in Supabase Storage — no compression or cropping |
| 6 | Metadata registered in Supabase Postgres under the ECHD schema |
| 7 | Annotation queue, including OCR-assisted auto-annotation and human verification |
| 9–12 | Dataset versioning, and ZIP export bundling images with `metadata.json` + `annotations.csv` |

---

## Dataset metadata

Every image is one `dataset_images` row plus its `annotations` rows, and the
API returns them in the nested ECHD shape:

```json
{
  "image_id": "IMG0001",
  "image_path": "physics/physics_lec1/frame0001.jpg",
  "sequence_id": "physics_lec1", "subject": "Physics",
  "board_type": "Blackboard",    "writer_id": "teacher_a",
  "video_id": "…", "frame_index": 120, "timestamp_ms": 4800,
  "change_score": 0.42, "dataset_version": "ECHD_v1",
  "image_metadata":    { "width": 1920, "height": 1080, "format": "jpg", "size_kb": 143 },
  "annotations":       [ { "annotation_id": "ANN0001", "class": "Equation",
                           "bbox": [], "text": "F = ma", "latex": "",
                           "confidence": 1.0 } ],
  "quality_metadata":  { "blur_score": 0.0, "lighting_score": 0, "duplicate": false,
                         "occluded": false, "selected": true },
  "processing_status": { "ocr_completed": true, "annotation_completed": true,
                         "reviewed": true }
}
```

The provenance fields exist so a training split can be made without leakage:
`writer_id` and `sequence_id` let you hold out entire writers or lessons
rather than splitting frames of the same board across train and test, and
`processing_status.reviewed` restricts training to human-verified labels.

See [docs/SHARED_SETUP.md](docs/SHARED_SETUP.md#the-dataset-and-metadata)
for the field-by-field rationale and the export format.

---

## Setup

For the shared two-person configuration, follow
**[docs/SHARED_SETUP.md](docs/SHARED_SETUP.md)** — it covers creating the
Supabase project, applying the schema, and sharing credentials. The short
version:

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # fill in your Supabase URL + service_role key
```

Apply the database schema once per Supabase project: paste
[`supabase/schema.sql`](supabase/schema.sql) into the Supabase SQL Editor
and run it.

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
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | `service_role` key — server-side only, never commit |
| `STORAGE_BACKEND` | `supabase` for shared work, `local` for offline development |
| `SUPABASE_BUCKET` | Storage bucket name (default `echoboard-dataset`) |
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
| `GET` | `/api/download/dataset` | Export images + `metadata.json` + `annotations.csv` as a ZIP |

---

## Repository layout

```
backend/
  api.py               FastAPI application and all REST endpoints
  video_processor.py   Keyframe detection engine
  storage.py           Supabase Storage layer (or local, for offline work)
  database.py          Supabase Postgres layer, ECHD schema
supabase/
  schema.sql           Database schema — apply once in the SQL Editor
dashboard/
  src/components/      Upload panel, dataset explorer, annotation UI
  src/api.js           Typed API client for the backend
scripts/
  run_backend.bat            Windows convenience launcher
  ingest_folder.py           Bulk-ingest a folder of images, with labels
  sync_local_to_bucket.py    Migrate local images into the shared bucket
  fix_stuck_videos.py        Clear videos left with processing=True
docs/
  SHARED_SETUP.md      Multi-collaborator setup guide
```

---

## Security

The API has **no authentication**, and CORS is limited to localhost origins
by default. Both are appropriate while each collaborator runs the backend
on their own machine, which is the supported deployment model.

The backend holds the Supabase `service_role` key, which bypasses Row Level
Security. Keep it in `.env` (gitignored), never in the dashboard bundle, and
never in a commit. Do not expose port 8000 publicly or widen
`CORS_ORIGINS` without adding authentication: every endpoint — including
image deletion and full-dataset export — would otherwise be reachable by
anyone with the URL.

---

## Roadmap

- Board region detection (YOLO) to crop board area from the wider frame
- Handwriting recognition (MobileNet + Bi-LSTM + CTC) replacing OCR assistance
- Concept-level indexing and semantic search across lessons
- Inter-annotator agreement metrics for the verification workflow

---

## License

See [LICENSE](LICENSE).
