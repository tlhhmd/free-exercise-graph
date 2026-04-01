# free-exercise-graph — Claude Code Context

Read this file at the start of every session. Then read `DECISIONS.md`
for the full ADR history and `TODO.md` for current open items before
touching any ontology or pipeline files.

`TODO.md` is a live list of open work only — completed items are removed,
not checked off. Completed decisions live in `DECISIONS.md` as ADRs.

**At the end of every session**, update `TODO.md` to reflect what was
completed, what is now unblocked, and any new items that surfaced. Remove
items that are done. Do not let it go stale.

---

## What This Project Is

A multi-source semantic knowledge graph of exercises. Raw exercise data
is ingested from multiple upstream datasets, enriched via LLM against a
controlled ontology (muscles, movement patterns, joint actions, training
modalities, equipment), and materialised as RDF. The graph is queryable
via SPARQL and exposed through an MCP server for use in AI applications.

The static app now also depends on an offline substitute-discovery layer:
`graph.ttl` is projected into a sparse exercise similarity graph, then
reshaped into a UI-oriented substitute artifact. The browser reads those
precomputed JSON files; it does not compute graph logic at runtime.

**Owner:** Talha Ahmad — ontologist, knowledge graph architect. He can
read and write code but prefers to focus on design decisions. Be a
collaborative partner, not just an executor.

---

## Project Structure

- `ontology/` — TTL vocabulary and schema files (one file per concept domain)
- `sources/` — one subdirectory per upstream dataset; each is self-contained with its own `adapter.py`, `fetch.py`, `raw/`, and `mappings/`
- `pipeline/` — canonicalize → identity → reconcile → enrich → build → validate
- `enrichment/` — shared LLM enrichment service (`service.py`, `prompt_template.md`, schema)
- `scripts/` — offline similarity graph + substitute UI builders
- `data/generated/` — generated similarity, community, metrics, and substitute UI artifacts
- `app/` — static GitHub Pages app plus `build_site.py` export step
- `evals/` — gold standard annotation and eval tooling
- `queries/` — example SPARQL discovery queries
- `mcp_server.py` — MCP server backed by pyoxigraph in-process
- `test_shacl.py` — SHACL unit test suite
- `constants.py` — single source of truth for `FEG_NS`; import from here, never hardcode

---

## Read These When Relevant

- Core startup context:
  - `DECISIONS.md` — ADR history; required context for ontology or pipeline behavior changes
  - `TODO.md` — live open-work list; update this at session end
  - `docs/system_contracts.md` — what is source truth vs derived, and the safe rebuild order
  - `docs/repo_map.md` — fastest orientation map of where pipeline, scripts, app, and docs live

- Read when operating the pipeline:
  - `docs/full_run_playbook.md` — rebuilds, exports, release prep, and recovery
  - `docs/quality_surfaces.md` — what `test_shacl.py`, `pipeline/validate.py`, and CI each prove
  - `docs/sqlite_data_model.md` — table-level details for `pipeline/pipeline.db`
  - `docs/triage_workflow.md` — how to handle `possible_matches` and identity ambiguity
  - `pipeline_playbook.ipynb` — notebook-driven rebuild/debug flow

- Read when working on the app or product UX:
  - `app/README.md` — static app build, preview, and deploy flow
  - `docs/app_field_provenance.md` — which app fields are graph-native, computed, heuristic, or UI-only
  - `docs/DESIGN.md` — design system, visual direction, and frontend implementation guidance

- Read when you need examples or historical context:
  - `docs/reconciliation_example.md` — worked example of how one exercise moves through the pipeline
  - `LESSONS_LEARNED.md` — project-level takeaways, trade-offs, and scaling lessons
  - `codexlog.md` — recent implementation context that may not yet be fully condensed into permanent docs

Use `CLAUDE.md` for the mental model; use the docs above for the authoritative details.

---

## Key Design Principles

### Vocabularies are for users, not for ontologists
Our controlled vocabularies are interfaces for end users — people
browsing for exercises, filtering by muscle group, building programs.
Anatomical or ontological purity is secondary to usability and
discoverability. Prefer colloquial terms over formal anatomical names
where both are accurate. When in doubt: would a gym-goer understand
this?

### Every design decision gets an ADR
`DECISIONS.md` is the institutional memory of this project. Every
non-trivial decision — vocabulary changes, pipeline behavior, prompt
rules — gets documented with rationale. ADRs are numbered sequentially.
Always write the ADR before or immediately after making a change.

### Vocabulary changes require version bumps
All ontology files carry `owl:versionInfo`. Bump independently:
- MAJOR: breaking changes (removing concepts, renaming URIs)
- MINOR: additive changes (new concepts, new properties)
- PATCH: non-breaking corrections (comments, labels)

---

## Hard Rules

- **Never hardcode `https://placeholder.url#` in Python files.** Import `FEG_NS` from `constants.py` instead.
- **Never add, remove, or rename vocabulary concepts without an ADR.** This includes muscles, movement patterns, joint actions, training modalities, and involvement degrees. Annotation-only changes (scope notes, labels, comments) are PATCH-level and do not require an ADR.
- **Never modify files in `sources/*/raw/`.** They are upstream source datasets. Use each source's `fetch.py` to refresh them.
- **Never bump a vocabulary version without documenting the change** in DECISIONS.md.
- **Discuss before building.** For any ontology or pipeline decision that isn't obviously mechanical, raise the trade-off first.

---

## Ontology Overview

All vocabulary and schema files live in `ontology/`. Each file is independently versioned via `owl:versionInfo`.

| File | What it defines |
|---|---|
| `ontology.ttl` | Core OWL classes and properties (`Exercise`, `MuscleInvolvement`, `Muscle`, etc.) |
| `shapes.ttl` | SHACL validation shapes |
| `muscles.ttl` | 3-level SKOS muscle hierarchy (region → group → head); colloquial names preferred |
| `movement_patterns.ttl` | SKOS movement pattern vocabulary (HipHinge, Squat, Push, Pull, etc.) |
| `joint_actions.ttl` | SKOS joint action vocabulary (HipFlexion, KneeExtension, etc.) |
| `involvement_degrees.ttl` | PrimeMover / Synergist / Stabilizer / PassiveTarget |
| `training_modalities.ttl` | Assigned only when modality is a defining characteristic (ADR-021) |
| `equipment.ttl` | Equipment named individuals |
| `exercise_styles.ttl` | Bodybuilding / Calisthenics / Powerlifting / etc. |
| `laterality.ttl` | Bilateral / Unilateral / Contralateral / Ipsilateral |
| `planes_of_motion.ttl` | Sagittal / Frontal / Transverse |

**Namespace:** `https://placeholder.url#` (feg:) — placeholder, to be replaced before any public release.

---

## Pipeline Overview

The pipeline operates across all sources together, not per-source. Intermediate state lives in a SQLite database (`pipeline/pipeline.db`). Raw LLM responses are the only artifact retained as JSON.

Important distinction:

- the ontology + pipeline DB + `graph.ttl` are the graph build system
- the similarity/substitute scripts are downstream derived-artifact builders
- the static app is a consumer of those derived artifacts

For truth-boundary details, see `docs/system_contracts.md`.
For schema details, see `docs/sqlite_data_model.md`.

### Stage 1 — fetch.py (per source)
Downloads upstream source data into `sources/<source>/raw/`. Never modify raw files.

```bash
python3 sources/<source>/fetch.py
```

### Stage 2 — canonicalize.py
Aggregates all asserted facts from source records into the claims table, tagged by source and origin type. Runs conflict detection. Produces the canonical sparse layer per entity.

```bash
python3 pipeline/canonicalize.py
```

### Stage 3 — identity.py
Resolves source records across all sources into canonical entities using biomechanical similarity scoring. Writes entity clusters and confidence scores to SQLite. Ambiguous matches are linked via `possible_matches` and proceed independently — pipeline is never blocked.

```bash
python3 pipeline/identity.py
```

### Stage 4 — reconcile.py
Applies deterministic resolution algebra over asserted claims. Writes resolved claims to `resolved_claims`. Deferred conflicts enter the triage queue. No LLM involvement.

```bash
python3 pipeline/reconcile.py
python3 pipeline/reconcile.py --triage    # open triage queue for human review
```

### Stage 5 — enrich.py
Single LLM pass per canonical entity. Fills fields absent from resolved claims. Inferred claims are tagged separately from asserted ones and never overwrite resolved claims.

```bash
python3 pipeline/enrich.py
python3 pipeline/enrich.py --limit 10 --concurrency 4
python3 pipeline/enrich.py --force <ENTITY_ID>
python3 pipeline/enrich.py --dump-prompts <DIR>    # save prompts without calling LLM
python3 pipeline/enrich.py --dry-run               # count pending without API calls
python3 pipeline/enrich.py --restamp <TERM>        # re-enrich entities that had TERM stripped
python3 pipeline/enrich.py --quarantine            # list entities with ≥3 failures
```

**Failure handling:** Enrichment failures are written to `enrichment_failures`. Entities with ≥3 failures are skipped (quarantined) by default; use `--force` to retry and clear failure history.

**Vocabulary warnings:** Unknown vocab terms are stripped at validation time (not hard-failed), allowing partial enrichment to succeed. The one exception is `check_prime_mover` — no PrimeMover/PassiveTarget is a genuine failure. Stripped terms are persisted to `enrichment_warnings` for recovery via `--restamp` after vocabulary updates.

**Model tracking:** `enrichment_stamps.model` records which LLM model enriched each entity.

For table-by-table details on these bookkeeping surfaces, see `docs/sqlite_data_model.md`.

### Stage 6 — build.py
Assembles RDF from resolved and inferred claims. Asserted claims always take precedence over inferred. Writes `graph.ttl`.

```bash
python3 pipeline/build.py
```

### Stage 7 — scripts/build_similarity_graph.py
Projects `graph.ttl` into a weighted exercise-to-exercise similarity graph.
Emits sparse graph artifacts under `data/generated/`, including features,
edges, neighbors, communities, and build metrics.

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
```

### Stage 8 — scripts/build_substitute_ui.py
Consumes generated similarity/community/features artifacts and emits a
UI-facing substitute artifact with:

- `Closest Alternatives`
- `Different Equipment`
- collapsed `Explore This Family`

This stage also handles build-time bucket assignment, near-duplicate
suppression for visible substitutes, and reason-string generation.

```bash
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
```

### Stage 9 — app/build_site.py
Builds the static app payload from `pipeline.db` or `graph.ttl`, and
copies `exercise_substitute_ui.json` into `app/` when present.

```bash
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
```

### validate.py — data quality scorecard (ADR-095)

Run after every build.

```bash
python3 pipeline/validate.py --verbose        # fast (no SHACL)
python3 pipeline/validate.py --shacl --verbose  # full (slow, ~45s via oxrdflib)
```

Use:

- `test_shacl.py` for ontology/shape regression
- `pipeline/validate.py` for graph/data-product health
- CI for minimum repo-level release confidence

See `docs/quality_surfaces.md` for the authoritative breakdown.

### Static app build order

If you are shipping or reviewing the static app, the normal post-graph
build sequence is:

```bash
python3 pipeline/run.py --to build
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
```

Generated downstream artifacts include:

- `data/generated/exercise_features.json`
- `data/generated/exercise_similarity_edges.json`
- `data/generated/exercise_neighbors.json`
- `data/generated/exercise_communities.json`
- `data/generated/build_metrics.json`
- `data/generated/exercise_substitute_ui.json`
- `app/data.json`
- `app/vocab.json`
- `app/exercise_substitute_ui.json`

If you need the worked example for how facts move from messy source data to final graph output, read `docs/reconciliation_example.md`.
If you are dealing with ambiguous identity pairs, read `docs/triage_workflow.md`.

**URI conventions (ADR-040):**
- Exercises: `feg:ex_{id}` (avoids leading numeral / invalid NCName issues)
- Involvements: `feg:inv_ex_{id}_{feg_local_name}_{degree}` (no spaces)

---

## Tone and Working Style

- Talha is direct and pragmatic. Match that energy.
- Discuss design decisions before implementing — don't just build.
- Always write ADRs for non-trivial decisions.
- When something is ambiguous, ask one focused question rather than
  listing all possible options.
- This project is also a portfolio piece targeting senior ontology/
  knowledge graph roles ($180k-300k range). The governance discipline,
  ADR practice, and "vocabularies are for users" principle are all
  intentional signals. Keep that framing in mind.
