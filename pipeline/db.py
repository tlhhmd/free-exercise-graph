"""
pipeline/db.py

SQLite schema and connection utilities for the FEG pipeline.

All pipeline stages import get_connection() and init_db() from here.
The DB_PATH constant points to pipeline/pipeline.db (gitignored).

Tables:
  Stage 1 — canonicalize.py
    source_records    one row per source record (exercise from a source)
    source_claims     asserted facts from source records
    source_metadata   instructions text and raw source data per source record

  Stage 2 — identity.py
    entities          canonical entities (one per unique exercise)
    entity_sources    source_record → entity mapping
    possible_matches  deferred near-duplicate pairs

  Stage 3 — reconcile.py
    conflicts         detected conflicts between sources for same entity
    resolved_claims   reconciled facts per entity

  Stage 4 — enrich.py
    inferred_claims   LLM-inferred facts per entity
"""

import sqlite3
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DB_PATH = _HERE / "pipeline.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a sqlite3 connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all pipeline tables if they do not exist."""
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
-- ─── Stage 1: canonicalize ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS source_records (
    source          TEXT NOT NULL,          -- 'free-exercise-db' | 'functional-fitness-db'
    source_id       TEXT NOT NULL,          -- slugified exercise name from source
    display_name    TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

-- Asserted facts from source records.
-- predicate values: muscle, movement_pattern, joint_action_hint,
--   plane_of_motion, laterality, is_compound, is_combination,
--   exercise_style, training_modality_hint, equipment
CREATE TABLE IF NOT EXISTS source_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    value           TEXT NOT NULL,
    qualifier       TEXT,                   -- degree for muscle claims; NULL otherwise
    origin_type     TEXT NOT NULL           -- 'structured' | 'inferred'
        CHECK (origin_type IN ('structured', 'inferred')),
    FOREIGN KEY (source, source_id) REFERENCES source_records (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_claims_record
    ON source_claims (source, source_id);

CREATE TABLE IF NOT EXISTS source_metadata (
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    instructions    TEXT,                   -- joined instruction text (fed only)
    raw_data        TEXT,                   -- JSON blob of raw source row
    PRIMARY KEY (source, source_id),
    FOREIGN KEY (source, source_id) REFERENCES source_records (source, source_id)
);

-- ─── Stage 2: identity ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,       -- normalized name or 'fed_{source_id}'
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

-- Reconciled facts — one row per (entity, predicate, value) triple.
-- For scalar predicates (laterality, is_compound, is_combination)
-- only one row per predicate; for multi-valued (muscle, movement_pattern, etc.)
-- multiple rows are expected.
CREATE TABLE IF NOT EXISTS resolved_claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id           TEXT NOT NULL,
    predicate           TEXT NOT NULL,
    value               TEXT NOT NULL,
    qualifier           TEXT,               -- degree for muscle claims
    resolution_method   TEXT NOT NULL,      -- 'union' | 'conservative' | 'consensus'
                                            --   | 'coverage_gap' | 'deferred'
    conflict_id         INTEGER,
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id),
    FOREIGN KEY (conflict_id) REFERENCES conflicts (conflict_id)
);

CREATE INDEX IF NOT EXISTS idx_resolved_claims_entity
    ON resolved_claims (entity_id);

-- ─── Stage 4: enrich ──────────────────────────────────────────────────────────

-- LLM-inferred facts. Asserted resolved_claims always take precedence.
-- predicate values mirror ExerciseEnrichment fields:
--   muscle, movement_pattern, primary_joint_action, supporting_joint_action,
--   is_compound, laterality, is_combination, plane_of_motion,
--   exercise_style, training_modality
CREATE TABLE IF NOT EXISTS inferred_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    predicate       TEXT NOT NULL,
    value           TEXT NOT NULL,
    qualifier       TEXT,                   -- degree for muscle claims
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);

CREATE INDEX IF NOT EXISTS idx_inferred_claims_entity
    ON inferred_claims (entity_id);

-- Vocabulary version stamps at enrichment time, one row per entity.
CREATE TABLE IF NOT EXISTS enrichment_stamps (
    entity_id       TEXT PRIMARY KEY,
    versions_json   TEXT NOT NULL,          -- JSON dict of vocab name → version
    enriched_at     TEXT NOT NULL,          -- ISO-8601 UTC
    FOREIGN KEY (entity_id) REFERENCES entities (entity_id)
);
""")
    conn.close()
