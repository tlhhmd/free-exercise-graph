from __future__ import annotations

from dataclasses import dataclass

from scripts.lib.rdf_extract import ExerciseFeature

_BALLISTIC_MODALITIES = frozenset({"Power", "Plyometrics"})
_BALLISTIC_STYLES = frozenset({"Ballistics"})


@dataclass(frozen=True)
class NormalizedExerciseFeature:
    id: str
    name: str
    uri: str
    graph_id: str
    movement_patterns: frozenset[str]
    primary_joint_actions: frozenset[str]
    supporting_joint_actions: frozenset[str]
    prime_movers: frozenset[str]
    synergists: frozenset[str]
    stabilizers: frozenset[str]
    passive_targets: frozenset[str]
    equipment: frozenset[str]
    plane_of_motion: frozenset[str]
    style: frozenset[str]
    training_modalities: frozenset[str]
    laterality: str | None
    is_compound: bool
    is_combination: bool
    is_ballistic: bool
    primary_joint_action_count: int

    def to_export_dict(self) -> dict:
        return {
            "equipment": sorted(self.equipment),
            "graphId": self.graph_id,
            "id": self.id,
            "isBallistic": self.is_ballistic,
            "isCombination": self.is_combination,
            "isCompound": self.is_compound,
            "laterality": self.laterality,
            "movementPatterns": sorted(self.movement_patterns),
            "name": self.name,
            "passiveTargets": sorted(self.passive_targets),
            "planeOfMotion": sorted(self.plane_of_motion),
            "primeMovers": sorted(self.prime_movers),
            "primaryJointActions": sorted(self.primary_joint_actions),
            "style": sorted(self.style),
            "stabilizers": sorted(self.stabilizers),
            "supportingJointActions": sorted(self.supporting_joint_actions),
            "synergists": sorted(self.synergists),
            "trainingModalities": sorted(self.training_modalities),
            "uri": self.uri,
        }


def normalize_features(features: list[ExerciseFeature]) -> list[NormalizedExerciseFeature]:
    normalized: list[NormalizedExerciseFeature] = []
    for feature in features:
        training_modalities = frozenset(feature.training_modalities)
        style = frozenset(feature.style)
        normalized.append(
            NormalizedExerciseFeature(
                id=feature.id,
                name=feature.name,
                uri=feature.uri,
                graph_id=feature.graph_id,
                movement_patterns=frozenset(feature.movement_patterns),
                primary_joint_actions=frozenset(feature.primary_joint_actions),
                supporting_joint_actions=frozenset(feature.supporting_joint_actions),
                prime_movers=frozenset(feature.prime_movers),
                synergists=frozenset(feature.synergists),
                stabilizers=frozenset(feature.stabilizers),
                passive_targets=frozenset(feature.passive_targets),
                equipment=frozenset(feature.equipment),
                plane_of_motion=frozenset(feature.plane_of_motion),
                style=style,
                training_modalities=training_modalities,
                laterality=feature.laterality,
                is_compound=feature.is_compound,
                is_combination=feature.is_combination,
                is_ballistic=bool(training_modalities & _BALLISTIC_MODALITIES or style & _BALLISTIC_STYLES),
                primary_joint_action_count=len(feature.primary_joint_actions),
            )
        )
    normalized.sort(key=lambda item: item.id)
    return normalized
