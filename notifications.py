import json
import queue
import sqlite3
import threading
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


class NotificationManager:
    """Deliver stored alert events to configured external providers.

    Notification delivery runs on a dedicated background worker so external
    network requests cannot block alert detection or persistence. Events are
    queued in FIFO order and dispatched independently of telemetry collection.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.notification_queue = queue.Queue()

        self._init_db()
        self._load_config()

        self.notification_worker = threading.Thread(
            target=self._notification_worker,
            daemon=True,
        )

        self.notification_worker.start()


    def _connect_db(self):
        con = sqlite3.connect(
            self.db_path,
            timeout=10,
        )

        con.row_factory = sqlite3.Row

        return con


    def _init_db(self):
        with self._connect_db() as con:
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

        if (
            webhook["url"].strip()
            and not webhook["url"].strip().startswith(
                ("http://", "https://")
            )
        ):
            raise ValueError(
                "webhook.url must start with "
                "http:// or https://"
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

        if (
            gotify["server_url"]
            and not (
                gotify["server_url"].startswith(
                    "http://"
                )
                or gotify["server_url"].startswith(
                    "https://"
                )
            )
        ):
            raise ValueError(
                "gotify.server_url must start with "
                "http:// or https://"
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

        if (
            ntfy["server_url"]
            and not (
                ntfy["server_url"].startswith(
                    "http://"
                )
                or ntfy["server_url"].startswith(
                    "https://"
                )
            )
        ):
            raise ValueError(
                "ntfy.server_url must start with "
                "http:// or https://"
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

        with self._connect_db() as con:
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

        with self._connect_db() as con:
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

        request = urllib.request.Request(
            url,
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

        request = urllib.request.Request(
            url,
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

        request = urllib.request.Request(
            url,
            data=content.encode("utf-8"),
            headers=headers,
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


    def _notification_worker(
        self,
    ):
        """Dispatch queued events to each notification provider."""

        while True:
            event = self.notification_queue.get()

            try:
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
        self.notification_queue.put(
            deepcopy(event)
        )
