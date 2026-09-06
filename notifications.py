import json
import queue
import sqlite3
import threading
import urllib.error
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

        for provider in (
            "gotify",
            "pushover",
            "ntfy",
            "webhook",
        ):
            if config[provider]["enabled"]:
                raise ValueError(
                    f"{provider} notifications "
                    "are not implemented yet"
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


    def get_config(
        self,
    ):
        with self.lock:
            return deepcopy(
                NOTIFICATION_CONFIG
            )


    def save_config(
        self,
        config,
    ):
        global NOTIFICATION_CONFIG

        validated = self.validate_config(
            config
        )

        self._write_config_row(
            validated
        )

        with self.lock:
            NOTIFICATION_CONFIG = deepcopy(
                validated
            )

            return deepcopy(
                NOTIFICATION_CONFIG
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


    def _notification_worker(
        self,
    ):
        while True:
            event = self.notification_queue.get()

            try:
                self._send_discord(
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
