(() => {
    const allowedProfiles =
        new Set([
            "overview",
            "counters",
            "datapath",
            "ppv4",
            "burst"
        ]);


    const sectionLabels = {
        STATUS: "Status",
        CAPABILITY:
            "Capability and Configuration",
        LAN:
            "LAN Interface Status & Counters",
        ALARMS:
            "Active Alarms",
        OPTICAL_STATUS:
            "Optical Interface Status",
        OPTICAL_INFO:
            "Optical Interface Info",
        ALLOCATION_COUNTERS:
            "Allocation Counters",
        PLOAM_DOWNSTREAM:
            "PLOAM Downstream Counters",
        PLOAM_UPSTREAM:
            "PLOAM Upstream Counters",
        CQM_OFSC: "CQM ofsc",
        CQM_QUEUE_MAP: "CQM Queue Map",
        DATAPATH_PORTS: "Datapath Ports",
        DATAPATH_QOS: "Datapath QOS",
        PPV4_BUFFER_MGR_HW_STATS:
            "PPv4 Buffer MGR HW Stats",
        PPV4_QOS_QUEUE_PPS:
            "PPv4 QoS Queue PPS",
        PPV4_QUEUES_STATS:
            "PPv4 Queues Stats",
        PPV4_TREE: "PPv4 Tree",
        PPV4_QSTATS: "PPv4 QStats",
        DEBUG_BURST_PROFILE:
            "Debug Burst Profile",
    };


    const profileLabels = {
        overview: "Overview",
        counters: "Counters",
        datapath: "Datapath",
        ppv4: "PPv4",
        burst: "Burst Profile",
    };


    const profileButtons = Array.from(
        document.querySelectorAll(
            "[data-diagnostics-profile]"
        )
    );


    const runButton =
        document.getElementById(
            "diagnosticsRun"
        );


    const statusElement =
        document.getElementById(
            "diagnosticsStatus"
        );


    const resultsElement =
        document.getElementById(
            "diagnosticsResults"
        );


    const profileLabelElement =
        document.getElementById(
            "diagnosticsProfileLabel"
        );


    let selectedProfile =
        "overview";


    let running =
        false;


    function setStatus(
        text,
        level=""
    ) {
        if (!statusElement) {
            return;
        }

        statusElement.textContent =
            text;

        statusElement.className =
            "diagnostics-status";

        if (level) {
            statusElement.className +=
                ` ${level}`;
        }
    }


    function setSelectedProfile(
        profile
    ) {
        if (
            !allowedProfiles.has(
                profile
            )
        ) {
            return false;
        }

        selectedProfile =
            profile;

        profileButtons.forEach(
            button => {
                const active =
                    button.dataset
                        .diagnosticsProfile
                    === profile;

                button.className =
                    "diagnostics-profile-button"
                    + (
                        active
                            ? " active"
                            : ""
                    );

                button.ariaPressed =
                    active
                        ? "true"
                        : "false";
            }
        );

        return true;
    }


    function setBusy(
        busy
    ) {
        running =
            busy;

        if (resultsElement) {
            resultsElement.ariaBusy =
                busy
                    ? "true"
                    : "false";
        }

        if (runButton) {
            runButton.disabled =
                busy;

            runButton.textContent =
                busy
                    ? "Running…"
                    : "Run Diagnostics";
        }

        profileButtons.forEach(
            button => {
                button.disabled =
                    busy;
            }
        );
    }


    function emptyResults(
        message
    ) {
        if (!resultsElement) {
            return;
        }

        const empty =
            document.createElement(
                "p"
            );

        empty.className =
            "diagnostics-empty";

        empty.textContent =
            message;

        resultsElement.replaceChildren(
            empty
        );
    }


    function renderDiagnosticSections(
        sections
    ) {
        if (!resultsElement) {
            return;
        }

        const entries =
            Object.entries(
                sections || {}
            );

        if (entries.length === 0) {
            emptyResults(
                "No diagnostic output was returned."
            );
            return;
        }

        const nodes = [];

        entries.forEach(
            ([name, output]) => {
                const article =
                    document.createElement(
                        "article"
                    );

                article.className =
                    "diagnostics-section";


                const heading =
                    document.createElement(
                        "h3"
                    );

                heading.textContent =
                    sectionLabels[name]
                    || name.replaceAll(
                        "_",
                        " "
                    );


                const pre =
                    document.createElement(
                        "pre"
                    );

                const outputText =
                    output == null
                        ? ""
                        : String(output);

                const outputIsEmpty =
                    outputText.trim() === "";

                pre.className =
                    outputIsEmpty
                        ? "diagnostics-output diagnostics-output-empty"
                        : "diagnostics-output";

                pre.textContent =
                    outputIsEmpty
                        ? "No output returned."
                        : outputText;


                article.append(
                    heading,
                    pre
                );

                nodes.push(
                    article
                );
            }
        );

        resultsElement.replaceChildren(
            ...nodes
        );
    }


    async function runDiagnostics() {
        if (
            running
            || !allowedProfiles.has(
                selectedProfile
            )
        ) {
            return;
        }

        const label =
            profileLabels[
                selectedProfile
            ];


        setBusy(
            true
        );

        setStatus(
            `Running ${label} diagnostics…`,
            "warn"
        );

        emptyResults(
            "Waiting for ONT diagnostic output…"
        );


        try {
            const response =
                await fetch(
                    "/api/diagnostics",
                    {
                        method: "POST",
                        headers: {
                            Accept:
                                "application/json",
                            "Content-Type":
                                "application/json",
                        },
                        body: JSON.stringify({
                            profile:
                                selectedProfile,
                        }),
                    }
                );


            let payload = {};

            try {
                payload =
                    await response.json();
            } catch (error) {
                throw new Error(
                    "The server returned an invalid response"
                );
            }


            if (!response.ok) {
                if (response.status === 409) {
                    setStatus(
                        payload
                        && payload.error
                        || "Diagnostics are already running.",
                        "warn"
                    );

                    emptyResults(
                        "Wait for the active diagnostic request to finish, then try again."
                    );

                    return;
                }

                throw new Error(
                    payload
                    && payload.error
                    || (
                        "Diagnostics request failed "
                        + `(${response.status})`
                    )
                );
            }


            if (
                !payload
                || typeof payload !== "object"
                || typeof payload.enabled !== "boolean"
                || typeof payload.online !== "boolean"
                || !payload.sections
                || typeof payload.sections !== "object"
                || Array.isArray(payload.sections)
            ) {
                throw new Error(
                    "The server returned an invalid response"
                );
            }


            if (!payload.enabled) {
                setStatus(
                    payload.error
                    || "Advanced SSH telemetry is disabled.",
                    "warn"
                );

                emptyResults(
                    "Diagnostics are unavailable while SSH telemetry is disabled."
                );

                return;
            }


            if (!payload.online) {
                setStatus(
                    payload.error
                    || "ONT diagnostics are unavailable.",
                    "bad"
                );

                emptyResults(
                    "No diagnostic output was returned."
                );

                return;
            }


            renderDiagnosticSections(
                payload.sections
            );


            if (
                profileLabelElement
            ) {
                profileLabelElement
                    .textContent =
                    label;
            }


            setStatus(
                `${label} diagnostics complete.`,
                "good"
            );

        } catch (error) {
            setStatus(
                "Diagnostics failed: "
                + (
                    error
                    && error.message
                        ? error.message
                        : "Unknown error"
                ),
                "bad"
            );

            emptyResults(
                "No diagnostic output was returned."
            );

        } finally {
            setBusy(
                false
            );
        }
    }


    profileButtons.forEach(
        button => {
            button.addEventListener(
                "click",
                () => {
                    setSelectedProfile(
                        button.dataset
                            .diagnosticsProfile
                    );
                }
            );
        }
    );


    if (runButton) {
        runButton.addEventListener(
            "click",
            () => {
                runDiagnostics();
            }
        );
    }


    setSelectedProfile(
        selectedProfile
    );


    globalThis.xonuDiagnostics = {
        renderDiagnosticSections,
        runDiagnostics,
        setSelectedProfile,
    };
})();
