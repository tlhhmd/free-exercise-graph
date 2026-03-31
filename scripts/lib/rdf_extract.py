from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

FEG = Namespace("https://placeholder.url#")


@dataclass(frozen=True)
class ExerciseFeature:
    id: str
    name: str
    uri: str
    graph_id: str
    movement_patterns: tuple[str, ...]
    primary_joint_actions: tuple[str, ...]
    supporting_joint_actions: tuple[str, ...]
    prime_movers: tuple[str, ...]
    synergists: tuple[str, ...]
    stabilizers: tuple[str, ...]
    passive_targets: tuple[str, ...]
    equipment: tuple[str, ...]
    plane_of_motion: tuple[str, ...]
    style: tuple[str, ...]
    training_modalities: tuple[str, ...]
    laterality: str | None
    is_compound: bool
    is_combination: bool

    def to_export_dict(self) -> dict:
        return {
            "equipment": list(self.equipment),
            "graphId": self.graph_id,
            "id": self.id,
            "isCombination": self.is_combination,
            "isCompound": self.is_compound,
            "laterality": self.laterality,
            "movementPatterns": list(self.movement_patterns),
            "name": self.name,
            "passiveTargets": list(self.passive_targets),
            "planeOfMotion": list(self.plane_of_motion),
            "primeMovers": list(self.prime_movers),
            "primaryJointActions": list(self.primary_joint_actions),
            "style": list(self.style),
            "stabilizers": list(self.stabilizers),
            "supportingJointActions": list(self.supporting_joint_actions),
            "synergists": list(self.synergists),
            "trainingModalities": list(self.training_modalities),
            "uri": self.uri,
        }


def _local(term) -> str:
    return str(term).split("#")[-1]


def _bool_value(term) -> bool:
    return str(term).strip().lower() == "true"


def _sorted_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _legacy_id(graph: Graph, exercise) -> str:
    legacy = graph.value(exercise, FEG.legacySourceId)
    if legacy:
        return str(legacy)
    local = _local(exercise)
    return local[3:] if local.startswith("ex_") else local


def extract_features(graph_path: Path) -> list[ExerciseFeature]:
    graph = Graph()
    graph.parse(graph_path, format="turtle")

    exercises: list[ExerciseFeature] = []
    for exercise in graph.subjects(RDF.type, FEG.Exercise):
        uri = str(exercise)
        graph_id = _local(exercise)
        name = str(graph.value(exercise, RDFS.label) or graph_id)

        prime_movers: list[str] = []
        synergists: list[str] = []
        stabilizers: list[str] = []
        passive_targets: list[str] = []
        for involvement in graph.objects(exercise, FEG.hasInvolvement):
            muscle = graph.value(involvement, FEG.muscle)
            degree = graph.value(involvement, FEG.degree)
            if muscle is None or degree is None:
                continue
            muscle_local = _local(muscle)
            degree_local = _local(degree)
            if degree_local == "PrimeMover":
                prime_movers.append(muscle_local)
            elif degree_local == "Synergist":
                synergists.append(muscle_local)
            elif degree_local == "Stabilizer":
                stabilizers.append(muscle_local)
            elif degree_local == "PassiveTarget":
                passive_targets.append(muscle_local)

        exercises.append(
            ExerciseFeature(
                id=_legacy_id(graph, exercise),
                name=name,
                uri=uri,
                graph_id=graph_id,
                movement_patterns=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.movementPattern)]),
                primary_joint_actions=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.primaryJointAction)]),
                supporting_joint_actions=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.supportingJointAction)]),
                prime_movers=_sorted_unique(prime_movers),
                synergists=_sorted_unique(synergists),
                stabilizers=_sorted_unique(stabilizers),
                passive_targets=_sorted_unique(passive_targets),
                equipment=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.equipment)]),
                plane_of_motion=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.planeOfMotion)]),
                style=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.exerciseStyle)]),
                training_modalities=_sorted_unique([_local(item) for item in graph.objects(exercise, FEG.trainingModality)]),
                laterality=next((_local(item) for item in graph.objects(exercise, FEG.laterality)), None),
                is_compound=any(_bool_value(item) for item in graph.objects(exercise, FEG.isCompound)),
                is_combination=any(_bool_value(item) for item in graph.objects(exercise, FEG.isCombination)),
            )
        )

    exercises.sort(key=lambda item: item.id)
    return exercises
