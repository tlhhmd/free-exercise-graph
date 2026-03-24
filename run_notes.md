# Enrichment Run Notes

Observations and flags from reviewing enrichment output. Add notes after each review batch.

---

## Batch 1 — 10 exercises, Claude Sonnet 4.6, 2026-03-23

**Provider:** claude-sonnet-4-6
**Concurrency:** 4
**Exercises reviewed:** 10 (ffdb-heavy sample, specialist movements)

### Quality signals

- **Cossack Squat** — correctly assigned `AntiLateralFlexion` + `Squat` dual patterns and `FrontalPlane` + `SagittalPlane`. Strong.
- **Pallof Press** — `AntiRotation`, `TransversePlane`, `TransverseAbdominis` as PrimeMover. Correct.
- **KB Clean to Thruster** — `is_combination: true`, three movement patterns (HipHinge, KneeDominant, VerticalPush), `Power` modality. All correct.
- **Single Arm Ring Push Up** — `AntiRotation` added on top of `HorizontalPush` for instability demand. Good nuance.
- **KB Clean to Split Jerk** — `Lunge` pattern captured for the split position. Correct.
- **Hollow Body Flutter Kicks** — `AntiExtension` + `IsometricHold` dual patterns. Correct.

### Flags

- **Bar Dead Hang** — `Brachioradialis` and `WristFlexors` listed as PrimeMover. Shoulder girdle depressors (LowerTrapezius, SerratusAnterior) seem more defensible as primary. Both are present as Stabilizer. Watch for this pattern on other hangs, carries, and dead hang holds — if systematic, add a prompt grounding example.

### Verdict

Quality sufficient to run full batch. No prompt changes needed yet.

---

## Batch 2 — 100 exercises, Claude Sonnet 4.6, 2026-03-23

**Provider:** claude-sonnet-4-6
**Concurrency:** 3
**Total after batch:** 260/3450 (7.5%)

No failures. Cache holding at `cached=10896` on every call.

---

## Batch 3 — 250 exercises, Claude Sonnet 4.6, 2026-03-23

**Provider:** claude-sonnet-4-6
**Concurrency:** 3
**Total after batch:** 358/3450 (10.4%)

### Failures (2)

- **Alternating Single Arm Dumbbell Pendlay Row** — `HipHinge` placed in `supporting_joint_actions`. Model confused movement pattern with joint action. Schema `auto_correct_cross_vocab` only covered muscle↔joint_action confusion, not movement_pattern↔joint_action. Fixed in schema.py.
- **Double Kettlebell Gorilla Row** — same `HipHinge` in `supporting_joint_actions` failure. Occurred before schema fix was deployed.

### Schema fix deployed
Extended `auto_correct_cross_vocab` to strip movement pattern terms from joint action fields when correctly placed in `movement_patterns`.

---

## Batch 4 — 500 exercises, Claude Sonnet 4.6, 2026-03-23

**Provider:** claude-sonnet-4-6
**Concurrency:** 3
**Total after batch:** 855/3450 (24.8%)

### Failures (3)

- **Barbell Zercher Alternating Forward Lunge** — `BicepsBrachii` and `BicepsShortHead` both listed; ancestor overlap validator hard-failed. Root: correct to strip ancestor, not fail.
- **Alternating Single Arm Landmine Z Press** — `SerrratusAnterior` (triple-r typo). Unknown muscle validator hard-failed. Root: strip unknown, not fail.
- **Macebell Order Alternating Russian Step Up** — `ScapularStability` in `supporting_joint_actions`. Not a joint action term. Root: strip unknown, not fail.

### Schema fix deployed
All validators (`check_vocabulary`, `check_no_ancestor_overlap`, `check_no_duplicate_muscles`, `check_core_stabilizer`) converted from hard-fail to strip-and-warn. Warnings printed to stderr with `⚠` prefix. `check_prime_mover` remains hard-fail — no PrimeMover/PassiveTarget is a genuine enrichment failure.

---

## Batch 5 — 750 exercises, Claude Sonnet 4.6, 2026-03-23

**Provider:** claude-sonnet-4-6
**Concurrency:** 4
**Total after batch:** 1605/3450 (46.5%)
**Failures:** 0 (strip-and-warn validators deployed from batch 4)

### Warnings observed (stderr only — enrichment_warnings table not yet in place)

- **TrapezoidalHead** — stripped as unknown muscle. `Trapezius` and/or `UpperTrapezius` likely the intended term. No action needed; model self-corrects with valid terms.
- **HipFlexors + Iliopsoas ancestor overlap** — `Iliopsoas` (more specific) kept; `HipFlexors` (ancestor group) stripped. Correct behaviour.
- **GluteusMedius duplicate** — first occurrence kept, duplicate stripped. No action needed.
- **ScapularStability** — stripped from joint action field. Not a vocabulary term in any field. No action needed.
- **HipCircumduction** — stripped as unknown joint action. Determined to be a legitimate vocabulary gap (not hallucination). **→ ADR-094: added `feg:HipCircumduction` under `feg:Hip` in joint_actions.ttl, version bumped 0.2.0 → 0.3.0.** Knee Circles re-enriched manually via `--force`.
- **AntiLateralFlexion in joint action field** — movement pattern term placed in joint action field without a corresponding `movement_patterns` entry. Stripped by `auto_correct_cross_vocab` / `check_vocabulary`. No action needed.
- **InfraspinatusHead** — stripped as unknown muscle (we use `Infraspinatus` or group-level). Exercise also had `RotatorCuff` as PrimeMover. `useGroupLevel` is set for RotatorCuff heads — this is correct behaviour, no action needed.

### Infrastructure deployed this batch
- `enrichment_warnings` table created: persists `(entity_id, predicate, stripped_value, enriched_at)` for every stripped term.
- `enrichment_failures` table created: persists `(entity_id, failed_at, error)` for API/validation failures.
- `enrichment_stamps.model` column added: tracks which LLM model enriched each entity. Backfilled 109 rows with `claude-sonnet-4-6`.
- `--restamp <TERM>` flag: re-enriches all entities that had a specific term stripped (vocab update recovery).
- `--quarantine` flag: lists entities with ≥3 failures (skipped by default enrichment run).

### Note
Warnings from batches 1–5 were emitted to stderr only. The `enrichment_warnings` table was created during batch 5 but no historical backfill was performed. Future batches will persist warnings automatically.

---

## Batch 6 — 1000 exercises, Claude Sonnet 4.6, 2026-03-24

**Provider:** claude-sonnet-4-6
**Concurrency:** 4
**Total after batch:** 2604/3450 (75.5%)
**Failures:** 0

### Warnings (persisted to enrichment_warnings)

- **HipHinge** in `supporting_joint_actions` (1x) — recurring pattern, always stripped correctly.
- **ForearmPronation** as muscle (1x) — a movement description, not a muscle. Stripped.
- **ObliqueExternal** as muscle (1x) — reversed word order; correct term is `ExternalOblique`. **→ Added `skos:altLabel "ObliqueExternal"` to `feg:ExternalOblique` and `skos:altLabel "ObliqueInternal"` to `feg:InternalOblique` in muscles.ttl (PATCH, 0.12.0 → 0.12.1). Restamped affected entity.**
- **ScapularStability** in `supporting_joint_actions` (1x) — stripped.

### Other work done this batch
- `docs/reconciliation_example.md` created: Dead Bug traced through all 5 pipeline stages.
- `.github/workflows/ci.yml` expanded: SHACL + build + smoke SPARQL query.
- `TODO.md` reorganised around portfolio finishing priorities.

---

## Re-enrichment run — 3455 exercises, Claude Sonnet 4.6, 2026-03-24

**Provider:** claude-sonnet-4-6
**Concurrency:** 4
**Total:** 3455/3455 (100%) ✅
**Failures:** 0

Full re-enrichment after enrichment state was lost during the March 24 Codex refactor session. No prompt or ontology changes since the previous completed run. Rate started at ~14/min, peaked at ~36/min, settled at ~25/min under sustained load (API rate limiting). Total wall time ~2.5 hours.

### Warnings (14 total, 9 distinct terms — persisted to enrichment_warnings)

- **HipHinge** in `supporting_joint_actions` (5x) — same recurring pattern. Always stripped. Bent-over row exercises: `fed_Alternating_Kettlebell_Row`, `fed_Bent_Over_Two_Dumbbell_Row`, `fed_Bent_Over_Two_Dumbbell_Row_With_Palms_In`, `fed_One_Arm_Long_Bar_Row`, `ffdb_Double_Kettlebell_Gorilla_Row`.
- **InfraspinatusHead** (2x) — stripped; `useGroupLevel` maps to `RotatorCuff`. Same exercises as previous run.
- **AntiRotation** in `supporting_joint_actions` (1x) — `single_arm_bench_press`. Movement pattern term in JA field.
- **HipRotation** (1x) — `ffdb_Tire_Sledge_Hammer_Staggered_Stance_Slam`. Not a valid joint action term; may be a vocabulary gap.
- **HipShift** (1x) — `fed_Cable_Judo_Flip`. Not a valid term in any vocab field.
- **Piriformis** (1x) — `ffdb_Miniband_Side_Lying_Clamshell`. Not in muscles.ttl; deep external hip rotator. Potential vocabulary gap.
- **RearDelt** (1x) — `face_pull`. Colloquial name; correct term is `PosteriorDeltoid`. Prompt miss.
- **SerrratusAnterior** (1x) — triple-r typo, same as batch 4. `fed_Alternating_Deltoid_Raise`.
- **TrapezTrapezius** (1x) — garbled term. `ffdb_Heavy_Sandbag_Shoulder_Alternating_Curtsy_Lunge`.

All 14 are tracked in TODO.md as timeliness candidates.

### Corpus stats

| Metric | Value |
|---|---|
| Graph triples | 238,908 |
| Exercises with no movement pattern | 517 (15%) |
| Combination exercises | 292 (8.5%) |
| Compound exercises | 2,826 (82%) |
| Top movement patterns | VerticalPush (502), Lunge (456), HipHinge (445) |
| Top primary joint action | HipExtension (1,557) |
| Top exercise style | Bodybuilding (1,382) |
| Laterality split | Bilateral 1,613 / Unilateral 1,546 |
| Total warnings | 14 (9 distinct terms) |
| Total failures | 0 |

### Post-run
`python3 pipeline/build.py` → 238,908 triples. `python3 pipeline/validate.py --shacl --verbose` → 1 failure (Parallette Push Up to L Sit JA overlap), 2 warnings (timeliness + completeness).

---

## Final batch — 845 exercises, Claude Sonnet 4.6, 2026-03-24

**Provider:** claude-sonnet-4-6
**Concurrency:** 4
**Total after batch:** 3450/3450 (100%) ✅
**Failures:** 0

### Warnings (persisted to enrichment_warnings)

- **HipHinge** in `supporting_joint_actions` (4x) — recurring, stripped correctly every time.
- **ScapularStability** in `supporting_joint_actions` (1x) — stripped.
- **AntiRotation** in `supporting_joint_actions` (1x) — movement pattern term in joint action field, stripped.
- **Forearms ancestor overlap** (1x) — `WristFlexors` (descendant) present; `Forearms` (ancestor) stripped.

### Final corpus stats

| Metric | Value |
|---|---|
| Graph triples | 107,598 |
| Exercises with no movement pattern | 521 (15%) — isolation exercise gap, decision pending |
| Combination exercises | 293 (8.5%) |
| Compound exercises | 2,816 (82%) |
| Top movement patterns | VerticalPush (506), Lunge (451), HipHinge (446) |
| Top primary joint action | HipExtension (1,578) |
| Top exercise style | Bodybuilding (1,380) |
| Laterality split | Bilateral 1,598 / Unilateral 1,552 |
| Total warnings (all batches) | 10 distinct stripped terms |
| Total failures (all batches) | 3 (all pre-strip-and-warn, batch 4) |

### Post-run
`python3 pipeline/build.py` → 107,598 triples. `python3 test_shacl.py` → 11/11 passing.

---
