# Test Bench: Course & layout

The bench uses a **400 × 400 × 135 mm wooden box**, three 27 mm balls, a manual release gate, ten input buttons, two yellow output lamps, an LCD and addressable lighting.

**Build status:** dimensions are nominal; physical fit and electrical checks are listed in [Checks before use](test-bench/checks.md).

<span id="powered-launch-gate-options"></span>

## How the ball course works

1. Three balls queue in the front-left trough, at T1, T2 and T3.
2. Move the front ball by hand to the rear-right shooter pocket. The remaining balls roll forward.
3. The ball rests against the manual gate and blocks **Ready**. **Fire** is a separate input button.
4. Lift the gate **30 mm**. Gravity takes the ball past Onfield, Bumper 1, the corner, Bumper 2 and Drain, back to the trough.

Bumper stations sense passage. Yellow lamps show MOSFET output activity; the bench has no powered bumper or trough ejector.

## Layout and illustrations

![Assembly with the ball course, LCD, blue input buttons, yellow output lamps and perimeter lighting.](./media/bench-course-front-right-v7.png)

**The render shows the arrangement; use the dimensioned plan below for placement.** Sensor and Pi power-board details in the render are illustrative. The ten additional panel-status lamps and their controller do not yet have assigned mounting positions.

![Dimensioned course and component-bay plan.](./media/bench-course-layout.png)

## Dimensions and placement

All dimensions are **millimetres**. Origin: **inside rear-left corner**; x right, y forward, z up from the original inner bottom. Nominal cavity: **380 × 380 × 125**. Bays include reserved space for cables; measure the fitted assemblies before drilling.

| Assembly | Position and size | Height / clearance |
| --- | --- | --- |
| Carrier | x=5, y=5; **370 × 370 × 6** | Top z=6. Five millimetres nominal side clearance. Spreads loads over the original thin bottom. |
| Course floor | x=10, y=10; **360 × 360**, front-right **260 × 260** removed; 6 thick | Two 100 mm wide legs. Running surface approximately z=41 at shooter and z=22.5 at T1. |
| Running lane | Rear centre y=60; left centre x=60; **30 clear** | 27 mm balls; 12-thick, 30-high rails. Inner rails meet at (75,75), maintaining an enclosed L-shaped route with 30 mm clear legs. |
| Console top | x=125, y=125; **240 × 240 × 6** | Top z=95, underside z=89. Front open below the panel for access/airflow. |
| Console support | Two side walls 240 long; rear wall between them | **12 thick × 83 high**. 6 carrier + 83 support + 6 top = **95**. |
| Pi, power board and cables | x=140, y=140; **110 × 70** | Reserve **z=6–58** for boards, cooler, fixings and cables; **7 mm** below the LCD reservation. Final fit needs checking. |
| ESP and terminal bay | x=255, y=140; **97 × 105** | 87 × 75 breakout; USB exits toward the front. Allow **z≤50**, including wiring. |
| Fuse bay | x=140, y=212; **110 × 85** | Actual block 87 × 52 × 42. Direct mounting on carrier gives top z≈48; reserve to z=51 with mounting allowance. |
| Converter bay | x=255, y=247; **90 × 53** | Rotate the 53 × 50 case so terminal leads use the extra width. Keep installed top/wiring below z=45. |
| Lamp driver bay | x=220, y=300; **55 × 65** | Two 25-wide boards side by side, 5 apart; 47-long bodies leave 18 total for end connections. Top/wiring ≤z=40. |
| Main fuse holder | x=292, y=305; **55 × 55** | One holder at **z=6–40**; check body and cable bends. |
| 5 V fuse holders | x=140, y=304; **65 × 55** | Two holders at **z=6–40**; check bodies and cable bends. |
| Right-side inlet | Candidate centre **y=285, z=40**; interior reservation x=350, y=270, **30 × 30** | Reserve **z=25–55** for connector and leads. Cutout, fixings and strain relief pending. |
| Right console-wall passage | **y=260–310, z=20–65** | **50 × 45** opening through the 12 mm wall. Check wall strength and protect cable edges. |
| Interface under console | x=273, y=260; **80 × 50** | **70 × 50** board at x=278–348, y=260–310, components down. Keep within **z=60–89**; see [interface board](test-bench/interface-board.md). |
| Power connectors under console | x=140, y=190, **100 × 20**; and x=140, y=275, **100 × 25** | Three WAGO connectors in each row. Keep connectors and harness within z=65–89; levers must remain accessible when the console is lifted. |
| Lamp keepouts | x=187, y=317 and x=302, y=317; **36 × 36** each | Reserve **z=60–95**, including nuts and wire bends. Measure the complete lamps before final mounting. |

Course running surface: `z = 22 + 0.035 × (x − 60) + 0.035 × (350 − y)`. This gives approximately **2° fall leftward and forward**. Set the slope with stacked pads and shims, and test ball travel before gluing.

### Controls and sensing coordinates

| Element | Centre coordinates | Mounting / action |
| --- | --- | --- |
| Shooter Ready | (313.5, 60) | Gate's closed downstream face x=300. Ball rests at x=313.5; lift gate manually. |
| Onfield / Bumper 1 | (240, 60) / (160, 60) | Opposed heads outside the rear rails. |
| Bumper 2 / Drain | (60, 155) / (60, 235) | Opposed heads outside the left rails. |
| T3 / T2 / T1 | (60, 282.5) / (60, 309.5) / (60, 336.5) | **27 mm pitch**; front end-stop face y=350. |
| First button row | x=150, 195, 240, 285, 325; y=225 | Start, Fire, Lock, Ramp, Orbit. **Ø12 holes**, Ø14 faces; blue LED rings. |
| Second button row | x=150, 195, 240; y=260 | Target, Bump 1, Bump 2. |
| Left flipper pair | Input **(170,335)**; output lamp **(205,335)** | Both on the top panel; **35 mm centre spacing**. Label group **LEFT FLIPPER**, with **INPUT** and **OUTPUT** beneath the respective parts. |
| Right flipper pair | Input **(285,335)**; output lamp **(320,335)** | Same spacing and arrangement; label **RIGHT FLIPPER / INPUT / OUTPUT**. These are the two flipper buttons within the ten-button total. |
| Dedicated output lamps | Centres as above | **Ø22 holes**, Ø24.8 faces, 15 mm thread. Allow 35 mm below and 5 mm above the panel until measured. |
| LCD reservation | Upper-left at (140, 140), **100 × 50**; PCB nominally at (150,140) | Trace the actual bezel. Reserve **z=65–100** for display, retainers and connections. |
| Status / key LEDs | Upper-left (255, 144) / (255, 180) | Six pixels / nominal 100 mm per row; labels beside individual pixels. |

Mount the **16 sensor heads** on adjustable pads outside the rails. Start with the beam **24 mm above the local running surface**, then align using the received pair. Trial the rail apertures on offcuts before drilling all stations. At this height, touching 27 mm balls leave an ideal **10 mm clear sensing gap**; verify actual transitions at operating speed.

<div hidden>
<ul>
<li id="materials-and-mounting"><a data-section-redirect href="test-bench/construction.md#materials-and-mounting">Materials and mounting</a></li>
<li id="mdf-sheet-material"><a data-section-redirect href="test-bench/construction.md#mdf-sheet-material">MDF sheet material</a></li>
<li id="panel-off-service-view"><a data-section-redirect href="test-bench/construction.md#panel-off-service-view">Panel-off service view</a></li>
<li id="cut-list"><a data-section-redirect href="test-bench/construction.md#cut-list">Cut list</a></li>
<li id="fastening-sequence"><a data-section-redirect href="test-bench/construction.md#fastening-sequence">Fastening sequence</a></li>
<li id="lighting-and-electrical-connections"><a data-section-redirect href="test-bench/wiring.md#lighting-and-electrical-connections">Lighting and electrical connections</a></li>
<li id="direct-sensor-connections"><a data-section-redirect href="test-bench/wiring.md#direct-sensor-connections">Direct sensor connections</a></li>
<li id="flipper-inputs-and-coil-output-lamps"><a data-section-redirect href="test-bench/wiring.md#flipper-inputs-and-coil-output-lamps">Flipper inputs and coil-output lamps</a></li>
<li id="led-strip-and-signal-interfaces"><a data-section-redirect href="test-bench/wiring.md#led-strip-and-signal-interfaces">LED strip and signal interfaces</a></li>
<li id="single-soldered-interface-board"><a data-section-redirect href="test-bench/interface-board.md#single-soldered-interface-board">Single soldered interface board</a></li>
<li id="board-layout-and-fitted-parts"><a data-section-redirect href="test-bench/interface-board.md#board-layout-and-fitted-parts">Board layout and fitted parts</a></li>
<li id="wiring-diagram-and-harness"><a data-section-redirect href="test-bench/interface-board.md#wiring-diagram-and-harness">Wiring diagram and harness</a></li>
<li id="copper-side-links"><a data-section-redirect href="test-bench/interface-board.md#copper-side-links">Copper-side links</a></li>
<li id="mounting-assembly-and-checks"><a data-section-redirect href="test-bench/interface-board.md#mounting-assembly-and-checks">Mounting, assembly and checks</a></li>
<li id="power-and-host-connections"><a data-section-redirect href="test-bench/power.md#power-and-host-connections">Power and host connections</a></li>
<li id="single-power-inlet"><a data-section-redirect href="test-bench/power.md#single-power-inlet">Single power inlet</a></li>
<li id="normal-mac-use-and-portable-pi-demos"><a data-section-redirect href="test-bench/power.md#usb-connection">USB connection</a></li>
<li id="amazoncouk-shopping-list"><a data-section-redirect href="test-bench/shopping-list.md#amazoncouk-shopping-list">Amazon.co.uk shopping list</a></li>
<li id="products"><a data-section-redirect href="test-bench/shopping-list.md#products">Products</a></li>
<li id="components-taken-from-the-electronics-kit"><a data-section-redirect href="test-bench/shopping-list.md#components-taken-from-the-electronics-kit">Components taken from the electronics kit</a></li>
<li id="readable-engineering-checks-and-unresolved-evidence"><a data-section-redirect href="test-bench/checks.md#readable-engineering-checks-and-unresolved-evidence">Checks before use</a></li>
</ul>
</div>
