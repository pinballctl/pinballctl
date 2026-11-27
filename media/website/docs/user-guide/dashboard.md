# Dashboard

Open **Dashboard** after signing in to check the Raspberry Pi, the bridge and the ESP32 controller in one place. The seven dashlets also summarize recent play and recorded maintenance. Most live readings refresh about every 10 seconds while the page is visible. The time in the corner of each dashlet tells you when its data last updated.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"full_page":true}' alt="Full Pinball CTL dashboard with all seven dashlets">

## Wi-Fi

<img src="./media/screenshot-dashboard-wifi.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=wifi]"}' alt="Wi-Fi dashlet showing the network name, IP address and signal strength">

Check **Connected** and **SSID** to see whether the Pi has joined the expected wireless network. **Interface** identifies the Pi’s Wi-Fi adapter, and **IP** shows the address it has on that network. **Signal** is reported in dBm. A value closer to zero means a stronger signal.

Use [Wi-Fi](wifi.md) to change the network or investigate a disconnected adapter.

## Bridge Performance

<img src="./media/screenshot-dashboard-bridge-performance.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=perf]","next_click":[{"action":"click","selector":"[data-dashlet=perf] summary"}]}' alt="Bridge Performance dashlet with event rates, pending work and expanded metrics">

Read the three rates to see how many events the bridge receives, how many the Pi processes and how many deliveries the ESP confirms per second. **Waiting or awaiting ESP** counts events queued for delivery plus those already sent and awaiting confirmation. A count that keeps growing is a reason to check the detailed metrics for a backlog.

Expand **Detailed metrics** to inspect pending host work, processing and delivery latency, dropped inputs, and failed or unconfirmed deliveries. An overload alert appears if the bridge stops due to overload. **Auto refresh (1s)** gives you a faster view during a test. Select **Open performance history** for charts and session totals. [Performance](performance.md)

## Bridge & Uptime

<img src="./media/screenshot-dashboard-bridge-uptime.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=bridge]"}' alt="Bridge &amp; Uptime dashlet showing a running bridge and the Pi’s boot time and uptime">

**Status** shows whether the bridge process is running. **Detected via** tells you how the app found that process, and **PID** gives its process ID when available. Check **Connected** in the ESP32 dashlet separately to confirm that the bridge can communicate with the controller.

**Host boot time** and **Host uptime** describe the Pi. Use them to check whether it restarted recently, and open [Logs](logs.md) to investigate an unexpected stop or restart.

## ESP32

<img src="./media/screenshot-dashboard-esp32.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=esp]"}' alt="ESP32 dashlet with firmware, connection, coil safety, clock and deployment status">

**Connected** shows whether the bridge has a fresh connection report from the controller. **Firmware** and **Chip** identify the controller, while **Time** and **Time Sync** show its reported clock and synchronization status. Open [ESPLink](esplink.md) if the controller is disconnected or you need to check which device is attached.

**Rules Sync**, **Hardware Sync** and **Lighting Sync** compare the Pi’s saved configuration with what is deployed on the ESP. Each row shows **In Sync** or **Out of Sync**, with a last sync time when available. **Not Connected** means the dashboard could not verify the sync state. If a row is **Out of Sync**, review the saved changes and deploy from the corresponding [Rules](rules.md), [Hardware](hardware.md) or [Lighting](lighting.md) page.

**Coil safety** reports **Armed**, **Disarmed**, **Fault** or **Unknown**. **Unknown** means there is no fresh safety report. Open Hardware for fault details. Keep coil power disconnected while investigating connectivity or sync. The controller can arm automatically when its safety checks pass. [Coil Safety](../technical-notes/coil-safety.md)

## Dependencies

<img src="./media/screenshot-dashboard-dependencies.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=deps]"}' alt="Dependencies dashlet showing host tools with OK and Missing badges">

The dashlet lists tools checked on the Pi, such as `arduino-cli`, `esptool` and `godot`. Each tool shows **OK** or **Missing**, with a version when the app can read one. Use this dashlet to check that the tools needed for a build or firmware flash are available. [Firmware](firmware.md)

## Gameplay

<img src="./media/screenshot-dashboard-gameplay.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=gameplay]"}' alt="Gameplay dashlet showing recent game counts, player entries and top score">

The summary looks at games that ended in the past seven days, within the latest 200 saved games. **Games ended** includes games ended by the operator if they were saved. **Avg game time** is the average elapsed time from start to end, and **Last game ended** shows the most recent finish.

**Player entries** counts each player once per game. **Multiplayer games** counts games with at least two players, and **Top score** is the highest individual player score in the summary. The dashlet shows dashes when there are no saved games in the period. Select **Open Game Management** to check the current session and credits. [Game Management](game-management.md)

## Machine

<img src="./media/screenshot-dashboard-machine.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":900,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"target":"[data-dashlet=machine]"}' alt="Machine dashlet showing the latest service and repair dates and total log entries">

**Last service logged** and **Last repair logged** show the dates of the latest entries of each type. A dash means there is no recorded date for that type. **Log entries** counts all saved entries, including other types. Select **Open Service Log** to read the records or add an entry. [Service Log](service-log.md)
