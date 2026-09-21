"""
storage.py
EchoBoard Dataset Creation Module — Image Storage Layer

Stores original keyframe images in Supabase Storage, in the same project
that holds the dataset metadata (see backend/database.py). One Supabase
account therefore provides both halves of the dataset, and no collaborator
has to host or keep running an object-storage server.

Two backends are supported, selected explicitly via STORAGE_BACKEND:

  supabase  Supabase Storage bucket. This is the shared backend: every
            collaborator points at the same project, so images uploaded by
            one person are immediately readable by everyone.

  local     Plain filesystem storage under dataset/echoboard-dataset/,
            mirroring the bucket layout. Solo development and offline work
            only.

There is deliberately NO automatic fallback from 'supabase' to 'local'.
Metadata lives in the shared database while bytes live in the bucket;
silently writing bytes to one machine's disk would register rows that every
collaborator can see but nobody else can read. A misconfigured or
unreachable bucket therefore raises instead of degrading quietly, matching
the no-fallback stance in database.py.

Object paths are <subject>/<sequence_id>/<filename> and are stored verbatim
in dataset_images.image_path, so metadata and bytes stay addressable
together for later model training.

IMPORTANT: Images are stored as-is — NO compression, NO cropping,
NO modification of any kind.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ---------------------------------------------------------------------------
# Configuration — loaded from .env (see .env.example)
# ---------------------------------------------------------------------------
# "supabase" (shared bucket) or "local" (filesystem, solo development).
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "supabase").strip().lower()

# Storage reuses the same project credentials as the metadata layer.
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "echoboard-dataset").strip()

# Local filesystem directory (mirrors the bucket structure).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATASET_DIR = os.path.join(os.path.dirname(BASE_DIR), "dataset", "echoboard-dataset")

_VALID_BACKENDS = ("supabase", "local")

# True once init_storage() has verified the Supabase bucket.
USE_SUPABASE = False


class StorageConfigError(RuntimeError):
    """Raised when the storage backend is misconfigured or unreachable."""


def _bucket():
    """Return the Supabase Storage bucket proxy for this project."""
    import database as db

    try:
        client = db.get_client()
    except db.DatabaseConfigError as exc:
        # Storage and metadata share SUPABASE_URL / SUPABASE_SERVICE_KEY.
        raise StorageConfigError(str(exc)) from exc
    return client.storage.from_(SUPABASE_BUCKET)


def init_storage():
    """
    Initialize and verify the configured storage backend.

    Raises StorageConfigError if STORAGE_BACKEND=supabase and the bucket
    cannot be reached, so the API refuses to start rather than writing
    images somewhere collaborators cannot read.
    """
    global USE_SUPABASE

    if STORAGE_BACKEND not in _VALID_BACKENDS:
        raise StorageConfigError(
            f"STORAGE_BACKEND must be one of {_VALID_BACKENDS}, got '{STORAGE_BACKEND}'."
        )

    if STORAGE_BACKEND == "local":
        USE_SUPABASE = False
        os.makedirs(LOCAL_DATASET_DIR, exist_ok=True)
        print(f"  Storage: local filesystem ({LOCAL_DATASET_DIR})")
        print("  NOTE: images are NOT shared with collaborators in this mode.")
        return

    import database as db

    try:
        client = db.get_client()
    except db.DatabaseConfigError as exc:
        raise StorageConfigError(str(exc)) from exc

    try:
        buckets = client.storage.list_buckets()
    except Exception as exc:
        raise StorageConfigError(
            f"Could not reach Supabase Storage: {exc}\n"
            "  Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env "
            "(see docs/SHARED_SETUP.md)."
        ) from exc

    names = {getattr(b, "name", None) or (b.get("name") if isinstance(b, dict) else None)
             for b in (buckets or [])}

    if SUPABASE_BUCKET not in names:
        # The service_role key may create buckets; try once so first-time
        # setup does not require a manual step, and report clearly if the
        # key is not permitted to.
        try:
            client.storage.create_bucket(SUPABASE_BUCKET, options={"public": False})
            print(f"  Created private Supabase Storage bucket '{SUPABASE_BUCKET}'.")
        except Exception as exc:
            raise StorageConfigError(
                f"Supabase Storage bucket '{SUPABASE_BUCKET}' does not exist and "
                f"could not be created automatically: {exc}\n"
                "  Create it once in Supabase Dashboard > Storage > New bucket "
                "(keep it private), then set SUPABASE_BUCKET in .env "
                "(see docs/SHARED_SETUP.md)."
            ) from exc

    USE_SUPABASE = True
    print(f"  Storage: Supabase Storage bucket '{SUPABASE_BUCKET}'")


def _local_path(object_path: str) -> str:
    return os.path.join(LOCAL_DATASET_DIR, object_path.replace("/", os.sep))


def _content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def store_image(image_bytes: bytes, subject: str, sequence_id: str,
                filename: str) -> str:
    """
    Store an original image in the dataset.

    Path structure: <subject>/<sequence_id>/<filename> within the bucket.

    Returns the object path, which is recorded in dataset_images.image_path.

    IMPORTANT: The image is stored AS-IS — no compression, no cropping,
    no modification of any kind.
    """
    parts = [p for p in (subject, sequence_id, filename) if p]
    return store_object("/".join(parts), image_bytes)


def store_object(object_path: str, image_bytes: bytes) -> str:
    """
    Store bytes at an exact object path, returning that path.

    store_image() builds the conventional <subject>/<sequence_id>/<filename>
    path and delegates here. Use this directly when a path already exists,
    for example when migrating local files that are already laid out.
    """
    if USE_SUPABASE:
        # upsert allows re-processing a sequence without a duplicate-object
        # error, matching the previous object-store behaviour.
        _bucket().upload(
            object_path,
            image_bytes,
            file_options={
                "content-type": _content_type(object_path),
                "upsert": "true",
            },
        )
        return object_path

    local_path = _local_path(object_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(image_bytes)
    return object_path


def get_image(object_path: str) -> bytes:
    """
    Retrieve an image by its object path, returning the raw bytes.

    Returns b"" if the object does not exist. If the exact path is missing,
    alternative image extensions are tried, which tolerates historical
    .jpeg/.png mismatches between stored metadata and stored bytes.
    """
    if not object_path:
        return b""

    if USE_SUPABASE:
        bucket = _bucket()
        for candidate in _extension_candidates(object_path):
            try:
                data = bucket.download(candidate)
                if data:
                    return data
            except Exception:
                continue
        return b""

    for candidate in _extension_candidates(object_path):
        local_path = _local_path(candidate)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
    return b""


def _extension_candidates(object_path: str) -> list:
    """The exact path first, then the same path with other image extensions."""
    base, ext = os.path.splitext(object_path)
    candidates = [object_path]
    candidates.extend(
        base + alt for alt in (".jpg", ".jpeg", ".png") if alt != ext.lower()
    )
    return candidates


def delete_image(object_path: str):
    """Delete an image from storage. Missing objects are ignored."""
    if not object_path:
        return

    if USE_SUPABASE:
        _bucket().remove([object_path])
        return

    local_path = _local_path(object_path)
    if os.path.exists(local_path):
        os.unlink(local_path)


def list_images(subject: str = None, sequence_id: str = None) -> list:
    """List all image object paths, optionally filtered by subject/sequence."""
    prefix = ""
    if subject:
        prefix = f"{subject}/"
        if sequence_id:
            prefix = f"{subject}/{sequence_id}/"

    if USE_SUPABASE:
        return _list_supabase(prefix.rstrip("/"))

    results = []
    search_dir = _local_path(prefix) if prefix else LOCAL_DATASET_DIR
    if os.path.exists(search_dir):
        for root, _dirs, files in os.walk(search_dir):
            for name in files:
                if name.lower().endswith((".jpg", ".jpeg", ".png")):
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, LOCAL_DATASET_DIR).replace(os.sep, "/")
                    results.append(rel)
    return results


def _list_supabase(prefix: str, _depth: int = 0) -> list:
    """
    Recursively list image objects under a prefix.

    Supabase Storage lists one folder level at a time, so directories are
    walked explicitly. Entries without an id are folders.
    """
    if _depth > 8:  # Guard against unexpectedly deep nesting.
        return []

    try:
        entries = _bucket().list(prefix) or []
    except Exception:
        return []

    results = []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else getattr(entry, "name", None)
        if not name:
            continue
        child = f"{prefix}/{name}" if prefix else name

        is_folder = (entry.get("id") is None) if isinstance(entry, dict) else False
        if is_folder:
            results.extend(_list_supabase(child, _depth + 1))
        elif name.lower().endswith((".jpg", ".jpeg", ".png")):
            results.append(child)
    return results
