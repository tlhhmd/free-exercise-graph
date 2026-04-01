"""
pipeline/identity.py

Stage 2: Cluster source_records into canonical entities.

Algorithm:
  1. Exact name match (after equipment-aware normalization): auto-merge, confidence=1.0
  2. No match found: emit as standalone entity, confidence=1.0
  3. Near-name match — token Jaccard ≥ 0.5 on normalized name tokens
     (Levenshtein ≤ 2 retained as additional path for short names ≤ 2 tokens):
       compute biomechanical similarity score
       score ≥ 0.7 → auto-merge
       0.4 ≤ score < 0.7 → defer (possible_matches, status='open')
       score < 0.4 → keep separate

Name normalization strips equipment modifier words (ADR-092, ADR-001):
  Barbell, Dumbbell, Kettlebell, Cable, Machine, etc. — equipment is not identity.

Biomechanical similarity:
  movement_pattern overlap (Jaccard): weight 0.4
  laterality match:                   weight 0.2
  equipment overlap (Jaccard):        weight 0.2
  muscle region overlap (Jaccard):    weight 0.2
    — for free-exercise-db: raw muscle strings mapped inline to feg regions
    — for functional-fitness-db: feg-mapped values from source_claims

Entity ID conventions:
  - Merged entity (appears in both sources): normalized_name
  - Single-source (fed):  'fed_{source_id}'
  - Single-source (ffdb): 'ffdb_{source_id}'

Usage:
    python3 pipeline/identity.py
    python3 pipeline/identity.py --dry-run   # print clusters, no writes
    python3 pipeline/identity.py --drop-enrichment   # allow destructive entity-id removal
"""

import argparse
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, delete_entity_runtime_state, entity_ids_with_llm_state, get_connection

# Source name prefixes for single-source entities
_SOURCE_PREFIX = {
    "free-exercise-db":      "fed",
    "functional-fitness-db": "ffdb",
}


# ─── Manual merge exclusions (ADR-112) ───────────────────────────────────────
#
# Pairs that must never be auto-merged, keyed by frozenset of (source, source_id).
# Add an entry here when the biomechanical scorer produces a false positive — i.e.
# two exercises that score ≥ 0.7 but are genuinely distinct movements.
_MERGE_EXCLUSIONS: set[frozenset] = {
    # 3/4 Sit-Up ≠ Butterfly Sit-Up: different ROM and leg position
    frozenset([("free-exercise-db", "3_4_Sit_Up"), ("functional-fitness-db", "Bodyweight_Butterfly_Sit_Up")]),
    # Press Sit-Up ≠ Turkish Sit-Up: different movement pattern
    frozenset([("free-exercise-db", "Press_Sit_Up"), ("functional-fitness-db", "Barbell_Turkish_Sit_Up")]),
    # Single Arm Cable Crossover ≠ Single Arm Cable Bayesian Curl: different movement entirely
    frozenset([("free-exercise-db", "Single_Arm_Cable_Crossover"), ("functional-fitness-db", "Single_Arm_Cable_Bayesian_Curl")]),
}


# ─── Equipment modifier words (ADR-092) ───────────────────────────────────────

# Words that describe equipment context, not exercise identity (ADR-001).
# Stripped from names before comparison so "Barbell Romanian Deadlift" and
# "Romanian Deadlift" normalise to the same token set.
_EQUIPMENT_MODIFIERS = {
    "barbell", "dumbbell", "dumbbells", "kettlebell", "kettlebells",
    "cable", "cables", "machine", "ez", "curl", "bar",
    "resistance", "band", "bands", "bodyweight", "medicine",
    "ball", "foam", "roller", "exercise", "sandbag", "suspension",
    "trainer", "weighted",
}


# ─── Inline fed muscle → feg region mapping (ADR-092) ─────────────────────────

# free-exercise-db uses 17 coarse colloquial muscle strings. Map to feg region
# local names for biomechanical scoring. No crosswalk file needed — these
# strings are stable (sourced from a static JSON dataset).
_FED_MUSCLE_MAP: dict[str, str] = {
    "abdominals":  "Abdominals",
    "abductors":   "Abductors",
    "adductors":   "Adductors",
    "biceps":      "Biceps",
    "calves":      "Calves",
    "chest":       "Chest",
    "forearms":    "Forearms",
    "glutes":      "Glutes",
    "hamstrings":  "Hamstrings",
    "lats":        "LatissimusDorsi",
    "lower back":  "LowerBack",
    "middle back": "MiddleBack",
    "neck":        "Traps",       # closest region; neck as a standalone region not in vocabulary
    "quadriceps":  "Quadriceps",
    "shoulders":   "Shoulders",
    "traps":       "Traps",
    "triceps":     "Triceps",
}


# ─── Name normalisation ───────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, strip equipment modifiers, collapse whitespace."""
    name = name.lower()
    name = name.replace("-", " ")  # treat hyphens as word separators before stripping punctuation
    name = re.sub(r"[^a-z0-9\s]", "", name)
    tokens = [t for t in name.split() if t not in _EQUIPMENT_MODIFIERS]
    return " ".join(tokens).strip()


def _tokens(norm: str) -> set[str]:
    """Return the set of tokens from a normalized name."""
    return set(norm.split()) if norm else set()


# ─── Levenshtein distance ─────────────────────────────────────────────────────

try:
    from rapidfuzz.distance import Levenshtein as _RFLevenshtein
    def _levenshtein(a: str, b: str) -> int:
        return _RFLevenshtein.distance(a, b, score_cutoff=2) if abs(len(a) - len(b)) <= 2 else 3
except ImportError:
    def _levenshtein(a: str, b: str) -> int:
        if abs(len(a) - len(b)) > 2:
            return 3  # fast rejection: length difference alone exceeds threshold
        if a == b:
            return 0
        if len(a) < len(b):
            a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            curr = [i]
            for j, cb in enumerate(b, 1):
                curr.append(min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                ))
            prev = curr
        return prev[len(b)]


# ─── Biomechanical similarity ─────────────────────────────────────────────────

def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _fed_muscles_from_raw(conn, source_id: str) -> set[str]:
    """Extract feg region names from free-exercise-db raw_data JSON.

    free-exercise-db stores primaryMuscles/secondaryMuscles as coarse colloquial
    strings. Map them to feg region names inline (ADR-092) — no crosswalk file needed.
    """
    row = conn.execute(
        "SELECT raw_data FROM source_metadata WHERE source='free-exercise-db' AND source_id=?",
        (source_id,),
    ).fetchone()
    if not row or not row["raw_data"]:
        return set()
    import json
    data = json.loads(row["raw_data"])
    result = set()
    for field in ("primaryMuscles", "secondaryMuscles"):
        for m in data.get(field) or []:
            feg = _FED_MUSCLE_MAP.get(m.strip().lower())
            if feg:
                result.add(feg)
    return result


def _biomechanical_score(conn, source_a: str, id_a: str, source_b: str, id_b: str) -> float:
    def claims(source, source_id, predicate):
        rows = conn.execute(
            "SELECT value FROM source_claims WHERE source=? AND source_id=? AND predicate=?",
            (source, source_id, predicate),
        ).fetchall()
        return {r[0] for r in rows}

    def muscle_regions(source, source_id) -> set[str]:
        """Return a set of feg region-level muscle names for scoring."""
        if source == "free-exercise-db":
            return _fed_muscles_from_raw(conn, source_id)
        # ffdb: feg-mapped values already in source_claims; coarsen to first camelCase word
        rows = conn.execute(
            "SELECT value FROM source_claims WHERE source=? AND source_id=? AND predicate='muscle'",
            (source, source_id),
        ).fetchall()
        result = set()
        for (val,) in rows:
            parts = re.sub(r"([A-Z])", r" \1", val).split()
            if parts:
                result.add(parts[0])   # e.g. "GluteusMaximus" → "Gluteus"
        return result

    # Movement patterns
    mp_a = claims(source_a, id_a, "movement_pattern")
    mp_b = claims(source_b, id_b, "movement_pattern")
    mp_score = _jaccard(mp_a, mp_b)

    # Laterality
    lat_a = claims(source_a, id_a, "laterality")
    lat_b = claims(source_b, id_b, "laterality")
    if lat_a and lat_b:
        lat_score = 1.0 if lat_a == lat_b else 0.0
    else:
        lat_score = 0.5  # one or both absent — neutral

    # Equipment
    eq_a = claims(source_a, id_a, "equipment")
    eq_b = claims(source_b, id_b, "equipment")
    eq_score = _jaccard(eq_a, eq_b)

    # Muscle regions
    cma = muscle_regions(source_a, id_a)
    cmb = muscle_regions(source_b, id_b)
    muscle_score = _jaccard(cma, cmb)

    return (
        0.4 * mp_score
        + 0.2 * lat_score
        + 0.2 * eq_score
        + 0.2 * muscle_score
    )


# ─── Main clustering ──────────────────────────────────────────────────────────

def _make_entity_id(norm_name: str, source: str, source_id: str, merged: bool) -> str:
    if merged:
        # Slug the normalized name
        return re.sub(r"\s+", "_", norm_name)
    prefix = _SOURCE_PREFIX.get(source, source.split("-")[0])
    return f"{prefix}_{source_id}"


def cluster(conn, dry_run: bool = False, drop_enrichment: bool = False) -> dict:
    """Build entity clusters. Returns summary stats dict."""
    records = conn.execute(
        "SELECT source, source_id, display_name FROM source_records ORDER BY source, source_id"
    ).fetchall()

    # Build {norm_name: [(source, source_id, display_name)]}
    by_norm: dict[str, list[tuple]] = {}
    for r in records:
        norm = _normalize(r["display_name"])
        by_norm.setdefault(norm, []).append((r["source"], r["source_id"], r["display_name"]))

    entities: list[dict] = []      # {entity_id, display_name, sources: [(source, source_id, confidence)]}
    possible: list[dict] = []      # {entity_id_a, entity_id_b, score}

    # Pass 1: exact name matches → auto-merge
    processed_norms = set()
    for norm, group in by_norm.items():
        processed_norms.add(norm)
        if len(group) == 1:
            source, source_id, display_name = group[0]
            entity_id = _make_entity_id(norm, source, source_id, merged=False)
            entities.append({
                "entity_id":    entity_id,
                "display_name": display_name,
                "status":       "resolved",
                "sources":      [(source, source_id, 1.0)],
            })
        else:
            # Multiple sources with exact same normalized name → merge
            entity_id = _make_entity_id(norm, "", "", merged=True)
            display_name = group[0][2]  # use first source's display name
            entities.append({
                "entity_id":    entity_id,
                "display_name": display_name,
                "status":       "resolved",
                "sources":      [(s, sid, 1.0) for s, sid, _ in group],
            })

    # Pass 2: near-name matches across unmatched single-source entities
    # Only check pairs from different sources
    single_source_entities = [e for e in entities if len(e["sources"]) == 1]
    by_source: dict[str, list[dict]] = {}
    for e in single_source_entities:
        src = e["sources"][0][0]
        by_source.setdefault(src, []).append(e)

    _TOKEN_JACCARD_THRESHOLD = 0.5
    _TOKEN_JACCARD_MIN_TOKENS = 1  # ignore empty names

    sources = list(by_source.keys())
    if len(sources) >= 2:
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                src_a, src_b = sources[i], sources[j]
                list_a = by_source[src_a]
                list_b = by_source[src_b]

                # Build token index for list_b: token → list of (entity, norm, token_set)
                # Allows fast candidate lookup: any entity sharing a token with ea is a candidate.
                token_index_b: dict[str, list] = {}
                for eb in list_b:
                    norm_b = _normalize(eb["display_name"])
                    toks_b = _tokens(norm_b)
                    for tok in toks_b:
                        token_index_b.setdefault(tok, []).append((eb, norm_b, toks_b))

                for ea in list_a:
                    norm_a = _normalize(ea["display_name"])
                    toks_a = _tokens(norm_a)
                    src_id_a = ea["sources"][0][1]

                    if len(toks_a) < _TOKEN_JACCARD_MIN_TOKENS:
                        continue

                    # Candidate set: any entity in list_b that shares at least one token with ea.
                    # Deduplicate by entity_id since an entity may appear in multiple token buckets.
                    seen_b: set[str] = set()
                    candidates: list[tuple] = []
                    for tok in toks_a:
                        for eb, norm_b, toks_b in token_index_b.get(tok, []):
                            if eb["entity_id"] not in seen_b:
                                seen_b.add(eb["entity_id"])
                                candidates.append((eb, norm_b, toks_b))

                    for eb, norm_b, toks_b in candidates:
                        # Skip entities already absorbed into another merge
                        if eb.get("_absorbed"):
                            continue

                        # Token Jaccard filter
                        union = toks_a | toks_b
                        jaccard = len(toks_a & toks_b) / len(union) if union else 0.0

                        # Also accept Levenshtein ≤ 2 for short names (≤ 2 tokens) where
                        # Jaccard is unstable (e.g. single-word names like "Squat" vs "Squats")
                        is_short = len(toks_a) <= 2 and len(toks_b) <= 2
                        lev_close = is_short and _levenshtein(norm_a, norm_b) <= 2

                        if jaccard < _TOKEN_JACCARD_THRESHOLD and not lev_close:
                            continue

                        src_id_b = eb["sources"][0][1]
                        pair_key = frozenset([(src_a, src_id_a), (src_b, src_id_b)])
                        if pair_key in _MERGE_EXCLUSIONS:
                            continue
                        score = _biomechanical_score(conn, src_a, src_id_a, src_b, src_id_b)
                        if score >= 0.7:
                            ea["sources"].append((src_b, src_id_b, score))
                            eb["_absorbed"] = True
                        elif score >= 0.4:
                            possible.append({
                                "entity_id_a": ea["entity_id"],
                                "entity_id_b": eb["entity_id"],
                                "score":       score,
                            })

    if dry_run:
        merged = [e for e in entities if len(e["sources"]) > 1]
        absorbed = [e for e in entities if e.get("_absorbed")]
        pending_triage = possible
        print(f"Entities: {len(entities) - len(absorbed)} canonical")
        print(f"  {len(merged)} merged (multiple sources)")
        print(f"  {len(absorbed)} absorbed into merges")
        print(f"  {len(pending_triage)} near-matches deferred to triage")
        for e in merged:
            srcs = ", ".join(f"{s}:{sid}" for s, sid, _ in e["sources"])
            print(f"    MERGE  {e['entity_id']}  ← {srcs}")
        for p in pending_triage:
            print(f"    TRIAGE {p['entity_id_a']} ↔ {p['entity_id_b']}  score={p['score']:.2f}")
        return {"entities": len(entities) - len(absorbed), "merged": len(merged), "triage": len(pending_triage)}

    # Write
    with conn:
        conn.execute("DELETE FROM resolved_claims")
        conn.execute("DELETE FROM possible_matches")
        conn.execute("DELETE FROM entity_sources")
        conn.execute("DELETE FROM conflicts")

        current_ids = {
            r[0] for r in conn.execute("SELECT entity_id FROM entities").fetchall()
        }
        new_entity_rows = [e for e in entities if not e.get("_absorbed")]
        new_ids = {e["entity_id"] for e in new_entity_rows}
        removed_ids = current_ids - new_ids
        protected_ids = entity_ids_with_llm_state(conn)
        protected_removed = removed_ids & protected_ids
        if protected_removed and not drop_enrichment:
            sample = ", ".join(sorted(protected_removed)[:5])
            more = f" (+{len(protected_removed) - 5} more)" if len(protected_removed) > 5 else ""
            raise RuntimeError(
                "identity.py would remove entity IDs that already have persisted enrichment state: "
                f"{sample}{more}. Re-run with --dry-run to inspect the new clustering, or use "
                "`python3 pipeline/canonicalize.py --reset` / `python3 pipeline/run.py --reset-db` "
                "if you intentionally want a full rebuild."
            )

        removable = removed_ids if drop_enrichment else (removed_ids - protected_ids)
        delete_entity_runtime_state(conn, removable)
        if removable:
            conn.executemany(
                "DELETE FROM entities WHERE entity_id = ?",
                [(entity_id,) for entity_id in sorted(removable)],
            )

        for e in new_entity_rows:
            conn.execute(
                """
                INSERT INTO entities (entity_id, display_name, status)
                VALUES (?, ?, ?)
                ON CONFLICT(entity_id)
                DO UPDATE SET
                    display_name = excluded.display_name,
                    status = excluded.status
                """,
                (e["entity_id"], e["display_name"], e["status"]),
            )
            for source, source_id, confidence in e["sources"]:
                conn.execute(
                    "INSERT INTO entity_sources (entity_id, source, source_id, confidence) VALUES (?, ?, ?, ?)",
                    (e["entity_id"], source, source_id, confidence),
                )

        # Build set of surviving entity_ids (absorbed entities are not written)
        absorbed_ids = {e["entity_id"] for e in entities if e.get("_absorbed")}
        for p in possible:
            if p["entity_id_a"] in absorbed_ids or p["entity_id_b"] in absorbed_ids:
                continue  # entity was later absorbed — triage entry is moot
            conn.execute(
                "INSERT INTO possible_matches (entity_id_a, entity_id_b, score, status) VALUES (?, ?, ?, 'open')",
                (p["entity_id_a"], p["entity_id_b"], p["score"]),
            )

    total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    merged_count   = conn.execute(
        "SELECT COUNT(DISTINCT entity_id) FROM entity_sources GROUP BY entity_id HAVING COUNT(*) > 1"
    ).fetchall()
    triage_count   = conn.execute("SELECT COUNT(*) FROM possible_matches WHERE status='open'").fetchone()[0]

    return {
        "entities": total_entities,
        "merged":   len(merged_count),
        "triage":   triage_count,
    }


def run(*, db_path=DB_PATH, dry_run: bool = False, drop_enrichment: bool = False) -> dict:
    conn = get_connection(db_path)
    try:
        return cluster(conn, dry_run=dry_run, drop_enrichment=drop_enrichment)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster source records into canonical entities.")
    parser.add_argument("--dry-run", action="store_true", help="Print clusters without writing")
    parser.add_argument(
        "--drop-enrichment",
        action="store_true",
        help="Allow removal of entities even if they already have persisted enrichment state",
    )
    args = parser.parse_args()

    stats = run(dry_run=args.dry_run, drop_enrichment=args.drop_enrichment)

    if not args.dry_run:
        print(f"Entities:  {stats['entities']}")
        print(f"Merged:    {stats['merged']}")
        print(f"Triage:    {stats['triage']}")


if __name__ == "__main__":
    main()
