"use strict";

(() => {
    const memory = document.getElementById("memoryUsage");
    const meter = document.getElementById("memoryMeter");
    const load = document.getElementById("loadAverage");

    function updateMemory() {
        if (!memory || !meter) return;

        const raw = memory.textContent.trim();
        const match = raw.match(/^(\d+(?:\.\d+)?)%\s*used$/);
        const value = match ? Number(match[1]) : NaN;
        const valid = Number.isFinite(value);

        const percent = valid ?
            Math.min(100, Math.max(0, value)) : 0;

        meter.style.setProperty(
            "--dial-angle",
            (percent * 2.7) + "deg"
        );

        meter.setAttribute(
            "aria-label",
            valid ? `Memory usage ${value}%` :
                "Memory usage unavailable"
        );
    }

    function updateLoad() {
        if (!load) return;

        const values = load.textContent.trim().split(" / ");

        ["load1", "load5", "load15"].forEach((id, i) => {
            const el = document.getElementById(id);
            if (!el) return;

            const value = values[i]?.trim();
            el.textContent =
                value && value !== "-" ? value : "-";
        });
    }

    for (const [element, callback] of [
        [memory, updateMemory],
        [load, updateLoad]
    ]) {
        if (!element) continue;

        new MutationObserver(callback).observe(element, {
            childList:true,
            characterData:true,
            subtree:true
        });

        callback();
    }
})();
