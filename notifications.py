import http.client
import ipaddress
import json
import os
import queue
import socket
import sqlite3
from contextlib import closing
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy


DEFAULT_NOTIFICATION_CONFIG = {
    "discord": {
        "enabled": False,
        "webhook_url": "",
    },
    "gotify": {
        "enabled": False,
        "server_url": "",
        "token": "",
    },
    "pushover": {
        "enabled": False,
        "user_key": "",
        "api_token": "",
    },
    "ntfy": {
        "enabled": False,
        "server_url": "https://ntfy.sh",
        "topic": "",
        "token": "",
    },
    "webhook": {
        "enabled": False,
        "url": "",
    },
}

NOTIFICATION_CONFIG = deepcopy(
    DEFAULT_NOTIFICATION_CONFIG
)

NOTIFICATION_QUEUE_MAXSIZE = 100
NOTIFICATION_QUEUE_TTL_SECONDS = 30 * 60
NOTIFICATION_REQUEST_TIMEOUT_SECONDS = 10
NOTIFICATION_PRIVATE_ORIGINS_ENV = (
    "NOTIFICATION_PRIVATE_ORIGINS"
)


def _connect_pinned_socket(
    family,
    sockaddr,
    timeout,
):
    sock = socket.socket(
        family,
        socket.SOCK_STREAM,
    )

    try:
        sock.settimeout(timeout)
        sock.connect(sockaddr)

    except BaseException:
        sock.close()
        raise

    return sock


class _PinnedHTTPConnection(
    http.client.HTTPConnection
):
    def __init__(
        self,
        host,
        port,
        family,
        sockaddr,
        timeout,
    ):
        super().__init__(
            host,
            port=port,
            timeout=timeout,
        )

        self._pinned_family = family
        self._pinned_sockaddr = sockaddr

    def connect(self):
        self.sock = _connect_pinned_socket(
            self._pinned_family,
            self._pinned_sockaddr,
            self.timeout,
        )


class _PinnedHTTPSConnection(
    http.client.HTTPSConnection
):
    def __init__(
        self,
        host,
        port,
        family,
        sockaddr,
        timeout,
    ):
        super().__init__(
            host,
            port=port,
            timeout=timeout,
        )

        self._pinned_family = family
        self._pinned_sockaddr = sockaddr

    def connect(self):
        sock = _connect_pinned_socket(
            self._pinned_family,
            self._pinned_sockaddr,
            self.timeout,
        )

        try:
            self.sock = self._context.wrap_socket(
                sock,
                server_hostname=self.host,
            )

        except BaseException:
            sock.close()
            raise


class LatestNotificationQueue(queue.Queue):
    """Bounded FIFO queue that retains the newest notifications."""

    def put_latest(
        self,
        item,
    ):
        """Insert without blocking, dropping the oldest item if full."""

        dropped_oldest = False

        # Queue.get() and Queue.put() use the same underlying
        # mutex. Holding it here makes replacement atomic with
        # respect to the notification worker.
        with self.not_full:
            if (
                self.maxsize > 0
                and
                self._qsize() >= self.maxsize
            ):
                self._get()

                self.unfinished_tasks -= 1

                if self.unfinished_tasks == 0:
                    self.all_tasks_done.notify_all()

                dropped_oldest = True

            self._put(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

        return dropped_oldest


class NotificationManager:
    """Deliver stored alert events to configured external providers.

    Notification delivery runs on a dedicated background worker so external
    network requests cannot block alert detection or persistence. Events are
    queued in FIFO order and dispatched independently of telemetry collection.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.private_notification_origins = (
            self._load_private_notification_origins()
        )
        self.notification_queue = LatestNotificationQueue(
            maxsize=NOTIFICATION_QUEUE_MAXSIZE
        )

        self._init_db()
        self._load_config()

        self.notification_worker = threading.Thread(
            target=self._notification_worker,
            daemon=True,
        )

        self.notification_worker.start()


    @staticmethod
    def _parse_notification_url(
        url,
    ):
        if not isinstance(url, str):
            raise ValueError(
                "Notification URL must be a string"
            )

        url = url.strip()

        if not url:
            raise ValueError(
                "Notification URL must not be empty"
            )

        if any(
            ord(char) < 0x20
            or ord(char) == 0x7f
            for char in url
        ):
            raise ValueError(
                "Notification URL contains "
                "invalid control characters"
            )

        try:
            parsed = urllib.parse.urlsplit(url)
        except ValueError as exc:
            raise ValueError(
                "Notification URL is invalid"
            ) from exc

        scheme = parsed.scheme.lower()

        if scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                "Notification URL must use "
                "http:// or https://"
            )

        if (
            parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(
                "Notification URL must not "
                "contain credentials"
            )

        try:
            host = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValueError(
                "Notification URL has an invalid port"
            ) from exc

        if not host:
            raise ValueError(
                "Notification URL must contain a host"
            )

        if parsed.fragment:
            raise ValueError(
                "Notification URL must not "
                "contain a fragment"
            )

        host = host.rstrip(".")

        if not host:
            raise ValueError(
                "Notification URL must contain a host"
            )

        try:
            ip_value = ipaddress.ip_address(host)
        except ValueError:
            try:
                host = (
                    host.encode("idna")
                    .decode("ascii")
                    .lower()
                )
            except UnicodeError as exc:
                raise ValueError(
                    "Notification URL has an invalid host"
                ) from exc
        else:
            host = ip_value.compressed

        default_port = (
            443
            if scheme == "https"
            else 80
        )

        if port is None:
            port = default_port

        path = parsed.path or "/"
        target = path

        if parsed.query:
            target += (
                "?"
                + parsed.query
            )

        try:
            host_ip = ipaddress.ip_address(host)
        except ValueError:
            host_display = host
        else:
            if isinstance(
                host_ip,
                ipaddress.IPv6Address,
            ):
                host_display = (
                    f"[{host}]"
                )
            else:
                host_display = host

        host_header = host_display

        if port != default_port:
            host_header = (
                f"{host_display}:{port}"
            )

        return {
            "scheme": scheme,
            "host": host,
            "port": port,
            "path": parsed.path,
            "query": parsed.query,
            "target": target,
            "host_header": host_header,
            "origin": (
                scheme,
                host,
                port,
            ),
        }


    def _load_private_notification_origins(
        self,
    ):
        raw = os.environ.get(
            NOTIFICATION_PRIVATE_ORIGINS_ENV,
            "",
        )

        origins = set()

        for entry in raw.split(","):
            entry = entry.strip()

            if not entry:
                continue

            try:
                parsed = self._parse_notification_url(
                    entry
                )

                if (
                    parsed["path"]
                    not in {
                        "",
                        "/",
                    }
                    or parsed["query"]
                ):
                    raise ValueError(
                        "allowlist entries must be origins"
                    )

                origins.add(
                    parsed["origin"]
                )

            except ValueError as exc:
                print(
                    "Ignoring invalid "
                    f"{NOTIFICATION_PRIVATE_ORIGINS_ENV} "
                    f"entry: {exc}"
                )

        return origins


    @staticmethod
    def _notification_address_is_public(
        address,
    ):
        if (
            isinstance(
                address,
                ipaddress.IPv6Address,
            )
            and
            address.ipv4_mapped is not None
        ):
            address = address.ipv4_mapped

        return (
            address.is_global
            and not address.is_loopback
            and not address.is_private
            and not address.is_link_local
            and not address.is_multicast
            and not address.is_unspecified
            and not address.is_reserved
        )


    def _resolve_notification_destination(
        self,
        url,
    ):
        destination = (
            self._parse_notification_url(url)
        )

        allow_non_public = (
            destination["origin"]
            in self.private_notification_origins
        )

        try:
            addresses = socket.getaddrinfo(
                destination["host"],
                destination["port"],
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )

        except socket.gaierror as exc:
            raise ValueError(
                "Notification destination "
                "could not be resolved"
            ) from exc

        endpoints = []
        seen = set()

        for (
            family,
            _socktype,
            _proto,
            _canonname,
            sockaddr,
        ) in addresses:
            if family not in {
                socket.AF_INET,
                socket.AF_INET6,
            }:
                continue

            address_text = (
                sockaddr[0]
                .split("%", 1)[0]
            )

            try:
                address = ipaddress.ip_address(
                    address_text
                )
            except ValueError as exc:
                raise ValueError(
                    "Notification destination "
                    "resolved to an invalid address"
                ) from exc

            if (
                not allow_non_public
                and not self._notification_address_is_public(
                    address
                )
            ):
                raise ValueError(
                    "Notification destination "
                    "must resolve only to public "
                    "IP addresses"
                )

            identity = (
                family,
                sockaddr,
            )

            if identity in seen:
                continue

            seen.add(identity)
            endpoints.append(identity)

        if not endpoints:
            raise ValueError(
                "Notification destination "
                "has no usable IP address"
            )

        destination["endpoints"] = endpoints

        return destination


    def _post_notification_url(
        self,
        url,
        payload,
        headers,
    ):
        destination = (
            self._resolve_notification_destination(
                url
            )
        )

        last_error = None

        for family, sockaddr in (
            destination["endpoints"]
        ):
            if destination["scheme"] == "https":
                connection = _PinnedHTTPSConnection(
                    destination["host"],
                    destination["port"],
                    family,
                    sockaddr,
                    NOTIFICATION_REQUEST_TIMEOUT_SECONDS,
                )
            else:
                connection = _PinnedHTTPConnection(
                    destination["host"],
                    destination["port"],
                    family,
                    sockaddr,
                    NOTIFICATION_REQUEST_TIMEOUT_SECONDS,
                )

            request_headers = dict(headers)
            request_headers["Host"] = (
                destination["host_header"]
            )

            try:
                connection.request(
                    "POST",
                    destination["target"],
                    body=payload,
                    headers=request_headers,
                )

                response = connection.getresponse()
                status = response.status
                response.read()

                return status

            except (
                http.client.HTTPException,
                TimeoutError,
                OSError,
            ) as exc:
                last_error = exc

            finally:
                connection.close()

        if last_error is not None:
            raise last_error

        raise OSError(
            "Notification destination "
            "could not be reached"
        )


    def _connect_db(self):
        con = sqlite3.connect(
            self.db_path,
            timeout=10,
        )

        con.row_factory = sqlite3.Row

        return con


    def _init_db(self):
        with closing(self._connect_db()) as con, con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS notification_config (
                    id INTEGER PRIMARY KEY
                        CHECK (id = 1),
                    config_json TEXT NOT NULL
                )
            """)


    def validate_config(
        self,
        config,
    ):
        if not isinstance(
            config,
            dict,
        ):
            raise ValueError(
                "Notification configuration "
                "must be an object"
            )

        expected_providers = set(
            DEFAULT_NOTIFICATION_CONFIG.keys()
        )

        actual_providers = set(
            config.keys()
        )

        if actual_providers != expected_providers:
            missing = (
                expected_providers
                - actual_providers
            )

            unknown = (
                actual_providers
                - expected_providers
            )

            if missing:
                raise ValueError(
                    "Missing notification provider: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            raise ValueError(
                "Unknown notification provider: "
                + ", ".join(
                    sorted(unknown)
                )
            )

        for provider, defaults in (
            DEFAULT_NOTIFICATION_CONFIG.items()
        ):
            settings = config.get(
                provider
            )

            if not isinstance(
                settings,
                dict,
            ):
                raise ValueError(
                    f"{provider} must be an object"
                )

            expected_keys = set(
                defaults.keys()
            )

            actual_keys = set(
                settings.keys()
            )

            if actual_keys != expected_keys:
                missing = (
                    expected_keys
                    - actual_keys
                )

                unknown = (
                    actual_keys
                    - expected_keys
                )

                if missing:
                    raise ValueError(
                        f"{provider} is missing: "
                        + ", ".join(
                            sorted(missing)
                        )
                    )

                raise ValueError(
                    f"{provider} has unknown setting: "
                    + ", ".join(
                        sorted(unknown)
                    )
                )

            enabled = settings.get(
                "enabled"
            )

            if not isinstance(
                enabled,
                bool,
            ):
                raise ValueError(
                    f"{provider}.enabled "
                    "must be true or false"
                )

            for key in expected_keys:
                if key == "enabled":
                    continue

                value = settings.get(
                    key
                )

                if not isinstance(
                    value,
                    str,
                ):
                    raise ValueError(
                        f"{provider}.{key} "
                        "must be a string"
                    )

        webhook = config["webhook"]

        if (
            webhook["enabled"]
            and not webhook["url"].strip()
        ):
            raise ValueError(
                "webhook.url is required "
                "when Webhook notifications are enabled"
            )

        if webhook["url"].strip():
            self._parse_notification_url(
                webhook["url"]
            )

        pushover = config["pushover"]

        if (
            pushover["enabled"]
            and not pushover["user_key"].strip()
        ):
            raise ValueError(
                "pushover.user_key is required "
                "when Pushover notifications are enabled"
            )

        if (
            pushover["enabled"]
            and not pushover["api_token"].strip()
        ):
            raise ValueError(
                "pushover.api_token is required "
                "when Pushover notifications are enabled"
            )


        gotify = config["gotify"]

        if (
            gotify["enabled"]
            and not gotify["server_url"].strip()
        ):
            raise ValueError(
                "gotify.server_url is required "
                "when Gotify notifications are enabled"
            )

        if (
            gotify["enabled"]
            and not gotify["token"].strip()
        ):
            raise ValueError(
                "gotify.token is required "
                "when Gotify notifications are enabled"
            )

        if gotify["server_url"].strip():
            self._parse_notification_url(
                gotify["server_url"]
            )


        discord = config["discord"]

        if (
            discord["enabled"]
            and not discord["webhook_url"].strip()
        ):
            raise ValueError(
                "discord.webhook_url is required "
                "when Discord notifications are enabled"
            )

        if (
            discord["webhook_url"]
            and not discord["webhook_url"].startswith(
                "https://discord.com/api/webhooks/"
            )
        ):
            raise ValueError(
                "discord.webhook_url must be a "
                "Discord webhook URL"
            )


        ntfy = config["ntfy"]

        if (
            ntfy["enabled"]
            and not ntfy["server_url"].strip()
        ):
            raise ValueError(
                "ntfy.server_url is required "
                "when ntfy notifications are enabled"
            )

        if (
            ntfy["enabled"]
            and not ntfy["topic"].strip()
        ):
            raise ValueError(
                "ntfy.topic is required "
                "when ntfy notifications are enabled"
            )

        if ntfy["server_url"].strip():
            self._parse_notification_url(
                ntfy["server_url"]
            )


        return deepcopy(
            config
        )


    def _write_config_row(
        self,
        config,
    ):
        config_json = json.dumps(
            config,
            separators=(",", ":"),
        )

        with closing(self._connect_db()) as con, con:
            con.execute(
                """
                INSERT INTO notification_config (
                    id,
                    config_json
                )
                VALUES (1, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    config_json = excluded.config_json
                """,
                (
                    config_json,
                ),
            )


    def _load_config(self):
        global NOTIFICATION_CONFIG

        with closing(self._connect_db()) as con, con:
            row = con.execute(
                """
                SELECT config_json
                FROM notification_config
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            config = deepcopy(
                DEFAULT_NOTIFICATION_CONFIG
            )

            self._write_config_row(
                config
            )

        else:
            try:
                config = json.loads(
                    row["config_json"]
                )

                config = self.validate_config(
                    config
                )

            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                config = deepcopy(
                    DEFAULT_NOTIFICATION_CONFIG
                )

                self._write_config_row(
                    config
                )

        with self.lock:
            NOTIFICATION_CONFIG = deepcopy(
                config
            )


    def _public_config(
        self,
        config,
    ):
        public = deepcopy(
            config
        )

        secret_fields = {
            "discord": (
                "webhook_url",
            ),
            "gotify": (
                "token",
            ),
            "pushover": (
                "user_key",
                "api_token",
            ),
            "ntfy": (
                "token",
            ),
            "webhook": (
                "url",
            ),
        }

        for provider, fields in (
            secret_fields.items()
        ):
            for field in fields:
                configured = bool(
                    public[provider][field]
                )

                public[provider][field] = ""

                public[provider][
                    f"{field}_configured"
                ] = configured

        return public


    def get_config(
        self,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG
            )

        return self._public_config(
            config
        )


    def save_config(
        self,
        config,
    ):
        global NOTIFICATION_CONFIG

        if not isinstance(
            config,
            dict,
        ):
            raise ValueError(
                "Notification configuration "
                "must be an object"
            )

        with self.lock:
            current = deepcopy(
                NOTIFICATION_CONFIG
            )

        incoming = deepcopy(
            config
        )

        secret_fields = {
            "discord": (
                "webhook_url",
            ),
            "gotify": (
                "token",
            ),
            "pushover": (
                "user_key",
                "api_token",
            ),
            "ntfy": (
                "token",
            ),
            "webhook": (
                "url",
            ),
        }

        for provider, fields in (
            secret_fields.items()
        ):
            settings = incoming.get(
                provider
            )

            if not isinstance(
                settings,
                dict,
            ):
                continue

            for field in fields:
                configured_key = (
                    f"{field}_configured"
                )

                was_configured = (
                    settings.pop(
                        configured_key,
                        False,
                    )
                    is True
                )

                value = settings.get(
                    field
                )

                if (
                    was_configured
                    and value == ""
                ):
                    settings[field] = (
                        current[provider][field]
                    )

        validated = self.validate_config(
            incoming
        )

        self._write_config_row(
            validated
        )

        with self.lock:
            NOTIFICATION_CONFIG = deepcopy(
                validated
            )

            saved = deepcopy(
                NOTIFICATION_CONFIG
            )

        return self._public_config(
            saved
        )


    def _send_discord(
        self,
        event,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG["discord"]
            )

        if not config["enabled"]:
            return

        webhook_url = (
            config["webhook_url"].strip()
        )

        if not webhook_url:
            return

        severity = (
            event.get("severity")
            or "warning"
        )

        message = (
            event.get("message")
            or "Alert"
        )

        metric = (
            event.get("metric")
            or ""
        )

        content = (
            f"[{severity.upper()}] "
            f"{message}"
        )

        if metric:
            content += (
                f"\nMetric: {metric}"
            )

        payload = json.dumps(
            {
                "content": content,
                "allowed_mentions": {
                    "parse": []
                },
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type":
                    "application/json",
                "User-Agent":
                    "X-ONU-SFPP-Dashboard",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                response.read()

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
        ):
            return


    def _send_webhook(
        self,
        event,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG["webhook"]
            )

        if not config["enabled"]:
            return

        url = (
            config["url"]
            .strip()
        )

        if not url:
            return

        payload = json.dumps({
            "source":
                "X-ONU-SFPP Dashboard",
            "event":
                event,
        }).encode("utf-8")

        headers = {
            "Content-Type":
                "application/json",
            "User-Agent":
                "X-ONU-SFPP-Dashboard",
        }

        try:
            self._post_notification_url(
                url,
                payload,
                headers,
            )

        except (
            ValueError,
            UnicodeError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ):
            return



    def _send_pushover(
        self,
        event,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG["pushover"]
            )

        if not config["enabled"]:
            return

        user_key = (
            config["user_key"]
            .strip()
        )

        api_token = (
            config["api_token"]
            .strip()
        )

        if (
            not user_key
            or not api_token
        ):
            return

        severity = (
            event.get("severity")
            or "warning"
        )

        message = (
            event.get("message")
            or "Alert"
        )

        metric = (
            event.get("metric")
            or ""
        )

        content = (
            f"[{severity.upper()}] "
            f"{message}"
        )

        if metric:
            content += (
                f"\nMetric: {metric}"
            )

        priority_map = {
            "critical": 1,
            "warning": 0,
            "info": -1,
        }

        priority = priority_map.get(
            severity.lower(),
            0,
        )

        payload = urllib.parse.urlencode({
            "token": api_token,
            "user": user_key,
            "title": "X-ONU-SFPP Dashboard",
            "message": content,
            "priority": priority,
        }).encode("utf-8")

        request = urllib.request.Request(
            "https://api.pushover.net/1/messages.json",
            data=payload,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
                "User-Agent":
                    "X-ONU-SFPP-Dashboard",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                response.read()

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
        ):
            return


    def _send_gotify(
        self,
        event,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG["gotify"]
            )

        if not config["enabled"]:
            return

        server_url = (
            config["server_url"]
            .strip()
            .rstrip("/")
        )

        token = (
            config["token"]
            .strip()
        )

        if (
            not server_url
            or not token
        ):
            return

        severity = (
            event.get("severity")
            or "warning"
        )

        message = (
            event.get("message")
            or "Alert"
        )

        metric = (
            event.get("metric")
            or ""
        )

        content = (
            f"[{severity.upper()}] "
            f"{message}"
        )

        if metric:
            content += (
                f"\nMetric: {metric}"
            )

        priority_map = {
            "critical": 10,
            "warning": 5,
            "info": 0,
        }

        priority = priority_map.get(
            severity.lower(),
            0,
        )

        url = (
            f"{server_url}/message"
            f"?token={urllib.parse.quote(token, safe='')}"
        )

        payload = json.dumps({
            "title":
                "X-ONU-SFPP Dashboard",
            "message":
                content,
            "priority":
                priority,
        }).encode("utf-8")

        headers = {
            "Content-Type":
                "application/json",
            "User-Agent":
                "X-ONU-SFPP-Dashboard",
        }

        try:
            self._post_notification_url(
                url,
                payload,
                headers,
            )

        except (
            ValueError,
            UnicodeError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ):
            return



    def _send_ntfy(
        self,
        event,
    ):
        with self.lock:
            config = deepcopy(
                NOTIFICATION_CONFIG["ntfy"]
            )

        if not config["enabled"]:
            return

        server_url = (
            config["server_url"]
            .strip()
            .rstrip("/")
        )

        topic = (
            config["topic"]
            .strip()
            .strip("/")
        )

        token = (
            config["token"]
            .strip()
        )

        if (
            not server_url
            or not topic
        ):
            return

        severity = (
            event.get("severity")
            or "warning"
        )

        message = (
            event.get("message")
            or "Alert"
        )

        metric = (
            event.get("metric")
            or ""
        )

        content = (
            f"[{severity.upper()}] "
            f"{message}"
        )

        if metric:
            content += (
                f"\nMetric: {metric}"
            )

        priority_map = {
            "critical": "5",
            "warning": "4",
            "info": "3",
        }

        priority = priority_map.get(
            severity.lower(),
            "3",
        )

        topic_path = urllib.parse.quote(
            topic,
            safe="",
        )

        url = (
            f"{server_url}/{topic_path}"
        )

        headers = {
            "Content-Type":
                "text/plain; charset=utf-8",
            "User-Agent":
                "X-ONU-SFPP-Dashboard",
            "Title":
                "X-ONU-SFPP Dashboard",
            "Priority":
                priority,
        }

        if token:
            headers["Authorization"] = (
                f"Bearer {token}"
            )

        try:
            self._post_notification_url(
                url,
                content.encode("utf-8"),
                headers,
            )

        except (
            ValueError,
            UnicodeError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ):
            return



    def _queued_notification_expired(
        self,
        queued,
    ):
        age = (
            time.monotonic()
            -
            queued["queued_at"]
        )

        return (
            age
            >
            NOTIFICATION_QUEUE_TTL_SECONDS
        )


    def _deliver_queued_notification(
        self,
        queued,
    ):
        """Deliver one queued notification unless it has become stale."""

        if self._queued_notification_expired(
            queued
        ):
            return False

        event = queued["event"]

        self._send_discord(
            event
        )

        self._send_pushover(
            event
        )

        self._send_gotify(
            event
        )

        self._send_ntfy(
            event
        )

        self._send_webhook(
            event
        )

        return True


    def _notification_worker(
        self,
    ):
        """Dispatch pending notifications without blocking alert storage."""

        while True:
            queued = self.notification_queue.get()

            try:
                self._deliver_queued_notification(
                    queued
                )

            except Exception as exc:
                print(
                    "Notification worker failed: "
                    f"{exc}"
                )

            finally:
                self.notification_queue.task_done()


    def process_event(
        self,
        event,
    ):
        """
        Queue a newly recorded alert event.

        Events are processed in FIFO order so
        notifications preserve alert ordering.
        Notification delivery remains asynchronous
        and cannot block alert collection or storage.
        """
        queued = {
            "queued_at": time.monotonic(),
            "event": deepcopy(event),
        }

        dropped_oldest = (
            self.notification_queue.put_latest(
                queued
            )
        )

        if dropped_oldest:
            print(
                "Notification queue full; oldest "
                "queued notification was dropped"
            )
