#!/usr/bin/env python3
"""
test_shacl.py — SHACL constraint test harness.

Builds an in-memory vocabulary graph from ontology files and injects malformed
exercise instances to verify that each SHACL shape catches the expected
violation.

Usage:
    python3 test_shacl.py

Exit codes:
    0 — all expected violations were caught; no unexpected violations
    1 — one or more test cases failed
"""

import sys
from pathlib import Path

import pyshacl
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH, XSD

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS

ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
SHAPES_TTL = ONTOLOGY_DIR / "shapes.ttl"

FEG = Namespace(FEG_NS)

_passed = 0
_failed = 0


# ── Graph utilities ──────────────────────────────────────────────────────────


def _load_vocab() -> Graph:
    """All ontology vocabulary files merged (shapes excluded)."""
    g = Graph()
    for ttl in sorted(ONTOLOGY_DIR.glob("*.ttl")):
        if ttl.name != "shapes.ttl":
            g.parse(ttl, format="turtle")
    return g


def _shapes() -> Graph:
    return Graph().parse(SHAPES_TTL, format="turtle")


def _validate(data: Graph, shapes: Graph) -> tuple[bool, list[str]]:
    conforms, results_graph, _ = pyshacl.validate(data, shacl_graph=shapes)
    messages = [
        str(results_graph.value(r, SH.resultMessage))
        for r in results_graph.subjects(RDF.type, SH.ValidationResult)
    ]
    return conforms, messages


def _fresh(vocab: Graph) -> Graph:
    """Return a fresh copy of the vocab graph for each test."""
    g = Graph()
    for triple in vocab:
        g.add(triple)
    return g


def _make_exercise(g: Graph, ex_id: str) -> None:
    """Add a minimal valid enriched exercise to the graph (HipHinge, GluteusMaximus PrimeMover)."""
    ex = FEG[f"ex_{ex_id}"]
    inv = FEG[f"inv_{ex_id}_GluteusMaximus_PrimeMover"]
    g.add((ex, RDF.type, FEG.Exercise))
    g.add((ex, RDFS.label, Literal(f"Test Exercise {ex_id}", datatype=XSD.string)))
    g.add((ex, FEG.movementPattern, FEG.HipHinge))
    g.add((ex, FEG.hasInvolvement, inv))
    g.add((inv, RDF.type, FEG.MuscleInvolvement))
    g.add((inv, FEG.muscle, FEG.GluteusMaximus))
    g.add((inv, FEG.degree, FEG.PrimeMover))


# ── Assertion helpers ─────────────────────────────────────────────────────────


def ok(name: str, conforms: bool, messages: list[str], fragment: str) -> None:
    global _passed, _failed
    if conforms:
        print(f"  FAIL  {name}: expected violation but graph conforms")
        _failed += 1
        return
    if any(fragment.lower() in m.lower() for m in messages):
        print(f"  PASS  {name}")
        _passed += 1
    else:
        print(f"  FAIL  {name}: violation raised but expected fragment not found")
        print(f"        expected: {fragment!r}")
        print(f"        got:      {messages}")
        _failed += 1


def ok_clean(name: str, conforms: bool, messages: list[str]) -> None:
    global _passed, _failed
    if conforms:
        print(f"  PASS  {name} (no violations)")
        _passed += 1
    else:
        print(f"  FAIL  {name}: expected no violations, got {messages}")
        _failed += 1


# ── Test cases ────────────────────────────────────────────────────────────────


def main() -> None:
    vocab = _load_vocab()
    shapes = _shapes()

    print("Running SHACL constraint tests\n")

    # T00 ── Baseline: a well-formed exercise should pass ─────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T00")
    ok_clean("T00 baseline valid exercise", *_validate(g, shapes))

    # T01 ── No movementPattern — now valid (ADR-059: pattern is optional) ────
    g = _fresh(vocab)
    _make_exercise(g, "T01")
    g.remove((FEG["ex_T01"], FEG.movementPattern, None))
    ok_clean("T01 no movementPattern (optional since ADR-059)", *_validate(g, shapes))

    # T02 ── No hasInvolvement ────────────────────────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T02")
    ex = FEG["ex_T02"]
    for inv in list(g.objects(ex, FEG.hasInvolvement)):
        g.remove((ex, FEG.hasInvolvement, inv))
        for p, o in list(g.predicate_objects(inv)):
            g.remove((inv, p, o))
    ok("T02 no hasInvolvement", *_validate(g, shapes), "muscle involvement")

    # T03 ── No PrimeMover and no PassiveTarget ───────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T03")
    inv = FEG["inv_T03_GluteusMaximus_PrimeMover"]
    g.remove((inv, FEG.degree, FEG.PrimeMover))
    g.add((inv, FEG.degree, FEG.Synergist))
    ok("T03 no PrimeMover or PassiveTarget", *_validate(g, shapes), "PrimeMover")

    # T04 ── Duplicate muscle across involvements ─────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T04")
    ex = FEG["ex_T04"]
    inv2 = FEG["inv_T04_GluteusMaximus_Synergist"]
    g.add((ex, FEG.hasInvolvement, inv2))
    g.add((inv2, RDF.type, FEG.MuscleInvolvement))
    g.add((inv2, FEG.muscle, FEG.GluteusMaximus))  # same muscle as PrimeMover inv
    g.add((inv2, FEG.degree, FEG.Synergist))
    ok("T04 duplicate muscle", *_validate(g, shapes), "more than once")

    # T05 ── Ancestor+child double-counting ───────────────────────────────────
    # RectusFemoris is skos:broader+ Quadriceps — listing both is double-counting
    g = _fresh(vocab)
    _make_exercise(g, "T05")
    ex = FEG["ex_T05"]
    # Replace base involvement with RectusFemoris PrimeMover
    g.remove((ex, FEG.hasInvolvement, FEG["inv_T05_GluteusMaximus_PrimeMover"]))
    for p, o in list(g.predicate_objects(FEG["inv_T05_GluteusMaximus_PrimeMover"])):
        g.remove((FEG["inv_T05_GluteusMaximus_PrimeMover"], p, o))
    inv_rf = FEG["inv_T05_RectusFemoris_PrimeMover"]
    g.add((ex, FEG.hasInvolvement, inv_rf))
    g.add((inv_rf, RDF.type, FEG.MuscleInvolvement))
    g.add((inv_rf, FEG.muscle, FEG.RectusFemoris))
    g.add((inv_rf, FEG.degree, FEG.PrimeMover))
    # Add its ancestor Quadriceps as well
    inv_quad = FEG["inv_T05_Quadriceps_Synergist"]
    g.add((ex, FEG.hasInvolvement, inv_quad))
    g.add((inv_quad, RDF.type, FEG.MuscleInvolvement))
    g.add((inv_quad, FEG.muscle, FEG.Quadriceps))
    g.add((inv_quad, FEG.degree, FEG.Synergist))
    ok("T05 ancestor+child double-counting", *_validate(g, shapes), "ancestor")

    # T06 ── Core as PrimeMover ───────────────────────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T06")
    ex = FEG["ex_T06"]
    inv_core = FEG["inv_T06_Core_PrimeMover"]
    g.add((ex, FEG.hasInvolvement, inv_core))
    g.add((inv_core, RDF.type, FEG.MuscleInvolvement))
    g.add((inv_core, FEG.muscle, FEG.Core))
    g.add((inv_core, FEG.degree, FEG.PrimeMover))
    ok("T06 Core as PrimeMover", *_validate(g, shapes), "Core")

    # T07 ── Invalid involvement degree ───────────────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T07")
    ex = FEG["ex_T07"]
    inv_bad = FEG["inv_T07_ErectorSpinae_Bogus"]
    g.add((ex, FEG.hasInvolvement, inv_bad))
    g.add((inv_bad, RDF.type, FEG.MuscleInvolvement))
    g.add((inv_bad, FEG.muscle, FEG.ErectorSpinae))
    g.add((inv_bad, FEG.degree, FEG["Bogus"]))  # not a real degree
    ok("T07 invalid involvement degree", *_validate(g, shapes), "Degree must be one of")

    # T08 ── useGroupLevel head violation ─────────────────────────────────────
    # RhomboidMajor is a head under Rhomboids (useGroupLevel=true)
    g = _fresh(vocab)
    _make_exercise(g, "T08")
    ex = FEG["ex_T08"]
    inv_rhom = FEG["inv_T08_RhomboidMajor_Synergist"]
    g.add((ex, FEG.hasInvolvement, inv_rhom))
    g.add((inv_rhom, RDF.type, FEG.MuscleInvolvement))
    g.add((inv_rhom, FEG.muscle, FEG.RhomboidMajor))
    g.add((inv_rhom, FEG.degree, FEG.Synergist))
    ok("T08 useGroupLevel head (RhomboidMajor)", *_validate(g, shapes), "useGroupLevel")

    # T09 ── isCompound with multiple values ──────────────────────────────────
    g = _fresh(vocab)
    _make_exercise(g, "T09")
    g.add((FEG["ex_T09"], FEG.isCompound, Literal(True, datatype=XSD.boolean)))
    g.add((FEG["ex_T09"], FEG.isCompound, Literal(False, datatype=XSD.boolean)))
    ok("T09 isCompound multiple values", *_validate(g, shapes), "isCompound")

    # T10 ── primaryJointAction using joint grouping node (not a feg:JointAction) ─
    # feg:Shoulder is skos:Concept only — not a feg:JointAction instance
    g = _fresh(vocab)
    _make_exercise(g, "T10")
    g.add((FEG["ex_T10"], FEG.primaryJointAction, FEG.Shoulder))
    ok("T10 primaryJointAction using grouping node", *_validate(g, shapes), "Primary joint action")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 50}")
    print(f"Results: {_passed} passed  |  {_failed} failed")
    sys.exit(0 if _failed == 0 else 1)


if __name__ == "__main__":
    main()
