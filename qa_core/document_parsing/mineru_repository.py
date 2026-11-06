"""Separate SQLite task store. Does not initialize or alter knowledge-base tables."""
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from .mineru_client import MinerUError


class TaskRepository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS parse_tasks (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                UNIQUE(owner, request_key))""")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, task, queue_limit=20):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT fingerprint,payload FROM parse_tasks WHERE owner=? AND request_key=?",
                                          (task["owner"], task["request_key"])).fetchone()
            if existing:
                if existing[0] != task["fingerprint"]:
                    raise MinerUError("idempotency_conflict", 409)
                return json.loads(existing[1]), False
            count = connection.execute("SELECT COUNT(*) FROM parse_tasks WHERE status IN ('created','uploading','pending','running')").fetchone()[0]
            if count >= queue_limit:
                raise MinerUError("queue_full", 429)
            connection.execute("INSERT INTO parse_tasks(id,owner,request_key,fingerprint,payload,status) VALUES(?,?,?,?,?,?)", (
                task["id"], task["owner"], task["request_key"], task["fingerprint"], json.dumps(task), task["status"]))
            return task, True

    def get(self, task_id, owner=None):
        with self.connect() as connection:
            row = connection.execute("SELECT owner,payload,cancel_requested FROM parse_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None or (owner is not None and row[0] != owner):
            raise MinerUError("task_not_found", 404)
        return {**json.loads(row[1]), "cancel_requested": bool(row[2])}

    def save(self, task):
        with self.connect() as connection:
            connection.execute("UPDATE parse_tasks SET payload=?,status=? WHERE id=?", (json.dumps(task), task["status"], task["id"]))

    def request_cancel(self, task_id, owner):
        self.get(task_id, owner)
        with self.connect() as connection:
            connection.execute("UPDATE parse_tasks SET cancel_requested=1 WHERE id=? AND owner=?", (task_id, owner))

    def resumable(self, limit=20):
        with self.connect() as connection:
            rows = connection.execute("SELECT payload FROM parse_tasks WHERE status IN ('created','uploading','pending','running') ORDER BY rowid LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]
