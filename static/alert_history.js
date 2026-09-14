const ALERT_HISTORY_PAGE_SIZE = 25;

let alertHistoryOffset = 0;
let alertHistoryTotal = 0;


function formatHistoryAlertTime(ts) {
    if (!ts) {
        return "Unknown time";
    }

    const date = new Date(ts);

    if (Number.isNaN(date.getTime())) {
        return ts;
    }

    return date.toLocaleString();
}


function renderAlertHistory(events) {
    const list = document.getElementById(
        "historyAlertsList"
    );

    if (!list) {
        return;
    }

    if (!Array.isArray(events)) {
        events = [];
    }

    if (events.length === 0) {
        list.innerHTML = `
            <div class="alerts-empty">
                No alert events have been recorded.
            </div>
        `;

        return;
    }

    const rows = events.map((event) => {
        const allowedSeverities = new Set([
            "info",
            "warning",
            "critical",
        ]);

        const candidateSeverity = String(
            event?.severity || "warning"
        ).toLowerCase();

        const severity = allowedSeverities.has(
            candidateSeverity
        )
            ? candidateSeverity
            : "warning";

        const article = document.createElement(
            "article"
        );
        article.className = `alert-row ${severity}`;

        const main = document.createElement("div");
        main.className = "alert-main";

        const severityElement = document.createElement(
            "span"
        );
        severityElement.className = "alert-severity";
        severityElement.textContent = severity.toUpperCase();

        const message = document.createElement("strong");
        message.className = "alert-message";
        message.textContent = String(
            event?.message || "Alert"
        );

        const time = document.createElement("span");
        time.className = "alert-time";
        time.textContent = String(
            formatHistoryAlertTime(event?.ts)
        );

        main.append(
            severityElement,
            message,
            time
        );
        article.append(main);

        return article;
    });

    list.replaceChildren(...rows);
}


function updateAlertHistoryControls(eventCount) {
    const summary = document.getElementById(
        "historyAlertSummary"
    );

    const pageStatus = document.getElementById(
        "historyPageStatus"
    );

    const previous = document.getElementById(
        "historyPrevious"
    );

    const next = document.getElementById(
        "historyNext"
    );

    const totalPages = Math.max(
        1,
        Math.ceil(
            alertHistoryTotal /
            ALERT_HISTORY_PAGE_SIZE
        )
    );

    const currentPage =
        Math.floor(
            alertHistoryOffset /
            ALERT_HISTORY_PAGE_SIZE
        ) + 1;

    if (summary) {
        if (alertHistoryTotal === 0) {
            summary.textContent =
                "No stored alerts";

            summary.className =
                "advanced-status good";
        } else {
            summary.textContent =
                `${alertHistoryTotal} stored alert${
                    alertHistoryTotal === 1
                        ? ""
                        : "s"
                }`;

            summary.className =
                "advanced-status warn";
        }
    }

    if (pageStatus) {
        if (alertHistoryTotal === 0) {
            pageStatus.textContent =
                "Page 1 of 1";
        } else {
            const first =
                alertHistoryOffset + 1;

            const last =
                alertHistoryOffset +
                eventCount;

            pageStatus.textContent =
                `Page ${currentPage} of ${totalPages} · `
                + `${first}-${last} of ${alertHistoryTotal}`;
        }
    }

    if (previous) {
        previous.disabled =
            alertHistoryOffset === 0;
    }

    if (next) {
        next.disabled =
            alertHistoryOffset +
            eventCount >=
            alertHistoryTotal;
    }
}


async function loadAlertHistory() {
    const list = document.getElementById(
        "historyAlertsList"
    );

    const summary = document.getElementById(
        "historyAlertSummary"
    );

    try {
        const [
            eventsResponse,
            countResponse,
        ] = await Promise.all([
            fetch(
                `/api/alerts?limit=${ALERT_HISTORY_PAGE_SIZE}`
                + `&offset=${alertHistoryOffset}`,
                {
                    cache: "no-store",
                }
            ),
            fetch(
                "/api/alerts/count",
                {
                    cache: "no-store",
                }
            ),
        ]);

        if (!eventsResponse.ok) {
            throw new Error(
                `Alerts HTTP ${eventsResponse.status}`
            );
        }

        if (!countResponse.ok) {
            throw new Error(
                `Count HTTP ${countResponse.status}`
            );
        }

        const events =
            await eventsResponse.json();

        const countData =
            await countResponse.json();

        alertHistoryTotal =
            Number(countData.count) || 0;

        if (
            alertHistoryTotal > 0 &&
            alertHistoryOffset >= alertHistoryTotal
        ) {
            alertHistoryOffset =
                Math.max(
                    0,
                    (
                        Math.ceil(
                            alertHistoryTotal /
                            ALERT_HISTORY_PAGE_SIZE
                        ) - 1
                    ) *
                    ALERT_HISTORY_PAGE_SIZE
                );

            return loadAlertHistory();
        }

        renderAlertHistory(events);

        updateAlertHistoryControls(
            Array.isArray(events)
                ? events.length
                : 0
        );

    } catch (error) {
        if (summary) {
            summary.textContent =
                "Alerts unavailable";

            summary.className =
                "advanced-status bad";
        }

        if (list) {
            list.innerHTML = `
                <div class="alerts-empty">
                    Unable to load alert history.
                </div>
            `;
        }
    }
}


const historyPrevious =
    document.getElementById(
        "historyPrevious"
    );

if (historyPrevious) {
    historyPrevious.addEventListener(
        "click",
        () => {
            alertHistoryOffset =
                Math.max(
                    0,
                    alertHistoryOffset -
                    ALERT_HISTORY_PAGE_SIZE
                );

            loadAlertHistory();
        }
    );
}


const historyNext =
    document.getElementById(
        "historyNext"
    );

if (historyNext) {
    historyNext.addEventListener(
        "click",
        () => {
            if (
                alertHistoryOffset +
                ALERT_HISTORY_PAGE_SIZE >=
                alertHistoryTotal
            ) {
                return;
            }

            alertHistoryOffset +=
                ALERT_HISTORY_PAGE_SIZE;

            loadAlertHistory();
        }
    );
}


loadAlertHistory();
