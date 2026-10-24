"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "../static/trusted_browsers.js"),
    "utf8"
);

const currentId = "a".repeat(64);
const otherId = "b".repeat(64);

function element(tag = "div") {
    const listeners = {};

    return {
        tag,
        className: "",
        textContent: "",
        disabled: false,
        children: [],
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        replaceChildren(...children) {
            this.children = [...children];
        },
        addEventListener(type, callback) {
            listeners[type] = callback;
        },
        async click() {
            if (listeners.click) {
                return listeners.click();
            }
        },
    };
}

function setup(confirmResult = true) {
    const list = element();
    const status = element();
    const refresh = element("button");
    const calls = [];
    const redirects = [];

    let domReady;
    let sessions = [
        {
            id: currentId,
            remembered: true,
            browser_label:
                "Firefox <img src=x onerror=alert(1)>",
            expires_at: 2000000000,
        },
        {
            id: otherId,
            remembered: false,
            browser_label: "Other browser",
            expires_at: 2000000000,
        },
    ];

    const document = {
        addEventListener(type, callback) {
            assert.equal(type, "DOMContentLoaded");
            domReady = callback;
        },
        getElementById(id) {
            return {
                trustedBrowserList: list,
                trustedStatus: status,
                refreshSessions: refresh,
            }[id] || null;
        },
        createElement(tag) {
            return element(tag);
        },
    };

    const window = {
        async fetch(url, options = {}) {
            calls.push({url, options});

            if (url === "/api/browser-session") {
                return {
                    ok: true,
                    json: async () => ({id: currentId}),
                };
            }

            if (url === "/api/browser-sessions") {
                return {
                    ok: true,
                    json: async () => sessions,
                };
            }

            if (
                url.startsWith("/api/browser-sessions/") &&
                options.method === "DELETE"
            ) {
                const id = url.split("/").pop();
                sessions = sessions.filter(
                    session => session.id !== id
                );

                return {
                    ok: true,
                    json: async () => ({revoked: true}),
                };
            }

            throw new Error("Unexpected endpoint: " + url);
        },
        confirm() {
            return confirmResult;
        },
        location: {
            replace(url) {
                redirects.push(url);
            },
        },
    };

    vm.runInNewContext(source, {
        document,
        window,
        Date,
        Number,
        encodeURIComponent,
    });

    return {
        list,
        status,
        refresh,
        calls,
        redirects,
        start() {
            domReady();
        },
    };
}

async function settle() {
    await new Promise(resolve => setImmediate(resolve));
}

async function run() {
    {
        const app = setup();
        app.start();
        await settle();

        assert.equal(app.list.children.length, 2);
        assert.equal(
            app.status.textContent,
            "2 active session(s)"
        );

        const first = app.list.children[0];
        const second = app.list.children[1];

        assert.equal(
            first.children[0].children[0].textContent,
            "This browser"
        );

        assert.equal(
            second.children[0].children[0].textContent,
            "Other browser"
        );

        assert.equal(
            first.children[0].children[1].textContent,
            "Firefox <img src=x onerror=alert(1)>"
        );

        console.log(
            "PASS: Current browser identified and labels rendered as text"
        );
    }

    {
        const app = setup();
        app.start();
        await settle();

        const other = app.list.children[1];
        await other.children[1].click();

        assert.ok(app.calls.some(
            call =>
                call.url ===
                "/api/browser-sessions/" + otherId &&
                call.options.method === "DELETE"
        ));

        assert.equal(app.list.children.length, 1);
        assert.equal(app.redirects.length, 0);

        console.log(
            "PASS: Other browser revoked without logging out current browser"
        );
    }

    {
        const app = setup();
        app.start();
        await settle();

        const current = app.list.children[0];
        await current.children[1].click();

        assert.ok(app.calls.some(
            call =>
                call.url ===
                "/api/browser-sessions/" + currentId &&
                call.options.method === "DELETE"
        ));

        assert.deepEqual(app.redirects, ["/login"]);

        console.log(
            "PASS: Current browser revocation redirects to login"
        );
    }

    {
        const app = setup(false);
        app.start();
        await settle();

        await app.list.children[1].children[1].click();

        assert.equal(
            app.calls.filter(
                call => call.options.method === "DELETE"
            ).length,
            0
        );

        console.log(
            "PASS: Revocation requires confirmation"
        );
    }
}

run().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
