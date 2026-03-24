"""
pipeline/db.py

SQLite schema and lifecycle helpers for the FEG pipeline.

The database is the intermediate system of record for the pipeline:

Stage 1 — canonicalize.py
  source_records      one row per source record (exercise from a source)
  source_claims       asserted facts from source records
  source_metadata     instructions text and raw source data per source record

Stage 2 — identity.py
  entities            canonical entities (one per unique exercise)
  entity_sources      source_record -> entity mapping
  possible_matches    deferred near-duplicate pairs

Stage 3 — reconcile.py
  conflicts           detected conflicts between sources for same entity
  resolved_claims     reconciled facts per entity

Stage 4 — enrich.py
  inferred_claims     LLM-inferred facts per entity
  enrichment_stamps   vocab versions + timestamp + model per entity
  enrichment_warnings stripped values to restamp after vocab additions
  enrichment_failures retry/quarantine bookkeeping
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DB_PATH = _HERE / "pipeline.db"


def _sidecars(db_path: Path) -> tuple[Path, Path]:
    return (
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-wal"),
    )


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a sqlite3 connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError as exc:
        conn.close()
        if "disk i/o" not in str(exc).lower():
            raise
        # WAL/SHM files are transient. If they are stale, retry once after removing them.
        for path in _sidecars(db_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def reset_db(db_path: Path = DB_PATH) -> None:
    """Remove the SQLite database and any WAL sidecar files."""
    for path in (db_path, *_sidecars(db_path)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def entity_ids_with_llm_state(conn: sqlite3.Connection) -> set[str]:
    """Return entity IDs with persisted enrichment state we should protect by default."""
    protected: set[str] = set()
    for table in ("inferred_claims", "enrichment_stamps", "enrichment_warnings", "enrichment_failures"):
        if not table_exists(conn, table):
            continue
        rows = conn.execute(f"SELECT DISTINCT entity_id FROM {table}").fetchall()
        protected.update(r[0] for r in rows)
    return protected


def delete_entity_runtime_state(conn: sqlite3.Connection, entity_ids: set[str]) -> None:
    """Delete runtime state for a set of entity IDs."""
    if not entity_ids:
        return
    rows = [(entity_id,) for entity_id in sorted(entity_ids)]
    for table in ("enrichment_failures", "enrichment_warnings", "enrichment_stamps", "inferred_claims"):
        if table_exists(conn, table):
            conn.executemany(f"DELETE FROM {table} WHERE entity_id = ?", rows)


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all pipeline tables if they do not exist."""
    conn = get_connection(db_path)
    with conn:
        conn.executescript(
            """
-- ─── Stage 1: canonicalize ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS source_records (
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS source_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    value           TEXT NOT NULL,
    qualifier       TEXT,
    origin_type     TEXT NOT NULL
        CHECK (origin_type IN ('structured', 'inferred')),
    FOREIGN KEY (source, source_id) REFERENCES source_records (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_claims_record
    ON source_claims (source, source_id);

CREATE TABLE IF NOT EXISTS source_metadata (
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    instructions    TEXT,
    raw_data        TEXT,
    PRIMARY KEY (source, source_id),
    FOREIGN KEY (source, source_id) REFERENCES source_records (source, source_id)
);

-- ─── Stage 2: identity ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'resolved'
        CHECK (status IN ('resolved', 'deferred'))
);

CREATE TABLE IF NOT EXISTS entity_sources (
    entity_id       TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (source, source_id),
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id),
    FOREIGN KEY (source, source_id) REFERENCES source_records (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_sources_entity
    ON entity_sources (entity_id);

CREATE TABLE IF NOT EXISTS possible_matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id_a     TEXT NOT NULL,
    entity_id_b     TEXT NOT NULL,
    score           REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'merged', 'separate', 'variant_of')),
    FOREIGN KEY (entity_id_a) REFERENCES entities (entity_id),
    FOREIGN KEY (entity_id_b) REFERENCES entities (entity_id)
);

-- ─── Stage 3: reconcile ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id           TEXT NOT NULL,
    predicate           TEXT NOT NULL,
    description         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'deferred')),
    resolution_method   TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);

CREATE TABLE IF NOT EXISTS resolved_claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id           TEXT NOT NULL,
    predicate           TEXT NOT NULL,
    value               TEXT NOT NULL,
    qualifier           TEXT,
    resolution_method   TEXT NOT NULL,
    conflict_id         INTEGER,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id),
    FOREIGN KEY (conflict_id) REFERENCES conflicts (conflict_id)
);

CREATE INDEX IF NOT EXISTS idx_resolved_claims_entity
    ON resolved_claims (entity_id);

-- ─── Stage 4: enrich ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS inferred_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    value           TEXT NOT NULL,
    qualifier       TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);

CREATE INDEX IF NOT EXISTS idx_inferred_claims_entity
    ON inferred_claims (entity_id);

CREATE TABLE IF NOT EXISTS enrichment_stamps (
    entity_id       TEXT PRIMARY KEY,
    versions_json   TEXT NOT NULL,
    enriched_at     TEXT NOT NULL,
    model           TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);

CREATE TABLE IF NOT EXISTS enrichment_warnings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    stripped_value  TEXT NOT NULL,
    enriched_at     TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);

CREATE INDEX IF NOT EXISTS idx_enrichment_warnings_value
    ON enrichment_warnings (stripped_value);

CREATE TABLE IF NOT EXISTS enrichment_failures (
    entity_id       TEXT NOT NULL,
    failed_at       TEXT NOT NULL,
    error           TEXT,
    PRIMARY KEY (entity_id, failed_at),
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);
"""
        )
    conn.close()
