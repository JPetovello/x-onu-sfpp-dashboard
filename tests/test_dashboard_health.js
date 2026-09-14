const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


const context = {
    console,
    setInterval() {},
    fetch() {
        return new Promise(() => {});
    },
    localStorage: {
        getItem() {
            return null;
        },
        setItem() {},
    },
    document: {
        getElementById() {
            return null;
        },
        querySelectorAll() {
            return [];
        },
    },
    window: {
        addEventListener() {},
    },
};


vm.createContext(context);

for (const name of ["tx_health.js", "dashboard.js"]) {
    vm.runInContext(
        fs.readFileSync(
            path.join(__dirname, `../static/${name}`),
            "utf8"
        ),
        context
    );
}


context.alertConfigFixture = {
    ploam: {
        operational_state: 51,
    },
    quality: {
        rx_power: {
            poor_low: -27,
            poor_high: -8,
            fair_low: -24,
            great_low: -20,
            great_high: -14,
        },
        tx_power: {
            profile: "legacy",
            operating_min: null,
            operating_max: null,
            low_alarm: 1,
            low_warning: 2,
            high_warning: 7,
            high_alarm: 8,
            cosmetic_great_low: 4,
            cosmetic_great_high: 5,
        },
        thermal: {
            warm: 75,
            hot: 85,
        },
    },
};

context.coreFixture = {
    online: true,
    metrics: {
        ploam_state: 51,
        rx_power_dBm: -15.9,
        tx_power_dBm: 6.2,
        optic_tempC: 40,
        cpu1_tempC: 45,
        cpu2_tempC: 46,
    },
};

vm.runInContext(
    "alertConfig = alertConfigFixture; " +
        "latestCore = coreFixture; latestAdvanced = null;",
    context
);

assert.deepEqual(
    Array.from(context.overallHealthState()),
    ["HEALTHY", "good"]
);

vm.runInContext(
    "alertConfig = null; latestCore.metrics.ploam_state = 51;",
    context
);

assert.deepEqual(
    Array.from(context.overallHealthState()),
    ["HEALTHY", "good"]
);

vm.runInContext(
    "alertConfig = alertConfigFixture;",
    context
);

vm.runInContext(
    "alertConfig.ploam.operational_state = 40; " +
        "latestCore.metrics.ploam_state = 40;",
    context
);

assert.deepEqual(
    Array.from(context.overallHealthState()),
    ["HEALTHY", "good"]
);

vm.runInContext(
    "latestCore.metrics.ploam_state = 51;",
    context
);

assert.deepEqual(
    Array.from(context.overallHealthState()),
    ["NOT OPERATIONAL", "bad"]
);

for (const value of [null, "", "not-a-state", Infinity]) {
    context.invalidPloamFixture = value;
    vm.runInContext(
        "latestCore.metrics.ploam_state = invalidPloamFixture;",
        context
    );

    assert.deepEqual(
        Array.from(context.overallHealthState()),
        ["NOT OPERATIONAL", "bad"]
    );
}


console.log(
    "Dashboard PLOAM health follows configured policy"
);
