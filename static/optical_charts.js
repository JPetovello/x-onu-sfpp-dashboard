"use strict";

// Read-only, real historical data. No simulated readings.
(() => {
    const svgNS = "http://www.w3.org/2000/svg";

    const charts = [
        ["rxTrendChart", "rxTrendCaption", "rx_power_dBm", "RX"],
        ["txTrendChart", "txTrendCaption", "tx_power_dBm", "TX"]
    ];

    function render(rows, chartId, captionId, key, name) {
        const svg = document.getElementById(chartId);
        const caption = document.getElementById(captionId);

        if (!svg || !caption) return;

        svg.replaceChildren();

        const values = rows
            .filter(row => row && row[key] !== null &&
                row[key] !== undefined && row[key] !== "")
            .map(row => Number(row[key]))
            .filter(Number.isFinite);

        if (values.length < 2) {
            caption.textContent = "No recorded history available";
            svg.setAttribute("aria-label", name + " history unavailable");
            return;
        }

        const low = Math.min(...values);
        const high = Math.max(...values);
        const padding = Math.max((high - low) * 0.15, 0.05);
        const min = low - padding;
        const max = high + padding;

        const points = values.map((value, index) => {
            const x = 3 + (index / (values.length - 1)) * 414;
            const y = 66 - ((value - min) / (max - min)) * 60;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        }).join(" ");

        const line = document.createElementNS(svgNS, "polyline");
        line.setAttribute("points", points);
        line.setAttribute("fill", "none");
        line.setAttribute("stroke", "currentColor");
        line.setAttribute("stroke-width", "2.5");
        line.setAttribute("stroke-linecap", "round");
        line.setAttribute("stroke-linejoin", "round");

        svg.appendChild(line);
        svg.setAttribute(
            "aria-label",
            `${name} optical power trend, ${values.length} samples`
        );

        caption.textContent =
            `${values.length} recorded samples · past hour`;
    }

    async function refresh() {
        let rows;

        try {
            const response = await fetch(
                "/api/history?range=1h",
                { cache: "no-store" }
            );

            if (!response.ok) throw new Error("History request failed");

            rows = await response.json();

            if (!Array.isArray(rows)) {
                throw new Error("Unexpected history format");
            }
        } catch (error) {
            for (const [, captionId] of charts) {
                const caption = document.getElementById(captionId);
                if (caption) caption.textContent = "History unavailable";
            }
            return;
        }

        for (const [chartId, captionId, key, name] of charts) {
            render(rows, chartId, captionId, key, name);
        }
    }

    refresh();
    setInterval(refresh, 60000);
})();
