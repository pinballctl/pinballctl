# Performance

Performance shows how events move through the bridge, host processing and ESP confirmation path. Open **Platform → Performance** to investigate responsiveness, bursts of activity and delivery backlogs.

<img src="./media/screenshot-feature-performance.webp" data-source='{"url":"/login","next_url":"/performance/","dark_mode":true,"settle_ms":1000,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Performance module showing live delivery metrics and throughput, backlog and latency charts" style="width:100%;height:auto;">

The screenshot is refreshed by the website's `utils/site-screenshots.txt` manifest. It shows a real application session; quiet graphs are normal when no gameplay events are arriving.

## Live controls and history

- **Live updates** pauses or resumes updates in this browser view. It does not pause the bridge or gameplay.
- **History** selects one minute or five minutes of chart history.
- The bridge collects a sample each second and retains five minutes. Restarting the bridge clears this history and its session counters.
- The page refreshes once per second while visible and live updates are enabled. A hidden browser tab stops polling; bridge history collection continues.
- Stale samples (over three seconds old), disconnected ESP status or unavailable metrics are reported as unavailable rather than zero. Existing charts can still contain earlier samples.

## Metric cards

| Metric | What it tells you |
| --- | --- |
| Incoming events/sec | Rate of incoming bridge events. This is not a count of physical button presses. |
| ESP confirmations/sec | Rate of confirmed tracked event deliveries to the ESP. |
| Waiting to send | Events queued for ESP delivery. |
| Awaiting ESP | Sent events waiting for confirmation. |
| Host work pending | Event work waiting for host processing. |
| Event round trip p95 (ms) | 95th-percentile time from sending an event to its ESP confirmation. |
| Delivery p95 including queue (ms) | 95th-percentile delivery time including the bridge queue wait. |
| Oldest queued event (ms) | How long the oldest queued event has been waiting. |
| Unconfirmed deliveries | Tracked deliveries that timed out during this bridge session. |
| ESP rejections | Tracked deliveries rejected by the ESP during this session. |
| Rejected during overload | Activations rejected while delivery overload protection is active. |
| Overload stops | Number of overload incidents in this bridge session. |

A p95 value describes the slower end of the recent measured deliveries: approximately 95% completed within that time. Latency values use the latest 256 confirmations, rather than every event in the selected chart window.

## Reading the graphs

**Event throughput:** blue is received events, green is host-processed events, and amber is ESP confirmations. These measure different stages and do not need to match. Host-only scoring or audio work does not require a matching ESP delivery unless another configured action needs it.

**Backlog:** blue is waiting to send, green is host work pending, and amber is awaiting ESP confirmation. Look for queues that grow and stay elevated rather than judging a single brief spike.

**Event round-trip latency:** blue is serial round-trip p95; green includes bridge queue time. A growing gap between them points to time spent waiting before transmission.

ESP confirmation means the controller accepted an event. It does **not** prove that a physical coil, lamp or other device moved or operated. These graphs also do not measure the direct local switch-to-flipper response time of ESP-owned rules.

## Overload protection and recovery

The bridge stops activations when queue wait exceeds **100 ms**, or an outstanding tracked confirmation exceeds **250 ms**. These are protective delay limits, not a guaranteed events-per-second capacity.

During an overload, activations are rejected and coils are disarmed; release events remain eligible for delivery. Stale activations are not replayed later.

An isolated overload can recover automatically with supporting firmware after a minimum two-second cooldown and a healthy quiet period. Recovery checks include empty delivery and host queues, confirmed disarming, fresh ESP status, firmware readiness and no firmware fault. Restoring an earlier armed state requires the safety handshake to succeed. Recovery is conditional, not a promise to resume after a fixed two seconds.

Three overload incidents within 60 seconds latch a repeated-overload lockout. Firmware faults and failed or unconfirmed recovery also leave the system disarmed. Investigate the cause before resuming operation.

### Reset overload

**Reset overload** is a diagnostic control shown during an overload, not a normal gameplay requirement. It requests recovery with coils left disarmed. The button is enabled after disarming is confirmed, but the bridge can still reject the request if outstanding deliveries remain or recovery is unsupported. It does not bypass firmware faults or cooldown checks.

## A practical investigation

1. Watch normal play first and note whether queues return toward zero between bursts.
2. Compare received events with host processing and confirmations; remember that one input may produce several configured actions.
3. If delivery p95 rises while round-trip p95 stays low, inspect the waiting-to-send backlog.
4. If host work grows, inspect the rules, scoring, audio and media triggered by those events.
5. Use the [event logs](14-logs.md) and [ESP connection tools](11-esplink.md) to investigate rejected deliveries, disconnects or repeated overloads.

The dashboard provides a quick overview; Performance provides the detailed history. Do not infer a universal throughput limit from a single load test: the work each event triggers matters.
