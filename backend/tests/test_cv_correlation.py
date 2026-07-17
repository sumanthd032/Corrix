"""Scripted correlation layer: a CV detection's zone-context correlation
is checked against the real Step 2 worker-location stream, not
hardcoded, per CORRIX_DATA_METHODOLOGY.md §9 and Step 6's Definition of
Done (source/correlation_source fields correctly valued)."""

from datetime import datetime, timedelta

from app.cv.correlation import correlate_detection
from app.cv.inference import Detection
from app.schemas import BadgeEventType, BadgePingEvent

START = datetime(2026, 7, 19, 10, 0, 0)


def test_person_detection_with_matching_badge_ping():
    detection = Detection(class_name="Person", confidence=0.9, bbox_xyxy=(0, 0, 10, 10))
    pings = [
        BadgePingEvent(
            badge_id="W-0142", zone_id="Z1", timestamp=START, event_type=BadgeEventType.ZONE_ENTRY
        )
    ]
    event = correlate_detection(
        detection, "Z1", START + timedelta(seconds=30), pings, event_id="CV-0001"
    )
    assert event.source == "real_inference"
    assert event.correlation_source == "simulated"
    assert "matches badge-ping W-0142" in event.correlation


def test_person_detection_with_no_matching_badge_ping():
    detection = Detection(class_name="Person", confidence=0.9, bbox_xyxy=(0, 0, 10, 10))
    event = correlate_detection(detection, "Z1", START, [], event_id="CV-0002")
    assert event.source == "real_inference"
    assert event.correlation_source == "simulated"
    assert event.correlation == "no matching badge-ping in Z1"


def test_person_detection_with_stale_badge_ping_beyond_tolerance():
    detection = Detection(class_name="Person", confidence=0.9, bbox_xyxy=(0, 0, 10, 10))
    pings = [
        BadgePingEvent(
            badge_id="W-0142", zone_id="Z1", timestamp=START, event_type=BadgeEventType.ZONE_ENTRY
        )
    ]
    stale_time = START + timedelta(minutes=10)
    event = correlate_detection(detection, "Z1", stale_time, pings, event_id="CV-0003")
    assert event.correlation == "no matching badge-ping in Z1"


def test_non_person_detection_has_no_correlation():
    detection = Detection(class_name="no_helmet", confidence=0.8, bbox_xyxy=(0, 0, 10, 10))
    event = correlate_detection(detection, "Z1", START, [], event_id="CV-0004")
    assert event.correlation is None
    assert event.correlation_source is None
    assert event.source == "real_inference"
