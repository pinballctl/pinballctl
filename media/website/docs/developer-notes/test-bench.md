# Test Bench: Course & layout

The Test Bench is for testing pinballctl software, specifically **[ball management](../user-guide/ball-management.md), [scoring](../user-guide/scoring.md) and [events](../user-guide/events.md)**. The ball course, sensors and buttons provide physical inputs for these tests, with lamps, an LCD and addressable lighting for output feedback.

The bench uses a **400 × 400 × 135 mm wooden box**, three 27 mm balls, a manual release gate, ten input buttons and two yellow output lamps.

<span id="powered-launch-gate-options"></span>

## How the ball course works

1. Three balls queue in the front-left trough, at T1, T2 and T3.
2. The front ball is transferred by hand to the rear-right shooter pocket. The remaining balls roll forward.
3. The ball rests against the manual gate and blocks **Ready**. **Fire** is a separate input button.
4. The gate lifts **30 mm** to release the ball. Gravity takes it past Onfield, Bumper 1, the corner, Bumper 2 and Drain, back to the trough.

Bumper stations sense passage. Yellow lamps show MOSFET output activity; the bench has no powered bumper or trough ejector.

## Control and safety checks

With coil power disconnected, the LED bench exercised both Live View flippers,
rapid presses, automatic heartbeat recovery and Hardware Sync during input.
The ESP discarded presses during cooldown. The bridge discarded presses
queued during startup or sync and accepted fresh input once ready. A short heartbeat interruption
disarmed the ESP, and a healthy heartbeat let it rearm without a reset.

The LED configuration established event routing and recovery behavior. Pulse
timing, hold behavior, current, temperature and shutdown with real coils and
drivers remain target-hardware checks. [Coil Safety](../technical-notes/coil-safety.md)

## Layout and illustrations

![Assembly with the ball course, LCD, blue input buttons, yellow output lamps and perimeter lighting.](./media/bench-course-front-right-v7.png)

The render shows the overall arrangement. The **dimensioned plan below shows component placement**.

![Dimensioned course and component-bay plan.](./media/bench-course-layout.png)

<div hidden>
<ul>
<li id="materials-and-mounting"><a data-section-redirect href="test-bench/construction.md#materials-and-mounting">Materials and mounting</a></li>
<li id="mdf-sheet-material"><a data-section-redirect href="test-bench/construction.md#mdf-sheet-material">MDF sheet material</a></li>
<li id="panel-off-service-view"><a data-section-redirect href="test-bench/construction.md#panel-off-service-view">Panel-off service view</a></li>
<li id="fastening-sequence"><a data-section-redirect href="test-bench/construction.md#fastening-sequence">Fastening sequence</a></li>
<li id="lighting-and-electrical-connections"><a data-section-redirect href="test-bench/wiring.md#lighting-and-electrical-connections">Lighting and electrical connections</a></li>
<li id="direct-sensor-connections"><a data-section-redirect href="test-bench/wiring.md#direct-sensor-connections">Direct sensor connections</a></li>
<li id="flipper-inputs-and-coil-output-lamps"><a data-section-redirect href="test-bench/wiring.md#flipper-inputs-and-coil-output-lamps">Flipper inputs and coil-output lamps</a></li>
<li id="led-strip-and-signal-interfaces"><a data-section-redirect href="test-bench/wiring.md#led-strip-and-signal-interfaces">LED strip and signal interfaces</a></li>
<li id="single-soldered-interface-board"><a data-section-redirect href="test-bench/interface-board.md#single-soldered-interface-board">Single soldered interface board</a></li>
<li id="board-layout-and-fitted-parts"><a data-section-redirect href="test-bench/interface-board.md#board-layout-and-fitted-parts">Board layout and fitted parts</a></li>
<li id="wiring-diagram-and-harness"><a data-section-redirect href="test-bench/interface-board.md#wiring-diagram-and-harness">Wiring diagram and harness</a></li>
<li id="copper-side-links"><a data-section-redirect href="test-bench/interface-board.md#copper-side-links">Copper-side links</a></li>
<li id="mounting-assembly-and-checks"><a data-section-redirect href="test-bench/interface-board.md#mounting">Board mounting</a></li>
<li id="power-and-host-connections"><a data-section-redirect href="test-bench/power.md#power-and-host-connections">Power and host connections</a></li>
<li id="single-power-inlet"><a data-section-redirect href="test-bench/power.md#single-power-inlet">Single power inlet</a></li>
<li id="normal-mac-use-and-portable-pi-demos"><a data-section-redirect href="test-bench/power.md#usb-connection">USB connection</a></li>
<li id="amazoncouk-shopping-list"><a data-section-redirect href="test-bench/shopping-list.md#amazoncouk-shopping-list">Amazon.co.uk shopping list</a></li>
<li id="products"><a data-section-redirect href="test-bench/shopping-list.md#products">Products</a></li>
<li id="components-taken-from-the-electronics-kit"><a data-section-redirect href="test-bench/interface-board.md#board-layout-and-fitted-parts">Interface-board parts</a></li>
</ul>
</div>
