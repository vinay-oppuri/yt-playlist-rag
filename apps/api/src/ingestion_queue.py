"""SQLite-backed, restart-safe queue for playlist transcript indexing."""

import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class IngestionQueue:
    """Persist playlist jobs and process videos one at a time with bounded retries."""

    def __init__(
        self,
        process_video: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        database_path: Optional[str] = None,
        max_attempts: Optional[int] = None,
    ):
        api_root = Path(__file__).resolve().parent.parent
        configured_path = database_path or os.getenv("INGESTION_DB_PATH")
        path = Path(configured_path) if configured_path else api_root / "data" / "ingestion_jobs.sqlite3"
        if not path.is_absolute():
            path = api_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = path
        self.process_video = process_video
        try:
            configured_attempts = max_attempts if max_attempts is not None else int(os.getenv("INGESTION_MAX_ATTEMPTS", "3"))
        except ValueError:
            configured_attempts = 3
        self.max_attempts = max(1, configured_attempts)
        self.owner_id = str(uuid.uuid4())
        try:
            self.lease_seconds = max(10, int(os.getenv("INGESTION_WORKER_LEASE_SECONDS", "30")))
        except ValueError:
            self.lease_seconds = 30
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        self._paused = threading.Event()
        self._wake = threading.Event()
        self._lease_owned = threading.Event()
        self._current: Optional[Dict[str, Any]] = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    playlist_id TEXT,
                    playlist_title TEXT,
                    collection_name TEXT NOT NULL,
                    videos_collection TEXT NOT NULL,
                    target_words INTEGER NOT NULL,
                    overlap_words INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ingestion_items (
                    job_id TEXT NOT NULL REFERENCES ingestion_jobs(job_id) ON DELETE CASCADE,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    playlist_index INTEGER,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    chunks INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(job_id, video_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ingestion_items_queue
                    ON ingestion_items(status, job_id, playlist_index);
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
                    ON ingestion_jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS ingestion_worker_lease (
                    lease_name TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ingestion_control (
                    control_id INTEGER PRIMARY KEY CHECK(control_id=1),
                    paused INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO ingestion_control(control_id, paused) VALUES (1, 0);
                """
            )
            self._ensure_column(connection, "ingestion_items", "claimed_by", "TEXT")
            self._ensure_column(connection, "ingestion_items", "lease_expires_at", "REAL")
            control = connection.execute(
                "SELECT paused FROM ingestion_control WHERE control_id=1"
            ).fetchone()
            if control and control["paused"]:
                self._paused.set()

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            try:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError as exc:
                # Two API processes may run the same schema migration at startup.
                if "duplicate column name" not in str(exc).lower():
                    raise

    def enqueue(
        self,
        videos: List[Dict[str, Any]],
        *,
        collection_name: str,
        videos_collection: str,
        target_words: int,
        overlap_words: int,
        playlist_id: Optional[str],
        playlist_title: Optional[str],
    ) -> str:
        job_id = str(uuid.uuid4())
        now = _utc_now()
        with self._connection() as connection:
            control = connection.execute(
                "SELECT paused FROM ingestion_control WHERE control_id=1"
            ).fetchone()
            initial_status = "paused" if control and control["paused"] else "queued"
            connection.execute(
                "INSERT INTO ingestion_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, playlist_id, playlist_title, collection_name, videos_collection,
                 target_words, overlap_words, initial_status, now, now),
            )
            for index, video in enumerate(videos, start=1):
                video_id = str(video.get("video_id") or "").strip()
                if not video_id:
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO ingestion_items "
                    "(job_id, video_id, title, url, playlist_index, status, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (job_id, video_id, str(video.get("title") or f"Video {video_id}"),
                     str(video.get("url") or f"https://www.youtube.com/watch?v={video_id}"),
                     video.get("playlist_index", index), initial_status, now),
                )
        self.start()
        self._wake.set()
        return job_id

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._wake.set()
                return
            self._shutdown.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="durable-playlist-ingest")
            self._thread.start()

    def pause(self) -> bool:
        self._paused.set()
        self._wake.set()
        with self._connection() as connection:
            connection.execute("UPDATE ingestion_control SET paused=1 WHERE control_id=1")
            connection.execute(
                "UPDATE ingestion_jobs SET status='paused', updated_at=? WHERE status IN ('queued','running')",
                (_utc_now(),),
            )
        return bool(self._thread and self._thread.is_alive())

    def resume(self) -> bool:
        self._paused.clear()
        with self._connection() as connection:
            connection.execute("UPDATE ingestion_control SET paused=0 WHERE control_id=1")
            connection.execute(
                "UPDATE ingestion_jobs SET status='queued', updated_at=? WHERE status='paused'",
                (_utc_now(),),
            )
            connection.execute(
                "UPDATE ingestion_items SET status='queued', updated_at=? WHERE status='paused'",
                (_utc_now(),),
            )
        self.start()
        self._wake.set()
        return True

    def _is_queue_paused(self) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT paused FROM ingestion_control WHERE control_id=1"
            ).fetchone()
        paused = bool(row and row["paused"])
        if paused:
            self._paused.set()
        else:
            self._paused.clear()
        return paused

    def retry_failed(self, job_id: str, video_id: Optional[str] = None) -> int:
        now = _utc_now()
        with self._connection() as connection:
            if video_id:
                cursor = connection.execute(
                    "UPDATE ingestion_items SET status='queued', attempts=0, error=NULL, updated_at=? "
                    "WHERE job_id=? AND video_id=? AND status='failed'",
                    (now, job_id, video_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE ingestion_items SET status='queued', attempts=0, error=NULL, updated_at=? "
                    "WHERE job_id=? AND status='failed'",
                    (now, job_id),
                )
            retried = cursor.rowcount
            if retried:
                connection.execute(
                    "UPDATE ingestion_jobs SET status='queued', updated_at=? WHERE job_id=?",
                    (now, job_id),
                )
        if retried:
            self._paused.clear()
            self.start()
            self._wake.set()
        return retried

    def shutdown(self, wait_seconds: float = 10.0) -> None:
        self._shutdown.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=wait_seconds)
        if not thread or not thread.is_alive():
            self._release_worker_lease()

    def _acquire_worker_lease(self) -> bool:
        now = time.time()
        expires = now + self.lease_seconds
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO ingestion_worker_lease(lease_name, owner_id, expires_at) "
                "VALUES ('playlist-worker', ?, ?) "
                "ON CONFLICT(lease_name) DO UPDATE SET owner_id=excluded.owner_id, expires_at=excluded.expires_at "
                "WHERE ingestion_worker_lease.owner_id=? OR ingestion_worker_lease.expires_at<=?",
                (self.owner_id, expires, self.owner_id, now),
            )
            acquired = cursor.rowcount > 0
            if acquired:
                # Recover only claims whose lease expired. A live process holding
                # a valid lease is never reset by another API process starting up.
                connection.execute(
                    "UPDATE ingestion_items SET status='queued', claimed_by=NULL, lease_expires_at=NULL, "
                    "error='Recovered after worker lease expired', updated_at=? "
                    "WHERE status='processing' AND (lease_expires_at IS NULL OR lease_expires_at<=?)",
                    (_utc_now(), now),
                )
                connection.execute(
                    "UPDATE ingestion_jobs SET status='queued', updated_at=? WHERE status='running' "
                    "AND NOT EXISTS (SELECT 1 FROM ingestion_items i WHERE i.job_id=ingestion_jobs.job_id "
                    "AND i.status='processing') AND EXISTS (SELECT 1 FROM ingestion_items i "
                    "WHERE i.job_id=ingestion_jobs.job_id AND i.status='queued')",
                    (_utc_now(),),
                )
        if acquired:
            self._lease_owned.set()
            self._start_heartbeat()
        return acquired

    def _start_heartbeat(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker_lease, daemon=True, name="ingest-lease-heartbeat"
        )
        self._heartbeat_thread.start()

    def _heartbeat_worker_lease(self) -> None:
        interval = max(2.0, self.lease_seconds / 3)
        while not self._shutdown.wait(interval) and self._lease_owned.is_set():
            if not self._thread or not self._thread.is_alive():
                self._release_worker_lease()
                return
            now = time.time()
            expires = now + self.lease_seconds
            try:
                with self._connection() as connection:
                    cursor = connection.execute(
                        "UPDATE ingestion_worker_lease SET expires_at=? "
                        "WHERE lease_name='playlist-worker' AND owner_id=? AND expires_at>?",
                        (expires, self.owner_id, now),
                    )
                    if cursor.rowcount != 1:
                        self._lease_owned.clear()
                        self._wake.set()
                        return
                    connection.execute(
                        "UPDATE ingestion_items SET lease_expires_at=?, updated_at=? "
                        "WHERE status='processing' AND claimed_by=?",
                        (expires, _utc_now(), self.owner_id),
                    )
            except sqlite3.Error as exc:
                print(f"[Ingestion queue] Lease heartbeat failed: {exc}")

    def _release_worker_lease(self) -> None:
        self._lease_owned.clear()
        now = time.time()
        with self._connection() as connection:
            connection.execute(
                "UPDATE ingestion_worker_lease SET expires_at=? "
                "WHERE lease_name='playlist-worker' AND owner_id=?",
                (now, self.owner_id),
            )
            connection.execute(
                "UPDATE ingestion_items SET lease_expires_at=? "
                "WHERE status='processing' AND claimed_by=?",
                (now, self.owner_id),
            )

    def _claim_next(self) -> Optional[Dict[str, Any]]:
        now = time.time()
        expires = now + self.lease_seconds
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM ingestion_worker_lease WHERE lease_name='playlist-worker'"
            ).fetchone()
            control = connection.execute(
                "SELECT paused FROM ingestion_control WHERE control_id=1"
            ).fetchone()
            if not lease or lease["owner_id"] != self.owner_id or lease["expires_at"] <= now:
                self._lease_owned.clear()
                return None
            if control and control["paused"]:
                self._paused.set()
                return None
            connection.execute(
                "UPDATE ingestion_items SET status='queued', claimed_by=NULL, lease_expires_at=NULL, "
                "error='Recovered after item lease expired', updated_at=? "
                "WHERE status='processing' AND (lease_expires_at IS NULL OR lease_expires_at<=?)",
                (_utc_now(), now),
            )
            connection.execute(
                "UPDATE ingestion_jobs SET status='queued', updated_at=? WHERE status='running' "
                "AND NOT EXISTS (SELECT 1 FROM ingestion_items i WHERE i.job_id=ingestion_jobs.job_id "
                "AND i.status='processing') AND EXISTS (SELECT 1 FROM ingestion_items i "
                "WHERE i.job_id=ingestion_jobs.job_id AND i.status='queued')",
                (_utc_now(),),
            )
            row = connection.execute(
                "SELECT i.*, j.playlist_id, j.playlist_title, j.collection_name, "
                "j.videos_collection, j.target_words, j.overlap_words "
                "FROM ingestion_items i JOIN ingestion_jobs j USING(job_id) "
                "WHERE i.status='queued' AND j.status IN ('queued','running') "
                "AND NOT EXISTS (SELECT 1 FROM ingestion_items p WHERE p.status='processing') "
                "ORDER BY j.created_at, i.playlist_index LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            updated = _utc_now()
            connection.execute(
                "UPDATE ingestion_items SET status='processing', attempts=attempts+1, error=NULL, "
                "claimed_by=?, lease_expires_at=?, updated_at=? "
                "WHERE job_id=? AND video_id=? AND status='queued'",
                (self.owner_id, expires, updated, row["job_id"], row["video_id"]),
            )
            connection.execute(
                "UPDATE ingestion_jobs SET status='running', updated_at=? WHERE job_id=?",
                (updated, row["job_id"]),
            )
            claimed = dict(row)
            claimed["attempts"] = int(row["attempts"]) + 1
            return claimed

    def _finish_item(self, item: Dict[str, Any], result: Optional[Dict[str, Any]], error: Optional[str]) -> None:
        now = _utc_now()
        if error:
            retry = int(item["attempts"]) < self.max_attempts
            status = "queued" if retry else "failed"
            message = error[:2000]
            chunks = 0
        else:
            result = result or {}
            chunks = int(result.get("chunks") or 0)
            status = "completed" if result.get("status") == "success" else "no_captions"
            message = None

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM ingestion_worker_lease WHERE lease_name='playlist-worker'"
            ).fetchone()
            if not lease or lease["owner_id"] != self.owner_id or lease["expires_at"] <= time.time():
                self._lease_owned.clear()
                return
            connection.execute(
                "UPDATE ingestion_items SET status=?, chunks=?, error=?, claimed_by=NULL, lease_expires_at=NULL, "
                "updated_at=? WHERE job_id=? AND video_id=? AND claimed_by=? AND status='processing'",
                (status, chunks, message, now, item["job_id"], item["video_id"], self.owner_id),
            )
            finished = connection.execute("SELECT changes()").fetchone()[0]
            if not finished:
                return
            remaining = connection.execute(
                "SELECT COUNT(*) FROM ingestion_items WHERE job_id=? AND status NOT IN "
                "('completed','no_captions','failed','skipped')",
                (item["job_id"],),
            ).fetchone()[0]
            if not remaining:
                failures = connection.execute(
                    "SELECT COUNT(*) FROM ingestion_items WHERE job_id=? AND status IN ('failed','no_captions')",
                    (item["job_id"],),
                ).fetchone()[0]
                job_status = "completed_with_errors" if failures else "completed"
            else:
                control = connection.execute(
                    "SELECT paused FROM ingestion_control WHERE control_id=1"
                ).fetchone()
                job_status = "paused" if control and control["paused"] else "queued"
            connection.execute(
                "UPDATE ingestion_jobs SET status=?, updated_at=? WHERE job_id=?",
                (job_status, now, item["job_id"]),
            )

    def _run(self) -> None:
        while not self._shutdown.is_set():
            # Clear before checking the database so enqueue() cannot have its
            # wake signal lost between an empty read and the subsequent wait.
            self._wake.clear()
            if self._paused.is_set():
                if self._is_queue_paused():
                    self._wake.wait(1.0)
                    continue
            try:
                if not self._lease_owned.is_set() and not self._acquire_worker_lease():
                    self._wake.wait(1.0)
                    continue
                item = self._claim_next()
            except sqlite3.Error as exc:
                print(f"[Ingestion queue] Could not claim work: {exc}")
                self._shutdown.wait(1.0)
                continue
            if item is None:
                self._wake.wait(1.0)
                continue
            self._current = {
                "job_id": item["job_id"], "video_id": item["video_id"], "title": item["title"]
            }
            try:
                try:
                    result = self.process_video(item, item)
                except Exception as exc:
                    self._finish_item(item, None, f"{type(exc).__name__}: {exc}")
                    if int(item["attempts"]) < self.max_attempts:
                        self._shutdown.wait(min(2 ** (int(item["attempts"]) - 1), 15))
                else:
                    self._finish_item(item, result, None)
            except sqlite3.Error as exc:
                # Releasing an uncommitted claim lets the next lease holder
                # safely retry it; transcript point IDs make that idempotent.
                print(f"[Ingestion queue] Could not save job progress: {exc}")
                self._release_worker_lease()
            finally:
                self._current = None

    def get_job(self, job_id: str, include_items: bool = True) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            job_row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if job_row is None:
                return None
            counts = {
                row["status"]: int(row["count"])
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM ingestion_items WHERE job_id=? GROUP BY status",
                    (job_id,),
                ).fetchall()
            }
            total = sum(counts.values())
            details = None
            if include_items:
                details = [dict(row) for row in connection.execute(
                    "SELECT video_id, title, url, playlist_index, status, attempts, chunks, error, updated_at "
                    "FROM ingestion_items WHERE job_id=? ORDER BY playlist_index",
                    (job_id,),
                ).fetchall()]
            else:
                details = [dict(row) for row in connection.execute(
                    "SELECT video_id, title, status, attempts, error FROM ingestion_items "
                    "WHERE job_id=? AND status='failed' ORDER BY playlist_index LIMIT 10",
                    (job_id,),
                ).fetchall()]
        job = dict(job_row)
        job.update({"items" if include_items else "failed_items": details, "counts": counts, "total": total})
        job["completed"] = counts.get("completed", 0) + counts.get("no_captions", 0) + counts.get("failed", 0)
        return job

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT job_id FROM ingestion_jobs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [job for row in rows if (job := self.get_job(row["job_id"], include_items=False)) is not None]

    def status(self) -> Dict[str, Any]:
        with self._connection() as connection:
            active_row = connection.execute(
                "SELECT job_id FROM ingestion_jobs WHERE status IN ('queued','running','paused') "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM ingestion_worker_lease WHERE lease_name='playlist-worker'"
            ).fetchone()
            processing = connection.execute(
                "SELECT video_id, title FROM ingestion_items WHERE status='processing' LIMIT 1"
            ).fetchone()
        active = self.get_job(active_row["job_id"], include_items=False) if active_row else None
        worker_active = bool(lease and lease["expires_at"] > time.time())
        paused = self._is_queue_paused()
        return {
            "is_running": bool(
                active and active["status"] in {"queued", "running"}
                and worker_active and not paused
            ),
            "worker_alive": worker_active,
            "worker_owner": lease["owner_id"] if worker_active else None,
            "is_paused": bool(paused or (active and active["status"] == "paused")),
            "current_video": processing["title"] if processing else (self._current or {}).get("title"),
            "current_video_id": processing["video_id"] if processing else (self._current or {}).get("video_id"),
            "job_id": active.get("job_id") if active else None,
            "playlist_id": active.get("playlist_id") if active else None,
            "playlist_title": active.get("playlist_title") if active else None,
            "completed": active.get("completed", 0) if active else 0,
            "total": active.get("total", 0) if active else 0,
            "counts": active.get("counts", {}) if active else {},
        }
