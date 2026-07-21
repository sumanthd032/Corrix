"""Where an uploaded historian CSV lives between Step 9's upload
endpoint and Step 8's live-factory WebSocket, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 9: "writing the raw CSV to a
per-factory path under a data/factory_uploads/ directory (gitignored)
and having Step 8's websocket read it by factory_id." Deliberately not
a database table, per the same step's explicit instruction not to
over-engineer this.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_ROOT = REPO_ROOT / "data" / "factory_uploads"


def _factory_dir(factory_id: str) -> Path:
    return UPLOADS_ROOT / factory_id


def save_uploaded_csv(
    factory_id: str, file_bytes: bytes, column_map: dict, speed_multiplier: float
) -> None:
    factory_dir = _factory_dir(factory_id)
    factory_dir.mkdir(parents=True, exist_ok=True)
    (factory_dir / "data.csv").write_bytes(file_bytes)
    (factory_dir / "meta.json").write_text(
        json.dumps({"column_map": column_map, "speed_multiplier": speed_multiplier}),
        encoding="utf-8",
    )


def load_uploaded_csv(factory_id: str) -> tuple[bytes, dict, float] | None:
    factory_dir = _factory_dir(factory_id)
    data_path = factory_dir / "data.csv"
    meta_path = factory_dir / "meta.json"
    if not data_path.is_file() or not meta_path.is_file():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return data_path.read_bytes(), meta["column_map"], meta["speed_multiplier"]


def _save_uploaded(
    kind: str, factory_id: str, file_bytes: bytes, column_map: dict, speed_multiplier: float
) -> None:
    factory_dir = _factory_dir(factory_id)
    factory_dir.mkdir(parents=True, exist_ok=True)
    (factory_dir / f"{kind}.csv").write_bytes(file_bytes)
    (factory_dir / f"{kind}_meta.json").write_text(
        json.dumps({"column_map": column_map, "speed_multiplier": speed_multiplier}),
        encoding="utf-8",
    )


def _load_uploaded(kind: str, factory_id: str) -> tuple[bytes, dict, float] | None:
    factory_dir = _factory_dir(factory_id)
    data_path = factory_dir / f"{kind}.csv"
    meta_path = factory_dir / f"{kind}_meta.json"
    if not data_path.is_file() or not meta_path.is_file():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return data_path.read_bytes(), meta["column_map"], meta["speed_multiplier"]


def save_uploaded_permits(
    factory_id: str, file_bytes: bytes, column_map: dict, speed_multiplier: float
) -> None:
    _save_uploaded("permits", factory_id, file_bytes, column_map, speed_multiplier)


def load_uploaded_permits(factory_id: str) -> tuple[bytes, dict, float] | None:
    return _load_uploaded("permits", factory_id)


def save_uploaded_badges(
    factory_id: str, file_bytes: bytes, column_map: dict, speed_multiplier: float
) -> None:
    _save_uploaded("badges", factory_id, file_bytes, column_map, speed_multiplier)


def load_uploaded_badges(factory_id: str) -> tuple[bytes, dict, float] | None:
    return _load_uploaded("badges", factory_id)
