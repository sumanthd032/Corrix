"""Virtual Sensor Simulator control-surface endpoints, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 19: what a judge's slider/toggle/
button in VirtualSensorPanel.tsx (Step 21) actually calls. Each route
is a thin wrapper over app/ingestion/virtual_sensor_publisher.py; no
Council, detection, or MQTT logic lives here.

Rate-limited per factory_id (Step 26): a simple in-memory token bucket
shared across all three routes for a given factory, so a rapidly-
dragged slider or a scripted flood can't publish fast enough to
overwhelm the live-factory websocket's Council-convening loop. A
token bucket, not a fixed window, so normal interactive use (a few
slider drags, a badge toggle, a permit button) never gets throttled,
only a sustained flood does.
"""

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ingestion.virtual_sensor_publisher import (
    publish_badge_event,
    publish_permit,
    set_gas_target,
)
from app.schemas import GasType, PermitType

router = APIRouter()

RATE_LIMIT_PER_SECOND = 10.0
RATE_LIMIT_BURST = 20.0


class _TokenBucket:
    def __init__(self, rate: float, burst: float) -> None:
        self._rate = rate
        self._tokens = burst
        self._burst = burst
        self._last_check = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_check
        self._last_check = now
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


_buckets: dict[str, _TokenBucket] = {}


def _check_rate_limit(factory_id: str) -> None:
    bucket = _buckets.setdefault(factory_id, _TokenBucket(RATE_LIMIT_PER_SECOND, RATE_LIMIT_BURST))
    if not bucket.allow():
        raise HTTPException(
            status_code=429,
            detail=f"Too many virtual-sensor requests for factory {factory_id}; slow down.",
        )


class SetGasTargetRequest(BaseModel):
    gas_type: GasType
    target_concentration: float


class BadgeToggleRequest(BaseModel):
    badge_id: str
    entering: bool


class PermitRequest(BaseModel):
    permit_type: PermitType


@router.post("/api/virtual-sensor/{factory_id}/{zone_id}/gas")
async def virtual_gas(factory_id: str, zone_id: str, req: SetGasTargetRequest) -> dict:
    _check_rate_limit(factory_id)
    await set_gas_target(factory_id, zone_id, req.gas_type.value, req.target_concentration)
    return {"ok": True}


@router.post("/api/virtual-sensor/{factory_id}/{zone_id}/badge")
async def virtual_badge(factory_id: str, zone_id: str, req: BadgeToggleRequest) -> dict:
    _check_rate_limit(factory_id)
    await publish_badge_event(factory_id, zone_id, req.badge_id, req.entering)
    return {"ok": True}


@router.post("/api/virtual-sensor/{factory_id}/{zone_id}/permit")
async def virtual_permit(factory_id: str, zone_id: str, req: PermitRequest) -> dict:
    _check_rate_limit(factory_id)
    await publish_permit(factory_id, zone_id, req.permit_type.value)
    return {"ok": True}
