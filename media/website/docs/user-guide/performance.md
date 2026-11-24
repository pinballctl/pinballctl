# Performance

Use Performance to see whether events are backing up or arriving late. Compare the graph with the bridge state and the event log at the same time.

## At a glance

**Throughput**. Compare event rates over the selected interval.

**Backlog**. Check whether events are waiting to be processed.

**Latency**. Look for changes in delivery time during the same test.

## Before you start

Have the application/bridge running and know whether an ESP is connected. Reproduce only a small controlled non-coil test, with logs available for the same time window.

## Investigate a slow or missed event

1. Open **Platform → Performance**. The overview shows the connection, event rates and one chart at a time. Use **Throughput**, **Backlog** and **Latency** to change the chart, and **Counters** for the full queue and error counts.

2. Watch throughput, queue depth/oldest work and delivery latency together while operating one input. **Expected:** the event is processed without a sustained growing backlog.

3. If rates diverge or latency rises, compare the matching period in Bridge/Events logs and check ESP connection. **Expected:** the bottleneck is identified before changing limits.

4. After resolving the source of load or disconnect, observe cooldown/recovery and re-enable requirements. **Expected:** status returns to the documented healthy state; repeated overload/fault conditions remain subject to protective handling.

<img src="./media/screenshot-feature-performance.webp" data-source='{"url":"/login","next_url":"/performance/","dark_mode":true,"settle_ms":1000,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Performance module showing live delivery metrics and throughput, backlog and latency charts" style="width:100%;height:auto;">

The screenshot uses simulated data. An **ESP connected · Gameplay idle** status means zero gameplay events is expected. **Last ESP message** and **ESP heartbeats** show link activity separately from event throughput.

The incoming and processed cards also show session totals when the Bridge provides a sample. Those totals stay visible after play or a test run ends, even when the live rates return to zero.

## Check the result

Compare the same time window across graphs. An idle or disconnected controller can have missing confirmation data; zero is not proof of instantaneous delivery.

**Safety:** Do not raise safety limits or send rapid activations to improve a graph. Protective stops must remain in place; keep physical timing tests for the target Pi/ESP.

## Troubleshooting

If queues keep growing, stop the test and inspect duplicate/self-triggering events and connection state. If the UI has no data, check services/logs and selected history period before assuming the system is healthy.

## Related guides

Next: [Logs](logs.md), [ESPLink](esplink.md), [Rules](rules.md).

## Counters, graphs and recovery

### Live controls and history

- **Live** pauses or resumes updates in this browser view. It does not pause the bridge or gameplay.
- **History** selects one minute or five minutes of chart history.
- The bridge collects a sample each second and retains five minutes. Restarting the bridge clears this history and its session counters.
- The page refreshes once per second while visible and live updates are enabled. A hidden browser tab stops polling; bridge history collection continues.
- If the Bridge stops responding or a sample is delayed, the page retries and labels the previous values as the last sample. **Bridge running · Waiting for ESP** means the Bridge answered but has no recent ESP traffic.

### Metric cards

| Metric | What it tells you |
| --- | --- |
| Incoming events/sec | Rate of all decoded input events, including synthetic and diagnostic events. |
| Host processed/sec | Rate of successful completions by the ordered Bridge worker. |
| Physical events/sec | Rate of decoded physical events. A press and release can produce two or more events. |
| Physical wire bytes/sec | Framed bytes per second used by physical events, including their headers. |
| Host completion p95 (ms) | Time from admission to the ordered Bridge worker through its completion, including queue wait. |
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
| Missing physical sequences | Sequence numbers skipped between received physical frames. |
| Repeated or out-of-order sequences | Physical frames that repeat a sequence or arrive behind the latest sequence. |
| Firmware input drops | Physical events the ESP reports it could not queue. These can also appear as sequence gaps. |
| Host queue drops | Decoded events rejected or abandoned by the host queue during overload. |
| Compact frame errors | Compact frames that failed to decode. |
| Host processing or log errors | Failures completing host work or writing the event audit log. |
| Overload stops | Number of overload incidents in this bridge session. |

A p95 value describes the slower end of recent events. Approximately 95% completed within that time. Delivery and serial timings use the latest 256 confirmations. Host timing uses the latest 256 successful worker events. Open **Counters** for the detailed counts.

### Reading the graphs

**Event throughput:** blue is received events, green is host-processed events, and amber is ESP confirmations. These measure different stages and do not need to match. Host-only scoring or audio work does not require a matching ESP delivery unless another configured action needs it.

**Backlog:** blue is waiting to send, green is host work pending, and amber is awaiting ESP confirmation. Look for queues that grow and stay elevated rather than judging a single brief spike.

**Event latency.** Blue is serial round-trip p95. Green includes time queued before transmission. Amber shows successful host work after receipt and includes the host queue wait.

ESP confirmation means the controller accepted an event. It does **not** prove that a physical coil, lamp or other device moved or operated. These graphs also do not measure the direct local switch-to-flipper response time of ESP-owned rules.

### Overload protection and recovery

The bridge stops activations when queue wait exceeds **100 ms**, or an outstanding tracked confirmation exceeds **250 ms**. These are protective delay limits, not a guaranteed events-per-second capacity.

During an overload, activations are rejected and coils are disarmed; release events remain eligible for delivery. Stale activations are not replayed later.

An isolated overload can recover automatically with supporting firmware after a minimum two-second cooldown and a healthy quiet period. Recovery checks include empty delivery and host queues, confirmed disarming, fresh ESP status, firmware readiness and no firmware fault. Current firmware resumes event delivery while disarmed, then applies its normal automatic arming checks. Recovery time depends on those checks.

Three overload incidents within 60 seconds latch a repeated-overload lockout. Firmware faults and failed or unconfirmed recovery also leave the system disarmed. Investigate the cause before resuming operation.

### Reset overload

**Reset overload** requests event delivery recovery after disarming is confirmed. The bridge can reject the request if outstanding deliveries remain or recovery is unsupported. Current firmware can arm again after recovery once its normal safety checks pass. A latched firmware fault requires a separate reset.

### A practical investigation

1. Watch normal play first and note whether queues return toward zero between bursts.
2. Compare received events with host processing and confirmations; remember that one input may produce several configured actions.
3. If delivery p95 rises while round-trip p95 stays low, inspect the waiting-to-send backlog.
4. If host work grows, inspect the rules, scoring, audio and media triggered by those events.
5. Use the [event logs](logs.md) and [ESP connection tools](esplink.md) to investigate rejected deliveries, disconnects or repeated overloads.

The dashboard provides a quick overview; Performance provides the detailed history. Do not infer a universal throughput limit from a single load test: the work each event triggers matters.
