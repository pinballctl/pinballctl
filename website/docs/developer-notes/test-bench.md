# Test Bench

**Revision 2 · Amazon.co.uk audit · 18 November 2026.** This is a one-box development bench with real rolling balls, a three-position trough, hand-loaded shooter, manual launch gate, ten buttons, an LCD, two large flipper indication lamps and addressable lighting. It uses the selected **400 × 400 × 135 mm WooDeeDoo box**. All mechanisms and controllers are in that box; the two mains adapters remain outside during use. Storage for the adapters inside the box is not allocated.

The purchase list now identifies all installed components, fittings and consumables. The build uses plywood cut to size, drilled holes, glued supports and a small soldered interface board. It needs no 3D printer, custom PCB or machined trough.

**The audit does not establish a 100% dimension-verified or tested build.** Amazon listings do not publish the large lamps' depth/cap height/panel grip, the LCD's complete thickness/bezel dimensions, or the populated ESP stack height. These are explicit unresolved fit checks, not values inferred from a render. The box's internal dimensions are also approximate. The layout below reserves space for those parts, but final drilling and a full-build order remain conditional on those measurements.

![Illustrative revision 2 view of the natural plywood box, manual shooter, eight optical pairs and raised control console.](./media/bench-course-realistic-v2.png)

Illustrative revision 2 view. The scale plan and tables below specify dimensions, pixel counts and fixing positions; appearance and small details in this AI render are approximate. It is not a photograph of a completed prototype.

![Revision 2 scale plan showing the real-ball course, control console, enlarged controller and fuse bays, and conditional closed height.](./media/bench-course-layout.png)

The scale drawing controls placement. Green rectangles include allocated wire/connector space; they are not actual PCB outlines. The small interface and power connectors attach to the console underside, in the separate view below. Overall box dimensions exclude small external catches and the external lid stay.

## What changed after checking the listings

- The Freenove breakout is **87 × 75 mm**, so its previous 95 × 70 mm bay was too small. Its revised bay is **97 × 105 mm**, with terminal wires turning upward.
- The two **47 × 25 × 15 mm** lamp drivers now have a **55 × 65 mm** bay, including wire bends.
- A covered **87 × 52 × 42 mm** four-way fuse block replaces loose installed fuse holders. Its bay includes connection space.
- The converter has a published **53 × 50 × 20 mm** drawing. Its wiring faces sideways into a **90 × 53 mm** bay.
- The LCD selection changes to the integrated Freenove 1602, whose gallery explicitly labels the **80 × 36 mm** PCB. Its bezel and thickness still need checking.
- Three plywood walls support the removable console. The small interface moves underneath the console; it no longer competes for floor space.
- The widened corner uses square-cut rails. The starting beam height increases from 21 to **24 mm**, giving a larger theoretical clear gap between touching balls.

## How the ball course works

1. Three 27 mm balls queue in the low front-left trough. T1 is nearest the front end stop, then T2 and T3.
2. Lift T1's ball **by hand** into the higher rear-right shooter pocket. The other two balls roll forward and change the trough signals naturally. Once settled, T1 and T2 are occupied and T3 is empty.
3. The ball rests against the manual gate and blocks **Ready**. The **Fire** button is a separate input. It does not move a solenoid or open the gate.
4. Lift the gate 30 mm. The ball clears Ready, crosses Onfield, Bumper 1, the corner, Bumper 2 and Drain, then rejoins the trough at T3.
5. All three trough positions are occupied again. Repeat the hand transfer for the next launch.

Bumper stations detect passage; they do not kick the ball. This tests real ball occupancy and moving-ball events. It does not reproduce the forces of a complete pinball playfield or an automatic trough ejector. Hand transfer is the agreed first-build method.

## Dimensions and placement

All dimensions below are **millimetres**. The origin is the **inside rear-left corner**, x to the right, y toward the front, and z upward from the original inner bottom. These are design coordinates, not a drilling template. The nominal usable cavity is **380 × 380 × 125**.

| Assembly | Position and size | Height / fit basis |
| --- | --- | --- |
| Carrier | x=5, y=5; **370 × 370 × 6** | Top z=6. Five millimetres nominal side clearance. Spreads loads over the original thin bottom. |
| Course floor | x=10, y=10; **360 × 360**, front-right **260 × 260** removed; 6 thick | Two 100 mm wide legs. Running surface approximately z=41 at shooter and z=22.5 at T1. |
| Running lane | Rear centre y=60; left centre x=60; **30 clear** | 27 mm balls; 12-thick, 30-high rails. Widened corner clear area is approximately 55 × 55. |
| Console top | x=125, y=125; **240 × 240 × 6** | Top z=95, underside z=89. Front open below the panel for access/airflow. |
| Console support | Two side walls 240 long; rear wall between them | **12 thick × 83 high**. 6 carrier + 83 support + 6 top = **95**. |
| Pi and cable bay | x=140, y=140; **110 × 70** | Populated assembly and connections must stay at/below z=50. Official cooler fits inside this allowance; USB mouldings and bends still need a dry fit. |
| ESP and terminal bay | x=255, y=140; **97 × 105** | 87 × 75 breakout inside; wires rise at the sides and USB exits toward the front. **z≤50 is an unverified assembly allowance.** |
| Fuse bay | x=140, y=212; **110 × 85** | Actual block 87 × 52 × 42. Direct mounting on carrier gives top z≈48; reserve to z=51 with mounting allowance. |
| Converter bay | x=255, y=247; **90 × 53** | Rotate the 53 × 50 case so terminal leads use the extra width. Keep installed top/wiring below z=45. |
| Lamp driver bay | x=220, y=300; **55 × 65** | Two 25-wide boards side by side, 5 apart; 47-long bodies leave 18 total for end connections. Top/wiring ≤z=40. |
| Interface under console | x=255, y=160; **80 × 50** | Actual perfboard 70 × 50, components facing down. Keep whole assembly within **z=60–89**, at least 10 above the ESP reservation. |
| Power connectors under console | x=140, y=190, **100 × 20**; and x=140, y=275, **100 × 25** | Three WAGO connectors in each row. Keep connectors and harness within z=65–89; levers must remain accessible when the console is lifted. |
| Lamp keepouts | x=150, y=305 and x=280, y=305; **60 × 60** each | No electronics in these columns. **65 body + 12 wire allowance below z=95 ends at z=18; this is conditional, not a published lamp measurement.** |

The course's nominal running surface is `z = 22 + 0.035 × (x − 60) + 0.035 × (350 − y)`. This gives approximately **2° leftward** and **2° forward** slopes, with a diagonal resultant near 2.8°. Set it with support pads and sanded shims; it is not an instruction to machine an angled floor. Leave support pads loose until repeated ball runs work, then glue them and fasten the course floor.

### Controls and sensing coordinates

| Element | Centre coordinates | Mounting / action |
| --- | --- | --- |
| Shooter Ready | (313.5, 60) | Gate's closed downstream face x=300. Ball rests at x=313.5; lift gate manually. |
| Onfield / Bumper 1 | (240, 60) / (160, 60) | Opposed heads outside the rear rails. |
| Bumper 2 / Drain | (60, 155) / (60, 235) | Opposed heads outside the left rails. |
| T3 / T2 / T1 | (60, 282.5) / (60, 309.5) / (60, 336.5) | **27 mm pitch**; front end-stop face y=350. |
| First button row | x=150, 195, 240, 285, 330; y=220 | Start, Fire, Lock, Ramp, Orbit. Ø16 mounting holes; Ø18 faces. |
| Second button row | Same x; y=260 | Target, Bump 1, Bump 2, Left Flipper, Right Flipper. |
| Large lamps | (180, 335), (310, 335) | Ø46 faces; defer Ø23.5 mounting holes until thread/grip/depth check. |
| LCD reservation | Upper-left at (140, 140), 90 × 50 | Centre the actual 80 × 36 PCB here. Trace bezel and holes from the received module. |
| Status / key LEDs | Upper-left (255, 144) / (255, 180) | Six pixels / nominal 100 mm per row; labels beside individual pixels. |

Eight sensor pairs means **16 physical heads**. Mount each on an adjustable plywood pad outside the rails, with the optical axis initially **24 mm above the local running surface**. Start the pads with laminated 12 + 6 mm offcuts and shim to the measured lens centre; do not assume the lens is exactly halfway up its housing. Drill aligned beam apertures through both rails, starting around 3 mm and enlarging only if alignment requires it. Fix the heads through their flanges with small screws and nylon washers, without distorting the housing.

For a 27 mm ball, radius r=13.5 and beam height h=24, the ideal blocked length is `2 × √(13.5² − (24 − 13.5)²) = 16.97 mm`. Touching balls therefore leave an ideal **27 − 16.97 = 10.03 mm** clear window. This is more generous than the previous 4.55 mm window at h=21. Finite beam width, reflections, ball speed and debounce shorten the real clear interval. At an illustrative 500 mm/s, 10 mm lasts only 20 ms even before those losses: test the actual event stream rather than assuming a debounce setting will preserve every transition.

## Mounting and simple cut list

![Carrier, console support and optical mounting sections for revision 2.](./media/bench-course-mounting.png)

![Console underside layout showing separate interface and power-connector positions with lamp and switch clearances.](./media/bench-course-underside.png)

Use ordinary saw cuts and drilled holes. The tools assumed already available are a square/ruler, saw or jigsaw, drill with depth stop/countersink, clamps, sandpaper/file, small screwdrivers, wire stripper, insulated-terminal crimper, soldering iron, heat source for shrink, multimeter and marker. No laser cutting or CNC is required.

| Cut material | Quantity / finished nominal size | Purpose |
| --- | --- | --- |
| 6 mm sheet 1 | 1 × **370 × 370** | Carrier. Trim to delivered cavity; do not force it between walls. |
| 6 mm sheet 2 | 1 × **360 × 360**, remove front-right **260 × 260** | L-shaped course. Cut the 240 square console from that waste, allowing for kerf. |
| 6 mm waste | 1 × **240 × 240** | Removable console. Mark control centres, then trace the actual LCD. |
| 12 mm sheet | 2 × **240 × 83**; 1 × **216 × 83** | Console side walls and rear wall, forming a U. Glue to carrier and each other; keep the front open. |
| 12 mm sheet | 1 × **317 × 30**; 1 × **305 × 30**; 2 × **250 × 30** | Rear outer, left outer and two inner rails. Inside lane faces at x=45/75 and y=45/75. Inner rails start 100 mm from the rear/left datum. |
| 12 mm sheet | 2 × **30 × 30** | Trough front stop and shooter outer end stop. |
| 6 mm waste | 1 × **29 × 40** | Manual gate, 6 thick. Slide in a **7 mm** guide gap; 30 mm lift clears the ball. Round the top edge for fingers. |
| 6/12 mm waste | 4 guide cheeks about **12 × 40**, plus spacing offcuts | Screw-on gate guides outside the clear lane. Establish the 7 mm channel with the actual gate; no tight friction fit. |
| 12 mm waste | 4 × **30 × 12** | Horizontal console fixing cleats, 12 thick, on the upper inside faces of the U-frame. Top surfaces z=89; screws enter their broad faces. |
| 12 mm waste | 4 × **30 × 12** | Carrier retaining cleats, 12 thick, screwed to pine sidewalls above carrier edges. Place away from the low trough and cable entry. |
| 12 + 6 mm waste | 16 × roughly **20 × 20** pads, shimmed | One per sensor head. Final shim height comes from its actual lens position. |
| 12/6 mm waste | Six or more **30 × 30** pads, stacked/trimmed | Support the course floor at its measured slope. All loads go into the carrier. |
| 6 mm waste | 1 × **110 × 54** | Removable trough transport cover spanning the rail tops at y≈250–360. Add 3 mm foam underneath over the balls. |
| 12 mm waste | 1 × **29 × 12** keeper, 12 thick | Glued under the rear end of the transport cover across the lane. Its underside is lower than a ball's diameter, so balls cannot escape backward. Existing front stop retains the other end. |
| 12 mm waste | Two halves making **40 × 40 × 12** overall | Split cable-entry backing inside the right wall, around a 25 mm pass-through hole. Cut a padded cable opening after the USB plug and pigtail have passed through. |
| 6/12 mm waste | Cable-clamp bars about **40 × 12** and backing about **50 × 30** | Foam-padded strain relief for the two low-voltage entry leads. |
| 12 mm waste | Backing about **50 × 30** at each catch/stay attachment where needed | Spread loads on the 3 mm lid; keep backing clear of the lamp caps when closed. |

Both 6 mm sheets and the 12 mm sheet have sufficient nominal area for these cuts and offcuts. This is not a nesting guarantee for every saw/kerf; mark the complete cut plan on the sheets before sawing. Leave shims and fittings' final holes until the physical parts arrive.

### Fastening sequence

1. **Fit the carrier.** Countersink/counterbore the underside for board standoff nuts before installing it. For a 6 mm male stud, a roughly 3 mm-deep recess leaves 3 mm of plywood and room for the small nut; verify complete engagement with the actual washer/nut. Keep the underside flush so it does not point-load the original 3 mm bottom. Retain the carrier with four sidewall cleats; M3×20 through a 12 mm cleat gives about 8 mm penetration into a nominal 10 mm pine wall. Measure first and avoid breakthrough.
2. **Build the U-frame.** Glue the three walls to the carrier and one another. Glue the four upper cleats inside, with screw centres at (245,143), (347,207), (143,325) and (347,330); the underside drawing shows their positions clear of the controls. Pilot-drilled M3×16 screws through the 6 mm console enter the 12 mm cleats by about 10 mm. The console lifts off after removing four screws. Drill ventilation holes in both frame sides and leave the front open; keep wires away from the Pi fan.
3. **Fit controllers and power.** Use 10 mm nylon standoffs and matching screws/nuts. Pi holes take M2.5; use the actual other boards as hole templates. Mount the covered fuse block and converter directly to the carrier through their mounting features, using short screws whose points finish inside the carrier; do not add the 10 mm board standoffs beneath these two parts. Leave the two lamp columns empty.
4. **Fit the console underside.** Install the interface on the listed 10 mm standoffs, components downward, with its lowest point above z=60. Mount the reservoir capacitors on their sides if needed, insulate their leads and retain their bodies; their actual dimensions must fit the same envelope. Retain six WAGOs in the two marked rows with screw-mounted saddles/ties and foam as needed. Keep their levers free. Reserve a relaxed service loop, roughly 150–200 mm of extra harness, so the panel can be lifted and supported without pulling terminals. Disconnect labelled screw/lever terminals for complete removal.
5. **Prototype then fix the course.** Temporarily clamp rails and pads, run all three balls repeatedly, and adjust the floor and sensor alignment. Glue the proven rails and support pads. Attach the floor to support pads using countersunk screws clear of the lane; screw points must finish inside the supporting timber. Keep the running surface smooth and free of screw heads.
6. **Fit lighting and entries.** Use short, screw-retained LED clips and backing where needed. Solder flexible links at cut pads; no folded strip corners. Pass the Pi's USB-C plug and captive DC pigtail through the right-side 25 mm opening before fitting the split padded backing. Place it near y=285, z=60 and provide a corresponding passage through the U-frame side wall; verify the cable bends clear the converter below and switch tails above. Restrain the cables internally; do not rely on their solder joints or pinch the insulation. Both entering cables carry low voltage.
7. **Fit closure hardware last.** Dry-fit the two front catches and one externally mounted right-rear locking stay. Transfer their holes from the actual hardware because the listing does not provide complete patterns, and the stay's open-length figures conflict. Back thin lid material. Prove free movement and positive locking before relying on the stay.
8. **Prepare for transport.** Put all three balls in the trough, install the padded cover with four M2.5×16 screws into the rail tops, close the manual gate, disconnect external supplies and secure the lid catches. The cover's rear keeper and front stop trap the balls; they must not be loose among electronics. Carry the box supporting its base, not by the lid/stay. Remove the cover before testing.

## Lighting and electrical connections

The main effect strip is **four separate 12-pixel sections**, nominally 200 mm each, centred on the four inner walls at approximately z=110. The console has a six-pixel status row and six-pixel key-light row, nominally 100 mm each. **48 + 6 + 6 = 60 pixels.** Cut on the marked copper pads by pixel count; measure the real strip rather than assuming a cut lands at an exact ruler mark.

The three lighting groups can use three ESP data outputs and three channels of the AHCT125, or one chained data stream if the firmware configuration requires it. **The fitted component schedule above is for one chained stream** with one 330 Ω series resistor. For three independent streams, use three 330 Ω resistors and three 10 kΩ data pull-downs from the same kit; two extra of each are already included. Keep every run's data direction consistent and all 5 V supply feeds parallel. This does not prescribe a GPIO map.

| Connection / protection | Concrete arrangement |
| --- | --- |
| Pi/ESP power | P24 directly to Pi USB-C. Pi USB-A → P23 → ESP serial/programming USB-C. Leave breakout external-power input unused. **Do not join the lighting buck's 5 V to USB VBUS or the ESP's USB-fed 5 V rail.** |
| 12 V input | P25 → captive P27 female socket → **F1 3 A** in P17, positioned close to the entry. Confirm centre-positive polarity before connection. |
| Buck branch | F1 output → converter input. Converter output verified near 5.0 V before attaching LEDs/display. |
| Lighting branch | Converter +5 V → **F2 5 A** → 18 AWG distribution → all strip sections. The worst-case planning allowance is **60 × 60 mA = 3.6 A / 18 W**, not a measured strip demand. |
| Logic/display branch | Converter +5 V → **F3 2 A** → LCD, AHCT125, I²C converter high side and eight sensor pairs, using 22 AWG. Sensor signal pull-ups and the I²C low side use the ESP's **3.3 V**. |
| Indicator branch | F1 output → **F4 2 A** → two P16 drivers → the two lamp LED connections, following each driver's labelled supply/load terminals. Use separate ESP control signals, verified active-high and OFF at reset. |
| Returns | Join low-voltage grounds at labelled distribution points. Main LED current returns directly in 18 AWG to the converter/supply return, not through the ESP breakout, sensor harness or USB cable. |
| Distribution | Six WAGOs: 12 V split; two linked 5 V lighting groups; logic 5 V split; power return; logic/control return. Each WAGO is one common electrical node. Link the lighting connectors with 18 AWG. The six strip returns join a soldered, insulated 18 AWG return trunk leading to the power-return connector; retain each splice and never put multiple conductors into one lever port. Low-current sensor/button buses may use soldered, insulated 22 AWG branches. |
| Input count | Ten momentary inputs + eight optical receivers = **18 inputs**, plus two lamp-control outputs, LCD I²C and LED data. Check the selected ESP board's available pins and boot/flash restrictions before assigning them. |

Fuses protect the selected wiring branches; they do not replace firmware pulse limits or guarantee protection of every semiconductor. The 3 A input and 5 A lighting values are starting design choices for this LED/lamp rig, subject to confirming inrush, voltage drop and the actual loads. Check that P17's four circuits are isolated so the 12 V and 5 V feeds cannot be bridged by an internal common bus. A different fuse-block revision with a common bus would not be a valid substitution.

For the AHCT125, use its actual datasheet pinout, decouple at the IC and tie unused inputs to a defined level. Use the correct output-enable states for the selected channels. The LCD needs a suitable driver for its actual I²C device/address; detect and verify it rather than assuming an address. The bidirectional LCD level converter is a different circuit from the fast LED buffer.

## Amazon.co.uk shopping list

**Audit date: 18 November 2026.** Every purchase link in these tables was opened on Amazon.co.uk. The selected option, quantity and available dimensional evidence are recorded here. Availability and prices can change; no order was placed. Quantities are for a complete new build; omit matching items already owned. Tools are listed separately and are not installed parts.

**This is a complete purchase schedule for the proposed assembly, but not a fully dimension-verified bill of materials.** “Not published” means the listing does not provide that measurement. A reserved space is a design allowance, never a substituted product dimension. In particular, lamp depth, LCD thickness and the populated ESP height remain unresolved. Do not cut their final mounting features or order the whole build on the assumption that those checks passed.

### Box, ball course and controls

| ID / quantity | Exact product and variant | Published dimensions / specification | Installation and evidence |
| --- | --- | --- | --- |
| P01 · 1 | [WooDeeDoo B0973KZMGK](https://www.amazon.co.uk/dp/B0973KZMGK?th=1), **40 × 40 × 13.5 cm** | Outside **400 × 400 × 135 mm**; inside **approximately 380 × 380 × 125 mm**; 3 mm birch-ply lid/base | Listing text. Original hinges included. The inner size is approximate; check the delivered box and hinge intrusion. |
| P02 · 1 pack of 3 | [sourcing map chrome steel balls, 27 mm](https://www.amazon.co.uk/dp/B0CCJXJJWR) | **Ø27 mm**, three balls | Listing size. 30 mm clear lane gives 3 mm total lateral clearance. Not a claim of regulation pinball weight or diameter. |
| P03 · 2 sheets | [6 mm plywood, 600 × 600 mm](https://www.amazon.co.uk/dp/B0GZBRJCFZ) | **600 × 600 × 6 mm** each | Carrier, course, console, gate and covers; see cut list. All are DIY wooden parts, not purchased pinball mechanisms. |
| P04 · 1 sheet | [12 mm plywood, 600 × 600 mm](https://www.amazon.co.uk/dp/B07WNJ7BW5) | **600 × 600 × 12 mm** | Rails, console support frame, pads, cleats and backing pieces. Allow saw kerf and trim shims to the measured running height. |
| P05 · 8 pairs | [Adafruit ADA2167 3 mm break-beam sensors](https://www.amazon.co.uk/dp/B01BU6YBWU) | Each head **20 × 10 × 8 mm**; cable **230 mm**; 3.3–5.5 V | Amazon product identity; dimensions and open-collector output from [Adafruit](https://www.adafruit.com/product/2167). Sixteen heads total. First prove one pair with touching balls, then populate the remaining stations. |
| P06 · 2 packs of 5 | [Gebildet B081JJBN4G](https://www.amazon.co.uk/dp/B081JJBN4G), **16 mm Momentary Flat Head** | Face **Ø18 mm**, mounting **Ø16 mm**, overall length **22 mm**, cap **1.9 mm** | Amazon gallery drawing. Ten switches, supplied nuts. Reserve 35 mm below console top including wire bends. Check the nut seats fully on the 6 mm panel; no latching variant. |
| P07 · 1 pack of 2 | [uxcell yellow 12 V LED arcade buttons](https://www.amazon.co.uk/dp/B07XYWYJFJ) | Face **Ø46 mm**; listed mounting hole **Ø23.5 mm**; **12 V LED** | Use only the LED terminals as flipper indication loads. **Full depth, cap height and panel grip not published.** The 65 mm body + 12 mm wire allowance is not verified. Mounting nuts and microswitches supplied; switches unused. |
| P08 · 1 pack of 2; use 1 | [Freenove I²C LCD1602, new type](https://www.amazon.co.uk/dp/B0B76Z83Y4), **I2C 1602 2 Pack** | PCB **80 × 36 mm**, mounting holes **Ø3 mm** | Amazon gallery labels. Integrated I²C circuit replaces the earlier Youmile backpack candidate. **Bezel size, hole centres and complete thickness not published.** Reserve 90 × 50 × 30 mm; trace the received bezel and holes. |
| P09 · 1 metre | [BTF-LIGHTING WS2812B](https://www.amazon.co.uk/dp/B01CDTED80), **1 m / 60 LEDs, Gold Wire Black PCB IP30** | **5 V**, 60 pixels/m, nominal **16.67 mm cut pitch** | Each LED is cuttable. Four 12-pixel runs and two six-pixel rows consume exactly 60 pixels. Measure PCB width before using the selected 10 mm clips; listing text did not dimension it. Existing [5 m version](https://www.amazon.co.uk/dp/B01CDTEJBG) can supply the same pieces. |

### Controllers, interfaces and power

| ID / quantity | Exact product and variant | Published dimensions / specification | Installation and evidence |
| --- | --- | --- | --- |
| P10 · 1 if needed | [Raspberry Pi 5, SC1111, 4 GB](https://www.amazon.co.uk/dp/B0CK3L9WD3) | PCB **85 × 56 mm**; holes **Ø2.7 mm**, **58 × 49 mm** centres | Amazon identity; [official mechanical drawing](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf). Reserve 110 × 70 mm including USB connection space. Existing Pi 5 can be reused. |
| P11 · 1 | [Official Raspberry Pi Active Cooler, SC1148](https://www.amazon.co.uk/dp/B0CLXZBR5P) | **63.5 × 42.5 × 13.7 mm** | [Official drawing](https://pip-assets.raspberrypi.com/categories/993-raspberry-pi-active-cooler/documents/RP-008187-DS-1-raspberry-pi-active-cooler-mechanical-drawing.pdf?disposition=inline) and Amazon model. Supplied push pins, thermal pads and fan lead; connect to Pi fan socket. No additional Pi enclosure. |
| P12 · 1 if needed | [SanDisk High Endurance 32 GB microSDHC](https://www.amazon.co.uk/dp/B07P14QHB7) | **32 GB**, microSD form factor; standard card envelope **15 × 11 × 1 mm** | Capacity verified in listing; card envelope is the microSD format, not a measured sample. Existing configured card can be reused. Keep access to the Pi card edge. |
| P13 · 1 pack of 2; use 1 | [Freenove ESP32-S3, 16 MB Flash, 2 Pack](https://www.amazon.co.uk/dp/B0FRRJCDHF), **FNK0099K** | 16 MB flash / 8 MB PSRAM, USB-C; complete board dimensions not published | Concrete new-purchase option. Do not assume it is the same revision as an existing FNK0085. Check firmware target and board pinout before deployment; this design does not assign GPIO numbers. |
| P14 · 1 | [Freenove FNK0091 breakout](https://www.amazon.co.uk/dp/B0CD2512JV) | PCB **87 × 75 mm**; 2.54 mm headers | Amazon gallery distinguishes board size from its 125 × 80 × 25 mm packaging. Manufacturer lists Freenove ESP32/S3 compatibility. **Populated height not published.** Reserve 97 × 105 mm and z≤50 mm; route terminal wires upward. No external barrel power into this board. |
| P15 · 1 | [VOLRANTISE converter](https://www.amazon.co.uk/dp/B09WZ9DC9W), **12/24 V to 5 V 10 A** | **53 × 50 × 20 mm**; 10–35 V input; 5 V / 10 A advertised output | Amazon dimension drawing. Reserve 90 × 53 mm with connections facing sideways. Supplies lighting/display, not Pi USB-C. Verify output voltage and temperature under the actual load. |
| P16 · 1 pack of 4; use 2 | [JZK F5305S optocoupled MOSFET modules](https://www.amazon.co.uk/dp/B09SWRF88D) | Each **47 × 25 × 15 mm**; input 3–24 V, about 5 mA; load supply 5–36 V | Listing text. Two boards side by side in a 55 × 65 mm bay including bends. Read the board terminal labels; do not infer a generic low-side wiring topology. |
| P17 · 1 | [Gebildet four-way covered blade-fuse box](https://www.amazon.co.uk/dp/B076P4LBSG), **4 way** | **87 × 52 × 42 mm**; **6.3 mm tabs** | Amazon gallery drawing, not the 200 × 140 × 50 mm product-table packaging value. Four isolated circuits are required; continuity-check before wiring. Comes with cover, eight spades and mixed fuses. |
| P18 · 1 kit | [iLulala six holders / 66 standard blade fuses](https://www.amazon.co.uk/dp/B0DKX9R1FK) | Six each of **2, 3, 5, 7.5, 10, 15, 20, 25, 30, 35, 40 A** | Use **one 3 A, one 5 A and two 2 A fuses** in P17. This kit supplies the smaller ratings and spares; its bulky inline holders are **not installed**. Fuse-body dimensions are the standard ATO/ATC format; confirm seating in P17. |
| P19 · 1 | [Adafruit ADA1787 / 74AHCT125](https://www.amazon.co.uk/dp/B00XW2L39K) | **14-pin through-hole DIP**, 2.54 mm pitch | LED data buffer, soldered directly to P21 board. [TI datasheet](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf) defines pinout and electrical limits. This is an IC, not a finished driver board. |
| P20 · 1 pack of 15; use 1 | [RUNCCI-YUN four-channel I²C level converters](https://www.amazon.co.uk/dp/B082F6BSB5) | PCB **13 × 15 mm**, 2.54 mm header pitch | Listing text. Used for LCD SDA/SCL between 3.3 V and 5 V; not for WS2812 data. Solder to the small interface board. |
| P21 · 1 kit | [OFNMY 1628-piece electronics kit](https://www.amazon.co.uk/dp/B0FFTDD9JQ), **1628 PCS** | PCBs **20 × 80, 30 × 70, 40 × 60, 50 × 70 mm** | Gallery contents include 330 Ω, 4.7 kΩ and 10 kΩ resistors (20 each), 100 nF ceramics, and 470 µF / 16 V electrolytics. Use the 50 × 70 mm board for interfaces; the other boards are spares; detailed component use below. Breadboards are for the preliminary test only. |
| P22 · 1 pack of 25 | [WAGO 221-415, five-lever connectors](https://www.amazon.co.uk/dp/B0107SYYGU), **5-Lever** | **29.9 × 18.6 × 8.3 mm**; 0.14–4 mm² flexible copper | [Manufacturer dimensions](https://www.wago.com/global/installation-terminal-blocks-and-connectors/splicing-connector-with-levers/p/221-415). Allow up to six connectors for power distribution, retained by cable ties with levers accessible. Each connector joins all five ports; it is not five isolated poles. |
| P23 · 1 pack of 2; use 1 | [Anker USB-A to USB-C cable](https://www.amazon.co.uk/dp/B0D5XY3C2T), **0.3 m + 0.3 m, Black** | **300 mm including connectors**, USB 2 data up to 480 Mbit/s | Listing explicitly confirms data support. Pi USB-A to the ESP programming/serial USB-C port. Connector moulding dimensions not published; use the reserved connection spaces. |
| P24 · 1 if needed | [Official Raspberry Pi 27 W supply, White](https://www.amazon.co.uk/dp/B0CLY1671K) | **5.1 V / 5 A**, **1.2 m** captive 18 AWG USB-C cable | UK three-pin plug shown in listing. Adapter stays outside the box. Retain the complete USB-C connection; no 5 V buck substitution. |
| P25 · 1 | [Mean Well GST60A12-P1J](https://www.amazon.co.uk/dp/B013EU0AQQ) | **12 V / 5 A**, body **125 × 50 × 31.5 mm**, P1J **5.5 × 2.1 mm** centre-positive plug | Enclosed external adapter. Size from [GST60A manufacturer specification](https://www.mean-well.ru/uploads/files/datasheets/GST60A12-P1J.pdf). Requires P26. No mains wiring inside the wooden box. |
| P26 · 1 | [kenable UK to IEC C13 lead](https://www.amazon.co.uk/dp/B003OSQ626), **Black, 1 m** | **1 m**, three-core **0.75 mm²**, **5 A fused UK plug** | Listing confirms C13 female and earth conductor. Connects P25 to the wall; stays outside. |
| P27 · 1 pack of 2 pairs | [COOLM 18 AWG DC pigtails](https://www.amazon.co.uk/dp/B0CZT24S48), **2 Pair DC Mount Connector** | **5.5 × 2.1 mm**, 18 AWG; seller specifies 0–48 V / about 5 A | Use one female socket as a captive external pigtail, not through a thick wooden panel. Socket body/thread dimensions are not published. Route wires through the padded entry and clamp them inside. Male mates and spare pair remain spares. |

### All installed fittings and consumables

| ID / quantity | Exact Amazon.co.uk product | Size / contents | Use |
| --- | --- | --- | --- |
| F01 · 1 kit | [WiMas 940-piece nylon standoffs](https://www.amazon.co.uk/dp/B0CJFG1XDR), Black | M2/M2.5/M3/M4; gallery includes **10 mm body + 6 mm male stud**, M2.5×6 and M3×6 screws/nuts | Pi uses M2.5; other boards use the size that passes freely through their actual holes. Recess carrier nuts as described in the fastening sequence. |
| F02 · 1 kit | [AMLOOPH 535-piece wood screws](https://www.amazon.co.uk/dp/B0CPF54WYQ) | M2×6/10; M2.5×12/16/20; M3×8/10/12/16/20 mm | Pilot-drilled wooden joints, clips, console screws and backing. Choose length by the actual material stack; do not blindly use fitting-kit screws. |
| F03 · 1 kit | [Jeboler 500 nylon washers](https://www.amazon.co.uk/dp/B0D4952M2T) | M2, M2.5, M3, M4, M5, M6, M8, M10 | Protect PCB/plastic flanges and spread small-screw loads. Exact washer thickness is not listed; allow and measure it in the fastening stack. |
| F04 · 1 pack if needed | [Gorilla Wood Glue, 236 ml × 2](https://www.amazon.co.uk/dp/B07BVN1H3B) | Two **236 ml** bottles | Frame, rails, cleats, pads and lid backing; clamp and cure per bottle instructions. Do not glue the removable console. |
| F05 · 1 kit | [TUOFENG 18 AWG silicone wire](https://www.amazon.co.uk/dp/B07G744V5Z), 18awg silicone wire set | Six colours × **13.2 ft / about 4 m**; **2.3 mm OD**; 150×0.08 mm tinned-copper strands | Main low-voltage supply, fused 5 V lighting distribution and return. |
| F06 · 1 kit | [LEDLightsWorld 22 AWG silicone wire](https://www.amazon.co.uk/dp/B0GXYYP42B), **22 AWG / 0.3 mm²** | Eight colours × **5 m**, 60×0.08 mm strands; seller rates 3 A | Signals, buttons, sensor extensions, LCD and low-current lamp branches. Includes extra ties/shrink; these are not relied on for the quantities below. |
| F07 · 1 pack of 20 | [Switch Electronics fully insulated female spades](https://www.amazon.co.uk/dp/B00XWE7S2Y) | **6.3 × 0.8 mm**, red, **16–22 AWG** | Eight fuse-box connections, plus spares. Use these correctly sized crimps rather than assuming the included fuse-box spades fit 18 AWG. Lamp LED connections are soldered and insulated. |
| F08 · 1 kit | [ELECTRAPICK 560 heat-shrink pieces](https://www.amazon.co.uk/dp/B092VWZN4W), **560PCS** | **2:1**, **45 mm** lengths; ID 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 10, 13 mm | Insulate soldered joints and lamp terminals; choose size from the completed joint diameter. |
| F09 · 1 pack of 100 | [VIPMOON LED strip clips](https://www.amazon.co.uk/dp/B0B6QQLY6Q), **Type 2 – 10 mm** | For **10 mm strip**, 100 clips and screws | Use two or three per segment, positioned between pixels. Clip body dimensions are not published. Check PCB width and clip pressure; substitute F02 short screws where necessary. |
| F10 · 1 kit | [DYMHQ screw-mount cable-tie set](https://www.amazon.co.uk/dp/B0F5GYZQ97) | 200 saddles **15 × 10 × 7 mm**, 200 ties **100 mm**, 200 screws | Restrain harnesses and WAGO bodies. Prefer screws into 12 mm plywood backing, not adhesive-only fixing or the original 3 mm base. |
| F11 · 1 roll | [RS neoprene adhesive strip](https://www.amazon.co.uk/dp/B0086KQSMK), **10 mm wide / 3 mm thick** | **10 mm × 3 mm × 10 m** | Padded ball cover, low-voltage cable-entry lining, clamp pads and four base pads. Not a structural adhesive joint. |
| F12 · 1 pack of 2 | [YOOZIYA A2/304 toggle catches](https://www.amazon.co.uk/dp/B0GLZ2Y67C), **56 mm** | **56 mm nominal length**, two catches/eight screws | Two on the front. Width, projection and hole pattern not dimensioned. Fit to the actual lid seam, with plywood backing where needed; check closure before drilling. |
| F13 · 1 pack of 2; use 1 | [FdcZeyxior locking lid stays](https://www.amazon.co.uk/dp/B0HCCBXGN8) | **110 mm folded**, **40 mm foot width**; text says **190 mm** open, drawing **195 mm** | Mount one on the outside right-rear, clear of the course. This source discrepancy remains open: use the received part to set pivots and prove locking/closure. Do not treat the hinge as a certified carry handle or load-rated restraint. |
| F14 · 1 reel if needed | [0.8 mm lead-free rosin-core solder](https://www.amazon.co.uk/dp/B0BFW8TS6H), **20 g** | **Ø0.8 mm**, Sn99.3/Cu0.7 as listed | Interface board, LED joints, extensions and lamp connections. Use the alloy’s appropriate soldering process; the listing's generic melting-temperature text is inconsistent and is not a design value. |

The existing box hinges are reused. The manual gate, its guides, optical mounting pads, ventilation openings, console support frame, cable-entry backing, transport cover and retaining cleats are made from P03/P04. There is no unlisted metal trough, printed bracket, custom carrier PCB, barrel-to-USB power converter, paint or cosmetic ABS overlay in this revision. Small identification labels can be written directly on the plywood with the workshop marker.

### Components taken from the electronics kit

| Function | Fitted parts |
| --- | --- |
| WS2812 data | P19 AHCT125, one **330 Ω** series resistor close to the first pixel, one **10 kΩ** data-input pull-down, one **100 nF** ceramic directly across IC supply pins. Define unused inputs and enables; leave unused outputs disconnected. |
| Optical inputs | Eight **10 kΩ** pull-ups to **3.3 V**, one per receiver output. Receiver/emitter power is 5 V from the protected logic branch; only the open-collector signal reaches ESP inputs. |
| Manual buttons | Ten **4.7 kΩ** pull-ups to **3.3 V**; switches connect their inputs to common ground. |
| Lamp driver inputs | Two **10 kΩ** pull-downs at the input connectors, subject to confirming active-high behaviour of P16. Verify the lamps remain OFF through reset, USB connection and loss of control. |
| LED supply reservoir | Two **470 µF / 16 V** capacitors in parallel, **940 µF nominal**, across the 5 V lighting input with correct polarity. |
| Soldered boards | **50 × 70 mm** interface board under the console, including low-current common-return connections. Header links from the kit are signal-only, strain-relieved, and must not carry the main strip current. |

The schedule uses 11 of the supplied 10 kΩ resistors, ten 4.7 kΩ resistors and one 330 Ω resistor. It requires soldering a small interface circuit; it is not a fully plug-together kit. Route the LED power bus in 18 AWG wire and WAGO connectors, not through thin perfboard traces or the ESP breakout.

## Readable engineering checks and unresolved evidence

These are the actual results and limits of the placement calculation; no separate JSON file is needed to understand them.

| Check | Result | What it proves / does not prove |
| --- | --- | --- |
| Internal plan fit | Carrier 370 inside nominal 380 leaves **5 mm each side** | Arithmetic against the seller's approximate cavity. Does not establish manufacturing tolerances or hinge intrusion. |
| Console height | **6 + 83 + 6 = 95 mm** | Defines the built support stack. |
| Conditional lamp/lid clearance | **125 − (95 + 20) = 10 mm** | Only passes if actual lamp cap is ≤20 mm and no lid backing occupies that column. The cap dimension is not published. |
| Conditional lamp lower clearance | **95 − 65 − 12 = 18 mm** | Reserves an empty column for lamp and wire. Actual lamp body/grip remains unverified. |
| Small button clearance | 22 mm overall with 1.9 mm cap; 35 mm total allowance below top ends at z=60 | At least **9 mm** above the fuse reservation at z=51. Actual screw/wire bends still need inspection. |
| ESP/interface separation | ESP reservation ends z=50; interface begins z=60 | **10 mm planned vertical gap**. Populated ESP height is not published. |
| Carrier modules and frame | Revised three-dimensional bounding boxes do not intersect | Includes the lamp keepouts, U-frame walls and four upper fixing cleats. Does not model individual wires, every nut, lid motion or board deflection. |
| Ball/lane clearance | **30 − 27 = 3 mm total** | Nominal lateral clearance. Surface finish and an actual rolling trial remain necessary. |
| Touching-ball gap | **10.03 mm ideal point-beam gap at h=24** | Geometry only. Real beam width and event filtering can still hide a transition. |
| LED allocation | **12 + 12 + 12 + 12 + 6 + 6 = 60** | Exactly one 60-pixel metre by pixel count. Actual cut lengths/clip fit need checking. |

**Unresolved dimensions, explicitly visible:** P07 lamp body/cap/grip; P08 LCD complete thickness/bezel/hole centres; P13/P14 populated ESP height and cable mouldings; P09/F09 strip width and clip engagement; F12 catch pattern/projection; F13 stay pivot geometry and conflicting 190/195 mm length. Socket P27 body/grip is also unpublished, which is why it is used as a restrained pigtail rather than a panel-mounted fitting. These prevent a blanket “every dimension verified” claim. Packaging measurements, an AI illustration, and a nominal collision check are not substitutes.

Before making the final console holes, place the actual lamps, LCD and controller assemblies against the reserved envelopes. If a lamp exceeds either allowance, the current closed-height layout fails and must change. Do not silently shorten its wiring allowance or remove the lid clearance to make a drawing pass.

Then test one optical pair with touching balls at the chosen height, all eight stations through repeated cycles, the gate, the widened corner and the transport cover. Test power-up/reset OFF, input polarity, LED full-white supply voltage, cable temperature and Pi/converter temperature with the intended ventilation. Physical build, closure, transport and electrical load tests have **not** been performed by this documentation work.

The large lamps demonstrate output commands and light-load switching. They do not validate real solenoid current, flyback, pulse timing under a coil load or flipper mechanics. No application, bridge, firmware or runtime GPIO changes are included. Existing arming, watchdog, pulse-limit and fault behaviour must remain enforced.

## Earlier concept render and design history

![Earlier realistic concept illustration, retained for visual context rather than component-fit evidence.](./media/bench-course-realistic.png)

This earlier AI illustration is **superseded by revision 2's drawings and shopping list**. It uses generic board/fitting depictions, the former dark console and earlier internal arrangement. It is not a photograph of purchased parts or a construction reference. The current illustration and drawings show the natural plywood and revised layout; only the dimensioned drawings and written specifications control construction.

The [printed enclosure study](test-bench-enclosure-study.md) retains the earlier approved visual concept and CAD context. Subsequent stock-box studies explored KNAGGLIG, Creative Deco and Hammond enclosures before the 400 mm WooDeeDoo box was selected. Those older controls, custom PCB proposals and pin allocations do not carry into this revision automatically.

Engineering originals and reproducible drawings remain in the repository under `docs/design/test-bench/woodeedoo-course-v1/`. The current decisions, quantities, dimensions, cut list, mounting, electrical arrangement and unresolved checks are all written on this page; machine-readable records are supporting source files, not hidden requirements.
