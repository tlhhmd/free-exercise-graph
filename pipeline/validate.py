"""
pipeline/validate.py

Data quality scorecard for the free-exercise-graph.

Reports on five dimensions (ADR-095):

  Dimension     Severity  What it checks
  ──────────────────────────────────────────────────────────────────────────
  validity      fail      SHACL conformance of graph.ttl
  uniqueness    fail      Duplicate exercise labels
  integrity     fail      Vocab references in inferred_claims that don't
                          resolve to a known ontology term
  timeliness    warn      enrichment_warnings not yet resolved via --restamp
  completeness  warn      Exercises missing movementPattern, hasInvolvement,
                          primaryJointAction; involvements missing degree

Note: accuracy (are enrichment assignments correct?) is out of scope here —
that is the domain of eval.py + gold standard annotation.

Usage:
    python3 pipeline/validate.py
    python3 pipeline/validate.py --graph /path/to/graph.ttl
    python3 pipeline/validate.py --db-path /path/to/pipeline.db
    python3 pipeline/validate.py --verbose          # list offending entities
    python3 pipeline/validate.py --json             # machine-readable output

Exit codes:
    0 — no failures (warnings allowed)
    1 — one or more failures

Note on SHACL performance: pyshacl uses the oxrdflib backend (Oxigraph store) for
SPARQL-accelerated validation (~45s on the full graph vs ~10min with pure rdflib).
Validity is skipped by default for fast iteration. Use --shacl to run it.
For unit-level shape testing, use test_shacl.py.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pyshacl
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, SH

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import FEG_NS
from pipeline.db import DB_PATH, get_connection

FEG = Namespace(FEG_NS)

_ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"
_DEFAULT_GRAPH = _PROJECT_ROOT / "graph.ttl"

# Maps inferred_claims predicate → vocab key used in extract_vocab_sets()
_PREDICATE_VOCAB_KEY: dict[str, str] = {
    "muscle":                 "muscles",
    "movement_pattern":       "movement_patterns",
    "primary_joint_action":   "joint_actions",
    "supporting_joint_action":"joint_actions",
    "training_modality":      "training_modalities",
    "plane_of_motion":        "planes_of_motion",
    "exercise_style":         "exercise_styles",
    "laterality":             "laterality",
}


# ─── Result types ─────────────────────────────────────────────────────────────

@dataclass
class DimensionResult:
    name: str
    status: str          # "PASS" | "WARN" | "FAIL"
    summary: str
    detail: list[str] = field(default_factory=list)


# ─── Ontology loading ─────────────────────────────────────────────────────────

_STEM_REMAP = {
    "involvement_degrees": "degrees",
    "training_modalities": "modalities",
}


def _load_ontology_graphs() -> dict[str, Graph]:
    """Load all ontology TTL files (shapes excluded) keyed by stem.

    Some stems are remapped to match the keys expected by extract_vocab_sets():
      involvement_degrees → degrees
      training_modalities → modalities
    """
    graphs: dict[str, Graph] = {}
    for ttl in sorted(_ONTOLOGY_DIR.glob("*.ttl")):
        if ttl.name == "shapes.ttl":
            continue
        g = Graph()
        g.parse(ttl, format="turtle")
        key = _STEM_REMAP.get(ttl.stem, ttl.stem)
        graphs[key] = g
    return graphs


def _build_vocab_sets(graphs: dict[str, Graph]) -> dict[str, frozenset[str]]:
    """Return {vocab_key: {local_name, ...}} using the same logic as enrichment/_vocab.py."""
    from enrichment._vocab import extract_vocab_sets
    return {k: frozenset(v) for k, v in extract_vocab_sets(graphs, FEG).items()}


# ─── Dimension: Validity ──────────────────────────────────────────────────────

def check_validity(graph_path: Path, run_shacl: bool = False) -> DimensionResult:
    if not run_shacl:
        return DimensionResult(
            "Validity", "PASS",
            "Skipped (use --shacl to run; slow on full graph). Shape unit tests: test_shacl.py",
        )

    if not graph_path.exists():
        return DimensionResult(
            "Validity", "FAIL",
            f"graph.ttl not found at {graph_path} — run pipeline/build.py first",
        )

    # Use oxrdflib (Oxigraph) store for SPARQL-accelerated validation (~45s vs ~10min)
    data_graph = Graph(store="Oxigraph")
    data_graph.parse(graph_path, format="turtle")

    shapes_graph = Graph()
    shapes_graph.parse(_ONTOLOGY_DIR / "shapes.ttl", format="turtle")

    conforms, results_graph, _ = pyshacl.validate(data_graph, shacl_graph=shapes_graph)

    if conforms:
        ex_count = sum(1 for _ in data_graph.subjects(RDF.type, FEG.Exercise))
        return DimensionResult("Validity", "PASS", f"0 violations across {ex_count:,} exercises")

    violations = list(results_graph.subjects(RDF.type, SH.ValidationResult))
    detail = []
    for v in violations[:50]:
        msg = results_graph.value(v, SH.resultMessage)
        focus = results_graph.value(v, SH.focusNode)
        detail.append(f"  {focus} — {msg}")

    overflow = len(violations) - 50
    if overflow > 0:
        detail.append(f"  … and {overflow} more")

    return DimensionResult(
        "Validity", "FAIL",
        f"{len(violations)} SHACL violation(s)",
        detail,
    )


# ─── Dimension: Uniqueness ────────────────────────────────────────────────────

def check_uniqueness(graph_path: Path) -> DimensionResult:
    if not graph_path.exists():
        return DimensionResult("Uniqueness", "FAIL", "graph.ttl not found — run build.py first")

    data_graph = Graph()
    data_graph.parse(graph_path, format="turtle")

    # Collect all exercise labels
    label_to_uris: dict[str, list[str]] = {}
    for ex in data_graph.subjects(RDF.type, FEG.Exercise):
        for label in data_graph.objects(ex, RDFS.label):
            key = str(label).strip().lower()
            label_to_uris.setdefault(key, []).append(str(ex))

    duplicates = {label: uris for label, uris in label_to_uris.items() if len(uris) > 1}

    if not duplicates:
        return DimensionResult("Uniqueness", "PASS", "0 duplicate exercise labels")

    detail = []
    for label, uris in sorted(duplicates.items()):
        detail.append(f"  {label!r}: {', '.join(uris)}")

    return DimensionResult(
        "Uniqueness", "FAIL",
        f"{len(duplicates)} duplicate exercise label(s)",
        detail,
    )


# ─── Dimension: Integrity ─────────────────────────────────────────────────────

def check_integrity(vocab_sets: dict[str, frozenset[str]], db_path: Path = DB_PATH) -> DimensionResult:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT entity_id, predicate, value, qualifier FROM inferred_claims"
    ).fetchall()
    conn.close()

    bad: list[str] = []

    for row in rows:
        entity_id = row["entity_id"]
        predicate = row["predicate"]
        value = row["value"]
        qualifier = row["qualifier"]

        # Check value against its vocab set
        vocab_key = _PREDICATE_VOCAB_KEY.get(predicate)
        if vocab_key and value not in vocab_sets.get(vocab_key, frozenset()):
            bad.append(f"  {entity_id}  {predicate}={value!r} (not in {vocab_key})")

        # Check qualifier (degree) for muscle claims
        if predicate == "muscle" and qualifier is not None:
            if qualifier not in vocab_sets.get("degrees", frozenset()):
                bad.append(f"  {entity_id}  muscle={value!r} degree={qualifier!r} (unknown degree)")

    if not bad:
        return DimensionResult("Integrity", "PASS", "All vocab references resolve")

    return DimensionResult(
        "Integrity", "FAIL",
        f"{len(bad)} unresolvable vocab reference(s) in inferred_claims",
        bad[:50] + ([f"  … and {len(bad) - 50} more"] if len(bad) > 50 else []),
    )


# ─── Dimension: Timeliness ────────────────────────────────────────────────────

def check_timeliness(db_path: Path = DB_PATH) -> DimensionResult:
    conn = get_connection(db_path)

    # Unresolved warnings: entity not re-enriched since the warning was recorded
    rows = conn.execute("""
        SELECT ew.entity_id, ew.predicate, ew.stripped_value, ew.enriched_at AS warned_at
        FROM enrichment_warnings ew
        JOIN enrichment_stamps es ON es.entity_id = ew.entity_id
        WHERE es.enriched_at <= ew.enriched_at
        ORDER BY ew.stripped_value, ew.entity_id
    """).fetchall()
    conn.close()

    if not rows:
        return DimensionResult("Timeliness", "PASS", "No unresolved enrichment warnings")

    # Group by stripped_value for summary
    by_term: dict[str, list[str]] = {}
    for row in rows:
        by_term.setdefault(row["stripped_value"], []).append(row["entity_id"])

    term_summary = ", ".join(
        f"{term!r} ({len(entities)} exercise{'s' if len(entities) != 1 else ''})"
        for term, entities in sorted(by_term.items())
    )
    detail = []
    for term, entities in sorted(by_term.items()):
        detail.append(f"  {term!r}: {len(entities)} exercise(s) not yet restamped")
        for eid in entities[:5]:
            detail.append(f"    - {eid}")
        if len(entities) > 5:
            detail.append(f"    … and {len(entities) - 5} more")

    return DimensionResult(
        "Timeliness", "WARN",
        f"{len(rows)} unresolved warning(s) across {len(by_term)} term(s): {term_summary}",
        detail,
    )


# ─── Dimension: Completeness ──────────────────────────────────────────────────

def check_completeness(db_path: Path = DB_PATH) -> DimensionResult:
    conn = get_connection(db_path)

    total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    def missing(predicate: str, exempt_passive: bool = False) -> list[str]:
        """Entity IDs missing the given predicate in both resolved and inferred claims."""
        base = """
            SELECT e.entity_id FROM entities e
            WHERE e.entity_id NOT IN (
                SELECT DISTINCT entity_id FROM inferred_claims  WHERE predicate = ?
                UNION
                SELECT DISTINCT entity_id FROM resolved_claims  WHERE predicate = ?
            )
        """
        if exempt_passive:
            # Exempt exercises where all involvements are PassiveTarget
            base += """
                AND e.entity_id NOT IN (
                    SELECT DISTINCT entity_id FROM inferred_claims
                    WHERE predicate = 'muscle' AND qualifier = 'PassiveTarget'
                )
            """
        return [r[0] for r in conn.execute(base, (predicate, predicate)).fetchall()]

    # Involvements missing a degree
    no_degree = conn.execute("""
        SELECT COUNT(*) FROM inferred_claims
        WHERE predicate = 'muscle' AND (qualifier IS NULL OR qualifier = '')
    """).fetchone()[0]

    missing_pattern   = missing("movement_pattern")
    missing_involve   = missing("muscle")
    missing_pja       = missing("primary_joint_action", exempt_passive=True)

    conn.close()

    issues = []
    if missing_pattern:
        issues.append(f"{len(missing_pattern):,}/{total:,} exercises missing movementPattern")
    if missing_involve:
        issues.append(f"{len(missing_involve):,}/{total:,} exercises missing muscle involvements")
    if missing_pja:
        issues.append(f"{len(missing_pja):,}/{total:,} exercises missing primaryJointAction (passive exempt)")
    if no_degree:
        issues.append(f"{no_degree:,} muscle involvement(s) missing degree")

    detail = []
    def _sample(label: str, entity_ids: list[str], limit: int = 10) -> None:
        if not entity_ids:
            return
        detail.append(f"  {label} ({len(entity_ids):,} total):")
        for eid in entity_ids[:limit]:
            detail.append(f"    - {eid}")
        if len(entity_ids) > limit:
            detail.append(f"    … and {len(entity_ids) - limit} more")

    _sample("missing movementPattern", missing_pattern)
    _sample("missing muscle involvements", missing_involve)
    _sample("missing primaryJointAction", missing_pja)

    if not issues:
        return DimensionResult("Completeness", "PASS", f"All expected fields present across {total:,} exercises")

    return DimensionResult(
        "Completeness", "WARN",
        "; ".join(issues),
        detail,
    )


# ─── Reporting ────────────────────────────────────────────────────────────────

_STATUS_SYMBOL = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}
_COL_WIDTH = 14


def _print_scorecard(results: list[DimensionResult], verbose: bool) -> None:
    print("\nData Quality Scorecard — free-exercise-graph")
    print("─" * 60)
    print(f"  {'Dimension':<{_COL_WIDTH}}  {'Status':<6}  Summary")
    print("─" * 60)
    for r in results:
        sym = _STATUS_SYMBOL[r.status]
        print(f"  {r.name:<{_COL_WIDTH}}  {sym} {r.status:<5}  {r.summary}")
    print("─" * 60)

    if verbose:
        for r in results:
            if r.detail:
                print(f"\n  [{r.name}]")
                for line in r.detail:
                    print(line)

    fails = sum(1 for r in results if r.status == "FAIL")
    warns = sum(1 for r in results if r.status == "WARN")
    print(f"\n  {fails} failure(s)  {warns} warning(s)\n")


def _print_json(results: list[DimensionResult]) -> None:
    out = [
        {"dimension": r.name, "status": r.status, "summary": r.summary, "detail": r.detail}
        for r in results
    ]
    print(json.dumps(out, indent=2))


def run_scorecard(
    *,
    graph_path: Path = _DEFAULT_GRAPH,
    run_shacl: bool = False,
    db_path: Path = DB_PATH,
) -> list[DimensionResult]:
    ontology_graphs = _load_ontology_graphs()
    vocab_sets = _build_vocab_sets(ontology_graphs)
    return [
        check_validity(graph_path, run_shacl=run_shacl),
        check_uniqueness(graph_path),
        check_integrity(vocab_sets, db_path=db_path),
        check_timeliness(db_path=db_path),
        check_completeness(db_path=db_path),
    ]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="FEG data quality scorecard")
    parser.add_argument("--graph", type=Path, default=_DEFAULT_GRAPH,
                        help="Path to graph.ttl (default: project root)")
    parser.add_argument("--db-path", type=Path, default=DB_PATH,
                        help="Path to pipeline SQLite database (default: pipeline/pipeline.db)")
    parser.add_argument("--shacl", action="store_true",
                        help="Run full SHACL validation (slow on large graphs)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print offending entities per dimension")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")
    args = parser.parse_args()

    results = run_scorecard(graph_path=args.graph, run_shacl=args.shacl, db_path=args.db_path)

    if args.json:
        _print_json(results)
    else:
        _print_scorecard(results, verbose=args.verbose)

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
