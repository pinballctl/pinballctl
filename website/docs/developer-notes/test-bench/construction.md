# Test Bench: Materials & construction

## Materials and mounting

### MDF sheet material

Use **two A2 sheets of 6 mm MDF** and **one A2 sheet of 12 mm MDF**; see [P03/P04](shopping-list.md#box-and-mdf). Plan within **594 × 420 mm** and measure the delivered sheets.

- **6 mm sheet 1:** 370 × 370 carrier.
- **6 mm sheet 2:** 360 × 360 course; cut the 240 × 240 console top from its waste.
- **12 mm sheet:** console walls, rails, stops and backing. Keep offcuts for pads, cleats, shims and gate guides.

For a **3 mm saw kerf**, two 83 mm-high bands hold the console walls. Two 30 mm-high bands hold the rail pairs **317 + 263 mm** and **305 + 275 mm**; each pair uses 583 mm including the separating cut. Mark all parts using the actual kerf before cutting.

Keep standard MDF dry and seal its exposed faces and edges after fitting. Allow for coating thickness in the gate and ball lane.

Use wood glue for structural joints. Optional super-glue tacks hold alignment in small, separate spots; do not mix the adhesives or replace the wood glue's clamp/cure time. Trial on offcuts and leave removable parts unglued.

### Panel-off service view

Disconnect the **12 V input and host USB**, remove the four console screws and support the panel beside the box. The harness must not carry its weight. Allow **150–200 mm slack** in ordinary signal bundles; disconnect the short LED data lead and any short power leads before lifting.

The LCD, interface board, WAGOs, buttons and lamps lift with the panel. The Pi, power boards, ESP, fuses and MOSFET modules stay on the carrier.

![Carrier, console and sensor mounting sections.](./media/bench-course-mounting.png)

![Console underside showing the LCD, interface, connectors and control clearances.](./media/bench-course-underside.png)

### Cut list

All dimensions are **millimetres**. Adjust the carrier to the actual cavity. Leave hardware holes and small mounting pads until the received components can be fitted.

| Cut material | Quantity / finished nominal size | Purpose |
| --- | --- | --- |
| 6 mm sheet 1 (P03) | 1 × **370 × 370** | Carrier. Trim to delivered cavity; do not force it between walls. |
| 6 mm sheet 2 (P03) | 1 × **360 × 360**, remove front-right **260 × 260** | L-shaped course. Cut the 240 square console from that waste, allowing for kerf. |
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

<span id="fastening-sequence"></span>

### Mounting

- **Carrier:** preserve the full 6 mm thickness. Use standoff fixings that leave the underside flat. Retain it with four cleats screwed into the pine sidewalls, not the thin base.
- **Console:** glue the U-frame to the carrier and retain the top with four removable screws. Reference fixing centres are **(249,143), (347,207), (143,325), (347,330)**; size the pads and check wiring clearance before drilling. Keep the front open and provide ventilation.
- **Electronics:** match standoffs to board holes and check the complete installed height, including connectors. Keep the Pi cooler clear. The combined Pi/power-board bay is **110 × 70 × 52 mm**; verify the complete assembly fits.
- **Panel:** trace the LCD bezel and controls from the actual parts. Retain the LCD at blank PCB edges. Keep the [interface assembly](interface-board.md#mounting-assembly-and-checks) within **z=60–89** and provide cable restraint beside it.
- **Course:** dry-fit the rails, slope, gate and sensors; prove repeated ball runs before gluing. Keep fixing heads out of the lane.
- **Lid and cover:** back the thin lid at catch/stay fixings. Prove full movement and cover retention before transport. Carry supporting the base; remove the trough cover before use.

Follow the illustrated [Build steps](build-steps.md) for assembly order. Final mounting hardware, inlet fixings and cover retention are tracked in [Checks before use](checks.md).
