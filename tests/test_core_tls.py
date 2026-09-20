import os
import unittest
from unittest import mock

import app as dashboard_app


class CoreTLSConfigurationTests(unittest.TestCase):

    def test_default_preserves_legacy_disabled_verification(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIs(
                dashboard_app.load_ont_tls_verify(),
                False,
            )

    def test_verification_can_be_enabled(self):
        with mock.patch.dict(
            os.environ,
            {"ONT_TLS_VERIFY": "true"},
            clear=True,
        ):
            self.assertIs(
                dashboard_app.load_ont_tls_verify(),
                True,
            )

    def test_common_boolean_values_are_supported(self):
        for value in ("1", "yes", "on"):
            with self.subTest(value=value):
                with mock.patch.dict(
                    os.environ,
                    {"ONT_TLS_VERIFY": value},
                    clear=True,
                ):
                    self.assertIs(
                        dashboard_app.load_ont_tls_verify(),
                        True,
                    )

        for value in ("0", "no", "off", "false"):
            with self.subTest(value=value):
                with mock.patch.dict(
                    os.environ,
                    {"ONT_TLS_VERIFY": value},
                    clear=True,
                ):
                    self.assertIs(
                        dashboard_app.load_ont_tls_verify(),
                        False,
                    )

    def test_invalid_verify_value_is_rejected(self):
        with mock.patch.dict(
            os.environ,
            {"ONT_TLS_VERIFY": "maybe"},
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                dashboard_app.load_ont_tls_verify()

    def test_custom_ca_bundle_enables_verification(self):
        with mock.patch.dict(
            os.environ,
            {
                "ONT_TLS_CA_BUNDLE":
                    "/run/secrets/ont-ca.pem",
            },
            clear=True,
        ):
            self.assertEqual(
                dashboard_app.load_ont_tls_verify(),
                "/run/secrets/ont-ca.pem",
            )

    def test_custom_ca_bundle_allows_explicit_true(self):
        with mock.patch.dict(
            os.environ,
            {
                "ONT_TLS_VERIFY": "true",
                "ONT_TLS_CA_BUNDLE":
                    "/run/secrets/ont-ca.pem",
            },
            clear=True,
        ):
            self.assertEqual(
                dashboard_app.load_ont_tls_verify(),
                "/run/secrets/ont-ca.pem",
            )

    def test_ca_bundle_with_disabled_verification_is_rejected(self):
        with mock.patch.dict(
            os.environ,
            {
                "ONT_TLS_VERIFY": "false",
                "ONT_TLS_CA_BUNDLE":
                    "/run/secrets/ont-ca.pem",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                dashboard_app.load_ont_tls_verify()

    def test_fetch_metrics_uses_configured_verification(self):
        response = mock.Mock()
        response.json.return_value = {}

        with (
            mock.patch.object(
                dashboard_app,
                "ONT_TLS_VERIFY",
                True,
            ),
            mock.patch.object(
                dashboard_app.requests,
                "get",
                return_value=response,
            ) as request_get,
        ):
            dashboard_app.fetch_metrics()

        self.assertIs(
            request_get.call_args.kwargs["verify"],
            True,
        )

        self.assertEqual(
            request_get.call_args.kwargs["timeout"],
            dashboard_app.REQUEST_TIMEOUT,
        )

    def test_fetch_metrics_uses_custom_ca_bundle(self):
        response = mock.Mock()
        response.json.return_value = {}

        ca_bundle = "/run/secrets/ont-ca.pem"

        with (
            mock.patch.object(
                dashboard_app,
                "ONT_TLS_VERIFY",
                ca_bundle,
            ),
            mock.patch.object(
                dashboard_app.requests,
                "get",
                return_value=response,
            ) as request_get,
        ):
            dashboard_app.fetch_metrics()

        self.assertEqual(
            request_get.call_args.kwargs["verify"],
            ca_bundle,
        )


if __name__ == "__main__":
    unittest.main()
