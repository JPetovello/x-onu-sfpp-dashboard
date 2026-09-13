import json
import math
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime

from notifications import NotificationManager
from tx_health import classify_tx_power


CONFIG_VERSION = 3

TX_PROFILE_LEGACY = "legacy"
TX_PROFILE_XGSPONST2001_A01 = (
    "xgsponst2001-a01"
)
TX_PROFILE_CUSTOM = "custom"

TX_PROFILES = {
    TX_PROFILE_LEGACY: {
        "id": TX_PROFILE_LEGACY,
        "label": "Legacy",
        "description": (
            "Preserves the original dashboard "
            "TX grading and alert behavior."
        ),
        "thresholds": {
            "profile": TX_PROFILE_LEGACY,
            "operating_min": None,
            "operating_max": None,
            "low_alarm": 1,
            "low_warning": 2,
            "high_warning": 7,
            "high_alarm": 8,
            "cosmetic_great_low": 4,
            "cosmetic_great_high": 5,
        },
    },
    TX_PROFILE_XGSPONST2001_A01: {
        "id": TX_PROFILE_XGSPONST2001_A01,
        "label": "XGSPONST2001 A-01",
        "description": (
            "Uses the documented XGS-PON TX "
            "operating specification of 4.00-9.00 "
            "dBm inclusive. Values outside that "
            "envelope are out of specification."
        ),
        "thresholds": {
            "profile": TX_PROFILE_XGSPONST2001_A01,
            "operating_min": 4.0,
            "operating_max": 9.0,
            "low_alarm": None,
            "low_warning": None,
            "high_warning": None,
            "high_alarm": None,
            "cosmetic_great_low": None,
            "cosmetic_great_high": None,
        },
    },
}


PLOAM_STATES = {
    11: "O1.1 - Initial / searching",
    12: "O1.2 - Downstream sync",
    23: "O2.3 - Serial number sent",
    30: "O3 - Serial number acknowledged",
    40: "O4 - Ranging",
    51: "O5.1 - Associated",
}


DEFAULT_ALERT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "quality": {
        "warning_samples": 3,
        "warning_severity": "warning",
        "critical_severity": "critical",
        "recovery_severity": "info",
        "rx_power": {
            "poor_low": -27,
            "poor_high": -8,
            "fair_low": -24,
            "great_low": -20,
            "great_high": -14,
        },
        "tx_power": deepcopy(
            TX_PROFILES[
                TX_PROFILE_LEGACY
            ]["thresholds"]
        ),
        "thermal": {
            "warm": 75,
            "hot": 85,
        },
    },
    "ploam": {
        "operational_state": 51,
        "not_operational_severity": "critical",
        "recovered_severity": "info",
    },
    "gem_key_errors": {
        "severity": "warning",
        "min_delta": 1,
    },
    "active_alarms": {
        "increased_severity": "critical",
        "cleared_severity": "info",
        "decreased_severity": "info",
    },
    "core_reachability": {
        "failure_samples": 3,
        "unreachable_severity": "critical",
        "recovered_severity": "info",
    },
    "counters": (
        {
            "metric_name": "bip_errors",
            "alert_type": "bip_errors",
            "severity": "warning",
            "label": "BIP errors",
            "min_delta": 10,
            "cooldown_seconds": 300,
        },
        {
            "metric_name": "corrected_fec_codewords",
            "alert_type": "corrected_fec",
            "severity": "warning",
            "label": "Corrected FEC codewords",
            "min_delta": 100,
            "cooldown_seconds": 300,
        },
        {
            "metric_name": "uncorrected_fec_codewords",
            "alert_type": "uncorrected_fec",
            "severity": "critical",
            "label": "Uncorrected FEC codewords",
            "min_delta": 1,
            "cooldown_seconds": 0,
        },
        {
            "metric_name": "psbd_hec_corrected",
            "alert_type": "psbd_hec_corrected",
            "severity": "warning",
            "label": "Corrected PSBd HEC errors",
            "min_delta": 10,
            "cooldown_seconds": 300,
        },
        {
            "metric_name": "psbd_hec_uncorrected",
            "alert_type": "psbd_hec_uncorrected",
            "severity": "critical",
            "label": "Uncorrected PSBd HEC errors",
            "min_delta": 1,
            "cooldown_seconds": 0,
        },
        {
            "metric_name": "fs_hec_corrected",
            "alert_type": "fs_hec_corrected",
            "severity": "warning",
            "label": "Corrected FS HEC errors",
            "min_delta": 10,
            "cooldown_seconds": 300,
        },
        {
            "metric_name": "fs_hec_uncorrected",
            "alert_type": "fs_hec_uncorrected",
            "severity": "critical",
            "label": "Uncorrected FS HEC errors",
            "min_delta": 1,
            "cooldown_seconds": 0,
        },
        {
            "metric_name": "ploam_mic_errors",
            "alert_type": "ploam_mic_errors",
            "severity": "critical",
            "label": "PLOAM MIC errors",
            "min_delta": 1,
            "cooldown_seconds": 0,
        },
    ),
}

ALERT_CONFIG = deepcopy(
    DEFAULT_ALERT_CONFIG
)



class AlertManager:
    """Evaluate telemetry and persist alert state/events.

    Alert detection is stateful. The manager tracks previous observations,
    pending counter deltas, and cooldown timestamps so cumulative ONT counters
    generate events only when new errors occur.

    Event storage is kept separate from external notification delivery.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.RLock()

        self.previous = {}
        self.pending = {}
        self.last_alert = {}

        self.notification_manager = (
            NotificationManager(
                self.db_path
            )
        )

        self._init_db()
        self._load_config()


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
                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    metric TEXT,
                    previous_value REAL,
                    current_value REAL,
                    delta REAL,
                    message TEXT NOT NULL
                )
            """)

            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_events_ts
                ON alert_events(ts)
            """)

            con.execute("""
                CREATE TABLE IF NOT EXISTS alert_config (
                    id INTEGER PRIMARY KEY
                        CHECK (id = 1),
                    config_json TEXT NOT NULL
                )
            """)


    def validate_config(
        self,
        config,
    ):
        allowed_severities = {
            "info",
            "warning",
            "critical",
        }

        def require_dict(
            value,
            path,
        ):
            if not isinstance(
                value,
                dict,
            ):
                raise ValueError(
                    f"{path} must be an object"
                )

            return value

        def require_keys(
            value,
            expected,
            path,
        ):
            actual = set(
                value.keys()
            )

            expected = set(
                expected
            )

            missing = (
                expected
                -
                actual
            )

            extra = (
                actual
                -
                expected
            )

            if missing:
                names = ", ".join(
                    sorted(missing)
                )

                raise ValueError(
                    f"{path} is missing: {names}"
                )

            if extra:
                names = ", ".join(
                    sorted(extra)
                )

                raise ValueError(
                    f"{path} has unknown keys: {names}"
                )

        def require_severity(
            value,
            path,
        ):
            if value not in allowed_severities:
                allowed = ", ".join(
                    sorted(
                        allowed_severities
                    )
                )

                raise ValueError(
                    f"{path} must be one of: "
                    f"{allowed}"
                )

        def require_int(
            value,
            path,
            minimum=None,
            maximum=None,
        ):
            if (
                isinstance(
                    value,
                    bool,
                )
                or
                not isinstance(
                    value,
                    int,
                )
            ):
                raise ValueError(
                    f"{path} must be an integer"
                )

            if (
                minimum is not None
                and
                value < minimum
            ):
                raise ValueError(
                    f"{path} must be >= "
                    f"{minimum}"
                )

            if (
                maximum is not None
                and
                value > maximum
            ):
                raise ValueError(
                    f"{path} must be <= "
                    f"{maximum}"
                )

        def require_number(
            value,
            path,
        ):
            if (
                isinstance(
                    value,
                    bool,
                )
                or
                not isinstance(
                    value,
                    (
                        int,
                        float,
                    ),
                )
            ):
                raise ValueError(
                    f"{path} must be a number"
                )

            if not math.isfinite(
                float(value)
            ):
                raise ValueError(
                    f"{path} must be finite"
                )

        def require_optional_number(
            value,
            path,
        ):
            if value is not None:
                require_number(
                    value,
                    path,
                )

        config = require_dict(
            config,
            "config",
        )

        require_keys(
            config,
            DEFAULT_ALERT_CONFIG.keys(),
            "config",
        )

        require_int(
            config["config_version"],
            "config.config_version",
        )

        if config["config_version"] != CONFIG_VERSION:
            raise ValueError(
                "config.config_version must be "
                f"{CONFIG_VERSION}"
            )

        quality = require_dict(
            config["quality"],
            "quality",
        )

        require_keys(
            quality,
            DEFAULT_ALERT_CONFIG[
                "quality"
            ].keys(),
            "quality",
        )

        require_int(
            quality["warning_samples"],
            "quality.warning_samples",
            minimum=1,
            maximum=1000,
        )

        for key in (
            "warning_severity",
            "critical_severity",
            "recovery_severity",
        ):
            require_severity(
                quality[key],
                f"quality.{key}",
            )

        rx = require_dict(
            quality["rx_power"],
            "quality.rx_power",
        )

        require_keys(
            rx,
            DEFAULT_ALERT_CONFIG[
                "quality"
            ]["rx_power"].keys(),
            "quality.rx_power",
        )

        for key in (
            "poor_low",
            "poor_high",
            "fair_low",
            "great_low",
            "great_high",
        ):
            require_number(
                rx[key],
                f"quality.rx_power.{key}",
            )

        if not (
            rx["poor_low"]
            <
            rx["fair_low"]
            <=
            rx["great_low"]
            <=
            rx["great_high"]
            <=
            rx["poor_high"]
        ):
            raise ValueError(
                "RX thresholds must satisfy "
                "poor_low < fair_low <= "
                "great_low <= great_high <= "
                "poor_high"
            )

        tx = require_dict(
            quality["tx_power"],
            "quality.tx_power",
        )

        require_keys(
            tx,
            DEFAULT_ALERT_CONFIG[
                "quality"
            ]["tx_power"].keys(),
            "quality.tx_power",
        )

        profile = tx["profile"]

        if profile not in {
            TX_PROFILE_LEGACY,
            TX_PROFILE_XGSPONST2001_A01,
            TX_PROFILE_CUSTOM,
        }:
            raise ValueError(
                "quality.tx_power.profile must be "
                "one of: legacy, "
                "xgsponst2001-a01, custom"
            )

        for key in (
            "operating_min",
            "operating_max",
            "low_alarm",
            "low_warning",
            "high_warning",
            "high_alarm",
            "cosmetic_great_low",
            "cosmetic_great_high",
        ):
            require_optional_number(
                tx[key],
                f"quality.tx_power.{key}",
            )

        operating_min = tx["operating_min"]
        operating_max = tx["operating_max"]

        if (
            (operating_min is None)
            != (operating_max is None)
        ):
            raise ValueError(
                "TX operating envelope bounds must "
                "both be set or both be disabled"
            )

        if (
            operating_min is not None
            and operating_min >= operating_max
        ):
            raise ValueError(
                "TX operating envelope must satisfy "
                "operating_min < operating_max"
            )

        if (
            profile != TX_PROFILE_XGSPONST2001_A01
            and operating_min is not None
        ):
            raise ValueError(
                "TX operating envelope is only valid "
                "for the xgsponst2001-a01 profile"
            )

        if profile != TX_PROFILE_XGSPONST2001_A01:
            require_number(
                tx["low_alarm"],
                "quality.tx_power.low_alarm",
            )

            require_number(
                tx["low_warning"],
                "quality.tx_power.low_warning",
            )

            if tx["low_alarm"] >= tx["low_warning"]:
                raise ValueError(
                    "TX thresholds must satisfy "
                    "low_alarm < low_warning"
                )

            high_warning = tx["high_warning"]
            high_alarm = tx["high_alarm"]

            if (
                high_warning is not None
                and high_warning <= tx["low_warning"]
            ):
                raise ValueError(
                    "TX high_warning must be greater "
                    "than low_warning"
                )

            if (
                high_alarm is not None
                and high_alarm <= tx["low_warning"]
            ):
                raise ValueError(
                    "TX high_alarm must be greater "
                    "than low_warning"
                )

            if (
                high_warning is not None
                and high_alarm is not None
                and high_warning >= high_alarm
            ):
                raise ValueError(
                    "TX high thresholds must satisfy "
                    "high_warning < high_alarm"
                )

        great_low = tx["cosmetic_great_low"]
        great_high = tx["cosmetic_great_high"]

        if (great_low is None) != (great_high is None):
            raise ValueError(
                "TX cosmetic GREAT thresholds must "
                "both be set or both be disabled"
            )

        if (
            great_low is not None
            and great_low > great_high
        ):
            raise ValueError(
                "TX cosmetic GREAT thresholds must "
                "satisfy cosmetic_great_low <= "
                "cosmetic_great_high"
            )

        if profile in TX_PROFILES:
            expected = TX_PROFILES[
                profile
            ]["thresholds"]

            if tx != expected:
                raise ValueError(
                    "Named TX profiles must use "
                    "their defined thresholds; use "
                    "the custom profile for edits"
                )

        thermal = require_dict(
            quality["thermal"],
            "quality.thermal",
        )

        require_keys(
            thermal,
            DEFAULT_ALERT_CONFIG[
                "quality"
            ]["thermal"].keys(),
            "quality.thermal",
        )

        require_number(
            thermal["warm"],
            "quality.thermal.warm",
        )

        require_number(
            thermal["hot"],
            "quality.thermal.hot",
        )

        if not (
            thermal["warm"]
            <
            thermal["hot"]
        ):
            raise ValueError(
                "Thermal thresholds must satisfy "
                "warm < hot"
            )

        ploam = require_dict(
            config["ploam"],
            "ploam",
        )

        require_keys(
            ploam,
            DEFAULT_ALERT_CONFIG[
                "ploam"
            ].keys(),
            "ploam",
        )

        require_int(
            ploam["operational_state"],
            "ploam.operational_state",
            minimum=0,
            maximum=255,
        )

        require_severity(
            ploam[
                "not_operational_severity"
            ],
            (
                "ploam."
                "not_operational_severity"
            ),
        )

        require_severity(
            ploam[
                "recovered_severity"
            ],
            "ploam.recovered_severity",
        )

        gem = require_dict(
            config["gem_key_errors"],
            "gem_key_errors",
        )

        require_keys(
            gem,
            DEFAULT_ALERT_CONFIG[
                "gem_key_errors"
            ].keys(),
            "gem_key_errors",
        )

        require_severity(
            gem["severity"],
            "gem_key_errors.severity",
        )

        require_int(
            gem["min_delta"],
            "gem_key_errors.min_delta",
            minimum=1,
        )

        active_alarms = require_dict(
            config["active_alarms"],
            "active_alarms",
        )

        require_keys(
            active_alarms,
            DEFAULT_ALERT_CONFIG[
                "active_alarms"
            ].keys(),
            "active_alarms",
        )

        for key in (
            "increased_severity",
            "cleared_severity",
            "decreased_severity",
        ):
            require_severity(
                active_alarms[key],
                f"active_alarms.{key}",
            )

        reachability = require_dict(
            config["core_reachability"],
            "core_reachability",
        )

        require_keys(
            reachability,
            DEFAULT_ALERT_CONFIG[
                "core_reachability"
            ].keys(),
            "core_reachability",
        )

        require_int(
            reachability["failure_samples"],
            "core_reachability.failure_samples",
            minimum=1,
            maximum=1000,
        )

        for key in (
            "unreachable_severity",
            "recovered_severity",
        ):
            require_severity(
                reachability[key],
                (
                    "core_reachability."
                    f"{key}"
                ),
            )

        counters = config["counters"]

        if not isinstance(
            counters,
            (
                list,
                tuple,
            ),
        ):
            raise ValueError(
                "counters must be an array"
            )

        defaults_by_metric = {
            rule["metric_name"]: rule
            for rule in (
                DEFAULT_ALERT_CONFIG[
                    "counters"
                ]
            )
        }

        if len(counters) != len(
            defaults_by_metric
        ):
            raise ValueError(
                "counters must contain exactly "
                f"{len(defaults_by_metric)} rules"
            )

        seen_metrics = set()

        for index, rule in enumerate(
            counters
        ):
            path = (
                f"counters[{index}]"
            )

            rule = require_dict(
                rule,
                path,
            )

            require_keys(
                rule,
                (
                    "metric_name",
                    "alert_type",
                    "severity",
                    "label",
                    "min_delta",
                    "cooldown_seconds",
                ),
                path,
            )

            metric_name = rule[
                "metric_name"
            ]

            if metric_name not in (
                defaults_by_metric
            ):
                raise ValueError(
                    f"{path}.metric_name "
                    "is not a supported counter"
                )

            if metric_name in seen_metrics:
                raise ValueError(
                    f"Duplicate counter rule: "
                    f"{metric_name}"
                )

            seen_metrics.add(
                metric_name
            )

            default_rule = (
                defaults_by_metric[
                    metric_name
                ]
            )

            for identity_key in (
                "alert_type",
                "label",
            ):
                if (
                    rule[identity_key]
                    !=
                    default_rule[
                        identity_key
                    ]
                ):
                    raise ValueError(
                        f"{path}.{identity_key} "
                        "cannot be changed"
                    )

            require_severity(
                rule["severity"],
                f"{path}.severity",
            )

            require_int(
                rule["min_delta"],
                f"{path}.min_delta",
                minimum=1,
            )

            require_int(
                rule[
                    "cooldown_seconds"
                ],
                (
                    f"{path}."
                    "cooldown_seconds"
                ),
                minimum=0,
                maximum=86400,
            )

        return deepcopy(
            config
        )


    def _normalize_config_shape(
        self,
        config,
    ):
        """Upgrade legacy config in memory without changing its policy."""

        config = deepcopy(
            config
        )

        if not isinstance(config, dict):
            return config

        quality = config.get(
            "quality"
        )

        if not isinstance(quality, dict):
            return config

        tx = quality.get(
            "tx_power"
        )

        if (
            "config_version" not in config
            and isinstance(tx, dict)
        ):
            old_keys = {
                "poor_low",
                "poor_high",
                "fair_low",
                "fair_high",
                "great_low",
                "great_high",
            }

            if set(tx.keys()) == old_keys:
                old_default = {
                    "poor_low": 1,
                    "poor_high": 8,
                    "fair_low": 2,
                    "fair_high": 7,
                    "great_low": 4,
                    "great_high": 5,
                }

                profile = (
                    TX_PROFILE_LEGACY
                    if tx == old_default
                    else TX_PROFILE_CUSTOM
                )

                quality["tx_power"] = {
                    "profile": profile,
                    "operating_min": None,
                    "operating_max": None,
                    "low_alarm": tx["poor_low"],
                    "low_warning": tx["fair_low"],
                    "high_warning": tx["fair_high"],
                    "high_alarm": tx["poor_high"],
                    "cosmetic_great_low": tx["great_low"],
                    "cosmetic_great_high": tx["great_high"],
                }

                config["config_version"] = (
                    CONFIG_VERSION
                )

        tx = quality.get(
            "tx_power"
        )

        if (
            config.get("config_version") == 2
            and isinstance(tx, dict)
        ):
            version_two_keys = {
                "profile",
                "low_alarm",
                "low_warning",
                "high_warning",
                "high_alarm",
                "cosmetic_great_low",
                "cosmetic_great_high",
            }

            if set(tx.keys()) == version_two_keys:
                if (
                    tx.get("profile")
                    == TX_PROFILE_XGSPONST2001_A01
                ):
                    tx["profile"] = TX_PROFILE_CUSTOM

                tx["operating_min"] = None
                tx["operating_max"] = None
                config["config_version"] = (
                    CONFIG_VERSION
                )

        reachability = quality and config.get(
            "core_reachability"
        )

        if isinstance(reachability, dict):
            reachability.setdefault(
                "failure_samples",
                DEFAULT_ALERT_CONFIG[
                    "core_reachability"
                ]["failure_samples"],
            )

        return config


    def _write_config_row(
        self,
        con,
        config,
    ):
        con.execute(
            """
            INSERT INTO alert_config (
                id,
                config_json
            )
            VALUES (1, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                config_json = excluded.config_json
            """,
            (
                json.dumps(
                    config
                ),
            ),
        )


    def _load_config(
        self,
    ):
        with self._connect_db() as con:
            row = con.execute(
                """
                SELECT config_json
                FROM alert_config
                WHERE id = 1
                """
            ).fetchone()

            if row is None:
                config = self.validate_config(
                    DEFAULT_ALERT_CONFIG
                )

                self._write_config_row(
                    con,
                    config,
                )

            else:
                try:
                    config = json.loads(
                        row["config_json"]
                    )

                    config = self._normalize_config_shape(
                        config
                    )

                    config = (
                        self.validate_config(
                            config
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    config = (
                        self.validate_config(
                            DEFAULT_ALERT_CONFIG
                        )
                    )

                    self._write_config_row(
                        con,
                        config,
                    )

        global ALERT_CONFIG

        with self.lock:
            ALERT_CONFIG = deepcopy(
                config
            )


    def get_config(
        self,
    ):
        with self.lock:
            return deepcopy(
                ALERT_CONFIG
            )


    def get_tx_profiles(
        self,
    ):
        profiles = [
            deepcopy(profile)
            for profile in TX_PROFILES.values()
        ]

        profiles.append(
            {
                "id": TX_PROFILE_CUSTOM,
                "label": "Custom",
                "description": (
                    "User-defined TX warning and "
                    "alarm thresholds."
                ),
                "thresholds": None,
            }
        )

        return {
            "config_version": CONFIG_VERSION,
            "profiles": profiles,
        }


    def save_config(
        self,
        config,
    ):
        config = self._normalize_config_shape(
            config
        )

        config_copy = (
            self.validate_config(
                config
            )
        )

        with self._connect_db() as con:
            self._write_config_row(
                con,
                config_copy,
            )

        global ALERT_CONFIG

        with self.lock:
            previous_tx = deepcopy(
                ALERT_CONFIG["quality"][
                    "tx_power"
                ]
            )

            ALERT_CONFIG = deepcopy(
                config_copy
            )

            if (
                previous_tx
                != config_copy["quality"][
                    "tx_power"
                ]
            ):
                self._reset_tx_runtime_state_locked()

        return self.get_config()


    def _reset_tx_runtime_state_locked(
        self,
    ):
        state_key = (
            "core_quality",
            "tx_power_dBm",
        )

        active_key = (
            "quality_active",
            state_key,
        )

        pending_key = (
            "quality_pending",
            state_key,
        )

        self.previous.pop(
            state_key,
            None,
        )

        self.previous.pop(
            active_key,
            None,
        )

        self.pending.pop(
            pending_key,
            None,
        )


    def _timestamp_seconds(
        self,
        ts,
    ):
        try:
            return datetime.fromisoformat(
                ts
            ).timestamp()
        except (
            TypeError,
            ValueError,
        ):
            return None


    def _cooldown_active(
        self,
        state_key,
        ts,
        cooldown_seconds,
    ):
        if cooldown_seconds <= 0:
            return False

        current_time = (
            self._timestamp_seconds(
                ts
            )
        )

        if current_time is None:
            return False

        with self.lock:
            last_time = self.last_alert.get(
                state_key
            )

        if last_time is None:
            return False

        elapsed = (
            current_time
            -
            last_time
        )

        return (
            elapsed
            <
            cooldown_seconds
        )


    def _mark_alert(
        self,
        state_key,
        ts,
    ):
        current_time = (
            self._timestamp_seconds(
                ts
            )
        )

        if current_time is None:
            return

        with self.lock:
            self.last_alert[state_key] = (
                current_time
            )


    def _record_event(
        self,
        ts,
        alert_type,
        severity,
        metric,
        previous_value,
        current_value,
        delta,
        message,
    ):
        """Persist an alert before attempting external notification delivery.

        Notification failures are intentionally contained so an alert that was
        successfully detected and stored remains part of history even when an
        external provider is unavailable or misconfigured.
        """

        with self._connect_db() as con:
            con.execute(
                """
                INSERT INTO alert_events (
                    ts,
                    alert_type,
                    severity,
                    metric,
                    previous_value,
                    current_value,
                    delta,
                    message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    alert_type,
                    severity,
                    metric,
                    previous_value,
                    current_value,
                    delta,
                    message,
                ),
            )

        event = {
            "ts": ts,
            "alert_type": alert_type,
            "severity": severity,
            "metric": metric,
            "previous_value": previous_value,
            "current_value": current_value,
            "delta": delta,
            "message": message,
        }

        try:
            self.notification_manager.process_event(
                event
            )
        except Exception as exc:
            print(
                "Notification processing failed: "
                f"{exc}"
            )


    def _process_counter(
        self,
        ts,
        metrics,
        metric_name,
        alert_type,
        severity,
        label,
        min_delta=1,
        cooldown_seconds=0,
    ):
        """Process a cumulative counter using deltas rather than absolute value.

        The first observation establishes a baseline. Positive deltas may be
        accumulated while a cooldown is active, and a later flat sample may
        flush that pending increase once the cooldown expires.

        A decreasing counter is treated as a reset or ONT reboot and clears
        any pending delta instead of creating a false alert.
        """

        current = metrics.get(
            metric_name
        )

        if current is None:
            return

        state_key = (
            "counter",
            metric_name,
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

            self.previous[state_key] = (
                current
            )

        if previous is None:
            return

        sample_delta = (
            current
            -
            previous
        )

        # Counter decreased, most likely because
        # the ONT rebooted or the counter reset.
        if sample_delta < 0:
            with self.lock:
                self.pending.pop(
                    state_key,
                    None,
                )

            return

        with self.lock:
            pending = self.pending.get(
                state_key
            )

            if sample_delta > 0:
                if pending is None:
                    pending = {
                        "previous_value":
                            previous,
                        "delta":
                            0,
                    }

                pending["delta"] += (
                    sample_delta
                )

                self.pending[state_key] = (
                    pending
                )

            # A flat poll can still flush a pending
            # alert after its cooldown has expired.
            if pending is None:
                return

            accumulated_delta = (
                pending["delta"]
            )

            alert_previous = (
                pending[
                    "previous_value"
                ]
            )

        if accumulated_delta < min_delta:
            return

        alert_state_key = (
            "alert",
            alert_type,
        )

        if self._cooldown_active(
            alert_state_key,
            ts,
            cooldown_seconds,
        ):
            return

        self._record_event(
            ts=ts,
            alert_type=alert_type,
            severity=severity,
            metric=metric_name,
            previous_value=alert_previous,
            current_value=current,
            delta=accumulated_delta,
            message=(
                f"{label} increased by "
                f"{accumulated_delta} "
                f"({alert_previous} -> {current})"
            ),
        )

        with self.lock:
            self.pending.pop(
                state_key,
                None,
            )

        self._mark_alert(
            alert_state_key,
            ts,
        )


    def _process_gem_key_errors(
        self,
        ts,
        metrics,
    ):
        gem_id = metrics.get(
            "gem_id"
        )

        current = metrics.get(
            "key_errors"
        )

        if (
            gem_id is None
            or
            current is None
        ):
            return

        state_key = (
            "gem_key_errors",
            gem_id,
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

            self.previous[state_key] = (
                current
            )

        if previous is None:
            return

        delta = (
            current
            -
            previous
        )

        if delta < 0:
            return

        if delta < (
            ALERT_CONFIG[
                "gem_key_errors"
            ]["min_delta"]
        ):
            return

        self._record_event(
            ts=ts,
            alert_type="gem_key_errors",
            severity=(
                ALERT_CONFIG[
                    "gem_key_errors"
                ]["severity"]
            ),
            metric="key_errors",
            previous_value=previous,
            current_value=current,
            delta=delta,
            message=(
                f"GEM {gem_id} key errors "
                f"increased by {delta} "
                f"({previous} -> {current})"
            ),
        )


    def _process_active_alarms(
        self,
        ts,
        metrics,
    ):
        current = metrics.get(
            "active_alarm_count"
        )

        if current is None:
            return

        state_key = (
            "active_alarm_count",
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

            self.previous[state_key] = (
                current
            )

        if previous is None:
            return

        if current == previous:
            return

        delta = (
            current
            -
            previous
        )

        if current > previous:
            self._record_event(
                ts=ts,
                alert_type="active_alarms",
                severity=(
                    ALERT_CONFIG[
                        "active_alarms"
                    ]["increased_severity"]
                ),
                metric="active_alarm_count",
                previous_value=previous,
                current_value=current,
                delta=delta,
                message=(
                    f"Active alarms increased "
                    f"from {previous} to {current}"
                ),
            )

            return

        if current == 0:
            self._record_event(
                ts=ts,
                alert_type="active_alarms_cleared",
                severity=(
                    ALERT_CONFIG[
                        "active_alarms"
                    ]["cleared_severity"]
                ),
                metric="active_alarm_count",
                previous_value=previous,
                current_value=current,
                delta=delta,
                message=(
                    f"Active alarms cleared "
                    f"({previous} -> 0)"
                ),
            )

            return

        self._record_event(
            ts=ts,
            alert_type="active_alarms_decreased",
            severity=(
                ALERT_CONFIG[
                    "active_alarms"
                ]["decreased_severity"]
            ),
            metric="active_alarm_count",
            previous_value=previous,
            current_value=current,
            delta=delta,
            message=(
                f"Active alarms decreased "
                f"from {previous} to {current}"
            ),
        )


    def _rx_status(
        self,
        value,
    ):
        thresholds = (
            ALERT_CONFIG["quality"][
                "rx_power"
            ]
        )

        try:
            value = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return (
                "UNKNOWN",
                "unknown",
                None,
            )

        if not math.isfinite(value):
            return (
                "UNKNOWN",
                "unknown",
                None,
            )

        if (
            value <= thresholds["poor_low"]
            or
            value > thresholds["poor_high"]
        ):
            return (
                "POOR",
                "bad",
                value,
            )

        if value < thresholds["fair_low"]:
            return (
                "FAIR",
                "warn",
                value,
            )

        if (
            value >= thresholds["great_low"]
            and
            value <= thresholds["great_high"]
        ):
            return (
                "GREAT",
                "good",
                value,
            )

        return (
            "GOOD",
            "good",
            value,
        )


    def _tx_status(
        self,
        value,
    ):
        thresholds = (
            ALERT_CONFIG["quality"][
                "tx_power"
            ]
        )

        return classify_tx_power(
            value,
            thresholds,
        )


    def _thermal_status(
        self,
        metrics,
    ):
        thresholds = (
            ALERT_CONFIG["quality"][
                "thermal"
            ]
        )

        values = []

        for metric_name in (
            "optic_tempC",
            "cpu1_tempC",
            "cpu2_tempC",
        ):
            value = metrics.get(
                metric_name
            )

            try:
                value = float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if not math.isfinite(value):
                continue

            values.append(
                value
            )

        if not values:
            return (
                "UNKNOWN",
                "unknown",
                None,
            )

        maximum = max(
            values
        )

        if maximum >= thresholds["hot"]:
            return (
                "HOT",
                "bad",
                maximum,
            )

        if maximum >= thresholds["warm"]:
            return (
                "WARM",
                "warn",
                maximum,
            )

        return (
            "NORMAL",
            "good",
            maximum,
        )


    def _process_core_reachability(
        self,
        ts,
        online,
        error=None,
    ):
        state_key = (
            "core_reachability",
        )

        pending_key = (
            "core_reachability",
        )

        current = bool(
            online
        )

        failure_samples = (
            ALERT_CONFIG[
                "core_reachability"
            ]["failure_samples"]
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

        if current:
            with self.lock:
                self.pending.pop(
                    pending_key,
                    None,
                )

                if previous is None:
                    self.previous[state_key] = (
                        True
                    )

                    return

                if previous:
                    return

                self.previous[state_key] = (
                    True
                )

            self._record_event(
                ts=ts,
                alert_type="core_recovered",
                severity=(
                    ALERT_CONFIG[
                        "core_reachability"
                    ]["recovered_severity"]
                ),
                metric="online",
                previous_value=0,
                current_value=1,
                delta=1,
                message=(
                    "Core telemetry connection "
                    "recovered"
                ),
            )

            return

        with self.lock:
            if previous is False:
                self.pending.pop(
                    pending_key,
                    None,
                )

                return

            pending = self.pending.get(
                pending_key
            )

            if pending is None:
                pending = {
                    "count": 1,
                }
            else:
                pending["count"] += 1

            self.pending[pending_key] = (
                pending
            )

            count = pending["count"]

        if count < failure_samples:
            return

        with self.lock:
            self.pending.pop(
                pending_key,
                None,
            )

            self.previous[state_key] = (
                False
            )

        if previous is None:
            message = (
                "Core telemetry is unreachable "
                "at startup"
            )

            previous_value = None
            delta = None

        else:
            message = (
                "Core telemetry became "
                "unreachable"
            )

            previous_value = 1
            delta = -1

        if error:
            message += (
                f": {error}"
            )

        self._record_event(
            ts=ts,
            alert_type="core_unreachable",
            severity=(
                ALERT_CONFIG[
                    "core_reachability"
                ]["unreachable_severity"]
            ),
            metric="online",
            previous_value=previous_value,
            current_value=0,
            delta=delta,
            message=message,
        )

    def _process_ploam_state(
        self,
        ts,
        metrics,
    ):
        value = metrics.get(
            "ploam_state"
        )

        try:
            numeric_value = float(
                value
            )

            if not math.isfinite(
                numeric_value
            ):
                return

            current = int(
                numeric_value
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return

        current_operational = (
            current
            ==
            ALERT_CONFIG["ploam"][
                "operational_state"
            ]
        )

        state_key = (
            "ploam_operational",
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

            self.previous[state_key] = (
                (
                    current_operational,
                    current,
                )
            )

        if previous is None:
            if current_operational:
                return

            current_name = (
                PLOAM_STATES.get(
                    current,
                    f"State {current}",
                )
            )

            self._record_event(
                ts=ts,
                alert_type="ploam_not_operational",
                severity=(
                    ALERT_CONFIG["ploam"][
                        "not_operational_severity"
                    ]
                ),
                metric="ploam_state",
                previous_value=None,
                current_value=current,
                delta=None,
                message=(
                    "PLOAM started in "
                    f"{current_name}"
                ),
            )

            return

        (
            previous_operational,
            previous_state,
        ) = previous

        if (
            current_operational
            ==
            previous_operational
        ):
            return

        current_name = (
            PLOAM_STATES.get(
                current,
                f"State {current}",
            )
        )

        previous_name = (
            PLOAM_STATES.get(
                previous_state,
                f"State {previous_state}",
            )
        )

        if current_operational:
            self._record_event(
                ts=ts,
                alert_type="ploam_recovered",
                severity=(
                    ALERT_CONFIG["ploam"][
                        "recovered_severity"
                    ]
                ),
                metric="ploam_state",
                previous_value=previous_state,
                current_value=current,
                delta=(
                    current
                    -
                    previous_state
                ),
                message=(
                    "PLOAM state recovered "
                    f"from {previous_name} "
                    f"to {current_name}"
                ),
            )

            return

        self._record_event(
            ts=ts,
            alert_type="ploam_not_operational",
            severity=(
                ALERT_CONFIG["ploam"][
                    "not_operational_severity"
                ]
            ),
            metric="ploam_state",
            previous_value=previous_state,
            current_value=current,
            delta=(
                current
                -
                previous_state
            ),
            message=(
                "PLOAM state left "
                f"{previous_name} "
                f"and entered {current_name}"
            ),
        )


    def _process_quality_state(
        self,
        ts,
        state_key,
        alert_prefix,
        metric_name,
        label,
        status_text,
        level,
        value,
        unit,
    ):
        pending_key = (
            "quality_pending",
            state_key,
        )

        if level == "unknown":
            with self.lock:
                self.pending.pop(
                    pending_key,
                    None,
                )

            return

        if value is None:
            return

        active_key = (
            "quality_active",
            state_key,
        )

        with self.lock:
            previous = self.previous.get(
                state_key
            )

            self.previous[state_key] = (
                (
                    status_text,
                    level,
                    value,
                )
            )

            active_level = (
                self.previous.get(
                    active_key
                )
            )

        if previous is None:
            if level == "good":
                return

            previous = (
                status_text,
                level,
                value,
            )

        (
            previous_text,
            previous_level,
            previous_value,
        ) = previous

        if level == "bad":
            with self.lock:
                self.pending.pop(
                    pending_key,
                    None,
                )

            if active_level == "bad":
                return

            self._record_event(
                ts=ts,
                alert_type=(
                    f"{alert_prefix}_poor"
                ),
                severity=(
                    ALERT_CONFIG["quality"][
                        "critical_severity"
                    ]
                ),
                metric=metric_name,
                previous_value=previous_value,
                current_value=value,
                delta=(
                    value
                    -
                    previous_value
                ),
                message=(
                    f"{label} entered "
                    f"{status_text} range "
                    f"({previous_value:g}{unit} "
                    f"-> {value:g}{unit})"
                ),
            )

            with self.lock:
                self.previous[
                    active_key
                ] = "bad"

            return

        if level == "warn":
            if active_level == "warn":
                with self.lock:
                    self.pending.pop(
                        pending_key,
                        None,
                    )

                return

            with self.lock:
                pending = self.pending.get(
                    pending_key
                )

                if (
                    pending is None
                    or
                    pending.get("level")
                    != "warn"
                ):
                    pending = {
                        "level": "warn",
                        "count": 1,
                        "previous_text":
                            previous_text,
                        "previous_value":
                            previous_value,
                    }
                else:
                    pending["count"] += 1

                self.pending[
                    pending_key
                ] = pending

                count = pending["count"]

                alert_previous_text = (
                    pending[
                        "previous_text"
                    ]
                )

                alert_previous_value = (
                    pending[
                        "previous_value"
                    ]
                )

            if count < (
                ALERT_CONFIG["quality"][
                    "warning_samples"
                ]
            ):
                return

            if active_level == "bad":
                message = (
                    f"{label} improved "
                    f"from {alert_previous_text} "
                    f"to {status_text} "
                    f"({alert_previous_value:g}{unit} "
                    f"-> {value:g}{unit})"
                )
            else:
                message = (
                    f"{label} entered "
                    f"{status_text} range "
                    f"({alert_previous_value:g}{unit} "
                    f"-> {value:g}{unit})"
                )

            self._record_event(
                ts=ts,
                alert_type=(
                    f"{alert_prefix}_warning"
                ),
                severity=(
                    ALERT_CONFIG["quality"][
                        "warning_severity"
                    ]
                ),
                metric=metric_name,
                previous_value=(
                    alert_previous_value
                ),
                current_value=value,
                delta=(
                    value
                    -
                    alert_previous_value
                ),
                message=message,
            )

            with self.lock:
                self.pending.pop(
                    pending_key,
                    None,
                )

                self.previous[
                    active_key
                ] = "warn"

            return

        if level == "good":
            with self.lock:
                self.pending.pop(
                    pending_key,
                    None,
                )

            if active_level not in (
                "warn",
                "bad",
            ):
                return

            self._record_event(
                ts=ts,
                alert_type=(
                    f"{alert_prefix}_recovered"
                ),
                severity=(
                    ALERT_CONFIG["quality"][
                        "recovery_severity"
                    ]
                ),
                metric=metric_name,
                previous_value=previous_value,
                current_value=value,
                delta=(
                    value
                    -
                    previous_value
                ),
                message=(
                    f"{label} recovered "
                    f"from {previous_text} "
                    f"to {status_text} "
                    f"({previous_value:g}{unit} "
                    f"-> {value:g}{unit})"
                ),
            )

            with self.lock:
                self.previous.pop(
                    active_key,
                    None,
                )


    def _process_rx_power(
        self,
        ts,
        metrics,
    ):
        (
            status_text,
            level,
            value,
        ) = self._rx_status(
            metrics.get(
                "rx_power_dBm"
            )
        )

        self._process_quality_state(
            ts=ts,
            state_key=(
                "core_quality",
                "rx_power_dBm",
            ),
            alert_prefix="rx_power",
            metric_name="rx_power_dBm",
            label="RX power",
            status_text=status_text,
            level=level,
            value=value,
            unit=" dBm",
        )


    def _process_tx_power(
        self,
        ts,
        metrics,
    ):
        # Keep classification and transition processing atomic with a TX
        # policy change so a sample cannot straddle the old and new policy.
        with self.lock:
            (
                status_text,
                level,
                value,
            ) = self._tx_status(
                metrics.get(
                    "tx_power_dBm"
                )
            )

            self._process_quality_state(
                ts=ts,
                state_key=(
                    "core_quality",
                    "tx_power_dBm",
                ),
                alert_prefix="tx_power",
                metric_name="tx_power_dBm",
                label="TX power",
                status_text=status_text,
                level=level,
                value=value,
                unit=" dBm",
            )


    def _process_thermal_state(
        self,
        ts,
        metrics,
    ):
        (
            status_text,
            level,
            value,
        ) = self._thermal_status(
            metrics
        )

        self._process_quality_state(
            ts=ts,
            state_key=(
                "core_quality",
                "thermal",
            ),
            alert_prefix="thermal",
            metric_name="temperature_max",
            label="Thermal state",
            status_text=status_text,
            level=level,
            value=value,
            unit=" C",
        )


    def process_core_sample(
        self,
        ts,
        metrics,
    ):
        """Evaluate alerts derived from a successful core telemetry sample."""

        self._process_core_reachability(
            ts=ts,
            online=True,
        )

        self._process_ploam_state(
            ts,
            metrics,
        )

        self._process_rx_power(
            ts,
            metrics,
        )

        self._process_tx_power(
            ts,
            metrics,
        )

        self._process_thermal_state(
            ts,
            metrics,
        )


    def process_core_unreachable(
        self,
        ts,
        error=None,
    ):
        """Record core-collector reachability state when collection fails."""

        self._process_core_reachability(
            ts=ts,
            online=False,
            error=error,
        )


    def process_sample(
        self,
        ts,
        metrics,
    ):
        """Evaluate alerts derived from one advanced SSH telemetry sample."""

        self._process_gem_key_errors(
            ts,
            metrics,
        )

        for rule in (
            ALERT_CONFIG["counters"]
        ):
            self._process_counter(
                ts=ts,
                metrics=metrics,
                metric_name=(
                    rule["metric_name"]
                ),
                alert_type=(
                    rule["alert_type"]
                ),
                severity=(
                    rule["severity"]
                ),
                label=rule["label"],
                min_delta=(
                    rule["min_delta"]
                ),
                cooldown_seconds=(
                    rule[
                        "cooldown_seconds"
                    ]
                ),
            )

        self._process_active_alarms(
            ts,
            metrics,
        )


    def recent_events(
        self,
        limit=100,
        offset=0,
    ):
        limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        offset = max(
            0,
            int(offset),
        )

        with self._connect_db() as con:
            rows = con.execute(
                """
                SELECT
                    id,
                    ts,
                    alert_type,
                    severity,
                    metric,
                    previous_value,
                    current_value,
                    delta,
                    message
                FROM alert_events
                ORDER BY ts DESC
                LIMIT ?
                OFFSET ?
                """,
                (
                    limit,
                    offset,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def event_count(self):
        with self._connect_db() as con:
            row = con.execute(
                """
                SELECT COUNT(*) AS count
                FROM alert_events
                """
            ).fetchone()

        return int(row["count"])
