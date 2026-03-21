# TODO

Items are grouped by theme, roughly priority-ordered within each group.

---

## Enrichment pipeline

- [x] **Fix Prime Mover inflation** — tightened PrimeMover `rdfs:comment` to require primary biomechanical action matching defining joint action (ADR-056). `repair_04` consolidates all heads of a MuscleRegion post-ingestion when all siblings present at same degree (ADR-055). Prompt pulls definition dynamically from vocabulary.
- [x] **Add Power modality** — `feg:Power` named individual in `training_modalities.ttl`. ADR-050.
- [x] **Mobility/SoftTissue Prime Mover exemption** — added `feg:PassiveTarget` involvement degree. Exercises with PassiveTarget are exempt from PrimeMover requirement. ADR-052.
- [x] **Joint action movement patterns** — Resolved as a three-layer orthogonal model (ADR-053/054). `feg:primaryJointAction` / `feg:supportingJointAction` subproperties added (ADR-058). `AntiExtension`, `AntiRotation`, `AntiLateralFlexion` added as sub-patterns under `TrunkStability`. `SpinalStability` added as a joint action (isometric).
- [x] **Re-enrich all exercises with new schema** — 50 exercises re-enriched with `primary_joint_actions` / `supporting_joint_actions` split. SHACL conforms. 3 post-enrichment prompt fixes identified (self_eval_round3.md).
- [x] **Re-enrich round 4** — 50 exercises re-enriched with improved prompt (ADR-060). SHACL conforms (1 manual inline fix). Self-eval in eval_package/self_eval_round4.md.
- [x] **check_stale.py** — detects enriched exercises whose vocabulary version stamps are behind current vocabulary. Exits 1 if stale, 0 if current. Flags: `--verbose`, `--names-only`.
- [x] **Per-exercise file storage + backoff** — enriched/ and quarantine/ use one file per exercise. enrich.py retries 429s with exponential backoff (tenacity). Default concurrency=1. ADR-063.
- [x] **Address prompt failure modes from self_eval_round3** — (1) joint action concepts leaking into muscle involvements; (2) setup-position-as-joint-action; (3) anti-extension / SpinalExtension confusion; (4) empty array fallback. All addressed in ADR-060. Round 4 self-eval confirms: setup-position 3→0, SpinalExtension confusion 1→0, misspellings 2→0, JA-as-muscle 3→1 (1 manual fix). New: TricepsBrachii group-level in minor roles (6 ex), AnkleEversion on squat — see self_eval_round4.md.
- [x] **ScapularUpwardRotation-as-muscle** — three-layer fix: `owl:disjointWith` on `feg:Muscle`, SHACL SPARQL constraint (injected into prompt), `repair_05` safety net (ADR-061). Alternating Cable Shoulder Press re-enriched clean. No manual fixes required going forward.
- [x] **Address remaining prompt failure modes from self_eval_round4** — (1) Dorsiflexion vs AnkleEversion for squats; (2) TricepsBrachii specificity in Stabilizer/Synergist roles; (3) Push/Pull on isolation exercises; (4) Anti-movement pattern joint action generalization; (5) Stabilizer inflation on Mobility exercises; (6) explosive hip extension PrimeMover. All addressed via rdfs:comment additions in ADR-062. shapes.ttl 0.8.0, involvement_degrees.ttl 0.2.2.
- [x] **Re-enrich round 5** — 50 exercises re-enriched (ADR-062 prompt). 3 inline fixes (Windmill, Heel Touchers, Renegade Row, Kettlebell Row JA). SHACL conforms (0 violations). Self-eval in self_eval_round5.md.
- [ ] **Continue enrichment** — currently at 50/873. Scale up after gold standard validation.

---

## Ontology and vocabulary

- [x] **Tighten `movementPattern sh:minCount`** — tightened to 1 in ADR-051; relaxed back to 0 in ADR-059. Movement patterns are now optional — isolation exercises with no clean pattern return empty array.
- [x] **Joint action vocabulary** — `joint_actions.ttl` v0.1.0 with 45 actions across 9 joint grouping nodes. `feg:primaryJointAction` and `feg:supportingJointAction` subproperties added (ADR-058). `shapes.ttl` v0.6.1.
- [x] **Rhomboids in useGroupLevel** — decision: keep heads (RhomboidMajor/RhomboidMinor). The distinction is meaningful for exercise programming (major = lower/mid scapula retraction, minor = upper). No useGroupLevel flag.
- [ ] **Namespace** — replace `https://placeholder.url#` with a real URI before any public release.
- [x] **URI hygiene** — exercise IDs sanitized at URI construction time: hyphens replaced with underscores in `preprocess.py` (`sanitized_id` field) and `ingest.py` (`_sanitize_id()`). Raw ID preserved in `feg:legacySourceId`. ADR-064.

---

## Evaluation

- [x] **Gold standard annotation workbook** — `evals/gold_annotation.xlsx` with index sheet + one sheet per exercise (50 total). Pre-populated from enriched output. Status dropdowns, correction columns.
- [x] **seed.json refreshed** — 50 exercises, full current schema (primary/supporting joint actions).
- [x] **eval_package refreshed** — `exercises.json` (50 ex), `vocabulary.ttl` (1325 triples), `INSTRUCTIONS.md` (updated for round 4 + TricepsBrachii note), `self_eval_round4.md`. Round 4 enrichment, SHACL conforms.
- [x] **eval_package round 5** — rebuilt `exercises.json` (50 ex), `vocabulary.ttl` (1470 triples), `INSTRUCTIONS.md` (updated Known Issues — 11 items), `self_eval_round5.md`. Vocab versions shapes 0.8.0, degrees 0.2.2.
- [ ] **Annotate gold standard** — review `evals/gold_annotation.xlsx`. Target: 30–50 exercises fully verified.
- [ ] **eval.py** — automated scoring against completed gold standard (precision/recall/F1 per field).

---

## Pipeline and tooling

- [x] **SPARQL query library** — `queries/` directory with 5 analytical queries covering exercise discovery, substitution, push/pull balance, region targeting, and enrichment coverage.
- [x] **pyproject.toml** — ruff config, pinned dependencies, streamlit optional extra.
- [x] **SHACL test harness** — `test_shacl.py` at project root. 11 test cases covering all constraint categories. Uses in-memory vocab graph; 11/11 passing.

---

## Governance and documentation

- [x] **README.md** — project overview with architecture, governance framing, and run instructions.
- [x] **sources/free-exercise-db/README.md** — expanded to cover enrich.py, check_stale.py, enriched/ folder, ontology relationship table, and full script reference.
- [x] **CONTRIBUTING.md** — lightweight operational guide covering change process, ADR requirement, vocabulary versioning, generated files, and safe scripts. At project root.
- [ ] **GOVERNANCE.md** — formal change management process document (heavier than CONTRIBUTING.md — covers conflict resolution, release process, namespace ownership).
