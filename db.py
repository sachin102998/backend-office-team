"""Tiny SQLite store for tasks, schedules, chat history, and pending confirmations."""
import sqlite3
import json
import time
from contextlib import contextmanager
from app.config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL,
    command TEXT,
    status TEXT,          -- queued | running | done | needs_confirmation | error
    result TEXT,
    agent TEXT
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cron TEXT,
    command TEXT,
    enabled INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    role TEXT,
    content TEXT
);
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL,
    kind TEXT,            -- email | whatsapp
    payload TEXT,         -- json of the action awaiting yes/no
    summary TEXT
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with db() as c:
        c.executescript(_SCHEMA)


# ---- tasks ----
def add_task(command, agent="manager", status="queued"):
    with db() as c:
        cur = c.execute(
            "INSERT INTO tasks(created,command,status,agent) VALUES(?,?,?,?)",
            (time.time(), command, status, agent),
        )
        return cur.lastrowid


def set_task(task_id, status=None, result=None, agent=None):
    with db() as c:
        row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return
        c.execute(
            "UPDATE tasks SET status=?, result=?, agent=? WHERE id=?",
            (
                status or row["status"],
                result if result is not None else row["result"],
                agent or row["agent"],
                task_id,
            ),
        )


def recent_tasks(limit=50):
    with db() as c:
        rows = c.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---- schedules ----
def add_schedule(cron, command):
    with db() as c:
        cur = c.execute(
            "INSERT INTO schedules(cron,command,enabled) VALUES(?,?,1)",
            (cron, command),
        )
        return cur.lastrowid


def list_schedules():
    with db() as c:
        rows = c.execute("SELECT * FROM schedules WHERE enabled=1").fetchall()
        return [dict(r) for r in rows]


# ---- chat history ----
def add_chat(role, content):
    with db() as c:
        c.execute(
            "INSERT INTO chat(ts,role,content) VALUES(?,?,?)",
            (time.time(), role, content),
        )


def history(limit=30):
    with db() as c:
        rows = c.execute(
            "SELECT role,content FROM chat ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# ---- pending confirmations ----
def add_pending(kind, payload, summary):
    with db() as c:
        cur = c.execute(
            "INSERT INTO pending(created,kind,payload,summary) VALUES(?,?,?,?)",
            (time.time(), kind, json.dumps(payload), summary),
        )
        return cur.lastrowid


def list_pending():
    with db() as c:
        rows = c.execute("SELECT * FROM pending ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def pop_pending(pid):
    with db() as c:
        row = c.execute("SELECT * FROM pending WHERE id=?", (pid,)).fetchone()
        if row:
            c.execute("DELETE FROM pending WHERE id=?", (pid,))
            return dict(row)
    return None
