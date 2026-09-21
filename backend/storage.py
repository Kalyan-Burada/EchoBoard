"""
storage.py
EchoBoard Dataset Creation Module — Image Storage Layer

Stores original keyframe images in an S3-compatible object store.

Two backends are supported, selected explicitly via STORAGE_BACKEND:

  s3     Any S3-compatible object store — Cloudflare R2, Backblaze B2,
         Amazon S3, or a self-hosted MinIO server. This is the shared
         backend: every collaborator points at the same bucket, so images
         uploaded by one person are immediately readable by everyone.

  local  Plain filesystem storage under dataset/echoboard-dataset/,
         mirroring the bucket layout. Intended for solo development and
         offline work only.

There is deliberately NO automatic fallback from 's3' to 'local'. In a
shared setup, metadata lives in a shared MongoDB while bytes live in the
bucket; silently writing bytes to one machine's disk would register rows
that every collaborator can see but nobody else can read. A misconfigured
or unreachable bucket therefore raises instead of degrading quietly. This
mirrors the no-fallback stance taken by database.py.

IMPORTANT: Images are stored as-is — NO compression, NO cropping,
NO modification of any kind.
"""

import io
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ---------------------------------------------------------------------------
# Configuration — loaded from .env (see .env.example)
# ---------------------------------------------------------------------------
# "s3" (shared object store) or "local" (filesystem, solo development).
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "s3").strip().lower()

# Host[:port] of the S3-compatible endpoint, WITHOUT a scheme.
#   Cloudflare R2   <account-id>.r2.cloudflarestorage.com
#   Backblaze B2    s3.<region>.backblazeb2.com
#   Amazon S3       s3.<region>.amazonaws.com
#   Local MinIO     localhost:9000
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "").strip()
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_SECURE = os.environ.get("S3_SECURE", "true").strip().lower() == "true"
S3_BUCKET = os.environ.get("S3_BUCKET", "echoboard-dataset").strip()

# Cloudflare R2 requires the literal region "auto". Most other providers
# accept their own region name; MinIO ignores it entirely.
S3_REGION = os.environ.get("S3_REGION", "auto").strip() or None

# Local filesystem directory (mirrors the bucket structure).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATASET_DIR = os.path.join(os.path.dirname(BASE_DIR), "dataset", "echoboard-dataset")

_VALID_BACKENDS = ("s3", "local")

# True once init_storage() has verified the configured backend.
USE_S3 = False
_s3_client = None


class StorageConfigError(RuntimeError):
    """Raised when the storage backend is misconfigured or unreachable."""


def _get_s3_client():
    """Return the S3-compatible client, creating it on first call."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    try:
        from minio import Minio
        import urllib3
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StorageConfigError(
            "The 'minio' package is required for the s3 storage backend. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    missing = [
        name
        for name, value in (
            ("S3_ENDPOINT", S3_ENDPOINT),
            ("S3_ACCESS_KEY", S3_ACCESS_KEY),
            ("S3_SECRET_KEY", S3_SECRET_KEY),
        )
        if not value
    ]
    if missing:
        raise StorageConfigError(
            "Missing required storage settings: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your bucket credentials, "
            "or set STORAGE_BACKEND=local to work offline."
        )

    if "://" in S3_ENDPOINT:
        raise StorageConfigError(
            f"S3_ENDPOINT must not include a scheme (got '{S3_ENDPOINT}'). "
            "Use the bare host, e.g. <account-id>.r2.cloudflarestorage.com, "
            "and control TLS with S3_SECURE."
        )

    # Bound the connect timeout so misconfiguration surfaces as a fast, clear
    # error rather than a long hang at startup.
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=5.0, read=60.0),
        retries=urllib3.Retry(total=2, backoff_factor=0.2),
    )

    _s3_client = Minio(
        S3_ENDPOINT,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        secure=S3_SECURE,
        region=S3_REGION,
        http_client=http_client,
    )
    return _s3_client


def init_storage():
    """
    Initialize and verify the configured storage backend.

    Raises StorageConfigError if STORAGE_BACKEND=s3 and the bucket cannot be
    reached, so the API refuses to start rather than writing images to a
    location other collaborators cannot read.
    """
    global USE_S3

    if STORAGE_BACKEND not in _VALID_BACKENDS:
        raise StorageConfigError(
            f"STORAGE_BACKEND must be one of {_VALID_BACKENDS}, got '{STORAGE_BACKEND}'."
        )

    if STORAGE_BACKEND == "local":
        USE_S3 = False
        os.makedirs(LOCAL_DATASET_DIR, exist_ok=True)
        print(f"  Storage: local filesystem ({LOCAL_DATASET_DIR})")
        print("  NOTE: images are NOT shared with collaborators in this mode.")
        return

    client = _get_s3_client()
    try:
        bucket_found = client.bucket_exists(S3_BUCKET)
    except Exception as exc:
        raise StorageConfigError(
            f"Could not reach the object store at '{S3_ENDPOINT}': {exc}\n"
            "  Check S3_ENDPOINT, S3_REGION, S3_SECURE and your access keys "
            "in .env (see docs/SHARED_SETUP.md)."
        ) from exc

    if not bucket_found:
        raise StorageConfigError(
            f"Bucket '{S3_BUCKET}' was not found at '{S3_ENDPOINT}'.\n"
            "  Create it once in your provider's console, then set S3_BUCKET "
            "in .env (see docs/SHARED_SETUP.md). Buckets are not created "
            "automatically, because API tokens are normally scoped to a "
            "single existing bucket."
        )

    USE_S3 = True
    scheme = "https" if S3_SECURE else "http"
    print(f"  Storage: S3-compatible bucket '{S3_BUCKET}' ({scheme}://{S3_ENDPOINT})")


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

    Returns the object path (relative to the bucket root).

    IMPORTANT: The image is stored AS-IS — no compression, no cropping,
    no modification of any kind.
    """
    object_path = f"{subject}/{sequence_id}/{filename}"

    if USE_S3:
        client = _get_s3_client()
        client.put_object(
            S3_BUCKET,
            object_path,
            io.BytesIO(image_bytes),
            length=len(image_bytes),
            content_type=_content_type(filename),
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
    if USE_S3:
        client = _get_s3_client()
        for candidate in _extension_candidates(object_path):
            response = None
            try:
                response = client.get_object(S3_BUCKET, candidate)
                return response.read()
            except Exception:
                continue
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()
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
    if USE_S3:
        client = _get_s3_client()
        client.remove_object(S3_BUCKET, object_path)
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

    if USE_S3:
        client = _get_s3_client()
        objects = client.list_objects(S3_BUCKET, prefix=prefix, recursive=True)
        return [
            obj.object_name
            for obj in objects
            if obj.object_name.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

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
