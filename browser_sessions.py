"""Server-side, revocable browser sessions for optional dashboard login."""

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import closing

COOKIE_NAME = "__Host-xonu_session"
REMEMBER_SECONDS = 7 * 24 * 60 * 60
REMEMBER_DAYS_OPTIONS = (1, 3, 7, 14, 30)
BROWSER_SECONDS = 12 * 60 * 60
MAX_SESSIONS = 32

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class BrowserSessions:
    """Only hashes of bearer tokens are persisted to SQLite."""

    def __init__(self, db_path):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def initialize(self):
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS browser_sessions (
                    token_hash TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    remembered INTEGER NOT NULL,
                    browser_label TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS browser_sessions_expires
                ON browser_sessions(expires_at)
            """)

    def issue(
        self, remember=False, browser_label="", remember_days=7
    ):
        if not isinstance(remember, bool):
            raise ValueError("remember must be a boolean")

        if (
            type(remember_days) is not int
            or remember_days not in REMEMBER_DAYS_OPTIONS
        ):
            raise ValueError("Invalid remembered-session duration")

        if not isinstance(browser_label, str):
            browser_label = ""

        token = secrets.token_urlsafe(32)
        now = int(time.time())
        lifetime = (
            remember_days * 24 * 60 * 60
            if remember else BROWSER_SECONDS
        )
        expiry = now + lifetime

        with closing(self._connect()) as db, db:
            db.execute(
                "DELETE FROM browser_sessions WHERE expires_at <= ?",
                (now,),
            )
            db.execute("""
                INSERT INTO browser_sessions (
                    token_hash, created_at, expires_at,
                    remembered, browser_label
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                _token_hash(token),
                now,
                expiry,
                int(remember),
                browser_label[:120],
            ))
            db.execute("""
                DELETE FROM browser_sessions WHERE token_hash IN (
                    SELECT token_hash FROM browser_sessions
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT -1 OFFSET ?
                )
            """, (MAX_SESSIONS,))

        return token, expiry

    def find(self, token):
        if not isinstance(token, str):
            return None

        if not _TOKEN_PATTERN.fullmatch(token):
            return None

        with closing(self._connect()) as db:
            row = db.execute("""
                SELECT token_hash, created_at, expires_at,
                       remembered, browser_label
                FROM browser_sessions
                WHERE token_hash = ?
            """, (_token_hash(token),)).fetchone()

        if row is None or row[2] <= int(time.time()):
            return None

        return {
            "id": row[0],
            "created_at": row[1],
            "expires_at": row[2],
            "remembered": bool(row[3]),
            "browser_label": row[4],
        }

    @staticmethod
    def csrf_token(token):
        if not isinstance(token, str):
            return None

        if not _TOKEN_PATTERN.fullmatch(token):
            return None

        return hashlib.sha256(
            ("xonu-csrf-v1:" + token).encode("ascii")
        ).hexdigest()

    @classmethod
    def verify_csrf(cls, token, submitted):
        expected = cls.csrf_token(token)

        return (
            expected is not None
            and isinstance(submitted, str)
            and bool(_HASH_PATTERN.fullmatch(submitted))
            and hmac.compare_digest(expected, submitted)
        )

    def revoke(self, token):
        if not isinstance(token, str):
            return False

        if not _TOKEN_PATTERN.fullmatch(token):
            return False

        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "DELETE FROM browser_sessions WHERE token_hash = ?",
                (_token_hash(token),),
            )
            return cursor.rowcount > 0

    def revoke_id(self, session_id):
        if not isinstance(session_id, str):
            return False

        if not _HASH_PATTERN.fullmatch(session_id):
            return False

        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "DELETE FROM browser_sessions WHERE token_hash = ?",
                (session_id,),
            )
            return cursor.rowcount > 0

    def active(self):
        with closing(self._connect()) as db:
            rows = db.execute("""
                SELECT token_hash, created_at, expires_at,
                       remembered, browser_label
                FROM browser_sessions
                WHERE expires_at > ?
                ORDER BY created_at DESC
            """, (int(time.time()),)).fetchall()

        return [
            {
                "id": row[0],
                "created_at": row[1],
                "expires_at": row[2],
                "remembered": bool(row[3]),
                "browser_label": row[4],
            }
            for row in rows
        ]
