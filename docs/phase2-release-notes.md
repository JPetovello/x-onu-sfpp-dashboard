# Phase 2 — Release Notes

Status: **Released as `v3.8.0`**

Starting release: `v3.7.0`

This document describes the Phase 2 changes published in `v3.8.0`.

## Interface

- Redesigned Dashboard, Advanced, Diagnostics, Alerts & Notifications, and Alert History pages.
- Dedicated stylesheets and visualization modules.
- Independent optical module and CPU temperature gauges.
- Updated optical, traffic, and system metrics visualizations.
- Retained historical time-range controls and on-demand diagnostics.

## Thermal Monitoring

- Alert configuration schema version 4.
- Optical module warning / critical defaults: 60 °C / 70 °C.
- CPU warning / critical defaults: 75 °C / 85 °C.
- Independent optical, CPU 1, and CPU 2 alert and recovery state.
- Compatibility handling for existing version 3 configuration, including preserving custom thresholds.

## Validation

- 158 Python regression tests passed during release-candidate testing.
- Eight JavaScript regression suites passed.
- Authentication and API integration checks passed.
- Separate hardened-container test passed.
- Candidate image and 31 local application files matched.
- Security scans reported no findings in the completed test environment.

Validation results describe the tested candidate, not a claim that every possible production environment is covered. Documentation-only changes still require a final diff review before release.

## Operator Upgrade Notes

- Use the existing GitHub Actions to GHCR release process.
- Publishing an approved version tag produces the release image and the automatic `latest` tag.
- Apply the image update through Unraid Docker **Update All** after publishing succeeds.
- Back up `/data/metrics.db` consistently before updating.
- Existing Unraid environment variables and runtime parameters are not automatically changed by pulling a new image.
- Configure both dashboard authentication environment variables separately.
- HTTP Basic authentication does not encrypt credentials on a plain HTTP connection.
- Test optional Docker runtime hardening separately before applying it to the production template.

## Rollback

Preserve the original image reference, container settings, and a verified pre-upgrade SQLite backup. Reverting the image after saving version 4 alert configuration may require restoring compatible version 3 database state. Restoring a database backup can lose data collected since its creation.
