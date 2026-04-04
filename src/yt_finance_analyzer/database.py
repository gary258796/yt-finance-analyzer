"""SQLite 資料庫操作模組，用於追蹤影片處理狀態。"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from yt_finance_analyzer.models import VideoMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL Statements
# ---------------------------------------------------------------------------

_CREATE_VIDEOS_TABLE = """
CREATE TABLE IF NOT EXISTS videos (
    video_id       TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    channel_id     TEXT NOT NULL,
    channel_name   TEXT NOT NULL,
    published_at   TEXT NOT NULL,
    url            TEXT NOT NULL,
    description    TEXT,
    duration_seconds INTEGER,
    language       TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    error_message  TEXT,
    started_at     TEXT,
    completed_at   TEXT,
    processing_time_seconds REAL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_CREATE_PROCESSING_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS processing_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT NOT NULL,
    action      TEXT NOT NULL,
    status      TEXT NOT NULL,
    message     TEXT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);
"""


class Database:
    """SQLite 資料庫操作封裝。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # -- connection management ------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
        return self._conn

    def close(self) -> None:
        """關閉資料庫連線。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- schema ---------------------------------------------------------------

    def init_db(self) -> None:
        """建立資料表（若不存在）。"""
        conn = self._get_conn()
        conn.execute(_CREATE_VIDEOS_TABLE)
        conn.execute(_CREATE_PROCESSING_LOG_TABLE)
        conn.commit()
        logger.info("資料庫初始化完成: %s", self._db_path)

    # -- CRUD -----------------------------------------------------------------

    def is_video_processed(self, video_id: str) -> bool:
        """檢查影片是否已處理（status 不是 pending 且不是 failed）。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT status FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return False
        return row["status"] not in ("pending", "failed")

    def save_video_metadata(self, metadata: VideoMetadata) -> None:
        """儲存影片 metadata，若已存在則更新。"""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO videos (video_id, title, channel_id, channel_name,
                                    published_at, url, description, duration_seconds, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    duration_seconds = excluded.duration_seconds
                """,
                (
                    metadata.video_id,
                    metadata.title,
                    metadata.channel_id,
                    metadata.channel_name,
                    metadata.published_at.isoformat(),
                    metadata.url,
                    metadata.description,
                    metadata.duration_seconds,
                    metadata.language,
                ),
            )
            conn.commit()
            logger.debug("已儲存影片 metadata: %s", metadata.video_id)
        except sqlite3.Error:
            logger.exception("儲存影片 metadata 失敗: %s", metadata.video_id)
            raise

    def update_video_status(
        self,
        video_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """更新影片處理狀態。"""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        try:
            updates = {"status": status, "error_message": error_message}
            if status == "pending":
                updates["started_at"] = now
            if status in ("analysis_done", "reported", "failed"):
                updates["completed_at"] = now

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [video_id]

            conn.execute(
                f"UPDATE videos SET {set_clause} WHERE video_id = ?",  # noqa: S608
                values,
            )
            conn.commit()

            # 寫入 processing_log
            conn.execute(
                "INSERT INTO processing_log (video_id, action, status, message) VALUES (?, ?, ?, ?)",
                (video_id, "status_update", status, error_message),
            )
            conn.commit()
            logger.debug("影片 %s 狀態更新為: %s", video_id, status)
        except sqlite3.Error:
            logger.exception("更新影片狀態失敗: %s", video_id)
            raise

    def get_videos_by_status(self, status: str) -> list[dict]:
        """取得特定狀態的所有影片。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = ? ORDER BY published_at DESC",
            (status,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_videos_for_date(self, date: str) -> list[dict]:
        """取得特定日期的所有影片（依 published_at 日期篩選）。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM videos WHERE date(published_at) = ? ORDER BY published_at DESC",
            (date,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_videos_for_week(self, week_start: str, week_end: str) -> list[dict]:
        """取得特定週區間的所有影片。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM videos WHERE date(published_at) BETWEEN ? AND ? ORDER BY published_at DESC",
            (week_start, week_end),
        ).fetchall()
        return [dict(row) for row in rows]
