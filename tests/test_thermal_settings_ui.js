"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(
    "web_templates/alerts_settings_content.html", "utf8"
);

const controls = [
    "alertOpticWarm",
    "alertOpticHot",
    "alertThermalWarm",
    "alertThermalHot"
];

for (const id of controls) {
    assert.equal(
        html.split(`id="${id}"`).length - 1,
        1,
        `Unique settings control: ${id}`
    );
}

const elements = {};

const ids = [
    ...controls,
    "alertConfigStatus",
    "alertWarningSamples",
    "alertRxPoorLow",
    "alertRxFairLow",
    "alertRxPoorHigh",
    "alertTxProfile",
    "alertTxLowAlarm",
    "alertTxLowWarning",
    "alertTxHighWarning",
    "alertTxHighAlarm",
    "alertGemMinDelta",
    "alertGemSeverity",
    "alertPloamNotOperationalSeverity",
    "alertPloamRecoveredSeverity",
    "alertActiveAlarmIncreasedSeverity",
    "alertActiveAlarmDecreasedSeverity",
    "alertActiveAlarmClearedSeverity",
    "alertReachabilityFailureSamples",
    "alertReachabilityUnreachableSeverity",
    "alertReachabilityRecoveredSeverity"
];

for (const id of ids) {
    const invalid = new Set();

    elements[id] = {
        value: "",
        textContent: "",
        className: "",
        hidden: false,
        disabled: false,
        classList: {
            add: value => invalid.add(value),
            remove: value => invalid.delete(value),
            contains: value => invalid.has(value)
        },
        addEventListener() {}
    };
}

let saved = null;

const context = {
    console,
    structuredClone,
    setInterval() {},
    localStorage: {
        getItem() { return null; },
        setItem() {}
    },
    document: {
        getElementById: id => elements[id] || null,
        querySelectorAll: () => []
    },
    fetch: async (url, options) => {
        assert.equal(url, "/api/alert-config");
        assert.equal(options.method, "PUT");

        saved = JSON.parse(options.body);

        return {
            ok: true,
            json: async () => saved
        };
    }
};

vm.createContext(context);

vm.runInContext(
    fs.readFileSync("static/alerts.js", "utf8"),
    context
);

const initial = {
    config_version: 4,
    quality: {
        warning_samples: 3,
        rx_power: {
            poor_low: -27,
            fair_low: -24,
            poor_high: -8
        },
        tx_power: {
            profile: "legacy",
            operating_min: null,
            operating_max: null,
            low_alarm: 1,
            low_warning: 2,
            high_warning: 7,
            high_alarm: 8
        },
        thermal: {
            warm: 75,
            hot: 85,
            optic_warm: 60,
            optic_hot: 70
        }
    },
    gem_key_errors: {
        min_delta: 1,
        severity: "warning"
    },
    ploam: {
        not_operational_severity: "critical",
        recovered_severity: "info"
    },
    active_alarms: {
        increased_severity: "critical",
        decreased_severity: "info",
        cleared_severity: "info"
    },
    core_reachability: {
        failure_samples: 3,
        unreachable_severity: "critical",
        recovered_severity: "info"
    },
    counters: []
};

context.initialConfigFixture = initial;

vm.runInContext(
    "currentAlertConfig = initialConfigFixture",
    context
);

context.renderAlertConfig(initial);

assert.equal(elements.alertOpticWarm.value, 60);
assert.equal(elements.alertOpticHot.value, 70);
assert.equal(elements.alertThermalWarm.value, 75);
assert.equal(elements.alertThermalHot.value, 85);

elements.alertOpticWarm.value = "58.5";
elements.alertOpticHot.value = "69.5";
elements.alertThermalWarm.value = "73.5";
elements.alertThermalHot.value = "84.5";

(async () => {
    await context.saveAlertConfig();

    assert.ok(saved, "Settings were submitted");

    assert.deepEqual(saved.quality.thermal, {
        warm: 73.5,
        hot: 84.5,
        optic_warm: 58.5,
        optic_hot: 69.5
    });

    assert.equal(saved.config_version, 4);
    assert.equal(
        elements.alertConfigStatus.textContent,
        "Settings saved"
    );

    context.markBackendErrorFields(
        "quality.thermal.optic_hot must be finite"
    );

    assert.ok(
        elements.alertOpticHot.classList.contains("invalid")
    );

    console.log(
        "PASS: Optical and CPU settings UI round-trip"
    );
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
