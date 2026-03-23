"""
pipeline/identity.py

Stage 2: Cluster source_records into canonical entities.

Algorithm:
  1. Exact name match (after normalization): auto-merge, confidence=1.0
  2. No match found: emit as standalone entity, confidence=1.0
  3. Near-name match (Levenshtein ≤ 2 after normalization):
       compute biomechanical similarity score
       score ≥ 0.7 → auto-merge
       0.4 ≤ score < 0.7 → defer (possible_matches, status='open')
       score < 0.4 → keep separate

Biomechanical similarity (for near-name pairs):
  movement_pattern overlap (Jaccard): weight 0.4
  laterality match:                   weight 0.2
  equipment overlap (Jaccard):        weight 0.2
  coarse muscle group overlap (Jaccard, first token of muscle name): weight 0.2

Entity ID conventions:
  - Merged entity (appears in both sources): normalized_name
  - Single-source (fed):  'fed_{source_id}'
  - Single-source (ffdb): 'ffdb_{source_id}'

Usage:
    python3 pipeline/identity.py
    python3 pipeline/identity.py --dry-run   # print clusters, no writes
"""

import argparse
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection

# Source name prefixes for single-source entities
_SOURCE_PREFIX = {
    "free-exercise-db":      "fed",
    "functional-fitness-db": "ffdb",
}


# ─── Name normalisation ───────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


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


def _biomechanical_score(conn, source_a: str, id_a: str, source_b: str, id_b: str) -> float:
    def claims(source, source_id, predicate):
        rows = conn.execute(
            "SELECT value FROM source_claims WHERE source=? AND source_id=? AND predicate=?",
            (source, source_id, predicate),
        ).fetchall()
        return {r[0] for r in rows}

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

    # Coarse muscle group (first token of muscle name, e.g. "Quadriceps" from "QuadricepsFemoris")
    def coarse_muscles(source, source_id):
        rows = conn.execute(
            "SELECT value FROM source_claims WHERE source=? AND source_id=? AND predicate='muscle'",
            (source, source_id),
        ).fetchall()
        # Split camelCase on capital letters to get first word
        result = set()
        for (val,) in rows:
            parts = re.sub(r"([A-Z])", r" \1", val).split()
            if parts:
                result.add(parts[0].lower())
        return result

    cma = coarse_muscles(source_a, id_a)
    cmb = coarse_muscles(source_b, id_b)
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


def cluster(conn, dry_run: bool = False) -> dict:
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

    sources = list(by_source.keys())
    if len(sources) >= 2:
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                src_a, src_b = sources[i], sources[j]
                list_a = by_source[src_a]
                list_b = by_source[src_b]

                # Build first-word index for list_b for fast pre-filtering
                # Two names with different first words can't have Levenshtein ≤ 2
                # unless the names are very short (≤ 4 chars)
                first_word_b: dict[str, list] = {}
                for eb in list_b:
                    norm_b = _normalize(eb["display_name"])
                    fw = norm_b.split()[0] if norm_b else ""
                    first_word_b.setdefault(fw, []).append((eb, norm_b))

                for ea in list_a:
                    norm_a = _normalize(ea["display_name"])
                    src_id_a = ea["sources"][0][1]
                    fw_a = norm_a.split()[0] if norm_a else ""

                    # Candidate list: same first word, OR short names (≤ 6 chars total)
                    candidates = first_word_b.get(fw_a, [])
                    if len(norm_a) <= 6:
                        # Short names: also check all other buckets
                        candidates = [(eb, nb) for fw, eblist in first_word_b.items() for eb, nb in eblist]

                    for eb, norm_b in candidates:
                        if _levenshtein(norm_a, norm_b) > 2:
                            continue
                        src_id_b = eb["sources"][0][1]
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
        conn.execute("DELETE FROM inferred_claims")
        conn.execute("DELETE FROM enrichment_stamps")
        conn.execute("DELETE FROM resolved_claims")
        conn.execute("DELETE FROM conflicts")
        conn.execute("DELETE FROM possible_matches")
        conn.execute("DELETE FROM entity_sources")
        conn.execute("DELETE FROM entities")

        for e in entities:
            if e.get("_absorbed"):
                continue
            conn.execute(
                "INSERT INTO entities (entity_id, display_name, status) VALUES (?, ?, ?)",
                (e["entity_id"], e["display_name"], e["status"]),
            )
            for source, source_id, confidence in e["sources"]:
                conn.execute(
                    "INSERT INTO entity_sources (entity_id, source, source_id, confidence) VALUES (?, ?, ?, ?)",
                    (e["entity_id"], source, source_id, confidence),
                )

        for p in possible:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster source records into canonical entities.")
    parser.add_argument("--dry-run", action="store_true", help="Print clusters without writing")
    args = parser.parse_args()

    conn = get_connection(DB_PATH)
    stats = cluster(conn, dry_run=args.dry_run)
    conn.close()

    if not args.dry_run:
        print(f"Entities:  {stats['entities']}")
        print(f"Merged:    {stats['merged']}")
        print(f"Triage:    {stats['triage']}")


if __name__ == "__main__":
    main()
