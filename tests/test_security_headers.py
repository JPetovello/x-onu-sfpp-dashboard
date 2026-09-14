import unittest
import unittest.mock

import app as dashboard_app


class SecurityHeaderTests(unittest.TestCase):

    def setUp(self):
        dashboard_app.app.config["TESTING"] = True
        self.client = dashboard_app.app.test_client()

    def test_dashboard_has_security_headers(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertEqual(
            response.headers["X-Frame-Options"],
            "DENY",
        )
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "no-referrer",
        )
        self.assertEqual(
            response.headers["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=()",
        )

        self.assertEqual(
            response.headers["Content-Security-Policy"],
            (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self'; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
        )

    def test_api_response_has_security_headers(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "healthy"},
        )

        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertEqual(
            response.headers["X-Frame-Options"],
            "DENY",
        )
        self.assertIn(
            "frame-ancestors 'none'",
            response.headers[
                "Content-Security-Policy"
            ],
        )

    def test_static_response_has_security_headers(self):
        response = self.client.get("/static/style.css")
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertIn(
            "default-src 'self'",
            response.headers[
                "Content-Security-Policy"
            ],
        )


    def test_hsts_is_disabled_by_default(self):
        with unittest.mock.patch.object(
            dashboard_app,
            "REQUIRE_HTTPS",
            False,
        ):
            response = self.client.get("/")

        self.assertNotIn(
            "Strict-Transport-Security",
            response.headers,
        )

    def test_hsts_is_enabled_when_https_is_required(self):
        with unittest.mock.patch.object(
            dashboard_app,
            "REQUIRE_HTTPS",
            True,
        ):
            response = self.client.get("/")

        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=31536000",
        )


if __name__ == "__main__":
    unittest.main()
