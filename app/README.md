# Static App

This directory contains the full GitHub Pages product surface for `free-exercise-graph`.

Everything app-related now lives here:

- [build_site.py](/Users/talha/Code/free-exercise-graph/app/build_site.py): exports app-ready JSON from `pipeline.db` or `graph.ttl`
- [index.html](/Users/talha/Code/free-exercise-graph/app/index.html): static shell
- [style.css](/Users/talha/Code/free-exercise-graph/app/style.css): visual system
- [app.js](/Users/talha/Code/free-exercise-graph/app/app.js): client-side state, filtering, and interaction logic
- [illustrations/anatomy-front.svg](/Users/talha/Code/free-exercise-graph/app/illustrations/anatomy-front.svg): front anatomy illustration layer
- [illustrations/anatomy-back.svg](/Users/talha/Code/free-exercise-graph/app/illustrations/anatomy-back.svg): back anatomy illustration layer
- [data.json](/Users/talha/Code/free-exercise-graph/app/data.json): committed exercise payload
- [vocab.json](/Users/talha/Code/free-exercise-graph/app/vocab.json): committed vocabulary payload

The app is intentionally static-first:

- expensive ontology work happens at build/export time
- the browser only does fast client-side filtering, state management, and rendering
- deployment is just publishing this directory to GitHub Pages

Field provenance matters here:

- graph-native vs normalized vs heuristic app fields are tracked in [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md)
- the long-term goal is to move as much useful semantics as possible out of ad hoc product heuristics and into graph-governed outputs

Current V2 surfaces:

- deterministic search that understands ontology labels like modalities and movement patterns
- simpler exercise cards with graph-grounded summaries
- cleaner filter panels that behave like one group instead of stacked drawers
- richer detail sheets focused on graph-backed anatomy, patterns, joint actions, equipment, and substitutes
- vocabulary descriptions for patterns and modalities
- URL-synced app state for sharing and restore

Illustration note:

- the anatomy art now lives in the two SVG files under [illustrations](/Users/talha/Code/free-exercise-graph/app/illustrations)
- designers can redraw shapes and labels there directly
- keep the `muscle-region` class plus `data-muscles` / `data-label` attributes intact so the app bindings continue to work

---

## Local Preview

From the repo root:

```bash
python3 -m http.server 8000
```

Then open:

- [http://localhost:8000/app/](http://localhost:8000/app/)

Use a hard refresh after CSS or JSON changes:

- `Cmd + Shift + R`

---

## Regenerating App Data

### From the built graph

Use this when `graph.ttl` is the source you want to publish:

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph
```

### From the live pipeline DB

Use this during local development when `pipeline/pipeline.db` is the freshest source:

```bash
python3 app/build_site.py
```

### Explicit output directory

```bash
python3 app/build_site.py --from-graph --out app
```

---

## Typical Update Flow

```bash
python3 pipeline/run.py --to build
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph
python3 -m http.server 8000
```

After checking locally, commit:

- [app/index.html](/Users/talha/Code/free-exercise-graph/app/index.html)
- [app/style.css](/Users/talha/Code/free-exercise-graph/app/style.css)
- [app/app.js](/Users/talha/Code/free-exercise-graph/app/app.js)
- [app/data.json](/Users/talha/Code/free-exercise-graph/app/data.json)
- [app/vocab.json](/Users/talha/Code/free-exercise-graph/app/vocab.json)

GitHub Pages deploys this directory directly via [.github/workflows/deploy.yml](/Users/talha/Code/free-exercise-graph/.github/workflows/deploy.yml).

---

## Product Direction

For field-level provenance and promotion targets, see [docs/app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md).

The substitute UX now reads from [exercise_substitute_ui.json](/Users/talha/Code/free-exercise-graph/app/exercise_substitute_ui.json), a build-time presentation artifact derived from the Phase 1 similarity graph outputs. It intentionally separates:

- closest direct replacements
- different-equipment alternatives
- broader family exploration

The browser does not compute substitute buckets or dedupe variants at runtime.
