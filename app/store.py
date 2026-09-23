import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .jobs import ClaimedJob, VideoJob


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, concept TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                filename TEXT, error TEXT, attempt_count INTEGER NOT NULL DEFAULT 0,
                claim_token TEXT, lease_expires_at REAL)""")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs(status, lease_expires_at, created_at)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _public(row) -> VideoJob:
        return VideoJob(
            id=row["id"], concept=row["concept"], status=row["status"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            video_url=f'/videos/{row["id"]}/file' if row["status"] == "succeeded" else None,
            error=row["error"] if row["status"] == "failed" else None,
        )

    def create_job(self, concept: str) -> VideoJob:
        job_id, now = str(uuid4()), _iso(time.time())
        with self._connect() as db:
            db.execute("INSERT INTO jobs (id,concept,status,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (job_id, concept, "queued", now, now))
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._public(row)

    def get_job(self, job_id: UUID | str) -> VideoJob | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (str(job_id),)).fetchone()
        return self._public(row) if row else None

    def get_filename(self, job_id: UUID | str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT filename FROM jobs WHERE id=? AND status='succeeded'", (str(job_id),)).fetchone()
        return row["filename"] if row else None

    def list_jobs(self) -> list[VideoJob]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC, id DESC").fetchall()
        return [self._public(row) for row in rows]

    def claim_next_job(self, now: float | None = None, lease_seconds: int = 90) -> ClaimedJob | None:
        now = time.time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""UPDATE jobs SET status='failed', error='Generation stopped after repeated worker interruptions',
                claim_token=NULL, lease_expires_at=NULL, updated_at=?
                WHERE status='processing' AND lease_expires_at<=? AND attempt_count>=3""", (_iso(now), now))
            row = db.execute("""SELECT * FROM jobs WHERE status='queued'
                OR (status='processing' AND lease_expires_at<=? AND attempt_count<3)
                ORDER BY created_at, id LIMIT 1""", (now,)).fetchone()
            if not row:
                return None
            token = uuid4().hex
            db.execute("""UPDATE jobs SET status='processing', claim_token=?, lease_expires_at=?,
                attempt_count=attempt_count+1, updated_at=?, error=NULL WHERE id=?""",
                (token, now + lease_seconds, _iso(now), row["id"]))
            return ClaimedJob(id=row["id"], concept=row["concept"],
                              claim_token=token, attempt_count=row["attempt_count"] + 1)

    def renew_lease(self, job_id: UUID | str, token: str, now: float | None = None, lease_seconds: int = 90) -> bool:
        now = time.time() if now is None else now
        with self._connect() as db:
            cur = db.execute("""UPDATE jobs SET lease_expires_at=?, updated_at=?
                WHERE id=? AND status='processing' AND claim_token=? AND lease_expires_at>?""",
                (now + lease_seconds, _iso(now), str(job_id), token, now))
            return cur.rowcount == 1

    def mark_succeeded(self, job_id: UUID | str, token: str, filename: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._connect() as db:
            cur = db.execute("""UPDATE jobs SET status='succeeded', filename=?, updated_at=?,
                claim_token=NULL, lease_expires_at=NULL WHERE id=? AND status='processing'
                AND claim_token=? AND lease_expires_at>?""",
                (filename, _iso(now), str(job_id), token, now))
            return cur.rowcount == 1

    def mark_failed(self, job_id: UUID | str, token: str, message: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._connect() as db:
            cur = db.execute("""UPDATE jobs SET status='failed', error=?, updated_at=?,
                claim_token=NULL, lease_expires_at=NULL WHERE id=? AND status='processing'
                AND claim_token=? AND lease_expires_at>?""",
                (message[:240], _iso(now), str(job_id), token, now))
            return cur.rowcount == 1
