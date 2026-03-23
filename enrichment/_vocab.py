"""
enrichment/_vocab.py

Extracts controlled vocabulary sets from loaded ontology graphs.
Called by schema.setup_validators() and service.vocabulary_versions().
"""

from rdflib import Graph
from rdflib.namespace import RDF


def extract_vocab_sets(graphs: dict[str, Graph], FEG) -> dict[str, set[str]]:
    """Return {field_name: {local_name, ...}} for every validated enrichment field.

    FEG is a rdflib.Namespace instance pointing to the project namespace.
    graphs must contain at minimum the keys used below; unknown keys are ignored.
    """

    def local_names(g: Graph, *types) -> set[str]:
        names = set()
        for rdf_type in types:
            names |= {str(s).split("#")[-1] for s in g.subjects(RDF.type, rdf_type)}
        return names

    result: dict[str, set[str]] = {}

    if "joint_actions" in graphs:
        result["joint_actions"] = local_names(graphs["joint_actions"], FEG.JointAction)

    if "movement_patterns" in graphs:
        result["movement_patterns"] = local_names(
            graphs["movement_patterns"], FEG.MovementPattern
        )

    if "modalities" in graphs:
        result["training_modalities"] = local_names(
            graphs["modalities"], FEG.TrainingModality
        )

    if "muscles" in graphs:
        result["muscles"] = local_names(
            graphs["muscles"],
            FEG.Muscle,
            FEG.MuscleRegion,
            FEG.MuscleGroup,
            FEG.MuscleHead,
        )

    if "degrees" in graphs:
        result["degrees"] = local_names(graphs["degrees"], FEG.InvolvementDegree)

    if "planes_of_motion" in graphs:
        result["planes_of_motion"] = local_names(
            graphs["planes_of_motion"], FEG.PlaneOfMotion
        )

    if "exercise_styles" in graphs:
        result["exercise_styles"] = local_names(
            graphs["exercise_styles"], FEG.ExerciseStyle
        )

    if "laterality" in graphs:
        result["laterality"] = local_names(graphs["laterality"], FEG.Laterality)

    return result
