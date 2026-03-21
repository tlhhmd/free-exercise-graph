#!/usr/bin/env python3
"""
fetch.py — Download the raw exercise dataset from yuhonas/free-exercise-db.

Usage:
    python3 sources/free-exercise-db/fetch.py

Downloads exercises.json from the upstream GitHub repository and writes it to
raw/exercises.json (relative to this script). The destination file is treated
as read-only source data — do not modify it manually.

Source URL is documented in sources/free-exercise-db/catalog.ttl
(dcat:downloadURL on the feg:SourceDistribution resource).
"""

from pathlib import Path

import httpx

SOURCE_URL = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/refs/heads/main/dist/exercises.json"
DEST = Path(__file__).resolve().parent / "raw" / "exercises.json"


def main():
    print(f"Fetching {SOURCE_URL}")
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(SOURCE_URL)
        response.raise_for_status()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(response.content)
    print(f"Written: {DEST} ({len(response.content):,} bytes)")


if __name__ == "__main__":
    main()
