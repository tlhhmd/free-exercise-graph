"""
pipeline/reconcile.py

Stage 3: Apply resolution algebra over source_claims per canonical entity.

Writes to resolved_claims and conflicts. Deferred scalars go to conflicts
with status='deferred'; enrichment will fill them in.

Resolution algebra (applied per entity, per predicate):

  predicate              rule
  ─────────────────────────────────────────────────────────────────────
  muscle (presence)      union
  muscle (degree)        conservative: PrimeMover > Synergist > Stabilizer > PassiveTarget
                         (only applies when both sources assert a degree for the same muscle)
  movement_pattern       union
  joint_action_hint      union (collect all; primary/supporting routing deferred to enrich)
  plane_of_motion        union
  equipment              union
  exercise_style         union
  training_modality_hint union (pass through as hint)
  movement_pattern_hint  union
  laterality             coverage gap → take what exists; conflict (both assert different) → defer
  is_compound            coverage gap → take what exists; conflict → defer
  is_combination         coverage gap → take what exists; conflict → defer

After muscle union: ancestor deduplication (if both Quadriceps and RectusFemoris
appear, drop the ancestor). Uses SKOS broader chain from muscles.ttl.

Usage:
    python3 pipeline/reconcile.py
    python3 pipeline/reconcile.py --triage     # print deferred conflicts
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection

# Degree ordering: lower index = "stronger" claim
_DEGREE_ORDER = ["PrimeMover", "Synergist", "Stabilizer", "PassiveTarget"]

# Source-role → approximate degree hint (used to assign degrees to fed muscles
# that have no resolved degree yet — enrichment will confirm/override)
_ROLE_TO_DEGREE_HINT = {
    "prime":     "PrimeMover",
    "secondary": "Synergist",
    "tertiary":  "Stabilizer",
}

# Multi-valued predicates resolved by union
_UNION_PREDICATES = {
    "movement_pattern",
    "joint_action_hint",
    "plane_of_motion",
    "equipment",
    "exercise_style",
    "training_modality_hint",
    "movement_pattern_hint",
}

# Scalar predicates resolved by coverage-gap / defer
_SCALAR_PREDICATES = {"laterality", "is_compound", "is_combination"}


# ─── Ancestor map loading ────────────────────────────────────────────────────

def _load_ancestor_map() -> dict[str, frozenset[str]]:
    """Load SKOS broader chain for muscles from muscles.ttl."""
    try:
        from rdflib import Graph, Namespace
        from rdflib.namespace import SKOS
        g = Graph()
        g.parse(_PROJECT_ROOT / "ontology" / "muscles.ttl", format="turtle")

        def local(uri) -> str:
            return str(uri).split("#")[-1]

        def ancestors(uri) -> frozenset[str]:
            result: set[str] = set()
            queue = list(g.objects(uri, SKOS.broader))
            while queue:
                p = queue.pop()
                name = local(p)
                if name not in result:
                    result.add(name)
                    queue.extend(g.objects(p, SKOS.broader))
            return frozenset(result)

        all_subjects = set(g.subjects(SKOS.broader, None)) | set(g.objects(None, SKOS.broader))
        return {local(s): ancestors(s) for s in all_subjects}
    except Exception:
        return {}


# ─── Per-entity reconciliation ───────────────────────────────────────────────

def _reconcile_entity(conn, entity_id: str, ancestor_map: dict) -> None:
    # Gather all source claims for this entity
    rows = conn.execute(
        """
        SELECT sc.predicate, sc.value, sc.qualifier, sc.source
        FROM source_claims sc
        JOIN entity_sources es ON sc.source = es.source AND sc.source_id = es.source_id
        WHERE es.entity_id = ?
        """,
        (entity_id,),
    ).fetchall()

    # Group by predicate
    by_pred: dict[str, list[dict]] = {}
    for r in rows:
        by_pred.setdefault(r["predicate"], []).append({
            "value":     r["value"],
            "qualifier": r["qualifier"],
            "source":    r["source"],
        })

    resolved: list[dict] = []  # {predicate, value, qualifier, resolution_method}
    conflicts: list[dict] = []  # {predicate, description}

    # ── Union predicates ──────────────────────────────────────────────────
    for pred in _UNION_PREDICATES:
        if pred not in by_pred:
            continue
        seen = set()
        for claim in by_pred[pred]:
            if claim["value"] not in seen:
                seen.add(claim["value"])
                resolved.append({
                    "predicate":         pred,
                    "value":             claim["value"],
                    "qualifier":         None,
                    "resolution_method": "union",
                })

    # ── Muscle claims ─────────────────────────────────────────────────────
    if "muscle" in by_pred:
        # Build {muscle_name: {source_role/degree}} per source
        # fed gives source_role (prime/secondary/tertiary), no feg degree
        # ffdb gives feg_name directly; source_role is also present
        muscle_claims = by_pred["muscle"]

        # Collect all unique muscle names first (union of presence)
        muscles_seen: dict[str, list[str]] = {}  # muscle → [qualifier from each claim]
        for c in muscle_claims:
            muscles_seen.setdefault(c["value"], []).append(c["qualifier"] or "")

        # For each muscle, determine the resolved degree:
        #   - If multiple sources both assert a recognisable feg degree → conservative (min)
        #   - If only one source has a degree hint → use it
        #   - If only source_role hints (fed) → map to degree hint (will be confirmed by LLM)
        for muscle, qualifiers in muscles_seen.items():
            feg_degrees = [q for q in qualifiers if q in _DEGREE_ORDER]
            role_hints  = [_ROLE_TO_DEGREE_HINT[q] for q in qualifiers if q in _ROLE_TO_DEGREE_HINT and q not in _DEGREE_ORDER]

            all_degrees = feg_degrees + role_hints
            if len(set(all_degrees)) == 1:
                degree = all_degrees[0]
                method = "consensus"
            elif len(all_degrees) > 1:
                # Conservative: use "weakest" (highest index) — least likely to over-claim
                # Actually in muscle context, conservative means the more modest claim
                # PrimeMover=0 is most specific; Stabilizer=2 is most conservative
                # We keep the one that is most modest (highest index)
                degree = max(all_degrees, key=lambda d: _DEGREE_ORDER.index(d))
                method = "conservative"
            elif all_degrees:
                degree = all_degrees[0]
                method = "coverage_gap"
            else:
                # No degree info at all — leave blank, enrich.py will fill
                degree = None
                method = "coverage_gap"

            resolved.append({
                "predicate":         "muscle",
                "value":             muscle,
                "qualifier":         degree,
                "resolution_method": method,
            })

        # Ancestor deduplication: if Quadriceps and RectusFemoris both present, drop Quadriceps
        muscle_names = {r["value"] for r in resolved if r["predicate"] == "muscle"}
        to_drop = set()
        for m in muscle_names:
            for anc in ancestor_map.get(m, frozenset()):
                if anc in muscle_names:
                    to_drop.add(anc)
        if to_drop:
            resolved = [
                r for r in resolved
                if not (r["predicate"] == "muscle" and r["value"] in to_drop)
            ]

    # ── Scalar predicates ──────────────────────────────────────────────────
    for pred in _SCALAR_PREDICATES:
        if pred not in by_pred:
            continue
        claims = by_pred[pred]
        values = {c["value"] for c in claims}
        if len(values) == 1:
            # Consensus or coverage gap — both the same
            method = "consensus" if len(claims) > 1 else "coverage_gap"
            resolved.append({
                "predicate":         pred,
                "value":             next(iter(values)),
                "qualifier":         None,
                "resolution_method": method,
            })
        else:
            # Conflict — defer
            desc = f"Sources disagree on {pred}: {', '.join(sorted(values))}"
            conflicts.append({"predicate": pred, "description": desc})

    # Write resolved_claims
    conn.executemany(
        """INSERT INTO resolved_claims (entity_id, predicate, value, qualifier, resolution_method)
           VALUES (?, ?, ?, ?, ?)""",
        [(entity_id, r["predicate"], r["value"], r["qualifier"], r["resolution_method"])
         for r in resolved],
    )

    # Write conflicts
    for c in conflicts:
        conn.execute(
            """INSERT INTO conflicts (entity_id, predicate, description, status)
               VALUES (?, ?, ?, 'deferred')""",
            (entity_id, c["predicate"], c["description"]),
        )


# ─── Main ────────────────────────────────────────────────────────────────────

def run(db_path=DB_PATH) -> dict:
    conn = get_connection(db_path)
    ancestor_map = _load_ancestor_map()

    entities = conn.execute("SELECT entity_id FROM entities").fetchall()

    with conn:
        conn.execute("DELETE FROM conflicts")
        conn.execute("DELETE FROM resolved_claims")

        for row in entities:
            _reconcile_entity(conn, row["entity_id"], ancestor_map)

    total_resolved = conn.execute("SELECT COUNT(*) FROM resolved_claims").fetchone()[0]
    total_conflicts = conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
    deferred = conn.execute(
        "SELECT COUNT(*) FROM conflicts WHERE status='deferred'"
    ).fetchone()[0]

    conn.close()
    return {
        "resolved_claims": total_resolved,
        "conflicts":       total_conflicts,
        "deferred":        deferred,
    }


def _print_triage(db_path=DB_PATH) -> None:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT c.conflict_id, c.entity_id, e.display_name, c.predicate, c.description
           FROM conflicts c JOIN entities e ON c.entity_id = e.entity_id
           WHERE c.status = 'deferred'
           ORDER BY c.predicate, c.entity_id"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No deferred conflicts.")
        return
    print(f"{len(rows)} deferred conflict(s):\n")
    for r in rows:
        print(f"  [{r['conflict_id']}] {r['display_name']} ({r['entity_id']})")
        print(f"       predicate: {r['predicate']}")
        print(f"       {r['description']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile source claims into resolved_claims.")
    parser.add_argument("--triage", action="store_true", help="Print deferred conflicts and exit")
    args = parser.parse_args()

    if args.triage:
        _print_triage()
        return

    stats = run()
    print(f"Resolved claims: {stats['resolved_claims']}")
    print(f"Conflicts:       {stats['conflicts']}")
    print(f"Deferred:        {stats['deferred']}")


if __name__ == "__main__":
    main()
