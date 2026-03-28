# TODO

Remaining work is grouped by execution horizon.

---

## Now

- [ ] **SHACL failure: Parallette Push Up to L Sit** — `ex_ffdb_Parallette_Push_Up_to_L_Sit` has a joint action appearing in both `primaryJointAction` and `supportingJointAction`. Force restamp: `python3 pipeline/enrich.py --force ffdb_Parallette_Push_Up_to_L_Sit`.
- [ ] **Add Piriformis to muscles.ttl** — Miniband Side Lying Clamshell emits `Piriformis` (real muscle, not in vocab). Needs ADR (minor vocab addition, MINOR version bump), then `--restamp Piriformis`. HipExternalRotation comment in joint_actions.ttl already references piriformis.
- [ ] **CoreFlexion movement pattern decision** — 51 exercises (Crunches, Sit-Ups, Hanging Leg Raises, Cable Crunches, etc.) have `RectusAbdominis`/`Obliques` as PrimeMover and `SpinalFlexion` as joint action but no movement pattern. Gap: no pattern for dynamic spinal flexion. Options: `SpinalFlexion` (reuse JA name, risk confusion) or `CoreFlexion` (coined, gym-friendly). ADR required before any vocab change.
- [ ] **Movement pattern prompt misses (~10 exercises)** — upright rows missing `VerticalPull`, pelican curls missing `HorizontalPull`. Restamp candidates once identified. Lower priority than Piriformis/CoreFlexion.
- [ ] **Double Kettlebell Gorilla Row HipHinge warning** — persists after restamp (prompt fix insufficient for this entity). `movement_pattern: HorizontalPull` is correct; data is not degraded. Low priority.
- [ ] **Remove dead compare/build CSS from style.css** — compare-tray, compare-grid, build-slot, mode-chip, mode-bar styles remain after compare/build removal from JS/HTML.
- [ ] **Gold standard annotation** — `evals/gold_annotation.xlsx` is blank. After graph is complete, seed with archetype exercises (one per movement pattern). Target 30–50 verified. Use run_notes.md flags (Brachioradialis on hangs, etc.) as candidates.
- [ ] **eval.py** — automated scoring against completed gold standard (precision/recall/F1 per field). Unblocked after annotation.

---

## Next

- [ ] **PROV-O in graph** — `enrichment_stamps.model` is stored. Update `build.py` to emit `prov:wasAttributedTo` on inferred claims and `prov:wasGeneratedBy` for the enrichment activity (model, timestamp). Requires ontology additions; write ADR first.
- [ ] **Performance benchmarking script** — `pipeline/bench.py` that times each stage end-to-end. Currently measured manually: canonicalize 0.2s, identity 0.18s, reconcile 0.24s, build 1.87s.
- [ ] **Claude Desktop integration test** — configure `claude_desktop_config.json` and test `find_substitutions` with equipment constraints end-to-end.
- [ ] **Promote stable app heuristics into graph-governed outputs** — tracked in [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md). Candidates: `visualRegions`, `bodyFocus`, `explosiveness`, `builderRoles`, maybe `movementFamily`. Requires deliberate separation between governed computed exports and purely presentational copy like `whyHints` / `practicalNote`.

---

## Later

- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release. Decision: `https://feg.talha.foo/ontology#` (feg:) and `https://feg.talha.foo/data#` (fegd:). Requires GitHub Pages + DNS setup on talha.foo.
- [ ] **Namespace migration** — `constants.py` and `sync_namespaces.py` are ready. Update `FEG_NS` in `constants.py` then run `python3 sync_namespaces.py --apply` when DNS is in place.
