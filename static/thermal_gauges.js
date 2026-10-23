"use strict";
// Visual guidance only. Actual alert policies remain server-managed.
(() => {
    const labels = {
        optimal:"Optimal", warm:"Warm",
        warning:"Warning", critical:"Critical",
        unavailable:"Unavailable"
    };

    const sensors = [
        ["opticTemp","opticMeter","opticLevel","Optical"],
        ["cpu1Temp","cpu1Meter","cpu1Level","CPU 1"],
        ["cpu2Temp","cpu2Meter","cpu2Level","CPU 2"]
    ];

    for (const [valueId, meterId, levelId, name] of sensors) {
        const element = document.getElementById(valueId);
        const meter = document.getElementById(meterId);
        const levelText = document.getElementById(levelId);
        if (!element || !meter || !levelText) continue;

        const tile = meter.closest(".thermal-tile");

        const render = () => {
            const raw = element.textContent.trim();
            const temp = raw === "" ? NaN : Number(raw);
            const valid = Number.isFinite(temp);

            const bands = valueId === "opticTemp" ?
                [50, 60, 70] : [65, 75, 85];

            const level = !valid ? "unavailable" :
                temp >= bands[2] ? "critical" :
                temp >= bands[1] ? "warning" :
                temp >= bands[0] ? "warm" : "optimal";

            tile.dataset.level = level;
            levelText.textContent = labels[level];

            const angle = valid ?
                Math.min(100, Math.max(0, temp)) * 2.7 : 0;

            meter.style.setProperty("--dial-angle", `${angle}deg`);

            meter.setAttribute("aria-label",
                valid ?
                `${name} temperature ${raw} degrees Celsius, ${labels[level]}` :
                `${name} temperature unavailable`
            );
        };

        new MutationObserver(render).observe(element, {
            childList:true,
            characterData:true,
            subtree:true
        });
        render();
    }
})();
