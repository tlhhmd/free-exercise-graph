#!/usr/bin/env python3
"""
pipeline/db_backup.py

Backup and restore helper for pipeline/pipeline.db.

This exists because paid-for enrichment state currently lives in SQLite.
If you want to preserve inferred_claims + enrichment_stamps before a reset or
experimental refactor, snapshot the DB first.

Usage:
    python3 pipeline/db_backup.py backup
    python3 pipeline/db_backup.py list
    python3 pipeline/db_backup.py restore --latest --yes
    python3 pipeline/db_backup.py restore pipeline/backups/pipeline-20260324-101500.db --yes
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.db import DB_PATH, reset_db

BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(src_path: Path, dest_path: Path) -> None:
    src = _connect(src_path)
    dest = _connect(dest_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()


def _backup_name(prefix: str = "pipeline") -> str:
    return f"{prefix}-{_timestamp()}.db"


def list_backups() -> list[Path]:
    backup_dir = _ensure_backup_dir()
    return sorted(backup_dir.glob("*.db"))


def backup_db(db_path: Path = DB_PATH, dest: Path | None = None) -> Path:
    if not db_path.exists():
        raise SystemExit(f"SQLite DB not found at {db_path}")

    backup_dir = _ensure_backup_dir()
    dest_path = dest or backup_dir / _backup_name()
    if dest_path.exists():
        raise SystemExit(f"Refusing to overwrite existing backup: {dest_path}")

    _snapshot(db_path, dest_path)
    return dest_path


def resolve_backup(path_arg: str | None, latest: bool) -> Path:
    if latest:
        backups = list_backups()
        if not backups:
            raise SystemExit(f"No backups found in {BACKUP_DIR}")
        return backups[-1]
    if not path_arg:
        raise SystemExit("Provide a backup path or use --latest")
    path = Path(path_arg)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise SystemExit(f"Backup file not found: {path}")
    return path


def restore_db(
    backup_path: Path,
    *,
    db_path: Path = DB_PATH,
    create_pre_restore_backup: bool = True,
) -> Path | None:
    pre_restore_backup = None
    if db_path.exists() and create_pre_restore_backup:
        pre_restore_backup = backup_db(db_path=db_path, dest=_ensure_backup_dir() / _backup_name("pre-restore"))

    reset_db(db_path)
    _snapshot(backup_path, db_path)
    return pre_restore_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup and restore pipeline SQLite state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a timestamped SQLite backup")
    backup_parser.add_argument("--db-path", type=Path, default=DB_PATH)
    backup_parser.add_argument("--dest", type=Path, default=None, help="Optional explicit destination path")

    list_parser = subparsers.add_parser("list", help="List known SQLite backups")
    list_parser.add_argument("--dir", type=Path, default=BACKUP_DIR)

    restore_parser = subparsers.add_parser("restore", help="Restore SQLite state from a backup")
    restore_parser.add_argument("backup_path", nargs="?", default=None)
    restore_parser.add_argument("--latest", action="store_true", help="Restore the newest backup in pipeline/backups")
    restore_parser.add_argument("--db-path", type=Path, default=DB_PATH)
    restore_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that you want to overwrite the current pipeline DB",
    )
    restore_parser.add_argument(
        "--no-pre-restore-backup",
        action="store_true",
        help="Skip creating a safety backup of the current DB before restore",
    )

    args = parser.parse_args()

    if args.command == "backup":
        dest = backup_db(db_path=args.db_path, dest=args.dest)
        print(f"Created backup: {dest}")
        return

    if args.command == "list":
        backup_dir = args.dir
        backups = sorted(backup_dir.glob("*.db")) if backup_dir.exists() else []
        if not backups:
            print(f"No backups found in {backup_dir}")
            return
        for path in backups:
            print(path)
        return

    if args.command == "restore":
        if not args.yes:
            raise SystemExit("Restore is destructive. Re-run with --yes to confirm.")
        backup_path = resolve_backup(args.backup_path, args.latest)
        pre_restore = restore_db(
            backup_path,
            db_path=args.db_path,
            create_pre_restore_backup=not args.no_pre_restore_backup,
        )
        print(f"Restored SQLite DB from: {backup_path}")
        if pre_restore is not None:
            print(f"Safety backup of previous DB written to: {pre_restore}")
        return


if __name__ == "__main__":
    main()
