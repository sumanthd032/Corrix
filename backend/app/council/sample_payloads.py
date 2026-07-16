"""Hand-crafted evidence payloads for S1-S4, per CORRIX_BUILD_PLAN.md Step 4:
"Prompt-engineer each persona against hand-fed sample payloads first —
don't wait for Step 2/3 to be fully wired; a hardcoded S1-shaped JSON blob
is enough to start." These are the raw, per-agent evidence slices fed to
each persona's LLM call — deliberately plain factual descriptions, not
pre-written English verdicts, so the persona's own prompt is what does
the actual reasoning.

Each payload only contains the fields that agent's own real-world
counterpart would actually see — mirroring the agent-silo design, not
just narratively but in the shape of this test data too.
"""

S1_ANCHOR_PAYLOAD = {
    "zone_id": "Z1",
    "scenario_id": "S1",
    "process_safety_engineer": (
        "Ladle moisture/dryness checklist CHK-0410 compliance score for Zone 1 "
        "dropped from 0.92 to 0.57 approximately 8 minutes ago. No further "
        "degradation since."
    ),
    "permit_control_officer": (
        "Permit P-2291 (lifting_operation), issued by Shift Supervisor A. Rao, "
        "active in Zone 1, linked to checklist CHK-0410."
    ),
    "shift_operations": (
        "Zone 1 shift changeover begins in 8 minutes. Changeover window is 15 "
        "minutes."
    ),
    "site_safety_observer": (
        "Badge W-0142 has been present in Zone 1 for the last 5 minutes, "
        "within the active permit's coverage window."
    ),
}

S2_CONFINED_SPACE_PAYLOAD = {
    "zone_id": "Z7",
    "scenario_id": "S2",
    "process_safety_engineer": (
        "Zone 7 (confined space, Gas Collection Vault) combustible gas reading: "
        "O2 20.1% (normal), LEL 13.8% and rising (alarm threshold 10% LEL, "
        "already exceeded), reading has climbed sharply in the last 15 minutes "
        "after a period of relative stability around 7% LEL."
    ),
    "permit_control_officer": (
        "Permit P-4410 (confined_space_entry) active in Zone 7."
    ),
    "shift_operations": (
        "Zone 7 shift changeover begins in 5 minutes."
    ),
    "site_safety_observer": (
        "Badge W-0210 entered Zone 7 approximately 2 minutes ago, shortly "
        "before the gas reading began its second climb."
    ),
}

S3_MAINTENANCE_GAS_PAYLOAD = {
    "zone_id": "Z2",
    "scenario_id": "S3",
    "process_safety_engineer": (
        "Zone 2 (Gas Collection Main) combustible gas reading has risen "
        "steadily from 2% LEL to 12.4% LEL over the last 70 minutes (alarm "
        "threshold 10% LEL, exceeded roughly 10 minutes ago), trend is "
        "monotonic and still climbing."
    ),
    "permit_control_officer": (
        "Permit P-7701 (cold_work, routine maintenance) active in Zone 2, "
        "issued at the start of the gas rise."
    ),
    "shift_operations": (
        "Zone 2 shift changeover begins in 20 minutes."
    ),
    "site_safety_observer": (
        "Badge W-0305 has been present in Zone 2 for the entire maintenance "
        "window, consistent with the active permit."
    ),
}

S4_HOT_WORK_PAYLOAD = {
    "zone_id": "Z2",
    "scenario_id": "S4",
    "process_safety_engineer": (
        "Zone 2 combustible gas reading spiked from 2% LEL to 11.3% LEL over "
        "roughly 5 minutes (alarm threshold 10% LEL, exceeded), consistent "
        "with a discrete release; now beginning to decay."
    ),
    "permit_control_officer": (
        "Permit P-9102 (hot_work) active in Zone 2, issued 10 minutes before "
        "the gas release began."
    ),
    "shift_operations": (
        "Zone 2 shift changeover begins in 20 minutes."
    ),
    "site_safety_observer": (
        "Badge W-0417 present in Zone 2 throughout, consistent with the "
        "active hot-work permit."
    ),
}

ALL_SAMPLE_PAYLOADS = {
    "S1": S1_ANCHOR_PAYLOAD,
    "S2": S2_CONFINED_SPACE_PAYLOAD,
    "S3": S3_MAINTENANCE_GAS_PAYLOAD,
    "S4": S4_HOT_WORK_PAYLOAD,
}
