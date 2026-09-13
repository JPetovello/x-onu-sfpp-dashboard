const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


function fakeElement(value = "") {
    const listeners = {};

    return {
        value,
        textContent: "",
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

elements.alertTxLowAlarm.value = "1.50";
elements.alertTxLowAlarm.trigger("input");

assert.equal(
    elements.alertTxProfile.value,
    "custom"
);

console.log(
    "TX threshold edits select the Custom profile"
);
