import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4


def test_sqlite_store_records_current_schema_version():
    from qingqing_v1.store import SqliteStore

    path = Path(__file__).resolve().parents[1] / ".test-tmp" / f"schema-{uuid4().hex}.db"
    try:
        store = SqliteStore(path)
        assert store.schema_version() == 1
        store.db.close()
    finally:
        path.unlink(missing_ok=True)


def test_sqlite_backup_is_a_readable_database():
    from scripts.sqlite_backup import create_sqlite_backup

    folder = Path(__file__).resolve().parents[1] / ".test-tmp"
    source = folder / f"source-{uuid4().hex}.db"
    backup = folder / f"backup-{uuid4().hex}.db"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(source)) as db:
            with db:
                db.execute("CREATE TABLE proof(value TEXT)")
                db.execute("INSERT INTO proof(value) VALUES('ok')")
        create_sqlite_backup(source, backup)
        with closing(sqlite3.connect(backup)) as db:
            assert db.execute("SELECT value FROM proof").fetchone()[0] == "ok"
    finally:
        source.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)
