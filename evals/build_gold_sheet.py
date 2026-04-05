"""
Build per-exercise gold-review CSVs from the live canonical pipeline DB.

Usage:
    python3 evals/build_gold_sheet.py
    python3 evals/build_gold_sheet.py --limit 60
    python3 evals/build_gold_sheet.py --entity-id good_morning --entity-id sit_up
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.db import DB_PATH, get_connection
from pipeline.effective_claims import effective_prediction_record, load_muscle_maps

_ONTOLOGY_DIR = _ROOT / "ontology"
_UNREVIEWED_DIR = _HERE / "unreviewed"

STATUS_HEADER = "status (pending/accepted/modified/flagged)"
CSV_HEADERS = ["field", "predicted_value", "corrected_value", STATUS_HEADER, "comments"]
DEFAULT_STATUS = "pending"
BLANK_MUSCLE_ROWS = 4

FIELD_ORDER = [
    "entity_id",
    "exercise_name",
    "movement_patterns",
    "primary_joint_actions",
    "supporting_joint_actions",
    "training_modalities",
    "plane_of_motion",
    "exercise_style",
    "laterality",
    "is_compound",
    "is_combination",
]


def _fmt_list(value) -> str:
    if not value:
        return ""
    return ", ".join(str(item) for item in value)


def _fmt_bool(value) -> str:
    if value is None:
        return ""
    return "TRUE" if value else "FALSE"


def _field_predicted_value(field: str, exercise: dict) -> str:
    if field == "entity_id":
        return exercise["entity_id"]
    if field == "exercise_name":
        return exercise["name"]
    value = exercise.get(field)
    if isinstance(value, list):
        return _fmt_list(value)
    if isinstance(value, bool) or value is None:
        return _fmt_bool(value)
    return str(value or "")


def _edge_tokens(exercise: dict) -> list[str]:
    tokens: list[str] = []
    if exercise["source_count"] > 1:
        tokens.append("multi-source")
    if exercise["source_count"] > 2:
        tokens.append("3+ sources")
    if not exercise.get("movement_patterns"):
        tokens.append("no movement pattern")
    if exercise.get("laterality") in {"Contralateral", "Ipsilateral"}:
        tokens.append(f"laterality:{exercise['laterality']}")
    if exercise.get("is_compound") is False:
        tokens.append("isolation")
    if exercise.get("is_combination") is True:
        tokens.append("combination")
    for modality in exercise.get("training_modalities") or []:
        tokens.append(f"modality:{modality}")
    for plane in exercise.get("plane_of_motion") or []:
        if plane != "SagittalPlane":
            tokens.append(f"plane:{plane}")
    return tokens


def _load_candidates(conn) -> list[dict]:
    group_level_map, ancestor_map = load_muscle_maps(_ONTOLOGY_DIR)

    source_map: dict[str, list[tuple[str, str]]] = {}
    for row in conn.execute(
        "SELECT entity_id, source, source_id FROM entity_sources ORDER BY entity_id, source, source_id"
    ):
        source_map.setdefault(row["entity_id"], []).append((row["source"], row["source_id"]))

    stamp_map = {
        row["entity_id"]: {"enriched_at": row["enriched_at"], "model": row["model"]}
        for row in conn.execute("SELECT entity_id, enriched_at, model FROM enrichment_stamps")
    }

    exercises: list[dict] = []
    rows = conn.execute("SELECT entity_id, display_name FROM entities ORDER BY display_name, entity_id").fetchall()
    for row in rows:
        entity_id = row["entity_id"]
        record = effective_prediction_record(
            conn,
            entity_id,
            group_level_map=group_level_map,
            ancestor_map=ancestor_map,
        )
        sources = source_map.get(entity_id, [])
        stamp = stamp_map.get(entity_id, {})
        record.update({
            "name": row["display_name"],
            "entity_id": entity_id,
            "source_count": len(sources),
            "source_summary": ", ".join(sorted({source for source, _ in sources})) or "",
            "source_ids": ", ".join(f"{source}:{source_id}" for source, source_id in sources) or "",
            "enriched_at": stamp.get("enriched_at") or "",
            "model": stamp.get("model") or "",
        })
        record["edge_tokens"] = _edge_tokens(record)
        exercises.append(record)
    return exercises


def _pick_representative_sample(exercises: list[dict], limit: int, seed: int) -> list[dict]:
    if limit >= len(exercises):
        for exercise in exercises:
            exercise["selection_reason"] = "full population"
        return list(exercises)

    token_freq: dict[str, int] = {}
    for exercise in exercises:
        for token in set(exercise["edge_tokens"]):
            token_freq[token] = token_freq.get(token, 0) + 1

    edge_quota = min(limit // 3, 15)
    uncovered = set(token_freq)
    selected_ids: set[str] = set()
    edge_selected: list[dict] = []

    while len(edge_selected) < edge_quota:
        best = None
        best_score = 0.0
        best_tags: list[str] = []

        for exercise in exercises:
            if exercise["entity_id"] in selected_ids:
                continue
            unique_tokens = sorted(set(exercise["edge_tokens"]))
            score = sum(1.0 / token_freq[token] for token in unique_tokens if token in uncovered)
            if score <= 0:
                continue
            tags = sorted(unique_tokens, key=lambda token: (token_freq[token], token))
            tie_break = (exercise["source_count"], exercise["enriched_at"], exercise["name"])
            if score > best_score or (
                score == best_score
                and best is not None
                and tie_break > (best["source_count"], best["enriched_at"], best["name"])
            ):
                best = exercise
                best_score = score
                best_tags = tags

        if best is None:
            break

        selected_ids.add(best["entity_id"])
        uncovered.difference_update(best["edge_tokens"])
        best["selection_reason"] = f"coverage: {', '.join(best_tags[:3])}"
        edge_selected.append(best)

    remaining = [exercise for exercise in exercises if exercise["entity_id"] not in selected_ids]
    rng = random.Random(seed)
    rng.shuffle(remaining)
    fill = remaining[: max(0, limit - len(edge_selected))]
    for exercise in fill:
        exercise["selection_reason"] = f"representative random (seed={seed})"

    sample = edge_selected + fill
    return sorted(sample, key=lambda exercise: (exercise["name"].lower(), exercise["entity_id"]))


def _select_exercises(conn, *, limit: int, seed: int, entity_ids: list[str]) -> list[dict]:
    exercises = _load_candidates(conn)
    by_id = {exercise["entity_id"]: exercise for exercise in exercises}

    if entity_ids:
        missing = [entity_id for entity_id in entity_ids if entity_id not in by_id]
        if missing:
            raise SystemExit(f"Unknown entity_id(s): {', '.join(missing[:10])}")
        selected = [by_id[entity_id] for entity_id in entity_ids]
        for exercise in selected:
            exercise["selection_reason"] = "explicit entity_id"
        return selected

    return _pick_representative_sample(exercises, limit=limit, seed=seed)


def _slugify_filename(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "exercise"


def _unique_file_name(output_dir: Path, entity_id: str, exercise_name: str) -> Path:
    short_hash = hashlib.sha1(entity_id.encode("utf-8")).hexdigest()[:8]
    base = f"{_slugify_filename(exercise_name)}__{short_hash}"
    path = output_dir / f"{base}.csv"
    n = 2
    while path.exists():
        path = output_dir / f"{base}_{n}.csv"
        n += 1
    return path


def _build_rows(exercise: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for field in FIELD_ORDER:
        comments = ""
        if field == "exercise_name":
            comments = exercise.get("selection_reason", "")
        rows.append({
            "field": field,
            "predicted_value": _field_predicted_value(field, exercise),
            "corrected_value": "",
            STATUS_HEADER: DEFAULT_STATUS,
            "comments": comments,
        })

    involvements = exercise.get("muscle_involvements") or []
    total_slots = len(involvements) + BLANK_MUSCLE_ROWS
    for idx in range(total_slots):
        involvement = involvements[idx] if idx < len(involvements) else {"muscle": "", "degree": ""}
        prefix = f"muscle_involvement_{idx + 1:02d}"
        rows.append({
            "field": f"{prefix}_muscle",
            "predicted_value": involvement.get("muscle", ""),
            "corrected_value": "",
            STATUS_HEADER: DEFAULT_STATUS,
            "comments": "",
        })
        rows.append({
            "field": f"{prefix}_involvementdegree",
            "predicted_value": involvement.get("degree", ""),
            "corrected_value": "",
            STATUS_HEADER: DEFAULT_STATUS,
            "comments": "",
        })

    return rows


def _write_exercise_csv(path: Path, exercise: dict) -> None:
    rows = _build_rows(exercise)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-exercise gold review CSVs")
    parser.add_argument("--output-dir", default=str(_UNREVIEWED_DIR), help="Directory to write per-exercise CSVs into")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to pipeline.db")
    parser.add_argument("--limit", type=int, default=50, help="Representative sample size when no explicit IDs are given")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic seed for representative sampling")
    parser.add_argument("--entity-id", action="append", default=[], help="Explicit canonical entity_id to include; may be repeated")
    args = parser.parse_args()

    conn = get_connection(Path(args.db))
    exercises = _select_exercises(conn, limit=args.limit, seed=args.seed, entity_ids=args.entity_id)
    conn.close()

    if not exercises:
        raise SystemExit("No exercises selected for CSV generation.")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for file in out_dir.glob("*.csv"):
        if file.name != ".gitkeep":
            file.unlink()

    for exercise in exercises:
        out = _unique_file_name(out_dir, exercise["entity_id"], exercise["name"])
        _write_exercise_csv(out, exercise)
        print(f"Wrote 1 exercise → {out}")


if __name__ == "__main__":
    main()
