"""SQLite-backed, restart-safe queue for playlist transcript indexing."""

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class IngestionQueue:
    """Persist playlist jobs and process videos one at a time with bounded retries."""

    TERMINAL_ITEM_STATES = {"completed", "no_captions", "failed", "skipped"}

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
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        self._paused = threading.Event()
        self._wake = threading.Event()
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
                """
            )
            # A process may have exited between claiming and committing an item.
            # Qdrant upserts are deterministic, so returning it to the queue is safe.
            connection.execute(
                "UPDATE ingestion_items SET status='queued', error='Recovered after worker restart', updated_at=? "
                "WHERE status='processing'",
                (_utc_now(),),
            )
            connection.execute(
                "UPDATE ingestion_jobs SET status='queued', updated_at=? WHERE status='running'",
                (_utc_now(),),
            )

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
            connection.execute(
                "INSERT INTO ingestion_jobs VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)",
                (job_id, playlist_id, playlist_title, collection_name, videos_collection,
                 target_words, overlap_words, now, now),
            )
            for index, video in enumerate(videos, start=1):
                video_id = str(video.get("video_id") or "").strip()
                if not video_id:
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO ingestion_items "
                    "(job_id, video_id, title, url, playlist_index, status, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 'queued', ?)",
                    (job_id, video_id, str(video.get("title") or f"Video {video_id}"),
                     str(video.get("url") or f"https://www.youtube.com/watch?v={video_id}"),
                     video.get("playlist_index", index), now),
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
            connection.execute(
                "UPDATE ingestion_jobs SET status='paused', updated_at=? WHERE status IN ('queued','running')",
                (_utc_now(),),
            )
        return bool(self._thread and self._thread.is_alive())

    def resume(self) -> bool:
        self._paused.clear()
        with self._connection() as connection:
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

    def _claim_next(self) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT i.*, j.playlist_id, j.playlist_title, j.collection_name, "
                "j.videos_collection, j.target_words, j.overlap_words "
                "FROM ingestion_items i JOIN ingestion_jobs j USING(job_id) "
                "WHERE i.status='queued' AND j.status IN ('queued','running') "
                "ORDER BY j.created_at, i.playlist_index LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            now = _utc_now()
            connection.execute(
                "UPDATE ingestion_items SET status='processing', attempts=attempts+1, error=NULL, updated_at=? "
                "WHERE job_id=? AND video_id=? AND status='queued'",
                (now, row["job_id"], row["video_id"]),
            )
            connection.execute(
                "UPDATE ingestion_jobs SET status='running', updated_at=? WHERE job_id=?",
                (now, row["job_id"]),
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
            connection.execute(
                "UPDATE ingestion_items SET status=?, chunks=?, error=?, updated_at=? WHERE job_id=? AND video_id=?",
                (status, chunks, message, now, item["job_id"], item["video_id"]),
            )
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
                job_status = "paused" if self._paused.is_set() else "queued"
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
                self._wake.wait()
                continue
            item = self._claim_next()
            if item is None:
                self._wake.wait()
                continue
            self._current = {
                "job_id": item["job_id"], "video_id": item["video_id"], "title": item["title"]
            }
            try:
                result = self.process_video(item, item)
                self._finish_item(item, result, None)
            except Exception as exc:
                self._finish_item(item, None, f"{type(exc).__name__}: {exc}")
                if int(item["attempts"]) < self.max_attempts:
                    self._shutdown.wait(min(2 ** (int(item["attempts"]) - 1), 15))
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
        active = self.get_job(active_row["job_id"], include_items=False) if active_row else None
        return {
            "is_running": bool(
                active and active["status"] in {"queued", "running"}
                and self._thread and self._thread.is_alive() and not self._paused.is_set()
            ),
            "worker_alive": bool(self._thread and self._thread.is_alive()),
            "is_paused": bool(self._paused.is_set() or (active and active["status"] == "paused")),
            "current_video": (self._current or {}).get("title"),
            "current_video_id": (self._current or {}).get("video_id"),
            "job_id": active.get("job_id") if active else None,
            "playlist_id": active.get("playlist_id") if active else None,
            "playlist_title": active.get("playlist_title") if active else None,
            "completed": active.get("completed", 0) if active else 0,
            "total": active.get("total", 0) if active else 0,
            "counts": active.get("counts", {}) if active else {},
        }
