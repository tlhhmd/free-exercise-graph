# TODO

Items are grouped by theme, roughly priority-ordered within each group.

---

## Enrichment provider decision (pending — 2026-03-23)

Considering Claude Sonnet 4.6 (~$52, done in hours) vs. Gemini 2.0 Flash paid (~$2, done in hours) vs. Gemini 2.0 Flash free (3 days, $0). Sonnet is the leaning. Key question: is the quality difference worth ~$50 on a constrained-output task?

- [ ] **Decide on provider and kick off full enrichment run**

---

## Enrichment in progress

Gemini 3.1 Pro (`gemini-3.1-pro-preview`) selected as provider.

**Option A — synchronous:** Context cache active (`pipeline/gemini_cache_id.txt`). Rate limit: ~250 RPD → ~16-day run at 4,095 entities. Script is resume-safe via `enrichment_stamps`.

**Option B — batch:** `pipeline/batch_export.py` + `pipeline/batch_ingest.py`. Single async job, ~24h turnaround, 50% cheaper, no RPD limit.

- [ ] **Complete enrichment** (via sync or batch), then:
  ```bash
  python3 pipeline/build.py
  python3 test_shacl.py
  ```
- [ ] **Verify Gemini context cache** (sync path only) — check that `cached=~9000` appears in enrich.py output on every call. If `cached=0`, the cache creation failed and we're paying full input price per call.

---


## Pipeline improvements (pre-enrichment)

- [ ] **Decide on enrichment provider and kick off run** — see section above.

## Provenance (post-enrichment)

- [ ] **PROV-O in graph** — `enrichment_stamps.model` is now stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims, and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions: import PROV-O, define enrichment activity class. Write ADR first.
- [ ] **SHACL/ontology: isolation exercise movement patterns** — 12 exercises have no movement pattern because the vocabulary lacks isolation patterns (ElbowFlexion, HipAbduction, etc.). Decide: add them, or accept that isolation exercises have no pattern. ADR required.
- [ ] **SHACL/ontology: Mobility/SoftTissue PrimeMover exemption** — 4 stretches correctly have only PassiveTarget muscles but will fail `sh:minCount 1` PrimeMover. Relax constraint for passive exercises. ADR required.

## Pipeline improvements (post-enrichment)

- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end and prints a table. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
---

## MCP server

- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.

---

## Ontology and vocabulary

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.

---

## Evaluation and HITL

- [ ] **Annotate gold standard** — review `evals/gold_annotation.xlsx`. Target: 30–50 exercises fully verified.
- [ ] **eval.py** — automated scoring against completed gold standard (precision/recall/F1 per field).
- [ ] **HITL correction loop** — mechanism for domain experts to flag incorrect classifications, with corrections feeding back into prompt grounding and ontology guidance. Architecture (triage queue → prompt update → re-enrich) needs design before building.

---

## Validation and quality

- [ ] **Build `pipeline/validate.py`** — 6-dimension quality scorecard (validity, uniqueness, integrity, timeliness, consistency, completeness). Design before building; needs a real graph to validate against. Unblock after enrichment completes.
- [ ] **Add build smoke test to CI** — `pipeline/build.py` can run against an empty `pipeline.db` to verify RDF assembly doesn't crash. Add as a CI step after seeding a minimal fixture DB.
- [ ] **Trend tracking** — append summary stats from `validate.py` runs to `quality_history.csv` once validate.py exists.

---

## Personas and use cases

Four JTBDs are documented in README.md. No further action needed.
