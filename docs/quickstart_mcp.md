# Quickstart: MCP Server

Use this when you want Claude Desktop to query the built graph directly.

This assumes you already have a current `graph.ttl`. If not, start with
[quickstart_graph.md](/Users/talha/Code/free-exercise-graph/docs/quickstart_graph.md).

---

## 1. Build The Graph

```bash
cd /Users/talha/Code/free-exercise-graph
python3 pipeline/run.py --to build
```

---

## 2. Add The Claude Desktop Config

Edit `~/.claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "free-exercise-graph": {
      "command": "python3",
      "args": ["/absolute/path/to/free-exercise-graph/mcp_server.py"]
    }
  }
}
```

Replace the path with your local checkout path.

---

## 3. Restart Claude Desktop

After restart, the server should load `graph.ttl` in-process through
`pyoxigraph`.

---

## 4. Try First Queries

Example prompts:

- `Find me compound hip hinge exercises I can do with just a barbell`
- `What are good substitutes for Romanian Deadlift if I do not have a barbell?`
- `Show me the full muscle hierarchy for the posterior chain`
- `What exercises involve shoulder abduction as a primary joint action?`

---

## 5. If Something Looks Wrong

- Rebuild the graph: `python3 pipeline/run.py --to build`
- Check your config path points to the right checkout
- Use [troubleshooting.md](/Users/talha/Code/free-exercise-graph/docs/troubleshooting.md) for rebuild and stale-state guidance
