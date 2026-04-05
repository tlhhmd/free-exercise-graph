"""
Score current pipeline predictions against submitted per-exercise gold CSVs.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.db import DB_PATH, get_connection
from pipeline.effective_claims import effective_prediction_record, load_muscle_maps

_ONTOLOGY_DIR = _ROOT / "ontology"
_SUBMITTED_DIR = _ROOT / "evals" / "submitted"
_SCORED_DIR = _ROOT / "evals" / "scored"
STATUS_HEADER = "status (pending/accepted/modified/flagged)"

FIELD_SPECS = [
    ("movement_patterns", "Movement Patterns", "set"),
    ("primary_joint_actions", "Primary Joint Actions", "set"),
    ("supporting_joint_actions", "Supporting Joint Actions", "set"),
    ("training_modalities", "Training Modalities", "set"),
    ("plane_of_motion", "Plane Of Motion", "set"),
    ("exercise_style", "Exercise Style", "set"),
    ("laterality", "Laterality", "scalar"),
    ("is_compound", "Is Compound", "bool"),
    ("is_combination", "Is Combination", "bool"),
]

FIELD_KIND = {key: kind for key, _, kind in FIELD_SPECS}
FIELD_NAME_ALIASES = {
    "movement_pattern": "movement_patterns",
    "movement_patterns": "movement_patterns",
    "primary_joint_action": "primary_joint_actions",
    "primary_joint_actions": "primary_joint_actions",
    "supporting_joint_action": "supporting_joint_actions",
    "supporting_joint_actions": "supporting_joint_actions",
    "training_modality": "training_modalities",
    "training_modalities": "training_modalities",
    "plane_of_motion": "plane_of_motion",
    "exercise_style": "exercise_style",
    "laterality": "laterality",
    "is_compound": "is_compound",
    "is_combination": "is_combination",
    "muscle": "muscle",
}

ACTIVE_FIELD_STATUSES = {"accepted", "modified"}
ACTIVE_REVIEW_STATUSES = {"accepted", "modified", "flagged"}
MUSCLE_FIELD_RE = re.compile(r"^muscle_involvement_(\d+)_(muscle|involvementdegree)$")


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def set_f1(pred: set[str], gold: set[str]) -> dict[str, float]:
    return _prf(len(pred & gold), len(pred - gold), len(gold - pred))


def muscle_scores(pred_involvements: list[dict], gold_involvements: list[dict]) -> dict[str, Any]:
    pred_pairs = {(item["muscle"], item["degree"]) for item in pred_involvements}
    gold_pairs = {(item["muscle"], item["degree"]) for item in gold_involvements}
    pred_names = {item["muscle"] for item in pred_involvements}
    gold_names = {item["muscle"] for item in gold_involvements}

    strict = set_f1(pred_pairs, gold_pairs)
    muscle = set_f1(pred_names, gold_names)

    shared = pred_names & gold_names
    degree_correct = 0
    degree_total = 0
    if shared:
        gold_degree = {item["muscle"]: item["degree"] for item in gold_involvements}
        pred_degree = {item["muscle"]: item["degree"] for item in pred_involvements}
        for muscle_name in shared:
            degree_total += 1
            if pred_degree.get(muscle_name) == gold_degree.get(muscle_name):
                degree_correct += 1

    return {
        "strict_f1": strict["f1"],
        "strict_precision": strict["precision"],
        "strict_recall": strict["recall"],
        "muscle_f1": muscle["f1"],
        "muscle_precision": muscle["precision"],
        "muscle_recall": muscle["recall"],
        "degree_acc": degree_correct / degree_total if degree_total else None,
        "degree_correct": degree_correct,
        "degree_total": degree_total,
    }


def _parse_csv_cell(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _bool_cell(value: str | None) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"TRUE", "YES", "1"}:
        return True
    if text in {"FALSE", "NO", "0"}:
        return False
    return None


def _field_value(raw_value, kind: str):
    if kind == "set":
        return _parse_csv_cell(raw_value)
    if kind == "bool":
        return _bool_cell(raw_value)
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    return text or None


def load_gold_csv(csv_path: Path) -> dict[str, dict]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    entity_id = None
    record: dict[str, Any] = {}
    muscle_slots: dict[str, dict[str, dict[str, str]]] = {}

    for row in rows:
        field = str(row.get("field") or "").strip()
        predicted = str(row.get("predicted_value") or "").strip()
        corrected = str(row.get("corrected_value") or "").strip()
        status = str(row.get(STATUS_HEADER) or row.get("status") or "pending").strip().lower()

        if field == "entity_id" and predicted:
            entity_id = predicted
            continue

        if field == "exercise_name":
            continue

        muscle_match = MUSCLE_FIELD_RE.match(field)
        if muscle_match:
            slot, part = muscle_match.groups()
            muscle_slots.setdefault(slot, {})[part] = {
                "predicted": predicted,
                "corrected": corrected,
                "status": status,
            }
            continue

        if field not in FIELD_KIND:
            continue
        if status not in ACTIVE_FIELD_STATUSES:
            continue

        chosen = predicted if status == "accepted" else corrected
        if not chosen:
            continue
        parsed = _field_value(chosen, FIELD_KIND[field])
        if parsed is not None:
            record[field] = parsed

    if not entity_id:
        return {}

    involvements: list[dict[str, str]] = []
    for slot in sorted(muscle_slots, key=int):
        muscle_row = muscle_slots[slot].get("muscle")
        degree_row = muscle_slots[slot].get("involvementdegree")
        if not muscle_row or not degree_row:
            continue

        muscle_status = muscle_row["status"]
        degree_status = degree_row["status"]
        if muscle_status not in ACTIVE_FIELD_STATUSES or degree_status not in ACTIVE_FIELD_STATUSES:
            continue

        muscle = (
            muscle_row["predicted"]
            if muscle_status == "accepted"
            else muscle_row["corrected"]
        ).strip()
        degree = (
            degree_row["predicted"]
            if degree_status == "accepted"
            else degree_row["corrected"]
        ).strip()

        if not muscle or not degree:
            continue
        involvements.append({"muscle": muscle, "degree": degree})

    if involvements:
        record["muscle_involvements"] = involvements

    if not record:
        return {}
    return {entity_id: {"id": entity_id, **record}}


def _gold_sources(path: Path) -> list[Path]:
    if not path.exists():
        raise SystemExit(f"Gold path not found: {path}")
    if path.is_file():
        return [path]
    files = sorted(
        file for file in path.glob("*.csv")
        if file.is_file() and file.name != ".gitkeep"
    )
    if not files:
        raise SystemExit(f"No .csv review files found in {path}")
    return files


def load_gold(path: Path) -> tuple[dict[str, dict], list[Path]]:
    files = _gold_sources(path)
    merged: dict[str, dict] = {}
    for file in files:
        gold = load_gold_csv(file)
        for entity_id, record in gold.items():
            if entity_id in merged:
                raise SystemExit(
                    f"Duplicate reviewed entity_id across submitted files: {entity_id} "
                    f"(at least one duplicate in {file})"
                )
            merged[entity_id] = record
    return merged, files


def load_predictions(exercise_ids: list[str], db_path: Path = DB_PATH) -> dict[str, dict]:
    conn = get_connection(db_path)
    group_level_map, ancestor_map = load_muscle_maps(_ONTOLOGY_DIR)
    preds: dict[str, dict] = {}
    for entity_id in exercise_ids:
        preds[entity_id] = effective_prediction_record(
            conn,
            entity_id,
            group_level_map=group_level_map,
            ancestor_map=ancestor_map,
        )
    conn.close()
    return preds


def score_exercise(pred: dict, gold: dict) -> dict[str, Any]:
    result: dict[str, Any] = {"id": gold["id"]}

    for key, _, kind in FIELD_SPECS:
        if key not in gold:
            result[key] = None
            continue
        if kind == "set":
            result[key] = set_f1(set(pred.get(key) or []), set(gold.get(key) or []))
        else:
            result[key] = int(pred.get(key) == gold.get(key))

    if "muscle_involvements" in gold:
        result["muscle"] = muscle_scores(
            pred.get("muscle_involvements") or [],
            gold.get("muscle_involvements") or [],
        )
    else:
        result["muscle"] = None

    return result


def aggregate(per_exercise: list[dict]) -> dict[str, Any]:
    def _macro_f1(field: str) -> dict[str, float]:
        metrics = [exercise[field] for exercise in per_exercise if isinstance(exercise.get(field), dict)]
        if not metrics:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "n": 0}
        return {
            "precision": sum(metric["precision"] for metric in metrics) / len(metrics),
            "recall": sum(metric["recall"] for metric in metrics) / len(metrics),
            "f1": sum(metric["f1"] for metric in metrics) / len(metrics),
            "n": len(metrics),
        }

    def _accuracy(field: str) -> dict[str, float]:
        values = [exercise[field] for exercise in per_exercise if exercise.get(field) is not None]
        if not values:
            return {"accuracy": 0.0, "n": 0}
        return {"accuracy": sum(values) / len(values), "n": len(values)}

    agg: dict[str, Any] = {"n": len(per_exercise)}
    for key, _, kind in FIELD_SPECS:
        agg[key] = _macro_f1(key) if kind == "set" else _accuracy(key)

    muscle_metrics = [exercise["muscle"] for exercise in per_exercise if exercise.get("muscle")]
    if muscle_metrics:
        counted = [metric for metric in muscle_metrics if metric["degree_acc"] is not None]
        agg["muscle"] = {
            "strict_f1": sum(metric["strict_f1"] for metric in muscle_metrics) / len(muscle_metrics),
            "strict_precision": sum(metric["strict_precision"] for metric in muscle_metrics) / len(muscle_metrics),
            "strict_recall": sum(metric["strict_recall"] for metric in muscle_metrics) / len(muscle_metrics),
            "muscle_f1": sum(metric["muscle_f1"] for metric in muscle_metrics) / len(muscle_metrics),
            "muscle_precision": sum(metric["muscle_precision"] for metric in muscle_metrics) / len(muscle_metrics),
            "muscle_recall": sum(metric["muscle_recall"] for metric in muscle_metrics) / len(muscle_metrics),
            "degree_acc": sum(metric["degree_acc"] for metric in counted) / len(counted) if counted else None,
            "n": len(muscle_metrics),
        }
    else:
        agg["muscle"] = {
            "strict_f1": 0.0,
            "strict_precision": 0.0,
            "strict_recall": 0.0,
            "muscle_f1": 0.0,
            "muscle_precision": 0.0,
            "muscle_recall": 0.0,
            "degree_acc": None,
            "n": 0,
        }

    return agg


def _pct(value: float | None) -> str:
    if value is None:
        return "  —  "
    return f"{value * 100:.1f}%"


def _selected_fields(field_arg: str | None) -> list[str]:
    if not field_arg:
        return [key for key, _, _ in FIELD_SPECS] + ["muscle"]
    normalized = FIELD_NAME_ALIASES.get(field_arg)
    if not normalized:
        raise SystemExit(f"Unknown field: {field_arg}")
    return [normalized]


def print_report(agg: dict, per_exercise: list[dict], *, selected_fields: list[str], verbose: bool = False) -> None:
    print(f"\nEval Report — {agg['n']} exercise(s) with at least one scored field")
    print("─" * 78)

    set_labels = {key: label for key, label, kind in FIELD_SPECS if kind == "set"}
    scalar_labels = {key: label for key, label, kind in FIELD_SPECS if kind != "set"}

    if any(field in selected_fields for field in set_labels):
        print(f"{'Field':<28} {'P':>7} {'R':>7} {'F1':>7} {'n':>5}")
        print("─" * 78)
        for key, label in set_labels.items():
            if key not in selected_fields:
                continue
            metric = agg[key]
            print(f"{label:<28} {_pct(metric['precision'])} {_pct(metric['recall'])} {_pct(metric['f1'])} {metric['n']:>5}")
        print()

    if "muscle" in selected_fields:
        metric = agg["muscle"]
        print(f"{'Muscle (strict, w/ degree)':<28} {_pct(metric['strict_precision'])} {_pct(metric['strict_recall'])} {_pct(metric['strict_f1'])} {metric['n']:>5}")
        print(f"{'Muscle (name only)':<28} {_pct(metric['muscle_precision'])} {_pct(metric['muscle_recall'])} {_pct(metric['muscle_f1'])} {metric['n']:>5}")
        print(f"{'Degree accuracy (cond.)':<28}                   {_pct(metric['degree_acc'])} {metric['n']:>5}")
        print()

    scalar_fields = [field for field in scalar_labels if field in selected_fields]
    if scalar_fields:
        print(f"{'Field':<28} {'Accuracy':>12} {'n':>5}")
        print("─" * 78)
        for key in scalar_fields:
            metric = agg[key]
            print(f"{scalar_labels[key]:<28} {_pct(metric['accuracy']):>12} {metric['n']:>5}")
        print("─" * 78)

    if verbose:
        print("\nPer-exercise breakdown:")
        for exercise in per_exercise:
            print(f"  {exercise['id']}")
            for key in selected_fields:
                if key == "muscle":
                    metric = exercise.get("muscle")
                    if metric:
                        print(
                            f"    muscle_strict={_pct(metric['strict_f1'])} "
                            f"muscle_name={_pct(metric['muscle_f1'])} "
                            f"degree_acc={_pct(metric['degree_acc'])}"
                        )
                    continue
                metric = exercise.get(key)
                if isinstance(metric, dict):
                    print(f"    {key} f1={_pct(metric['f1'])}")
                elif metric is not None:
                    print(f"    {key} accuracy={_pct(metric)}")


def archive_scored_files(files: list[Path], destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        target = destination_dir / file.name
        if target.exists():
            raise SystemExit(f"Cannot archive scored file; destination already exists: {target}")
        file.rename(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score pipeline predictions against submitted gold CSVs")
    parser.add_argument("--gold", default=str(_SUBMITTED_DIR), help="Reviewed CSV file or directory of submitted CSVs")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to pipeline.db")
    parser.add_argument("--archive-scored", action="store_true", help="Move successfully scored submitted CSVs into evals/scored")
    parser.add_argument("--scored-dir", default=str(_SCORED_DIR), help="Destination directory for archived scored CSVs")
    parser.add_argument("--field", help="Score only one field")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-exercise breakdown")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        sys.exit(f"pipeline.db not found: {db_path}")

    selected_fields = _selected_fields(args.field)
    gold_path = Path(args.gold)
    print(f"Loading gold standard from {gold_path}...")
    gold, source_files = load_gold(gold_path)
    if not gold:
        sys.exit("No reviewed exercises found (all rows Pending, or no valid corrected rows).")
    print(f"  {len(gold)} reviewed exercise(s) loaded from {len(source_files)} file(s).")

    print(f"Loading predictions from {db_path}...")
    preds = load_predictions(list(gold.keys()), db_path)

    missing = [entity_id for entity_id in gold if entity_id not in preds]
    if missing:
        print(f"  Warning: {len(missing)} exercise(s) in gold have no current prediction: {missing[:5]}")

    per_exercise = []
    for entity_id, gold_record in gold.items():
        pred = preds.get(entity_id, {"id": entity_id})
        scored = score_exercise(pred, gold_record)
        if any(scored.get(field) is not None for field in selected_fields):
            per_exercise.append(scored)

    if not per_exercise:
        sys.exit("No scored fields found in the reviewed CSV files.")

    agg = aggregate(per_exercise)
    print_report(agg, per_exercise, selected_fields=selected_fields, verbose=args.verbose)

    if args.archive_scored:
        archive_scored_files(source_files, Path(args.scored_dir))
        print(f"\nArchived {len(source_files)} scored file(s) to {args.scored_dir}")


if __name__ == "__main__":
    main()
