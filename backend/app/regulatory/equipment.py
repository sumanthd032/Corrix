"""A small, illustrative equipment list, one plausible asset per zone,
just enough for the Equipment node type in the graph schema to be
genuinely populated and linkable from Incident records, not merely
declared. Not exhaustive; a real deployment would import an actual
asset register (§16 roadmap)."""

EQUIPMENT = [
    {"equipment_id": "EQ-Z1-LADLE-02", "name": "Ladle 2", "equipment_type": "ladle", "zone_id": "Z1"},
    {"equipment_id": "EQ-Z2-GASHDR-01", "name": "Gas Collection Header", "equipment_type": "gas_header", "zone_id": "Z2"},
    {"equipment_id": "EQ-Z3-WELDBAY-01", "name": "Maintenance Welding Bay", "equipment_type": "workbench", "zone_id": "Z3"},
    {"equipment_id": "EQ-Z7-VAULT-01", "name": "Gas Collection Vault Access Hatch", "equipment_type": "confined_space_entry_point", "zone_id": "Z7"},
]
