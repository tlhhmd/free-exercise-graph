#!/usr/bin/env python3
"""
pipeline/run.py

Canonical pipeline runner for local development, onboarding, and CI.

By default this rebuilds the deterministic pipeline stages through `build`
without calling the LLM. Add `--with-enrich` when you intentionally want to
spend tokens on enrichment.

Examples:
    python3 pipeline/run.py
    python3 pipeline/run.py --reset-db --yes-reset-db
    python3 pipeline/run.py --to validate
    python3 pipeline/run.py --with-enrich --to build --limit 25
    python3 pipeline/run.py --from reconcile --to validate
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import build as build_stage
from pipeline import canonicalize, enrich as enrich_stage, identity, reconcile
from pipeline.db import DB_PATH, entity_ids_with_llm_state, get_connection, reset_db
from pipeline.db_backup import backup_db
from pipeline.export_enrichment import export_enrichment
from pipeline.release_bundle import create_bundle

STAGES = ("canonicalize", "identity", "reconcile", "enrich", "build", "validate", "shacl")


def _selected_stages(stage_from: str, stage_to: str, with_enrich: bool) -> list[str]:
    start = STAGES.index(stage_from)
    end = STAGES.index(stage_to)
    if start > end:
        raise SystemExit(f"--from {stage_from} must come before --to {stage_to}")
    selected = list(STAGES[start : end + 1])
    if "enrich" in selected and not with_enrich:
        selected.remove("enrich")
    return selected


def _run_validate(*, with_shacl: bool, db_path: Path) -> None:
    cmd = [sys.executable, str(PROJECT_ROOT / "pipeline" / "validate.py")]
    cmd.extend(["--db-path", str(db_path)])
    if with_shacl:
        cmd.append("--shacl")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def _run_shacl() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "test_shacl.py")],
        cwd=PROJECT_ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical FEG pipeline runner")
    parser.add_argument("--from", dest="stage_from", choices=STAGES, default="canonicalize")
    parser.add_argument("--to", dest="stage_to", choices=STAGES, default="build")
    parser.add_argument(
        "--with-enrich",
        action="store_true",
        help="Include the LLM enrichment stage (costs API tokens)",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete pipeline.db and rebuild deterministic state from source truth",
    )
    parser.add_argument(
        "--yes-reset-db",
        action="store_true",
        help="Acknowledge that --reset-db will discard persisted LLM enrichment state",
    )
    parser.add_argument(
        "--no-backup-before-reset",
        action="store_true",
        help="Skip the automatic SQLite backup that normally runs before --reset-db",
    )
    parser.add_argument("--source", choices=list(canonicalize._SOURCES.keys()))
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--limit", type=int, default=None, help="Limit entities for enrichment")
    parser.add_argument("--concurrency", type=int, default=1, help="LLM concurrency for enrich stage")
    parser.add_argument("--force", nargs="+", metavar="ENTITY_ID", help="Force re-enrichment of specific entity IDs")
    parser.add_argument("--dump-prompts", type=Path, default=None, metavar="DIR")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--thinking", default=None, metavar="LEVEL")
    parser.add_argument("--dry-run-enrich", action="store_true")
    parser.add_argument(
        "--no-export-after-enrich",
        action="store_true",
        help="Skip the automatic JSONL export written after a successful enrich stage",
    )
    parser.add_argument(
        "--bundle-after-build",
        action="store_true",
        help="Create a timestamped release bundle after build/validate completes",
    )
    parser.add_argument(
        "--drop-enrichment",
        action="store_true",
        help="Allow identity rebuilds that discard persisted enrichment state for removed entity IDs",
    )
    parser.add_argument(
        "--validate-shacl",
        action="store_true",
        help="Run full SHACL inside pipeline/validate.py when validate is selected",
    )
    args = parser.parse_args()

    selected = _selected_stages(args.stage_from, args.stage_to, args.with_enrich)
    if args.reset_db:
        protected_ids: set[str] = set()
        if args.db_path.exists():
            with get_connection(args.db_path) as conn:
                protected_ids = entity_ids_with_llm_state(conn)
            if protected_ids and not args.yes_reset_db:
                raise SystemExit(
                    "--reset-db would discard persisted LLM enrichment state. "
                    "Re-run with --yes-reset-db to confirm."
                )
            if not args.no_backup_before_reset:
                backup_path = backup_db(db_path=args.db_path)
                print(f"Automatic backup before reset: {backup_path}")
        print("Resetting pipeline database...")
        reset_db(args.db_path)

    for stage in selected:
        print(f"\n== {stage} ==")
        if stage == "canonicalize":
            sources = [args.source] if args.source else list(canonicalize._SOURCES.keys())
            canonicalize.run(sources, db_path=args.db_path)
        elif stage == "identity":
            stats = identity.run(db_path=args.db_path, dry_run=False, drop_enrichment=args.drop_enrichment)
            print(f"Entities:  {stats['entities']}")
            print(f"Merged:    {stats['merged']}")
            print(f"Triage:    {stats['triage']}")
        elif stage == "reconcile":
            stats = reconcile.run(db_path=args.db_path)
            print(f"Resolved claims: {stats['resolved_claims']}")
            print(f"Conflicts:       {stats['conflicts']}")
            print(f"Deferred:        {stats['deferred']}")
        elif stage == "enrich":
            enrich_stage.run(
                limit=args.limit,
                concurrency=args.concurrency,
                force=args.force,
                dump_prompts_dir=args.dump_prompts,
                dry_run=args.dry_run_enrich,
                provider=args.provider,
                model=args.model,
                thinking_level=args.thinking,
                db_path=args.db_path,
            )
            if not args.dry_run_enrich and not args.no_export_after_enrich:
                export_path, export_count = export_enrichment(db_path=args.db_path)
                print(f"Exported enrichment snapshot: {export_path} ({export_count} entities)")
        elif stage == "build":
            build_stage.build(db_path=args.db_path)
        elif stage == "validate":
            _run_validate(with_shacl=args.validate_shacl, db_path=args.db_path)
        elif stage == "shacl":
            _run_shacl()

    if args.bundle_after_build and any(stage in selected for stage in ("build", "validate")):
        bundle_dir = create_bundle(db_path=args.db_path)
        print(f"Created release bundle: {bundle_dir}")


if __name__ == "__main__":
    main()
