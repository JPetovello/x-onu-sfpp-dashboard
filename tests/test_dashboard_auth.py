import base64
import os
import unittest
import unittest.mock

import app as dashboard_app


class DashboardAuthTests(unittest.TestCase):

    def setUp(self):
        dashboard_app.app.config["TESTING"] = True
        self.client = dashboard_app.app.test_client()

    @staticmethod
    def basic_auth(username, password):
        encoded = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")

        return {
            "Authorization": f"Basic {encoded}"
        }

    def test_authentication_is_disabled_when_unconfigured(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="",
            DASHBOARD_AUTH_PASSWORD="",
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_authentication_when_configured(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="admin",
            DASHBOARD_AUTH_PASSWORD="correct-secret",
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 401)
        self.assertIn(
            "Basic realm=",
            response.headers["WWW-Authenticate"],
        )

    def test_wrong_credentials_are_rejected(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="admin",
            DASHBOARD_AUTH_PASSWORD="correct-secret",
        ):
            response = self.client.get(
                "/",
                headers=self.basic_auth(
                    "admin",
                    "wrong-secret",
                ),
            )

        self.assertEqual(response.status_code, 401)

    def test_correct_credentials_are_accepted(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="admin",
            DASHBOARD_AUTH_PASSWORD="correct-secret",
        ):
            response = self.client.get(
                "/",
                headers=self.basic_auth(
                    "admin",
                    "correct-secret",
                ),
            )

        self.assertEqual(response.status_code, 200)

    def test_configuration_write_requires_authentication(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="admin",
            DASHBOARD_AUTH_PASSWORD="correct-secret",
        ):
            response = self.client.put(
                "/api/retention-config",
                json={
                    "telemetry_days": 90,
                    "alert_days": 90,
                },
            )

        self.assertEqual(response.status_code, 401)

    def test_health_endpoint_remains_available(self):
        with unittest.mock.patch.multiple(
            dashboard_app,
            DASHBOARD_AUTH_USERNAME="admin",
            DASHBOARD_AUTH_PASSWORD="correct-secret",
        ):
            response = self.client.get("/api/health")

        self.assertNotEqual(response.status_code, 401)

    def test_partial_auth_configuration_is_rejected(self):
        with unittest.mock.patch.dict(
            os.environ,
            {"DASHBOARD_AUTH_USERNAME": "admin"},
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                dashboard_app.load_dashboard_auth()

        with unittest.mock.patch.dict(
            os.environ,
            {"DASHBOARD_AUTH_PASSWORD": "secret"},
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                dashboard_app.load_dashboard_auth()


if __name__ == "__main__":
    unittest.main()
