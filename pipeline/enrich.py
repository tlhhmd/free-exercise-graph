"""
pipeline/enrich.py

Stage 4: Single LLM pass per canonical entity.

Reads resolved_claims per entity, formats a user message, calls the LLM via
the configured provider, and writes inferred claims to inferred_claims.
Asserted resolved_claims always take precedence — enrichment only fills gaps.

Provider selection (in priority order):
  --provider / --model CLI flags
  FEG_PROVIDER / FEG_MODEL env vars
  Defaults: anthropic / claude-sonnet-4-6

Usage:
    python3 pipeline/enrich.py
    python3 pipeline/enrich.py --limit 10 --concurrency 4
    python3 pipeline/enrich.py --provider gemini
    python3 pipeline/enrich.py --provider gemini --model gemini-3.1-pro-preview --thinking low
    python3 pipeline/enrich.py --force <entity_id>
    python3 pipeline/enrich.py --dump-prompts <DIR>
    python3 pipeline/enrich.py --dry-run     # count pending, no API calls
"""

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection
from enrichment.providers import make_provider
from enrichment.service import (
    build_system_prompt,
    load_graphs,
    parse_enrichment,
    vocabulary_versions,
)
from enrichment.schema import setup_validators

_PROMPT_TEMPLATE = _PROJECT_ROOT / "enrichment" / "prompt_template.md"


# ─── User message formatting ──────────────────────────────────────────────────

def _format_user_message(conn, entity_id: str, display_name: str) -> str:
    lines = [f"Name: {display_name}", ""]

    # Resolved claims
    rows = conn.execute(
        "SELECT predicate, value, qualifier FROM resolved_claims WHERE entity_id = ? ORDER BY predicate, value",
        (entity_id,),
    ).fetchall()

    by_pred: dict[str, list] = {}
    for r in rows:
        by_pred.setdefault(r["predicate"], []).append((r["value"], r["qualifier"]))

    context_lines = []

    if "muscle" in by_pred:
        with_degree = [
            f"{v} ({q})" if q else v
            for v, q in by_pred["muscle"]
        ]
        context_lines.append(f"  Muscles: {', '.join(with_degree)}")

    if "movement_pattern" in by_pred:
        vals = [v for v, _ in by_pred["movement_pattern"]]
        context_lines.append(f"  Movement patterns: {', '.join(vals)}")

    if "laterality" in by_pred:
        val = by_pred["laterality"][0][0]
        context_lines.append(f"  Laterality: {val}")

    if "plane_of_motion" in by_pred:
        vals = [v for v, _ in by_pred["plane_of_motion"]]
        context_lines.append(f"  Plane of motion: {', '.join(vals)}")

    if "is_combination" in by_pred:
        val = by_pred["is_combination"][0][0]
        context_lines.append(f"  Is combination: {val}")

    if "is_compound" in by_pred:
        val = by_pred["is_compound"][0][0]
        context_lines.append(f"  Is compound: {val}")

    if "exercise_style" in by_pred:
        vals = [v for v, _ in by_pred["exercise_style"]]
        context_lines.append(f"  Exercise style: {', '.join(vals)}")

    if "training_modality_hint" in by_pred:
        vals = [v for v, _ in by_pred["training_modality_hint"]]
        context_lines.append(f"  Training modality (from source): {', '.join(vals)}")

    if "movement_pattern_hint" in by_pred:
        vals = [v for v, _ in by_pred["movement_pattern_hint"]]
        context_lines.append(f"  Movement pattern hint (from source): {', '.join(vals)}")

    if context_lines:
        lines.append("Known from sources (use as strong hints):")
        lines.extend(context_lines)
        lines.append("")
        lines.append(
            "Source muscle hints guide degrees "
            "(PrimeMover/Synergist/Stabilizer/PassiveTarget). "
            "Override with your judgment. Add any muscles the source omitted."
        )

    # Joint action hints (from source — primary/supporting routing is LLM's job)
    if "joint_action_hint" in by_pred:
        vals = [v for v, _ in by_pred["joint_action_hint"]]
        lines.append("")
        lines.append(
            f"Joint actions from source (assign to primary or supporting): "
            f"{', '.join(vals)}"
        )

    # Instructions text (fed exercises)
    # Get from entity_sources → source_metadata
    meta_rows = conn.execute(
        """SELECT sm.instructions
           FROM source_metadata sm
           JOIN entity_sources es ON sm.source = es.source AND sm.source_id = es.source_id
           WHERE es.entity_id = ? AND sm.instructions IS NOT NULL AND sm.instructions != ''
           LIMIT 1""",
        (entity_id,),
    ).fetchall()
    if meta_rows:
        instructions = meta_rows[0]["instructions"]
        lines.append("")
        lines.append(f"Instructions: {instructions}")

    return "\n".join(lines)


# ─── Writing inferred claims ──────────────────────────────────────────────────

def _write_inferred(conn, entity_id: str, fields: dict, vocab_versions: dict) -> None:
    """Write LLM output to inferred_claims and enrichment_stamps."""
    rows = []

    for mi in fields.get("muscle_involvements", []):
        rows.append((entity_id, "muscle", mi["muscle"], mi["degree"]))

    for mp in fields.get("movement_patterns", []):
        rows.append((entity_id, "movement_pattern", mp, None))

    for ja in fields.get("primary_joint_actions", []):
        rows.append((entity_id, "primary_joint_action", ja, None))

    for ja in fields.get("supporting_joint_actions", []):
        rows.append((entity_id, "supporting_joint_action", ja, None))

    for tm in fields.get("training_modalities", []):
        rows.append((entity_id, "training_modality", tm, None))

    for pom in fields.get("plane_of_motion", []):
        rows.append((entity_id, "plane_of_motion", pom, None))

    for es in fields.get("exercise_style", []):
        rows.append((entity_id, "exercise_style", es, None))

    for pred, key in [
        ("is_compound",   "is_compound"),
        ("is_combination","is_combination"),
    ]:
        val = fields.get(key)
        if val is not None:
            rows.append((entity_id, pred, "true" if val else "false", None))

    if laterality := fields.get("laterality"):
        rows.append((entity_id, "laterality", laterality, None))

    conn.executemany(
        "INSERT INTO inferred_claims (entity_id, predicate, value, qualifier) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        "INSERT OR REPLACE INTO enrichment_stamps (entity_id, versions_json, enriched_at) VALUES (?, ?, ?)",
        (entity_id, json.dumps(vocab_versions), datetime.now(timezone.utc).isoformat()),
    )


# ─── Main enrichment loop ─────────────────────────────────────────────────────

def run(
    *,
    limit: int | None = None,
    concurrency: int = 1,
    force: list[str] | None = None,
    dump_prompts_dir: Path | None = None,
    dry_run: bool = False,
    provider: str | None = None,
    model: str | None = None,
    thinking_level: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    conn = get_connection(db_path)

    already_done = {r[0] for r in conn.execute("SELECT entity_id FROM enrichment_stamps").fetchall()}

    entities = conn.execute(
        "SELECT entity_id, display_name FROM entities ORDER BY entity_id"
    ).fetchall()

    if force:
        force_set = set(force)
        pending = [e for e in entities if e["entity_id"] in force_set]
        # Remove existing stamps for forced re-enrichment
        with conn:
            for eid in force_set:
                conn.execute("DELETE FROM enrichment_stamps WHERE entity_id = ?", (eid,))
                conn.execute("DELETE FROM inferred_claims WHERE entity_id = ?", (eid,))
    else:
        pending = [e for e in entities if e["entity_id"] not in already_done]

    if limit:
        pending = list(pending)
        random.shuffle(pending)
        pending = pending[:limit]

    if dry_run:
        print(f"Pending: {len(pending)} / {len(entities)} entities")
        conn.close()
        return

    if not pending:
        print("Nothing to enrich — all entities done.")
        conn.close()
        return

    print("Loading ontology...")
    graphs = load_graphs()
    system_prompt = build_system_prompt(graphs, _PROMPT_TEMPLATE)
    vocab_vers = vocabulary_versions(graphs)
    setup_validators(graphs)

    if dump_prompts_dir is not None:
        dump_prompts_dir = Path(dump_prompts_dir)
        dump_prompts_dir.mkdir(parents=True, exist_ok=True)
        (dump_prompts_dir / "system_prompt.txt").write_text(system_prompt)
        for e in pending:
            msg = _format_user_message(conn, e["entity_id"], e["display_name"])
            (dump_prompts_dir / f"{e['entity_id']}.txt").write_text(msg)
        print(f"Saved system_prompt.txt + {len(pending)} prompts to {dump_prompts_dir}")
        conn.close()
        return

    llm = make_provider(provider=provider, model=model, thinking_level=thinking_level)
    total = len(pending)
    print(f"Enriching {total} entities (provider={llm.__class__.__name__} model={llm.model} concurrency={concurrency})...")

    def process(entity_row):
        entity_id    = entity_row["entity_id"]
        display_name = entity_row["display_name"]
        thread_conn = get_connection(db_path)
        user_msg = _format_user_message(thread_conn, entity_id, display_name)
        thread_conn.close()
        try:
            raw, usage = llm.call(system_prompt, user_msg)
            enrichment = parse_enrichment(raw)
            return entity_id, display_name, enrichment.model_dump(exclude_none=True), usage, None
        except Exception as e:
            return entity_id, display_name, None, None, e

    completed = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process, e): e for e in pending}
        for future in as_completed(futures):
            entity_id, display_name, fields, usage, err = future.result()
            completed += 1
            if err:
                print(f"  ❌ [{completed}/{total}] {display_name}  {err}", flush=True)
            else:
                with get_connection(db_path) as write_conn:
                    _write_inferred(write_conn, entity_id, fields, vocab_vers)
                usage_str = f"  {usage}" if usage else ""
                print(f"  ✅ [{completed}/{total}] {display_name}{usage_str}", flush=True)

    done_count = conn.execute("SELECT COUNT(*) FROM enrichment_stamps").fetchone()[0]
    conn.close()
    print(f"\n{done_count} / {len(entities)} entities enriched.")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM enrichment for canonical entities.")
    parser.add_argument("--limit",       type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--force",       nargs="+", metavar="ENTITY_ID")
    parser.add_argument("--dump-prompts", type=Path, default=None, metavar="DIR")
    parser.add_argument("--dry-run",      action="store_true")
    parser.add_argument("--provider",     default=None, help="anthropic or gemini (default: FEG_PROVIDER env var, else anthropic)")
    parser.add_argument("--model",        default=None, help="model id (default: FEG_MODEL env var, else provider default)")
    parser.add_argument("--thinking",     default=None, metavar="LEVEL",
                        help="Gemini thinking level: minimal | low | medium | high")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    run(
        limit=args.limit,
        concurrency=args.concurrency,
        force=args.force,
        dump_prompts_dir=args.dump_prompts,
        dry_run=args.dry_run,
        provider=args.provider,
        model=args.model,
        thinking_level=args.thinking,
    )


if __name__ == "__main__":
    main()
