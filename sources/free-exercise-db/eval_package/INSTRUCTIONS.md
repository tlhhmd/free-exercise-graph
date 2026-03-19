# Exercise Classification Evaluation

Thank you for evaluating this dataset. This document explains what you are reviewing, why it matters, and how to provide feedback.

---

## Background

We are building a **semantic knowledge graph** of exercises on top of an open-source exercise database (~873 exercises). The source database records basic facts about each exercise — name, instructions, and a flat list of primary and secondary muscles — but no structured classification.

We have used an AI system (Claude, Anthropic) to enrich each exercise with four additional properties:

1. **Movement pattern** — the mechanical structure of the movement
2. **Training modality** — the physiological adaptation the exercise targets (if applicable)
3. **Muscle involvements** — which muscles are recruited, and to what degree
4. **Unilateral flag** — whether the exercise is performed one limb at a time

These enriched classifications will become structured data in a knowledge graph. Downstream applications include:

- **Exercise discovery** — "show me horizontal pull exercises targeting the lats"
- **Substitution** — "find a replacement for barbell rows that uses the same movement pattern and primary muscles"
- **Program design** — filtering by muscle group, movement pattern, or modality when building training plans

Because the graph is used for structured querying, **incorrect classifications have real consequences**: an exercise miscategorised as a push movement will appear in push day recommendations, and a muscle assigned the wrong degree will skew muscle balance analysis.

---

## The Data

`exercises.json` contains 50 exercises. Each has this structure:

```json
{
  "id": "Barbell_Deadlift",
  "name": "Barbell Deadlift",
  "instructions": "Stand in front of a loaded barbell...",
  "source_muscles": {
    "primary": ["lower back"],
    "secondary": ["calves", "forearms", "glutes", "hamstrings", ...]
  },
  "enrichment": {
    "movement_patterns": ["HipHinge"],
    "training_modalities": [],
    "muscle_involvements": [
      {"muscle": "GluteusMaximus", "degree": "PrimeMover"},
      {"muscle": "ErectorSpinae", "degree": "Synergist"},
      ...
    ],
    "is_unilateral": false
  },
  "notes": "",
  "flag": false
}
```

`source_muscles` is the original flat data from the source database — provided for reference only. The `enrichment` block is what you are evaluating.

The `notes` and `flag` fields are for your feedback (see below).

---

## Vocabulary

All values in the enrichment block must come from the controlled vocabularies below. Part of your evaluation is assessing whether the right terms were chosen.

---

### Involvement Degrees

Every muscle involvement has a degree. There are exactly three:

| Degree | Definition |
|---|---|
| **Prime Mover** | The muscle primarily responsible for producing the movement. The prime mover is the intended target of the exercise. |
| **Synergist** | A muscle that assists the prime mover in producing the movement. Contributes meaningfully but is not the primary target. |
| **Stabilizer** | A muscle that contracts to stabilize a joint without contributing directly to the movement. Active but not trained in a meaningful strength or hypertrophy sense. |

**Rules:**
- Every exercise must have at least one Prime Mover.
- A muscle may only appear once per exercise (not as both Synergist and Stabilizer, for example).
- Prefer specificity: if a specific muscle head is relevant, name it rather than the group (e.g. `AnteriorDeltoid` rather than `Deltoid`). Exceptions noted in the Muscle section below.

---

### Movement Patterns

Use the most specific pattern that applies. An exercise may have more than one pattern (e.g. a thruster is both `KneeDominant` and `VerticalPush`). Use a parent pattern only when no child fits.

```
Carry — Movements in which load is held and transported, demanding full-body stability and grip.
HipHinge — Hip-driven movements with significant posterior chain recruitment.
KneeDominant — Knee-driven movements with significant quadriceps recruitment.
  Lunge — Knee dominant with one foot traveling forward, dynamic balance demand.
  SplitSquat — Knee dominant with staggered stance, both feet fixed.
  Squat — Bilateral knee dominant, both feet fixed, hips descend.
Locomotion — Whole-body travel: running, jumping, crawling.
Mobility — Stretching, flexibility, range of motion work.
Pull — Force produced by pulling load toward the body.
  HorizontalPull — Pulling horizontally (rows): mid-back, rear delt, biceps.
  VerticalPull — Pulling vertically (pull-ups, lat pulldowns): lats, biceps.
Push — Force produced by pushing load away from the body.
  HorizontalPush — Pushing horizontally (bench press): chest, front delt, triceps.
  VerticalPush — Pushing vertically (overhead press): shoulders, triceps.
Rotation — Trunk rotation or anti-rotation: obliques, deep core.
SoftTissue — Foam rolling, myofascial release.
TrunkStability — Trunk flexion, extension, or isometric: planks, crunches, ab work.
```

---

### Training Modalities

Assign a modality **only when it is a defining characteristic** of the exercise — not merely its common training context. Most resistance training exercises (squats, rows, presses) have no defining modality and should have an empty list.

| Modality | Assign when... |
|---|---|
| **Cardio** | Cardiovascular endurance is the defining purpose (e.g. jump rope, cycling). |
| **Hypertrophy** | Moderate loads and volume are structurally built into the exercise. Rare — most exercises can be used for hypertrophy regardless of classification. |
| **Mobility** | Improving range of motion is the defining purpose. |
| **Plyometrics** | Explosive intent and stretch-shortening cycle are the defining feature (e.g. box jump, clap push-up). |
| **Strength** | Maximal force production is the defining purpose. Rare — most exercises can be used for strength. |

---

### Muscles

The muscle vocabulary is a three-level hierarchy: **Region → Group → Head**.

Prefer the most specific term available (Head > Group > Region). Use a group when no head distinction is meaningful. Use a region only when no group applies.

**Exception — group-level muscles:** The following groups are the correct granularity regardless of degree. Do not use their individual heads:

- Erector Spinae
- Gastrocnemius
- Obliques
- Rhomboids
- Rotator Cuff
- Scalenes
- Wrist Extensors
- Wrist Flexors

**Full muscle hierarchy:**

```
Abdominals (region)
  Core (group) — convenience term for compound movements where bracing is incidental
  Obliques (group) ← use group level, not heads
    ExternalOblique (head)
    InternalOblique (head)
  RectusAbdominis (group)
  TransverseAbdominis (group)

Abductors (region)
  TensorFasciaeLatae (group)

Adductors (region)
  AdductorBrevis (head)
  AdductorLongus (head)
  AdductorMagnus (head)
  Gracilis (group)

Biceps (region)
  BicepsBrachii (group)
    BicepsLongHead (head)
    BicepsShortHead (head)
  Brachialis (group)

Chest (region)
  PectoralisMajor (group)
    ClavicularHead (head)
    SternalHead (head)
  PectoralisMinor (group)
  SerratusAnterior (group)

Forearms (region)
  Brachioradialis (group)
  WristExtensors (group) ← use group level, not heads
    ExtensorCarpiRadialis (head)
    ExtensorCarpiUlnaris (head)
  WristFlexors (group) ← use group level, not heads
    FlexorCarpiRadialis (head)
    FlexorCarpiUlnaris (head)

Glutes (region)
  GluteusMaximus (group)
  GluteusMedius (group)
  GluteusMinimus (group)

Hamstrings (region)
  BicepsFemoris (head)
  Semimembranosus (head)
  Semitendinosus (head)

Lats (region)
  LatissimusDorsi (group)

LowerBack (region)
  ErectorSpinae (group) ← use group level, not heads
    Iliocostalis (head)
    Longissimus (head)
    Spinalis (head)
  Psoas (group)
    Iliopsoas (head)
  QuadratusLumborum (group)

LowerLeg (region)
  Calves (region)
    Gastrocnemius (group) ← use group level, not heads
      LateralGastrocnemius (head)
      MedialGastrocnemius (head)
    Soleus (group)
  TibialisAnterior (group)

MiddleBack (region)
  Rhomboids (group) ← use group level, not heads
    RhomboidMajor (head)
    RhomboidMinor (head)

Neck (region)
  Scalenes (group) ← use group level, not heads
    AnteriorScalene (head)
    MiddleScalene (head)
    PosteriorScalene (head)
  Sternocleidomastoid (group)

Quadriceps (region)
  RectusFemoris (head)
  VastusIntermedius (head)
  VastusLateralis (head)
  VastusMedialis (head)

Shoulders (region)
  Deltoid (group)
    AnteriorDeltoid (head)
    LateralDeltoid (head)
    PosteriorDeltoid (head)
  RotatorCuff (group) ← use group level, not heads
    Infraspinatus (head)
    Subscapularis (head)
    Supraspinatus (head)
    TeresMinor (head)

Traps (region)
  Trapezius (group)
    LowerTrapezius (head)
    MiddleTrapezius (head)
    UpperTrapezius (head)

Triceps (region)
  TricepsBrachii (group)
    TricepsLateralHead (head)
    TricepsLongHead (head)
    TricepsMedialHead (head)
```

---

## What to Evaluate

For each exercise, assess:

1. **Movement pattern(s)** — correct pattern selected? Too broad, too specific, or missing?
2. **Training modality** — correctly omitted for most exercises? Correctly assigned where relevant?
3. **Muscle involvements** — are the right muscles listed? Are degrees correct (prime mover vs synergist vs stabilizer)? Any muscles missing or wrongly included?
4. **Unilateral flag** — correct? (True only for exercises inherently performed one limb at a time.)

You do not need to re-classify every exercise from scratch. Focus on identifying errors, omissions, and cases where you disagree with the classification.

---

## How to Provide Feedback

Edit `exercises.json` directly:

- Set `"flag": true` for any exercise where you have a concern.
- Use the `"notes"` field to describe the issue and, where possible, the correction.

Example:

```json
{
  "name": "Seated Hamstring and Calf Stretch",
  "flag": true,
  "notes": "Should be classified as Mobility modality. Gastrocnemius should be PrimeMover not Synergist."
}
```

You do not need to edit any other fields — just flag and note. We will incorporate your feedback into the vocabulary and re-run the classification where needed.

---

## Questions

If anything is unclear, or if you encounter a muscle or movement that does not appear to fit the vocabulary, please note it — those gaps are valuable feedback in themselves.
