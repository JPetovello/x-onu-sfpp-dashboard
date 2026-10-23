"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(
    "static/thermal_gauges.js", "utf8"
);

const elements = {};
const observers = [];

for (const [prefix, name] of [
    ["optic", "Optical"],
    ["cpu1", "CPU 1"],
    ["cpu2", "CPU 2"]
]) {
    const tile = {dataset: {}};
    const style = {setProperty() {}};

    elements[`${prefix}Temp`] = {textContent: "-"};
    elements[`${prefix}Level`] = {textContent: ""};
    elements[`${prefix}Meter`] = {
        closest: () => tile,
        style,
        setAttribute(key, value) {
            this[key] = value;
        }
    };

    elements[`${prefix}Tile`] = tile;
}

class FakeObserver {
    constructor(callback) {
        this.callback = callback;
    }
    observe(element) {
        observers.push({
            element,
            callback: this.callback
        });
    }
}

vm.runInNewContext(source, {
    document: {
        getElementById: id => elements[id] || null
    },
    MutationObserver: FakeObserver
});

function verify(prefix, value, expected) {
    const element = elements[`${prefix}Temp`];
    element.textContent = String(value);

    const observer = observers.find(
        item => item.element === element
    );

    assert.ok(observer);
    observer.callback();

    assert.equal(
        elements[`${prefix}Tile`].dataset.level,
        expected,
        `${prefix} at ${value}°C`
    );

    assert.equal(
        elements[`${prefix}Level`].textContent.toLowerCase(),
        expected
    );
}

for (const [value, level] of [
    [49.9, "optimal"],
    [50, "warm"],
    [59.9, "warm"],
    [60, "warning"],
    [69.9, "warning"],
    [70, "critical"],
    ["-", "unavailable"]
]) {
    verify("optic", value, level);
}

for (const prefix of ["cpu1", "cpu2"]) {
    for (const [value, level] of [
        [64.9, "optimal"],
        [65, "warm"],
        [74.9, "warm"],
        [75, "warning"],
        [84.9, "warning"],
        [85, "critical"],
        ["-", "unavailable"]
    ]) {
        verify(prefix, value, level);
    }
}

console.log(
    "PASS: Optical, CPU 1 and CPU 2 gauge boundary tests"
);
