"""
pipeline/canonicalize.py

Stage 1: Read all source exercises via adapters and write asserted claims to SQLite.

Creates one source_record per source exercise. Does NOT yet create canonical
entities — that is identity.py's job. Claims here are attributed to a specific
(source, source_id) pair, not yet to a canonical entity.

Predicate vocabulary (claims.predicate):
  muscle                 — qualifier = degree hint (prime/secondary/tertiary), value = source muscle name
  movement_pattern       — value = feg local name
  joint_action_hint      — value = feg local name (primary vs supporting routed by enrich.py)
  plane_of_motion        — value = feg local name
  laterality             — value = feg local name (Bilateral/Unilateral/etc.)
  is_compound            — value = 'true' | 'false'
  is_combination         — value = 'true' | 'false'
  exercise_style         — value = feg local name
  training_modality_hint — value = feg local name (hint only; enrichment decides)
  movement_pattern_hint  — value = feg local name (rerouted from style col in ffdb)
  equipment              — value = feg local name

Replay contract:
  - safe to rerun for unchanged source-record sets
  - refuses to silently delete source records already referenced downstream
  - use --reset (or pipeline/run.py --reset-db) for an intentional full rebuild

Usage:
    python3 pipeline/canonicalize.py                    # all sources
    python3 pipeline/canonicalize.py --source free-exercise-db
    python3 pipeline/canonicalize.py --reset --yes-reset  # drop and recreate all tables
"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, entity_ids_with_llm_state, get_connection, init_db, reset_db
from pipeline.db_backup import backup_db

_SOURCES = {
    "free-exercise-db":       "sources.free-exercise-db.adapter",
    "functional-fitness-db":  "sources.functional-fitness-db.adapter",
}


def _import_adapter(source: str):
    """Import a source adapter module by dotted path, handling hyphenated package names."""
    import importlib
    # Hyphens in package names: use importlib with path manipulation instead
    if source == "free-exercise-db":
        adapter_path = _PROJECT_ROOT / "sources" / "free-exercise-db" / "adapter.py"
    else:
        adapter_path = _PROJECT_ROOT / "sources" / "functional-fitness-db" / "adapter.py"

    import importlib.util
    spec = importlib.util.spec_from_file_location(f"adapter_{source}", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_source(conn, source: str, exercises: list[dict]) -> int:
    """Insert source_records, source_claims, and source_metadata for one source.

    Returns the number of exercises written.
    """
    written = 0
    for ex in exercises:
        source_id    = ex["id"]
        display_name = ex["display_name"]
        known        = ex.get("known", {})

        # ── source_records ────────────────────────────────────────────────
        conn.execute(
            """
            INSERT INTO source_records (source, source_id, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(source, source_id)
            DO UPDATE SET display_name = excluded.display_name
            """,
            (source, source_id, display_name),
        )

        # ── source_metadata ───────────────────────────────────────────────
        # Combine instructions + raw muscle hints (fed) for LLM context
        instructions_parts = []
        if inst := known.get("instructions"):
            instructions_parts.append(inst)
        if muscles_hint := known.get("muscles_hint"):
            instructions_parts.append(f"Source muscles — {muscles_hint}")
        instructions = "\n".join(instructions_parts) or None
        raw_data     = json.dumps(ex.get("raw_data", {"equipment": ex.get("equipment", [])}))
        conn.execute(
            """
            INSERT INTO source_metadata (source, source_id, instructions, raw_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, source_id)
            DO UPDATE SET
                instructions = excluded.instructions,
                raw_data = excluded.raw_data
            """,
            (source, source_id, instructions, raw_data),
        )

        # ── source_claims — equipment ─────────────────────────────────────
        for eq in ex.get("equipment", []):
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "equipment", eq, None, "structured"),
            )

        # ── source_claims — muscles ───────────────────────────────────────
        for m in known.get("muscles", []):
            # fed muscles have 'source_name' (raw string); ffdb have 'feg_name'
            value = m.get("feg_name") or m.get("source_name", "")
            if not value:
                continue
            qualifier = m.get("source_role")  # prime / secondary / tertiary
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "muscle", value, qualifier, "structured"),
            )

        # ── source_claims — movement_patterns ────────────────────────────
        for mp in known.get("movement_patterns", []):
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "movement_pattern", mp, None, "structured"),
            )

        # ── source_claims — joint_action_hints ───────────────────────────
        for ja in known.get("joint_actions_from_source", []):
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "joint_action_hint", ja, None, "structured"),
            )

        # ── source_claims — plane_of_motion ──────────────────────────────
        for pom in known.get("plane_of_motion", []):
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "plane_of_motion", pom, None, "structured"),
            )

        # ── source_claims — scalar fields ────────────────────────────────
        for predicate, key in [
            ("laterality",            "laterality"),
            ("training_modality_hint","training_modality_hint"),
            ("movement_pattern_hint", "movement_pattern_hint"),
        ]:
            val = known.get(key)
            if val is not None:
                conn.execute(
                    "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                    (source, source_id, predicate, str(val), None, "structured"),
                )

        for predicate, key in [
            ("is_compound",   "is_compound"),
            ("is_combination","is_combination"),
        ]:
            val = known.get(key)
            if val is not None:
                conn.execute(
                    "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                    (source, source_id, predicate, "true" if val else "false", None, "structured"),
                )

        # ── source_claims — exercise_style ────────────────────────────────
        for es in known.get("exercise_style", []):
            conn.execute(
                "INSERT INTO source_claims (source, source_id, predicate, value, qualifier, origin_type) VALUES (?, ?, ?, ?, ?, ?)",
                (source, source_id, "exercise_style", es, None, "structured"),
            )

        written += 1
    return written


def run(sources: list[str], db_path=DB_PATH) -> None:
    init_db(db_path)
    conn = get_connection(db_path)

    for source in sources:
        print(f"Loading {source}...")
        adapter = _import_adapter(source)
        exercises = adapter.get_exercises()
        print(f"  {len(exercises)} exercises")

        incoming_ids = {ex["id"] for ex in exercises}
        existing_ids = {
            r[0]
            for r in conn.execute(
                "SELECT source_id FROM source_records WHERE source = ?",
                (source,),
            ).fetchall()
        }
        obsolete_ids = sorted(existing_ids - incoming_ids)
        if obsolete_ids:
            placeholders = ", ".join("?" for _ in obsolete_ids)
            refs = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM entity_sources
                WHERE source = ? AND source_id IN ({placeholders})
                """,
                (source, *obsolete_ids),
            ).fetchone()[0]
            if refs:
                names = ", ".join(obsolete_ids[:5])
                more = f" (+{len(obsolete_ids) - 5} more)" if len(obsolete_ids) > 5 else ""
                raise SystemExit(
                    "canonicalize.py detected obsolete source records that are already referenced "
                    "downstream. To protect existing entity mappings and enrichments, it will not "
                    f"delete them automatically. Obsolete IDs: {names}{more}. "
                    "Use `python3 pipeline/run.py --reset-db --to build` to rebuild from source truth."
                )

        # Clear structured claims/metadata for this source before re-inserting.
        # source_records are preserved and upserted so downstream entity mappings remain valid.
        with conn:
            conn.execute("DELETE FROM source_claims WHERE source = ?", (source,))
            conn.execute("DELETE FROM source_metadata WHERE source = ?", (source,))

        with conn:
            n = _write_source(conn, source, exercises)

            if obsolete_ids:
                rows = [(source, source_id) for source_id in obsolete_ids]
                conn.executemany(
                    "DELETE FROM source_metadata WHERE source = ? AND source_id = ?",
                    rows,
                )
                conn.executemany(
                    "DELETE FROM source_records WHERE source = ? AND source_id = ?",
                    rows,
                )

        rows = conn.execute(
            "SELECT COUNT(*) FROM source_claims WHERE source = ?", (source,)
        ).fetchone()[0]
        print(f"  Wrote {n} records, {rows} claims")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonicalize source exercises into SQLite.")
    parser.add_argument(
        "--source", choices=list(_SOURCES.keys()),
        help="Process a single source only (default: all sources)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop and recreate all pipeline tables before running",
    )
    parser.add_argument(
        "--yes-reset",
        action="store_true",
        help="Acknowledge that --reset discards persisted LLM enrichment state",
    )
    parser.add_argument(
        "--no-backup-before-reset",
        action="store_true",
        help="Skip the automatic SQLite backup that normally runs before --reset",
    )
    args = parser.parse_args()

    if args.reset:
        protected_ids: set[str] = set()
        if DB_PATH.exists():
            with get_connection(DB_PATH) as conn:
                protected_ids = entity_ids_with_llm_state(conn)
            if protected_ids and not args.yes_reset:
                raise SystemExit(
                    "--reset would discard persisted LLM enrichment state. "
                    "Re-run with --yes-reset to confirm."
                )
            if not args.no_backup_before_reset:
                backup_path = backup_db(db_path=DB_PATH)
                print(f"Automatic backup before reset: {backup_path}")
        print("Resetting pipeline database...")
        reset_db(DB_PATH)

    sources = [args.source] if args.source else list(_SOURCES.keys())
    run(sources)

    # Summary
    conn = get_connection(DB_PATH)
    total_records = conn.execute("SELECT COUNT(*) FROM source_records").fetchone()[0]
    total_claims  = conn.execute("SELECT COUNT(*) FROM source_claims").fetchone()[0]
    conn.close()
    print(f"\nTotal: {total_records} source records, {total_claims} claims")


if __name__ == "__main__":
    main()
