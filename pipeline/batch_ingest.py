"""
pipeline/batch_ingest.py

Polls a Gemini batch job and writes results to inferred_claims when done.

Reads the job name from pipeline/batch_job_id.txt (written by batch_export.py).
Uses pipeline/batch_manifest.json for entity_id → index correlation as a fallback
when response metadata is unavailable.

Usage:
    python3 pipeline/batch_ingest.py             # check status, ingest if done
    python3 pipeline/batch_ingest.py --wait      # block until complete, then ingest
    python3 pipeline/batch_ingest.py --job <name>  # override job name from file
    python3 pipeline/batch_ingest.py --status    # print job status and exit

After ingest completes, batch_job_id.txt and batch_manifest.json are removed.
Re-run pipeline/build.py to assemble the updated graph.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.artifacts import ARTIFACTS_DIR, make_timestamped_dir, utc_timestamp, write_json
from pipeline.db import DB_PATH, get_connection
from enrichment.service import load_graphs, vocabulary_versions
from enrichment.schema import setup_validators
from pipeline.enrich import _write_inferred

_BATCH_JOB_ID_FILE = _PROJECT_ROOT / "pipeline" / "batch_job_id.txt"
_BATCH_MANIFEST_FILE = _PROJECT_ROOT / "pipeline" / "batch_manifest.json"

# Poll interval and max wait
_POLL_INTERVAL_SECONDS = 60
_MAX_WAIT_HOURS = 48


def _job_is_terminal(state) -> bool:
    from google.genai import types
    return state in {
        types.JobState.JOB_STATE_SUCCEEDED,
        types.JobState.JOB_STATE_FAILED,
        types.JobState.JOB_STATE_CANCELLED,
        types.JobState.JOB_STATE_EXPIRED,
        types.JobState.JOB_STATE_PARTIALLY_SUCCEEDED,
    }


def _load_manifest() -> dict[str, str]:
    """Return index → entity_id mapping from batch_manifest.json."""
    if not _BATCH_MANIFEST_FILE.exists():
        return {}
    rows = json.loads(_BATCH_MANIFEST_FILE.read_text())
    return {str(r["index"]): r["entity_id"] for r in rows}


def ingest(
    *,
    job_name: str | None = None,
    wait: bool = False,
    db_path: Path = DB_PATH,
) -> None:
    from google import genai
    from google.genai import types
    from enrichment.service import parse_enrichment as _parse

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    if not job_name:
        if not _BATCH_JOB_ID_FILE.exists():
            print("No batch job found. Run batch_export.py first.")
            return
        job_name = _BATCH_JOB_ID_FILE.read_text().strip()

    print(f"Job: {job_name}")

    # Poll loop
    deadline = time.monotonic() + _MAX_WAIT_HOURS * 3600
    while True:
        job = client.batches.get(name=job_name)
        state = job.state
        stats = job.completion_stats
        stats_str = ""
        if stats:
            stats_str = (
                f"  succeeded={stats.succeeded_count or 0}"
                f"  failed={stats.failed_count or 0}"
                f"  total={stats.total_count or 0}"
            )
        print(f"  State: {state}{stats_str}")

        if _job_is_terminal(state):
            break

        if not wait:
            print("Job still running. Re-run with --wait to block, or check again later.")
            return

        if time.monotonic() > deadline:
            print(f"Timed out after {_MAX_WAIT_HOURS}h. Check job status manually.")
            return

        print(f"  Waiting {_POLL_INTERVAL_SECONDS}s...")
        time.sleep(_POLL_INTERVAL_SECONDS)

    if state != types.JobState.JOB_STATE_SUCCEEDED and state != types.JobState.JOB_STATE_PARTIALLY_SUCCEEDED:
        print(f"Job ended with state {state}. No results to ingest.")
        if job.error:
            print(f"  Error: {job.error}")
        return

    # Extract inline responses
    dest = job.dest
    if not dest or not dest.inlined_responses:
        print("No inline responses in job result.")
        return

    responses = dest.inlined_responses
    print(f"\nIngesting {len(responses)} responses...")
    archive_dir = make_timestamped_dir(ARTIFACTS_DIR / "raw_responses", "batch-ingest", job_name)
    write_json(
        archive_dir / "manifest.json",
        {
            "started_at": utc_timestamp(compact=False),
            "job_name": job_name,
            "db_path": str(db_path),
            "response_count": len(responses),
        },
    )
    print(f"Archiving batch responses to {archive_dir}")

    # Build manifest for fallback entity_id lookup
    manifest = _load_manifest()

    # Load ontology for vocab versions
    from enrichment.service import load_graphs
    graphs = load_graphs()
    vocab_vers = vocabulary_versions(graphs)
    setup_validators(graphs)

    conn = get_connection(db_path)
    ok = 0
    failed = 0

    for i, inlined_resp in enumerate(responses):
        # Resolve entity_id: prefer metadata echo, fall back to manifest index
        meta = inlined_resp.metadata or {}
        entity_id = meta.get("entity_id") or manifest.get(str(i))

        if not entity_id:
            print(f"  ⚠️  [{i}] Could not resolve entity_id — skipping")
            write_json(
                archive_dir / f"unresolved-{i}.json",
                {
                    "index": i,
                    "captured_at": utc_timestamp(compact=False),
                    "entity_id": None,
                    "metadata": meta,
                    "error": "Could not resolve entity_id",
                },
            )
            failed += 1
            continue

        if inlined_resp.error:
            print(f"  ❌ [{i}] {entity_id}  error={inlined_resp.error}", flush=True)
            write_json(
                archive_dir / f"{entity_id}.json",
                {
                    "index": i,
                    "captured_at": utc_timestamp(compact=False),
                    "entity_id": entity_id,
                    "metadata": meta,
                    "raw_response": None,
                    "parsed_fields": None,
                    "error": str(inlined_resp.error),
                },
            )
            failed += 1
            continue

        resp = inlined_resp.response
        if not resp or not resp.text:
            print(f"  ❌ [{i}] {entity_id}  empty response", flush=True)
            write_json(
                archive_dir / f"{entity_id}.json",
                {
                    "index": i,
                    "captured_at": utc_timestamp(compact=False),
                    "entity_id": entity_id,
                    "metadata": meta,
                    "raw_response": None,
                    "parsed_fields": None,
                    "error": "empty response",
                },
            )
            failed += 1
            continue

        try:
            enrichment = _parse(resp.text)
            fields = enrichment.model_dump(exclude_none=True)
        except Exception as e:
            print(f"  ❌ [{i}] {entity_id}  parse error: {e}", flush=True)
            write_json(
                archive_dir / f"{entity_id}.json",
                {
                    "index": i,
                    "captured_at": utc_timestamp(compact=False),
                    "entity_id": entity_id,
                    "metadata": meta,
                    "raw_response": resp.text,
                    "parsed_fields": None,
                    "error": str(e),
                },
            )
            failed += 1
            continue

        with get_connection(db_path) as write_conn:
            # Clear any prior inferred claims (in case of partial re-run)
            write_conn.execute("DELETE FROM inferred_claims WHERE entity_id = ?", (entity_id,))
            write_conn.execute("DELETE FROM enrichment_stamps WHERE entity_id = ?", (entity_id,))
            _write_inferred(write_conn, entity_id, fields, vocab_vers)
        write_json(
            archive_dir / f"{entity_id}.json",
            {
                "index": i,
                "captured_at": utc_timestamp(compact=False),
                "entity_id": entity_id,
                "metadata": meta,
                "raw_response": resp.text,
                "parsed_fields": fields,
                "warnings": [
                    {"predicate": predicate, "stripped_value": stripped_value}
                    for predicate, stripped_value in enrichment._warnings
                ],
                "error": None,
            },
        )

        ok += 1
        if ok % 100 == 0:
            print(f"  ... {ok} done so far", flush=True)

    conn.close()

    total_enriched = get_connection(db_path).execute(
        "SELECT COUNT(*) FROM enrichment_stamps"
    ).fetchone()[0]
    total_entities = get_connection(db_path).execute(
        "SELECT COUNT(*) FROM entities"
    ).fetchone()[0]

    print(f"\nIngest complete: {ok} ok, {failed} failed")
    print(f"{total_enriched} / {total_entities} entities enriched total")

    # Clean up batch tracking files
    if failed == 0:
        _BATCH_JOB_ID_FILE.unlink(missing_ok=True)
        _BATCH_MANIFEST_FILE.unlink(missing_ok=True)
        print("Cleaned up batch_job_id.txt and batch_manifest.json.")
    else:
        print(f"Kept batch_job_id.txt and batch_manifest.json ({failed} failed — inspect manually).")

    print("\nNext step: python3 pipeline/build.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Gemini batch enrichment results.")
    parser.add_argument("--job",    default=None, help="batch job name (default: from batch_job_id.txt)")
    parser.add_argument("--wait",   action="store_true", help="poll until complete")
    parser.add_argument("--status", action="store_true", help="print job status and exit")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    if args.status:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        job_name = args.job or (
            _BATCH_JOB_ID_FILE.read_text().strip() if _BATCH_JOB_ID_FILE.exists() else None
        )
        if not job_name:
            print("No batch job found.")
            return
        job = client.batches.get(name=job_name)
        stats = job.completion_stats
        stats_str = ""
        if stats:
            stats_str = (
                f"  succeeded={stats.succeeded_count or 0}"
                f"  failed={stats.failed_count or 0}"
                f"  total={stats.total_count or 0}"
            )
        print(f"Job  : {job_name}")
        print(f"State: {job.state}{stats_str}")
        if job.create_time:
            print(f"Created  : {job.create_time}")
        if job.end_time:
            print(f"Completed: {job.end_time}")
        return

    ingest(job_name=args.job, wait=args.wait)


if __name__ == "__main__":
    main()
