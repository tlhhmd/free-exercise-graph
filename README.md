# free-exercise-graph

A semantic knowledge graph of exercises built on top of open exercise datasets. This project enriches flat source data with a formal ontology and a multi-stage LLM classification pipeline, then materialises the result as RDF and serves it via MCP.

This is a portfolio project targeting senior ontology and knowledge graph engineering roles. The governance discipline (ADRs, vocabulary versioning, SHACL validation), the "vocabularies are for users" design principle, and the three-layer movement model are all intentional design signals.

---

## Thank You to Our Sources

This project stands on the shoulders of people who freely shared their work. We are grateful.

- **[yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)** — 873 exercises with muscle, equipment, and category data. Released into the public domain under the [Unlicense](https://unlicense.org/). The foundation of this graph.

- **[Strength to Overcome — Functional Fitness Exercise Database](https://strengthtoovercome.com/functional-fitness-exercise-database)** — 3,000+ functional exercises with 30+ classification fields including difficulty, plane of motion, grip type, and posture. Shared freely by its creator for the fitness community. Used here with gratitude and full credit.

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
| Unilateral flag | Nothing | Boolean — inherently one-limb exercise |

---

## Repo Map

```
free-exercise-graph/
  ontology/                        vocabulary and schema files (TTL)
    ontology.ttl                   OWL class definitions, properties, and LLM classification guidance
    muscles.ttl                    muscle SKOS hierarchy (region → group → head)
    movement_patterns.ttl          movement pattern SKOS vocabulary
    involvement_degrees.ttl        PrimeMover / Synergist / Stabilizer / PassiveTarget
    training_modalities.ttl        Strength / Mobility / Plyometrics / Power / Cardio
    joint_actions.ttl              45 joint actions across 9 joint groups
    equipment.ttl                  equipment named individuals
    laterality.ttl                 Bilateral / Unilateral / Contralateral / Ipsilateral
    planes_of_motion.ttl           Sagittal / Frontal / Transverse
    exercise_styles.ttl            Bodybuilding / Calisthenics / Powerlifting / OlympicWeightlifting / etc.
    shapes.ttl                     SHACL validation shapes (structural constraint + CI gate)

  sources/
    free-exercise-db/
      fetch.py                     download exercises.json from upstream
      enrich.py                    LLM enrichment pipeline — writes per-exercise JSON to enriched/
      check_stale.py               detect enriched exercises with outdated vocabulary stamps
      build.py                     assemble ingested.ttl from enriched/ and ontology files
      validate.py                  6-dimension quality scorecard
      run_pipeline.py              end-to-end runner: build + validate with telemetry
      prompt_builder.py            build LLM prompts from ontology property rdfs:comments
      telemetry.py                 per-step timing and JSON run reports
      mappings/
        equipment_crosswalk.csv    source equipment strings → feg: local names
      raw/exercises.json           upstream source (read-only)
      enriched/                    per-exercise enrichment JSON (version controlled — the dataset)

  mcp_server.py                    MCP server: 5 tools backed by pyoxigraph in-process

  test_shacl.py                    SHACL constraint test harness (11 tests)
  DECISIONS.md                     full ADR history (74 ADRs)
  TODO.md                          open items
```

---

## Architecture

```
raw/exercises.json          (upstream source — read-only)
        │
        ▼
   enrich.py                LLM classification via Claude
   + Pydantic validators     structure, cross-field rules, vocabulary checks at write time
        │
        ▼
enriched/{id}.json          one file per exercise — the dataset (version controlled)
        │
        ▼
   build.py                 pure Python JSON→RDF assembly (~1s)
        │                   reads ontology/*.ttl + enriched/*.json
        ▼
  ingested.ttl              43,051 triples (gitignored — derived artifact)
        │
   ┌────┴────────────────┐
   ▼                     ▼
validate.py          test_shacl.py
6-dimension          SHACL shapes
quality scorecard    CI gate
        │
        ▼
mcp_server.py        pyoxigraph in-process SPARQL
5 MCP tools          search, get, substitute, hierarchy, joint-action
```

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

LLM classification instructions live as `rdfs:comment` on OWL property definitions in `ontology.ttl`. This is the semantically correct home — property documentation belongs on the property. `shapes.ttl` contains only structural validation: cardinalities, class membership, `sh:in` enumerations.

### Vocabulary versioning

All ontology files carry `owl:versionInfo` (semver). Changes are typed:

- **MAJOR** — breaking (removing concepts, renaming URIs)
- **MINOR** — additive (new concepts, new properties)
- **PATCH** — non-breaking corrections (comments, labels)

`check_stale.py` detects enriched exercises whose vocabulary stamps are behind current vocabulary versions.

---

## MCP Server

`mcp_server.py` loads `ingested.ttl` into pyoxigraph in-process (no Docker, no external services) and exposes 5 tools via the MCP protocol:

| Tool | Description |
|---|---|
| `search_exercises` | Filter by muscle(s), movement pattern, equipment, and/or involvement degree |
| `get_exercise` | Full record: muscles + degrees, joint actions, movement patterns, equipment |
| `find_substitutions` | Exercises sharing the same primary movement pattern and PrimeMover muscles, filtered to available equipment |
| `get_muscle_hierarchy` | SKOS tree: regions → groups → heads, with `useGroupLevel` flags |
| `query_by_joint_action` | Exercises where a given joint action appears as primary |

### Quick start: Time-to-First-Query

**1. Build the graph** (required before starting the server):

```bash
python3 sources/free-exercise-db/build.py
```

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
- Never modify `sources/free-exercise-db/raw/exercises.json` (upstream source)
- Never bump a vocabulary version without documenting the change
- Discuss before building — raise trade-offs before implementing

See `CONTRIBUTING.md` for the full operational guide.

---

## Quick Start

### Prerequisites

```bash
pip install -e .
```

Requires `ANTHROPIC_API_KEY` in environment or `.env` file for `enrich.py`.

### Run the pipeline

```bash
# 1. Fetch upstream source (skip if exercises.json already present)
python3 sources/free-exercise-db/fetch.py

# 2. Enrich exercises via LLM (all 873 already committed to enriched/)
#    Only needed after vocabulary changes or to re-enrich specific exercises
python3 sources/free-exercise-db/enrich.py --limit 50 --random

# 3. Check staleness after vocabulary changes
python3 sources/free-exercise-db/check_stale.py

# 4. Build ingested.ttl (~1s)
python3 sources/free-exercise-db/build.py

# 5. SHACL test gate
python3 test_shacl.py

# 6. Quality scorecard
python3 sources/free-exercise-db/validate.py

# Or run build + validate together:
python3 sources/free-exercise-db/run_pipeline.py
```

### Start the MCP server

```bash
python3 mcp_server.py
```

---

## Current Status

| Metric | Value |
|---|---|
| Total exercises | 873 |
| Enriched | 873 / 873 (complete) |
| Total RDF triples | 43,051 |
| Vocabulary files | 8 |
| ADRs | 74 |
| SHACL test cases | 11 / 11 passing |
| Joint action vocabulary | 45 actions, 9 joint groups |
| Build time | ~1s |

---

## Namespace

All URIs use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent domain. This will be updated before any public release.
