# Accelerometer

Use motion readings to understand table movement and calibrate a repeatable level reference before building nudge or tilt responses.

## Before you start

Have a supported connected sensor, live ESP communication and a securely mounted machine. Know the intended physical mounting orientation and keep outputs disabled for motion tests.

## Try it step by step

1. Open Accelerometer and check sensor online/error status and raw readings. **Expected:** live readings change when the sensor moves; stale values are not a calibration.

2. Place the machine at its intended physical level, then choose **Save Baseline**. **Expected:** the reference is saved and pushed to the ESP, with a reported result.

3. Check pitch/roll against the saved baseline, including the actual mounting orientation. **Expected:** level readings are meaningful for this installation.

4. Perform a small controlled movement and observe the activity counters and event log. **Expected:** nudge/lift activity corresponds to real motion without unexpected repeats.

<img src="./media/screenshot-feature-accelerometer.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"accelerometer\"]","wait_for":"#accelerometer-page"}]}' alt="Accelerometer module overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Online/raw status establishes live sensor data. 2. Save Baseline records the reference. 3. Pitch/roll and activity provide the test result.

## Helpful checks

This page exposes baseline calibration and live readings. Do not assume it provides a user-editable threshold control: verify available runtime/firmware configuration before tuning nudge/tilt behaviour.

**Safety:** Do not shake a powered machine to test a coil rule. Keep people clear of moving parts and use small controlled movements with outputs disabled.

## If the result is different

If readings are absent, check live connection and sensor status before saving a baseline. If angles look inverted or offset, check mounting/orientation and recalibrate at the intended level; a baseline cannot repair wiring or an unsupported sensor.

## Continue your build

Next: [ESPLink](11-esplink.md), [Hardware](7-hardware.md), [Events](27-events.md), [Logs](14-logs.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Module Does

- Polls the ESP for live accelerometer status and metrics.
- Shows current pitch and roll against your saved baseline.
- Highlights nudge and lift activity so you can verify event behaviour.
- Displays raw values and runtime metadata for diagnostics.

## Save Baseline

Use **Save Baseline** when the machine is physically level. The current readings are stored as the reference offset and pushed to the ESP in the same action.

This baseline is used to:

- Calculate pitch and roll relative to your calibrated level.
- Improve consistency when checking if a table has been moved.
- Keep runtime motion logic aligned with your real machine orientation (including inverted mounting).

## Table Level View

The level view uses dedicated pitch and roll spirit indicators.

- Pitch shows front/back tilt relative to baseline.
- Roll shows left/right tilt relative to baseline.
- Status text indicates when the table is level or outside expected tolerance.

## Activity and Raw Data

The module also includes:

- **Nudges** counter: increments when motion crosses the configured nudge threshold.
- **Lifts** counter: increments when lift angle logic is triggered.
- A raw data table showing values such as axis readings, angle, calibration state, sample timing, and sensor online/error state.
