import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TrustedBrowsersLayoutTests(unittest.TestCase):

    def test_phase2_page_layout(self):
        local = (
            ROOT / "static/trusted_browsers.css"
        ).read_text()

        self.assertIn(
            "width: min(1376px, calc(100% - 48px));",
            local,
        )
        self.assertIn(
            "font-size: clamp(30px, 4vw, 43px);",
            local,
        )
        self.assertIn("padding: 28px 0 50px;", local)
        self.assertIn("margin-bottom: 26px;", local)
        self.assertIn("width: calc(100% - 28px);", local)

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
