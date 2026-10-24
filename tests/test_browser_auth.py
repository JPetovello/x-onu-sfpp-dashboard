"""Isolated integration tests for optional browser authentication."""

import tempfile
import unittest
from pathlib import Path

from flask import Flask, jsonify

from browser_auth import BrowserAuth
from browser_sessions import COOKIE_NAME


ORIGIN = "https://dashboard.example.test"


class BrowserAuthIntegrationTests(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="xonu-auth-test-"
        )
        self.addCleanup(temporary.cleanup)

        database = str(
            Path(temporary.name) / "test.sqlite"
        )

        self.auth = BrowserAuth(
            database,
            ORIGIN,
            "admin",
            "correct-password",
        )

        self.app = Flask(
            __name__,
            template_folder="../web_templates",
        )
        self.app.config["TESTING"] = True

        @self.app.context_processor
        def browser_mode():
            return {"browser_auth_enabled": True}

        self.app.before_request(
            self.auth.check_request
        )

        @self.app.get("/")
        def dashboard():
            return "Dashboard ready"

        @self.app.get("/api/health")
        def health():
            return jsonify(status="healthy")

        @self.app.route(
            "/api/test-config",
            methods=["GET", "PUT"],
        )
        def test_config():
            return jsonify(ok=True)

        self.auth.install(self.app)
        self.client = self.app.test_client()

    def request(self, method, path, client=None, **kwargs):
        target = client or self.client
        return target.open(
            path,
            method=method,
            base_url=ORIGIN,
            **kwargs,
        )

    def login(
        self,
        password="correct-password",
        remember=True,
        client=None,
        origin=ORIGIN,
    ):
        return self.request(
            "POST",
            "/api/browser-login",
            client=client,
            json={
                "username": "admin",
                "password": password,
                "remember": remember,
            },
            headers={
                "Origin": origin,
                "Sec-Fetch-Site": "same-origin",
            },
        )

    def csrf(self, client=None):
        response = self.request(
            "GET",
            "/api/browser-session",
            client=client,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        return response.get_json()["csrf_token"]

    def test_login_page_renders(self):
        response = self.request("GET", "/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="loginForm"', response.data)
        self.assertIn(b'id="rememberBrowser"', response.data)
        self.assertIn(
            b"/static/login.js",
            response.data,
        )

    def test_trusted_browsers_requires_login(self):
        response = self.request("GET", "/trusted-browsers")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_trusted_browsers_page_renders(self):
        self.assertEqual(self.login().status_code, 200)

        response = self.request("GET", "/trusted-browsers")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="trustedBrowserList"', response.data)
        self.assertIn(b"/static/trusted_browsers.js", response.data)
        self.assertIn(b"Trusted Browsers", response.data)

    def test_current_session_id_matches_active_session(self):
        self.assertEqual(self.login().status_code, 200)

        current = self.request(
            "GET", "/api/browser-session"
        ).get_json()

        sessions = self.request(
            "GET", "/api/browser-sessions"
        ).get_json()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(current["id"], sessions[0]["id"])

    def test_revoking_current_session_clears_cookie(self):
        self.assertEqual(self.login().status_code, 200)

        session_id = self.request(
            "GET", "/api/browser-session"
        ).get_json()["id"]

        response = self.request(
            "DELETE",
            "/api/browser-sessions/" + session_id,
            headers={
                "Origin": ORIGIN,
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": self.csrf(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["revoked"])
        self.assertIn(
            "Max-Age=0",
            response.headers.get("Set-Cookie", ""),
        )

        self.assertEqual(
            self.request("GET", "/api/browser-session").status_code,
            401,
        )

    def test_unauthenticated_api_is_blocked(self):
        response = self.request(
            "GET",
            "/api/test-config",
        )
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_changes_are_blocked(self):
        response = self.request(
            "PUT",
            "/api/test-config",
            json={"enabled": True},
        )
        self.assertEqual(response.status_code, 401)

    def test_health_remains_public(self):
        response = self.request(
            "GET",
            "/api/health",
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_to_login(self):
        response = self.request("GET", "/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/login",
            response.headers["Location"],
        )

    def test_correct_password_creates_session(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

        dashboard = self.request("GET", "/")
        self.assertEqual(dashboard.status_code, 200)

        config = self.request(
            "GET", "/api/test-config"
        )
        self.assertEqual(config.status_code, 200)

    def test_wrong_password_is_rejected(self):
        response = self.login(
            password="incorrect-password"
        )
        self.assertEqual(response.status_code, 401)

        protected = self.request(
            "GET", "/api/test-config"
        )
        self.assertEqual(protected.status_code, 401)

    def test_cookie_security_attributes(self):
        response = self.login(remember=True)
        cookie = response.headers["Set-Cookie"]

        self.assertIn(COOKIE_NAME + "=", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Path=/", cookie)
        self.assertIn("Max-Age=604800", cookie)
        self.assertNotIn("Domain=", cookie)

    def test_adjustable_remember_cookie_lifetime(self):
        for days in (1, 3, 7, 14, 30):
            with self.subTest(days=days):
                response = self.request(
                    "POST",
                    "/api/browser-login",
                    json={
                        "username": "admin",
                        "password": "correct-password",
                        "remember": True,
                        "remember_days": days,
                    },
                    headers={
                        "Origin": ORIGIN,
                        "Sec-Fetch-Site": "same-origin",
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    f"Max-Age={days * 86400}",
                    response.headers["Set-Cookie"],
                )

    def test_invalid_remember_cookie_duration(self):
        for days in (0, 2, 31, "30", None, True):
            with self.subTest(days=days):
                response = self.request(
                    "POST",
                    "/api/browser-login",
                    json={
                        "username": "admin",
                        "password": "correct-password",
                        "remember": True,
                        "remember_days": days,
                    },
                    headers={
                        "Origin": ORIGIN,
                        "Sec-Fetch-Site": "same-origin",
                    },
                )

                self.assertEqual(response.status_code, 400)

    def test_normal_browser_session_cookie(self):
        response = self.login(remember=False)
        cookie = response.headers["Set-Cookie"]

        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertNotIn("Max-Age=", cookie)

    def test_login_rejects_cross_origin(self):
        response = self.login(
            origin="https://attacker.example"
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_is_required_for_config_changes(self):
        self.assertEqual(
            self.login().status_code,
            200,
        )

        response = self.request(
            "PUT",
            "/api/test-config",
            json={"enabled": True},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(response.status_code, 403)

        response = self.request(
            "PUT",
            "/api/test-config",
            json={"enabled": True},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": self.csrf(),
                "Sec-Fetch-Site": "same-origin",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_csrf_does_not_override_origin_check(self):
        self.login()

        response = self.request(
            "PUT",
            "/api/test-config",
            json={"enabled": True},
            headers={
                "Origin": "https://attacker.example",
                "X-CSRF-Token": self.csrf(),
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_logout_revokes_session(self):
        self.login()

        response = self.request(
            "POST",
            "/api/browser-logout",
            headers={
                "Origin": ORIGIN,
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": self.csrf(),
            },
        )

        self.assertEqual(response.status_code, 200)

        protected = self.request(
            "GET",
            "/api/test-config",
        )

        self.assertEqual(protected.status_code, 401)

    def test_one_browser_can_revoke_another(self):
        self.login()

        second_client = self.app.test_client()

        self.assertEqual(
            self.login(client=second_client).status_code,
            200,
        )

        sessions = self.request(
            "GET",
            "/api/browser-sessions",
        ).get_json()

        self.assertEqual(len(sessions), 2)

        second_cookie = second_client.get_cookie(
            COOKIE_NAME,
            domain="dashboard.example.test",
        )

        self.assertIsNotNone(second_cookie)

        second_record = self.auth.sessions.find(
            second_cookie.value
        )

        self.assertIsNotNone(second_record)

        response = self.request(
            "DELETE",
            "/api/browser-sessions/"
            + second_record["id"],
            headers={
                "Origin": ORIGIN,
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": self.csrf(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["revoked"])

        blocked = self.request(
            "GET",
            "/api/test-config",
            client=second_client,
        )

        self.assertEqual(blocked.status_code, 401)

        still_allowed = self.request(
            "GET",
            "/api/test-config",
        )

        self.assertEqual(still_allowed.status_code, 200)

    def proxy_login_attempt(self, peer, forwarded):
        return self.request(
            "POST",
            "/api/browser-login",
            json={
                "username": "admin",
                "password": "wrong-password",
                "remember": False,
            },
            headers={
                "Origin": ORIGIN,
                "Sec-Fetch-Site": "same-origin",
                "X-Forwarded-For": forwarded,
            },
            environ_overrides={"REMOTE_ADDR": peer},
        )

    def test_untrusted_forwarded_header_cannot_bypass_limit(self):
        from ipaddress import ip_address

        self.auth.trusted_proxy_ips = frozenset()

        for i in range(5):
            response = self.proxy_login_attempt(
                "192.0.2.10",
                f"198.51.100.{i + 1}",
            )
            self.assertEqual(response.status_code, 401)

        response = self.proxy_login_attempt(
            "192.0.2.10", "198.51.100.99"
        )
        self.assertEqual(response.status_code, 429)

    def test_trusted_proxy_separates_client_limits(self):
        from ipaddress import ip_address

        self.auth.trusted_proxy_ips = frozenset({
            ip_address("192.0.2.10")
        })

        for _ in range(5):
            response = self.proxy_login_attempt(
                "192.0.2.10", "198.51.100.1"
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.proxy_login_attempt(
            "192.0.2.10", "198.51.100.1"
        )
        self.assertEqual(blocked.status_code, 429)

        independent = self.proxy_login_attempt(
            "192.0.2.10", "198.51.100.2"
        )
        self.assertEqual(independent.status_code, 401)

    def test_ambiguous_forwarding_falls_back_to_proxy_ip(self):
        from ipaddress import ip_address

        self.auth.trusted_proxy_ips = frozenset({
            ip_address("192.0.2.10")
        })

        for i in range(5):
            response = self.proxy_login_attempt(
                "192.0.2.10",
                f"198.51.100.{i + 1}, 203.0.113.1",
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.proxy_login_attempt(
            "192.0.2.10",
            "198.51.100.99, 203.0.113.1",
        )
        self.assertEqual(blocked.status_code, 429)

    def test_invalid_trusted_proxy_configuration_rejected(self):
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"DASHBOARD_TRUSTED_PROXY_IPS": "not-an-ip"},
        ):
            with self.assertRaises(RuntimeError):
                self.auth._load_trusted_proxy_ips()

    def test_login_rate_limiting(self):
        for _ in range(5):
            response = self.login(
                password="incorrect-password"
            )
            self.assertEqual(
                response.status_code,
                401,
            )

        blocked = self.login()

        self.assertEqual(
            blocked.status_code,
            429,
        )


if __name__ == "__main__":
    unittest.main()
