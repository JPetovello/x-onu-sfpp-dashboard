(function (root, factory) {
    const api = factory();

    if (
        typeof module === "object" &&
        module.exports
    ) {
        module.exports = api;
    }

    if (root) {
        root.classifyTxPower =
            api.classifyTxPower;
    }
})(
    typeof globalThis !== "undefined"
        ? globalThis
        : this,
    function () {
        function classifyTxPower(
            rawValue,
            thresholds
        ) {
            const value = Number(rawValue);

            if (
                rawValue === null ||
                rawValue === "" ||
                !Number.isFinite(value) ||
                !thresholds
            ) {
                return [
                    "UNKNOWN",
                    "unknown"
                ];
            }

            const highAlarm =
                thresholds.high_alarm;

            if (
                value <= thresholds.low_alarm ||
                (
                    highAlarm !== null &&
                    highAlarm !== undefined &&
                    value >= highAlarm
                )
            ) {
                return [
                    thresholds.profile === "legacy"
                        ? "POOR"
                        : "ALARM",
                    "bad"
                ];
            }

            const highWarning =
                thresholds.high_warning;

            if (
                value < thresholds.low_warning ||
                (
                    highWarning !== null &&
                    highWarning !== undefined &&
                    value > highWarning
                )
            ) {
                return [
                    thresholds.profile === "legacy"
                        ? "FAIR"
                        : "WARNING",
                    "warn"
                ];
            }

            const greatLow =
                thresholds.cosmetic_great_low;

            const greatHigh =
                thresholds.cosmetic_great_high;

            if (
                greatLow !== null &&
                greatLow !== undefined &&
                greatHigh !== null &&
                greatHigh !== undefined &&
                value >= greatLow &&
                value <= greatHigh
            ) {
                return [
                    "GREAT",
                    "good"
                ];
            }

            return [
                thresholds.profile === "legacy"
                    ? "GOOD"
                    : "NORMAL",
                "good"
            ];
        }

        return {
            classifyTxPower,
        };
    }
);
