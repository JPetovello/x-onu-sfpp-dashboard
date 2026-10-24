(() => {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
        const list = document.getElementById(
            "trustedBrowserList"
        );
        const status = document.getElementById(
            "trustedStatus"
        );
        const refresh = document.getElementById(
            "refreshSessions"
        );

        if (!list || !status || !refresh) {
            return;
        }

        function formatDate(timestamp) {
            if (
                !Number.isSafeInteger(timestamp) ||
                timestamp < 0
            ) {
                return "Unknown";
            }

            const date = new Date(timestamp * 1000);

            return Number.isNaN(date.getTime())
                ? "Unknown"
                : date.toLocaleString();
        }

        function makeText(tag, className, content) {
            const element = document.createElement(tag);
            element.className = className;
            element.textContent = content;
            return element;
        }

        async function loadSessions() {
            refresh.disabled = true;
            status.textContent = "Loading active sessions…";
            list.replaceChildren();

            try {
                const [currentResponse, sessionsResponse] =
                    await Promise.all([
                        window.fetch("/api/browser-session"),
                        window.fetch("/api/browser-sessions"),
                    ]);

                if (
                    !currentResponse.ok ||
                    !sessionsResponse.ok
                ) {
                    throw new Error("Session request failed");
                }

                const current = await currentResponse.json();
                const sessions = await sessionsResponse.json();

                if (
                    !current ||
                    typeof current.id !== "string" ||
                    !Array.isArray(sessions)
                ) {
                    throw new Error("Invalid session response");
                }

                status.textContent =
                    sessions.length + " active session(s)";

                for (const session of sessions) {
                    const isCurrent = session.id === current.id;
                    const card = document.createElement("div");
                    card.className = "trusted-session";

                    const details = document.createElement("div");
                    details.className =
                        "trusted-session-details";

                    details.appendChild(makeText(
                        "strong",
                        "trusted-session-title",
                        isCurrent
                            ? "This browser"
                            : "Other browser"
                    ));

                    details.appendChild(makeText(
                        "span",
                        "trusted-session-meta",
                        session.browser_label ||
                            "Browser not identified"
                    ));

                    details.appendChild(makeText(
                        "span",
                        "trusted-session-meta",
                        (
                            session.remembered
                                ? "Remembered session"
                                : "Browser session"
                        ) +
                        " · Expires: " +
                        formatDate(session.expires_at)
                    ));

                    card.appendChild(details);

                    const revoke = document.createElement(
                        "button"
                    );
                    revoke.type = "button";
                    revoke.textContent = isCurrent
                        ? "Revoke this browser"
                        : "Revoke access";

                    revoke.addEventListener(
                        "click",
                        async () => {
                            const message = isCurrent
                                ? "Sign out this browser?"
                                : "Revoke this browser session?";

                            if (!window.confirm(message)) {
                                return;
                            }

                            revoke.disabled = true;

                            try {
                                const response = await window.fetch(
                                    "/api/browser-sessions/" +
                                        encodeURIComponent(session.id),
                                    { method: "DELETE" }
                                );

                                if (!response.ok) {
                                    throw new Error(
                                        "Revocation failed"
                                    );
                                }

                                if (isCurrent) {
                                    window.location.replace(
                                        "/login"
                                    );
                                    return;
                                }

                                await loadSessions();
                            } catch (_) {
                                revoke.disabled = false;
                                status.textContent =
                                    "Unable to revoke session.";
                            }
                        }
                    );

                    card.appendChild(revoke);
                    list.appendChild(card);
                }
            } catch (_) {
                status.textContent =
                    "Unable to load active sessions.";
            } finally {
                refresh.disabled = false;
            }
        }

        refresh.addEventListener("click", loadSessions);
        loadSessions();
    });
})();
