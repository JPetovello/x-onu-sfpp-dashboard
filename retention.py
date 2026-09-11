import json
import sqlite3
from datetime import datetime, timedelta, timezone


TELEMETRY_RETENTION_OPTIONS = {
    7,
    30,
    60,
    90,
    180,
    365,
}

ALERT_RETENTION_OPTIONS = {
    30,
    90,
    180,
    365,
}


class RetentionManager:
    """Manage telemetry and alert-history retention settings and cleanup.

    New installations use the dashboard's current retention defaults. Existing
    installations without saved dashboard-managed retention configuration keep
    their legacy telemetry retention value so an upgrade does not silently
    change established data-retention behavior.
    """

    def __init__(
        self,
        db_path,
        legacy_telemetry_days=30,
        new_install=False,
    ):
        self.db_path = db_path
        self.legacy_telemetry_days = max(
            1,
            int(legacy_telemetry_days),
        )
        self.new_install = bool(new_install)

        self._init_db()

    def _connect_db(self):
        con = sqlite3.connect(
            self.db_path,
            timeout=30,
        )
        con.row_factory = sqlite3.Row
        return con

    def _default_config(self):
        """Return defaults appropriate for a new or migrated installation.

        Existing installations inherit their legacy telemetry retention value;
        new installations begin with the current dashboard default.
        """

        if self.new_install:
            telemetry_days = 90
        else:
            telemetry_days = (
                self.legacy_telemetry_days
            )

        return {
            "telemetry_days": telemetry_days,
            "alert_days": 365,
        }

    def _init_db(self):
        with self._connect_db() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS retention_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    config_json TEXT NOT NULL
                )
                """
            )

            row = con.execute(
                """
                SELECT config_json
                FROM retention_config
                WHERE id = 1
                """
            ).fetchone()

            if row is None:
                con.execute(
                    """
                    INSERT INTO retention_config (
                        id,
                        config_json
                    )
                    VALUES (1, ?)
                    """,
                    (
                        json.dumps(
                            self._default_config()
                        ),
                    ),
                )

    def get_config(self):
        with self._connect_db() as con:
            row = con.execute(
                """
                SELECT config_json
                FROM retention_config
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return self._default_config()

        try:
            config = json.loads(
                row["config_json"]
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return self._default_config()

        defaults = self._default_config()

        return {
            "telemetry_days": config.get(
                "telemetry_days",
                defaults["telemetry_days"],
            ),
            "alert_days": config.get(
                "alert_days",
                defaults["alert_days"],
            ),
        }

    @staticmethod
    def _validate_days(
        value,
        allowed,
        field_name,
    ):
        if value is None:
            return None

        if isinstance(value, bool):
            raise ValueError(
                f"{field_name} must be a supported "
                "retention period or null"
            )

        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be a supported "
                "retention period or null"
            )

        if value not in allowed:
            raise ValueError(
                f"Unsupported {field_name}: {value}"
            )

        return value

    def save_config(self, config):
        """Validate and persist retention configuration.

        An unchanged legacy telemetry retention value is preserved even when it
        is not one of the current selectable UI options. This allows upgraded
        installations to retain their previous effective policy until the user
        deliberately chooses a new value.
        """

        if not isinstance(config, dict):
            raise ValueError(
                "Retention configuration must be "
                "a JSON object"
            )

        current = self.get_config()

        telemetry_value = (
            config["telemetry_days"]
            if "telemetry_days" in config
            else current["telemetry_days"]
        )

        current_telemetry_days = current[
            "telemetry_days"
        ]

        if (
            telemetry_value
            == current_telemetry_days
            and isinstance(
                current_telemetry_days,
                int,
            )
            and not isinstance(
                current_telemetry_days,
                bool,
            )
            and current_telemetry_days > 0
        ):
            telemetry_days = (
                current_telemetry_days
            )
        else:
            telemetry_days = self._validate_days(
                telemetry_value,
                TELEMETRY_RETENTION_OPTIONS,
                "telemetry_days",
            )

        alert_days = self._validate_days(
            (
                config["alert_days"]
                if "alert_days" in config
                else current["alert_days"]
            ),
            ALERT_RETENTION_OPTIONS,
            "alert_days",
        )

        saved = {
            "telemetry_days": telemetry_days,
            "alert_days": alert_days,
        }

        with self._connect_db() as con:
            con.execute(
                """
                INSERT INTO retention_config (
                    id,
                    config_json
                )
                VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    config_json = excluded.config_json
                """,
                (
                    json.dumps(saved),
                ),
            )

        return saved

    def cleanup(self):
        """Delete telemetry and alert events older than configured cutoffs."""

        config = self.get_config()
        now = datetime.now(timezone.utc)

        telemetry_days = config[
            "telemetry_days"
        ]

        alert_days = config["alert_days"]

        deleted = {
            "samples": 0,
            "advanced_samples": 0,
            "alert_events": 0,
        }

        with self._connect_db() as con:
            if telemetry_days is not None:
                cutoff = (
                    now
                    - timedelta(
                        days=telemetry_days
                    )
                ).isoformat()

                for table in (
                    "samples",
                    "advanced_samples",
                ):
                    cursor = con.execute(
                        f"""
                        DELETE FROM {table}
                        WHERE ts < ?
                        """,
                        (cutoff,),
                    )

                    deleted[table] = (
                        cursor.rowcount
                    )

            if alert_days is not None:
                cutoff = (
                    now
                    - timedelta(
                        days=alert_days
                    )
                ).isoformat()

                cursor = con.execute(
                    """
                    DELETE FROM alert_events
                    WHERE ts < ?
                    """,
                    (cutoff,),
                )

                deleted["alert_events"] = (
                    cursor.rowcount
                )

        return deleted
