"""
api.py
EchoBoard - FastAPI REST API

Run with:
    venv/bin/uvicorn api:app --reload --port 8000

Provides REST endpoints for the React dashboard.
"""

import io
import os
import shutil
import tempfile
import zipfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

import database as db
from video_processor import process_video

app = FastAPI(title="EchoBoard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


# --- Models ----------------------------------------------------------------
class UrlRequest(BaseModel):
    url: str
    sample_every_n_frames: int = 3
    motion_threshold: float = 0.03
    stable_frames_required: int = 4
    new_content_threshold: float = 0.05


# --- Dashboard -------------------------------------------------------------
@app.get("/api/stats")
def get_stats():
    return db.get_stats()


# --- Videos ----------------------------------------------------------------
@app.get("/api/videos")
def list_videos():
    return db.get_all_videos()


@app.get("/api/videos/{video_id}")
def get_video(video_id: str):
    v = db.get_video_by_id(video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return v


@app.delete("/api/videos/{video_id}")
def delete_video_endpoint(video_id: str):
    v = db.get_video_by_id(video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    db.delete_video(video_id)
    return {"message": f"Deleted '{v['filename']}' and its keyframes"}


# --- Keyframes -------------------------------------------------------------
@app.get("/api/videos/{video_id}/keyframes")
def get_keyframes(video_id: str):
    kfs = db.get_keyframes_for_video(video_id)
    for kf in kfs:
        kf.pop("image_bytes", None)
    return kfs


@app.get("/api/keyframes/{kf_id}/image")
def get_keyframe_image(kf_id: str):
    kf = db.get_keyframe_by_id(kf_id)
    if not kf or not kf.get("image_bytes"):
        raise HTTPException(404, "Image not found")
    return Response(content=kf["image_bytes"], media_type="image/jpeg")


# --- Upload: Video ---------------------------------------------------------
@app.post("/api/upload/video")
async def upload_video(
    file: UploadFile = File(...),
    sample_every_n_frames: int = Form(3),
    motion_threshold: float = Form(0.03),
    stable_frames_required: int = Form(4),
    new_content_threshold: float = Form(0.05),
):
    suffix = os.path.splitext(file.filename or ".mp4")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = process_video(
            tmp_path, video_id=None,
            sample_every_n_frames=sample_every_n_frames,
            motion_threshold=motion_threshold,
            stable_frames_required=stable_frames_required,
            new_content_threshold=new_content_threshold,
        )
        video_id = db.insert_video(
            filename=file.filename,
            duration_sec=result["duration_sec"],
            total_frames=result["total_frames"],
            fps=result["fps"],
        )
        for kf in result["keyframes"]:
            db.insert_keyframe(
                video_id=video_id,
                frame_number=kf["frame_number"],
                timestamp_sec=kf["timestamp_sec"],
                image_path=kf["image_path"],
                change_score=kf["change_score"],
            )
            if os.path.exists(kf["image_path"]):
                os.unlink(kf["image_path"])

        return {
            "video_id": video_id,
            "filename": file.filename,
            "duration_sec": result["duration_sec"],
            "keyframes_captured": len(result["keyframes"]),
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --- Upload: Images --------------------------------------------------------
@app.post("/api/upload/images")
async def upload_images(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files provided")

    video_id = db.insert_video(
        filename=f"Image Upload ({len(files)} images)",
        duration_sec=0, total_frames=len(files), fps=0,
    )
    for i, img in enumerate(files):
        suffix = os.path.splitext(img.filename or ".jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await img.read())
            tmp_path = tmp.name
        db.insert_keyframe(
            video_id=video_id, frame_number=i + 1,
            timestamp_sec=i, image_path=tmp_path, change_score=0,
        )
        os.unlink(tmp_path)

    return {"video_id": video_id, "images_stored": len(files)}


# --- Upload: URL -----------------------------------------------------------
@app.post("/api/upload/url")
def upload_url(req: UrlRequest):
    try:
        import yt_dlp
    except ImportError:
        raise HTTPException(500, "yt-dlp not installed")

    tmp_dir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
            "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [lambda d: print(f"[yt-dlp] {d['status']} {d.get('_percent_str','').strip()} {d.get('filename','')}", flush=True)],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title", "Downloaded Video")
            tmp_path = ydl.prepare_filename(info)

        result = process_video(
            tmp_path, video_id=None,
            sample_every_n_frames=req.sample_every_n_frames,
            motion_threshold=req.motion_threshold,
            stable_frames_required=req.stable_frames_required,
            new_content_threshold=req.new_content_threshold,
        )
        video_id = db.insert_video(
            filename=title,
            duration_sec=result["duration_sec"],
            total_frames=result["total_frames"],
            fps=result["fps"],
        )
        for kf in result["keyframes"]:
            db.insert_keyframe(
                video_id=video_id,
                frame_number=kf["frame_number"],
                timestamp_sec=kf["timestamp_sec"],
                image_path=kf["image_path"],
                change_score=kf["change_score"],
            )
            if os.path.exists(kf["image_path"]):
                os.unlink(kf["image_path"])

        return {
            "video_id": video_id, "title": title,
            "duration_sec": result["duration_sec"],
            "keyframes_captured": len(result["keyframes"]),
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --- Dataset ZIP Download -------------------------------------------------
@app.get("/api/videos/{video_id}/download")
def download_video_zip(video_id: str):
    """Download all keyframes of a single video as a ZIP."""
    v = db.get_video_by_id(video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    kfs = db.get_keyframes_for_video(video_id)
    if not kfs:
        raise HTTPException(404, "No keyframes found")

    buf = io.BytesIO()
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in v["filename"])
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for kf in kfs:
            if kf.get("image_bytes"):
                fname = f"{safe_name}_t{kf['timestamp_sec']}s_f{kf['frame_number']}.jpg"
                zf.writestr(fname, kf["image_bytes"])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@app.get("/api/download/dataset")
def download_full_dataset():
    """Download ALL keyframes from every video as one ZIP (the full dataset)."""
    videos = db.get_all_videos()
    if not videos:
        raise HTTPException(404, "No videos in database")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for v in videos:
            kfs = db.get_keyframes_for_video(v["id"])
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in v["filename"])
            for kf in kfs:
                if kf.get("image_bytes"):
                    fname = f"{safe_name}/t{kf['timestamp_sec']}s_f{kf['frame_number']}.jpg"
                    zf.writestr(fname, kf["image_bytes"])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="echoboard_dataset.zip"'},
    )


# --- Search ----------------------------------------------------------------
@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    results = db.search_keyframes(q)
    for r in results:
        r.pop("image_bytes", None)
    return results
