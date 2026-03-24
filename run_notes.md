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

---
