#!/usr/bin/env python3
"""
pipeline/export_enrichment.py

Export persisted enrichment state into a portable JSONL artifact.

Usage:
    python3 pipeline/export_enrichment.py
    python3 pipeline/export_enrichment.py --output pipeline/exports/my-run.jsonl
    python3 pipeline/export_enrichment.py --db-path /tmp/pipeline.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.artifacts import EXPORTS_DIR, ensure_dir, utc_timestamp
from pipeline.db import DB_PATH, get_connection, table_exists


def default_output_path() -> Path:
    ensure_dir(EXPORTS_DIR)
    return EXPORTS_DIR / f"enrichment-{utc_timestamp()}.jsonl"


def _load_by_entity(conn, table: str, sql: str) -> dict[str, list[dict]]:
    if not table_exists(conn, table):
        return {}
    grouped: dict[str, list[dict]] = {}
    for row in conn.execute(sql).fetchall():
        payload = dict(row)
        entity_id = payload.pop("entity_id")
        grouped.setdefault(entity_id, []).append(payload)
    return grouped


def export_enrichment(*, db_path: Path = DB_PATH, output: Path | None = None) -> tuple[Path, int]:
    conn = get_connection(db_path)
    if not table_exists(conn, "enrichment_stamps"):
        conn.close()
        raise SystemExit(f"SQLite DB at {db_path} does not contain enrichment tables yet")

    stamps = conn.execute(
        """
        SELECT es.entity_id, e.display_name, es.versions_json, es.enriched_at, es.model
        FROM enrichment_stamps es
        JOIN entities e ON e.entity_id = es.entity_id
        ORDER BY es.entity_id
        """
    ).fetchall()

    claims_by_entity = _load_by_entity(
        conn,
        "inferred_claims",
        """
        SELECT entity_id, predicate, value, qualifier
        FROM inferred_claims
        ORDER BY entity_id, predicate, value, qualifier
        """,
    )
    warnings_by_entity = _load_by_entity(
        conn,
        "enrichment_warnings",
        """
        SELECT entity_id, predicate, stripped_value, enriched_at
        FROM enrichment_warnings
        ORDER BY entity_id, predicate, stripped_value
        """,
    )
    failures_by_entity = _load_by_entity(
        conn,
        "enrichment_failures",
        """
        SELECT entity_id, failed_at, error
        FROM enrichment_failures
        ORDER BY entity_id, failed_at
        """,
    )
    conn.close()

    output_path = output or default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in stamps:
            entity_id = row["entity_id"]
            payload = {
                "entity_id": entity_id,
                "display_name": row["display_name"],
                "stamp": {
                    "versions_json": json.loads(row["versions_json"]),
                    "enriched_at": row["enriched_at"],
                    "model": row["model"],
                },
                "claims": claims_by_entity.get(entity_id, []),
                "warnings": warnings_by_entity.get(entity_id, []),
                "failures": failures_by_entity.get(entity_id, []),
            }
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
            count += 1

    return output_path, count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export persisted enrichment state to JSONL")
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output_path, count = export_enrichment(db_path=args.db_path, output=args.output)
    print(f"Exported {count} enriched entities to {output_path}")


if __name__ == "__main__":
    main()
