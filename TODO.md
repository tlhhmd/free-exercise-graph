# TODO

Items are grouped by theme, roughly priority-ordered within each group.

---

## Enrichment pipeline

- [ ] **Fix Prime Mover inflation** _(LOE: Low)_ — prompt refinement to limit prime movers to absolute primary drivers on multi-phase/compound exercises (e.g. Clean and Press). Re-enrich affected exercises. No schema changes.
- [x] **Add Power modality** — `feg:Power` named individual in `training_modalities.ttl`. ADR-050.
- [x] **Mobility/SoftTissue Prime Mover exemption** — added `feg:PassiveTarget` involvement degree. Exercises with PassiveTarget are exempt from PrimeMover requirement. ADR-052.
- [ ] **Joint action movement patterns** _(LOE: Medium–High)_ — `Pull` and `VerticalPush` are poor fits for isolation exercises (curls, lateral raises, front raises). Consider adding `ElbowFlexion`, `ElbowExtension`, `ShoulderAbduction`, `ShoulderFlexion` etc. as movement pattern concepts. Vocabulary design decision needed before implementation — are joint actions peers to existing patterns or a separate layer? Large re-enrichment scope.
- [ ] **Continue enrichment** — currently at 50/873 exercises. Scale up once prompt issues above are addressed.
- [ ] **check_stale.py** — tool to detect enriched exercises whose vocabulary version stamps are behind current vocabulary. Needed once enrichment is at scale and vocabulary is still evolving.

---

## Ontology and vocabulary

- [x] **Tighten `movementPattern sh:minCount`** — tightened to 1 in ADR-051. validate.py now filters to enriched exercises only.
- [ ] **Rhomboids in useGroupLevel** — model consistently uses `RhomboidMajor`/`RhomboidMinor` as prime movers on row exercises despite the group-level rule. Repair queries catch this post-ingestion, but revisit whether Rhomboids belongs in `useGroupLevel` or whether heads are legitimately meaningful.
- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release.

---

## Evaluation

- [ ] **Incorporate eval feedback** — two evaluation reports in `eval_package/`. Address findings in priority order: Prime Mover inflation → Power modality → Mobility exemption → joint action patterns.
- [ ] **Gold standard dataset** — 30–50 exercises with human-verified classifications. Required for quantitative eval (F1, precision, recall per field). `evals/annotate.py` exists for this purpose.
- [ ] **eval.py** — automated scoring against gold standard.

---

## Pipeline and tooling

- [x] **SPARQL query library** — `queries/` directory with 5 analytical queries covering exercise discovery, substitution, push/pull balance, region targeting, and enrichment coverage.
- [x] **pyproject.toml** — ruff config, pinned dependencies, streamlit optional extra.

---

## Governance and documentation

- [ ] **README.md** — project overview with architecture, governance framing, and run instructions.
- [ ] **GOVERNANCE.md** — formal change management process document.
- [ ] **Update ADR-047** — domain corrected from `feg:Muscle` to `feg:MuscleGroup`; version bumped to 0.2.1; `skos:editorialNote` added. ADR text still reflects old domain.
- [ ] **Update ADR-048** — repair.py was folded into `ingest.py` rather than kept as a standalone script. ADR text describes repair.py as a separate tool.
