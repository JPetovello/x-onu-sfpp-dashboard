import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import requests
import urllib3
from flask import Flask, jsonify, render_template, request

from advanced import AdvancedCollector
from retention import RetentionManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "metrics.db")
DATABASE_EXISTED_AT_STARTUP = os.path.exists(DB_PATH)

ONT_URL = os.environ.get(
    "ONT_URL",
    "https://192.168.11.1/cgi-bin/luci/8311/metrics",
)

POLL_SECONDS = max(2, int(os.environ.get("POLL_SECONDS", "10")))
RETENTION_DAYS = max(1, int(os.environ.get("RETENTION_DAYS", "30")))
REQUEST_TIMEOUT = max(1, int(os.environ.get("REQUEST_TIMEOUT", "5")))

app = Flask(__name__, template_folder="web_templates")

start_time = time.time()

state_lock = threading.Lock()

state = {
    "online": False,
    "last_success": None,
    "last_error": None,
    "metrics": None,
}

PLOAM_STATES = {
    11: "O1.1 - Initial / searching",
    12: "O1.2 - Downstream sync",
    23: "O2.3 - Serial number sent",
    30: "O3 - Serial number acknowledged",
    40: "O4 - Ranging",
    51: "O5.1 - Associated",
}

METRIC_COLUMNS = [
    "cpu1_tempC",
    "cpu2_tempC",
    "module_voltage",
    "optic_tempC",
    "ploam_state",
    "rx_power_dBm",
    "tx_bias_mA",
    "tx_power_dBm",
]



def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()



def db_connect():
    os.makedirs(DATA_DIR, exist_ok=True)

    con = sqlite3.connect(
        DB_PATH,
        timeout=10,
    )

    con.row_factory = sqlite3.Row

    return con



def init_db():
    with db_connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                cpu1_tempC REAL,
                cpu2_tempC REAL,
                module_voltage REAL,
                optic_tempC REAL,
                ploam_state INTEGER,
                rx_power_dBm REAL,
                tx_bias_mA REAL,
                tx_power_dBm REAL
            )
        """)

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_samples_ts
            ON samples(ts)
        """)



def normalize_metrics(payload):
    result = {}

    for key in METRIC_COLUMNS:
        value = payload.get(key)

        if value is None:
            result[key] = None

        elif key == "ploam_state":
            result[key] = int(value)

        else:
            result[key] = float(value)

    return result



def save_sample(metrics, ts):
    values = [
        metrics.get(k)
        for k in METRIC_COLUMNS
    ]

    placeholders = ",".join(
        ["?"] *
        (1 + len(METRIC_COLUMNS))
    )

    columns = ",".join(
        ["ts"] +
        METRIC_COLUMNS
    )

    with db_connect() as con:
        con.execute(
            f"""
            INSERT INTO samples
            ({columns})
            VALUES ({placeholders})
            """,
            [ts] + values,
        )



def cleanup_old_samples():
    retention_manager.cleanup()



def fetch_metrics():
    response = requests.get(
        ONT_URL,
        timeout=REQUEST_TIMEOUT,
        verify=False,
        headers={
            "User-Agent":
            "x-onu-dashboard/2.0"
        },
    )

    response.raise_for_status()

    return normalize_metrics(
        response.json()
    )



def collector_loop():
    cleanup_counter = 0

    while True:

        try:
            metrics = fetch_metrics()

        except Exception as exc:
            ts = utc_now_iso()

            error = (
                f"{type(exc).__name__}: {exc}"
            )

            with state_lock:
                state["online"] = False
                state["last_error"] = error

            try:
                advanced_collector.alert_manager.process_core_unreachable(
                    ts,
                    error,
                )

            except Exception as alert_exc:
                print(
                    "Core unreachable alert processing failed: "
                    f"{type(alert_exc).__name__}: "
                    f"{alert_exc}"
                )

        else:
            ts = utc_now_iso()

            with state_lock:
                state["online"] = True
                state["last_success"] = ts
                state["last_error"] = None
                state["metrics"] = metrics

            try:
                save_sample(
                    metrics,
                    ts,
                )

                advanced_collector.alert_manager.process_core_sample(
                    ts,
                    metrics,
                )

            except Exception as exc:
                print(
                    "Core sample processing failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        cleanup_counter += 1

        if cleanup_counter >= max(
            1,
            int(3600 / POLL_SECONDS)
        ):
            try:
                cleanup_old_samples()
            except Exception:
                pass

            cleanup_counter = 0

        time.sleep(POLL_SECONDS)



def start_collector():

    thread = threading.Thread(
        target=collector_loop,
        name="collector",
        daemon=True,
    )

    thread.start()



@app.route("/")
def index():
    return render_template(
        "index.html",
        poll_seconds=POLL_SECONDS,
    )



@app.route("/alerts-settings")
def alerts_settings():
    return render_template(
        "alerts_settings.html",
    )


@app.route("/api/current")
def api_current():

    with state_lock:
        snapshot = dict(state)

    metrics = snapshot.get(
        "metrics"
    )

    if (
        metrics
        and
        metrics.get("ploam_state")
        is not None
    ):
        code = metrics[
            "ploam_state"
        ]

        snapshot["ploam_label"] = (
            PLOAM_STATES.get(
                code,
                f"State {code}"
            )
        )

    else:
        snapshot["ploam_label"] = None

    snapshot["dashboard_uptime_seconds"] = int(
        time.time() - start_time
    )

    return jsonify(snapshot)



RANGES = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}



@app.route("/api/history")
def api_history():

    range_name = request.args.get(
        "range",
        "24h",
    )

    delta = RANGES.get(
        range_name,
        RANGES["24h"],
    )

    cutoff = (
        datetime.now(timezone.utc)
        - delta
    ).isoformat()

    with db_connect() as con:

        rows = con.execute("""
            SELECT
                ts,
                cpu1_tempC,
                cpu2_tempC,
                module_voltage,
                optic_tempC,
                ploam_state,
                rx_power_dBm,
                tx_bias_mA,
                tx_power_dBm
            FROM samples
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (cutoff,)).fetchall()

    max_points = 900

    step = max(
        1,
        len(rows) // max_points
    )

    return jsonify(
        [
            dict(r)
            for r in rows[::step]
        ]
    )



@app.route("/api/stats")
def api_stats():

    range_name = request.args.get(
        "range",
        "24h",
    )

    delta = RANGES.get(
        range_name,
        RANGES["24h"],
    )

    cutoff = (
        datetime.now(timezone.utc)
        - delta
    ).isoformat()

    with db_connect() as con:

        row = con.execute("""
            SELECT

                COUNT(*) AS samples,

                MIN(ts) AS first_sample,
                MAX(ts) AS last_sample,

                MIN(rx_power_dBm) AS rx_min,
                AVG(rx_power_dBm) AS rx_avg,
                MAX(rx_power_dBm) AS rx_max,

                MIN(tx_power_dBm) AS tx_min,
                AVG(tx_power_dBm) AS tx_avg,
                MAX(tx_power_dBm) AS tx_max,

                MIN(optic_tempC) AS optic_min,
                AVG(optic_tempC) AS optic_avg,
                MAX(optic_tempC) AS optic_max,

                MIN(cpu1_tempC) AS cpu1_min,
                AVG(cpu1_tempC) AS cpu1_avg,
                MAX(cpu1_tempC) AS cpu1_max,

                MIN(cpu2_tempC) AS cpu2_min,
                AVG(cpu2_tempC) AS cpu2_avg,
                MAX(cpu2_tempC) AS cpu2_max,

                MIN(module_voltage) AS voltage_min,
                AVG(module_voltage) AS voltage_avg,
                MAX(module_voltage) AS voltage_max,

                MIN(tx_bias_mA) AS bias_min,
                AVG(tx_bias_mA) AS bias_avg,
                MAX(tx_bias_mA) AS bias_max

            FROM samples
            WHERE ts >= ?
        """, (cutoff,)).fetchone()

    return jsonify(
        dict(row)
    )



@app.route("/api/info")
def api_info():

    with db_connect() as con:

        row = con.execute("""
            SELECT
                COUNT(*) AS total_samples,
                MIN(ts) AS first_sample,
                MAX(ts) AS last_sample
            FROM samples
        """).fetchone()

    return jsonify({
        "ont_url": ONT_URL,
        "poll_seconds": POLL_SECONDS,
        "retention_days": retention_manager.get_config()[
            "telemetry_days"
        ],
        "database": DB_PATH,
        **dict(row),
    })



@app.route("/api/advanced/current")
def api_advanced_current():

    return jsonify(
        advanced_collector.snapshot()
    )



@app.route("/api/advanced/history")
def api_advanced_history():

    range_name = request.args.get(
        "range",
        "24h",
    )

    return jsonify(
        advanced_collector.history(
            range_name
        )
    )



@app.route("/api/advanced/stats")
def api_advanced_stats():

    range_name = request.args.get(
        "range",
        "24h",
    )

    return jsonify(
        advanced_collector.stats(
            range_name
        )
    )



@app.route("/api/alerts")
def api_alerts():

    limit = request.args.get(
        "limit",
        default=100,
        type=int,
    )

    return jsonify(
        advanced_collector.alert_manager.recent_events(
            limit
        )
    )



@app.route(
    "/api/alert-config",
    methods=["GET", "PUT"],
)
def api_alert_config():

    manager = (
        advanced_collector.alert_manager
    )

    if request.method == "GET":
        return jsonify(
            manager.get_config()
        )

    config = request.get_json(
        silent=True
    )

    if config is None:
        return jsonify(
            {
                "error": (
                    "Request body must contain "
                    "a JSON object"
                )
            }
        ), 400

    try:
        saved_config = manager.save_config(
            config
        )

    except ValueError as exc:
        return jsonify(
            {
                "error": str(exc)
            }
        ), 400

    return jsonify(
        saved_config
    )


@app.route(
    "/api/notification-config",
    methods=["GET", "PUT"],
)
def api_notification_config():

    manager = (
        advanced_collector
        .alert_manager
        .notification_manager
    )

    if request.method == "GET":
        return jsonify(
            manager.get_config()
        )

    config = request.get_json(
        silent=True
    )

    if config is None:
        return jsonify(
            {
                "error": (
                    "Request body must contain "
                    "a JSON object"
                )
            }
        ), 400

    try:
        saved_config = manager.save_config(
            config
        )

    except ValueError as exc:
        return jsonify(
            {
                "error": str(exc)
            }
        ), 400

    return jsonify(
        saved_config
    )



@app.route(
    "/api/retention-config",
    methods=["GET", "PUT"],
)
def api_retention_config():
    if request.method == "GET":
        return jsonify(
            retention_manager.get_config()
        )

    config = request.get_json(
        silent=True
    )

    if config is None:
        return jsonify(
            {
                "error": (
                    "Request body must contain "
                    "a JSON object"
                )
            }
        ), 400

    try:
        saved_config = retention_manager.save_config(
            config
        )
    except ValueError as exc:
        return jsonify(
            {
                "error": str(exc)
            }
        ), 400

    return jsonify(
        saved_config
    )


init_db()

retention_manager = RetentionManager(
    DB_PATH,
    legacy_telemetry_days=RETENTION_DAYS,
    new_install=not DATABASE_EXISTED_AT_STARTUP,
)

advanced_collector = AdvancedCollector(
    DB_PATH,
    RETENTION_DAYS,
)

start_collector()
advanced_collector.start()
