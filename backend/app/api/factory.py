"""Bring Your Own Factory: create and fetch a user-onboarded
`FactoryProfile`, per CORRIX_REAL_DATA_BUILD_PLAN.md Step 3. Persistence
is `app/storage/factory_store.py`'s `save_factory`/`load_factory`; this
module only adds request validation and HTTP framing.
"""

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.ingestion.csv_ingest import replay_csv
from app.ingestion.csv_upload_store import save_uploaded_csv
from app.schemas.factory import FactoryProfile
from app.storage.factory_store import load_factory, save_factory

router = APIRouter()


class SetDataSourceRequest(BaseModel):
    data_source: Literal["csv", "mqtt", "opcua"]


def _validate_layout(profile: FactoryProfile) -> None:
    zone_ids = [z.zone_id for z in profile.layout.zones]
    if len(zone_ids) != len(set(zone_ids)):
        raise HTTPException(status_code=422, detail="Zone IDs must be unique within a factory.")

    zone_id_set = set(zone_ids)
    for edge in profile.layout.adjacency:
        if edge.zone_a not in zone_id_set or edge.zone_b not in zone_id_set:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Adjacency edge references an unknown zone: "
                    f"{edge.zone_a} <-> {edge.zone_b}"
                ),
            )


@router.post("/api/factory")
async def create_factory(profile: FactoryProfile) -> dict:
    _validate_layout(profile)
    save_factory(profile)
    return {"factoryId": profile.factory_id}


@router.get("/api/factory/{factory_id}")
async def get_factory(factory_id: str) -> FactoryProfile:
    profile = load_factory(factory_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No factory found for id {factory_id}")
    return profile


@router.patch("/api/factory/{factory_id}/data-source")
async def set_data_source(factory_id: str, req: SetDataSourceRequest) -> FactoryProfile:
    profile = load_factory(factory_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No factory found for id {factory_id}")
    profile.data_source = req.data_source
    save_factory(profile)
    return profile


@router.post("/api/factory/{factory_id}/csv-upload")
async def upload_csv(
    factory_id: str,
    file: UploadFile,
    column_map: str = Form(...),
    speed_multiplier: float = Form(30.0),
) -> dict:
    profile = load_factory(factory_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No factory found for id {factory_id}")

    try:
        parsed_column_map = json.loads(column_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"column_map is not valid JSON: {exc}")

    file_bytes = await file.read()

    # Validate by actually running Step 6's adapter over the upload at
    # replay-instant speed into a throwaway queue, rather than
    # duplicating its column/type checks here: a bad column_map or a
    # malformed column never gets persisted as if it were usable.
    dry_run_queue: asyncio.Queue = asyncio.Queue()
    try:
        await replay_csv(file_bytes, parsed_column_map, speed_multiplier=1_000_000.0, queue=dry_run_queue)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    save_uploaded_csv(factory_id, file_bytes, parsed_column_map, speed_multiplier)
    return {"factoryId": factory_id, "rowsIngested": dry_run_queue.qsize()}
