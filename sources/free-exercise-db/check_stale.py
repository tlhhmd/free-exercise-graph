#!/usr/bin/env python3
"""
check_stale.py — Detect enriched exercises whose vocabulary version stamps
are behind the current vocabulary.

An exercise is stale if any vocabulary file it was enriched against has since
been updated (version bumped) or if a vocabulary file that now exists was not
present when the exercise was enriched (e.g. joint_actions.ttl added after
initial enrichment run).

Usage:
    python3 sources/free-exercise-db/check_stale.py
    python3 sources/free-exercise-db/check_stale.py --verbose
    python3 sources/free-exercise-db/check_stale.py --names-only

Exit codes:
    0 — all enriched exercises are current
    1 — one or more exercises are stale
"""

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph, URIRef

_HERE = Path(__file__).parent
_ONTOLOGY_DIR = _HERE.parent.parent / "ontology"
_ENRICHED_DIR = _HERE / "enriched"

OWL_VERSION = URIRef("http://www.w3.org/2002/07/owl#versionInfo")

# Vocabulary files that contribute to enrichment decisions.
# Keys match the vocabulary_versions dict written by enrich.py.
VOCAB_FILES = {
    "movement_patterns": "movement_patterns.ttl",
    "muscles": "muscles.ttl",
    "degrees": "involvement_degrees.ttl",
    "modalities": "training_modalities.ttl",
    "joint_actions": "joint_actions.ttl",
    "shapes": "shapes.ttl",
}


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _current_versions() -> dict[str, str]:
    versions = {}
    for key, filename in VOCAB_FILES.items():
        g = Graph()
        g.parse(_ONTOLOGY_DIR / filename, format="turtle")
        for _, _, v in g.triples((None, OWL_VERSION, None)):
            versions[key] = str(v)
            break
    return versions


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect stale enriched exercises.")
    parser.add_argument("--verbose", action="store_true", help="Show why each exercise is stale.")
    parser.add_argument("--names-only", action="store_true", help="Print only stale exercise names.")
    args = parser.parse_args()

    enriched_files = sorted(_ENRICHED_DIR.glob("*.json")) if _ENRICHED_DIR.exists() else []
    if not enriched_files:
        print("No enriched files found — nothing to check.")
        sys.exit(0)

    enriched = [json.loads(p.read_text()) for p in enriched_files]
    current = _current_versions()

    stale = []
    for ex in enriched:
        if "vocabulary_versions" not in ex:
            stale.append((ex["name"], ["no vocabulary_versions stamp"]))
            continue

        stamped = ex["vocabulary_versions"]
        reasons = []

        for key, current_v in current.items():
            if key not in stamped:
                reasons.append(f"{key}: missing (current {current_v})")
            elif _parse_version(stamped[key]) < _parse_version(current_v):
                reasons.append(f"{key}: {stamped[key]} → {current_v}")

        if reasons:
            stale.append((ex["name"], reasons))

    total = len(enriched)
    n_stale = len(stale)
    n_current = total - n_stale

    if args.names_only:
        for name, _ in stale:
            print(name)
        sys.exit(1 if stale else 0)

    print(f"Enriched: {total}  |  Current: {n_current}  |  Stale: {n_stale}")

    if stale:
        print()
        for name, reasons in stale:
            if args.verbose:
                print(f"  {name}")
                for r in reasons:
                    print(f"    - {r}")
            else:
                print(f"  {name}  ({', '.join(reasons)})")

    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
