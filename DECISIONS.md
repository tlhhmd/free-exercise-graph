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
(read-only). Handled post-ingestion by `repair_03_dedup_involvements_cross_degree.sparql`
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

1. **repair_01_use_group_level.sparql** — useGroupLevel collapse: replaces any
   `MuscleHead` with its parent `MuscleGroup` when the group carries
   `feg:useGroupLevel true`. Motivated by the LLM consistently using
   `RhomboidMajor`/`RhomboidMinor` as prime movers on row exercises despite the
   prompt instruction.

2. **repair_02_dedup_involvements.sparql** — same-degree dedup: after the
   useGroupLevel collapse, two involvements from the same exercise may point to
   the same muscle with the same degree. Removes the duplicate, keeping the
   lower URI for deterministic output.

3. **repair_03_dedup_involvements_cross_degree.sparql** — cross-degree dedup:
   removes the lower-priority involvement when the same muscle appears at multiple
   degrees within a single exercise (PrimeMover > Synergist > Stabilizer). Handles
   the 9 upstream exercises where a muscle appears in both `primaryMuscles` and
   `secondaryMuscles` (documented in ADR-044).

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
