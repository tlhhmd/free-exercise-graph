"""
check_stale.py

Compares vocabulary versions stamped in enriched exercise files against
the current versions in the ontology files. Reports any enriched exercise
that was produced against an older vocabulary version and should be rerun.

Vocabularies tracked:
    muscles               muscles.ttl
    movement_patterns     movement_patterns.ttl
    involvement_degrees   involvement_degrees.ttl
    training_modalities   training_modalities.ttl
    shapes                shapes.ttl
    ontology              ontology.ttl

Usage:
    python3 check_stale.py           # report stale exercises
    python3 check_stale.py --list    # print stale ids one per line
                                       (pipe to enrich.py --force)

Exit codes:
    0 - all enriched exercises are current
    1 - one or more stale exercises found
"""

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace, OWL, URIRef

FEG = Namespace("https://placeholder.url#")
PLACEHOLDER_BASE = "https://placeholder.url#"

_HERE = Path(__file__).parent
_ONTOLOGY_DIR = _HERE.parent / "ontology"
_ENRICHED_DIR = _HERE.parent / "data" / "enriched"

# Each entry: (vocabulary key, filename, subject URI)
_VOCABULARY_SOURCES = [
    ("muscles",             "muscles.ttl",             FEG.MuscleScheme),
    ("movement_patterns",   "movement_patterns.ttl",   FEG.MovementPatternScheme),
    ("involvement_degrees", "involvement_degrees.ttl", FEG.InvolvementDegreeVocabulary),
    ("training_modalities", "training_modalities.ttl", FEG.TrainingModalityVocabulary),
    ("shapes",              "shapes.ttl",               FEG.ShapesGraph),
    ("ontology",            "ontology.ttl",             URIRef(PLACEHOLDER_BASE)),
]


def _current_versions() -> dict[str, str]:
    """Read current vocabulary versions from all ontology files."""
    versions = {}
    for key, filename, subject in _VOCABULARY_SOURCES:
        g = Graph()
        g.parse(_ONTOLOGY_DIR / filename, format="turtle")
        v = g.value(subject, OWL.versionInfo)
        versions[key] = str(v) if v else "unknown"
    return versions


def _check(current: dict[str, str]) -> list[dict]:
    """
    Return a list of stale exercise records. Each record has:
        id, enriched_at, stale_fields
    where stale_fields is a list of {vocabulary, file_version, current_version}.
    """
    stale = []

    for path in sorted(_ENRICHED_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        file_versions = data.get("vocabulary_versions", {})

        stale_fields = []
        for key, current_version in current.items():
            file_version = file_versions.get(key)
            if file_version != current_version:
                stale_fields.append({
                    "vocabulary": key,
                    "file_version": file_version or "missing",
                    "current_version": current_version,
                })

        if stale_fields:
            stale.append({
                "id": data.get("id", path.stem),
                "enriched_at": data.get("enriched_at", "unknown"),
                "stale_fields": stale_fields,
            })

    return stale


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check enriched exercises for stale vocabulary versions."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print stale exercise ids only, one per line.",
    )
    args = parser.parse_args()

    current = _current_versions()
    stale = _check(current)

    if args.list:
        for record in stale:
            print(record["id"])
        sys.exit(1 if stale else 0)

    print("Current vocabulary versions:")
    for k, v in current.items():
        print(f"  {k}: {v}")
    print()

    if not stale:
        print("All enriched exercises are current.")
        sys.exit(0)

    print(f"{len(stale)} stale exercise(s) found:\n")
    for record in stale:
        print(f"  {record['id']}  (enriched: {record['enriched_at']})")
        for field in record["stale_fields"]:
            print(
                f"    {field['vocabulary']}: "
                f"{field['file_version']} → {field['current_version']}"
            )
    print()
    print("Rerun stale exercises with:")
    print(
        "  python3 pipeline/check_stale.py --list | "
        "xargs -I{} python3 pipeline/enrich.py --id {} --force"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
