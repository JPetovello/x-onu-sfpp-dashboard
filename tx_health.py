import math


def classify_tx_power(value, thresholds):
    """Return the display label, operational level, and numeric TX value."""

    try:
        value = float(value)
    except (TypeError, ValueError):
        return ("UNKNOWN", "unknown", None)

    if not math.isfinite(value):
        return ("UNKNOWN", "unknown", None)

    operating_min = thresholds.get("operating_min")
    operating_max = thresholds.get("operating_max")

    if (
        operating_min is not None
        and operating_max is not None
    ):
        if value < operating_min or value > operating_max:
            return ("ALARM", "bad", value)

        return ("NORMAL", "good", value)

    low_alarm = thresholds["low_alarm"]
    low_warning = thresholds["low_warning"]
    high_warning = thresholds.get("high_warning")
    high_alarm = thresholds.get("high_alarm")

    if (
        value <= low_alarm
        or (
            high_alarm is not None
            and value >= high_alarm
        )
    ):
        label = (
            "POOR"
            if thresholds["profile"] == "legacy"
            else "ALARM"
        )
        return (label, "bad", value)

    if (
        value < low_warning
        or (
            high_warning is not None
            and value > high_warning
        )
    ):
        label = (
            "FAIR"
            if thresholds["profile"] == "legacy"
            else "WARNING"
        )
        return (label, "warn", value)

    great_low = thresholds.get("cosmetic_great_low")
    great_high = thresholds.get("cosmetic_great_high")

    if (
        great_low is not None
        and great_high is not None
        and value >= great_low
        and value <= great_high
    ):
        return ("GREAT", "good", value)

    label = (
        "GOOD"
        if thresholds["profile"] == "legacy"
        else "NORMAL"
    )
    return (label, "good", value)
