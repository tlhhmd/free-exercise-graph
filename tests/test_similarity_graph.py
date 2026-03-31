from __future__ import annotations

import json

from scripts.lib.export_json import export_similarity_artifacts
from scripts.lib.feature_normalize import NormalizedExerciseFeature, normalize_features
from scripts.lib.rdf_extract import extract_features
from scripts.lib.similarity import build_similarity_outputs, score_pair


def _feature(
    exercise_id: str,
    *,
    movement_patterns: tuple[str, ...] = (),
    primary_joint_actions: tuple[str, ...] = (),
    supporting_joint_actions: tuple[str, ...] = (),
    prime_movers: tuple[str, ...] = (),
    synergists: tuple[str, ...] = (),
    stabilizers: tuple[str, ...] = (),
    equipment: tuple[str, ...] = (),
    plane_of_motion: tuple[str, ...] = (),
    style: tuple[str, ...] = (),
    training_modalities: tuple[str, ...] = (),
    laterality: str | None = None,
    is_compound: bool = False,
    is_combination: bool = False,
) -> NormalizedExerciseFeature:
    return NormalizedExerciseFeature(
        id=exercise_id,
        name=exercise_id.replace("_", " ").title(),
        uri=f"https://placeholder.url#{exercise_id}",
        graph_id=f"ex_{exercise_id}",
        movement_patterns=frozenset(movement_patterns),
        primary_joint_actions=frozenset(primary_joint_actions),
        supporting_joint_actions=frozenset(supporting_joint_actions),
        prime_movers=frozenset(prime_movers),
        synergists=frozenset(synergists),
        stabilizers=frozenset(stabilizers),
        passive_targets=frozenset(),
        equipment=frozenset(equipment),
        plane_of_motion=frozenset(plane_of_motion),
        style=frozenset(style),
        training_modalities=frozenset(training_modalities),
        laterality=laterality,
        is_compound=is_compound,
        is_combination=is_combination,
        is_ballistic=bool(set(training_modalities) & {"Power", "Plyometrics"} or set(style) & {"Ballistics"}),
        primary_joint_action_count=len(primary_joint_actions),
    )


def test_extract_features_from_graph_turtle(tmp_path):
    graph_path = tmp_path / "mini.ttl"
    graph_path.write_text(
        """
        @prefix feg: <https://placeholder.url#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

        feg:ex_deadlift a feg:Exercise ;
          rdfs:label "Deadlift" ;
          feg:legacySourceId "deadlift" ;
          feg:movementPattern feg:HipHinge ;
          feg:primaryJointAction feg:HipExtension ;
          feg:supportingJointAction feg:KneeExtension ;
          feg:equipment feg:Barbell ;
          feg:planeOfMotion feg:SagittalPlane ;
          feg:laterality feg:Bilateral ;
          feg:isCompound true ;
          feg:isCombination false ;
          feg:exerciseStyle feg:Powerlifting ;
          feg:trainingModality feg:Strength ;
          feg:hasInvolvement _:pm, _:st .

        _:pm feg:muscle feg:GluteusMaximus ; feg:degree feg:PrimeMover .
        _:st feg:muscle feg:ErectorSpinae ; feg:degree feg:Stabilizer .
        """,
        encoding="utf-8",
    )

    features = normalize_features(extract_features(graph_path))

    assert len(features) == 1
    feature = features[0]
    assert feature.id == "deadlift"
    assert feature.movement_patterns == {"HipHinge"}
    assert feature.primary_joint_actions == {"HipExtension"}
    assert feature.supporting_joint_actions == {"KneeExtension"}
    assert feature.prime_movers == {"GluteusMaximus"}
    assert feature.stabilizers == {"ErectorSpinae"}
    assert feature.equipment == {"Barbell"}
    assert feature.laterality == "Bilateral"
    assert feature.is_compound is True
    assert feature.is_combination is False


def test_similarity_scoring_is_symmetric():
    weights = {
        "sameMovementPattern": 5,
        "sharedPrimaryJointAction": 4,
        "sharedSupportingJointAction": 2,
        "sharedPrimeMover": 4,
        "sharedSynergist": 2,
        "sharedStabilizer": 1,
        "sameLaterality": 2,
        "samePlaneOfMotion": 1,
        "sameCompoundStatus": 1,
        "sharedExerciseStyle": 1,
        "sharedEquipment": 1,
        "combinationMismatchPenalty": -3,
        "ballisticMismatchPenalty": -2,
        "primaryActionCountMismatchPenalty": -1,
    }
    left = _feature(
        "deadlift",
        movement_patterns=("HipHinge",),
        primary_joint_actions=("HipExtension",),
        prime_movers=("GluteusMaximus",),
        stabilizers=("ErectorSpinae",),
        equipment=("Barbell",),
        plane_of_motion=("SagittalPlane",),
        laterality="Bilateral",
        is_compound=True,
    )
    right = _feature(
        "romanian_deadlift",
        movement_patterns=("HipHinge",),
        primary_joint_actions=("HipExtension",),
        prime_movers=("GluteusMaximus",),
        stabilizers=("ErectorSpinae",),
        equipment=("Barbell",),
        plane_of_motion=("SagittalPlane",),
        laterality="Bilateral",
        is_compound=True,
    )

    forward = score_pair(left, right, weights, include_breakdown=True)
    reverse = score_pair(right, left, weights, include_breakdown=True)

    assert forward["score"] == reverse["score"]
    assert forward["reason"] == reverse["reason"]
    assert forward["breakdown"] == reverse["breakdown"]


def test_neighbors_never_include_self():
    weights = {
        "sameMovementPattern": 5,
        "sharedPrimaryJointAction": 4,
        "sharedSupportingJointAction": 2,
        "sharedPrimeMover": 4,
        "sharedSynergist": 2,
        "sharedStabilizer": 1,
        "sameLaterality": 2,
        "samePlaneOfMotion": 1,
        "sameCompoundStatus": 1,
        "sharedExerciseStyle": 1,
        "sharedEquipment": 1,
        "combinationMismatchPenalty": -3,
        "ballisticMismatchPenalty": -2,
        "primaryActionCountMismatchPenalty": -1,
    }
    settings = {
        "emitDebugBreakdowns": True,
        "minScore": 3,
        "topNeighborsPerExercise": 3,
    }
    features = [
        _feature(
            "deadlift",
            movement_patterns=("HipHinge",),
            primary_joint_actions=("HipExtension",),
            prime_movers=("GluteusMaximus",),
            equipment=("Barbell",),
            laterality="Bilateral",
            is_compound=True,
        ),
        _feature(
            "romanian_deadlift",
            movement_patterns=("HipHinge",),
            primary_joint_actions=("HipExtension",),
            prime_movers=("GluteusMaximus",),
            equipment=("Barbell",),
            laterality="Bilateral",
            is_compound=True,
        ),
        _feature(
            "push_up",
            movement_patterns=("HorizontalPush",),
            primary_joint_actions=("ElbowExtension",),
            prime_movers=("PectoralisMajor",),
            equipment=("Bodyweight",),
            laterality="Bilateral",
            is_compound=True,
        ),
    ]

    _edges, neighbors, _metrics = build_similarity_outputs(features, weights, settings)

    for exercise_id, items in neighbors.items():
        assert items
        assert all(item["id"] != exercise_id for item in items)


def test_export_json_writes_expected_shapes(tmp_path):
    out_dir = tmp_path / "generated"
    export_similarity_artifacts(
        out_dir,
        features=[{"id": "deadlift"}],
        edges=[{"source": "deadlift", "target": "romanian_deadlift", "score": 10.0}],
        neighbors={"deadlift": [{"id": "romanian_deadlift", "score": 10.0}]},
        communities={"0": {"members": ["deadlift", "romanian_deadlift"], "size": 2}},
        metrics={"exercise_count": 2, "edge_count": 1},
    )

    features = json.loads((out_dir / "exercise_features.json").read_text(encoding="utf-8"))
    edges = json.loads((out_dir / "exercise_similarity_edges.json").read_text(encoding="utf-8"))
    neighbors = json.loads((out_dir / "exercise_neighbors.json").read_text(encoding="utf-8"))
    communities = json.loads((out_dir / "exercise_communities.json").read_text(encoding="utf-8"))
    metrics = json.loads((out_dir / "build_metrics.json").read_text(encoding="utf-8"))

    assert features == [{"id": "deadlift"}]
    assert edges[0]["source"] == "deadlift"
    assert neighbors["deadlift"][0]["id"] == "romanian_deadlift"
    assert communities["0"]["size"] == 2
    assert metrics["edge_count"] == 1
