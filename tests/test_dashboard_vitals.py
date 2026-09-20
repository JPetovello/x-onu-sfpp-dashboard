import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DASHBOARD = (
    ROOT
    / "web_templates"
    / "index.html"
)

ADVANCED = (
    ROOT
    / "web_templates"
    / "advanced.html"
)


class DashboardVitalsTests(unittest.TestCase):

    def test_dashboard_keeps_live_vitals(self):
        text = DASHBOARD.read_text()

        required_ids = (
            "rxPower",
            "txPower",
            "txBias",
            "voltage",
            "opticTemp",
            "cpu1Temp",
            "cpu2Temp",
            "downloadRate",
            "uploadRate",
            "downloadTotal",
            "uploadTotal",
            "ontUptime",
            "memoryUsage",
            "memoryDetail",
            "loadAverage",
        )

        for element_id in required_ids:
            with self.subTest(
                element_id=element_id
            ):
                self.assertEqual(
                    text.count(
                        f'id="{element_id}"'
                    ),
                    1,
                )

    def test_module_health_is_not_duplicated_on_advanced(self):
        text = ADVANCED.read_text()

        dashboard_only_ids = (
            "opticTemp",
            "cpu1Temp",
            "cpu2Temp",
            "ontUptime",
            "memoryUsage",
            "memoryDetail",
            "loadAverage",
        )

        for element_id in dashboard_only_ids:
            with self.subTest(
                element_id=element_id
            ):
                self.assertNotIn(
                    f'id="{element_id}"',
                    text,
                )


if __name__ == "__main__":
    unittest.main()
