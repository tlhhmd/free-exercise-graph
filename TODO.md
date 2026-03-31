# TODO

Remaining work is grouped by execution horizon.

---

## Now

- [ ] **Residual movement pattern gaps** — TODO text is stale. The graph still has compound exercises with no movement pattern, and `DECISIONS.md` still treats this as an open vocabulary/design question rather than a closed bookkeeping task. Reconcile the current backlog count and decide which are legitimate no-pattern cases vs. candidates for new pattern concepts.
- [ ] **Gold standard annotation** — `evals/gold_annotation.xlsx` is now seeded (51 sheets total including index), so the workbook is no longer blank. Remaining work: verify/correct 30–50 exercises. Current sheets appear to still be in `Pending` status. Methodology: strict (muscle, degree) pair F1 + muscle-name F1 + conditional degree accuracy; exact movement pattern match; leaf-level annotation required (ADR-109). Use `run_notes.md` flags as candidates.

---

## Next

- [ ] **Deploy and verify Builder View** — Builder View implementation and `observatory.json` are in the repo, and Pages deploy validation exists in CI. Remaining work: open the live site, search for "Dead Bug", open the detail sheet, confirm the User/Builder toggle appears and all 5 stages render. Five curated exercises: Dead Bug, Romanian Deadlift, Cable Crunch, Double KB Gorilla Row, Bent Over Barbell Row.
- [ ] **PROV-O in graph** — `enrichment_stamps.model` is stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions; write ADR first.
- [x] **Design system migration** — `docs/DESIGN.md` written. Type scale (7 tokens) and border radius scale (6 tokens) migrated in `app/style.css`. Accessibility pass: 7 contrast failures fixed (degree badge text darkened, exercises/vocab accents darkened, stabilizer badge de-coupled from accent, nav bar on vocab tab fixed).
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.
- [ ] **Promote stable app heuristics into graph-governed outputs** — planning/tracking doc exists in [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md). Remaining work is the actual promotion. Candidates: `visualRegions`, `bodyFocus`, `explosiveness`, `builderRoles`, maybe `movementFamily`. Requires deliberate separation between governed computed exports and purely presentational copy like `whyHints` / `practicalNote`.

---

## Later

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.
