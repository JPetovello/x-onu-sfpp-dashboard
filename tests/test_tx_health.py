import json
import math
import unittest
from pathlib import Path

from tx_health import classify_tx_power


FIXTURES = Path(__file__).with_name(
    "tx_classification_cases.json"
)


class TxHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(
            FIXTURES.read_text(encoding="utf-8")
        )

    def test_shared_classification_cases(self):
        for case in self.fixtures["cases"]:
            with self.subTest(case=case):
                thresholds = self.fixtures[
                    "profiles"
                ][case["profile"]]

                label, level, value = classify_tx_power(
                    case["value"],
                    thresholds,
                )

                self.assertEqual(label, case["label"])
                self.assertEqual(level, case["level"])
                self.assertEqual(value, case["value"])

    def test_invalid_values_are_unknown(self):
        thresholds = self.fixtures["profiles"][
            "xgsponst2001-a01"
        ]

        for value in (
            None,
            "not-a-number",
            math.nan,
            math.inf,
            -math.inf,
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    classify_tx_power(value, thresholds),
                    ("UNKNOWN", "unknown", None),
                )


if __name__ == "__main__":
    unittest.main()
