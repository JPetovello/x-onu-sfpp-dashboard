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
        collector.diagnostics_lock = (
            threading.Lock()
        )

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

        actual_commands = tuple(
            line.strip()
            for line in command.splitlines()
            if line.strip().startswith("pontop ")
        )

        self.assertEqual(
            actual_commands,
            expected_commands,
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

        actual_commands = tuple(
            line.strip()
            for line in command.splitlines()
            if line.strip().startswith("pontop ")
        )

        self.assertEqual(
            actual_commands,
            expected_commands,
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

    def test_expert_profiles_use_only_fixed_allowlisted_commands(self):
        cases = {
            "datapath": (
                "pontop -b -g 'CQM ofsc'",
                "pontop -b -g 'CQM Queue Map'",
                "pontop -b -g 'Datapath Ports'",
                "pontop -b -g 'Datapath QOS'",
            ),
            "ppv4": (
                "pontop -b -g 'PPv4 Buffer MGR HW Stats'",
                "pontop -b -g 'PPv4 QoS Queue PPS'",
                "pontop -b -g 'PPv4 Queues Stats'",
                "pontop -b -g 'PPv4 Tree'",
                "pontop -b -g 'PPv4 QStats'",
            ),
            "burst": (
                "pontop -b -g 'Debug Burst Profile'",
            ),
        }

        for profile, expected_commands in cases.items():
            with self.subTest(profile=profile):
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
                        return_value=(
                            "__XONU_TEST__\nraw output"
                        ),
                    ) as exec_mock,
                ):
                    result = collector.diagnostics(
                        profile
                    )

                command = exec_mock.call_args.args[1]
                actual_commands = tuple(
                    line.strip()
                    for line in command.splitlines()
                    if line.strip().startswith(
                        "pontop "
                    )
                )

                self.assertEqual(
                    actual_commands,
                    expected_commands,
                )
                self.assertTrue(result["online"])
                self.assertEqual(
                    result["profile"],
                    profile,
                )
                client.close.assert_called_once_with()

    def test_all_profiles_enable_shell_fail_fast(self):
        for profile in (
            "overview",
            "counters",
            "datapath",
            "ppv4",
            "burst",
        ):
            with self.subTest(profile=profile):
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
                        return_value=(
                            "__XONU_TEST__\nraw output"
                        ),
                    ) as exec_mock,
                ):
                    result = collector.diagnostics(
                        profile
                    )

                command = (
                    exec_mock
                    .call_args
                    .args[1]
                )

                command_lines = [
                    line.strip()
                    for line
                    in command.splitlines()
                    if line.strip()
                ]

                self.assertGreater(
                    len(command_lines),
                    1,
                )

                self.assertEqual(
                    command_lines[0],
                    "set -e",
                )

                self.assertTrue(
                    result["online"]
                )


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

    def test_concurrency_guard_rejects_second_request(self):
        collector = self._collector()
        client = mock.Mock()
        entered = threading.Event()
        release = threading.Event()
        first_result = {}

        def blocking_exec(*_args):
            entered.set()
            self.assertTrue(
                release.wait(timeout=2)
            )
            return "__XONU_STATUS__\nready"

        def first_request():
            first_result.update(
                collector.diagnostics("overview")
            )

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
                return_value=client,
            ),
            mock.patch.object(
                collector,
                "_exec",
                side_effect=blocking_exec,
            ),
        ):
            thread = threading.Thread(
                target=first_request
            )
            thread.start()
            self.assertTrue(
                entered.wait(timeout=2)
            )

            second = collector.diagnostics(
                "counters"
            )

            release.set()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertTrue(first_result["online"])
        self.assertTrue(second["busy"])
        self.assertFalse(second["online"])
        self.assertIn(
            "already running",
            second["error"],
        )

    def test_concurrency_guard_is_released_after_failure(self):
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
                side_effect=[
                    RuntimeError("synthetic failure"),
                    "__XONU_STATUS__\nrecovered",
                ],
            ),
        ):
            failed = collector.diagnostics(
                "overview"
            )
            recovered = collector.diagnostics(
                "overview"
            )

        self.assertFalse(failed["online"])
        self.assertFalse(failed["busy"])
        self.assertTrue(recovered["online"])
        self.assertFalse(recovered["busy"])

    def test_client_close_failure_is_contained_and_guard_released(self):
        collector = self._collector()
        client = mock.Mock()

        client.close.side_effect = RuntimeError(
            "synthetic close failure"
        )

        with (
            mock.patch.object(
                collector,
                "_ssh_client",
                return_value=client,
            ),
            mock.patch.object(
                collector,
                "_exec",
                side_effect=[
                    "__XONU_STATUS__\nfirst",
                    "__XONU_STATUS__\nsecond",
                ],
            ),
            mock.patch(
                "builtins.print"
            ) as print_mock,
        ):
            first = collector.diagnostics(
                "overview"
            )

            second = collector.diagnostics(
                "overview"
            )

        self.assertTrue(first["online"])
        self.assertFalse(first["busy"])

        self.assertTrue(second["online"])
        self.assertFalse(second["busy"])

        self.assertEqual(
            client.close.call_count,
            2,
        )

        print_mock.assert_called()


    def test_diagnostics_do_not_persist_or_process_alerts(self):
        collector = self._collector()
        collector.alert_manager = mock.Mock()
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
                return_value=(
                    "__XONU_STATUS__\nraw"
                ),
            ),
            mock.patch.object(
                collector,
                "_connect_db",
            ) as database_mock,
        ):
            result = collector.diagnostics(
                "overview"
            )

        self.assertTrue(result["online"])
        database_mock.assert_not_called()
        collector.alert_manager.assert_not_called()
        self.assertEqual(
            collector.alert_manager.method_calls,
            [],
        )

    def test_diagnostic_output_is_bounded_and_marked(self):
        sections = {
            "FIRST": "A" * 100,
            "SECOND": "B" * 100,
        }

        bounded = (
            AdvancedCollector
            ._bound_diagnostic_sections(
                sections,
                max_section_chars=60,
                max_total_chars=120,
            )
        )

        self.assertIn(
            "output truncated",
            bounded["FIRST"],
        )
        self.assertIn(
            "output truncated",
            bounded["SECOND"],
        )
        self.assertLessEqual(
            sum(map(len, bounded.values())),
            120,
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
            response = self.client.post(
                "/api/diagnostics",
                json={
                    "profile":
                        "arbitrary-command",
                },
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

    def test_each_valid_api_profile_routes_to_collector(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        for profile in (
            "overview",
            "counters",
            "datapath",
            "ppv4",
            "burst",
        ):
            with self.subTest(profile=profile):
                payload = {
                    "enabled": True,
                    "online": True,
                    "busy": False,
                    "profile": profile,
                    "error": None,
                    "sections": {
                        "TEST": "synthetic",
                    },
                }

                with mock.patch.object(
                    collector,
                    "diagnostics",
                    return_value=payload,
                ) as diagnostics_mock:
                    response = self.client.post(
                        "/api/diagnostics",
                        json={
                            "profile": profile,
                        },
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
                    profile
                )

    def test_missing_or_invalid_json_returns_400(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        cases = (
            {},
            {"data": "not json"},
            {"json": None},
            {"json": []},
            {"json": {}},
            {"json": {"profile": 42}},
            {
                "json": {
                    "profile": "overview",
                    "command": "arbitrary",
                },
            },
        )

        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with mock.patch.object(
                    collector,
                    "diagnostics",
                ) as diagnostics_mock:
                    response = self.client.post(
                        "/api/diagnostics",
                        **kwargs,
                    )

                self.assertEqual(
                    response.status_code,
                    400,
                )
                diagnostics_mock.assert_not_called()

    def test_diagnostics_requires_json_content_type_and_valid_json(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        cases = (
            {
                "data":
                    '{"profile":"overview"}',
                "content_type":
                    "text/plain",
            },
            {
                "data":
                    '{"profile":',
                "content_type":
                    "application/json",
            },
        )

        for request_kwargs in cases:
            with self.subTest(
                request_kwargs=request_kwargs
            ):
                with mock.patch.object(
                    collector,
                    "diagnostics",
                ) as diagnostics_mock:
                    response = self.client.post(
                        "/api/diagnostics",
                        **request_kwargs,
                    )

                self.assertEqual(
                    response.status_code,
                    400,
                )

                diagnostics_mock.assert_not_called()


    def test_get_does_not_execute_diagnostics(self):
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
            )

        self.assertEqual(
            response.status_code,
            405,
        )
        diagnostics_mock.assert_not_called()

    def test_diagnostics_post_requires_authentication_before_collector(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        with (
            mock.patch.multiple(
                self.app_module,
                DASHBOARD_AUTH_USERNAME="admin",
                DASHBOARD_AUTH_PASSWORD="correct-secret",
            ),
            mock.patch.object(
                collector,
                "diagnostics",
            ) as diagnostics_mock,
        ):
            response = self.client.post(
                "/api/diagnostics",
                json={
                    "profile": "overview",
                },
            )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertIn(
            "Basic realm=",
            response.headers[
                "WWW-Authenticate"
            ],
        )

        diagnostics_mock.assert_not_called()


    def test_busy_api_result_returns_409(self):
        collector = (
            self.app_module
            .advanced_collector
        )
        payload = {
            "enabled": True,
            "online": False,
            "busy": True,
            "profile": "datapath",
            "error": "Diagnostics are already running",
            "sections": {},
        }

        with mock.patch.object(
            collector,
            "diagnostics",
            return_value=payload,
        ):
            response = self.client.post(
                "/api/diagnostics",
                json={"profile": "datapath"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), payload)

    def test_api_response_is_json_safe(self):
        collector = (
            self.app_module
            .advanced_collector
        )

        with mock.patch.object(
            collector,
            "diagnostics",
            return_value={
                "enabled": True,
                "online": True,
                "busy": False,
                "profile": "overview",
                "error": None,
                "sections": {
                    "STATUS": float("nan"),
                },
            },
        ):
            response = self.client.post(
                "/api/diagnostics",
                json={"profile": "overview"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            response.get_json()["sections"]["STATUS"]
        )


if __name__ == "__main__":
    unittest.main()
