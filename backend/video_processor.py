"""
video_processor.py
EchoBoard Dataset Creation Module — Frame Acquisition & Intelligent Keyframe Selection

Stage 2: Frame Acquisition
  - Opens video files using OpenCV
  - Reads frames sequentially
  - Supports configurable sampling (sample_every_n_frames)
  - No recognition occurs here — only image acquisition

Stage 3: Intelligent Keyframe Selection
  - Compares consecutive frames to detect board state changes
  - Uses frame differencing + morphological filtering + motion threshold
  - Only saves frames when the board has "settled" (writing completed)
  - Ignores tiny movements, camera noise, teacher movement, lighting fluctuations
  - Saves only meaningful writing changes as keyframes

IMPORTANT: This module does NOT perform OCR, handwriting recognition,
YOLO detection, MobileNet classification, or Bi-LSTM/GRU inference.
Those belong to later training phases.
"""

import cv2
import os
import time

# Temporary frame output directory (frames are moved to MinIO/local storage after)
FRAMES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)


def _frame_diff_score(frame_a, frame_b):
    """
    Return a 0.0–1.0 score representing the fraction of pixels that changed
    between two grayscale frames. Uses thresholding to ignore minor noise.
    """
    diff = cv2.absdiff(frame_a, frame_b)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return changed_pixels / total_pixels


def _apply_morphological_filter(gray_frame):
    """
    Apply morphological filtering to reduce noise from camera jitter
    and minor lighting fluctuations. Returns a cleaned grayscale frame.
    """
    # Gaussian blur to smooth noise
    blurred = cv2.GaussianBlur(gray_frame, (5, 5), 0)
    # Morphological closing to fill small gaps from noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
    return cleaned


def process_video(
    video_path,
    video_id=None,
    sample_every_n_frames=3,     # analyze every Nth frame (speed vs. accuracy)
    motion_threshold=0.03,       # fraction of pixels changed between consecutive
                                 # samples to count as "hand/chalk still moving"
    stable_frames_required=4,    # consecutive calm samples before considering
                                 # the board "settled"
    new_content_threshold=0.05,  # fraction of pixels changed vs. last SAVED keyframe
                                 # required to bother saving again
                                 # (skips saving duplicates of an unchanged board)
    min_gap_seconds=0.5,         # don't save two keyframes closer than this
    on_keyframe=None,            # callback for real-time keyframe processing
    download_thread=None,        # active background download thread
    stop_event=None,             # threading.Event to signal early exit
):
    """
    Reads a video file, detects board keyframes using intelligent frame
    analysis, saves them as JPGs in FRAMES_DIR, and returns metadata.

    The algorithm:
      1. Sample every Nth frame to reduce computation
      2. Compare each sampled frame to the PREVIOUS sampled frame
         → measures if something is currently moving (writing in progress)
      3. Track consecutive "calm" frames (motion below threshold)
      4. When enough calm frames accumulate (board has "settled"):
         - Compare the settled frame to the LAST SAVED keyframe
         - Only save if there is genuinely new content
      5. Apply morphological filtering to reduce noise sensitivity

    Supports progressive streaming: if download_thread is provided,
    it waits for the file to grow and re-opens/seeks as needed.

    Returns: dict with fps, total_frames, duration_sec, keyframes list
    """
    # Wait for the file to exist and have data (for progressive downloads)
    start_wait = time.time()
    while True:
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            break
        if download_thread and not download_thread.is_alive() and not os.path.exists(video_path):
            raise ValueError(f"Download thread stopped before writing file: {video_path}")
        if time.time() - start_wait > 45:
            raise TimeoutError(f"Timed out waiting for video data: {video_path}")
        time.sleep(0.5)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        time.sleep(1.0)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    keyframes = []
    prev_gray = None           # previous analyzed frame (for motion detection)
    last_saved_gray = None     # last frame we actually saved (for dedup)
    last_saved_time = -min_gap_seconds
    calm_streak = 0
    frame_idx = 0

    video_basename = os.path.splitext(os.path.basename(video_path))[0]

    while True:
        ret, frame = cap.read()
        if not ret:
            # If download is still active, wait for more frames
            if download_thread and download_thread.is_alive() and not (stop_event and stop_event.is_set()):
                cap.release()
                time.sleep(1.0)
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    time.sleep(1.0)
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        break
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                continue
            else:
                break

        # Check stop_event on every frame
        if stop_event and stop_event.is_set():
            print("  Stop event received — exiting early.", flush=True)
            break

        if frame_idx % sample_every_n_frames == 0:
            if frame_idx % 500 == 0:
                if total_frames > 0:
                    print(f"  Processing frame {frame_idx}/{total_frames} ({100*frame_idx//total_frames}%)", flush=True)
                else:
                    print(f"  Processing frame {frame_idx} (timestamp {frame_idx/fps:.1f}s)", flush=True)

            # Convert to grayscale and apply morphological filtering
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = _apply_morphological_filter(gray)
            timestamp_sec = frame_idx / fps

            # Stage 3a: Compare to previous frame → detect active writing
            if prev_gray is None:
                motion_score = 0.0
            else:
                motion_score = _frame_diff_score(prev_gray, gray)

            if motion_score < motion_threshold:
                calm_streak += 1
            else:
                calm_streak = 0  # actively changing right now, reset

            # Stage 3b: Check if board has settled
            settled = calm_streak >= stable_frames_required
            enough_gap = (timestamp_sec - last_saved_time) >= min_gap_seconds

            if settled and enough_gap:
                # Stage 3c: Compare to last saved → is this genuinely new content?
                if last_saved_gray is None:
                    is_new_content = True
                    content_score = 0.0
                else:
                    content_score = _frame_diff_score(last_saved_gray, gray)
                    is_new_content = content_score >= new_content_threshold

                if is_new_content:
                    # Save the original frame as-is (no compression, no cropping)
                    image_filename = f"{video_basename}_f{frame_idx}.jpg"
                    image_path = os.path.join(FRAMES_DIR, image_filename)
                    cv2.imwrite(image_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

                    kf_data = {
                        "frame_number": frame_idx,
                        "timestamp_sec": round(timestamp_sec, 2),
                        "timestamp_ms": int(timestamp_sec * 1000),
                        "image_path": image_path,
                        "change_score": round(content_score, 3),
                    }
                    keyframes.append(kf_data)

                    # Trigger on_keyframe callback immediately
                    if on_keyframe:
                        on_keyframe(kf_data)

                    last_saved_gray = gray
                    last_saved_time = timestamp_sec
                    calm_streak = 0  # require fresh calm streak

            prev_gray = gray

        frame_idx += 1

    cap.release()

    # Update total frames and duration
    total_frames = frame_idx
    duration_sec = total_frames / fps if fps else 0

    return {
        "fps": fps,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "keyframes": keyframes,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python video_processor.py <path_to_video>")
        sys.exit(1)

    result = process_video(sys.argv[1], video_id=None)
    print(f"FPS: {result['fps']}, Duration: {result['duration_sec']:.1f}s")
    print(f"Captured {len(result['keyframes'])} keyframes:")
    for kf in result["keyframes"]:
        print(f"  Frame {kf['frame_number']} @ {kf['timestamp_sec']}s (change: {kf['change_score']})")
