# Switch-event performance

The November 2026 host replay alternated switch closes and opens with scoring enabled and 48 authored rules. Across three runs on an ARM Mac, median host processing fell from 6.34 ms to 3.09 ms per event and the 95th percentile fell from 6.82 ms to 3.51 ms. Each run measured 600 events after 100 warm-up events. The replay covered host processing and event logging using temporary storage.

A separate run fed 400 switch edges at 100 per second through the Bridge using simulated serial. The baseline and tuned runs processed all edges in order, each awarding 20,000 points and recording 200 Rules hits. Start, launch and drain were also verified. In that comparison, the 95th percentile from frame injection to host rule completion fell from 94.44 ms to 9.89 ms.

That pass reused a database connection across the manager work for one event, read only the state needed by that work, and marked bus events that had already passed through the managers. Rules prepared trigger definitions once per configuration load and retained useful trigger history. The replay used the original JSON frames.

The host replay leaves physical debounce, serial transfer and actual output timing to the assembled bench. Measure the switch-to-output path for local ESP actions and Pi-driven actions separately. [Test Bench](../developer-notes/test-bench.md) · [Bridge performance](../technical-notes/bridge-performance.md)

## 400-event load target

Compact physical events carry complete observations for each edge. In the local fixture, eight device observations produced a frame of about 94 bytes including framing, compared with about 447 bytes in the JSON replay. At 400 events/s that is about 37.6 kB/s of physical event traffic. Keeping each snapshot in its own frame avoids depending on earlier messages to interpret a switch. The Bridge expands each frame for both logs.

The local test used an ARM Mac, simulated 460800-baud UART pacing, 48 loaded rules and one score award per switch close. Two 20-second runs at 400 events/s used evenly spaced input and groups of six. Each run processed 8,000 test edges plus start, launch and drain in sequence. Each verified 4,000 awards, 4,000 Rules hits, every delivered score notification and every expanded input in both logs across rotation. The 95th percentile from the simulated edge to Bridge worker completion was about 34 ms in both runs.

An earlier run under the same load filled the host queue when Audio was rewriting its status snapshot for every event. Audio now samples the status for inputs with no associated action. Gameplay events still follow the ordered path, and events that trigger audio actions still execute individually. The physical link, storage performance on the Pi and switch-to-output timing remain bench measurements. Use the Performance page to compare incoming and processed rates, backlog and loss counters during that test.

A subsequent replay with the live Performance page open received 8,002 frames. The host completed 3,963 and discarded 4,039 after the host queue filled. The serial sequence and decode counters showed zero errors. The compact overview now retrieves only new history samples during polling. Sustained 400 events/s with live monitoring still needs verification.
