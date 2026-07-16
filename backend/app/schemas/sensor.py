from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class GasType(str, Enum):
    O2 = "O2"
    CO = "CO"
    H2S = "H2S"
    LEL = "LEL"


class GasSensorReading(BaseModel):
    """Atmospheric gas sensor reading for S2/S3/S4, modeled by the OU process
    in CORRIX_DATA_METHODOLOGY.md §3. Not used for S1 — see compliance.py."""

    zone_id: str
    gas_type: GasType
    concentration: float
    unit: str
    timestamp: datetime
