# Test Bench

**Design review: 18 November 2026.** A portable development rig in the **400 × 400 × 135 mm WooDeeDoo box**, with a real three-ball trough, hand-loaded shooter and manual launch gate. Ten **Gebildet 12mm Momentary Blue LED High Head** buttons, a flush LCD, two dedicated yellow coil-output lamps and addressable lighting exercise the controller alongside the rolling-ball course. Each flipper has a button and a separate, larger lamp, grouped on the left or right of the top panel.

**The design and shopping list are still provisional.** The agreed single 12 V inlet and selected Yahboom Pi power board are not yet fitted into the dimensioned layout. Several component depths also remain unpublished. The [remaining checks](#readable-engineering-checks-and-unresolved-evidence) explain what must be resolved before a full-build order or final drilling.

The construction uses cut sheet material, glued supports, drilled holes and a small soldered interface board. No printed brackets, custom PCB or machined trough are required. All purchase links are Amazon.co.uk; manufacturer links provide technical evidence.

## How the ball course works

1. Three 27 mm balls queue in the front-left trough: T1 at the end stop, then T2 and T3.
2. Transfer T1's ball **by hand** to the higher rear-right shooter pocket. The remaining balls roll forward, naturally changing the trough signals; T1/T2 become occupied and T3 empty.
3. The ball rests against the manual gate and blocks **Ready**. The **Fire** button sends a separate input; it does not move the gate.
4. Lift the gate 30 mm. The ball passes Onfield, Bumper 1, the enclosed corner, Bumper 2 and Drain, then returns to T3.

Bumper stations detect passage rather than kick the ball. The yellow lamps are actual loads switched by the two MOSFET outputs; they do not validate real coil current, flyback or flipper mechanics. This bench tests occupancy and event sequences without an automatic trough ejector.

## Layout and illustrations

![Provisional scale plan: course, console and reserved electronics bays. Yahboom power-board mounting and the revised inlet are not included.](./media/bench-course-layout.png)

The drawing uses nominal component envelopes, including connector space, rather than exact PCB outlines. **It is a placement study, not a drilling template or proof of physical fit.** The power revision and proposed MDF fixings still need integrating. External catches/stay are outside the quoted box size; adapter storage inside the box is not allocated.

![Earlier front-right illustration with the panel installed, ten 12mm Momentary Blue LED High Head buttons, right-side LED feed and flush LCD. Power entry is superseded.](./media/bench-course-front-right-v5.png)

This earlier AI illustration shows the general arrangement. Its **yellow arcade buttons, flipper-control positions, two external power leads and plywood interior are superseded** by the dedicated lamps, paired controls, single inlet and MDF selection below. It does not depict the Yahboom assembly. Use the current dimensioned plan and written specifications for review; small component details and proportions in this illustration are approximate.

## Dimensions and placement

All dimensions below are **millimetres**. The origin is the **inside rear-left corner**, x to the right, y toward the front, and z upward from the original inner bottom. These are design coordinates, not a drilling template. The nominal usable cavity is **380 × 380 × 125**.

| Assembly | Position and size | Height / fit basis |
| --- | --- | --- |
| Carrier | x=5, y=5; **370 × 370 × 6** | Top z=6. Five millimetres nominal side clearance. Spreads loads over the original thin bottom. |
| Course floor | x=10, y=10; **360 × 360**, front-right **260 × 260** removed; 6 thick | Two 100 mm wide legs. Running surface approximately z=41 at shooter and z=22.5 at T1. |
| Running lane | Rear centre y=60; left centre x=60; **30 clear** | 27 mm balls; 12-thick, 30-high rails. Inner rails meet at (75,75), maintaining an enclosed L-shaped route with 30 mm clear legs. |
| Console top | x=125, y=125; **240 × 240 × 6** | Top z=95, underside z=89. Front open below the panel for access/airflow. |
| Console support | Two side walls 240 long; rear wall between them | **12 thick × 83 high**. 6 carrier + 83 support + 6 top = **95**. |
| Pi and cable bay | x=140, y=140; **110 × 70** | Populated assembly and connections must stay at/below z=50. This reservation excludes the Yahboom power board. The combined stack, cooler and USB bends need a new fit check. |
| ESP and terminal bay | x=255, y=140; **97 × 105** | 87 × 75 breakout inside; wires rise at the sides and USB exits toward the front. **z≤50 is an unverified assembly allowance.** |
| Fuse bay | x=140, y=212; **110 × 85** | Actual block 87 × 52 × 42. Direct mounting on carrier gives top z≈48; reserve to z=51 with mounting allowance. |
| Converter bay | x=255, y=247; **90 × 53** | Rotate the 53 × 50 case so terminal leads use the extra width. Keep installed top/wiring below z=45. |
| Lamp driver bay | x=220, y=300; **55 × 65** | Two 25-wide boards side by side, 5 apart; 47-long bodies leave 18 total for end connections. Top/wiring ≤z=40. |
| Interface under console | x=255, y=160; **80 × 50** | Actual perfboard 70 × 50, components facing down. Keep whole assembly within **z=60–89**, at least 10 above the ESP reservation. |
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
| First button row | x=150, 195, 240, 285, 325; y=225 | Start, Fire, Lock, Ramp, Orbit. **12mm Momentary Blue LED High Head**; Ø12 mounting holes, Ø14 faces, raised Ø7.4 metal centres and blue LED rings. Shifted 5 mm forward, with Orbit 5 mm left, to clear the interface, rear connectors and reference fixing pad. |
| Second button row | x=150, 195, 240; y=260 | Target, Bump 1, Bump 2. |
| Left flipper pair | Input **(170,335)**; output lamp **(205,335)** | Both on the top panel; **35 mm centre spacing**. Label group **LEFT FLIPPER**, with **INPUT** and **OUTPUT** beneath the respective parts. |
| Right flipper pair | Input **(285,335)**; output lamp **(320,335)** | Same spacing and arrangement; label **RIGHT FLIPPER / INPUT / OUTPUT**. These are the two flipper buttons within the ten-button total. |
| Dedicated output lamps | Centres as above | P07: **Ø24.8 face, Ø16 luminous area, Ø22 hole, 15 mm thread**. Supplied rear nuts; check engagement through the 6 mm panel. Overall wired depth and cap height unpublished; allow 35 mm below panel top and 5 mm above until measured. |
| LCD reservation | Upper-left at (140, 140), **100 × 50**; PCB nominally at (150,140) | Bezel through a traced cutout; PCB and connections behind the panel. Reserve 30 mm below panel top, down to z=65, and at most 5 mm above. LCD retention on blank PCB edges needs revised MDF mounting pads/through-fixings. |
| Status / key LEDs | Upper-left (255, 144) / (255, 180) | Six pixels / nominal 100 mm per row; labels beside individual pixels. |

Eight sensor pairs means **16 physical heads**. Reserve an adjustable MDF mounting pad for each head outside the rails, with the optical axis initially **24 mm above the local running surface**. Start the pads with laminated 12 + 6 mm offcuts and shim to the measured lens centre; do not assume the lens is exactly halfway up its housing. Drill aligned beam apertures through both rails, starting around 3 mm and enlarging only if alignment requires it. Revise pad footprints and flange fixings for MDF before drilling; spread pressure with washers and leave room for alignment without distorting the housing.

For a 27 mm ball, radius r=13.5 and beam height h=24, the ideal blocked length is `2 × √(13.5² − (24 − 13.5)²) = 16.97 mm`. Touching balls therefore leave an ideal **27 − 16.97 = 10.03 mm** clear window. Finite beam width, reflections, ball speed and debounce shorten the real clear interval. At an illustrative 500 mm/s, 10 mm lasts only 20 ms even before those losses: test the actual event stream rather than assuming a debounce setting will preserve every transition.

## Materials and mounting

### MDF sheet material

**P03 and P04 now select moisture-resistant MDF, replacing both plywood purchases.** P03 is two **600 × 600 × 6 mm** GATE8 sheets at **£17 each**; P04 is one **600 × 600 × 12 mm** GATE8 sheet at **£23**. The £57 sheet total is included below, saving £20.98 against the former plywood. The bought WooDeeDoo box retains its original pine walls and birch-ply lid/base.

The main panel, rail and frame dimensions stay the same. **Small fixing details still need revision:** do not copy the former recessed carrier nuts, tiny screw-in LCD tabs or screws into the narrow rail edges directly into MDF. The [European Panel Federation guidance](https://mdf-info.eu/using-mdf/fixing/screwing) calls for suitable pilot holes and edge distances; several existing small blocks do not provide those distances. Plan larger glued mounting pads or through-bolts with load-spreading washers, then check the added space and select any extra hardware before drilling. These details are not yet dimensioned in the drawings.

MDF provides the preferred smooth finish. Sealer/primer and paint remain unselected and excluded from the subtotal; allow for coating thickness in the gate and ball lane. Moisture-resistant MDF is not waterproof. The earlier realistic illustrations retain their plywood appearance; they do not specify the selected sheet material.

**Adhesives — tack with super glue, bond with wood glue:** Dry-fit the bare MDF first. Spread F04 over most of the joint, leaving a few small, separate bare spots for F15. Keep the adhesives and activator out of each other's areas; do not mix them. Use F15 sparingly to hold alignment, following its activator instructions. Trial this assembly method on offcuts first. Retain the wood glue's specified clamping and cure time before loading the joint. F15 is only a positioning aid here: its manufacturer excludes load-bearing applications. Keep the removable console unglued and apply activator away from electronics and optical faces.

F04 remains the cheaper **EVO-STIK 250 ml at £4.19**. The alternative [Gorilla Wood Glue 236 ml, B0058NUA6S](https://www.amazon.co.uk/dp/B0058NUA6S) was **£6.00**, in stock and sold/dispatched by Amazon on 18 November 2026. It is wood glue, with [20–30 minutes of clamping and 24 hours to cure](https://uk.gorillaglue.com/products/wood-glue). Buy one wood glue, plus F15 if needed; the alternative is not added to the subtotal.

### Panel-off service view

![Earlier panel-off illustration showing the recessed LCD, service wiring and carrier. Lamp bodies, control positions, power hardware and plywood material are superseded.](./media/bench-course-service-v5.png)

The panel is lifted and rotated for illustration; it has **no permanent hinge**. Disconnect the 12 V input and host USB power, remove four console screws, then support the panel within the slack of its harness. Allow approximately **150–200 mm extra harness**; disconnect labelled terminals for complete removal. The wires must not carry the panel's weight.

The LCD, interface, six WAGOs, button backs and lamp bodies move with the panel. The Pi, ESP, fuse block, lighting converter and lamp drivers stay on the carrier. This illustration retains the earlier power arrangement; it does not establish clearance for the new Yahboom board.

![Provisional carrier, console and sensor mounting sections.](./media/bench-course-mounting.png)

![Provisional console underside: LCD, interface and connectors, with control and lamp clearances.](./media/bench-course-underside.png)

### Cut list

The upright course walls and console support walls are cut from **P04 (12 mm MDF)**. The course sits on stacked blocks cut from **P03/P04 offcuts**, trimmed and shimmed to its slope; these are made during assembly. Keep offcuts for the sensor pads too. The separate **F01 nylon standoffs** support the electronic boards. Final MDF pad sizes and fixings remain unresolved.

The main cuts below use **P03 (6 mm MDF)** and **P04 (12 mm MDF)**. Nominal sheet area is sufficient, but lay out every cut with saw kerf before cutting. Adjust the carrier to the delivered cavity. Small fixing pieces remain provisional as identified below; leave their cuts, final control holes and inlet backing until the MDF mounting details and actual parts can be checked.

| Cut material | Quantity / finished nominal size | Purpose |
| --- | --- | --- |
| 6 mm sheet 1 | 1 × **370 × 370** | Carrier. Trim to delivered cavity; do not force it between walls. |
| 6 mm sheet 2 | 1 × **360 × 360**, remove front-right **260 × 260** | L-shaped course. Cut the 240 square console from that waste, allowing for kerf. |
| MDF waste | LCD retainers: size/fixing pending | Replace the former 12 × 12 screw-in plywood tabs with an MDF-compatible retention detail; keep contact on blank PCB edges. |
| 6 mm waste | 1 × **240 × 240** | Removable console. Mark control centres, then trace the actual LCD bezel for its window; leave the PCB and lead connections behind the panel. |
| 12 mm sheet | 2 × **240 × 83**; 1 × **216 × 83** | Console side walls and rear wall, forming a U. Glue to carrier and each other; keep the front open. |
| 12 mm sheet | 1 × **317 × 30**; 1 × **305 × 30**; 1 × **275 × 30**; 1 × **263 × 30** | Rear outer, left outer and two inner rails. Inside lane faces at x=45/75 and y=45/75. Rear inner rail starts (75,75); left inner rail starts (75,87) and butts against it. There is no inner-corner gap. |
| 12 mm sheet | 2 × **30 × 30** | Trough front stop and shooter outer end stop. |
| 6 mm waste | 1 × **29 × 40** | Manual gate, 6 thick. Slide in a **7 mm** guide gap; 30 mm lift clears the ball. Round the top edge for fingers. |
| 6/12 mm waste | 4 guide cheeks about **12 × 40**, plus spacing offcuts | Glue guide cheeks outside the clear lane after proving the 7 mm channel with the finished gate; no tight friction fit. |
| 12 mm waste | Console fixing pads: size/fixing pending | Former 30 × 12 screw blocks are envelope references only; use larger glued pads or through-fixings and recheck controls/clearance. |
| 12 mm waste | 4 × **30 × 12** | Carrier retaining cleats, 12 thick, screwed to pine sidewalls above carrier edges. Place away from the low trough and cable entry. |
| 12 + 6 mm waste | 16 sensor pads; footprint/fixing pending | One per head. Former 20 × 20 pads need an MDF-compatible attachment; shim height follows the actual lens position. |
| 12/6 mm waste | Six or more **30 × 30** pads, stacked/trimmed | Support the course floor at its measured slope. All loads go into the carrier. |
| 6 mm waste | 1 × **110 × 54** | Removable trough transport cover spanning the rail tops at y≈250–360. Add 3 mm foam underneath over the balls. |
| 12 mm waste | 1 × **29 × 12** keeper, 12 thick | Glued under the rear end of the transport cover across the lane. Its underside is lower than a ball's diameter, so balls cannot escape backward. Existing front stop retains the other end. |
| 6/12 mm waste | Cable-clamp bars about **40 × 12** and backing about **50 × 30** | Internal harness restraint; inlet backing and final cable-clamp dimensions depend on the selected connector. |
| 12 mm waste | Backing about **50 × 30** at each catch/stay attachment where needed | Spread loads on the 3 mm lid; keep backing clear of the lamp caps when closed. |

### Fastening sequence

1. **Carrier:** preserve the full 6 mm MDF thickness; the former 3 mm-deep standoff-nut recess is retired. Resolve flush underside retention or a revised mounting-pad arrangement before fitting electronics. Four sidewall cleats can retain the carrier with clearance holes through the cleats and screws into the original pine walls; check engagement and spread head pressure with washers.
2. **Console:** glue the U-frame to the carrier. The former four fixing centres **(249,143), (347,207), (143,325), (347,330)** remain placement references; enlarge/reposition mounting pads and choose fasteners before making these holes in MDF. Keep the front open, drill side ventilation and keep wires clear of the Pi fan.
3. **Boards:** retain the nominal 10 mm nylon-standoff allowance, M2.5 for the Pi and sizes matched to other holes. Standoff retention, fuse-block/converter fixings and any added pads need a new clearance check; do not rely on short screws into thin MDF. Keep the reserved lamp and button wiring volumes clear. Final Pi/Yahboom mounting remains pending.
4. **Console underside:** trace the received LCD bezel, leaving its PCB behind the panel. Retain its blank edges using the revised mounting pads/through-fixings once sized; the former tiny screw-in tabs are not an MDF fixing instruction. Mount the interface components downward within z=60–89; lay reservoir capacitors on their sides if necessary. Tie the WAGOs into their marked rows, with levers accessible. Fit the buttons and dedicated lamps through the panel with their supplied nuts; check engagement and avoid crushing the MDF. Restrain lamp leads with slack beneath each pair, and route button leads downward/frontward, clear of the interface and connectors.
5. **Course:** clamp rails and adjustable pads first. Test all three balls, the 30 mm corner, gate and optical transitions before gluing. Glue the proven supports and rails with the listed wood glue; keep joints bare until bonded. Keep all fixing heads outside the ball lane and its running surface smooth.
6. **Lighting and inlet:** dry-fit the continuous strip, then solder insulated feed/injection and console-row leads at marked pads. Retain wires down the right wall and through the console-side passage. **Do not drill the retired two-lead entry hole.** Final inlet cutout, backing, strain relief and protection remain to be specified.
7. **Closure and transport:** fit the two front catches and external right-rear locking stay from the actual parts, backing thin lid material. Prove free movement and positive locking. Resolve cover retention into larger pads or through-fixings; do not reuse the former four screws into the 12 mm rail edges. Prove that the foam-padded cover, rear keeper and front stop securely retain all three balls before transport. Close the gate, disconnect external cables and latch the lid. Carry supporting the base; remove the trough cover before testing.

Workshop tools assumed available: ruler/square, saw or jigsaw, drill with depth stop/countersink, clamps, sandpaper/file, screwdrivers, wire stripper, insulated-terminal crimper, soldering iron, heat-shrink heat source, multimeter and marker. These are excluded from the shopping total.

## Lighting and electrical connections

### Direct sensor connections

**P05 remains Adafruit 2167**, using the ESP's internal pull-ups to avoid a separate sensor interface circuit. Adafruit documents the receiver's open-collector output and the option to use a microcontroller's built-in pull-up ([product specification](https://www.adafruit.com/product/2167), [wiring guide](https://learn.adafruit.com/ir-breakbeam-sensors/arduino)).

- **Emitter:** red lead to the protected **5 V logic supply**, black to ground. It needs power but no ESP GPIO.
- **Receiver:** red lead to the same protected **5 V logic supply**, black to common ground, and white/yellow signal lead directly to one ESP input. Enable that input's **3.3 V internal pull-up** (`INPUT_PULLUP`); do not pull the signal up to 5 V.

Eight stations therefore use **eight ESP inputs**, with power distributed to all sixteen heads. The sensors draw power from the supply rail, never from an output GPIO. No additional sensor resistors, level converters or custom sensor PCB are planned. The firmware supports internal pull-ups; confirm each chosen pin is configured with one enabled and check the blocked/clear states. Test transitions with the final cable lengths, LED effects and touching balls before fixing the debounce settings.

The [Helilyco four-pair set, B0HH9PRJ1N](https://www.amazon.co.uk/dp/B0HH9PRJ1N?th=1), **With Terminals**, was considered at **£7.79 per pack** on 18 November 2026 (£15.58 for eight pairs). Its listing specifies 5 V operation but does not establish output voltage/type or individual head dimensions. It is **not selected** because direct ESP compatibility is unverified; the advertised Raspberry Pi compatibility and 2.54 mm terminals do not establish that. The existing P05 price and shopping subtotal remain unchanged.

### Flipper inputs and coil-output lamps

Each side has **one blue momentary input button and one dedicated yellow output lamp** on the top panel. P07 replaces the yellow arcade buttons previously used only for their LEDs; the new lamps have no push switch. Their Ø24.8 faces are larger than the blue buttons' Ø14 faces.

| Path | Connection and purpose |
| --- | --- |
| Input | Blue button's normally-open contacts → ESP switch input → configured flipper rule. Releasing the button opens the input again. |
| Output | ESP output → that side's P16 MOSFET control input. Protected 12 V supplies the module's load circuit and its separate yellow lamp, connected according to the module's terminal labels. Each lamp's power must pass through its own MOSFET-switched output. |
| Button lighting | Blue ring → steady protected 12 V backlight bus. It does not indicate the MOSFET output, and its LED pins remain separate from the switch contacts. |

The yellow lamp therefore shows the switched electrical output under a small load, including when an output test activates it without a button press. Configure the ESP rule and output safety limits; do not connect the button directly to the lamp or substitute a GPIO status LED. Check P16's terminal labels, active level and reset-OFF behaviour before connecting it; no board-specific terminal or GPIO assignment is implied here.

P07 is listed as **12–24 V AC/DC, 20 mA**. On this bench it uses 12 V. It represents a coil firing visually but cannot test coil current, inductive kick, flyback protection or mechanical movement. Its pulse/PWM response is unspecified: a visible flash is not a measurement of output pulse duration.

### LED strip and signal interfaces

**P09 now uses one 2 m Tesfish roll.** At 60 pixels/m, the nominal cuts are **89 pixels / 1.483 m** for the perimeter and **6 pixels / 0.100 m** for each console row: **101 pixels / 1.683 m total**. That leaves **19 pixels / 0.317 m** spare, or **18 pixels / 0.300 m** if final fitting needs 102 pixels. The same 5 V supply, data buffer and fitted-pixel power budget apply. Cut the continuous perimeter first, then the two short rows; dry-fit before cutting.

Use **one continuous perimeter strip** on the inside walls at about **z=110**, with a feed gap on the **right near y=285**. The nominal path is 1.495 m with 10 mm-radius corners: 89 pixels / 1.483 m leaves about 11.5 mm for the gap. These bends are design allowances, not a manufacturer-specified minimum radius. Dry-fit before cutting; keep pixels and any factory joins off bends, and never crease the strip.

Retain feed/data wires down the inner right wall to the console-side passage near **z=60**, clear of button tails and the converter. Feed power at the strip start and approximately opposite side. The end-of-strip data continues to the console's **six status pixels and six key-light pixels**, each row about 100 mm. Nominal total **101 pixels**; the power budget allows **102** after final trimming. Use the supplied adhesive on clean, smooth timber, supplemented by clips where needed.

The two level-shifting parts have different jobs:

| Part | Connection | Why it is included |
| --- | --- | --- |
| P19 **74AHCT125** | ESP 3.3 V output → 5 V LED data | Actively drives the precisely timed, one-way WS2812 signal. It is a bare IC soldered to the interface board; an appropriate assembled buffer could replace it. |
| P20 **bidirectional I²C module** | ESP ↔ LCD SDA/SCL, 3.3 V ↔ 5 V | Allows the LCD bus to work in both directions. It is not the selected substitute for the LED buffer. Neither part supplies LED load power. |

A direct 3.3 V LED signal can work in some conditions, but the bench retains the buffer for dependable 5 V signalling. See [Adafruit's AHCT125 guidance](https://www.adafruit.com/product/1787). I²C-style pull-up circuits have different drive characteristics; [Adafruit's explanation](https://www.adafruit.com/product/757) describes the slower rising signals of that circuit type. The Amazon P20 listing does not publish a timing specification that establishes it as an equivalent WS2812 driver.

The component schedule uses **one chained LED data stream**, one AHCT125 channel and one 330 Ω resistor; it does not assign a GPIO. Use the IC datasheet for pinout/enables, define unused inputs and leave unused outputs disconnected. Verify the LCD's actual I²C device/address and driver.

### Single power inlet

**Agreed arrangement:** external enclosed 12 V supply → right-side XT60 inlet → main fuse → separately protected Pi-converter, lighting/logic-converter and 12 V indicator branches. Mains stays outside the box. P24 Yahboom powers the Pi through its supplied USB-C bridge; P15 powers the lighting/display. Do not parallel their 5 V outputs or join the lighting rail to USB VBUS.

P24 is selected. The remaining inlet/supply entries below are **comparison candidates, excluded from the shopping subtotal**. Prices were checked on 18 November 2026; listing claims are not independent load tests.

| Amazon.co.uk candidate | Item price | Decision / remaining evidence |
| --- | ---: | --- |
| [Weishuo 12 V / 20 A / 240 W car-socket adapter, B0HB4BXY3T](https://www.amazon.co.uk/dp/B0HB4BXY3T) | £26.16 | Advertised capacity is sufficient. Sustained output, cable rating and protection remain unverified. Replacing its low-voltage socket with XT60 would require proper termination; no mains modification. |
| [RUNCCI-YUN XT60E-M panel / female cable set, B0D46FPJ6D](https://www.amazon.co.uk/dp/B0D46FPJ6D), 5 pairs | £6.99 | Preferred contact arrangement: recessed female contacts on the live supply lead. Flange, cutout, screws, wooden-wall attachment and strain relief still need checking. |

The previously suggested [ECSiNG kit B0DBV3KZRX](https://www.amazon.co.uk/dp/B0DBV3KZRX) puts male contacts on the live supply lead, so the opposite arrangement is preferred. The [generic USB-C buck B0CRVW7N2J](https://www.amazon.co.uk/dp/B0CRVW7N2J) does not document Pi 5 power negotiation; the selected Yahboom does ([manufacturer](https://category.yahboom.net/collections/accessory/products/power-board-pi5), [technical manual](https://wiki.geekworm.com/YB-MPP01)). A 5 A label alone is insufficient evidence of negotiation. [Raspberry Pi's power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply) explains the resulting USB peripheral limits.

Planning allowances are **25.5 W Pi/USB peripherals**, **30.6 W for 102 pixels at 60 mA each**, **5 W sensors/LCD/interface**, and a provisional **10 W for 12 V lamps/rings**. At 90% converter efficiency, `(25.5 + 30.6 + 5) / 0.90 + 10 = 77.9 W`, or **6.5 A at 12 V**; at 80%, **7.2 A**. An enclosed **12 V / 10 A** supply is a reasonable target; 20 A is not essential. No alternative 10 A Amazon product is selected. This budget excludes real coils.

**Final fuse values, wire sizes and holder positions are pending.** The former 5 A input schedule is retired. P17 has four positions; P18 includes additional inline holders, but their locations and total requirement must be allocated for the combined supply. Verify P17 has isolated circuits before mixing 12 V and 5 V branches.

| Branch / connection | Intended wiring |
| --- | --- |
| Pi | Protected 12 V → P24 → Pi USB-C. Combined board/cooler/bridge clearance must be resolved. |
| Lighting | Protected 12 V → P15 → separately fused 5 V strip/console feeds. **6.12 A / 30.6 W** is a conservative planning maximum, not measured demand. |
| Logic | Separately protected P15 5 V → LCD, AHCT125, I²C high side and optical heads. Signals/pull-ups and I²C low side use ESP 3.3 V. |
| Indicators | Protected 12 V → two independent P16 MOSFET load circuits → left/right P07 yellow lamps. Separate parallel 12 V bus powers the steady blue button rings. Verify terminal labels, input polarity and reset-OFF behaviour. |
| Returns/distribution | Common low-voltage ground, with main LED return directly to the converter. No strip current through ESP, sensor wiring or USB. Six WAGOs are reserved; each joins all five ports into one node. Use one conductor per port and retained insulated splices for branching. Recheck node allocation for the new Pi branch. |
| I/O | Ten buttons + eight optical receivers = **18 inputs**, plus two lamp outputs, LCD I²C and LED data. Confirm available pins and boot/flash restrictions before assigning GPIOs. |

### Normal Mac use and portable Pi demos

The **Mac is the normal host**; the **Pi is for portable demos**. Connect the Mac data cable directly to the ESP serial/programming USB-C port. For demos, open the box, unplug it and connect P23 from Pi USB-A to **the same ESP port**. No USB switch, hub, selector or extra panel USB socket is included.

Disable outputs and stop the current bridge/flashing process before swapping, then start the new host's bridge. USB supplies the ESP as well as data; expect a disconnect and possible restart. Do not connect both hosts through different ESP sockets or add a parallel 5 V feed to its USB-powered rail. Keep configuration/media on both hosts consistent; cable swapping does not synchronise them. The existing Mac cable is assumed available.

## Amazon.co.uk shopping list

**Working purchase schedule, not a complete build order.** Prices/variants and photographs were checked on **18 November 2026**. Dimensions marked unpublished are still unknown; reserved envelopes are design allowances. Thumbnails enlarge and may show whole packs, not fitted quantities. Tables scroll horizontally; the dashed edge indicates more columns.

Totals use whole packs and one-time new offers, including items marked “if needed”; subtract existing stock when applicable. P10 uses the lowest displayed new buying option. Delivery is excluded: P19 showed **£6.32**, P24 **£14.99** additional delivery. No coupons, subscriptions or used offers are assumed. Prices and availability can change.

| Purchase group | Item subtotal |
| --- | ---: |
| Box, course and controls (P01–P09, MDF sheets) | £245.56 |
| Controllers, interfaces and power (P10–P24) | £288.87 |
| Fixings, wire and consumables (F01–F15) | £115.23 |
| **Selected priced items — incomplete build subtotal** | **£649.66** |

**Excluded:** replacement external supply/inlet, any extra protection/wiring, revised MDF mounting hardware and finish, tools and delivery. MDF sheets are now included. Retired P25–P27 (5 A supply, its mains lead and barrel entry) have been removed from the purchase table and subtotal; part IDs are preserved. This is not a £649.66 complete kit.

### Box, ball course and controls

| ID / quantity | Exact product and variant | Price / buy unit | Line total | Published dimensions / specification | Installation and evidence |
| --- | --- | ---: | ---: | --- | --- |
| P01 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p01.jpg" alt="P01: WooDeeDoo B0973KZMGK" width="84" height="84" loading="lazy"> [WooDeeDoo B0973KZMGK](https://www.amazon.co.uk/dp/B0973KZMGK?th=1), **40 × 40 × 13.5 cm** | £33.99 | **£33.99** | Outside **400 × 400 × 135 mm**; inside **approximately 380 × 380 × 125 mm**; 3 mm birch-ply lid/base | Listing text. Original hinges included. The inner size is approximate; check the delivered box and hinge intrusion. |
| P02 · 1 pack of 3 | <img class="part-thumbnail" src="./media/test-bench-parts/p02.jpg" alt="P02: sourcing map chrome steel balls, 27 mm" width="84" height="84" loading="lazy"> [sourcing map chrome steel balls, 27 mm](https://www.amazon.co.uk/dp/B0CCJXJJWR) | £11.19 | **£11.19** | **Ø27 mm**, three balls | Listing size. 30 mm clear lane gives 3 mm total lateral clearance. Not a claim of regulation pinball weight or diameter. |
| P03 · 2 sheets | <img class="part-thumbnail" src="./media/test-bench-parts/mdf-option.jpg" alt="P03: GATE8 6 mm moisture-resistant MDF, 600 × 600 mm" width="84" height="84" loading="lazy"> [GATE8 moisture-resistant MDF, B0B21V5VRM](https://www.amazon.co.uk/dp/B0B21V5VRM), **600 × 600 mm, 6 mm thick** | £17.00 | **£34.00** | **600 × 600 × 6 mm** each; one sheet per buy unit | Cut into the carrier, course floor, console top, gate and covers. Keep offcuts for support layers and shims. Listing size/price checked 18 November 2026; in stock. Full-thickness carrier and revised underside fixings required; see mounting notes. |
| P04 · 1 sheet | <img class="part-thumbnail" src="./media/test-bench-parts/mdf-option.jpg" alt="P04: GATE8 12 mm moisture-resistant MDF, 600 × 600 mm" width="84" height="84" loading="lazy"> [GATE8 moisture-resistant MDF, B0B25KRGVS](https://www.amazon.co.uk/dp/B0B25KRGVS), **600 × 600 mm, 12 mm thick** | £23.00 | **£23.00** | **600 × 600 × 12 mm**; one sheet | Cut into the upright ball-guide walls (30 mm high), console support walls (83 mm high), end stops, support blocks and backing. Listing size/price checked 18 November 2026; in stock. Glue fixed joints; small screw-block and cover fixings need revision. Same generic seller photograph as P03; use the linked thickness. |
| P05 · 8 pairs | <img class="part-thumbnail" src="./media/test-bench-parts/p05.jpg" alt="P05: Adafruit ADA2167 3 mm break-beam sensors" width="84" height="84" loading="lazy"> [Adafruit ADA2167 3 mm break-beam sensors](https://www.amazon.co.uk/dp/B01BU6YBWU) | £11.16 | **£89.28** | Each head **20 × 10 × 8 mm**; cable **230 mm**; 3.3–5.5 V | Amazon product identity; dimensions and open-collector output from [Adafruit](https://www.adafruit.com/product/2167). Both heads powered; only receiver signal goes to ESP, using its internal 3.3 V pull-up. No external sensor circuit planned. Sixteen heads total; first prove one pair with touching balls. |
| P06 · 3 packs of 4; use 10 | <img class="part-thumbnail" src="./media/test-bench-parts/p06.jpg" alt="P06: Gebildet 12mm Momentary Blue LED High Head buttons" width="84" height="84" loading="lazy"> [**Gebildet 12mm Momentary Blue LED High Head**](https://www.amazon.co.uk/dp/B088CNW12P?th=1), B088CNW12P | £7.89 | **£23.67** | Face **Ø14 mm**, hole **Ø12 mm**, actuator **Ø7.4 mm**; maximum panel **8 mm**; separate **12–24 V DC blue LED** and normally-open momentary contact. | Supplied nuts; solder terminals. Overall depth/cap height unpublished: verify the 35 mm rear / 10 mm top allowances. Gallery/text disagree on thread pitch (0.75/0.8 mm); use supplied nuts in plain holes. [Terminal drawing](./media/test-bench-parts/p06-dimensions.jpg). |
| P07 · 1 pack of 2; use both | <img class="part-thumbnail" src="./media/test-bench-parts/p07-indicator.jpg" alt="P07: PATIKIL dedicated yellow indicator lamps, 22 mm" width="84" height="84" loading="lazy"> [PATIKIL indicator lights, B0FBGLDVNQ](https://www.amazon.co.uk/dp/B0FBGLDVNQ), **Yellow, 22mm** | £8.49 | **£8.49** | **Ø24.8 face / Ø16 luminous area / Ø22 hole / 15 mm thread**; 12–24 V AC/DC, 20 mA; leads about 205 mm | Dedicated lamps with supplied nuts, no switches. One 12 V load per P16 MOSFET. [Listing dimension image](./media/test-bench-parts/p07-indicator-dimensions.jpg). Complete depth, cap height and grip unpublished; reserve 35 mm wired rear / 5 mm above panel until measured. Check nut engagement through 6 mm MDF. |
| P08 · 1 display | <img class="part-thumbnail" src="./media/test-bench-parts/p08-single.jpg" alt="P08: Freenove I²C LCD1602, new type, single display" width="84" height="84" loading="lazy"> [Freenove I²C LCD1602, B0B76YGDV4](https://www.amazon.co.uk/dp/B0B76YGDV4?th=1), **I2C 1602** (single pack) | £7.95 | **£7.95** | PCB **80 × 36 mm**, mounting holes **Ø3 mm**; 16 characters × 2 lines; integrated I²C conversion circuit | [Gallery dimensions](./media/test-bench-parts/p08-dimensions.jpg). Bezel, hole centres and complete thickness unpublished. Keep the 100 × 50 reservation, 30 below / 5 above panel; trace the received bezel. £3 below the former two-pack. In stock, sold by Freenove-EU / dispatched by Amazon; checked 18 November 2026. |
| P09 · 1 roll of 2 m; reuse if owned | <img class="part-thumbnail" src="./media/test-bench-parts/p09-tesfish-2m.jpg" alt="P09: Tesfish WS2812B, 2 m / 120 LEDs, black PCB" width="84" height="84" loading="lazy"> [Tesfish WS2812B, B0D5B5CGVX](https://www.amazon.co.uk/dp/B0D5B5CGVX), **2m 120leds Ws2812b** | £13.99 | **£13.99** | **2000 × 10 mm**, thickness unpublished; **5 V**, 60 individually addressable pixels/m; nominal **16.67 mm cut pitch** (gallery rounds to 17 mm). Title says IP30, description IP20: indoor, non-waterproof use. | Self-adhesive; three-pin JST-SM and separate power leads at both ends. Cut 89 perimeter + 6 status + 6 key pixels; 19 spare nominally. [Dimension / mounting image](./media/test-bench-parts/p09-tesfish-dimensions.jpg). Keep the perimeter continuous; dry-fit bends and any factory joins. £21 below the former 5 m roll; in stock, sold by Newjack / dispatched by Amazon, checked 18 November 2026. |

### Controllers, interfaces and power

| ID / quantity | Exact product and variant | Price / buy unit | Line total | Published dimensions / specification | Installation and evidence |
| --- | --- | ---: | ---: | --- | --- |
| P10 · 1 if needed | <img class="part-thumbnail" src="./media/test-bench-parts/p10.jpg" alt="P10: Raspberry Pi 5, SC1111, 4 GB" width="84" height="84" loading="lazy"> [Raspberry Pi 5, SC1111, 4 GB](https://www.amazon.co.uk/dp/B0CK3L9WD3) | £124.70 (lowest new offer) | **£124.70** | PCB **85 × 56 mm**; holes **Ø2.7 mm**, **58 × 49 mm** centres | Amazon identity; [official mechanical drawing](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf). Reserve 110 × 70 mm including USB connection space. Existing Pi 5 can be reused. |
| P11 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p11.jpg" alt="P11: Official Raspberry Pi Active Cooler, SC1148" width="84" height="84" loading="lazy"> [Official Raspberry Pi Active Cooler, SC1148](https://www.amazon.co.uk/dp/B0CLXZBR5P) | £8.29 | **£8.29** | **63.5 × 42.5 × 13.7 mm** | [Official drawing](https://pip-assets.raspberrypi.com/categories/993-raspberry-pi-active-cooler/documents/RP-008187-DS-1-raspberry-pi-active-cooler-mechanical-drawing.pdf?disposition=inline) and Amazon model. Supplied push pins, thermal pads and fan lead; connect to Pi fan socket. No additional Pi enclosure. |
| P12 · 1 if needed | <img class="part-thumbnail" src="./media/test-bench-parts/p12.jpg" alt="P12: SanDisk High Endurance 32 GB microSDHC" width="84" height="84" loading="lazy"> [SanDisk High Endurance 32 GB microSDHC](https://www.amazon.co.uk/dp/B07P14QHB7) | £22.55 | **£22.55** | **32 GB**, microSD form factor; standard card envelope **15 × 11 × 1 mm** | Capacity verified in listing; card envelope is the microSD format, not a measured sample. Existing configured card can be reused. Keep access to the Pi card edge. |
| P13 · 1 pack of 2; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p13.jpg" alt="P13: Freenove ESP32-S3, 16 MB Flash, 2 Pack" width="84" height="84" loading="lazy"> [Freenove ESP32-S3, 16 MB Flash, 2 Pack](https://www.amazon.co.uk/dp/B0FRRJCDHF), **FNK0099K** | £21.95 | **£21.95** | 16 MB flash / 8 MB PSRAM, USB-C; complete board dimensions not published | Concrete new-purchase option. Do not assume it is the same revision as an existing FNK0085. Check firmware target and board pinout before deployment; this design does not assign GPIO numbers. |
| P14 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p14.jpg" alt="P14: Freenove FNK0091 breakout" width="84" height="84" loading="lazy"> [Freenove FNK0091 breakout](https://www.amazon.co.uk/dp/B0CD2512JV) | £11.95 | **£11.95** | PCB **87 × 75 mm**; 2.54 mm headers | Gallery PCB size (not packaging). Manufacturer lists Freenove ESP32/S3 compatibility. Populated height unpublished; 97 × 105 bay, z≤50 allowance. No separate barrel power. |
| P15 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p15.jpg" alt="P15: VOLRANTISE converter" width="84" height="84" loading="lazy"> [VOLRANTISE converter](https://www.amazon.co.uk/dp/B09WZ9DC9W), **12/24 V to 5 V 10 A** | £11.99 | **£11.99** | **53 × 50 × 20 mm**; 10–35 V input; 5 V / 10 A advertised output | Amazon dimension drawing. Reserve 90 × 53 mm with connections facing sideways. Supplies lighting/display, not Pi USB-C. Verify output voltage and temperature under the actual load. |
| P16 · 1 pack of 4; use 2 | <img class="part-thumbnail" src="./media/test-bench-parts/p16.jpg" alt="P16: JZK F5305S optocoupled MOSFET modules" width="84" height="84" loading="lazy"> [JZK F5305S optocoupled MOSFET modules](https://www.amazon.co.uk/dp/B09SWRF88D) | £7.09 | **£7.09** | Each **47 × 25 × 15 mm**; input 3–24 V, about 5 mA; load supply 5–36 V | Listing text. One board per flipper lamp; two side by side in a 55 × 65 mm bay including bends. Read the board terminal labels; do not infer a generic low-side wiring topology. |
| P17 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p17.jpg" alt="P17: Gebildet four-way covered blade-fuse box" width="84" height="84" loading="lazy"> [Gebildet four-way covered blade-fuse box](https://www.amazon.co.uk/dp/B076P4LBSG), **4 way** | £8.44 | **£8.44** | **87 × 52 × 42 mm**; **6.3 mm tabs** | Gallery dimensions; four isolated circuits required, verify by continuity. Cover/eight spades/mixed fuses included. Revised circuit allocation and extra holder positions pending. |
| P18 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/p18.jpg" alt="P18: iLulala six holders / 66 standard blade fuses" width="84" height="84" loading="lazy"> [iLulala six holders / 66 standard blade fuses](https://www.amazon.co.uk/dp/B0DKX9R1FK) | £7.99 | **£7.99** | Six each of **2, 3, 5, 7.5, 10, 15, 20, 25, 30, 35, 40 A** | Six inline holders plus 66 fuses; standard ATO/ATC format. Final fuse schedule and additional holder positions pending for the single inlet. Confirm seating in P17. |
| P19 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p19.jpg" alt="P19: Adafruit ADA1787 / 74AHCT125" width="84" height="84" loading="lazy"> [Adafruit ADA1787 / 74AHCT125](https://www.amazon.co.uk/dp/B00XW2L39K) | £3.46 (+ £6.32 delivery shown) | **£3.46** | **14-pin through-hole DIP**, 2.54 mm pitch | **LED data:** raises ESP 3.3 V data to 5 V; actively driven, one-way buffer. Bare IC soldered to P21, not a ready-made module. [TI datasheet](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf). |
| P20 · 1 pack of 15; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p20.jpg" alt="P20: RUNCCI-YUN four-channel I²C level converters" width="84" height="84" loading="lazy"> [RUNCCI-YUN four-channel I²C level converters](https://www.amazon.co.uk/dp/B082F6BSB5) | £6.99 | **£6.99** | PCB **13 × 15 mm**, 2.54 mm header pitch | **LCD data:** bidirectional SDA/SCL conversion between 3.3 V and 5 V. Solder to P21; not the selected WS2812 buffer substitute. |
| P21 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/p21.jpg" alt="P21: OFNMY 1628-piece electronics kit" width="84" height="84" loading="lazy"> [OFNMY 1628-piece electronics kit](https://www.amazon.co.uk/dp/B0FFTDD9JQ), **1628 PCS** | £22.99 | **£22.99** | PCBs **20 × 80, 30 × 70, 40 × 60, 50 × 70 mm** | Gallery contents include 330 Ω, 4.7 kΩ and 10 kΩ resistors (20 each), 100 nF ceramics, and 470 µF / 16 V electrolytics. Use the 50 × 70 mm board for interfaces; the other boards are spares; detailed component use below. Breadboards are for the preliminary test only. |
| P22 · 1 pack of 25 | <img class="part-thumbnail" src="./media/test-bench-parts/p22.jpg" alt="P22: WAGO 221-415, five-lever connectors" width="84" height="84" loading="lazy"> [WAGO 221-415, five-lever connectors](https://www.amazon.co.uk/dp/B0107SYYGU), **5-Lever** | £11.00 | **£11.00** | **29.9 × 18.6 × 8.3 mm**; 0.14–4 mm² flexible copper | [Manufacturer dimensions](https://www.wago.com/global/installation-terminal-blocks-and-connectors/splicing-connector-with-levers/p/221-415). Allow up to six connectors for power distribution, retained by cable ties with levers accessible. Each connector joins all five ports; it is not five isolated poles. |
| P23 · 1 pack of 2; use 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p23.jpg" alt="P23: Anker USB-A to USB-C cable" width="84" height="84" loading="lazy"> [Anker USB-A to USB-C cable](https://www.amazon.co.uk/dp/B0D5XY3C2T), **0.3 m + 0.3 m, Black** | £5.49 | **£5.49** | **300 mm including connectors**, USB 2 data up to 480 Mbit/s | Listing explicitly confirms data support. Pi USB-A to the ESP programming/serial USB-C port. Connector moulding dimensions not published; use the reserved connection spaces. |
| P24 · 1 | <img class="part-thumbnail" src="./media/test-bench-parts/p24.jpg" alt="P24: Yahboom Pi 5 PD power expansion board" width="84" height="84" loading="lazy"> [Yahboom Pi 5 PD power board, B0D3L6Y92G](https://www.amazon.co.uk/dp/B0D3L6Y92G) | £13.99 | **£13.99** | PCB **65 × 56 mm**; **7–24 V input → 5 V / 5 A** with Pi 5 USB-PD negotiation | Selected Pi converter; supplied stacking hardware/dual-USB-C bridge. [Technical specification](https://wiki.geekworm.com/YB-MPP01). Stack height, cooler clearance and terminal access unallocated. Offer adds £14.99 delivery; £28.98 delivered, estimated 14 December 2026 at check. No extra buck in series. |

### Fixings, wire and consumables

| ID / quantity | Exact Amazon.co.uk product | Price / buy unit | Line total | Size / contents | Use |
| --- | --- | ---: | ---: | --- | --- |
| F01 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f01.jpg" alt="F01: WiMas 940-piece nylon standoffs" width="84" height="84" loading="lazy"> [WiMas 940-piece nylon standoffs](https://www.amazon.co.uk/dp/B0CJFG1XDR), Black | £14.99 | **£14.99** | M2/M2.5/M3/M4; gallery includes **10 mm body + 6 mm male stud**, M2.5×6 and M3×6 screws/nuts | Pi uses M2.5; match other board holes. Carrier retention must be revised for full-thickness MDF; the former recessed-nut arrangement is retired. |
| F02 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f02.jpg" alt="F02: AMLOOPH 535-piece wood screws" width="84" height="84" loading="lazy"> [AMLOOPH 535-piece wood screws](https://www.amazon.co.uk/dp/B0CPF54WYQ) | £6.99 | **£6.99** | M2×6/10; M2.5×12/16/20; M3×8/10/12/16/20 mm | Pilot-drilled wooden joints, clips, console screws and backing. Choose length by the actual material stack; do not blindly use fitting-kit screws. |
| F03 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f03.jpg" alt="F03: Jeboler 500 nylon washers" width="84" height="84" loading="lazy"> [Jeboler 500 nylon washers](https://www.amazon.co.uk/dp/B0D4952M2T) | £2.68 | **£2.68** | M2, M2.5, M3, M4, M5, M6, M8, M10 | Protect PCB/plastic flanges and spread small-screw loads. Exact washer thickness is not listed; allow and measure it in the fastening stack. |
| F04 · 1 bottle if needed | <img class="part-thumbnail" src="./media/test-bench-parts/f04-evo-stik.jpg" alt="F04: EVO-STIK Exterior Wood Glue, 250 ml" width="84" height="84" loading="lazy"> [EVO-STIK Exterior Wood Glue, B0002JT0J6](https://www.amazon.co.uk/dp/B0002JT0J6), **250ML** | £4.19 | **£4.19** | One **250 ml** bottle; D3 PVAc wood adhesive, suitable for MDF | Frame, rails, cleats, pads and lid backing; clamp and cure per bottle instructions. Do not glue the removable console. Replaces the £14.25 Gorilla two-pack, saving £10.06 with less glue (250 ml versus 472 ml). Price/variant checked 18 November 2026; [manufacturer guidance](https://diy.evo-stik.co.uk/en-UK/our-ranges/wood-adhesives/wood-glue-exterior). |
| F05 · 1 kit | <img class="part-thumbnail" src="./media/test-bench-parts/f05.jpg" alt="F05: TUOFENG 18 AWG silicone wire" width="84" height="84" loading="lazy"> [TUOFENG 18 AWG silicone wire](https://www.amazon.co.uk/dp/B07G744V5Z), 18awg silicone wire set | £15.99 | **£15.99** | Six colours × **13.2 ft / about 4 m**; **2.3 mm OD**; 150×0.08 mm tinned-copper strands | 5 V lighting distribution and return. Recheck the new combined 12 V main-feed gauge against length, current, connector and fuse ratings; this row does not approve 18 AWG for that feed. |
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

| Function | Fitted parts |
| --- | --- |
| WS2812 data | P19 AHCT125, one **330 Ω** series resistor close to the first pixel, one **10 kΩ** data-input pull-down, one **100 nF** ceramic directly across IC supply pins. Define unused inputs and enables; leave unused outputs disconnected. |
| Optical inputs | **No external resistors fitted:** use the eight ESP inputs' internal **3.3 V pull-ups** for the selected Adafruit open-collector receivers. Both heads use protected 5 V power; only receiver signals connect to GPIO. Verify pull-up configuration and transitions with the final harness. |
| Manual buttons | Ten **4.7 kΩ** pull-ups to **3.3 V**; each button's two switch pins connect its input to common ground. Its separate LED +/− pins connect only to the protected 12 V ring-light bus/return, never to an ESP input. Confirm terminal identity against the product diagram and continuity-test before power. |
| Lamp driver inputs | Two **10 kΩ** pull-downs at the input connectors, subject to confirming active-high behaviour of P16. Verify the lamps remain OFF through reset, USB connection and loss of control. |
| LED supply reservoir | Two **470 µF / 16 V** capacitors in parallel, **940 µF nominal**, across the 5 V lighting input with correct polarity. |
| Soldered boards | **50 × 70 mm** interface board under the console, including low-current common-return connections. Header links from the kit are signal-only, strain-relieved, and must not carry the main strip current. |

The blue rings are fixed-colour 12 V backlights here and add no GPIOs. Solder four insulated leads per button: two for the contact, two for the LED. The metal body is not a return terminal. Keep the 12 V rings separate from the 3.3 V switch inputs.

The schedule uses three of the supplied 10 kΩ resistors, ten 4.7 kΩ resistors and one 330 Ω resistor; the former eight external sensor pull-ups are omitted. Sensor connections need no custom circuit, but the existing LED/LCD interfaces still require assembly. Route the LED power bus in 18 AWG wire and WAGO connectors, not through thin perfboard traces or the ESP breakout.

## Readable engineering checks and unresolved evidence

The geometry check finds no overlapping **modelled** module/keepout envelopes, including all ten buttons' **24 × 24 × 35 mm** wiring reservations. It excludes individual wire routing, final fixing details, deflection, lid motion and the new Pi power arrangement. No physical build, rolling, closure, transport or load test has been performed.

| Item | Current evidence / required next check |
| --- | --- |
| Box and carrier | 370 carrier in approximate 380 cavity leaves **5 mm each side**. Measure the delivered box, hinge intrusion and wall/base thickness before cutting. |
| Console and lamps | Stack **6 + 83 + 6 = 95 mm**. P07's conditional 5 mm cap ends at **z=100**, leaving 25 mm to nominal lid; 35 mm wired rear allowance ends at **z=60**. Published 15 mm thread does not establish complete depth or panel grip. Measure the received lamp and nut engagement. The taller button allowance ends at z=105, leaving **20 mm** overall nominal lid clearance. |
| Small buttons | Published Ø14 face / Ø12 hole / 8 mm maximum panel suit 6 mm sheet. Assumed 35 mm rear ends at **z=60**, 9 above fuse envelope; 10 mm cap ends at z=105. Actual overall depth and wired clearance remain unknown. |
| LCD and interface | LCD reservation z=65–100, interface z=60–89, controller envelopes end z=50. Verify LCD bezel/thickness/tab contact and populated ESP height; these gaps are conditional. |
| Pi power and inlet | P24 board is 65 × 56, but stack/cooler/bridge/terminal clearances are not allocated. Select/verify supply and XT60 flange/cutout, attachment and strain relief. Revise holder positions, fuse ratings, wire sizes and distribution. |
| MDF | P03/P04 and subtotal now use 6/12 mm MDF. Main dimensions are retained; carrier standoff retention, LCD tabs, console/sensor pads and transport-cover fixings need revision and a new clearance check. Old small-block screw details are not approved for MDF. Extra hardware/finish not selected. |
| Ball sensing | **30 − 27 = 3 mm** total lane clearance. Ideal **10.03 mm** touching-ball clear window at h=24 is geometry only. Test one pair first, then all eight stations at realistic speed/debounce, including corner and gate. |
| Lighting | **89 + 6 + 6 = 101** nominal pixels; budget **102**, within P09’s 120-pixel / 2 m roll. Width is 10 mm; thickness, minimum bend radius and factory-join spacing are unpublished. Verify these, adhesive and clip engagement before cutting. |
| Closure fittings | Catch pattern/projection unpublished; stay text says 190 mm open versus 195 mm drawing. Set holes/pivots from actual parts and prove locking/closure with lid backing clear of lamps. |
| Electrical validation | Verify driver reset-OFF/input polarity, sensor logic, LCD operation, Pi power detection, full-white voltage drop, current and cable/converter/Pi temperatures with intended ventilation. Fuse sizing must protect the actual conductors/connectors. |

The ESP must retain arming, watchdog, pulse-limit and fault protections. This documentation makes no application, firmware or GPIO-map changes.

The [earlier enclosure study](test-bench-enclosure-study.md) is historical context; its parts/pin assignments do not carry forward automatically.
