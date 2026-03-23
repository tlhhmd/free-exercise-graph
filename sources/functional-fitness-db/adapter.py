"""
sources/functional-fitness-db/adapter.py

Source adapter for Strength to Overcome — Functional Fitness Exercise Database.

get_exercises() returns a normalized list of exercise dicts for pipeline/canonicalize.py.
Extracted from enrich.py: _read_exercises() + _load_crosswalks() logic, adapted to
the canonical adapter shape.
"""

import csv
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

_RAW_CSV   = _HERE / "raw" / "Exercises.csv"
_MAPPINGS  = _HERE / "mappings"

SOURCE = "functional-fitness-db"

# ─── Constant maps ────────────────────────────────────────────────────────────

_PLANE_MAP = {
    "Sagittal Plane":   "SagittalPlane",
    "Frontal Plane":    "FrontalPlane",
    "Transverse Plane": "TransversePlane",
}

_STYLE_MAP = {
    "Animal Flow":           "AnimalFlow",
    "Balance":               "Balance",
    "Ballistics":            "Ballistics",
    "Bodybuilding":          "Bodybuilding",
    "Calisthenics":          "Calisthenics",
    "Grinds":                "Grinds",
    "Olympic Weightlifting": "OlympicWeightlifting",
    "Postural":              "Postural",
    "Powerlifting":          "Powerlifting",
}

_STYLE_REROUTES = {
    "Plyometric": ("training_modality_hint", "Plyometrics"),
    "Mobility":   ("movement_pattern_hint",  "Mobility"),
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_")


def _load_crosswalks() -> dict:
    muscle_xwalk: dict[str, str] = {}
    with open(_MAPPINGS / "muscle_crosswalk.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] == "matched":
                muscle_xwalk[row["source_value"]] = row["feg_local_name"]

    movement_xwalk: dict[str, tuple[str, str]] = {}
    with open(_MAPPINGS / "movement_pattern_crosswalk.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] == "matched":
                movement_xwalk[row["source_value"]] = (
                    row["feg_local_name"],
                    row["target_property"],
                )

    eq_xwalk: dict[str, str] = {}
    eq_path = _MAPPINGS / "equipment_crosswalk.csv"
    if eq_path.exists():
        with open(eq_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["status"] == "matched":
                    eq_xwalk[row["source_value"]] = row["feg_local_name"]

    return {"muscles": muscle_xwalk, "movements": movement_xwalk, "equipment": eq_xwalk}


# ─── Main export ──────────────────────────────────────────────────────────────

def get_exercises() -> list[dict]:
    """Return exercises from functional-fitness-db in canonical adapter format.

    Each exercise dict has:
      id           str   — slugified name
      source       str   — 'functional-fitness-db'
      display_name str   — original name
      equipment    list[str]   — feg local names
      known        dict  — asserted structured facts; keys:
        muscles              list[{feg_name, source_role}]
        movement_patterns    list[str]   — feg local names
        joint_actions_from_source list[str]  — feg local names (primary/supporting TBD by LLM)
        plane_of_motion      list[str]
        laterality           str | None
        is_combination       bool | None
        is_compound          bool | None
        force_type_hint      str | None
        exercise_style       list[str]
        training_modality_hint str | None
        movement_pattern_hint  str | None
      absent       list[str]   — empty for ffdb (all fields measured)
    """
    crosswalks = _load_crosswalks()
    muscle_xwalk   = crosswalks["muscles"]
    movement_xwalk = crosswalks["movements"]
    eq_xwalk       = crosswalks["equipment"]

    exercises = []
    with open(_RAW_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    for row in rows[16:]:  # data starts at row 17 (0-indexed: 16)
        if not row or not row[1].strip():
            continue
        name = row[1].strip()

        # ── Muscles ───────────────────────────────────────────────────────
        muscles = []
        for val, role in [
            (row[6]  if len(row) > 6  else "", "prime"),
            (row[7]  if len(row) > 7  else "", "secondary"),
            (row[8]  if len(row) > 8  else "", "tertiary"),
        ]:
            val = val.strip()
            if not val:
                continue
            feg_name = muscle_xwalk.get(val)
            if feg_name:
                muscles.append({"feg_name": feg_name, "source_role": role})

        # ── Equipment ─────────────────────────────────────────────────────
        equipment = []
        for val in [
            row[9]  if len(row) > 9  else "",
            row[11] if len(row) > 11 else "",
        ]:
            val = val.strip()
            feg = eq_xwalk.get(val)
            if feg:
                equipment.append(feg)

        # ── Movement patterns + joint actions ─────────────────────────────
        movement_patterns: list[str] = []
        joint_actions_from_source: list[str] = []
        for val in [
            row[21] if len(row) > 21 else "",
            row[22] if len(row) > 22 else "",
            row[23] if len(row) > 23 else "",
        ]:
            val = val.strip()
            if not val:
                continue
            mapping = movement_xwalk.get(val)
            if mapping:
                feg_name, target_prop = mapping
                if target_prop == "feg:movementPattern":
                    movement_patterns.append(feg_name)
                else:
                    joint_actions_from_source.append(feg_name)

        # ── Plane of motion ───────────────────────────────────────────────
        planes = []
        for val in [
            row[24] if len(row) > 24 else "",
            row[25] if len(row) > 25 else "",
            row[26] if len(row) > 26 else "",
        ]:
            feg_name = _PLANE_MAP.get(val.strip())
            if feg_name:
                planes.append(feg_name)

        # ── Laterality (col 30) ───────────────────────────────────────────
        laterality_raw = row[30].strip() if len(row) > 30 else ""
        laterality = laterality_raw if laterality_raw in {
            "Bilateral", "Unilateral", "Contralateral", "Ipsilateral"
        } else None

        # ── Is combination (col 20) ───────────────────────────────────────
        combo_raw = row[20].strip() if len(row) > 20 else ""
        is_combination: bool | None = (
            True  if combo_raw == "Combo Exercise" else
            False if combo_raw == "Single Exercise" else
            None
        )

        # ── Is compound (col 29) ──────────────────────────────────────────
        mechanics_raw = row[29].strip() if len(row) > 29 else ""
        is_compound: bool | None = (
            True  if mechanics_raw == "Compound"  else
            False if mechanics_raw == "Isolation" else
            None
        )
        force_type_hint = mechanics_raw if mechanics_raw not in {"Compound", "Isolation", ""} else None

        # ── Exercise classification (col 31) ──────────────────────────────
        style_raw = row[31].strip() if len(row) > 31 else ""
        exercise_style: list[str] = []
        training_modality_hint: str | None = None
        movement_pattern_hint: str | None = None

        if style_raw in _STYLE_MAP:
            exercise_style.append(_STYLE_MAP[style_raw])
        elif style_raw in _STYLE_REROUTES:
            field, feg_name = _STYLE_REROUTES[style_raw]
            if field == "training_modality_hint":
                training_modality_hint = feg_name
            else:
                movement_pattern_hint = feg_name

        exercises.append({
            "id":           _slugify(name),
            "source":       SOURCE,
            "display_name": name,
            "equipment":    equipment,
            "known": {
                "muscles":                   muscles,
                "movement_patterns":         movement_patterns,
                "joint_actions_from_source": joint_actions_from_source,
                "plane_of_motion":           planes,
                "laterality":                laterality,
                "is_combination":            is_combination,
                "is_compound":               is_compound,
                "force_type_hint":           force_type_hint,
                "exercise_style":            exercise_style,
                "training_modality_hint":    training_modality_hint,
                "movement_pattern_hint":     movement_pattern_hint,
            },
            "absent": [],  # ffdb has structured columns for all predicate categories
        })

    return exercises
