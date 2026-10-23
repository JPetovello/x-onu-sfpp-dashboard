import tempfile
import unittest
from pathlib import Path

from alerts import AlertManager


class IndependentThermalAlertTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "alerts.db")
        self.manager = AlertManager(self.db)
        self.events = []
        self.manager._record_event = (
            lambda **event: self.events.append(event)
        )

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, **metrics):
        self.manager._process_thermal_state(
            "2026-10-23T16:00:00+00:00",
            metrics,
        )

    def types(self):
        return [e["alert_type"] for e in self.events]

    def test_optical_warning_requires_three_samples(self):
        self.sample(optic_tempC=60)
        self.sample(optic_tempC=60)
        self.assertEqual(self.events, [])

        self.sample(optic_tempC=60)
        self.assertEqual(
            self.types(),
            ["thermal_optic_warning"],
        )

        self.sample(optic_tempC=65)
        self.assertEqual(len(self.events), 1)

    def test_optical_critical_is_immediate(self):
        self.sample(optic_tempC=70)
        self.assertEqual(
            self.types(),
            ["thermal_optic_poor"],
        )
        self.assertEqual(
            self.events[0]["metric"],
            "optic_tempC",
        )

        self.sample(optic_tempC=75)
        self.assertEqual(len(self.events), 1)

    def test_cpu_thresholds_do_not_use_optical_limits(self):
        for _ in range(3):
            self.sample(cpu1_tempC=70, cpu2_tempC=70)

        self.assertEqual(self.events, [])

        for _ in range(3):
            self.sample(cpu1_tempC=75, cpu2_tempC=74)

        self.assertEqual(
            self.types(),
            ["thermal_cpu1_warning"],
        )

        self.sample(cpu2_tempC=85)
        self.assertEqual(
            self.types(),
            [
                "thermal_cpu1_warning",
                "thermal_cpu2_poor",
            ],
        )

    def test_sensor_recoveries_are_independent(self):
        self.sample(optic_tempC=70, cpu1_tempC=85)

        self.assertEqual(
            self.types(),
            [
                "thermal_optic_poor",
                "thermal_cpu1_poor",
            ],
        )

        self.sample(optic_tempC=49, cpu1_tempC=86)

        self.assertEqual(
            self.types(),
            [
                "thermal_optic_poor",
                "thermal_cpu1_poor",
                "thermal_optic_recovered",
            ],
        )

        self.sample(cpu1_tempC=60)

        self.assertEqual(
            self.types()[-1],
            "thermal_cpu1_recovered",
        )

    def test_missing_sensor_does_not_recover_other(self):
        self.sample(optic_tempC=70)
        self.sample(cpu1_tempC=55)
        self.assertEqual(
            self.types(),
            ["thermal_optic_poor"],
        )

        self.sample(optic_tempC=None)
        self.sample(optic_tempC=float("nan"))
        self.assertEqual(len(self.events), 1)

    def test_warning_interruption_resets_debounce(self):
        self.sample(optic_tempC=60)
        self.sample(optic_tempC=60)
        self.sample(optic_tempC=49)
        self.sample(optic_tempC=60)
        self.sample(optic_tempC=60)

        self.assertEqual(self.events, [])

        self.sample(optic_tempC=60)
        self.assertEqual(
            self.types(),
            ["thermal_optic_warning"],
        )

    def test_optical_policy_change_only_resets_optic(self):
        self.sample(optic_tempC=70, cpu1_tempC=85)

        optic_key = ("core_quality", "optic_tempC")
        cpu_key = ("core_quality", "cpu1_tempC")

        config = self.manager.get_config()
        config["quality"]["thermal"]["optic_hot"] = 72
        self.manager.save_config(config)

        self.assertNotIn(optic_key, self.manager.previous)
        self.assertIn(cpu_key, self.manager.previous)

    def test_cpu_policy_change_preserves_optic(self):
        self.sample(optic_tempC=70, cpu1_tempC=85)

        optic_key = ("core_quality", "optic_tempC")
        cpu_key = ("core_quality", "cpu1_tempC")

        config = self.manager.get_config()
        config["quality"]["thermal"]["hot"] = 87
        self.manager.save_config(config)

        self.assertIn(optic_key, self.manager.previous)
        self.assertNotIn(cpu_key, self.manager.previous)

    def test_thermal_state_survives_restart(self):
        self.sample(optic_tempC=70)
        self.manager._persist_runtime_state()

        reloaded = AlertManager(self.db)
        events = []
        reloaded._record_event = (
            lambda **event: events.append(event)
        )

        reloaded._process_thermal_state(
            "2026-10-23T16:01:00+00:00",
            {"optic_tempC": 71},
        )

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
