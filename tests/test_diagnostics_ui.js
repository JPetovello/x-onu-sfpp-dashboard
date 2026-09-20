const assert =
    require("node:assert/strict");

const fs =
    require("node:fs");

const path =
    require("node:path");

const vm =
    require("node:vm");


function fakeElement(
    tagName = "div"
) {
    const listeners = {};

    return {
        tagName:
            tagName.toUpperCase(),

        childNodes: [],

        className: "",

        textContent: "",

        disabled: false,

        dataset: {},

        append(...children) {
            this.childNodes.push(
                ...children
            );
        },

        replaceChildren(...children) {
            this.childNodes =
                children;
        },

        addEventListener(
            name,
            callback
        ) {
            listeners[name] =
                callback;
        },

        click() {
            if (listeners.click) {
                return listeners.click();
            }
        },
    };
}


function createHarness(
    fetchImpl
) {
    const overviewButton =
        fakeElement("button");

    overviewButton.dataset
        .diagnosticsProfile =
        "overview";


    const countersButton =
        fakeElement("button");

    countersButton.dataset
        .diagnosticsProfile =
        "counters";


    const elements = {
        diagnosticsRun:
            fakeElement("button"),

        diagnosticsStatus:
            fakeElement("p"),

        diagnosticsResults:
            fakeElement("div"),

        diagnosticsProfileLabel:
            fakeElement("span"),
    };


    const fetchCalls = [];


    const context = {
        console,

        fetch(
            url,
            options
        ) {
            fetchCalls.push({
                url,
                options,
            });

            return fetchImpl(
                url,
                options
            );
        },

        document: {
            getElementById(id) {
                return elements[id]
                    || null;
            },

            querySelectorAll(selector) {
                if (
                    selector
                    ===
                    "[data-diagnostics-profile]"
                ) {
                    return [
                        overviewButton,
                        countersButton,
                    ];
                }

                return [];
            },

            createElement(tagName) {
                return fakeElement(
                    tagName
                );
            },
        },
    };


    vm.createContext(
        context
    );


    vm.runInContext(
        fs.readFileSync(
            path.join(
                __dirname,
                "../static/diagnostics.js"
            ),
            "utf8"
        ),
        context
    );


    return {
        context,
        elements,
        fetchCalls,
        overviewButton,
        countersButton,
    };
}


{
    const harness =
        createHarness(
            () => {
                throw new Error(
                    "fetch must not run on load"
                );
            }
        );

    assert.equal(
        harness.fetchCalls.length,
        0
    );

    assert.equal(
        harness.overviewButton
            .className,
        "diagnostics-profile-button active"
    );
}


{
    const harness =
        createHarness(
            () => {
                throw new Error(
                    "unused"
                );
            }
        );

    const malicious =
        "<img src=x onerror=alert(1)>";

    harness.context
        .xonuDiagnostics
        .renderDiagnosticSections({
            STATUS: malicious,
        });


    const results =
        harness.elements
            .diagnosticsResults;

    assert.equal(
        results.childNodes.length,
        1
    );

    const article =
        results.childNodes[0];

    assert.equal(
        article.tagName,
        "ARTICLE"
    );

    assert.equal(
        article.childNodes[0]
            .textContent,
        "Status"
    );

    assert.equal(
        article.childNodes[1]
            .textContent,
        malicious
    );

    assert.equal(
        article.childNodes[1]
            .childNodes.length,
        0
    );
}


(async () => {
    const harness =
        createHarness(
            async () => ({
                ok: true,
                status: 200,

                async json() {
                    return {
                        enabled: true,
                        online: true,
                        profile:
                            "counters",
                        error: null,
                        sections: {
                            PLOAM_UPSTREAM:
                                "Counter : 42",
                        },
                    };
                },
            })
        );


    assert.equal(
        harness.context
            .xonuDiagnostics
            .setSelectedProfile(
                "counters"
            ),
        true
    );


    await harness.context
        .xonuDiagnostics
        .runDiagnostics();


    assert.equal(
        harness.fetchCalls.length,
        1
    );

    assert.equal(
        harness.fetchCalls[0].url,
        "/api/diagnostics"
        + "?profile=counters"
    );

    assert.equal(
        harness.elements
            .diagnosticsStatus
            .textContent,
        "Counters diagnostics complete."
    );

    assert.equal(
        harness.elements
            .diagnosticsStatus
            .className,
        "diagnostics-status good"
    );

    assert.equal(
        harness.elements
            .diagnosticsProfileLabel
            .textContent,
        "Counters"
    );


    const article =
        harness.elements
            .diagnosticsResults
            .childNodes[0];

    assert.equal(
        article.childNodes[0]
            .textContent,
        "PLOAM Upstream Counters"
    );

    assert.equal(
        article.childNodes[1]
            .textContent,
        "Counter : 42"
    );
})()
.then(async () => {
    const harness =
        createHarness(
            async () => ({
                ok: true,
                status: 200,

                async json() {
                    return {
                        enabled: true,
                        online: false,
                        profile:
                            "overview",
                        error:
                            "Synthetic SSH failure",
                        sections: {},
                    };
                },
            })
        );


    await harness.context
        .xonuDiagnostics
        .runDiagnostics();


    assert.equal(
        harness.elements
            .diagnosticsStatus
            .className,
        "diagnostics-status bad"
    );

    assert.equal(
        harness.elements
            .diagnosticsStatus
            .textContent,
        "Synthetic SSH failure"
    );

    assert.equal(
        harness.elements
            .diagnosticsRun
            .disabled,
        false
    );
})
.then(() => {
    console.log(
        "Diagnostics UI is manual, safe, and profile-scoped"
    );
})
.catch(error => {
    console.error(error);
    process.exitCode = 1;
});
