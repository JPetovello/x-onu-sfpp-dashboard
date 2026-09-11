(() => {
    const STORAGE_KEY = "xonu-theme";
    const VALID_THEMES = new Set(["system", "dark", "light"]);

    function getSavedTheme() {
        const saved = localStorage.getItem(STORAGE_KEY);
        return VALID_THEMES.has(saved) ? saved : "system";
    }

    function getSystemTheme() {
        return window.matchMedia("(prefers-color-scheme: light)").matches
            ? "light"
            : "dark";
    }

    function resolveTheme(preference) {
        return preference === "system"
            ? getSystemTheme()
            : preference;
    }

    function applyTheme(preference) {
        const resolved = resolveTheme(preference);

        document.documentElement.dataset.theme = resolved;
        document.documentElement.dataset.themePreference = preference;

        window.dispatchEvent(
            new CustomEvent(
                "xonu-theme-change",
                {
                    detail: {
                        preference,
                        resolved
                    }
                }
            )
        );
    }

    let preference = getSavedTheme();

    applyTheme(preference);

    const systemTheme = window.matchMedia(
        "(prefers-color-scheme: light)"
    );

    systemTheme.addEventListener("change", () => {
        if (preference === "system") {
            applyTheme("system");
        }
    });

    document.addEventListener("DOMContentLoaded", () => {
        const selector = document.getElementById("themeSelector");

        if (!selector) {
            return;
        }

        selector.value = preference;

        selector.addEventListener("change", () => {
            const selected = selector.value;

            if (!VALID_THEMES.has(selected)) {
                return;
            }

            preference = selected;
            localStorage.setItem(STORAGE_KEY, preference);
            applyTheme(preference);
        });
    });
})();
