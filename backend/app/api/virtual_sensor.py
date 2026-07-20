"""Virtual Sensor Simulator control-surface endpoints, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 19: what a judge's slider/toggle/
button in VirtualSensorPanel.tsx (Step 21) actually calls. Each route
is a thin wrapper over app/ingestion/virtual_sensor_publisher.py; no
Council, detection, or MQTT logic lives here.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.ingestion.virtual_sensor_publisher import (
    publish_badge_event,
    publish_permit,
    set_gas_target,
)
from app.schemas import GasType, PermitType

router = APIRouter()


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
    await set_gas_target(factory_id, zone_id, req.gas_type.value, req.target_concentration)
    return {"ok": True}


@router.post("/api/virtual-sensor/{factory_id}/{zone_id}/badge")
async def virtual_badge(factory_id: str, zone_id: str, req: BadgeToggleRequest) -> dict:
    await publish_badge_event(factory_id, zone_id, req.badge_id, req.entering)
    return {"ok": True}


@router.post("/api/virtual-sensor/{factory_id}/{zone_id}/permit")
async def virtual_permit(factory_id: str, zone_id: str, req: PermitRequest) -> dict:
    await publish_permit(factory_id, zone_id, req.permit_type.value)
    return {"ok": True}
