(() => {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
        const form = document.getElementById("loginForm");
        const submit = document.getElementById("loginSubmit");
        const errorBox = document.getElementById("loginError");
        const username = document.getElementById("loginUsername");
        const password = document.getElementById("loginPassword");
        const remember = document.getElementById("rememberBrowser");
        const duration = document.getElementById("rememberDays");

        if (!form || !remember || !duration) {
            return;
        }

        duration.disabled = !remember.checked;

        remember.addEventListener("change", () => {
            duration.disabled = !remember.checked;
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            submit.disabled = true;
            submit.textContent = "Signing in...";
            errorBox.hidden = true;
            errorBox.textContent = "";

            try {
                const response = await fetch(
                    "/api/browser-login",
                    {
                        method: "POST",
                        credentials: "same-origin",
                        cache: "no-store",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            username: username.value,
                            password: password.value,
                            remember: remember.checked,
                            remember_days: Number(duration.value),
                        }),
                    }
                );

                if (response.ok) {
                    password.value = "";

                    const requested = new URLSearchParams(
                        window.location.search
                    ).get("next");

                    const safeDestination =
                        requested &&
                        /^\/(?!\/)[A-Za-z0-9/_-]*$/.test(
                            requested
                        ) &&
                        !requested.startsWith("/api/") &&
                        !requested.startsWith("/static/")
                            ? requested
                            : "/";

                    window.location.replace(safeDestination);
                    return;
                }

                if (response.status === 429) {
                    errorBox.textContent =
                        "Too many attempts. Try again in a few minutes.";
                } else {
                    errorBox.textContent =
                        "Sign-in failed. Check your credentials.";
                }
            } catch (_) {
                errorBox.textContent =
                    "Unable to contact the dashboard.";
            } finally {
                errorBox.hidden = !errorBox.textContent;
                submit.disabled = false;
                submit.textContent = "Sign in";
            }
        });
    });
})();
