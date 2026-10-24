"""Isolated regression tests for revocable browser sessions."""

import hashlib
from contextlib import closing
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from browser_sessions import (
    BrowserSessions,
    BROWSER_SECONDS,
    REMEMBER_SECONDS,
    MAX_SESSIONS,
)


class BrowserSessionTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(
            prefix="xonu-browser-test-"
        )
        self.addCleanup(tmp.cleanup)

        self.db_path = Path(tmp.name) / "test.sqlite"
        self.sessions = BrowserSessions(str(self.db_path))
        self.sessions.initialize()

    def test_database_initialization(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table'"
                )
            }

        self.assertIn("browser_sessions", tables)

        # Reinitialization must preserve existing sessions.
        token, _ = self.sessions.issue()
        self.sessions.initialize()
        self.assertIsNotNone(self.sessions.find(token))

    def test_random_session_tokens(self):
        tokens = {
            self.sessions.issue()[0]
            for _ in range(10)
        }

        self.assertEqual(len(tokens), 10)

        for token in tokens:
            self.assertRegex(
                token,
                r"^[A-Za-z0-9_-]{43}$",
            )

    def test_normal_session_lifetime(self):
        now = 2_000_000_000

        with patch("browser_sessions.time.time",
                   return_value=now):
            token, expiry = self.sessions.issue(False)

        self.assertEqual(expiry, now + BROWSER_SECONDS)
        self.assertFalse(
            self.sessions.find(token)["remembered"]
        )

    def test_remembered_session_lifetime(self):
        now = 2_000_000_000

        with patch("browser_sessions.time.time",
                   return_value=now):
            token, expiry = self.sessions.issue(True)

        self.assertEqual(expiry, now + REMEMBER_SECONDS)
        self.assertTrue(
            self.sessions.find(token)["remembered"]
        )

    def test_adjustable_remembered_session_duration(self):
        now = 2_000_000_000

        for days in (1, 3, 7, 14, 30):
            with self.subTest(days=days):
                with patch(
                    "browser_sessions.time.time",
                    return_value=now,
                ):
                    token, expiry = self.sessions.issue(
                        remember=True,
                        remember_days=days,
                    )

                self.assertEqual(
                    expiry,
                    now + days * 24 * 60 * 60,
                )

    def test_invalid_session_durations_are_rejected(self):
        for days in (0, 2, 31, -1, "30", None, True, 1.5):
            with self.subTest(days=days):
                with self.assertRaises(ValueError):
                    self.sessions.issue(
                        remember=True,
                        remember_days=days,
                    )

    def test_expired_sessions_are_rejected(self):
        now = 2_000_000_000

        with patch("browser_sessions.time.time",
                   return_value=now):
            token, expiry = self.sessions.issue(True)

        with patch("browser_sessions.time.time",
                   return_value=expiry):
            self.assertIsNone(self.sessions.find(token))
            self.assertEqual(self.sessions.active(), [])

    def test_invalid_tokens_are_rejected(self):
        for token in (
            None,
            "",
            "invalid",
            "a" * 42,
            "a" * 44,
            "!" * 43,
        ):
            self.assertIsNone(self.sessions.find(token))
            self.assertFalse(self.sessions.revoke(token))

    def test_session_revocation(self):
        token, _ = self.sessions.issue()

        self.assertIsNotNone(self.sessions.find(token))
        self.assertTrue(self.sessions.revoke(token))
        self.assertIsNone(self.sessions.find(token))
        self.assertFalse(self.sessions.revoke(token))

    def test_revoke_one_session_without_affecting_another(self):
        first, _ = self.sessions.issue()
        second, _ = self.sessions.issue()

        first_id = self.sessions.find(first)["id"]

        self.assertTrue(self.sessions.revoke_id(first_id))
        self.assertIsNone(self.sessions.find(first))
        self.assertIsNotNone(self.sessions.find(second))

    def test_csrf_verification(self):
        token, _ = self.sessions.issue()
        csrf = self.sessions.csrf_token(token)

        self.assertTrue(
            self.sessions.verify_csrf(token, csrf)
        )
        self.assertFalse(
            self.sessions.verify_csrf(token, "wrong")
        )
        self.assertFalse(
            self.sessions.verify_csrf(None, csrf)
        )

        other, _ = self.sessions.issue()

        self.assertFalse(
            self.sessions.verify_csrf(other, csrf)
        )

    def test_raw_token_not_stored_in_database(self):
        token, _ = self.sessions.issue()

        with closing(sqlite3.connect(self.db_path)) as db:
            stored = db.execute(
                "SELECT token_hash FROM browser_sessions"
            ).fetchone()[0]

        self.assertNotEqual(stored, token)
        self.assertEqual(
            stored,
            hashlib.sha256(
                token.encode("ascii")
            ).hexdigest(),
        )

    def test_session_limit(self):
        tokens = []

        for i in range(MAX_SESSIONS + 3):
            with patch("browser_sessions.time.time",
                       return_value=2_000_000_000 + i):
                token, _ = self.sessions.issue()
                tokens.append(token)

        with patch("browser_sessions.time.time",
                   return_value=2_000_000_100):
            active = self.sessions.active()

            self.assertEqual(len(active), MAX_SESSIONS)
            self.assertIsNone(
                self.sessions.find(tokens[0])
            )
            self.assertIsNotNone(
                self.sessions.find(tokens[-1])
            )

    def test_invalid_remember_value(self):
        with self.assertRaises(ValueError):
            self.sessions.issue("yes")

    def test_browser_label_is_bounded(self):
        token, _ = self.sessions.issue(
            browser_label="A" * 500
        )

        record = self.sessions.find(token)

        self.assertEqual(
            len(record["browser_label"]),
            120,
        )


if __name__ == "__main__":
    unittest.main()
