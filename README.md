# free-exercise-graph

**free-exercise-graph** is a semantic knowledge graph of exercises built on an OWL ontology and SHACL constraints. Use it to find true substitutes, audit what your program is actually training, and build workouts that aren't tied to how any single source labels a movement.

It pulls from multiple open datasets and gives them a consistent structure through a shared ontology. Exercises are enriched via LLM classification into ontology-defined fields — prompts are dynamically generated from the ontology to constrain outputs to a controlled vocabulary. Across sources, exercises that describe the same movement are linked together, even when named or described differently.

---

## Thank You to Our Sources

This project stands on the shoulders of people who freely shared their work. We are grateful.

- **[yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)** — 873 exercises with muscle, equipment, and category data. Released into the public domain under the [Unlicense](https://unlicense.org/).

- **[Strength to Overcome — Functional Fitness Exercise Database](https://strengthtoovercome.com/functional-fitness-exercise-database)** — 3,240 functional exercises with 30+ classification fields including difficulty, plane of motion, grip type, and posture. Shared freely by its creator for the fitness community. Used here with gratitude and full credit.

---

## Who Uses This

| Persona | Problem | What FEG provides |
|---|---|---|
| **Agentic Developer** | LLMs hallucinate muscle involvements and contradict themselves across sessions | A structured, queryable source of truth to ground AI coaching agents via MCP |
| **Content Architect** | Exercise libraries degrade over time as contributors tag inconsistently | Version-controlled vocabulary with ADR-driven change governance |
| **Clinical Exercise Specialist** | No app models joint-level mechanics needed for rehabilitation programming | 45 joint actions across 9 joints — query by action, exclude by injury constraint |
| **Casual Gymgoer** | Wants to find exercises by feel ("something for legs, no equipment") not anatomy | Movement pattern + muscle group + equipment filtering in plain language via MCP |

---

## What It Adds

| Layer | Source data | This project |
|---|---|---|
| Muscles | Flat string list (e.g. "lower back") | Structured 3-level hierarchy with involvement degrees (PrimeMover / Synergist / Stabilizer / PassiveTarget) |
| Movement patterns | Nothing | SKOS vocabulary with parent/child concepts (e.g. `Squat` under `KneeDominant`) |
| Joint actions | Nothing | 45 joint actions across 9 joints (Shoulder, Elbow, Scapula, Forearm, Wrist, Hip, Knee, Ankle, Spine) |
| Training modality | Category field (e.g. "Strength") | Controlled vocabulary assigned only when modality is a defining characteristic |
| Compound flag | Nothing | Boolean — multi-joint force production vs. isolation |
| Laterality | Nothing | Bilateral / Unilateral / Contralateral / Ipsilateral |

---

## Repo Map

```
free-exercise-graph/
  ontology/                        vocabulary and schema files (TTL, independently versioned)
    ontology.ttl                   OWL class definitions, properties, LLM classification guidance
    muscles.ttl                    muscle SKOS hierarchy (region → group → head)
    movement_patterns.ttl          movement pattern SKOS vocabulary
    joint_actions.ttl              45 joint actions across 9 joint groups
    involvement_degrees.ttl        PrimeMover / Synergist / Stabilizer / PassiveTarget
    training_modalities.ttl        Strength / Mobility / Plyometrics / Power / Cardio
    equipment.ttl                  equipment named individuals
    laterality.ttl                 Bilateral / Unilateral / Contralateral / Ipsilateral
    planes_of_motion.ttl           Sagittal / Frontal / Transverse
    exercise_styles.ttl            Bodybuilding / Calisthenics / Powerlifting / etc.
    shapes.ttl                     SHACL validation shapes

  sources/
    free-exercise-db/
      fetch.py                     download exercises.json from upstream
      adapter.py                   normalise source records for the pipeline
      mappings/
        equipment_crosswalk.csv    source equipment strings → feg: local names
      raw/exercises.json           upstream source (read-only)

    functional-fitness-db/
      fetch.py                     download and convert Excel source from upstream
      adapter.py                   normalise source records for the pipeline
      mappings/
        muscle_crosswalk.csv       source muscle strings → feg: local names
        movement_pattern_crosswalk.csv
        equipment_crosswalk.csv
      raw/                         upstream source files (read-only)

  pipeline/
    db.py                          SQLite schema and connection helper
    artifacts.py                   shared helper for exports, raw-response archives, release bundles
    run.py                         canonical runner for rebuilds and stage orchestration
    canonicalize.py                Stage 1: load source records + asserted claims into SQLite
    identity.py                    Stage 2: resolve source records into canonical entities
    reconcile.py                   Stage 3: deterministic conflict resolution (no LLM)
    enrich.py                      Stage 4: LLM enrichment pass — fills gaps in resolved claims
    build.py                       Stage 5: assemble graph.ttl from resolved + inferred claims
    validate.py                    data quality scorecard (validity / uniqueness / integrity / timeliness / completeness)
    triage.py                      interactive review queue for ambiguous identity matches
    db_backup.py                   snapshot/restore helper for pipeline.db
    export_enrichment.py           portable JSONL export of paid-for enrichment state
    import_enrichment.py           restore exported enrichment into a deterministic rebuild
    release_bundle.py              freeze DB + graph + scorecard into a timestamped bundle
    pipeline.db                    SQLite intermediate store (gitignored)
    backups/                       SQLite snapshots created before risky resets
    exports/                       portable JSONL enrichment exports
    artifacts/raw_responses/       archived raw LLM inputs/outputs per enrichment run
    releases/                      timestamped release bundles for restore/demo handoff

  enrichment/
    service.py                     ontology loading, prompt assembly, LLM response parsing
    providers.py                   LLM provider adapters (Anthropic, Gemini) with usage normalisation
    schema.py                      Pydantic output model — enforces ontology constraints at parse time
    prompt_template.md             system prompt template with <<<placeholder>>> slots
    prompt_builder.py              renders prompt_template.md from live ontology graphs
    _vocab.py                      vocab extraction utilities

  evals/                           gold standard annotation and eval tooling
  queries/                         example SPARQL discovery queries
  docs/
    system_contracts.md            source-of-truth boundaries, reset/replay semantics
    full_run_playbook.md           step-by-step safe runbook for local full runs
    sqlite_data_model.md           SQLite table dictionary, ERD, and RDF mapping
    quality_surfaces.md            SHACL vs validate.py vs CI
    triage_workflow.md             human-in-the-loop review and restamp loop
    reconciliation_example.md      worked example: Dead Bug across all pipeline stages
  mcp_server.py                    MCP server: 5 tools backed by pyoxigraph in-process
  test_shacl.py                    SHACL constraint test harness (14 tests)
  constants.py                     single source of truth for FEG_NS namespace
  codexlog.md                      refactor log: what changed and why
  DECISIONS.md                     full ADR history
  TODO.md                          open items
```

---

## Docs by Audience

- **New engineer / ontology engineer:** start with [docs/system_contracts.md](docs/system_contracts.md), then [docs/sqlite_data_model.md](docs/sqlite_data_model.md), then [CONTRIBUTING.md](CONTRIBUTING.md)
- **Operator running the full pipeline:** use [docs/full_run_playbook.md](docs/full_run_playbook.md)
- **Ontologist / taxonomy reviewer:** read [DECISIONS.md](DECISIONS.md), [ontology/](ontology/), [docs/sqlite_data_model.md](docs/sqlite_data_model.md), and [docs/quality_surfaces.md](docs/quality_surfaces.md)
- **Product / PM / portfolio reviewer:** read this README, [docs/reconciliation_example.md](docs/reconciliation_example.md), and [codexlog.md](codexlog.md)

---

## Architecture

The pipeline is identity-first: exercises from multiple sources are resolved into canonical entities before any LLM enrichment occurs. Each canonical entity is enriched exactly once, on the union of asserted facts from all contributing sources. Intermediate state lives in a SQLite database (`pipeline/pipeline.db`).

```
sources/*/raw/              upstream source data (read-only)
        │
        ▼
  adapter.py                normalise per-source records into a common schema
        │
        ▼
 canonicalize.py            load source records + asserted claims into SQLite
        │
        ▼
  identity.py               resolve source records into canonical entities
                            weighted biomechanical similarity scoring
                            ambiguous matches deferred, not blocked
        │
        ▼
  reconcile.py              deterministic resolution algebra (no LLM)
                            consensus / union / conservative / defer
                            deferred conflicts → triage queue
        │
        ▼
   enrich.py                single LLM pass per canonical entity
                            fills genuine gaps only
                            inferred claims tagged separately from asserted
        │
        ▼
   build.py                 RDF assembly from resolved + inferred claims
                            asserted always takes precedence over inferred
        │
        ▼
   graph.ttl                assembled knowledge graph (gitignored)
        │
   ┌────┴─────────────────────┐
   ▼                          ▼
validate.py               test_shacl.py
data product health       ontology/shape regression tests
        │
        ▼
mcp_server.py             pyoxigraph in-process SPARQL
5 MCP tools               search, get, substitute, hierarchy, joint-action
```

See ADR-086–090 in `DECISIONS.md` for the full architecture rationale.

---

## Ontology

### Core classes

`feg:Exercise`, `feg:MuscleInvolvement`, `feg:Muscle` (→ `MuscleRegion` / `MuscleGroup` / `MuscleHead`), `feg:MovementPattern`, `feg:JointAction`, `feg:TrainingModality`, `feg:InvolvementDegree`, `feg:Equipment`

### Three-layer movement model

Movement classification uses three orthogonal axes:

1. **Movement patterns** — user-facing navigation (Push/Pull, KneeDominant, HipHinge, Mobility, etc.). These are the labels gym-goers use.
2. **Compound/Isolation** — boolean first-pass for program design. Two or more distinct joints contributing to force production = compound.
3. **Joint actions** — mechanical precision layer (HipExtension, KneeExtension, ScapularRetraction, etc.). 45 actions across 9 joints. Useful for substitution and balance analysis.

### Prompt grounding

LLM classification instructions live as `rdfs:comment` on OWL property definitions in `ontology.ttl`. This is the semantically correct home — property documentation belongs on the property. The prompt template in `enrichment/prompt_template.md` uses `<<<placeholder>>>` slots that are rendered at runtime from the live ontology graphs.

### Vocabulary versioning

All ontology files carry `owl:versionInfo` (semver). Changes are typed:

- **MAJOR** — breaking (removing concepts, renaming URIs)
- **MINOR** — additive (new concepts, new properties)
- **PATCH** — non-breaking corrections (comments, labels)

Every version bump requires an ADR in `DECISIONS.md`.

---

## MCP Server

`mcp_server.py` loads `graph.ttl` into pyoxigraph in-process (no Docker, no external services) and exposes 5 tools via the MCP protocol:

| Tool | Description |
|---|---|
| `search_exercises` | Filter by muscle(s), movement pattern, equipment, and/or involvement degree |
| `get_exercise` | Full record: muscles + degrees, joint actions, movement patterns, equipment |
| `find_substitutions` | Exercises sharing the same primary movement pattern and PrimeMover muscles, filtered to available equipment |
| `get_muscle_hierarchy` | SKOS tree: regions → groups → heads, with `useGroupLevel` flags |
| `query_by_joint_action` | Exercises where a given joint action appears as primary |

### Quick start: Time-to-First-Query

**1. Build the graph**:

```bash
python3 pipeline/run.py --to build
```

For the fully enriched graph, enrichment should already have run. The same command is
also useful for deterministic rebuilds that preserve existing enrichment state.

**2. Configure Claude Desktop** — add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "free-exercise-graph": {
      "command": "python3",
      "args": ["/absolute/path/to/free-exercise-graph/mcp_server.py"]
    }
  }
}
```

**3. Restart Claude Desktop**, then try:

- *"Find me compound hip hinge exercises I can do with just a barbell"*
- *"What are good substitutes for Romanian Deadlift if I don't have a barbell?"*
- *"Show me the full muscle hierarchy for the posterior chain"*
- *"What exercises involve shoulder abduction as a primary joint action?"*

---

## Governance

Every non-trivial decision — vocabulary additions, pipeline behavior changes, prompt rules — is documented as an Architecture Decision Record in `DECISIONS.md`. ADRs are numbered sequentially. The discipline is intentional: the graph is used for structured querying, and incorrect classifications have real downstream consequences.

**Hard rules:**
- Never add or remove vocabulary concepts without an ADR
- Never modify files in `sources/*/raw/` (upstream source data)
- Never bump a vocabulary version without documenting the change
- Discuss before building — raise trade-offs before implementing

See `CONTRIBUTING.md` for the full operational guide.

---

## Quick Start

### Prerequisites

```bash
pip install -e .
```

Requires an API key for the LLM provider used for enrichment:
- Anthropic (default): `ANTHROPIC_API_KEY`
- Gemini: `GEMINI_API_KEY`

Set in environment or a `.env` file.

### Run the pipeline

`pipeline/run.py` is the canonical entrypoint. By default it rebuilds the deterministic
stages (`canonicalize -> identity -> reconcile -> build`) without calling the LLM.
For the safest full local workflow, follow [docs/full_run_playbook.md](/Users/talha/Code/free-exercise-graph/docs/full_run_playbook.md).

```bash
# 1. Fetch upstream sources (skip if raw/ files already present)
python3 sources/free-exercise-db/fetch.py
python3 sources/functional-fitness-db/fetch.py

# 2. Snapshot current SQLite state if you care about existing enrichment
python3 pipeline/db_backup.py backup

# 3. Deterministic rebuild from source truth (safe default, no API calls)
python3 pipeline/run.py --to build

# 4. Full run including enrichment (costs API tokens; auto-exports JSONL afterward)
python3 pipeline/run.py --with-enrich --to build --concurrency 4
python3 pipeline/run.py --with-enrich --to build --provider gemini --concurrency 4

# 5. Validation surfaces
python3 pipeline/validate.py --verbose
python3 test_shacl.py

# 6. Freeze a release/demo bundle
python3 pipeline/release_bundle.py

# 7. Full rebuild from scratch (explicitly resets SQLite only)
python3 pipeline/run.py --reset-db --yes-reset-db --to build
```

### Manual stage order

If you need the individual scripts, the order is:

```bash
python3 pipeline/canonicalize.py
python3 pipeline/identity.py
python3 pipeline/reconcile.py
python3 pipeline/enrich.py        # optional / costs tokens
python3 pipeline/build.py
python3 pipeline/validate.py
python3 test_shacl.py
```

Important:
- Re-running upstream stages after changing source truth may require `--reset-db` on the runner.
- Existing enrichment state is preserved by default. The repo will not drop already-paid-for LLM output unless you explicitly choose a destructive rebuild path.
- `pipeline/run.py --reset-db` now auto-backs up SQLite by default and requires `--yes-reset-db` when LLM state is present.
- `pipeline/enrich.py` archives raw responses under `pipeline/artifacts/raw_responses/` and the canonical runner auto-exports enrichment JSONL after a successful enrich stage.
- If you need to restore enrichment into a deterministic rebuild, use `python3 pipeline/import_enrichment.py <artifact.jsonl>`.

### Start the MCP server

```bash
python3 mcp_server.py
# rebuild first if needed:
python3 pipeline/run.py --to build
```

---

## Current Status

Latest completed full enriched local run:

| Metric | Value |
|---|---|
| Source exercises | 4,113 (873 free-exercise-db + 3,240 functional-fitness-db) |
| Canonical entities | 3,450 (after identity resolution) |
| Enriched | 3,450 / 3,450 (100%) |
| Graph triples | 238,390 |
| Ontology files | 11 (independently versioned) |
| ADRs | 105 |
| SHACL test cases | 14 / 14 passing |
| Joint action vocabulary | 46 actions, 9 joint groups |

---

Deterministic rebuilds from source truth may differ slightly from the latest enriched run
while triage/review work is still being folded back into the canonical entity layer.

## Namespace

All URIs use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent domain. This will be updated before any public release. See `TODO.md` for the migration plan.
