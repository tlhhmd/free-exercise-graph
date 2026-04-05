# Repo Map

```
free-exercise-graph/
  ontology/                        vocabulary and schema files (TTL, independently versioned)
    ontology.ttl                   OWL class definitions, properties, LLM classification guidance
    muscles.ttl                    muscle SKOS hierarchy (region → group → head)
    movement_patterns.ttl          movement pattern SKOS vocabulary
    joint_actions.ttl              46 joint actions across 9 joint groups
    involvement_degrees.ttl        PrimeMover / Synergist / Stabilizer / PassiveTarget
    training_modalities.ttl        Strength / Mobility / Plyometrics / Power / Cardio
    equipment.ttl                  equipment named individuals
    laterality.ttl                 Bilateral / Unilateral / Contralateral / Ipsilateral
    planes_of_motion.ttl           Sagittal / Frontal / Transverse
    exercise_styles.ttl            Bodybuilding / Calisthenics / Powerlifting / etc.
    shapes.ttl                     SHACL validation shapes

  sources/
    free-exercise-db/
      fetch.py                     download exercises.json from upstream
      adapter.py                   normalise source records for the pipeline
      mappings/
        equipment_crosswalk.csv    source equipment strings → feg: local names
      raw/exercises.json           upstream source (read-only)

    functional-fitness-db/
      fetch.py                     download and convert Excel source from upstream
      adapter.py                   normalise source records for the pipeline
      mappings/
        muscle_crosswalk.csv       source muscle strings → feg: local names
        movement_pattern_crosswalk.csv
        equipment_crosswalk.csv
      raw/                         upstream source files (read-only)

  pipeline/
    db.py                          SQLite schema and connection helper
    artifacts.py                   shared helper for exports, raw-response archives, release bundles
    run.py                         canonical runner for rebuilds and stage orchestration
    canonicalize.py                Stage 1: load source records + asserted claims into SQLite
    identity.py                    Stage 2: resolve source records into canonical entities
    reconcile.py                   Stage 3: deterministic conflict resolution (no LLM)
    enrich.py                      Stage 4: LLM enrichment pass — fills gaps in resolved claims
    build.py                       Stage 5: assemble graph.ttl from resolved + inferred claims
    validate.py                    data quality scorecard (validity / uniqueness / integrity / timeliness / completeness)
    triage.py                      interactive review queue for ambiguous identity matches
    db_backup.py                   snapshot/restore helper for pipeline.db
    export_enrichment.py           portable JSONL export of paid-for enrichment state
    import_enrichment.py           restore exported enrichment into a deterministic rebuild
    release_bundle.py              freeze DB + graph + scorecard into a timestamped bundle
    pipeline.db                    SQLite intermediate store (gitignored)
    backups/                       SQLite snapshots created before risky resets
    exports/                       portable JSONL enrichment exports
    artifacts/raw_responses/       archived raw LLM inputs/outputs per enrichment run

  enrichment/
    service.py                     ontology loading, prompt assembly, LLM response parsing
    providers.py                   LLM provider adapters (Anthropic, Gemini) with usage normalisation
    schema.py                      Pydantic output model — enforces ontology constraints at parse time
    prompt_template.md             system prompt template with <<<placeholder>>> slots
    prompt_builder.py              renders prompt_template.md from live ontology graphs
    _vocab.py                      vocab extraction utilities

  scripts/
    build_similarity_graph.py      offline RDF → weighted exercise similarity graph build
    build_substitute_ui.py         offline similarity → substitute presentation artifact build
    lib/
      rdf_extract.py               exercise feature extraction from RDF/Turtle
      feature_normalize.py         canonical feature normalization for graph build
      similarity.py                weighted pairwise scoring and neighbor selection
      community.py                 Louvain community detection helpers
      export_json.py               stable JSON writer helpers
      substitute_ui.py             bucket, dedupe, and reason-string logic for substitute UX

  data/generated/                  generated similarity and substitute artifacts (derived)
    exercise_features.json         canonical feature projection per exercise
    exercise_similarity_edges.json sparse exported similarity edges
    exercise_neighbors.json        top neighbors per exercise
    exercise_communities.json      community membership export
    build_metrics.json             graph build diagnostics
    exercise_substitute_ui.json    app-facing substitute buckets + reasons
    exercise_substitute_ui_debug.json optional debug metadata for bucket decisions

  evals/                           canonical gold workbook generator, workbook, and eval scorer
  queries/                         example SPARQL discovery queries
  app/
    README.md                      app-specific guide: build, preview, deploy, product roadmap
    build_site.py                  export app/data.json + app/vocab.json and copy substitute UI artifact
    build_observatory.py           export Builder View / observatory payload for curated exercises
    index.html                     static app shell
    style.css                      static app visual system
    app.js                         client-side state, filtering, and interactions
    data.json                      committed exercise payload for GitHub Pages
    vocab.json                     committed vocabulary payload for GitHub Pages
    exercise_substitute_ui.json    committed substitute presentation artifact for GitHub Pages
    observatory.json               committed Builder View payload for GitHub Pages
  docs/
    index.md                       canonical docs landing page and task router
    quickstart_graph.md            shortest path to a deterministic local graph build
    quickstart_mcp.md              shortest path to Claude Desktop MCP usage
    quickstart_app.md              shortest path to local app rebuild + preview
    troubleshooting.md             stale-state, rebuild, and missing-artifact guide
    system_contracts.md            source-of-truth boundaries, reset/replay semantics
    full_run_playbook.md           step-by-step safe runbook for local full runs
    sqlite_data_model.md           SQLite table dictionary, ERD, and RDF mapping
    quality_surfaces.md            SHACL vs validate.py vs CI
    triage_workflow.md             human-in-the-loop review and restamp loop
    reconciliation_example.md      worked example: Dead Bug across all pipeline stages
  mcp_server.py                    MCP server: 5 tools backed by pyoxigraph in-process
  test_shacl.py                    SHACL constraint test harness (14 tests)
  constants.py                     single source of truth for FEG_NS namespace
  codexlog.md                      refactor log: what changed and why
  DECISIONS.md                     full ADR history
  TODO.md                          open items
  LESSONS_LEARNED.md               meta-level project takeaways
  pipeline_playbook.ipynb          operator notebook for rebuild and export flows
```
