"""
app.py
EchoBoard - Streamlit UI

Run with:
    streamlit run app.py

Lets a user:
  1. Upload a classroom video.
  2. Process it into board keyframes (via video_processor.py).
  3. Store keyframes + metadata in SQLite (via database.py).
  4. Browse the resulting timeline like a lesson replay, and search across
     videos once OCR text is attached to keyframes.
"""

import os
import tempfile
import streamlit as st

import database as db
from video_processor import process_video

st.set_page_config(page_title="EchoBoard", page_icon="📝", layout="wide")

db.init_db()

st.title("📝 EchoBoard")
st.caption("Every Lesson Preserved. Every Concept Searchable.")

tab_upload, tab_library, tab_search = st.tabs(["Upload & Process", "Lesson Library", "Search"])

# ---------------------------------------------------------------------------
# TAB 1: Upload & Process
# ---------------------------------------------------------------------------
with tab_upload:
    st.subheader("Upload a classroom video")
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "avi", "mov", "mkv"])

    col1, col2 = st.columns(2)
    with col1:
        sample_every_n_frames = st.slider("Analyze every Nth frame (speed)", 1, 10, 3)
        stable_frames_required = st.slider("Frames of calm before saving", 2, 10, 4)
    with col2:
        motion_threshold = st.slider("Motion sensitivity (%)", 0.01, 2.0, 0.03, step=0.01)
        new_content_threshold = st.slider("New-content sensitivity (%)", 0.01, 2.0, 0.05, step=0.01)

    if uploaded_file is not None and st.button("Process Video", type="primary"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        with st.spinner("Watching the board and extracting keyframes..."):
            result = process_video(
                tmp_path,
                video_id=None,
                sample_every_n_frames=sample_every_n_frames,
                motion_threshold=motion_threshold,
                stable_frames_required=stable_frames_required,
                new_content_threshold=new_content_threshold,
            )

            video_id = db.insert_video(
                filename=uploaded_file.name,
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

        os.unlink(tmp_path)
        st.success(f"Done! Captured {len(result['keyframes'])} keyframes from a "
                   f"{result['duration_sec']:.1f}s video.")
        st.session_state["last_video_id"] = video_id

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
            v["id"]: f"{v['filename']} — {v['duration_sec']:.1f}s ({v['uploaded_at'][:19]})"
            for v in videos
        }
        default_id = st.session_state.get("last_video_id", videos[0]["id"])
        selected_id = st.selectbox(
            "Choose a lesson",
            options=list(video_labels.keys()),
            format_func=lambda vid: video_labels[vid],
            index=list(video_labels.keys()).index(default_id) if default_id in video_labels else 0,
        )

        keyframes = db.get_keyframes_for_video(selected_id)
        st.write(f"**{len(keyframes)} keyframes captured** — replay the board's evolution below.")

        if keyframes:
            idx = st.slider("Timeline position", 0, len(keyframes) - 1, 0)
            kf = keyframes[idx]
            st.image(kf["image_path"], caption=f"t = {kf['timestamp_sec']}s (frame {kf['frame_number']})")

            with st.expander("View all keyframes as a grid"):
                cols = st.columns(4)
                for i, kf in enumerate(keyframes):
                    with cols[i % 4]:
                        st.image(kf["image_path"], caption=f"t={kf['timestamp_sec']}s")

# ---------------------------------------------------------------------------
# TAB 3: Search
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Search across all lessons")
    st.caption("Searches OCR text attached to keyframes. Plug in a handwriting-recognition "
               "model (e.g. TrOCR, or the pipeline described in your report) to populate "
               "`ocr_text` in the database for each keyframe.")
    query = st.text_input("Search term (e.g. a formula or keyword)")
    if query:
        results = db.search_keyframes(query)
        if not results:
            st.warning("No matches found. (Note: OCR text isn't populated yet in this MVP.)")
        for r in results:
            st.image(r["image_path"], caption=f"{r['video_filename']} — t={r['timestamp_sec']}s")
