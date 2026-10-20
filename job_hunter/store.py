"""SQLite privato: ogni modifica è transazionale, nessun CV nei log."""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
import uuid


class Store:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "hunter.sqlite3"
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, created REAL NOT NULL,
                  updated REAL NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, pdf BLOB);
                CREATE INDEX IF NOT EXISTS runs_fingerprint ON runs(fingerprint, created);
                CREATE TABLE IF NOT EXISTS results (
                  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                  company_id TEXT NOT NULL, payload TEXT NOT NULL,
                  PRIMARY KEY(run_id, company_id));
                CREATE TABLE IF NOT EXISTS cache (
                  key TEXT PRIMARY KEY, expires REAL NOT NULL, payload TEXT NOT NULL);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def create(self, params, pdf, source_name):
        fingerprint = hashlib.sha256(pdf + json.dumps(params, sort_keys=True).encode()).hexdigest()
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT id FROM runs WHERE fingerprint=? AND created>? ORDER BY created DESC LIMIT 1",
                             (fingerprint, now - 60)).fetchone()
            if old:
                return old["id"], False
            run_id = str(uuid.uuid4())
            data = {"params": params, "source_name": source_name, "cv_hash": hashlib.sha256(pdf).hexdigest(),
                    "candidates": [], "companies": {}, "errors": [], "stages": [],
                    "queries_used": 0, "pages_used": 0, "http_retries": 0}
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
                       (run_id, fingerprint, now, now, "queued", json.dumps(data), pdf))
        return run_id, True

    def get(self, run_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Ricerca inesistente")
        return {**dict(row), "data": json.loads(row["payload"])}

    def save(self, run, status=None, clear_pdf=False):
        with self.db() as db:
            db.execute("UPDATE runs SET payload=?, status=?, updated=?, pdf=CASE WHEN ? THEN NULL ELSE pdf END WHERE id=?",
                       (json.dumps(run["data"], ensure_ascii=False), status or run["status"], time.time(), clear_pdf, run["id"]))
        if status:
            run["status"] = status

    def claim(self, run_id, max_runtime):
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError("Ricerca inesistente")
            if row["status"] != "queued":
                return False, False
            active = db.execute("SELECT id FROM runs WHERE status='running' LIMIT 1").fetchone()
            if active:
                return False, True
            data = json.loads(row["payload"])
            data["deadline"] = now + max_runtime
            data["started_at"] = now
            db.execute("UPDATE runs SET status='running', payload=?, updated=? WHERE id=?",
                       (json.dumps(data), now, run_id))
        return True, False

    def put_result(self, run_id, company):
        with self.db() as db:
            db.execute("INSERT INTO results VALUES (?,?,?) ON CONFLICT(run_id,company_id) DO UPDATE SET payload=excluded.payload",
                       (run_id, company["company_id"], json.dumps(company, ensure_ascii=False)))

    def results(self, run_id):
        self.get(run_id)
        with self.db() as db:
            rows = db.execute("SELECT payload FROM results WHERE run_id=?", (run_id,)).fetchall()
        items = [json.loads(row[0]) for row in rows]
        return sorted(items, key=lambda c: (c["location"].get("distance_km") is None,
                      c["location"].get("distance_km") or 0, -(c.get("fit") or {}).get("score", 0)))

    def cache_get(self, key):
        with self.db() as db:
            row = db.execute("SELECT payload FROM cache WHERE key=? AND expires>?", (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, key, value, hours):
        with self.db() as db:
            db.execute("INSERT INTO cache VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET expires=excluded.expires,payload=excluded.payload",
                       (key, time.time() + hours * 3600, json.dumps(value)))

    def delete(self, run_id):
        with self.db() as db:
            db.execute("DELETE FROM runs WHERE id=?", (run_id,))
        with self.db() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def sweep(self, retention_days):
        now = time.time()
        with self.db() as db:
            running = db.execute("SELECT * FROM runs WHERE status='running'").fetchall()
            for row in running:
                data = json.loads(row["payload"])
                if data.get("deadline", 0) < now:
                    data["errors"].append({"stage": "watchdog", "code": "runtime_exceeded"})
                    count = db.execute("SELECT count(*) FROM results WHERE run_id=?", (row["id"],)).fetchone()[0]
                    db.execute("UPDATE runs SET status=?,payload=?,pdf=NULL,updated=? WHERE id=?",
                               ("partial" if count else "failed", json.dumps(data), now, row["id"]))
            db.execute("DELETE FROM runs WHERE created<?", (now - retention_days * 86400,))
            db.execute("DELETE FROM cache WHERE expires<?", (now,))

    def summary(self, run_id):
        run = self.get(run_id)
        d = run["data"]
        return {"run_id": run_id, "status": run["status"], "created_at": run["created"],
                "updated_at": run["updated"], "companies_saved": len(self.results(run_id)),
                "companies_discovered": len(d["candidates"]), "queries_used": d["queries_used"],
                "pages_used": d["pages_used"], "http_retries": d["http_retries"], "errors": d["errors"]}
