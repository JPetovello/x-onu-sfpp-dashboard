let currentAlertConfig = null;
let currentNotificationConfig = null;


const alertCounterControls = {
    bip_errors: {
        minDelta: "alertCounterBipMinDelta",
        cooldown: "alertCounterBipCooldown",
        severity: "alertCounterBipSeverity",
    },

    corrected_fec_codewords: {
        minDelta: "alertCounterCorrectedFecMinDelta",
        cooldown: "alertCounterCorrectedFecCooldown",
        severity: "alertCounterCorrectedFecSeverity",
    },

    uncorrected_fec_codewords: {
        minDelta: "alertCounterUncorrectedFecMinDelta",
        cooldown: "alertCounterUncorrectedFecCooldown",
        severity: "alertCounterUncorrectedFecSeverity",
    },

    psbd_hec_corrected: {
        minDelta: "alertCounterPsbdCorrectedMinDelta",
        cooldown: "alertCounterPsbdCorrectedCooldown",
        severity: "alertCounterPsbdCorrectedSeverity",
    },

    psbd_hec_uncorrected: {
        minDelta: "alertCounterPsbdUncorrectedMinDelta",
        cooldown: "alertCounterPsbdUncorrectedCooldown",
        severity: "alertCounterPsbdUncorrectedSeverity",
    },

    fs_hec_corrected: {
        minDelta: "alertCounterFsCorrectedMinDelta",
        cooldown: "alertCounterFsCorrectedCooldown",
        severity: "alertCounterFsCorrectedSeverity",
    },

    fs_hec_uncorrected: {
        minDelta: "alertCounterFsUncorrectedMinDelta",
        cooldown: "alertCounterFsUncorrectedCooldown",
        severity: "alertCounterFsUncorrectedSeverity",
    },

    ploam_mic_errors: {
        minDelta: "alertCounterPloamMicMinDelta",
        cooldown: "alertCounterPloamMicCooldown",
        severity: "alertCounterPloamMicSeverity",
    },
};


function formatAlertTime(ts) {
    if (!ts) {
        return "-";
    }

    const date = new Date(ts);

    if (Number.isNaN(date.getTime())) {
        return ts;
    }

    return date.toLocaleString();
}


function renderAlerts(events) {
    const list = document.getElementById(
        "alertsList"
    );

    const summary = document.getElementById(
        "alertSummary"
    );

    if (!list || !summary) {
        return;
    }

    if (!Array.isArray(events)) {
        events = [];
    }

    if (events.length === 0) {
        summary.textContent =
            "No recent alerts";

        summary.className =
            "advanced-status good";

        list.innerHTML = `
            <div class="alerts-empty">
                No alert events have been recorded.
            </div>
        `;

        return;
    }

    summary.textContent =
        `${events.length} recent alert${
            events.length === 1 ? "" : "s"
        }`;

    summary.className =
        "advanced-status warn";

    list.innerHTML = events
        .map((event) => {
            const severity =
                event.severity || "warning";

            return `
                <article class="alert-row ${severity}">
                    <div class="alert-main">
                        <span class="alert-severity">
                            ${severity.toUpperCase()}
                        </span>

                        <strong class="alert-message">
                            ${event.message || "Alert"}
                        </strong>

                        <span class="alert-time">
                            ${formatAlertTime(event.ts)}
                        </span>
                    </div>
                </article>
            `;
        })
        .join("");
}


function getAlertElement(id) {
    return document.getElementById(id);
}


function setAlertValue(
    id,
    value
) {
    const element =
        getAlertElement(id);

    if (element) {
        element.value = value;
    }
}


function getCounterElements(metricName) {
    const controls =
        alertCounterControls[metricName];

    if (!controls) {
        return null;
    }

    return {
        minDelta:
            getAlertElement(
                controls.minDelta
            ),

        cooldown:
            getAlertElement(
                controls.cooldown
            ),

        severity:
            getAlertElement(
                controls.severity
            ),
    };
}


function renderCounterConfig(counters) {
    if (!Array.isArray(counters)) {
        return;
    }

    counters.forEach((rule) => {
        const elements =
            getCounterElements(
                rule.metric_name
            );

        if (!elements) {
            return;
        }

        if (elements.minDelta) {
            elements.minDelta.value =
                rule.min_delta;
        }

        if (elements.cooldown) {
            elements.cooldown.value =
                rule.cooldown_seconds;
        }

        if (elements.severity) {
            elements.severity.value =
                rule.severity;
        }
    });
}


function renderAlertConfig(config) {
    const quality = config?.quality;

    if (!quality) {
        throw new Error(
            "Alert quality configuration is missing"
        );
    }

    const rx = quality.rx_power;
    const tx = quality.tx_power;
    const thermal = quality.thermal;

    if (!rx || !tx || !thermal) {
        throw new Error(
            "Alert threshold configuration is missing"
        );
    }

    setAlertValue(
        "alertWarningSamples",
        quality.warning_samples
    );

    setAlertValue(
        "alertRxPoorLow",
        rx.poor_low
    );

    setAlertValue(
        "alertRxFairLow",
        rx.fair_low
    );

    setAlertValue(
        "alertRxPoorHigh",
        rx.poor_high
    );

    setAlertValue(
        "alertTxPoorLow",
        tx.poor_low
    );

    setAlertValue(
        "alertTxFairLow",
        tx.fair_low
    );

    setAlertValue(
        "alertTxFairHigh",
        tx.fair_high
    );

    setAlertValue(
        "alertTxPoorHigh",
        tx.poor_high
    );

    setAlertValue(
        "alertThermalWarm",
        thermal.warm
    );

    setAlertValue(
        "alertThermalHot",
        thermal.hot
    );

    setAlertValue(
        "alertGemMinDelta",
        config.gem_key_errors?.min_delta
    );

    setAlertValue(
        "alertGemSeverity",
        config.gem_key_errors?.severity
    );

    setAlertValue(
        "alertPloamNotOperationalSeverity",
        config.ploam?.not_operational_severity
    );

    setAlertValue(
        "alertPloamRecoveredSeverity",
        config.ploam?.recovered_severity
    );

    setAlertValue(
        "alertActiveAlarmIncreasedSeverity",
        config.active_alarms?.increased_severity
    );

    setAlertValue(
        "alertActiveAlarmDecreasedSeverity",
        config.active_alarms?.decreased_severity
    );

    setAlertValue(
        "alertActiveAlarmClearedSeverity",
        config.active_alarms?.cleared_severity
    );

    setAlertValue(
        "alertReachabilityUnreachableSeverity",
        config.core_reachability?.unreachable_severity
    );

    setAlertValue(
        "alertReachabilityRecoveredSeverity",
        config.core_reachability?.recovered_severity
    );

    renderCounterConfig(
        config.counters
    );

    const status =
        getAlertElement(
            "alertConfigStatus"
        );

    if (status) {
        status.textContent =
            "Settings loaded";

        status.className =
            "advanced-status good";
    }
}


function clearAlertInvalidFields() {
    document
        .querySelectorAll(
            ".alert-setting-input.invalid"
        )
        .forEach((element) => {
            element.classList.remove(
                "invalid"
            );
        });
}


function markAlertInvalid(id) {
    const element =
        getAlertElement(id);

    if (element) {
        element.classList.add(
            "invalid"
        );
    }
}


function readNumber(
    id,
    label
) {
    const element =
        getAlertElement(id);

    if (!element) {
        throw new Error(
            `${label} control is missing`
        );
    }

    const value =
        Number(element.value);

    if (!Number.isFinite(value)) {
        markAlertInvalid(id);

        throw new Error(
            `${label} must be a number`
        );
    }

    return value;
}


function readInteger(
    id,
    label,
    minimum = null,
    maximum = null
) {
    const value =
        readNumber(
            id,
            label
        );

    if (!Number.isInteger(value)) {
        markAlertInvalid(id);

        throw new Error(
            `${label} must be an integer`
        );
    }

    if (
        minimum !== null
        && value < minimum
    ) {
        markAlertInvalid(id);

        throw new Error(
            `${label} must be at least ${minimum}`
        );
    }

    if (
        maximum !== null
        && value > maximum
    ) {
        markAlertInvalid(id);

        throw new Error(
            `${label} must be no more than ${maximum}`
        );
    }

    return value;
}


function readSelect(
    id,
    label
) {
    const element =
        getAlertElement(id);

    if (!element) {
        throw new Error(
            `${label} control is missing`
        );
    }

    return element.value;
}


function updateCounterConfig(config) {
    config.counters.forEach((rule) => {
        const controls =
            alertCounterControls[
                rule.metric_name
            ];

        if (!controls) {
            throw new Error(
                `Unsupported counter: ${
                    rule.metric_name
                }`
            );
        }

        rule.min_delta =
            readInteger(
                controls.minDelta,
                `${rule.label} minimum delta`,
                1
            );

        rule.cooldown_seconds =
            readInteger(
                controls.cooldown,
                `${rule.label} cooldown`,
                0,
                86400
            );

        rule.severity =
            readSelect(
                controls.severity,
                `${rule.label} severity`
            );
    });
}


function markBackendErrorFields(message) {
    const lower =
        String(message || "")
            .toLowerCase();

    if (lower.includes("warning_samples")) {
        markAlertInvalid(
            "alertWarningSamples"
        );
    }

    if (
        lower.includes("rx threshold")
        || lower.includes("rx_power")
    ) {
        markAlertInvalid(
            "alertRxPoorLow"
        );

        markAlertInvalid(
            "alertRxFairLow"
        );

        markAlertInvalid(
            "alertRxPoorHigh"
        );
    }

    if (
        lower.includes("tx threshold")
        || lower.includes("tx_power")
    ) {
        markAlertInvalid(
            "alertTxPoorLow"
        );

        markAlertInvalid(
            "alertTxFairLow"
        );

        markAlertInvalid(
            "alertTxFairHigh"
        );

        markAlertInvalid(
            "alertTxPoorHigh"
        );
    }

    if (
        lower.includes("thermal")
    ) {
        markAlertInvalid(
            "alertThermalWarm"
        );

        markAlertInvalid(
            "alertThermalHot"
        );
    }

    if (
        lower.includes("gem_key_errors")
        || lower.includes("gem key")
    ) {
        markAlertInvalid(
            "alertGemMinDelta"
        );
    }
}


async function loadAlertConfig() {
    try {
        const response = await fetch(
            "/api/alert-config",
            {
                cache: "no-store",
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const config =
            await response.json();

        currentAlertConfig =
            structuredClone(config);

        renderAlertConfig(
            currentAlertConfig
        );

    } catch (error) {
        const status =
            getAlertElement(
                "alertConfigStatus"
            );

        if (status) {
            status.textContent =
                "Settings unavailable";

            status.className =
                "advanced-status bad";
        }
    }
}


async function saveAlertConfig() {
    const status =
        getAlertElement(
            "alertConfigStatus"
        );

    clearAlertInvalidFields();

    if (!currentAlertConfig) {
        if (status) {
            status.textContent =
                "Settings unavailable";

            status.className =
                "advanced-status bad";
        }

        return;
    }

    try {
        const config =
            structuredClone(
                currentAlertConfig
            );

        config.quality.warning_samples =
            readInteger(
                "alertWarningSamples",
                "Warning samples",
                1,
                1000
            );

        config.quality.rx_power.poor_low =
            readNumber(
                "alertRxPoorLow",
                "RX poor low"
            );

        config.quality.rx_power.fair_low =
            readNumber(
                "alertRxFairLow",
                "RX fair low"
            );

        config.quality.rx_power.poor_high =
            readNumber(
                "alertRxPoorHigh",
                "RX poor high"
            );

        config.quality.tx_power.poor_low =
            readNumber(
                "alertTxPoorLow",
                "TX poor low"
            );

        config.quality.tx_power.fair_low =
            readNumber(
                "alertTxFairLow",
                "TX fair low"
            );

        config.quality.tx_power.fair_high =
            readNumber(
                "alertTxFairHigh",
                "TX fair high"
            );

        config.quality.tx_power.poor_high =
            readNumber(
                "alertTxPoorHigh",
                "TX poor high"
            );

        config.quality.thermal.warm =
            readNumber(
                "alertThermalWarm",
                "Thermal warm"
            );

        config.quality.thermal.hot =
            readNumber(
                "alertThermalHot",
                "Thermal hot"
            );

        config.gem_key_errors.min_delta =
            readInteger(
                "alertGemMinDelta",
                "GEM key error minimum delta",
                1
            );

        config.gem_key_errors.severity =
            readSelect(
                "alertGemSeverity",
                "GEM key error severity"
            );

        config.ploam.not_operational_severity =
            readSelect(
                "alertPloamNotOperationalSeverity",
                "PLOAM not operational severity"
            );

        config.ploam.recovered_severity =
            readSelect(
                "alertPloamRecoveredSeverity",
                "PLOAM recovered severity"
            );

        config.active_alarms.increased_severity =
            readSelect(
                "alertActiveAlarmIncreasedSeverity",
                "Active alarm increased severity"
            );

        config.active_alarms.decreased_severity =
            readSelect(
                "alertActiveAlarmDecreasedSeverity",
                "Active alarm decreased severity"
            );

        config.active_alarms.cleared_severity =
            readSelect(
                "alertActiveAlarmClearedSeverity",
                "Active alarm cleared severity"
            );

        config.core_reachability.unreachable_severity =
            readSelect(
                "alertReachabilityUnreachableSeverity",
                "ONT unreachable severity"
            );

        config.core_reachability.recovered_severity =
            readSelect(
                "alertReachabilityRecoveredSeverity",
                "ONT recovered severity"
            );

        updateCounterConfig(config);

        if (status) {
            status.textContent =
                "Saving...";

            status.className =
                "advanced-status";
        }

        const response = await fetch(
            "/api/alert-config",
            {
                method: "PUT",

                headers: {
                    "Content-Type":
                        "application/json",
                },

                body: JSON.stringify(
                    config
                ),
            }
        );

        let body = null;

        try {
            body =
                await response.json();
        } catch (error) {
            body = null;
        }

        if (!response.ok) {
            const message =
                body?.error
                || `HTTP ${response.status}`;

            markBackendErrorFields(
                message
            );

            throw new Error(
                message
            );
        }

        currentAlertConfig =
            structuredClone(body);

        renderAlertConfig(
            currentAlertConfig
        );

        if (status) {
            status.textContent =
                "Settings saved";

            status.className =
                "advanced-status good";
        }

    } catch (error) {
        if (status) {
            status.textContent =
                error.message
                || "Unable to save settings";

            status.className =
                "advanced-status bad";
        }
    }
}


function renderNotificationConfig(config) {
    const enabled =
        getAlertElement(
            "notificationDiscordEnabled"
        );

    const webhookUrl =
        getAlertElement(
            "notificationDiscordWebhookUrl"
        );

    const status =
        getAlertElement(
            "notificationSettingsStatus"
        );

    if (
        !enabled
        || !webhookUrl
        || !status
    ) {
        return;
    }

    enabled.checked =
        Boolean(
            config?.discord?.enabled
        );

    webhookUrl.value =
        config?.discord?.webhook_url
        || "";

    status.textContent =
        "Settings loaded";

    status.className =
        "advanced-status good";
}


async function loadNotificationConfig() {
    try {
        const response = await fetch(
            "/api/notification-config",
            {
                cache: "no-store",
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const config =
            await response.json();

        currentNotificationConfig =
            structuredClone(config);

        renderNotificationConfig(
            currentNotificationConfig
        );

    } catch (error) {
        const status =
            getAlertElement(
                "notificationSettingsStatus"
            );

        if (status) {
            status.textContent =
                "Settings unavailable";

            status.className =
                "advanced-status bad";
        }
    }
}


async function saveNotificationConfig() {
    const status =
        getAlertElement(
            "notificationSettingsStatus"
        );

    const enabled =
        getAlertElement(
            "notificationDiscordEnabled"
        );

    const webhookUrl =
        getAlertElement(
            "notificationDiscordWebhookUrl"
        );

    if (
        !currentNotificationConfig
        || !enabled
        || !webhookUrl
    ) {
        if (status) {
            status.textContent =
                "Settings unavailable";

            status.className =
                "advanced-status bad";
        }

        return;
    }

    try {
        const config =
            structuredClone(
                currentNotificationConfig
            );

        config.discord.enabled =
            enabled.checked;

        config.discord.webhook_url =
            webhookUrl.value.trim();

        if (status) {
            status.textContent =
                "Saving...";

            status.className =
                "advanced-status";
        }

        const response = await fetch(
            "/api/notification-config",
            {
                method: "PUT",

                headers: {
                    "Content-Type":
                        "application/json",
                },

                body: JSON.stringify(
                    config
                ),
            }
        );

        let body = null;

        try {
            body =
                await response.json();
        } catch (error) {
            body = null;
        }

        if (!response.ok) {
            throw new Error(
                body?.error
                || `HTTP ${response.status}`
            );
        }

        currentNotificationConfig =
            structuredClone(body);

        renderNotificationConfig(
            currentNotificationConfig
        );

        if (status) {
            status.textContent =
                "Settings saved";

            status.className =
                "advanced-status good";
        }

    } catch (error) {
        if (status) {
            status.textContent =
                error.message
                || "Unable to save settings";

            status.className =
                "advanced-status bad";
        }
    }
}


async function loadAlerts() {
    try {
        const response = await fetch(
            "/api/alerts?limit=25",
            {
                cache: "no-store",
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const events =
            await response.json();

        renderAlerts(events);

    } catch (error) {
        const list =
            getAlertElement(
                "alertsList"
            );

        const summary =
            getAlertElement(
                "alertSummary"
            );

        if (summary) {
            summary.textContent =
                "Alerts unavailable";

            summary.className =
                "advanced-status bad";
        }

        if (list) {
            list.innerHTML = `
                <div class="alerts-empty">
                    Unable to load alert history.
                </div>
            `;
        }
    }
}


const alertSaveSettings =
    getAlertElement(
        "alertSaveSettings"
    );

if (alertSaveSettings) {
    alertSaveSettings.addEventListener(
        "click",
        saveAlertConfig
    );
}


const notificationSaveSettings =
    getAlertElement(
        "notificationSaveSettings"
    );

if (notificationSaveSettings) {
    notificationSaveSettings.addEventListener(
        "click",
        saveNotificationConfig
    );
}


document
    .querySelectorAll(
        ".alert-setting-input"
    )
    .forEach((element) => {
        element.addEventListener(
            "input",
            () => {
                element.classList.remove(
                    "invalid"
                );
            }
        );

        element.addEventListener(
            "change",
            () => {
                element.classList.remove(
                    "invalid"
                );
            }
        );
    });


loadAlertConfig();
loadNotificationConfig();
loadAlerts();

setInterval(
    loadAlerts,
    30000
);
