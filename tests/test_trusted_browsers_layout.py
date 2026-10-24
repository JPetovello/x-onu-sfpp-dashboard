import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TrustedBrowsersLayoutTests(unittest.TestCase):

    def test_shared_dashboard_width(self):
        local = (ROOT / "static/trusted_browsers.css").read_text()
        shared = (ROOT / "static/style.css").read_text()

        self.assertNotRegex(
            local,
            r"body\.xonu-trusted-browsers\s+\.shell\s*\{",
        )
        self.assertRegex(
            shared,
            r"(?s)\.shell\s*\{[^}]*1180px",
        )

    def test_theme_selector_present(self):
        html = (
            ROOT / "web_templates/trusted_browsers.html"
        ).read_text()

        self.assertEqual(html.count('id="themeSelector"'), 1)
        self.assertIn('class="theme-control"', html)

        for theme in ("system", "dark", "light"):
            with self.subTest(theme=theme):
                self.assertIn(
                    f'<option value="{theme}">',
                    html,
                )

    def test_shared_navigation_and_theme_script(self):
        html = (
            ROOT / "web_templates/trusted_browsers.html"
        ).read_text()

        self.assertIn(
            '{% include "_page_nav.html" %}',
            html,
        )
        self.assertIn("/static/theme.js", html)


if __name__ == "__main__":
    unittest.main()
