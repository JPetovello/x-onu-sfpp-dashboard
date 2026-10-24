(() => {
    "use strict";

    const nativeFetch = window.fetch.bind(window);
    const protectedMethods = new Set([
        "POST", "PUT", "PATCH", "DELETE"
    ]);

    let csrfPromise = null;
    let redirecting = false;

    function goToLogin() {
        if (redirecting) {
            return;
        }

        redirecting = true;

        const destination = window.location.pathname;
        window.location.replace(
            "/login?next=" + encodeURIComponent(destination)
        );
    }

    async function getCsrfToken() {
        if (!csrfPromise) {
            csrfPromise = (async () => {
                const response = await nativeFetch(
                    "/api/browser-session",
                    {
                        credentials: "same-origin",
                        cache: "no-store",
                    }
                );

                if (response.status === 401) {
                    goToLogin();
                }

                if (!response.ok) {
                    throw new Error(
                        "Unable to verify browser session"
                    );
                }

                const data = await response.json();
                const token = data && data.csrf_token;

                if (
                    typeof token !== "string" ||
                    !/^[a-f0-9]{64}$/.test(token)
                ) {
                    throw new Error("Invalid CSRF token");
                }

                return token;
            })().catch((error) => {
                csrfPromise = null;
                throw error;
            });
        }

        return csrfPromise;
    }

    window.fetch = async function protectedFetch(
        input,
        options = {}
    ) {
        const requestObject =
            typeof Request === "function" &&
            input instanceof Request;

        const target = new URL(
            requestObject ? input.url : input,
            window.location.href
        );

        const method = String(
            options.method ||
            (requestObject ? input.method : "GET")
        ).toUpperCase();

        const isLocalApi =
            target.origin === window.location.origin &&
            target.pathname.startsWith("/api/");

        if (!isLocalApi) {
            return nativeFetch(input, options);
        }

        let requestOptions = options;

        if (protectedMethods.has(method)) {
            const token = await getCsrfToken();

            const headers = new Headers(
                requestObject ? input.headers : undefined
            );

            if (options.headers) {
                new Headers(options.headers).forEach(
                    (value, key) => headers.set(key, value)
                );
            }

            headers.set("X-CSRF-Token", token);

            requestOptions = {
                ...options,
                credentials: "same-origin",
                headers,
            };
        }

        const response = await nativeFetch(
            input,
            requestOptions
        );

        if (response.status === 401) {
            goToLogin();
        }

        return response;
    };

    document.addEventListener(
        "DOMContentLoaded",
        () => {
            const logout = document.getElementById(
                "xonuLogoutButton"
            );

            if (!logout) {
                return;
            }

            logout.addEventListener(
                "click",
                async () => {
                    logout.disabled = true;

                    try {
                        const response = await window.fetch(
                            "/api/browser-logout",
                            { method: "POST" }
                        );

                        if (!response.ok) {
                            throw new Error(
                                "Logout request failed"
                            );
                        }

                        csrfPromise = null;
                        window.location.replace("/login");
                    } catch (_) {
                        logout.disabled = false;
                        window.alert(
                            "Sign out failed. Please try again."
                        );
                    }
                }
            );
        }
    );
})();
