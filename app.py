"""
app.py
EchoBoard - Streamlit UI

Run with:
    venv/bin/streamlit run app.py

Lets a user:
  1. Upload a classroom video, board images, or paste a video URL.
  2. Process videos into board keyframes (via video_processor.py).
  3. Store keyframes + metadata in MongoDB Atlas (via database.py).
  4. Browse the resulting timeline like a lesson replay, and search across
     videos once OCR text is attached to keyframes.
"""

import os
import shutil
import tempfile
import streamlit as st

import database as db
from video_processor import process_video

st.set_page_config(page_title="EchoBoard", page_icon="📝", layout="wide")

db.init_db()

st.title("📝 EchoBoard")
st.caption("Every Lesson Preserved. Every Concept Searchable.")

tab_upload, tab_library, tab_search = st.tabs(
    ["Upload & Process", "Lesson Library", "Search"]
)


# ---------------------------------------------------------------------------
# Helper: process a video file, store results in MongoDB, clean up local files
# ---------------------------------------------------------------------------
def _process_and_store(video_path, display_name, sample_every_n_frames,
                       motion_threshold, stable_frames_required,
                       new_content_threshold):
    """Run the keyframe extractor, insert into MongoDB, clean up local JPGs."""
    result = process_video(
        video_path,
        video_id=None,
        sample_every_n_frames=sample_every_n_frames,
        motion_threshold=motion_threshold,
        stable_frames_required=stable_frames_required,
        new_content_threshold=new_content_threshold,
    )

    video_id = db.insert_video(
        filename=display_name,
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
        # Clean up the local JPG — the image is now safe in MongoDB
        if os.path.exists(kf["image_path"]):
            os.unlink(kf["image_path"])

    return video_id, result


# ---------------------------------------------------------------------------
# TAB 1: Upload & Process
# ---------------------------------------------------------------------------
with tab_upload:
    st.subheader("Add classroom content")

    input_method = st.radio(
        "Choose input method",
        ["📹 Upload Video", "🖼️ Upload Images", "🔗 Video URL"],
        horizontal=True,
    )

    # -----------------------------------------------------------------------
    # Option 1: Upload Video file
    # -----------------------------------------------------------------------
    if input_method == "📹 Upload Video":
        st.caption("Upload a recorded classroom video — EchoBoard will "
                   "automatically extract the key board states.")
        uploaded_file = st.file_uploader(
            "Choose a video file", type=["mp4", "avi", "mov", "mkv", "webm"]
        )

        col1, col2 = st.columns(2)
        with col1:
            sample_n = st.slider("Analyze every Nth frame (speed)",
                                 1, 10, 3, key="v_sample")
            stable_n = st.slider("Frames of calm before saving",
                                 2, 10, 4, key="v_stable")
        with col2:
            motion_t = st.slider("Motion sensitivity (%)",
                                 0.01, 2.0, 0.03, step=0.01, key="v_motion")
            content_t = st.slider("New-content sensitivity (%)",
                                  0.01, 2.0, 0.05, step=0.01, key="v_content")

        if uploaded_file is not None and st.button("Process Video",
                                                   type="primary"):
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=os.path.splitext(uploaded_file.name)[1],
            ) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            with st.spinner("Watching the board and extracting keyframes…"):
                video_id, result = _process_and_store(
                    tmp_path, uploaded_file.name,
                    sample_n, motion_t, stable_n, content_t,
                )

            os.unlink(tmp_path)
            st.success(
                f"Done! Captured **{len(result['keyframes'])} keyframes** "
                f"from a {result['duration_sec']:.1f}s video."
            )
            st.session_state["last_video_id"] = video_id

    # -----------------------------------------------------------------------
    # Option 2: Upload Images directly
    # -----------------------------------------------------------------------
    elif input_method == "🖼️ Upload Images":
        st.caption(
            "Upload board / lecture photos directly — they'll be stored as "
            "keyframes without video processing."
        )
        uploaded_images = st.file_uploader(
            "Choose image files",
            type=["jpg", "jpeg", "png", "bmp", "webp"],
            accept_multiple_files=True,
        )

        if uploaded_images and st.button("Store Images", type="primary"):
            with st.spinner(f"Storing {len(uploaded_images)} image(s)…"):
                # Create a single "video" entry to group these images
                video_id = db.insert_video(
                    filename=f"Image Upload ({len(uploaded_images)} images)",
                    duration_sec=0,
                    total_frames=len(uploaded_images),
                    fps=0,
                )

                for i, img_file in enumerate(uploaded_images):
                    # Save to a temp file so insert_keyframe can read it
                    suffix = os.path.splitext(img_file.name)[1] or ".jpg"
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=suffix
                    ) as tmp:
                        tmp.write(img_file.read())
                        tmp_path = tmp.name

                    db.insert_keyframe(
                        video_id=video_id,
                        frame_number=i + 1,
                        timestamp_sec=i,
                        image_path=tmp_path,
                        change_score=0,
                    )
                    os.unlink(tmp_path)  # clean up temp file

            st.success(
                f"Done! Stored **{len(uploaded_images)} image(s)** as "
                f"keyframes in the cloud database."
            )
            st.session_state["last_video_id"] = video_id

    # -----------------------------------------------------------------------
    # Option 3: Video URL (YouTube, direct link, etc.)
    # -----------------------------------------------------------------------
    elif input_method == "🔗 Video URL":
        st.caption(
            "Paste a YouTube URL or direct video link — it will be "
            "downloaded and processed automatically."
        )
        video_url = st.text_input(
            "Video URL",
            placeholder="https://www.youtube.com/watch?v=… or direct .mp4 link",
        )

        col1, col2 = st.columns(2)
        with col1:
            sample_n = st.slider("Analyze every Nth frame (speed)",
                                 1, 10, 3, key="u_sample")
            stable_n = st.slider("Frames of calm before saving",
                                 2, 10, 4, key="u_stable")
        with col2:
            motion_t = st.slider("Motion sensitivity (%)",
                                 0.01, 2.0, 0.03, step=0.01, key="u_motion")
            content_t = st.slider("New-content sensitivity (%)",
                                  0.01, 2.0, 0.05, step=0.01, key="u_content")

        if video_url and st.button("Download & Process", type="primary"):
            try:
                import yt_dlp
            except ImportError:
                st.error(
                    "**yt-dlp** is not installed. Run:\n\n"
                    "```\nvenv/bin/pip install yt-dlp\n```"
                )
                st.stop()

            tmp_dir = tempfile.mkdtemp()
            try:
                # --- Download ---
                with st.spinner("⬇️ Downloading video…"):
                    ydl_opts = {
                        "format": (
                            "best[height<=720][ext=mp4]/"
                            "best[height<=720]/best"
                        ),
                        "outtmpl": os.path.join(
                            tmp_dir, "%(title).80s.%(ext)s"
                        ),
                        "quiet": True,
                        "no_warnings": True,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=True)
                        video_title = info.get("title", "Downloaded Video")
                        tmp_path = ydl.prepare_filename(info)

                st.info(f"Downloaded: **{video_title}**")

                # --- Process keyframes ---
                with st.spinner("🔍 Extracting keyframes…"):
                    video_id, result = _process_and_store(
                        tmp_path, video_title,
                        sample_n, motion_t, stable_n, content_t,
                    )

                st.success(
                    f"Done! Captured **{len(result['keyframes'])} keyframes** "
                    f"from *{video_title}* ({result['duration_sec']:.1f}s)."
                )
                st.session_state["last_video_id"] = video_id

            except yt_dlp.utils.DownloadError as e:
                st.error(f"Download failed: {e}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                # Clean up entire temp directory
                shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TAB 2: Lesson Library (browse / replay)
# ---------------------------------------------------------------------------
with tab_library:
    st.subheader("Your processed lessons")
    videos = db.get_all_videos()

    if not videos:
        st.info("No videos processed yet. Go to the Upload tab first.")
    else:
        video_labels = {
            v["id"]: (
                f"{v['filename']} — {v['duration_sec']:.1f}s "
                f"({v['uploaded_at'][:19]})"
            )
            for v in videos
        }
        default_id = st.session_state.get("last_video_id", videos[0]["id"])
        selected_id = st.selectbox(
            "Choose a lesson",
            options=list(video_labels.keys()),
            format_func=lambda vid: video_labels[vid],
            index=(
                list(video_labels.keys()).index(default_id)
                if default_id in video_labels else 0
            ),
        )

        keyframes = db.get_keyframes_for_video(selected_id)
        st.write(
            f"**{len(keyframes)} keyframes captured** — "
            f"replay the board's evolution below."
        )

        if keyframes:
            idx = st.slider("Timeline position", 0, len(keyframes) - 1, 0)
            kf = keyframes[idx]
            st.image(
                kf.get("image_bytes", b""),
                caption=(
                    f"t = {kf['timestamp_sec']}s "
                    f"(frame {kf['frame_number']})"
                ),
            )

            with st.expander("View all keyframes as a grid"):
                cols = st.columns(4)
                for i, kf in enumerate(keyframes):
                    with cols[i % 4]:
                        st.image(
                            kf.get("image_bytes", b""),
                            caption=f"t={kf['timestamp_sec']}s",
                        )


# ---------------------------------------------------------------------------
# TAB 3: Search
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Search across all lessons")
    st.caption(
        "Searches OCR text attached to keyframes. Plug in a "
        "handwriting-recognition model (e.g. TrOCR, or the pipeline "
        "described in your report) to populate `ocr_text` in the database "
        "for each keyframe."
    )
    query = st.text_input("Search term (e.g. a formula or keyword)")
    if query:
        results = db.search_keyframes(query)
        if not results:
            st.warning(
                "No matches found. "
                "(Note: OCR text isn't populated yet in this MVP.)"
            )
        for r in results:
            st.image(
                r.get("image_bytes", b""),
                caption=(
                    f"{r['video_filename']} — t={r['timestamp_sec']}s"
                ),
            )
