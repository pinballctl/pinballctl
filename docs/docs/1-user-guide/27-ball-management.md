# Ball Management

Ball Management records physical observations and expected movements. Game Management decides whether those observations finish a logical turn. A physical ball inventory and **balls per player** are separate settings.

<img src="./media/screenshot-feature-ball.webp" data-source='{"url": "/login", "dark_mode": true, "settle_ms": 800, "click": [{"action": "type", "selector": "input[name=\"username\"]"}, {"action": "type", "selector": "input[name=\"password\"]"}, {"action": "click", "selector": "button[type=\"submit\"]", "wait_for": "[data-menu-toggle]"}], "next_url": "/ball/"}' alt="Ball Management observation overview" style="width:100%;height:auto;">

## Minimal machine

In Settings, set the number of physical balls, add a mapped shooter-departure input with role **launch**, and a drain input with role **drain**. No trough sensor is required. Set each input's active polarity and debounce interval. Save while no game is running, then Sync Rules to deploy its observation watches.

Shooter departure adds one to the in-play estimate. Drain removes one when a corresponding estimate exists. Unknown is never treated as zero. The page shows configured physical inventory, inferred in-play count, confidence, sensor levels, last observations, pending movements and a transition timeline. Live View and Playfield also show the published manager summary; Media overlays read the current player, ball and credits from Game Management.

## Devices, troughs and locks

Advanced settings define device IDs, friendly names, capacities, expected destinations and movement timeouts. Sensor roles are launch, drain, occupancy, entrance, exit and lock. Multiple individual occupancy sensors in one zone produce a confirmed count only after every configured occupancy input has been observed. Entrance/exit observations alone cannot establish an unknown initial count. Counts outside configured capacities require recovery.

A requested movement requires active gameplay, fresh confirmed occupancy, a configured destination and no existing movement from that device. Matching destination observations confirm the movement; timeout makes state uncertain and requires recovery. No retry/search sequence fires automatically.

An optional mapped release output and bounded pulse (1–250 ms) can be configured per device. **Request movement** records the expectation, then the existing bridge/ESP safety path sends one pulse request using a fresh firmware timestamp. ESP arming, stale-command, recovery and coil limits still apply. Missing clock support, rejected commands or uncertain delivery enter recovery. A durable send receipt prevents replay after a crash; an uncertain send may therefore be lost, rather than fired twice. Inspect and reconcile before deliberately requesting a new movement.

## Reconciliation and simulation

Pause an active game first. **Reconcile physical state** requires the operator's observed in-play count and a reason. It clears pending expectations, records an audit event and leaves a recovering game paused. Resume is explicit. Reconciliation describes human evidence; it does not turn inferred locations into sensor-confirmed occupancy.

An input held active beyond the configured freshness interval is reported as a sensor alert. Movement timeouts, impossible drains and capacity mismatches explain why progression is blocked. Inspect sensor wiring, ball locations and the recorded evidence before reconciling. A restored snapshot never proves where physical balls are now.

Input simulation is available only when authorised test mode is enabled in Game Management. Simulated observations never operate outputs directly. Physical events carry explicit firmware provenance; generic event injection cannot create a trusted coin or physical observation.

These are configurable observations and one-shot controlled movements, not a universal mechanical driver, automatic ball-search engine or arbitrary multiball policy. Mechanism-specific retry/search behaviour remains excluded unless separately designed and safety-tested. Actual Pi/ESP sensors, pulse timing and mechanical release/arrival behaviour require physical validation.
