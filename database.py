import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "decision_engine.db"

def now():
    return datetime.now(timezone.utc).isoformat()

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS workflow_requests (
            request_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            status TEXT NOT NULL,
            decision TEXT,
            explanation TEXT,
            rule_trace TEXT NOT NULL DEFAULT '[]',
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_key TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_key) REFERENCES workflow_requests(request_key)
        )""")

def audit(c, key, event_type, details):
    c.execute("INSERT INTO audit_events(request_key,event_type,details,created_at) VALUES(?,?,?,?)",
              (key, event_type, json.dumps(details), now()))

def create_or_get_request(key, payload):
    with connect() as c:
        row = c.execute("SELECT * FROM workflow_requests WHERE request_key=?", (key,)).fetchone()
        if row:
            return serialize(row), False
        ts = now()
        c.execute("""INSERT INTO workflow_requests
            (request_key,payload,status,rule_trace,created_at,updated_at)
            VALUES(?,?, 'RECEIVED','[]',?,?)""", (key, json.dumps(payload), ts, ts))
        audit(c, key, "REQUEST_RECEIVED", {"payload": payload})
        return serialize(c.execute("SELECT * FROM workflow_requests WHERE request_key=?", (key,)).fetchone()), True

def serialize(row):
    if not row: return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    d["rule_trace"] = json.loads(d["rule_trace"])
    return d

def get_request(key):
    with connect() as c:
        return serialize(c.execute("SELECT * FROM workflow_requests WHERE request_key=?", (key,)).fetchone())

def update_request(key, *, status=None, decision=None, explanation=None, rule_trace=None, retry_count=None, event=None, details=None):
    with connect() as c:
        fields, values = [], []
        for name, value in [("status", status), ("decision", decision), ("explanation", explanation),
                            ("rule_trace", json.dumps(rule_trace) if rule_trace is not None else None),
                            ("retry_count", retry_count)]:
            if value is not None:
                fields.append(f"{name}=?"); values.append(value)
        fields.append("updated_at=?"); values.append(now())
        values.append(key)
        c.execute(f"UPDATE workflow_requests SET {','.join(fields)} WHERE request_key=?", values)
        if event:
            audit(c, key, event, details or {})

def get_audit(key):
    with connect() as c:
        rows = c.execute("SELECT * FROM audit_events WHERE request_key=? ORDER BY id", (key,)).fetchall()
        return [{"id": r["id"], "event_type": r["event_type"], "details": json.loads(r["details"]), "created_at": r["created_at"]} for r in rows]

def list_requests():
    with connect() as c:
        rows = c.execute("SELECT * FROM workflow_requests ORDER BY created_at DESC").fetchall()
        return [serialize(r) for r in rows]
