#!/usr/bin/env python3
"""
run_pipeline.py — End-to-end pipeline runner (build + validate) with telemetry.

Skips enrichment. Runs build then validate in-process and emits a combined
JSON run report to runs/<timestamp>_pipeline.json.

Usage:
    python3 sources/free-exercise-db/run_pipeline.py
    python3 sources/free-exercise-db/run_pipeline.py --skip-validate
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure this file's directory is on the path so sibling imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build
import validate
from telemetry import RUNS_DIR


def _merge_reports(build_path: Path, validate_path: Path) -> Path:
    """Merge two phase run reports into a single combined report."""
    bld = json.loads(build_path.read_text())
    val = json.loads(validate_path.read_text())

    combined = {
        "run_id": bld["run_id"],
        "pipeline": "build+validate",
        "git_sha": bld["git_sha"],
        "total_wall_s": round(bld["total_wall_s"] + val["total_wall_s"], 3),
        "total_cpu_s": round(bld["total_cpu_s"] + val["total_cpu_s"], 3),
        "phases": {
            "build": {
                "total_wall_s": bld["total_wall_s"],
                "total_cpu_s": bld["total_cpu_s"],
                "steps": bld["steps"],
            },
            "validate": {
                "total_wall_s": val["total_wall_s"],
                "total_cpu_s": val["total_cpu_s"],
                "steps": val["steps"],
            },
        },
    }

    out_path = RUNS_DIR / f"{bld['run_id']}_pipeline.json"
    out_path.write_text(json.dumps(combined, indent=2))

    build_path.unlink(missing_ok=True)
    validate_path.unlink(missing_ok=True)

    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Run build + validate end-to-end with telemetry."
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Run build only, skip validation.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Quality report CSV path (passed through to validate).",
    )
    args = parser.parse_args()

    # ── Build ──────────────────────────────────────────────────────────────────
    build_report = build.main()

    if args.skip_validate:
        print(f"\nPipeline report: {build_report}")
        return

    # ── Validate ───────────────────────────────────────────────────────────────
    # Patch sys.argv so validate's argparse sees the right flags
    _orig_argv = sys.argv
    sys.argv = [validate.__file__]
    if args.csv:
        sys.argv += ["--csv", args.csv]
    try:
        validate_report, has_violations = validate.main()
    finally:
        sys.argv = _orig_argv

    # ── Combined report ────────────────────────────────────────────────────────
    combined = _merge_reports(build_report, validate_report)
    print(f"\nCombined pipeline report: {combined}")

    sys.exit(1 if has_violations else 0)


if __name__ == "__main__":
    main()
