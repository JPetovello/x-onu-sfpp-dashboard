import json
import os
import sqlite3
import tempfile
import unittest

from alerts import AlertManager


from contextlib import closing
class AlertRuntimePersistenceTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.tempdir.name,
            "alerts.db",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_runtime_state_round_trips_across_restart(self):
        manager = AlertManager(self.db_path)

        quality_state = (
            "core_quality",
            "rx_power_dBm",
        )

        active_state = (
            "quality_active",
            quality_state,
        )

        pending_state = (
            "quality_pending",
            quality_state,
        )

        counter_state = (
            "counter",
            "bip_errors",
        )

        cooldown_state = (
            "alert",
            "bip_errors",
        )

        manager.previous[quality_state] = (
            "FAIR",
            "warn",
            -25.0,
        )

        manager.previous[active_state] = "warn"

        manager.pending[pending_state] = {
            "level": "warn",
            "count": 2,
            "previous_text": "GOOD",
            "previous_value": -16.0,
        }

        manager.previous[counter_state] = 100

        manager.pending[counter_state] = {
            "previous_value": 100,
            "delta": 5,
        }

        manager.last_alert[cooldown_state] = 12345.0

        manager._persist_runtime_state()

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous[
                quality_state
            ],
            (
                "FAIR",
                "warn",
                -25.0,
            ),
        )

        self.assertEqual(
            reloaded.previous[
                active_state
            ],
            "warn",
        )

        self.assertEqual(
            reloaded.pending[
                pending_state
            ],
            {
                "level": "warn",
                "count": 2,
                "previous_text": "GOOD",
                "previous_value": -16.0,
            },
        )

        self.assertEqual(
            reloaded.previous[
                counter_state
            ],
            100,
        )

        self.assertEqual(
            reloaded.pending[
                counter_state
            ],
            {
                "previous_value": 100,
                "delta": 5,
            },
        )

        self.assertEqual(
            reloaded.last_alert[
                cooldown_state
            ],
            12345.0,
        )

    def test_core_processing_is_persisted(self):
        manager = AlertManager(self.db_path)

        manager.process_core_sample(
            "2026-09-14T18:00:00+00:00",
            {},
        )

        reloaded = AlertManager(self.db_path)

        self.assertIs(
            reloaded.previous[
                ("core_reachability",)
            ],
            True,
        )

    def test_advanced_counter_baseline_is_persisted(self):
        manager = AlertManager(self.db_path)

        manager.process_sample(
            "2026-09-14T18:00:00+00:00",
            {
                "bip_errors": 25,
            },
        )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous[
                (
                    "counter",
                    "bip_errors",
                )
            ],
            25,
        )

    def test_pending_reachability_debounce_survives_restart(self):
        manager = AlertManager(self.db_path)

        manager.process_core_unreachable(
            "2026-09-14T18:00:00+00:00"
        )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.pending[
                ("core_reachability",)
            ]["count"],
            1,
        )

    def test_config_mismatch_rejects_runtime_state(self):
        manager = AlertManager(self.db_path)

        manager.previous[
            ("core_reachability",)
        ] = True

        manager._persist_runtime_state()

        with closing(sqlite3.connect(
            self.db_path
        )) as con, con:
            con.execute(
                """
                UPDATE alert_runtime_state
                SET config_json = ?
                WHERE id = 1
                """,
                (
                    json.dumps(
                        {"mismatch": True}
                    ),
                ),
            )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous,
            {},
        )

        self.assertEqual(
            reloaded.pending,
            {},
        )

        self.assertEqual(
            reloaded.last_alert,
            {},
        )

    def test_corrupt_runtime_state_is_ignored(self):
        manager = AlertManager(self.db_path)

        config_json = manager._runtime_config_json(
            manager.get_config()
        )

        with closing(sqlite3.connect(
            self.db_path
        )) as con, con:
            con.execute(
                """
                INSERT INTO alert_runtime_state (
                    id,
                    config_json,
                    state_json
                )
                VALUES (1, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    config_json = excluded.config_json,
                    state_json = excluded.state_json
                """,
                (
                    config_json,
                    "{not-json",
                ),
            )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous,
            {},
        )

        self.assertEqual(
            reloaded.pending,
            {},
        )

        self.assertEqual(
            reloaded.last_alert,
            {},
        )

    def test_config_rebaseline_is_persisted(self):
        manager = AlertManager(self.db_path)

        tx_state = (
            "core_quality",
            "tx_power_dBm",
        )

        rx_state = (
            "core_quality",
            "rx_power_dBm",
        )

        manager.previous[tx_state] = (
            "GOOD",
            "good",
            5.0,
        )

        manager.previous[rx_state] = (
            "GOOD",
            "good",
            -16.0,
        )

        config = manager.get_config()

        config["quality"]["rx_power"][
            "poor_low"
        ] -= 0.1

        manager.save_config(config)

        reloaded = AlertManager(self.db_path)

        self.assertNotIn(
            rx_state,
            reloaded.previous,
        )

        self.assertIn(
            tx_state,
            reloaded.previous,
        )

    def test_semantically_invalid_runtime_state_is_ignored(
        self,
    ):
        manager = AlertManager(self.db_path)

        config_json = manager._runtime_config_json(
            manager.get_config()
        )

        payload = {
            "version": 1,
            "previous":
                manager._encode_runtime_value(
                    {
                        (
                            "core_reachability",
                        ): "not-a-bool",
                    }
                ),
            "pending":
                manager._encode_runtime_value(
                    {}
                ),
            "last_alert":
                manager._encode_runtime_value(
                    {}
                ),
        }

        with closing(sqlite3.connect(
            self.db_path
        )) as con, con:
            con.execute(
                """
                INSERT INTO alert_runtime_state (
                    id,
                    config_json,
                    state_json
                )
                VALUES (1, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    config_json = excluded.config_json,
                    state_json = excluded.state_json
                """,
                (
                    config_json,
                    json.dumps(payload),
                ),
            )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous,
            {},
        )
        self.assertEqual(
            reloaded.pending,
            {},
        )
        self.assertEqual(
            reloaded.last_alert,
            {},
        )

    def test_non_finite_runtime_state_is_ignored(
        self,
    ):
        manager = AlertManager(self.db_path)

        config_json = manager._runtime_config_json(
            manager.get_config()
        )

        payload = {
            "version": 1,
            "previous":
                manager._encode_runtime_value(
                    {}
                ),
            "pending":
                manager._encode_runtime_value(
                    {}
                ),
            "last_alert":
                manager._encode_runtime_value(
                    {
                        (
                            "alert",
                            "bip_errors",
                        ): float("nan"),
                    }
                ),
        }

        with closing(sqlite3.connect(
            self.db_path
        )) as con, con:
            con.execute(
                """
                INSERT INTO alert_runtime_state (
                    id,
                    config_json,
                    state_json
                )
                VALUES (1, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    config_json = excluded.config_json,
                    state_json = excluded.state_json
                """,
                (
                    config_json,
                    json.dumps(payload),
                ),
            )

        reloaded = AlertManager(self.db_path)

        self.assertEqual(
            reloaded.previous,
            {},
        )
        self.assertEqual(
            reloaded.pending,
            {},
        )
        self.assertEqual(
            reloaded.last_alert,
            {},
        )


if __name__ == "__main__":
    unittest.main()
