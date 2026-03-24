"""
pipeline/batch_export.py

Stage 5 (batch variant): Submit all pending entities to the Gemini Batch API
in a single async job. Results come back within ~24 hours at 50% cost vs.
synchronous enrichment, with no RPD limit.

The batch job name is written to pipeline/batch_job_id.txt. A manifest JSON
(pipeline/batch_manifest.json) records entity_id → request index so that
batch_ingest.py can correlate responses even if metadata echo isn't available.

Usage:
    python3 pipeline/batch_export.py
    python3 pipeline/batch_export.py --model gemini-2.0-flash-001
    python3 pipeline/batch_export.py --dry-run   # count pending, no API call
    python3 pipeline/batch_export.py --limit 100 # submit a partial batch

Provider note:
    Batch jobs use the full system prompt per request (no context cache — the
    Gemini Batch API does not support cached_content). The 50% batch discount
    applies to all input tokens.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection
from enrichment.service import build_system_prompt, load_graphs, vocabulary_versions
from enrichment.schema import setup_validators, ExerciseEnrichment

# Reuse user message formatter from enrich.py
from pipeline.enrich import _format_user_message

_PROMPT_TEMPLATE = _PROJECT_ROOT / "enrichment" / "prompt_template.md"
_BATCH_JOB_ID_FILE = _PROJECT_ROOT / "pipeline" / "batch_job_id.txt"
_BATCH_MANIFEST_FILE = _PROJECT_ROOT / "pipeline" / "batch_manifest.json"

DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _build_request_config(system_prompt: str, types) -> object:
    """Build a GenerateContentConfig with structured output and thinking disabled."""
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=ExerciseEnrichment,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def submit_batch(
    *,
    model: str = DEFAULT_MODEL,
    limit: int | None = None,
    dry_run: bool = False,
    db_path: Path = DB_PATH,
) -> None:
    conn = get_connection(db_path)

    already_done = {
        r[0] for r in conn.execute("SELECT entity_id FROM enrichment_stamps").fetchall()
    }
    entities = conn.execute(
        "SELECT entity_id, display_name FROM entities ORDER BY entity_id"
    ).fetchall()
    pending = [e for e in entities if e["entity_id"] not in already_done]

    if limit:
        pending = pending[:limit]

    if dry_run:
        print(f"Pending: {len(pending)} / {len(entities)} entities")
        conn.close()
        return

    if not pending:
        print("Nothing to enrich — all entities done.")
        conn.close()
        return

    if _BATCH_JOB_ID_FILE.exists():
        existing = _BATCH_JOB_ID_FILE.read_text().strip()
        print(f"Warning: a batch job already exists: {existing}")
        print("Run batch_ingest.py to process it first, or delete batch_job_id.txt.")
        conn.close()
        return

    print("Loading ontology...")
    graphs = load_graphs()
    system_prompt = build_system_prompt(graphs, _PROMPT_TEMPLATE)
    setup_validators(graphs)

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)
    config = _build_request_config(system_prompt, types)

    print(f"Building {len(pending)} inline requests...")
    inlined_requests = []
    manifest = []  # [{entity_id, display_name, index}]

    for i, entity_row in enumerate(pending):
        entity_id = entity_row["entity_id"]
        display_name = entity_row["display_name"]
        user_msg = _format_user_message(conn, entity_id, display_name)

        inlined_requests.append(
            types.InlinedRequest(
                model=model,
                contents=user_msg,
                config=config,
                metadata={"entity_id": entity_id},
            )
        )
        manifest.append({"entity_id": entity_id, "display_name": display_name, "index": i})

    conn.close()

    print(f"Submitting batch job ({len(inlined_requests)} requests, model={model})...")
    t0 = time.monotonic()
    batch_job = client.batches.create(
        model=model,
        src=types.BatchJobSource(inlined_requests=inlined_requests),
        config=types.CreateBatchJobConfig(display_name="feg-enrichment"),
    )
    elapsed = time.monotonic() - t0

    _BATCH_JOB_ID_FILE.write_text(batch_job.name)
    _BATCH_MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))

    print(f"\nBatch job submitted in {elapsed:.1f}s")
    print(f"  Job name : {batch_job.name}")
    print(f"  State    : {batch_job.state}")
    print(f"  Requests : {len(inlined_requests)}")
    print(f"  Saved to : {_BATCH_JOB_ID_FILE}")
    print(f"  Manifest : {_BATCH_MANIFEST_FILE}")
    print()
    print("Next step: run `python3 pipeline/batch_ingest.py --wait` to poll and ingest.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a Gemini batch enrichment job.")
    parser.add_argument("--model",    default=DEFAULT_MODEL)
    parser.add_argument("--limit",    type=int, default=None)
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    submit_batch(model=args.model, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
