import json
import sqlite3
import tempfile
import unittest

from copy import deepcopy
from pathlib import Path

from alerts import AlertManager, DEFAULT_ALERT_CONFIG


class ThermalConfigV4Tests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "alerts.db")
        self.manager = AlertManager(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_separate_defaults(self):
        config = self.manager.get_config()
        self.assertEqual(config["config_version"], 4)
        self.assertEqual(
            config["quality"]["thermal"],
            {
                "warm": 75,
                "hot": 85,
                "optic_warm": 60,
                "optic_hot": 70,
            },
        )

    def test_default_v3_migration(self):
        legacy = deepcopy(DEFAULT_ALERT_CONFIG)
        legacy["config_version"] = 3
        legacy["quality"]["thermal"] = {
            "warm": 75,
            "hot": 85,
        }

        migrated = self.manager._normalize_config_shape(
            legacy
        )

        self.assertEqual(migrated["config_version"], 4)
        self.assertEqual(
            migrated["quality"]["thermal"],
            {
                "warm": 75,
                "hot": 85,
                "optic_warm": 60,
                "optic_hot": 70,
            },
        )
        self.manager.validate_config(migrated)

    def test_custom_v3_policy_is_preserved(self):
        legacy = deepcopy(DEFAULT_ALERT_CONFIG)
        legacy["config_version"] = 3
        legacy["quality"]["thermal"] = {
            "warm": 66,
            "hot": 78,
        }

        migrated = self.manager._normalize_config_shape(
            legacy
        )

        self.assertEqual(
            migrated["quality"]["thermal"],
            {
                "warm": 66,
                "hot": 78,
                "optic_warm": 66,
                "optic_hot": 78,
            },
        )
        self.manager.validate_config(migrated)

    def test_invalid_optic_thresholds_rejected(self):
        for bad in (
            {"optic_warm": 70, "optic_hot": 60},
            {"optic_warm": 60, "optic_hot": 60},
            {"optic_warm": True, "optic_hot": 70},
            {"optic_warm": float("nan"), "optic_hot": 70},
        ):
            with self.subTest(bad=bad):
                config = deepcopy(DEFAULT_ALERT_CONFIG)
                config["quality"]["thermal"].update(bad)

                with self.assertRaises(ValueError):
                    self.manager.validate_config(config)

    def test_existing_saved_configuration_loads(self):
        legacy = deepcopy(DEFAULT_ALERT_CONFIG)
        legacy["config_version"] = 3
        legacy["quality"]["thermal"] = {
            "warm": 68,
            "hot": 82,
        }

        original = json.dumps(legacy)

        with sqlite3.connect(self.db) as con:
            con.execute(
                "UPDATE alert_config SET config_json=? "
                "WHERE id=1",
                (original,),
            )

        manager = AlertManager(self.db)

        self.assertEqual(
            manager.get_config()["quality"]["thermal"],
            {
                "warm": 68,
                "hot": 82,
                "optic_warm": 68,
                "optic_hot": 82,
            },
        )

        with sqlite3.connect(self.db) as con:
            stored = con.execute(
                "SELECT config_json FROM alert_config "
                "WHERE id=1"
            ).fetchone()[0]

        self.assertEqual(stored, original)

    def test_v4_round_trip(self):
        config = self.manager.get_config()
        config["quality"]["thermal"].update({
            "warm": 74,
            "hot": 84,
            "optic_warm": 58,
            "optic_hot": 69,
        })

        self.manager.save_config(config)
        reloaded = AlertManager(self.db)

        self.assertEqual(
            reloaded.get_config()["quality"]["thermal"],
            config["quality"]["thermal"],
        )


if __name__ == "__main__":
    unittest.main()
