import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import paramiko

from alerts import AlertManager


RANGES = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


class _TOFUPolicy(
    paramiko.MissingHostKeyPolicy
):
    """Remember the first SSH host key until authentication succeeds."""

    def __init__(self):
        self.hostname = None
        self.key = None

    def missing_host_key(
        self,
        client,
        hostname,
        key,
    ):
        self.hostname = hostname
        self.key = key


class AdvancedCollector:
    def __init__(self, db_path, retention_days=30):
        self.db_path = db_path
        self.retention_days = retention_days

        self.enabled = os.environ.get(
            "SSH_ENABLED", "false"
        ).strip().lower() in {
            "1", "true", "yes", "on"
        }

        self.host = os.environ.get(
            "SSH_HOST", "192.168.11.1"
        )

        self.port = max(
            1,
            int(os.environ.get("SSH_PORT", "22"))
        )

        self.user = os.environ.get(
            "SSH_USER", "root"
        )

        self.password = os.environ.get(
            "SSH_PASSWORD", ""
        )

        self.known_hosts_path = os.path.join(
            os.path.dirname(self.db_path),
            "ssh_known_hosts",
        )

        self.poll_seconds = max(
            15,
            int(
                os.environ.get(
                    "SSH_POLL_SECONDS",
                    "30",
                )
            ),
        )

        self.timeout = max(
            3,
            int(
                os.environ.get(
                    "SSH_TIMEOUT",
                    "10",
                )
            ),
        )

        self.command_timeout = max(
            5,
            int(
                os.environ.get(
                    "SSH_COMMAND_TIMEOUT",
                    "30",
                )
            ),
        )

        self.lock = threading.Lock()

        self.state = {
            "enabled": self.enabled,
            "online": False,
            "last_success": None,
            "last_error": None,
            "metrics": None,
            "module_info": None,
        }

        self.previous_counter_sample = None

        self._init_db()

        self.alert_manager = AlertManager(
            self.db_path
        )


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
                CREATE TABLE IF NOT EXISTS
                advanced_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,

                    pon_state TEXT,
                    fec_upstream TEXT,
                    fec_downstream TEXT,

                    active_alarm_count INTEGER,

                    gem_index INTEGER,
                    gem_id INTEGER,
                    alloc_id INTEGER,

                    us_packets INTEGER,
                    us_bytes INTEGER,

                    ds_packets INTEGER,
                    ds_bytes INTEGER,

                    key_errors INTEGER,

                    upload_bps REAL,
                    download_bps REAL,

                    bip_errors INTEGER,
                    total_fec_codewords INTEGER,
                    corrected_fec_codewords INTEGER,
                    uncorrected_fec_codewords INTEGER,
                    corrected_fec_bytes INTEGER,
                    fec_errored_seconds INTEGER,

                    psbd_hec_corrected INTEGER,
                    psbd_hec_uncorrected INTEGER,
                    fs_hec_corrected INTEGER,
                    fs_hec_uncorrected INTEGER,
                    lost_words_hec INTEGER,
                    ploam_mic_errors INTEGER,

                    ont_uptime_seconds REAL,

                    load_1m REAL,
                    load_5m REAL,
                    load_15m REAL,

                    memory_total_kb INTEGER,
                    memory_used_kb INTEGER,
                    memory_available_kb INTEGER,

                    alarms_json TEXT
                )
            """)

            con.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_advanced_samples_ts
                ON advanced_samples(ts)
            """)


    @staticmethod
    def _safe_int(value):

        try:
            return int(
                str(value).strip()
            )

        except (
            TypeError,
            ValueError,
        ):
            return None


    @staticmethod
    def _safe_float(value):

        try:
            return float(
                str(value).strip()
            )

        except (
            TypeError,
            ValueError,
        ):
            return None


    @staticmethod
    def _parse_key_values(text):

        result = {}

        for raw_line in text.splitlines():

            if ":" not in raw_line:
                continue

            key, value = raw_line.split(
                ":",
                1,
            )

            key = key.strip()
            value = value.strip()

            if key:
                result[key] = value

        return result


    @staticmethod
    def _split_sections(output):

        sections = {}

        current = None
        lines = []

        for line in output.splitlines():

            match = re.fullmatch(
                r"__XONU_([A-Z0-9_]+)__",
                line.strip(),
            )

            if match:

                if current is not None:

                    sections[current] = (
                        "\n".join(lines).strip()
                    )

                current = match.group(1)
                lines = []

            elif current is not None:

                lines.append(line)

        if current is not None:

            sections[current] = (
                "\n".join(lines).strip()
            )

        return sections


    @staticmethod
    def _parse_gem_status(text):

        gems = []

        for line in text.splitlines():

            match = re.match(
                r"^\s*(\d+)\s+"
                r"(\d+)\s+"
                r"(\S+)\s+"
                r"(\S+)\s+"
                r"(OMCI|Ethernet)\s+",
                line,
            )

            if not match:
                continue

            alloc_id = (
                None
                if match.group(3) == "n.a."
                else int(match.group(3))
            )

            gems.append({
                "gem_index":
                    int(match.group(1)),

                "gem_id":
                    int(match.group(2)),

                "alloc_id":
                    alloc_id,

                "alloc_status":
                    match.group(4),

                "kind":
                    match.group(5),
            })

        return gems


    @staticmethod
    def _parse_gem_counters(text):

        counters = {}

        for line in text.splitlines():

            match = re.match(
                r"^\s*(\d+)\s+"
                r"(\d+)\s+"
                r"(\d+)\s+"
                r"(\d+)\s+"
                r"(\d+)\s+"
                r"(\d+)\s+"
                r"(\d+)\s*$",
                line,
            )

            if not match:
                continue

            values = [
                int(match.group(i))
                for i in range(1, 8)
            ]

            counters[values[0]] = {
                "gem_index": values[0],
                "gem_id": values[1],
                "us_packets": values[2],
                "us_bytes": values[3],
                "ds_packets": values[4],
                "ds_bytes": values[5],
                "key_errors": values[6],
            }

        return counters


    @staticmethod
    def _select_data_gem(
        gems,
        counters,
    ):

        candidates = [
            gem
            for gem in gems
            if (
                gem["kind"] == "Ethernet"
                and
                gem["alloc_status"] == "Valid"
                and
                gem["gem_id"] != 65534
                and
                gem["gem_index"] in counters
            )
        ]

        if not candidates:

            candidates = [
                gem
                for gem in gems
                if (
                    gem["kind"] == "Ethernet"
                    and
                    gem["gem_id"] != 65534
                    and
                    gem["gem_index"] in counters
                )
            ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda gem: (
                counters[
                    gem["gem_index"]
                ]["ds_bytes"]
                +
                counters[
                    gem["gem_index"]
                ]["us_bytes"]
            ),
        )


    @staticmethod
    def _parse_alarms(text):

        alarms = []

        for line in text.splitlines():

            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith(
                "Page:"
            ):
                continue

            if stripped.startswith(
                "Alarm type"
            ):
                continue

            if (
                set(stripped)
                <= {"-", "="}
            ):
                continue

            alarms.append(stripped)

        return alarms


    def _parse_system(self, text):

        result = {
            "ont_uptime_seconds": None,
            "load_1m": None,
            "load_5m": None,
            "load_15m": None,
            "memory_total_kb": None,
            "memory_used_kb": None,
            "memory_available_kb": None,
        }

        for line in text.splitlines():

            line = line.strip()

            if line.startswith("UPTIME "):

                parts = line.split()

                if len(parts) >= 2:
                    result[
                        "ont_uptime_seconds"
                    ] = self._safe_float(
                        parts[1]
                    )

            elif line.startswith("LOAD "):

                parts = line.split()

                if len(parts) >= 4:

                    result["load_1m"] = (
                        self._safe_float(
                            parts[1]
                        )
                    )

                    result["load_5m"] = (
                        self._safe_float(
                            parts[2]
                        )
                    )

                    result["load_15m"] = (
                        self._safe_float(
                            parts[3]
                        )
                    )

            elif line.startswith("MEM "):

                parts = line.split()

                if len(parts) >= 4:

                    result[
                        "memory_total_kb"
                    ] = self._safe_int(
                        parts[1]
                    )

                    result[
                        "memory_used_kb"
                    ] = self._safe_int(
                        parts[2]
                    )

                    result[
                        "memory_available_kb"
                    ] = self._safe_int(
                        parts[3]
                    )

        return result


    def _ssh_client(self):

        if not self.password:

            raise RuntimeError(
                "SSH_PASSWORD is empty"
            )

        client = paramiko.SSHClient()

        tofu_policy = None

        if os.path.exists(
            self.known_hosts_path
        ):
            client.load_host_keys(
                self.known_hosts_path
            )
            client.set_missing_host_key_policy(
                paramiko.RejectPolicy()
            )
        else:
            tofu_policy = _TOFUPolicy()

            client.set_missing_host_key_policy(
                tofu_policy
            )

        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,

            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,

            look_for_keys=False,
            allow_agent=False,
        )

        if (
            tofu_policy is not None
            and tofu_policy.hostname is not None
            and tofu_policy.key is not None
        ):
            host_keys = paramiko.HostKeys()

            host_keys.add(
                tofu_policy.hostname,
                tofu_policy.key.get_name(),
                tofu_policy.key,
            )

            host_keys.save(
                self.known_hosts_path
            )

        return client


    def _exec(
        self,
        client,
        command,
    ):

        stdin, stdout, stderr = (
            client.exec_command(
                command,
                timeout=
                    self.command_timeout,
            )
        )

        stdout.channel.settimeout(
            self.command_timeout
        )

        output = stdout.read().decode(
            "utf-8",
            errors="replace",
        )

        error = stderr.read().decode(
            "utf-8",
            errors="replace",
        )

        exit_status = (
            stdout
            .channel
            .recv_exit_status()
        )

        if exit_status != 0:

            raise RuntimeError(
                "SSH command exited "
                f"{exit_status}: "
                f"{error.strip() or 'no stderr'}"
            )

        return output


    def _collect_dynamic(
        self,
        client,
    ):

        command = r'''
echo __XONU_STATUS__
pontop -b -g s

echo __XONU_ALARMS__
pontop -b -g w

echo __XONU_GEM_STATUS__
pontop -b -g 'GEM/XGEM Port Status'

echo __XONU_GEM_COUNTERS__
pontop -b -g 'GEM/XGEM Port Counters'

echo __XONU_FEC__
pontop -b -g f

echo __XONU_GTC__
pontop -b -g t

echo __XONU_SYSTEM__
awk '{print "UPTIME " $1}' /proc/uptime
awk '{print "LOAD " $1 " " $2 " " $3}' /proc/loadavg
awk '
/MemTotal:/ {
    total=$2
}
/MemAvailable:/ {
    available=$2
}
END {
    print "MEM " total " " total-available " " available
}
' /proc/meminfo
'''

        output = self._exec(
            client,
            command,
        )

        sections = self._split_sections(
            output
        )

        status = self._parse_key_values(
            sections.get(
                "STATUS",
                "",
            )
        )

        fec = self._parse_key_values(
            sections.get(
                "FEC",
                "",
            )
        )

        gtc = self._parse_key_values(
            sections.get(
                "GTC",
                "",
            )
        )

        gems = self._parse_gem_status(
            sections.get(
                "GEM_STATUS",
                "",
            )
        )

        counters = (
            self._parse_gem_counters(
                sections.get(
                    "GEM_COUNTERS",
                    "",
                )
            )
        )

        selected_gem = (
            self._select_data_gem(
                gems,
                counters,
            )
        )

        alarms = self._parse_alarms(
            sections.get(
                "ALARMS",
                "",
            )
        )

        system = self._parse_system(
            sections.get(
                "SYSTEM",
                "",
            )
        )

        metrics = {
            "pon_state":
                status.get(
                    "PON PLOAM Status"
                ),

            "fec_upstream":
                status.get(
                    "FEC upstream"
                )
                or
                fec.get(
                    "FEC upstream"
                ),

            "fec_downstream":
                status.get(
                    "FEC downstream"
                )
                or
                fec.get(
                    "FEC downstream"
                ),

            "active_alarm_count":
                len(alarms),

            "alarms":
                alarms,

            "gem_index":
                None,

            "gem_id":
                None,

            "alloc_id":
                None,

            "us_packets":
                None,

            "us_bytes":
                None,

            "ds_packets":
                None,

            "ds_bytes":
                None,

            "key_errors":
                None,

            "upload_bps":
                None,

            "download_bps":
                None,

            "bip_errors":
                self._safe_int(
                    fec.get(
                        "BIP errors"
                    )
                ),

            "total_fec_codewords":
                self._safe_int(
                    fec.get(
                        "Total FEC codewords"
                    )
                ),

            "corrected_fec_codewords":
                self._safe_int(
                    fec.get(
                        "Corrected FEC codewords"
                    )
                ),

            "uncorrected_fec_codewords":
                self._safe_int(
                    fec.get(
                        "Uncorrected FEC codewords"
                    )
                ),

            "corrected_fec_bytes":
                self._safe_int(
                    fec.get(
                        "Corrected FEC bytes"
                    )
                ),

            "fec_errored_seconds":
                self._safe_int(
                    fec.get(
                        "FEC errored seconds"
                    )
                ),

            "psbd_hec_corrected":
                self._safe_int(
                    gtc.get(
                        "PSBd HEC errors corrected"
                    )
                ),

            "psbd_hec_uncorrected":
                self._safe_int(
                    gtc.get(
                        "PSBd HEC errors uncorrected"
                    )
                ),

            "fs_hec_corrected":
                self._safe_int(
                    gtc.get(
                        "FS HEC errors corrected"
                    )
                ),

            "fs_hec_uncorrected":
                self._safe_int(
                    gtc.get(
                        "FS HEC errors uncorrected"
                    )
                ),

            "lost_words_hec":
                self._safe_int(
                    gtc.get(
                        "Lost words due to HEC errors"
                    )
                ),

            "ploam_mic_errors":
                self._safe_int(
                    gtc.get(
                        "PLOAM MIC errors"
                    )
                ),

            **system,
        }

        if selected_gem is not None:

            gem_counter = counters[
                selected_gem[
                    "gem_index"
                ]
            ]

            metrics.update(
                selected_gem
            )

            metrics.update(
                gem_counter
            )

        return metrics


    def _collect_static(
        self,
        client,
    ):

        command = r'''
echo __XONU_CAPABILITY__
pontop -b -g c

echo __XONU_OPTICAL_INFO__
pontop -b -g 'Optical Interface Info'
'''

        output = self._exec(
            client,
            command,
        )

        sections = self._split_sections(
            output
        )

        capability = (
            self._parse_key_values(
                sections.get(
                    "CAPABILITY",
                    "",
                )
            )
        )

        optical = (
            self._parse_key_values(
                sections.get(
                    "OPTICAL_INFO",
                    "",
                )
            )
        )

        return {
            "basic_modes":
                capability.get(
                    "Basic mode(s)"
                ),

            "omci_support":
                capability.get(
                    "OMCI support"
                ),

            "crypto_modes":
                capability.get(
                    "Crypto mode(s)"
                ),

            "gem_ports":
                self._safe_int(
                    capability.get(
                        "GEM Ports"
                    )
                ),

            "allocations":
                self._safe_int(
                    capability.get(
                        "Allocations"
                    )
                ),

            "vendor_name":
                optical.get(
                    "Vendor name"
                ),

            "part_number":
                optical.get(
                    "Part number"
                ),

            "revision":
                optical.get(
                    "Revision"
                ),

            "date_code":
                optical.get(
                    "Date code"
                ),

            "wavelength":
                optical.get(
                    "Wavelength"
                ),

            "dmi":
                optical.get(
                    "Digital monitoring implemented"
                ),

            "calibration":
                optical.get(
                    "Calibration"
                ),

            "rx_measurement_type":
                optical.get(
                    "Received power measurement type"
                ),

            "compliance":
                optical.get(
                    "Compliance"
                ),
        }


    def _apply_rates(
        self,
        metrics,
        now_epoch,
    ):

        if (
            metrics.get("us_bytes")
            is None
            or
            metrics.get("ds_bytes")
            is None
        ):
            self.previous_counter_sample = None
            return

        current = {
            "ts_epoch":
                now_epoch,

            "gem_id":
                metrics.get(
                    "gem_id"
                ),

            "us_bytes":
                metrics.get(
                    "us_bytes"
                ),

            "ds_bytes":
                metrics.get(
                    "ds_bytes"
                ),
        }

        previous = (
            self.previous_counter_sample
        )

        self.previous_counter_sample = (
            current
        )

        if (
            not previous
            or
            previous.get("gem_id")
            != current.get("gem_id")
        ):
            return

        elapsed = (
            current["ts_epoch"]
            -
            previous["ts_epoch"]
        )

        if elapsed <= 0:
            return

        us_delta = (
            current["us_bytes"]
            -
            previous["us_bytes"]
        )

        ds_delta = (
            current["ds_bytes"]
            -
            previous["ds_bytes"]
        )

        # A negative delta means the ONU
        # rebooted or the GEM counter reset.
        if us_delta >= 0:

            metrics["upload_bps"] = (
                us_delta
                * 8.0
                / elapsed
            )

        if ds_delta >= 0:

            metrics["download_bps"] = (
                ds_delta
                * 8.0
                / elapsed
            )


    def _save_sample(
        self,
        ts,
        metrics,
    ):

        row = dict(metrics)

        row["alarms_json"] = (
            json.dumps(
                row.pop(
                    "alarms",
                    [],
                ),
                separators=(",", ":"),
            )
        )

        columns = [
            "pon_state",
            "fec_upstream",
            "fec_downstream",
            "active_alarm_count",

            "gem_index",
            "gem_id",
            "alloc_id",

            "us_packets",
            "us_bytes",
            "ds_packets",
            "ds_bytes",

            "key_errors",

            "upload_bps",
            "download_bps",

            "bip_errors",
            "total_fec_codewords",
            "corrected_fec_codewords",
            "uncorrected_fec_codewords",
            "corrected_fec_bytes",
            "fec_errored_seconds",

            "psbd_hec_corrected",
            "psbd_hec_uncorrected",
            "fs_hec_corrected",
            "fs_hec_uncorrected",
            "lost_words_hec",
            "ploam_mic_errors",

            "ont_uptime_seconds",

            "load_1m",
            "load_5m",
            "load_15m",

            "memory_total_kb",
            "memory_used_kb",
            "memory_available_kb",

            "alarms_json",
        ]

        placeholders = ",".join(
            "?"
            for _ in range(
                len(columns) + 1
            )
        )

        with self._connect_db() as con:

            con.execute(
                f"""
                INSERT INTO advanced_samples
                (ts,{",".join(columns)})
                VALUES ({placeholders})
                """,
                [
                    ts,
                    *[
                        row.get(column)
                        for column
                        in columns
                    ],
                ],
            )


    def _cleanup(self):

        cutoff = (
            datetime.now(
                timezone.utc
            )
            -
            timedelta(
                days=self.retention_days
            )
        )

        with self._connect_db() as con:

            con.execute(
                """
                DELETE FROM advanced_samples
                WHERE ts < ?
                """,
                (
                    cutoff.isoformat(),
                ),
            )


    def collect_once(self):

        client = None

        try:

            client = (
                self._ssh_client()
            )

            metrics = (
                self._collect_dynamic(
                    client
                )
            )

            with self.lock:

                need_static = (
                    self.state[
                        "module_info"
                    ]
                    is None
                )

            module_info = (
                self._collect_static(
                    client
                )
                if need_static
                else None
            )

            now_epoch = time.time()

            ts = (
                datetime.fromtimestamp(
                    now_epoch,
                    timezone.utc,
                ).isoformat()
            )

            self._apply_rates(
                metrics,
                now_epoch,
            )

            self._save_sample(
                ts,
                metrics,
            )

            with self.lock:

                self.state[
                    "online"
                ] = True

                self.state[
                    "last_success"
                ] = ts

                self.state[
                    "last_error"
                ] = None

                self.state[
                    "metrics"
                ] = metrics

                if (
                    module_info
                    is not None
                ):

                    self.state[
                        "module_info"
                    ] = module_info

            try:
                self.alert_manager.process_sample(
                    ts,
                    metrics,
                )

            except Exception as alert_exc:
                print(
                    "Advanced alert processing failed: "
                    f"{type(alert_exc).__name__}: "
                    f"{alert_exc}"
                )

        except Exception as exc:

            with self.lock:

                self.state[
                    "online"
                ] = False

                self.state[
                    "last_error"
                ] = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

        finally:

            if client is not None:
                client.close()


    def _loop(self):

        while True:

            started = (
                time.monotonic()
            )

            self.collect_once()

            elapsed = (
                time.monotonic()
                -
                started
            )

            time.sleep(
                max(
                    1,
                    self.poll_seconds
                    -
                    elapsed,
                )
            )


    def start(self):

        if not self.enabled:
            return

        thread = threading.Thread(
            target=self._loop,
            name="ssh-collector",
            daemon=True,
        )

        thread.start()


    def snapshot(self):

        with self.lock:

            return {
                "enabled":
                    self.state[
                        "enabled"
                    ],

                "online":
                    self.state[
                        "online"
                    ],

                "last_success":
                    self.state[
                        "last_success"
                    ],

                "last_error":
                    self.state[
                        "last_error"
                    ],

                "metrics":
                    (
                        dict(
                            self.state[
                                "metrics"
                            ]
                        )
                        if
                        self.state[
                            "metrics"
                        ]
                        else None
                    ),

                "module_info":
                    (
                        dict(
                            self.state[
                                "module_info"
                            ]
                        )
                        if
                        self.state[
                            "module_info"
                        ]
                        else None
                    ),

                "host":
                    self.host,

                "port":
                    self.port,

                "user":
                    self.user,

                "poll_seconds":
                    self.poll_seconds,
            }


    def history(
        self,
        range_name="24h",
    ):

        delta = RANGES.get(
            range_name,
            RANGES["24h"],
        )

        cutoff = (
            datetime.now(
                timezone.utc
            )
            -
            delta
        ).isoformat()

        with self._connect_db() as con:

            rows = con.execute("""
                SELECT
                    ts,
                    gem_id,
                    upload_bps,
                    download_bps,
                    key_errors,
                    bip_errors,
                    corrected_fec_codewords,
                    uncorrected_fec_codewords,
                    fec_errored_seconds,
                    psbd_hec_uncorrected,
                    fs_hec_uncorrected,
                    ploam_mic_errors,
                    active_alarm_count,
                    ont_uptime_seconds,
                    load_1m,
                    load_5m,
                    load_15m,
                    memory_total_kb,
                    memory_used_kb,
                    memory_available_kb
                FROM advanced_samples
                WHERE ts >= ?
                ORDER BY ts ASC
            """, (
                cutoff,
            )).fetchall()

        max_points = 900

        step = max(
            1,
            len(rows)
            //
            max_points,
        )

        return [
            dict(row)
            for row
            in rows[::step]
        ]


    def stats(
        self,
        range_name="24h",
    ):

        delta = RANGES.get(
            range_name,
            RANGES["24h"],
        )

        cutoff = (
            datetime.now(
                timezone.utc
            )
            -
            delta
        ).isoformat()

        with self._connect_db() as con:

            first = con.execute("""
                SELECT *
                FROM advanced_samples
                WHERE ts >= ?
                ORDER BY ts ASC
                LIMIT 1
            """, (
                cutoff,
            )).fetchone()

            last = con.execute("""
                SELECT *
                FROM advanced_samples
                WHERE ts >= ?
                ORDER BY ts DESC
                LIMIT 1
            """, (
                cutoff,
            )).fetchone()

            aggregate = con.execute("""
                SELECT
                    COUNT(*) AS samples,

                    AVG(download_bps)
                        AS download_bps_avg,

                    MAX(download_bps)
                        AS download_bps_max,

                    AVG(upload_bps)
                        AS upload_bps_avg,

                    MAX(upload_bps)
                        AS upload_bps_max

                FROM advanced_samples
                WHERE ts >= ?
            """, (
                cutoff,
            )).fetchone()

        result = dict(
            aggregate
        )

        counter_fields = [
            "key_errors",
            "bip_errors",
            "corrected_fec_codewords",
            "uncorrected_fec_codewords",
            "fec_errored_seconds",
            "psbd_hec_corrected",
            "psbd_hec_uncorrected",
            "fs_hec_corrected",
            "fs_hec_uncorrected",
            "lost_words_hec",
            "ploam_mic_errors",
        ]

        for field in counter_fields:

            result[
                f"{field}_delta"
            ] = None

            if (
                first is not None
                and
                last is not None
            ):

                a = first[field]
                b = last[field]

                if (
                    a is not None
                    and
                    b is not None
                    and
                    b >= a
                ):

                    result[
                        f"{field}_delta"
                    ] = (
                        b - a
                    )

        return result
