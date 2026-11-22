"""Private SQLite task journal and state transitions."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

STATES = {
    "triage_pending", "needs_attention", "queued", "running",
    "review_pending", "revision_queued", "done", "blocked", "cancelled",
}


def data_dir() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "multi_modal"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


class TaskStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "tasks.sqlite3")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        os.chmod(self.path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
              prompt TEXT NOT NULL, state TEXT NOT NULL, task_type TEXT DEFAULT '',
              complexity INTEGER, priority INTEGER, risk TEXT DEFAULT '',
              confidence REAL, rationale TEXT DEFAULT '', suggested_model TEXT DEFAULT '',
              assigned_model TEXT DEFAULT '', output TEXT DEFAULT '',
              review_packet TEXT DEFAULT '', review_response TEXT DEFAULT '',
              retry_count INTEGER NOT NULL DEFAULT 0, error TEXT DEFAULT '',
              git_repo TEXT NOT NULL DEFAULT '', git_context TEXT NOT NULL DEFAULT '',
              git_context_paths TEXT NOT NULL DEFAULT '', git_patch_sha256 TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
              at REAL NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL
            );
        """)
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(tasks)")}
        for name, declaration in (
            ("git_repo", "TEXT NOT NULL DEFAULT ''"),
            ("git_context", "TEXT NOT NULL DEFAULT ''"),
            ("git_context_paths", "TEXT NOT NULL DEFAULT ''"),
            ("git_patch_sha256", "TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in columns:
                self.db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {declaration}")
        interrupted = self.db.execute("SELECT id FROM tasks WHERE state='running'").fetchall()
        for row in interrupted:
            self.db.execute("UPDATE tasks SET state='blocked', error='Application restarted while inference was active', updated=? WHERE id=?", (time.time(), row['id']))
            self._event(row['id'], "blocked", "Application restarted while inference was active; inspect and retry manually")
            task = self.db.execute("SELECT * FROM tasks WHERE id=?", (row['id'],)).fetchone()
            packet = (f"Codex review request\nTask ID: {row['id']}\nPurpose: Application restarted during local inference; inspect the partial task and advise whether to retry.\n"
                      f"Assigned local model: {task['assigned_model']}\n\nUser request:\n{task['prompt']}\n\n"
                      f"Prior output/error:\n{task['output'] or task['error']}\n\n"
                      "Return APPROVE or CHANGES: with actionable guidance. This packet does not authorize tool execution.")
            self.db.execute("UPDATE tasks SET review_packet=? WHERE id=?", (packet, row['id']))
        empty_completions = self.db.execute("SELECT id FROM tasks WHERE state='review_pending' AND trim(output)='' ").fetchall()
        for row in empty_completions:
            message = "Local model returned an empty response; retry against the originally assigned model."
            self.db.execute("UPDATE tasks SET state='blocked', error=?, updated=?, review_packet=review_packet || char(10) || char(10) || ? WHERE id=?",
                            (message, time.time(), message, row['id']))
            self._event(row['id'], "blocked", message)
        self.db.commit()

    def _event(self, task_id: str, state: str, detail: str) -> None:
        self.db.execute("INSERT INTO events(task_id,at,state,detail) VALUES(?,?,?,?)", (task_id, time.time(), state, detail))

    def create(self, prompt: str, *, git_repo: str = "", git_context: str = "", git_context_paths: str = "") -> str:
        task_id, now = uuid.uuid4().hex[:12], time.time()
        with self.lock:
            self.db.execute("INSERT INTO tasks(id,created,updated,prompt,state,git_repo,git_context,git_context_paths) VALUES(?,?,?,?,?,?,?,?)",
                            (task_id, now, now, prompt.strip(), "triage_pending", git_repo, git_context, git_context_paths))
            self._event(task_id, "triage_pending", "Submitted for local triage")
            self.db.commit()
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(row) for row in self.db.execute("SELECT * FROM tasks ORDER BY CASE state WHEN 'running' THEN 0 WHEN 'triage_pending' THEN 1 WHEN 'queued' THEN 2 WHEN 'revision_queued' THEN 3 WHEN 'review_pending' THEN 4 WHEN 'needs_attention' THEN 5 ELSE 6 END, priority DESC, created")]

    def events(self, task_id: str) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(row) for row in self.db.execute("SELECT * FROM events WHERE task_id=? ORDER BY id", (task_id,))]

    def update(self, task_id: str, state: str, detail: str, **fields: Any) -> None:
        if state not in STATES:
            raise ValueError(f"Invalid task state: {state}")
        allowed = {"task_type", "complexity", "priority", "risk", "confidence", "rationale", "suggested_model", "assigned_model", "output", "review_packet", "review_response", "retry_count", "error", "git_repo", "git_context", "git_context_paths", "git_patch_sha256"}
        if fields.keys() - allowed:
            raise ValueError("Unknown task fields")
        assignments = ["state=?", "updated=?"]
        values: list[Any] = [state, time.time()]
        for key, value in fields.items():
            assignments.append(f"{key}=?")
            values.append(value)
        values.append(task_id)
        with self.lock:
            self.db.execute(f"UPDATE tasks SET {', '.join(assignments)} WHERE id=?", values)
            self._event(task_id, state, detail)
            self.db.commit()

    def close(self) -> None:
        with self.lock:
            self.db.close()
