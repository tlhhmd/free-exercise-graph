#!/usr/bin/env python3
"""
preprocess.py — Normalise raw exercise data using crosswalk CSVs.

Usage:
    python3 sources/free-exercise-db/preprocess.py

Reads exercises.json and muscle_crosswalk.csv, replaces primaryMuscles and
secondaryMuscles source strings with their feg_local_name equivalents, and
writes exercises_normalized.json (gitignored). Run before ingest.py.

Business logic (source string → feg_local_name mappings) lives in the
crosswalk CSVs — this script applies them generically.
"""

import csv
import json
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
EXERCISES_JSON = SOURCE_DIR / "raw" / "exercises.json"
EXERCISES_NORMALIZED_JSON = SOURCE_DIR / "raw" / "exercises_normalized.json"
MUSCLE_CROSSWALK_CSV = SOURCE_DIR / "mappings" / "muscle_crosswalk.csv"


def load_crosswalk(path: Path) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8") as f:
        return {row["source_string"]: row["feg_local_name"] for row in csv.DictReader(f)}


def main():
    crosswalk = load_crosswalk(MUSCLE_CROSSWALK_CSV)

    with open(EXERCISES_JSON, encoding="utf-8") as f:
        exercises = json.load(f)

    for ex in exercises:
        ex["primaryMuscles"] = [crosswalk.get(m, m) for m in ex.get("primaryMuscles", [])]
        ex["secondaryMuscles"] = [crosswalk.get(m, m) for m in ex.get("secondaryMuscles", [])]
        ex["sanitized_id"] = ex["id"].replace("-", "_")

    with open(EXERCISES_NORMALIZED_JSON, "w", encoding="utf-8") as f:
        json.dump(exercises, f)

    print(f"Normalised {len(exercises)} exercises → {EXERCISES_NORMALIZED_JSON.name}")


if __name__ == "__main__":
    main()
