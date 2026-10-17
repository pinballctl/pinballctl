# Accelerometer

The Accelerometer module gives you a live view of table motion and level data from supported sensors (such as MMA8452), and provides a simple baseline calibration workflow.

<img src="./media/screenshot-feature-accelerometer.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"accelerometer\"]","wait_for":"#accelerometer-page"}]}' alt="Accelerometer module overview" style="width: 100%;height: auto;">

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
