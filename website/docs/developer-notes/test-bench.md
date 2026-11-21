# Test Bench: Course & layout

**Design review: 19 November 2026.** A portable development rig in the **400 × 400 × 135 mm WooDeeDoo box**, with a real three-ball trough, hand-loaded shooter and manual launch gate. Ten **Gebildet 12mm Momentary Blue LED High Head** buttons, a flush LCD, two dedicated yellow coil-output lamps and addressable lighting exercise the controller alongside the rolling-ball course. Each flipper has a button and a separate, larger lamp, grouped on the left or right of the top panel.

**The design and shopping list are still provisional.** The layout reserves space for the selected Yahboom Pi power board, fuse holders and a right-side single 12 V inlet. Their complete installed dimensions and several other component depths remain unverified. The [remaining checks](test-bench/checks.md#readable-engineering-checks-and-unresolved-evidence) explain what must be resolved before a full-build order or final drilling.

The construction uses cut sheet material, glued supports, drilled holes and a small soldered interface board. No printed brackets, custom PCB or machined trough are required. All purchase links are Amazon.co.uk; manufacturer links provide technical evidence.

## How the ball course works

1. Three 27 mm balls queue in the front-left trough: T1 at the end stop, then T2 and T3.
2. Transfer T1's ball **by hand** to the higher rear-right shooter pocket. The remaining balls roll forward, naturally changing the trough signals; T1/T2 become occupied and T3 empty.
3. The ball rests against the manual gate and blocks **Ready**. The **Fire** button sends a separate input; it does not move the gate.
4. Lift the gate 30 mm. The ball passes Onfield, Bumper 1, the enclosed corner, Bumper 2 and Drain, then returns to T3.

Bumper stations detect passage rather than kick the ball. The yellow lamps are actual loads switched by the two MOSFET outputs; they do not validate real coil current, flyback or flipper mechanics. This bench tests occupancy and event sequences without an automatic trough ejector.

## Layout and illustrations

![Front-right assembly illustration with MDF course, flush LCD, ten blue input buttons, paired yellow output lamps and a continuous perimeter LED strip.](./media/bench-course-front-right-v7.png)

The two larger yellow parts labelled **OUTPUT** are **P07 indicator lamps**, with no push switch. The small blue-ring parts labelled **INPUT** are the P06 flipper buttons. All ten panel buttons use the blue P06 type. See [flipper inputs and output lamps](test-bench/wiring.md#flipper-inputs-and-coil-output-lamps) for their separate connections.

The AI-generated realistic views illustrate the proposed assembly and component appearance. Wire routing, terminal details and fasteners are illustrative, not a wiring or fixing guide. Use the dimensioned drawings for positions and quantities; neither view is a drilling template or proof of fit. The inlet shown is a candidate, with its flange and attachment still to be checked.

![Provisional scale plan with Pi/Yahboom, three inline fuse-holder reservations and the right-side inlet passage.](./media/bench-course-layout.png)

The plan uses nominal component envelopes including connector space. The Pi/Yahboom stack, three inline holders and inlet have conditional reservations; final MDF fixings, wire routes and connector dimensions need measurement. External catches/stay are outside the quoted box size; adapter storage inside the box is not allocated.

## Dimensions and placement

All dimensions below are **millimetres**. The origin is the **inside rear-left corner**, x to the right, y toward the front, and z upward from the original inner bottom. These are design coordinates, not a drilling template. The nominal usable cavity is **380 × 380 × 125**.

| Assembly | Position and size | Height / fit basis |
| --- | --- | --- |
| Carrier | x=5, y=5; **370 × 370 × 6** | Top z=6. Five millimetres nominal side clearance. Spreads loads over the original thin bottom. |
| Course floor | x=10, y=10; **360 × 360**, front-right **260 × 260** removed; 6 thick | Two 100 mm wide legs. Running surface approximately z=41 at shooter and z=22.5 at T1. |
| Running lane | Rear centre y=60; left centre x=60; **30 clear** | 27 mm balls; 12-thick, 30-high rails. Inner rails meet at (75,75), maintaining an enclosed L-shaped route with 30 mm clear legs. |
| Console top | x=125, y=125; **240 × 240 × 6** | Top z=95, underside z=89. Front open below the panel for access/airflow. |
| Console support | Two side walls 240 long; rear wall between them | **12 thick × 83 high**. 6 carrier + 83 support + 6 top = **95**. |
| Pi, Yahboom and cable bay | x=140, y=140; **110 × 70** | Yahboom below Pi, cooler above; supplied USB-C bridge. Reserve **z=6–58** for the complete assembly, including retention and bends. This unverified 52 mm allowance leaves **7 mm** below the LCD rear reservation. |
| ESP and terminal bay | x=255, y=140; **97 × 105** | 87 × 75 breakout inside; wires rise at the sides and USB exits toward the front. **z≤50 is an unverified assembly allowance.** |
| Fuse bay | x=140, y=212; **110 × 85** | Actual block 87 × 52 × 42. Direct mounting on carrier gives top z≈48; reserve to z=51 with mounting allowance. |
| Converter bay | x=255, y=247; **90 × 53** | Rotate the 53 × 50 case so terminal leads use the extra width. Keep installed top/wiring below z=45. |
| Lamp driver bay | x=220, y=300; **55 × 65** | Two 25-wide boards side by side, 5 apart; 47-long bodies leave 18 total for end connections. Top/wiring ≤z=40. |
| Main fuse holder | x=292, y=305; **55 × 55** | One P18 holder, **z=6–40**, near the inlet. Body and bend dimensions need measurement. |
| 5 V fuse holders | x=140, y=304; **65 × 55** | Two P18 holders, lighting and logic, **z=6–40**. Conditional body/bend reservation. |
| Right-side inlet | Candidate centre **y=285, z=40**; interior reservation x=350, y=270, **30 × 30** | Reserve **z=25–55** for connector and leads. Flange, wall grip, cutout and strain relief are unverified. |
| Right console-wall passage | **y=260–310, z=20–65** | Proposed **50 wide × 45 high** opening through the 12 mm wall, for inlet and LED leads. Check wall strength and edge protection before cutting; this is not the external inlet cutout. |
| Interface under console | x=273, y=260; **80 × 50** | Actual perfboard x=278–348, y=260–310, **70 × 50**, components facing down. Keep whole assembly within **z=60–89**, at least 15 above the converter reservation. See the [single-board layout](test-bench/interface-board.md#single-soldered-interface-board). |
| Power connectors under console | x=140, y=190, **100 × 20**; and x=140, y=275, **100 × 25** | Three WAGO connectors in each row. Keep connectors and harness within z=65–89; levers must remain accessible when the console is lifted. |
| Lamp keepouts | x=187, y=317 and x=302, y=317; **36 × 36** each | Reserve **z=60–95**, including nut and lead bends: a conditional **35 mm wired rear allowance**, not a published body depth. Lower carrier electronics must stay clear of this volume. |

The course's nominal running surface is `z = 22 + 0.035 × (x − 60) + 0.035 × (350 − y)`. This gives approximately **2° leftward** and **2° forward** slopes, with a diagonal resultant near 2.8°. Set it with support pads and sanded shims; it is not an instruction to machine an angled floor. Leave support pads loose until repeated ball runs work, then glue them and fasten the course floor.

### Controls and sensing coordinates

| Element | Centre coordinates | Mounting / action |
| --- | --- | --- |
| Shooter Ready | (313.5, 60) | Gate's closed downstream face x=300. Ball rests at x=313.5; lift gate manually. |
| Onfield / Bumper 1 | (240, 60) / (160, 60) | Opposed heads outside the rear rails. |
| Bumper 2 / Drain | (60, 155) / (60, 235) | Opposed heads outside the left rails. |
| T3 / T2 / T1 | (60, 282.5) / (60, 309.5) / (60, 336.5) | **27 mm pitch**; front end-stop face y=350. |
| First button row | x=150, 195, 240, 285, 325; y=225 | Start, Fire, Lock, Ramp, Orbit. **12mm Momentary Blue LED High Head**; Ø12 mounting holes, Ø14 faces, raised Ø7.4 metal centres and blue LED rings. The modelled wiring zones clear the interface, rear connectors and reference fixing pad. |
| Second button row | x=150, 195, 240; y=260 | Target, Bump 1, Bump 2. |
| Left flipper pair | Input **(170,335)**; output lamp **(205,335)** | Both on the top panel; **35 mm centre spacing**. Label group **LEFT FLIPPER**, with **INPUT** and **OUTPUT** beneath the respective parts. |
| Right flipper pair | Input **(285,335)**; output lamp **(320,335)** | Same spacing and arrangement; label **RIGHT FLIPPER / INPUT / OUTPUT**. These are the two flipper buttons within the ten-button total. |
| Dedicated output lamps | Centres as above | P07: **Ø24.8 face, Ø16 luminous area, Ø22 hole, 15 mm thread**. Supplied rear nuts; check engagement through the 6 mm panel. Overall wired depth and cap height unpublished; allow 35 mm below panel top and 5 mm above until measured. |
| LCD reservation | Upper-left at (140, 140), **100 × 50**; PCB nominally at (150,140) | Bezel through a traced cutout; PCB and connections behind the panel. Reserve 30 mm below panel top, down to z=65, and at most 5 mm above. MDF mounting pads/through-fixings for LCD retention on blank PCB edges are not yet sized. |
| Status / key LEDs | Upper-left (255, 144) / (255, 180) | Six pixels / nominal 100 mm per row; labels beside individual pixels. |

Eight sensor pairs means **16 physical heads**. Reserve an adjustable MDF mounting pad for each head outside the rails, with the optical axis initially **24 mm above the local running surface**. Start the pads with laminated 12 + 6 mm offcuts and shim to the measured lens centre; do not assume the lens is exactly halfway up its housing. Drill aligned beam apertures through both rails, starting around 3 mm and enlarging only if alignment requires it. Size pad footprints and choose flange fixings for MDF before drilling; spread pressure with washers and leave room for alignment without distorting the housing.

For a 27 mm ball, radius r=13.5 and beam height h=24, the ideal blocked length is `2 × √(13.5² − (24 − 13.5)²) = 16.97 mm`. Touching balls therefore leave an ideal **27 − 16.97 = 10.03 mm** clear window. Finite beam width, reflections, ball speed and debounce shorten the real clear interval. At an illustrative 500 mm/s, 10 mm lasts only 20 ms even before those losses: test the actual event stream rather than assuming a debounce setting will preserve every transition.

<details class="previous-sections">
<summary>Links to sections from the original page</summary>
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
<li id="normal-mac-use-and-portable-pi-demos"><a data-section-redirect href="test-bench/power.md#normal-mac-use-and-portable-pi-demos">Normal Mac use and portable Pi demos</a></li>
<li id="amazoncouk-shopping-list"><a data-section-redirect href="test-bench/shopping-list.md#amazoncouk-shopping-list">Amazon.co.uk shopping list</a></li>
<li id="products"><a data-section-redirect href="test-bench/shopping-list.md#products">Products</a></li>
<li id="components-taken-from-the-electronics-kit"><a data-section-redirect href="test-bench/shopping-list.md#components-taken-from-the-electronics-kit">Components taken from the electronics kit</a></li>
<li id="readable-engineering-checks-and-unresolved-evidence"><a data-section-redirect href="test-bench/checks.md#readable-engineering-checks-and-unresolved-evidence">Readable engineering checks and unresolved evidence</a></li>
</ul>
</details>
