"""Step 6's Definition of Done: live inference runs at acceptable FPS on
actual demo hardware — measured here, not assumed. This machine is
CPU-only (no GPU); the bound below is deliberately generous rather than
tuned to look good, since demo hardware is what it is."""

import time

import cv2

from app.cv.inference import get_model, run_inference_on_frame

VIDEO_PATH = "../assets/videos/test_site.mp4"
MIN_ACCEPTABLE_FPS = 3.0  # sampled-frame MCP queries, not continuous 30fps tracking


def test_inference_meets_minimum_fps_on_this_hardware():
    cap = cv2.VideoCapture(VIDEO_PATH)
    frames = []
    for _ in range(20):
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
    cap.release()
    assert len(frames) == 20

    model = get_model()
    run_inference_on_frame(frames[0], model)  # warmup, excluded from timing

    start = time.time()
    for frame in frames:
        run_inference_on_frame(frame, model)
    elapsed = time.time() - start
    fps = len(frames) / elapsed

    assert fps >= MIN_ACCEPTABLE_FPS, f"only {fps:.2f} FPS on this demo hardware"
