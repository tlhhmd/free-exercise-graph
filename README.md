# free-exercise-graph

A semantic knowledge graph of exercises built on top of [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db) (~873 exercises). The source database records basic facts — name, instructions, primary and secondary muscles. This project enriches that flat data with a formal ontology and a multi-stage LLM classification pipeline, then materialises the result as RDF.

This is a portfolio project targeting senior ontology and knowledge graph engineering roles. The governance discipline (ADRs, vocabulary versioning, SHACL validation), the "vocabularies are for users" design principle, and the three-layer movement model are all intentional design signals.

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
    ontology.ttl                   OWL class definitions and properties
    muscles.ttl                    muscle SKOS hierarchy (region → group → head)
    movement_patterns.ttl          movement pattern SKOS vocabulary
    involvement_degrees.ttl        PrimeMover / Synergist / Stabilizer / PassiveTarget
    training_modalities.ttl        Strength / Mobility / Plyometrics / Power / Cardio
    joint_actions.ttl              45 joint actions across 9 joint groups
    equipment.ttl                  equipment named individuals
    shapes.ttl                     SHACL validation shapes

  sources/
    free-exercise-db/              all scripts and artifacts for this source dataset
      fetch.py                     download exercises.json from upstream
      preprocess.py                normalise muscle strings via crosswalk CSVs
      enrich.py                    LLM enrichment pipeline (writes exercises_enriched.json)
      ingest.py                    morph-KGC + enrichment merge + repair queries → ingested.ttl
      validate.py                  SHACL validation (enriched exercises only)
      check_stale.py               detect enriched exercises with outdated vocabulary stamps
      prompt_template.md           system prompt template for enrich.py
      queries/                     SPARQL UPDATE repair queries (repair_01 … repair_04)
      mappings/                    YARRRML mapping, crosswalk CSVs, morph-KGC config
      raw/exercises.json           upstream source (read-only)
      eval_package/                exercises + vocabulary + instructions for third-party eval

  pipeline/
    prompt_builder.py              generic utilities for building LLM prompts from RDF

  evals/                           Streamlit annotation tool and gold standard WIP

  test_shacl.py                    SHACL constraint test harness (11 tests, run at root)
  DECISIONS.md                     full ADR history — read before touching ontology or pipeline
  TODO.md                          open items
```

---

## Architecture

```
raw/exercises.json               (upstream source — read-only)
        │
        ▼
   preprocess.py                 normalise muscle strings via crosswalk CSVs
        │
        ▼
raw/exercises_normalized.json
        │
        ├──────────────────────────────────────────────────────────────┐
        │                                                              │
        ▼                                                              ▼
   enrich.py                                                      morph-KGC
   (LLM classification via Claude)                            (YARRRML → RDF)
        │                                                              │
        ▼                                                              │
enriched/exercises_enriched.json                                       │
        │                                                              │
        └──────────────────────────────────┬───────────────────────────┘
                                           │
                                           ▼
                                       ingest.py
                               (merge + repair queries + serialise)
                                           │
                                           ▼
                                     ingested.ttl
                                           │
                                      ┌────┴────┐
                                      ▼         ▼
                                 validate.py  test_shacl.py
                              (real data)   (constraint harness)
```

All paths above are under `sources/free-exercise-db/` unless otherwise noted.

---

## Ontology

### Core classes

`feg:Exercise`, `feg:MuscleInvolvement`, `feg:Muscle` (→ `MuscleRegion` / `MuscleGroup` / `MuscleHead`), `feg:MovementPattern`, `feg:JointAction`, `feg:TrainingModality`, `feg:InvolvementDegree`, `feg:Equipment`

### Three-layer movement model

Movement classification uses three orthogonal axes:

1. **Movement patterns** — user-facing navigation (Push/Pull, KneeDominant, HipHinge, Mobility, etc.). These are the labels gym-goers use.
2. **Compound/Isolation** — boolean first-pass for program design. Two or more distinct joints contributing to force production = compound.
3. **Joint actions** — mechanical precision layer (HipExtension, KneeExtension, ScapularRetraction, etc.). 45 actions across 9 joints. Useful for substitution and balance analysis.

### Vocabulary versioning

All ontology files carry `owl:versionInfo` (semver). Changes are typed:

- **MAJOR** — breaking (removing concepts, renaming URIs)
- **MINOR** — additive (new concepts, new properties)
- **PATCH** — non-breaking corrections (comments, labels)

`check_stale.py` detects enriched exercises whose vocabulary stamps are behind current vocabulary versions.

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
# add streamlit for the annotation tool:
pip install -e ".[evals]"
```

Requires `ANTHROPIC_API_KEY` in environment or `.env` file for `enrich.py`.

### Run the full pipeline

```bash
# 1. Fetch upstream source (skip if exercises.json already present)
python3 sources/free-exercise-db/fetch.py

# 2. Normalise muscle strings
python3 sources/free-exercise-db/preprocess.py

# 3. Enrich exercises via LLM (--limit N for a subset, --random for random order)
python3 sources/free-exercise-db/enrich.py --limit 50 --random

# 4. Check staleness (vocabulary drift detection)
python3 sources/free-exercise-db/check_stale.py

# 5. Ingest → ingested.ttl
python3 sources/free-exercise-db/ingest.py

# 6. Test SHACL shapes
python3 test_shacl.py

# 7. Validate real data
python3 sources/free-exercise-db/validate.py
```

---

## Current Status

| Metric | Value |
|---|---|
| Total exercises | 873 |
| Enriched | ~49 (scaling in progress) |
| Vocabulary files | 8 |
| ADRs | 57 |
| SHACL test cases | 11 / 11 passing |
| Joint action vocabulary | 45 actions, 9 joint groups |

---

## Namespace

All URIs use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent domain. This will be updated before any public release.
