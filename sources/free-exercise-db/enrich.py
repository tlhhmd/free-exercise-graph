"""
enrich.py

LLM enrichment pipeline for free-exercise-db exercises.

Reads exercises.json, calls the Claude API to add movement patterns,
training modalities, muscle involvements, and unilateral flags, and writes
one JSON file per exercise to the enriched/ directory. Automatically resumes
from prior runs (already-enriched exercises are skipped). Rate-limited
requests are retried with exponential backoff before falling back to quarantine/.

Usage:
    python3 sources/free-exercise-db/enrich.py
    python3 sources/free-exercise-db/enrich.py --limit 10
    python3 sources/free-exercise-db/enrich.py --concurrency 4
    python3 sources/free-exercise-db/enrich.py --model claude-haiku-4-5-20251001
    python3 sources/free-exercise-db/enrich.py --force Barbell_Deadlift Plank
"""

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

sys.path.insert(0, str(Path(__file__).parent))
from prompt_builder import (
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
_ENRICHED_DIR = _HERE / "enriched"
_QUARANTINE_DIR = _HERE / "quarantine"

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
        "joint_actions": load("joint_actions.ttl"),
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


def _extract_vocab_sets(graphs: dict[str, Graph]) -> dict[str, set[str]]:
    """Extract known local names for each vocabulary field for post-LLM validation."""
    def local_names(g: Graph, *types) -> set[str]:
        names = set()
        for rdf_type in types:
            names |= {str(s).split("#")[-1] for s in g.subjects(RDF.type, rdf_type)}
        return names

    return {
        "joint_actions": local_names(graphs["joint_actions"], FEG.JointAction),
        "movement_patterns": local_names(graphs["movement_patterns"], FEG.MovementPattern),
        "training_modalities": local_names(graphs["modalities"], FEG.TrainingModality),
        "muscles": local_names(
            graphs["muscles"], FEG.Muscle, FEG.MuscleRegion, FEG.MuscleGroup, FEG.MuscleHead
        ),
        "degrees": local_names(graphs["degrees"], FEG.InvolvementDegree),
    }


def _validate_fields(fields: dict, vocab: dict[str, set[str]]) -> None:
    """Validate LLM output against known vocabulary. Raises ValueError on unknown terms."""
    errors = []
    for ja in fields.get("primary_joint_actions", []):
        if ja not in vocab["joint_actions"]:
            errors.append(f"Unknown primary_joint_action: {ja!r}")
    for ja in fields.get("supporting_joint_actions", []):
        if ja not in vocab["joint_actions"]:
            errors.append(f"Unknown supporting_joint_action: {ja!r}")
    for mp in fields.get("movement_patterns", []):
        if mp not in vocab["movement_patterns"]:
            errors.append(f"Unknown movement_pattern: {mp!r}")
    for tm in fields.get("training_modalities", []):
        if tm not in vocab["training_modalities"]:
            errors.append(f"Unknown training_modality: {tm!r}")
    for inv in fields.get("muscle_involvements", []):
        if inv.get("muscle") not in vocab["muscles"]:
            errors.append(f"Unknown muscle: {inv.get('muscle')!r}")
        if inv.get("degree") not in vocab["degrees"]:
            errors.append(f"Unknown degree: {inv.get('degree')!r}")
    if errors:
        raise ValueError(f"Vocabulary validation failed: {'; '.join(errors)}")


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
        "primary_joint_action_rule": property_comment(g_shapes, FEG.Exercise, FEG.primaryJointAction),
        "supporting_joint_action_rule": property_comment(
            g_shapes, FEG.Exercise, FEG.supportingJointAction
        ),
        "joint_action_tree": skos_tree(graphs["joint_actions"], FEG.JointActionScheme),
        "is_compound_rule": property_comment(g_shapes, FEG.Exercise, FEG.isCompound),
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


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
    wait=wait_exponential(multiplier=30, min=30, max=180),
    stop=stop_after_attempt(4),
    reraise=True,
)
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
    parser.add_argument(
        "--exercises-file",
        type=Path,
        default=None,
        help="Path to a JSON file of exercise objects to use instead of the default exercises.json.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of parallel LLM requests (default: 1). Increase carefully — rate limits apply.",
    )
    parser.add_argument(
        "--force",
        nargs="+",
        metavar="EXERCISE_ID",
        help="Re-enrich specific exercise IDs, overwriting existing enriched/quarantine files.",
    )
    args = parser.parse_args()

    _ENRICHED_DIR.mkdir(exist_ok=True)
    _QUARANTINE_DIR.mkdir(exist_ok=True)

    # --force: delete target files so they are treated as pending
    if args.force:
        for ex_id in args.force:
            for target_dir in (_ENRICHED_DIR, _QUARANTINE_DIR):
                p = target_dir / f"{ex_id}.json"
                if p.exists():
                    p.unlink()
                    print(f"  Cleared {p.relative_to(_HERE)}")

    exercises_path = args.exercises_file if args.exercises_file else _EXERCISES
    exercises: list[dict] = json.loads(exercises_path.read_text())

    done_ids = {p.stem for p in _ENRICHED_DIR.glob("*.json")}
    quarantine_ids = {p.stem for p in _QUARANTINE_DIR.glob("*.json")}
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
    vocab = _extract_vocab_sets(graphs)

    client = anthropic.Anthropic()
    print(
        f"Enriching {len(pending)} exercises with {args.model} "
        f"(concurrency={args.concurrency}, {len(done_ids)} done, {len(quarantine_ids)} quarantined)."
    )

    def process(exercise: dict) -> tuple[dict, dict | None, Exception | None]:
        try:
            fields = enrich_exercise(client, system_prompt, exercise, args.model)
            _validate_fields(fields, vocab)
            return exercise, fields, None
        except (json.JSONDecodeError, anthropic.APIError, ValueError) as e:
            return exercise, None, e

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(process, ex): ex for ex in pending}
        for future in as_completed(futures):
            exercise, fields, err = future.result()
            if err:
                (_QUARANTINE_DIR / f"{exercise['id']}.json").write_text(
                    json.dumps({"exercise": exercise, "error": str(err)}, indent=2)
                )
                print(f"  ✗ {exercise['name']}  {err}", flush=True)
            else:
                (_ENRICHED_DIR / f"{exercise['id']}.json").write_text(
                    json.dumps({**exercise, **fields, "vocabulary_versions": vocab_versions}, indent=2)
                )
                print(f"  ✓ {exercise['name']}", flush=True)

    final_done = len(list(_ENRICHED_DIR.glob("*.json")))
    final_quarantine = len(list(_QUARANTINE_DIR.glob("*.json")))
    print(f"\n{final_done} enriched, {final_quarantine} quarantined.")


if __name__ == "__main__":
    main()
