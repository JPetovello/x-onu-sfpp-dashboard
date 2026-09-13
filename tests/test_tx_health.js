const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
    classifyTxPower,
} = require("../static/tx_health.js");

const fixtures = JSON.parse(
    fs.readFileSync(
        path.join(
            __dirname,
            "tx_classification_cases.json"
        ),
        "utf8"
    )
);

fixtures.cases.forEach((testCase) => {
    const thresholds =
        fixtures.profiles[testCase.profile];

    assert.deepEqual(
        classifyTxPower(
            testCase.value,
            thresholds
        ),
        [
            testCase.label,
            testCase.level,
        ]
    );
});

[
    null,
    "",
    undefined,
    "not-a-number",
    Number.NaN,
    Number.POSITIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
].forEach((value) => {
    assert.deepEqual(
        classifyTxPower(
            value,
            fixtures.profiles[
                "xgsponst2001-a01"
            ]
        ),
        [
            "UNKNOWN",
            "unknown",
        ]
    );
});

console.log(
    `${fixtures.cases.length + 7} JavaScript TX classification cases passed`
);
