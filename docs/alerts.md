# Alert Settings Reference

The **Alert Settings** panel on the **Alerts & Notifications** page controls when alert events are generated and what severity is assigned to them.

Changing an alert severity does not change when the condition is detected. It changes how the resulting event is classified. Available severities are **Info**, **Warning**, and **Critical**.

The defaults are intended to provide useful monitoring without generating an alert for every small fluctuation. They can be adjusted for the optical levels and behavior normally seen on a particular ONT or network.

## Warning Debounce

**Warning debounce** is the number of consecutive warning-level samples that must be observed before a signal-quality warning is generated.

Default:

    3 samples

For example, with the default value of `3`, a warning condition must be present for three consecutive samples before the dashboard records a warning.

This helps prevent a brief optical or temperature fluctuation from creating an unnecessary alert.

Poor or critical conditions are not delayed by the warning debounce and can generate an alert immediately.

If a warning condition disappears before the required number of consecutive samples is reached, the pending warning is cleared.

## RX Power Thresholds

The RX power settings define the receive optical-power ranges used by the alert system.

Defaults:

    Poor low:   -27 dBm
    Fair low:   -24 dBm
    Great low:  -20 dBm
    Great high: -14 dBm
    Poor high:   -8 dBm

The settings exposed in the dashboard define the important boundaries used to decide whether received optical power is normal, warning-level, or poor.

**Poor low** defines the lower extreme. RX power at or beyond the poor range is treated as a critical-quality condition.

**Fair low** defines the transition into the lower warning range.

**Poor high** defines the upper extreme where excessive receive power is considered poor.

The internal **Great** range is used for signal-quality classification and is not normally something that needs to be adjusted.

Because optical power is expressed in negative dBm values, a value such as `-27 dBm` represents less received optical power than `-20 dBm`.

Warning-level RX conditions are subject to **Warning debounce**. Poor conditions can alert immediately. When an active RX warning or critical condition returns to the normal range, a recovery event is generated.

## TX Power Thresholds

TX power uses a profile-aware operational health model. The selected profile and its persisted thresholds drive both the dashboard TX badge and server-side TX alerts.

Operational states are:

- **NORMAL**: inside the configured warning and alarm boundaries.
- **WARNING**: beyond a warning boundary but not an alarm boundary. Warning alerts use the configured consecutive-sample debounce.
- **ALARM**: at or beyond an alarm boundary. Alarm conditions can alert immediately.
- **UNKNOWN**: the reading is missing, invalid, or nonfinite.

The following profiles are available:

**Legacy** preserves the original dashboard behavior exactly. It is the default for fresh installations and for an existing saved configuration that still matches the original defaults:

    Low alarm:     1 dBm
    Low warning:   2 dBm
    High warning:  7 dBm
    High alarm:    8 dBm
    Cosmetic Great range: 4-5 dBm

Legacy retains the historical GOOD / FAIR / POOR display wording. GREAT is only a cosmetic subdivision of the healthy state: it does not change alert severity or overall operational health.

**XGSPONST2001 A-01** uses the documented XGS-PON upstream mean launch-power operating specification:

    Operating minimum: 4.00 dBm
    Operating maximum: 9.00 dBm
    Warning bands:     None

Its behavior is:

    TX < 4.00 dBm         ALARM / OUT OF SPEC
    4.00 <= TX <= 9.00   NORMAL
    TX > 9.00 dBm         ALARM / OUT OF SPEC

This specification defines an operating envelope, not separate warning thresholds. A value outside the envelope therefore enters the existing immediate alarm path without warning debounce. Readings such as `6.22 dBm` and `7.1-7.3 dBm` are NORMAL.

The EEPROM investigation remains useful background but does not define this profile's operational policy. The module reports low alarm `2.00 dBm`, low warning `3.00 dBm`, and `0xFFFF` for both upper threshold words. `0xFFFF` is the maximum SFF-8472 TX-power encoding, approximately `8.16 dBm`, rather than a meaningful calibrated high-side threshold. None of those EEPROM values are used as operational thresholds by the XGSPONST2001 A-01 profile.

**Custom** allows user-defined low thresholds and optional upper warning and alarm thresholds. Leaving an upper field blank disables that boundary; disabled thresholds are stored as JSON `null`, not a magic numeric value. Manually editing a TX threshold changes the selected profile to Custom.

Existing saved configurations are preserved. A source-code default change does not silently migrate them, and the XGSPONST2001 A-01 profile is applied only when selected explicitly. Changing the TX profile or thresholds clears only the in-memory TX debounce and active-classification baseline so the policy change itself cannot create a bogus warning or recovery event. Historical telemetry and alert events are not rewritten.

## Thermal Thresholds

Optical module, CPU 1, and CPU 2 temperatures are monitored independently.

Default alert thresholds:

    Optical warm: 60 °C
    Optical hot:  70 °C
    CPU warm:     75 °C
    CPU hot:      85 °C

Warm conditions use the configured warning debounce. Hot conditions can generate immediate critical alerts. Each sensor maintains independent warning, critical, and recovery state.

The dashboard gauges use separate visual guidance bands for optical and CPU temperatures. These are monitoring indicators, not manufacturer-certified operating limits, and do not necessarily match the configurable alert boundaries.

Existing configuration version 3 installations using the original 75 °C / 85 °C defaults migrate to 60 °C / 70 °C optical alert thresholds while retaining 75 °C / 85 °C CPU thresholds. Existing custom thermal thresholds are preserved.

Configuration version 4 is used when the upgraded configuration is saved. Loading an existing configuration does not by itself require rewriting the stored database row.

## GEM Key Errors

GEM key errors are monitored as a counter increase rather than simply checking whether the counter is non-zero.

Defaults:

    Minimum delta: 1
    Severity:      Warning

**Minimum delta** is the minimum increase required before an alert is generated.

For example, with a Minimum Delta of `1`, a GEM key-error counter increasing from `100` to `101` can generate an alert. A counter that remains at `100` does not repeatedly alert merely because its lifetime value is non-zero.

**Severity** controls whether a generated GEM key-error event is recorded as Info, Warning, or Critical.

## PLOAM State

The alert system monitors whether the ONT is in its configured operational PLOAM state.

Default operational state:

    51 = O5.1 - Associated

The PLOAM settings control the severity assigned to two events:

**Not operational** is used when the ONT is observed outside the configured operational PLOAM state.

Default severity:

    Critical

**Recovered** is used when the ONT returns to the configured operational state.

Default severity:

    Info

If the dashboard starts while the ONT is already in a non-operational PLOAM state, that condition can also generate an alert rather than requiring a transition to occur after startup.

## Active Alarms

The dashboard monitors the number of active alarms reported by the ONT.

Three severity settings control how changes are reported:

**Increased** is used when the active alarm count rises.

Default severity:

    Critical

**Decreased** is used when the active alarm count falls but remains above zero.

Default severity:

    Info

**Cleared** is used when the active alarm count returns to zero.

Default severity:

    Info

The first observed alarm count establishes the initial baseline and does not by itself generate a change event.

## ONT Reachability

ONT reachability monitors the core JSON telemetry connection independently from optional SSH telemetry.

**Failure debounce** controls how many consecutive failed core telemetry samples are required before the ONT is considered unreachable.

Default:

    3 samples

A successful telemetry sample before the debounce threshold is reached clears the pending failures without generating an unreachable or recovery event. After an outage has been confirmed, the first successful telemetry sample generates the recovery event immediately.

**Unreachable** controls the severity used when the core metrics endpoint becomes unreachable.

Default severity:

    Critical

**Recovered** controls the severity used when the core telemetry connection becomes reachable again.

Default severity:

    Info

If the dashboard starts and the core telemetry endpoint is already unreachable, an initial unreachable event can be generated.

A failure of optional SSH telemetry does not by itself cause a core reachability alert.

## Error Counter Alerts

Advanced SSH telemetry provides several cumulative XGS-PON error counters. These alerts are based on **new counter increases**, not on the lifetime value already stored by the ONT.

Each counter rule can contain:

**Minimum delta** — the amount the counter must increase before an alert is generated.

**Cooldown** — the minimum number of seconds after an alert before another alert of the same type may be generated.

**Severity** — whether the generated event is classified as Info, Warning, or Critical.

Counter increases can accumulate across multiple collection cycles until Minimum Delta is reached.

For example, with:

    Minimum delta: 10

three successive increases of `+3`, `+4`, and `+3` accumulate to `+10` and can generate an alert.

If a counter decreases, the dashboard assumes that the ONT rebooted or the counter was reset. Any pending accumulated increase for that counter is discarded rather than treating the reset as an error event.

A cooldown does not mean counter monitoring stops. Increases can continue to be observed while the cooldown is active, and a pending alert can be emitted after the cooldown expires once its configured conditions are satisfied.

The default counter rules are:

| Counter | Minimum Delta | Cooldown | Severity |
| --- | ---: | ---: | --- |
| BIP errors | 10 | 300 seconds | Warning |
| Corrected FEC codewords | 100 | 300 seconds | Warning |
| Uncorrected FEC codewords | 1 | 0 seconds | Critical |
| Corrected PSBd HEC errors | 10 | 300 seconds | Warning |
| Uncorrected PSBd HEC errors | 1 | 0 seconds | Critical |
| Corrected FS HEC errors | 10 | 300 seconds | Warning |
| Uncorrected FS HEC errors | 1 | 0 seconds | Critical |
| PLOAM MIC errors | 1 | 0 seconds | Critical |

A cooldown of `0` means there is no cooldown period.

The higher default thresholds and cooldowns on corrected-error counters help avoid excessive notifications from small bursts of errors that the link successfully corrected.

Uncorrected errors and PLOAM MIC errors default to a Minimum Delta of `1`, Critical severity, and no cooldown because a newly observed uncorrected error is generally more significant than a corrected error.

## Alert Recovery Events

Where recovery detection is supported, the dashboard records a separate event when an active problem returns to normal.

Examples include:

- RX or TX optical quality returning to normal
- Temperature returning to normal
- PLOAM returning to the operational state
- Core telemetry becoming reachable again

Active ONT alarm decreases and clearing are also recorded as separate alert events.

Recovery events default to **Info** where a separate recovery severity is available.

## Alert Settings and Notifications

Alert generation and notification delivery are separate operations.

The dashboard provides a dedicated **Alerts & Notifications** page for configuring alert behavior and external notification delivery. The main dashboard continues to display **Recent Alerts** without using space for configuration controls.

**Alert Settings** determine whether an event is generated and the severity assigned to it.

**Notification Settings** determine whether generated events are sent to an external notification provider.

Supported notification providers are:

- Discord
- ntfy
- Gotify
- Pushover
- Generic Webhook
- Email (Gmail SMTP)

This means alerts continue to be evaluated and stored in the dashboard database even when external notifications are disabled.

Enabling a notification provider does not change the alert thresholds. It simply allows generated alert events to be delivered through the configured provider.
