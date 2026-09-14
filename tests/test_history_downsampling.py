import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app as app_module
from advanced import AdvancedCollector


class HistoryDownsamplingTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

        self.core_db = os.path.join(
            self.tempdir.name,
            "core.db",
        )

        self.advanced_db = os.path.join(
            self.tempdir.name,
            "advanced.db",
        )

        self.base_time = (
            datetime.now(timezone.utc)
            - timedelta(minutes=30)
        )

        self._create_core_db()
        self._create_advanced_db()

    def tearDown(self):
        self.tempdir.cleanup()

    def _timestamp(self, index):
        return (
            self.base_time
            + timedelta(seconds=index)
        ).isoformat()

    def _create_core_db(self):
        with sqlite3.connect(self.core_db) as con:
            con.execute("""
                CREATE TABLE samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    cpu1_tempC REAL,
                    cpu2_tempC REAL,
                    module_voltage REAL,
                    optic_tempC REAL,
                    ploam_state INTEGER,
                    rx_power_dBm REAL,
                    tx_bias_mA REAL,
                    tx_power_dBm REAL
                )
            """)

            con.execute("""
                CREATE INDEX idx_samples_ts
                ON samples(ts)
            """)

    def _create_advanced_db(self):
        with sqlite3.connect(self.advanced_db) as con:
            con.execute("""
                CREATE TABLE advanced_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    gem_id INTEGER,
                    upload_bps REAL,
                    download_bps REAL,
                    key_errors INTEGER,
                    bip_errors INTEGER,
                    corrected_fec_codewords INTEGER,
                    uncorrected_fec_codewords INTEGER,
                    fec_errored_seconds INTEGER,
                    psbd_hec_uncorrected INTEGER,
                    fs_hec_uncorrected INTEGER,
                    ploam_mic_errors INTEGER,
                    active_alarm_count INTEGER,
                    ont_uptime_seconds REAL,
                    load_1m REAL,
                    load_5m REAL,
                    load_15m REAL,
                    memory_total_kb INTEGER,
                    memory_used_kb INTEGER,
                    memory_available_kb INTEGER
                )
            """)

            con.execute("""
                CREATE INDEX idx_advanced_samples_ts
                ON advanced_samples(ts)
            """)

    def _insert_core_rows(self, count):
        rows = [
            (
                self._timestamp(index),
                float(index),
                float(index + 1),
                3.3,
                float(index + 2),
                51,
                -20.0,
                10.0,
                6.0,
            )
            for index in range(count)
        ]

        with sqlite3.connect(self.core_db) as con:
            con.executemany(
                """
                INSERT INTO samples (
                    ts,
                    cpu1_tempC,
                    cpu2_tempC,
                    module_voltage,
                    optic_tempC,
                    ploam_state,
                    rx_power_dBm,
                    tx_bias_mA,
                    tx_power_dBm
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _insert_advanced_rows(self, count):
        rows = [
            (
                self._timestamp(index),
                index,
            )
            for index in range(count)
        ]

        with sqlite3.connect(self.advanced_db) as con:
            con.executemany(
                """
                INSERT INTO advanced_samples (
                    ts,
                    gem_id
                )
                VALUES (?, ?)
                """,
                rows,
            )

    def _core_history(self):
        with (
            patch.object(
                app_module,
                "DB_PATH",
                self.core_db,
            ),
            patch.object(
                app_module,
                "DATA_DIR",
                self.tempdir.name,
            ),
        ):
            client = app_module.app.test_client()

            response = client.get(
                "/api/history?range=1h"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        return response.get_json()

    def _advanced_history(self):
        collector = AdvancedCollector.__new__(
            AdvancedCollector
        )

        collector.db_path = self.advanced_db

        return collector.history("1h")

    def test_core_small_history_preserves_every_row(self):
        self._insert_core_rows(10)

        history = self._core_history()

        self.assertEqual(
            len(history),
            10,
        )

        self.assertEqual(
            [row["cpu1_tempC"] for row in history],
            [float(index) for index in range(10)],
        )

    def test_core_large_history_preserves_existing_sampling(self):
        self._insert_core_rows(1801)

        history = self._core_history()

        # Existing behavior:
        # step = 1801 // 900 = 2
        # rows[::2] returns indexes 0..1800.
        expected = list(
            range(
                0,
                1801,
                2,
            )
        )

        self.assertEqual(
            len(history),
            len(expected),
        )

        self.assertEqual(
            [row["cpu1_tempC"] for row in history],
            [float(index) for index in expected],
        )

    def test_advanced_small_history_preserves_every_row(self):
        self._insert_advanced_rows(10)

        history = self._advanced_history()

        self.assertEqual(
            len(history),
            10,
        )

        self.assertEqual(
            [row["gem_id"] for row in history],
            list(range(10)),
        )

    def test_advanced_large_history_preserves_existing_sampling(self):
        self._insert_advanced_rows(1801)

        history = self._advanced_history()

        expected = list(
            range(
                0,
                1801,
                2,
            )
        )

        self.assertEqual(
            len(history),
            len(expected),
        )

        self.assertEqual(
            [row["gem_id"] for row in history],
            expected,
        )


if __name__ == "__main__":
    unittest.main()
