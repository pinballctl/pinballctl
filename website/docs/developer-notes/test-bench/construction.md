# Test Bench: Materials & construction

MDF, cut lists, mounting, service access and the fastening sequence.

**Provisional design.** Read the [remaining checks](checks.md) before ordering, cutting or wiring. No physical build or load test has validated this proposal.

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

The LCD, interface, six WAGOs, button backs and lamp bodies move with the panel. The Pi/Yahboom stack, ESP, four-way fuse block, three inline holders, lighting converter and two lamp drivers stay on the carrier. Support the disconnected panel underside-up on offcuts beside the box. This temporary service space is outside the closed transport footprint. The dimensioned underside view below locates the interface near the right-side LED feed; its [close-up render and wiring](interface-board.md#single-soldered-interface-board) show the board itself.

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
| 12 mm sheet | 2 × **240 × 83**; 1 × **216 × 83** | Console side walls and rear wall, forming a U. The right wall has the proposed 50 × 45 cable passage in the [layout](../test-bench.md#dimensions-and-placement). Confirm it against the actual connections before cutting. Glue the frame; keep the front open. |
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
