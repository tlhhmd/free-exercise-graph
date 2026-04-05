"""
Helpers for computing the effective canonical-entity claim surface.

This module centralizes the precedence rules used by the build and eval tooling
so they stay aligned as the pipeline evolves.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Literal as RDFLiteral, Namespace
from rdflib.namespace import RDF, SKOS

from constants import FEG_NS

FEG = Namespace(FEG_NS)
DEGREE_PRIORITY = {"PrimeMover": 0, "Synergist": 1, "Stabilizer": 2, "PassiveTarget": 3}
INFERRED_FILL_PREDICATES = frozenset({
    "primary_joint_action",
    "supporting_joint_action",
    "training_modality",
})


def load_muscle_maps(ontology_dir: Path) -> tuple[dict[str, str], dict[str, frozenset[str]]]:
    """Return (group_level_map, ancestor_map) from muscles.ttl."""
    g = Graph()
    g.parse(ontology_dir / "muscles.ttl", format="turtle")

    def local(uri) -> str:
        return str(uri).split("#")[-1]

    group_level_map: dict[str, str] = {}
    for group in g.subjects(FEG.useGroupLevel, RDFLiteral(True)):
        group_name = local(group)
        for head in g.subjects(SKOS.broader, group):
            group_level_map[local(head)] = group_name

    all_muscles = (
        set(g.subjects(RDF.type, FEG.Muscle))
        | set(g.subjects(RDF.type, FEG.MuscleRegion))
        | set(g.subjects(RDF.type, FEG.MuscleGroup))
        | set(g.subjects(RDF.type, FEG.MuscleHead))
    )

    def ancestors_of(uri) -> frozenset[str]:
        result: set[str] = set()
        queue = list(g.objects(uri, SKOS.broader))
        while queue:
            parent = queue.pop()
            name = local(parent)
            if name not in result:
                result.add(name)
                queue.extend(g.objects(parent, SKOS.broader))
        return frozenset(result)

    ancestor_map = {local(m): ancestors_of(m) for m in all_muscles}
    return group_level_map, ancestor_map


def effective_claims(conn, entity_id: str) -> dict[str, list[tuple[str, str | None]]]:
    """Return {predicate: [(value, qualifier)]} for one canonical entity."""
    resolved = conn.execute(
        "SELECT predicate, value, qualifier FROM resolved_claims WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()
    inferred = conn.execute(
        "SELECT predicate, value, qualifier FROM inferred_claims WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()

    by_pred: dict[str, list[tuple[str, str | None]]] = {}
    for row in resolved:
        by_pred.setdefault(row["predicate"], []).append((row["value"], row["qualifier"]))

    resolved_preds = set(by_pred.keys())

    resolved_muscles: dict[str, str | None] = {
        row["value"]: row["qualifier"]
        for row in resolved
        if row["predicate"] == "muscle"
    }
    inferred_muscles: dict[str, str | None] = {
        row["value"]: row["qualifier"]
        for row in inferred
        if row["predicate"] == "muscle"
    }

    merged_muscles: list[tuple[str, str | None]] = []
    for muscle, resolved_degree in resolved_muscles.items():
        inferred_degree = inferred_muscles.get(muscle)
        if inferred_degree == "PrimeMover" and resolved_degree != "PrimeMover":
            merged_muscles.append((muscle, "PrimeMover"))
        else:
            merged_muscles.append((muscle, resolved_degree))
    for muscle, inferred_degree in inferred_muscles.items():
        if muscle not in resolved_muscles:
            merged_muscles.append((muscle, inferred_degree))
    if merged_muscles:
        by_pred["muscle"] = merged_muscles

    for row in inferred:
        predicate = row["predicate"]
        if predicate == "muscle":
            continue
        if predicate in INFERRED_FILL_PREDICATES or predicate not in resolved_preds:
            by_pred.setdefault(predicate, []).append((row["value"], row["qualifier"]))

    return by_pred


def normalize_muscle_claims(
    muscle_claims: list[tuple[str, str | None]],
    *,
    group_level_map: dict[str, str],
    ancestor_map: dict[str, frozenset[str]],
) -> list[tuple[str, str]]:
    """Apply the same muscle normalization used by the graph build."""
    best_degree: dict[str, str] = {}
    for muscle, degree in muscle_claims:
        if degree is None:
            continue
        muscle = group_level_map.get(muscle, muscle)
        current = best_degree.get(muscle)
        if current is None or DEGREE_PRIORITY.get(degree, 99) < DEGREE_PRIORITY.get(current, 99):
            best_degree[muscle] = degree

    muscle_set = set(best_degree)
    ancestors_to_remove = {
        ancestor
        for muscle in muscle_set
        for ancestor in ancestor_map.get(muscle, frozenset())
        if ancestor in muscle_set
    }
    for ancestor in ancestors_to_remove:
        del best_degree[ancestor]

    return sorted(best_degree.items(), key=lambda item: (DEGREE_PRIORITY.get(item[1], 99), item[0]))


def effective_prediction_record(
    conn,
    entity_id: str,
    *,
    group_level_map: dict[str, str],
    ancestor_map: dict[str, frozenset[str]],
) -> dict:
    """Return the current prediction surface as a plain dict for eval/export tooling."""
    claims = effective_claims(conn, entity_id)

    laterality_values = [value for value, _ in claims.get("laterality", [])]
    laterality = laterality_values[0] if laterality_values else None

    compound_values = [value for value, _ in claims.get("is_compound", [])]
    combination_values = [value for value, _ in claims.get("is_combination", [])]

    return {
        "id": entity_id,
        "movement_patterns": [value for value, _ in claims.get("movement_pattern", [])],
        "primary_joint_actions": [value for value, _ in claims.get("primary_joint_action", [])],
        "supporting_joint_actions": [value for value, _ in claims.get("supporting_joint_action", [])],
        "training_modalities": [value for value, _ in claims.get("training_modality", [])],
        "plane_of_motion": [value for value, _ in claims.get("plane_of_motion", [])],
        "exercise_style": [value for value, _ in claims.get("exercise_style", [])],
        "laterality": laterality,
        "is_compound": compound_values[0].lower() == "true" if compound_values else None,
        "is_combination": combination_values[0].lower() == "true" if combination_values else None,
        "muscle_involvements": [
            {"muscle": muscle, "degree": degree}
            for muscle, degree in normalize_muscle_claims(
                claims.get("muscle", []),
                group_level_map=group_level_map,
                ancestor_map=ancestor_map,
            )
        ],
    }
