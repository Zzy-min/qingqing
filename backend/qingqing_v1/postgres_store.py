"""PostgreSQL-backed store with the same surface as SqliteStore."""

from __future__ import annotations

import json
import threading
from urllib.parse import urlparse

from .store import DEFAULT_PREFERENCES


class PostgresStore:
    """Uses psycopg (v3) when available. Connection string via DSN."""

    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL store: pip install psycopg[binary]") from exc
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.dsn = dsn
        self.lock = threading.RLock()
        self.conn = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'free');
                    CREATE TABLE IF NOT EXISTS identities(email TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE);
                    CREATE TABLE IF NOT EXISTS auth_codes(
                      id TEXT PRIMARY KEY, email TEXT NOT NULL, code_hash TEXT NOT NULL,
                      expires_at BIGINT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,
                      attempts INTEGER NOT NULL DEFAULT 0, created_at BIGINT NOT NULL);
                    CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS credentials(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS custom_models(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS runs(
                      id TEXT PRIMARY KEY, user_id TEXT NOT NULL, idempotency_key TEXT, payload TEXT NOT NULL,
                      UNIQUE(user_id, idempotency_key));
                    CREATE TABLE IF NOT EXISTS invocations(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, run_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS memory_items(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS tool_calls(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL);
                    """
                )
            self.conn.commit()

    def reset(self) -> None:
        with self.lock:
            with self.conn.cursor() as cur:
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
                    cur.execute(f"DELETE FROM {table}")
            self.conn.commit()

    def ensure_user(self, uid: str, plan: str = "free") -> None:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(id, plan) VALUES(%s, %s) ON CONFLICT (id) DO NOTHING",
                    (uid, plan),
                )
            self.conn.commit()

    def get_user(self, uid: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, plan FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
        return dict(row) if row else None

    def set_plan(self, uid: str, plan: str) -> None:
        self.ensure_user(uid)
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute("UPDATE users SET plan=%s WHERE id=%s", (plan, uid))
            self.conn.commit()

    def user_for_email(self, email: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT user_id FROM identities WHERE email=%s", (email,))
            row = cur.fetchone()
        return row["user_id"] if row else None

    def bind_email(self, email: str, uid: str) -> None:
        self.ensure_user(uid)
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO identities(email, user_id) VALUES(%s, %s) ON CONFLICT (email) DO NOTHING",
                    (email, uid),
                )
            self.conn.commit()

    def count_recent_auth_codes(self, email: str, since: int) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM auth_codes WHERE email=%s AND created_at>=%s",
                (email, since),
            )
            return int(cur.fetchone()["c"])

    def save_auth_code(self, value: dict) -> None:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_codes(id,email,code_hash,expires_at,consumed,attempts,created_at) VALUES(%s,%s,%s,%s,0,0,%s)",
                    (value["id"], value["email"], value["code_hash"], value["expires_at"], value["created_at"]),
                )
            self.conn.commit()

    def latest_auth_code(self, email: str):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM auth_codes WHERE email=%s ORDER BY created_at DESC LIMIT 1",
                (email,),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def increment_auth_attempt(self, code_id: str) -> None:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute("UPDATE auth_codes SET attempts=attempts+1 WHERE id=%s", (code_id,))
            self.conn.commit()

    def consume_auth_code(self, code_id: str) -> None:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute("UPDATE auth_codes SET consumed=1 WHERE id=%s", (code_id,))
            self.conn.commit()

    def save_preferences(self, uid: str, value: dict) -> None:
        self.ensure_user(uid)
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO preferences(user_id, payload) VALUES(%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET payload=EXCLUDED.payload
                    """,
                    (uid, json.dumps(value)),
                )
            self.conn.commit()

    def get_preferences(self, uid: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT payload FROM preferences WHERE user_id=%s", (uid,))
            row = cur.fetchone()
        return {**DEFAULT_PREFERENCES, **(json.loads(row["payload"]) if row else {})}

    def _save(self, table: str, uid: str, value: dict) -> None:
        self.ensure_user(uid)
        payload = json.dumps(value)
        with self.lock:
            with self.conn.cursor() as cur:
                if table == "runs":
                    cur.execute(
                        """
                        INSERT INTO runs(id,user_id,idempotency_key,payload) VALUES(%s,%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE SET user_id=EXCLUDED.user_id,
                          idempotency_key=EXCLUDED.idempotency_key, payload=EXCLUDED.payload
                        """,
                        (value["id"], uid, value.get("idempotency_key"), payload),
                    )
                elif table in {"invocations", "ledger", "artifacts"}:
                    cur.execute(
                        f"""
                        INSERT INTO {table}(id,user_id,run_id,payload) VALUES(%s,%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE SET user_id=EXCLUDED.user_id,
                          run_id=EXCLUDED.run_id, payload=EXCLUDED.payload
                        """,
                        (value["id"], uid, value["run_id"], payload),
                    )
                else:
                    cur.execute(
                        f"""
                        INSERT INTO {table}(id,user_id,payload) VALUES(%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE SET user_id=EXCLUDED.user_id, payload=EXCLUDED.payload
                        """,
                        (value["id"], uid, payload),
                    )
            self.conn.commit()

    def create_run_once(self, uid: str, value: dict) -> bool:
        self.ensure_user(uid)
        try:
            with self.lock:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO runs(id,user_id,idempotency_key,payload) VALUES(%s,%s,%s,%s)",
                        (value["id"], uid, value.get("idempotency_key"), json.dumps(value)),
                    )
                self.conn.commit()
            return True
        except Exception as exc:
            self.conn.rollback()
            # unique violation
            if getattr(exc, "sqlstate", None) == "23505" or "unique" in str(exc).lower():
                return False
            raise

    def claim_run_status(self, uid: str, item_id: str, expected: str, updates: dict):
        with self.lock:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT payload FROM runs WHERE user_id=%s AND id=%s FOR UPDATE", (uid, item_id))
                    row = cur.fetchone()
                    if not row:
                        self.conn.rollback()
                        return None
                    current = json.loads(row["payload"])
                    if current.get("status") != expected:
                        self.conn.rollback()
                        return None
                    updated = {**current, **updates}
                    cur.execute(
                        "UPDATE runs SET payload=%s WHERE user_id=%s AND id=%s",
                        (json.dumps(updated), uid, item_id),
                    )
                self.conn.commit()
                return updated
            except Exception:
                self.conn.rollback()
                raise

    def _list(self, table: str, uid: str):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {table} WHERE user_id=%s", (uid,))
            rows = cur.fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def _get(self, table: str, uid: str, item_id: str):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {table} WHERE user_id=%s AND id=%s", (uid, item_id))
            row = cur.fetchone()
        return json.loads(row["payload"]) if row else None

    def _delete(self, table: str, uid: str, item_id: str) -> bool:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE user_id=%s AND id=%s", (uid, item_id))
                count = cur.rowcount
            self.conn.commit()
        return count > 0

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
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM runs WHERE user_id=%s AND idempotency_key=%s",
                (uid, key),
            )
            row = cur.fetchone()
        return json.loads(row["payload"]) if row else None

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


def is_postgres_url(url: str) -> bool:
    try:
        scheme = urlparse(url).scheme.lower()
    except Exception:
        return False
    return scheme in {"postgres", "postgresql"}
