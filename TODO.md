# TODO

Remaining work is grouped by execution horizon.

---

## Now

- [ ] **SHACL failure: Parallette Push Up to L Sit** — `ex_ffdb_Parallette_Push_Up_to_L_Sit` has a joint action appearing in both `primaryJointAction` and `supportingJointAction`. Force restamp: `python3 pipeline/enrich.py --force ffdb_Parallette_Push_Up_to_L_Sit`.
- [ ] **Timeliness: 14 exercises with unresolved enrichment warnings** — 9 stripped terms from the latest run: `AntiRotation` (1), `HipHinge` (5 bent-over rows), `HipRotation` (1), `HipShift` (1), `InfraspinatusHead` (2), `Piriformis` (1), `RearDelt` (1), `SerrratusAnterior` (typo, 1), `TrapezTrapezius` (typo, 1). Each either needs the vocab term added/fixed and a restamp, or the prompt corrected. Typos (`SerrratusAnterior`, `TrapezTrapezius`) are straightforward fixes; others need ADR consideration.
- [ ] **Movement pattern gaps (506 exercises, 15%)** — Investigated: 459 true isolations (correct, no pattern needed), 9 passive/mobility (covered by SHACL exemption TODO), 53 compound exercises with no pattern. The 53 split into: ~25 ab/core (SpinalFlexion-dominant, potential `CoreFlexion` pattern gap), ~8 battle ropes + ~3 cardio (genuinely no pattern, accept gap), ~10 prompt misses (upright rows → `VerticalPull`, pelican curls → `HorizontalPull` — restamp candidates). Decision: do not add `CoreFlexion` or isolation-level patterns without serious deliberation — the fundamental movement pattern vocabulary is well-established and should not be extended lightly. Backlogged. ADR required before any vocabulary addition.
- [ ] **Gold standard annotation** — `evals/gold_annotation.xlsx` is blank. After graph is complete, seed with archetype exercises (one per movement pattern). Target 30–50 verified. Use run_notes.md flags (Brachioradialis on hangs, etc.) as candidates.
- [ ] **eval.py** — automated scoring against completed gold standard (precision/recall/F1 per field). Unblocked after annotation.

---

## Next

- [ ] **PROV-O in graph** — `enrichment_stamps.model` is stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions; write ADR first.
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.

---

## Later

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.
