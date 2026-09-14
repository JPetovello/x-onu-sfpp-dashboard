import importlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock


class TelemetryValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()

        environment = {
            "DATA_DIR": cls.tempdir.name,
            "ONT_URL": "http://127.0.0.1:9/unreachable",
            "SSH_ENABLED": "false",
        }

        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(
                threading.Thread,
                "start",
                autospec=True,
            ),
        ):
            sys.modules.pop("app", None)
            cls.app_module = importlib.import_module("app")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("app", None)
        cls.tempdir.cleanup()

    def test_core_non_finite_values_become_missing(self):
        invalid_values = (
            math.nan,
            math.inf,
            -math.inf,
            "1e309",
        )

        for field in self.app_module.METRIC_COLUMNS:
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    payload = {
                        name: None
                        for name in self.app_module.METRIC_COLUMNS
                    }
                    payload[field] = value

                    metrics = self.app_module.normalize_metrics(
                        payload
                    )

                    self.assertIsNone(metrics[field])

                    serialized = json.dumps(
                        metrics,
                        allow_nan=False,
                    )
                    self.assertNotIn("NaN", serialized)
                    self.assertNotIn("Infinity", serialized)

                    browser_json = (
                        self.app_module.app.json.dumps(
                            metrics
                        )
                    )
                    json.loads(browser_json)

    def test_core_non_finite_values_are_not_persisted(self):
        payload = {
            name: None
            for name in self.app_module.METRIC_COLUMNS
        }
        payload["rx_power_dBm"] = math.inf

        metrics = self.app_module.normalize_metrics(payload)
        self.app_module.save_sample(
            metrics,
            "2026-09-14T00:00:00+00:00",
        )

        with sqlite3.connect(
            self.app_module.DB_PATH
        ) as connection:
            stored = connection.execute(
                "SELECT rx_power_dBm FROM samples "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]

        self.assertIsNone(stored)

    def test_legacy_non_finite_core_history_is_json_safe(self):
        with self.app_module.db_connect() as connection:
            connection.execute(
                """
                INSERT INTO samples (ts, rx_power_dBm)
                VALUES (?, ?)
                """,
                (
                    self.app_module.utc_now_iso(),
                    float("inf"),
                ),
            )

        response = self.app_module.app.test_client().get(
            "/api/history"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Infinity", response.data)
        self.assertIsNone(
            response.get_json()[-1]["rx_power_dBm"]
        )

    def test_advanced_api_output_has_non_finite_backstop(self):
        collector = self.app_module.advanced_collector

        with mock.patch.object(
            collector,
            "history",
            return_value=[{"load_1m": float("-inf")}],
        ):
            response = self.app_module.app.test_client().get(
                "/api/advanced/history"
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Infinity", response.data)
        self.assertIsNone(
            response.get_json()[0]["load_1m"]
        )

    def test_finite_core_values_are_preserved(self):
        payload = {
            name: None
            for name in self.app_module.METRIC_COLUMNS
        }
        payload.update(
            {
                "ploam_state": 51,
                "rx_power_dBm": -15.9,
                "tx_power_dBm": 6.2,
            }
        )

        metrics = self.app_module.normalize_metrics(payload)

        self.assertEqual(metrics["ploam_state"], 51)
        self.assertEqual(metrics["rx_power_dBm"], -15.9)
        self.assertEqual(metrics["tx_power_dBm"], 6.2)

    def test_decimal_string_ploam_state_remains_invalid(self):
        payload = {
            name: None
            for name in self.app_module.METRIC_COLUMNS
        }
        payload["ploam_state"] = "51.9"

        with self.assertRaises(ValueError):
            self.app_module.normalize_metrics(payload)

    def test_advanced_non_finite_values_become_missing(self):
        safe_float = (
            self.app_module.AdvancedCollector._safe_float
        )

        for value in (
            math.nan,
            math.inf,
            -math.inf,
            "1e309",
        ):
            with self.subTest(value=value):
                self.assertIsNone(safe_float(value))

        self.assertEqual(safe_float("1.25"), 1.25)

        parsed = self.app_module.advanced_collector._parse_system(
            "UPTIME Infinity\n"
            "LOAD NaN 1e309 -Infinity"
        )

        self.assertIsNone(parsed["ont_uptime_seconds"])
        self.assertIsNone(parsed["load_1m"])
        self.assertIsNone(parsed["load_5m"])
        self.assertIsNone(parsed["load_15m"])

    def test_error_summary_does_not_persist_raw_input(self):
        marker = "<img src=x onerror=alert(1)>"

        summary = self.app_module.core_error_summary(
            ValueError(marker)
        )

        self.assertEqual(
            summary,
            "Core telemetry contained an invalid value",
        )
        self.assertNotIn(marker, summary)


if __name__ == "__main__":
    unittest.main()
