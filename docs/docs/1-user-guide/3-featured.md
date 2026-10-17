# Features

Full overview of the main Pinball CTL features.

Use the table for a quick summary, and find the detailed sections to understand what each area does.

## At-a-Glance Feature Table

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Purpose</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Dashboard</td><td>Live overview of machine state, connectivity, and runtime health.</td></tr>
      <tr><td>Rules</td><td>Create and manage gameplay rules, triggers, and actions.</td></tr>
      <tr><td>Scoring</td><td>Author points, progressive scoring rules, and combo scoring logic.</td></tr>
      <tr><td>Audio</td><td>Manage sound assets, cue playback behavior, output routing, and usage mapping.</td></tr>
      <tr><td>Media</td><td>Build visual scenes with assets and overlays, then launch kiosk displays for runtime.</td></tr>
      <tr><td>Lighting</td><td>Author scene-based lighting with rich live preview before rollout.</td></tr>
      <tr><td>Accelerometer</td><td>Calibrate table level, monitor live motion data, and track nudge/lift activity.</td></tr>
      <tr><td>Playfield</td><td>Visual playfield editor with live simulation preview for faster iteration.</td></tr>
      <tr><td>Hardware</td><td>Discover hardware, map inputs/outputs, and manage hardware configuration.</td></tr>
      <tr><td>ESPLink</td><td>Manage ESP32 link status, versions, and manifest sync workflow.</td></tr>
      <tr><td>Firmware</td><td>Firmware package and deployment support for ESP32 targets.</td></tr>
      <tr><td>Service Log</td><td>Service and maintenance logging for users and engineers.</td></tr>
      <tr><td>Logs</td><td>View and inspect application and bridge logs from the web UI.</td></tr>
      <tr><td>Wi-Fi</td><td>Network connection status and Wi-Fi setup controls.</td></tr>
      <tr><td>Settings</td><td>System-wide configuration, identity, and environment options.</td></tr>
    </tbody>
  </table>
</div>

## Dashboard

The Dashboard is the first operational view after login. It is designed for quick checks before you start rule or lighting work.

Key features:

- Live status cards for network, bridge, ESP32 link, and uptime.
- Dependency visibility for required tooling.
- High-level machine and gameplay metrics in one place.
- Fast way to spot faults before troubleshooting deeper features.

## Rules

Rules is the gameplay authoring area. It defines how machine events trigger actions and behaviour.

Key features:

- Rule creation and editing workflows.
- Trigger and condition-based action execution.
- Integration with lighting actions (including scene selection and control options).
- Integration with media actions (control videos, switch overlays and update content live).

## Playfield

Playfield is the visual model of your playfield and hardware placement.

Key features:

- Placement and sizing of playfield elements.
- Simulation preview for quick visual validation as you build.
- Hardware binding support for visual validation.
- Editing tools to maintain a clean machine map.
- Preview the playfield changes before applying them to your live machine workflow.
- Playfield event handling mirrors hardware flow, so triggers and responses behave consistently.
- Test trigger logic with immediate on-screen feedback that reflects hardware events.
- Assign keyboard shortcuts to trigger events like flipper activations and bumper hits
- Useful reference context when authoring rules and lighting.

## Scoring

Scoring is the point-system authoring area. It lets you build base points, progressive hit rules, and combo awards without writing code.

Key features:

- Base points table for fixed score awards from hardware and fired events.
- Progressive scoring rules with minimum hit thresholds and optional time windows.
- Cooloff controls to reduce hit streak value over time.
- Combo authoring with ordered or any-order step matching.
- Optional combo multipliers and emitted events for integration with Rules and Lighting.

## Audio

Audio manages sound assets and runtime playback rules from one place on the Pi side.

Key features:

- Asset library with multi-upload and inline preview.
- Cue editor for output, bus, volume, loop, repeats, and cooldown.
- Output/device visibility and runtime playback monitoring.
- Usage mapping for quick cue/asset lookup and diagnostics.

## Media

Media is the scene authoring and playback module for videos and overlays across your configured displays.

Key features:

- Stage editor with scene selector, options, overlays, and live preview.
- Launch controls for fullscreen kiosk and small-window testing.
- Library tab for asset upload, browsing, and preview.
- Displays tab for detection and runtime environment checks.
- Runtime tab for active scene visibility and stop controls.

## Lighting

Lighting is a full scene authoring workflow for table effects and player feedback.

Key features:

- Scene and timeline editing.
- Pattern-based animation generation.
- Custom keyframes and tag-based frame markers.
- Cast targeting, layering options, and playback controls.
- Build your lighting plan by scene, timeline, and target selection.
- Apply pattern/show behaviour and test playback in preview before rollout.
- Tune behaviour safely without requiring immediate live hardware control.

## Accelerometer

Accelerometer provides live motion and level visibility for the table, with baseline calibration and runtime diagnostics.

Key features:

- Save Baseline workflow to capture the current table position as your reference point.
- Live pitch and roll spirit-level indicators for quick levelling checks.
- Nudge and lift activity counters with immediate runtime feedback.
- Raw sensor values and status details for diagnostics and setup validation.


## Hardware

Hardware manages the machine's physical I/O mapping and integration data used by runtime services.

Key features:

- Mapping of switches, coils, lights, and related channels.
- Hardware profile and mapping management.
- Data used by bridge/runtime deployment steps.
- Foundation for safe, deterministic control at runtime.

## ESPLink

ESPLink manages the Pi-to-ESP workflow and device-side compatibility checks.

Key features:

- Connection and sync status visibility.
- Clear checks that Pi and ESP are on matching versions and manifest data before deployment.
- Workflow support for updating or synchronising device state.
- Integration point between authoring on Pi and execution on ESP32.
- Built in flashing for firmware updates

## Firmware

Firmware supports firmware package handling and update flow for ESP targets.

Key features:

- Firmware metadata and package handling.
- Updates from official Pinball CTL releases are available and listed here.
- Assisted update/deploy workflow hooks.
- Clear separation between host-side authoring and device runtime code.
- Useful for controlled release and maintenance tasks.

## Service Log

Service Log focuses on service and maintenance history for managed services.

Key features:

- Service and maintenance logging for users and engineers.
- Maintenance history for physical machine work such as cleaning and inspections.
- Records of hardware replacement and service actions over time.
- Helps teams track what was serviced, when it was done, and what changed.
- Helps confirm long-running service stability.

## Logs

Logs provides direct access to application and bridge output for troubleshooting.

Key features:

- Read runtime logs from the web UI.
- Inspect bridge and web logging without leaving the browser.
- Useful for identifying serial, protocol, or configuration issues.
- Supports day-to-day diagnostics during development and testing.

## Wi-Fi

Wi-Fi shows and manages network connection details relevant to remote use.

Key features:

- Current connection status and interface details.
- Wi-Fi setup/update controls.
- Helps confirm browser access and API reachability.
- Core tool for headless Pi deployments.
- Planned: Wi-Fi connected services will provide support for global leaderboards.

## Settings

Settings contains installation-wide configuration options.

Key features:

- Identity and general system settings.
- Security-related settings such as login credentials.
- Import/export style configuration workflows where supported.
- Central place for persistent environment-level options.
