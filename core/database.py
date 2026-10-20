"""
SQLite database management for processed posts tracking, activity logs, and repost statistics.
"""

from __future__ import annotations
import sqlite3
import os
import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reposter.db"
)


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Processed posts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_posts (
                    post_id TEXT PRIMARY KEY,
                    channel TEXT,
                    source_date TEXT,
                    text_snippet TEXT,
                    has_photo INTEGER DEFAULT 0,
                    status TEXT,
                    mriyu_msg_id TEXT,
                    error_detail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Activity logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    message TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_post_processed(self, post_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_id,))
            return cursor.fetchone() is not None

    def mark_post_processed(
        self,
        post_id: str,
        channel: str,
        source_date: Optional[str] = None,
        text_snippet: Optional[str] = None,
        has_photo: bool = False,
        status: str = "reposted",
        mriyu_msg_id: Optional[str] = None,
        error_detail: Optional[str] = None,
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_posts
                (post_id, channel, source_date, text_snippet, has_photo, status, mriyu_msg_id, error_detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                post_id,
                channel,
                source_date or "",
                (text_snippet or "")[:200],
                1 if has_photo else 0,
                status,
                str(mriyu_msg_id or ""),
                error_detail or "",
            ))
            conn.commit()

    def add_log(self, level: str, message: str, details: str = ""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (level, message, details, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (level.upper(), message, details))
            conn.commit()

    def get_recent_logs(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if level:
                cursor.execute("""
                    SELECT id, level, message, details, timestamp
                    FROM activity_logs
                    WHERE level = ?
                    ORDER BY id DESC LIMIT ?
                """, (level.upper(), limit))
            else:
                cursor.execute("""
                    SELECT id, level, message, details, timestamp
                    FROM activity_logs
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_recent_posts(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT post_id, channel, source_date, text_snippet, has_photo, status, mriyu_msg_id, error_detail, created_at
                FROM processed_posts
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_posts")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_posts WHERE status = 'reposted'")
            reposted = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_posts WHERE status = 'filtered'")
            filtered = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_posts WHERE status = 'error'")
            errors = cursor.fetchone()[0]

            cursor.execute("""
                SELECT created_at FROM processed_posts 
                WHERE status = 'reposted' 
                ORDER BY created_at DESC LIMIT 1
            """)
            last_repost_row = cursor.fetchone()
            last_repost = last_repost_row[0] if last_repost_row else None

            return {
                "total_processed": total,
                "reposted": reposted,
                "filtered": filtered,
                "errors": errors,
                "last_repost_time": last_repost,
            }

    def clear_logs(self):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM activity_logs")
            conn.commit()

    def clear_processed_posts(self):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM processed_posts")
            conn.commit()

