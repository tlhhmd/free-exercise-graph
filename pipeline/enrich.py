"""
enrich.py

Enriches exercises from dist/exercises.json by calling the Anthropic API
to classify each exercise with movement patterns, training modalities,
muscle involvements, and unilateral flag.

Output:
    data/enriched/<id>.json   - source fields preserved, enrichment added
    data/quarantine/<id>.json - exercises that failed enrichment

Usage:
    python enrich.py                         # enrich all exercises
    python enrich.py --limit 20              # enrich first N exercises
    python enrich.py --id Barbell_Deadlift   # enrich a single exercise by id

Idempotent: already-enriched exercises are skipped unless --force is passed.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from prompt import SYSTEM_PROMPT, format_user_message

# ─── Paths ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
_EXERCISES_JSON = _HERE.parent / "dist" / "exercises.json"
_ENRICHED_DIR = _HERE.parent / "data" / "enriched"
_QUARANTINE_DIR = _HERE.parent / "data" / "quarantine"

# ─── Config ───────────────────────────────────────────────────────────────────

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
CONCURRENCY = 1  # max simultaneous API calls

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── Valid values (populated at startup from ontology files) ──────────────────

_VALID_MUSCLES: set[str] = set()
_VALID_PATTERNS: set[str] = set()
_VALID_MODALITIES = {"Strength", "Hypertrophy", "Cardio", "Mobility", "Plyometrics"}
_VALID_DEGREES = {"PrimeMover", "Synergist", "Stabilizer"}

_VOCAB_VERSIONS: dict[str, str] = {}  # populated by _load_valid_values


def _load_valid_values() -> None:
    """Populate valid value sets and vocabulary versions from ontology files."""
    from rdflib import Graph, Namespace, OWL, URIRef
    from rdflib.namespace import SKOS

    feg = Namespace("https://placeholder.url#")
    ont_dir = _HERE.parent / "ontology"

    def local(uri):
        s = str(uri)
        return s.split("#")[-1] if "#" in s else s.split("/")[-1]

    # muscles
    g_muscles = Graph()
    g_muscles.parse(ont_dir / "muscles.ttl", format="turtle")
    for concept in g_muscles.subjects(SKOS.inScheme, feg.MuscleScheme):
        _VALID_MUSCLES.add(local(concept))
    v = g_muscles.value(feg.MuscleScheme, OWL.versionInfo)
    _VOCAB_VERSIONS["muscles"] = str(v) if v else "unknown"

    # movement patterns
    g_patterns = Graph()
    g_patterns.parse(ont_dir / "movement_patterns.ttl", format="turtle")
    for concept in g_patterns.subjects(SKOS.inScheme, feg.MovementPatternScheme):
        _VALID_PATTERNS.add(local(concept))
    v = g_patterns.value(feg.MovementPatternScheme, OWL.versionInfo)
    _VOCAB_VERSIONS["movement_patterns"] = str(v) if v else "unknown"

    # flat vocabularies - version only, no valid-value sets needed
    flat_vocabs = [
        (
            "involvement_degrees",
            "involvement_degrees.ttl",
            feg.InvolvementDegreeVocabulary,
        ),
        (
            "training_modalities",
            "training_modalities.ttl",
            feg.TrainingModalityVocabulary,
        ),
        ("shapes", "shapes.ttl", feg.ShapesGraph),
        ("ontology", "ontology.ttl", URIRef("https://placeholder.url#")),
    ]
    for key, filename, subject in flat_vocabs:
        g = Graph()
        g.parse(ont_dir / filename, format="turtle")
        v = g.value(subject, OWL.versionInfo)
        _VOCAB_VERSIONS[key] = str(v) if v else "unknown"

    log.info(
        "vocabulary versions — %s",
        ", ".join(f"{k}: {v}" for k, v in _VOCAB_VERSIONS.items()),
    )


# ─── Validation ───────────────────────────────────────────────────────────────


def _validate(exercise_id: str, data: dict) -> list[str]:
    """
    Lightweight structural validation of LLM output.
    Returns a list of error strings. Empty list means valid.
    """
    errors = []

    # movement_patterns
    patterns = data.get("movement_patterns")
    if not patterns or not isinstance(patterns, list):
        errors.append("movement_patterns missing or empty")
    else:
        for p in patterns:
            if p not in _VALID_PATTERNS:
                errors.append(f"unknown movement pattern: {p!r}")

    # training_modalities (optional)
    modalities = data.get("training_modalities", [])
    if not isinstance(modalities, list):
        errors.append("training_modalities must be a list")
    else:
        for m in modalities:
            if m not in _VALID_MODALITIES:
                errors.append(f"unknown training modality: {m!r}")

    # muscle_involvements
    involvements = data.get("muscle_involvements")
    if not involvements or not isinstance(involvements, list):
        errors.append("muscle_involvements missing or empty")
    else:
        has_prime = False
        for inv in involvements:
            muscle = inv.get("muscle")
            degree = inv.get("degree")
            if muscle not in _VALID_MUSCLES:
                errors.append(f"unknown muscle: {muscle!r}")
            if degree not in _VALID_DEGREES:
                errors.append(f"unknown degree: {degree!r}")
            if degree == "PrimeMover":
                has_prime = True
        if not has_prime:
            errors.append("no PrimeMover found in muscle_involvements")

    # is_unilateral (optional, must be boolean if present)
    if "is_unilateral" in data and not isinstance(data["is_unilateral"], bool):
        errors.append("is_unilateral must be a boolean")

    return errors


# ─── Core enrichment ──────────────────────────────────────────────────────────


async def _enrich_one(
    client: anthropic.AsyncAnthropic,
    exercise: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[str, dict | None, str | None]:
    """
    Enrich a single exercise. Returns (id, enriched_dict, error_message).
    enriched_dict is None on failure; error_message is None on success.
    """
    exercise_id = exercise["id"]

    async with semaphore:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": format_user_message(exercise)}],
            )
        except anthropic.APIError as exc:
            return exercise_id, None, f"API error: {exc}"

    await asyncio.sleep(2)
    raw = response.content[0].text.strip()

    # strip accidental markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(line for line in lines if not line.startswith("```")).strip()

    try:
        enrichment = json.loads(raw)
    except json.JSONDecodeError as exc:
        return exercise_id, None, f"JSON parse error: {exc}\nRaw response:\n{raw}"

    errors = _validate(exercise_id, enrichment)
    if errors:
        return exercise_id, None, "Validation errors:\n" + "\n".join(errors)

    from datetime import datetime, timezone

    enriched = {
        **exercise,
        **enrichment,
        "vocabulary_versions": dict(_VOCAB_VERSIONS),
        "enriched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return exercise_id, enriched, None


# ─── I/O helpers ──────────────────────────────────────────────────────────────


def _output_path(exercise_id: str) -> Path:
    return _ENRICHED_DIR / f"{exercise_id}.json"


def _quarantine_path(exercise_id: str) -> Path:
    return _QUARANTINE_DIR / f"{exercise_id}.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────


async def _run(exercises: list[dict], force: bool) -> None:
    import httpx

    async with httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=CONCURRENCY,
            max_keepalive_connections=CONCURRENCY,
            keepalive_expiry=30,
        )
    ) as http_client:
        client = anthropic.AsyncAnthropic(http_client=http_client)
        await _run_with_client(client, exercises, force)


async def _run_with_client(
    client: anthropic.AsyncAnthropic,
    exercises: list[dict],
    force: bool,
) -> None:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    to_process = []
    skipped = 0
    for ex in exercises:
        path = _output_path(ex["id"])
        if path.exists() and not force:
            skipped += 1
        else:
            to_process.append(ex)

    if skipped:
        log.info(
            "skipping %d already-enriched exercises (use --force to re-enrich)",
            skipped,
        )

    if not to_process:
        log.info("nothing to do")
        return

    log.info(
        "enriching %d exercises (concurrency=%d, model=%s)",
        len(to_process),
        CONCURRENCY,
        MODEL,
    )

    tasks = [_enrich_one(client, ex, semaphore) for ex in to_process]

    success = 0
    quarantined = 0

    for coro in asyncio.as_completed(tasks):
        exercise_id, enriched, error = await coro

        if enriched is not None:
            _write_json(_output_path(exercise_id), enriched)
            quarantine_file = _quarantine_path(exercise_id)
            if quarantine_file.exists():
                quarantine_file.unlink()
                log.info("ok          %s (quarantine cleared)", exercise_id)
            else:
                log.info("ok          %s", exercise_id)
            success += 1
        else:
            _write_json(
                _quarantine_path(exercise_id),
                {"id": exercise_id, "error": error},
            )
            quarantined += 1
            log.warning(
                "quarantine  %s  %s",
                exercise_id,
                error.splitlines()[0],
            )

    log.info(
        "done — %d enriched, %d quarantined, %d skipped",
        success,
        quarantined,
        skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich exercises with LLM classification."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N exercises.",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Process a single exercise by id.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich even if output already exists.",
    )
    args = parser.parse_args()

    _load_valid_values()

    with open(_EXERCISES_JSON, encoding="utf-8") as f:
        exercises = json.load(f)

    if args.id:
        exercises = [ex for ex in exercises if ex["id"] == args.id]
        if not exercises:
            log.error("no exercise found with id %r", args.id)
            sys.exit(1)
    elif args.limit:
        exercises = exercises[: args.limit]

    asyncio.run(_run(exercises, force=args.force))


if __name__ == "__main__":
    main()
