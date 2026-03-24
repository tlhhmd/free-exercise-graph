#!/usr/bin/env python3
"""
pipeline/import_enrichment.py

Restore exported enrichment JSONL into a deterministic SQLite rebuild.

Usage:
    python3 pipeline/import_enrichment.py pipeline/exports/enrichment-20260324-120000.jsonl
    python3 pipeline/import_enrichment.py ./artifact.jsonl --replace-existing
    python3 pipeline/import_enrichment.py ./artifact.jsonl --skip-missing-entities
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection, init_db, table_exists


def _entity_exists(conn, entity_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
    return row is not None


def _delete_existing(conn, entity_id: str) -> None:
    for table in ("enrichment_failures", "enrichment_warnings", "enrichment_stamps", "inferred_claims"):
        if table_exists(conn, table):
            conn.execute(f"DELETE FROM {table} WHERE entity_id = ?", (entity_id,))


def import_enrichment(
    input_path: Path,
    *,
    db_path: Path = DB_PATH,
    replace_existing: bool = False,
    skip_missing_entities: bool = False,
) -> dict[str, int]:
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    init_db(db_path)
    conn = get_connection(db_path)

    inserted = 0
    skipped_existing = 0
    skipped_missing = 0

    with conn, input_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            entity_id = payload["entity_id"]

            if not _entity_exists(conn, entity_id):
                if skip_missing_entities:
                    skipped_missing += 1
                    continue
                raise SystemExit(
                    f"Import file references unknown entity_id {entity_id!r} on line {line_number}. "
                    "Run deterministic stages first, or use --skip-missing-entities."
                )

            existing = conn.execute(
                "SELECT 1 FROM enrichment_stamps WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
            if existing and not replace_existing:
                skipped_existing += 1
                continue

            _delete_existing(conn, entity_id)

            stamp = payload["stamp"]
            conn.execute(
                """
                INSERT INTO enrichment_stamps (entity_id, versions_json, enriched_at, model)
                VALUES (?, ?, ?, ?)
                """,
                (
                    entity_id,
                    json.dumps(stamp["versions_json"]),
                    stamp["enriched_at"],
                    stamp.get("model"),
                ),
            )

            claims = payload.get("claims", [])
            if claims:
                conn.executemany(
                    """
                    INSERT INTO inferred_claims (entity_id, predicate, value, qualifier)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            entity_id,
                            claim["predicate"],
                            claim["value"],
                            claim.get("qualifier"),
                        )
                        for claim in claims
                    ],
                )

            warnings = payload.get("warnings", [])
            if warnings:
                conn.executemany(
                    """
                    INSERT INTO enrichment_warnings (entity_id, predicate, stripped_value, enriched_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            entity_id,
                            warning["predicate"],
                            warning["stripped_value"],
                            warning["enriched_at"],
                        )
                        for warning in warnings
                    ],
                )

            failures = payload.get("failures", [])
            if failures:
                conn.executemany(
                    """
                    INSERT INTO enrichment_failures (entity_id, failed_at, error)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (
                            entity_id,
                            failure["failed_at"],
                            failure.get("error"),
                        )
                        for failure in failures
                    ],
                )

            inserted += 1

    conn.close()
    return {
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "skipped_missing": skipped_missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import enrichment JSONL into pipeline SQLite")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Overwrite enrichment already stored for matching entity IDs",
    )
    parser.add_argument(
        "--skip-missing-entities",
        action="store_true",
        help="Skip JSONL rows whose entity_id does not exist in the current deterministic rebuild",
    )
    args = parser.parse_args()

    stats = import_enrichment(
        args.input_path,
        db_path=args.db_path,
        replace_existing=args.replace_existing,
        skip_missing_entities=args.skip_missing_entities,
    )
    print(
        "Imported {inserted} entities"
        " (skipped existing: {skipped_existing}, skipped missing: {skipped_missing})".format(**stats)
    )


if __name__ == "__main__":
    main()
