"""
enrichment/service.py

Shared LLM enrichment utilities for the FEG pipeline.

Provides ontology loading, system prompt assembly, and LLM response parsing.
LLM calls are made via provider objects from enrichment.providers.
Orchestration lives in pipeline/enrich.py.

Usage:
    from enrichment.service import (
        load_graphs, vocabulary_versions, build_system_prompt, parse_enrichment,
    )
    from enrichment.providers import make_provider
    from enrichment.schema import setup_validators
"""

import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import FEG_NS
from enrichment._vocab import extract_vocab_sets
from enrichment.schema import ExerciseEnrichment, normalize_casing, setup_validators

FEG = Namespace(FEG_NS)
ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"


# ─── Ontology loading ──────────────────────────────────────────────────────────


def load_graphs(ontology_dir: Path = ONTOLOGY_DIR) -> dict[str, Graph]:
    """Load all ontology TTL files required for enrichment.

    Returns a graphs dict keyed by logical name. Pass this to
    setup_validators(), vocabulary_versions(), and build_system_prompt().
    """
    def load(*files) -> Graph:
        g = Graph()
        for f in files:
            g.parse(ontology_dir / f, format="turtle")
        return g

    return {
        "ontology":          load("ontology.ttl"),
        "muscles":           load("muscles.ttl", "ontology.ttl"),
        "movement_patterns": load("movement_patterns.ttl"),
        "joint_actions":     load("joint_actions.ttl"),
        "modalities":        load("training_modalities.ttl"),
        "degrees":           load("involvement_degrees.ttl"),
        "laterality":        load("laterality.ttl"),
        "planes_of_motion":  load("planes_of_motion.ttl"),
        "exercise_styles":   load("exercise_styles.ttl"),
    }


def vocabulary_versions(graphs: dict[str, Graph]) -> dict[str, str]:
    """Extract owl:versionInfo from each graph. Used to stamp enriched files."""
    owl_version = URIRef("http://www.w3.org/2002/07/owl#versionInfo")
    versions = {}
    for name, g in graphs.items():
        for _, _, v in g.triples((None, owl_version, None)):
            versions[name] = str(v)
            break
    return versions


# ─── Prompt assembly ──────────────────────────────────────────────────────────


def _degree_definitions(g: Graph) -> str:
    degrees = sorted(
        g.subjects(RDF.type, FEG.InvolvementDegree),
        key=lambda u: str(u).split("#")[-1],
    )
    lines = []
    for degree in degrees:
        label = g.value(degree, RDFS.label) or str(degree).split("#")[-1]
        comment = g.value(degree, RDFS.comment)
        lines.append(f"{label} — {comment}" if comment else str(label))
    return "\n".join(lines)


def _modality_list(g: Graph) -> str:
    modalities = sorted(
        g.subjects(RDF.type, FEG.TrainingModality),
        key=lambda u: str(u).split("#")[-1],
    )
    lines = []
    for m in modalities:
        label = g.value(m, RDFS.label) or str(m).split("#")[-1]
        comment = g.value(m, RDFS.comment)
        lines.append(f"{label} — {comment}" if comment else str(label))
    return "\n".join(lines)


def _vocab_list(g: Graph, rdf_type) -> str:
    """Render local_name — comment lines for all individuals of rdf_type."""
    items = sorted(
        g.subjects(RDF.type, rdf_type),
        key=lambda u: str(u).split("#")[-1],
    )
    lines = []
    for item in items:
        label = g.value(item, RDFS.label) or str(item).split("#")[-1]
        comment = g.value(item, RDFS.comment)
        local = str(item).split("#")[-1]
        lines.append(f"{local} ({label}) — {comment}" if comment else f"{local} ({label})")
    return "\n".join(lines)


def build_system_prompt(graphs: dict[str, Graph], template: Path) -> str:
    """Render the system prompt template with ontology-derived content.

    template — path to a prompt_template.md file containing <<<placeholder>>> slots.
    """
    # Import here to avoid circular issues; prompt_builder lives in enrichment/
    sys.path.insert(0, str(Path(__file__).parent))
    from prompt_builder import group_level_muscles, property_comment, render, skos_tree

    g_ontology = graphs["ontology"]
    type_map = {
        str(FEG.MuscleRegion): "(region)",
        str(FEG.MuscleGroup):  "(group)",
        str(FEG.MuscleHead):   "(head)",
    }

    variables = {
        "movement_pattern_rule":          property_comment(g_ontology, FEG.movementPattern),
        "movement_pattern_tree":          skos_tree(graphs["movement_patterns"], FEG.MovementPatternScheme),
        "training_modality_rule":         property_comment(g_ontology, FEG.trainingModality),
        "training_modality_list":         _modality_list(graphs["modalities"]),
        "involvement_degree_definitions": _degree_definitions(graphs["degrees"]),
        "muscle_specificity_rule":        property_comment(g_ontology, FEG.muscle),
        "head_usage_rules":               group_level_muscles(graphs["muscles"], FEG.useGroupLevel),
        "muscle_tree":                    skos_tree(
            graphs["muscles"],
            FEG.MuscleScheme,
            type_map=type_map,
            include_scope_notes=True,
        ),
        "primary_joint_action_rule":      property_comment(g_ontology, FEG.primaryJointAction),
        "supporting_joint_action_rule":   property_comment(g_ontology, FEG.supportingJointAction),
        "joint_action_tree":              skos_tree(graphs["joint_actions"], FEG.JointActionScheme),
        "is_compound_rule":               property_comment(g_ontology, FEG.isCompound),
        "laterality_rule":                property_comment(g_ontology, FEG.laterality),
        "is_combination_rule":            property_comment(g_ontology, FEG.isCombination),
        "plane_of_motion_rule":           property_comment(g_ontology, FEG.planeOfMotion),
        "plane_of_motion_list":           _vocab_list(graphs["planes_of_motion"], FEG.PlaneOfMotion),
        "exercise_style_rule":            property_comment(g_ontology, FEG.exerciseStyle),
        "exercise_style_list":            _vocab_list(graphs["exercise_styles"], FEG.ExerciseStyle),
    }
    return render(template, variables)



def parse_enrichment(raw: str) -> ExerciseEnrichment:
    """Parse and validate the last JSON object from a raw LLM response.

    The model may emit prose before or after the JSON, or self-correct
    by emitting multiple JSON objects. We take the last valid top-level
    object to tolerate both patterns.

    Raises json.JSONDecodeError if no valid JSON found.
    Raises pydantic.ValidationError if the object fails schema validation.
    """
    decoder = json.JSONDecoder()
    text = raw.strip()
    pos = 0
    last_obj = None
    while pos < len(text):
        # Advance to the next opening brace before attempting a parse
        while pos < len(text) and text[pos] != "{":
            pos += 1
        if pos >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, pos)
            last_obj = obj
            pos = end
        except json.JSONDecodeError:
            pos += 1  # skip this '{' and keep scanning
    if last_obj is None:
        raise json.JSONDecodeError("No valid JSON object found", text, 0)
    return ExerciseEnrichment.model_validate(normalize_casing(last_obj))
