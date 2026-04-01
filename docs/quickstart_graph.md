# Quickstart: Build The Graph

Use this when you want a deterministic local build with no LLM calls.

If you need backup, restore, enrichment, or release-bundle guidance, use the
full operator runbook instead:
[full_run_playbook.md](/Users/talha/Code/free-exercise-graph/docs/full_run_playbook.md).

---

## 1. Install

```bash
cd /Users/talha/Code/free-exercise-graph
pip install -e .
```

---

## 2. Build

```bash
python3 pipeline/run.py --to build
```

This rebuilds the deterministic stages:

1. `canonicalize`
2. `identity`
3. `reconcile`
4. `build`

It does not spend API tokens.

---

## 3. Validate

```bash
python3 pipeline/validate.py --verbose
python3 test_shacl.py
```

What you should see:

- `pipeline/validate.py` completes without obvious structural failures
- `test_shacl.py` passes all fixture checks

---

## 4. What To Do Next

- **Run the MCP server:** [quickstart_mcp.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_mcp.md)
- **Build the static app:** [quickstart_app.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_app.md)
- **Understand rebuild boundaries:** [system_contracts.md](/Users/talha/Code/free-exercise-graph/docs/system_contracts.md)
- **Debug stale outputs or missing artifacts:** [troubleshooting.md](/Users/talha/Code/free-exercise-graph/docs/troubleshooting.md)
