# Shared setup — working on EchoBoard with a team

This guide configures EchoBoard so that **two or more people share one
dataset without anyone having to keep a server running.** Uploads made by
one person are immediately visible to everyone else.

Everything lives in a single **Supabase** project: image metadata in
PostgreSQL, and the image files in Supabase Storage. One account, one set of
credentials, no card required on the free tier.

## Why no one needs to host anything

EchoBoard has three moving parts, and only the first two hold state:

| Component | Location | Shared? |
|---|---|---|
| **Supabase Postgres** — dataset metadata (ECHD schema) | Managed cloud | Yes, one project for the team |
| **Supabase Storage** — the keyframe images | Managed cloud | Yes, same project |
| **FastAPI backend + dashboard** | Each person's own machine | No — and it doesn't need to be |

The backend is **stateless**: it holds no dataset of its own and only
translates between the browser and Supabase. Two people can therefore run
their own local copy at the same time, pointed at the same project, and see
identical data. Nobody is the "host", and no machine has to stay awake for
the other person.

```
  Person A                          Person B
  ┌─────────────────┐               ┌─────────────────┐
  │ dashboard :5173 │               │ dashboard :5173 │
  │ backend   :8000 │               │ backend   :8000 │
  └────────┬────────┘               └────────┬────────┘
           │                                 │
           └────────────┬────────────────────┘
                        ▼
         ┌──────────────────────────────┐
         │  Supabase project            │
         │   • Postgres  (metadata)     │
         │   • Storage   (images)       │
         └──────────────────────────────┘
```

### Free-tier limits worth knowing

The Supabase free tier includes **500 MB of database** and **1 GB of file
storage**, and pauses a project after a week of inactivity (one click
resumes it). Metadata rows are tiny, so storage is the ceiling that matters:
roughly 3,000–10,000 keyframes at typical classroom-board JPEG sizes. Check
**Project Settings > Usage** as the dataset grows.

## One-time setup (done once, by one person)

### 1. Create the Supabase project

1. Sign up at <https://supabase.com> and create a new project.
2. Choose a region near you and save the database password Supabase
   generates (you will not need it for EchoBoard, but losing it is
   inconvenient).
3. Wait for provisioning to finish — about two minutes.

### 2. Apply the database schema

1. Open **SQL Editor** in the Supabase dashboard.
2. Paste the entire contents of [`supabase/schema.sql`](../supabase/schema.sql)
   and press **Run**.

This creates four tables (`dataset_images`, `annotations`, `videos`,
`dataset_versions`), their indexes, and the two ID-generating functions. The
script is idempotent, so re-running it is harmless.

Row Level Security is enabled with no policies, which means anonymous and
signed-in browser clients cannot touch these tables. The backend uses the
`service_role` key, which bypasses RLS by design.

### 3. Collect the credentials

From **Project Settings > API**, copy:

- **Project URL** — `https://<project-ref>.supabase.co`
- **`service_role` key** (under Project API keys, "reveal")

The `service_role` key is a full administrative credential. Keep it
server-side, never put it in the dashboard/frontend, and never commit it.
Do **not** use the `anon` key: RLS will reject it.

### 4. Share the credentials

Send the project URL and `service_role` key to your teammate over a private
channel. **Never commit them** — `.env` is gitignored and the repository
contains only `.env.example`.

The storage bucket is created automatically on first backend start. If your
key is not permitted to create buckets, make one manually in
**Storage > New bucket**, name it `echoboard-dataset`, and keep it
**private**.

## Per-person setup (each collaborator, on their own machine)

```bash
git clone https://github.com/Shanmukha-Gautam-Pidaparthi/EchoBoard.git
cd EchoBoard

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then fill in the shared values
```

Fill in `.env`:

```ini
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>

STORAGE_BACKEND=supabase
SUPABASE_BUCKET=echoboard-dataset
```

Then start the two processes, in separate terminals:

```bash
python -m uvicorn backend.api:app --reload --port 8000   # or: scripts\run_backend.bat
cd dashboard && npm install && npm run dev
```

Open <http://localhost:5173>. Both people run exactly this, at the same
time, independently.

### Verifying it works

On startup the backend prints both backends:

```
  Database: Supabase — https://<project-ref>.supabase.co [OK] Connected
  Storage: Supabase Storage bucket 'echoboard-dataset'
```

Have one person upload a video, then have the other refresh their own
dashboard. The keyframes should appear. If they do, the shared setup is
correct.

## The dataset and metadata

Each image is one `dataset_images` row plus zero or more `annotations` rows.
The API returns them in the original nested ECHD shape, so the stored
metadata is exactly what a training pipeline needs:

| Group | Fields | Why it matters for training |
|---|---|---|
| Identity | `image_id` (IMG0001), `image_name`, `image_path` | Joins a label to its image bytes |
| Provenance | `sequence_id`, `subject`, `board_type`, `writer_id`, `video_id`, `frame_index`, `timestamp_ms`, `change_score` | Lets you split by lesson or writer so the same board does not appear in both train and test |
| `image_metadata` | `width`, `height`, `format`, `size_kb` | Filter or bucket by resolution without reading every file |
| `annotations[]` | `annotation_id`, `class`, `bbox`, `text`, `latex`, `confidence` | The labels themselves |
| `quality_metadata` | `blur_score`, `lighting_score`, `duplicate`, `occluded`, `selected` | Exclude unusable samples |
| `processing_status` | `ocr_completed`, `annotation_completed`, `reviewed` | Train only on human-verified labels |

### Bulk-ingesting a folder of images

The dashboard upload suits a handful of files. For a whole folder, use the
script: it records the provenance the browser upload leaves empty, measures
image sharpness (variance of the Laplacian) into `blur_score`, skips images
already ingested so it can be re-run, and can attach transcriptions from a
labels file.

```bash
# Preview without writing anything
python scripts/ingest_folder.py ./boards \
    --subject Physics --writer-id teacher_a \
    --sequence-id physics_lec1 --dry-run

# Ingest, attaching labels
python scripts/ingest_folder.py ./boards \
    --subject Physics --writer-id teacher_a \
    --sequence-id physics_lec1 --labels labels.json
```

`--labels` takes a JSON object keyed by image filename:

```json
{
  "board_001.jpg": {
    "lines": ["Newton's Laws", "F = ma"],
    "regions": [
      {"class": "Header",   "text": "Newton's Laws", "confidence": 0.9},
      {"class": "Equation", "text": "F = ma", "latex": "F = ma"}
    ],
    "lighting_score": 70,
    "occluded": false,
    "duplicate": false
  }
}
```

Use `lines` for a plain line-by-line transcription, `regions` for control
over class, bbox and LaTeX. Both may be given; a combined `FullBoard`
annotation is added automatically when there are several lines.

Labels loaded this way are always written with `reviewed=false`. Machine
transcriptions — whether from the OCR endpoint or a vision model — are a
first pass to speed up human labelling, not ground truth. Verify them in
the Dataset Explorer, which sets `reviewed=true`, and train on verified
rows so your accuracy figures mean what they claim.

### Exporting for training

`GET /api/download/dataset` (the dashboard's Download button) returns a ZIP
containing the images in their bucket layout plus:

- `metadata.json` — the complete ECHD record for every exported image
- `annotations.csv` — a flat `image_path`-to-label table for data loaders

Because `image_path` in both manifests matches the archive member paths, the
export can be fed to a training script without touching Supabase.

To query directly instead, the `writer_id` and `reviewed` columns are
indexed, so a reviewed-only, writer-disjoint split is a plain SQL query in
the Supabase SQL Editor.

## Migrating images you already have locally

If you previously ran with local or MinIO storage, your images are in
`dataset/echoboard-dataset/` and not yet in Supabase. After configuring
`.env`, upload them once:

```bash
python scripts/sync_local_to_bucket.py --dry-run   # preview
python scripts/sync_local_to_bucket.py             # upload
```

Objects already present are skipped, so the script is safe to re-run. Note
this migrates image **bytes** only; metadata rows written to a previous
MongoDB instance are not carried over.

## Working offline

Set `STORAGE_BACKEND=local` to write images to `dataset/echoboard-dataset/`
instead of the bucket. Images saved this way are **not** visible to
collaborators until you run the sync script above. Metadata still goes to
the shared Supabase project, so prefer this only for short offline sessions
— or the rows you add will reference images only your machine holds.

## Troubleshooting

**`the ECHD schema is missing`** — step 2 has not been run against this
project. Apply `supabase/schema.sql` in the SQL Editor.

**`Could not find the function public.next_image_id`** or a missing table
that you know exists — Supabase caches the API schema. Run
`NOTIFY pgrst, 'reload schema';` in the SQL Editor, or toggle
**Project Settings > API > Restart server**.

**`Missing required Supabase settings`** — `.env` is absent or incomplete.
Copy `.env.example` and fill both `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.

**Row-level-security or permission errors on insert** — you are almost
certainly using the `anon` key. Switch to `service_role`.

**Bucket could not be created** — create `echoboard-dataset` manually under
Storage, keep it private, and restart the backend.

**The backend refuses to start on a database or storage error.** This is
deliberate. Metadata is shared, so silently writing images to one machine's
disk would register rows every collaborator can see but nobody else can
read. Fix the configuration, or set `STORAGE_BACKEND=local` explicitly.

**A project that went idle** — free projects pause after ~1 week of
inactivity. Resume it from the Supabase dashboard.

## A note on security

The API has **no authentication**, and CORS is restricted to localhost
origins by default. This is safe while each person runs the backend on their
own machine. Do not expose port 8000 to the internet or widen
`CORS_ORIGINS` without adding authentication first — every endpoint,
including image deletion and full-dataset export, would otherwise be open to
anyone with the URL, and the backend holds a `service_role` key.
