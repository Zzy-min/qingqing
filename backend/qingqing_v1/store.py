import json
import os
import sqlite3
import threading
from pathlib import Path


DEFAULT_PREFERENCES = {
    "advanced_mode_enabled": False,
    "credential_preference": "platform_first",
    "memory_enabled": True,
    "style_notes": "",
    "avoid_notes": "",
    "preferred_tone": "",
}


class SqliteStore:
    """Persistent per-user repository for the QingQing v1 account domain."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'free');
        CREATE TABLE IF NOT EXISTS identities(email TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS auth_codes(id TEXT PRIMARY KEY, email TEXT NOT NULL, code_hash TEXT NOT NULL,
          expires_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS credentials(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS custom_models(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, idempotency_key TEXT, payload TEXT NOT NULL,
          UNIQUE(user_id, idempotency_key));
        CREATE TABLE IF NOT EXISTS invocations(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_items(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tool_calls(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
        """)

    def reset(self):
        with self.lock:
            for table in (
                "auth_codes",
                "identities",
                "artifacts",
                "ledger",
                "invocations",
                "runs",
                "custom_models",
                "credentials",
                "preferences",
                "memory_items",
                "tool_calls",
                "users",
            ):
                self.db.execute(f"DELETE FROM {table}")
            self.db.commit()

    def ensure_user(self, uid: str, plan: str = "free"):
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO users(id,plan) VALUES(?,?)", (uid, plan))
            self.db.commit()

    def get_user(self, uid: str):
        row = self.db.execute("SELECT id,plan FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def set_plan(self, uid: str, plan: str):
        self.ensure_user(uid)
        with self.lock:
            self.db.execute("UPDATE users SET plan=? WHERE id=?", (plan, uid))
            self.db.commit()

    def user_for_email(self, email: str):
        row = self.db.execute("SELECT user_id FROM identities WHERE email=?", (email,)).fetchone()
        return row[0] if row else None

    def bind_email(self, email: str, uid: str):
        self.ensure_user(uid)
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO identities(email,user_id) VALUES(?,?)", (email, uid))
            self.db.commit()

    def count_recent_auth_codes(self, email: str, since: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM auth_codes WHERE email=? AND created_at>=?", (email, since)).fetchone()[0]

    def save_auth_code(self, value: dict):
        with self.lock:
            self.db.execute(
                "INSERT INTO auth_codes(id,email,code_hash,expires_at,consumed,attempts,created_at) VALUES(?,?,?,?,0,0,?)",
                (value["id"], value["email"], value["code_hash"], value["expires_at"], value["created_at"]),
            )
            self.db.commit()

    def latest_auth_code(self, email: str):
        row = self.db.execute("SELECT * FROM auth_codes WHERE email=? ORDER BY created_at DESC LIMIT 1", (email,)).fetchone()
        return dict(row) if row else None

    def increment_auth_attempt(self, code_id: str):
        with self.lock:
            self.db.execute("UPDATE auth_codes SET attempts=attempts+1 WHERE id=?", (code_id,)); self.db.commit()

    def consume_auth_code(self, code_id: str):
        with self.lock:
            self.db.execute("UPDATE auth_codes SET consumed=1 WHERE id=?", (code_id,)); self.db.commit()

    def save_preferences(self, uid: str, value: dict):
        self.ensure_user(uid)
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES(?,?)", (uid, json.dumps(value)))
            self.db.commit()

    def get_preferences(self, uid: str):
        row = self.db.execute("SELECT payload FROM preferences WHERE user_id=?", (uid,)).fetchone()
        return {**DEFAULT_PREFERENCES, **(json.loads(row[0]) if row else {})}

    def _save(self, table: str, uid: str, value: dict):
        self.ensure_user(uid)
        with self.lock:
            if table == "runs":
                self.db.execute(
                    "INSERT OR REPLACE INTO runs(id,user_id,idempotency_key,payload) VALUES(?,?,?,?)",
                    (value["id"], uid, value.get("idempotency_key"), json.dumps(value)),
                )
            elif table in {"invocations", "ledger", "artifacts"}:
                self.db.execute(
                    f"INSERT OR REPLACE INTO {table}(id,user_id,run_id,payload) VALUES(?,?,?,?)",
                    (value["id"], uid, value["run_id"], json.dumps(value)),
                )
            elif table in {"memory_items", "tool_calls", "credentials", "custom_models"}:
                self.db.execute(
                    f"INSERT OR REPLACE INTO {table}(id,user_id,payload) VALUES(?,?,?)",
                    (value["id"], uid, json.dumps(value)),
                )
            else:
                self.db.execute(f"INSERT OR REPLACE INTO {table}(id,user_id,payload) VALUES(?,?,?)", (value["id"], uid, json.dumps(value)))
            self.db.commit()

    def create_run_once(self, uid: str, value: dict) -> bool:
        """Insert a new run without replacing an existing idempotency winner."""
        self.ensure_user(uid)
        try:
            with self.lock:
                self.db.execute(
                    "INSERT INTO runs(id,user_id,idempotency_key,payload) VALUES(?,?,?,?)",
                    (value["id"], uid, value.get("idempotency_key"), json.dumps(value)),
                )
                self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def claim_run_status(self, uid: str, item_id: str, expected: str, updates: dict):
        """Atomically transition a run from one state, including across processes."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute(
                    "SELECT payload FROM runs WHERE user_id=? AND id=?",
                    (uid, item_id),
                ).fetchone()
                if not row:
                    self.db.rollback()
                    return None
                current = json.loads(row[0])
                if current.get("status") != expected:
                    self.db.rollback()
                    return None
                updated = {**current, **updates}
                self.db.execute(
                    "UPDATE runs SET payload=? WHERE user_id=? AND id=?",
                    (json.dumps(updated), uid, item_id),
                )
                self.db.commit()
                return updated
            except Exception:
                self.db.rollback()
                raise

    def _list(self, table: str, uid: str):
        return [json.loads(row[0]) for row in self.db.execute(f"SELECT payload FROM {table} WHERE user_id=?", (uid,))]

    def _get(self, table: str, uid: str, item_id: str):
        row = self.db.execute(f"SELECT payload FROM {table} WHERE user_id=? AND id=?", (uid, item_id)).fetchone()
        return json.loads(row[0]) if row else None

    def _delete(self, table: str, uid: str, item_id: str):
        with self.lock:
            cursor = self.db.execute(f"DELETE FROM {table} WHERE user_id=? AND id=?", (uid, item_id))
            self.db.commit()
        return cursor.rowcount > 0

    def save_credential(self, uid, value): self._save("credentials", uid, value)
    def list_credentials(self, uid): return self._list("credentials", uid)
    def get_credential(self, uid, item_id): return self._get("credentials", uid, item_id)
    def delete_credential(self, uid, item_id): return self._delete("credentials", uid, item_id)
    def save_custom_model(self, uid, value): self._save("custom_models", uid, value)
    def list_custom_models(self, uid): return self._list("custom_models", uid)
    def get_custom_model(self, uid, item_id): return self._get("custom_models", uid, item_id)
    def delete_custom_model(self, uid, item_id): return self._delete("custom_models", uid, item_id)
    def save_run(self, uid, value): self._save("runs", uid, value)
    def list_runs(self, uid): return self._list("runs", uid)
    def get_run(self, uid, item_id): return self._get("runs", uid, item_id)
    def get_run_by_idempotency(self, uid, key):
        row = self.db.execute("SELECT payload FROM runs WHERE user_id=? AND idempotency_key=?", (uid, key)).fetchone()
        return json.loads(row[0]) if row else None
    def save_invocation(self, uid, value): self._save("invocations", uid, value)
    def list_invocations(self, uid, run_id=None):
        values = self._list("invocations", uid)
        return [value for value in values if run_id is None or value["run_id"] == run_id]
    def get_invocation(self, uid, item_id): return self._get("invocations", uid, item_id)
    def save_ledger(self, uid, value): self._save("ledger", uid, value)
    def list_ledger(self, uid, run_id=None):
        values = self._list("ledger", uid)
        return [value for value in values if run_id is None or value["run_id"] == run_id]
    def save_artifact(self, uid, value): self._save("artifacts", uid, value)
    def list_artifacts(self, uid, run_id=None):
        values = self._list("artifacts", uid)
        return [value for value in values if run_id is None or value["run_id"] == run_id]
    def get_artifact(self, uid, item_id): return self._get("artifacts", uid, item_id)

    def save_memory(self, uid, value): self._save("memory_items", uid, value)
    def list_memory(self, uid): return self._list("memory_items", uid)
    def get_memory(self, uid, item_id): return self._get("memory_items", uid, item_id)
    def delete_memory(self, uid, item_id): return self._delete("memory_items", uid, item_id)

    def save_tool_call(self, uid, value): self._save("tool_calls", uid, value)
    def list_tool_calls(self, uid): return self._list("tool_calls", uid)
    def get_tool_call(self, uid, item_id): return self._get("tool_calls", uid, item_id)


def _default_database_path() -> Path:
    configured = os.environ.get("QINGQING_DATABASE_PATH")
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "qingqing.db"


store = SqliteStore(_default_database_path())
