# Test Bench

![Latest test bench mockup: retail-style controls, recessed half-size breadboard, and USB and 12V input on the right side.](./media/test-bench-concepts-v8.png)

**Current approved visual baseline: revision 8, 10 November 2026.** Use this mockup as the starting image for every subsequent design change. Preserve its charcoal enclosure, restrained teal lighting, orange arcade buttons, retail control styles and overall appearance unless a change is explicitly requested. Keep the newest approved mockup here, inside the page content.

*Visual approval covers the style and appearance. Component fit, custom RGB diffusers, electronics and manufacturing validation remain in progress; use the component schedule and CAD for dimensions.*

## Current design

A desktop bench for testing Pinball CTL inputs, lighting, display, motion sensing and MOSFET output indicators. **Function before form**, with revision 8 as the approved appearance. This page maintains the current position and component shortlist; update existing entries as decisions change.

| Area | Current position |
|---|---|
| Enclosure | Charcoal printed case, shallow sloping lid, symmetric sides; working shell 360 × 280mm, 60mm front / 90mm rear. Separate base and lid snap together with integral rear pivots and two front release clips. |
| Controls | 17 momentary inputs: 11 playfield, four front (Start, Launch, Select, Add Player), two mirrored side flippers. Use the retail control forms below. |
| Playfield grouping | Lock, left ramp, skill, entry and right orbit above three pop bumpers; standup, shooter and drain below. |
| Button lighting | One addressable RGB pixel per input, 17 chained on one data pin. Separate custom diffusers; the purchased switch's own lamp is unused. Switch contacts remain separate inputs. |
| Display lighting | One continuous main strip, plus separate 12-pixel and six-status-pixel groups. Working main-strip allowance: 320mm, approximately 46 pixels at 144/m; final count depends on fit. |
| Output testing | Two amber lights driven through the actual MOSFET output stages, at the lower left/right near the flippers. No physical solenoids. |
| Breadboard | Recessed half-size 400-point board, 83 × 56mm candidate; CAD reconstruction uses an 85 × 58mm tray recess, target 1mm proud. Pocket depth awaits a measured sample. |
| Expansion | Female expansion connections and switched, protected 3.3V/GND and 5V/GND outputs beside the breadboard. Pinout and current limits pending. |
| External connections | USB and 12V DC input on the **right side toward the rear**, on the fixed base and clear of the right flipper. No top-panel 12V connection. |
| Electronics | Socketed ESP32-S3 carrier PCB, 12V conversion, LCD, accelerometer, LED connections and input terminals. PCB design pending; host location remains open. |

Background: [Development Platform](1-development-platform.md) and [configured hardware inventory](../1-user-guide/7.2-hardware-inventory.md). Pop Bumper 1/2/3 are recorded locally on GPIO 17/47/48. Select/Add Player still need pin allocation and behaviour; existing gameplay references need reconciliation. Bench pixel counts and press-to-light behaviour are not deployed by this design work.

## Internal layout

![Internal concept showing the closed cutaway and open lid, carrier PCB, ESP, converter modules and wiring reserves.](./media/test-bench-internal-v1.png)

The next deliverable is the **custom carrier PCB itself**: a dimensioned outline, ESP socket footprint, labelled connector pinout, schematic and placement/routing layout. The current illustration is only a placement concept. A functional connection schedule is saved in `docs/design/test-bench/mechanical-v2/carrier-connections.json`: 17 switch inputs, four RGB outputs, two I²C connections, two MOSFET lamp outputs, 12V input, prototype power and expansion. Exact ESP variant, connector parts/pin order and protection must be resolved before a fabrication-ready board can be produced.

The internal study uses the approved revision 8 exterior. **A single custom carrier PCB is proposed**, with a socketed ESP, purchased converter modules, input protection, two MOSFET indicator drivers and labelled removable connectors. It remains fixed in the base; playfield controls, LCD, breadboard and lighting lift with the lid. Front and side controls stay with the base.

| Area | Placement and clearance proposal |
|---|---|
| Carrier PCB | 230 × 140mm, x=100–330 / y=105–245mm from the left/front. Board underside z=10mm above the outer bottom; 1.6mm board thickness. Printed retention supports still need design. |
| ESP | Rear-left part of carrier; reserve 80 × 40mm including socket/access, top z=32mm. Antenna faces a reserved clear area; exact board dimensions, orientation and copper keepout await selection. |
| Converter modules | Right half: 30 × 30mm bays for the 5V candidate and an unselected 3.3V buck. Reserve top z=30mm including mounting. Under the breadboard tray this gives approximately 29mm nominal vertical clearance. Thermal and connector clearances remain unverified. |
| Switch terminals | Keep tall parts out from under the bumper and skill-button tails. The skill envelope leaves roughly 14mm above bare PCB in this study. Keep the front 35mm band free for front-button wiring. |
| Side ports | USB and 12V stay at the right rear on the fixed base. Reserve 45mm inward cable access for USB, with protection near DC entry. |
| Lid harness | Removable connectors, strain relief on base and lid, and a relaxed service loop near the rear centre between hinges. Verify length, bend radius and pinch clearance throughout opening; provide a temporary prop until a lid stay is designed. |

[Dimensioned internal placement plan](./media/test-bench-internal-plan-v1.png). Coordinates and height arithmetic are saved in `docs/design/test-bench/mechanical-v2/internal-layout.json`. These are proposed envelopes, not a routed PCB or populated collision check. The existing hinge sweep covers the shell only; it does not validate installed modules or moving wires. No exact footprint, current rating or manufacturing release is implied by the rendering.

## Current components and shopping list

Maintain this as the single current shortlist: update quantities, links, prices and fit status in place. **Candidates, not an approved order.** Prices were researched on 10 November 2026, exclude delivery and require checking before purchase; VAT is noted where known. Amazon UK is preferred where exact variants and dimensions can be verified; UK specialist sources are used below. Reuse existing controller/sensor parts after identification. No complete cost total is available while fabrication and protection remain unpriced.

| Component / quantity | Candidate, supplier and recorded price | Dimensions, mounting and outstanding checks |
|---|---|---|
| Three pop bumpers | [Sanwa OBSF-24, orange option, Arcade Parts UK](https://www.arcadepartsuk.com/products/sanwa-obsf-24-24mm-arcade-buttons), £2.70 each displayed; £8.10 for three, VAT basis and orange stock to confirm | Ø24mm mounting, Ø27.2mm bezel; reserve 32mm terminal envelope plus 13mm wiring space. Custom Ø34mm RGB surround. Verify panel clip engagement including diffuser stack. |
| Lock, left ramp, entry, right orbit and shooter: five | [Omron D2F-01L, CPC SW02690](https://cpc.farnell.com/omron/d2f-01l/microswitch-lever/dp/SW02690), £0.97 ex VAT each; £4.85 ex / £5.82 inc VAT for five | Body 12.8 × 5.8 × 6.5mm; lever free height up to 10mm. Two Ø2mm mounting holes, 6.5mm centres. Reserve a custom 30 × 34mm module and 25mm underside depth. Use the actual metal lever. Carrier and protected overtravel stop require detailed design; no sculpted cap is assumed. |
| Skill-shot and standup inputs: two | [HCSWIT0028 rectangular momentary, Hobby Components](https://hobbycomponents.com/switches/634-non-latching-rectangle-push-button-switch-dc-12v-red), £1.24 ex each; £2.48 ex / about £2.98 inc VAT for two | Ø16mm mounting thread; 24 × 18mm face, 20 × 14mm actuator, 40mm total height. Reserve 50mm depth with wiring. Use stock red/green variants. Verify colour SKU before ordering. |
| Front controls, flippers and drain: seven | [ModMaker 16mm momentary](https://www.modmaker.com/16mm-green-led-stainless-steel-illuminated-switch-with-flat-flush-actuator), £2.50 each displayed; £17.50 total, VAT basis unconfirmed | Ø16mm hole, Ø18mm bezel, 20mm to contact ends; reserve 35mm for body/wiring, Ø30mm custom surround. Nut-mounted; no enclosure screws. Flat, flush stainless actuator and thin metal bezel. The external RGB diffuser is a separate proposed printed part. |
| Half-size breadboard: one | [Makertronics 5115-001, Technobots](https://www.technobotsonline.com/makertronics-400-point-solderless-breadboard.html), £1.52 inc VAT | 83 × 56mm vendor footprint. Height, adhesive thickness and interlock protrusions require sample verification before final recess depth. |
| RGB pixel optical/electrical samples, 1 pack |[Adafruit ADA1312, five individual pixels, The Pi Hut](https://thepihut.com/collections/maker-store/products/adafruit-breadboard-friendly-rgb-smart-neopixel-pack-of-4) — £7.70 inc VAT per five-pack| Enough to test a single-pixel surround and short chain. Breakout dimensions must be checked before mounting. Production may use individual cut strip pixels or small daughterboards instead; do not buy 17 full rings. |
| Addressable strip, 1m candidate |[144 pixels/m WS2812B strip, The Saber Armory](https://thesaberarmory.com/collections/neopixels-led-strips/products/high-quality-ws2812b-144-led-per-meter-neopixel-led-strip) — £12.00 displayed; VAT basis unconfirmed| Nominal pitch 6.94mm. Confirm exact width, cut pads, supply rating and SKU. One reel could supply main, 12, 6 and 17 individual button pixels if single-pixel cuts are suitable. The main run stays physically continuous. |
| 16×2 display, 1 |[PCF8574 LCD1602, Kunkune](https://kunkune.co.uk/shop/arduino-sensors/lcd-1602-module-iic-i2c-serial-backlight/) — £3.90 listed in-stock offer; variant/VAT to confirm| Exact backpack-inclusive dimensions and mounting holes pending. Reserve 90 × 45 × 25mm provisionally. Must match current PCF8574-style driver; not every I²C 1602 module does. Check pull-up voltage. |
| ESP32-S3, reuse existing | [Freenove ESP32-S3 WROOM / FNK0085 family](https://docs.freenove.com/projects/fnk0085/en/latest/), identified from the project photo; no new purchase planned | Two 20-pin header rows and dual USB-C. N16R8 purchase record conflicts with black-board N8R8 appearance; exact variant, row spacing, outline and underside clearance remain unverified. |
| Accelerometer, 1 or reuse |[MMA8452Q breakout, SK Pang](https://www.skpang.co.uk/collections/accelerometers/products/triple-axis-accelerometer-breakout-mma8452q) — £9.00 inc VAT| Prefer reusing the configured sensor after identification. Candidate outline/holes pending; reserve 30 × 30mm. Rigid mounting with recorded orientation. |
| External 12V supply, 1 candidate |[Mean Well GST60A12-P1J, DigiKey UK](https://www.digikey.co.uk/en/products/detail/mean-well-usa-inc/GST60A12-P1J/7703712) — £14.28 ex VAT / about £17.14 inc VAT| 12V 5A; external body 125 × 50 × 31.5mm; centre-positive 5.5/2.1mm plug. Requires a separate UK IEC C13 lead. Final rating depends on full load budget. |
| 5V buck converter, candidate only |[Pololu D36V50F5, The Pi Hut](https://thepihut.com/collections/all/products/pololu-5v-5-5a-step-down-voltage-regulator-d36v50f5) — £38.40 inc VAT| [Manufacturer dimensions](https://www.pololu.com/product/4091/specs): 25.4 × 25.4 × 9.525mm without headers. Nominal 5.5A is operating-condition dependent. Thermal/load validation needed; not yet selected for the complete bench. |
| MOSFET output lamps, 2 |[12V panel indicator, Furneaux Riddall](https://www.furneauxriddall.com/products/8-2mm-led-panel-indicator-12v) — £5.74 inc VAT; £11.48 for two| Amber candidate; 300mm leads. Verify exact cutout and body depth from drawing/sample before panel design. These remain separate MOSFET loads, not addressable substitutes. |
| MOSFET stages, 2 prototype modules or PCB circuits |[Adafruit 5648 driver](https://www.adafruit.com/product/5648) — US $3.95 each; UK landed price pending| Module 25.4 × 17.7 × 7.2mm. Candidate for indicator-load prototyping; final carrier may integrate the stages instead. Do not double-count modules and integrated circuits. |
| Right-side USB extension, 1 | USB-C-compatible extension; exact part and price pending | The photographed board has USB-C ports. Micro-B candidate withdrawn. Port choice, connector cutout, cable bend and USB power isolation need verification. |
| Right-side DC inlet, 1 candidate | [Switchcraft 721AU drawing](https://www.switchcraft.com/assets/1/6/721AU_CD.pdf); UK price pending | Ø8mm panel hole, Ø14.3mm flange, 20.8mm overall, 2.1mm centre pin. Confirm exact variant rating and adapter engagement; reserve 25mm wiring depth. |
| Expansion sockets, power switch and 3.3V buck module | Parts and prices pending; 30 × 30mm converter bay reserved | Reserve 34 × 8mm expansion and 58 × 8mm power windows; these are layout allowances, not selected connector sizes. |
| Protection and interfaces | Fuses, rail current limiting, USB backfeed protection, LED level translation and decoupling: parts/prices pending | Complete the electrical design and load budget before selection. |
| Wiring and fabrication | Keyed connectors, wire, controller sockets, feet, custom diffusers, PCB and printed case: prices pending | Define cable lengths, mounting stack, assembly process and service before quotation. |

The [Sanwa catalog](https://www.rs2006.co.jp/e/sanwaseimitsu/Sanwa2019OCR.pdf) and [Omron D2F datasheet](https://omronfs.omron.com/en_US/ecb/products/pdf/en-d2f.pdf) support the control dimensions. Verify low-current contact operation, lever travel and carrier stops with samples. Retail switches keep their original actuators; RGB surrounds and mounts are custom parts requiring optical and fit tests.

### Existing ESP identification and pin audit

The [project photograph](./media/build-image2.png) shows a **Freenove ESP32-S3 WROOM**, matching the [FNK0085 family and published pinout](https://github.com/Freenove/Freenove_ESP32_S3_WROOM_Board/blob/main/ESP32S3_Pinout.png): two 20-pin header rows, dual USB-C and a camera connector. Reuse this board family; do not substitute a generic DevKitC footprint. The original Amazon short link now returns HTTP 404. The purchase record says N16R8, but the black board resembles the N8R8 version described in [Freenove's guide](https://docs.freenove.com/projects/fnk0085/en/latest/fnk0085/codes/C/Preface.html); exact memory and board revision remain unconfirmed. Header spacing and outline require a dimensioned drawing or measurements before socket release. The generic ESP in the internal illustration is not its mechanical model.

**Resolve before routing:** GPIO37 (saved left-flipper input) is a PSRAM connection on R8 modules; GPIO48 (Pop Bumper 3) shares the onboard RGB LED. GPIO38/39/40 overlap SD-card functions, and the camera shares other configured pins. Keep accessories disconnected while assessing reuse; review LCD SCL on strapping GPIO3 and USB power paths. No runtime mapping has been changed. Evidence, header order and audit notes are saved in `docs/design/test-bench/mechanical-v2/esp-board-identification.json`. [Espressif's module datasheet](https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf) confirms the R8 GPIO35–37 restriction.

## Engineering status and next steps

**Mechanical prototype:** the editable native document is `docs/design/test-bench/freecad-v8/test-bench-v8.FCStd`, with dimensioned sketches, extrusions, fillets and boolean features. The native preview workflow reopens that saved file. The preceding `cad-v8` STEP/STL geometry is retained as the migration reference; its `geometry-checks.json` records shell validity, floor checks and sampled released-shell motion. Component retention, wiring, loaded motion and printing remain unvalidated. The earlier mechanical-v2 files retain the preliminary internal PCB placement and board-identification evidence; their old shell dimensions and hinge checks do not apply to this reconstruction.

[View current open-lid CAD](./media/test-bench-freecad-v8-open.png) · [View current top CAD](./media/test-bench-freecad-v8-top.png)

**Electrical design:** not yet implemented. Keep ESP GPIO at 3.3V logic, audit the exact module's pin restrictions, and design separate protected supply branches with a common ground. Prototype power defaults off; connect breadboard rails by jumpers. One-pixel surrounds need appropriate data interfacing and power distribution. The 81-pixel fit example (46 + 12 + 6 + 17) allows 4.86A at 5V using a conservative 60mA/pixel assumption, before other loads; the buck candidate is not approved by this estimate. Complete the actual part-based load and thermal budget.

**Output indicators:** retain firmware arming, pulse limits, watchdogs and faults. Lamps show switching under a light load; they do not validate solenoid driving or provide accurate pulse timing. Provide test points and do not lengthen pulses just to make them visible.

Next work:

1. Confirm budget, controller/USB variant, host location and parts to reuse. Measure button samples, breadboard height, LCD and connectors; the USB cutout remains provisional.
2. Test one single-pixel diffuser and print the hinge/latch coupons with the intended service/material. Complete carriers, electronics retention, wiring clearance and lid support.
3. Design the schematic and PCB, assign expansion pins and input-to-pixel mapping, specify rail protection, then complete electrical and mechanical checks.
4. Validate a complete prototype for fit, repeated opening, input behaviour, lighting, power and temperature before releasing enclosure and PCB manufacturing files.

No manufacturing package is released. Final deliverables are editable CAD and printable parts, schematic/layout, fabrication and assembly files, a complete BOM and recorded prototype checks.

## Mockup gallery

Revision 8 remains the current approved mockup and stays at the top of this page. Earlier concept images are visual history only; their component choices and dimensions do not define the build. CAD previews are kept separately below. Click an image to enlarge.

<div class="doc-mockup-gallery">
<figure><img src="./media/test-bench-concepts-v8.png" alt="Approved revision 8 mockup."><figcaption>Current — revision 8</figcaption></figure>
<figure><img src="./media/test-bench-internal-v1.png" alt="Proposed open and closed internal layout."><figcaption>Internal layout — proposal 1</figcaption></figure>
</div>

## CAD previews and files

These engineering previews are separate from the approved mockup at the top of this page; they do not replace it as the current visual baseline. **The editable CAD is now the native FreeCAD document `docs/design/test-bench/freecad-v8/test-bench-v8.FCStd`**, with sketches and driving dimensions, extrusions, fillets and cuts. The conversion preserves the preceding CAD geometry and control layout.

![Closed revision 8 assembly rendered from the saved native FreeCAD document.](./media/test-bench-freecad-v8-closed.png)

[Open-lid FreeCAD render](./media/test-bench-freecad-v8-open.png) · [Top FreeCAD render](./media/test-bench-freecad-v8-top.png)

Open the FCStd directly in FreeCAD; no Python script is needed to edit its sketches or recompute its features. Named profiles include the base and lid outlines, button mounting hole, LCD opening and breadboard recess. The **View settings — lid angle** control switches between closed (0°) and open (75°). Lettering retains the original solid glyph outlines to preserve its appearance; purchased parts remain dimensioned envelopes.

**These previews are rendered from the saved FCStd file.** The export script reopens that document and tessellates its assembly; the renderer uses those meshes. Save native edits before refreshing previews. Editing instructions, migration scripts and validation records are in `docs/design/test-bench/freecad-v8/`. The earlier `cad-v8` scripts and STEP files remain the conversion reference, not the editable master.

The 360 × 280mm shell dimensions remain the working size. Radii, locations and unmeasured component details are reconstruction assumptions, not measurements from a real product. These remain **design-review files, not an order-ready release**: component retention, exact supplier fit, populated lid motion, wiring and print tolerances still need validation. The reference image does not establish those hidden details.
