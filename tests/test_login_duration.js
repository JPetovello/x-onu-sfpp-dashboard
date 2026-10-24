"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(
    "static/login.js",
    "utf8"
);

let ready;
let submit;
let change;
let submitted;
const redirects = [];

const elements = {
    loginForm: {
        addEventListener(type, callback) {
            if (type === "submit") submit = callback;
        },
    },
    loginSubmit: {
        disabled: false,
        textContent: "",
    },
    loginError: {
        hidden: true,
        textContent: "",
    },
    loginUsername: {
        value: "test-user",
    },
    loginPassword: {
        value: "test-password",
    },
    rememberBrowser: {
        checked: false,
        addEventListener(type, callback) {
            if (type === "change") change = callback;
        },
    },
    rememberDays: {
        value: "7",
        disabled: true,
    },
};

const document = {
    addEventListener(type, callback) {
        if (type === "DOMContentLoaded") ready = callback;
    },
    getElementById(id) {
        return elements[id] || null;
    },
};

const window = {
    location: {
        search: "",
        replace(url) {
            redirects.push(url);
        },
    },
};

async function fakeFetch(url, options) {
    assert.equal(url, "/api/browser-login");
    submitted = JSON.parse(options.body);

    return {
        ok: true,
        status: 200,
    };
}

vm.runInNewContext(source, {
    window,
    document,
    fetch: fakeFetch,
    URLSearchParams,
    Number,
});

async function run() {
    ready();

    assert.equal(elements.rememberDays.disabled, true);

    elements.rememberBrowser.checked = true;
    change();

    assert.equal(elements.rememberDays.disabled, false);

    elements.rememberDays.value = "30";

    await submit({
        preventDefault() {},
    });

    assert.equal(submitted.remember, true);
    assert.equal(submitted.remember_days, 30);
    assert.deepEqual(redirects, ["/"]);

    console.log(
        "PASS: Remembered-browser duration selector"
    );
    console.log(
        "PASS: 30-day duration submitted to backend"
    );
}

run().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
