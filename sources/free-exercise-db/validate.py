#!/usr/bin/env python3
"""
validate.py — Validate enriched exercises across 6 quality dimensions.

Dimensions:
  1. Validity      — SHACL conformance (pyshacl)
  2. Uniqueness    — duplicate muscle involvements, joint actions, movement patterns
  3. Integrity     — every vocabulary reference resolves to a known ontology term
  4. Timeliness    — enriched exercises have current vocabulary_versions stamps
  5. Consistency   — cross-field rule violations (JA ↔ pattern, isCompound ↔ JA count)
  6. Completeness  — required fields present (movement patterns, involvements, JAs)

Usage:
    python3 sources/free-exercise-db/validate.py
    python3 sources/free-exercise-db/validate.py --csv report.csv
    python3 sources/free-exercise-db/validate.py --all

Exits 0 if no validity failures, 1 if any validity violations found.
CSV written to sources/free-exercise-db/quality_report.csv by default.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import pyshacl
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SH

SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent.parent
sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS
from telemetry import PipelineRun
INGESTED_TTL = SOURCE_DIR / "ingested.ttl"
SHAPES_TTL = PROJECT_ROOT / "ontology" / "shapes.ttl"
ENRICHED_DIR = SOURCE_DIR / "enriched"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"

FEG = Namespace(FEG_NS)
FEG_STR = FEG_NS
OWL_VERSION = URIRef("http://www.w3.org/2002/07/owl#versionInfo")

VOCAB_FILES = {
    "movement_patterns": "movement_patterns.ttl",
    "muscles": "muscles.ttl",
    "degrees": "involvement_degrees.ttl",
    "modalities": "training_modalities.ttl",
    "joint_actions": "joint_actions.ttl",
    "shapes": "shapes.ttl",
}


def _sanitize_id(raw_id: str) -> str:
    return raw_id.replace("-", "_")


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _current_vocab_versions() -> dict[str, str]:
    versions = {}
    for key, filename in VOCAB_FILES.items():
        g = Graph()
        g.parse(ONTOLOGY_DIR / filename, format="turtle")
        for _, _, v in g.triples((None, OWL_VERSION, None)):
            versions[key] = str(v)
            break
    return versions


def _shorten(uri: str) -> str:
    return uri.replace(FEG_STR, "feg:")


def filter_enriched(data: Graph) -> tuple[Graph, int, int]:
    """Remove unenriched exercises. Returns (filtered_graph, total, enriched_count)."""
    all_exercises = set(data.subjects(RDF.type, FEG.Exercise))
    # feg:isCompound is always set by enrich.py and never by morph-KGC, making it
    # a reliable enrichment marker. If this assumption changes, update accordingly.
    enriched = set(data.subjects(FEG.isCompound, None))
    unenriched = all_exercises - enriched

    for ex in unenriched:
        for inv in list(data.objects(ex, FEG.hasInvolvement)):
            for tp, to in list(data.predicate_objects(inv)):
                data.remove((inv, tp, to))
        for p, o in list(data.predicate_objects(ex)):
            data.remove((ex, p, o))

    return data, len(all_exercises), len(enriched)


# ── Dimension checks ──────────────────────────────────────────────────────────


def check_validity(data: Graph, shapes: Graph) -> dict[str, list[str]]:
    """SHACL conformance. Returns {uri: [messages]}."""
    conforms, results_graph, _ = pyshacl.validate(data, shacl_graph=shapes)
    issues: dict[str, list[str]] = {}
    if not conforms:
        for result in results_graph.subjects(SH.resultMessage, None):
            msg = str(results_graph.value(result, SH.resultMessage))
            focus = results_graph.value(result, SH.focusNode)
            issues.setdefault(str(focus), []).append(msg)
    return issues


def check_uniqueness(data: Graph) -> dict[str, list[str]]:
    """Duplicate involvements, joint actions, or movement patterns per exercise."""
    issues: dict[str, list[str]] = {}

    # Duplicate muscle+degree combinations
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?muscle ?degree (COUNT(?inv) AS ?n) WHERE {
            ?exercise feg:hasInvolvement ?inv .
            ?inv feg:muscle ?muscle ; feg:degree ?degree .
        }
        GROUP BY ?exercise ?muscle ?degree
        HAVING (COUNT(?inv) > 1)
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"duplicate involvement: {_shorten(str(row.muscle))} @ {_shorten(str(row.degree))} ×{row.n}"
        )

    # Duplicate primary joint actions
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?ja (COUNT(?ja) AS ?n) WHERE {
            ?exercise feg:primaryJointAction ?ja .
        }
        GROUP BY ?exercise ?ja
        HAVING (COUNT(?ja) > 1)
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"duplicate primary JA: {_shorten(str(row.ja))} ×{row.n}"
        )

    # Duplicate supporting joint actions
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?ja (COUNT(?ja) AS ?n) WHERE {
            ?exercise feg:supportingJointAction ?ja .
        }
        GROUP BY ?exercise ?ja
        HAVING (COUNT(?ja) > 1)
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"duplicate supporting JA: {_shorten(str(row.ja))} ×{row.n}"
        )

    # Same JA in both primary and supporting
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?ja WHERE {
            ?exercise feg:primaryJointAction ?ja ;
                      feg:supportingJointAction ?ja .
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"JA in both primary and supporting: {_shorten(str(row.ja))}"
        )

    # Duplicate movement patterns
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?mp (COUNT(?mp) AS ?n) WHERE {
            ?exercise feg:movementPattern ?mp .
        }
        GROUP BY ?exercise ?mp
        HAVING (COUNT(?mp) > 1)
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"duplicate movement pattern: {_shorten(str(row.mp))} ×{row.n}"
        )

    return issues


def check_integrity(data: Graph) -> dict[str, list[str]]:
    """Every vocabulary reference must resolve to a known ontology term."""
    issues: dict[str, list[str]] = {}

    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?muscle WHERE {
            ?exercise feg:hasInvolvement ?inv .
            ?inv feg:muscle ?muscle .
            FILTER NOT EXISTS {
                ?muscle a ?t .
                FILTER (?t IN (feg:MuscleRegion, feg:MuscleGroup, feg:MuscleHead))
            }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"unknown muscle: {_shorten(str(row.muscle))}"
        )

    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?mp WHERE {
            ?exercise feg:movementPattern ?mp .
            FILTER NOT EXISTS { ?mp a feg:MovementPattern }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"unknown movement pattern: {_shorten(str(row.mp))}"
        )

    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?ja WHERE {
            { ?exercise feg:primaryJointAction ?ja }
            UNION
            { ?exercise feg:supportingJointAction ?ja }
            FILTER NOT EXISTS { ?ja a feg:JointAction }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"unknown joint action: {_shorten(str(row.ja))}"
        )

    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise ?degree WHERE {
            ?exercise feg:hasInvolvement ?inv .
            ?inv feg:degree ?degree .
            FILTER NOT EXISTS { ?degree a feg:InvolvementDegree }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"unknown degree: {_shorten(str(row.degree))}"
        )

    return issues


def check_timeliness(data: Graph) -> dict[str, list[str]]:
    """Exercises enriched against stale vocabulary versions."""
    issues: dict[str, list[str]] = {}
    if not ENRICHED_DIR.exists():
        return issues

    try:
        current = _current_vocab_versions()
    except Exception:
        return issues

    for p in sorted(ENRICHED_DIR.glob("*.json")):
        try:
            ex = json.loads(p.read_text())
        except Exception:
            continue

        ex_uri = FEG_STR + "ex_" + _sanitize_id(ex.get("id", ""))

        if "vocabulary_versions" not in ex:
            issues.setdefault(ex_uri, []).append("no vocabulary_versions stamp")
            continue

        stamped = ex["vocabulary_versions"]
        for key, current_v in current.items():
            if key not in stamped:
                issues.setdefault(ex_uri, []).append(
                    f"vocab {key}: missing (current {current_v})"
                )
            elif _parse_version(stamped[key]) < _parse_version(current_v):
                issues.setdefault(ex_uri, []).append(
                    f"vocab {key}: {stamped[key]} → {current_v}"
                )

    return issues


def check_consistency(data: Graph) -> dict[str, list[str]]:
    """Cross-field rule violations."""
    issues: dict[str, list[str]] = {}

    # Compound exercises: HipExtension/HipFlexion as primary JA → expect hip-dominant pattern
    # Scoped to isCompound=true — isolation hip exercises legitimately lack a hip pattern.
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise WHERE {
            ?exercise feg:isCompound true ;
                      feg:primaryJointAction ?ja .
            FILTER (?ja IN (feg:HipExtension, feg:HipFlexion))
            FILTER NOT EXISTS {
                ?exercise feg:movementPattern ?mp .
                FILTER (?mp IN (feg:HipHinge, feg:KneeDominant, feg:Squat, feg:SplitSquat, feg:Lunge))
            }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            "hip JA (HipExtension/HipFlexion) without hip-dominant movement pattern"
        )

    # Compound exercises: ShoulderFlexion/Extension as primary JA → expect Push or Pull pattern
    # Scoped to isCompound=true — isolation shoulder exercises legitimately lack a push/pull pattern.
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise WHERE {
            ?exercise feg:isCompound true ;
                      feg:primaryJointAction ?ja .
            FILTER (?ja IN (feg:ShoulderFlexion, feg:ShoulderExtension))
            FILTER NOT EXISTS {
                ?exercise feg:movementPattern ?mp .
                FILTER (?mp IN (feg:Push, feg:HorizontalPush, feg:VerticalPush,
                                feg:Pull, feg:HorizontalPull, feg:VerticalPull))
            }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            "shoulder JA (ShoulderFlexion/Extension) without Push/Pull movement pattern"
        )

    # SpinalStability as primary JA → expect anti-movement pattern (no isCompound scope —
    # SpinalStability always implies an anti-movement exercise regardless of compound status)
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise WHERE {
            ?exercise feg:primaryJointAction feg:SpinalStability .
            FILTER NOT EXISTS {
                ?exercise feg:movementPattern ?mp .
                FILTER (?mp IN (feg:TrunkStability, feg:AntiExtension,
                                feg:AntiRotation, feg:AntiLateralFlexion))
            }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            "SpinalStability primary JA without anti-movement pattern"
        )

    # Note: isCompound=false + 3+ primary JAs rule removed (ADR-070).
    # Multi-plane mobility exercises (circles) and supination curls legitimately
    # have 3–4 JAs while being isolation movements. Rule produced 0 true positives.

    return issues


def check_completeness(data: Graph) -> dict[str, list[str]]:
    """Required fields present for enriched exercises."""
    issues: dict[str, list[str]] = {}

    # Compound exercises without movement patterns (isolation exercises are exempt —
    # the ontology explicitly permits empty movement_patterns for single-joint exercises)
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise WHERE {
            ?exercise feg:isCompound true .
            FILTER NOT EXISTS { ?exercise feg:movementPattern ?mp }
            FILTER NOT EXISTS {
                ?exercise feg:hasInvolvement ?inv .
                ?inv feg:degree feg:PassiveTarget .
            }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append("no movement patterns")

    # Fewer than 2 muscle involvements
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise (COUNT(?inv) AS ?n) WHERE {
            ?exercise feg:isCompound ?c .
            OPTIONAL { ?exercise feg:hasInvolvement ?inv }
        }
        GROUP BY ?exercise
        HAVING (COUNT(?inv) < 2)
    """
    ):
        issues.setdefault(str(row.exercise), []).append(
            f"only {row.n} muscle involvement(s)"
        )

    # No primary joint actions
    for row in data.query(
        """
        PREFIX feg: <https://placeholder.url#>
        SELECT ?exercise WHERE {
            ?exercise feg:isCompound ?c .
            FILTER NOT EXISTS { ?exercise feg:primaryJointAction ?ja }
        }
    """
    ):
        issues.setdefault(str(row.exercise), []).append("no primary joint actions")

    return issues


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Validate enriched exercises — 6 quality dimensions."
    )
    parser.add_argument(
        "--csv",
        default=str(SOURCE_DIR / "quality_report.csv"),
        help="CSV output path (default: quality_report.csv alongside ingested.ttl)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Include perfect-scoring exercises in stdout (default: imperfect only)",
    )
    args = parser.parse_args()

    run = PipelineRun("validate")

    with run.step("load ingested.ttl"):
        data = Graph().parse(INGESTED_TTL, format="turtle")
    run.steps[-1].label = f"load ingested.ttl ({len(data):,} triples)"

    with run.step("load shapes.ttl"):
        shapes = Graph().parse(SHAPES_TTL, format="turtle")

    with run.step("filter enriched exercises"):
        data, total, enriched_count = filter_enriched(data)
    run.steps[-1].label = f"filter enriched ({enriched_count}/{total} exercises)"

    print(f"\nValidating {enriched_count}/{total} enriched exercises\n")

    # Collect enriched exercise URIs → display labels
    exercises: dict[str, str] = {}
    for ex_uri in data.subjects(FEG.isCompound, None):
        label = data.value(ex_uri, RDFS.label)
        exercises[str(ex_uri)] = str(label) if label else _shorten(str(ex_uri))

    with run.step("check validity (SHACL)"):
        validity_issues = check_validity(data, shapes)
    run.steps[-1].label = f"check validity (SHACL) — {len(validity_issues)} issues"

    with run.step("check uniqueness"):
        uniqueness_issues = check_uniqueness(data)
    run.steps[-1].label = f"check uniqueness — {len(uniqueness_issues)} issues"

    with run.step("check integrity"):
        integrity_issues = check_integrity(data)
    run.steps[-1].label = f"check integrity — {len(integrity_issues)} issues"

    with run.step("check timeliness"):
        timeliness_issues = check_timeliness(data)
    run.steps[-1].label = f"check timeliness — {len(timeliness_issues)} issues"

    with run.step("check consistency"):
        consistency_issues = check_consistency(data)
    run.steps[-1].label = f"check consistency — {len(consistency_issues)} issues"

    with run.step("check completeness"):
        completeness_issues = check_completeness(data)
    run.steps[-1].label = f"check completeness — {len(completeness_issues)} issues"

    report_path = run.finish()

    # ── Quality report ─────────────────────────────────────────────────────────

    FAIL_DIMS = [
        ("validity", validity_issues),
        ("uniqueness", uniqueness_issues),
        ("integrity", integrity_issues),
    ]
    WARN_DIMS = [
        ("timeliness", timeliness_issues),
        ("consistency", consistency_issues),
        ("completeness", completeness_issues),
    ]
    ALL_DIMS = FAIL_DIMS + WARN_DIMS

    def score(issues_map: dict, uri: str, severity: str) -> str:
        return severity if uri in issues_map else "pass"

    rows = []
    for uri, name in sorted(exercises.items(), key=lambda x: x[1].lower()):
        row: dict[str, str] = {"name": name}
        all_issues: list[str] = []

        for dim, imap in FAIL_DIMS:
            row[dim] = score(imap, uri, "fail")
            all_issues.extend(imap.get(uri, []))

        for dim, imap in WARN_DIMS:
            row[dim] = score(imap, uri, "warn")
            all_issues.extend(imap.get(uri, []))

        row["issues"] = "; ".join(all_issues)
        rows.append(row)

    csv_path = Path(args.csv)
    fieldnames = [
        "name",
        "validity",
        "uniqueness",
        "integrity",
        "timeliness",
        "consistency",
        "completeness",
        "issues",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nQuality report: {csv_path}\n")

    dim_names = [d for d, _ in ALL_DIMS]
    counts = {d: sum(1 for r in rows if r[d] != "pass") for d in dim_names}
    print(f"{'Dimension':<16} {'Issues':>6}")
    print("-" * 24)
    for d in dim_names:
        print(f"{d:<16} {counts[d]:>6}")
    print()

    imperfect = [r for r in rows if any(r[d] != "pass" for d in dim_names)]
    target = rows if args.show_all else imperfect
    for r in target:
        print(r["name"])
        for d in dim_names:
            if r[d] != "pass":
                print(f"  [{r[d].upper()}] {d}")
        if r["issues"]:
            for issue in r["issues"].split("; "):
                print(f"    • {issue}")

    if validity_issues:
        print(f"\n{len(validity_issues)} exercise(s) with potential violations")
        return report_path, True

    print("Validity: conforms")
    return report_path, False


if __name__ == "__main__":
    _, has_violations = main()
    sys.exit(1 if has_violations else 0)
