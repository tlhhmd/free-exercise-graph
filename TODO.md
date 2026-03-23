# TODO

Items are grouped by theme, roughly priority-ordered within each group.

---

## Enrichment in progress

Gemini 3.1 Pro (`gemini-3.1-pro-preview`) selected as provider. Context cache active (`pipeline/gemini_cache_id.txt`). Rate limit: ~250 RPD → ~16-day run at 4,095 entities. Script is resume-safe via `enrichment_stamps`.

- [ ] **Let enrichment run to completion** — then:
  ```bash
  python3 pipeline/build.py
  python3 test_shacl.py
  ```
- [ ] **Verify Gemini context cache** — check that `cached=~9000` appears in enrich.py output on every call. If `cached=0`, the cache creation failed and we're paying full input price per call.

---

## Quarantine resolution (resolved by re-enrichment)

These 4 exercises will be re-enriched under the new pipeline. Keeping for reference:

- **HipHinge-in-joint-actions** (2 exercises: `Alternating_Double_Kettlebell_Bent_Over_Row`, `Alternating_Single_Arm_Kettlebell_Ballistic_Row`) — model has no joint action term for "maintaining a hip hinge position." Design decision: add `HipFlexionIsometric` or accept `HipFlexion` in supporting actions.
- **Hallucinated muscle names** (2 exercises: `Resistance_Band_Pull_Apart` → `InfraspinatusHead`, `Single_Arm_Kettlebell_Suitcase_Alternating_Reverse_Lunge` → `LowerGastrocnemius`) — re-enrich under new pipeline.

---

## Pipeline improvements (post-enrichment)

- [ ] **Triage queue tooling** — `identity.py` defers near-duplicate pairs to `possible_matches`. Build a simple CLI review tool: show pairs side by side, accept merge / separate / variant_of decisions.
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end and prints a table. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Fed muscle crosswalk** — fed exercises currently have no feg-mapped muscles in resolved_claims (raw strings, no crosswalk). The LLM infers them from scratch. A crosswalk would give the LLM better grounding for 873 fed exercises.

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

## Governance and documentation

- [ ] **Trend tracking for quality scorecard** — append summary stats from `validate.py` runs to `quality_history.csv` to show trend over time.
- [ ] **Productized quality scorecard** — stakeholder-readable Graph Health report summarizing `validate.py` output.

---

## Personas and use cases

Four JTBDs are documented in README.md. No further action needed.
