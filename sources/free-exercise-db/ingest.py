#!/usr/bin/env python3
"""
ingest.py — Run morph-KGC mappings, apply enrichment, repair, and produce ingested.ttl.

Usage:
    python3 sources/free-exercise-db/ingest.py

Requires exercises_normalized.json to exist (run preprocess.py first).
Executes the YARRRML mapping via morph-KGC, merges ontology vocabulary files,
layers on LLM enrichment data from exercises_enriched.json (if present), applies
SPARQL UPDATE repair queries from the queries/ subfolder, and serialises to
sources/free-exercise-db/ingested.ttl.
"""

import json
import os
from pathlib import Path

import morph_kgc
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, XSD

SOURCE_DIR = Path(__file__).resolve().parent  # sources/free-exercise-db/
PROJECT_ROOT = SOURCE_DIR.parent.parent  # project root
CONFIG_PATH = SOURCE_DIR / "mappings" / "morphkgc.ini"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
QUERIES_DIR = SOURCE_DIR / "queries"
ENRICHED_DIR = SOURCE_DIR / "enriched"
OUTPUT_PATH = SOURCE_DIR / "ingested.ttl"

FEG = Namespace("https://placeholder.url#")


def _sanitize_id(raw_id: str) -> str:
    return raw_id.replace("-", "_")


def _apply_enrichment(g, enriched: list[dict]) -> None:
    """Replace raw muscle involvements with enriched data and add movement
    patterns, training modalities, and isUnilateral for each enriched exercise."""
    for ex in enriched:
        ex_uri = FEG[f"ex_{_sanitize_id(ex['id'])}"]

        # Remove raw MuscleInvolvement nodes ingested from source data
        for inv in list(g.objects(ex_uri, FEG.hasInvolvement)):
            g.remove((ex_uri, FEG.hasInvolvement, inv))
            for triple in list(g.triples((inv, None, None))):
                g.remove(triple)

        # Add enriched muscle involvements
        for mi in ex.get("muscle_involvements", []):
            muscle, degree = mi["muscle"], mi["degree"]
            inv_uri = FEG[f"inv_ex_{_sanitize_id(ex['id'])}_{muscle}_{degree}"]
            g.add((ex_uri, FEG.hasInvolvement, inv_uri))
            g.add((inv_uri, RDF.type, FEG.MuscleInvolvement))
            g.add((inv_uri, FEG.muscle, FEG[muscle]))
            g.add((inv_uri, FEG.degree, FEG[degree]))

        # Add movement patterns
        for mp in ex.get("movement_patterns", []):
            g.add((ex_uri, FEG.movementPattern, FEG[mp]))

        # Add training modalities
        for tm in ex.get("training_modalities", []):
            g.add((ex_uri, FEG.trainingModality, FEG[tm]))

        # Add joint actions (new split format; fall back to legacy flat list)
        for ja in ex.get("primary_joint_actions", []):
            g.add((ex_uri, FEG.primaryJointAction, FEG[ja]))
        for ja in ex.get("supporting_joint_actions", []):
            g.add((ex_uri, FEG.supportingJointAction, FEG[ja]))
        # Legacy: exercises enriched before ADR-058 carry a flat joint_actions list
        if not ex.get("primary_joint_actions") and not ex.get("supporting_joint_actions"):
            for ja in ex.get("joint_actions", []):
                g.add((ex_uri, FEG.jointAction, FEG[ja]))

        # Add isCompound if present
        if "is_compound" in ex:
            g.add((ex_uri, FEG.isCompound, Literal(ex["is_compound"], datatype=XSD.boolean)))

        # Add isUnilateral if true
        if ex.get("is_unilateral"):
            g.add((ex_uri, FEG.isUnilateral, Literal(True, datatype=XSD.boolean)))


def main():
    # morph-KGC resolves relative paths from cwd; ensure we're at project root.
    os.chdir(PROJECT_ROOT)

    print("Running morph-KGC mappings...")
    data_graph = morph_kgc.materialize(str(CONFIG_PATH))
    print(f"  Data triples materialised: {len(data_graph)}")

    enriched_files = sorted(ENRICHED_DIR.glob("*.json")) if ENRICHED_DIR.exists() else []
    if enriched_files:
        enriched = [json.loads(p.read_text()) for p in enriched_files]
        before = len(data_graph)
        _apply_enrichment(data_graph, enriched)
        delta = len(data_graph) - before
        print(f"Enrichment applied: {len(enriched)} exercises, {delta:+d} triples")
    else:
        print("No enriched data found — skipping enrichment layer.")

    print("Merging vocabulary files...")
    for ttl_path in sorted(ONTOLOGY_DIR.glob("*.ttl")):
        if ttl_path.name != "shapes.ttl":
            data_graph.parse(ttl_path, format="turtle")
            print(f"  Loaded {ttl_path.name}")

    repair_queries = sorted(QUERIES_DIR.glob("repair_*.rq"))
    if repair_queries:
        print("Applying repair queries...")
        for query_path in repair_queries:
            before = len(data_graph)
            data_graph.update(query_path.read_text())
            delta = len(data_graph) - before
            print(f"  {query_path.name}: {delta:+d} triples")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data_graph.serialize(destination=str(OUTPUT_PATH), format="turtle")
    print(f"Output written: {OUTPUT_PATH}")
    print(f"Total triples: {len(data_graph)}")


if __name__ == "__main__":
    main()
