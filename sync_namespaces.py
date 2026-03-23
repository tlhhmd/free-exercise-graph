#!/usr/bin/env python3
"""
sync_namespaces.py — Propagate the FEG namespace from constants.py to all TTL,
SPARQL, and Python files in the project.

Run this after updating FEG_NS in constants.py to migrate the namespace URI
everywhere without manual search-and-replace.

Dry-run by default — pass --apply to write changes.

Usage:
    python3 sync_namespaces.py                                  # dry run
    python3 sync_namespaces.py --apply                          # apply changes
    python3 sync_namespaces.py --from https://old.ns# --apply  # custom source
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS

# File extensions to scan
EXTENSIONS = {".ttl", ".rq", ".py", ".md", ".sh"}

# Directories and files to skip entirely
SKIP_DIRS = {".git", ".ruff_cache", ".venv", "venv", "__pycache__", ".pytest_cache"}
SKIP_FILES = {"sync_namespaces.py", "constants.py"}


def _files(root: Path) -> list[Path]:
    result = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in EXTENSIONS and path.name not in SKIP_FILES:
            result.append(path)
    return sorted(result)


def sync(old_ns: str, new_ns: str, apply: bool) -> None:
    if old_ns == new_ns:
        print("Source and target namespaces are identical — nothing to do.")
        return

    print(f"  from: {old_ns}")
    print(f"    to: {new_ns}")
    print(f"  mode: {'APPLY' if apply else 'DRY RUN'}\n")

    changed = []
    for path in _files(PROJECT_ROOT):
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if old_ns not in original:
            continue

        updated = original.replace(old_ns, new_ns)
        count = original.count(old_ns)
        rel = path.relative_to(PROJECT_ROOT)
        changed.append((rel, count))

        if apply:
            path.write_text(updated, encoding="utf-8")

    if not changed:
        print("No files contain the source namespace.")
        return

    action = "Updated" if apply else "Would update"
    for rel, count in changed:
        print(f"  {action}: {rel}  ({count} occurrence{'s' if count > 1 else ''})")

    print(f"\n{'Updated' if apply else 'Would update'} {len(changed)} file(s).")
    if not apply:
        print("Re-run with --apply to write changes.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync FEG namespace across all project files.")
    parser.add_argument(
        "--from",
        dest="old_ns",
        default="https://placeholder.url#",
        help="Source namespace to replace (default: https://placeholder.url#)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry run)",
    )
    args = parser.parse_args()

    sync(old_ns=args.old_ns, new_ns=FEG_NS, apply=args.apply)


if __name__ == "__main__":
    main()
