# Performance

Use Performance to see whether events are backing up or arriving late. Compare the graph with the bridge state and the event log at the same time.

## Check the connection

| Status | What it means |
| --- | --- |
| Waiting for Bridge | The app has no current metrics sample from its Bridge. Open [ESPLink](esplink.md) and check that the controller is detected and that the Bridge is running. |
| Bridge running · Waiting for ESP | The Bridge answered. Check the USB connection in ESPLink for recent controller traffic. |
| ESP connected · Sampling | The Bridge is collecting enough data to calculate a rate. |
| ESP connected · Gameplay idle | Zero gameplay events per second is expected. Use **Last ESP message** and **ESP heartbeats** to check link activity. |
| ESP connected · Events flowing | The rate cards and selected chart are updating. |
| ESP connected · Overload | Activations have stopped. Inspect the backlog and open **Counters** before trying to resume. |
| Bridge sample delayed or Bridge status timed out | The page retries automatically and keeps the last sample visible when available. |

The regular app and any isolated replay have separate Bridge connections and history. Select the Performance page for the instance you are testing.

## Investigate a slow or missed event

1. Open **Platform → Performance**. The overview shows the connection, event rates and one chart at a time. Use **Throughput**, **Backlog** and **Latency** to change the chart, and **Counters** for the full queue and error counts.

2. Reproduce the issue with a controlled non-coil test. Compare rates, backlog and latency over the same history window. When the test ends, check that backlog returns to zero and the drop counters have stayed at zero.

3. If rates diverge or latency rises, compare the matching period in Bridge/Events logs and check ESP connection. **Expected:** the bottleneck is identified before changing limits.

4. After resolving the source of load or disconnect, observe cooldown/recovery and re-enable requirements. **Expected:** status returns to the documented healthy state; repeated overload/fault conditions remain subject to protective handling.

<img src="./media/screenshot-feature-performance.webp" data-source='{"url":"/login","next_url":"/performance/","dark_mode":true,"settle_ms":1000,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Performance overview showing an idle connection, session totals and the previous throughput burst" style="width:100%;height:auto;">

The screenshots show the end of a local replay over a simulated serial connection. The Bridge received and processed all 1,203 frames at a test rate of about 100 events per second. See the [Test Bench notes](../developer-notes/test-bench.md) for higher-rate runs and their limits.

The incoming and processed cards also show session totals when the Bridge provides a sample. Those totals stay visible after play or a test run ends, even when the live rates return to zero.

## Check the result

Compare the same time window across graphs. An idle or disconnected controller can have missing confirmation data; zero is not proof of instantaneous delivery.

**Safety:** Do not raise safety limits or send rapid activations to improve a graph. Protective stops must remain in place; keep physical timing tests for the target Pi/ESP.

## Troubleshooting

If queues keep growing, stop the test and check for rules that generate additional events or repeatedly trigger each other. If the overview shows dashes, use the connection status first. A dash means the measurement is unavailable. A displayed zero means a sample was available and the measured value was zero.

## Related guides

Next: [Logs](logs.md), [ESPLink](esplink.md), [Rules](rules.md).

## Counters, graphs and recovery

### Live controls and history

Use **Live** to pause or resume updates in the browser. The bridge and gameplay continue while the view is paused. **History** switches the chart between one and five minutes.

The bridge collects one sample per second and retains five minutes. The visible page refreshes once per second with live updates enabled. A hidden browser tab stops polling while the bridge continues collecting samples. Restarting the bridge clears its history and session counters.

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

<img src="./media/screenshot-performance-counters.webp" data-source='{"url":"/login","next_url":"/performance/","dark_mode":true,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#performance-open-counters","wait_for":"#performance-counters[open]"}],"target":"#performance-counters","target_padding":12,"target_max_height":390}' alt="Queue and error counters dialog showing host drops, firmware drops and missing physical sequences" style="width:100%;max-width:720px;height:auto;">

Compare the received and processed session totals after work has drained. **Firmware input drops** and **Missing physical sequences** can describe the same loss. **Host queue drops** shows work discarded after the Bridge decoded it.

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

### Reset Overload

**Reset Overload** requests event delivery recovery after disarming is confirmed. The bridge can reject the request if outstanding deliveries remain or recovery is unsupported. Current firmware can arm again after recovery once its normal safety checks pass. A latched firmware fault requires a separate reset.

### A practical investigation

1. Watch normal play first and note whether queues return toward zero between bursts.
2. Compare received events with host processing and confirmations; remember that one input may produce several configured actions.
3. If delivery p95 rises while round-trip p95 stays low, inspect the waiting-to-send backlog.
4. If host work grows, inspect the rules, scoring, audio and media triggered by those events.
5. Use the [event logs](logs.md) and [ESP connection tools](esplink.md) to investigate rejected deliveries, disconnects or repeated overloads.

The dashboard provides a quick overview; Performance provides the detailed history. Do not infer a universal throughput limit from a single load test: the work each event triggers matters.
