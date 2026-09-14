import json
import os
import tempfile
import unittest

from retention import RetentionManager


from contextlib import closing
class RetentionConfigTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.tempdir.name,
            "retention.db",
        )
        self.manager = RetentionManager(
            self.db_path,
            new_install=True,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _store_raw(self, value):
        with closing(self.manager._connect_db()) as con, con:
            con.execute(
                """
                UPDATE retention_config
                SET config_json = ?
                WHERE id = 1
                """,
                (value,),
            )

    def test_malformed_json_falls_back_to_defaults(self):
        self._store_raw("{not-json")

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 90,
                "alert_days": 365,
            },
        )

    def test_non_object_json_falls_back_to_defaults(self):
        self._store_raw("[]")

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 90,
                "alert_days": 365,
            },
        )

    def test_invalid_fields_fall_back_independently(self):
        self._store_raw(
            json.dumps(
                {
                    "telemetry_days": "bad",
                    "alert_days": 90,
                }
            )
        )

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 90,
                "alert_days": 90,
            },
        )

        self._store_raw(
            json.dumps(
                {
                    "telemetry_days": 30,
                    "alert_days": "bad",
                }
            )
        )

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 30,
                "alert_days": 365,
            },
        )

    def test_legacy_positive_telemetry_value_is_preserved(self):
        self._store_raw(
            json.dumps(
                {
                    "telemetry_days": 45,
                    "alert_days": 90,
                }
            )
        )

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 45,
                "alert_days": 90,
            },
        )

    def test_pathological_telemetry_value_falls_back_to_default(self):
        self._store_raw(
            json.dumps(
                {
                    "telemetry_days": 10**12,
                    "alert_days": 90,
                }
            )
        )

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 90,
                "alert_days": 90,
            },
        )

    def test_boolean_values_are_rejected(self):
        self._store_raw(
            json.dumps(
                {
                    "telemetry_days": True,
                    "alert_days": False,
                }
            )
        )

        self.assertEqual(
            self.manager.get_config(),
            {
                "telemetry_days": 90,
                "alert_days": 365,
            },
        )


if __name__ == "__main__":
    unittest.main()
