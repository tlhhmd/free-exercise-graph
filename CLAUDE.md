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

**Owner:** Talha Ahmad — ontologist, knowledge graph architect. He can
read and write code but prefers to focus on design decisions. Be a
collaborative partner, not just an executor.

---

## Project Structure

- `ontology/` — TTL vocabulary and schema files (one file per concept domain)
- `sources/` — one subdirectory per upstream dataset; each is self-contained with its own `adapter.py`, `fetch.py`, `raw/`, and `mappings/`
- `enrichment/` — shared LLM enrichment service (`service.py`, `prompt_template.md`, schema)
- `evals/` — gold standard annotation and eval tooling
- `queries/` — example SPARQL discovery queries
- `mcp_server.py` — MCP server backed by pyoxigraph in-process
- `test_shacl.py` — SHACL unit test suite
- `constants.py` — single source of truth for `FEG_NS`; import from here, never hardcode
- `refresh.sh` — rebuild graph + restart MCP server

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
```

### Stage 6 — build.py
Assembles RDF from resolved and inferred claims. Asserted claims always take precedence over inferred. Writes `graph.ttl`.

```bash
python3 pipeline/build.py
```

### validate.py — 6-dimension quality scorecard

| Dimension    | Severity | What it checks |
|---|---|---|
| validity     | fail | SHACL conformance |
| uniqueness   | fail | duplicate involvements, JAs, patterns |
| integrity    | fail | every vocab reference resolves to a known ontology term |
| timeliness   | warn | enriched exercises have current vocabulary_versions stamps |
| consistency  | warn | cross-field rules (JA ↔ pattern, isCompound ↔ JA count) |
| completeness | warn | movement patterns, involvements, and primary JAs present |

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
