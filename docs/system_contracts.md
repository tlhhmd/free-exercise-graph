# System Contracts

This document explains the operational boundaries of `free-exercise-graph`:
what is source truth, what is derived, and how to rebuild safely.

For the relational table-level contract, see [docs/sqlite_data_model.md](/Users/talha/Code/free-exercise-graph/docs/sqlite_data_model.md).

---

## Source of Truth

These are authoritative inputs:

- `ontology/*.ttl`
- `sources/*/raw/*`
- `sources/*/mappings/*`
- `DECISIONS.md`

These are not manually edited:

- `pipeline/pipeline.db`
- `pipeline/exports/*.jsonl`
- `pipeline/artifacts/raw_responses/`
- `pipeline/releases/`
- `graph.ttl`
- `data/generated/*.json`
- `app/data.json`
- `app/vocab.json`
- `app/exercise_substitute_ui.json`
- `app/observatory.json`
- quality reports and temporary batch/runtime files

---

## Pipeline Truth Layers

The system intentionally has five truth layers:

1. **Source truth**
   Raw source records plus crosswalks.

2. **Deterministic derived truth**
   SQLite tables created by:
   - `pipeline/canonicalize.py`
   - `pipeline/identity.py`
   - `pipeline/reconcile.py`

   These can be rebuilt from source truth.

3. **LLM-derived truth**
   SQLite tables created by `pipeline/enrich.py`:
   - `inferred_claims`
   - `enrichment_stamps`
   - `enrichment_warnings`
   - `enrichment_failures`

   These are derived, but not free to regenerate. Existing enrichment state is preserved by default.

4. **Durable recovery artifacts**
   Files written outside SQLite:
   - `pipeline/exports/*.jsonl`
   - `pipeline/artifacts/raw_responses/`
   - `pipeline/releases/`

   These exist so paid-for enrichment can survive DB resets, machine moves, and release cutovers.

5. **Product delivery artifacts**
   Files built from the current graph for the static app:
   - `data/generated/exercise_features.json`
   - `data/generated/exercise_similarity_edges.json`
   - `data/generated/exercise_neighbors.json`
   - `data/generated/exercise_communities.json`
   - `data/generated/build_metrics.json`
   - `data/generated/exercise_substitute_ui.json`
   - `app/data.json`
   - `app/vocab.json`
   - `app/exercise_substitute_ui.json`
   - `app/observatory.json`

   These are deterministic derived artifacts. They are committed for deployment convenience, but they are not source truth.

Fresh-clone implication:
- a deterministic rebuild works from committed source truth
- a fully enriched graph requires either existing local enrichment state or a new enrichment run
- if you already have paid-for enrichment in SQLite, back it up before any destructive reset with `python3 pipeline/db_backup.py backup`

---

## Canonical Runner

Use the runner unless you specifically need an individual stage:

```bash
python3 pipeline/run.py --to build
```

Useful modes:

```bash
# deterministic rebuild only
python3 pipeline/run.py --to build

# deterministic rebuild from a fresh SQLite DB
python3 pipeline/run.py --reset-db --yes-reset-db --to build

# include LLM enrichment
python3 pipeline/run.py --with-enrich --to build --concurrency 4
```

For a step-by-step safe operator workflow, see
[docs/full_run_playbook.md](/Users/talha/Code/free-exercise-graph/docs/full_run_playbook.md).

When shipping the static app, the normal build order after `graph.ttl` is current is:

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
python3 app/build_observatory.py --out app
```

---

## Reset Semantics

`--reset-db` deletes only the SQLite intermediate store. It now auto-backs up the
current DB by default, and it requires explicit acknowledgement when LLM state exists.
It does not modify:

- `sources/*/raw/*`
- `sources/*/mappings/*`
- ontology files

It will, however, remove persisted enrichment state stored in SQLite. Do not use it casually if you want to preserve already-paid-for LLM output.

Safe default:

```bash
python3 pipeline/run.py --to build
```

Use `--reset-db` only when:

- you intentionally want to rebuild from source truth
- upstream source-record membership changed
- deterministic stage state has become inconsistent

Recommended safety steps first:

```bash
python3 pipeline/db_backup.py backup
python3 pipeline/export_enrichment.py
```

---

## Stage Contracts

### `canonicalize.py`

- owns `source_records`, `source_claims`, `source_metadata`
- safe to rerun for unchanged source-record sets
- refuses to silently delete source records that are already referenced downstream

### `identity.py`

- owns `entities`, `entity_sources`, `possible_matches`
- preserves existing enrichment state by default
- refuses to remove enriched entity IDs unless you explicitly choose a destructive path

### `reconcile.py`

- rebuilds `resolved_claims` and `conflicts`
- deterministic and safe to rerun

### `enrich.py`

- writes inferred claims and enrichment bookkeeping
- expensive
- archives raw responses under `pipeline/artifacts/raw_responses/`
- skipped by default in the canonical runner

### `build.py`

- emits `graph.ttl`
- warns loudly when the graph is deterministic-only or only partially enriched
- deterministic given the current DB + ontology

### `scripts/build_similarity_graph.py`

- projects RDF exercise semantics into a weighted exercise-to-exercise graph
- emits sparse similarity, neighbor, community, and metrics artifacts under `data/generated/`
- deterministic given the current graph + config

### `scripts/build_substitute_ui.py`

- consumes generated similarity/community/features artifacts
- emits product-facing substitute buckets and debug metadata
- deterministic given the current generated similarity artifacts + config

### `app/build_observatory.py`

- emits `app/observatory.json` for the static app Builder View
- deterministic given the current pipeline SQLite state and curated observatory list
- separate from `build_site.py` on purpose so Builder View data stays explicit

### `validate.py`

- reports graph/data-product health
- does not mutate pipeline truth

---

## When to Re-enrich

You do **not** need to re-enrich for every code change.

You generally re-enrich when:

- ontology terms used by enrichment changed
- prompt grounding changed
- a specific stripped value was added to the vocabulary
- a specific entity needs correction

Useful commands:

```bash
python3 pipeline/enrich.py --force <entity_id>
python3 pipeline/enrich.py --restamp <term>
python3 pipeline/enrich.py --dry-run
```

After important runs, freeze a portable state:

```bash
python3 pipeline/export_enrichment.py
python3 pipeline/release_bundle.py
```

---

## What to Tell a New Teammate

If someone asks “what should I run first?”, the answer is:

```bash
pip install -e .
python3 pipeline/run.py --to build
python3 pipeline/validate.py --verbose
python3 test_shacl.py
```

If they are working on the static app rather than just the graph, add:

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
python3 app/build_observatory.py --out app
```
