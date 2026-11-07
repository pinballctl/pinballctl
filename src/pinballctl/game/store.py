"""Atomic command execution: BEGIN IMMEDIATE is the cross-process claim.

State, command receipt and outbox intent commit together. A process dying before
commit leaves no claim or partial transition. Result delivery is retryable.
"""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import sqlite3


def path(instance):
    return Path(instance) / "game/management.sqlite"


@contextmanager
def transaction(instance):
    file = path(instance)
    file.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(file, timeout=5)
    try:
        # SQLite cannot always wait while concurrent first-open connections both
        # change journal mode. Serialize initialization, then let BEGIN IMMEDIATE
        # arbitrate actual commands across processes.
        with file.with_suffix(".init.lock").open("a") as initialization:
            fcntl.flock(initialization, fcntl.LOCK_EX)
            if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(
                """CREATE TABLE IF NOT EXISTS documents(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,request TEXT NOT NULL,result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,name TEXT,params TEXT,delivered INTEGER NOT NULL DEFAULT 0,logged INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS ingress(id TEXT PRIMARY KEY,turn_id TEXT,rejected INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS financial_ids(id TEXT PRIMARY KEY,request TEXT NOT NULL,result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts(consumer TEXT,id TEXT,PRIMARY KEY(consumer,id));"""
            )
            if not any(row[1] == "logged" for row in db.execute("PRAGMA table_info(outbox)")):
                # Existing history stays in the manager database.
                db.execute("ALTER TABLE outbox ADD COLUMN logged INTEGER NOT NULL DEFAULT 1")
            db.execute("CREATE INDEX IF NOT EXISTS outbox_unlogged ON outbox(seq) WHERE logged=0")
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def read(db, key, default):
    row = db.execute("SELECT value FROM documents WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def write(db, key, value):
    db.execute(
        "INSERT INTO documents VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, separators=(",", ":"))),
    )
