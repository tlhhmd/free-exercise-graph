# TODO

Remaining work is grouped by execution horizon.

---

## Now

- [ ] **Gold standard annotation** — review the batched workbooks in `evals/unreviewed/`, then move completed batches into `evals/submitted/` for scoring with `python3 evals/eval.py`. Batches are generated from the live canonical `pipeline.db` using a representative 50-exercise sample plus a small edge-case coverage slice, split into 10-exercise files. Methodology: strict (muscle, degree) pair F1 + muscle-name F1 + conditional degree accuracy; exact movement pattern match; leaf-level annotation required (ADR-109). Use `run_notes.md` flags as candidates for explicit inclusion when rebuilding the workbook.

---

## Next

- [ ] **Deploy and verify Builder View** — Builder View implementation and `observatory.json` are in the repo, and Pages deploy validation exists in CI. Remaining work: open the live site, search for "Dead Bug", open the detail sheet, confirm the User/Builder toggle appears and all 5 stages render. Five curated exercises: Dead Bug, Romanian Deadlift, Cable Crunch, Double KB Gorilla Row, Bent Over Barbell Row.
- [ ] **Similarity blocking/scoring refinement** — the Phase 1 similarity build showed that very high-frequency concepts like `Core`, `ErectorSpinae`, and generic actions such as `HipExtension` can push candidate generation toward near all-pairs. Keep tuning the offline graph builder so broad stabilizers and generic actions do not dominate candidate nomination or inflate dense low-value neighborhoods.
- [ ] **Similarity-signal ontology review** — review whether the same high-frequency concepts are only an algorithm/blocking problem or evidence that the ontology/vocabulary needs refinement (for example hinge sub-taxonomy, trunk/bracing treatment, or more specific movement-intent dimensions). Write ADR first if this becomes a vocabulary change.
- [ ] **Pipeline-level substitute canonicalization + deduplication** — near-duplicate exercises are still leaking into substitute outputs as naming or minor-format variants of the same lift. Fix this upstream in the build pipeline rather than the frontend. Suggested direction: normalize exercise names (case, punctuation, token order, common synonyms), define a canonical key from movement pattern + primary joint actions + prime movers + normalized name skeleton, and collapse near-duplicates before neighbor selection or before UI emission.
- [ ] **Reason-string correctness in substitute build** — some generated explanations still mention differences that are not actually present (especially equipment). Move reason generation toward explicit feature-diff checks in the build step so we only mention true differences, avoid templated assumptions, and keep the UI copy trustworthy.
- [ ] **PROV-O in graph** — `enrichment_stamps.model` is stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions; write ADR first.
- [x] **Design system migration** — `docs/DESIGN.md` written. Type scale (7 tokens) and border radius scale (6 tokens) migrated in `app/style.css`. Accessibility pass: 7 contrast failures fixed (degree badge text darkened, exercises/vocab accents darkened, stabilizer badge de-coupled from accent, nav bar on vocab tab fixed).
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.
- [ ] **Promote stable app heuristics into graph-governed outputs** — planning/tracking doc exists in [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md). Remaining work is the actual promotion. Candidates: `visualRegions`, `bodyFocus`, `explosiveness`, `builderRoles`, maybe `movementFamily`. Requires deliberate separation between governed computed exports and purely presentational copy like `whyHints` / `practicalNote`.

---

## Later

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.
