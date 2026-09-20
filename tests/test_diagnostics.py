import importlib
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

from advanced import AdvancedCollector


class DiagnosticsCollectorTests(unittest.TestCase):

    @staticmethod
    def _collector(enabled=True):
        collector = AdvancedCollector.__new__(
            AdvancedCollector
        )

        collector.enabled = enabled

        return collector

    def test_overview_uses_fixed_allowlisted_commands(self):
        collector = self._collector()

        client = mock.Mock()

        output = """
__XONU_STATUS__
PON PLOAM Status : O5.1, Associated state

__XONU_CAPABILITY__
Basic mode(s) : G.987|G.989|

__XONU_LAN__
Link : Up

__XONU_ALARMS__
No active alarms

__XONU_OPTICAL_STATUS__
Laser : Enabled

__XONU_OPTICAL_INFO__
Vendor name : Example
"""

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
                return_value=client,
            ) as ssh_mock,
            mock.patch.object(
                collector,
                "_exec",
                return_value=output,
            ) as exec_mock,
        ):
            result = collector.diagnostics(
                "overview"
            )

        ssh_mock.assert_called_once_with()
        exec_mock.assert_called_once()

        command = exec_mock.call_args.args[1]

        expected_commands = (
            "pontop -b -g s",
            "pontop -b -g c",
            "pontop -b -g 'LAN Interface Status & Counters'",
            "pontop -b -g w",
            "pontop -b -g 'Optical Interface Status'",
            "pontop -b -g 'Optical Interface Info'",
        )

        for expected in expected_commands:
            with self.subTest(command=expected):
                self.assertIn(
                    expected,
                    command,
                )

        self.assertNotIn(
            "Allocation Counters",
            command,
        )

        self.assertNotIn(
            "PLOAM Downstream Counters",
            command,
        )

        self.assertNotIn(
            "PLOAM Upstream Counters",
            command,
        )

        self.assertTrue(result["enabled"])
        self.assertTrue(result["online"])
        self.assertEqual(
            result["profile"],
            "overview",
        )
        self.assertIsNone(result["error"])

        self.assertIn(
            "STATUS",
            result["sections"],
        )
        self.assertIn(
            "CAPABILITY",
            result["sections"],
        )
        self.assertIn(
            "LAN",
            result["sections"],
        )
        self.assertIn(
            "ALARMS",
            result["sections"],
        )
        self.assertIn(
            "OPTICAL_STATUS",
            result["sections"],
        )
        self.assertIn(
            "OPTICAL_INFO",
            result["sections"],
        )

        client.close.assert_called_once_with()

    def test_counters_uses_fixed_allowlisted_commands(self):
        collector = self._collector()

        client = mock.Mock()

        output = """
__XONU_ALLOCATION_COUNTERS__
Alloc counter : 1

__XONU_PLOAM_DOWNSTREAM__
Downstream counter : 2

__XONU_PLOAM_UPSTREAM__
Upstream counter : 3
"""

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
                return_value=client,
            ),
            mock.patch.object(
                collector,
                "_exec",
                return_value=output,
            ) as exec_mock,
        ):
            result = collector.diagnostics(
                "counters"
            )

        command = exec_mock.call_args.args[1]

        expected_commands = (
            "pontop -b -g 'Allocation Counters'",
            "pontop -b -g 'PLOAM Downstream Counters'",
            "pontop -b -g 'PLOAM Upstream Counters'",
        )

        for expected in expected_commands:
            with self.subTest(command=expected):
                self.assertIn(
                    expected,
                    command,
                )

        self.assertNotIn(
            "LAN Interface Status & Counters",
            command,
        )

        self.assertNotIn(
            "Optical Interface Status",
            command,
        )

        self.assertEqual(
            result["profile"],
            "counters",
        )
        self.assertTrue(result["online"])

        self.assertIn(
            "ALLOCATION_COUNTERS",
            result["sections"],
        )
        self.assertIn(
            "PLOAM_DOWNSTREAM",
            result["sections"],
        )
        self.assertIn(
            "PLOAM_UPSTREAM",
            result["sections"],
        )

        client.close.assert_called_once_with()

    def test_unknown_profile_is_rejected_before_ssh(self):
        collector = self._collector()

        with mock.patch.object(
            collector,
            "_ssh_client",
        ) as ssh_mock:
            with self.assertRaises(ValueError):
                collector.diagnostics(
                    "totally-not-a-profile"
                )

        ssh_mock.assert_not_called()

    def test_disabled_diagnostics_never_connects(self):
        collector = self._collector(
            enabled=False
        )

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
            ) as ssh_mock,
            mock.patch.object(
                collector,
                "_exec",
            ) as exec_mock,
        ):
            result = collector.diagnostics(
                "overview"
            )

        ssh_mock.assert_not_called()
        exec_mock.assert_not_called()

        self.assertFalse(result["enabled"])
        self.assertFalse(result["online"])
        self.assertEqual(
            result["profile"],
            "overview",
        )
        self.assertEqual(
            result["sections"],
            {},
        )
        self.assertIn(
            "disabled",
            result["error"].lower(),
        )

    def test_exec_failure_returns_error_and_closes_client(self):
        collector = self._collector()

        client = mock.Mock()

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
                return_value=client,
            ),
            mock.patch.object(
                collector,
                "_exec",
                side_effect=RuntimeError(
                    "synthetic diagnostic failure"
                ),
            ),
        ):
            result = collector.diagnostics(
                "overview"
            )

        self.assertTrue(result["enabled"])
        self.assertFalse(result["online"])
        self.assertEqual(
            result["profile"],
            "overview",
        )
        self.assertEqual(
            result["sections"],
            {},
        )

        self.assertIn(
            "RuntimeError",
            result["error"],
        )
        self.assertIn(
            "synthetic diagnostic failure",
            result["error"],
        )

        client.close.assert_called_once_with()

    def test_connection_failure_returns_controlled_error(self):
        collector = self._collector()

        with mock.patch.object(
            collector,
            "_ssh_client",
            side_effect=RuntimeError(
                "synthetic connection failure"
            ),
        ):
            result = collector.diagnostics(
                "overview"
            )

        self.assertTrue(result["enabled"])
        self.assertFalse(result["online"])
        self.assertEqual(
            result["sections"],
            {},
        )
        self.assertIn(
            "synthetic connection failure",
            result["error"],
        )


class DiagnosticsApiTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = (
            tempfile.TemporaryDirectory()
        )

        environment = {
            "DATA_DIR": cls.tempdir.name,
            "ONT_URL": (
                "http://127.0.0.1:9/unreachable"
            ),
            "SSH_ENABLED": "false",
            "DASHBOARD_AUTH_USERNAME": "",
            "DASHBOARD_AUTH_PASSWORD": "",
        }

        with (
            mock.patch.dict(
                os.environ,
                environment,
            ),
            mock.patch.object(
                threading.Thread,
                "start",
                autospec=True,
            ),
        ):
            sys.modules.pop(
                "app",
                None,
            )

            cls.app_module = (
                importlib.import_module(
                    "app"
                )
            )

        cls.app_module.app.config[
            "TESTING"
        ] = True

        cls.client = (
            cls.app_module.app.test_client()
        )

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(
            "app",
            None,
        )

        cls.tempdir.cleanup()

    def test_unknown_api_profile_returns_400_without_collector_call(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        with mock.patch.object(
            collector,
            "diagnostics",
        ) as diagnostics_mock:
            response = self.client.get(
                "/api/diagnostics"
                "?profile=arbitrary-command"
            )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.get_json(),
            {
                "error":
                    "Unknown diagnostic profile",
            },
        )

        diagnostics_mock.assert_not_called()

    def test_overview_api_routes_to_collector(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        payload = {
            "enabled": True,
            "online": True,
            "profile": "overview",
            "error": None,
            "sections": {
                "STATUS": "synthetic status",
            },
        }

        with mock.patch.object(
            collector,
            "diagnostics",
            return_value=payload,
        ) as diagnostics_mock:
            response = self.client.get(
                "/api/diagnostics"
                "?profile=overview"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.get_json(),
            payload,
        )

        diagnostics_mock.assert_called_once_with(
            "overview"
        )

    def test_counters_api_routes_to_collector(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        payload = {
            "enabled": True,
            "online": True,
            "profile": "counters",
            "error": None,
            "sections": {
                "PLOAM_UPSTREAM":
                    "synthetic counter",
            },
        }

        with mock.patch.object(
            collector,
            "diagnostics",
            return_value=payload,
        ) as diagnostics_mock:
            response = self.client.get(
                "/api/diagnostics"
                "?profile=counters"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.get_json(),
            payload,
        )

        diagnostics_mock.assert_called_once_with(
            "counters"
        )

    def test_api_defaults_to_overview(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        with mock.patch.object(
            collector,
            "diagnostics",
            return_value={
                "enabled": False,
                "online": False,
                "profile": "overview",
                "error": "disabled",
                "sections": {},
            },
        ) as diagnostics_mock:
            response = self.client.get(
                "/api/diagnostics"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        diagnostics_mock.assert_called_once_with(
            "overview"
        )


if __name__ == "__main__":
    unittest.main()
