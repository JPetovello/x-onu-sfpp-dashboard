const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


function fakeElement(tagName = "div") {
    const listeners = {};

    return {
        tagName: tagName.toUpperCase(),
        childNodes: [],
        className: "",
        textContent: "",
        disabled: false,
        append(...children) {
            this.childNodes.push(...children);
        },
        replaceChildren(...children) {
            this.childNodes = children;
        },
        addEventListener(name, callback) {
            listeners[name] = callback;
        },
    };
}


function createContext(elements) {
    return {
        console,
        structuredClone,
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
            getElementById(id) {
                return elements[id] || null;
            },
            querySelectorAll() {
                return [];
            },
            createElement(tagName) {
                return fakeElement(tagName);
            },
        },
    };
}


function loadScript(name, context) {
    vm.createContext(context);
    vm.runInContext(
        fs.readFileSync(
            path.join(__dirname, `../static/${name}`),
            "utf8"
        ),
        context
    );
}


function assertSafeRow(list, expectedMessage) {
    assert.equal(list.childNodes.length, 1);

    const article = list.childNodes[0];
    const main = article.childNodes[0];
    const severity = main.childNodes[0];
    const message = main.childNodes[1];
    const time = main.childNodes[2];

    assert.equal(article.tagName, "ARTICLE");
    assert.equal(article.className, "alert-row warning");
    assert.equal(severity.textContent, "WARNING");
    assert.equal(message.textContent, expectedMessage);
    assert.match(time.textContent, /<svg onload=alert\(3\)>/);
    assert.equal(message.childNodes.length, 0);
}


const maliciousEvent = {
    severity: "critical\" onclick=alert(1)",
    message: "<img src=x onerror=alert(2)>",
    ts: "<svg onload=alert(3)>",
};


{
    const list = fakeElement();
    const summary = fakeElement();
    const elements = {};
    const context = createContext(elements);

    loadScript("alerts.js", context);

    elements.alertsList = list;
    elements.alertSummary = summary;
    context.renderAlerts([maliciousEvent]);

    assertSafeRow(list, maliciousEvent.message);

    context.renderAlerts([
        {
            severity: "critical",
            message: "Normal alert",
            ts: "2026-09-14T00:00:00+00:00",
        },
    ]);

    assert.equal(
        list.childNodes[0].className,
        "alert-row critical"
    );
    assert.equal(
        list.childNodes[0].childNodes[0]
            .childNodes[1].textContent,
        "Normal alert"
    );
}


{
    const list = fakeElement();
    const elements = {};
    const context = createContext(elements);

    loadScript("alert_history.js", context);

    elements.historyAlertsList = list;
    context.renderAlertHistory([maliciousEvent]);

    assertSafeRow(list, maliciousEvent.message);

    context.renderAlertHistory([
        {
            severity: "info",
            message: "Normal history event",
            ts: "2026-09-14T00:00:00+00:00",
        },
    ]);

    assert.equal(
        list.childNodes[0].className,
        "alert-row info"
    );
    assert.equal(
        list.childNodes[0].childNodes[0]
            .childNodes[1].textContent,
        "Normal history event"
    );
}


console.log(
    "Recent and historical alert rendering is safe"
);
