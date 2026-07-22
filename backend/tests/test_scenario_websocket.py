"""The scenario WebSocket's playback/reconsideration control flow
(`app.api.websocket._stream_playback`, `scenario_websocket`). Two tiers:
a fast, LLM-free tier driving `_stream_playback` directly against a
hand-built playback with `_convene_council`/`_reconsider` mocked out, so
the message-routing logic itself is what's under test; and one real
end-to-end run through `/ws/scenario`, matching this suite's existing
`skip_on_rate_limit()` discipline for real LLM calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api import websocket
from app.api.live_scenario import PlaybackFrame
from app.main import app
from tests.conftest import skip_on_rate_limit

ZONE_ID = "Z1"


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


def _playback(trigger_frame_index: int = 0):
    return SimpleNamespace(
        frames=[
            PlaybackFrame(minute=0.0, zone_risk={ZONE_ID: "SAFE"}, worker_positions={}),
            PlaybackFrame(minute=1.0, zone_risk={ZONE_ID: "HIGH"}, worker_positions={}),
        ],
        trigger_frame_index=trigger_frame_index,
    )


def test_stream_playback_routes_reconsider_messages_correctly():
    """A single pass exercising every case at once, resolved purely
    through queue ordering (no real-time injection needed, since
    `incoming.get_nowait()`/`get()` return whatever is already queued in
    FIFO order regardless of which loop iteration reads it):

    1. A "reconsider" queued before the trigger frame has no verdict to
       attach to and must be dropped (the bug this feature's own
       restructuring introduced and then fixed: it must NOT be requeued
       and fire later against the eventual verdict).
    2. A "reconsider" queued for the frame right after the trigger (a
       verdict now exists) must call `_reconsider`.
    3. A "reconsider" queued for consumption during the trailing idle
       loop (i.e. after `playback_complete`) must still call
       `_reconsider` -- the regression case this feature exists to fix.
    4. A "start" message ends everything, even with reconsiderations
       already having happened, and is returned to the caller.
    """
    incoming: "asyncio.Queue[dict]" = asyncio.Queue()
    incoming.put_nowait({"type": "reconsider", "note": "premature, before any verdict"})
    incoming.put_nowait({"type": "reconsider", "note": "first reconsideration, mid-playback"})
    incoming.put_nowait({"type": "reconsider", "note": "second reconsideration, post-completion"})
    incoming.put_nowait({"type": "start", "scenario_id": "S2"})

    fake_ws = _FakeWebSocket()
    mock_convene = AsyncMock(return_value=SimpleNamespace(marker="convened"))
    mock_reconsider = AsyncMock(side_effect=lambda ws, context, note: SimpleNamespace(marker=note))

    with (
        patch.object(websocket, "_convene_council", mock_convene),
        patch.object(websocket, "_reconsider", mock_reconsider),
    ):
        result = asyncio.run(
            websocket._stream_playback(fake_ws, incoming, _playback(trigger_frame_index=0))
        )

    assert mock_convene.call_count == 1
    assert [call.args[2] for call in mock_reconsider.call_args_list] == [
        "first reconsideration, mid-playback",
        "second reconsideration, post-completion",
    ]
    assert result == {"type": "start", "scenario_id": "S2"}
    assert {"type": "playback_complete"} in fake_ws.sent
    assert any(m["type"] == "tick" for m in fake_ws.sent)


def test_stream_playback_reconsider_with_no_convening_ever_run_is_dropped():
    """No trigger frame at all in this playback (a normal-day run):
    every "reconsider" sent must be dropped, never call `_reconsider`,
    and never crash the connection."""
    incoming: "asyncio.Queue[dict]" = asyncio.Queue()
    incoming.put_nowait({"type": "reconsider", "note": "nothing to reconsider"})
    incoming.put_nowait({"type": "reconsider", "note": "still nothing"})
    incoming.put_nowait({"type": "__disconnect__"})

    fake_ws = _FakeWebSocket()
    mock_convene = AsyncMock()
    mock_reconsider = AsyncMock()

    # trigger_frame_index far past the end of `frames`, so the trigger
    # branch is never reached -- a "no compound risk detected" playback.
    playback = SimpleNamespace(
        frames=[PlaybackFrame(minute=0.0, zone_risk={ZONE_ID: "SAFE"}, worker_positions={})],
        trigger_frame_index=999,
    )

    with (
        patch.object(websocket, "_convene_council", mock_convene),
        patch.object(websocket, "_reconsider", mock_reconsider),
    ):
        result = asyncio.run(websocket._stream_playback(fake_ws, incoming, playback))

    mock_convene.assert_not_called()
    mock_reconsider.assert_not_called()
    assert result == {"type": "__disconnect__"}


def test_scenario_websocket_reconsider_after_verdict_produces_a_new_verdict():
    """Real end-to-end run through /ws/scenario: real playback ticking,
    a real Council convening, and a real Chair-only reconsideration
    incorporating a Safety Officer's note, all through the actual route
    (not the mocked unit tier above)."""
    client = TestClient(app)
    first_verdict = None
    second_verdict = None
    reconsidering_seen = False

    with client.websocket_connect("/ws/scenario") as ws:
        ws.send_json({"type": "start", "scenario_id": "S1"})
        with skip_on_rate_limit():
            for _ in range(400):
                msg = ws.receive_json()
                if msg["type"] == "verdict":
                    first_verdict = msg["verdict"]
                    break
                if msg["type"] in ("playback_complete", "council_error"):
                    break
            assert first_verdict is not None, "never reached a verdict during S1's playback"

            ws.send_json(
                {
                    "type": "reconsider",
                    "note": "The compliance reading was independently reverified on-site.",
                }
            )
            for _ in range(50):
                msg = ws.receive_json()
                if msg["type"] == "reconsidering":
                    reconsidering_seen = True
                if msg["type"] == "verdict":
                    second_verdict = msg["verdict"]
                    break

        assert reconsidering_seen
        assert second_verdict is not None
        assert second_verdict["council"] == first_verdict["council"]
