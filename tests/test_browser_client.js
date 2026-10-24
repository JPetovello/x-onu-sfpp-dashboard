"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "../static/browser_client.js"),
    "utf8"
);

const origin = "https://xonu.home.arpa";
const csrf = "a".repeat(64);

function setup(responder) {
    const requests = [];
    const redirects = [];
    let domReady = null;
    let logoutClick = null;

    const logout = {
        disabled: false,
        addEventListener(event, callback) {
            assert.equal(event, "click");
            logoutClick = callback;
        },
    };

    const nativeFetch = async (input, options = {}) => {
        requests.push({ input, options });

        if (responder) {
            return responder(input, options);
        }

        if (input === "/api/browser-session") {
            return {
                ok: true,
                status: 200,
                json: async () => ({ csrf_token: csrf }),
            };
        }

        return { ok: true, status: 200 };
    };

    const window = {
        fetch: nativeFetch,
        location: {
            pathname: "/alerts-settings",
            href: `${origin}/alerts-settings`,
            origin,
            replace(destination) {
                redirects.push(destination);
            },
        },
        alert(message) {
            throw new Error(`Unexpected alert: ${message}`);
        },
    };

    const document = {
        addEventListener(event, callback) {
            assert.equal(event, "DOMContentLoaded");
            domReady = callback;
        },
        getElementById(id) {
            return id === "xonuLogoutButton"
                ? logout
                : null;
        },
    };

    vm.runInNewContext(source, {
        window,
        document,
        URL,
        Headers,
        Request,
        Set,
        String,
        encodeURIComponent,
    }, {
        filename: "browser_client.js",
    });

    return {
        window,
        requests,
        redirects,
        triggerDomReady() {
            domReady();
        },
        async clickLogout() {
            return logoutClick();
        },
    };
}

async function run() {
    {
        const app = setup();

        const response = await app.window.fetch(
            "/api/notification-config"
        );

        assert.equal(response.status, 200);
        assert.equal(app.requests.length, 1);

        console.log(
            "PASS: Read-only API requests"
        );
    }

    {
        const app = setup();

        for (const url of [
            "/api/alert-config",
            "/api/notification-config",
        ]) {
            await app.window.fetch(url, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: "{}",
            });
        }

        assert.equal(app.requests.length, 3);
        assert.equal(
            app.requests[0].input,
            "/api/browser-session"
        );

        for (const request of app.requests.slice(1)) {
            assert.equal(
                request.options.headers.get("X-CSRF-Token"),
                csrf
            );
            assert.equal(
                request.options.headers.get("Content-Type"),
                "application/json"
            );
            assert.equal(
                request.options.credentials,
                "same-origin"
            );
        }

        console.log(
            "PASS: API writes receive CSRF protection"
        );
    }

    {
        const app = setup();

        await app.window.fetch(
            "https://elsewhere.example/api/change",
            { method: "PUT" }
        );

        assert.equal(app.requests.length, 1);

        console.log(
            "PASS: CSRF tokens not sent to external origins"
        );
    }

    {
        const app = setup(async input => {
            if (input === "/api/protected") {
                return { ok: false, status: 401 };
            }

            throw new Error("Unexpected request");
        });

        await app.window.fetch("/api/protected");

        assert.deepEqual(app.redirects, [
            "/login?next=%2Falerts-settings",
        ]);

        console.log(
            "PASS: Unauthorized requests redirect to login"
        );
    }

    {
        const app = setup();

        app.triggerDomReady();
        await app.clickLogout();

        assert.deepEqual(app.redirects, ["/login"]);

        assert.equal(
            app.requests[0].input,
            "/api/browser-session"
        );

        assert.equal(
            app.requests[1].input,
            "/api/browser-logout"
        );

        assert.equal(
            app.requests[1].options.headers.get(
                "X-CSRF-Token"
            ),
            csrf
        );

        console.log(
            "PASS: Logout is CSRF-protected"
        );
    }
}

run().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
