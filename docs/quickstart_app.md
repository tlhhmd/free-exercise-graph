# Quickstart: Static App

Use this when you want to rebuild the GitHub Pages app locally, including the
substitute UI artifact and Builder View payload.

This assumes the deterministic pipeline state is current. If not, start with
[quickstart_graph.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_graph.md).

---

## 1. Build The Graph

```bash
cd /Users/talha/Code/free-exercise-graph
python3 pipeline/run.py --to build
```

---

## 2. Build App Artifacts

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
python3 app/build_observatory.py --out app
```

What this produces:

- `app/data.json`
- `app/vocab.json`
- `app/exercise_substitute_ui.json`
- `app/observatory.json`

---

## 3. Preview Locally

```bash
python3 -m http.server 8000
```

Then open [http://localhost:8000/app/](http://localhost:8000/app/).

Use a hard refresh after JSON or CSS changes:

- `Cmd + Shift + R`

---

## 4. What To Verify

- exercises load and filter correctly
- substitute sections render
- Builder View appears for curated observatory exercises
- vocabulary and anatomy tabs still load

---

## 5. Related Docs

- Full app guide: [README.md](/Users/talha/Code/free-exercise-graph/app/README.md)
- App field provenance: [app_field_provenance.md](/Users/talha/Code/free-exercise-graph/docs/app_field_provenance.md)
- Troubleshooting: [troubleshooting.md](/Users/talha/Code/free-exercise-graph/docs/troubleshooting.md)
