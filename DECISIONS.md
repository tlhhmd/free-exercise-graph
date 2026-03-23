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

### ADR-031: Streamlit adopted for annotation tool; Marimo deprecated for this use case
**Decision:** The gold standard annotation tool (`evals/annotate.py`) is built with
Streamlit rather than Marimo. ADR-013 (Marimo over Jupyter) is superseded for the
annotation use case specifically; Marimo remains available for exploratory analysis.

**Rationale:** Marimo's reactive execution graph created persistent friction with
the annotation UI. Specifically: `mo.ui.array` nesting caused rendering failures,
multi-state update ordering produced blank screens, and the cell-dependency model
made dynamic row editing (add/delete muscle involvements) unstable. Streamlit's
linear top-to-bottom execution model and `st.data_editor` component provide the
stability required for high-integrity manual data entry.

**Implication:** `evals/annotate_test.py` (the Marimo prototype) is retained for
reference but is not the active tool. The active annotator is `evals/annotate.py`
(Streamlit). `review.py` (quarantine triage UI) may use either framework — evaluate
at build time.

---

### ADR-032: seed.json → gold.json annotation pipeline
**Decision:** The eval annotation workflow uses two separate files:
- `evals/seed.json` — immutable reference: LLM-generated enrichments for the 30
  sampled exercises. Never written by the annotator.
- `evals/gold.json` — evolving ground truth: human-verified and corrected records.
  Written on each Save. Initialized from seed on first run if absent.

**Rationale:** Treating the seed as immutable preserves the original LLM output as
a reference for side-by-side comparison. The annotator always shows both columns
(Seed Reference | Gold Standard), which makes errors of omission and commission
immediately visible. Separating the files prevents accidental overwrites and allows
diffing seed vs gold to measure correction rate.

**Side-by-side layout:** Left column shows the seed record read-only. Right column
is the editable gold form. A "Reset to Seed" button restores the gold record from
seed for the current exercise.

---

### ADR-033: Annotation UI vocabulary derived exclusively from ontology TTL files
**Decision:** All controlled vocabulary shown in the annotation UI (muscles,
movement patterns, training modalities, involvement degrees) is parsed at runtime
from `ontology/*.ttl` via rdflib. No strings for these terms are hardcoded in
`annotate.py`.

**Rationale:** Hardcoding vocabulary in the annotator creates "Label Drift" — the
UI silently falls out of sync when TTL files are updated, allowing annotators to
select terms that no longer exist or miss newly added terms. Loading from TTL at
startup ensures the annotator always reflects the current vocabulary state.

**Implementation:** `get_ontology_data()` (decorated with `@st.cache_data`) parses
all `*.ttl` files in `ontology/` and extracts concept local names from the four
SKOS concept schemes: `MuscleScheme`, `MovementPatternScheme`,
`TrainingModalityScheme`, `InvolvementDegreeScheme`.

---

### ADR-034: Double Counting detection in annotation UI
**Decision:** The annotation UI validates muscle involvement selections in real time
and flags any case where both a muscle and one of its SKOS ancestors are selected
simultaneously (e.g. selecting both `Hamstrings` and `Posterior` as prime movers).

**Rationale:** Double counting at the parent/child level would inflate involvement
coverage in the gold standard and produce misleading F1-score calculations during
eval. A parent concept subsumes its children — selecting both means the same muscle
mass is counted twice. The flag is a soft warning (not a hard block) to support
edge cases where explicit redundancy is intentional.

**Implementation:** `check_double_counting()` walks `HIERARCHY` (a dict of
`{muscle: [parents]}` built from `skos:broader` edges) and flags any selected
muscle whose parent is also in the selected set.

---

### ADR-035: Hierarchical muscle explorer for annotation discovery
**Decision:** The annotation tool includes a modal "Muscle Hierarchy Explorer" that
renders the local SKOS neighbourhood of any muscle node (its parents and children)
as a D3.js force graph, with navigation buttons to zoom in to children or zoom out
to parents.

**Rationale:** The muscle vocabulary has 60+ concepts across three hierarchy levels.
An annotator selecting muscles for a novel exercise cannot hold the full tree in
working memory. Without a discovery mechanism they default to vague group-level
terms (e.g. `Shoulders`) instead of precise head-level terms (e.g. `AnteriorDeltoid`)
that make the gold standard more valuable for fine-grained eval. The explorer
resolves this by letting the annotator navigate the graph and copy the selected term
back to the annotation form.

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

### ADR-036: Equipment vocabulary as named individuals in equipment.ttl
**Decision:** Equipment terms from the source dataset are encoded as
`owl:NamedIndividual` instances of `feg:Equipment` in a new file
`ontology/equipment.ttl`. Version starts at 0.1.0.

**12 terms, source string → URI mapping:**

| Source string | URI |
|---|---|
| `bands` | `feg:Bands` |
| `barbell` | `feg:Barbell` |
| `body only` | `feg:Bodyweight` |
| `cable` | `feg:Cable` |
| `dumbbell` | `feg:Dumbbell` |
| `e-z curl bar` | `feg:EZCurlBar` |
| `exercise ball` | `feg:ExerciseBall` |
| `foam roll` | `feg:FoamRoller` |
| `kettlebells` | `feg:Kettlebell` |
| `machine` | `feg:Machine` |
| `medicine ball` | `feg:MedicineBall` |
| `other` | `feg:Other` |

**Structural choices:**
- `feg:Bodyweight` preferred over `feg:BodyOnly` — user-facing vocabulary
  principle (ADR-018); "body only" is the source's term, "bodyweight" is
  what gym-goers say.
- `feg:Kettlebell` singular — consistent with other singular noun URIs in
  the vocabulary; source dataset uses "kettlebells" (plural).
- `feg:FoamRoller` over `feg:FoamRoll` — the noun is the tool, not the action.
- Source string aliases preserved as `skos:altLabel` for discoverability.
- Same `owl:NamedIndividual` pattern as `involvement_degrees.ttl` and
  `training_modalities.ttl`.

**Rationale:** Equipment is a flat enumeration with no hierarchy needed in v1.
The `owl:NamedIndividual` pattern is consistent with other flat vocabularies
in this project. `feg:Other` is retained as a first-class term (not dropped)
to faithfully represent the known gap in the source dataset.

---

### ADR-037: Structural refactor — data engineering lifecycle layout
**Decision:** Reorganise the project around a dataset-centric layout with
a `source/` directory as the primary pattern for per-dataset work. The
LLM enrichment layer (enrich.py, enriched JSON) is decoupled and set aside
for a future redesign. The raw-to-RDF pipeline is rebuilt on morph-KGC with
declarative YARRRML mappings.

**New layout (see ADR-041 for subsequent rename to `sources/`):**
```
source/
  raw/exercises.json            ← read-only source (moved from dist/)
  mappings/
    exercises.yarrrml.yaml      ← YARRRML mapping rules
    muscle_crosswalk.csv        ← source string → feg:Muscle URI
    equipment_crosswalk.csv     ← source string → feg:Equipment URI
    morphkgc.ini                ← morph-KGC execution config
  catalog/
    catalog.ttl                 ← DCAT + PROV-O provenance stubs
pipeline/
  map.py                        ← runner: morph-KGC → ingested.ttl
```

**What was removed:**
- `pipeline/encode.py`, `pipeline/merge.py` — superseded by morph-KGC
- `data/rdf/` — per-exercise TTL files replaced by single graph output
- `pipeline/enrich.py`, `prompt.py`, `check_stale.py`, `data/enriched/`,
  `data/quarantine/` — LLM enrichment layer decoupled for redesign as a
  distinct pipeline stage (subsequently completed — see ADR-045 through ADR-048)

**Supersedes:** ADR-037 (encode.py design) and ADR-038 (merge.py), both now
obsolete.

**Rationale:** The incremental encode.py + merge.py pattern served the LLM
enrichment workflow but created accidental coupling between the enrichment
step and the RDF serialisation step. Decoupling them as separate layers —
raw→RDF (morph-KGC) and enriched→RDF (LLM enrichment layer) — is cleaner
and scales better across additional datasets.

---

### ADR-038: YARRRML + morph-KGC for raw→RDF transformation
**Decision:** `source/raw/exercises.json` is mapped to RDF using a YARRRML
mapping file (`source/mappings/exercises.yarrrml.yaml`) executed by
morph-KGC v2.6.x via `pipeline/map.py`. This replaces `encode.py` and
`merge.py`.

**Mapping coverage from source schema:**

| Source field | Mapping |
|---|---|
| `id` | `feg:legacySourceId` (xsd:string) + URI template `feg:{id}` |
| `name` | `rdfs:label` |
| `equipment` | `feg:equipment` → crosswalk join → `feg:{Equipment}` IRI |
| `primaryMuscles[]` | `feg:hasInvolvement` → MuscleInvolvement (degree: PrimeMover) |
| `secondaryMuscles[]` | `feg:hasInvolvement` → MuscleInvolvement (degree: Synergist) |
| `category` | Deferred — source conflates modality with sport discipline (ADR-013) |
| `force`, `level`, `mechanic` | Dropped (ADR-010) |
| `instructions`, `images` | Dropped — not modelled in ontology.ttl v1 |

**MuscleInvolvement URI scheme:** `feg:inv_{id}_{source_muscle_string}_{degree}`.
Template-based, deterministic, human-readable. Source strings with spaces
("lower back", "middle back") are percent-encoded by morph-KGC
(`feg:inv_X_lower%20back_PrimeMover`). Supersedes ADR-003 (SHA256 skolem URIs).

**Muscle and equipment crosswalk:** Source strings (e.g. "lower back",
"body only", "foam roll") map to feg: vocabulary URIs via two CSV lookup
tables (`muscle_crosswalk.csv`, `equipment_crosswalk.csv`). All 17 source
muscle terms and 12 equipment terms have explicit mappings. morph-KGC
implements the join via referencing object maps.

**morph-KGC configuration note:** When one YARRRML file contains triples maps
for multiple data sources (JSON + CSV crosswalks), all triples maps must be in
the same file for cross-TM join references to resolve at parse time. The .ini
uses a single `[AllMappings]` section with no `file_path` override, so each
triples map uses its YARRRML `access` value (file path literal) as the data
source — resolved relative to the project root (cwd of map.py).

**Rationale:** YARRRML is declarative, auditable, and tool-agnostic within the
RML ecosystem. morph-KGC v2.6.x supports YARRRML natively. A single-command
runner (`python3 pipeline/map.py`) replaces the two-step encode+merge workflow.
The pattern scales to additional datasets by adding new `source/` subdirectories
with their own YARRRML and crosswalk files.

---

### ADR-039: Minimum viable provenance — DCAT + PROV-O
**Decision:** A minimal `source/catalog/catalog.ttl` file records the dataset
lineage using DCAT and PROV-O vocabularies. It is a stub — enough to demonstrate
the governance pattern, not a fully populated provenance record.

**Contents:**
- `dcat:Catalog` → `dcat:Dataset` for the exercise graph
- `dcat:Distribution` pointing to `dist/graph.ttl`
- `prov:Activity` stub linking the morph-KGC mapping to the distribution
- `prov:Entity` for the source JSON, `prov:SoftwareAgent` for morph-KGC

**What is deferred:** Actual run timestamps, input/output checksums,
vocabulary version stamps. These can be added programmatically by `map.py`
in a future iteration.

**Rationale:** DCAT is the W3C standard for data catalog metadata. PROV-O
provides the lineage vocabulary. Even a stub demonstrates the governance
intent and establishes extension points for future automation.

---

### ADR-040: URI naming conventions — `ex_` prefix and normalized muscle strings
**Decision:** Exercise and MuscleInvolvement URIs follow these rules:

1. **Exercise URIs:** `feg:ex_$(id)` — the `ex_` prefix ensures URIs are valid
   NCNames (no leading numeral, no QName issues), and is a stable, readable
   convention across all exercise nodes. `feg:legacySourceId` still captures
   the raw `$(id)` for provenance.

2. **MuscleInvolvement URIs:** `feg:inv_ex_$(id)_$(normalizedMuscle)_$(degree)` —
   uses the crosswalk `feg_local_name` (e.g., `LowerBack`, `MiddleBack`) rather
   than the raw source string, eliminating percent-encoded spaces.

3. **Normalization step:** `pipeline/map.py` pre-processes `exercises.json` before
   morph-KGC runs, replacing `primaryMuscles` and `secondaryMuscles` array values
   with their `feg_local_name` equivalents from `muscle_crosswalk.csv`. The
   normalized exercises are written to `exercises_normalized.json` (gitignored)
   in the same `raw/` directory, and the YARRRML mapping references this file.

4. **Hyphens in exercise IDs** (`Bent-Knee_Hip_Raise`): hyphens are valid IRI
   characters (RFC 3987). They prevent use as Turtle QNames, but serializers
   fall back to `<full-IRI>` notation — no semantic harm. Not addressed in v1.

**Rationale:** Percent-encoded spaces in URIs are technically valid IRIs but
violate standard data element naming rules and reduce readability in SPARQL
queries and serialised Turtle. The `ex_` prefix resolves the numeral-start
issue without touching source `id` values. The normalization step is a minimal
preprocessing stage that keeps the YARRRML mapping declarative while producing
clean output.

**Supersedes:** The URI scheme in ADR-038 (which accepted `lower%20back` in
involvement URIs as a known limitation).

---

### ADR-041: Source layout renamed to `sources/free-exercise-db/`
**Decision:** The `source/` directory is renamed to `sources/free-exercise-db/`.
The pipeline output moves from `dist/graph.ttl` to
`sources/free-exercise-db/ingested.ttl`.

**Layout:**
```
sources/
  free-exercise-db/
    raw/
      exercises.json              ← read-only source (fetched by fetch.py)
      exercises_normalized.json   ← generated by map.py (gitignored)
    mappings/
      exercises.yarrrml.yaml
      muscle_crosswalk.csv
      equipment_crosswalk.csv
      morphkgc.ini
    catalog/
      catalog.ttl                 ← scoped to this source only
    ingested.ttl                  ← morph-KGC output (gitignored)
```

**Rationale:** `sources/` (plural) signals that the project is designed for
multiple data sources. Placing `ingested.ttl` inside the source folder rather
than a top-level `dist/` makes the lineage self-evident: each source folder
contains its raw data, mapping rules, provenance metadata, and ingestion output
as a cohesive unit.

---

### ADR-042: Source-specific scripts live inside their source folder
**Decision:** `fetch.py` and `map.py` move from `pipeline/` into
`sources/free-exercise-db/`. The `pipeline/` directory is reserved for
tools that operate across sources or at a higher orchestration level
(e.g., the LLM enrichment layer when redesigned).

**Resulting layout (at time of this ADR — subsequently extended, see ADR-043 and ADR-048):**
```
sources/free-exercise-db/
  fetch.py          ← downloads exercises.json from upstream
  preprocess.py     ← normalises muscle strings via crosswalk CSVs
  ingest.py         ← morph-KGC + enrichment layer + repair queries → ingested.ttl
  validate.py       ← SHACL validation gate
  enrich.py         ← LLM enrichment pipeline (redesigned — see ADR-045)
  queries/          ← SPARQL UPDATE repair queries (see ADR-048)
  raw/
  mappings/
  catalog/
pipeline/
  prompt_builder.py ← use-case-agnostic prompt assembly utilities (see ADR-045)
```

**Rationale:** `fetch.py` is trivially source-specific — it hardcodes the
upstream URL for yuhonas/free-exercise-db. `preprocess.py` and `ingest.py`
are also source-specific: the muscle string normalisation step is bespoke to
how free-exercise-db encodes muscle names; a generic mapper would not need it.
Co-locating these scripts with the source data they operate on makes each
`sources/` subdirectory a self-contained, independently runnable unit. The
`pipeline/` directory holds tools that are use-case-agnostic and reusable
across sources.

**Run commands:**
```bash
python3 sources/free-exercise-db/fetch.py
python3 sources/free-exercise-db/preprocess.py
python3 sources/free-exercise-db/ingest.py
python3 sources/free-exercise-db/validate.py
```

---

### ADR-043: Separate preprocessing and ingestion into distinct scripts
**Decision:** `map.py` is split into two scripts and `map.py` is removed:

- `preprocess.py` — reads crosswalk CSVs and normalises the raw JSON into
  `exercises_normalized.json`. No RDF logic.
- `ingest.py` — runs morph-KGC on the normalised JSON, merges vocabulary
  files, applies the LLM enrichment layer, and runs repair queries. Serialises
  to `ingested.ttl`.

**Rationale:** The preprocessing step (crosswalk lookup, string normalisation)
and the ingestion step (YARRRML mapping, RDF serialisation) are distinct
concerns. Keeping them in one script conflates data preparation with pipeline
execution. Separating them makes each script independently runnable,
independently testable, and easier to reason about.

**Business logic stays in CSVs:** `preprocess.py` reads the crosswalk CSVs
generically — no mappings are hardcoded in Python. The CSVs remain the
authoritative source of the source→vocabulary translation decisions.

**Note:** `ingest.py` was subsequently extended to integrate the LLM enrichment
layer and ontology-driven repair queries as additional pipeline stages (see
ADR-045 through ADR-048). It is the central integration point of the pipeline.

---

### ADR-044: SHACL validation step — validate.py and shapes.ttl relaxation
**Decision:** Add `validate.py` to `sources/free-exercise-db/` as a fourth
pipeline stage. Relax the `feg:movementPattern sh:minCount` constraint in
`shapes.ttl` from `1` to `0`. Bump `shapes.ttl` version `0.1.0` → `0.1.1`.

**movementPattern constraint relaxed:** Movement patterns are not present in the
raw source data — they are assigned during LLM enrichment. `sh:minCount 0` allows
raw ingestion to pass validation. The constraint will be tightened back to
`sh:minCount 1` (with Mobility/SoftTissue exemptions) once movement pattern
coverage criteria are established (tracked in TODO).

**9 duplicate-muscle exercises (source data quality):** The following exercises
have the same muscle listed in both `primaryMuscles` and `secondaryMuscles` in
the upstream source:

- Kneeling Hip Flexor, Clean and Press, Hurdle Hops, All Fours Quad Stretch,
  Bent-Arm Barbell Pullover, Barbell Step Ups, Upper Back Stretch,
  Snatch Deadlift, Split Snatch

These are upstream data quality issues surfaced by SHACL. Not fixed at the source
(read-only). Handled post-ingestion by the cross-degree dedup repair pass in `ingest.py`
(see ADR-048), which removes the lower-priority involvement when the same muscle
appears at multiple degrees within a single exercise.

**validate.py behaviour:** Streams each violation as subject URI followed by the
violation message. Exits non-zero if any violations are found, making it usable as
a pipeline gate. Vocabulary files are merged into `ingested.ttl` — no separate
ontology graph is needed for SHACL class resolution.

---

### ADR-045: SHACL shapes as single source of truth for enrichment prompt rules
**Decision:** SHACL shapes are the authoritative source for enrichment prompt rules.
`sh:message` carries validation-failure text (unchanged). `rdfs:comment` on property
shapes carries instructional content for the LLM. The prompt builder reads both from
`shapes.ttl` at import time alongside the vocabulary TTL files. Two rules previously
maintained only as prompt prose are promoted to SHACL constraints.

**Changes to `shapes.ttl` (0.1.1 → 0.2.0):**
- `rdfs:comment` on `movementPattern` property shape: specificity preference (child > parent)
- `rdfs:comment` on `isUnilateral` property shape: omission semantics (omit for bilateral)
- `rdfs:comment` on `trainingModality` property shape: omission rule (defining characteristic only)
- `rdfs:comment` on `muscle` property shape in `MuscleInvolvementShape`: specificity preference (MuscleHead > MuscleGroup > MuscleRegion)
- New SPARQL constraint on `ExerciseShape`: ancestor double-counting — an exercise may not list both a muscle and one of its `skos:broader` ancestors
- New SPARQL constraint on `MuscleInvolvementShape`: `Core` must always be degree `Stabilizer`

**Rationale:** The previous `prompt.py` maintained two parallel sources of truth —
rules in `shapes.ttl` (for validation) and rules in prompt prose (for LLM guidance).
These diverge silently as the vocabulary evolves. Co-locating rules in `shapes.ttl`
means a vocabulary change that warrants a new validation constraint automatically
updates the prompt on next import. `rdfs:comment` is the natural carrier for
instructional content; `sh:message` is the natural carrier for violation messages.
The `Core` and ancestor double-counting rules gain validation teeth, not just
documentation.

**Pattern for the new `prompt.py`:** Extract instructional content by reading:
- `rdfs:comment` on property shapes for field-level rules
- `sh:message` on SPARQL constraints for cross-field rules
- `rdfs:comment` / `skos:scopeNote` on vocabulary concepts (e.g. movement pattern
  `rdfs:comment`, `Core` `skos:scopeNote`)

**Why `rdfs:comment` over `sh:description`:** `sh:description` is semantically
equivalent but less consistent with the rest of the ontology. `rdfs:comment` is
used throughout all vocabulary files — using it on shape blank nodes keeps the
documentation pattern uniform.

---

### ADR-046: Group-level scopeNotes for muscles not distinguished in exercise programming
**Decision:** Added `skos:scopeNote` to five muscle groups flagging that group-level
is the appropriate term — heads exist for anatomical completeness but are not
meaningfully distinguished in exercise science or programming:

- `RotatorCuff` — functional unit for glenohumeral stabilization
- `ErectorSpinae` — heads run in parallel, not trained independently
- `Gastrocnemius` — medial/lateral heads rarely distinguished in training
- `WristFlexors` — individual heads not distinguished in programming
- `WristExtensors` — individual heads not distinguished in programming

Bumped `muscles.ttl` 0.6.0 → 0.7.0 (MINOR: additive).

**Rationale:** Discovered during enrichment batch review that the LLM consistently
used group-level terms for these muscles, which we initially flagged as specificity
violations. On inspection, group-level is the correct exercise science usage for
all five. The prompt rule "prefer head over group" is correct in general but needed
explicit exceptions for muscles where the group IS the functional unit. The
`skos:scopeNote` pattern (established for `Core` in ADR-024) is the right carrier —
it surfaces in the rendered prompt via `include_scope_notes=True` and documents the
design intent in the vocabulary itself.

**Not added:** `BicepsBrachii`, `PectoralisMajor`, `Trapezius` — head-level
distinction is genuinely meaningful for these (hammer vs supinated curl, incline vs
flat press, upper/mid/lower trap work).

---

### ADR-047: feg:useGroupLevel boolean property for muscle group granularity
**Decision:** Add `feg:useGroupLevel` as an `owl:DatatypeProperty` (range `xsd:boolean`)
on `feg:MuscleGroup`. When asserted as `true` on a `MuscleGroup`, it signals that the
group is the appropriate enrichment term — the individual heads are not meaningfully
distinguished in exercise programming. Absence means heads should be enumerated.

**Groups annotated `feg:useGroupLevel true`:**
RotatorCuff, ErectorSpinae, Gastrocnemius, WristFlexors, WristExtensors,
Obliques, Scalenes, Rhomboids.

**Replaces** the prose `skos:scopeNote` approach used on the first five groups
(ADR-046). The Core `skos:scopeNote` is retained — it serves a different purpose
(explaining a convenience term, not signalling granularity preference).

**Rationale:** The scopeNote approach encoded the same rule five times as
hand-crafted prose. The prompt builder passed the text through verbatim — no
consistency, no machine-readability. A boolean property lets the prompt builder
generate a single, consistent instruction block from a SPARQL query. Follows the
`feg:isUnilateral` precedent: presence = signal, absence = default. Named individuals
(e.g. `feg:UseGroupLevel`) were considered and rejected — YAGNI; a boolean is
sufficient since there is no anticipated third state. A `feg:MuscleShape` in
`shapes.ttl` validates correct usage.

**Additional annotation:** `skos:editorialNote` added to `feg:useGroupLevel` in
`ontology.ttl` to surface the pipeline semantics: groups with this flag are listed
explicitly in the enrichment prompt as exceptions to the head-preference rule.

**Version bumps:** `ontology.ttl` 0.1.0 → 0.2.1 (additive property + editorial note),
`muscles.ttl` 0.7.0 → 0.8.0, `shapes.ttl` 0.2.1 → 0.3.0.

**Post-hoc correction:** The `owl:DatatypeProperty` domain was initially declared on
`feg:Muscle` (the abstract superclass) rather than `feg:MuscleGroup`. Corrected to
`feg:MuscleGroup` — `useGroupLevel` only makes sense on groups, not on regions or heads.
The ontology version was already at 0.2.1 when the correction was made; no additional
bump was required.

---

### ADR-048: Repair queries integrated into ingest.py
**Decision:** Post-ingest graph repair is implemented as SPARQL UPDATE queries stored
in `sources/free-exercise-db/queries/` and executed as the final stage of `ingest.py`.
There is no standalone `repair.py`. The repair step runs after morph-KGC mapping and
LLM enrichment have been applied, before `ingested.ttl` is serialised.

**Pipeline:**
```
preprocess.py → ingest.py (morph-KGC + enrichment + repair queries) → validate.py
```

**Repair queries (executed in numeric prefix order):**

1. **repair_01_use_group_level.rq** — useGroupLevel collapse: replaces any
   `MuscleHead` with its parent `MuscleGroup` when the group carries
   `feg:useGroupLevel true`. Motivated by the LLM consistently using
   `RhomboidMajor`/`RhomboidMinor` as prime movers on row exercises despite the
   prompt instruction.

2. **repair_02_dedup_involvements.rq** — same-degree dedup: after the
   useGroupLevel collapse, two involvements from the same exercise may point to
   the same muscle with the same degree. Removes the duplicate, keeping the
   lower URI for deterministic output.

3. **Cross-degree dedup** — removes the lower-priority involvement when the same muscle
   appears at multiple degrees within a single exercise (PrimeMover > Synergist >
   Stabilizer). Handles the upstream exercises where a muscle appears in both
   `primaryMuscles` and `secondaryMuscles` (documented in ADR-044).

4. **Muscle region consolidation** — when all direct children of a `feg:MuscleRegion`
   appear on the same exercise at the same degree, replaces them with a single
   involvement for the parent region. See ADR-055.

**Numeric prefixes** enforce execution order. The useGroupLevel collapse (01) must
run before same-degree dedup (02) because the collapse may create new duplicates.

**What repair queries do NOT do:**
- Parse SHACL validation reports — repairs are ontology-driven, not report-driven.
  `feg:useGroupLevel` is the authoritative signal; no coupling to SHACL message strings.
- Fix anything not derivable from vocabulary semantics alone.

**Why not SHACL rules (`sh:SPARQLRule`)?** SHACL Advanced Features rules are
constructive only — they can add triples but cannot DELETE. A true repair
(replace head URI with group URI) requires DELETE + INSERT, which requires SPARQL UPDATE.

**Rationale:** The LLM enrichment step produces semantically reasonable but
occasionally vocabulary-inconsistent output. A post-ingest repair layer is cleaner
than patching the prompt for every edge case, and more honest than silently accepting
violations.

---

### ADR-051: movementPattern sh:minCount tightened to 1; validate.py filters to enriched exercises
**Decision:** Tighten `feg:movementPattern sh:minCount` from `0` to `1` in `shapes.ttl`.
Update `validate.py` to filter to enriched exercises (those with at least one
`feg:movementPattern`) before running SHACL validation. Bump `shapes.ttl` `0.3.0 → 0.3.1`
(PATCH: constraint correction).

**validate.py behaviour:** Removes unenriched exercises and their MuscleInvolvement nodes
from the data graph before handing it to pyshacl. Reports `N/873 enriched exercises`
at the start of each run. Raw exercises are not checked — their missing movement patterns
are expected and not meaningful as violations.

**Rationale:** `minCount 0` was a temporary relaxation added in ADR-044 because the
enrichment layer had not yet been integrated into `ingest.py`. Now that it is (ADR-048),
the relaxation is no longer needed. Tightening to `1` makes the constraint honest: any
enriched exercise that emerges from the pipeline without a movement pattern is a genuine
error. The validate.py filter keeps the validator usable during incremental enrichment —
reporting 843 constant violations for raw exercises would drown out real signal.

---

### ADR-050: feg:Power training modality added
**Decision:** Add `feg:Power` as a named individual of `feg:TrainingModality` in
`training_modalities.ttl`. Bump `0.1.0 → 0.2.0` (MINOR: additive).

**Definition:** Training principally focused on developing rate of force development
under load. The defining exercises are Olympic lifts and their derivatives: clean,
snatch, jerk, and their hang, power, and split variants. Distinct from Plyometrics:
explosive force production under load, no stretch-shortening cycle.

**Rationale:** Olympic lifts were being assigned `feg:Plyometrics` — the only
explosive modality available — despite not relying on the stretch-shortening cycle.
This misclassification was identified during evaluation (eval report, March 2026).
The Power/Plyometrics distinction is meaningful for program design: Power exercises
require technical coaching, peak in a specific load range, and are sequenced
differently than plyometric work in a training block. The boundary is encoded in the
`rdfs:comment` as a direct rule for the enrichment pipeline: explosive force under
load (Power) vs. stretch-shortening cycle (Plyometrics).

**Exercises affected:** Hang Clean, Power Snatch, Clean and Press, and other Olympic
lift variants previously mis-assigned to Plyometrics.

---

### ADR-049: rdfs:label added to all movement pattern concepts
**Decision:** Add `rdfs:label` to every concept in `movement_patterns.ttl`, mirroring
the value of the existing `skos:prefLabel`. Bump `movement_patterns.ttl` `0.4.0 → 0.4.1`
(PATCH: non-breaking addition).

**Rationale:** The rest of the vocabulary (`muscles.ttl`, `training_modalities.ttl`,
`involvement_degrees.ttl`) uses `rdfs:label` as the primary human-readable label.
Movement patterns were the only file that used only `skos:prefLabel`, requiring
SPARQL queries to branch on the property depending on what type of resource they
were labelling. Adding `rdfs:label` makes `rdfs:label` the uniform label predicate
across the entire graph — queries can use `?x rdfs:label ?label` without needing to
know whether `?x` is a muscle, pattern, or degree. `skos:prefLabel` is retained for
SKOS-aware consumers.

---

### ADR-054: Anti-movement sub-patterns under TrunkStability; SpinalStability joint action
**Decision:** Add three sub-patterns under `feg:TrunkStability` in `movement_patterns.ttl`:
`feg:AntiExtension`, `feg:AntiRotation`, `feg:AntiLateralFlexion`. Add `feg:SpinalStability`
as a joint action in `joint_actions.ttl`. Update `TrunkStability` comment to describe it
as a parent concept. Bump `movement_patterns.ttl` `0.4.1 → 0.5.0` (MINOR: additive).

**Two-layer model for trunk stability exercises:**

| Exercise | Movement Pattern | Joint Action |
|---|---|---|
| Plank | AntiExtension | SpinalStability |
| Ab Wheel Rollout | AntiExtension | SpinalStability |
| Dead Bug | AntiExtension | SpinalStability |
| Pallof Press | AntiRotation | SpinalStability |
| Single-Arm Carry | AntiRotation | SpinalStability |
| Side Plank | AntiLateralFlexion | SpinalStability |
| Suitcase Carry | AntiLateralFlexion | SpinalStability |
| Russian Twist | Rotation | SpinalRotation |

The joint action (`SpinalStability`) captures the mechanical reality: the spine is not
moving, it is resisting load isometrically. The movement pattern captures what direction
it is resisting — which is the program design signal. The two dimensions are orthogonal
and complementary: you need both to fully describe the exercise.

**Why SpinalStability is a valid joint action despite being an absence of movement:**
Joint actions are mechanical descriptors of what the body is doing under load. Resisting
movement under load is a genuine mechanical demand — the muscles are contracting, the
joint is loaded, and the exercise produces a specific adaptation. "The spine does not move"
is as mechanically meaningful as "the spine flexes." Planks and rollouts are programmed
for their isometric anti-extension demand, not as a residual category. Encoding this as a
joint action makes that demand queryable.

**TrunkStability as parent only:** `TrunkStability` remains in the vocabulary as the
parent grouping concept, consistent with the existing hierarchy pattern (Push →
HorizontalPush/VerticalPush). The prompt specificity rule ("prefer child over parent")
applies: exercises should always be assigned one of the three sub-patterns where applicable.

**Rotation vs. AntiRotation:** `feg:Rotation` (existing) covers dynamic rotational
movements (Russian Twist, woodchop, cable rotation) where the spine actively rotates.
`feg:AntiRotation` covers exercises where the spine resists rotation (Pallof press,
single-arm work). These are distinct training stimuli and are now cleanly separated.

---

### ADR-055: Post-repair consolidation of muscle head involvements into parent region
**Decision:** Add a muscle region consolidation repair pass to `ingest.py` that
consolidates muscle head involvements into their parent `MuscleRegion` when all direct
children of that region appear on the same exercise at the same involvement degree.

**Problem:** LLM enrichment assigns individual muscle heads (e.g. all four quadriceps
heads, all three hamstring heads) as separate PrimeMover involvements. This is
anatomically precise but creates redundant data: in quad-dominant exercises the four
heads always fire as a unit, so listing them individually inflates prime mover counts
without adding useful programming information. The same pattern appears for the three
adductors on adduction exercises.

**Scope — MuscleRegion only:** The consolidation is scoped to `feg:MuscleRegion`
parents. This captures Quadriceps → {RectusFemoris, VastusLateralis, VastusMedialis,
VastusIntermedius} and Hamstrings → {BicepsFemoris, Semitendinosus, Semimembranosus}
without touching MuscleGroup → MuscleHead relationships (e.g. Deltoid heads, Triceps
heads) where individual head distinction remains useful.

**Why not useGroupLevel:** `useGroupLevel=true` on Quadriceps and Hamstrings was
considered but rejected. Both are typed `feg:MuscleRegion`, not `feg:MuscleGroup`, so
adding the property would be a type mismatch. More importantly, `useGroupLevel`
prevents the LLM from ever using heads — which forecloses the possibility that an
exercise truly isolates one head (e.g. leg extension emphasising RectusFemoris via hip
flexion positioning). The repair query approach is more forgiving: heads are
permitted in enrichment output and collapsed post-hoc only when all siblings are
present at the same degree.

**Consolidation rule:** For each `(exercise, parent, degree)` triple where `parent` is
a `feg:MuscleRegion` with at least two direct `skos:broader` children, and where every
direct child of that parent appears as an involvement at `degree` on the exercise:
replace all child involvements with a single involvement for `parent` at `degree`. The
parent is not added if it is already an involvement on the exercise at any degree.

**SPARQL implementation note:** `skos:narrower` is not used in the vocabulary; the
"all children present" check uses the `FILTER NOT EXISTS { ?absentChild skos:broader
?parent . FILTER NOT EXISTS { ... } }` universal quantification pattern instead.

---

### ADR-053: Joint action vocabulary and feg:jointAction property
**Decision:** Add `feg:jointAction` as a new `owl:ObjectProperty` on `feg:Exercise`,
pointing to named individuals of a new `feg:JointAction` class. Add `feg:isCompound`
as a convenience `owl:DatatypeProperty` (range `xsd:boolean`) on `feg:Exercise`.
Encode the joint action vocabulary in a new `ontology/joint_actions.ttl` file,
organised as a SKOS hierarchy with joint grouping nodes as top concepts and
individual actions as `skos:narrower` concepts. Start at version `0.1.0`.

**Three-layer movement model:**

| Layer | Property | Purpose |
|---|---|---|
| Push/pull archetypes | `feg:movementPattern` | User-facing navigation and filtering |
| Structural complexity | `feg:isCompound` | Program design — exercise selection and balance |
| Mechanical precision | `feg:jointAction` | Substitution reasoning, muscle targeting, correctness |

Each layer is orthogonal. A barbell row is `HorizontalPull` (pattern),
`isCompound true`, and `ShoulderExtension + ScapularRetraction + ElbowFlexion`
(joint actions). A bicep curl is also `Pull` and `ElbowFlexion`, but
`isCompound false` — they share a pattern and a joint action, yet are not
interchangeable. The combination of all three dimensions enables that distinction.

**Why `feg:jointAction` is not modelled as SKOS narrower under `feg:movementPattern`:**
Joint actions and movement patterns are different kinds of things. `ElbowFlexion`
is not a subtype of `Pull` — elbow flexion occurs in rows (Pull), certain carries,
and isometric holds. `ShoulderAbduction` does not sit under either Push or Pull.
Encoding joint actions as narrower movement pattern concepts would bake incorrect
inferences into the graph via `skos:broader*` traversal. Separate properties keep
each dimension semantically coherent.

**Why SKOS hierarchy by joint:** Grouping nodes (`Shoulder`, `Elbow`, `Hip`,
`Knee`, `Ankle`, `Spine`, `Scapula`) enable traversal queries — "find all exercises
involving any shoulder joint action" via `?action skos:broader* feg:Shoulder`.
Consistent with the muscle vocabulary pattern (region → group → head). The
relationship is "action occurs at this joint" rather than strict IS-A, which is
the same pragmatic use of `skos:broader` already established in `muscles.ttl`.

**Vocabulary — ~35 terms across 7 joints:**

| Joint | Actions |
|---|---|
| Shoulder | Flexion, Extension, Abduction, Adduction, HorizontalAbduction, HorizontalAdduction, InternalRotation, ExternalRotation |
| Elbow | Flexion, Extension |
| Scapula | Retraction, Protraction, Depression, Elevation |
| Hip | Flexion, Extension, Abduction, Adduction, InternalRotation, ExternalRotation |
| Knee | Flexion, Extension |
| Ankle | Dorsiflexion, Plantarflexion, Inversion, Eversion |
| Spine | Flexion, Extension, Rotation, LateralFlexion |

URIs use joint prefix: `feg:ShoulderFlexion`, `feg:ElbowFlexion`, `feg:HipExtension`, etc.
Ankle terms use full anatomical name (`feg:Dorsiflexion`) rather than
`feg:AnkleDorsiflexion` — the `Dorsiflexion` and `Plantarflexion` terms are
unambiguous without the joint prefix; `Inversion` and `Eversion` get
`feg:AnkleInversion` / `feg:AnkleEversion` to avoid confusion with spinal/other contexts.

**`feg:isCompound` as boolean first pass:** The compound/isolation distinction
is not strictly binary — there is a spectrum from true isolation (single joint,
single muscle group) to fully integrated compound movements. What "compound" really
encodes is the number of meaningful joints contributing to force production.
A boolean is a pragmatic first pass and adequate for v1 filtering use cases.
Future: derive from joint action count or replace with a small controlled vocabulary.

**`feg:jointAction` attaches to `feg:Exercise`, not `feg:MuscleInvolvement`:**
Attaching to involvement would enable mechanically precise statements like
"GluteusMaximus is PrimeMover via HipExtension" — useful for distinguishing
hamstrings-via-HipExtension (deadlift) from hamstrings-via-KneeFlexion (leg curl)
in substitution queries. Deferred: exercise-level joint action combined with
movement pattern already partially captures this distinction
(HipHinge vs KneeDominant), and involvement-level is Medium-High LOE for v1.
Noted as a known limitation for future work.

**Files affected:**
- `ontology/joint_actions.ttl` — new vocabulary file (`0.1.0`)
- `ontology/ontology.ttl` — add `feg:JointAction` class, `feg:jointAction` and `feg:isCompound` properties
- `ontology/shapes.ttl` — add validation shapes for `jointAction` and `isCompound`
- `sources/free-exercise-db/prompt_template.md` — add joint actions section and example
- `sources/free-exercise-db/enrich.py` — add joint action tree and isCompound rule to prompt assembly
- `pipeline/prompt_builder.py` — no changes needed (generic utilities already handle new vocabulary)

---

### ADR-052: PassiveTarget involvement degree for Mobility and SoftTissue exercises
**Decision:** Add `feg:PassiveTarget` as a fourth `feg:InvolvementDegree` named
individual in `involvement_degrees.ttl`. Update `shapes.ttl` to: (a) include
`PassiveTarget` in the allowed `sh:in` enumeration for `feg:degree`; (b) exempt
exercises with at least one `PassiveTarget` involvement from the `PrimeMover`
`sh:minCount 1` requirement. Add a Mobility example to `prompt_template.md`.
Bump `involvement_degrees.ttl` `0.1.0 → 0.2.0` (MINOR: additive), `shapes.ttl`
`0.3.1 → 0.4.0` (MINOR: new constraint logic).

**Definition:** A muscle that is the passive target of a stretch or soft tissue
technique. Used in Mobility and SoftTissue exercises where the muscle is being
lengthened or treated rather than actively contracting. Exercises with at least
one PassiveTarget involvement are exempt from the PrimeMover requirement.
Synergists and Stabilizers may still be present if other muscles are actively engaged.

**Rationale:** The `sh:minCount 1` PrimeMover constraint was correct for active
exercises but semantically wrong for passive stretches and foam rolling — these
exercises have no prime mover by definition. Two options were considered:

1. **Global relaxation** — allow zero PrimeMover involvements for all exercises.
   Rejected: loses the validation guarantee for active exercises.

2. **PassiveTarget degree** — add a new degree that carries explicit semantic
   meaning (which muscle is being stretched/treated) and serves as the exemption
   signal. Chosen.

**PassiveTarget carries semantic value** beyond just being an exemption flag: it
distinguishes which muscle is the target of the treatment, enabling queries like
"find all exercises that stretch the hamstrings" without ambiguity. It also
documents the biomechanical relationship correctly — the stretched muscle is not
active and should not be classified as PrimeMover, Synergist, or Stabilizer.

**SHACL constraint change:** The PrimeMover constraint was a `sh:property
sh:minCount 1` rule, which cannot express conditional logic. It was replaced with
a `sh:sparql` constraint that fires only when neither PrimeMover nor PassiveTarget
involvements are present — preserving the guarantee for active exercises while
exempting passive ones.

**Scope:** PassiveTarget is the correct degree for: static stretches, PNF stretching,
yoga poses, foam rolling, and myofascial release. It should not be used on exercises
where the muscle is eccentrically loaded under tension (e.g. Romanian deadlift
hamstrings — these are PrimeMover with an eccentric emphasis, not passive targets).

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

- **SPARQL query library** — `queries/` directory with analytical queries demonstrating
  graph value (exercise discovery, substitution, muscle balance).
- **check_stale.py** — detects enriched exercises whose vocabulary version stamps are
  behind the current vocabulary. Needed once enrichment is at scale and vocabulary is
  still evolving.
- **Gold standard dataset** — 30–50 exercises with human-verified classifications.
  Required for quantitative eval (F1, precision, recall per field). `evals/annotate.py`
  exists for this purpose.
- **eval.py** — automated scoring against gold standard.
- **GOVERNANCE.md** — formal change management process document.
- **README.md** — project overview with architecture, governance framing, and run instructions.
- **pyproject.toml** — ruff config, pinned dependencies (morph-kgc, rdflib, pyshacl,
  anthropic, python-dotenv).

---

### ADR-061: Disjointness enforcement for feg:Muscle / feg:JointAction
**Decision:** Three coordinated changes to prevent joint action concept names from appearing
in muscle involvements, and to handle them automatically when they do:

1. **`owl:disjointWith feg:JointAction` on `feg:Muscle`** (`ontology.ttl` 0.4.0 → 0.5.0, MINOR):
   The two classes are semantically disjoint — a concept cannot be both a muscle and a joint
   action. Asserting this explicitly makes the constraint reasoner-accessible and self-documenting
   in the ontology rather than only implied by SHACL.

2. **SPARQL constraint on `MuscleInvolvementShape`** (`shapes.ttl` 0.6.2 → 0.7.0, MINOR):
   New `sh:sparql` constraint fires when `?muscle rdf:type feg:JointAction`. Message names the
   failure mode explicitly ("Joint action concept names… are NOT muscles"). `rdfs:comment` is
   present, so the rule is injected into the LLM prompt via `sparql_constraint_comments()` and
   appears in the `<<<sparql_constraints>>>` section. This is the prompt-facing enforcement.

3. **`repair_05_remove_jointaction_muscles.rq`**: SPARQL UPDATE that DELETEs any
   `MuscleInvolvement` (and all its triples) where `feg:muscle` is typed `feg:JointAction`.
   Runs as the fifth repair query in `ingest.py`. No-op when enriched data is clean; activates
   automatically for any legacy or future slip-through.

**Why all three:** The prompt prohibition in ADR-060 reduced the failure rate (3→1 across
rounds) but did not eliminate it. ScapularUpwardRotation leaked into muscle involvements in
every enrichment round. A single defence at the prompt level is insufficient for a systematic
failure mode. The three-layer approach (ontology declaration + SHACL prompt rule + repair
query) closes all gaps: the LLM is instructed not to do it, SHACL catches it if it does,
and repair_05 removes it automatically at ingest regardless.

**Validation:** After re-enriching Alternating_Cable_Shoulder_Press with the updated prompt,
ScapularUpwardRotation appeared only in `supporting_joint_actions` (correct) and not in
`muscle_involvements`. repair_05 ran and removed 0 triples — the safety net is active but
not needed. SHACL conforms.

**Afflicted exercise re-enriched:** Alternating_Cable_Shoulder_Press — previously required
a manual fix after every enrichment round. Now generates clean output without intervention.

---

### ADR-060: Prompt fixes for round 3 failure modes — setup-position, anti-extension, joint-action-as-muscle
**Decision:** Three rdfs:comment additions to `shapes.ttl` (v0.6.1 → v0.6.2, PATCH) and one
example addition to `prompt_template.md` to address systematic failure modes identified in
`self_eval_round3.md`. Also added `--exercises-file` argument to `enrich.py`.

**Changes:**

1. **`feg:muscle` rdfs:comment in `MuscleInvolvementShape`** — added explicit prohibition:
   "Critical: joint action concept names (e.g. ScapularUpwardRotation, HipFlexion, ElbowFlexion,
   ScapularRetraction) are NOT muscle names. Never use a joint action concept as a muscle value."
   Addresses: joint action concepts leaking into muscle involvements (3 occurrences across 2 rounds).

2. **`feg:primaryJointAction` rdfs:comment in `ExerciseShape`** — added anti-extension rule:
   "For anti-extension exercises (plank, ab rollout, dead bug), the primary joint action is
   SpinalStability — the spine is isometrically resisting extension load. Do NOT use
   SpinalExtension (that is for exercises where the spine actively extends)."
   Addresses: anti-extension / SpinalExtension confusion (1 occurrence in round 3).

3. **`feg:supportingJointAction` rdfs:comment in `ExerciseShape`** — added setup-position rule:
   "Setup-position rule: do not assign joint actions that describe the starting position of an
   exercise. Only include joint actions that occur during the movement itself. Example: bent knees
   at the start of a glute bridge are setup, not KneeFlexion; semi-locked knees during a good
   morning are setup, not a movement action."
   Addresses: setup-position-as-joint-action (3 occurrences in round 3).

4. **Plank example added to `prompt_template.md`** — shows AntiExtension pattern with
   SpinalStability (not SpinalExtension) as primary joint action. Supports rule 2 above with
   a concrete worked example.

5. **`--exercises-file` flag added to `enrich.py`** — allows passing a custom exercises JSON
   path for targeted re-enrichment (e.g. re-enriching only the 50 seed exercises after prompt
   changes).

**Round 4 results (from self_eval_round4.md):**
- Setup-position-as-joint-action: 3 → 0 ✓
- Anti-extension/SpinalExtension confusion: 1 → 0 ✓
- Misspelled muscle names: 2 → 0 ✓
- Joint action concepts as muscles: 3 → 1 (1 manual fix applied) — improved

**New issues surfaced in round 4:**
- TricepsBrachii group-level in Stabilizer/Synergist roles (6 exercises) — quality concern,
  not a SHACL violation. Deferred to next prompt iteration.
- AnkleEversion on Barbell Full Squat (should be Dorsiflexion) — flagged for annotator review.

---

### ADR-059: feg:movementPattern sh:minCount relaxed to 0
**Decision:** Relax the SHACL constraint on `feg:movementPattern` from `sh:minCount 1`
to `sh:minCount 0`. Movement patterns are now optional. Bump `shapes.ttl` `0.6.0 → 0.6.1`
(PATCH: constraint relaxation).

**Rationale:** Graph analysis of 50 enriched exercises identified a category of isolation
exercises that have no clean movement pattern — hip adduction, lying leg curl, lateral
raise, trunk flexion work. Forcing a pattern on these (e.g. assigning `Pull` to Band Hip
Adductions) creates noise in pattern-based clusters and substitution queries. The
vocabulary is deliberately coarse and user-facing; it should not be extended to cover
every isolation modality. The correct response for unclassifiable exercises is an empty
array, not a forced label.

**Prompt rule added:** "If no pattern fits well, return an empty array — do not force an
ill-fitting label. Isolation exercises that are not curls, rows, presses, or hinges often
have no clean pattern."

**Prior decision:** ADR-051 tightened this constraint to `sh:minCount 1`. That decision
was correct at the time (validate.py filters to enriched exercises, so unenriched exercises
are not affected). This ADR supersedes the minCount portion of ADR-051.

---

### ADR-058: feg:primaryJointAction and feg:supportingJointAction subproperties
**Decision:** Introduce `feg:primaryJointAction` and `feg:supportingJointAction` as
`rdfs:subPropertyOf feg:jointAction`. In data, only the subproperties are asserted;
the umbrella `feg:jointAction` is used for queries (resolves to both via RDFS inference).
Bump `ontology.ttl` `0.3.0 → 0.4.0` (MINOR) and `shapes.ttl` `0.5.0 → 0.6.0` (MINOR).

**primaryJointAction:** The joint actions that directly produce the exercise's defining
movement — the mechanical reason the exercise exists. Typically 1–3 per exercise.

**supportingJointAction:** Joint actions that contribute meaningfully but are not the
defining stimulus. Assigned only when relevant for substitution, fatigue accumulation,
or inter-muscular coordination. **Not a biomechanical inventory** — exhaustive supporting
lists degrade query quality. Typically 0–3 per exercise. When in doubt, omit.

**Rejected alternative — reified JointActionInvolvement node:** MuscleInvolvement was
reified because its role vocabulary is genuinely rich (4 distinct degrees) and the
nodes participate in repair queries. Joint action roles are essentially binary
(defining vs. supporting). The added complexity of reification is not justified.

**Rejected alternative — flat feg:jointAction with a separate feg:primaryJointAction:**
Double-asserting primary actions (once on each property) creates redundancy and
complicates repair queries. The subproperty approach is clean: one assertion per action.

**Governance rule on supportingJointAction:** Supporting joint actions must be selective,
not exhaustive. They should only capture contributions that matter for substitution,
fatigue, or coordination. This is a data governance rule enforced through prompt
instructions and annotation review, not purely through SHACL.

**Ingest compatibility:** `ingest.py` handles both the new format (`primary_joint_actions`,
`supporting_joint_actions` fields) and the legacy flat `joint_actions` field, allowing
existing enriched exercises to ingest correctly until re-enriched.

---

### ADR-057: pipeline/ directory — prompt_builder.py retained, legacy scripts removed
**Decision:** `pipeline/prompt_builder.py` is the canonical, actively-used module for
building LLM prompts from RDF ontology files. It is imported directly by
`sources/free-exercise-db/enrich.py` and has no project-specific knowledge. All other
scripts in `pipeline/` (`enrich.py`, `validate_graph.py`, `validate_ontology.py`,
`token_estimate.py`, `check_stale.py`) are legacy from an earlier pipeline design and
have been removed from version control.

**Legacy pipeline design:** The original pipeline wrote output to `data/graph/` and
`data/enriched/` paths. This was superseded by the `sources/free-exercise-db/`
layout (ADR-038 et seq.), which co-locates each source's scripts, mappings, and
artifacts. The legacy scripts referenced paths that no longer exist.

**`prompt_builder.py` location (updated):** Despite this ADR's original intent,
`prompt_builder.py` was moved into `sources/free-exercise-db/` alongside `enrich.py`.
The `pipeline/` directory no longer exists. `enrich.py` imports it via
`sys.path.insert(0, str(Path(__file__).parent))` which correctly resolves to the
co-located module. If a second source ever needs prompt building, extract it then.

**`exercises/` directory:** Removed from git tracking. No longer present in the repo.

---

### ADR-056: Tighten PrimeMover rdfs:comment to require primary biomechanical action
**Decision:** Update the `rdfs:comment` on `feg:PrimeMover` in `involvement_degrees.ttl`
to clarify that PrimeMover requires the muscle's **primary biomechanical action** to
directly produce the exercise's defining joint action(s). Bump version `0.2.0 → 0.2.1`
(PATCH: comment correction).

**Problem:** The previous definition — "the muscle or muscles primarily responsible for
producing the movement" — was ambiguous enough that the LLM assigned PrimeMover to
muscles that are active during a movement but contribute via a secondary action. The
canonical example: `LateralDeltoid` (primary action: shoulder abduction) assigned as
PrimeMover on a throwing exercise where `ShoulderFlexion` is the defining joint action.

**New rule:** A muscle is PrimeMover only if its primary biomechanical function directly
produces the exercise's defining joint action. A muscle active via a secondary function
— or one that assists without being the primary driver of that joint action — is
Synergist. The comment includes a concrete counterexample (LateralDeltoid on a throw)
to make the rule unambiguous for the LLM.

**Relationship to region consolidation (ADR-055):** When multiple muscles share the same
primary joint action (e.g. all four quadriceps heads producing KneeExtension), assigning
all of them PrimeMover remains valid and intentional — the consolidation repair pass
collapses them into the parent region post-ingestion. The PrimeMover comment notes this
explicitly to prevent undercounting in those cases.

---

### ADR-062: Round 4 annotator feedback — prompt and vocabulary fixes
**Decision:** Address actionable items from round 4 evaluation review (ChatGPT, Gemini,
and external ontologist annotations) via targeted `rdfs:comment` additions to `shapes.ttl`
and `involvement_degrees.ttl`. No new vocabulary concepts. Version bumps:
`shapes.ttl` 0.7.0 → 0.8.0 (MINOR: new constraint comment + significant comment additions);
`involvement_degrees.ttl` 0.2.1 → 0.2.2 (PATCH: comment clarification).

**Rejected ontology items (reasons recorded):**
- "Add Carry" — already exists (`feg:Carry`)
- "Add Lunge" — already exists (`feg:Lunge` under `feg:KneeDominant`)
- Pattern hierarchy via `rdfs:subClassOf` — misunderstands SKOS; hierarchy already encoded via `skos:broader`
- TrainingIntent layer — scope creep; largely covered by TrainingModality
- FunctionalMuscleGroup, Isometric joint actions, Axis/plane encoding, `feg:hasPrimaryJointActionTemplate`, Locomotion split — deferred to V2
- ClavicularHead/SternalHead rename — these are already the correct vocabulary names

**Design decisions locked in:**
- Alternate Heel Touchers: `SpinalLateralFlexion` is primary JA (lateral flexion is active); `Rotation` removed (empty array)
- Windmill: `SpinalLateralFlexion` is primary JA — spine IS moving, not isometrically holding
- Explosive hip extension (cleans, snatches, jumps): `GluteusMaximus` = PrimeMover, `Hamstrings` = Synergist
- `TricepsBrachii` group: must not be used; always decompose to `TricepsLongHead`, `TricepsLateralHead`, `TricepsMedialHead`

**Changes to `shapes.ttl`:**
1. `feg:movementPattern` comment — added explicit isolation prohibition: Push/Pull require
   multi-joint force production; single-joint movements (curls, lateral raises, triceps
   extensions, leg extensions/curls) return empty array.
2. `feg:primaryJointAction` comment — generalized anti-movement rule to all three Anti*
   patterns: AntiExtension → SpinalStability; AntiRotation → SpinalStability;
   AntiLateralFlexion → SpinalStability. Spine isometrically resists in all cases.
3. `feg:supportingJointAction` comment — ankle mechanics note for sagittal plane lifts:
   Dorsiflexion is the correct action for squats/deadlifts/lunges; AnkleEversion and
   AnkleInversion are movement faults, not defining supporting actions.
4. `feg:muscle` comment (MuscleInvolvementShape) — two additions: (a) TricepsBrachii
   must not be used; decompose to heads always; (b) on Mobility/stretch exercises,
   minimize Stabilizers — include only when there is a clear active stabilization demand.

**Changes to `involvement_degrees.ttl`:**
- `feg:PrimeMover` comment — added exception for explosive hip extension movements:
  GluteusMaximus is PrimeMover, Hamstrings are Synergist (biarticular; not the primary driver).

**Why not a SPARQL constraint for explosive PrimeMover?**
A `sh:sparql` constraint fires on all exercises with `feg:Power` modality, but not all
Power exercises are hip-extension movements (throws, for example). A false-positive rate
is unacceptable here. The rule belongs in `rdfs:comment` as model guidance, not as a
hard SHACL enforcement constraint.

**Follow-up:** Re-enrich all 50 seed exercises against the updated prompt; run pipeline
and validate (target: 0 SHACL violations). Rebuild eval_package for round 5.

---

### ADR-063: Per-exercise file storage for enriched and quarantine data; tenacity backoff
**Decision:** Replace the single `exercises_enriched.json` and `exercises_quarantine.json`
files with one JSON file per exercise: `enriched/{exercise_id}.json` and
`quarantine/{exercise_id}.json`. Add tenacity-based exponential backoff for
`RateLimitError` (429) in `enrich.py` before falling back to quarantine.
Default concurrency reduced to 1; `--concurrency N` flag retained for opt-in parallelism.

**Problem with single-file approach:**
1. Every write rewrites the entire array — O(n) I/O per exercise enriched
2. Concurrent writes required a thread lock on the whole file, limiting actual parallelism
3. Git diffs for re-enrichment runs were unreadable (thousands of lines changed for ~50 exercises)
4. Rate-limited (429) requests went immediately to quarantine with no retry — any concurrency
   above 1 would quarantine exercises that would have succeeded with a brief wait

**Per-file benefits:**
- Each write is atomic and touches only one file — no lock needed between concurrent exercises
- `git diff` on a re-enrichment run shows only the changed exercises
- Individual exercises can be deleted and re-enriched without touching others
- check_stale.py, ingest.py, and enrich.py all glob the directory — no array index management

**Tenacity backoff policy:**
- Retries on `anthropic.RateLimitError` (HTTP 429) only — not on other API errors
- Exponential backoff: min 30s, max 180s, multiplier 30 (30s → 90s → 180s)
- 4 attempts maximum before raising and going to quarantine
- `reraise=True` — final failure still reaches the except handler and quarantine

**Default concurrency changed to 1:** Concurrency=4 without backoff caused 20/50 quarantines
in round 5. With backoff, concurrency can be increased safely, but the safe default is 1.
Users opt in to parallelism via `--concurrency N`.

**Directory structure:**
```
sources/free-exercise-db/
  enriched/           # one .json per enriched exercise (gitignored)
    Barbell_Deadlift.json
    ...
  quarantine/         # one .json per failed exercise (gitignored)
    Some_Exercise.json   # {"exercise": {...}, "error": "..."}
```

**Migration:** existing `exercises_enriched.json` (52 exercises) split to per-file in place;
`exercises_quarantine.json` (0 entries) similarly migrated; old files deleted.

**Files changed:** `enrich.py`, `ingest.py`, `check_stale.py`, `pyproject.toml` (tenacity added),
`.gitignore` (quarantine/ added).

---

### ADR-064: URI hygiene — sanitize hyphens in exercise IDs
**Status:** Accepted

**Context:** 215 exercise IDs in the source dataset contain hyphens (e.g.
`Single-Leg_Lateral_Hop`, `Barbell_Bench_Press_-_Medium_Grip`). These produce URIs like
`feg:ex_Single-Leg_Lateral_Hop` which are valid IRIs but invalid XML NCNames, forcing
Turtle serializers to fall back to full angle-bracket notation (`<https://placeholder.url#ex_Single-Leg_Lateral_Hop>`)
and preventing compact SPARQL QName syntax. `validate.py` already shows `rdfs:label`
alongside URIs in violation messages, so debuggability with opaque URIs is not a concern.

**Decision:** Replace `-` with `_` in exercise IDs at URI construction time only.
`preprocess.py` adds a `sanitized_id` field to each record (`id.replace("-", "_")`).
`exercises.yarrrml.yaml` uses `$(sanitized_id)` in all URI templates and join conditions.
`ingest.py` applies `_sanitize_id()` in `_apply_enrichment`. The raw `id` value is
preserved as-is in `feg:legacySourceId` for provenance.

**Sanitized-descriptive over opaque:** The source IDs are already camelCase/underscore
style; hyphens are the only problem. Keeping the descriptive name maintains operator
legibility in SPARQL, Turtle, and violation messages without the stability cost of
opaque hash-based URIs.

**Consequences:** All previously ingested data must be re-ingested. Enriched JSON files
in `enriched/` are unaffected — they use the raw `id` field, and `_sanitize_id()` is
applied at the point of URI construction in `ingest.py`.

**Files changed:** `sources/free-exercise-db/preprocess.py`, `sources/free-exercise-db/mappings/exercises.yarrrml.yaml`,
`sources/free-exercise-db/ingest.py`.

---

### ADR-065: Add TeresMajor and Sartorius to muscles vocabulary
**Status:** Accepted

**Context:** During bulk enrichment, two exercises were quarantined due to vocabulary
validation failures: `Underhand_Cable_Pulldowns` (LLM output `TeresMajor`) and
`Seated_Leg_Curl` (LLM output `Sartorius`). Both are real muscles correctly identified
by the model — they were simply absent from the vocabulary.

**Decision:** Add both as `MuscleGroup` individuals (single muscles, no distinct
heads relevant to exercise programming):

- `feg:TeresMajor` under `feg:Lats` — acts synergistically with LatissimusDorsi in
  shoulder extension and adduction. Distinct from `feg:TeresMinor` (rotator cuff).
  Scope note clarifies the distinction and typical exercises where it appears.

- `feg:Sartorius` under `feg:Quadriceps` — anterior thigh muscle; assists knee
  flexion and hip flexion. Closest anatomical home in the existing hierarchy.
  Scope note clarifies it is not a quad head.

**Version bump:** `muscles.ttl` 0.8.0 → 0.9.0 (additive, MINOR).

**Files changed:** `ontology/muscles.ttl`.

---

### ADR-067: Pipeline cleanup — remove legacy code, unify sanitize_id, fix URI construction
**Status:** Accepted

**Context:** Codebase audit (2026-03-21) identified accumulated historical artifacts
after reaching 100% enrichment coverage (873/873 exercises).

**Changes:**

1. **Removed legacy `joint_actions` fallback in `ingest.py`** — pre-ADR-058 exercises
   carried a flat `joint_actions` list. All 873 exercises are now enriched with the
   split `primary_joint_actions` / `supporting_joint_actions` format. The fallback is
   dead code and has been removed.

2. **Extracted `sanitize_id` to `utils.py`** — the one-liner `id.replace("-", "_")`
   was duplicated in `preprocess.py` and `ingest.py`. Extracted to
   `sources/free-exercise-db/utils.py` and both files now import from it (ADR-064).

3. **Fixed hardcoded namespace in muscle region consolidation** — the URI construction
   for new involvement nodes duplicated the `https://placeholder.url#` namespace string.
   Fixed so namespace migration requires updating one place.

4. **Updated CLAUDE.md pipeline docs** — added `check_stale.py` section; expanded
   `enrich.py` usage examples to document `--retry-quarantine`, `--force`,
   `--concurrency`.

5. **Corrected ADR-057** — updated to reflect that `prompt_builder.py` now lives in
   `sources/free-exercise-db/` (not `pipeline/`) and that `exercises/` has been removed.

**Files changed:** `sources/free-exercise-db/ingest.py`,
`sources/free-exercise-db/preprocess.py`, `sources/free-exercise-db/utils.py` (new),
`CLAUDE.md`, `DECISIONS.md`.

---

### ADR-066: Vocabulary binding rule in prompt; robust JSON extraction
**Status:** Accepted

**Context:** Two persistent quarantine failures drove this change. (1) `Two-Arm_Kettlebell_Row`
consistently produced `HipHinge` as a `supporting_joint_action`. `HipHinge` is a
`MovementPattern`, not a `JointAction` — the model was crossing vocabulary boundaries
because no explicit constraint prevented it. (2) `Side_Jackknife` consistently produced
valid JSON followed by trailing text, causing `json.loads` to raise `Extra data`.

**Decision:**

1. Added a vocabulary-binding rule block to the output format section of
   `prompt_template.md`, immediately before the field-level rules. Each output field
   is explicitly bound to its own controlled vocabulary; a general "do not use a term
   from one vocabulary in a field that belongs to another" rule is stated once. No
   per-term exceptions.

2. Replaced `json.loads(raw)` in `enrich.py` with `json.JSONDecoder().raw_decode()`
   which parses the first complete JSON object and ignores any trailing content.

**Rationale:** A general vocabulary-binding rule is more maintainable than per-term
exceptions and guards against analogous crossover mistakes in other fields. `raw_decode`
is the standard library's own mechanism for tolerating trailing data — no third-party
dependency or regex required.

**Files changed:** `sources/free-exercise-db/prompt_template.md`,
`sources/free-exercise-db/enrich.py`.

---

### ADR-068: Remove preprocess.py; expand validate.py to 6-dimension quality scorecard
**Status:** Accepted

**Context:** `preprocess.py` now serves two purposes: (1) muscle crosswalk normalization
— dead work because `_apply_enrichment` in `ingest.py` deletes all morph-KGC muscle
involvements and replaces them with LLM-derived data; and (2) adding `sanitized_id` to
each exercise record — a one-liner trivially inlineable into `ingest.py`. Running a
separate preprocessing step for a dead crosswalk and a one-liner was unnecessary
complexity. Separately, `validate.py` only ran SHACL validation; systematic quality
analysis (completeness, consistency, referential integrity, etc.) was entirely manual.

**Decision:**

1. **Remove `preprocess.py`** and inline `sanitized_id` generation directly into
   `ingest.py` (load `raw/exercises.json`, add field, write `exercises_normalized.json`
   before calling `morph_kgc.materialize()`).

2. **Remove `muscle_crosswalk.csv`** and strip the three dead YARRRML maps
   (`MuscleConceptMap`, `PrimaryInvolvementMap`, `SecondaryInvolvementMap`) and their
   `feg:hasInvolvement` join conditions from `exercises.yarrrml.yaml`. The
   `EquipmentConceptMap` and its join are retained — equipment mapping is still active.

3. **Expand `validate.py`** to cover 6 quality dimensions:
   - **Validity** (fail): SHACL conformance — unchanged logic
   - **Uniqueness** (fail): duplicate muscle involvements, joint actions, movement
     patterns per exercise; JA appearing in both primary and supporting lists
   - **Integrity** (fail): every vocabulary reference (muscle, pattern, JA, degree)
     resolves to a known ontology term
   - **Timeliness** (warn): reuses `check_stale.py` logic; reads `vocabulary_versions`
     stamps from enriched JSON files
   - **Consistency** (warn): cross-field rules — hip JAs without hip patterns,
     shoulder JAs without Push/Pull, SpinalStability without anti-movement pattern,
     `isCompound=false` with 3+ primary JAs
   - **Completeness** (warn): no movement patterns (unless PassiveTarget), fewer
     than 2 muscle involvements, no primary joint actions

4. **CSV output** — `quality_report.csv` written alongside `ingested.ttl`; one row
   per enriched exercise with columns for each dimension score and issue detail.
   `--csv PATH` overrides the output path; `--all` includes perfect-scoring exercises
   in stdout (default: imperfect only). Exit behaviour unchanged: exits 1 only on
   validity failures.

**Rationale:** Muscle crosswalk normalization was pure dead weight once the LLM
enrichment pipeline took over. Inlining the sanitized_id computation eliminates a
manual pipeline step. Consolidating quality checks into validate.py gives a single
command that produces both a machine-readable scorecard and a human-reviewable CSV —
without fragmenting the quality tooling across multiple scripts.

**Files changed:** `sources/free-exercise-db/ingest.py`,
`sources/free-exercise-db/mappings/exercises.yarrrml.yaml`,
`sources/free-exercise-db/validate.py`, `CLAUDE.md`, `DECISIONS.md`.
**Deleted:** `sources/free-exercise-db/preprocess.py`,
`sources/free-exercise-db/mappings/muscle_crosswalk.csv`.

---

### ADR-069: Add LevatorScapulae to muscle vocabulary
**Status:** Accepted

**Context:** The integrity check on the quality report flagged `feg:LevatorScapulae` as
an unknown muscle reference on Barbell Shrug. The muscle is anatomically correct —
the levator scapulae elevates and downwardly rotates the scapula and is co-active with
the upper trapezius in shrugging movements. The model produced it correctly; the
vocabulary was simply missing it.

**Decision:** Add `feg:LevatorScapulae` as a `feg:MuscleGroup` under `feg:Neck`.
Bump muscles.ttl `owl:versionInfo` from `0.9.0` to `0.10.0` (MINOR: additive).

**Rationale:** Shrug variants and neck-loading exercises legitimately involve the
levator scapulae. Omitting it forces the model to use an imprecise substitute
(UpperTrapezius alone) or produce an integrity violation. Adding it to the Neck region
follows existing anatomical conventions in the vocabulary.

**Files changed:** `ontology/muscles.ttl`.

---

### ADR-070: Ancestor violation repair query; prompt fix; validate.py rule refinements
**Status:** Accepted

**Context:** The quality report revealed 396 SHACL validity failures, all from a single
rule: exercises assigning both a muscle and one of its SKOS ancestors (e.g. Quadriceps +
RectusFemoris). The constraint existed in shapes.ttl and was included in the prompt's
`<<<sparql_constraints>>>` section, but 396 violations indicate the model was not
respecting it reliably. Additionally, 164 consistency warns and 268 completeness warns
were false positives caused by rules that didn't account for isolation exercises.

**Decision:**

1. **Add ancestor-removal repair pass to `ingest.py`** — deletes ancestor involvements
   when a more-specific descendant is already present on the same exercise
   (`child skos:broader+ ancestor`). Runs after the joint-action-as-muscle pass. Fixes
   the 396 existing violations on next ingest without requiring re-enrichment, and acts
   as a permanent safety net for regressions.

2. **Add `### Ancestor rule` to `prompt_template.md`** — a dedicated section placed
   immediately before `### Group-level muscles`, with concrete wrong/right examples.
   The rule was already in `<<<sparql_constraints>>>` but buried at the end; a prominent
   section adjacent to the muscle specificity rules makes it harder to miss.

3. **Fix consistency rules in validate.py** — scope hip JA and shoulder JA cross-field
   rules to `isCompound=true`. Isolation exercises (cable kickbacks, lateral raises) have
   legitimate hip/shoulder JAs without a corresponding compound movement pattern.
   The `isCompound=false + 3+ primary JAs` rule was removed entirely — it produced 0 true
   positives across 873 exercises (circle mobility drills and supination curls legitimately
   have 3–4 JAs while being single-joint movements).

4. **Fix completeness rule in validate.py** — scope "no movement patterns" to
   `isCompound=true`. The ontology's own design (shapes.ttl `sh:minCount 0` on
   `feg:movementPattern`) explicitly permits empty patterns for isolation exercises.
   The completeness check now aligns with that intent.

**Rationale:** The repair pass is the right pattern for systematic data corrections that
the prompt alone cannot guarantee — it mirrors the joint-action-as-muscle pass which
addresses the same failure mode at a different level. Making the ancestor rule prominent
in the prompt reduces future recurrence. The validate.py rule fixes eliminate ~430 false
positives that were masking real signal.

**Files changed:** `sources/free-exercise-db/ingest.py`,
`sources/free-exercise-db/prompt_template.md`, `sources/free-exercise-db/validate.py`,
`DECISIONS.md`.

---

### ADR-071: Move prompt grounding from shapes.ttl to ontology.ttl
**Status:** Accepted

**Context:** Classification instructions for the LLM enrichment pipeline were stored as
`rdfs:comment` on SHACL property shapes and `sh:sparql` constraint nodes in `shapes.ttl`.
This created an architectural coupling: a validation schema was doing double duty as a
prompt configuration file. The two jobs have different audiences (SHACL validators vs LLM),
different editing cadences (schema changes vs prompt tuning), and different correctness
criteria. Prose hidden in SHACL blank nodes is non-obvious to readers and obscures the
intent of both the validation schema and the enrichment prompt.

**Decision:** Classification instructions move to `rdfs:comment` on OWL property definitions
in `ontology.ttl`. This is the semantically correct location: property documentation belongs
on the property, not on constraints that reference it. The prompt builder (`prompt_builder.py`)
now reads `rdfs:comment` directly from property URIs in `ontology.ttl` rather than traversing
SHACL shapes. `shapes.ttl` is stripped of all instructional prose and contains only structural
validation: cardinalities, class membership, `sh:in` enumerations, and validation messages.
Cross-field rules that previously appeared as standalone `sparql_constraint` bullets are
absorbed into the `rdfs:comment` of the most relevant property (`feg:muscle`, `feg:degree`).
`sparql_constraint_comments()` is removed from `prompt_builder.py`. The `## Validation
constraints` section is removed from `prompt_template.md`.

**Rationale:** Property semantics belong on the property. Editing classification rules for
the LLM now means editing the ontology file where the property is defined — the right place
for anyone reading the ontology to expect to find this information. SHACL remains the right
tool for structural validation and is now cleanly scoped to that role. The prompt content is
substantially identical to before; minor improvements were made to `feg:muscle` and `feg:degree`
comments while migrating.

**Files changed:** `ontology/ontology.ttl`, `ontology/shapes.ttl`,
`sources/free-exercise-db/prompt_builder.py`, `sources/free-exercise-db/enrich.py`,
`sources/free-exercise-db/prompt_template.md`, `DECISIONS.md`.

---

### ADR-072: Pydantic output model for enrichment-time validation
**Status:** Accepted

**Context:** The LLM enrichment pipeline validated post-hoc via a vocabulary term check
(`_validate_fields`) plus downstream repair passes in `ingest.py`. Cross-field rules (no
ancestor+descendant, Core as Stabilizer, no duplicate muscles, at least one PrimeMover) were
caught late — either by SHACL or by repair passes — rather than at the point of data creation.
This meant invalid enrichments could be written to `enriched/` and only surfaced during ingest.

**Decision:** Add `MuscleInvolvement` and `ExerciseEnrichment` Pydantic models to `enrich.py`.
Fields carry types only — no prompt instructions in `Field(description=...)`. Cross-field
business rules are `@model_validator` methods: (1) vocabulary term validity, (2) at least one
PrimeMover or PassiveTarget, (3) Core must be Stabilizer, (4) no useGroupLevel head terms,
(5) no duplicate muscles, (6) no ancestor+descendant overlap. Graph-dependent validators read
from precomputed lookup tables (`_ANCESTOR_MAP`, `_USE_GROUP_LEVEL_HEADS`) populated by
`_setup_validators()` after graphs load. A failed `model_validate()` raises `ValidationError`
and routes the exercise to quarantine. A passing exercise is written via `model_dump(exclude_none=True)`.

**Rationale:** Validation at write time means `enriched/*.json` is the authoritative,
pre-validated dataset. Downstream repair passes for these rules become unnecessary. The Pydantic
model is the output schema contract — code, not prose, not SHACL. The lookup tables are
precomputed once at startup (not per-exercise) so the per-exercise cost is negligible.

**Files changed:** `sources/free-exercise-db/enrich.py`, `DECISIONS.md`.

---

### ADR-073: Replace morph-KGC + ingest.py with build.py
**Status:** Accepted

**Context:** The old ingestion pipeline used morph-KGC (a mapping framework) with a YARRRML
mapping file to transform exercises.json into RDF. This required: generating
`exercises_normalized.json` with `sanitized_id` fields, running morph-KGC with a config file
and cwd dependency, handling FutureWarnings from the framework, and applying 6 repair passes
(3 SPARQL, 3 Python) to fix data quality issues that should never have reached the RDF layer.
The mapping itself was ~50 lines of YARRRML doing a flat JSON→RDF transform. With enrichment-time
Pydantic validation (ADR-072) handling the cross-field rules, repair passes 03, 04, 06 became
redundant. Repair passes 01, 02, 05 addressed upstream data quality issues (unmapped muscles,
duplicates, JA-as-muscle) that are now caught by Pydantic validators.

**Decision:** Replace `ingest.py` and the morph-KGC/YARRRML layer with `build.py` — ~120 lines
of straightforward Python JSON→RDF assembly using rdflib directly. `build.py` reads
`exercises.json`, applies the equipment crosswalk CSV, assembles Exercise triples for all 873
exercises, overlays enrichment triples from `enriched/*.json`, merges ontology vocabulary files,
and serialises to `ingested.ttl`. No repair passes. The pipeline now runs in <1s (down from
several minutes). `enriched/` is removed from `.gitignore` and version controlled — it is the
dataset; `ingested.ttl` remains gitignored as a derived artifact. `mappings/` directory
(YARRRML, morph-KGC config) is deleted.

**Rationale:** The right abstraction for "assemble a graph from JSON files" is 120 lines of
Python, not a mapping framework. Removing morph-KGC eliminates a dependency, a config file,
a cwd dependency, and FutureWarning noise. The repair passes were a symptom of validating
too late — moving validation upstream (Pydantic) eliminates the need for downstream fixes.
Version-controlling `enriched/` treats the dataset as what it is: the primary output of the
enrichment pipeline, not a gitignored cache.

**Files changed:** `sources/free-exercise-db/build.py` (new),
`sources/free-exercise-db/run_pipeline.py`, `.gitignore`, `DECISIONS.md`.
`sources/free-exercise-db/ingest.py` and `sources/free-exercise-db/mappings/` deleted.

---

### ADR-074: MCP server backed by pyoxigraph in-process
**Status:** Accepted

**Context:** The knowledge graph needs a consumption layer for AI applications. The graph
is ~43k triples once assembled — small enough to hold in process memory. The MCP protocol
(Model Context Protocol) is the standard interface for exposing structured tools to LLM
clients (Claude Desktop, etc.). SPARQL querying is required for the substitution tool, which
joins across movement patterns and PrimeMover muscles.

**Decision:** Implement `mcp_server.py` — a single-file MCP server that loads `ingested.ttl`
into a pyoxigraph in-process store at startup and exposes 5 tools:

1. `search_exercises(muscles, movement_pattern, equipment, degree)` — filter with all criteria
   ANDed; returns matching exercises with involvement summaries.
2. `get_exercise(exercise_id)` — full record: muscles + degrees, joint actions, movement
   patterns, training modalities, equipment, compound/unilateral flags.
3. `find_substitutions(exercise_id, equipment_available)` — exercises sharing the same primary
   movement pattern(s) and overlapping PrimeMover muscles; filtered to available equipment.
   Bodyweight exercises always included when equipment filter is active.
4. `get_muscle_hierarchy()` — complete SKOS muscle tree: regions → groups → heads, with
   `useGroupLevel` flags.
5. `query_by_joint_action(joint_action)` — exercises where the given joint action is primary.

pyoxigraph was chosen over rdflib for SPARQL because it uses a compiled query planner and
avoids rdflib's Python-level self-join bottlenecks.

**Rationale:** In-process loading eliminates infrastructure (no Docker, no Fuseki, no running
service). The store fits in ~50MB RSS. `find_substitutions` is the hero tool: semantically
grounded exercise substitution backed by the ontology — the kind of query that is impossible
against flat JSON data.

**Alternatives considered:**
- Apache Jena/Fuseki: correct tool for production, but overkill for a local dev/portfolio
  context and requires a running JVM process.
- rdflib SPARQL: available but slow for multi-join queries (Python-level evaluation).
- REST API instead of MCP: adds HTTP server boilerplate and doesn't integrate with Claude
  Desktop natively.

**Files changed:** `mcp_server.py` (new), `pyproject.toml` (add mcp, pyoxigraph deps),
`README.md`, `DECISIONS.md`.

---

### ADR-075: Replace feg:isUnilateral boolean with feg:laterality vocabulary
**Status:** Accepted

**Context:** The original `feg:isUnilateral` property was added early in the project as a
simple boolean flag: true if the exercise is performed one limb at a time, false if both
limbs work together. This was adequate for the free-exercise-db source, whose data didn't
distinguish between types of unilateral movement.

When mapping the Functional Fitness Exercise Database, the `Laterality` field surfaced four
distinct values: Bilateral, Unilateral, Contralateral, and Ipsilateral. Bilateral and
Unilateral are straightforward. Contralateral describes exercises where opposite limbs move
together — the Bird Dog is the canonical example: right arm extends simultaneously with the
left leg. Ipsilateral describes exercises where same-side limbs work together, as in certain
loaded carry variations and some single-leg, single-arm combinations.

The debate was whether Contralateral and Ipsilateral are worth distinguishing from plain
Unilateral. The case against: most gym-goers don't know or care about the difference, and
our search tools don't currently filter on laterality at all. The case for: Contralateral
exercises are clinically meaningful — they train anti-rotational core stability and
neuromuscular coordination in ways that standard Unilateral exercises don't. A clinical
exercise specialist programming around a unilateral hip pathology would treat a Contralateral
Bird Dog very differently from a Unilateral Single-Leg Romanian Deadlift. Collapsing them
to the same value loses that distinction permanently.

The four-value vocabulary also resolves a subtle problem with the boolean: "isUnilateral =
false" is ambiguous. It means Bilateral, but it could be read as "not a one-limb exercise"
— which is technically true of Contralateral exercises as well (both limbs are engaged, just
asynchronously). The vocabulary removes the ambiguity.

**Decision:** Deprecate `feg:isUnilateral` and introduce `feg:laterality` as an object
property pointing to a new `laterality.ttl` SKOS vocabulary with four named individuals:
`feg:Bilateral`, `feg:Unilateral`, `feg:Contralateral`, `feg:Ipsilateral`. This is a
breaking change to the property semantics and requires a MAJOR version bump on the ontology.
Free-exercise-db exercises will be backfilled via an LLM enrichment pass — the LLM can
reliably distinguish Contralateral exercises (Bird Dog, Dead Bug variants) from plain
Unilateral.

**Alternatives considered:**
- Keep boolean, map Contralateral/Ipsilateral to `true`: simple, but loses meaningful
  clinical information that is now in the dataset and costs nothing extra to model.
- Extend the boolean to a tri-value property (Bilateral / Unilateral / Contralateral),
  dropping Ipsilateral: considered briefly, but Ipsilateral appears in ~50 exercises and
  discarding it while adding the vocabulary anyway felt arbitrary.

**Files to change:** `ontology/ontology.ttl` (deprecate `feg:isUnilateral`, add
`feg:laterality`), new `ontology/laterality.ttl`, `ontology/shapes.ttl` (update SHACL
constraint), `sources/free-exercise-db/enrich.py` (add laterality to enrichment schema),
`sources/free-exercise-db/build.py` (update triple assembly), `DECISIONS.md`.

---

### ADR-076: Add feg:isCombination boolean property
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database distinguishes between "Single Exercise"
and "Combo Exercise" — exercises that chain two or more distinct movements into a single set.
Examples include a Squat-to-Press, a Deadlift-to-Row, or a Lunge-to-Curl. Combo exercises
are a common programming tool for time efficiency and metabolic conditioning, but they behave
differently from single-movement exercises in a knowledge graph context: they have multiple
primary movement patterns, their muscle involvement spans what would normally be two separate
exercises, and they are poor substitution candidates for either of their constituent movements.

The debate was whether this property is worth adding given that free-exercise-db has no
equivalent and all 873 existing exercises would default to false. The concern was that a
property that is null or false for all existing data adds noise without signal. The
counter-argument prevailed: as a second source adds ~3,240 exercises — many of them combo
exercises — the property becomes meaningful across the full graph. The backfill pass for
existing exercises is also tractable: an LLM can reliably identify combo exercises from
name and muscle involvement alone (a "Squat to Press" is unmistakably a combo exercise).

`feg:isCombination` is intentionally distinct from `feg:isCompound`. Compound refers to
joint mechanics — an exercise is compound if two or more distinct joints contribute to force
production. Combination refers to movement structure — the exercise is a deliberate sequence
of two independent movements performed as one. A Barbell Deadlift is compound but not a
combination. A Dumbbell Squat-to-Press is both.

**Decision:** Add `feg:isCombination` as a boolean datatype property on `feg:Exercise`.
Combo Exercise → `true`, Single Exercise → `false`. Backfill required for all free-exercise-db
exercises via LLM enrichment. Add to SHACL shapes with `sh:datatype xsd:boolean`.

**Alternatives considered:**
- Model as a combination-specific subclass of `feg:Exercise`: over-engineered for a boolean
  distinction. A flag is sufficient.
- Skip: combination exercises are a real programming concept and the data is clean and
  available. Dropping it is a one-way door — once we ingest without it, backfilling requires
  re-touching every exercise.

**Files to change:** `ontology/ontology.ttl` (add property definition), `ontology/shapes.ttl`
(add SHACL constraint), `sources/free-exercise-db/enrich.py` (add to enrichment schema),
`sources/free-exercise-db/build.py` (add triple assembly), `DECISIONS.md`.

---

### ADR-077: Add feg:planeOfMotion property and planes_of_motion.ttl vocabulary
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database classifies each exercise against up to
three planes of motion: Sagittal (forward/backward), Frontal (side to side), and Transverse
(rotational). These are the three cardinal planes of human movement — a foundational concept
in biomechanics with no ambiguity or disagreement across exercise science literature.

The plane of motion of an exercise has real downstream value. Program designers use it to
ensure movement variety: a well-designed training week should include exercises across all
three planes, not just sagittal-dominant lifts (which describes most standard strength
programs). For the substitution tool, plane of motion is a useful secondary filter — a
Transverse plane substitution for a Sagittal exercise is not a neutral swap for a rotational
athlete or a patient in rotational rehab.

The debate was whether this adds anything beyond what joint actions already provide. Joint
actions do imply planes — HipExtension is sagittal, HipAbduction is frontal, HipRotation is
transverse — but deriving plane from joint actions requires inference, and not all exercises
have complete joint action coverage. Plane of motion as a direct property is cheap to store,
easy to query, and immediately legible to non-specialists. A gym-goer searching for
"rotational exercises" doesn't know what transverse plane means, but a content architect
building a balanced program library does.

Free-exercise-db exercises have no plane of motion data. They will be backfilled via LLM
enrichment — the LLM can reliably assign planes from exercise name, movement pattern, and
muscle involvement.

**Decision:** Add `feg:planeOfMotion` as an object property and create
`ontology/planes_of_motion.ttl` with three SKOS named individuals: `feg:SagittalPlane`,
`feg:FrontalPlane`, `feg:TransversePlane`. An exercise may have multiple planes. MINOR
version bump on the ontology.

**Alternatives considered:**
- Derive plane from joint actions via SPARQL inference: correct in theory but brittle in
  practice — requires complete joint action coverage and adds query complexity with no
  benefit over a direct property.
- Use literal strings instead of named individuals: rejected on principle — controlled
  vocabulary terms belong in the ontology as named individuals, not as free-text strings.

**Files to change:** new `ontology/planes_of_motion.ttl`, `ontology/ontology.ttl` (add
property definition), `ontology/shapes.ttl` (add SHACL constraint), `DECISIONS.md`.

---

### ADR-078: Add feg:exerciseStyle property and exercise_styles.ttl vocabulary
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database classifies exercises under a "Primary
Exercise Classification" field with values including Bodybuilding, Calisthenics, Powerlifting,
Olympic Weightlifting, Plyometric, Mobility, Postural, Animal Flow, Ballistics, Grinds, and
Balance. This presented a mapping challenge: we already have `feg:TrainingModality`, defined
as "a category describing the physiological adaptation targeted by an exercise." Some of
these values fit that definition (Mobility, Plyometric), but most do not.

The key distinction that emerged from discussion: training modality answers "what does this
exercise do to the body?" Exercise style answers "what tradition or system does this exercise
belong to?" Bodybuilding, Calisthenics, Powerlifting, and Olympic Weightlifting are not
physiological adaptations — they are training systems with their own movement cultures,
technique standards, and communities. Animal Flow is a movement practice. Grinds is a
kettlebell sport term for slow-strength lifts as distinct from ballistic movements. These
are not modalities by our definition, and folding them into `feg:TrainingModality` would
corrupt a property that is currently clean and well-scoped.

The use case for exercise style is distinct from modality. A content architect building a
kettlebell-focused program library wants to filter the exercise database by style, not by
physiological outcome. An agentic coach serving an Olympic weightlifting athlete wants to
surface clean and jerk accessory work — searching by style is the natural query. A user
curious about Animal Flow wants to explore that movement system specifically. None of these
are questions that training modality can answer.

**Decision:** Add `feg:exerciseStyle` as an object property with the definition: "a category
describing the training system, tradition, or methodological context an exercise belongs to."
Create `ontology/exercise_styles.ttl` as a SKOS vocabulary. The exact set of named individuals
requires a separate vocabulary review pass — not all source values will survive as FEG
concepts (e.g. "Unsorted*" is dropped, Plyometric overlaps with the existing training
modality and needs a resolution decision). MINOR version bump on the ontology.

**Alternatives considered:**
- Fold style values into `feg:TrainingModality`: rejected. The property has a clear definition
  and Calisthenics, Animal Flow, and Grinds are not physiological adaptations by any
  reasonable reading. Contaminating a clean property with categorically different values
  is worse than adding a new property.
- Skip entirely: the source data is clean and the use cases are real. The content architect
  persona has no other way to filter by training system. Dropping it forfeits a meaningful
  dimension of the second source.

**Files to change:** new `ontology/exercise_styles.ttl`, `ontology/ontology.ttl` (add
property definition), `ontology/shapes.ttl` (add SHACL constraint), `DECISIONS.md`.

---

### ADR-079: Functional Fitness DB movement pattern field routes to two FEG properties
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database uses a flat "Movement Pattern #1/2/3"
field to classify exercises. When the full set of 41 unique values was enumerated, it became
clear that the source uses a single field to represent two distinct FEG concepts: movement
patterns and joint actions.

Movement patterns in FEG describe the mechanical structure of an exercise at the gross
movement level — Hip Hinge, Knee Dominant, Horizontal Push, Rotational. These are the
labels a trainer or gym-goer would use to categorise an exercise and are the basis for
substitution logic in the MCP server. Joint actions describe what the body is doing at the
level of individual joints — Hip Extension, Knee Flexion, Shoulder Abduction, Wrist
Extension. These are the precision layer used for clinical exercise programming and injury
constraint modelling.

The source conflates them because it has no ontological distinction between the two layers.
From a pure data standpoint, "Hip Hinge" and "Hip Extension" are both ways of saying
something about what the lower body does — the source field treats them identically. But in
FEG, Hip Hinge maps to `feg:movementPattern feg:HipHinge` while Hip Extension maps to
`feg:jointAction feg:HipExtension`. They are different properties pointing to different
classes.

Additionally, the source includes values with no FEG equivalent: "Other" and "Unsorted*"
carry no information and are dropped. Several joint action values in the source (Shoulder
Scapular Plane Elevation, Spinal Rotational) will need crosswalk review against existing
`joint_actions.ttl` entries to find the right mapping or determine whether new individuals
are needed.

**Decision:** Build a `movement_pattern_crosswalk.csv` with three columns: `source_value`,
`feg_local_name`, and `target_property`. The `target_property` column specifies either
`feg:movementPattern` or `feg:jointAction` for each source value. The ingest script reads
this column and routes each value to the correct RDF property at build time. Values mapped
to `feg:movementPattern` that are not in the current `movement_patterns.ttl` (Anti-Extension,
Anti-Flexion, Anti-Lateral Flexion, Anti-Rotational, Isometric Hold, Loaded Carry, Locomotion,
Lateral Locomotion) require a vocabulary addition ADR and a MINOR bump on
`movement_patterns.ttl` before use. Drop "Other" and "Unsorted*".

**Rationale:** The alternative — mapping all source values to `feg:movementPattern` and
treating joint actions as movement patterns — would corrupt the existing ontological
distinction that underlies the MCP `query_by_joint_action` tool. The routing approach
preserves clean property semantics at the cost of a slightly more complex crosswalk.

**Files to change:** new `sources/functional-fitness-db/mappings/movement_pattern_crosswalk.csv`,
`sources/functional-fitness-db/build.py` (route by target_property column), `DECISIONS.md`.

---

### ADR-080: Functional Fitness DB equipment: flatten primary and secondary into feg:equipment
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database splits equipment into two fields:
Primary Equipment (the load or primary tool) and Secondary Equipment (typically a surface,
support, or secondary load). The question was whether to model this role distinction in the
ontology.

Examining exercises with both fields populated revealed two distinct secondary equipment
roles. In most cases secondary equipment is a setup surface — a flat bench for a Barbell Hip
Thrust, an incline bench for Spider Curls, a Plyo Box for Step Ups. The bench is not what
you're lifting; it's what you're bracing against. In other cases — particularly the large
family of Slider exercises — the secondary equipment is the actual load: Slider Double
Kettlebell Front Rack Lateral Lunge lists Sliders as primary and Kettlebell as secondary,
but the kettlebell is the load being moved. Flattening would make these exercises findable
by "kettlebell" in a way that splitting would not.

The case for two properties (`feg:equipment` and `feg:setupEquipment`) was that it would
allow consumers to distinguish load from surface, and would make the substitution tool
smarter — swapping the load while keeping the setup context. The case against was complexity:
the distinction is meaningful only in a subset of exercises, the setup surface is rarely a
meaningful search filter for any of our four personas, and adding a second equipment property
means maintaining two crosswalks and two SHACL constraints for marginal gain.

**Decision:** Flatten both fields into `feg:equipment`. No role distinction is stored. Both
primary and secondary equipment are treated as required equipment for the exercise. "None"
in the secondary field is skipped. This makes all exercises findable by all their equipment
requirements, which is the primary query pattern for our use cases.

**Alternatives considered:**
- Two properties (`feg:equipment` / `feg:setupEquipment`): rejected. The setup surface is
  not a meaningful search axis for any current persona, and the Slider+load pattern is better
  handled by simply indexing both pieces of equipment under `feg:equipment`.
- Drop secondary equipment entirely: rejected. The Slider + Kettlebell family would become
  unfindable by kettlebell — a real gap for a user filtering by available equipment.

**Files to change:** `sources/functional-fitness-db/mappings/equipment_crosswalk.csv` (new),
`sources/functional-fitness-db/build.py` (merge both fields into feg:equipment), `DECISIONS.md`.

---

### ADR-081: Add lower leg muscles and Anconeus to muscles.ttl (v0.11.0)
**Status:** Accepted

**Context:** Mapping the Functional Fitness Exercise Database surfaced muscle names not
present in `muscles.ttl`: four lower leg muscles (Shins as a region, Extensor Digitorum
Longus, Extensor Hallucis Longus, Tibialis Posterior) and Anconeus. These appear in the
source's Prime Mover, Secondary, and Tertiary Muscle fields for shin-dominant exercises
(toe raises, ankle dorsiflexion work) and elbow extension work respectively.

The existing lower leg structure has `LowerLeg` as a region, `Calves` as a sub-region
(with Gastrocnemius and Soleus), and `TibialisAnterior` as a group directly under
`LowerLeg`. The missing muscles complete the anterior and posterior compartments of the
lower leg — a gap that was acceptable when the only source was free-exercise-db (which
rarely targets these muscles specifically) but becomes visible with a functional fitness
dataset that includes ankle dorsiflexion exercises and shin work.

Anconeus is a small elbow extensor that assists TricepsBrachii during extension. It
appears in the source as a secondary muscle on pressing movements. It is placed as a
`MuscleGroup` under the `Triceps` region — it is anatomically distinct from TricepsBrachii
but functionally in the same family.

**Decision:** Add to `muscles.ttl`:
- `feg:Shins` — MuscleRegion under `feg:LowerLeg`, colloquial term for the anterior
  lower leg compartment
- `feg:ExtensorDigitorumLongus` — MuscleGroup under `feg:Shins`
- `feg:ExtensorHallucisLongus` — MuscleGroup under `feg:Shins`
- `feg:TibialisPosterior` — MuscleGroup under `feg:LowerLeg` (posterior compartment,
  not part of Shins)
- `feg:Anconeus` — MuscleGroup under `feg:Triceps`

MINOR version bump: muscles.ttl 0.10.0 → 0.11.0.

**Files to change:** `ontology/muscles.ttl`, `DECISIONS.md`.

---

### ADR-082: Add Anti-Flexion, Isometric Hold, and Lateral Locomotion to movement_patterns.ttl (v0.6.0)
**Status:** Accepted

**Context:** Mapping the Functional Fitness Exercise Database surfaced three movement
pattern values not in `movement_patterns.ttl`: Anti-Flexion, Isometric Hold, and Lateral
Locomotion. A fourth value, Horizontal Adduction, was resolved by mapping it to the
existing joint action `feg:ShoulderHorizontalAdduction` — it routes to `feg:jointAction`,
not `feg:movementPattern`.

Anti-Flexion is the trunk stability pattern where the spine resists flexion forces — the
reverse of Anti-Extension. The canonical example is a back extension or a Superman hold.
It belongs as a sibling of `feg:AntiExtension` under `feg:TrunkStability`.

Isometric Hold is a pattern where the primary demand is maintaining a static position
under load rather than producing movement through a range of motion. Examples: wall sit,
plank hold, loaded carry (the isometric component). It is distinct from Anti-Extension
and Anti-Rotation, which are specific trunk patterns — Isometric Hold is a broader
category covering any exercise whose defining characteristic is positional maintenance.

Lateral Locomotion describes side-to-side travel through space — lateral shuffles, lateral
bounds, side-stepping patterns. It is a child of `feg:Locomotion`, which already exists
as a parent for forward/backward movement patterns.

**Decision:** Add to `movement_patterns.ttl`:
- `feg:AntiFlexion` — MovementPattern, `skos:broader feg:TrunkStability`
- `feg:IsometricHold` — MovementPattern, top-level (no parent; it is orthogonal to the
  push/pull/hinge/squat taxonomy)
- `feg:LateralLocomotion` — MovementPattern, `skos:broader feg:Locomotion`

MINOR version bump: movement_patterns.ttl 0.5.0 → 0.6.0.

**Files to change:** `ontology/movement_patterns.ttl`, `DECISIONS.md`.

---

### ADR-083: Add novel equipment from Functional Fitness DB to equipment.ttl (v0.2.0)
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database uses 32 equipment values not present
in the current `equipment.ttl`. These range from common gym equipment missing from the
original vocabulary (Bench, Plyo Box, Pull Up Bar, EZ Bar) to specialist tools from
kettlebell sport (Macebell, Clubbell, Indian Club), functional fitness (Bulgarian Bag,
Sandbag, Slam Ball, Wall Ball, Sliders, Sled, Suspension Trainer), and calisthenics
(Parallette Bars, Gymnastic Rings). The existing `equipment.ttl` was built against
free-exercise-db, which used a narrower equipment range.

All additions are additive — no existing concepts are modified. Several items require
notes on scope: Bench is added in three variants (Flat, Incline, Decline) because
equipment selection in exercise programming is bench-type specific; a flat bench and an
incline bench are not interchangeable setup surfaces.

**Decision:** Add all 32 items as `feg:Equipment` named individuals. MINOR version bump:
equipment.ttl 0.1.0 → 0.2.0.

New individuals: AbWheel, BattleRopes, BenchFlat, BenchIncline, BenchDecline,
BulgarianBag, ClimbingRope, Clubbell, EZBar, GravityBoots, GymnasticRings, HeavySandbag,
IndianClub, Landmine, Macebell, Miniband, ParalletteBar, PlyoBox, PullUpBar,
ResistanceBand, Sandbag, SlamBall, SlantBoard, Sled, SledgeHammer, Sliders, Superband,
SuspensionTrainer, Tire, TrapBar, WallBall, WeightPlate.

**Files to change:** `ontology/equipment.ttl`, `DECISIONS.md`.

---

---

### ADR-084: Functional Fitness DB enrichment adapter — known context pattern, soft-trust muscle degrees, and col 31 routing
**Status:** Accepted

**Context:** The Functional Fitness Exercise Database is a structured CSV source with
richer pre-classification than free-exercise-db. Where free-exercise-db provides only
a name and a flat list of primary/secondary muscles, the Functional Fitness DB provides
per-exercise muscle roles (prime, secondary, tertiary), movement patterns, plane of
motion, laterality, combination flag, and an exercise classification field. This creates
a design question for the enrichment adapter: how much of that pre-classified data should
the LLM receive, and in what form?

Three positions were considered for handling the source's pre-classified fields:

**Option A — Hard-trust:** Map source roles directly to enrichment degrees (prime →
PrimeMover, secondary → Synergist, tertiary → Stabilizer) and pass the complete
involvement list as pre-filled output. LLM overrides only for PassiveTarget on mobility
and stretch exercises. This maximally preserves source signal but bakes in whatever
classification errors exist in the source data, and gives the LLM no latitude to correct
degree assignments where the source role is misleading.

**Option B — Soft-trust (chosen):** Pass source fields as structured context in the
user message, not as pre-filled output. The LLM receives the muscle names with their
source roles as strong hints and produces the full `muscle_involvements` list using its
own judgment, keeping source roles as a prior. This is consistent with how free-exercise-db
enrichment uses `primaryMuscles`/`secondaryMuscles` — as signal, not gospel. It lets the
model correct obvious source errors (a secondary that should be PrimeMover, a tertiary
that is PassiveTarget on a stretch) while still benefiting from the richer source
structure.

**Option C — No-trust:** Strip all source roles and treat the crosswalk muscle names as
an unordered list only. Maximum LLM latitude, throws away the most signal.

The same soft-trust logic applies to movement patterns and joint actions resolved from
the crosswalk: they are passed as pre-classified context, and the LLM uses them as the
starting point for the output rather than filling from scratch.

**Fully resolved fields** — where the source value maps to an FEG vocab term without
ambiguity and the LLM has nothing to add — are passed as known constants and the LLM
is instructed to carry them through unchanged:
- `laterality` (col 30): source values are already Bilateral/Unilateral/Contralateral/Ipsilateral
- `is_combination` (col 20): "Combo Exercise" → true, "Single Exercise" → false
- `plane_of_motion` (cols 24–26): "Sagittal Plane" → SagittalPlane, etc.
- `is_compound` (col 29): "Compound" → true, "Isolation" → false (ambiguous values like
  "Pull" are surfaced as a `force_type_hint` and the LLM decides)

**Col 31 (Primary Exercise Classification) routing:** This field conflates exercise
styles with concepts that live in other FEG vocabulary fields. Most values map cleanly
to `feg:ExerciseStyle` named individuals. Two values route elsewhere:
- `Mobility` → passed as a movement pattern hint (Mobility is a `feg:MovementPattern`,
  not an `feg:ExerciseStyle`)
- `Plyometric` → passed as a training modality hint (Plyometrics is a `feg:TrainingModality`)
- `Unsorted*` → dropped

Routing at parse time (rather than passing raw text) keeps the LLM context structured
and avoids the model seeing a value in a "style" position that it knows belongs elsewhere.

**Exercise ID scheme:** The Functional Fitness DB CSV has no stable identifier column.
Exercise names are slugified (non-alphanumeric characters replaced with underscores)
to produce file-safe, human-readable IDs (e.g. "Bulgarian Split Squat" →
`Bulgarian_Split_Squat`). This matches the visual convention of free-exercise-db IDs
and is deterministic from the name. Duplicate names in the source would collide — if
this becomes a problem, a suffix counter or hash can be added.

**Decision:**
- Use soft-trust for muscle roles and movement pattern pre-classifications.
- Pass all resolved known fields as structured context in the user message.
- Route col 31 Mobility → movement pattern hint, Plyometric → training modality hint, Unsorted* → drop.
- Use slugified exercise names as stable IDs.
- The enrichment adapter (`sources/functional-fitness-db/enrich.py`) delegates all LLM
  mechanics to `enrichment/service.py` and handles only source-specific concerns:
  CSV parsing, crosswalk resolution, user message formatting, and file I/O.

**Files changed:** `sources/functional-fitness-db/enrich.py` (created), `DECISIONS.md`.

---

### ADR-085: Add feg:HipFlexors as a MuscleRegion; normalize spaced muscle name variants in validation
**Status:** Accepted

**Context:** During functional-fitness-db enrichment, two recurring failure modes were
identified:

1. The LLM emitted `"HipFlexors"` as a muscle name across multiple exercises. No such
   concept existed in the vocabulary — "Hip Flexors" only appeared as a `skos:altLabel`
   on `feg:Psoas`, which is one hip flexor, not the group.

2. The LLM emitted `"Serratus Anterior"` (human-readable, space-separated) instead of
   the camelCase `"SerratusAnterior"`. The `normalize_casing()` pre-validation function
   in `enrichment/schema.py` already did case-insensitive correction, but its lookup
   stripped nothing other than case — `"serratus anterior"` did not match
   `"serratusanterior"` in the lower_map.

**Decision:**

**HipFlexors vocabulary addition:** Add `feg:HipFlexors` as a `feg:MuscleRegion` and
`skos:topConceptOf feg:MuscleScheme`. "Hip Flexors" is a standard colloquial term used
by gym-goers, coaches, and source datasets. It spans multiple anatomical structures and
warrants a first-class region concept rather than an alias on a single muscle.

Hierarchy changes:
- `feg:Psoas` — `skos:broader` changed from `feg:LowerBack` to `feg:HipFlexors`;
  `skos:altLabel "Hip Flexors"` removed (the concept now lives at its own URI)
- `feg:Sartorius` — `skos:broader` changed from `feg:Quadriceps` to `feg:HipFlexors`
  (Sartorius is not a true quadriceps; it does not extend the knee)
- `feg:RectusFemoris` — retains `skos:broader feg:Quadriceps`; adds
  `skos:related feg:HipFlexors` (dual membership: canonical quad, secondary hip flexor)
- `feg:TensorFasciaeLatae` — retains `skos:broader feg:Abductors`; adds
  `skos:related feg:HipFlexors` (primary abductor, secondary hip flexor)
- `feg:Iliopsoas` — no change; already transitively under HipFlexors via Psoas

`sources/functional-fitness-db/mappings/muscle_crosswalk.csv` updated: "Hip Flexors"
now maps to `HipFlexors` (was `Iliopsoas`), covering 53 source exercises.

**Space-stripping normalizer fix:** `normalize_casing()` extended to try
`raw.replace(" ", "").lower()` as a fallback when the direct `raw.lower()` lookup
misses. Applied to both the `muscle_involvements` path and all list-field vocab
lookups. This makes the validator forgiving of any spaced-out camelCase term the model
returns (e.g. `"Serratus Anterior"` → `SerratusAnterior`, `"Hip Flexors"` →
`HipFlexors`).

Vocabulary version not bumped in this commit — to be done in a batched version bump.

**Files changed:** `ontology/muscles.ttl`, `enrichment/schema.py`,
`sources/functional-fitness-db/mappings/muscle_crosswalk.csv`, `DECISIONS.md`.

---

### ADR-086: Multi-Source Pipeline Rearchitecture
**Status:** Accepted

**Context:** The original pipeline enriches each source independently to completion — each source's `enrich.py` calls the LLM once per exercise, validates, and writes a finished `enriched/*.json` file. When a second source (functional-fitness-db) was added, this produced two independent enrichments of the same exercise with no shared state. Reconciliation was treated as a post-hoc merge problem: compare two finished outputs and pick a winner.

This framing has a fundamental sequencing error. Enrichment was doing two jobs conflated into one: (1) completing sparse source data, and (2) classifying the exercise against the ontology. Those jobs should be separated. Running the LLM twice on the same exercise introduces non-deterministic variance — the same exercise enriched independently from two sources will produce overlapping but not identical outputs, making it impossible to distinguish genuine disagreement from random variance. More critically, the pipeline conflates incompleteness with disagreement: if source A lists three muscles and source B lists five, that looks like a conflict but is actually just coverage difference.

**Decision:** Adopt an identity-first pipeline architecture. The new stage sequence is:

1. `fetch.py` — unchanged; downloads upstream source data
2. `identity.py` — resolves source records into canonical entities using biomechanical similarity; produces entity clusters with confidence scores
3. `canonicalize.py` — aggregates all asserted facts from source records into a canonical sparse layer per entity; detects and classifies conflicts explicitly
4. `reconcile.py` — applies deterministic resolution algebra to produce a single resolved claim per predicate per entity; defers unresolvable conflicts to a triage queue
5. `enrich.py` (rearchitected) — single LLM pass per canonical entity; fills genuine gaps only; inferred claims are tagged separately from asserted ones
6. `build.py` — assembles RDF from resolved and inferred claims; asserted claims always take precedence over inferred

The LLM never arbitrates disagreements. It receives one clean, conflict-free canonical input and fills fields absent from all sources. Every claim in the final graph is traceable to its origin (source, stage, resolution rule).

**Alternatives considered:**
- **Continue per-source enrichment, reconcile post-hoc:** Rejected. Produces non-deterministic variance, conflates incompleteness with disagreement, and makes audit trails difficult.
- **Re-enrich with both sources' data as input context:** Rejected. Non-deterministic; LLM still arbitrates rather than filling gaps.
- **Source precedence (one source always wins):** Rejected. Arbitrary, lossy, and breaks when a third source is added.

**Files to change:** `sources/*/enrich.py`, `sources/*/build.py`, new `pipeline/identity.py`, new `pipeline/canonicalize.py`, new `pipeline/reconcile.py`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, `TODO.md`, `DECISIONS.md`.

---

### ADR-087: SQLite as Intermediate Pipeline Storage
**Status:** Accepted

**Context:** The rearchitected pipeline (ADR-086) introduces multiple intermediate stages — identity clustering, canonical sparse layer, conflict detection, resolution, triage queue — each of which produces structured relational state. The current pattern of one JSON file per exercise is not well-suited to this workload: identity clusters are join queries, conflict detection is a group-by and filter, the triage queue is a filtered view of a conflicts table, and audit queries ("why did this muscle get this degree?") are provenance joins. All of these require hand-rolling joins and indexes in Python when working with JSON files.

**Decision:** Use SQLite for all intermediate pipeline state. Key tables:

- `entities` — one row per canonical entity (`entity_id`, `display_name`, `status`: resolved/deferred)
- `entity_sources` — maps source records to canonical entities (`entity_id`, `source`, `source_id`, `confidence`)
- `possible_matches` — links ambiguous identity candidates (`entity_id_a`, `entity_id_b`, `score`, `status`)
- `claims` — all asserted and inferred claims with provenance (`entity_id`, `predicate`, `value`, `qualifier`, `origin`, `source`, `claim_type`: asserted/inferred, `origin_type`: structured/absent/inferred)
- `conflicts` — detected conflicts over asserted claims (`conflict_id`, `entity_id`, `predicate`, `value`, `description`, `status`: open/resolved/deferred)
- `resolved_claims` — output of reconcile.py (`entity_id`, `predicate`, `value`, `qualifier`, `resolution_method`, `conflict_id`)
- `triage_queue` — deferred conflicts awaiting human review (`conflict_id`, `entity_id`, `description`, `options`, `status`)

Raw LLM responses are retained as JSON files (one per entity) for debuggability — they are large and unstructured and not queried programmatically.

**Alternatives considered:**
- **Extended JSON:** Rejected. Hand-rolled joins, no query language, debugging requires grepping hundreds of files.
- **RDF named graphs:** Rejected. Query complexity for ETL is high; SPARQL across named graphs is verbose and the intermediate pipeline is not a query problem.
- **RDF-star:** Rejected. Tooling support in rdflib and pyoxigraph is experimental; too much risk for a production pipeline.
- **DuckDB:** Rejected. OLAP engine optimised for columnar scans over large analytical datasets; the workload here is pure OLTP (row-level inserts, lookup by entity_id, small aggregations over hundreds of rows). Correct tool for the wrong job.

**Files to change:** New `pipeline/db.py` (schema + connection utilities), `pipeline/identity.py`, `pipeline/canonicalize.py`, `pipeline/reconcile.py`, `sources/*/enrich.py`, `sources/*/build.py`, `DECISIONS.md`.

---

### ADR-088: Identity Resolution Algorithm
**Status:** Accepted

**Context:** When two source records have the same name, they are candidates for the same canonical entity — but name equality alone is a weak signal. "Romanian Deadlift" in one source and "Romanian Deadlift" in another are likely the same exercise, but "Romanian Deadlift" and "Stiff-Leg Deadlift" may describe functionally identical movements with different names. Conversely, "Cable Fly" (chest) and "Cable Fly" (rear delt) are same-named but distinct movements. Collapsing distinct exercises into one canonical entity would contaminate both enrichments; failing to merge genuinely identical exercises wastes enrichment budget and produces duplicate graph nodes.

**Decision:** Compute a weighted similarity score over a feature vector. Biomechanical signals dominate; name and muscle list are weak signals.

Feature vector and weights (approximate; to be calibrated during implementation):
- Movement pattern match (categorical): high weight
- Primary joint actions overlap (Jaccard): high weight
- Laterality match: medium weight
- Equipment overlap (hierarchy-aware — barbell is-a free-weight): medium weight
- Normalised name similarity (string distance + embedding cosine): low weight
- Coarse muscle group overlap: low weight (noisy — the reconciliation data proves this)

Confidence outcomes:
- **High (auto-merge):** Strong agreement across biomechanical signals, no hard contradictions. Records collapsed into one canonical entity.
- **Low (separate entities):** Clear structural mismatch (different primary joint system, different movement pattern). Records kept as separate entities permanently.
- **Ambiguous (defer):** Mixed signals. Records linked by a `possible_matches` row with a confidence score. Each proceeds through independent canonicalization and enrichment. Human triage resolves merge/keep-separate/mark-as-variant-of. Pipeline is not blocked.

After enrichment, similarity can be recomputed with inferred joint actions as additional signal. If two deferred entities converge post-enrichment, the match is promoted to high confidence deterministically.

The `feg:variantOf` relationship is available for cases where two exercises share a pattern-level identity but differ enough in execution to warrant separate nodes (e.g. barbell vs dumbbell Romanian Deadlift). This reduces pressure on identity resolution to be perfect.

**Alternatives considered:**
- **Name equality only:** Rejected. Both false positives (same name, different movement) and false negatives (different name, same movement) are common enough to matter.
- **LLM-based identity resolution:** Rejected. Non-deterministic, expensive, and introduces a dependency on API availability in a stage that should be offline-capable.

**Files to change:** New `pipeline/identity.py`, `pipeline/db.py`, `DECISIONS.md`.

---

### ADR-089: Resolution Algebra
**Status:** Accepted

**Context:** After canonicalization, the claims table contains asserted facts from multiple sources with explicit conflict annotations. Before enrichment, these conflicts must be resolved deterministically into a single canonical claim per predicate per entity. The LLM must not be involved — resolution must be reproducible without API calls and auditable after the fact.

Different predicate families have different semantics and require different resolution strategies. A single rule applied uniformly across all fields produces incorrect results: union over involvement degrees is wrong (you can't union PrimeMover and Synergist), and conservative-degree over muscle lists is wrong (you'd drop muscles one source didn't mention).

**Decision:** Apply rules in the following precedence order per (entity, predicate) group:

1. **Consensus** — all sources assert the same value. Pass through unchanged. No conflict exists.

2. **Union** — set-valued, non-exclusive fields: `muscle_involvements` (muscle presence), `exercise_style`, `movement_patterns`. Take all distinct values asserted by any source. The ancestor validator (already implemented in `enrichment/schema.py`) runs after union to detect double-counting introduced by the merge.

3. **Conservative** — ordered qualifiers where a defined ranking exists. For involvement degrees: `PrimeMover > Synergist > Stabilizer > PassiveTarget`. When sources disagree on degree for the same muscle, take the lower rank. Rationale: overclaiming a muscle's role leads to worse user outcomes than underclaiming.

4. **Coverage gap** — exclusive scalar fields (`is_compound`, `laterality`, `is_combination`) where exactly one source has a non-null value. Treat as union: take the value that exists. This is not a conflict — it is incompleteness in one source.

5. **Defer** — genuinely contradictory exclusive scalars where multiple sources have conflicting non-null values with no structural basis to prefer one; and joint action routing conflicts (primary vs supporting) always defer regardless. Deferred claims enter the triage queue. The resolved claim is written as null and excluded from the graph until resolved.

Post-enrichment: inferred claims (origin_type=inferred) fill fields absent from resolved_claims. They do not overwrite. Asserted-resolved always takes precedence.

Note: a "source priority" rule (ffdb beats fed on scalar fields) was considered and rejected. Under the new architecture, source records without a structured column for a field contribute no claim at all (origin_type=absent), so apparent scalar conflicts between sources are actually coverage gaps resolved by rule 4. Source priority is not needed.

**Alternatives considered:**
- **LLM arbitration at merge time:** Rejected. Non-deterministic, expensive, contradicts the architectural principle that enrichment fills gaps rather than arbitrates.
- **Source priority (hardcoded ffdb > fed):** Rejected. Dissolves into the coverage gap rule under correct analysis; would break when a third source is added.
- **Majority vote:** Rejected. Requires three or more sources; deferred to future ADR when a third source is ingested.

**Files to change:** New `pipeline/reconcile.py`, `pipeline/db.py`, `DECISIONS.md`.

---

### ADR-090: Deprecate Existing Per-Source Enriched Files
**Status:** Accepted

**Context:** Both sources currently have `enriched/` directories containing one JSON file per exercise — 873 files in free-exercise-db and ~743 files in functional-fitness-db. These files were produced by the old per-source enrichment architecture. They conflate asserted source facts with LLM-inferred claims in a single flat object, carry no provenance annotation distinguishing the two, and were produced independently per source rather than per canonical entity. They are structurally incompatible with the new claims-based pipeline (ADR-086, ADR-087).

**Decision:** Delete all existing `enriched/*.json` files from both sources when implementation of the new pipeline begins. Do not attempt to migrate or adapt them.

The cost is manageable:
- Source assertion data (muscles, movement patterns, laterality, etc.) is fully recoverable from the crosswalk CSVs and raw source files — nothing is permanently lost.
- LLM enrichment work will be redone, but under the new architecture each canonical entity is enriched once on richer input (union of both sources' asserted facts). With only 14 cross-source overlaps currently, most canonical entities are 1:1 with source records, so re-enrichment volume is approximately the same.
- The new enrichments will be higher quality: the LLM sees more signal, produces no cross-source variance, and every output claim carries provenance.

Timing: deletion occurs at the start of implementation, not before. Existing files remain as reference material until the new pipeline is ready to produce replacements.

**Alternatives considered:**
- **Migrate existing files to the new schema:** Rejected. The asserted/inferred distinction cannot be recovered retroactively — we cannot know which fields in the existing JSON came from source data vs LLM inference. A migration would produce a provenance-annotated file with incorrect provenance.
- **Keep existing files as a bootstrap cache:** Rejected. Same problem — inferred claims would be incorrectly treated as asserted, corrupting the reconciliation stage.

**Files to change:** `sources/free-exercise-db/enriched/` (delete all), `sources/functional-fitness-db/enriched/` (delete all), `TODO.md`, `DECISIONS.md`.

---

## Open Questions

- **Joint action movement patterns:** `Pull` and `VerticalPush` are poor fits for
  isolation exercises (curls, lateral raises). Whether to add `ElbowFlexion`,
  `ShoulderAbduction`, etc. as movement pattern concepts — and whether these are peers
  to existing patterns or a separate layer — is an open vocabulary design question.
- **Mobility/SoftTissue Prime Mover exemption:** The SHACL `minCount 1` PrimeMover
  constraint is semantically wrong for passive stretches and soft tissue work. Options:
  relax globally for Mobility/SoftTissue exercises, or add a `PassiveTarget` involvement
  degree. ADR required before implementation.
- **movementPattern sh:minCount:** Relaxed to 0 in ADR-044. Should tighten back to 1
  (with Mobility/SoftTissue exemption) once movement pattern coverage criteria are established.
- **Power modality:** Olympic lifts and explosive strength movements are currently
  forced into `Plyometrics`. A `feg:Power` named individual would distinguish them.
- **Cossack squat classification:** Currently Squat in v1. Does lateral plane movement
  warrant a LateralSquat sub-pattern?
- **Push/Pull angle:** Is incline angle best captured as a property (feg:loadAngle)
  or does it need a sub-pattern?
- **Namespace:** Placeholder `https://placeholder.url#` needs a real URI before any
  public release.
