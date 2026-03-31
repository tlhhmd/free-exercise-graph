# free-exercise-graph

**[→ Live app](https://www.talha.foo/free-exercise-graph/)**

A semantic knowledge graph of **3,455 exercises** — reconciled from multiple open datasets, classified against a governed OWL/SHACL ontology, and queryable via MCP (for AI agents) and a static app (for humans).

The ontology, multi-source reconciliation pipeline, data quality framework, and 109 architecture decision records are original work. The exercise data comes from freely shared community datasets.

## What You Can Do With It

- **Find true substitutes** for any exercise based on shared movement patterns and prime movers — not just keyword similarity
- **Audit a training program** for muscle coverage gaps, joint action imbalances, or missing movement patterns
- **Ground an AI coaching agent** with structured, validated exercise data via MCP — no hallucinated muscle involvements
- **Query by joint action** to find or exclude exercises around a rehab constraint (e.g. "everything involving shoulder external rotation, nothing involving spinal flexion")
- **Browse exercises the way a gym-goer thinks** — by push/pull/legs, by equipment, by muscle group — through a static app or natural language via MCP

---

## By the Numbers

| | |
|---|---|
| **3,455** canonical entities | resolved from **4,113** source records across multiple datasets |
| **239,054** graph triples | assembled from resolved + inferred claims |
| **46** joint actions | across **9** joints |
| **11** ontology files | independently versioned (semver) |
| **109** ADRs | every non-trivial decision documented |
| **14/14** SHACL tests | passing |

---

## What This Project Adds

Source datasets provide exercise names, basic muscle lists, and broad categories. The graph adds the structured dimensions that make exercises queryable, comparable, and substitutable.

| Layer | Source data | This project | Example |
|---|---|---|---|
| Muscles | Flat string list | 3-level hierarchy (region → group → head) with involvement degrees | Bench Press: triceps as Synergist. Pushdown: triceps as PrimeMover. Same muscle, different intent. |
| Movement patterns | Nothing | SKOS hierarchy (HorizontalPush, VerticalPush under Push) | Floor Press substitutes for Bench Press; Overhead Press doesn't — hierarchy encodes that. |
| Joint actions | Nothing | 46 actions across 9 joints | Lateral Raise = shoulder abduction. Cable Y-Raise = shoulder flexion + scapular upward rotation. Same deltoids, different mechanics. |
| Training modality | Category field | Assigned only when modality is a defining characteristic | Kettlebell Swing is inherently Power; Barbell Squat is modality-agnostic. |
| Compound flag | Nothing | Boolean — multi-joint vs. isolation | Barbell Row (3 joints) vs. Bicep Curl (1 joint). |
| Laterality | Nothing | Bilateral / Unilateral / Contralateral / Ipsilateral | Dead Bug (contralateral) vs. Side Plank with leg lift (ipsilateral). |

---

## Architecture

Identity-first: resolve exercises into canonical entities across sources, then enrich each entity exactly once. Intermediate state lives in SQLite.

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

---

## How Reconciliation Works

The pipeline's value is clearest when sources disagree.

Three source records across two datasets describe variations of the **Dead Bug** exercise.

**Identity resolution** clusters all three into one canonical entity (`feg:ex_dead_bug`) based on muscle overlap, movement pattern, and name similarity.

**Conflict detection** finds that sources disagree on laterality — one says *Contralateral* (right arm + left leg move together), another says *Unilateral* (one limb loaded at a time). Both are defensible. The reconciler defers the conflict rather than guessing.

**Deterministic resolution** handles everything else: equipment is unioned (Bodyweight + Kettlebell both preserved), muscle involvement degrees are normalised from informal terms (`prime/secondary/tertiary`) to the controlled vocabulary (`PrimeMover/Synergist/Stabilizer`), and unanimous claims pass through.

**LLM enrichment** fills the gap — it sees the exercise context and infers *Contralateral* (the anatomically precise framing). It also adds muscles no source mentioned: TransverseAbdominis as PrimeMover, ErectorSpinae and Iliopsoas as Stabilizers. It identifies SpinalStability as the primary joint action.

The design philosophy: resolve what's resolvable, defer what isn't, enrich what's missing, and never let inferred claims overwrite source-asserted facts. Full walkthrough: [docs/reconciliation_example.md](docs/reconciliation_example.md).

---

## MCP Server

The graph's primary AI interface. Loads `graph.ttl` into pyoxigraph in-process — no Docker, no external services.

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

## Ontology

Movement classification uses three orthogonal axes:

1. **Movement patterns** — user-facing navigation (Push/Pull, HipHinge, KneeDominant, etc.). The labels gym-goers use to browse and filter.
2. **Compound/Isolation** — boolean split for program design. Multi-joint force production vs. single-joint accessories.
3. **Joint actions** — mechanical precision layer (46 actions across 9 joints). Two exercises can share a movement pattern and target the same muscles but load completely different joints — this axis catches that.

These three axes together are what make substitution, rehab-aware filtering, and program audit queries possible. Collapse any two into one and real use cases break.

All 11 ontology files carry `owl:versionInfo` (semver). Every version bump requires an ADR in `DECISIONS.md`.

LLM classification instructions are embedded as `rdfs:comment` on OWL property definitions. Enrichment prompts are rendered from the live ontology at runtime — so adding a vocabulary concept or tightening a classification rule propagates to the next enrichment run automatically, with no prompt engineering required.

---

## Governance

Every non-trivial decision — vocabulary additions, pipeline behavior changes, prompt rules — is documented as an Architecture Decision Record in `DECISIONS.md`. 105 ADRs and counting. The discipline is intentional: the graph is used for structured querying, and incorrect classifications have real downstream consequences.

**Hard rules:**
- Never add or remove vocabulary concepts without an ADR
- Never modify files in `sources/*/raw/` (upstream source data)
- Never bump a vocabulary version without documenting the change
- Discuss before building — raise trade-offs before implementing

See `CONTRIBUTING.md` for the full operational guide.

---

## Setup

```bash
pip install -e .
```

Set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in environment or `.env` for LLM enrichment.

```bash
# Deterministic rebuild (no API calls)
python3 pipeline/run.py --to build

# Full run including LLM enrichment
python3 pipeline/run.py --with-enrich --to build --concurrency 4

# Validate
python3 pipeline/validate.py --verbose
python3 test_shacl.py
```

For the full operational playbook (backups, resets, enrichment import/export, release bundles), see [docs/full_run_playbook.md](docs/full_run_playbook.md).

---

## Static App

A static GitHub Pages app under [app/](app/) — the human-facing surface of the graph. Client-side filtering by muscle, movement pattern, equipment, and modality. Anatomy illustrations. Deterministic search that understands ontology labels. All expensive ontology work happens at build time; the browser only does fast filtering and rendering.

```bash
python3 app/build_site.py    # export data.json + vocab.json from the graph
```

See ADR-086–090 in `DECISIONS.md` for architecture rationale, and [app/README.md](app/README.md) for the full guide.

---

## Thank You to Our Sources

This project stands on the shoulders of people who freely shared their work. We are grateful.

- **[yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)** — 873 exercises with muscle, equipment, and category data. Released into the public domain under the [Unlicense](https://unlicense.org/).

- **[Strength to Overcome — Functional Fitness Exercise Database](https://strengthtoovercome.com/functional-fitness-exercise-database)** — 3,240 functional exercises with 30+ classification fields including difficulty, plane of motion, grip type, and posture. Shared freely by its creator for the fitness community. Used here with gratitude and full credit.

---

## Docs by Audience

- **New engineer / ontology engineer:** [docs/system_contracts.md](docs/system_contracts.md) → [docs/sqlite_data_model.md](docs/sqlite_data_model.md) → [CONTRIBUTING.md](CONTRIBUTING.md)
- **Pipeline operator:** [docs/full_run_playbook.md](docs/full_run_playbook.md)
- **Ontologist / taxonomy reviewer:** [DECISIONS.md](DECISIONS.md), [ontology/](ontology/), [docs/sqlite_data_model.md](docs/sqlite_data_model.md), [docs/quality_surfaces.md](docs/quality_surfaces.md)
- **Product / design context:** this README → [docs/reconciliation_example.md](docs/reconciliation_example.md) → [app/README.md](app/README.md) → [codexlog.md](codexlog.md)
- **Frontend / static-app:** [app/README.md](app/README.md) → [docs/app_field_provenance.md](docs/app_field_provenance.md)

---

## Repo Layout

```
ontology/          11 TTL vocabulary + schema files (independently versioned)
sources/           per-source adapters, crosswalks, and read-only raw data
pipeline/          6-stage pipeline: canonicalize → identity → reconcile → enrich → build → validate
enrichment/        LLM prompt assembly, provider adapters, Pydantic output schema
app/               static GitHub Pages app (HTML/CSS/JS + build script)
mcp_server.py      5-tool MCP server backed by pyoxigraph
docs/              system contracts, data model, playbooks, worked examples
DECISIONS.md       105 architecture decision records
```

All URIs use `https://placeholder.url#` (prefix `feg:`) — placeholder pending a permanent domain. Full file-level map: [docs/repo_map.md](docs/repo_map.md)
