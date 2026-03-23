"""
enrich.py — functional-fitness-db enrichment adapter

Source-specific concerns:
  - Reading and parsing Exercises.csv
  - Resolving known fields via crosswalk CSVs (muscles, movement patterns)
  - Routing col 31 (Primary Exercise Classification) to correct enrichment fields
  - Formatting user messages with pre-classified context for the LLM

The LLM receives pre-classified fields as strong hints and fills genuine gaps:
  - muscle degrees (source prime/secondary/tertiary guide but don't dictate)
  - training_modalities
  - primary vs supporting joint action distinction
  - any muscles the source omitted

Usage:
    python3 sources/functional-fitness-db/enrich.py
    python3 sources/functional-fitness-db/enrich.py --limit 10
    python3 sources/functional-fitness-db/enrich.py --concurrency 4
    python3 sources/functional-fitness-db/enrich.py --force "Bulgarian_Split_Squat"
    python3 sources/functional-fitness-db/enrich.py --retry-quarantine
    python3 sources/functional-fitness-db/enrich.py --reparse-quarantine
    python3 sources/functional-fitness-db/enrich.py --dump-prompts /tmp/prompts
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from enrichment.service import DEFAULT_MODEL, reparse_quarantine, run_enrichment

# ─── Paths ────────────────────────────────────────────────────────────────────

_RAW_CSV    = _HERE / "raw" / "Exercises.csv"
_MAPPINGS   = _HERE / "mappings"
_ENRICHED   = _HERE / "enriched"
_QUARANTINE = _HERE / "quarantine"
_LOG        = _HERE / "enrich.log"

# ─── Plane of motion normalization ────────────────────────────────────────────

_PLANE_MAP = {
    "Sagittal Plane":  "SagittalPlane",
    "Frontal Plane":   "FrontalPlane",
    "Transverse Plane": "TransversePlane",
}

# ─── Exercise classification routing (col 31) ─────────────────────────────────
# Values that map cleanly to feg:ExerciseStyle local names:
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
# Values that belong to a different field:
_STYLE_REROUTES = {
    "Plyometric": ("training_modality_hint", "Plyometrics"),
    "Mobility":   ("movement_pattern_hint",  "Mobility"),
}
# "Unsorted*" → drop (not in either map)

# ─── Crosswalk loading ────────────────────────────────────────────────────────


def _load_crosswalks() -> dict:
    """Load matched rows from crosswalk CSVs into lookup dicts."""
    muscle_xwalk: dict[str, str] = {}
    with open(_MAPPINGS / "muscle_crosswalk.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] == "matched":
                muscle_xwalk[row["source_value"]] = row["feg_local_name"]

    # movement_xwalk: source_value → (feg_local_name, target_property)
    movement_xwalk: dict[str, tuple[str, str]] = {}
    with open(_MAPPINGS / "movement_pattern_crosswalk.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] == "matched":
                movement_xwalk[row["source_value"]] = (
                    row["feg_local_name"],
                    row["target_property"],
                )

    return {"muscles": muscle_xwalk, "movements": movement_xwalk}


# ─── CSV parsing ──────────────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    """Convert exercise name to a stable file-safe ID."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_")


def _read_exercises(crosswalks: dict) -> list[dict]:
    """Parse Exercises.csv and return a list of exercise dicts with resolved known fields."""
    muscle_xwalk   = crosswalks["muscles"]
    movement_xwalk = crosswalks["movements"]

    exercises = []
    with open(_RAW_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    for row in rows[16:]:  # data starts at row 17 (0-indexed: 16)
        if not row or not row[1].strip():
            continue
        name = row[1].strip()

        # ── Muscles with source roles ──────────────────────────────────────
        muscles = []
        for val, role in [
            (row[6] if len(row) > 6 else "", "prime"),
            (row[7] if len(row) > 7 else "", "secondary"),
            (row[8] if len(row) > 8 else "", "tertiary"),
        ]:
            val = val.strip()
            if not val:
                continue
            feg_name = muscle_xwalk.get(val)
            if feg_name:
                muscles.append({"feg_name": feg_name, "source_role": role})
            # gaps silently dropped — LLM will infer from name/context

        # ── Equipment (for build.py, not enrichment) ───────────────────────
        equipment = []
        eq_xwalk_path = _MAPPINGS / "equipment_crosswalk.csv"
        # loaded inline to avoid a second pass; small file
        # (cached in caller via crosswalks dict on repeated use)
        eq_xwalk = crosswalks.get("equipment", {})
        for val in [
            row[9] if len(row) > 9 else "",
            row[11] if len(row) > 11 else "",
        ]:
            val = val.strip()
            feg_name = eq_xwalk.get(val)
            if feg_name:
                equipment.append(feg_name)

        # ── Movement patterns + joint actions from source ──────────────────
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

        # ── Plane of motion ────────────────────────────────────────────────
        planes = []
        for val in [
            row[24] if len(row) > 24 else "",
            row[25] if len(row) > 25 else "",
            row[26] if len(row) > 26 else "",
        ]:
            val = val.strip()
            feg_name = _PLANE_MAP.get(val)
            if feg_name:
                planes.append(feg_name)

        # ── Laterality (col 30) ────────────────────────────────────────────
        laterality_raw = row[30].strip() if len(row) > 30 else ""
        laterality = laterality_raw if laterality_raw in {
            "Bilateral", "Unilateral", "Contralateral", "Ipsilateral"
        } else None

        # ── Is combination (col 20) ────────────────────────────────────────
        combo_raw = row[20].strip() if len(row) > 20 else ""
        is_combination: bool | None = (
            True  if combo_raw == "Combo Exercise" else
            False if combo_raw == "Single Exercise" else
            None
        )

        # ── Is compound (col 29) ──────────────────────────────────────────
        mechanics_raw = row[29].strip() if len(row) > 29 else ""
        is_compound: bool | None = (
            True  if mechanics_raw == "Compound" else
            False if mechanics_raw == "Isolation" else
            None  # "Pull" and others are ambiguous — let LLM decide
        )
        force_type_hint = mechanics_raw if mechanics_raw not in {"Compound", "Isolation", ""} else None

        # ── Exercise classification (col 31) — Option A routing ───────────
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
        # else: drop (Unsorted* etc.)

        exercises.append({
            "id": _slugify(name),
            "name": name,
            "equipment": equipment,
            "known": {
                "muscles": muscles,
                "movement_patterns": movement_patterns,
                "joint_actions_from_source": joint_actions_from_source,
                "plane_of_motion": planes,
                "laterality": laterality,
                "is_combination": is_combination,
                "is_compound": is_compound,
                "force_type_hint": force_type_hint,
                "exercise_style": exercise_style,
                "training_modality_hint": training_modality_hint,
                "movement_pattern_hint": movement_pattern_hint,
            },
        })

    return exercises


# ─── User message ─────────────────────────────────────────────────────────────


def format_user_message(exercise: dict) -> str:
    known = exercise["known"]
    lines = [f"Name: {exercise['name']}", ""]

    # Pre-classified context block
    context_lines = []

    if known["muscles"]:
        muscle_str = ", ".join(
            f"{m['feg_name']} ({m['source_role']})" for m in known["muscles"]
        )
        context_lines.append(f"  Muscles: {muscle_str}")

    if known["movement_patterns"]:
        context_lines.append(f"  Movement patterns: {', '.join(known['movement_patterns'])}")

    if known["joint_actions_from_source"]:
        context_lines.append(
            f"  Joint actions from source (assign to primary or supporting): "
            f"{', '.join(known['joint_actions_from_source'])}"
        )

    if known["laterality"]:
        context_lines.append(f"  Laterality: {known['laterality']}")

    if known["plane_of_motion"]:
        context_lines.append(f"  Plane of motion: {', '.join(known['plane_of_motion'])}")

    if known["is_combination"] is not None:
        context_lines.append(f"  Is combination: {str(known['is_combination']).lower()}")

    if known["is_compound"] is not None:
        context_lines.append(f"  Is compound: {str(known['is_compound']).lower()}")

    if known["force_type_hint"]:
        context_lines.append(f"  Force type (source): {known['force_type_hint']}")

    if known["exercise_style"]:
        context_lines.append(f"  Exercise style: {', '.join(known['exercise_style'])}")

    if known["training_modality_hint"]:
        context_lines.append(f"  Training modality (from source classification): {known['training_modality_hint']}")

    if known["movement_pattern_hint"]:
        context_lines.append(f"  Movement pattern (from source classification): {known['movement_pattern_hint']}")

    if context_lines:
        lines.append("Known from source (use as strong hints):")
        lines.extend(context_lines)
        lines.append("")
        lines.append(
            "Source muscle roles guide degrees "
            "(prime \u2248 PrimeMover, secondary \u2248 Synergist/PrimeMover, "
            "tertiary \u2248 Stabilizer/Synergist). "
            "Override with your judgment \u2014 especially PassiveTarget for mobility/stretch exercises. "
            "Add any muscles the source omitted."
        )

    return "\n".join(lines)


# ─── Source-specific functions ────────────────────────────────────────────────


def make_record(exercise: dict, fields: dict, vocab_versions: dict) -> dict:
    return {
        "id": exercise["id"],
        "name": exercise["name"],
        "equipment": exercise["equipment"],
        **fields,
        "vocabulary_versions": vocab_versions,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich functional-fitness-db exercises with LLM classifications."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--force", nargs="+", metavar="EXERCISE_ID")
    parser.add_argument("--retry-quarantine", action="store_true")
    parser.add_argument("--reparse-quarantine", action="store_true")
    parser.add_argument("--dump-prompts", type=Path, default=None, metavar="DIR")
    args = parser.parse_args()

    if args.reparse_quarantine:
        reparse_quarantine(_QUARANTINE, _ENRICHED, make_record)
        return

    print("Loading crosswalks...")
    crosswalks = _load_crosswalks()

    eq_path = _MAPPINGS / "equipment_crosswalk.csv"
    if eq_path.exists():
        eq_xwalk: dict[str, str] = {}
        with open(eq_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["status"] == "matched":
                    eq_xwalk[row["source_value"]] = row["feg_local_name"]
        crosswalks["equipment"] = eq_xwalk

    exercises = _read_exercises(crosswalks)

    run_enrichment(
        exercises=exercises,
        format_fn=format_user_message,
        make_record=make_record,
        enriched_dir=_ENRICHED,
        quarantine_dir=_QUARANTINE,
        log_path=_LOG,
        model=args.model,
        concurrency=args.concurrency,
        limit=args.limit,
        randomise=args.random,
        force=args.force,
        retry_quarantine=args.retry_quarantine,
        dump_prompts_dir=args.dump_prompts,
    )


if __name__ == "__main__":
    main()
