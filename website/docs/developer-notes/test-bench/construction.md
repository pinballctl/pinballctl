# Test Bench: Materials & construction

## Materials and mounting

### MDF sheet material

The build uses **two A2 sheets of 6 mm MDF** and **one A2 sheet of 12 mm MDF**, listed as [P03/P04](shopping-list.md#box-and-mdf). The cut layout fits within **594 × 420 mm**.

- **6 mm sheet 1:** 370 × 370 carrier.
- **6 mm sheet 2:** 360 × 360 course; its waste supplies the 240 × 240 console top.
- **12 mm sheet:** console walls, rails, stops and backing. Offcuts supply pads, cleats, shims and gate guides.

For a **3 mm saw kerf**, two 83 mm-high bands hold the console walls. Two 30 mm-high bands hold the rail pairs **317 + 263 mm** and **305 + 275 mm**; each pair uses 583 mm including the separating cut.

Sealed faces and edges protect the MDF from moisture. Gate and ball-lane clearances include the finish thickness.

Wood glue forms the structural joints. Optional super-glue tacks hold alignment in separate spots while the wood glue cures. Removable parts remain unglued.

### Panel-off service view

The console lifts out after disconnecting the **12 V input and host USB** and removing four screws. Signal bundles have **150–200 mm slack**; short LED data and power leads disconnect before lifting. The panel rests beside the box, with its weight supported independently of the harness.

The LCD, interface board, WAGOs, buttons and lamps lift with the panel. The Pi, power boards, ESP, fuses and MOSFET modules stay on the carrier.

![Carrier, console and sensor mounting sections.](./media/bench-course-mounting.png)

![Console underside showing the LCD, interface, connectors and control clearances.](./media/bench-course-underside.png)

### Cut list

All dimensions are nominal and in **millimetres**. The carrier fits the box cavity; component holes and mounting pads follow the fitted parts.

| Cut material | Quantity / finished nominal size | Purpose |
| --- | --- | --- |
| 6 mm sheet 1 (P03) | 1 × **370 × 370** | Removable carrier, trimmed to fit the cavity freely. |
| 6 mm sheet 2 (P03) | 1 × **360 × 360**, front-right **260 × 260** removed | L-shaped course; the cutout supplies the 240 square console top. |
| MDF waste | LCD retaining pads | Support at blank PCB edges. |
| 6 mm waste | 1 × **240 × 240** | Removable console. The LCD window follows its bezel, with the PCB and connections behind the panel. |
| 12 mm sheet | 2 × **240 × 83**; 1 × **216 × 83** | Glued U-frame with an open front. The right wall's **50 × 45** cable passage is shown in the [layout](../test-bench.md#layout-and-illustrations). |
| 12 mm sheet | 1 × **317 × 30**; 1 × **305 × 30**; 1 × **275 × 30**; 1 × **263 × 30** | Rear outer, left outer and two inner rails. Inside lane faces at x=45/75 and y=45/75. Rear inner rail starts (75,75); left inner rail starts (75,87) and butts against it. There is no inner-corner gap. |
| 12 mm sheet | 2 × **30 × 30** | Trough front stop and shooter outer end stop. |
| 6 mm waste | 1 × **29 × 40** | Manual gate, 6 thick, with a rounded finger edge. A **7 mm** guide gap allows free movement; 30 mm lift clears the ball. |
| 6/12 mm waste | 4 guide cheeks about **12 × 40**, plus spacing offcuts | Guides outside the clear lane, forming the 7 mm channel around the finished gate. |
| 12 mm waste | Console fixing pads | Support for the four removable top screws, clear of controls and wiring. |
| 12 mm waste | 4 × **30 × 12** | Carrier retaining cleats, 12 thick, screwed to pine sidewalls above carrier edges and clear of the trough and cable entry. |
| 12 + 6 mm waste | 16 sensor pads | One per head, with shim height set by the lens position. |
| 12/6 mm waste | Six or more **30 × 30** pads, stacked/trimmed | Support the course floor at its measured slope. All loads go into the carrier. |
| 6 mm waste | 1 × **110 × 54** | Removable trough transport cover spanning the rail tops at y≈250–360, with 3 mm foam underneath over the balls. |
| 12 mm waste | 1 × **29 × 12** keeper, 12 thick | Glued under the rear end of the transport cover across the lane. Its underside is lower than a ball's diameter, so balls cannot escape backward. The front stop retains the other end. |
| 6/12 mm waste | Cable-clamp bars about **40 × 12** and backing about **50 × 30** | Internal harness restraint. |
| 12 mm waste | Backing about **50 × 30** at catch/stay attachments | Load spreading on the 3 mm lid, clear of the lamp caps when closed. |

<span id="fastening-sequence"></span>

### Mounting

- **Carrier:** full 6 mm thickness, with a flat underside. Four cleats attach to the pine sidewalls rather than the thin base.
- **Console:** the U-frame is glued to the carrier; four screws retain the removable top. Reference centres are **(249,143), (347,207), (143,325), (347,330)**. The open front provides access and ventilation.
- **Electronics:** board standoffs leave the Pi cooler clear. The combined Pi/power-board bay allows **110 × 70 × 52 mm**, including connectors and fixings.
- **Panel:** LCD retainers contact blank PCB edges. The [interface assembly](interface-board.md#mounting-assembly-and-checks) occupies **z=60–89**, with cable restraint beside it.
- **Course:** rails and supports are glued to the carrier, with fixing heads outside the running lane.
- **Lid and cover:** backing spreads catch/stay loads on the thin lid. The padded trough cover is removable for operation; the base supports the bench during carrying.

The illustrated [Build steps](build-steps.md) show the assembly order.
