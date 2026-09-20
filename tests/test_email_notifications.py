import json
import smtplib
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from notifications import (
    DEFAULT_NOTIFICATION_CONFIG,
    GMAIL_SMTP_HOST,
    GMAIL_SMTP_PORT,
    GMAIL_SMTP_TIMEOUT_SECONDS,
    NotificationManager,
)


class EmailNotificationTests(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = str(
            Path(self.temporary_directory.name)
            / "dashboard.db"
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def make_manager(self):
        with patch(
            "notifications.threading.Thread.start"
        ):
            return NotificationManager(self.db_path)

    @staticmethod
    def enabled_email_config():
        config = deepcopy(DEFAULT_NOTIFICATION_CONFIG)
        config["email"] = {
            "enabled": True,
            "username": "sender@workspace.example",
            "app_password": "example-app-password",
            "to_address": "recipient@example.net",
        }
        return config

    def write_raw_config(self, config):
        with closing(
            sqlite3.connect(self.db_path)
        ) as con, con:
            con.execute("""
                CREATE TABLE notification_config (
                    id INTEGER PRIMARY KEY
                        CHECK (id = 1),
                    config_json TEXT NOT NULL
                )
            """)
            con.execute(
                """
                INSERT INTO notification_config (
                    id,
                    config_json
                )
                VALUES (1, ?)
                """,
                (json.dumps(config),),
            )

    def read_raw_config(self):
        with closing(
            sqlite3.connect(self.db_path)
        ) as con:
            row = con.execute(
                """
                SELECT config_json
                FROM notification_config
                WHERE id = 1
                """
            ).fetchone()

        return json.loads(row[0])

    def test_legacy_config_migrates_without_changing_values(self):
        legacy = deepcopy(DEFAULT_NOTIFICATION_CONFIG)
        legacy.pop("email")
        legacy["discord"]["webhook_url"] = (
            "https://discord.com/api/webhooks/123/secret"
        )
        legacy["gotify"]["server_url"] = (
            "https://gotify.example.com"
        )
        legacy["gotify"]["token"] = "gotify-secret"
        legacy["pushover"]["user_key"] = "user-secret"
        legacy["pushover"]["api_token"] = "api-secret"
        legacy["ntfy"]["topic"] = "saved-topic"
        legacy["ntfy"]["token"] = "ntfy-secret"
        legacy["webhook"]["url"] = (
            "https://example.com/private-hook"
        )
        self.write_raw_config(legacy)

        self.make_manager()

        migrated = self.read_raw_config()

        for provider, settings in legacy.items():
            self.assertEqual(
                migrated[provider],
                settings,
            )

        self.assertEqual(
            migrated["email"],
            DEFAULT_NOTIFICATION_CONFIG["email"],
        )
        self.assertFalse(migrated["email"]["enabled"])

    def test_unknown_legacy_provider_is_not_migrated(self):
        legacy = deepcopy(DEFAULT_NOTIFICATION_CONFIG)
        legacy.pop("email")
        legacy["unknown"] = {
            "enabled": False,
        }
        original = deepcopy(legacy)
        self.write_raw_config(legacy)

        manager = self.make_manager()

        self.assertEqual(
            self.read_raw_config(),
            original,
        )

        with self.assertRaises(ValueError):
            manager.validate_config(legacy)

    def test_malformed_legacy_provider_is_not_persisted(self):
        legacy = deepcopy(DEFAULT_NOTIFICATION_CONFIG)
        legacy.pop("email")
        legacy["discord"] = "malformed"
        original = deepcopy(legacy)
        self.write_raw_config(legacy)

        manager = self.make_manager()

        self.assertEqual(
            self.read_raw_config(),
            original,
        )

        migrated, changed = manager._migrate_config(
            legacy
        )
        self.assertTrue(changed)

        with self.assertRaises(ValueError):
            manager.validate_config(migrated)

    def test_app_password_is_masked_by_public_config(self):
        manager = self.make_manager()
        manager.save_config(
            self.enabled_email_config()
        )

        public = manager.get_config()

        self.assertEqual(
            public["email"]["app_password"],
            "",
        )
        self.assertTrue(
            public["email"][
                "app_password_configured"
            ]
        )

    def test_blank_configured_app_password_preserves_secret(self):
        manager = self.make_manager()
        manager.save_config(
            self.enabled_email_config()
        )
        public = manager.get_config()

        saved = manager.save_config(public)

        self.assertTrue(
            saved["email"][
                "app_password_configured"
            ]
        )
        self.assertEqual(
            self.read_raw_config()["email"][
                "app_password"
            ],
            "example-app-password",
        )

    def test_explicit_clear_removes_app_password(self):
        manager = self.make_manager()
        manager.save_config(
            self.enabled_email_config()
        )
        public = manager.get_config()
        public["email"]["enabled"] = False
        public["email"][
            "app_password_configured"
        ] = False

        saved = manager.save_config(public)

        self.assertFalse(
            saved["email"][
                "app_password_configured"
            ]
        )
        self.assertEqual(
            self.read_raw_config()["email"][
                "app_password"
            ],
            "",
        )

    def test_invalid_and_control_character_addresses_rejected(self):
        manager = self.make_manager()

        invalid_addresses = (
            "not-an-address",
            "sender@example.com\nBcc: attacker@example.net",
            "sender@example.com\rBcc: attacker@example.net",
            "\tsender@example.com",
            "sender @example.com",
            "sender@example..com",
        )

        for field in (
            "username",
            "to_address",
        ):
            for address in invalid_addresses:
                with self.subTest(
                    field=field,
                    address=address,
                ):
                    config = self.enabled_email_config()
                    config["email"][field] = address

                    with self.assertRaises(ValueError):
                        manager.validate_config(config)

    def test_enabled_email_requires_all_fields(self):
        manager = self.make_manager()

        for field in (
            "username",
            "app_password",
            "to_address",
        ):
            with self.subTest(field=field):
                config = self.enabled_email_config()
                config["email"][field] = ""

                with self.assertRaises(ValueError):
                    manager.validate_config(config)

    def test_send_email_uses_gmail_ssl_and_expected_message(self):
        manager = NotificationManager.__new__(
            NotificationManager
        )
        manager.lock = threading.Lock()
        config = self.enabled_email_config()
        context = object()
        smtp = Mock()
        smtp_context = Mock()
        smtp_context.__enter__ = Mock(
            return_value=smtp
        )
        smtp_context.__exit__ = Mock(
            return_value=False
        )
        event = {
            "severity": "critical",
            "message": "Optical signal out of range",
            "metric": "rx_power",
        }

        with (
            patch(
                "notifications.NOTIFICATION_CONFIG",
                config,
            ),
            patch(
                "notifications.ssl.create_default_context",
                return_value=context,
            ) as create_context,
            patch(
                "notifications.smtplib.SMTP_SSL",
                return_value=smtp_context,
            ) as smtp_ssl,
        ):
            manager._send_email(event)

        create_context.assert_called_once_with()
        smtp_ssl.assert_called_once_with(
            GMAIL_SMTP_HOST,
            GMAIL_SMTP_PORT,
            timeout=GMAIL_SMTP_TIMEOUT_SECONDS,
            context=context,
        )
        self.assertGreater(
            GMAIL_SMTP_TIMEOUT_SECONDS,
            0,
        )
        smtp.login.assert_called_once_with(
            "sender@workspace.example",
            "example-app-password",
        )
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(
            message["From"],
            "sender@workspace.example",
        )
        self.assertEqual(
            message["To"],
            "recipient@example.net",
        )
        self.assertEqual(
            message["Subject"],
            "X-ONU-SFPP Dashboard - CRITICAL",
        )
        body = message.get_content()
        self.assertIn("Severity: CRITICAL", body)
        self.assertIn(
            "Alert: Optical signal out of range",
            body,
        )
        self.assertIn("Metric: rx_power", body)

    def test_smtp_failure_does_not_escape_sender(self):
        manager = NotificationManager.__new__(
            NotificationManager
        )
        manager.lock = threading.Lock()
        config = self.enabled_email_config()

        with (
            patch(
                "notifications.NOTIFICATION_CONFIG",
                config,
            ),
            patch(
                "notifications.smtplib.SMTP_SSL",
                side_effect=smtplib.SMTPException(
                    "simulated failure"
                ),
            ),
        ):
            manager._send_email(
                {
                    "severity": "warning",
                    "message": "Test alert",
                }
            )


if __name__ == "__main__":
    unittest.main()
