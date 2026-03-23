"""
enrichment/service.py

Shared LLM enrichment service for all FEG source pipelines.

Provides ontology loading, system prompt assembly, the LLM call/parse loop,
and the shared enrichment orchestration (run_enrichment, reparse_quarantine).

Source-specific adapters (enrich.py in each source directory) handle:
  - Reading source exercises (_read_exercises / loading JSON)
  - User message formatting (format_user_message)
  - Enriched record assembly (make_record)
  - CLI argument parsing

Usage in a source adapter:
    from enrichment.service import (
        load_graphs, vocabulary_versions, build_system_prompt,
        call_llm, parse_enrichment, run_enrichment, reparse_quarantine,
    )
    from enrichment.schema import setup_validators
"""

import json
import random
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import FEG_NS
from enrichment._vocab import extract_vocab_sets
from enrichment.schema import ExerciseEnrichment, normalize_casing, setup_validators

FEG = Namespace(FEG_NS)
ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"

DEFAULT_MODEL = "claude-sonnet-4-6"


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


# ─── LLM call ─────────────────────────────────────────────────────────────────


@retry(
    retry=retry_if_exception_type(
        (anthropic.RateLimitError, anthropic.InternalServerError)
    ),
    wait=wait_exponential(multiplier=30, min=30, max=180),
    stop=stop_after_attempt(4),
    reraise=True,
)
def call_llm(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, object]:
    """Call the Claude API and return (raw_text, usage).

    usage has .input_tokens, .output_tokens, .cache_creation_input_tokens,
    .cache_read_input_tokens — use these to track cost and cache hit rate.

    Retries on rate-limit and server errors with exponential backoff.
    Raises on API failure after 4 attempts.
    """
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )
    if not response.content:
        raise ValueError(
            f"Empty content list from API (stop_reason={response.stop_reason!r})"
        )
    raw = response.content[0].text
    if not raw.strip():
        raise ValueError(
            f"Empty response text from API (stop_reason={response.stop_reason!r}, "
            f"content blocks={len(response.content)}, "
            f"block type={type(response.content[0]).__name__!r})"
        )
    return raw, response.usage


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


# ─── Shared orchestration ──────────────────────────────────────────────────────


def reparse_quarantine(
    quarantine_dir: Path,
    enriched_dir: Path,
    make_record: Callable[[dict, dict, dict], dict],
) -> None:
    """Re-parse raw_response from quarantine files without calling the LLM.

    Use after a vocabulary fix when the model's original response was correct
    but failed validation because a term wasn't in the vocab yet. Exercises
    that pass validation are moved to enriched/; those that still fail remain
    in quarantine with an updated error.
    """
    quarantine_files = list(quarantine_dir.glob("*.json"))
    if not quarantine_files:
        print("No quarantined exercises to reparse.")
        return

    graphs = load_graphs()
    vocab_vers = vocabulary_versions(graphs)
    setup_validators(graphs)

    passed = 0
    for p in quarantine_files:
        data = json.loads(p.read_text())
        raw = data.get("raw_response")
        exercise = data.get("exercise", {})
        name = exercise.get("name", p.stem)
        if not raw:
            print(f"  ⚠️  {name}  no raw_response — skipping")
            continue
        try:
            enrichment = parse_enrichment(raw)
            record = make_record(exercise, enrichment.model_dump(exclude_none=True), vocab_vers)
            (enriched_dir / p.name).write_text(json.dumps(record, indent=2))
            p.unlink()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            data["error"] = str(e)
            p.write_text(json.dumps(data, indent=2))
            print(f"  ❌ {name}  {e}")

    still_quarantined = len(list(quarantine_dir.glob("*.json")))
    print(f"\n{passed} reparsed, {still_quarantined} still quarantined.")


def run_enrichment(
    exercises: list[dict],
    format_fn: Callable[[dict], str],
    make_record: Callable[[dict, dict, dict], dict],
    enriched_dir: Path,
    quarantine_dir: Path,
    log_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    concurrency: int = 1,
    limit: int | None = None,
    randomise: bool = False,
    force: list[str] | None = None,
    retry_quarantine: bool = False,
    dump_prompts_dir: Path | None = None,
) -> None:
    """Orchestrate LLM enrichment for a list of exercises.

    Handles --retry-quarantine, --force, pending filtering, concurrency,
    logging, and file I/O. Source adapters provide exercises, format_fn,
    and make_record; everything else is shared.

    When dump_prompts_dir is set, saves system_prompt.txt and one
    {exercise_id}.txt per pending exercise instead of calling the LLM.
    """
    enriched_dir.mkdir(exist_ok=True)
    quarantine_dir.mkdir(exist_ok=True)

    if retry_quarantine:
        cleared = list(quarantine_dir.glob("*.json"))
        for p in cleared:
            p.unlink()
        print(f"  Cleared {len(cleared)} quarantine files.")

    if force:
        for ex_id in force:
            for d in (enriched_dir, quarantine_dir):
                p = d / f"{ex_id}.json"
                if p.exists():
                    p.unlink()
                    print(f"  Cleared {p.relative_to(enriched_dir.parent)}")

    done_ids = {p.stem for p in enriched_dir.glob("*.json")}
    quarantine_ids = {p.stem for p in quarantine_dir.glob("*.json")}

    pending = [
        e for e in exercises
        if e["id"] not in done_ids and e["id"] not in quarantine_ids
    ]

    if force:
        force_set = set(force)
        pending = [e for e in exercises if e["id"] in force_set]

    if randomise:
        random.shuffle(pending)
    if limit:
        pending = pending[:limit]

    if not pending:
        print("Nothing to enrich — all exercises are done or quarantined.")
        return

    print("Loading ontology...")
    graphs = load_graphs()
    system_prompt = build_system_prompt(graphs, _PROJECT_ROOT / "enrichment" / "prompt_template.md")
    vocab_vers = vocabulary_versions(graphs)
    setup_validators(graphs)

    if dump_prompts_dir is not None:
        dump_prompts_dir.mkdir(parents=True, exist_ok=True)
        (dump_prompts_dir / "system_prompt.txt").write_text(system_prompt)
        for exercise in pending:
            (dump_prompts_dir / f"{exercise['id']}.txt").write_text(format_fn(exercise))
        print(f"Saved system_prompt.txt + {len(pending)} exercise prompts to {dump_prompts_dir}")
        return

    client = anthropic.Anthropic()
    total = len(pending)
    print(
        f"Enriching {total} exercises with {model} "
        f"(concurrency={concurrency}, {len(done_ids)} done, "
        f"{len(quarantine_ids)} quarantined)."
    )

    completed = 0

    def _log(line: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        log_path.open("a").write(f"{ts} {line}\n")

    _log(f"START  {total} pending  model={model}  concurrency={concurrency}")

    def process(exercise: dict) -> tuple[dict, dict | None, str | None, object | None, Exception | None]:
        raw = None
        usage = None
        try:
            raw, usage = call_llm(client, system_prompt, format_fn(exercise), model)
            enrichment = parse_enrichment(raw)
            return exercise, enrichment.model_dump(exclude_none=True), raw, usage, None
        except Exception as e:
            return exercise, None, raw, usage, e

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process, ex): ex for ex in pending}
        for future in as_completed(futures):
            exercise, fields, raw, usage, err = future.result()
            completed += 1
            usage_str = ""
            if usage:
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
                usage_str = (
                    f"  in={usage.input_tokens} out={usage.output_tokens}"
                    f" cache_read={cache_read} cache_write={cache_write}"
                )
            if err:
                (quarantine_dir / f"{exercise['id']}.json").write_text(
                    json.dumps(
                        {"exercise": exercise, "error": str(err), "raw_response": raw},
                        indent=2,
                    )
                )
                print(f"  ❌ {exercise['name']}  {err}", flush=True)
                _log(f"FAIL  [{completed}/{total}]  {exercise['name']}  {err}")
            else:
                record = make_record(exercise, fields, vocab_vers)
                (enriched_dir / f"{exercise['id']}.json").write_text(
                    json.dumps(record, indent=2)
                )
                print(f"  ✅ {exercise['name']}{usage_str}", flush=True)
                _log(f"OK    [{completed}/{total}]  {exercise['name']}{usage_str}")

    final_done = len(list(enriched_dir.glob("*.json")))
    final_quarantine = len(list(quarantine_dir.glob("*.json")))
    _log(f"DONE   {final_done} enriched  {final_quarantine} quarantined")
    print(f"\n{final_done} enriched, {final_quarantine} quarantined.")
