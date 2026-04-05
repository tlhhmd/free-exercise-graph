# Full Run Playbook

This is the safest end-to-end way to run `free-exercise-graph` locally.

If you want the short version for a specific task, use:

- [quickstart_graph.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_graph.md)
- [quickstart_mcp.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_mcp.md)
- [quickstart_app.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_app.md)

Use this document when you want to:
- rebuild from source truth
- preserve paid-for enrichment
- run a fresh enrichment pass
- validate the output
- freeze the result into a restorable bundle

If you follow this playbook, you should not need oral handholding.

---

## 1. Prepare the Environment

```bash
cd /Users/talha/Code/free-exercise-graph
pip install -e .
```

Set the API key for the provider you plan to use:

```bash
export ANTHROPIC_API_KEY=...
# or
export GEMINI_API_KEY=...
```

Optional sanity check:

```bash
python3 test_shacl.py
```

---

## 2. Snapshot Current Local State

Do this before any serious rebuild work, especially if you already paid for enrichment.

```bash
python3 pipeline/db_backup.py backup
python3 pipeline/export_enrichment.py
```

What this gives you:
- a full SQLite snapshot in `pipeline/backups/`
- a portable JSONL export in `pipeline/exports/`

If `export_enrichment.py` reports `0` entities, that means your current DB does not
contain persisted enrichment state.

---

## 3. Refresh Source Data Intentionally

Only do this if you actually want the latest upstream raw files.

```bash
python3 sources/free-exercise-db/fetch.py
python3 sources/functional-fitness-db/fetch.py
```

Skip this step if you want to work from the already-checked-in raw source data.

---

## 4. Build the Deterministic Pipeline

Safe default:

```bash
python3 pipeline/run.py --to build
```

This runs:
1. `canonicalize`
2. `identity`
3. `reconcile`
4. `build`

It does **not** spend API tokens.

Use this command when:
- you want a fresh deterministic graph
- you want to verify the source adapters and identity/reconcile logic
- you want to rebuild without touching enrichment

---

## 5. Restore Existing Enrichment If Needed

If you rebuilt onto a fresh deterministic DB and want to restore an earlier export:

```bash
python3 pipeline/import_enrichment.py pipeline/exports/enrichment-YYYYMMDD-HHMMSS.jsonl
python3 pipeline/build.py
```

Use `--replace-existing` only when you intentionally want the import artifact to win.

Use `--skip-missing-entities` only when you knowingly changed deterministic entity IDs
and want a partial restore.

---

## 6. Inspect What Would Be Enriched

Before spending tokens, check pending work:

```bash
python3 pipeline/enrich.py --dry-run
```

If you only want a small sample first:

```bash
python3 pipeline/enrich.py --limit 10
python3 pipeline/build.py
python3 pipeline/validate.py --verbose
```

---

## 7. Run Full Enrichment

Anthropic example:

```bash
python3 pipeline/run.py --with-enrich --to build --concurrency 4
```

Gemini example:

```bash
python3 pipeline/run.py --with-enrich --to build --provider gemini --concurrency 4
```

What happens automatically now:
- raw model responses are archived under `pipeline/artifacts/raw_responses/`
- enrichment is written to SQLite
- the canonical runner exports a JSONL snapshot to `pipeline/exports/`
- `graph.ttl` is rebuilt from the current DB

If you want to re-enrich specific entities:

```bash
python3 pipeline/enrich.py --force <entity_id> <entity_id>
python3 pipeline/build.py
```

---

## 8. Run the Quality Surfaces

Product/data quality scorecard:

```bash
python3 pipeline/validate.py --verbose
```

Ontology/shape regression harness:

```bash
python3 test_shacl.py
```

Optional full SHACL against the built graph:

```bash
python3 pipeline/validate.py --shacl
```

Interpretation:
- `test_shacl.py` protects ontology/shape behavior
- `pipeline/validate.py` tells you whether the built graph is healthy enough to ship/demo

If you also want a fresh accuracy workbook and scorer pass:

```bash
python3 evals/build_gold_sheet.py
python3 evals/eval.py
```

Notes:
- `build_gold_sheet.py` now seeds from live canonical entities in `pipeline.db`
- the default output is batched into 10-exercise files under `evals/unreviewed/`
- move reviewed batches into `evals/submitted/`
- `eval.py` reads submitted batches and skips rows and fields still marked `Pending`

---

## 9. Build Product Artifacts

Once `graph.ttl` is current and validation looks good, build the static substitute/app artifacts:

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
python3 app/build_observatory.py --out app
```

What this gives you:
- sparse similarity graph artifacts under `data/generated/`
- app-facing substitute buckets in `data/generated/exercise_substitute_ui.json`
- refreshed static app payloads in `app/`
- refreshed Builder View payload in `app/observatory.json`

If you are only operating the MCP server, you can stop at `graph.ttl`.
If you are shipping the static app, this step is part of the real publish path.

---

## 10. Freeze a Release Bundle

Once you have a graph state you want to keep, freeze it:

```bash
python3 pipeline/release_bundle.py
```

Each bundle contains:
- `pipeline.db`
- `graph.ttl` if present
- `enrichment.jsonl` if enrichment exists
- `quality_scorecard.json`
- `metadata.json`

This is the easiest artifact to copy to another machine or archive before risky work.

---

## 11. Start the MCP Server

```bash
python3 mcp_server.py
```

If you are not sure the graph is current, rebuild first:

```bash
python3 pipeline/run.py --to build
```

---

## 12. If You Truly Need a Destructive Rebuild

This should be rare.

```bash
python3 pipeline/run.py --reset-db --yes-reset-db --to build
```

What this does:
- auto-backs up the current SQLite DB unless you explicitly disable that behavior
- deletes `pipeline/pipeline.db`
- rebuilds deterministic state from source truth

Use this when:
- deterministic tables are inconsistent
- source-record membership changed in a way upstream stages can no longer replay safely
- you intentionally want a clean rebuild

Do **not** use this casually if you have unexported enrichment state.

---

## 13. Recovery Commands

Restore the latest SQLite backup:

```bash
python3 pipeline/db_backup.py restore --latest --yes
```

Restore a specific SQLite backup:

```bash
python3 pipeline/db_backup.py restore pipeline/backups/pipeline-YYYYMMDD-HHMMSS.db --yes
```

Restore a portable enrichment export into the current deterministic DB:

```bash
python3 pipeline/import_enrichment.py pipeline/exports/enrichment-YYYYMMDD-HHMMSS.jsonl
python3 pipeline/build.py
```

---

## 14. Recommended Operator Habits

For any meaningful paid run:
1. `python3 pipeline/db_backup.py backup`
2. `python3 pipeline/export_enrichment.py`
3. `python3 pipeline/run.py --with-enrich --to build ...`
4. `python3 pipeline/validate.py --verbose`
5. `python3 pipeline/release_bundle.py`

That gives you:
- a pre-run SQLite checkpoint
- a post-run SQLite state
- a portable enrichment artifact
- a built graph
- a machine-readable quality record

That is the current safest way to operate this project.
