#!/usr/bin/env python3
"""
build.py — Assemble ingested.ttl from enriched JSON files.

Reads enriched/*.json (produced by enrich.py) and serializes to ingested.ttl.
Equipment is already resolved to feg: local names in the enriched files.

Usage:
    python3 sources/functional-fitness-db/build.py
"""

import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

SOURCE_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS

ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
ENRICHED_DIR = SOURCE_DIR / "enriched"
OUTPUT_PATH  = SOURCE_DIR / "ingested.ttl"

FEG = Namespace(FEG_NS)


def _add_exercise(g: Graph, ex: dict) -> None:
    uri = FEG[f"ex_ffdb_{ex['id']}"]
    g.add((uri, RDF.type, FEG.Exercise))
    g.add((uri, RDFS.label, Literal(ex["name"], datatype=XSD.string)))
    g.add((uri, FEG.legacySourceId, Literal(ex["id"], datatype=XSD.string)))

    for eq in ex.get("equipment", []):
        g.add((uri, FEG.equipment, FEG[eq]))

    for mi in ex.get("muscle_involvements", []):
        muscle, degree = mi["muscle"], mi["degree"]
        inv_uri = FEG[f"inv_ex_ffdb_{ex['id']}_{muscle}_{degree}"]
        g.add((uri, FEG.hasInvolvement, inv_uri))
        g.add((inv_uri, RDF.type, FEG.MuscleInvolvement))
        g.add((inv_uri, FEG.muscle, FEG[muscle]))
        g.add((inv_uri, FEG.degree, FEG[degree]))

    for mp in ex.get("movement_patterns", []):
        g.add((uri, FEG.movementPattern, FEG[mp]))

    for tm in ex.get("training_modalities", []):
        g.add((uri, FEG.trainingModality, FEG[tm]))

    for ja in ex.get("primary_joint_actions", []):
        g.add((uri, FEG.primaryJointAction, FEG[ja]))

    for ja in ex.get("supporting_joint_actions", []):
        g.add((uri, FEG.supportingJointAction, FEG[ja]))

    if (v := ex.get("is_compound")) is not None:
        g.add((uri, FEG.isCompound, Literal(v, datatype=XSD.boolean)))

    if (v := ex.get("is_combination")) is not None:
        g.add((uri, FEG.isCombination, Literal(v, datatype=XSD.boolean)))

    if laterality := ex.get("laterality"):
        g.add((uri, FEG.laterality, FEG[laterality]))

    for pom in ex.get("plane_of_motion", []):
        g.add((uri, FEG.planeOfMotion, FEG[pom]))

    for es in ex.get("exercise_style", []):
        g.add((uri, FEG.exerciseStyle, FEG[es]))


def main() -> None:
    g = Graph()

    vocab_files = [p for p in sorted(ONTOLOGY_DIR.glob("*.ttl")) if p.name != "shapes.ttl"]
    print(f"Loading vocabulary ({len(vocab_files)} files)...")
    for ttl in vocab_files:
        g.parse(ttl, format="turtle")

    enriched_files = sorted(ENRICHED_DIR.glob("*.json")) if ENRICHED_DIR.exists() else []
    print(f"Adding {len(enriched_files)} exercise(s)...")
    for path in enriched_files:
        _add_exercise(g, json.loads(path.read_text()))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(OUTPUT_PATH), format="turtle")
    print(f"Wrote {OUTPUT_PATH} ({g.__len__()} triples)")


if __name__ == "__main__":
    main()
