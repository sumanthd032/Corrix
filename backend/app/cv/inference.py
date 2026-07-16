"""Live CV inference pipeline, per CORRIX_BUILD_PLAN.md Step 6: real
bounding-box detections from a fine-tuned YOLO11n model (trained on the
real, open Ultralytics Construction-PPE dataset — see
scripts/train_ppe_model.py), run on a webcam feed or the sample clip,
timestamped as produced. Genuine forward-pass inference, not a
pre-baked detection log played back on a timer.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import cv2
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAINED_MODEL_PATH = REPO_ROOT / "backend" / "runs" / "ppe_detector" / "weights" / "best.pt"
FALLBACK_MODEL_PATH = "yolo11n.pt"  # zero-shot COCO weights, person-only

CONFIDENCE_THRESHOLD = 0.4


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@lru_cache
def get_model() -> YOLO:
    if TRAINED_MODEL_PATH.exists():
        return YOLO(str(TRAINED_MODEL_PATH))
    return YOLO(FALLBACK_MODEL_PATH)


def run_inference_on_frame(frame, model: YOLO | None = None) -> list[Detection]:
    model = model or get_model()
    results = model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            detections.append(
                Detection(
                    class_name=model.names[cls_id],
                    confidence=float(box.conf[0]),
                    bbox_xyxy=tuple(float(x) for x in box.xyxy[0]),
                )
            )
    return detections


def run_inference_on_video(
    video_path: Path,
    sample_interval_seconds: float = 1.0,
    start_time: datetime | None = None,
    max_frames: int | None = None,
):
    """Yields (video_offset_seconds, wall_clock_timestamp, detections) for
    frames sampled every `sample_interval_seconds` — real forward-pass
    inference per sampled frame, not interpolated or faked between
    samples."""
    model = get_model()
    start_time = start_time or datetime.now()
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(fps * sample_interval_seconds))

    frame_index = 0
    sampled_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_index % frame_interval == 0:
                video_offset = frame_index / fps
                detections = run_inference_on_frame(frame, model)
                yield (
                    video_offset,
                    start_time + timedelta(seconds=video_offset),
                    detections,
                )
                sampled_count += 1
                if max_frames is not None and sampled_count >= max_frames:
                    break
            frame_index += 1
    finally:
        cap.release()
