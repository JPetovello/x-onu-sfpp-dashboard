import json
import socket
import threading
import unittest
import urllib.parse
from unittest.mock import Mock, patch

from notifications import (
    NotificationManager,
    _PinnedHTTPConnection,
    _PinnedHTTPSConnection,
)


class NotificationSsrfTests(unittest.TestCase):

    def setUp(self):
        self.manager = NotificationManager.__new__(
            NotificationManager
        )
        self.manager.private_notification_origins = set()
        self.manager.lock = threading.Lock()

    @staticmethod
    def _ipv4(address, port):
        return (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (
                address,
                port,
            ),
        )

    @staticmethod
    def _ipv6(address, port):
        return (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (
                address,
                port,
                0,
                0,
            ),
        )

    def test_public_destination_is_allowed(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4(
                    "93.184.216.34",
                    443,
                )
            ],
        ):
            destination = (
                self.manager
                ._resolve_notification_destination(
                    "https://example.com/hook"
                )
            )

        self.assertEqual(
            destination["origin"],
            (
                "https",
                "example.com",
                443,
            ),
        )

        self.assertEqual(
            destination["endpoints"],
            [
                (
                    socket.AF_INET,
                    (
                        "93.184.216.34",
                        443,
                    ),
                )
            ],
        )

    def test_loopback_destination_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4(
                    "127.0.0.1",
                    80,
                )
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://localhost/hook"
                )

    def test_private_destination_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4(
                    "192.168.1.10",
                    8080,
                )
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://gotify.internal:8080"
                )

    def test_link_local_destination_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4(
                    "169.254.169.254",
                    80,
                )
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://metadata.invalid/"
                )

    def test_ipv6_loopback_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv6(
                    "::1",
                    80,
                )
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://[::1]/"
                )

    def test_mixed_public_private_dns_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4("93.184.216.34", 443),
                self._ipv4("10.0.0.20", 443),
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "https://alerts.example/hook"
                )

    def test_exact_allowlisted_private_origin_is_allowed(self):
        self.manager.private_notification_origins = {
            ("http", "gotify.internal", 8080)
        }

        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4("192.168.1.50", 8080)
            ],
        ):
            destination = (
                self.manager
                ._resolve_notification_destination(
                    "http://gotify.internal:8080/message"
                )
            )

        self.assertEqual(
            destination["endpoints"][0][1],
            ("192.168.1.50", 8080),
        )

    def test_allowlist_does_not_cover_other_port(self):
        self.manager.private_notification_origins = {
            ("http", "gotify.internal", 8080)
        }

        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv4("192.168.1.50", 8081)
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://gotify.internal:8081/message"
                )

    def test_url_credentials_are_rejected(self):
        with self.assertRaises(ValueError):
            self.manager._parse_notification_url(
                "https://user:pass@example.com/hook"
            )

    def test_non_http_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            self.manager._parse_notification_url(
                "file:///etc/passwd"
            )

    def test_fragment_is_rejected(self):
        with self.assertRaises(ValueError):
            self.manager._parse_notification_url(
                "https://example.com/hook#fragment"
            )

    def test_post_uses_validated_ip_and_does_not_redirect(self):
        destination = {
            "scheme": "https",
            "host": "alerts.example",
            "port": 443,
            "target": "/hook?source=xonu",
            "host_header": "alerts.example",
            "endpoints": [
                (
                    socket.AF_INET,
                    ("93.184.216.34", 443),
                )
            ],
        }

        response = Mock()
        response.status = 302
        response.read.return_value = b""

        connection = Mock()
        connection.getresponse.return_value = response

        with patch.object(
            self.manager,
            "_resolve_notification_destination",
            return_value=destination,
        ):
            with patch(
                "notifications._PinnedHTTPSConnection",
                return_value=connection,
            ) as connection_class:
                status = self.manager._post_notification_url(
                    "https://alerts.example/hook?source=xonu",
                    b"payload",
                    {
                        "Content-Type":
                            "application/json",
                    },
                )

        self.assertEqual(status, 302)

        connection_class.assert_called_once_with(
            "alerts.example",
            443,
            socket.AF_INET,
            ("93.184.216.34", 443),
            10,
        )

        connection.request.assert_called_once_with(
            "POST",
            "/hook?source=xonu",
            body=b"payload",
            headers={
                "Content-Type":
                    "application/json",
                "Host":
                    "alerts.example",
            },
        )

        connection.getresponse.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_discord_uses_pinned_notification_transport(self):
        webhook_url = (
            "https://discord.com/api/webhooks/"
            "123456/example-token"
        )

        config = {
            "discord": {
                "enabled": True,
                "webhook_url": webhook_url,
            },
        }

        event = {
            "severity": "warning",
            "message": "Test alert",
            "metric": "rx_power",
        }

        with (
            patch(
                "notifications.NOTIFICATION_CONFIG",
                config,
            ),
            patch.object(
                self.manager,
                "_post_notification_url",
                return_value=204,
            ) as post,
        ):
            self.manager._send_discord(event)

        post.assert_called_once()

        url, payload, headers = (
            post.call_args.args
        )

        self.assertEqual(url, webhook_url)

        self.assertEqual(
            json.loads(payload.decode("utf-8")),
            {
                "content":
                    "[WARNING] Test alert\n"
                    "Metric: rx_power",
                "allowed_mentions": {
                    "parse": []
                },
            },
        )

        self.assertEqual(
            headers,
            {
                "Content-Type":
                    "application/json",
                "User-Agent":
                    "X-ONU-SFPP-Dashboard",
            },
        )

    def test_pushover_uses_pinned_notification_transport(self):
        config = {
            "pushover": {
                "enabled": True,
                "user_key": "example-user",
                "api_token": "example-token",
            },
        }

        event = {
            "severity": "critical",
            "message": "Test alert",
            "metric": "tx_power",
        }

        with (
            patch(
                "notifications.NOTIFICATION_CONFIG",
                config,
            ),
            patch.object(
                self.manager,
                "_post_notification_url",
                return_value=200,
            ) as post,
        ):
            self.manager._send_pushover(event)

        post.assert_called_once()

        url, payload, headers = (
            post.call_args.args
        )

        self.assertEqual(
            url,
            "https://api.pushover.net/1/messages.json",
        )

        fields = urllib.parse.parse_qs(
            payload.decode("utf-8")
        )

        self.assertEqual(
            fields,
            {
                "token": ["example-token"],
                "user": ["example-user"],
                "title":
                    ["X-ONU-SFPP Dashboard"],
                "message": [
                    "[CRITICAL] Test alert\n"
                    "Metric: tx_power"
                ],
                "priority": ["1"],
            },
        )

        self.assertEqual(
            headers,
            {
                "Content-Type":
                    "application/x-www-form-urlencoded",
                "User-Agent":
                    "X-ONU-SFPP-Dashboard",
            },
        )

    def test_ipv4_mapped_loopback_is_rejected(self):
        with patch(
            "notifications.socket.getaddrinfo",
            return_value=[
                self._ipv6("::ffff:127.0.0.1", 80)
            ],
        ):
            with self.assertRaises(ValueError):
                self.manager._resolve_notification_destination(
                    "http://mapped.example/"
                )

    def test_private_origin_is_loaded_from_environment(self):
        with patch.dict(
            "notifications.os.environ",
            {
                "NOTIFICATION_PRIVATE_ORIGINS":
                    "http://gotify.internal:8080,"
                    "https://ntfy.internal"
            },
            clear=True,
        ):
            origins = (
                self.manager
                ._load_private_notification_origins()
            )

        self.assertEqual(
            origins,
            {
                ("http", "gotify.internal", 8080),
                ("https", "ntfy.internal", 443),
            },
        )

    def test_private_origin_environment_rejects_path(self):
        with patch.dict(
            "notifications.os.environ",
            {
                "NOTIFICATION_PRIVATE_ORIGINS":
                    "http://gotify.internal:8080/admin"
            },
            clear=True,
        ):
            with patch("builtins.print"):
                origins = (
                    self.manager
                    ._load_private_notification_origins()
                )

        self.assertEqual(origins, set())

    def test_pinned_http_connection_uses_supplied_address(self):
        connection = _PinnedHTTPConnection(
            "alerts.example",
            80,
            socket.AF_INET,
            ("93.184.216.34", 80),
            10,
        )

        pinned_socket = Mock()

        with patch(
            "notifications._connect_pinned_socket",
            return_value=pinned_socket,
        ) as connect_socket:
            connection.connect()

        connect_socket.assert_called_once_with(
            socket.AF_INET,
            ("93.184.216.34", 80),
            10,
        )

        self.assertIs(
            connection.sock,
            pinned_socket,
        )

    def test_pinned_https_uses_address_and_original_hostname(self):
        connection = _PinnedHTTPSConnection(
            "alerts.example",
            443,
            socket.AF_INET,
            ("93.184.216.34", 443),
            10,
        )

        raw_socket = Mock()
        tls_socket = Mock()
        context = Mock()
        context.wrap_socket.return_value = tls_socket
        connection._context = context

        with patch(
            "notifications._connect_pinned_socket",
            return_value=raw_socket,
        ) as connect_socket:
            connection.connect()

        connect_socket.assert_called_once_with(
            socket.AF_INET,
            ("93.184.216.34", 443),
            10,
        )

        context.wrap_socket.assert_called_once_with(
            raw_socket,
            server_hostname="alerts.example",
        )

        self.assertIs(
            connection.sock,
            tls_socket,
        )
