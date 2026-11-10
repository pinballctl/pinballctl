# Test Bench

## Purpose and status

Design a compact, self-contained desktop test bench that makes Pinball CTL's configured hardware tangible: press buttons, exercise switches, exercise MOSFET-switched coil-output indicators, operate lighting and display information. It should provide richer application testing than the existing LED-strip-and-buttons setup while remaining accessible for learning and maintenance.

**Status: component research and preliminary sizing, 10 November 2026.** No enclosure, circuit or manufacturing package has been validated or released. This page is the running record of discussions, proposals and decisions; proposed dimensions and arrangements are not approved specifications.

Background: [Development Platform](1-development-platform.md). The [hardware inventory](../1-user-guide/7.2-hardware-inventory.md) is the baseline for component names, GPIO assignments and configuration. It describes logical assignments, not verified physical parts.

## Agreed brief

- **Function before form:** choose actual components and validate fit, wiring access, thermal behaviour, serviceability and control ergonomics before refining appearance. Rendered shapes are not evidence of feasibility.
- Develop the **C-derived enclosure direction without a raised rear section**. The project owner rejected the raised tops in revision 2 and requested symmetrical left/right sides with matching flipper positions. Study a single shallow sloping top; final slope and dimensions remain open. Locate USB and 12V connections on a rear or side vertical face, never on the top surface.
- Study four front-face controls: **Start, Launch, Select and Add Player**. Select is intended for menu choices and related interactions; the fourth control is a proposed dedicated Add Player/expansion input. These new inputs and application behaviour require planning rather than being assumed to exist.
- Build a small box containing physical representations of all currently configured hardware, including buttons, LEDs, LCD and accelerometer. Represent the two coil outputs with visible MOSFET-switched lights; do not install physical solenoids or moving coil mechanisms.
- Explore design options and agree a product mockup before preparing manufacturing files.
- Design a 3D-printable enclosure with mounts for the PCB, components and wiring, suitable for ordering from an online printing service.
- Design a custom PCB with a plug-in ESP controller, conversion from a **12V DC external adapter**, LED outputs, and connections for all buttons and switches. No mains-voltage circuitry is planned inside this box.
- Research and recommend all required components, including the adapter, controller, converters, MOSFET output stages, indicator loads, connectors and enclosure hardware. Reuse of existing parts remains an option where their identity and suitability can be verified.
- Reserve an accessible breadboard bay for plugging in and testing additional components. The latest study targets a **full-size breadboard** rather than the earlier compact/half-size options; exact model and supporting connections remain open.
- Prioritise **one continuous main LED strip with as many pixels as practically fit**, across the width or around a compatible perimeter route. Fewer than 120 main-strip pixels is explicitly acceptable. Retain a separate 12-pixel strip and six status pixels. The enclosure may grow to accommodate useful lighting length and breadboard space; compactness is secondary to function.
- Eventually provide editable design sources and service-compatible printing, PCB fabrication and assembly files.
- Keep this page updated as discussions resolve requirements, component choices and design decisions.

The project owner confirmed external 12V adapter power, requested component selection and preferred the mini-cabinet direction on 10 November 2026. Budget, dimensions, detailed layout and component models remain open.

## Hardware coverage

### Playfield-style control grouping

Group test controls by their physical role on the table instead of the numbered 3×3 grid in the early renders. Keep a clear playfield control area alongside the separate full-size breadboard workspace.

| Zone | Controls and placement intent |
|---|---|
| Upper playfield | Lock and left ramp toward the left; skill shot toward the centre; playfield entry and right orbit toward the right, following the current layout. |
| Central playfield | Three pop-bumper test controls in a recognisable cluster, with nearby target controls. Jackpot Target has been repurposed as Pop Bumper 1; do not duplicate it. |
| Lower playfield | Drain centrally near the flipper area; shooter lane on the right near the launch end. |
| Sides | Mirrored left/right flipper buttons with corresponding MOSFET-switched indicator lights. |
| Front face | Start, Launch, Select and Add Player; retain easy access while operating the playfield controls. |

The local configuration was reconciled on 10 November 2026 at the project owner's request: **Pop Bumper 1 = GPIO 17** (formerly Jackpot Target), **Pop Bumper 2 = GPIO 47**, and **Pop Bumper 3 = GPIO 48**. All three are Button / Default inputs with LOW idle, and their existing layout positions were preserved. GPIO 47 and 48 were unassigned and marked general-purpose in the saved discovery snapshot; this does not verify external wiring.

The mapping blob was rebuilt locally without ESP deployment. Existing scoring/jackpot rules use a previous controller ID and were preserved; reconcile those separately before relying on gameplay behaviour. No bumper output drivers or physical bumper mechanisms were added.

### Component coverage and binding status

| Group | Required coverage | Initial physical proposal |
|---|---|---|
| Player controls | Left flipper, right flipper, launch and start: 4 inputs | Side-mounted flipper buttons and front-face launch and start buttons. |
| Proposed additional controls | Select and Add Player: 2 new inputs | Four-button front-face row with Start and Launch. Reserve electrical capacity; GPIO assignments and menu/player behaviour remain to be designed; addressable lighting is now requested for every button. |
| Playfield inputs | Drain, shooter lane, playfield entry, lock, left ramp, right orbit, standup target and skill-shot target: 8 non-bumper inputs | Individually labelled controls; consider lever microswitches for some positions to exercise real switch mechanisms. |
| Pop-bumper group | Three inputs on GPIO 17, 47 and 48 | Group three test buttons together; each layout symbol is now bound. GPIO 17 replaces Jackpot Target. |
| Button lighting | Proposed: one addressable RGB pixel for each of 17 buttons | Chain 17 pixels on one data output; a translucent surround distributes each pixel’s light. Replaces the proposed discrete lamp approach; runtime mapping unchanged. |
| Addressable lighting | Status RGB: 6 pixels; On Table Lights: 12; main strip: count determined by fit | Three independent groups. Prefer one continuous main strip; the saved inventory has 120 pixels, but a reduced count is approved for this bench. |
| Coil-output indicators | Left and right flipper roles: 2 independent outputs | Two visible lights, each driven through its own MOSFET output stage. Place symmetrically near the corresponding flipper side; no physical solenoids. |
| Display | One 16×2 I²C LCD | Readable top-panel display with accessible contrast adjustment if required. |
| Motion sensing | One MMA8452-compatible accelerometer | Rigidly mounted sensor with documented orientation, allowing nudge/lift tests of the box. |
| Controller | One plug-in ESP32-S3 board | Socketed carrier connection, accessible USB and reset/boot controls, antenna clearance. Exact board to be selected before socket layout. |

The baseline is **24 mapped components**, plus the controller, power system and supporting electronics. The LCD and accelerometer each count once despite using two GPIO connections. Preserve the current mapping where electrically suitable; document any proposed reassignment before changing it.

Adding Select and Add Player to the updated baseline would give **17 button/switch inputs** and **26 mapped components**, before expansion accessories. The bumper mappings are saved locally; Select and Add Player remain proposed and unassigned. Assess spare GPIO capacity after allocating those front controls.

The saved inventory records **120 + 12 + 6 pixels**, but the project owner has explicitly accepted fewer than 120 pixels on the test bench main strip. The new target is **N + 12 + 6 pixels**, where N is the useful capacity of one continuous strip within the chosen enclosure, subject to bend, electrical and thermal limits. Determine N after selecting the strip and checking its route. Update the bench mapping and affected lighting layouts/scenes when the physical count is fixed; the existing runtime configuration and dated inventory have not been changed.

## Historical enclosure studies

### Current visual study — revision 6

![Proposed 360 × 280mm test bench with 17 single-pixel illuminated button surrounds, a full-size breadboard, top and rear views.](./media/test-bench-concepts-v6.png)

Generated with built-in image generation on 10 November 2026; [revision 6 prompt](./media/test-bench-concepts-v6.prompt.txt). This study illustrates the proposed 360 × 280mm footprint, 60mm front / 90mm rear heights, 165 × 56mm full-size breadboard and one addressable RGB pixel behind each of 17 translucent button surrounds. The main strip is shown as the initial straight 320mm / approximately 46-pixel fit study, with separate 12-pixel and six-status-pixel sections. Four front controls, opposing flippers and two MOSFET output lamps remain.

The dimension annotations are design targets, not measurements of a CAD assembly. The rendered uniform glow must be tested with a single emitter and physical diffuser. The image depicts a USB Type-B rear socket; **that connector is illustrative and not selected**. Match the panel extension to the actual ESP board. The LCD's approximately 80 × 36mm label is an illustrative display outline, not verified dimensions for the shortlisted backpack assembly; retain the larger clearance allowance below. Bumpers are shown in a row rather than the proposed triangular alternative. Pixel counts, mounting details and wiring graphics are illustrative; use the electrical architecture and component tables as the design record. The rear cable direction and lack of a raised top are intentional.

### Previous visual study — revision 5

![Test bench with playfield-style controls, three pop-bumper buttons, two output indicator lights, a full-size breadboard and continuous main lighting concept.](./media/test-bench-concepts-v5.png)

Created with built-in image generation on 10 November 2026; [generation prompt](./media/test-bench-concepts-v5.prompt.txt). This study replaces the numbered grid with eleven playfield controls, including the three bumpers, and replaces both physical solenoids with MOSFET-switched indicator lights. Full-size breadboard space, four front controls, opposite side flipper buttons and rear connections remain.

The rounded continuous lighting path is an intention, not a verified strip-routing solution. Rendered pixel counts, dimensions and breadboard geometry are not specifications. The output lamps are grouped around the drawn playfield in this illustration; their final placement must be checked against the desired left/right symmetry and reach. The bumper buttons appear in a row here; a triangular cluster remains an alternative during dimensioned layout work.

Revisions 1–4 predate the decision to replace solenoids with MOSFET-switched lights. Their coil mechanisms and guards are superseded and must not be carried into the current mechanical design. Revision 5 reflects the indicator-light and grouped-control requirements. The latest functional requirements take precedence over all rendered details.

| Option | Arrangement | Advantages | Tradeoffs |
|---|---|---|---|
| A — Sloped desktop console | Sloped control panel, side flipper buttons, LCD at the rear, lighting around the panel and two visible coil mechanisms. | Comfortable interaction and a coherent demonstration unit. Initial recommendation. | Panel area, coil clearance and lighting layout must be checked together. |
| B — Flat modular instrument box | Flat lid with replaceable control, lighting and actuator panels. | Easy to service and revise; individual panels can be reprinted. | More seams, fasteners and internal cable management. |
| C — Mini pinball cabinet | Small cabinet silhouette with playfield-style controls and rear display area. | Visually communicates the purpose and offers room for labelled playfield zones. | Larger print volume and more complex assembly; not a working ball playfield unless separately agreed. |

A footprint around **250 × 180 mm** was suggested as a starting study, not accepted as a size limit. Height and final footprint depend on component dimensions, main-strip routing, cable bends, heat and print-service constraints. The Mac or Pi host is proposed to remain external over USB; internal host mounting is not yet agreed.

### Visual concepts — revision 1

![Three test bench concepts with accessible breadboard bays: sloped console, flat modular box and mini cabinet.](./media/test-bench-concepts-v1.png)

Generated on 10 November 2026 using the built-in image-generation tool. The [generation prompt](./media/test-bench-concepts-v1.prompt.txt) is retained for future revisions.

These illustrations compare appearance and component zones, not verified CAD or circuit designs. Each concept shows a breadboard bay, LCD, playfield controls, start/launch controls, flipper controls, lighting and two guarded miniature coil mechanisms. The accelerometer and controller would be inside the enclosure.

Rendered LED/button counts, connector details, labels and relative sizes are illustrative. In particular, the folded lighting feature does not establish that 120 pixels fit or meet the power/thermal budget. Extra illumination shown on controls or enclosure edges is styling only, not an agreed addition to the inventory. The modular concept depicts front-facing flipper controls as a placement alternative; side mounting remains available. The project owner subsequently preferred C, with simpler construction, four front controls and rear/side cable connections.

### Visual concepts — revision 2

![Three mini-cabinet studies with four front buttons, breadboard bays and rear USB and 12V connections: curved diffuser, straight light bars and wide workspace.](./media/test-bench-concepts-v2.png)

Generated on 10 November 2026 using built-in image generation; [revision 2 prompt](./media/test-bench-concepts-v2.prompt.txt). These are component-zone studies, not dimensioned layouts. Counts, labels, connector types and mechanism details remain illustrative. Rear-view insets establish cable direction only, not a finalized internal connector location.

| Study | Design question | Practical assessment |
|---|---|---|
| C1 — Clean console | Retain the taller cabinet shape and one broad curved diffuser? | Curved lighting needs the most mechanical validation; appearance must not drive component choice. |
| C2 — Light bars | Use three replaceable straight diffused lighting sections? | Preferred lighting approach to investigate for simple fabrication and service access. |
| C3 — Wide workspace | Widen and lower the enclosure for working space? | Preferred space-planning direction to investigate; actual access and clearances require measured parts. |

The initial recommendation was to investigate C3's workspace with C2's straight lighting sections. The project owner subsequently rejected the raised tops in these studies; revision 3 supersedes that enclosure geometry. Select and Add Player are shown as unlit controls; additional lamp outputs are not assumed. No decorative edge lighting is required.

### Visual concept — revision 3

![A symmetrical test bench with a single sloping top, opposing side flipper buttons, four front controls, breadboard bay and rear cable connections.](./media/test-bench-concepts-v3.png)

Generated on 10 November 2026 using built-in image generation; [revision 3 prompt](./media/test-bench-concepts-v3.prompt.txt). The revised study removes the raised display section and puts the LCD in the same top plane as the controls. Matching side walls and opposing flipper buttons establish left/right enclosure symmetry; the two guarded coil mechanisms are also placed on opposite sides. The breadboard and test-button zones remain functionally different rather than duplicating components merely for visual symmetry.

The top-down and rear views illustrate intended placement only. Exact symmetry, dimensions, mounting depths and connector positions must be established in CAD. Pixel counts and lighting lengths remain schematic: the short rendered light bar does not demonstrate accommodation of all 120 pixels. Revision 3 is a historical study, superseded by the larger revision 4 layout and subsequent continuous-strip requirement.

### Visual concept — revision 4

![Larger symmetrical test bench with a long U-shaped perimeter lighting run, separate short pixel strip and status lights, full-size breadboard bay, four front buttons and rear connections.](./media/test-bench-concepts-v4.png)

Generated on 10 November 2026 using built-in image generation; [revision 4 prompt](./media/test-bench-concepts-v4.prompt.txt). The project owner requested a full-width or perimeter main strip, more physical pixels for testing lighting displays, room for a larger box and potentially a full-size breadboard. This study adopts a full-size breadboard as its design target and uses three straight main-strip sections along the left, front and right edges, with concealed connections at the corners. This joined-section construction is now superseded by the preference for one physically continuous strip. Revision 4 remains a visual reference for the available lighting area, not an approved corner construction.

Keep the 12-pixel strip and six status pixels independent of the main strip. The main-strip count is now determined by practical fit, and fewer than 120 pixels is approved. Rendered pixel counts and breadboard proportions are illustrative rather than measured. A selected full-size board's actual outline, mounting and finger clearance must determine the bay size.

Determine main-strip capacity from the chosen pixel density and usable continuous length, allowing for permitted cut points, bend radius, power connections and diffuser space. A full-width straight run is an alternative if a continuous perimeter route cannot be achieved with the selected strip. Do not introduce corner joins merely to reproduce the render. Confirm actual pixel count after the route is dimensioned; no target of 120 pixels is imposed.

The earlier 250 × 180 mm study footprint is no longer a compactness target. A larger enclosure is acceptable. Final dimensions, strip density, current budget and breadboard model remain open.

### Lighting construction considerations

The neon-like glow is feasible as an effect: addressable LEDs can be covered by a diffuser, and [pre-diffused addressable strips exist](https://learn.adafruit.com/make-it-glow-neopixel-and-led-diffusion-tips-tricks/pre-diffused-strips). This does not validate the tightly curved shape in revision 1. [Adafruit's strip guidance](https://learn.adafruit.com/adafruit-neopixel-uberguide/neopixel-strips) also notes that flexible strips are not intended for repeated bending.

Prefer one physically continuous strip in a serviceable mounting channel. Choose a straight or gently routed arrangement that suits the actual strip; segmented bars and compact matrices are historical alternatives, not the current design target. Verify the exact strip's permitted bend direction and radius, cut points, pixel pitch, voltage, current and diffuser clearance before choosing a geometry. Do not bend a conventional strip sideways to match a render. Record pixel order and verify the lighting software layout against the physical route. A reduction from the original main-strip count is approved; the separate 12-pixel and six-pixel groups remain fixed.

Next design work should produce a dimensioned component placement and wiring-space study, including the breadboard, four front switches, LCD module depth, indicator mounts, cable bend space, converter cooling and removable PCB access. Expand the enclosure rather than forcing components into an attractive but unserviceable outline.

## Breadboard expansion bay

The project owner requested space for a breadboard to try additional components. Include this in the enclosure mockups rather than treating it as an accessory added after the PCB and enclosure are fixed.

Current proposal: a recessed, top-accessible, replaceable **full-size solderless breadboard** beside a clearly labelled expansion connector. This supersedes the earlier compact-versus-half-size study. Select the actual board before dimensioning the bay, and allow usable space around it rather than matching its outline tightly. Keep jumper wires clear of lighting channels, buttons and the lid seam. A removable cover could protect the bay when unused.

Proposed electrical provision, subject to design review:

- Ground and separately switched, current-limited prototype power, with available rails and limits labelled. Investigate 3.3V and 5V provision; avoid an exposed 12V breadboard rail in the initial design.
- Clearly marked logic voltage. A 5V power connection does not make ESP GPIO 5V tolerant; provide suitable interfacing where a test component requires it.
- Only expose spare GPIO or bus connections after checking the exact ESP board, existing assignments, reserved/boot pins, bus loading and address conflicts. No spare-pin count is promised yet; an expander may be needed.
- Keep the MOSFET indicator loads and bulk LED power on dedicated connections, outside the solderless breadboard. Define prototype power protection so an accidental short does not defeat the main output protections.
- Provide nearby test points and a connector/pinout reference in the final documentation. Make clear which shared signals can affect the existing components.

The bay is for low-power component experiments. New components still need appropriate software configuration or driver support; plugging them in does not automatically make them discoverable or supported by Pinball CTL.

## Proposed electrical architecture

The following is design intent, not a wiring diagram or approved schematic.

| Block | Intended responsibility | Checks before part selection and layout |
|---|---|---|
| 12V entry | External adapter connection, on/off control and protected power distribution. | Adapter rating and polarity, connector current, input protection, fuse coordination and cable strain relief. |
| Voltage conversion | Supply the selected LED, display, controller and sensor rails from 12V. | Worst-case load, converter losses, startup/inrush, cooling and whether to use converter modules or onboard regulators. Do not assume all peripherals use the same voltage. |
| ESP carrier | Secure removable controller connection and USB access. | Exact footprint and pinout, boot-pin constraints, antenna keepout and prevention of USB/external-supply backfeeding. |
| Inputs | Labelled connectors for 17 proposed button/switch inputs. | Defined idle states, voltage compatibility, filtering/protection and contact behaviour. Preserve existing idle settings unless deliberately revised. |
| Lighting | Three existing strip groups plus a proposed 17-pixel button chain on one additional data output; suitably rated power distribution. | Selected LED datasheets, logic-level translation where needed, branch current, wiring and connector ratings. Size protection for faults as well as normal operation. |
| Coil-output simulation | Two independent MOSFET-switched indicator loads with default-off behaviour. | Indicator voltage/current, suitable current limiting, MOSFET compatibility with ESP logic levels, gate biasing and startup/reset behaviour. No real-coil load rating or inductive capability is implied. |
| I²C peripherals | LCD and accelerometer connections matching their assigned buses. | Module supply requirements, pull-up voltages, level compatibility, address and cable length. |
| Diagnostics | Clearly labelled connectors and accessible test points. | Ground/rail access, output identification and practical probe clearance without shorting adjacent conductors. |
| Breadboard expansion | Accessible low-power prototyping connections and protected prototype power. | Spare pin availability, logic levels, current limits, shared-bus conflicts and jumper-wire clearance. |

### Coil-output simulation with lights

Replace physical solenoids with two separately labelled lights, one for each flipper output, positioned symmetrically. Each light must be switched through its corresponding MOSFET, not simply mirror the command using an unrelated GPIO or UI indication. Select an appropriate indicator load and its current limiting during component selection; exact voltage, part and circuit remain open.

This allows visible checks of channel selection, switching activity and commanded pulse/hold behaviour under a light load. A short pulse may be difficult to see, and brightness is not a reliable timing or PWM measurement. Provide output test points for instrumented checks. Do not extend configured pulses simply to make a light visible; any optional pulse-capture indicator would need to be clearly distinguished from the actual output state.

Retain firmware arming, pulse limits, cooldowns, watchdogs and fault handling. Both coil roles remain disabled in the saved inventory until deliberately configured for bench tests. Existing runtime mappings have not been changed.

These indicators do **not** validate real-coil current, force, heating, inductive turn-off, suppression or driver capability under a solenoid load. Do not describe the PCB as suitable for real coils based on indicator testing. Adding an external coil connection later would be a separate electrical-design and validation task. No coil mounts, motion guards or solenoid thermal clearance are required for the present enclosure.

## Addressable button lighting — current decision

Use **one addressable RGB pixel per button**, including eleven playfield controls, two flippers and four front controls: **17 pixels total**. The earlier 12-pixel-per-button ring and two-pixel-per-button suggestions are superseded. Keep the main strip as the larger lighting-display test area.

One ESP data output feeds pixel 1 DIN; its DOUT feeds pixel 2 DIN, continuing through all 17. All pixels also need regulated 5V and a common ground. Distribute power with appropriately rated branches rather than assuming the signal chain can carry all supply current. The ESP pin carries data, not LED power. Provide suitable 3.3V-to-5V data interfacing, decoupling and serviceable connectors; exact components and pin allocation remain pending. A broken data connection can affect every downstream pixel, so label chain order and provide accessible test connections.

Button switch contacts remain separate inputs. Proposed behaviour is to light the corresponding pixel after a debounced press and turn it off on release. This represents the input the controller registered; it does not require a separate LED GPIO per button. Map a stable pixel index to each input. This behaviour and the replacement of existing Start/Launch lamp mappings are **not implemented or deployed** by this documentation change.

A single pixel will illuminate a translucent annular surround around the button. This is a custom optical/mechanical assembly, not an off-the-shelf addressable ring. Prototype one button with an opaque light chamber and frosted diffuser before fixing its size: a single emitter may produce a bright spot rather than an even ring. Retain one pixel per button while testing diffuser geometry. The switch’s own single-colour LED, if present on a sample button, would be unused.

## Initial shopping list

Researched **10 November 2026**. These are candidate parts and displayed prices, not an approved order or complete build quotation. Prices exclude delivery; VAT is stated where verified. Amazon UK is preferred, but accessible listings did not consistently expose current prices and mechanical drawings. UK specialist alternatives are recorded rather than inventing Amazon prices. Dimensions below belong only to the linked part; allowances are design proposals, not vendor specifications.

| Item / quantity | Candidate and supplier | Displayed unit price | Dimensions and fitting / selection status |
|---|---|---|---|
| Button samples, eventually 17 | [ModMaker 16mm momentary stainless switch](https://www.modmaker.com/16mm-green-led-stainless-steel-illuminated-switch-with-flat-flush-actuator) | £2.50; £42.50 for 17, VAT basis unconfirmed | 16mm panel hole, 18mm bezel, 20mm underside-to-contact-end depth. Nut mounted; verify nut diameter and panel thickness. Integrated green LED is unused with our separate RGB pixel. Start with a sample; prefer an equivalent unlit version if verified. |
| RGB pixel optical/electrical samples, 1 pack | [Adafruit ADA1312, five individual pixels, The Pi Hut](https://thepihut.com/collections/maker-store/products/adafruit-breadboard-friendly-rgb-smart-neopixel-pack-of-4) | £7.70 inc VAT per five-pack | Enough to test a single-pixel surround and short chain. Breakout dimensions must be checked before mounting. Production may use individual cut strip pixels or small daughterboards instead; do not buy 17 full rings. |
| Addressable strip, 1m candidate | [144 pixels/m WS2812B strip, The Saber Armory](https://thesaberarmory.com/collections/neopixels-led-strips/products/high-quality-ws2812b-144-led-per-meter-neopixel-led-strip) | £12.00 displayed; VAT basis unconfirmed | Nominal pitch 6.94mm. Confirm exact width, cut pads, supply rating and SKU. One reel could supply main, 12, 6 and 17 individual button pixels if single-pixel cuts are suitable. The main run stays physically continuous. |
| Full-size breadboard, 1 | [Makertronics 830-point, Technobots](https://www.technobotsonline.com/makertronics-830-point-solderless-breadboard.html) | £1.79 inc VAT | 165 × 56mm; height not specified. Removable tray with retaining lips; do not bond it permanently to the enclosure. |
| 16×2 display, 1 | [PCF8574 LCD1602, Kunkune](https://kunkune.co.uk/shop/arduino-sensors/lcd-1602-module-iic-i2c-serial-backlight/) | £3.90 listed in-stock offer; variant/VAT to confirm | Exact backpack-inclusive dimensions and mounting holes pending. Reserve 90 × 45 × 25mm provisionally. Must match current PCF8574-style driver; not every I²C 1602 module does. Check pull-up voltage. |
| ESP32-S3, 1 or reuse | [ESP32-S3-DevKitC-1, The Pi Hut](https://thepihut.com/products/esp32-s3-devkitc-1-development-board) | £28.90 inc VAT | Variant, header positions and USB connector must be verified before carrier design. Reserve 80 × 40mm including access provisionally; this is not its board outline. |
| Accelerometer, 1 or reuse | [MMA8452Q breakout, SK Pang](https://www.skpang.co.uk/collections/accelerometers/products/triple-axis-accelerometer-breakout-mma8452q) | £9.00 inc VAT | Prefer reusing the configured sensor after identification. Candidate outline/holes pending; reserve 30 × 30mm. Rigid mounting with recorded orientation. |
| External 12V supply, 1 candidate | [Mean Well GST60A12-P1J, DigiKey UK](https://www.digikey.co.uk/en/products/detail/mean-well-usa-inc/GST60A12-P1J/7703712) | £14.28 ex VAT / about £17.14 inc VAT | 12V 5A; external body 125 × 50 × 31.5mm; centre-positive 5.5/2.1mm plug. Requires a separate UK IEC C13 lead. Final rating depends on full load budget. |
| 5V buck converter, candidate only | [Pololu D36V50F5, The Pi Hut](https://thepihut.com/collections/all/products/pololu-5v-5-5a-step-down-voltage-regulator-d36v50f5) | £38.40 inc VAT | [Manufacturer dimensions](https://www.pololu.com/product/4091/specs): 25.4 × 25.4 × 9.525mm without headers. Nominal 5.5A is operating-condition dependent. Thermal/load validation needed; not yet selected for the complete bench. |
| MOSFET output lamps, 2 | [12V panel indicator, Furneaux Riddall](https://www.furneauxriddall.com/products/8-2mm-led-panel-indicator-12v) | £5.74 inc VAT; £11.48 for two | Amber candidate; 300mm leads. Verify exact cutout and body depth from drawing/sample before panel design. These remain separate MOSFET loads, not addressable substitutes. |
| MOSFET stages, 2 prototype modules or PCB circuits | [Adafruit 5648 driver](https://www.adafruit.com/product/5648) | US $3.95 each; UK landed price pending | Module 25.4 × 17.7 × 7.2mm. Candidate for indicator-load prototyping; final carrier may integrate the stages instead. Do not double-count modules and integrated circuits. |
| Rear USB extension, 1 candidate | [Micro-B panel extension, The Pi Hut](https://thepihut.com/collections/raspberry-pi-cables/products/panel-mount-extension-usb-cable-micro-b-male-to-micro-b-female) | £3.90 inc VAT | 300mm cable, 18mm fixing centres; supplied M3 screws. Select only if it matches the actual ESP port; allow internal connector/cable clearance. |
| DC inlet, switch, fuses, USB power isolation, logic translators, prototype-rail protection | Exact parts pending electrical design | Not yet priced | Match adapter polarity and full branch currents. Do not select a low-current barrel jack solely because its plug fits. |
| Wiring, keyed connectors, sockets, fasteners, inserts, feet, diffusers, PCB and printed enclosure | Exact parts / fabrication services pending | Not yet priced | Define cable lengths, wire sizes, mounting stack and PCB assembly method before quoting. |

Amazon comparison candidates: [16mm Gebildet switch B0DLKQ893Y](https://www.amazon.co.uk/dp/B0DLKQ893Y) and [AZ-Delivery breadboard B078JGQKWP](https://www.amazon.co.uk/dp/B078JGQKWP). Current prices and exact variant dimensions were not verified, so neither is selected. No overall total is presented while essential protection, mechanics and fabrication remain unpriced. Recheck stock, VAT and prices before purchase.

## Preliminary dimensions and fit allowances

Study **360mm wide × 280mm deep**, with approximately **60mm front / 90mm rear height**, a single sloping top and no raised section. These are proposed outside dimensions, not a released CAD model. The 30mm rise over 280mm gives approximately 6° slope. Confirm whether a split enclosure is preferable for the chosen print service.

| Area | Initial allowance | Fitting approach / outstanding check |
|---|---|---|
| Button and light surround | Target 28–32mm surround diameter, at least 40mm centre spacing; reserve 35mm behind panel | 16mm nut-mounted switch plus separate pixel/diffuser pocket. Final optical cavity, nut access, wire exit and finger clearance need a sample. |
| Playfield controls | Left zone approximately 220 × 190mm | Eleven controls in table-like groups, with room for labels. Validate reach and positions in dimensioned CAD. |
| Breadboard | Right bay approximately 80 × 185mm | Orient the 165mm length front-to-back; retain removable tray and space for jumper wires. Verify board height before recess depth. |
| Display | Provisional 90 × 45 × 25mm envelope | Mount under the top on standoffs, with a window sized from the actual LCD and access to contrast adjustment. |
| Front and side controls | Four front buttons; two mirrored side buttons | Keep rings and rear wiring clear of corner joints and lid fasteners. All external USB/DC cables exit rear or side. |
| Main strip | Initial straight usable span 320mm | At 144 pixels/m, 46 pixels occupy about 319.4mm nominally; verify end pads and wire space. A longer continuous perimeter remains possible only with a verified bend-compatible strip. |
| Short/status strips | 12 and 6 pixels | About 83.3mm and 41.7mm at the same density, before connector allowance. Separate replaceable channels. |
| Electronics | Removable base-mounted carrier, protected wiring paths | Place controller and buck clear of switch tails and breadboard recess; reserve antenna clearance, airflow and access to mounting screws. |

The straight-run study totals **46 + 12 + 6 + 17 = 81 addressable pixels**. Only the button count is fixed here; 46 is a main-strip fit example, not a new configuration. At a conservative planning allowance of 60mA per pixel, LEDs alone could require 4.86A at 5V before logic, display and prototype loads. Use the exact selected LED datasheet and measured load to complete the budget; the candidate 5.5A converter is not yet approved. Normal brightness can be modest, but wiring and protection must not depend solely on software brightness limits.

Before fixing the PCB, audit the exact ESP module against current GPIO assignments. [Espressif’s board guide](https://documentation.espressif.com/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html) documents memory-related pin restrictions and board peripherals. In particular, GPIO 37 may be unavailable on octal-memory variants, and onboard RGB LED connections vary by board revision. The current flipper/bumper assignments must not be assumed compatible with every DevKitC-1. No pin reassignment is made here.

## Component selection and design process

1. **Resolve the concept and constraints.** Choose the enclosure arrangement, acceptable footprint and budget. Determine the main-strip count from continuous-strip fit; full 138-pixel coverage is no longer required.
2. **Prepare a candidate bill of materials.** Recommend exact orderable parts with supplier links, datasheets, dimensions, electrical ratings, indicative costs and alternatives. Include all fasteners, wiring, connectors and assembly consumables. The shortlist below is preliminary; no purchase or manufacturing release is approved.
3. **Verify electrical and mechanical feasibility.** Build the load budget for simultaneous lighting, MOSFET indicator loads and logic; check connector and trace requirements, heat, fit and safe defaults. Confirm the specific ESP board before designing its socket.
4. **Produce mockups.** Compare exterior concepts and an internal component layout using the selected parts' dimensions. Agree access, labels, light diffusion and assembly sequence before detailed CAD.
5. **Develop enclosure and PCB together.** Maintain mounting-hole, connector, USB and cable-clearance alignment. Keep editable sources, drawings and a revisioned BOM alongside the design.
6. **Review and prototype.** Run electrical/design-rule checks, inspect manufacturing previews, check print tolerances and obtain an electrical review of the power and MOSFET indicator design. Order a prototype only with project-owner authorization.
7. **Validate the physical prototype.** Check fit, rail voltages, load/thermal behaviour, USB power interactions, input events, lighting, sensor orientation, output timing and firmware limits with indicator loads, reset/disconnect states and power cutoff. Record results and required revisions.
8. **Release a manufacturing package.** Export the validated revision for the chosen suppliers. File-format acceptance alone does not establish that a design is production-ready.

## Planned deliverables

| Deliverable | Contents | Current status |
|---|---|---|
| Concept package | Exterior views, internal arrangement, options and approximate dimensions. | Revisions 1–6 rendered; revision 6 illustrates proposed dimensions, full-size breadboard and single-pixel button surrounds. Verified CAD and internal arrangement pending. |
| Component package | BOM, datasheet/supplier links, costs and electrical load budget. | Initial priced shortlist and sizing allowances below; detailed PCB BOM and fit verification pending. |
| Enclosure package | Editable parametric CAD, STEP assembly, printable parts, dimensional drawings and assembly instructions. | Not started. |
| PCB package | Editable schematic/layout, BOM, Gerbers, drill files, fabrication notes and assembly placement files where required. | Not started. |
| Verification record | Review results, rule checks, prototype measurements, fit checks and unresolved issues. | Not started. |

Supplier formats will be checked when a service is selected. For reference, [JLC3DP's ordering guide](https://jlc3dp.com/help/article/how-to-place-a-3d-printing-order) lists STL, STP, STEP and OBJ uploads. An assembled PCB also needs service-specific component and placement information; see [JLCPCB's BOM/CPL guidance](https://jlcpcb.com/help/article/advice-for-bom-and-cpl-files-preparation). These are format references, not selected suppliers or approved orders.

## Open decisions

| Decision | Current position |
|---|---|
| Power input | **Agreed:** external 12V DC adapter; exact model and rating to be recommended. |
| Component sourcing | Prefer Amazon UK; initial priced UK shortlist recorded above. Unverified dimensions and unpriced items remain explicit; purchases are separate. |
| Button lighting | **Agreed:** one addressable RGB pixel per button, 17 chained on one data pin. Custom diffusing surround; sample required before mechanical release. |
| Budget | Open, including enclosure printing, PCB assembly, parts, shipping and prototype revisions. |
| Enclosure style and dimensions | C-derived direction, but raised rear sections rejected. Symmetrical sides and opposing flipper positions required. Revision 3 studies a single sloping plane; final dimensions open. |
| External cable access | Rear or side vertical face required; no top-mounted USB or 12V connections. |
| Front controls | Study Start, Launch, Select and Add Player; two additional inputs need pin allocation and software design. |
| Playfield grouping and bumpers | Three bumper inputs bound locally to GPIO 17/47/48, with Jackpot Target repurposed. Use table-like placement; older gameplay references still need reconciliation. |
| Breadboard bay | Full-size board is the latest study target; exact model, power limits and expansion signals remain open. |
| Physical lighting layout | Prefer one continuous main strip with as many pixels as practically fit; fewer than 120 approved. Separate 12-pixel and six-pixel groups retained. Exact strip, route and count remain open. |
| Coil representation | Replace solenoids with two MOSFET-switched indicator lights. No moving mechanisms; exact load, voltage and driver parts remain open. |
| Controller/module reuse | Open; exact existing board variants and dimensions are not confirmed. |
| Host location | External Mac/Pi proposed; not yet agreed. |
| PCB assembly | Open; determine factory assembly versus hand-fitted connectors/modules. |
| Print material and manufacturing services | Open; select after fit, thermal and supplier reviews. |

## Discussion and decision log

| Date | Record |
|---|---|
| 10 November 2026 | Project owner requested a richer compact test bench covering the configured hardware, design options and mockups, a printable enclosure, and a custom ESP carrier PCB with power conversion and peripheral connections. |
| 10 November 2026 | Project owner confirmed an external 12V adapter and requested recommendations for all components. |
| 10 November 2026 | Initial proposal: compare sloped console, modular box and mini cabinet. No concept, dimensions, budget or component models approved. |
| 10 November 2026 | Project owner requested space for a breadboard to plug in and test additional components. Added an accessible expansion bay to the brief; dimensions, connectors and power provision remain proposed. |
| 10 November 2026 | Created revision 1 visual mockups of all three enclosure options with breadboard bays. Saved the comparison sheet and generation prompt; concept selection remains open. |
| 10 November 2026 | Project owner preferred C, requested rear/side USB and 12V ports, a Select control and potentially a fourth Add Player control, and simpler variations. Four front buttons are included in the next concept study. |
| 10 November 2026 | Project owner established **function before form**. Component feasibility, access, wiring and thermal design take priority over styling; no rendered lighting shape is a committed construction detail. |
| 10 November 2026 | Saved revision 2: C1 curved diffuser, C2 straight light bars and C3 wider workspace, each with four front controls and rear cable access. Proposed combining C3 workspace with C2 lighting for feasibility study; no variant approved. |
| 10 November 2026 | Project owner rejected the raised tops and required symmetrical left/right sides with matching flippers. Saved revision 3 with a single sloping top, flush LCD, opposing side flipper buttons and rear cable access. Awaiting feedback on the revised layout. |
| 10 November 2026 | Project owner requested a main strip spanning the full width or perimeter to maximise lighting-test pixels, retained the short 12-pixel and status groups, allowed a larger box and suggested a full-size breadboard. Revision 4 studies these changes; final dimensions and pixel capacity remain unverified. |
| 10 November 2026 | Project owner accepted fewer than 120 main-strip pixels and requested ideally one continuous strip with as many pixels as fit. This supersedes the full-count requirement and joined-section proposal; the 12-pixel and six-status-pixel groups remain unchanged. |
| 10 November 2026 | Project owner proposed replacing physical solenoids with lights switched through MOSFETs because coil mounting would be difficult. Adopted two symmetric output indicators; removed coil mounts/guards from the current brief and documented the limits of light-load testing. |
| 10 November 2026 | Project owner requested table-like control grouping and clarified that three pop bumpers had been added. Local layout confirms three bumper symbols, but one is bound to Jackpot Target and two are unbound; recorded the cluster requirement and mapping discrepancy without changing runtime files. |
| 10 November 2026 | At the project owner’s request, repurposed Jackpot Target as Pop Bumper 1 on GPIO 17, configured Pop Bumpers 2/3 on GPIO 47/48, bound existing layout symbols and rebuilt the local mapping blob. No ESP deployment or gameplay-rule changes. Saved revision 5 mockup with grouped playfield controls and MOSFET indicator lights. |
| 10 November 2026 | Requested component-led dimensions and an ongoing shopping list, preferably Amazon UK. Added a priced shortlist with mounting requirements and explicit unknowns; proposed a 360 × 280mm sizing study. |
| 10 November 2026 | Agreed one addressable RGB pixel per button, 17 total, chained on one data pin. This supersedes 12-pixel rings and the two-pixel suggestion. Separate switch inputs and MOSFET output lamps remain; diffuser fit and input-to-pixel behaviour require development. |
| 10 November 2026 | Saved revision 6 mockup showing the proposed 360 × 280mm enclosure, full-size 165 × 56mm breadboard and 17 single-pixel button surrounds. Recorded generated-image limitations, including the illustrative USB connector and unverified diffuser performance. |

As work continues, record new decisions here, update the affected sections and retain unresolved questions explicitly. This is a discussion record maintained during project work, not an automatic monitoring process.
