const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


function fakeElement(value = "") {
    const listeners = {};

    return {
        value,
        textContent: "",
        hidden: false,
        disabled: false,
        className: "",
        classList: {
            add() {},
            remove() {},
        },
        addEventListener(name, callback) {
            listeners[name] = callback;
        },
        trigger(name) {
            listeners[name]();
        },
    };
}


const elements = {
    alertTxProfile: fakeElement("legacy"),
    alertTxProfileHelp: fakeElement(),
    alertTxOperatingEnvelope: fakeElement(),
    alertTxOperatingMinimum: fakeElement(),
    alertTxOperatingMaximum: fakeElement(),
    alertTxThresholdControls: fakeElement(),
    alertTxLowAlarm: fakeElement("1.00"),
    alertTxLowWarning: fakeElement("2.00"),
    alertTxHighWarning: fakeElement("7.00"),
    alertTxHighAlarm: fakeElement("8.00"),
};

const context = {
    console,
    structuredClone,
    setInterval() {},
    localStorage: {
        getItem() {
            return null;
        },
        setItem() {},
    },
    document: {
        getElementById(id) {
            return elements[id] || null;
        },
        querySelectorAll() {
            return [];
        },
        createElement() {
            return fakeElement();
        },
    },
};

const settingsTemplate = fs.readFileSync(
    path.join(
        __dirname,
        "../web_templates/alerts_settings_content.html"
    ),
    "utf8"
);

const settingsPage = fs.readFileSync(
    path.join(
        __dirname,
        "../web_templates/alerts_settings.html"
    ),
    "utf8"
);

const settingsStyles = fs.readFileSync(
    path.join(
        __dirname,
        "../static/style.css"
    ),
    "utf8"
);

assert.match(
    settingsTemplate,
    /XGS-PON TX operating range/
);

assert.match(
    settingsTemplate,
    /This protection is active\.[\s\S]*trigger an immediate TX power/
);

assert.match(
    settingsTemplate,
    /id="alertTxOperatingEnvelope"[\s\S]*id="alertTxOperatingMinimum"[\s\S]*id="alertTxOperatingMaximum"/
);

assert.match(
    settingsTemplate,
    /id="alertTxThresholdControls"[\s\S]*id="alertTxLowAlarm"[\s\S]*id="alertTxLowWarning"[\s\S]*id="alertTxHighWarning"[\s\S]*id="alertTxHighAlarm"/
);

assert.match(
    settingsPage,
    /style\.css\?v=tx-profile-ui-2/
);

assert.match(
    settingsPage,
    /alerts\.js\?v=tx-profile-ui-2/
);

assert.match(
    settingsStyles,
    /#alertTxThresholdControls\[hidden\][\s\S]*display: none/
);

vm.createContext(context);
vm.runInContext(
    fs.readFileSync(
        path.join(
            __dirname,
            "../static/alerts.js"
        ),
        "utf8"
    ),
    context
);

const legacy = {
    profile: "legacy",
    operating_min: null,
    operating_max: null,
    low_alarm: 1,
    low_warning: 2,
    high_warning: 7,
    high_alarm: 8,
    cosmetic_great_low: 4,
    cosmetic_great_high: 5,
};

const xgsponst2001 = {
    profile: "xgsponst2001-a01",
    operating_min: 4,
    operating_max: 9,
    low_alarm: null,
    low_warning: null,
    high_warning: null,
    high_alarm: null,
    cosmetic_great_low: null,
    cosmetic_great_high: null,
};

context.profileCatalogFixture = {
    legacy: {
        description: "Legacy TX thresholds.",
        thresholds: legacy,
    },
    "xgsponst2001-a01": {
        description: "XGS-PON operating envelope.",
        thresholds: xgsponst2001,
    },
    custom: {
        description: "Custom TX thresholds.",
        thresholds: null,
    },
};

context.renderTxConfig(legacy);

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.value, "1.00");

vm.runInContext(
    "txProfileCatalog = profileCatalogFixture; " +
        "currentAlertConfig = {quality: {tx_power: " +
        "structuredClone(txProfileCatalog.legacy.thresholds)}};",
    context
);

elements.alertTxProfile.value = "xgsponst2001-a01";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, true);
assert.equal(elements.alertTxOperatingEnvelope.hidden, false);
assert.equal(elements.alertTxOperatingMinimum.textContent, "4.00 dBm");
assert.equal(elements.alertTxOperatingMaximum.textContent, "9.00 dBm");
assert.equal(elements.alertTxLowAlarm.value, "");
assert.equal(elements.alertTxHighAlarm.value, "");
assert.equal(
    elements.alertTxProfileHelp.textContent,
    "XGS-PON operating envelope."
);
assert.doesNotMatch(
    elements.alertTxOperatingEnvelope.textContent,
    /disabled/i
);

elements.alertTxProfile.value = "legacy";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.value, "1.00");
assert.equal(elements.alertTxLowWarning.value, "2.00");
assert.equal(elements.alertTxHighWarning.value, "7.00");
assert.equal(elements.alertTxHighAlarm.value, "8.00");
assert.equal(
    elements.alertTxProfileHelp.textContent,
    "Legacy TX thresholds."
);

elements.alertTxProfile.value = "custom";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.disabled, false);
assert.equal(elements.alertTxLowWarning.disabled, false);
assert.equal(elements.alertTxLowAlarm.value, "1.00");
assert.equal(elements.alertTxLowWarning.value, "2.00");
assert.equal(elements.alertTxHighWarning.value, "7.00");
assert.equal(elements.alertTxHighAlarm.value, "8.00");
assert.equal(
    elements.alertTxProfileHelp.textContent,
    "Custom TX thresholds."
);

elements.alertTxLowAlarm.value = "1.50";
elements.alertTxLowAlarm.trigger("input");

elements.alertTxLowWarning.value = "2.50";
elements.alertTxLowWarning.trigger("input");

elements.alertTxHighWarning.value = "7.50";
elements.alertTxHighWarning.trigger("input");

elements.alertTxHighAlarm.value = "8.50";
elements.alertTxHighAlarm.trigger("input");

assert.equal(
    elements.alertTxProfile.value,
    "custom"
);

elements.alertTxProfile.value = "xgsponst2001-a01";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, true);
assert.equal(elements.alertTxOperatingEnvelope.hidden, false);

elements.alertTxProfile.value = "custom";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.value, "1.50");
assert.equal(elements.alertTxLowWarning.value, "2.50");
assert.equal(elements.alertTxHighWarning.value, "7.50");
assert.equal(elements.alertTxHighAlarm.value, "8.50");
assert.equal(
    elements.alertTxProfileHelp.textContent,
    "Custom TX thresholds."
);

elements.alertTxProfile.value = "legacy";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.value, "1.00");
assert.equal(elements.alertTxHighAlarm.value, "8.00");

elements.alertTxProfile.value = "custom";
elements.alertTxProfile.trigger("change");

assert.equal(elements.alertTxThresholdControls.hidden, false);
assert.equal(elements.alertTxOperatingEnvelope.hidden, true);
assert.equal(elements.alertTxLowAlarm.value, "1.50");
assert.equal(elements.alertTxHighAlarm.value, "8.50");

console.log(
    "TX profile presentation and switching passed"
);
