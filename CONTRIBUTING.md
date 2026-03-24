# Contributing

This document covers the operational ground rules for working on `free-exercise-graph`.
Read `DECISIONS.md` for the full ADR history before making any ontology or pipeline change.

---

## Where to Start

1. **Read `DECISIONS.md`** — every non-trivial decision is documented there. Check it before touching ontology files or pipeline behaviour. ADRs are numbered sequentially; the highest number is the most recent.
2. **Read `TODO.md`** — current open items in priority order.
3. **Confirm your environment is healthy** before making changes:

```bash
pip install -e .
python3 pipeline/build.py
python3 test_shacl.py
```

---

## What Requires an ADR

Write an ADR in `DECISIONS.md` before (or immediately after) making any of the following:

| Change type | Examples |
|---|---|
| Vocabulary additions | New muscle concept, new movement pattern, new joint action |
| Vocabulary removals | Retiring a concept, merging two concepts |
| URI renames | Any change to a `feg:` local name |
| Version bumps | Any `owl:versionInfo` change in an ontology file |
| Pipeline behaviour | Enrichment prompt rule change, new output field, build logic changes |
| SHACL constraint changes | Tightening or relaxing `sh:minCount`, adding a new shape |

**Hard rule: never add or remove vocabulary concepts without an ADR.** This includes muscles,
movement patterns, joint actions, training modalities, and involvement degrees.

ADRs are numbered sequentially (ADR-001, ADR-002, …). Add new ones at the bottom of
`DECISIONS.md`. Record: the decision, the rationale, and any alternatives considered.

---

## Vocabulary Versioning

All ontology files carry `owl:versionInfo` (semver). Bump the version in the relevant file
whenever you make a change:

| Change type | Version component |
|---|---|
| Removing concepts, renaming URIs | MAJOR |
| Adding new concepts or properties | MINOR |
| Correcting labels, comments, editorial notes | PATCH |

Bump only the file(s) that changed. After bumping a version, any previously enriched entities
whose `enrichment_stamps.versions_json` is behind the new version will need re-enrichment.
Use `pipeline/enrich.py --force <entity_id>` to re-enrich specific entities, or clear stamps
and re-run the full enrichment pass.

---

## Which Outputs Are Committed vs. Derived

| File | Status | Notes |
|---|---|---|
| `sources/*/raw/` | **Committed, read-only** | Upstream source data — never modify directly |
| `sources/*/mappings/` | **Committed** | Crosswalk CSVs used by adapters |
| `pipeline/pipeline.db` | Gitignored (derived) | SQLite intermediate store — rebuilt by pipeline stages |
| `pipeline/gemini_cache_id.txt` | Gitignored (runtime) | Gemini context cache ID — persists across sessions |
| `graph.ttl` | Gitignored (derived) | Assembled by `pipeline/build.py` |

---

## Safe Scripts to Run

| Script | Effect |
|---|---|
| `sources/<source>/fetch.py` | Overwrites raw source data from upstream — only run intentionally |
| `pipeline/identity.py` | Writes to `pipeline.db`; read-only against source files |
| `pipeline/canonicalize.py` | Writes to `pipeline.db`; read-only against source files |
| `pipeline/reconcile.py` | Writes to `pipeline.db`; no API calls |
| `pipeline/triage.py` | Writes to `pipeline.db`; interactive; applies merges immediately |
| `pipeline/enrich.py` | Writes inferred claims to `pipeline.db`; **costs API tokens** |
| `pipeline/build.py` | Writes `graph.ttl` (gitignored) |
| `test_shacl.py` | Read-only; exits 0/1 — CI gate |

### Enrichment options

```bash
# Default provider (Anthropic)
python3 pipeline/enrich.py --concurrency 4

# Gemini (synchronous — subject to 250 RPD limit)
python3 pipeline/enrich.py --provider gemini
python3 pipeline/enrich.py --provider gemini --model gemini-3.1-pro-preview
python3 pipeline/enrich.py --provider gemini --thinking low

# Override model via env var
FEG_PROVIDER=gemini FEG_MODEL=gemini-3.1-pro-preview python3 pipeline/enrich.py

# Useful flags
python3 pipeline/enrich.py --dry-run              # count pending, no API calls
python3 pipeline/enrich.py --limit 10             # enrich a sample
python3 pipeline/enrich.py --force <entity_id>    # re-enrich a specific entity
python3 pipeline/enrich.py --dump-prompts ./out   # save prompts without calling API
```

### Gemini Batch API (faster, 50% cheaper)

Submits all pending entities as a single async job — no RPD limit, results in ~24h.

```bash
# Step 1: submit the batch job (saves job name to pipeline/batch_job_id.txt)
python3 pipeline/batch_export.py
python3 pipeline/batch_export.py --dry-run     # count pending, no API call
python3 pipeline/batch_export.py --limit 100   # partial batch for testing

# Step 2: poll and ingest when done
python3 pipeline/batch_ingest.py --status      # check job state
python3 pipeline/batch_ingest.py --wait        # block until complete, then ingest
python3 pipeline/batch_ingest.py               # ingest if already done

# Step 3: build graph
python3 pipeline/build.py
```

Batch tracking files (`pipeline/batch_job_id.txt`, `pipeline/batch_manifest.json`) are
gitignored and removed automatically after a clean ingest.

---

## Namespace

All URIs use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent
domain. Do not use this namespace for any external publication until it is replaced.
Import `FEG_NS` from `constants.py` — never hardcode the namespace string in Python files.

---

## Pipeline Dependency Order

```
sources/*/fetch.py
        ↓
pipeline/canonicalize.py
        ↓
pipeline/identity.py
        ↓
pipeline/reconcile.py
        ↓
pipeline/enrich.py
        ↓
pipeline/build.py
        ↓
test_shacl.py
```

`test_shacl.py` can run at any point — it uses in-memory test fixtures, not `graph.ttl`.

Each stage is resumable: re-running a stage picks up where it left off. `enrich.py` skips
entities that already have an `enrichment_stamps` entry. Use `--force` to override.
