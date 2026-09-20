import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "web_templates"


class PageLayoutTests(unittest.TestCase):

    def test_primary_pages_share_navigation(self):
        pages = (
            "index.html",
            "advanced.html",
            "diagnostics.html",
            "alerts_settings.html",
        )

        for page in pages:
            with self.subTest(page=page):
                text = (
                    TEMPLATES
                    / page
                ).read_text()

                self.assertIn(
                    '{% include "_page_nav.html" %}',
                    text,
                )

    def test_alerts_uses_common_header(self):
        text = (
            TEMPLATES
            / "alerts_settings.html"
        ).read_text()

        self.assertIn(
            """<h1>
            X-ONU-SFPP
        </h1>""",
            text,
        )

        self.assertIn(
            """<p class="subtitle">
            Alerts & Notifications
        </p>""",
            text,
        )

        self.assertNotIn(
            "← Back to Dashboard",
            text,
        )

    def test_alerts_nav_can_be_current(self):
        text = (
            TEMPLATES
            / "_page_nav.html"
        ).read_text()

        self.assertIn(
            'active_page == "alerts"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
