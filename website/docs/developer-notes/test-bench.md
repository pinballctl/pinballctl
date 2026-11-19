# Test Bench

**Design review: 19 November 2026.** A portable development rig in the **400 × 400 × 135 mm WooDeeDoo box**, with a real three-ball trough, hand-loaded shooter and manual launch gate. Ten **Gebildet 12mm Momentary Blue LED High Head** buttons, a flush LCD, two dedicated yellow coil-output lamps and addressable lighting exercise the controller alongside the rolling-ball course. Each flipper has a button and a separate, larger lamp, grouped on the left or right of the top panel.

**The design and shopping list are still provisional.** The layout reserves space for the selected Yahboom Pi power board, fuse holders and a right-side single 12 V inlet. Their complete installed dimensions and several other component depths remain unverified. The [remaining checks](#readable-engineering-checks-and-unresolved-evidence) explain what must be resolved before a full-build order or final drilling.

The construction uses cut sheet material, glued supports, drilled holes and a small soldered interface board. No printed brackets, custom PCB or machined trough are required. All purchase links are Amazon.co.uk; manufacturer links provide technical evidence.

## How the ball course works

1. Three 27 mm balls queue in the front-left trough: T1 at the end stop, then T2 and T3.
2. Transfer T1's ball **by hand** to the higher rear-right shooter pocket. The remaining balls roll forward, naturally changing the trough signals; T1/T2 become occupied and T3 empty.
3. The ball rests against the manual gate and blocks **Ready**. The **Fire** button sends a separate input; it does not move the gate.
4. Lift the gate 30 mm. The ball passes Onfield, Bumper 1, the enclosed corner, Bumper 2 and Drain, then returns to T3.

Bumper stations detect passage rather than kick the ball. The yellow lamps are actual loads switched by the two MOSFET outputs; they do not validate real coil current, flyback or flipper mechanics. This bench tests occupancy and event sequences without an automatic trough ejector.

## Layout and illustrations

![Front-right assembly illustration with MDF course, flush LCD, ten blue input buttons, paired yellow output lamps and a continuous perimeter LED strip.](./media/bench-course-front-right-v7.png)

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
| Interface under console | x=273, y=260; **80 × 50** | Actual perfboard x=278–348, y=260–310, **70 × 50**, components facing down. Keep whole assembly within **z=60–89**, at least 15 above the converter reservation. See the [single-board layout](#single-soldered-interface-board). |
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

## Materials and mounting

### MDF sheet material

Use **moisture-resistant MDF** for the internal panels, rails and supports:

- **P03:** two GATE8 sheets, **600 × 600 × 6 mm**, at **£17 each**.
- **P04:** one GATE8 sheet, **600 × 600 × 12 mm**, at **£23**.

The **£57** sheet total is included in the shopping list. The WooDeeDoo box has pine walls and a birch-ply lid/base.

**MDF fixing details are pending.** Carrier standoffs, LCD retainers, console/sensor pads and the transport cover need dimensioned attachments and a clearance check. Use glued mounting pads or through-bolts with load-spreading washers, sized for suitable pilot holes and edge distances as described in the [European Panel Federation guidance](https://mdf-info.eu/using-mdf/fixing/screwing). Select any additional hardware before drilling; the small pad envelopes in the drawings are placement references only.

MDF provides a smooth finish. Sealer/primer and paint are unselected and excluded from the subtotal; allow for coating thickness in the gate and ball lane. Moisture-resistant MDF is not waterproof.

**Adhesives — tack with super glue, bond with wood glue:** Dry-fit the bare MDF first. Spread F04 over most of the joint, leaving a few small, separate bare spots for F15. Keep the adhesives and activator out of each other's areas; do not mix them. Use F15 sparingly to hold alignment, following its activator instructions. Trial this assembly method on offcuts first. Retain the wood glue's specified clamping and cure time before loading the joint. F15 is only a positioning aid here: its manufacturer excludes load-bearing applications. Keep the removable console unglued and apply activator away from electronics and optical faces.

### Panel-off service view

The removable panel has **no permanent hinge**. Disconnect the 12 V input and host USB power, remove four console screws, then support the panel within the slack of its harness. Allow approximately **150–200 mm extra harness** for ordinary signal bundles. Keep the LED data connection short and disconnect it, along with any short power leads, before lifting the panel; disconnect labelled terminals for complete removal. The wires must not carry the panel's weight.

The LCD, interface, six WAGOs, button backs and lamp bodies move with the panel. The Pi/Yahboom stack, ESP, four-way fuse block, three inline holders, lighting converter and two lamp drivers stay on the carrier. Support the disconnected panel underside-up on offcuts beside the box. This temporary service space is outside the closed transport footprint. The dimensioned underside view below locates the interface near the right-side LED feed; its [close-up render and wiring](#single-soldered-interface-board) show the board itself.

The Yahboom sits beneath the Pi; the active cooler remains above. The drawing reserves a complete-stack height, but the supplied bridge, connector access, airflow and final fastening stack must be checked on the received parts.

![Provisional carrier, console and sensor mounting sections.](./media/bench-course-mounting.png)

![Provisional console underside: LCD, interface and connectors, with control and lamp clearances.](./media/bench-course-underside.png)

### Cut list

The upright course walls and console support walls are cut from **P04 (12 mm MDF)**. The course sits on stacked blocks cut from **P03/P04 offcuts**, trimmed and shimmed to its slope; these are made during assembly. Keep offcuts for the sensor pads too. The separate **F01 nylon standoffs** support the electronic boards. Final MDF pad sizes and fixings remain unresolved.

The main cuts below use **P03 (6 mm MDF)** and **P04 (12 mm MDF)**. Nominal sheet area is sufficient, but lay out every cut with saw kerf before cutting. Adjust the carrier to the delivered cavity. Small fixing pieces remain provisional as identified below; leave their cuts, final control holes and inlet backing until the MDF mounting details and actual parts can be checked.

| Cut material | Quantity / finished nominal size | Purpose |
| --- | --- | --- |
| 6 mm sheet 1 | 1 × **370 × 370** | Carrier. Trim to delivered cavity; do not force it between walls. |
| 6 mm sheet 2 | 1 × **360 × 360**, remove front-right **260 × 260** | L-shaped course. Cut the 240 square console from that waste, allowing for kerf. |
| MDF waste | LCD retainers: size/fixing pending | Size MDF-compatible retainers; keep contact on blank PCB edges. |
| 6 mm waste | 1 × **240 × 240** | Removable console. Mark control centres, then trace the actual LCD bezel for its window; leave the PCB and lead connections behind the panel. |
| 12 mm sheet | 2 × **240 × 83**; 1 × **216 × 83** | Console side walls and rear wall, forming a U. The right wall has the proposed 50 × 45 cable passage described above. Confirm it against the actual connections before cutting. Glue the frame; keep the front open. |
| 12 mm sheet | 1 × **317 × 30**; 1 × **305 × 30**; 1 × **275 × 30**; 1 × **263 × 30** | Rear outer, left outer and two inner rails. Inside lane faces at x=45/75 and y=45/75. Rear inner rail starts (75,75); left inner rail starts (75,87) and butts against it. There is no inner-corner gap. |
| 12 mm sheet | 2 × **30 × 30** | Trough front stop and shooter outer end stop. |
| 6 mm waste | 1 × **29 × 40** | Manual gate, 6 thick. Slide in a **7 mm** guide gap; 30 mm lift clears the ball. Round the top edge for fingers. |
| 6/12 mm waste | 4 guide cheeks about **12 × 40**, plus spacing offcuts | Glue guide cheeks outside the clear lane after proving the 7 mm channel with the finished gate; no tight friction fit. |
| 12 mm waste | Console fixing pads: size/fixing pending | Size glued pads or through-fixings and check control/wiring clearance before drilling. |
| 12 mm waste | 4 × **30 × 12** | Carrier retaining cleats, 12 thick, screwed to pine sidewalls above carrier edges. Place away from the low trough and cable entry. |
| 12 + 6 mm waste | 16 sensor pads; footprint/fixing pending | One per head. Size pads for MDF-compatible attachments; shim height follows the actual lens position. |
| 12/6 mm waste | Six or more **30 × 30** pads, stacked/trimmed | Support the course floor at its measured slope. All loads go into the carrier. |
| 6 mm waste | 1 × **110 × 54** | Removable trough transport cover spanning the rail tops at y≈250–360. Add 3 mm foam underneath over the balls. |
| 12 mm waste | 1 × **29 × 12** keeper, 12 thick | Glued under the rear end of the transport cover across the lane. Its underside is lower than a ball's diameter, so balls cannot escape backward. The front stop retains the other end. |
| 6/12 mm waste | Cable-clamp bars about **40 × 12** and backing about **50 × 30** | Internal harness restraint; inlet backing and final cable-clamp dimensions depend on the selected connector. |
| 12 mm waste | Backing about **50 × 30** at each catch/stay attachment where needed | Spread loads on the 3 mm lid; keep backing clear of the lamp caps when closed. |

### Fastening sequence

1. **Carrier:** preserve the full 6 mm MDF thickness. Specify standoff retention that leaves the carrier flat on the box base before fitting electronics. Four sidewall cleats can retain the carrier with clearance holes through the cleats and screws into the original pine walls; check engagement and spread head pressure with washers.
2. **Console:** glue the U-frame to the carrier. The four fixing centres **(249,143), (347,207), (143,325), (347,330)** are placement references only; size and position mounting pads and choose fasteners before drilling MDF. Keep the front open, drill side ventilation and keep wires clear of the Pi fan.
3. **Boards:** retain the nominal 10 mm nylon-standoff allowance, M2.5 for the Pi and sizes matched to other holes. Standoff retention, fuse-block/converter fixings and any added pads need a clearance check; do not rely on short screws into thin MDF. Keep the reserved lamp and button wiring volumes clear. Use the supplied Pi/Yahboom stacking hardware for their board-to-board attachment; verify the complete assembly fits its z=6–58 reservation. Carrier retention still needs dimensioning.
4. **Console underside:** trace the received LCD bezel, leaving its PCB behind the panel. Retain its blank PCB edges using MDF mounting pads/through-fixings once sized. Mount the interface components downward within z=60–89; keep reservoir capacitors within the single-board design’s Ø10 × 16 mm limit; revise the layout if received parts exceed it. Tie the WAGOs into their marked rows, with levers accessible. Fit the buttons and dedicated lamps through the panel with their supplied nuts; check engagement and avoid crushing the MDF. Restrain lamp leads with slack beneath each pair, and route button leads downward/frontward, clear of the interface and connectors.
5. **Course:** clamp rails and adjustable pads first. Test all three balls, the 30 mm corner, gate and optical transitions before gluing. Glue the proven supports and rails with the listed wood glue; keep joints bare until bonded. Keep all fixing heads outside the ball lane and its running surface smooth.
6. **Lighting and inlet:** dry-fit the continuous strip, then solder insulated feed/injection and console-row leads at marked pads. Retain wires down the right wall and through the console-side passage. Specify the single inlet cutout, backing, strain relief and protection before drilling.
7. **Closure and transport:** fit the two front catches and external right-rear locking stay from the actual parts, backing thin lid material. Prove free movement and positive locking. Specify cover retention using adequately sized pads or through-fixings before drilling. Prove that the foam-padded cover, rear keeper and front stop securely retain all three balls before transport. Close the gate, disconnect external cables and latch the lid. Carry supporting the base; remove the trough cover before testing.

Workshop tools assumed available: ruler/square, saw or jigsaw, drill with depth stop/countersink, clamps, sandpaper/file, screwdrivers, wire stripper, insulated-terminal crimper, soldering iron, heat-shrink heat source, multimeter and marker. These are excluded from the shopping total.

## Lighting and electrical connections

### Direct sensor connections

**P05 uses Adafruit 2167**, using the ESP's internal pull-ups to avoid a separate sensor interface circuit. Adafruit documents the receiver's open-collector output and the option to use a microcontroller's built-in pull-up ([product specification](https://www.adafruit.com/product/2167), [wiring guide](https://learn.adafruit.com/ir-breakbeam-sensors/arduino)).

- **Emitter:** red lead to the protected **5 V logic supply**, black to ground. It needs power but no ESP GPIO.
- **Receiver:** red lead to the same protected **5 V logic supply**, black to common ground, and white/yellow signal lead directly to one ESP input. Enable that input's **3.3 V internal pull-up** (`INPUT_PULLUP`); do not pull the signal up to 5 V.

Eight stations therefore use **eight ESP inputs**, with power distributed to all sixteen heads. The sensors draw power from the supply rail, never from an output GPIO. No additional sensor resistors, level converters or custom sensor PCB are planned. The firmware supports internal pull-ups; confirm each chosen pin is configured with one enabled and check the blocked/clear states. Test transitions with the final cable lengths, LED effects and touching balls before fixing the debounce settings.

### Flipper inputs and coil-output lamps

Each side has **one blue momentary input button and one dedicated yellow output lamp** on the top panel. The P07 lamps have no push switch. Their Ø24.8 faces are larger than the blue buttons' Ø14 faces.

| Path | Connection and purpose |
| --- | --- |
| Input | Blue button's normally-open contacts → ESP switch input → configured flipper rule. Releasing the button opens the input again. |
| Output | ESP output → that side's P16 MOSFET control input. Protected 12 V supplies the module's load circuit and its separate yellow lamp, connected according to the module's terminal labels. Each lamp's power must pass through its own MOSFET-switched output. |
| Button lighting | Blue ring → steady protected 12 V backlight bus. It does not indicate the MOSFET output, and its LED pins remain separate from the switch contacts. |

The yellow lamp therefore shows the switched electrical output under a small load, including when an output test activates it without a button press. Configure the ESP rule and output safety limits; do not connect the button directly to the lamp or substitute a GPIO status LED. Check P16's terminal labels, active level and reset-OFF behaviour before connecting it; no board-specific terminal or GPIO assignment is implied here.

P07 is listed as **12–24 V AC/DC, 20 mA**. On this bench it uses 12 V. It represents a coil firing visually but cannot test coil current, inductive kick, flyback protection or mechanical movement. Its pulse/PWM response is unspecified: a visible flash is not a measurement of output pulse duration.

### LED strip and signal interfaces

**P09 uses one 2 m Tesfish roll.** At 60 pixels/m, the nominal cuts are **89 pixels / 1.483 m** for the perimeter and **6 pixels / 0.100 m** for each console row: **101 pixels / 1.683 m total**. That leaves **19 pixels / 0.317 m** spare, or **18 pixels / 0.300 m** if final fitting needs 102 pixels. Cut the continuous perimeter first, then the two short rows; dry-fit before cutting.

Use **one continuous perimeter strip** on the inside walls at about **z=110**, with a feed gap on the **right near y=285**. The nominal path is 1.495 m with 10 mm-radius corners: 89 pixels / 1.483 m leaves about 11.5 mm for the gap. These bends are design allowances, not a manufacturer-specified minimum radius. Dry-fit before cutting; keep pixels and any factory joins off bends, and never crease the strip.

Retain feed/data wires down the inner right wall to the console-side passage near **z=60**, clear of button tails and the converter. Feed power at the strip start and approximately opposite side. The end-of-strip data continues to the console's **six status pixels and six key-light pixels**, each row about 100 mm. Nominal total **101 pixels**; the power budget allows **102** after final trimming. Use the supplied adhesive on clean, smooth timber, supplemented by clips where needed.

The two level-shifting parts have different jobs:

| Part | Connection | Why it is included |
| --- | --- | --- |
| P19 **74AHCT125** | ESP 3.3 V output → 5 V LED data | Actively drives the precisely timed, one-way WS2812 signal. It is a bare IC soldered to the interface board. |
| P20 **bidirectional I²C module** | ESP ↔ LCD SDA/SCL, 3.3 V ↔ 5 V | Allows the LCD bus to work in both directions. Neither part supplies LED load power. |

P19 provides the LED strip's 5 V data signal from the ESP's 3.3 V output ([Adafruit's AHCT125 guidance](https://www.adafruit.com/product/1787)). P20 handles the bidirectional LCD I²C bus; its pull-up-based signals have different drive characteristics ([Adafruit's explanation](https://www.adafruit.com/product/757)).

The component schedule uses **one chained LED data stream**, one AHCT125 channel and one 330 Ω resistor; it does not assign a GPIO. Use the IC datasheet for pinout/enables, define unused inputs and leave unused outputs disconnected. Verify the LCD's actual I²C device/address and driver.

## Single soldered interface board

All the small interface circuits fit on **one proposed 70 × 50 mm isolated-pad perfboard**: ten button pull-ups, two lamp-control pull-downs, LED data conditioning, LCD level shifting and LED reservoir capacitors. The Pi, ESP, converters, fuses and two ready-made lamp drivers remain on their existing mounts. The eight optical receivers connect directly to ESP inputs with internal pull-ups.

![Proposed 70 by 50 mm interface board with ten button resistors, LED buffer, LCD level converter and two reservoir capacitors.](./media/bench-interface-realistic-v1.png)

This AI-generated close-up illustrates component appearance and assembly. **Use the drawings and connection tables below for wiring.** The received P21 board must provide at least **24 × 16 usable isolated pads at 2.54 mm pitch**; its hole count, fixing pattern and component clearances have not been verified. The design is not yet a solder-ready template or tested circuit.

### Board layout and fitted parts

![Dimensioned component-side layout of the single interface perfboard.](./media/bench-interface-layout-v1.png)

Use design columns **A–X** and rows **1–16**; these are our labels, not the kit manufacturer's markings. A1 is nominally **5.79 mm from the left and 5.95 mm from the top** of the 70 × 50 outline. Translate the complete grid to the received board only after checking edge and fixing clearances. U1's notch points left; pin 1 is **C14**, not C11. R1–R10 lie flat; R11–R14 stand upright, with their long return leads insulated. U2 mounts on its supplied two six-pin headers, soldered at both ends.

| Fitted item | Quantity / lead positions | Existing Amazon purchase / fit requirement |
| --- | --- | --- |
| Isolated-pad perfboard | 1 × **70 × 50 mm**, nominal 1.6 mm thick | [P21 electronics kit](https://www.amazon.co.uk/dp/B0FFTDD9JQ). Verify grid, insulation between pads and actual thickness. No connected stripboard. |
| R1–R10, **4.7 kΩ** | 10; columns **B D F H J L N P R T**, each from row **2 to 6** | P21; 10.16 mm lead span. Allow body up to about 6.3 × 2.5 mm; measure supplied parts. |
| R11 / R12, **10 kΩ** | **K11–K12 / K14–K15** | P21; left/right lamp controls. Fit only for verified active-high P16 inputs. |
| R13, **10 kΩ** | **A12–A13** | P21; holds LED input low when ESP pin is undriven. |
| R14, **330 Ω** | **V12–V13** | P21; series LED-data resistor. Keep the last lead to the first pixel short. |
| U1, **74AHCT125 DIP14** | Pins **1–7 = C14–I14**; **14–8 = C11–I11** | [P19 Adafruit ADA1787](https://www.amazon.co.uk/dp/B00XW2L39K); 2.54 mm lead pitch, 7.62 mm row spacing. Direct soldering; no socket allocated. |
| U2, **bidirectional I²C module** | HV row **N10–S10**; LV row **N14–S14** | [P20 RUNCCI-YUN](https://www.amazon.co.uk/dp/B082F6BSB5); PCB 15 × 13 mm in this orientation. **10.16 mm row spacing is a design assumption**: verify before soldering. |
| C1, **100 nF ceramic** | **C9–D9**; non-polarised | P21; short links to U1 VCC/GND, close to pin 14. |
| C2 / C3, **470 µF / 16 V each** | C2 **+V2, −X2**; C3 **+V7, −X7** | P21; **940 µF in parallel**. Each must fit **Ø10 × 16 mm maximum above the component face**. Measure actual size/lead pitch; stripe marks negative. |
| Board mounting and harness | Four **10 mm** nylon spacers; insulated leads, ties, heat-shrink and solder | Existing F01, F05/F06, F08, F10 and F14 rows. No additional purchased interface module or connector kit. Final panel attachment hardware remains unselected. |

All purchases are already on the priced shopping list; this design adds no item to its subtotal. That does **not** resolve the existing unselected MDF mounting hardware or prove the kit's delivered footprint. The P20 module photograph shows its pull-up network; confirm its resistor markings and low/high-side rails before use. Do not add a second set of I²C pull-ups by default.

### Wiring diagram and harness

![Electrical schematic showing button pull-ups, lamp pull-downs, LED buffer and capacitors, and LCD level shifting.](./media/bench-interface-wiring-v1.png)

The LED buffer and C2/C3 use **5V_LED**, from the protected lighting branch. U2's high side and LCD use **5V_LOGIC**, from the separate logic branch. **Never join these positive rails or feed either into ESP USB VBUS.** Their grounds are common; the board's 3V3 comes from the USB-powered ESP. U1 channel 1 is enabled by grounding pin 1; this is not an output safety interlock. Firmware still controls safe output operation.

| Connection | Board pad(s) | Other end |
| --- | --- | --- |
| ESP supply reference | **P15 = 3V3**, **Q15 = GND** | ESP 3.3 V and GND terminals; no external feed into ESP 5 V. |
| Logic supply | **M9 = 5V_LOGIC** | Fused logic branch; LCD supply leaves at P9. |
| Lighting supply / reservoir spur | **V7 (+), X7 (−)** capacitor-lead joints | Short paired feed from the lighting distribution near the first pixel. Use retained 18 AWG leads joined to the capacitor leads; do not force thick wire into a small pad hole or remove strands. |
| LED data | **A11** input; **X13** output and **X12** companion GND | ESP LED output → A11; X13/X12 → first pixel DIN/GND. X10/X11 are lighting-rail test pads, not a high-current output connector. |
| LCD low side | **N15 = SDA**, **O15 = SCL** | ESP I²C pins. Start at 100 kHz; confirm address/driver. |
| LCD high side | **N9 = SDA**, **O9 = SCL**, **P9 = 5V_LOGIC**, **Q9 = GND** | LCD's matching labelled pins. Follow its markings, not a guessed cable order. |
| Left lamp control | **K9** from ESP; **K10** to driver | P16's verified active-high control input; connect its control return to common GND as required by the received module. |
| Right lamp control | **K16** from ESP; **L16** to driver | Second P16 control input, with the same polarity/return checks. |
| Button return | **A8 = GND** | Daisy-chain only the ten switch-return contacts. The blue LED rings have their own 12 V supply/return wiring. |

| Input / resistor | ESP harness pad | Button contact pad | Panel function |
| --- | --- | --- | --- |
| BTN01 / R1 | B7 | B8 | Start |
| BTN02 / R2 | D7 | D8 | Fire |
| BTN03 / R3 | F7 | F8 | Lock |
| BTN04 / R4 | H7 | H8 | Ramp |
| BTN05 / R5 | J7 | J8 | Orbit |
| BTN06 / R6 | L7 | L8 | Target |
| BTN07 / R7 | N7 | N8 | Bump 1 manual trigger |
| BTN08 / R8 | P7 | P8 | Bump 2 manual trigger |
| BTN09 / R9 | R7 | R8 | Left flipper input |
| BTN10 / R10 | T7 | T8 | Right flipper input |

The sensor Bumper 1/2 events and manual Bump 1/2 buttons remain distinct inputs. Names here identify wires, **not ESP GPIO numbers**; the final pin assignment must check the actual breakout, boot pins and firmware manifest.

### Copper-side links

![Mirrored solder-side connection map with separate supply rails and insulated point-to-point links.](./media/bench-interface-solder-v1.png)

View the copper side by flipping the component drawing left-to-right: **X is now on the left, A on the right**. Join only the pads listed on each table row. Lines are connection guides, not etched tracks; use insulated wire over crossings and intermediate pads. A crossing does not make a junction. Do not solder the unused output/channel pads to a passing link.

<!-- interface-net-table:start -->
| Net | Join these pads with insulated links |
| --- | --- |
| 3V3 | B2, D2, F2, H2, J2, L2, N2, P2, R2, T2, P14, P15 |
| GND | D9, C14, G14, I14, E11, H11, K12, K15, A13, X2, X7, X11, X12, Q10, Q9, Q14, Q15, A8 |
| 5V_LED | V2, V7, X10, C9, C11, D11, F14, G11 |
| 5V_LOGIC | M9, P9, P10 |
| LED_IN | A11, A12, D14 |
| LED_BUFFER | E14, V12 |
| LED_DIN | V13, X13 |
| LAMP_L | K9, K10, K11 |
| LAMP_R | K14, K16, L16 |
| SDA_3V3 | N14, N15 |
| SCL_3V3 | O14, O15 |
| SDA_5V | N9, N10 |
| SCL_5V | O9, O10 |
| BTN01 | B6, B7, B8 |
| BTN02 | D6, D7, D8 |
| BTN03 | F6, F7, F8 |
| BTN04 | H6, H7, H8 |
| BTN05 | J6, J7, J8 |
| BTN06 | L6, L7, L8 |
| BTN07 | N6, N7, N8 |
| BTN08 | P6, P7, P8 |
| BTN09 | R6, R7, R8 |
| BTN10 | T6, T7, T8 |
| No connection | H14, I11, F11, R10, S10, R14, S14 |
<!-- interface-net-table:end -->

The U2 high row is **HV1, HV2, HV, GND, HV3, HV4** from N10 to S10; the low row is **LV1, LV2, LV, GND, LV3, LV4** from N14 to S14. Match the delivered module's labels before mapping it to the grid. Unused U1 outputs are pins **6, 8 and 11**; unused inputs **5, 9 and 12** go to GND and unused enables **4, 10 and 13** go to 5V_LED. The [TI pinout and operating specifications](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf) support this connection schedule. [Adafruit's I²C level-shifter explanation](https://www.adafruit.com/product/757) describes the circuit type, not a certification of the selected third-party module.

### Mounting, assembly and checks

The board mounts **components downward** under the removable panel, in the **80 × 50 mm bay at x=273, y=260**; the PCB itself occupies **x=278–348, y=260–310**. Put the capacitor/data-output edge nearest the right box wall. The nominal 10 mm spacers put the solder face at z=79; with 1.6 mm board thickness and 16 mm components, the lowest part is **z=61.4**. This remains within the z=60–89 reservation and above the converter's z≤45 allowance. Keep copper-side links below 3 mm high. Corner holes and spacer/nut clearance must be checked on the delivered board; do not drill from the illustration.

Retain the four spacers with through-fixings or adequately sized glued MDF pads after checking the actual kit's threads and panel clearances. F01 does not yet establish the complete panel attachment. Fit harness restraints to the MDF next to the board so no cable load reaches a solder pad. Keep the main LED supply/return in the external WAGO/18 AWG distribution. The capacitor spur carries charging/transient current, so it needs robust joints and restraint too; it is not a strip-power pass-through.

The right-edge route through the existing wall passage gives a target of **about 100 mm** from R14 to the first pixel, with a GND companion wire. This is a packaging target, not a guaranteed signalling limit. [Adafruit recommends the resistor at the first-pixel end and a reservoir at the strip input](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices). Prove this short connection at full effects/current; if the actual route must be substantially longer, revise the board position or put R14 at the pixel rather than claiming this layout is equivalent. Do not add the normal 150–200 mm service loop to this data lead: disconnect its labelled, existing strip connector (data/GND only; keep its +5 V contact unused and insulated) with both supplies off before fully lifting the panel. Label and disconnect other short power leads as needed.

1. **Dry-fit:** measure the board grid, corner holes, capacitor envelopes, U2 header spacing and the installed stack. Check all three positive rails remain separate. Do not solder against an unverified module footprint.
2. **Assemble:** fit the ten flat resistors, U1 and C1, then upright resistors, U2 and capacitors. Keep IC notch/pin 1 and capacitor polarity visible. Use short, insulated links; add labelled harness tails and strain relief last. The copper-side map and component drawing share the same pad names.
3. **Unpowered checks:** inspect every joint; check net continuity and no supply shorts with the IC/module behaviour in mind. Confirm each button shorts only its input to GND, not its 12 V light pins. Confirm R11/R12 suit the actual P16 active level before connecting the drivers.
4. **Initial power:** leave lamp loads and the strip disconnected, apply appropriately fused bench supplies and verify 3.3 V/5 V rails and LCD low-side levels. No ESP input should be pulled to 5 V. Verify button states, LCD communication and buffer output, then power down before connecting the loads.
5. **Full bench:** check lamps remain OFF at boot/reset, sensor transitions, LED effects/full-white voltage drop and temperatures. Make/break connections with power off; stop outputs before shutdown or host swapping. Power sequencing and disconnected-harness behaviour have not been validated. Board-mounted pull-downs cannot control a driver whose signal lead is unplugged.

The generated connection check covers all 14 resistors, three capacitors, U1's 14 pins and U2's 12 pins: no duplicate component-lead holes, conflicting pad assignments or joined positive rails are present in the model. It does not inspect soldering, prove a delivered footprint, choose protective fuse values or replace a physical test.

## Power and host connections

### Single power inlet

**Power path:** external enclosed 12 V supply → right-side XT60 inlet → main fuse → separately protected Pi-converter, lighting/logic-converter and 12 V indicator branches. Mains stays outside the box. P24 Yahboom powers the Pi through its supplied USB-C bridge; P15 powers the lighting/display. Do not parallel their 5 V outputs or join the lighting rail to USB VBUS.

P24 is the selected Pi power board. The supply and inlet below are **awaiting confirmation and excluded from the shopping subtotal**. Prices were checked on 18 November 2026; listing claims are not independent load tests.

| Part awaiting confirmation | Item price | Required checks |
| --- | ---: | --- |
| [Weishuo 12 V / 20 A / 240 W car-socket adapter, B0HB4BXY3T](https://www.amazon.co.uk/dp/B0HB4BXY3T) | £26.16 | Advertised capacity is sufficient. Sustained output, cable rating and protection remain unverified. Replacing its low-voltage socket with XT60 would require proper termination; no mains modification. |
| [RUNCCI-YUN XT60E-M panel / female cable set, B0D46FPJ6D](https://www.amazon.co.uk/dp/B0D46FPJ6D), 5 pairs | £6.99 | Preferred contact arrangement: recessed female contacts on the live supply lead. Flange, cutout, screws, wooden-wall attachment and strain relief still need checking. |

The Yahboom board provides Pi 5 USB-PD power negotiation ([manufacturer](https://category.yahboom.net/collections/accessory/products/power-board-pi5), [technical manual](https://wiki.geekworm.com/YB-MPP01)). Check Pi power detection and available USB power against [Raspberry Pi's power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply).

Planning allowances are **25.5 W Pi/USB peripherals**, **30.6 W for 102 pixels at 60 mA each**, **5 W sensors/LCD/interface**, and a provisional **10 W for 12 V lamps/rings**. At 90% converter efficiency, `(25.5 + 30.6 + 5) / 0.90 + 10 = 77.9 W`, or **6.5 A at 12 V**; at 80%, **7.2 A**. An enclosed **12 V / 10 A** supply is a reasonable target; a verified Amazon supply is not yet selected. This budget excludes real coils.

**Fuse values and wire sizes remain pending.** P17 allocates three positions to the protected 12 V branches: Pi converter, lighting/logic converter and indicators; the fourth is spare. Three P18 inline holders provide the main 12 V fuse and separate 5 V lighting/logic fuses. Their body-and-lead reservations are shown in the plan, but actual holder fit and distribution wiring remain unverified. Check P17 circuit isolation and terminal identity before wiring.

| Branch / connection | Intended wiring |
| --- | --- |
| Pi | Protected 12 V → P24 → Pi USB-C. Yahboom below Pi; complete stack and bends must fit the conditional 110 × 70, z=6–58 reservation. |
| Lighting | Protected 12 V → P15 → separately fused 5 V strip/console feeds and AHCT125 buffer. **6.12 A / 30.6 W** is a conservative planning maximum, not measured demand. |
| Logic | Separately protected P15 5 V → LCD, I²C high side and optical heads. Signals/pull-ups and I²C low side use ESP 3.3 V. |
| Indicators | Protected 12 V → two independent P16 MOSFET load circuits → left/right P07 yellow lamps. Separate parallel 12 V bus powers the steady blue button rings. Verify terminal labels, input polarity and reset-OFF behaviour. |
| Returns/distribution | Common low-voltage ground, with main LED return directly to the converter. No strip current through ESP, sensor wiring or USB. Six WAGOs are reserved; each joins all five ports into one node. Use one conductor per port and retained insulated splices for branching. Confirm node allocation, including the Pi branch. |
| I/O | Ten buttons + eight optical receivers = **18 inputs**, plus two lamp outputs, LCD I²C and LED data. Confirm available pins and boot/flash restrictions before assigning GPIOs. |

### Normal Mac use and portable Pi demos

The **Mac is the normal host**; the **Pi is for portable demos**. Connect the Mac data cable directly to the ESP serial/programming USB-C port. For demos, open the box, unplug it and connect P23 from Pi USB-A to **the same ESP port**. No USB switch, hub, selector or extra panel USB socket is included.

Disable outputs and stop the current bridge/flashing process before swapping, then start the new host's bridge. USB supplies the ESP as well as data; expect a disconnect and possible restart. Do not connect both hosts through different ESP sockets or add a parallel 5 V feed to its USB-powered rail. Keep configuration/media on both hosts consistent; cable swapping does not synchronise them. The existing Mac cable is assumed available.

## Amazon.co.uk shopping list

Tick **Need** for items you need to buy. Rows stay in their original order and the **Need** label stays unchanged. Your selections stay in this browser, and the remaining estimate totals ticked items at the listed whole-pack prices. Partial quantities are not tracked. The subtotals below show the full purchase cost.

<div class="parts-checklist" data-parts-checklist="test-bench" hidden></div>
<noscript>Enable JavaScript to mark needed items and calculate what is still needed. The complete shopping list remains readable below.</noscript>

**Working purchase schedule, not a complete build order.** Prices/variants and photographs were checked on **18 November 2026**. Dimensions marked unpublished are still unknown; reserved envelopes are design allowances. Thumbnails enlarge and may show whole packs, not fitted quantities. Tables scroll horizontally; the dashed edge indicates more columns.

Totals use whole packs and one-time new offers, including items marked “if needed”; subtract existing stock when applicable. P10 uses the lowest displayed new buying option. Delivery is excluded: P19 showed **£6.32**, P24 **£14.99** additional delivery. No coupons, subscriptions or used offers are assumed. Prices and availability can change.

| Purchase group | Item subtotal |
| --- | ---: |
| Box, course and controls (P01–P09, MDF sheets) | £245.56 |
| Controllers, interfaces and power (P10–P24) | £288.87 |
| Fixings, wire and consumables (F01–F15) | £115.23 |
| **Selected priced items — incomplete build subtotal** | **£649.66** |

**Excluded:** external supply/inlet, any additional protection/wiring, MDF mounting hardware still to be specified, finish, tools and delivery. The subtotal does not cover a complete kit.

### Box, ball course and controls

| ID / quantity | Exact product and variant | Price / buy unit | Line total | Published dimensions / specification | Installation and evidence |
| --- | --- | ---: | ---: | --- | --- |
| P01 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p01.jpg" alt="P01: WooDeeDoo B0973KZMGK" width="84" height="84" loading="lazy"> [WooDeeDoo B0973KZMGK](https://www.amazon.co.uk/dp/B0973KZMGK?th=1), **40 × 40 × 13.5 cm** | £33.99 | **£33.99** | Outside **400 × 400 × 135 mm**; inside **approximately 380 × 380 × 125 mm**; 3 mm birch-ply lid/base | Listing text. Original hinges included. The inner size is approximate; check the delivered box and hinge intrusion. |
| P02 · 1 pack of 3 | <img class="part-thumbnail" src="./media/test-bench-parts/p02.jpg" alt="P02: sourcing map chrome steel balls, 27 mm" width="84" height="84" loading="lazy"> [sourcing map chrome steel balls, 27 mm](https://www.amazon.co.uk/dp/B0CCJXJJWR) | £11.19 | **£11.19** | **Ø27 mm**, three balls | Listing size. 30 mm clear lane gives 3 mm total lateral clearance. Not a claim of regulation pinball weight or diameter. |
| P03 · 2 sheets | <img class="part-thumbnail" src="./media/test-bench-parts/mdf-option.jpg" alt="P03: GATE8 6 mm moisture-resistant MDF, 600 × 600 mm" width="84" height="84" loading="lazy"> [GATE8 moisture-resistant MDF, B0B21V5VRM](https://www.amazon.co.uk/dp/B0B21V5VRM), **600 × 600 mm, 6 mm thick** | £17.00 | **£34.00** | **600 × 600 × 6 mm** each; one sheet per buy unit | Cut into the carrier, course floor, console top, gate and covers. Keep offcuts for support layers and shims. Listing size/price checked 18 November 2026; in stock. Preserve the full carrier thickness; underside fixings need specifying. See mounting notes. |
| P04 · 1 sheet | <img class="part-thumbnail" src="./media/test-bench-parts/mdf-option.jpg" alt="P04: GATE8 12 mm moisture-resistant MDF, 600 × 600 mm" width="84" height="84" loading="lazy"> [GATE8 moisture-resistant MDF, B0B25KRGVS](https://www.amazon.co.uk/dp/B0B25KRGVS), **600 × 600 mm, 12 mm thick** | £23.00 | **£23.00** | **600 × 600 × 12 mm**; one sheet | Cut into the upright ball-guide walls (30 mm high), console support walls (83 mm high), end stops, support blocks and backing. Listing size/price checked 18 November 2026; in stock. Glue fixed joints; pad and cover fixings need specifying. Same generic seller photograph as P03; use the linked thickness. |
| P05 · 8 pairs | <img class="part-thumbnail" src="./media/test-bench-parts/p05.jpg" alt="P05: Adafruit ADA2167 3 mm break-beam sensors" width="84" height="84" loading="lazy"> [Adafruit ADA2167 3 mm break-beam sensors](https://www.amazon.co.uk/dp/B01BU6YBWU) | £11.16 | **£89.28** | Each head **20 × 10 × 8 mm**; cable **230 mm**; 3.3–5.5 V | Amazon product identity; dimensions and open-collector output from [Adafruit](https://www.adafruit.com/product/2167). Both heads powered; only receiver signal goes to ESP, using its internal 3.3 V pull-up. No external sensor circuit planned. Sixteen heads total; first prove one pair with touching balls. |
| P06 · 3 packs of 4; use 10 | <img class="part-thumbnail" src="./media/test-bench-parts/p06.jpg" alt="P06: Gebildet 12mm Momentary Blue LED High Head buttons" width="84" height="84" loading="lazy"> [**Gebildet 12mm Momentary Blue LED High Head**](https://www.amazon.co.uk/dp/B088CNW12P?th=1), B088CNW12P | £7.89 | **£23.67** | Face **Ø14 mm**, hole **Ø12 mm**, actuator **Ø7.4 mm**; maximum panel **8 mm**; separate **12–24 V DC blue LED** and normally-open momentary contact. | Supplied nuts; solder terminals. Overall depth/cap height unpublished: verify the 35 mm rear / 10 mm top allowances. Gallery/text disagree on thread pitch (0.75/0.8 mm); use supplied nuts in plain holes. [Terminal drawing](./media/test-bench-parts/p06-dimensions.jpg). |
| P07 · 1 pack of 2; use both | <img class="part-thumbnail" src="./media/test-bench-parts/p07-indicator.jpg" alt="P07: PATIKIL dedicated yellow indicator lamps, 22 mm" width="84" height="84" loading="lazy"> [PATIKIL indicator lights, B0FBGLDVNQ](https://www.amazon.co.uk/dp/B0FBGLDVNQ), **Yellow, 22mm** | £8.49 | **£8.49** | **Ø24.8 face / Ø16 luminous area / Ø22 hole / 15 mm thread**; 12–24 V AC/DC, 20 mA; leads about 205 mm | Dedicated lamps with supplied nuts, no switches. One 12 V load per P16 MOSFET. [Listing dimension image](./media/test-bench-parts/p07-indicator-dimensions.jpg). Complete depth, cap height and grip unpublished; reserve 35 mm wired rear / 5 mm above panel until measured. Check nut engagement through 6 mm MDF. |
| P08 · 1 display | <img class="part-thumbnail" src="./media/test-bench-parts/p08-single.jpg" alt="P08: Freenove I²C LCD1602, new type, single display" width="84" height="84" loading="lazy"> [Freenove I²C LCD1602, B0B76YGDV4](https://www.amazon.co.uk/dp/B0B76YGDV4?th=1), **I2C 1602** (single pack) | £7.95 | **£7.95** | PCB **80 × 36 mm**, mounting holes **Ø3 mm**; 16 characters × 2 lines; integrated I²C conversion circuit | [Gallery dimensions](./media/test-bench-parts/p08-dimensions.jpg). Bezel, hole centres and complete thickness unpublished. Keep the 100 × 50 reservation, 30 below / 5 above panel; trace the received bezel. In stock, sold by Freenove-EU / dispatched by Amazon; checked 18 November 2026. |
| P09 · 1 roll of 2 m; reuse if owned | <img class="part-thumbnail" src="./media/test-bench-parts/p09-tesfish-2m.jpg" alt="P09: Tesfish WS2812B, 2 m / 120 LEDs, black PCB" width="84" height="84" loading="lazy"> [Tesfish WS2812B, B0D5B5CGVX](https://www.amazon.co.uk/dp/B0D5B5CGVX), **2m 120leds Ws2812b** | £13.99 | **£13.99** | **2000 × 10 mm**, thickness unpublished; **5 V**, 60 individually addressable pixels/m; nominal **16.67 mm cut pitch** (gallery rounds to 17 mm). Title says IP30, description IP20: indoor, non-waterproof use. | Self-adhesive; three-pin JST-SM and separate power leads at both ends. Cut 89 perimeter + 6 status + 6 key pixels; 19 spare nominally. [Dimension / mounting image](./media/test-bench-parts/p09-tesfish-dimensions.jpg). Keep the perimeter continuous; dry-fit bends and any factory joins. In stock, sold by Newjack / dispatched by Amazon, checked 18 November 2026. |

### Controllers, interfaces and power

| ID / quantity | Exact product and variant | Price / buy unit | Line total | Published dimensions / specification | Installation and evidence |
| --- | --- | ---: | ---: | --- | --- |
| P10 · 1 if needed | <img class="part-thumbnail" src="./media/test-bench-parts/p10.jpg" alt="P10: Raspberry Pi 5, SC1111, 4 GB" width="84" height="84" loading="lazy"> [Raspberry Pi 5, SC1111, 4 GB](https://www.amazon.co.uk/dp/B0CK3L9WD3) | £124.70 (lowest new offer) | **£124.70** | PCB **85 × 56 mm**; holes **Ø2.7 mm**, **58 × 49 mm** centres | Amazon identity; [official mechanical drawing](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf). Reserve 110 × 70 mm including USB connection space. Existing Pi 5 can be reused. |
| P11 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p11.jpg" alt="P11: Official Raspberry Pi Active Cooler, SC1148" width="84" height="84" loading="lazy"> [Official Raspberry Pi Active Cooler, SC1148](https://www.amazon.co.uk/dp/B0CLXZBR5P) | £8.29 | **£8.29** | **63.5 × 42.5 × 13.7 mm** | [Official drawing](https://pip-assets.raspberrypi.com/categories/993-raspberry-pi-active-cooler/documents/RP-008187-DS-1-raspberry-pi-active-cooler-mechanical-drawing.pdf?disposition=inline) and Amazon model. Supplied push pins, thermal pads and fan lead; connect to Pi fan socket. No additional Pi enclosure. |
| P12 · 1 if needed | <img class="part-thumbnail" src="./media/test-bench-parts/p12.jpg" alt="P12: SanDisk High Endurance 32 GB microSDHC" width="84" height="84" loading="lazy"> [SanDisk High Endurance 32 GB microSDHC](https://www.amazon.co.uk/dp/B07P14QHB7) | £22.55 | **£22.55** | **32 GB**, microSD form factor; standard card envelope **15 × 11 × 1 mm** | Capacity verified in listing; card envelope is the microSD format, not a measured sample. Existing configured card can be reused. Keep access to the Pi card edge. |
| P13 · 1 pack of 2; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p13.jpg" alt="P13: Freenove ESP32-S3, 16 MB Flash, 2 Pack" width="84" height="84" loading="lazy"> [Freenove ESP32-S3, 16 MB Flash, 2 Pack](https://www.amazon.co.uk/dp/B0FRRJCDHF), **FNK0099K** | £21.95 | **£21.95** | 16 MB flash / 8 MB PSRAM, USB-C; complete board dimensions not published | Verify the delivered board revision, firmware target and pinout before deployment; this design does not assign GPIO numbers. |
| P14 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p14.jpg" alt="P14: Freenove FNK0091 breakout" width="84" height="84" loading="lazy"> [Freenove FNK0091 breakout](https://www.amazon.co.uk/dp/B0CD2512JV) | £11.95 | **£11.95** | PCB **87 × 75 mm**; 2.54 mm headers | Gallery PCB size (not packaging). Manufacturer lists Freenove ESP32/S3 compatibility. Populated height unpublished; 97 × 105 bay, z≤50 allowance. No separate barrel power. |
| P15 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p15.jpg" alt="P15: VOLRANTISE converter" width="84" height="84" loading="lazy"> [VOLRANTISE converter](https://www.amazon.co.uk/dp/B09WZ9DC9W), **12/24 V to 5 V 10 A** | £11.99 | **£11.99** | **53 × 50 × 20 mm**; 10–35 V input; 5 V / 10 A advertised output | Amazon dimension drawing. Reserve 90 × 53 mm with connections facing sideways. Supplies lighting/display, not Pi USB-C. Verify output voltage and temperature under the actual load. |
| P16 · 1 pack of 4; use 2 | <img class="part-thumbnail" src="./media/test-bench-parts/p16.jpg" alt="P16: JZK F5305S optocoupled MOSFET modules" width="84" height="84" loading="lazy"> [JZK F5305S optocoupled MOSFET modules](https://www.amazon.co.uk/dp/B09SWRF88D) | £7.09 | **£7.09** | Each **47 × 25 × 15 mm**; input 3–24 V, about 5 mA; load supply 5–36 V | Listing text. One board per flipper lamp; two side by side in a 55 × 65 mm bay including bends. Read the board terminal labels; do not infer a generic low-side wiring topology. |
| P17 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p17.jpg" alt="P17: Gebildet four-way covered blade-fuse box" width="84" height="84" loading="lazy"> [Gebildet four-way covered blade-fuse box](https://www.amazon.co.uk/dp/B076P4LBSG), **4 way** | £8.44 | **£8.44** | **87 × 52 × 42 mm**; **6.3 mm tabs** | Gallery dimensions; four isolated circuits required, verify by continuity. Cover/eight spades/mixed fuses included. Three 12 V branches: P24, P15 and indicators; fourth spare. Holder and connection envelope shown in the plan. |
| P18 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/p18.jpg" alt="P18: iLulala six holders / 66 standard blade fuses" width="84" height="84" loading="lazy"> [iLulala six holders / 66 standard blade fuses](https://www.amazon.co.uk/dp/B0DKX9R1FK) | £7.99 | **£7.99** | Six each of **2, 3, 5, 7.5, 10, 15, 20, 25, 30, 35, 40 A** | Six inline holders plus 66 fuses; standard ATO/ATC format. Use three holders: main 12 V, 5 V lighting and 5 V logic. Body/lead dimensions and fuse ratings remain unverified; plan shows conditional reservations. Confirm seating in P17. |
| P19 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p19.jpg" alt="P19: Adafruit ADA1787 / 74AHCT125" width="84" height="84" loading="lazy"> [Adafruit ADA1787 / 74AHCT125](https://www.amazon.co.uk/dp/B00XW2L39K) | £3.46 (+ £6.32 delivery shown) | **£3.46** | **14-pin through-hole DIP**, 2.54 mm pitch | **LED data:** raises ESP 3.3 V data to 5 V; actively driven, one-way buffer. Bare IC soldered to P21, not a ready-made module. [TI datasheet](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf). |
| P20 · 1 pack of 15; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p20.jpg" alt="P20: RUNCCI-YUN four-channel I²C level converters" width="84" height="84" loading="lazy"> [RUNCCI-YUN four-channel I²C level converters](https://www.amazon.co.uk/dp/B082F6BSB5) | £6.99 | **£6.99** | PCB **13 × 15 mm**, 2.54 mm header pitch | **LCD data:** bidirectional SDA/SCL conversion between 3.3 V and 5 V. Solder to P21; not the selected WS2812 buffer substitute. |
| P21 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/p21.jpg" alt="P21: OFNMY 1628-piece electronics kit" width="84" height="84" loading="lazy"> [OFNMY 1628-piece electronics kit](https://www.amazon.co.uk/dp/B0FFTDD9JQ), **1628 PCS** | £22.99 | **£22.99** | PCBs **20 × 80, 30 × 70, 40 × 60, 50 × 70 mm** | Gallery contents include 330 Ω, 4.7 kΩ and 10 kΩ resistors (20 each), 100 nF ceramics, and 470 µF / 16 V electrolytics. Use the 50 × 70 mm board for interfaces; the other boards are spares; detailed component use below. Breadboards are for the preliminary test only. |
| P22 · 1 pack of 25 | <img class="part-thumbnail" src="./media/test-bench-parts/p22.jpg" alt="P22: WAGO 221-415, five-lever connectors" width="84" height="84" loading="lazy"> [WAGO 221-415, five-lever connectors](https://www.amazon.co.uk/dp/B0107SYYGU), **5-Lever** | £11.00 | **£11.00** | **29.9 × 18.6 × 8.3 mm**; 0.14–4 mm² flexible copper | [Manufacturer dimensions](https://www.wago.com/global/installation-terminal-blocks-and-connectors/splicing-connector-with-levers/p/221-415). Allow up to six connectors for power distribution, retained by cable ties with levers accessible. Each connector joins all five ports; it is not five isolated poles. |
| P23 · 1 pack of 2; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p23.jpg" alt="P23: Anker USB-A to USB-C cable" width="84" height="84" loading="lazy"> [Anker USB-A to USB-C cable](https://www.amazon.co.uk/dp/B0D5XY3C2T), **0.3 m + 0.3 m, Black** | £5.49 | **£5.49** | **300 mm including connectors**, USB 2 data up to 480 Mbit/s | Listing explicitly confirms data support. Pi USB-A to the ESP programming/serial USB-C port. Connector moulding dimensions not published; use the reserved connection spaces. |
| P24 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p24.jpg" alt="P24: Yahboom Pi 5 PD power expansion board" width="84" height="84" loading="lazy"> [Yahboom Pi 5 PD power board, B0D3L6Y92G](https://www.amazon.co.uk/dp/B0D3L6Y92G) | £13.99 | **£13.99** | PCB **65 × 56 mm**; **7–24 V input → 5 V / 5 A** with Pi 5 USB-PD negotiation | Selected Pi converter; supplied stacking hardware/dual-USB-C bridge. [Technical specification](https://wiki.geekworm.com/YB-MPP01). Mount beneath Pi, cooler above. Complete stack/bridge/bends reserved within 110 × 70, z=6–58; actual height, airflow and terminal access unverified. Offer adds £14.99 delivery; £28.98 delivered, estimated 14 December 2026 at check. No extra buck in series. |

### Fixings, wire and consumables

| ID / quantity | Exact Amazon.co.uk product | Price / buy unit | Line total | Size / contents | Use |
| --- | --- | ---: | ---: | --- | --- |
| F01 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f01.jpg" alt="F01: WiMas 940-piece nylon standoffs" width="84" height="84" loading="lazy"> [WiMas 940-piece nylon standoffs](https://www.amazon.co.uk/dp/B0CJFG1XDR), Black | £14.99 | **£14.99** | M2/M2.5/M3/M4; gallery includes **10 mm body + 6 mm male stud**, M2.5×6 and M3×6 screws/nuts | Pi uses M2.5; match other board holes. Standoff retention must preserve the full MDF thickness and leave the carrier flat on the box base; fixings are not yet specified. |
| F02 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f02.jpg" alt="F02: AMLOOPH 535-piece wood screws" width="84" height="84" loading="lazy"> [AMLOOPH 535-piece wood screws](https://www.amazon.co.uk/dp/B0CPF54WYQ) | £6.99 | **£6.99** | M2×6/10; M2.5×12/16/20; M3×8/10/12/16/20 mm | Pilot-drilled wooden joints, clips, console screws and backing. Choose length by the actual material stack; do not blindly use fitting-kit screws. |
| F03 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f03.jpg" alt="F03: Jeboler 500 nylon washers" width="84" height="84" loading="lazy"> [Jeboler 500 nylon washers](https://www.amazon.co.uk/dp/B0D4952M2T) | £2.68 | **£2.68** | M2, M2.5, M3, M4, M5, M6, M8, M10 | Protect PCB/plastic flanges and spread small-screw loads. Exact washer thickness is not listed; allow and measure it in the fastening stack. |
| F04 · 1 bottle if needed | <img class="part-thumbnail" src="./media/test-bench-parts/f04-evo-stik.jpg" alt="F04: EVO-STIK Exterior Wood Glue, 250 ml" width="84" height="84" loading="lazy"> [EVO-STIK Exterior Wood Glue, B0002JT0J6](https://www.amazon.co.uk/dp/B0002JT0J6), **250ML** | £4.19 | **£4.19** | One **250 ml** bottle; D3 PVAc wood adhesive, suitable for MDF | Frame, rails, cleats, pads and lid backing; clamp and cure per bottle instructions. Do not glue the removable console. Price/variant checked 18 November 2026; [manufacturer guidance](https://diy.evo-stik.co.uk/en-UK/our-ranges/wood-adhesives/wood-glue-exterior). |
| F05 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f05.jpg" alt="F05: TUOFENG 18 AWG silicone wire" width="84" height="84" loading="lazy"> [TUOFENG 18 AWG silicone wire](https://www.amazon.co.uk/dp/B07G744V5Z), 18awg silicone wire set | £15.99 | **£15.99** | Six colours × **13.2 ft / about 4 m**; **2.3 mm OD**; 150×0.08 mm tinned-copper strands | 5 V lighting distribution and return. Check the combined 12 V main-feed gauge against length, current, connector and fuse ratings; this row does not approve 18 AWG for that feed. |
| F06 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f06.jpg" alt="F06: LEDLightsWorld 22 AWG silicone wire" width="84" height="84" loading="lazy"> [LEDLightsWorld 22 AWG silicone wire](https://www.amazon.co.uk/dp/B0GXYYP42B), **22 AWG / 0.3 mm²** | £16.90 | **£16.90** | Eight colours × **5 m**, 60×0.08 mm strands; seller rates 3 A | Signals, buttons, sensor extensions, LCD and low-current lamp branches. Includes extra ties/shrink; these are not relied on for the quantities below. |
| F07 · 1 pack of 20 | <img class="part-thumbnail" src="./media/test-bench-parts/f07.jpg" alt="F07: Switch Electronics fully insulated female spades" width="84" height="84" loading="lazy"> [Switch Electronics fully insulated female spades](https://www.amazon.co.uk/dp/B00XWE7S2Y) | £4.19 | **£4.19** | **6.3 × 0.8 mm**, red, **16–22 AWG** | Eight fuse-box connections, plus spares. Use these correctly sized crimps rather than assuming the included fuse-box spades fit 18 AWG. Lamp lead extensions, if needed, are soldered and insulated. |
| F08 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f08.jpg" alt="F08: ELECTRAPICK 560 heat-shrink pieces" width="84" height="84" loading="lazy"> [ELECTRAPICK 560 heat-shrink pieces](https://www.amazon.co.uk/dp/B092VWZN4W), **560PCS** | £6.50 | **£6.50** | **2:1**, **45 mm** lengths; ID 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 10, 13 mm | Insulate soldered joints and lamp lead extensions; choose size from the completed joint diameter. |
| F09 · 1 pack of 100 | <img class="part-thumbnail" src="./media/test-bench-parts/f09.jpg" alt="F09: VIPMOON LED strip clips" width="84" height="84" loading="lazy"> [VIPMOON LED strip clips](https://www.amazon.co.uk/dp/B0B6QQLY6Q), **Type 2 – 10 mm** | £7.99 | **£7.99** | For **10 mm strip**, 100 clips and screws | Supplementary retention at feed points/console rows, between pixels; perimeter primarily uses supplied adhesive. Clip body size unpublished; check pressure and use F02 short screws where needed. |
| F10 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f10.jpg" alt="F10: DYMHQ screw-mount cable-tie set" width="84" height="84" loading="lazy"> [DYMHQ screw-mount cable-tie set](https://www.amazon.co.uk/dp/B0F5GYZQ97) | £7.99 | **£7.99** | 200 saddles **15 × 10 × 7 mm**, 200 ties **100 mm**, 200 screws | Restrain harnesses and WAGO bodies. Use mechanically retained saddles on suitably sized MDF pads or through-fixings; verify engagement/edge distances. Do not screw into the original 3 mm base. |
| F11 · 1 roll | <img class="part-thumbnail" src="./media/test-bench-parts/f11.jpg" alt="F11: RS neoprene adhesive strip" width="84" height="84" loading="lazy"> [RS neoprene adhesive strip](https://www.amazon.co.uk/dp/B0086KQSMK), **10 mm wide / 3 mm thick** | £8.40 | **£8.40** | **10 mm × 3 mm × 10 m** | Padded transport cover, cable clamps and base pads. Not a structural adhesive or a substitute for inlet strain relief. |
| F12 · 1 pack of 2 | <img class="part-thumbnail" src="./media/test-bench-parts/f12.jpg" alt="F12: YOOZIYA A2/304 toggle catches" width="84" height="84" loading="lazy"> [YOOZIYA A2/304 toggle catches](https://www.amazon.co.uk/dp/B0GLZ2Y67C), **56 mm** | £4.49 | **£4.49** | **56 mm nominal length**, two catches/eight screws | Two on the front. Width, projection and hole pattern not dimensioned. Fit to the actual lid seam, with MDF backing/load-spreading fixings where needed; check closure before drilling. |
| F13 · 1 pack of 2; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/f13.jpg" alt="F13: FdcZeyxior locking lid stays" width="84" height="84" loading="lazy"> [FdcZeyxior locking lid stays](https://www.amazon.co.uk/dp/B0HCCBXGN8) | £3.99 | **£3.99** | **110 mm folded**, **40 mm foot width**; text says **190 mm** open, drawing **195 mm** | Outside right-rear; set pivots from received part and prove locking/closure. Open-length discrepancy unresolved. Back thin lid material; not a carry handle. |
| F14 · 1 reel if needed | <img class="part-thumbnail" src="./media/test-bench-parts/f14.jpg" alt="F14: 0.8 mm lead-free rosin-core solder" width="84" height="84" loading="lazy"> [0.8 mm lead-free rosin-core solder](https://www.amazon.co.uk/dp/B0BFW8TS6H), **0.8mm-15g(Net)** selected option (title says 20 g) | £3.79 | **£3.79** | **Ø0.8 mm**, Sn99.3/Cu0.7; budget one reel at the smaller **15 g net** option | Interface, LEDs and lamp joints. Budget the selected 15 g option despite the 20 g title. Listing melting-temperature text is inconsistent; follow the actual alloy/process. |
| F15 · 1 kit if needed | <img class="part-thumbnail" src="./media/test-bench-parts/f15-mitre-fast.jpg" alt="F15: Everbuild Mitre Fast, 50 g super glue and 200 ml activator" width="84" height="84" loading="lazy"> [Everbuild Mitre Fast, B00BDTF0PW](https://www.amazon.co.uk/dp/B00BDTF0PW), **50g/200ml** | £6.15 | **£6.15** | **50 g** high-viscosity cyanoacrylate + **200 ml** aerosol activator; suitable for MDF; bonds most surfaces in about **10 seconds**; gaps up to **0.2 mm** | Small, separate tack spots hold parts in position while F04 wood glue cures over the rest of the joint. Do not mix adhesives or replace the wood glue’s clamping/cure time. Trial on offcuts; F15 is not the load-bearing bond. Also suitable for non-load-bearing trim. [Manufacturer instructions and limitations](https://gbr.sika.com/dam/dms/gb01/6/everbuild-mitre-fast.pdf). One-time offer checked 18 November 2026. |

### Components taken from the electronics kit

P21 supplies the single **70 × 50 mm board**, **10 × 4.7 kΩ**, **3 × 10 kΩ**, **1 × 330 Ω**, **1 × 100 nF** and **2 × 470 µF / 16 V**. P19/P20 supply the two interface devices. The [single-board assembly schedule](#board-layout-and-fitted-parts) gives their locations, fit limits and wiring. Eight optical inputs use ESP internal pull-ups; no external sensor circuit is fitted. Main LED power stays in the external 18 AWG/WAGO distribution.

## Readable engineering checks and unresolved evidence

The geometry check finds no overlapping **modelled** module/keepout envelopes, including all ten buttons' **24 × 24 × 35 mm** wiring reservations. It includes conditional reservations for the Pi/Yahboom stack, three inline holders and right-side inlet/passage. It excludes individual wire routing, final fixing details, deflection and lid motion. No physical build, rolling, closure, transport or load test has been performed.

| Item | Current evidence / required next check |
| --- | --- |
| Box and carrier | 370 carrier in approximate 380 cavity leaves **5 mm each side**. Measure the delivered box, hinge intrusion and wall/base thickness before cutting. |
| Console and lamps | Stack **6 + 83 + 6 = 95 mm**. P07's conditional 5 mm cap ends at **z=100**, leaving 25 mm to nominal lid; 35 mm wired rear allowance ends at **z=60**. Published 15 mm thread does not establish complete depth or panel grip. Measure the received lamp and nut engagement. The taller button allowance ends at z=105, leaving **20 mm** overall nominal lid clearance. |
| Small buttons | Published Ø14 face / Ø12 hole / 8 mm maximum panel suit 6 mm sheet. Assumed 35 mm rear ends at **z=60**, 9 above fuse envelope; 10 mm cap ends at z=105. Actual overall depth and wired clearance remain unknown. |
| LCD and interface | LCD reservation z=65–100; Pi/Yahboom ends at z=58, leaving **7 mm nominal gap**. Interface z=60–89 clears the converter z≤45 by 15 mm; the proposed component bottom is z=61.4. Its pad grid, corner fixings, U2 row spacing and capacitor dimensions need measurement. Verify actual depths, cable bends, airflow and retention; these gaps are conditional. |
| Pi power and inlet | P24 board is 65 × 56; a complete-stack **110 × 70 × 52** envelope includes mounting, cooler, bridge and bends as an allowance only. Check actual assembly and cooling with the panel closed. Inlet and three holders have conditional bays; verify their bodies, wall passage, flange/cutout, attachment and strain relief. Supply/inlet selection, fuse ratings, wire sizes and distribution remain open. |
| MDF | P03/P04 supply 6/12 mm MDF. Carrier standoff retention, LCD retainers, console/sensor pads and transport-cover fixings need dimensioning and a clearance check. Additional hardware and finish are not selected. |
| Ball sensing | **30 − 27 = 3 mm** total lane clearance. Ideal **10.03 mm** touching-ball clear window at h=24 is geometry only. Test one pair first, then all eight stations at realistic speed/debounce, including corner and gate. |
| Lighting | **89 + 6 + 6 = 101** nominal pixels; budget **102**, within P09’s 120-pixel / 2 m roll. Width is 10 mm; thickness, minimum bend radius and factory-join spacing are unpublished. Verify these, adhesive and clip engagement before cutting. |
| Closure fittings | Catch pattern/projection unpublished; stay text says 190 mm open versus 195 mm drawing. Set holes/pivots from actual parts and prove locking/closure with lid backing clear of lamps. |
| Electrical validation | Verify driver reset-OFF/input polarity, sensor logic, LCD operation, Pi power detection, full-white voltage drop, current and cable/converter/Pi temperatures with intended ventilation. Fuse sizing must protect the actual conductors/connectors. |

The ESP must enforce arming, watchdog, pulse-limit and fault protections. GPIO assignments and firmware configuration must be verified for the fitted hardware.
