# Architecture Decision Record
## free-exercise-graph Ontology

This document captures the design decisions, rationale, open questions,
and backlog items for the free-exercise-graph ontology. It is a living
document and should be updated as decisions are made or revisited.

---

## Source Data

**Base dataset:** [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)
(public domain, Unlicense) — 800+ exercises in JSON format.

### Source Schema Critique

| Property | Decision | Rationale |
|---|---|---|
| `id` | Keep as `feg:legacySourceId` | Preserve provenance link to source data |
| `name` | Keep as `rdfs:label` | Standard semantic web practice |
| `force` | **Drop** | push/pull/static too coarse; replaced by MovementPattern |
| `level` | **Drop** | Criteria undefined, no v1 use case dependency |
| `mechanic` | **Drop** | Redundant with MovementPattern; see ADR-010 |
| `equipment` | Keep, model as class hierarchy | "other" is a known gap in source data |
| `primaryMuscles` | **Replace** with MuscleInvolvement model | Binary primary/secondary too coarse and misleading |
| `secondaryMuscles` | **Replace** with MuscleInvolvement model | Same reason |
| `category` | **Restructure** as TrainingModality | Source data conflates modality with sport discipline |
| `instructions` | Keep as data property | Useful content, out of scope for enrichment |
| `images` | Keep as data property | Out of scope for enrichment |

### Known Data Quality Issues

- **Equipment as identity:** Exercises like "Jogging, Treadmill" treat
  equipment context as part of exercise identity - a modeling mistake.
  Equipment is a property of how an exercise is performed, not of the
  exercise itself.
- **Muscle granularity:** Source terms like "shoulders" and "biceps" are
  regional, not anatomical. They map to muscle regions, not individual
  muscles.
- **Undefined levels:** beginner/intermediate/expert assigned
  inconsistently across contributors with no documented criteria.
- **"Other" equipment:** Catch-all that inflates ambiguity - a known
  incomplete enumeration.
- **Entity resolution:** Multiple entries for effectively the same
  exercise (e.g. Barbell Squat, Olympic Squat, Weighted Squat). Not
  resolved in v1.
- **Category conflation:** "strength" vs "powerlifting" vs "olympic
  weightlifting" mix training modality with sport discipline.

---

## V1 Use Cases

1. **Exercise Understanding:** Given an exercise, what muscles does it
   work and how (prime mover vs synergist vs stabilizer)?
2. **Exercise Discovery:** Given constraints (target muscle, equipment,
   movement pattern, modality), find relevant exercises.
3. **Exercise Substitution:** Given an exercise and a constraint
   (equipment), find alternatives sharing the same movement pattern.

---

## Design Principles

### Vocabularies are for users, not for ontologists

Our controlled vocabularies (muscles, movement patterns) are interfaces
for end users - people browsing for exercises, filtering by muscle group,
or building workout programs. Anatomical or ontological purity is
secondary to usability and discoverability.

**What this means in practice:**
- Prefer colloquial terms over formal anatomical names where both are
  accurate (e.g. "Calves" not "Triceps Surae", "Lats" not
  "Latissimus Dorsi Region")
- Nested regions are acceptable when the nesting matches how users
  think, even if it introduces hierarchy depth that is inconsistent
  with other parts of the vocabulary
- A user browsing for calf exercises should find them under "Lower Leg"
  because that is where they would look - not alongside "Lower Leg" as
  a confusing peer
- When in doubt, ask: would a gym-goer understand this? If not, find a
  better term or structure

**What this does not mean:**
- Accuracy still matters - "Calves" under "Lower Leg" is both usable
  AND anatomically correct
- We do not invent colloquial terms that have no grounding in exercise
  science
- Formal names are preserved as `skos:altLabel` so they remain
  discoverable

---

## Core Design Decisions

### ADR-001: Equipment is a property, not an identity
**Decision:** Equipment is modeled as a property of Exercise, not as
part of the exercise's identity. A barbell Romanian deadlift and a
dumbbell Romanian deadlift are the same exercise with different
equipment values.

**Rationale:** The movement pattern and target muscles are what define
an exercise. Equipment is a constraint on how it's performed. Encoding
equipment in exercise identity inflates the dataset artificially and
breaks substitution logic.

**Implications:** Exercises with "Barbell", "Dumbbell", "Kettlebell"
etc. in their names may be candidates for entity resolution in v2.

---

### ADR-002: MuscleInvolvement as a reified relationship
**Decision:** Muscle involvement is modeled as a named node
(`feg:MuscleInvolvement`) connecting an exercise to a muscle with a
degree property, rather than as direct `primaryMuscle`/`secondaryMuscle`
properties.

**Rationale:** The binary primary/secondary distinction in the source
data is too coarse and misleading. A deadlift lists forearms as
"secondary" but they are really stabilizers - a user should not think
deadlifts are a forearm exercise. The reified relationship allows us to
capture PrimeMover, Synergist, and Stabilizer distinctions.

**Downstream benefit:** Maps naturally to a fact table in analytical
systems (Databricks, Snowflake). Supports both exercise-first and
muscle-first queries without structural changes.

---

### ADR-003: Skolemized (opaque) URIs for MuscleInvolvement instances
**Decision:** MuscleInvolvement instances use opaque URIs (e.g.
`:inv_a3f9b2`) rather than blank nodes or human-readable URIs (e.g.
`:Deadlift_Hamstrings`).

**Rationale:** Blank nodes are not addressable, don't survive
serialization reliably across systems, and make SPARQL queries more
verbose. Human-readable URIs encode assumptions (exercise names, muscle
names) that create maintenance problems if either changes. Opaque URIs
generated via UUID are stable, addressable, and free of semantic
assumptions.

---

### ADR-004: InvolvementDegree named individuals
**Decision:** Three named individuals for InvolvementDegree: PrimeMover,
Synergist, Stabilizer.

**Rationale:** Antagonist was considered but dropped - it describes a
muscle being lengthened while another contracts, not a useful training
fact for exercise lookup or substitution. Antagonist supersets are
better captured through MovementPattern relationships
(HorizontalPush/HorizontalPull are inherently antagonist patterns) than
through muscle tagging.

---

### ADR-005: Progression/regression deferred to v2
**Decision:** `feg:isProgressionOf` and `feg:isRegressionOf` are not
modeled in v1.

**Rationale:** Progression is multidimensional - difficulty, load
position, stability demand, and equipment all contribute independently.
A simple inverse property pair oversimplifies this and risks misleading
users. The design question of whether to model progression as a simple
inverse pair or with a dimension property is deferred to v2 when use
cases are better understood.

**Previously considered:** An inverse property pair with
`owl:inverseOf` was designed and subsequently dropped after stress
testing against the squat family revealed the multidimensionality
problem.

---

### ADR-006: MovementPattern hierarchy using SKOS
**Decision:** MovementPattern hierarchy encoded using SKOS
(`skos:broader`/`skos:narrower`) rather than OWL subclasses.

**Rationale:** OWL subclass reasoning is valuable when you need the
reasoner to infer class membership automatically. In this project,
movement patterns are asserted explicitly by the LLM enrichment
pipeline - inference is not needed. SKOS is simpler, more flexible, and
easier to extend without recompiling an ontology.

---

### ADR-007: Unilateral/bilateral as a data property, not a hierarchy level
**Decision:** `feg:isUnilateral` is a boolean data property on Exercise
rather than a MovementPattern sub-pattern.

**Rationale:** Unilateral vs bilateral cuts across all movement patterns
(squats, hinges, carries, presses) consistently. Encoding it as a
property avoids redundant sub-patterns (SingleLegSquat, SingleLegHinge,
etc.) and keeps the hierarchy focused on mechanical distinctions that
cannot be captured as properties.

**Absence convention:** When `feg:isUnilateral` is absent, bilateral
execution is assumed. The enrichment pipeline only needs to explicitly
flag unilateral exercises. Query authors should treat absence as false.

---

### ADR-008: MovementPattern hierarchy structure
**Decision:** The following hierarchy, encoded in SKOS:

```
MovementPattern
  ├── KneeDominant
  │     ├── Squat
  │     ├── SplitSquat
  │     └── Lunge
  ├── HipHinge
  ├── Push
  │     ├── HorizontalPush
  │     └── VerticalPush
  ├── Pull
  │     ├── HorizontalPull
  │     └── VerticalPull
  ├── Carry
  ├── Rotation
  ├── TrunkStability
  ├── Mobility
  ├── SoftTissue
  └── Locomotion
```

**Note:** ExplosiveHinge and ConventionalHinge were designed and
subsequently dropped (ADR-015). Core was renamed to TrunkStability
(ADR-023). Mobility and SoftTissue were added during enrichment
(ADR-028, ADR-022).

**Rationale:**
- KneeDominant sub-patterns (Squat, SplitSquat, Lunge) are mechanically
  distinct and matter for substitution logic. SplitSquat and Lunge are
  distinguished by whether the rear foot travels.
- Push and Pull parent concepts added to support PPL program analysis
  and handle intermediate angles (e.g. incline press) that are neither
  purely horizontal nor vertical.
- Carry, Rotation, TrunkStability, and Locomotion have no sub-patterns
  whose distinctions could not be better captured as properties.

**Note on Cossack Squat:** The cossack squat does not fit cleanly into
Squat, SplitSquat, or Lunge due to its lateral plane of motion.
Classified as Squat in v1. LateralSquat sub-pattern considered for v2.

---

### ADR-009: TrainingModality replaces category
**Decision:** Source data `category` field is replaced by
`feg:TrainingModality`. Sport discipline (powerlifting, olympic
weightlifting, strongman) is not modeled in v1.

**Rationale:** Source category conflates training modality (what
physiological adaptation is targeted) with sport discipline (what
competitive context the exercise belongs to). These are independent
facts. Sport discipline is deferred to v2.

**TrainingModality named individuals:** Strength, Hypertrophy, Cardio,
Mobility, Plyometrics. All defined as "principally focused on" their
respective adaptations to acknowledge that modalities overlap in
practice (e.g. strength and hypertrophy).

---

### ADR-010: mechanic and level data properties dropped
**Decision:** The source data `mechanic` (compound/isolation) and
`level` (beginner/intermediate/expert) properties are not modeled in v1.

**Rationale:**
- `mechanic`: compound/isolation is largely redundant with
  MovementPattern. A hip hinge is always compound; a bicep curl is
  always isolation. The distinction adds little beyond what movement
  pattern already captures.
- `level`: criteria for beginner/intermediate/expert were never defined
  in the source data and were assigned inconsistently across
  contributors. None of the three v1 use cases depend on this property.

---

### ADR-011: feg:legacySourceId naming
**Decision:** The provenance property linking exercises back to the
source dataset is named `feg:legacySourceId` rather than `feg:sourceId`.

**Rationale:** "Legacy" signals to downstream consumers that this
identifier belongs to the upstream dataset and should not be treated as
a primary key in this graph. It makes the provenance intent explicit.

---

### ADR-012: MovementPatternScheme as ConceptScheme name
**Decision:** The SKOS ConceptScheme for movement patterns is named
`feg:MovementPatternScheme` rather than `feg:MovementPattern`.

**Rationale:** `feg:MovementPattern` is already used as an OWL class.
Reusing the same URI for a ConceptScheme would create a naming
collision. The Scheme is a separate resource that organizes the
controlled vocabulary.

---

### ADR-013: Notebook tooling - Marimo over Jupyter
**Decision:** Project notebooks are written in Marimo rather than
Jupyter.

**Rationale:**
- Reactive execution model - cells update automatically when
  dependencies change, well-suited to iterative data exploration.
- Pure Python files - version control friendly, clean diffs in GitHub,
  no JSON blob noise.
- Built-in interactivity without extra widget libraries - useful for
  the human review interface in the enrichment pipeline.
- Renders as a web app - better portfolio presentation than a static
  notebook.

**Note:** Marimo's reactivity means cell execution order is determined
by data dependencies, not position. Deliberate dependency structuring
is required in the enrichment pipeline where order of operations
matters.

---

### ADR-014: Inverse object properties dropped from v1
**Decision:** No `owl:inverseOf` declarations in v1. The `feg:exercise`
back-reference property (MuscleInvolvement -> Exercise) was also dropped.

**Rationale:** Inverses add complexity without clear v1 use case
benefit. All three v1 use cases traverse from Exercise ->
MuscleInvolvement via `feg:hasInvolvement`, never the other direction.
SPARQL can query both directions by reversing the triple pattern.
Inverses can be added in v2 if a specific query pattern demands them.

---

### ADR-015: ExplosiveHinge dropped, Plyometrics handles explosive intent
**Decision:** `feg:ExplosiveHinge` and `feg:ConventionalHinge` are not
modeled. `feg:HipHinge` has no sub-patterns in v1. The explosive quality
of movements like kettlebell swings, cleans, and snatches is captured by
`feg:Plyometrics` as a TrainingModality rather than by a MovementPattern
sub-pattern.

**Rationale:** MovementPattern describes mechanics - how the body moves.
TrainingModality describes intent - what adaptation is being trained.
These are orthogonal. A kettlebell swing is a HipHinge mechanically and
Plyometrics by intent. Encoding explosiveness in MovementPattern conflates
mechanics with intent. Plyometrics as a TrainingModality captures the
explosive quality cleanly without requiring a separate sub-pattern, and
applies consistently across any movement pattern (a thruster can be
Plyometrics, a jump squat can be Plyometrics, etc.).

**Implication:** The open question about ExplosiveHinge as a top-level
vs sub-pattern is resolved by dropping it entirely.

---

### ADR-016: Muscle vocabulary built in-house, no external ontology import
**Decision:** The muscle vocabulary is built and maintained as part of
this project. No external anatomy ontology (FMA, Uberon) is imported.

**Rationale:** FMA is the authoritative human anatomy ontology but is
not useful for our purposes. It models anatomy for medical/surgical
contexts at excessive granularity (lateralized instances, muscle bodies,
tendons, fascicles). Its hierarchy is encoded as OWL restrictions on
blank nodes rather than clean subClassOf relationships, making traversal
impractical. Its maintenance has lapsed and licensing is unclear for
reuse. Uberon is actively maintained but oriented toward cross-species
integration which is out of scope.

**Alternative considered:** MIREOT from FMA - importing only the terms
we need with `skos:exactMatch` cross-references. Rejected because FMA's
opaque numeric IDs (`fma:fma297594`) add no human-readable value, and
the maintenance burden of keeping cross-references current against a
lapsed ontology is not justified.

**Implication:** Our muscle vocabulary is authoritative by virtue of
using standard anatomical terminology (Gray's Anatomy, Terminologia
Anatomica), not by linking to an external ontology.

---

### ADR-017: Muscle hierarchy as Region -> Muscle -> MuscleHead using SKOS
**Decision:** Muscles are organized in a three-level hierarchy:
MuscleRegion -> Muscle -> MuscleHead, encoded with `skos:broader` /
`skos:narrower`. The LLM enrichment pipeline classifies at the
MuscleHead level. Muscles with no meaningful head-level distinction
are leaf nodes at the Muscle level.

**Rationale:** Same reasoning as ADR-006 (MovementPattern hierarchy).
SKOS is simpler than OWL subclasses for controlled vocabularies that
do not require automated inference. The three-level hierarchy mirrors
how exercise science discusses muscles in practice and supports queries
at any level of granularity via SPARQL property paths (`skos:broader+`).

**Leaf node convention:** When a muscle has no meaningful head-level
distinction (e.g. Latissimus Dorsi, Soleus, Brachialis), it is modeled
as a `feg:Muscle` with no MuscleHead children. The LLM classifies at
the Muscle level for these cases.

---

### ADR-018: Muscle region names use colloquial exercise science terms
**Decision:** MuscleRegion labels use colloquial exercise science
terminology rather than formal anatomical region names. Examples:
"Lats" not "Posterior Thorax," "Traps" not "Posterior Cervical Region,"
"Quads" not "Anterior Compartment of Thigh."

**Rationale:** The source dataset uses colloquial terms
(quadriceps, shoulders, lats, traps). Our region labels are the
semantic upgrade of those source terms. Using colloquial names
preserves continuity with the source data and matches how coaches,
athletes, and exercise scientists actually communicate.

**Formal names preserved via skos:altLabel** where useful
(e.g. `skos:altLabel "Latissimus Dorsi"` on the Lats region).

---

### ADR-019: Trapezius belongs to Traps region; Middle Trapezius has skos:related Middle Back
**Decision:** The Trapezius muscle and all three of its heads (Upper,
Middle, Lower) belong to the Traps region via `skos:broader`.
Middle Trapezius additionally has `skos:related feg:MiddleBack` to
capture its functional association with rowing and scapular retraction
movements without polluting the primary hierarchy.

**Rationale:** Muscles with multiple `skos:broader` parents create
ambiguity in hierarchy traversal - a query for "all muscles in Middle
Back" would return Middle Trapezius even though it is primarily a trap
muscle. `skos:related` captures the functional association without
making it a structural parent. This is the intended use of `skos:related`
in SKOS - associative relationships that are meaningful but not
hierarchical.

**Implication:** Queries traversing `skos:broader+` from Middle Back
will not return Trapezius heads. Queries wanting functional Middle Back
muscles should union `skos:broader+` with `skos:related`.

---

### ADR-020: Muscles appearing in multiple functional regions use skos:related
**Decision:** Muscles that are functionally associated with multiple
regions are assigned one canonical `skos:broader` parent and use
`skos:related` for secondary associations. Canonical parent is the
region where the muscle is most commonly trained.

**Cases:**
- Gluteus Medius/Minimus: canonical parent Glutes,
  `skos:related feg:Abductors`
- Brachioradialis: canonical parent Forearms,
  `skos:related feg:Biceps`
- Middle Trapezius: canonical parent Traps,
  `skos:related feg:MiddleBack` (see ADR-019)

**Rationale:** Multiple `skos:broader` parents are technically valid
in SKOS but create ambiguity in hierarchy traversal queries. A single
canonical parent keeps the hierarchy clean and predictable.

---

### ADR-021: TrainingModality assigned only when a distinguishing characteristic
**Decision:** `feg:trainingModality` is assigned only when the modality
is a defining characteristic of the exercise, not as a general descriptor
of the physiological context in which it might be performed.

**Examples of when to assign:**
- Box Jump -> Plyometrics (explosive intent is the defining feature)
- Yoga Flow -> Mobility (flexibility adaptation is the defining feature)
- 400m Run -> Cardio (cardiovascular adaptation is the defining feature)

**Examples of when to omit:**
- Barbell Squat -> no modality (could be Strength or Hypertrophy
  depending on rep range, load, and intent - none of which are in
  our data)
- Dumbbell Curl -> no modality (same reasoning)

**Rationale:** Strength and Hypertrophy are the default context for
most resistance training exercises. Assigning them universally adds
no discriminating information and creates ambiguity the LLM will
resolve inconsistently across exercises. Omitting modality for
exercises where it is not distinctive keeps the field meaningful
where it does appear.

**Implication:** Most resistance training exercises will have no
TrainingModality. The field will be most populated for cardio,
plyometric, and mobility exercises.

**Open question:** Whether to revisit this in v2 when use cases
around program design (e.g. PPL splits, modality-based filtering)
become clearer.

---

### ADR-022: SoftTissue movement pattern added for foam rolling and myofascial release
**Decision:** Add `feg:SoftTissue` as a top-level movement pattern in
`movement_patterns.ttl` to cover foam rolling, myofascial release, and
similar soft tissue work.

**Rationale:** Discovered during initial enrichment run - the exercise
"Adductor" (foam roll adductor release) returned no movement pattern
because nothing in the vocabulary fit. The LLM correctly declined to
hallucinate a pattern, causing a validation failure. `SoftTissue` fills
this gap cleanly.

**Scope:** Foam rolling, massage tools, myofascial release techniques.
Does not cover static or dynamic stretching - that is covered by
`feg:Mobility` (ADR-028).

---

### ADR-023: Core movement pattern renamed to TrunkStability
**Decision:** Renamed `feg:Core` to `feg:TrunkStability` in
`movement_patterns.ttl`.

**Rationale:** `Core` is too generic - it reads as a catch-all for any
exercise involving trunk musculature, which includes almost every
compound movement. The definition (flexion, extension, isometric demand)
was sound but the label was misleading. `TrunkStability` is more precise
and clearly distinct from `Rotation` (rotational and anti-rotational
patterns).

**Scope:** Planks, crunches, sit-ups, dead bugs, hollow holds, leg
raises, ab rollouts, hyperextensions. Hanging leg raises included
despite hip flexor prime movers, as the exercise intent is trunk
stability training.

**Not in scope:** Rotation (separate pattern), Carry (core involved
but not the defining pattern), compound lifts where core is a
stabilizer rather than the movement pattern.

---

### ADR-024: Core added as a MuscleGroup under Abdominals
**Decision:** Added `feg:Core` as a `MuscleGroup` under `feg:Abdominals`
representing the anterior core as a functional unit.

**Rationale:** During initial enrichment run the LLM hallucinated
`CoreAbdominals` and `CoreRegion` on compound movements (overhead press,
kettlebell press) where core is incidental stabilization. `Core` as a
catch-all was initially rejected because it conflicted with the `Core`
movement pattern. After renaming that pattern to `TrunkStability`
(ADR-023), `Core` became available as a muscle term.

**Usage rule encoded in prompt:** Use `Core` as a stabilizer on compound
movements where core involvement is incidental. Use specific muscles
(RectusAbdominis, TransverseAbdominis, Obliques, etc.) for dedicated
core exercises where the core is the primary target.

**Semantic note:** `Core` as a MuscleGroup is intentionally coarser than
other entries in the vocabulary. It trades anatomical precision for
practical utility on the large class of compound exercises where
enumerating every abdominal stabilizer would add noise without value.

---

### ADR-025: Psoas added under LowerBack with skos:related Quadriceps
**Decision:** Added `feg:Psoas` as a `MuscleGroup` under `feg:LowerBack`
with `skos:related feg:Quadriceps`.

**Rationale:** Discovered during initial enrichment run - the exercise
"All_Fours_Quad_Stretch" returned `Psoas` which was not in the
vocabulary. The psoas is the primary hip flexor and genuinely relevant
for hip flexor stretches and hip hinge movements. Canonical parent is
`LowerBack` reflecting its lumbar origin; `skos:related Quadriceps`
captures its functional role as a hip flexor.

---

### ADR-026: Calves restructured as subregion under LowerLeg
**Decision:** Added `feg:LowerLeg` as a top-level `MuscleRegion`.
`feg:Calves` is now a `MuscleRegion` nested under `LowerLeg` via
`skos:broader`. `feg:TibialisAnterior` sits directly under `LowerLeg`
as a peer of `Calves`.

**Rationale:** The tibialis anterior needed a home. Creating a `LowerLeg`
region and placing `Calves` inside it as a named subregion is more
usable than either (a) putting tibialis under `Calves` (anatomically
wrong) or (b) creating a peer `LowerLeg` region alongside `Calves`
(confusing to lay users who correctly understand calves as part of the
lower leg). Design principle applied: vocabularies are for users, not
for ontologists.

---

### ADR-027: TibialisAnterior added under LowerLeg
**Decision:** Added `feg:TibialisAnterior` as a `MuscleGroup` under
`feg:LowerLeg`.

**Rationale:** Discovered during enrichment run - the exercise
`Anterior_Tibialis-SMR` returned `Tibialis` which was not in the
vocabulary. The tibialis anterior is the primary dorsiflexor and
genuinely relevant for lower leg exercises and stretches.

**Note:** `skos:altLabel "Tibialis"` added to catch the LLM's shorthand.

---

### ADR-028: Mobility added as a movement pattern
**Decision:** Added `feg:Mobility` as a top-level movement pattern in
`movement_patterns.ttl`.

**Rationale:** Discovered during enrichment run - stretching exercises
(`All_Fours_Quad_Stretch`, `Behind_Head_Chest_Stretch`) returned
`Mobility` as a movement pattern but it did not exist in the vocabulary,
causing validation failures. `SoftTissue` was added earlier for foam
rolling but is not appropriate for stretching. `Mobility` and
`SoftTissue` are now peers at the top level.

**Scope:** Static stretches, dynamic stretches, flexibility work, range
of motion exercises. Does not cover foam rolling or myofascial release
(SoftTissue).

---

### ADR-029: Semantic versioning added to all ontology files
**Decision:** All six ontology/vocabulary files carry `owl:versionInfo`
with independent semantic version numbers. Starting versions:

| File                      | Version | Rationale |
|---------------------------|---------|-----------|
| `muscles.ttl`             | 0.5.0   | 5 meaningful changes since initial creation |
| `movement_patterns.ttl`   | 0.4.0   | 4 meaningful changes since initial creation |
| `involvement_degrees.ttl` | 0.1.0   | New file, stable enumeration |
| `training_modalities.ttl` | 0.1.0   | New file, stable enumeration |
| `shapes.ttl`              | 0.1.0   | New file, relatively stable |
| `ontology.ttl`            | 0.1.0   | Core schema, relatively stable |

**Versioning approach:** Semantic versioning (MAJOR.MINOR.PATCH).
- MAJOR: breaking changes (removing concepts, renaming URIs)
- MINOR: additive changes (new concepts, new properties)
- PATCH: non-breaking corrections (fixing comments, labels)

**Independent versioning:** Each file is versioned independently.
Muscle vocabulary and movement pattern vocabulary evolve at different
rates and for different reasons - coupling their versions would obscure
what actually changed.

**Stamping:** `enrich.py` reads all six versions at startup and stamps
them into every enriched JSON as `vocabulary_versions`. `check_stale.py`
compares stamped versions against current files and reports exercises
that need rerunning after vocabulary changes.

**Implementation for flat vocabularies** (`involvement_degrees.ttl`,
`training_modalities.ttl`, `shapes.ttl`): A lightweight
`owl:Ontology` resource carries `owl:versionInfo`. No SKOS concept
scheme needed for flat enumerations.

---

### ADR-030: Iliopsoas added as MuscleHead under Psoas
**Decision:** Added `feg:Iliopsoas` as a `MuscleHead` under `feg:Psoas`
with `skos:altLabel "Psoas Major"`.

**Rationale:** Discovered during enrichment — the exercise
`Bent-Knee_Hip_Raise` returned `Iliopsoas` which was not in the
vocabulary. Iliopsoas is the anatomical compound of psoas major and
iliacus; in exercise science it is commonly used as the functional
unit name for hip flexor work. Modeling it as a MuscleHead under Psoas
allows the LLM to use either `Psoas` (group-level) or `Iliopsoas`
(head-level) and both resolve to valid vocabulary terms.

**Hierarchy:** LowerBack → Psoas → Iliopsoas.

**Note:** ADR-025 (Psoas as MuscleGroup) and ADR-024 (Core as
MuscleGroup) were both decided previously but never applied to
`muscles.ttl`. All three concepts are implemented together in this
change. Version bumped from 0.5.0 → 0.6.0 (MINOR: additive).

---

## Backlog

### Deferred from v1 by design

- **Sport/discipline classification** - powerlifting, olympic
  weightlifting, strongman as a separate class from TrainingModality.
- **Biomechanical properties** - peak contraction point, resistance
  curve.
- **Load position property** - would handle edge cases like good
  morning (back-loaded hinge) vs conventional deadlift (floor-loaded).
- **Progression/regression modeling** - deferred pending decision on
  whether to model as simple inverse pair or with a dimension property.
- **isVariantOf relationship** - captures variations without implying
  difficulty ordering (e.g. sumo vs conventional deadlift).
- **LateralSquat sub-pattern** - for cossack squat and similar lateral
  plane knee dominant movements.
- **Push/Pull angle property** - feg:loadAngle for incline variations.
- **Rotation sub-patterns** - anti-rotation vs rotation distinction.
- **Mobility vs SoftTissue boundary** - may need revisiting as more
  exercises are seen.

### Requires user session data (out of scope for static graph)

- Am I overtraining?
- Personalized substitution based on injury history
- Volume calculation policies (the dumbbell logic problem)
- Stimulus-to-fatigue ratio modeling
- 1RM and progressive overload modeling
- RIR/RPE feedback loops

### Entity resolution

- Multiple entries for effectively the same exercise (Barbell Squat,
  Olympic Squat, Weighted Squat). Not resolved in v1 - exercises are
  treated as distinct individuals even when semantically identical.
- Proposed v2 approach: movement pattern-based entity resolution,
  allowing exercise history merging.

### Pipeline and tooling

- **encode.py** - enriched JSON -> RDF Turtle (pipeline incomplete
  without this)
- **review.py** - Marimo UI for quarantine triage
- **eval framework** - gold standard dataset, rubric, eval.py
- **Crosswalk document** - map source dataset flat muscle terms to
  our hierarchy
- **SPARQL query library** - analytical queries demonstrating graph value
- **GOVERNANCE.md** - formal change management process document
- **README.md** - project overview with governance framing
- **pyproject.toml** - ruff config, dependencies

---

## Open Questions

- **Cossack squat classification:** Currently Squat in v1. Does lateral
  plane movement warrant a LateralSquat sub-pattern?
- **Push/Pull angle:** Is incline angle best captured as a property
  (feg:loadAngle) or does it need a sub-pattern?
- **TrainingModality in v2:** Whether to revisit modality assignment
  when use cases around program design (PPL splits, modality filtering)
  become clearer.
- **Namespace:** Placeholder `https://placeholder.url#` needs a real
  URI before any public release.
