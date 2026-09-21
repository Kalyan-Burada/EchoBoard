# Shared setup — working on EchoBoard with a team

This guide configures EchoBoard so that **two or more people share one
dataset without anyone having to keep a server running.** Uploads made by
one person are immediately visible to everyone else.

## Why no one needs to host anything

EchoBoard has three moving parts, and only the first two hold state:

| Component | Location | Shared? |
|---|---|---|
| **MongoDB Atlas** — dataset metadata (ECHD schema) | Managed cloud | Yes, one cluster for the team |
| **Object storage** — the keyframe images | Managed cloud bucket | Yes, one bucket for the team |
| **FastAPI backend + dashboard** | Each person's own machine | No — and it doesn't need to be |

The backend is **stateless**: it holds no dataset of its own, and only
translates between the browser and those two cloud services. Two people can
therefore run their own local copy at the same time, pointed at the same
cloud resources, and see identical data. Nobody is the "host", and no
machine has to stay awake for the other person.

This replaces the earlier arrangement, where images lived in a MinIO server
on one laptop. That required the laptop's owner to keep a terminal running,
and broke whenever they closed it.

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
         │  MongoDB Atlas  (metadata)   │
         │  Object bucket  (images)     │
         └──────────────────────────────┘
```

## One-time setup (done once, by one person)

### 1. MongoDB Atlas

1. Create a free **M0** cluster at <https://www.mongodb.com/atlas>.
2. **Database Access** → add a database user; save the password.
3. **Network Access** → add the IP addresses of everyone on the team.
   `0.0.0.0/0` works but allows connections from anywhere; prefer listing
   real addresses where you can.
4. **Connect → Drivers** → copy the `mongodb+srv://...` connection string.

### 2. Object storage bucket

Any S3-compatible provider works, since EchoBoard talks to all of them
through one client. **Cloudflare R2** is the recommended default: its free
tier includes 10 GB of storage and, unlike most alternatives, charges
nothing for egress — which matters because annotation and dataset export
read images repeatedly.

1. In the Cloudflare dashboard, open **R2** and create a bucket named
   `echoboard-dataset`.
2. Go to **R2 → API → Manage API Tokens** and create a token with
   **Object Read & Write** permission, scoped to that bucket.
3. Record the **Access Key ID**, **Secret Access Key**, and your
   **Account ID** (the endpoint is `<account-id>.r2.cloudflarestorage.com`).

Equivalent alternatives: **Backblaze B2** (10 GB free; egress capped at 3×
stored bytes per day) or **Amazon S3**. For either, set `S3_ENDPOINT` and
`S3_REGION` to that provider's values — no code changes are needed.

### 3. Share the credentials

Send the connection string and the three bucket values to your teammate
over a private channel. **Never commit them** — `.env` is gitignored, and
the repository contains only `.env.example`.

## Per-person setup (each collaborator, on their own machine)

```bash
git clone https://github.com/Shanmukha-Gautam-Pidaparthi/EchoBoard.git
cd EchoBoard

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then fill in the shared values
```

Fill in `.env` with the values from the one-time setup:

```ini
MONGODB_URI=mongodb+srv://...
DATABASE_NAME=EchoBoardDB

STORAGE_BACKEND=s3
S3_ENDPOINT=<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY=<access-key-id>
S3_SECRET_KEY=<secret-access-key>
S3_BUCKET=echoboard-dataset
S3_REGION=auto
S3_SECURE=true
```

Then start the two processes, in separate terminals:

```bash
python -m uvicorn backend.api:app --reload --port 8000   # or: scripts\run_backend.bat
cd dashboard && npm install && npm run dev
```

Open <http://localhost:5173>. Both people run exactly this, at the same
time, independently.

### Verifying it works

On startup the backend prints the active storage backend:

```
  Storage: S3-compatible bucket 'echoboard-dataset' (https://<account-id>.r2.cloudflarestorage.com)
```

Have one person upload a video, then have the other refresh their own
dashboard. The keyframes should appear. If they do, the shared setup is
correct.

## Migrating images you already have locally

If you used the old local/MinIO storage, your images are in
`dataset/echoboard-dataset/` and are not yet in the shared bucket. After
configuring `.env` as above, upload them once:

```bash
python scripts/sync_local_to_bucket.py --dry-run   # preview
python scripts/sync_local_to_bucket.py             # upload
```

Objects already present in the bucket are skipped, so the script is safe to
re-run.

## Working offline

Set `STORAGE_BACKEND=local` to write images to `dataset/echoboard-dataset/`
instead of the bucket. Images saved this way are **not** visible to
collaborators until you run the sync script above. If you also want an
isolated metadata store, point `DATABASE_NAME` at a different database name
so you do not add rows the team can see but cannot read.

## Troubleshooting

**`Bucket 'echoboard-dataset' was not found`** — the bucket must be created
in the provider console; EchoBoard does not create it, because API tokens
are normally scoped to a single existing bucket. Check `S3_BUCKET` for
typos.

**`Could not reach the object store`** — verify `S3_ENDPOINT` has no
`https://` prefix, that `S3_SECURE=true` for cloud providers, and that
`S3_REGION=auto` when using R2.

**The backend refuses to start on a storage error.** This is deliberate.
Metadata is shared, so silently writing images to one machine's disk would
register rows that every collaborator can see but nobody else can read. Fix
the configuration, or set `STORAGE_BACKEND=local` explicitly.

**MongoDB connection timeouts** — your current IP is probably not in the
Atlas Network Access list. Home IP addresses change; re-add yours.

## A note on security

The API has **no authentication**, and CORS is restricted to localhost
origins by default. This is safe while each person runs the backend on their
own machine. Do not expose port 8000 to the internet or widen
`CORS_ORIGINS` without adding authentication first — every endpoint,
including image deletion and full-dataset export, would otherwise be open
to anyone with the URL.
