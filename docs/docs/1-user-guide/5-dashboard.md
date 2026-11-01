# Dashboard

See what is connected, spot warnings and jump into the part of your build you need. Use this page to decide whether the machine is ready for configuration or needs investigation.

## Before you start

Start the application and sign in. A live ESP is needed for controller checks; offline authoring does not provide live hardware status.

## Try it step by step

1. Open **Dashboard**. Check the network/address and Bridge status. **Expected:** the Pi is reachable and the intended bridge is running before physical tests.

2. Check ESP connection and firmware information. **Expected:** a live connected controller for hardware work. Open ESPLink if the controller is missing or identity is uncertain.

3. Check Hardware, Rules and Lighting sync rows when available. **Expected:** you can identify which saved configuration still needs deployment; a missing row is not proof of sync.

4. Open the module associated with a warning, resolve it and return to Dashboard. **Expected:** the live status reflects the change after refresh.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Dashboard feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Check Bridge and ESP status. 2. Read sync rows. 3. Open a focused module to investigate; displayed sample values are not a hardware test.

## Helpful checks

Read status cards as a starting point. Demo/trend values are not a verified credit meter, physical ball inventory or proof of gameplay readiness.

**Safety:** Keep outputs disabled during connectivity and sync investigation. A green connection badge does not arm or certify coil wiring.

## If the result is different

If a card looks stale, return the page to the foreground and allow polling. Compare with ESPLink and Logs. If the UI itself is unavailable, check the actual start mode and port in Detailed Setup.

## Continue your build

Next: [ESPLink](11-esplink.md), [Logs](14-logs.md), [Troubleshooting](26-troubleshooting.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Feature Does

It continuously polls runtime APIs and presents a single at-a-glance state for:

- connectivity
- bridge/runtime processes
- ESP state
- sync status
- dependency/tooling readiness

## Live Refresh Behaviour

Dashboard refreshes automatically in the background.

Key behaviour:

- Regular polling (about every 10 seconds).
- Polling pauses when the page is hidden, then resumes when visible.
- If bridge is running but ESP is not yet connected, quick retry mode is used.

## Card-by-Card Reference

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Card</th>
        <th>What it shows</th>
        <th>How to use it</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Wi-Fi</td>
        <td>interface, connected status badge, SSID, IP address, signal</td>
        <td>Confirm remote browser access health.</td>
      </tr>
      <tr>
        <td>Bridge</td>
        <td>running/stopped status badge, detection source, PID</td>
        <td>Verify bridge lifecycle state.</td>
      </tr>
      <tr>
        <td>Uptime</td>
        <td>since timestamp, human duration, raw seconds</td>
        <td>Spot unexpected restarts.</td>
      </tr>
      <tr>
        <td>ESP32</td>
        <td>firmware, chip, ESP time, connected status, time sync status</td>
        <td>Confirm ESP connectivity and clock health.</td>
      </tr>
      <tr>
        <td>ESP32 Sync Rows (when connected)</td>
        <td>Rules Sync (state + last sync), Hardware Sync (state + last sync), Lighting Sync (state + last sync), badges: <code>In Sync</code>, <code>Out of Sync</code>, <code>—</code></td>
        <td>Verify deployment sync state before testing gameplay.</td>
      </tr>
      <tr>
        <td>Dependencies</td>
        <td>tooling inventory with tool name, version (shortened if long), <code>OK</code>/<code>Missing</code> badge</td>
        <td>Confirm build/flash prerequisites are installed.</td>
      </tr>
      <tr>
        <td>Gameplay / Revenue Snapshot / Player Flow / Machine</td>
        <td>demo/trend style values and machine summary context</td>
        <td>Use as operational context alongside technical health cards.</td>
      </tr>
    </tbody>
  </table>
</div>

## Typical Workflow

1. Open Dashboard first.
2. Confirm Wi-Fi, Bridge, and ESP are healthy.
3. Check sync status rows when ESP is connected.
4. If not healthy, move to the relevant feature:
   - Logs for runtime output
   - Hardware for mapping/sync
   - ESPLink for bridge/device controls

## Example Checks

### Pre-deployment check

Before syncing rules or lighting:

- Bridge = Running
- ESP Connected = Yes
- Time Sync = OK
- Dependencies = all `OK`

### Post-maintenance check

After service work:

- Wi-Fi badge = Yes
- Bridge PID populated
- Uptime progressing normally
- no unexpected sync regressions

## Related Features

- [Hardware](7-hardware.md)
- [ESPLink](11-esplink.md)
- [Logs](14-logs.md)
