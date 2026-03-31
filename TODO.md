# TODO

Remaining work is grouped by execution horizon.

---

## Now

- [ ] **Residual movement pattern gaps (74 exercises)** — All categorized and accepted. Breakdown: chest flyes (24, ShoulderHorizontalAdduction alone), front raises (13, ShoulderFlexion alone), glute/hip isolation (12), scaption/deltoid (5), leg extensions (2), neck work (3), pullovers/straight-arm pulls (5), battling ropes (5), cardio equipment (stationary/recumbent bike), other (5). All are isolation exercises or cardio equipment that the compound-JA filter catches but correctly have no pattern. Known false-positive rate in the completeness check. No action needed before gold annotation.
- [ ] **Gold standard annotation** — `evals/gold_annotation.xlsx` is blank. Seed with archetype exercises (one per movement pattern). Target 30–50 verified. Methodology: strict (muscle, degree) pair F1 + muscle-name F1 + conditional degree accuracy; exact movement pattern match; leaf-level annotation required (ADR-109). Use run_notes.md flags as candidates.

---

## Next

- [ ] **Deploy and verify Builder View** — push to GitHub Pages. Open the live site, search for "Dead Bug", open the detail sheet, confirm the User/Builder toggle appears and all 5 stages render. Five curated exercises: Dead Bug, Romanian Deadlift, Cable Crunch, Double KB Gorilla Row, Bent Over Barbell Row.
- [ ] **PROV-O in graph** — `enrichment_stamps.model` is stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions; write ADR first.
- [ ] **Design system migration** — `docs/DESIGN.md` written. Type scale (7 tokens) and border radius scale (6 tokens) migrated in `app/style.css`. Accessibility pass: 7 contrast failures fixed (degree badge text darkened, exercises/vocab accents darkened, stabilizer badge de-coupled from accent, nav bar on vocab tab fixed).
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.
- [ ] **Promote stable app heuristics into graph-governed outputs** — tracked in [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md). Candidates: `visualRegions`, `bodyFocus`, `explosiveness`, `builderRoles`, maybe `movementFamily`. Requires deliberate separation between governed computed exports and purely presentational copy like `whyHints` / `practicalNote`.

---

## Later

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.
