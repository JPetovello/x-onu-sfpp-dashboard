const HISTORY_RANGE_STORAGE_KEY = "x-onu-dashboard-history-range";
const VALID_HISTORY_RANGES = new Set(["1h", "6h", "24h", "7d", "30d"]);

let selectedRange = localStorage.getItem(HISTORY_RANGE_STORAGE_KEY) || "24h";

if (!VALID_HISTORY_RANGES.has(selectedRange)) {
    selectedRange = "24h";
}

let latestCore = null;
let latestAdvanced = null;
let latestAdvancedStats = null;
let alertConfig = null;

let coreHistory = [];
let advancedHistory = [];


function byId(id) {
    return document.getElementById(id);
}


function setText(
    id,
    value
) {
    const element =
        byId(id);

    if (element) {
        element.textContent =
            value;
    }
}


function setClass(
    id,
    className
) {
    const element =
        byId(id);

    if (element) {
        element.className =
            className;
    }
}


function fmt(
    value,
    digits = 2
) {
    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
            Number(value)
        )
    ) {
        return "-";
    }

    return Number(
        value
    ).toFixed(
        digits
    );
}


function fmtInteger(
    value
) {
    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
            Number(value)
        )
    ) {
        return "-";
    }

    return Math.round(
        Number(value)
    ).toLocaleString();
}


function fmtRate(
    bitsPerSecond
) {
    const value =
        Number(
            bitsPerSecond
        );

    if (
        !Number.isFinite(
            value
        )
    ) {
        return "-";
    }

    if (
        value >=
        1000000000
    ) {
        return (
            value /
            1000000000
        ).toFixed(2) +
        " Gbps";
    }

    if (
        value >=
        1000000
    ) {
        return (
            value /
            1000000
        ).toFixed(2) +
        " Mbps";
    }

    if (
        value >=
        1000
    ) {
        return (
            value /
            1000
        ).toFixed(1) +
        " Kbps";
    }

    return value.toFixed(0) +
        " bps";
}


function fmtBytes(
    bytes
) {
    const value =
        Number(bytes);

    if (
        !Number.isFinite(
            value
        )
    ) {
        return "-";
    }

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
        "PB"
    ];

    let result =
        value;

    let index = 0;

    while (
        result >= 1000 &&
        index <
        units.length - 1
    ) {
        result /= 1000;
        index += 1;
    }

    const digits =
        index <= 1
            ? 0
            : 2;

    return result.toFixed(
        digits
    ) +
    " " +
    units[index];
}


function formatDuration(
    seconds
) {
    const value =
        Number(seconds);

    if (
        !Number.isFinite(
            value
        )
    ) {
        return "-";
    }

    const days =
        Math.floor(
            value /
            86400
        );

    const hours =
        Math.floor(
            (
                value %
                86400
            ) /
            3600
        );

    const minutes =
        Math.floor(
            (
                value %
                3600
            ) /
            60
        );

    if (
        days > 0
    ) {
        return `${days}d ${hours}h ${minutes}m`;
    }

    if (
        hours > 0
    ) {
        return `${hours}h ${minutes}m`;
    }

    return `${minutes}m`;
}


function rangeLabel() {
    const labels = {
        "1h": "1h",
        "6h": "6h",
        "24h": "24h",
        "7d": "7d",
        "30d": "30d"
    };

    return labels[
        selectedRange
    ] || selectedRange;
}


function setHealthBadge(
    id,
    text,
    level
) {
    const element =
        byId(id);

    if (!element) {
        return;
    }

    element.textContent =
        text;

    element.className =
        "health-badge " +
        level;
}


function rxStatus(
    value
) {
    value =
        Number(value);

    const thresholds =
        alertConfig &&
        alertConfig.quality &&
        alertConfig.quality.rx_power;

    if (
        !Number.isFinite(
            value
        ) ||
        !thresholds
    ) {
        return [
            "UNKNOWN",
            "unknown"
        ];
    }

    if (
        value <= thresholds.poor_low ||
        value > thresholds.poor_high
    ) {
        return [
            "POOR",
            "bad"
        ];
    }

    if (
        value < thresholds.fair_low
    ) {
        return [
            "FAIR",
            "warn"
        ];
    }

    if (
        value >= thresholds.great_low &&
        value <= thresholds.great_high
    ) {
        return [
            "GREAT",
            "good"
        ];
    }

    return [
        "GOOD",
        "good"
    ];
}


function txStatus(
    value
) {
    const thresholds =
        alertConfig &&
        alertConfig.quality &&
        alertConfig.quality.tx_power;

    return classifyTxPower(
        value,
        thresholds
    );
}


function thermalStatus(
    optic,
    cpu1,
    cpu2
) {
    const values = [
        Number(optic),
        Number(cpu1),
        Number(cpu2)
    ].filter(
        Number.isFinite
    );

    const thresholds =
        alertConfig &&
        alertConfig.quality &&
        alertConfig.quality.thermal;

    if (
        !values.length ||
        !thresholds
    ) {
        return [
            "UNKNOWN",
            "unknown"
        ];
    }

    const maximum =
        Math.max(
            ...values
        );

    if (
        maximum >= thresholds.hot
    ) {
        return [
            "HOT",
            "bad"
        ];
    }

    if (
        maximum >= thresholds.warm
    ) {
        return [
            "WARM",
            "warn"
        ];
    }

    return [
        "NORMAL",
        "good"
    ];
}


function cleanPipeList(
    value
) {
    if (!value) {
        return "-";
    }

    return String(value)
        .split("|")
        .map(
            item =>
                item.trim()
        )
        .filter(Boolean)
        .join(" / ");
}


function updateCoreDisplay(
    data
) {
    latestCore =
        data;

    const online =
        Boolean(
            data.online
        );

    setClass(
        "statusDot",
        "status-dot " +
        (
            online
                ? "online"
                : "offline"
        )
    );

    setText(
        "statusText",
        online
            ? "ONT ONLINE"
            : "ONT UNREACHABLE"
    );

    setHealthBadge(
        "summaryOnline",
        online
            ? "ONLINE"
            : "OFFLINE",
        online
            ? "good"
            : "bad"
    );


    if (
        data.last_success
    ) {
        setText(
            "lastUpdate",
            "Last sample " +
            new Date(
                data.last_success
            ).toLocaleString()
        );
    } else if (
        data.last_error
    ) {
        setText(
            "lastUpdate",
            data.last_error
        );
    }


    setText(
        "dashboardUptime",
        formatDuration(
            data.dashboard_uptime_seconds
        )
    );


    const metrics =
        data.metrics;

    if (!metrics) {
        updateOverallHealth();
        return;
    }


    setText(
        "rxPower",
        fmt(
            metrics.rx_power_dBm
        )
    );

    setText(
        "txPower",
        fmt(
            metrics.tx_power_dBm
        )
    );

    setText(
        "txBias",
        fmt(
            metrics.tx_bias_mA
        )
    );

    setText(
        "voltage",
        fmt(
            metrics.module_voltage
        )
    );

    setText(
        "opticTemp",
        fmt(
            metrics.optic_tempC,
            1
        )
    );

    setText(
        "cpu1Temp",
        fmt(
            metrics.cpu1_tempC,
            1
        )
    );

    setText(
        "cpu2Temp",
        fmt(
            metrics.cpu2_tempC,
            1
        )
    );


    const [
        rxText,
        rxLevel
    ] =
        rxStatus(
            metrics.rx_power_dBm
        );

    setHealthBadge(
        "rxHealth",
        rxText,
        rxLevel
    );


    const [
        txText,
        txLevel
    ] =
        txStatus(
            metrics.tx_power_dBm
        );

    setHealthBadge(
        "txHealth",
        txText,
        txLevel
    );


    const ploam =
        Number(
            metrics.ploam_state
        );

    if (
        ploam === 51
    ) {
        setHealthBadge(
            "summaryPon",
            "O5.1 ASSOCIATED",
            "good"
        );
    } else {
        setHealthBadge(
            "summaryPon",
            data.ploam_label ||
            `STATE ${ploam}`,
            "bad"
        );
    }


    updateOverallHealth();
}


function updateAdvancedDisplay(
    data
) {
    latestAdvanced =
        data;

    if (
        !data ||
        !data.enabled
    ) {
        const status =
            byId(
                "advancedStatus"
            );

        status.textContent =
            "Advanced telemetry disabled";

        status.className =
            "advanced-status";

        clearAdvancedDisplay();

        updateOverallHealth();

        return;
    }


    const status =
        byId(
            "advancedStatus"
        );


    if (
        !data.online
    ) {
        status.textContent =
            "Advanced telemetry unavailable";

        status.className =
            "advanced-status bad";

        clearAdvancedDisplay();

        updateOverallHealth();

        return;
    }


    status.textContent =
        `SSH telemetry online · ${data.poll_seconds}s poll`;

    status.className =
        "advanced-status good";


    const m =
        data.metrics ||
        {};


    setText(
        "downloadRate",
        fmtRate(
            m.download_bps
        )
    );

    setText(
        "uploadRate",
        fmtRate(
            m.upload_bps
        )
    );

    setText(
        "downloadTotal",
        fmtBytes(
            m.ds_bytes
        )
    );

    setText(
        "uploadTotal",
        fmtBytes(
            m.us_bytes
        )
    );


    setText(
        "ontUptime",
        formatDuration(
            m.ont_uptime_seconds
        )
    );


    const totalMemory =
        Number(
            m.memory_total_kb
        );

    const usedMemory =
        Number(
            m.memory_used_kb
        );

    if (
        Number.isFinite(
            totalMemory
        ) &&
        Number.isFinite(
            usedMemory
        ) &&
        totalMemory > 0
    ) {
        const percent =
            (
                usedMemory /
                totalMemory
            ) *
            100;

        setText(
            "memoryUsage",
            `${percent.toFixed(1)}% used`
        );

        setText(
            "memoryDetail",
            `${fmtBytes(
                usedMemory * 1024
            )} / ${fmtBytes(
                totalMemory * 1024
            )}`
        );
    } else {
        setText(
            "memoryUsage",
            "-"
        );

        setText(
            "memoryDetail",
            "-"
        );
    }


    setText(
        "loadAverage",
        [
            fmt(
                m.load_1m,
                2
            ),
            fmt(
                m.load_5m,
                2
            ),
            fmt(
                m.load_15m,
                2
            )
        ].join(" / ")
    );


    setText(
        "fecUpstream",
        m.fec_upstream ||
        "-"
    );

    setText(
        "fecDownstream",
        m.fec_downstream ||
        "-"
    );


    setText(
        "technicalGem",
        m.gem_id ??
        "-"
    );

    setText(
        "technicalAlloc",
        m.alloc_id ??
        "-"
    );


    const info =
        data.module_info ||
        {};


    setText(
        "infoPart",
        info.part_number ||
        "-"
    );

    setText(
        "infoRevision",
        info.revision ||
        "-"
    );

    setText(
        "infoWavelength",
        info.wavelength ||
        "-"
    );

    setText(
        "infoVendor",
        info.vendor_name ||
        "-"
    );

    setText(
        "infoDmi",
        info.dmi ||
        "-"
    );

    setText(
        "infoCalibration",
        info.calibration ||
        "-"
    );

    setText(
        "infoRxType",
        info.rx_measurement_type ||
        "-"
    );

    setText(
        "infoCompliance",
        info.compliance ||
        "-"
    );

    setText(
        "infoModes",
        cleanPipeList(
            info.basic_modes
        )
    );

    setText(
        "infoOmci",
        info.omci_support ||
        "-"
    );

    setText(
        "infoGemPorts",
        info.gem_ports ??
        "-"
    );

    setText(
        "infoAllocations",
        info.allocations ??
        "-"
    );


    updateHealthCounters();

    updateOverallHealth();
}


function clearAdvancedDisplay() {
    const ids = [
        "downloadRate",
        "uploadRate",
        "downloadTotal",
        "uploadTotal",
        "ontUptime",
        "memoryUsage",
        "memoryDetail",
        "loadAverage",
        "fecUpstream",
        "fecDownstream",
        "bipErrors",
        "correctedFec",
        "uncorrectedFec",
        "hecErrors",
        "micErrors",
        "activeAlarms",
        "keyErrors",
        "technicalGem",
        "technicalAlloc",
        "infoPart",
        "infoRevision",
        "infoWavelength",
        "infoVendor",
        "infoDmi",
        "infoCalibration",
        "infoRxType",
        "infoCompliance",
        "infoModes",
        "infoOmci",
        "infoGemPorts",
        "infoAllocations"
    ];

    for (
        const id
        of ids
    ) {
        setText(
            id,
            "-"
        );
    }
}


function updateAdvancedStats(
    data
) {
    latestAdvancedStats =
        data;

    updateHealthCounters();

    updateOverallHealth();
}


function updateHealthCounters() {
    if (
        !latestAdvanced ||
        !latestAdvanced.enabled ||
        !latestAdvanced.online ||
        !latestAdvanced.metrics
    ) {
        return;
    }

    const m =
        latestAdvanced.metrics;

    const s =
        latestAdvancedStats ||
        {};


    const bipDelta =
        Number(
            s.bip_errors_delta ||
            0
        );

    setText(
        "bipErrors",
        `${fmtInteger(
            m.bip_errors
        )} total · +${fmtInteger(
            bipDelta
        )} (${rangeLabel()})`
    );


    const correctedDelta =
        Number(
            s.corrected_fec_codewords_delta ||
            0
        );

    setText(
        "correctedFec",
        `${fmtInteger(
            m.corrected_fec_codewords
        )} total · +${fmtInteger(
            correctedDelta
        )}`
    );


    const uncorrectedDelta =
        Number(
            s.uncorrected_fec_codewords_delta ||
            0
        );

    setText(
        "uncorrectedFec",
        `${fmtInteger(
            m.uncorrected_fec_codewords
        )} total · +${fmtInteger(
            uncorrectedDelta
        )}`
    );


    const correctedHecDelta =
        Number(
            s.psbd_hec_corrected_delta ||
            0
        ) +
        Number(
            s.fs_hec_corrected_delta ||
            0
        );

    const uncorrectedHecDelta =
        Number(
            s.psbd_hec_uncorrected_delta ||
            0
        ) +
        Number(
            s.fs_hec_uncorrected_delta ||
            0
        );


    const currentCorrectedHec =
        Number(
            m.psbd_hec_corrected ||
            0
        ) +
        Number(
            m.fs_hec_corrected ||
            0
        );

    const currentUncorrectedHec =
        Number(
            m.psbd_hec_uncorrected ||
            0
        ) +
        Number(
            m.fs_hec_uncorrected ||
            0
        );


    setText(
        "hecErrors",
        `${fmtInteger(
            currentUncorrectedHec
        )} uncorrected · ${fmtInteger(
            currentCorrectedHec
        )} corrected · +${fmtInteger(
            uncorrectedHecDelta +
            correctedHecDelta
        )}`
    );


    const micDelta =
        Number(
            s.ploam_mic_errors_delta ||
            0
        );

    setText(
        "micErrors",
        `${fmtInteger(
            m.ploam_mic_errors
        )} total · +${fmtInteger(
            micDelta
        )}`
    );


    const alarms =
        Number(
            m.active_alarm_count
        );

    if (
        Number.isFinite(
            alarms
        )
    ) {
        setText(
            "activeAlarms",
            alarms === 0
                ? "None"
                : fmtInteger(
                    alarms
                )
        );
    } else {
        setText(
            "activeAlarms",
            "-"
        );
    }


    const keyDelta =
        Number(
            s.key_errors_delta ||
            0
        );

    setText(
        "keyErrors",
        `${fmtInteger(
            m.key_errors
        )} total · +${fmtInteger(
            keyDelta
        )} (${rangeLabel()})`
    );
}


function overallHealthState() {
    if (
        !latestCore ||
        !latestCore.online
    ) {
        return [
            "UNREACHABLE",
            "bad"
        ];
    }


    const coreMetrics =
        latestCore.metrics ||
        {};


    if (
        Number(
            coreMetrics.ploam_state
        ) !== 51
    ) {
        return [
            "NOT OPERATIONAL",
            "bad"
        ];
    }


    const [
        rxText,
        rxLevel
    ] =
        rxStatus(
            coreMetrics.rx_power_dBm
        );


    const [
        txText,
        txLevel
    ] =
        txStatus(
            coreMetrics.tx_power_dBm
        );


    const [
        thermalText,
        thermalLevel
    ] =
        thermalStatus(
            coreMetrics.optic_tempC,
            coreMetrics.cpu1_tempC,
            coreMetrics.cpu2_tempC
        );


    if (
        rxLevel === "bad" ||
        txLevel === "bad" ||
        thermalLevel === "bad"
    ) {
        return [
            "ATTENTION",
            "bad"
        ];
    }


    if (
        rxLevel === "warn" ||
        txLevel === "warn" ||
        thermalLevel === "warn"
    ) {
        return [
            "ATTENTION",
            "warn"
        ];
    }


    if (
        latestAdvanced &&
        latestAdvanced.enabled &&
        latestAdvanced.online &&
        latestAdvanced.metrics
    ) {
        const m =
            latestAdvanced.metrics;

        const s =
            latestAdvancedStats ||
            {};


        const seriousDelta =
            Number(
                s.uncorrected_fec_codewords_delta ||
                0
            ) +
            Number(
                s.psbd_hec_uncorrected_delta ||
                0
            ) +
            Number(
                s.fs_hec_uncorrected_delta ||
                0
            ) +
            Number(
                s.ploam_mic_errors_delta ||
                0
            );


        if (
            Number(
                m.active_alarm_count ||
                0
            ) > 0 ||
            seriousDelta > 0
        ) {
            return [
                "ATTENTION",
                "warn"
            ];
        }
    }


    return [
        "HEALTHY",
        "good"
    ];
}

function updateOverallHealth() {
    const [
        text,
        level
    ] =
        overallHealthState();

    setHealthBadge(
        "summaryHealth",
        text,
        level
    );


    const coreText =
        latestCore &&
        latestCore.online
            ? "Core telemetry online"
            : "Core telemetry unavailable";


    let advancedText =
        "Advanced telemetry disabled";


    if (
        latestAdvanced &&
        latestAdvanced.enabled
    ) {
        advancedText =
            latestAdvanced.online
                ? "Advanced telemetry online"
                : "Advanced telemetry unavailable";
    }


    setText(
        "footerStatus",
        `${coreText} · ${advancedText}`
    );
}


async function loadAlertConfig() {
    try {
        const response =
            await fetch(
                "/api/alert-config"
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        alertConfig =
            await response.json();
    } catch (error) {
        console.error(
            "Unable to load alert configuration:",
            error
        );
    }
}


async function loadCurrent() {
    try {
        const response =
            await fetch(
                "/api/current",
                {
                    cache:
                        "no-store"
                }
            );

        if (
            !response.ok
        ) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        updateCoreDisplay(
            await response.json()
        );
    } catch (
        error
    ) {
        setClass(
            "statusDot",
            "status-dot offline"
        );

        setText(
            "statusText",
            "DASHBOARD ERROR"
        );

        setText(
            "lastUpdate",
            error.message
        );
    }
}


async function loadAdvancedCurrent() {
    try {
        const response =
            await fetch(
                "/api/advanced/current",
                {
                    cache:
                        "no-store"
                }
            );

        if (
            !response.ok
        ) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        updateAdvancedDisplay(
            await response.json()
        );
    } catch (
        error
    ) {
        latestAdvanced = {
            enabled: false,
            online: false
        };

        const status =
            byId(
                "advancedStatus"
            );

        status.textContent =
            "Advanced telemetry unavailable";

        status.className =
            "advanced-status bad";

        clearAdvancedDisplay();

        updateOverallHealth();
    }
}


async function loadHistory() {
    const coreUrl =
        `/api/history?range=${encodeURIComponent(
            selectedRange
        )}`;

    const advancedUrl =
        `/api/advanced/history?range=${encodeURIComponent(
            selectedRange
        )}`;

    try {
        const response =
            await fetch(
                coreUrl,
                {
                    cache:
                        "no-store"
                }
            );

        if (
            response.ok
        ) {
            coreHistory =
                await response.json();
        }
    } catch (
        error
    ) {
        console.error(
            "Core history:",
            error
        );
    }


    try {
        const response =
            await fetch(
                advancedUrl,
                {
                    cache:
                        "no-store"
                }
            );

        if (
            response.ok
        ) {
            advancedHistory =
                await response.json();
        } else {
            advancedHistory =
                [];
        }
    } catch (
        error
    ) {
        advancedHistory =
            [];
    }


    setText(
        "powerSamples",
        `${coreHistory.length.toLocaleString()} plotted samples`
    );

    setText(
        "tempSamples",
        `${coreHistory.length.toLocaleString()} plotted samples`
    );

    setText(
        "trafficSamples",
        `${advancedHistory.length.toLocaleString()} plotted samples`
    );


    drawAllCharts();
}


async function loadAdvancedStats() {
    try {
        const response =
            await fetch(
                `/api/advanced/stats?range=${encodeURIComponent(
                    selectedRange
                )}`,
                {
                    cache:
                        "no-store"
                }
            );

        if (
            !response.ok
        ) {
            return;
        }

        updateAdvancedStats(
            await response.json()
        );
    } catch (
        error
    ) {
        latestAdvancedStats =
            null;
    }
}


function cssColor(
    variable
) {
    return getComputedStyle(
        document.documentElement
    ).getPropertyValue(
        variable
    ).trim();
}


function drawChart(
    canvasId,
    rows,
    series,
    valueFormatter,
    options = {}
) {
    const canvas =
        byId(
            canvasId
        );

    if (!canvas) {
        return;
    }


    const rect =
        canvas.getBoundingClientRect();

    const dpr =
        window.devicePixelRatio ||
        1;


    const cssWidth =
        Math.max(
            320,
            rect.width
        );

    const cssHeight =
        options.height ||
        280;


    canvas.width =
        Math.round(
            cssWidth *
            dpr
        );

    canvas.height =
        Math.round(
            cssHeight *
            dpr
        );


    const ctx =
        canvas.getContext(
            "2d"
        );


    ctx.setTransform(
        dpr,
        0,
        0,
        dpr,
        0,
        0
    );


    ctx.clearRect(
        0,
        0,
        cssWidth,
        cssHeight
    );


    const padding = {
        left: 60,
        right: 16,
        top: 18,
        bottom: 34
    };


    const values =
        [];


    for (
        const row
        of rows
    ) {
        for (
            const item
            of series
        ) {
            const value =
                Number(
                    row[
                        item.key
                    ]
                );

            if (
                Number.isFinite(
                    value
                )
            ) {
                values.push(
                    value
                );
            }
        }
    }


    if (
        !rows.length ||
        !values.length
    ) {
        ctx.fillStyle =
            cssColor(
                "--muted"
            );

        ctx.font =
            "13px system-ui";

        ctx.fillText(
            "Waiting for history samples...",
            padding.left,
            44
        );

        return;
    }


    let minimum =
        Math.min(
            ...values
        );

    let maximum =
        Math.max(
            ...values
        );


    let spread =
        maximum -
        minimum;


    if (
        spread === 0
    ) {
        spread =
            Math.max(
                Math.abs(
                    maximum
                ) *
                .1,
                1
            );
    }


    minimum -=
        spread *
        .15;

    maximum +=
        spread *
        .15;


    if (
        Number.isFinite(
            Number(
                options.minValue
            )
        )
    ) {
        minimum =
            Number(
                options.minValue
            );
    }


    if (
        Number.isFinite(
            Number(
                options.maxValue
            )
        )
    ) {
        maximum =
            Number(
                options.maxValue
            );
    }


    if (
        maximum <= minimum
    ) {
        maximum =
            minimum + 1;
    }


    const plotWidth =
        cssWidth -
        padding.left -
        padding.right;

    const plotHeight =
        cssHeight -
        padding.top -
        padding.bottom;


    const xFor =
        index =>
            padding.left +
            (
                index /
                Math.max(
                    1,
                    rows.length -
                    1
                )
            ) *
            plotWidth;


    const yFor =
        value =>
            padding.top +
            (
                1 -
                (
                    value -
                    minimum
                ) /
                (
                    maximum -
                    minimum
                )
            ) *
            plotHeight;


    ctx.strokeStyle =
        cssColor(
            "--line"
        );

    ctx.lineWidth =
        1;


    ctx.fillStyle =
        cssColor(
            "--muted"
        );

    ctx.font =
        "10px system-ui";


    const gridLines =
        5;


    for (
        let i = 0;
        i <= gridLines;
        i += 1
    ) {
        const ratio =
            i /
            gridLines;

        const y =
            padding.top +
            ratio *
            plotHeight;


        ctx.beginPath();

        ctx.moveTo(
            padding.left,
            y
        );

        ctx.lineTo(
            cssWidth -
            padding.right,
            y
        );

        ctx.stroke();


        const value =
            maximum -
            ratio *
            (
                maximum -
                minimum
            );


        ctx.fillText(
            valueFormatter(
                value
            ),
            5,
            y + 3
        );
    }


    const timeIndexes = [
        0,
        Math.floor(
            (
                rows.length -
                1
            ) /
            2
        ),
        rows.length -
        1
    ];


    for (
        const index
        of timeIndexes
    ) {
        if (
            index < 0 ||
            !rows[index]
        ) {
            continue;
        }


        const date =
            new Date(
                rows[index].ts
            );


        const label =
            selectedRange === "7d" ||
            selectedRange === "30d"
                ? date.toLocaleDateString(
                    [],
                    {
                        month:
                            "short",
                        day:
                            "numeric"
                    }
                )
                : date.toLocaleTimeString(
                    [],
                    {
                        hour:
                            "2-digit",
                        minute:
                            "2-digit"
                    }
                );


        const x =
            xFor(
                index
            );


        ctx.fillText(
            label,
            Math.max(
                padding.left,
                Math.min(
                    x - 22,
                    cssWidth -
                    padding.right -
                    45
                )
            ),
            cssHeight -
            8
        );
    }


    for (
        const item
        of series
    ) {
        ctx.strokeStyle =
            cssColor(
                item.color
            );

        ctx.lineWidth =
            2;

        ctx.lineJoin =
            "round";

        ctx.lineCap =
            "round";


        let started =
            false;


        ctx.beginPath();


        for (
            let i = 0;
            i < rows.length;
            i += 1
        ) {
            const value =
                Number(
                    rows[i][
                        item.key
                    ]
                );


            if (
                !Number.isFinite(
                    value
                )
            ) {
                started =
                    false;

                continue;
            }


            const x =
                xFor(i);

            const y =
                yFor(value);


            if (
                !started
            ) {
                ctx.moveTo(
                    x,
                    y
                );

                started =
                    true;
            } else {
                ctx.lineTo(
                    x,
                    y
                );
            }
        }


        ctx.stroke();
    }
}


function drawAllCharts() {
    drawChart(
        "rxPowerChart",
        coreHistory,
        [
            {
                key:
                    "rx_power_dBm",
                color:
                    "--rx"
            }
        ],
        value =>
            `${value.toFixed(1)} dBm`,
        {
            height: 190
        }
    );


    drawChart(
        "txPowerChart",
        coreHistory,
        [
            {
                key:
                    "tx_power_dBm",
                color:
                    "--tx"
            }
        ],
        value =>
            `${value.toFixed(1)} dBm`,
        {
            height: 190
        }
    );


    const latestHistoryPoint =
        coreHistory.length
            ? coreHistory[
                coreHistory.length - 1
            ]
            : null;


    setText(
        "rxHistoryCurrent",
        latestHistoryPoint
            ? `${fmt(
                latestHistoryPoint.rx_power_dBm
            )} dBm`
            : "-"
    );


    setText(
        "txHistoryCurrent",
        latestHistoryPoint
            ? `${fmt(
                latestHistoryPoint.tx_power_dBm
            )} dBm`
            : "-"
    );


    drawChart(
        "tempChart",
        coreHistory,
        [
            {
                key:
                    "optic_tempC",
                color:
                    "--optic"
            },
            {
                key:
                    "cpu1_tempC",
                color:
                    "--cpu1"
            },
            {
                key:
                    "cpu2_tempC",
                color:
                    "--cpu2"
            }
        ],
        value =>
            `${value.toFixed(0)}°`
    );


    drawChart(
        "trafficChart",
        advancedHistory,
        [
            {
                key:
                    "download_bps",
                color:
                    "--download"
            },
            {
                key:
                    "upload_bps",
                color:
                    "--upload"
            }
        ],
        value =>
            fmtRate(
                value
            ),
        {
            minValue: 0
        }
    );
}


async function refreshCurrent() {
    await loadAlertConfig();

    await Promise.all([
        loadCurrent(),
        loadAdvancedCurrent()
    ]);
}


async function refreshHistory() {
    await Promise.all([
        loadHistory(),
        loadAdvancedStats()
    ]);
}


function setRange(
    range
) {
    selectedRange =
        range;

    localStorage.setItem(
        HISTORY_RANGE_STORAGE_KEY,
        selectedRange
    );


    document
        .querySelectorAll(
            ".range-buttons button"
        )
        .forEach(
            button => {
                button.classList.toggle(
                    "active",
                    button.dataset.range ===
                    selectedRange
                );
            }
        );


    refreshHistory();
}


document
    .querySelectorAll(
        ".range-buttons button"
    )
    .forEach(
        button => {
            button.addEventListener(
                "click",
                () => {
                    setRange(
                        button.dataset.range
                    );
                }
            );
        }
    );


window.addEventListener(
    "resize",
    () => {
        drawAllCharts();
    }
);


refreshCurrent();
setRange(selectedRange);


setInterval(
    refreshCurrent,
    5000
);


setInterval(
    refreshHistory,
    30000
);

window.addEventListener(
    "xonu-theme-change",
    () => {
        drawAllCharts();
    }
);
