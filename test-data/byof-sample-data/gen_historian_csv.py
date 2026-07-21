"""Throwaway generator for the BYOF sample historian CSV. Not part of the
app; run once to produce historian_readings.csv, then delete or ignore."""

import csv
import random
from datetime import datetime, timedelta, timezone

random.seed(7)

START = datetime(2026, 7, 21, 6, 0, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=1)
ROWS = 30
SPIKE_START = 24  # last 6 rows ramp toward the trigger

# (zone_id, gas_type, baseline, jitter, spike_target, direction)
CHANNELS = [
    ("Z1", "LEL", 5.0, 0.15, 46.0, "up"),     # ladle bay: rising flammable gas
    ("Z2", "CO", 22.0, 1.2, 160.0, "up"),      # gas main: CO buildup
    ("Z3", "O2", 20.9, 0.08, 14.5, "down"),    # maintenance bay: oxygen deficiency
    ("Z4", "H2S", 1.8, 0.15, 1.8, "flat"),     # control room: stays calm (control channel)
]

rows = []
for zone_id, gas, baseline, jitter, target, direction in CHANNELS:
    for i in range(ROWS):
        ts = START + STEP * i
        if direction == "flat" or i < SPIKE_START:
            value = baseline + random.uniform(-jitter, jitter)
        else:
            progress = (i - SPIKE_START + 1) / (ROWS - SPIKE_START)
            value = baseline + (target - baseline) * progress + random.uniform(-jitter, jitter)
        rows.append((ts.strftime("%Y-%m-%dT%H:%M:%SZ"), zone_id, round(value, 2), gas))

rows.sort(key=lambda r: r[0])

with open("historian_readings.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "zone_id", "concentration", "gas"])
    writer.writerows(rows)

print(f"wrote {len(rows)} rows")
