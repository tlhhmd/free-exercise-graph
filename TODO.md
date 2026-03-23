# TODO

Items are grouped by theme, roughly priority-ordered within each group.

---

## In progress

- [ ] **functional-fitness-db enrichment** — ~1645/3242 done, 14 quarantined. **Blocked:** fix HipFlexors ancestor violation before resuming (see below), then run `python3 sources/functional-fitness-db/enrich.py --concurrency 4`.

- [ ] **Fix HipFlexors ancestor violation in prompt** — ADR-085 added `feg:HipFlexors` as a `MuscleRegion` with `Psoas` and `Sartorius` as narrower concepts. The model now lists both `HipFlexors` and `Psoas`/`Iliopsoas` on the same exercise, tripping the ancestor rule (`HipFlexors is an ancestor of Psoas/Iliopsoas — double-counting`). The prompt's ancestor rule section (`enrichment/prompt_template.md`) needs an explicit example showing that listing `HipFlexors` precludes listing `Psoas`, `Iliopsoas`, or `Sartorius` in the same exercise. Also retry the 2 quarantined exercises that hit this error (`Bar_Hanging_Knees_to_Wrists`, `Parallette_L_Sit_to_Pike_Press_Handstand`) after the fix.

---

## Pipeline

- [ ] **Graph refresh** — `refresh.sh` exists (build → pkill mcp_server.py). Claude Desktop reloads the server automatically after the kill.

---

## Multi-source assembly

Design decisions needed before implementing a second source or `assemble.py`:

- [ ] **Output artifact naming** — decision: top-level assembled output is `graph.ttl`. Update `assemble.py`, MCP server, and any consumers when multi-source assembly is built.
- [ ] **Vocabulary loading responsibility** — decision: stays per-source. Each source's `build.py` remains self-contained and independently runnable. `assemble.py` de-duplicates vocabulary triples at merge time.
- [ ] **PROV-O / catalog merge strategy** — decision: catalogs stay scoped to their source. `assemble.py` does not merge them into `graph.ttl`. A root-level `catalog.ttl` for the assembled graph is a separate future artifact if needed.
- [ ] **Semantic reconciliation framework** — when two sources disagree on a classification (Source A: Biceps, Source B: Brachialis), what wins? Design the conflict detection and resolution model before ingesting a second source. Options: provenance-weighted priority, human triage queue, consensus rule. Needs an ADR.

---

## MCP server

- [ ] **Claude Desktop integration test** — configure claude_desktop_config.json and test `find_substitutions` with equipment constraints end-to-end
- [ ] **Startup time** — current approach loads ingested.ttl at server start (~0.6s). Acceptable for now; if it becomes an issue, pre-build a pyoxigraph persistent store file.
- [ ] **Developer onboarding / quick-start** — "Time-to-First-Query < 5 minutes" path: configure MCP, run one query, see a result. No onboarding path currently documented in README or CONTRIBUTING.

---

## Enrichment pipeline


---

## Ontology and vocabulary

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: split into `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are built and ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.

---

## Evaluation and HITL

- [ ] **Annotate gold standard** — review `evals/gold_annotation.xlsx`. Target: 30–50 exercises fully verified.
- [ ] **eval.py** — automated scoring against completed gold standard (precision/recall/F1 per field).
- [ ] **HITL correction loop** — formal mechanism for domain experts (kinesiologists, coaches) to flag incorrect classifications, with corrections feeding back into prompt grounding and ontology guidance. Seed: `evals/` annotation tooling. Needs design before building — the feedback loop architecture (triage queue → prompt update → re-enrich) is the hard part.

---

## Governance and documentation

- [ ] **Trend tracking for quality scorecard** — `graph_health.py` generates per-run snapshots but has no history. Consider appending summary stats to a `quality_history.csv` to show trend over time.
- [ ] **Productized quality scorecard** — stakeholder-readable Graph Health report summarizing `validate.py` output: failure counts by dimension, % of library at completeness standard, trend over time. Replaces raw CSV as the communication artifact for collaborators and reviewers.

---

## Personas and use cases

Document four JTBDs in README or a dedicated PERSONAS.md to ground design decisions and communicate scope to reviewers:

- [ ] **Agentic Developer** — grounding AI coaches and fitness apps in a verifiable, machine-readable source of truth for exercise classification.
- [ ] **Content Architect** — centralized, version-controlled governance for large exercise libraries across platforms or product lines.
- [ ] **Clinical Exercise Specialist** — prescribing programs with precision around specific joint limitations, contraindications, or rehab stages.
- [ ] **Casual Gymgoer** — intuitive discovery by movement pattern, muscle group, or available equipment without needing anatomical vocabulary.
