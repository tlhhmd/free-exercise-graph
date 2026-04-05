# free-exercise-graph — Claude Code Context

At the start of every session:
1. Read `CLAUDE.md`.
2. Read `DECISIONS.md` (ADR history).
3. Read `TODO.md` (open work).

At the end of every session:
- Update `TODO.md`: remove completed items, add newly surfaced work, and note anything now unblocked.

For any non-trivial ontology, pipeline, or product decision: discuss the trade-off before implementing, then record the decision in `DECISIONS.md`.

---

## Project Mission

free-exercise-graph is a multi-source semantic knowledge graph of exercises. It ingests upstream exercise data, reconciles and enriches it against a controlled ontology, materialises the result as RDF, and exposes it through SPARQL, an MCP server, and a static app.

Substitute discovery is built offline from `graph.ttl` into derived JSON artifacts — the static app does not compute substitute logic at runtime.

Talha Ahmad is the owner: an ontologist and knowledge graph architect who prefers to focus on design decisions. Be a collaborative partner, not just an executor.

---

## Hard Rules

- Never hardcode `https://placeholder.url#` in Python files. Import `FEG_NS` from `constants.py`.
- Never add, remove, or rename vocabulary concepts without an ADR.
- Annotation-only edits (labels, comments, scope notes) do not require an ADR, but still require a version bump.
- Never modify files in `sources/*/raw/`. Refresh them only through the relevant `fetch.py`.
- Never bump a vocabulary version without documenting the change in `DECISIONS.md`.
- Do not make ontology or pipeline behavior changes casually. Raise the trade-off first unless the task is obviously mechanical.

---

## Design Principles

**Vocabularies are for users.** Favor terms understandable to gym-goers, not ontological purity.

**Governance is part of the product.** ADR discipline, provenance, and careful versioning are intentional. Preserve that standard.

**Derived artifacts are downstream.** `ontology/ + pipeline DB + graph.ttl` = source graph system. Similarity/substitute scripts and the static app are downstream consumers. Keep that boundary clear when reasoning about truth and rebuild order.

---

## Working Style

- Match Talha's direct, pragmatic tone.
- Prefer one focused question over a long list of speculative questions.
- Be opinionated when needed, but grounded in existing rules and decisions.
- Preserve the project's value as a portfolio piece for senior ontology / knowledge graph work.

---

## Repo Landmarks

- `ontology/` — vocabularies, schema, and shapes
- `sources/` — fetch/adaptation logic and raw upstream data
- `pipeline/` — canonicalize → identity → reconcile → enrich → build → validate
- `scripts/` — similarity graph and substitute artifact builders
- `data/generated/` — derived similarity and substitute artifacts
- `app/` — static site and export/build step
- `evals/` — evaluation assets and tooling
- `mcp_server.py` — MCP server over the built graph
- `constants.py` — source of truth for `FEG_NS`

---

## Key Docs (read when relevant)

| Doc | When to read |
|---|---|
| `docs/system_contracts.md` | truth boundaries, safe rebuild order |
| `docs/repo_map.md` | repo orientation |
| `docs/full_run_playbook.md` | rebuilds, exports, release prep, recovery |
| `docs/quality_surfaces.md` | what each validation layer proves |
| `docs/sqlite_data_model.md` | pipeline DB schema |
| `docs/triage_workflow.md` | ambiguous identity matches |
| `pipeline_playbook.ipynb` | notebook-based rebuild/debug |
| `app/README.md` | app build and deploy |
| `docs/app_field_provenance.md` | which app fields are graph-native vs heuristic |
| `docs/DESIGN.md` | design system and frontend guidance |
| `docs/reconciliation_example.md` | worked source-to-graph example |
| `LESSONS_LEARNED.md` | project-level takeaways |
| `codexlog.md` | recent implementation context |

When docs and code appear to disagree, inspect the code and recent ADRs before assuming the doc is current.

---

## Vocabulary Versioning

Files in `ontology/` use `owl:versionInfo`. Any ontology change must include the appropriate version bump:
- **MAJOR** — breaking (remove concept, rename URI)
- **MINOR** — additive (new concept or property)
- **PATCH** — non-breaking correction (label, comment, scope note)