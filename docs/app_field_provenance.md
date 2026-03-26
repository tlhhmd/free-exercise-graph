# App Field Provenance

This document makes a strict distinction between:

- graph-native fields
- graph-backed normalized fields
- product heuristics derived from graph facts
- app-only UX behavior

The current static app intentionally uses a heuristic layer to stay fast and useful on GitHub Pages.
The long-term goal is to shrink that heuristic layer and move as much semantics as possible into the graph or into graph-governed computed outputs.

Primary implementation files:

- [app/build_site.py](/Users/talha/Code/free-exercise-graph/app/build_site.py)
- [app/app.js](/Users/talha/Code/free-exercise-graph/app/app.js)

---

## Source Classes

### 1. Graph-native

These are fields that correspond directly to facts asserted in the graph or pipeline knowledge model.
They may be exported into app JSON, but the meaning already exists in the graph.

### 2. Graph-backed normalized

These are not raw one-to-one graph fields, but they are still close to graph truth.
They mostly:

- merge resolved + inferred claims
- normalize hierarchy
- collapse heads to groups when ontology governance says to do so
- deduplicate ancestors

These should be treated as governed projections of graph semantics, not freehand UI inventions.

### 3. Product heuristic

These are deterministic summaries created for product use.
They are currently useful, but they are not yet first-class graph semantics.

Examples:

- `spinalLoad`
- `bodyFocus`
- `skillLevel`
- `shoulder_friendly`

These are the main candidates for future graph promotion or ontology-backed computed layers.

### 4. App-only UX behavior

These are interface decisions.
They are not ontology terms and should not be mistaken for graph-native concepts.

---

## Exercise Payload Fields

| Field | Current Status | Current Source | Notes | Promotion Target |
| --- | --- | --- | --- | --- |
| `id` | Graph-native | canonical entity id | canonical exercise identifier | keep as-is |
| `name` | Graph-native | canonical exercise label | display label from entity | keep as-is |
| `patterns` | Graph-native | inferred `movement_pattern` claims | exported as local ids | keep as-is |
| `primaryJA` | Graph-native | inferred `primary_joint_action` claims | exported as local ids | keep as-is |
| `supportingJA` | Graph-native | inferred `supporting_joint_action` claims | exported as local ids | keep as-is |
| `equipment` | Graph-native | resolved `equipment` claims | deterministic source-side fact | keep as-is |
| `laterality` | Graph-native | inferred `laterality` claim | exported as local id | keep as-is |
| `modality` | Graph-native | inferred `training_modality` claim | exported as local id | keep as-is |
| `style` | Graph-native | inferred `exercise_style` claims | currently light-use in app | keep as-is |
| `compound` | Graph-native | inferred `is_compound` | boolean projection of graph fact | keep as-is |
| `combination` | Graph-native | inferred `is_combination` | boolean projection of graph fact | keep as-is |
| `muscles` | Graph-backed normalized | merged `resolved_claims` + `inferred_claims` plus ontology hierarchy normalization | respects `feg:useGroupLevel`, degree priority, ancestor stripping | likely keep as governed export, not raw graph duplication |
| `visualRegions` | Product heuristic | `_derive_visual_regions()` in [app/build_site.py](/Users/talha/Code/free-exercise-graph/app/build_site.py) | maps ontology muscle nodes to simplified UI regions via `_REGION_ALIASES` | candidate for governed computed layer or explicit region projection |
| `bodyFocus` | Product heuristic | `_derive_body_focus()` | coarse bucket like `upper`, `lower`, `posterior_chain` | candidate for graph-backed classification or computed export |
| `spinalLoad` | Product heuristic | `_derive_spinal_load()` | heuristic from patterns, equipment, modality, compoundness, regions | candidate for future ontology concept only after ADR |
| `explosiveness` | Product heuristic | `_derive_explosiveness()` | heuristic from modality and pattern cues | candidate for graph-backed computed layer |
| `skillLevel` | Product heuristic | `_derive_skill_level()` | heuristic from laterality, equipment, compoundness, combination | keep heuristic for now; promote only if modeling use case becomes clear |
| `builderRoles` | Product heuristic | `_derive_builder_roles()` | product slot mapping such as `squat`, `hinge`, `push` | candidate for app-level computed layer; not necessarily ontology term |
| `movementFamily` | Product heuristic | `_derive_movement_family()` | one coarse family chosen from patterns | candidate to replace with governed query view |
| `compareAttributes` | Product heuristic / denormalized export | `_decorate_exercises()` | app performance object flattened for compare mode | keep as export convenience, not ontology target |
| `whyHints` | Product heuristic / presentation | `_derive_why_hints()` | product-facing explanation strings | do not promote directly; replace with graph-grounded explanation templates over time |
| `practicalNote` | Product heuristic / presentation | `_derive_practical_note()` | high-level product copy | do not promote directly |

---

## Vocabulary Payload Fields

| Field | Current Status | Current Source | Notes | Promotion Target |
| --- | --- | --- | --- | --- |
| `patterns[].id/label/parent/depth/count` | Graph-native + graph rollup | ontology + count rollups | true ontology hierarchy with app counts | keep as-is |
| `patterns[].description` | Product/editorial copy | `_PATTERN_COPY` in [app/build_site.py](/Users/talha/Code/free-exercise-graph/app/build_site.py) | explanatory text for UI | candidate for ontology annotations later |
| `modalities[].id/label/count` | Graph-native + graph rollup | ontology + counts | true modality vocabulary | keep as-is |
| `modalities[].description` | Product/editorial copy | `_MODALITY_COPY` | UI explainer text | candidate for ontology annotations later |
| `equipment[]` | Graph-native + graph rollup | ontology + counts | exported directly | keep as-is |
| `joints[]` | Graph-native + graph rollup | ontology + counts | exported directly | keep as-is |
| `muscles.regions[]` | Graph-native hierarchy + count rollup | ontology + counts | region/group/head/muscle hierarchy | keep as-is |
The current app no longer exposes preset chips.
Search is now a direct match over exported exercise properties and ontology-backed labels.

If product shortcuts return later, they should be tracked here explicitly as UI behavior rather than being conflated with ontology vocabulary.

---

## Guidance For Future Work

### Safe to keep outside the graph for now

- `compareAttributes`
- `whyHints`
- `practicalNote`
- share-state / URL serialization
- card layout metadata

These are presentation-layer concerns.

### Strong candidates for graph-governed computed exports

- `visualRegions`
- `bodyFocus`
- `explosiveness`
- `builderRoles`
- maybe `movementFamily`

These are useful enough that they may deserve a governed deterministic layer closer to the graph.

### Requires caution and likely ADR before ontology promotion

- `spinalLoad`
- `skillLevel`
- product notions like “shoulder friendly”

These are product-useful, but they are not obviously ontology concepts yet.
Promoting them too early would risk baking opinionated coaching/product abstractions into the domain model.

---

## Working Principle

When adding a new app field, decide explicitly:

1. Is this already in the graph?
2. If not, is it a governed projection of graph facts?
3. If not, is it only a product heuristic?
4. If it is heuristic, do we expect to eventually promote it into the graph or keep it firmly in the UI layer?

If the answer to `4` is “promote,” add the field here and track the migration path before the heuristic spreads further.
