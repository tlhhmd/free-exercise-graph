#!/usr/bin/env python3
"""
build.py — Assemble ingested.ttl from enriched JSON and ontology vocabulary files.

Replaces ingest.py + morph-KGC. Pure Python JSON→RDF assembly — no mapping
framework, no repair passes, no intermediate normalized JSON.

Steps:
  1  Load all ontology vocabulary files (excluding shapes.ttl)
  2  Read equipment crosswalk CSV → {source_string: feg_local_name}
  3  For each exercise in exercises.json: add basic metadata triples
  4  For each enriched exercise: add enrichment triples (overwrites no source data —
     unenriched exercises simply lack the enrichment properties)
  5  Serialize to ingested.ttl

Usage:
    python3 sources/free-exercise-db/build.py
"""

import csv
import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent.parent
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS
from telemetry import PipelineRun


def _sanitize_id(raw_id: str) -> str:
    """Replace hyphens with underscores in exercise IDs for URI construction (ADR-064)."""
    return raw_id.replace("-", "_")

# ── Paths ─────────────────────────────────────────────────────────────────────

ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
EXERCISES_PATH = SOURCE_DIR / "raw" / "exercises.json"
ENRICHED_DIR = SOURCE_DIR / "enriched"
EQUIPMENT_CROSSWALK = SOURCE_DIR / "mappings" / "equipment_crosswalk.csv"
OUTPUT_PATH = SOURCE_DIR / "ingested.ttl"

FEG = Namespace(FEG_NS)


# ── Assembly ──────────────────────────────────────────────────────────────────


def _load_equipment_map() -> dict[str, str]:
    """Return {source_string: feg_local_name} from equipment_crosswalk.csv."""
    result: dict[str, str] = {}
    with EQUIPMENT_CROSSWALK.open() as f:
        for row in csv.DictReader(f):
            result[row["source_string"]] = row["feg_local_name"]
    return result


def _add_exercise(g: Graph, ex: dict, equip_map: dict[str, str]) -> None:
    """Add basic Exercise triples for one source exercise."""
    uri = FEG[f"ex_{_sanitize_id(ex['id'])}"]
    g.add((uri, RDF.type, FEG.Exercise))
    g.add((uri, RDFS.label, Literal(ex["name"], datatype=XSD.string)))
    g.add((uri, FEG.legacySourceId, Literal(ex["id"], datatype=XSD.string)))
    if eq := equip_map.get(ex.get("equipment", "") or ""):
        g.add((uri, FEG.equipment, FEG[eq]))


def _add_enrichment(g: Graph, ex: dict) -> None:
    """Add enrichment triples for one enriched exercise."""
    ex_uri = FEG[f"ex_{_sanitize_id(ex['id'])}"]

    for mi in ex.get("muscle_involvements", []):
        muscle, degree = mi["muscle"], mi["degree"]
        inv_uri = FEG[f"inv_ex_{_sanitize_id(ex['id'])}_{muscle}_{degree}"]
        g.add((ex_uri, FEG.hasInvolvement, inv_uri))
        g.add((inv_uri, RDF.type, FEG.MuscleInvolvement))
        g.add((inv_uri, FEG.muscle, FEG[muscle]))
        g.add((inv_uri, FEG.degree, FEG[degree]))

    for mp in ex.get("movement_patterns", []):
        g.add((ex_uri, FEG.movementPattern, FEG[mp]))

    for tm in ex.get("training_modalities", []):
        g.add((ex_uri, FEG.trainingModality, FEG[tm]))

    for ja in ex.get("primary_joint_actions", []):
        g.add((ex_uri, FEG.primaryJointAction, FEG[ja]))

    for ja in ex.get("supporting_joint_actions", []):
        g.add((ex_uri, FEG.supportingJointAction, FEG[ja]))

    if (is_compound := ex.get("is_compound")) is not None:
        g.add((ex_uri, FEG.isCompound, Literal(is_compound, datatype=XSD.boolean)))

    if (is_combination := ex.get("is_combination")) is not None:
        g.add((ex_uri, FEG.isCombination, Literal(is_combination, datatype=XSD.boolean)))

    if laterality := ex.get("laterality"):
        g.add((ex_uri, FEG.laterality, FEG[laterality]))

    for pom in ex.get("plane_of_motion", []):
        g.add((ex_uri, FEG.planeOfMotion, FEG[pom]))

    for es in ex.get("exercise_style", []):
        g.add((ex_uri, FEG.exerciseStyle, FEG[es]))

    # Deprecated — kept during migration for exercises not yet re-enriched
    if ex.get("is_unilateral") and not ex.get("laterality"):
        g.add((ex_uri, FEG.isUnilateral, Literal(True, datatype=XSD.boolean)))


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> Path:
    run = PipelineRun("build")
    g = Graph()

    # 1 — Vocabulary
    vocab_files = [p for p in sorted(ONTOLOGY_DIR.glob("*.ttl")) if p.name != "shapes.ttl"]
    with run.step_graph(f"vocabulary ({len(vocab_files)} files)", g):
        for ttl in vocab_files:
            g.parse(ttl, format="turtle")

    # 2 — Source exercises
    equip_map = _load_equipment_map()
    exercises = json.loads(EXERCISES_PATH.read_text())
    with run.step_graph(f"source exercises ({len(exercises)})", g):
        for ex in exercises:
            _add_exercise(g, ex, equip_map)

    # 3 — Enrichment layer
    enriched_files = sorted(ENRICHED_DIR.glob("*.json")) if ENRICHED_DIR.exists() else []
    with run.step_graph(f"enrichment ({len(enriched_files)} exercises)", g):
        for path in enriched_files:
            _add_enrichment(g, json.loads(path.read_text()))

    # 4 — Serialize
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with run.step_graph(f"serialize → {OUTPUT_PATH.name}", g):
        g.serialize(destination=str(OUTPUT_PATH), format="turtle")

    return run.finish()


if __name__ == "__main__":
    main()
