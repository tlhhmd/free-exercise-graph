# free-exercise-db

**Source:** [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)
**License:** [Unlicense](https://unlicense.org/) (public domain)
**Format:** JSON — 873 exercises with muscle, equipment, and category fields

---

## Pipeline

Run steps in order from the project root:

```bash
# 1. Download upstream source (skip if exercises.json already present)
python3 sources/free-exercise-db/fetch.py

# 2. Enrich via LLM (movement patterns, joint actions, involvement degrees)
python3 sources/free-exercise-db/enrich.py --limit 50 --random

# 3. Check for vocabulary drift (recommended after any vocabulary version bump)
python3 sources/free-exercise-db/check_stale.py

# 4. Build → ingested.ttl
python3 sources/free-exercise-db/build.py

# 5. Validate
python3 sources/free-exercise-db/validate.py
```

Steps 4 and 5 can be run together via `run_pipeline.py`.

`fetch.py` only needs re-running when pulling a fresh upstream snapshot.
`enrich.py` must run before `build.py` — its output (`enriched/*.json`) is merged during assembly.

---

## Script Reference

### fetch.py
Downloads `exercises.json` from the upstream GitHub repo. Writes to `raw/` (read-only thereafter).

### enrich.py
LLM enrichment pipeline. Calls Claude (via `prompt_builder.py`) to classify each exercise
with movement patterns, joint actions, involvement degrees (PrimeMover/Synergist/Stabilizer),
training modality, compound flag, and unilateral flag. Writes one JSON file per exercise to
`enriched/`. Failed exercises go to `quarantine/`. Rate-limited requests are retried with
exponential backoff before falling back to quarantine. Automatically resumes — already-enriched
exercises are skipped.

Flags:
- `--limit N` — enrich at most N exercises
- `--random` — process in random order (useful for sampling)
- `--concurrency N` — parallel LLM requests (default: 1)
- `--force ID [ID ...]` — re-enrich specific exercise IDs, overwriting existing files
- `--retry-quarantine` — re-attempt all quarantined exercises

Requires `ANTHROPIC_API_KEY` in environment or `.env` file.

### check_stale.py
Detects enriched exercises whose `vocabulary_versions` stamps are behind the current ontology
versions. Exits 1 if any stale exercises are found. Run after vocabulary bumps to identify
exercises that need re-enrichment.

Flags:
- `--verbose` — show per-exercise detail
- `--names-only` — print only exercise names

### build.py
Pure Python JSON→RDF assembly. Loads all ontology vocabulary files, reads `raw/exercises.json`
for basic metadata, overlays `enriched/*.json` for enrichment triples, and serialises to
`ingested.ttl`. Runs in ~1s. No morph-KGC, no repair passes.

### validate.py
6-dimension quality scorecard. Runs validity (SHACL), uniqueness, integrity, timeliness,
consistency, and completeness checks on enriched exercises. Writes a per-exercise CSV report
to `quality_report.csv`. Exits 0 if no validity failures, 1 if any violations.

Flags:
- `--all` — include perfect exercises in stdout output
- `--csv PATH` — override CSV output path

### graph_health.py
Reads `quality_report.csv` and produces a stakeholder-readable Graph Health report.
Outputs Markdown to stdout by default; optionally writes `.md` and `.html` files.

```bash
python3 sources/free-exercise-db/graph_health.py
python3 sources/free-exercise-db/graph_health.py --md report.md --html report.html
```

### run_pipeline.py
End-to-end runner: runs `build.py` then `validate.py` in-process with combined telemetry report.

```bash
python3 sources/free-exercise-db/run_pipeline.py
python3 sources/free-exercise-db/run_pipeline.py --skip-validate
```

---

## Folder Layout

```
free-exercise-db/
  fetch.py                          download exercises.json from upstream GitHub
  enrich.py                         LLM enrichment pipeline (Claude)
  prompt_builder.py                 utilities for building LLM prompts from RDF ontology files
  prompt_template.md                system prompt template for enrich.py
  check_stale.py                    vocabulary drift detection
  build.py                          JSON→RDF assembly → ingested.ttl
  validate.py                       6-dimension quality scorecard
  run_pipeline.py                   end-to-end runner (build + validate)
  telemetry.py                      pipeline telemetry (PipelineRun, step timers)
  graph_health.py                   Graph Health report (Markdown + HTML) from quality_report.csv
  catalog.ttl                       DCAT + PROV-O provenance (machine-readable)
  raw/
    exercises.json                  upstream source (read-only)
  enriched/
    {exercise_id}.json              one file per enriched exercise (version controlled)
  quarantine/
    {exercise_id}.json              failed enrichments for inspection (gitignored)
  mappings/
    equipment_crosswalk.csv         source equipment strings → feg: local names
  queries/
    repair_01_*.rq                  SPARQL UPDATE: drop unmapped muscles (reference)
    repair_02_*.rq                  SPARQL UPDATE: remove duplicate involvements (reference)
    repair_05_*.rq                  SPARQL UPDATE: remove joint action muscles (reference)
  ingested.ttl                      pipeline output (gitignored — rebuilt by build.py)
```

---

## Ontology Relationship

This source pipeline consumes the shared vocabulary files in `ontology/`:

| Vocabulary | Used by |
|---|---|
| `ontology/muscles.ttl` | enrichment prompt, build.py validation, SHACL shapes |
| `ontology/movement_patterns.ttl` | enrichment prompt, SHACL shapes |
| `ontology/joint_actions.ttl` | enrichment prompt, SHACL shapes |
| `ontology/involvement_degrees.ttl` | enrichment prompt, SHACL shapes |
| `ontology/training_modalities.ttl` | enrichment prompt, SHACL shapes |
| `ontology/equipment.ttl` | equipment_crosswalk.csv, build.py |
| `ontology/shapes.ttl` | validate.py, test_shacl.py |

Vocabulary changes (concept additions, removals, URI renames) require an ADR and a version bump
in the relevant ontology file. See `CONTRIBUTING.md` for the change process.

---

## Mapping Coverage

| Source field | Mapped to |
|---|---|
| `id` | `feg:legacySourceId` + URI template `feg:ex_{id}` |
| `name` | `rdfs:label` |
| `equipment` | `feg:equipment` → `feg:{Equipment}` individual |
| `primaryMuscles[]` | dropped — superseded by LLM enrichment involvements |
| `secondaryMuscles[]` | dropped — superseded by LLM enrichment involvements |
| `category` | deferred — conflates modality with sport discipline (ADR-013) |
| `force`, `level`, `mechanic` | dropped (ADR-010) |
| `instructions`, `images` | dropped — not modelled in v1 |

LLM enrichment adds: `feg:movementPattern`, `feg:primaryJointAction`, `feg:supportingJointAction`,
`feg:isCompound`, `feg:isUnilateral`, `feg:hasInvolvement` (with refined degrees), `feg:trainingModality`.

---

## Known Data Quality Issues

These are upstream source issues — `exercises.json` is read-only and not corrected here.

**9 exercises with duplicate muscles** (same muscle in both `primaryMuscles` and
`secondaryMuscles`): All Fours Quad Stretch, Barbell Step Ups, Bent-Arm Barbell
Pullover, Clean and Press, Hurdle Hops, Kneeling Hip Flexor, Snatch Deadlift,
Split Snatch, Upper Back Stretch. Surfaced by SHACL validation (ADR-044).
