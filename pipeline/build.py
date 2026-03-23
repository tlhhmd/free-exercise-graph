"""
pipeline/build.py

Stage 5: Assemble graph.ttl from resolved_claims + inferred_claims.

For each canonical entity:
  1. Take all rows from resolved_claims (asserted facts from sources)
  2. Add inferred_claims for predicates NOT already covered by resolved_claims
     (asserted always takes precedence)
  3. Emit RDF triples per ADR-040 URI conventions

URI conventions (ADR-040):
  Exercise:    feg:ex_{entity_id}
  Involvement: feg:inv_ex_{entity_id}_{muscle}_{degree}

Output: graph.ttl (gitignored) in project root.

Usage:
    python3 pipeline/build.py
    python3 pipeline/build.py --output /path/to/graph.ttl
"""

import argparse
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import FEG_NS
from pipeline.db import DB_PATH, get_connection

FEG = Namespace(FEG_NS)
_ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "graph.ttl"


# ─── URI helpers ──────────────────────────────────────────────────────────────

def _ex_uri(entity_id: str) -> URIRef:
    safe = entity_id.replace("-", "_")
    return FEG[f"ex_{safe}"]


def _inv_uri(entity_id: str, muscle: str, degree: str) -> URIRef:
    safe = entity_id.replace("-", "_")
    return FEG[f"inv_ex_{safe}_{muscle}_{degree}"]


# ─── Effective claim computation ──────────────────────────────────────────────

def _effective_claims(conn, entity_id: str) -> dict[str, list[tuple[str, str | None]]]:
    """Return {predicate: [(value, qualifier)]} for one entity.

    Asserted (resolved_claims) takes precedence.
    Inferred (inferred_claims) fills predicates not in resolved_claims.
    """
    resolved = conn.execute(
        "SELECT predicate, value, qualifier FROM resolved_claims WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()

    inferred = conn.execute(
        "SELECT predicate, value, qualifier FROM inferred_claims WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()

    # Build resolved predicate set
    by_pred: dict[str, list[tuple]] = {}
    for r in resolved:
        by_pred.setdefault(r["predicate"], []).append((r["value"], r["qualifier"]))

    resolved_preds = set(by_pred.keys())

    # Inferred fills predicates not covered at all by resolved_claims.
    # Exception: joint_action_hint in resolved maps to primary/supporting in inferred —
    # we always use inferred for these two.
    inferred_fills = {"primary_joint_action", "supporting_joint_action", "training_modality"}
    for r in inferred:
        pred = r["predicate"]
        if pred in inferred_fills or pred not in resolved_preds:
            by_pred.setdefault(pred, []).append((r["value"], r["qualifier"]))

    # Scalar override: if resolved has is_compound/is_combination/laterality, don't also infer
    for scalar in ("is_compound", "is_combination", "laterality"):
        if scalar in resolved_preds and scalar in by_pred:
            # keep only resolved value (already there)
            pass

    return by_pred


# ─── RDF assembly ─────────────────────────────────────────────────────────────

def _add_entity(g: Graph, entity_id: str, display_name: str, claims: dict) -> None:
    uri = _ex_uri(entity_id)
    g.add((uri, RDF.type, FEG.Exercise))
    g.add((uri, RDFS.label, Literal(display_name, datatype=XSD.string)))
    g.add((uri, FEG.legacySourceId, Literal(entity_id, datatype=XSD.string)))

    # Equipment
    for eq, _ in claims.get("equipment", []):
        g.add((uri, FEG.equipment, FEG[eq]))

    # Muscle involvements
    muscle_claims = claims.get("muscle", [])
    for muscle, degree in muscle_claims:
        if degree is None:
            # Try to find degree from inferred muscle_involvements
            continue  # skip muscles with no degree — enrich should have filled this
        inv = _inv_uri(entity_id, muscle, degree)
        g.add((uri, FEG.hasInvolvement, inv))
        g.add((inv, RDF.type, FEG.MuscleInvolvement))
        g.add((inv, FEG.muscle, FEG[muscle]))
        g.add((inv, FEG.degree, FEG[degree]))

    # Movement patterns
    for mp, _ in claims.get("movement_pattern", []):
        g.add((uri, FEG.movementPattern, FEG[mp]))

    # Joint actions (from inferred only — resolved has hints, not primary/supporting split)
    for ja, _ in claims.get("primary_joint_action", []):
        g.add((uri, FEG.primaryJointAction, FEG[ja]))
    for ja, _ in claims.get("supporting_joint_action", []):
        g.add((uri, FEG.supportingJointAction, FEG[ja]))

    # Training modalities
    for tm, _ in claims.get("training_modality", []):
        g.add((uri, FEG.trainingModality, FEG[tm]))

    # Plane of motion
    for pom, _ in claims.get("plane_of_motion", []):
        g.add((uri, FEG.planeOfMotion, FEG[pom]))

    # Exercise style
    for es, _ in claims.get("exercise_style", []):
        g.add((uri, FEG.exerciseStyle, FEG[es]))

    # Laterality
    for laterality, _ in claims.get("laterality", []):
        g.add((uri, FEG.laterality, FEG[laterality]))

    # Boolean flags
    for pred, rdf_prop in [("is_compound", FEG.isCompound), ("is_combination", FEG.isCombination)]:
        for val, _ in claims.get(pred, []):
            bool_val = val == "true"
            g.add((uri, rdf_prop, Literal(bool_val, datatype=XSD.boolean)))


# ─── Main ─────────────────────────────────────────────────────────────────────

def build(output: Path = _DEFAULT_OUTPUT, db_path: Path = DB_PATH) -> int:
    """Build graph.ttl. Returns triple count."""
    g = Graph()

    # Load vocabulary
    vocab_files = [p for p in sorted(_ONTOLOGY_DIR.glob("*.ttl")) if p.name != "shapes.ttl"]
    print(f"Loading vocabulary ({len(vocab_files)} files)...")
    for ttl in vocab_files:
        g.parse(ttl, format="turtle")

    conn = get_connection(db_path)
    entities = conn.execute(
        "SELECT entity_id, display_name FROM entities ORDER BY entity_id"
    ).fetchall()
    enriched_ids = {r[0] for r in conn.execute("SELECT entity_id FROM enrichment_stamps").fetchall()}

    print(f"Assembling {len(entities)} entities ({len(enriched_ids)} enriched)...")
    for row in entities:
        entity_id    = row["entity_id"]
        display_name = row["display_name"]
        claims = _effective_claims(conn, entity_id)
        _add_entity(g, entity_id, display_name, claims)

    conn.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output), format="turtle")
    triple_count = len(g)
    print(f"Wrote {output} ({triple_count} triples)")
    return triple_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble graph.ttl from pipeline SQLite.")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(output=args.output)


if __name__ == "__main__":
    main()
