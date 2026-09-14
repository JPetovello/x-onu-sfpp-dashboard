import os
import tempfile
import unittest

from alerts import AlertManager


class AlertConfigRebaselineTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.tempdir.name,
            "alerts.db",
        )
        self.manager = AlertManager(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _seed_quality(self, metric):
        state = ("core_quality", metric)
        active = ("quality_active", state)
        pending = ("quality_pending", state)

        self.manager.previous[state] = (
            "WARNING",
            "warn",
            1.0,
        )
        self.manager.previous[active] = "warn"
        self.manager.pending[pending] = {
            "level": "warn",
            "count": 2,
        }

        return state, active, pending

    def test_rx_change_resets_only_rx(self):
        rx = self._seed_quality("rx_power_dBm")
        tx = self._seed_quality("tx_power_dBm")

        config = self.manager.get_config()
        config["quality"]["rx_power"]["poor_low"] -= 0.1

        self.manager.save_config(config)

        self.assertNotIn(rx[0], self.manager.previous)
        self.assertNotIn(rx[1], self.manager.previous)
        self.assertNotIn(rx[2], self.manager.pending)

        self.assertIn(tx[0], self.manager.previous)
        self.assertIn(tx[1], self.manager.previous)
        self.assertIn(tx[2], self.manager.pending)

    def test_warning_samples_resets_all_quality(self):
        keys = [
            self._seed_quality(metric)
            for metric in (
                "rx_power_dBm",
                "tx_power_dBm",
                "temperature_max",
            )
        ]

        ploam = ("ploam_operational",)
        self.manager.previous[ploam] = (True, 51)

        config = self.manager.get_config()
        config["quality"]["warning_samples"] += 1

        self.manager.save_config(config)

        for state, active, pending in keys:
            self.assertNotIn(
                state,
                self.manager.previous,
            )
            self.assertNotIn(
                active,
                self.manager.previous,
            )
            self.assertNotIn(
                pending,
                self.manager.pending,
            )

        self.assertIn(
            ploam,
            self.manager.previous,
        )

    def test_ploam_change_resets_only_ploam(self):
        ploam = ("ploam_operational",)
        reachability = ("core_reachability",)

        self.manager.previous[ploam] = (True, 51)
        self.manager.previous[reachability] = True

        config = self.manager.get_config()
        current = config["ploam"]["operational_state"]

        config["ploam"]["operational_state"] = (
            52 if current != 52 else 53
        )

        self.manager.save_config(config)

        self.assertNotIn(
            ploam,
            self.manager.previous,
        )
        self.assertIn(
            reachability,
            self.manager.previous,
        )

    def test_reachability_change_resets_debounce(self):
        key = ("core_reachability",)

        self.manager.previous[key] = True
        self.manager.pending[key] = {"count": 2}

        config = self.manager.get_config()
        config["core_reachability"][
            "failure_samples"
        ] += 1

        self.manager.save_config(config)

        self.assertNotIn(
            key,
            self.manager.previous,
        )
        self.assertNotIn(
            key,
            self.manager.pending,
        )

    def test_gem_change_resets_gem_baselines(self):
        first = ("gem_key_errors", 100)
        second = ("gem_key_errors", 200)
        unrelated = ("active_alarm_count",)

        self.manager.previous[first] = 10
        self.manager.previous[second] = 20
        self.manager.previous[unrelated] = 1

        config = self.manager.get_config()
        config["gem_key_errors"]["min_delta"] += 1

        self.manager.save_config(config)

        self.assertNotIn(first, self.manager.previous)
        self.assertNotIn(second, self.manager.previous)
        self.assertIn(unrelated, self.manager.previous)

    def test_counter_change_resets_only_that_counter(self):
        config = self.manager.get_config()

        changed = config["counters"][0]
        other = config["counters"][1]

        changed_state = (
            "counter",
            changed["metric_name"],
        )
        other_state = (
            "counter",
            other["metric_name"],
        )

        changed_alert = (
            "alert",
            changed["alert_type"],
        )
        other_alert = (
            "alert",
            other["alert_type"],
        )

        self.manager.previous[changed_state] = 10
        self.manager.pending[changed_state] = {
            "previous_value": 10,
            "delta": 5,
        }
        self.manager.last_alert[changed_alert] = 100.0

        self.manager.previous[other_state] = 20
        self.manager.pending[other_state] = {
            "previous_value": 20,
            "delta": 5,
        }
        self.manager.last_alert[other_alert] = 100.0

        changed["min_delta"] += 1

        self.manager.save_config(config)

        self.assertNotIn(
            changed_state,
            self.manager.previous,
        )
        self.assertNotIn(
            changed_state,
            self.manager.pending,
        )
        self.assertNotIn(
            changed_alert,
            self.manager.last_alert,
        )

        self.assertIn(
            other_state,
            self.manager.previous,
        )
        self.assertIn(
            other_state,
            self.manager.pending,
        )
        self.assertIn(
            other_alert,
            self.manager.last_alert,
        )

    def test_severity_only_change_preserves_state(self):
        rx = self._seed_quality("rx_power_dBm")

        counter = ("counter", "bip_errors")
        cooldown = ("alert", "bip_errors")

        self.manager.previous[counter] = 10
        self.manager.pending[counter] = {
            "previous_value": 10,
            "delta": 5,
        }
        self.manager.last_alert[cooldown] = 100.0

        config = self.manager.get_config()

        severity = config[
            "core_reachability"
        ]["unreachable_severity"]

        config["core_reachability"][
            "unreachable_severity"
        ] = (
            "warning"
            if severity != "warning"
            else "critical"
        )

        self.manager.save_config(config)

        self.assertIn(rx[0], self.manager.previous)
        self.assertIn(rx[1], self.manager.previous)
        self.assertIn(rx[2], self.manager.pending)

        self.assertIn(counter, self.manager.previous)
        self.assertIn(counter, self.manager.pending)
        self.assertIn(cooldown, self.manager.last_alert)


if __name__ == "__main__":
    unittest.main()
