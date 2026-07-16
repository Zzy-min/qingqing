"""Create or restore an atomic SQLite backup for local/single-node deployments."""

from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def create_sqlite_backup(source: Path, destination: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        with dst:
            src.backup(dst)
    return destination


def restore_sqlite_backup(backup: Path, destination: Path) -> None:
    if not backup.is_file():
        raise FileNotFoundError(backup)
    with closing(sqlite3.connect(backup)) as src, closing(sqlite3.connect(destination)) as dst:
        with dst:
            src.backup(dst)


def _default_database() -> Path:
    configured = os.environ.get("QINGQING_DATABASE_PATH")
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "qingqing.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=_default_database())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        if not args.confirm_restore:
            parser.error("--restore requires --confirm-restore")
        safety = args.database.with_suffix(args.database.suffix + ".pre-restore.bak")
        if args.database.exists():
            create_sqlite_backup(args.database, safety)
        restore_sqlite_backup(args.restore, args.database)
        print(f"restored database; safety backup={safety}")
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or args.database.parent / "backups" / f"qingqing-{timestamp}.db"
    create_sqlite_backup(args.database, output)
    print(f"backup created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
