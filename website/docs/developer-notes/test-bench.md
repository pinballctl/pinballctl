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

## Layout and illustrations

![Assembly with the ball course, LCD, blue input buttons, yellow output lamps and perimeter lighting.](./media/bench-course-front-right-v7.png)

The render shows the overall arrangement. The **dimensioned plan below shows component placement**.

![Dimensioned course and component-bay plan.](./media/bench-course-layout.png)

## Dimensions and placement

All dimensions are nominal and in **millimetres**. Origin: **inside rear-left corner**; x right, y forward, z up from the original inner bottom. Cavity: **380 × 380 × 125**. Component bays include space for cables and fixings.

| Assembly | Position and size | Height / clearance |
| --- | --- | --- |
| Carrier | x=5, y=5; **370 × 370 × 6** | Top z=6. Five millimetres nominal side clearance. Spreads loads over the original thin bottom. |
| Course floor | x=10, y=10; **360 × 360**, front-right **260 × 260** removed; 6 thick | Two 100 mm wide legs. Running surface approximately z=41 at shooter and z=22.5 at T1. |
| Running lane | Rear centre y=60; left centre x=60; **30 clear** | 27 mm balls; 12-thick, 30-high rails. Inner rails meet at (75,75), maintaining an enclosed L-shaped route with 30 mm clear legs. |
| Console top | x=125, y=125; **240 × 240 × 6** | Top z=95, underside z=89. Front open below the panel for access/airflow. |
| Console support | Two side walls 240 long; rear wall between them | **12 thick × 83 high**. 6 carrier + 83 support + 6 top = **95**. |
| Pi, power board and cables | x=140, y=140; **110 × 70** | **z=6–58** allowance for boards, cooler, fixings and cables; **7 mm** below the LCD bay. |
| ESP and terminal bay | x=255, y=140; **97 × 105** | 87 × 75 breakout; USB exits toward the front. Height allowance **z≤50**, including wiring. |
| Fuse bay | x=140, y=212; **110 × 85** | Block 87 × 52 × 42. Top z≈48 on the carrier, or z=51 including mounting allowance. |
| Converter bay | x=255, y=247; **90 × 53** | The 53 × 50 case sits with terminal leads along the wider dimension. Top/wiring allowance z≤45. |
| Lamp driver bay | x=220, y=300; **55 × 65** | Two 25-wide boards side by side, 5 apart; 47-long bodies leave 18 total for end connections. Top/wiring ≤z=40. |
| Main fuse holder | x=292, y=305; **55 × 55** | One holder and cable bends within **z=6–40**. |
| 5 V fuse holders | x=140, y=304; **65 × 55** | Two holders and cable bends within **z=6–40**. |
| Right-side inlet bay | Centre **y=285, z=40**; interior allowance x=350, y=270, **30 × 30** | **z=25–55** allowance for connector and leads. |
| Right console-wall passage | **y=260–310, z=20–65** | **50 × 45** opening through the 12 mm wall, with protected cable edges. |
| Interface under console | x=273, y=260; **80 × 50** | **70 × 50** board at x=278–348, y=260–310, components down. Keep within **z=60–89**; see [interface board](test-bench/interface-board.md). |
| Power connectors under console | x=140, y=190, **100 × 20**; and x=140, y=275, **100 × 25** | Three WAGO connectors in each row, within z=65–89. Levers are accessible with the console lifted. |
| Lamp keepouts | x=187, y=317 and x=302, y=317; **36 × 36** each | **z=60–95** allowance, including nuts and wire bends. |

Course running surface: `z = 22 + 0.035 × (x − 60) + 0.035 × (350 − y)`. This gives approximately **2° fall leftward and forward**. Stacked pads and shims support the course at this slope.

### Controls and sensing coordinates

| Element | Centre coordinates | Mounting / action |
| --- | --- | --- |
| Shooter Ready | (313.5, 60) | Gate's closed downstream face x=300. Ball rests at x=313.5; manual gate release. |
| Onfield / Bumper 1 | (240, 60) / (160, 60) | Opposed heads outside the rear rails. |
| Bumper 2 / Drain | (60, 155) / (60, 235) | Opposed heads outside the left rails. |
| T3 / T2 / T1 | (60, 282.5) / (60, 309.5) / (60, 336.5) | **27 mm pitch**; front end-stop face y=350. |
| First button row | x=150, 195, 240, 285, 325; y=225 | Start, Fire, Lock, Ramp, Orbit. **Ø12 holes**, Ø14 faces; blue LED rings. |
| Second button row | x=150, 195, 240; y=260 | Target, Bump 1, Bump 2. |
| Left flipper pair | Input **(170,335)**; output lamp **(205,335)** | Both on the top panel; **35 mm centre spacing**. Labels: **LEFT FLIPPER**, with **INPUT** and **OUTPUT** beneath the respective parts. |
| Right flipper pair | Input **(285,335)**; output lamp **(320,335)** | Same spacing and arrangement; labels **RIGHT FLIPPER / INPUT / OUTPUT**. These are the two flipper buttons within the ten-button total. |
| Dedicated output lamps | Centres as above | **Ø22 holes**, Ø24.8 faces, 15 mm thread. Clearance allowance: 35 mm below and 5 mm above the panel. |
| LCD bay | Upper-left at (140, 140), **100 × 50**; PCB nominally at (150,140) | **z=65–100** allowance for display, retainers and connections. Panel opening follows the bezel. |
| Status / key LEDs | Upper-left (255, 144) / (255, 180) | Six pixels / nominal 100 mm per row; labels beside individual pixels. |

The **16 sensor heads** sit on adjustable pads outside the rails, with beams **24 mm above the local running surface**. At this height, touching 27 mm balls leave a calculated **10 mm clear sensing gap**. The [build steps](test-bench/build-steps.md) cover sensor alignment and rail apertures.

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
<li id="components-taken-from-the-electronics-kit"><a data-section-redirect href="test-bench/interface-board.md#board-layout-and-fitted-parts">Interface-board parts</a></li>
</ul>
</div>
