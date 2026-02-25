"""
validate_graph.py

Validates enriched exercise RDF data against SHACL shapes.

Inputs:
    data/graph/exercises_enriched.ttl  - encoded RDF from encode.py
    ontology/shapes.ttl                - SHACL shapes

Outputs:
    data/graph/exercises.ttl           - passing exercises
    data/graph/quarantine.ttl          - failing exercises and their MuscleInvolvement
    data/graph/validation_report.jsonl - one record per failing exercise
    logs/validate_graph.log            - operational log

Usage:
    python pipeline/validate_graph.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import RDFS

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
ENRICHED_PATH = ROOT / "data" / "graph" / "exercises_enriched.ttl"
SHAPES_PATH = ROOT / "ontology" / "shapes.ttl"
ONTOLOGY_PATH = ROOT / "ontology" / "ontology.ttl"
OUTPUT_PATH = ROOT / "data" / "graph" / "exercises.ttl"
QUARANTINE_PATH = ROOT / "data" / "graph" / "quarantine.ttl"
REPORT_PATH = ROOT / "data" / "graph" / "validation_report.jsonl"
LOG_PATH = ROOT / "logs" / "validate_graph.log"

FEG = Namespace("https://placeholder.url#")
SH = Namespace("http://www.w3.org/ns/shacl#")

# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ─── Load graphs ──────────────────────────────────────────────────────────────


def load_graphs():
    """Load enriched data, ontology, and shapes graphs from disk."""
    log.info("Loading enriched graph from %s", ENRICHED_PATH)
    data_graph = Graph()
    data_graph.parse(ENRICHED_PATH, format="turtle")
    log.info("Loaded %d triples", len(data_graph))

    log.info("Loading ontology from %s", ONTOLOGY_PATH)
    ontology_graph = Graph()
    ontology_graph.parse(ONTOLOGY_PATH, format="turtle")

    log.info("Loading shapes from %s", SHAPES_PATH)
    shapes_graph = Graph()
    shapes_graph.parse(SHAPES_PATH, format="turtle")

    return data_graph, ontology_graph, shapes_graph


# ─── Run SHACL validation ─────────────────────────────────────────────────────


def run_validation(data_graph, ontology_graph, shapes_graph):
    """Run pyshacl and return conformance flag and results graph."""
    log.info("Running SHACL validation...")
    conforms, results_graph, _ = validate(
        data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="rdfs",
        abort_on_first=False,
    )
    log.info("Validation complete - conforms: %s", conforms)
    return conforms, results_graph


# ─── Extract failing exercises ────────────────────────────────────────────────


def get_failing_exercises(results_graph, data_graph):
    """
    Parse the SHACL results graph to find failing exercise URIs
    and their violation details.
    Returns a dict: { exercise_uri: [violation_messages] }
    """
    failures = {}

    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        focus = results_graph.value(result, SH.focusNode)
        message = results_graph.value(result, SH.resultMessage)

        if focus is None:
            continue

        exercise_uri = resolve_to_exercise(focus, data_graph)

        if exercise_uri is None:
            continue

        if exercise_uri not in failures:
            failures[exercise_uri] = []

        if message:
            failures[exercise_uri].append(str(message))

    return failures


def resolve_to_exercise(focus_uri, data_graph):
    """
    Given a focus node URI, return the Exercise URI it belongs to.
    If the focus is already an Exercise, return it directly.
    If it is a MuscleInvolvement, traverse back via hasInvolvement.
    Returns None if the focus cannot be resolved to an Exercise.
    """
    if (focus_uri, RDF.type, FEG.Exercise) in data_graph:
        return focus_uri

    for exercise in data_graph.subjects(FEG.hasInvolvement, focus_uri):
        return exercise

    return None


# ─── Collect MuscleInvolvement nodes for an exercise ─────────────────────────


def get_involvement_nodes(exercise_uri, data_graph):
    """
    Return all MuscleInvolvement URIs associated with an exercise
    via feg:hasInvolvement.
    """
    return list(data_graph.objects(exercise_uri, FEG.hasInvolvement))


# ─── Split graph into passing and failing ─────────────────────────────────────


def split_graph(data_graph, failing_exercises):
    """
    Split data_graph into passing and quarantine graphs.
    Quarantine contains failing exercises and all their
    MuscleInvolvement nodes. Passing contains everything else.
    """
    passing = Graph()
    quarantine = Graph()

    quarantine_uris = set(failing_exercises.keys())
    for exercise_uri in failing_exercises:
        for inv_node in get_involvement_nodes(exercise_uri, data_graph):
            quarantine_uris.add(inv_node)

    for prefix, namespace in data_graph.namespaces():
        passing.bind(prefix, namespace)
        quarantine.bind(prefix, namespace)

    for subject, predicate, obj in data_graph:
        if isinstance(subject, URIRef) and subject in quarantine_uris:
            quarantine.add((subject, predicate, obj))
        else:
            passing.add((subject, predicate, obj))

    return passing, quarantine


# ─── Write validation report ──────────────────────────────────────────────────


def write_report(failing_exercises, data_graph, pass_count, fail_count):
    """
    Write a JSONL validation report. First line is a summary record.
    Subsequent lines are one record per failing exercise.
    """
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now(timezone.utc).isoformat()

    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        summary = {
            "record_type": "summary",
            "timestamp": run_timestamp,
            "total": pass_count + fail_count,
            "passed": pass_count,
            "failed": fail_count,
        }
        report_file.write(json.dumps(summary) + "\n")

        for exercise_uri, messages in failing_exercises.items():
            label = data_graph.value(URIRef(exercise_uri), RDFS.label)
            record = {
                "record_type": "failure",
                "timestamp": run_timestamp,
                "exercise_uri": str(exercise_uri),
                "label": str(label) if label else None,
                "violations": list(set(messages)),
            }
            report_file.write(json.dumps(record) + "\n")

    log.info("Validation report written to %s", REPORT_PATH)


# ─── Write outputs ────────────────────────────────────────────────────────────


def write_outputs(passing_graph, quarantine_graph):
    """Serialize passing and quarantine graphs to disk."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    passing_graph.serialize(OUTPUT_PATH, format="turtle")
    log.info("Passing exercises written to %s", OUTPUT_PATH)

    quarantine_graph.serialize(QUARANTINE_PATH, format="turtle")
    log.info("Quarantined exercises written to %s", QUARANTINE_PATH)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    """
    Entry point. Loads graphs, runs SHACL validation, splits passing
    and failing exercises, writes outputs and report.
    """
    log.info("=== validate_graph.py starting ===")

    data_graph, ontology_graph, shapes_graph = load_graphs()

    all_exercises = set(data_graph.subjects(RDF.type, FEG.Exercise))
    total = len(all_exercises)
    log.info("Found %d exercises to validate", total)

    conforms, results_graph = run_validation(data_graph, ontology_graph, shapes_graph)

    if conforms:
        log.info("All exercises conform - writing to exercises.ttl")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        data_graph.serialize(OUTPUT_PATH, format="turtle")
        write_report({}, data_graph, total, 0)
        log.info("=== validate_graph.py complete ===")
        return

    failing_exercises = get_failing_exercises(results_graph, data_graph)
    fail_count = len(failing_exercises)
    pass_count = total - fail_count

    log.info("Validation failures: %d/%d exercises", fail_count, total)
    for uri, messages in failing_exercises.items():
        label = data_graph.value(URIRef(uri), RDFS.label)
        log.warning("  FAIL: %s", label or uri)
        for msg in set(messages):
            log.warning("    - %s", msg)

    passing_graph, quarantine_graph = split_graph(data_graph, failing_exercises)

    write_outputs(passing_graph, quarantine_graph)
    write_report(failing_exercises, data_graph, pass_count, fail_count)

    log.info("=== validate_graph.py complete ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
