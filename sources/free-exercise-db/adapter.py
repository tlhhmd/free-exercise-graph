"""
sources/free-exercise-db/adapter.py

Source adapter for yuhonas/free-exercise-db.

get_exercises() returns a normalized list of exercise dicts for pipeline/canonicalize.py.
The schema is intentionally thin — fed has no structured movement pattern, joint action,
laterality, or is_compound columns. Those fields are absent (not conflicted).
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_RAW_EXERCISES = _HERE / "raw" / "exercises.json"
_EQUIPMENT_CROSSWALK = _HERE / "mappings" / "equipment_crosswalk.csv"

SOURCE = "free-exercise-db"


def _load_equipment_crosswalk() -> dict[str, str]:
    import csv
    result: dict[str, str] = {}
    if not _EQUIPMENT_CROSSWALK.exists():
        return result
    with _EQUIPMENT_CROSSWALK.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # fed crosswalk uses 'source_string' column (not 'source_value')
            key = row.get("source_string") or row.get("source_value", "")
            feg = row.get("feg_local_name", "")
            if key and feg:
                result[key] = feg
    return result


def get_exercises() -> list[dict]:
    """Return exercises from free-exercise-db in canonical adapter format.

    Each exercise dict has:
      id           str   — slugified name (stable file-safe ID)
      source       str   — 'free-exercise-db'
      display_name str   — original name
      equipment    list[str]   — feg local names (may be empty)
      known        dict  — asserted structured facts; keys:
        muscles    list[{feg_name, source_role}]  — from primary/secondary muscle fields
        instructions str  — joined instruction text (for LLM enrichment context)
      absent       list[str]   — predicates absent in this source
                                 (no coverage gap conflict — they simply weren't measured)
    """
    raw: list[dict] = json.loads(_RAW_EXERCISES.read_text())
    equip_map = _load_equipment_crosswalk()

    exercises = []
    for ex in raw:
        name = ex.get("name", "").strip()
        if not name:
            continue

        # ID: exercises.json already has an 'id' field; use it, replacing hyphens
        ex_id = str(ex.get("id", name)).replace("-", "_").replace(" ", "_")

        # Equipment: fed has a single string field
        equipment: list[str] = []
        eq_raw = ex.get("equipment") or ""
        if isinstance(eq_raw, list):
            for val in eq_raw:
                feg = equip_map.get(str(val).strip())
                if feg:
                    equipment.append(feg)
        elif eq_raw:
            feg = equip_map.get(eq_raw.strip())
            if feg:
                equipment.append(feg)

        # Muscles: primary/secondary from source — raw strings, NO feg crosswalk exists for fed.
        # These are stored as LLM context hints only (via source_metadata), not as structured claims.
        # pipeline/enrich.py formats them into the user message; build.py gets muscle data from
        # inferred_claims only for fed-sourced entities.
        primary_muscles   = [m.strip() for m in ex.get("primaryMuscles", [])   if m.strip()]
        secondary_muscles = [m.strip() for m in ex.get("secondaryMuscles", []) if m.strip()]
        muscles_hint = ""
        if primary_muscles or secondary_muscles:
            parts = []
            if primary_muscles:
                parts.append("primary: " + ", ".join(primary_muscles))
            if secondary_muscles:
                parts.append("secondary: " + ", ".join(secondary_muscles))
            muscles_hint = " | ".join(parts)

        instructions = " ".join(ex.get("instructions", []) or []).strip()

        exercises.append({
            "id": ex_id,
            "source": SOURCE,
            "display_name": name,
            "equipment": equipment,
            "known": {
                "muscles":       [],          # no feg crosswalk — muscles stored as hint text only
                "muscles_hint":  muscles_hint, # raw muscle strings for LLM context
                "instructions":  instructions,
            },
            # fed has no structured data for these predicates — omit rather than infer
            "absent": [
                "movement_pattern",
                "joint_action_hint",
                "plane_of_motion",
                "laterality",
                "is_compound",
                "is_combination",
                "exercise_style",
                "training_modality_hint",
            ],
        })

    return exercises
