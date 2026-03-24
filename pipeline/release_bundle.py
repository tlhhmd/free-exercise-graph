#!/usr/bin/env python3
"""
pipeline/release_bundle.py

Freeze the current local pipeline state into a timestamped release bundle.

Bundle contents:
  - pipeline.db snapshot
  - exported enrichment JSONL (if any)
  - graph.ttl copy (if present)
  - machine-readable quality scorecard
  - metadata.json with row counts and file pointers
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.artifacts import RELEASES_DIR, make_timestamped_dir, write_json
from pipeline.db import DB_PATH, get_connection, table_exists
from pipeline.db_backup import backup_db
from pipeline.export_enrichment import export_enrichment
from pipeline.validate import run_scorecard

GRAPH_PATH = PROJECT_ROOT / "graph.ttl"


def _table_count(conn, table: str) -> int | None:
    if not table_exists(conn, table):
        return None
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def create_bundle(
    *,
    db_path: Path = DB_PATH,
    graph_path: Path = GRAPH_PATH,
    output_dir: Path | None = None,
) -> Path:
    bundle_dir = output_dir or make_timestamped_dir(RELEASES_DIR, "release-bundle")
    bundle_dir.mkdir(parents=True, exist_ok=True)

    db_snapshot = bundle_dir / "pipeline.db"
    backup_db(db_path=db_path, dest=db_snapshot)

    export_path = None
    with get_connection(db_path) as conn:
        if table_exists(conn, "enrichment_stamps"):
            stamp_count = conn.execute("SELECT COUNT(*) FROM enrichment_stamps").fetchone()[0]
        else:
            stamp_count = 0
    if stamp_count:
        export_path, export_count = export_enrichment(
            db_path=db_path,
            output=bundle_dir / "enrichment.jsonl",
        )
    else:
        export_count = 0

    graph_copy = None
    if graph_path.exists():
        graph_copy = bundle_dir / graph_path.name
        shutil.copy2(graph_path, graph_copy)

    scorecard = run_scorecard(graph_path=graph_path, db_path=db_path, run_shacl=False)
    scorecard_path = bundle_dir / "quality_scorecard.json"
    write_json(
        scorecard_path,
        [
            {
                "dimension": result.name,
                "status": result.status,
                "summary": result.summary,
                "detail": result.detail,
            }
            for result in scorecard
        ],
    )

    with get_connection(db_path) as conn:
        metadata = {
            "db_path": str(db_path),
            "graph_path": str(graph_path),
            "db_counts": {
                table: _table_count(conn, table)
                for table in (
                    "source_records",
                    "entities",
                    "resolved_claims",
                    "inferred_claims",
                    "enrichment_stamps",
                    "enrichment_warnings",
                    "enrichment_failures",
                )
            },
            "bundle_files": {
                "pipeline_db": db_snapshot.name,
                "graph_ttl": graph_copy.name if graph_copy else None,
                "enrichment_jsonl": export_path.name if export_path else None,
                "quality_scorecard": scorecard_path.name,
            },
            "enrichment_export_count": export_count,
        }
    write_json(bundle_dir / "metadata.json", metadata)
    return bundle_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a release bundle for the current local pipeline state")
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--graph", type=Path, default=GRAPH_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    bundle_dir = create_bundle(db_path=args.db_path, graph_path=args.graph, output_dir=args.output_dir)
    print(f"Created release bundle: {bundle_dir}")


if __name__ == "__main__":
    main()
