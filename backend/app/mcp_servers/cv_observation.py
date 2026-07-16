"""CV/Observation MCP Server.

Scoped, alongside Worker Location, to the Site Safety Observer agent
(CORRIX_PROJECT.md §6.1). Real tool as of Step 6: runs actual YOLO11n
forward-pass inference on a sample frame from the real demo clip
(assets/videos/test_site.mp4), then correlates any person-class
detection against the Step 2 worker-location stream for the given
scenario at the given minute — the real/simulated split is encoded in
the returned event's `source`/`correlation_source` fields, not just a
label.
"""

from datetime import timedelta
from pathlib import Path

import cv2
from mcp.server.fastmcp import FastMCP

from app.cv.correlation import correlate_detection
from app.cv.inference import get_model, run_inference_on_frame
from app.simulation.scenario_engine import (
    DEFAULT_START_TIME,
    find_scenario_config,
    run_scenario_from_file,
)

server = FastMCP("corrix-cv-observation")

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_CLIP_PATH = REPO_ROOT / "assets" / "videos" / "test_site.mp4"
SCENARIOS_ROOT = REPO_ROOT / "data" / "scenarios"


def _frame_at(video_path: Path, offset_seconds: float):
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1
    duration = frame_count / fps
    target_offset = offset_seconds % duration if duration > 0 else 0.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(target_offset * fps))
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


@server.tool()
def get_recent_detections(
    zone_id: str, scenario_id: str, seed: int, at_minute: float
) -> dict:
    """Return real CV detections for a zone at a given minute into a
    seeded scenario run, correlated against that scenario's real
    worker-location stream."""
    frame = _frame_at(SAMPLE_CLIP_PATH, at_minute * 60.0)
    if frame is None:
        return {"zone_id": zone_id, "detections": [], "error": "could not read sample clip frame"}

    detections = run_inference_on_frame(frame, get_model())

    path = find_scenario_config(SCENARIOS_ROOT, scenario_id, seed)
    out = run_scenario_from_file(path)
    detection_time = DEFAULT_START_TIME + timedelta(minutes=at_minute)

    events = [
        correlate_detection(
            d, zone_id, detection_time, out.worker_pings, event_id=f"CV-{zone_id}-{i:04d}"
        )
        for i, d in enumerate(detections)
    ]
    return {
        "zone_id": zone_id,
        "detections": [
            {
                "event_id": e.event_id,
                "detection": e.detection,
                "confidence": e.confidence,
                "source": e.source,
                "correlation": e.correlation,
                "correlation_source": e.correlation_source,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


if __name__ == "__main__":
    server.run_stdio_async()
