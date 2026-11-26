# Dashboard

Open Dashboard after signing in. It shows host and controller status, with links to the tools that can explain a warning.

## At a glance

**Host and bridge**. Check whether the web app can reach the ESP.

**Gameplay**. Review game and player activity from saved Game Management history.

**Module links**. Open a specific tool for connection, mapping or event details.

## Before you start

Start the application and sign in. A live ESP is needed for controller checks; offline authoring does not provide live hardware status.

## Check the machine before a session

1. Open **Dashboard**. Check the network/address and the status in **Bridge & Uptime**. **Expected:** the Pi is reachable and the intended bridge is running before physical tests.

2. Check connection and firmware information in the **ESP32** card. It spans two columns on wider screens and stacks with the other cards on phones. **Expected:** a live connected controller for hardware work. Open ESPLink if the controller is missing or identity is uncertain.

   **Coil safety** in the ESP32 card shows **Armed**, **Disarmed**, **Fault**, or **Unknown**. Open Hardware for the reported fault detail. Unknown means the bridge has no fresh ESP safety report. [Coil Safety](../technical-notes/coil-safety.md)

3. Check Hardware, Rules and Lighting sync rows when available. These rows appear with Time Sync in the right column of the ESP32 card on wide screens and below the controller details on smaller screens. **Expected:** you can identify which saved configuration still needs deployment; a missing row is not proof of sync.

4. Open the module associated with a warning, resolve it and return to Dashboard. **Expected:** the live status reflects the change after refresh.

The Bridge Performance card shows incoming events, host processing and ESP confirmations per second, plus the number of events waiting to send or awaiting ESP confirmation. Expand **Detailed metrics** for input, processing and delivery counters. Overload warnings appear above the metrics. Use **Auto refresh** to update the card every second, or open Performance for session totals and charts. [Performance](performance.md)

The two-column **Gameplay** card summarizes games saved in the last seven days. It shows games ended, their average elapsed time, when the last one ended, player entries, multiplayer games, and the top player score in those games. Each player counts once per game. The summary includes operator-ended games saved to history and uses the latest 200 saved games. Open [Game Management](game-management.md) to see the current session.

The **Machine** card shows when the latest service and repair were logged and how many entries are saved in total. Open [Service Log](service-log.md) for the maintenance records. Both cards keep their rows visible and show a dash for missing values.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"full_page":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Dashboard feature overview" style="width: 100%;height: auto;">

1. Check Bridge and ESP status. 2. Read sync rows. 3. Open a focused module to investigate; displayed sample values are not a hardware test.

## Check the result

Use Gameplay to review recent activity, Game Management to check the current game and credits, and Service Log to review recorded work.

**Safety:** Keep coil power disconnected during connectivity and sync investigation. The ESP can arm automatically once its safety checks pass.

## Troubleshooting

If a card looks stale, return the page to the foreground and allow polling. Compare with ESPLink and Logs. If the UI itself is unavailable, check the actual start mode and port in Detailed Setup.

## Related guides

Next: [ESPLink](esplink.md), [Logs](logs.md), [Troubleshooting](troubleshooting.md).

## Read the dashboard cards

### What This Feature Does

It continuously polls runtime APIs and presents a single at-a-glance state for:

- connectivity
- bridge/runtime processes
- ESP state
- sync status
- dependency/tooling readiness

### Live Refresh Behaviour

Dashboard refreshes automatically in the background.

Key behaviour:

- Regular polling (about every 10 seconds).
- Polling pauses when the page is hidden, then resumes when visible.
- If bridge is running but ESP is not yet connected, quick retry mode is used.

### Card-by-Card Reference

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
        <td>Bridge &amp; Uptime</td>
        <td>running/stopped status badge, detection source, PID, host boot time and uptime in readable form and seconds</td>
        <td>Verify bridge lifecycle state and spot unexpected host restarts.</td>
      </tr>
      <tr>
        <td>ESP32</td>
        <td>firmware, chip, ESP time, connected status, time sync status, coil safety</td>
        <td>Check ESP connectivity, clock health, and reported coil arming state.</td>
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
        <td>Gameplay</td>
        <td>saved game counts, elapsed game time, latest game, player entries, multiplayer games and top score</td>
        <td>Review recent play and player activity.</td>
      </tr>
      <tr>
        <td>Machine</td>
        <td>latest logged service and repair dates, total log entries</td>
        <td>Review the machine's recorded maintenance activity.</td>
      </tr>
    </tbody>
  </table>
</div>

### Typical Workflow

1. Open Dashboard first.
2. Confirm Wi-Fi, Bridge, and ESP are healthy.
3. Check sync status rows when ESP is connected.
4. If not healthy, move to the relevant feature:
   - Logs for runtime output
   - Hardware for mapping/sync
   - ESPLink for bridge/device controls

### Example Checks

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

- [Hardware](hardware.md)
- [ESPLink](esplink.md)
- [Logs](logs.md)
