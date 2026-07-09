"""
video_processor.py
EchoBoard - Frame capture & change-detection engine

Core idea (the "novelty" from your report): instead of saving every frame,
or one frame every N seconds, we watch for the board's WRITING STATE:

  1. Compare each new frame to the last SAVED keyframe.
  2. If the difference is large -> someone is actively writing/erasing
     ("dirty" state). We do NOT save yet, because the board is mid-change
     (hand/chalk still moving -> blurry, incomplete).
  3. Once the frame-to-frame difference stays LOW for a few consecutive
     frames (the board has "settled"), we save that stable frame as a new
     keyframe. This captures completed writing states and skips both
     duplicate frames and half-written blurry ones.

This is intentionally simple (pure OpenCV frame differencing) so it runs
fast on CPU with no GPU needed. It can later be swapped for a learned
"active writing region" detector (e.g. YOLOv8-nano, as in your report)
without changing the rest of the pipeline.
"""

import cv2
import os
import time

FRAMES_DIR = os.path.join(os.path.dirname(__file__), "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)


def _frame_diff_score(frame_a, frame_b):
    """Return a 0-100 'percent changed' score between two grayscale frames."""
    diff = cv2.absdiff(frame_a, frame_b)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = thresh.shape[0] * thresh.shape[1]
    return (changed_pixels / total_pixels)


def process_video(
    video_path,
    video_id=None,
    sample_every_n_frames=3,     # analyze every Nth frame (speed vs. accuracy)
    motion_threshold=0.03,       # % pixels changed between consecutive samples
                                 # to count as "hand/chalk still moving"
    stable_frames_required=4,    # consecutive calm samples before considering
                                 # the board "settled"
    new_content_threshold=0.05,  # % pixels changed vs. last SAVED keyframe
                                 # required to bother saving again
                                 # (skips saving duplicates of an unchanged board)
    min_gap_seconds=0.5,         # don't save two keyframes closer than this
    on_keyframe=None,            # callback function to process detected keyframes in real-time
    download_thread=None,        # active background download thread
    stop_event=None,             # threading.Event to signal early exit
):
    """
    Reads a video file, detects board keyframes, saves them as JPGs in
    FRAMES_DIR, and returns a list of dicts ready to insert into the DB.

    Supports progressive streaming/processing: if download_thread is provided,
    it will read frames from the growing file (or .part file) and reopen/seek
    until the downloader completes.
    """
    import time

    # Wait for the file to exist and have some data
    start_wait = time.time()
    while True:
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            break

        if download_thread and not download_thread.is_alive() and not os.path.exists(video_path):
            raise ValueError(f"Download thread stopped before writing file: {video_path}")

        if time.time() - start_wait > 45:  # 45 seconds timeout
            raise TimeoutError(f"Timed out waiting for video download to write data: {video_path}")
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
    prev_gray = None          # previous analyzed frame (for motion detection)
    last_saved_gray = None    # last frame we actually saved (for dedup)
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

        # Check stop_event on every sampled frame
        if stop_event and stop_event.is_set():
            print("  Stop event received — exiting early.", flush=True)
            break

        if frame_idx % sample_every_n_frames == 0:
            if frame_idx % 500 == 0:
                if total_frames > 0:
                    print(f"  Processing frame {frame_idx}/{total_frames} ({100*frame_idx//total_frames}%)", flush=True)
                else:
                    print(f"  Processing frame {frame_idx} (timestamp {frame_idx/fps:.1f}s)", flush=True)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            timestamp_sec = frame_idx / fps

            if prev_gray is None:
                motion_score = 0.0
            else:
                motion_score = _frame_diff_score(prev_gray, gray)

            if motion_score < motion_threshold:
                calm_streak += 1
            else:
                calm_streak = 0  # actively changing right now, reset

            settled = calm_streak >= stable_frames_required
            enough_gap = (timestamp_sec - last_saved_time) >= min_gap_seconds

            if settled and enough_gap:
                if last_saved_gray is None:
                    is_new_content = True
                    content_score = 0.0
                else:
                    content_score = _frame_diff_score(last_saved_gray, gray)
                    is_new_content = content_score >= new_content_threshold

                if is_new_content:
                    image_filename = f"{video_basename}_f{frame_idx}.jpg"
                    image_path = os.path.join(FRAMES_DIR, image_filename)
                    cv2.imwrite(image_path, frame)

                    kf_data = {
                        "frame_number": frame_idx,
                        "timestamp_sec": round(timestamp_sec, 2),
                        "image_path": image_path,
                        "change_score": round(content_score, 3),
                    }
                    keyframes.append(kf_data)

                    # Trigger on_keyframe callback immediately
                    if on_keyframe:
                        on_keyframe(kf_data)

                    last_saved_gray = gray
                    last_saved_time = timestamp_sec
                    # require a fresh calm streak before the next save
                    calm_streak = 0

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

    result = process_video(sys.argv[1], video_id=0)
    print(f"FPS: {result['fps']}, Duration: {result['duration_sec']:.1f}s")
    print(f"Captured {len(result['keyframes'])} keyframes:")
    for kf in result["keyframes"]:
        print(kf)
