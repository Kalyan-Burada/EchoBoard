"""
database.py
EchoBoard Dataset — Supabase (PostgreSQL) metadata layer

Stores dataset metadata in Supabase using the ECHD schema defined in
supabase/schema.sql. Access goes through the Supabase REST API with the
service_role key, so no direct PostgreSQL connection is required and the
backend works from any network.

The previous MongoDB implementation stored one document per image with
nested sub-documents. Those are normalised into columns and a child
`annotations` table here, and every read reassembles the original nested
shape:

    {
      "id": <uuid>,                  "image_id": "IMG0001",
      "image_name": ..., "image_path": ...,
      "sequence_id": ..., "subject": ..., "board_type": ...,
      "writer_id": ..., "video_id": ..., "frame_index": ...,
      "timestamp_ms": ..., "change_score": ..., "dataset_version": ...,
      "image_metadata":    {"width", "height", "format", "size_kb"},
      "annotations":       [{"annotation_id", "class", "bbox", "text",
                             "latex", "confidence"}],
      "quality_metadata":  {"blur_score", "lighting_score", "duplicate",
                            "occluded", "selected"},
      "processing_status": {"ocr_completed", "annotation_completed",
                            "reviewed"},
      "created_at": ..., "updated_at": ...
    }

Existing API responses and the dashboard therefore see the same structure
they saw under MongoDB.

There is no local database fallback: if Supabase is unreachable or the
schema has not been applied, startup fails with an actionable message
rather than silently accepting data that collaborators cannot read.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# ===========================================================================
# Configuration
# ===========================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")

# The service_role key bypasses Row Level Security and must stay server-side.
# SUPABASE_KEY is accepted as an alias for convenience.
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
).strip()

TABLE_IMAGES = "dataset_images"
TABLE_ANNOTATIONS = "annotations"
TABLE_VIDEOS = "videos"
TABLE_VERSIONS = "dataset_versions"

DEFAULT_VERSION = "ECHD_v1"

_client = None


class DatabaseConfigError(RuntimeError):
    """Raised when Supabase is misconfigured, unreachable, or unmigrated."""


# ===========================================================================
# Connection
# ===========================================================================
def get_client():
    """Return the shared Supabase client, creating it on first use."""
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        missing = []
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not SUPABASE_SERVICE_KEY:
            missing.append("SUPABASE_SERVICE_KEY")
        raise DatabaseConfigError(
            "Missing required Supabase settings: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your project URL and "
            "service_role key (see docs/SHARED_SETUP.md)."
        )

    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DatabaseConfigError(
            "The 'supabase' package is required. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# Backwards-compatible alias. The MongoDB layer exposed get_db(); callers that
# only need a handle keep working, though the returned object is now a
# Supabase client rather than a pymongo Database.
get_db = get_client


def init_db():
    """
    Verify that Supabase is reachable and that the ECHD schema is present.

    Raises DatabaseConfigError with actionable guidance on failure, so the
    API refuses to start rather than accepting uploads it cannot register.
    """
    client = get_client()

    try:
        client.table(TABLE_VERSIONS).select("version_id").limit(1).execute()
    except Exception as exc:
        message = str(exc)
        if "does not exist" in message or "PGRST205" in message or "42P01" in message:
            raise DatabaseConfigError(
                "Connected to Supabase, but the ECHD schema is missing.\n"
                "  Apply it once: Supabase Dashboard > SQL Editor > paste the\n"
                "  contents of supabase/schema.sql > Run.\n"
                f"  (detail: {message[:200]})"
            ) from exc
        raise DatabaseConfigError(
            f"Could not reach Supabase at '{SUPABASE_URL}': {message[:200]}\n"
            "  Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env "
            "(see docs/SHARED_SETUP.md)."
        ) from exc

    # Ensure the default dataset version exists, so inserts satisfy the
    # dataset_version foreign key on a freshly migrated project.
    try:
        existing = (
            client.table(TABLE_VERSIONS)
            .select("version_id")
            .eq("version_id", DEFAULT_VERSION)
            .execute()
        )
        if not existing.data:
            client.table(TABLE_VERSIONS).insert(
                {"version_id": DEFAULT_VERSION, "description": "Initial version"}
            ).execute()
    except Exception:
        # Non-fatal: the schema migration already seeds this row.
        pass

    print(f"  Database: Supabase — {SUPABASE_URL} [OK] Connected")


def _now():
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# Sequential ECHD identifiers
# ===========================================================================
def _next_image_id():
    """Allocate the next IMGxxxx id using a PostgreSQL sequence (race-free)."""
    result = get_client().rpc("next_image_id").execute()
    return result.data


def _next_annotation_id():
    """Allocate the next ANNxxxx id using a PostgreSQL sequence (race-free)."""
    result = get_client().rpc("next_annotation_id").execute()
    return result.data


# ===========================================================================
# Row shaping — flat SQL rows to the nested ECHD structure
# ===========================================================================
_ANNOTATION_FIELDS = ("annotation_id", "class", "bbox", "text", "latex", "confidence")


def _shape_annotation(row):
    return {field: row.get(field) for field in _ANNOTATION_FIELDS}


def _shape_image(row):
    """Convert a dataset_images row (optionally with embedded annotations)."""
    if row is None:
        return None

    annotations = row.get("annotations") or []
    if isinstance(annotations, dict):  # single embedded row
        annotations = [annotations]
    annotations = [_shape_annotation(a) for a in annotations]
    annotations.sort(key=lambda a: a.get("annotation_id") or "")

    return {
        "id": row.get("id"),
        "image_id": row.get("image_id"),
        "image_name": row.get("image_name"),
        "image_path": row.get("image_path"),
        # Provenance — required for downstream model training.
        "sequence_id": row.get("sequence_id"),
        "subject": row.get("subject"),
        "board_type": row.get("board_type"),
        "writer_id": row.get("writer_id"),
        "uploaded_by": row.get("uploaded_by"),
        "video_id": row.get("video_id"),
        "frame_index": row.get("frame_index"),
        "timestamp_ms": row.get("timestamp_ms"),
        "change_score": row.get("change_score"),
        "dataset_version": row.get("dataset_version"),
        "image_metadata": {
            "width": row.get("width"),
            "height": row.get("height"),
            "format": row.get("format"),
            "size_kb": row.get("size_kb"),
        },
        "annotations": annotations,
        "quality_metadata": {
            "blur_score": row.get("blur_score"),
            "lighting_score": row.get("lighting_score"),
            "duplicate": row.get("duplicate"),
            "occluded": row.get("occluded"),
            "selected": row.get("selected"),
        },
        "processing_status": {
            "ocr_completed": row.get("ocr_completed"),
            "annotation_completed": row.get("annotation_completed"),
            "reviewed": row.get("reviewed"),
        },
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# PostgREST embedding: fetch each image with its annotations in one request.
_IMAGE_SELECT = f"*, {TABLE_ANNOTATIONS}(*)"


# ===========================================================================
# Core CRUD — Dataset Images
# ===========================================================================
def insert_dataset_image(
    image_path: str,
    image_name: str = None,
    # Provenance (video and direct-upload pipelines)
    sequence_id: str = None,
    subject: str = None,
    board_type: str = None,
    writer_id: str = None,
    uploaded_by: str = None,
    video_id: str = None,
    frame_index: int = 0,
    timestamp_ms: int = 0,
    change_score: float = 0.0,
    dataset_version: str = None,
    # image_metadata
    width: int = 0,
    height: int = 0,
    format_type: str = None,
    size_kb: int = 0,
    # Optional first annotation
    annotation_text: str = "",
    annotation_class: str = "Text",
    **_ignored,
):
    """
    Insert one image record using the ECHD schema.

    Accepts both upload conventions used by the API: the keyframe pipeline
    supplies provenance (sequence_id, subject, frame_index, video_id, ...),
    while direct image upload supplies intrinsic metadata (image_name,
    width, height, format_type, size_kb). Either subset may be omitted.

    Returns the inserted record in the nested ECHD shape.
    """
    client = get_client()
    image_id = _next_image_id()
    now = _now()

    if not image_name:
        image_name = os.path.basename(image_path or "") or image_id
    if not format_type:
        format_type = (os.path.splitext(image_name)[1] or ".jpg").lstrip(".").lower()

    annotation_text = (annotation_text or "").strip()

    row = {
        "image_id": image_id,
        "image_name": image_name,
        "image_path": image_path,
        "sequence_id": sequence_id,
        "subject": subject,
        "board_type": board_type,
        "writer_id": writer_id,
        "uploaded_by": uploaded_by or writer_id,
        "video_id": video_id or None,
        "frame_index": int(frame_index or 0),
        "timestamp_ms": int(timestamp_ms or 0),
        "change_score": float(change_score or 0.0),
        "dataset_version": dataset_version or get_current_version(),
        "width": int(width or 0),
        "height": int(height or 0),
        "format": format_type,
        "size_kb": int(size_kb or 0),
        "annotation_completed": bool(annotation_text),
        "created_at": now,
        "updated_at": now,
    }

    inserted = client.table(TABLE_IMAGES).insert(row).execute()
    record = inserted.data[0] if inserted.data else row
    record["annotations"] = []

    if annotation_text:
        annotation = {
            "annotation_id": _next_annotation_id(),
            "image_id": image_id,
            "class": annotation_class or "Text",
            "bbox": [],
            "text": annotation_text,
            "latex": "",
            "confidence": 0.0,
        }
        client.table(TABLE_ANNOTATIONS).insert(annotation).execute()
        record["annotations"] = [annotation]

    return _shape_image(record)


def get_dataset_images(limit=500, sequence_id=None, subject=None, video_id=None,
                       reviewed=None, **_ignored):
    """
    Return dataset images, newest first, with their annotations.

    Filters are optional and applied server-side. The MongoDB implementation
    accepted these keyword arguments but ignored them, so callers that pass
    sequence_id now receive a correctly scoped result.
    """
    query = (
        get_client()
        .table(TABLE_IMAGES)
        .select(_IMAGE_SELECT)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if sequence_id is not None:
        query = query.eq("sequence_id", sequence_id)
    if subject is not None:
        query = query.eq("subject", subject)
    if video_id is not None:
        query = query.eq("video_id", video_id)
    if reviewed is not None:
        query = query.eq("reviewed", reviewed)

    return [_shape_image(row) for row in (query.execute().data or [])]


def get_dataset_image_by_id(image_id):
    """Look up by ECHD image_id (e.g. IMG0001)."""
    result = (
        get_client()
        .table(TABLE_IMAGES)
        .select(_IMAGE_SELECT)
        .eq("image_id", image_id)
        .limit(1)
        .execute()
    )
    return _shape_image(result.data[0]) if result.data else None


def get_dataset_image_by_internal_id(internal_id):
    """Look up by the internal UUID primary key."""
    try:
        result = (
            get_client()
            .table(TABLE_IMAGES)
            .select(_IMAGE_SELECT)
            .eq("id", str(internal_id))
            .limit(1)
            .execute()
        )
        return _shape_image(result.data[0]) if result.data else None
    except Exception:
        # Not a valid UUID, or a transient lookup failure.
        return None


def delete_dataset_image(image_id):
    """Delete an image record. Its annotations cascade in the database."""
    get_client().table(TABLE_IMAGES).delete().eq("image_id", image_id).execute()


def update_dataset_image_annotation(image_id: str, annotation_text: str,
                                    annotation_class: str = "Text",
                                    reviewed: bool = True):
    """
    Replace the annotations for an image and update its processing status.

    Accepts either an ECHD image_id or the internal UUID. Returns False if
    no matching image exists.
    """
    client = get_client()

    record = get_dataset_image_by_id(image_id) or get_dataset_image_by_internal_id(image_id)
    if not record:
        return False

    echd_id = record["image_id"]
    annotation_text = (annotation_text or "").strip()

    # Mirrors the previous behaviour of replacing the annotations array.
    client.table(TABLE_ANNOTATIONS).delete().eq("image_id", echd_id).execute()
    client.table(TABLE_ANNOTATIONS).insert({
        "annotation_id": _next_annotation_id(),
        "image_id": echd_id,
        "class": annotation_class or "Text",
        "bbox": [],
        "text": annotation_text,
        "latex": "",
        "confidence": 1.0 if reviewed else 0.8,
    }).execute()

    client.table(TABLE_IMAGES).update({
        "ocr_completed": True,
        "annotation_completed": bool(annotation_text),
        "reviewed": reviewed,
        "updated_at": _now(),
    }).eq("image_id", echd_id).execute()

    return True


def insert_annotations(image_id: str, annotations: list, mark_reviewed: bool = False):
    """
    Attach several annotations to one image, replacing any existing ones.

    update_dataset_image_annotation() stores exactly one annotation, which
    suits a single OCR pass. A board usually holds several distinct regions
    (a header, body lines, an equation), and each needs its own label with
    its own class and bbox, so this takes a list.

    Each entry may set: class, text, bbox, latex, confidence.
    Returns the number of annotation rows written.
    """
    client = get_client()

    record = get_dataset_image_by_id(image_id) or get_dataset_image_by_internal_id(image_id)
    if not record:
        return 0
    echd_id = record["image_id"]

    client.table(TABLE_ANNOTATIONS).delete().eq("image_id", echd_id).execute()

    rows = []
    for entry in annotations:
        text = (entry.get("text") or "").strip()
        rows.append({
            "annotation_id": _next_annotation_id(),
            "image_id": echd_id,
            "class": entry.get("class") or "Text",
            "bbox": entry.get("bbox") or [],
            "text": text,
            "latex": entry.get("latex") or "",
            "confidence": float(entry.get("confidence") or 0.0),
        })

    if rows:
        client.table(TABLE_ANNOTATIONS).insert(rows).execute()

    client.table(TABLE_IMAGES).update({
        "ocr_completed": True,
        "annotation_completed": any(r["text"] for r in rows),
        "reviewed": bool(mark_reviewed),
        "updated_at": _now(),
    }).eq("image_id", echd_id).execute()

    return len(rows)


def update_image_quality(image_id: str, blur_score=None, lighting_score=None,
                         duplicate=None, occluded=None, selected=None):
    """Update quality_metadata fields for one image. Unset args are left alone."""
    patch = {}
    for column, value in (
        ("blur_score", blur_score),
        ("lighting_score", lighting_score),
        ("duplicate", duplicate),
        ("occluded", occluded),
        ("selected", selected),
    ):
        if value is not None:
            patch[column] = value
    if not patch:
        return False
    patch["updated_at"] = _now()
    get_client().table(TABLE_IMAGES).update(patch).eq("image_id", image_id).execute()
    return True


# ===========================================================================
# Stats
# ===========================================================================
def _count(table, **filters):
    query = get_client().table(table).select("*", count="exact").limit(1)
    for column, value in filters.items():
        query = query.eq(column, value)
    return query.execute().count or 0


def get_stats():
    total = _count(TABLE_IMAGES)
    annotated = _count(TABLE_IMAGES, annotation_completed=True)
    return {
        "total_videos": _count(TABLE_VIDEOS),
        "total_images": total,
        "pending_annotations": total - annotated,
        "completed_annotations": annotated,
        "current_version": get_current_version(),
    }


# ===========================================================================
# Videos
#
# These were stubs under MongoDB (insert_video returned the literal string
# "stub_video_id" and get_videos returned []), which left the dashboard's
# video list permanently empty. They are backed by a real table now.
# ===========================================================================
def insert_video(filename="", duration_sec=0, total_frames=0, fps=0, processing=True):
    """Create a video row and return its UUID as a string."""
    result = get_client().table(TABLE_VIDEOS).insert({
        "filename": filename or "",
        "duration_sec": float(duration_sec or 0),
        "total_frames": int(total_frames or 0),
        "fps": float(fps or 0),
        "processing": bool(processing),
    }).execute()
    return str(result.data[0]["id"])


def update_video(video_id="", duration_sec=0, total_frames=0, fps=0, processing=False):
    """Update a video's measured properties and processing flag."""
    if not video_id:
        return
    get_client().table(TABLE_VIDEOS).update({
        "duration_sec": float(duration_sec or 0),
        "total_frames": int(total_frames or 0),
        "fps": float(fps or 0),
        "processing": bool(processing),
        "updated_at": _now(),
    }).eq("id", str(video_id)).execute()


def set_video_processing(video_id, processing: bool):
    """
    Flip only a video's processing flag.

    update_video() overwrites the measured duration/frames/fps, so callers
    that merely want to mark processing finished (the stop endpoint, error
    paths) must use this instead or they would zero out real measurements.
    """
    if not video_id:
        return
    get_client().table(TABLE_VIDEOS).update({
        "processing": bool(processing),
        "updated_at": _now(),
    }).eq("id", str(video_id)).execute()


def delete_images_for_video(video_id):
    """Delete every dataset image row belonging to one video."""
    if not video_id:
        return
    get_client().table(TABLE_IMAGES).delete().eq("video_id", str(video_id)).execute()


def get_videos(limit=50):
    """Return videos, newest first, each with its captured keyframe count."""
    rows = (
        get_client()
        .table(TABLE_VIDEOS)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    for row in rows:
        row["id"] = str(row["id"])
        row["keyframe_count"] = _count(TABLE_IMAGES, video_id=row["id"])
    return rows


def get_video(video_id):
    if not video_id:
        return None
    try:
        result = (
            get_client()
            .table(TABLE_VIDEOS)
            .select("*")
            .eq("id", str(video_id))
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if not result.data:
        return None
    row = result.data[0]
    row["id"] = str(row["id"])
    row["keyframe_count"] = _count(TABLE_IMAGES, video_id=row["id"])
    return row


def get_images_for_video(video_id):
    """Return every dataset image extracted from one video, in frame order."""
    if not video_id:
        return []
    try:
        rows = (
            get_client()
            .table(TABLE_IMAGES)
            .select(_IMAGE_SELECT)
            .eq("video_id", str(video_id))
            .order("frame_index")
            .execute()
            .data
            or []
        )
    except Exception:
        return []
    return [_shape_image(row) for row in rows]


def delete_video(video_id):
    """
    Delete a video row.

    Its images' video_id is set to null by the foreign key, so callers that
    also want the image records removed should delete them first, as the
    delete-video endpoint does.
    """
    if not video_id:
        return
    get_client().table(TABLE_VIDEOS).delete().eq("id", str(video_id)).execute()


# ===========================================================================
# Dataset versions
# ===========================================================================
def get_current_version():
    """Return the newest dataset version id, seeding ECHD_v1 if empty."""
    try:
        result = (
            get_client()
            .table(TABLE_VERSIONS)
            .select("version_id")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["version_id"]
    except Exception:
        pass
    return DEFAULT_VERSION


def get_all_versions():
    """Return every dataset version, newest first."""
    try:
        return (
            get_client()
            .table(TABLE_VERSIONS)
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        return [{"version_id": DEFAULT_VERSION, "description": "Initial version"}]


def create_new_version(description=""):
    """
    Create the next sequential dataset version (ECHD_v1 -> ECHD_v2 -> ...).

    Returns the new version id. This was previously a stub that always
    returned "ECHD_v2" without persisting anything.
    """
    client = get_client()
    existing = client.table(TABLE_VERSIONS).select("version_id").execute().data or []

    highest = 0
    for row in existing:
        version_id = row.get("version_id") or ""
        if version_id.startswith("ECHD_v"):
            suffix = version_id[len("ECHD_v"):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))

    new_version = f"ECHD_v{highest + 1}"
    client.table(TABLE_VERSIONS).insert({
        "version_id": new_version,
        "description": description or "",
    }).execute()
    return new_version


# ===========================================================================
# Data purge (admin utility)
# ===========================================================================
def purge_all():
    """Delete ALL dataset rows. Use with extreme caution."""
    client = get_client()
    # Annotations cascade from dataset_images, but clear them explicitly so
    # the operation is obvious in the logs.
    # PostgREST requires a filter on delete, so each uses a predicate that
    # matches every row. Note PostgreSQL rejects NUL characters in string
    # literals, so a NUL sentinel cannot be used here.
    never_a_uuid = "00000000-0000-0000-0000-000000000000"
    client.table(TABLE_ANNOTATIONS).delete().neq("annotation_id", "").execute()
    client.table(TABLE_IMAGES).delete().neq("image_id", "").execute()
    client.table(TABLE_VIDEOS).delete().neq("id", never_a_uuid).execute()
    print("  All Supabase dataset rows purged.")
