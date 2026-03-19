"""
enrich.py

LLM enrichment pipeline for free-exercise-db exercises.

Reads exercises.json, calls the Claude API to add movement patterns,
training modalities, muscle involvements, and unilateral flags, and writes
results to exercises_enriched.json. Automatically resumes from prior runs.
Failed exercises are written to exercises_quarantine.json for inspection.

Usage:
    python3 sources/free-exercise-db/enrich.py
    python3 sources/free-exercise-db/enrich.py --limit 10
    python3 sources/free-exercise-db/enrich.py --model claude-haiku-4-5-20251001
"""

import argparse
import json
import random
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pipeline.prompt_builder import (
    group_level_muscles,
    property_comment,
    render,
    skos_tree,
    sparql_constraint_comments,
)

# ─── Paths ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
_ONTOLOGY_DIR = _HERE.parent.parent / "ontology"
_TEMPLATE = _HERE / "prompt_template.md"
_EXERCISES = _HERE / "raw" / "exercises.json"
_ENRICHED = _HERE / "enriched" / "exercises_enriched.json"
_QUARANTINE = _HERE / "enriched" / "exercises_quarantine.json"

FEG = Namespace("https://placeholder.url#")
DEFAULT_MODEL = "claude-sonnet-4-6"

# ─── Ontology loading ─────────────────────────────────────────────────────────


def _load_graphs() -> dict[str, Graph]:
    def load(*files) -> Graph:
        g = Graph()
        for f in files:
            g.parse(_ONTOLOGY_DIR / f, format="turtle")
        return g

    return {
        "movement_patterns": load("movement_patterns.ttl"),
        "muscles": load("muscles.ttl", "ontology.ttl"),
        "degrees": load("involvement_degrees.ttl"),
        "modalities": load("training_modalities.ttl"),
        "shapes": load("shapes.ttl"),
    }


def _vocabulary_versions(graphs: dict[str, Graph]) -> dict[str, str]:
    owl_version = URIRef("http://www.w3.org/2002/07/owl#versionInfo")
    versions = {}
    for name, g in graphs.items():
        for _, _, v in g.triples((None, owl_version, None)):
            versions[name] = str(v)
            break
    return versions


# ─── Prompt assembly (exercise-graph specific) ────────────────────────────────


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


def build_system_prompt(graphs: dict[str, Graph]) -> str:
    type_map = {
        str(FEG.MuscleRegion): "(region)",
        str(FEG.MuscleGroup): "(group)",
        str(FEG.MuscleHead): "(head)",
    }
    g_shapes = graphs["shapes"]

    variables = {
        "is_unilateral_rule": property_comment(g_shapes, FEG.Exercise, FEG.isUnilateral),
        "movement_pattern_rule": property_comment(g_shapes, FEG.Exercise, FEG.movementPattern),
        "movement_pattern_tree": skos_tree(graphs["movement_patterns"], FEG.MovementPatternScheme),
        "training_modality_rule": property_comment(g_shapes, FEG.Exercise, FEG.trainingModality),
        "training_modality_list": _modality_list(graphs["modalities"]),
        "involvement_degree_definitions": _degree_definitions(graphs["degrees"]),
        "muscle_specificity_rule": property_comment(g_shapes, FEG.MuscleInvolvement, FEG.muscle),
        "head_usage_rules": group_level_muscles(graphs["muscles"], FEG.useGroupLevel),
        "muscle_tree": skos_tree(
            graphs["muscles"],
            FEG.MuscleScheme,
            type_map=type_map,
            include_scope_notes=True,
        ),
        "sparql_constraints": "\n".join(
            f"- {m}" for m in sparql_constraint_comments(g_shapes)
        ),
    }
    return render(_TEMPLATE, variables)


def format_user_message(exercise: dict) -> str:
    lines = [f"Name: {exercise['name']}"]
    if instructions := exercise.get("instructions"):
        lines.append(f"Instructions: {' '.join(instructions)}")
    primary = exercise.get("primaryMuscles", [])
    secondary = exercise.get("secondaryMuscles", [])
    if primary or secondary:
        lines.append(
            f"Source muscles - primary: {', '.join(primary) or 'none'}"
            f" | secondary: {', '.join(secondary) or 'none'}"
        )
    return "\n".join(lines)


# ─── LLM call ─────────────────────────────────────────────────────────────────


def enrich_exercise(
    client: anthropic.Anthropic,
    system_prompt: str,
    exercise: dict,
    model: str,
) -> dict:
    """Call the LLM and return parsed enrichment fields. Raises on failure."""
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": format_user_message(exercise)}],
    )
    return json.loads(response.content[0].text)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich exercises with LLM classifications.")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N exercises.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model ID.")
    parser.add_argument("--random", action="store_true", help="Pick exercises at random.")
    args = parser.parse_args()

    _ENRICHED.parent.mkdir(exist_ok=True)
    exercises: list[dict] = json.loads(_EXERCISES.read_text())
    enriched: list[dict] = json.loads(_ENRICHED.read_text()) if _ENRICHED.exists() else []
    quarantine: list[dict] = json.loads(_QUARANTINE.read_text()) if _QUARANTINE.exists() else []

    done_ids = {e["id"] for e in enriched if "movement_patterns" in e}
    quarantine_ids = {e["exercise"]["id"] for e in quarantine}
    pending = [e for e in exercises if e["id"] not in done_ids and e["id"] not in quarantine_ids]

    if args.random:
        random.shuffle(pending)
    if args.limit:
        pending = pending[: args.limit]

    if not pending:
        print("Nothing to enrich — all exercises are done or quarantined.")
        return

    print("Loading ontology...")
    graphs = _load_graphs()
    system_prompt = build_system_prompt(graphs)
    vocab_versions = _vocabulary_versions(graphs)

    client = anthropic.Anthropic()
    print(
        f"Enriching {len(pending)} exercises with {args.model} "
        f"({len(done_ids)} done, {len(quarantine_ids)} quarantined)."
    )

    for i, exercise in enumerate(pending, 1):
        print(f"  [{i}/{len(pending)}] {exercise['name']}", end="", flush=True)
        try:
            fields = enrich_exercise(client, system_prompt, exercise, args.model)
            enriched.append({**exercise, **fields, "vocabulary_versions": vocab_versions})
            _ENRICHED.write_text(json.dumps(enriched, indent=2))
            print(" ✓")
        except (json.JSONDecodeError, anthropic.APIError) as e:
            quarantine.append({"exercise": exercise, "error": str(e)})
            _QUARANTINE.write_text(json.dumps(quarantine, indent=2))
            print(f" ✗  {e}")

    print(f"\n{len(done_ids) + len(pending) - len(quarantine)} enriched, {len(quarantine)} quarantined.")


if __name__ == "__main__":
    main()
