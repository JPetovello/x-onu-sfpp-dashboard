"use strict";

(() => {
    const ns = "http://www.w3.org/2000/svg";

    const charts = [
        ["download", "download_bps"],
        ["upload", "upload_bps"]
    ];

    function render(direction, key, rows) {
        const svg = document.getElementById(
            direction + "TrafficTrend"
        );
        const caption = document.getElementById(
            direction + "TrafficCaption"
        );

        if (!svg || !caption) return;

        svg.replaceChildren();

        const values = rows
            .filter(row =>
                row &&
                row[key] !== null &&
                row[key] !== undefined &&
                row[key] !== ""
            )
            .map(row => Number(row[key]))
            .filter(value =>
                Number.isFinite(value) && value >= 0
            );

        if (values.length < 2) {
            caption.textContent = "No recorded history available";
            svg.setAttribute(
                "aria-label",
                direction + " history unavailable"
            );
            return;
        }

        const max = Math.max(1, ...values);

        const points = values.map((value, index) => {
            const x = 3 + index / (values.length - 1) * 414;
            const y = 74 - value / max * 68;
            return x.toFixed(2) + "," + y.toFixed(2);
        }).join(" ");

        const line = document.createElementNS(ns, "polyline");

        line.setAttribute("points", points);
        line.setAttribute("fill", "none");
        line.setAttribute("stroke", "currentColor");
        line.setAttribute("stroke-width", "2.5");
        line.setAttribute("stroke-linecap", "round");
        line.setAttribute("stroke-linejoin", "round");

        svg.appendChild(line);

        svg.setAttribute(
            "aria-label",
            direction + " traffic trend, " +
            values.length + " samples"
        );

        caption.textContent =
            values.length + " recorded samples · past hour";
    }

    async function refresh() {
        try {
            const response = await fetch(
                "/api/advanced/history?range=1h",
                { cache: "no-store" }
            );

            if (!response.ok) {
                throw new Error("History request failed");
            }

            const rows = await response.json();

            if (!Array.isArray(rows)) {
                throw new Error("Unexpected history format");
            }

            for (const [direction, key] of charts) {
                render(direction, key, rows);
            }
        } catch {
            for (const [direction] of charts) {
                const caption = document.getElementById(
                    direction + "TrafficCaption"
                );
                if (caption) {
                    caption.textContent = "History unavailable";
                }
            }
        }
    }

    refresh();
    setInterval(refresh, 60000);
})();
