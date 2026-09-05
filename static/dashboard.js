let selectedRange = "24h";
let lastHistoryRefresh = 0;


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


function setText(
    id,
    value
) {

    document
        .getElementById(id)
        .textContent = value;
}


function setBadge(
    id,
    text,
    level
) {

    const element =
        document
            .getElementById(id);

    element.textContent =
        text;

    element.className =
        "health-badge " +
        level;
}


function rxStatus(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return [
            "UNKNOWN",
            "unknown"
        ];
    }

    if (
        value <= -27 ||
        value > -8
    ) {
        return [
            "POOR",
            "bad"
        ];
    }

    if (
        value < -24
    ) {
        return [
            "FAIR",
            "warn"
        ];
    }

    if (
        value >= -20 &&
        value <= -14
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


function txStatus(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return [
            "UNKNOWN",
            "unknown"
        ];
    }

    if (
        value <= 1 ||
        value >= 8
    ) {
        return [
            "POOR",
            "bad"
        ];
    }

    if (
        value < 2 ||
        value > 7
    ) {
        return [
            "FAIR",
            "warn"
        ];
    }

    if (
        value >= 4 &&
        value <= 5
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


function thermalStatus(
    optic,
    cpu1,
    cpu2
) {

    const values = [
        optic,
        cpu1,
        cpu2
    ].filter(
        Number.isFinite
    );

    if (!values.length) {
        return [
            "UNKNOWN",
            "unknown"
        ];
    }

    const max =
        Math.max(
            ...values
        );

    if (max >= 85) {
        return [
            "HOT",
            "bad"
        ];
    }

    if (max >= 75) {
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


function formatDuration(
    seconds
) {

    seconds =
        Number(seconds) ||
        0;

    const days =
        Math.floor(
            seconds / 86400
        );

    const hours =
        Math.floor(
            (
                seconds % 86400
            ) / 3600
        );

    const minutes =
        Math.floor(
            (
                seconds % 3600
            ) / 60
        );

    if (days > 0) {
        return `${days}d ${hours}h`;
    }

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }

    return `${minutes}m`;
}


async function updateCurrent() {

    try {

        const response =
            await fetch(
                "/api/current",
                {
                    cache:
                    "no-store"
                }
            );

        const data =
            await response.json();


        const dot =
            document
                .getElementById(
                    "statusDot"
                );


        dot.className =
            "status-dot " +
            (
                data.online
                    ? "online"
                    : "offline"
            );


        setText(
            "statusText",
            data.online
                ? "ONT ONLINE"
                : "ONT UNREACHABLE"
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


        if (!data.metrics) {
            return;
        }


        const m =
            data.metrics;


        setText(
            "rxPower",
            fmt(
                m.rx_power_dBm
            )
        );

        setText(
            "txPower",
            fmt(
                m.tx_power_dBm
            )
        );

        setText(
            "txBias",
            fmt(
                m.tx_bias_mA
            )
        );

        setText(
            "voltage",
            fmt(
                m.module_voltage
            )
        );

        setText(
            "opticTemp",
            fmt(
                m.optic_tempC
            )
        );

        setText(
            "cpuTemps",
            `${fmt(m.cpu1_tempC)} / ${fmt(m.cpu2_tempC)}`
        );

        setText(
            "ploamLabel",
            data.ploam_label ||
            "Unknown"
        );

        setText(
            "ploamCode",
            m.ploam_state ??
            "-"
        );


        setBadge(
            "ponHealth",
            (
                data.online &&
                m.ploam_state === 51
            )
                ? "OPERATIONAL"
                : "NOT READY",
            (
                data.online &&
                m.ploam_state === 51
            )
                ? "good"
                : "bad"
        );


        const rx =
            rxStatus(
                m.rx_power_dBm
            );

        setBadge(
            "rxHealth",
            rx[0],
            rx[1]
        );


        const tx =
            txStatus(
                m.tx_power_dBm
            );

        setBadge(
            "txHealth",
            tx[0],
            tx[1]
        );


        const thermals =
            thermalStatus(
                Number(
                    m.optic_tempC
                ),
                Number(
                    m.cpu1_tempC
                ),
                Number(
                    m.cpu2_tempC
                )
            );

        setBadge(
            "thermalHealth",
            thermals[0],
            thermals[1]
        );

    } catch (error) {

        setText(
            "statusText",
            "DASHBOARD ERROR"
        );

        setText(
            "lastUpdate",
            String(error)
        );
    }
}


async function updateStats() {

    const response =
        await fetch(
            "/api/stats?range=24h",
            {
                cache:
                "no-store"
            }
        );

    const s =
        await response.json();


    setText(
        "rxMin",
        `${fmt(s.rx_min)} dBm`
    );

    setText(
        "rxAvg",
        `${fmt(s.rx_avg)} dBm`
    );

    setText(
        "rxMax",
        `${fmt(s.rx_max)} dBm`
    );


    setText(
        "txMin",
        `${fmt(s.tx_min)} dBm`
    );

    setText(
        "txAvg",
        `${fmt(s.tx_avg)} dBm`
    );

    setText(
        "txMax",
        `${fmt(s.tx_max)} dBm`
    );


    setText(
        "opticMin",
        `${fmt(s.optic_min)} °C`
    );

    setText(
        "opticAvg",
        `${fmt(s.optic_avg)} °C`
    );

    setText(
        "opticMax",
        `${fmt(s.optic_max)} °C`
    );


    setText(
        "statsSamples",
        s.samples ??
        0
    );
}


function drawChart(
    canvasId,
    rows,
    series,
    ySuffix
) {

    const canvas =
        document
            .getElementById(
                canvasId
            );


    const rect =
        canvas
            .getBoundingClientRect();


    const dpr =
        window.devicePixelRatio ||
        1;


    canvas.width =
        Math.max(
            600,
            rect.width * dpr
        );


    canvas.height =
        280 * dpr;


    const ctx =
        canvas
            .getContext(
                "2d"
            );


    ctx.scale(
        dpr,
        dpr
    );


    const w =
        canvas.width /
        dpr;


    const h =
        canvas.height /
        dpr;


    const pad = {
        l: 52,
        r: 14,
        t: 12,
        b: 28
    };


    ctx.clearRect(
        0,
        0,
        w,
        h
    );


    const values =
        [];


    for (
        const seriesItem
        of series
    ) {

        for (
            const row
            of rows
        ) {

            const value =
                Number(
                    row[
                        seriesItem.key
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
            "#8e9aa8";


        ctx.font =
            "13px system-ui";


        ctx.fillText(
            "Waiting for history samples...",
            pad.l,
            45
        );


        return;
    }


    let ymin =
        Math.min(
            ...values
        );


    let ymax =
        Math.max(
            ...values
        );


    let spread =
        ymax -
        ymin;


    if (
        spread <
        1
    ) {
        spread = 1;
    }


    ymin -=
        spread *
        0.18;


    ymax +=
        spread *
        0.18;


    const x =
        index =>
            pad.l +
            (
                index /
                Math.max(
                    1,
                    rows.length - 1
                )
            ) *
            (
                w -
                pad.l -
                pad.r
            );


    const y =
        value =>
            pad.t +
            (
                ymax -
                value
            ) /
            (
                ymax -
                ymin
            ) *
            (
                h -
                pad.t -
                pad.b
            );


    ctx.strokeStyle =
        "#29323d";


    ctx.fillStyle =
        "#8e9aa8";


    ctx.font =
        "10px system-ui";


    ctx.lineWidth =
        1;


    for (
        let i = 0;
        i <= 4;
        i++
    ) {

        const value =
            ymax -
            (
                ymax -
                ymin
            ) *
            (
                i / 4
            );


        const yy =
            y(value);


        ctx.beginPath();

        ctx.moveTo(
            pad.l,
            yy
        );

        ctx.lineTo(
            w -
            pad.r,
            yy
        );

        ctx.stroke();


        ctx.fillText(
            value.toFixed(1) +
            ySuffix,
            3,
            yy + 3
        );
    }


    for (
        const seriesItem
        of series
    ) {

        ctx.strokeStyle =
            seriesItem.color;


        ctx.lineWidth =
            2;


        ctx.beginPath();


        let started =
            false;


        rows.forEach(
            (
                row,
                index
            ) => {

                const value =
                    Number(
                        row[
                            seriesItem.key
                        ]
                    );


                if (
                    !Number.isFinite(
                        value
                    )
                ) {
                    return;
                }


                const xx =
                    x(index);


                const yy =
                    y(value);


                if (!started) {

                    ctx.moveTo(
                        xx,
                        yy
                    );

                    started =
                        true;

                } else {

                    ctx.lineTo(
                        xx,
                        yy
                    );
                }

            }
        );


        ctx.stroke();
    }


    const labels = [
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


    ctx.fillStyle =
        "#8e9aa8";


    labels.forEach(
        (
            index,
            position
        ) => {

            const dt =
                new Date(
                    rows[index].ts
                );


            const text =
                dt.toLocaleString(
                    [],
                    {
                        month:
                        "short",

                        day:
                        "numeric",

                        hour:
                        "numeric",

                        minute:
                        "2-digit"
                    }
                );


            ctx.textAlign =
                position === 0
                    ? "left"
                    :
                position === 2
                    ? "right"
                    :
                "center";


            ctx.fillText(
                text,
                x(index),
                h - 7
            );

        }
    );


    ctx.textAlign =
        "left";
}


async function updateHistory() {

    const response =
        await fetch(
            `/api/history?range=${encodeURIComponent(selectedRange)}`,
            {
                cache:
                "no-store"
            }
        );


    const rows =
        await response.json();


    setText(
        "sampleCount",
        `${rows.length} plotted samples`
    );


    drawChart(
        "powerChart",
        rows,
        [
            {
                key:
                "rx_power_dBm",

                color:
                "#69a7ff"
            },
            {
                key:
                "tx_power_dBm",

                color:
                "#ad86ff"
            }
        ],
        ""
    );


    drawChart(
        "tempChart",
        rows,
        [
            {
                key:
                "optic_tempC",

                color:
                "#48d597"
            },
            {
                key:
                "cpu1_tempC",

                color:
                "#ffb65c"
            },
            {
                key:
                "cpu2_tempC",

                color:
                "#ff7f87"
            }
        ],
        "°"
    );


    lastHistoryRefresh =
        Date.now();
}


document
    .querySelectorAll(
        "[data-range]"
    )
    .forEach(
        button => {

            button
                .addEventListener(
                    "click",
                    () => {

                        document
                            .querySelectorAll(
                                "[data-range]"
                            )
                            .forEach(
                                item =>
                                    item
                                        .classList
                                        .remove(
                                            "active"
                                        )
                            );


                        button
                            .classList
                            .add(
                                "active"
                            );


                        selectedRange =
                            button
                                .dataset
                                .range;


                        updateHistory();
                    }
                );

        }
    );


async function tick() {

    await updateCurrent();


    if (
        Date.now() -
        lastHistoryRefresh >
        30000
    ) {

        try {

            await Promise.all([
                updateHistory(),
                updateStats()
            ]);

        } catch (_) {
        }
    }

}


window.addEventListener(
    "resize",
    () =>
        updateHistory()
);


tick();

setInterval(
    tick,
    5000
);
