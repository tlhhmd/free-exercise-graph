#!/usr/bin/env bash
# refresh.sh — Rebuild the graph and restart the MCP server.
# Run from the project root after enriching or re-enriching exercises.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building graph..."
python3 "$SCRIPT_DIR/sources/free-exercise-db/build.py"

echo "Restarting MCP server..."
if pkill -f mcp_server.py 2>/dev/null; then
    echo "MCP server stopped — Claude Desktop will reload it automatically."
else
    echo "MCP server was not running."
fi
