#!/usr/bin/env python3
"""
validate.py — Validate enriched exercises in ingested.ttl against SHACL shapes.

Usage:
    python3 sources/free-exercise-db/validate.py

Loads ingested.ttl and ontology/shapes.ttl. Filters to enriched exercises only
(those with at least one feg:movementPattern) before running SHACL validation.
Raw unenriched exercises are not checked. Exits 0 if the graph conforms, 1 if
violations are found.
"""

import sys
from pathlib import Path

import pyshacl
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, SH

SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent.parent
INGESTED_TTL = SOURCE_DIR / "ingested.ttl"
SHAPES_TTL = PROJECT_ROOT / "ontology" / "shapes.ttl"

FEG = Namespace("https://placeholder.url#")
FEG_STR = "https://placeholder.url#"


def filter_enriched(data: Graph) -> tuple[Graph, int, int]:
    """Remove unenriched exercises (no movementPattern) and their involvements.

    Returns (filtered_graph, total_exercises, enriched_count).
    """
    all_exercises = set(data.subjects(RDF.type, FEG.Exercise))
    enriched = set(data.subjects(FEG.movementPattern, None))
    unenriched = all_exercises - enriched

    for ex in unenriched:
        for inv in list(data.objects(ex, FEG.hasInvolvement)):
            for tp, to in list(data.predicate_objects(inv)):
                data.remove((inv, tp, to))
        for p, o in list(data.predicate_objects(ex)):
            data.remove((ex, p, o))

    return data, len(all_exercises), len(enriched)


def main():
    data = Graph().parse(INGESTED_TTL, format="turtle")
    shapes = Graph().parse(SHAPES_TTL, format="turtle")

    data, total, enriched_count = filter_enriched(data)
    print(f"Validating {enriched_count}/{total} enriched exercises\n")

    conforms, results_graph, _ = pyshacl.validate(
        data,
        shacl_graph=shapes,
    )

    if conforms:
        print("Conforms: yes")
        sys.exit(0)

    count = 0
    for result in results_graph.subjects(SH.resultMessage, None):
        msg = str(results_graph.value(result, SH.resultMessage))
        focus = results_graph.value(result, SH.focusNode)
        label = data.value(focus, RDFS.label)
        node = (
            f"{str(focus).replace(FEG_STR, 'feg:')} ({label})"
            if label
            else str(focus).replace(FEG_STR, "feg:")
        )
        print(f"{node} — {msg}")
        count += 1

    print(f"\n{count} violation(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
