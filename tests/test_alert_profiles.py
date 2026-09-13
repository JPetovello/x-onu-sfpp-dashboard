import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from alerts import (
    AlertManager,
    DEFAULT_ALERT_CONFIG,
    TX_PROFILES,
    TX_PROFILE_CUSTOM,
    TX_PROFILE_XGSPONST2001_A01,
)


class AlertProfileTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(
            Path(self.tempdir.name) / "metrics.db"
        )
        self.manager = AlertManager(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def custom_config(self, **overrides):
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        tx = config["quality"]["tx_power"]
        tx.update(
            {
                "profile": TX_PROFILE_CUSTOM,
                "cosmetic_great_low": None,
                "cosmetic_great_high": None,
            }
        )
        tx.update(overrides)
        return config

    def test_optional_upper_threshold_combinations(self):
        combinations = (
            {
                "high_warning": None,
                "high_alarm": None,
            },
            {
                "high_warning": 7,
                "high_alarm": None,
            },
            {
                "high_warning": None,
                "high_alarm": 8,
            },
            {
                "high_warning": 7,
                "high_alarm": 8,
            },
        )

        for values in combinations:
            with self.subTest(values=values):
                config = self.custom_config(**values)
                self.assertEqual(
                    self.manager.validate_config(config),
                    config,
                )

    def test_invalid_threshold_ordering_is_rejected(self):
        invalid_values = (
            {
                "low_alarm": 3,
                "low_warning": 3,
            },
            {
                "high_warning": 2,
            },
            {
                "high_alarm": 2,
            },
            {
                "high_warning": 9,
                "high_alarm": 8,
            },
        )

        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.manager.validate_config(
                        self.custom_config(**values)
                    )

    def test_edited_named_profile_requires_custom(self):
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["quality"]["tx_power"][
            "low_alarm"
        ] = 1.5

        with self.assertRaises(ValueError):
            self.manager.validate_config(config)

        config["quality"]["tx_power"][
            "profile"
        ] = TX_PROFILE_CUSTOM

        self.manager.validate_config(config)

    def test_unversioned_default_becomes_legacy_without_db_rewrite(self):
        old_config = self._old_config()
        raw_json = json.dumps(old_config)

        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "UPDATE alert_config SET config_json = ? WHERE id = 1",
                (raw_json,),
            )

        manager = AlertManager(self.db_path)
        loaded = manager.get_config()

        self.assertEqual(
            loaded["quality"]["tx_power"]["profile"],
            "legacy",
        )

        with sqlite3.connect(self.db_path) as con:
            stored = con.execute(
                "SELECT config_json FROM alert_config WHERE id = 1"
            ).fetchone()[0]

        self.assertEqual(stored, raw_json)

    def test_unversioned_edited_config_becomes_custom(self):
        old_config = self._old_config()
        old_config["quality"]["tx_power"][
            "fair_high"
        ] = 7.5

        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "UPDATE alert_config SET config_json = ? WHERE id = 1",
                (json.dumps(old_config),),
            )

        manager = AlertManager(self.db_path)

        self.assertEqual(
            manager.get_config()["quality"][
                "tx_power"
            ]["profile"],
            "custom",
        )

    def test_version_two_named_profile_preserves_policy_as_custom(self):
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["config_version"] = 2
        config["quality"]["tx_power"] = {
            "profile": TX_PROFILE_XGSPONST2001_A01,
            "low_alarm": 2.0,
            "low_warning": 3.0,
            "high_warning": None,
            "high_alarm": None,
            "cosmetic_great_low": None,
            "cosmetic_great_high": None,
        }
        raw_json = json.dumps(config)

        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "UPDATE alert_config SET config_json = ? WHERE id = 1",
                (raw_json,),
            )

        manager = AlertManager(self.db_path)
        loaded = manager.get_config()

        self.assertEqual(loaded["config_version"], 3)
        self.assertEqual(
            loaded["quality"]["tx_power"]["profile"],
            "custom",
        )
        self.assertEqual(
            loaded["quality"]["tx_power"]["low_alarm"],
            2.0,
        )
        self.assertEqual(
            loaded["quality"]["tx_power"]["low_warning"],
            3.0,
        )

        with sqlite3.connect(self.db_path) as con:
            stored = con.execute(
                "SELECT config_json FROM alert_config WHERE id = 1"
            ).fetchone()[0]

        self.assertEqual(stored, raw_json)

    def test_profile_save_is_persistent_and_idempotent(self):
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["quality"]["tx_power"] = deepcopy(
            TX_PROFILES[
                TX_PROFILE_XGSPONST2001_A01
            ]["thresholds"]
        )

        self.manager.save_config(config)

        state_key = (
            "core_quality",
            "tx_power_dBm",
        )
        self.manager.previous[state_key] = (
            "NORMAL",
            "good",
            6.22,
        )

        self.manager.save_config(config)
        self.assertIn(state_key, self.manager.previous)

        reloaded = AlertManager(self.db_path)
        self.assertEqual(
            reloaded.get_config()["quality"][
                "tx_power"
            ],
            config["quality"]["tx_power"],
        )

    def test_tx_policy_change_resets_only_tx_runtime_state(self):
        tx_state = (
            "core_quality",
            "tx_power_dBm",
        )
        rx_state = (
            "core_quality",
            "rx_power_dBm",
        )
        tx_active = (
            "quality_active",
            tx_state,
        )
        tx_pending = (
            "quality_pending",
            tx_state,
        )
        rx_active = (
            "quality_active",
            rx_state,
        )

        self.manager.previous[tx_state] = (
            "FAIR", "warn", 7.1
        )
        self.manager.previous[tx_active] = "warn"
        self.manager.pending[tx_pending] = {
            "level": "warn",
            "count": 2,
        }
        self.manager.previous[rx_state] = (
            "GOOD", "good", -15.8
        )
        self.manager.previous[rx_active] = "warn"
        self.manager.pending["counter-state"] = {
            "count": 1,
        }

        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["quality"]["tx_power"] = deepcopy(
            TX_PROFILES[
                TX_PROFILE_XGSPONST2001_A01
            ]["thresholds"]
        )
        self.manager.save_config(config)

        self.assertNotIn(tx_state, self.manager.previous)
        self.assertNotIn(tx_active, self.manager.previous)
        self.assertNotIn(tx_pending, self.manager.pending)
        self.assertIn(rx_state, self.manager.previous)
        self.assertIn(rx_active, self.manager.previous)
        self.assertIn("counter-state", self.manager.pending)

    def test_custom_threshold_change_rebaselines_tx_state(self):
        config = self.custom_config(
            high_warning=None,
            high_alarm=None,
        )
        self.manager.save_config(config)

        tx_state = (
            "core_quality",
            "tx_power_dBm",
        )
        tx_active = (
            "quality_active",
            tx_state,
        )
        tx_pending = (
            "quality_pending",
            tx_state,
        )

        self.manager.previous[tx_state] = (
            "WARNING", "warn", 2.5
        )
        self.manager.previous[tx_active] = "warn"
        self.manager.pending[tx_pending] = {
            "level": "warn",
            "count": 2,
        }

        config["quality"]["tx_power"][
            "low_warning"
        ] = 3.5
        self.manager.save_config(config)

        self.assertNotIn(tx_state, self.manager.previous)
        self.assertNotIn(tx_active, self.manager.previous)
        self.assertNotIn(tx_pending, self.manager.pending)

    @staticmethod
    def _old_config():
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config.pop("config_version")
        config["quality"]["tx_power"] = {
            "poor_low": 1,
            "poor_high": 8,
            "fair_low": 2,
            "fair_high": 7,
            "great_low": 4,
            "great_high": 5,
        }
        return config


class TxAlertStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = str(
            Path(self.tempdir.name) / "metrics.db"
        )
        self.manager = AlertManager(db_path)
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["quality"]["tx_power"].update(
            {
                "profile": TX_PROFILE_CUSTOM,
                "low_alarm": 2.0,
                "low_warning": 3.0,
                "high_warning": None,
                "high_alarm": None,
                "cosmetic_great_low": None,
                "cosmetic_great_high": None,
            }
        )
        self.manager.save_config(config)
        self.events = []
        self.manager._record_event = self._record_event

    def tearDown(self):
        self.tempdir.cleanup()

    def _record_event(self, **event):
        self.events.append(event)

    def sample(self, value):
        self.manager._process_tx_power(
            "2026-09-13T00:00:00+00:00",
            {"tx_power_dBm": value},
        )

    def test_warning_debounce_and_duplicate_suppression(self):
        self.sample(2.5)
        self.sample(2.5)
        self.assertEqual(self.events, [])

        self.sample(2.5)
        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_warning"],
        )

        self.sample(2.5)
        self.assertEqual(len(self.events), 1)

    def test_interrupted_warning_sequence(self):
        self.sample(2.5)
        self.sample(2.5)
        self.sample(6.22)
        self.sample(2.5)
        self.sample(2.5)
        self.assertEqual(self.events, [])

    def test_alarm_is_immediate_and_duplicate_is_suppressed(self):
        self.sample(2.0)
        self.sample(1.99)
        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_poor"],
        )

    def test_warning_escalates_immediately_to_alarm(self):
        for _ in range(3):
            self.sample(2.5)

        self.sample(2.0)

        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_warning", "tx_power_poor"],
        )

    def test_recovery_is_immediate(self):
        self.sample(2.0)
        self.sample(6.22)

        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_poor", "tx_power_recovered"],
        )

    def test_unknown_does_not_recover_active_alarm(self):
        self.sample(2.0)
        self.sample(float("nan"))
        self.assertEqual(len(self.events), 1)

        self.sample(6.22)
        self.assertEqual(
            self.events[-1]["alert_type"],
            "tx_power_recovered",
        )

    def test_unknown_interrupts_pending_warning(self):
        self.sample(2.5)
        self.sample(2.5)
        self.sample(float("nan"))
        self.sample(2.5)
        self.sample(2.5)

        self.assertEqual(self.events, [])

    def test_alarm_to_warning_downgrade_is_debounced(self):
        self.sample(2.0)
        self.sample(2.5)
        self.sample(2.5)
        self.assertEqual(len(self.events), 1)

        self.sample(2.5)

        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_poor", "tx_power_warning"],
        )
        self.assertIn(
            "improved",
            self.events[-1]["message"],
        )


class Xgsponst2001SpecAlertTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = str(
            Path(self.tempdir.name) / "metrics.db"
        )
        self.manager = AlertManager(db_path)
        config = deepcopy(DEFAULT_ALERT_CONFIG)
        config["quality"]["tx_power"] = deepcopy(
            TX_PROFILES[
                TX_PROFILE_XGSPONST2001_A01
            ]["thresholds"]
        )
        self.manager.save_config(config)
        self.events = []
        self.manager._record_event = (
            lambda **event: self.events.append(event)
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def sample(self, value):
        self.manager._process_tx_power(
            "2026-09-13T00:00:00+00:00",
            {"tx_power_dBm": value},
        )

    def test_below_spec_is_immediate_alarm_without_warning(self):
        self.sample(3.99)

        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_poor"],
        )

    def test_above_spec_is_immediate_alarm_without_warning(self):
        self.sample(9.01)

        self.assertEqual(
            [event["alert_type"] for event in self.events],
            ["tx_power_poor"],
        )

    def test_inclusive_envelope_never_warns(self):
        for value in (4.0, 4.01, 6.22, 7.14, 7.33, 8.99, 9.0):
            self.sample(value)

        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
