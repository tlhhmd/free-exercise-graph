"""
enrich.py — free-exercise-db enrichment adapter

Source-specific concerns:
  - Reading exercises.json
  - Formatting user messages from yuhonas/free-exercise-db exercise objects

Usage:
    python3 sources/free-exercise-db/enrich.py
    python3 sources/free-exercise-db/enrich.py --limit 10
    python3 sources/free-exercise-db/enrich.py --concurrency 4
    python3 sources/free-exercise-db/enrich.py --model claude-haiku-4-5-20251001
    python3 sources/free-exercise-db/enrich.py --force Barbell_Deadlift Plank
    python3 sources/free-exercise-db/enrich.py --retry-quarantine
    python3 sources/free-exercise-db/enrich.py --reparse-quarantine
    python3 sources/free-exercise-db/enrich.py --dump-prompts /tmp/prompts
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from enrichment.service import DEFAULT_MODEL, reparse_quarantine, run_enrichment

# ─── Paths ────────────────────────────────────────────────────────────────────

_EXERCISES  = _HERE / "raw" / "exercises.json"
_ENRICHED   = _HERE / "enriched"
_QUARANTINE = _HERE / "quarantine"
_LOG        = _HERE / "enrich.log"


# ─── Source-specific functions ────────────────────────────────────────────────


def format_user_message(exercise: dict) -> str:
    lines = [f"Name: {exercise['name']}"]
    if instructions := exercise.get("instructions"):
        lines.append(f"Instructions: {' '.join(instructions)}")
    primary = exercise.get("primaryMuscles", [])
    secondary = exercise.get("secondaryMuscles", [])
    if primary or secondary:
        lines.append(
            f"Source muscles - primary: {', '.join(primary) or 'none'}"
            f" | secondary: {', '.join(secondary) or 'none'}"
        )
    return "\n".join(lines)


def make_record(exercise: dict, fields: dict, vocab_versions: dict) -> dict:
    return {**exercise, **fields, "vocabulary_versions": vocab_versions}


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich free-exercise-db exercises with LLM classifications."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--exercises-file", type=Path, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--force", nargs="+", metavar="EXERCISE_ID")
    parser.add_argument("--retry-quarantine", action="store_true")
    parser.add_argument("--reparse-quarantine", action="store_true")
    parser.add_argument("--dump-prompts", type=Path, default=None, metavar="DIR")
    args = parser.parse_args()

    if args.reparse_quarantine:
        reparse_quarantine(_QUARANTINE, _ENRICHED, make_record)
        return

    exercises_path = args.exercises_file or _EXERCISES
    exercises: list[dict] = json.loads(exercises_path.read_text())

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
