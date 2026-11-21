# Test Bench: Build steps

A simple order for building the box and MDF structure, then laying out the hardware before completing the electronics.

**Start with a dry assembly.** The dimensions below are the current nominal design, not a drilling template. Measure the delivered box and components first. The diagrams show finished part sizes; the isometric renders explain assembly. Neither certifies fit. All dimensions are **millimetres**.

This first stage uses the wooden box, **two A2 6 mm MDF sheets**, **one A2 12 mm MDF sheet**, wood screws, wood glue, optional Mitre Fast tack adhesive, catches and lid stay. Use the available power boards, fuse holder, buttons, lamps and one sensor pair as physical layout samples. The [complete cut list](construction.md#cut-list) remains the reference for quantities and the [remaining checks](checks.md) track unresolved details.

Tools assumed available: ruler, square, pencil, saw, drill, clamps and sanding block. Follow the MDF/tool supplier's dust-control and protective-equipment guidance when cutting or sanding.

## Before cutting: mark the sheets

1. Measure the box's clear internal width, depth and height, including hinges and the lid when shut. Mark **rear**, **front**, **left** and **right** on masking tape.
2. On **6 mm sheet 1**, reserve the **370 × 370 carrier**. Adjust it to the real cavity so it drops in and lifts out freely.
3. On **6 mm sheet 2**, reserve the **360 × 360 course blank**. Its front-right cutout supplies the **240 × 240 console top**. Save all other offcuts for the gate, cover, shims and backing.
4. On the **12 mm sheet**, reserve two **83 mm-high bands** for the console walls, then two **30 mm-high bands** for the rails. The [A2 cutting notes](construction.md#mdf-sheet-material) allow a provisional 3 mm saw kerf. Check your actual kerf and label every finished part before cutting.

Leave small mounting pads, hardware holes and the cable inlet until the actual fit is established. Keep the original box hinges in place.

## 1. Fit the carrier — part set A

![Part set A: carrier and cleat diagram, with an isometric assembly render.](./media/build-steps-carrier.png)

1. Cut the carrier slightly generously, then trim and sand until it sits flat without wedging against the box walls. The nominal 370 square leaves 5 mm around it in the approximate 380 square cavity.
2. Round off sharp edges and mark the carrier's front edge. Keep it removable for the next steps; do not glue it into the box.
3. Reserve four **30 × 12 × 12 cleats** from the 12 mm offcuts. Their eventual job is to retain the carrier from above, with screws into the **pine sidewalls**.

**Check before moving on:** the carrier lifts out, rests flat on the original base, and does not interfere with the lid. Leave final cleat positions and pilot holes until the course and hardware have been laid out. Do not rely on screws driven into the original thin base.

## 2. Dry-fit the console — part set B

![Part set B: console top and three wall diagrams, with an exploded isometric render.](./media/build-steps-console.png)

Cut **two 240 × 83 × 12 sides**, **one 216 × 83 × 12 rear wall**, and the **240 × 240 × 6 top**. Keep the front open: the rear wall fits between the two sides, making a **240 × 240 U-frame**.

1. Set the frame on the carrier at the [planned console position](../test-bench.md#dimensions-and-placement), x=125, y=125 from the box's inside rear-left corner. These coordinates refer to the box, not the carrier edge.
2. Clamp the walls square and lay the top on loosely. Carrier 6 + walls 83 + top 6 gives the nominal **95 mm panel-top height** above the original inner bottom.
3. Put the available boards beneath it and check that connectors, the Pi cooler and tools can be reached. Use paper templates for missing parts, including the LCD and interface board; their space must stay clear.
4. Mark component positions lightly. Keep the top solid for now: trace the actual LCD bezel and controls before making final openings. Reserve the full ten-button layout even when using fewer buttons initially.

**Check before gluing:** close the box lid with the top in place and use the component-height allowances in the [layout](../test-bench.md#dimensions-and-placement). Leave the right-wall cable passage, top fixing pads and screw centres provisional. Once the fit is established, glue and clamp the three frame joints and its attachment to the carrier. **Do not glue the removable top.**

## 3. Make the L-course and dry-fit its rails — part set C

![Part set C: course and rail diagrams, with an isometric render of the uninclined course assembly.](./media/build-steps-course.png)

1. Cut the **360 × 360 × 6 blank**, then remove the **front-right 260 × 260 area** to leave two **100 mm-wide legs**. Cut the console top from the removed piece; allow for kerf and keep the remaining waste.
2. Cut the four **12 mm-thick, 30 mm-high rails**: **317**, **305**, **275** and **263** long. Cut two **30 × 30 × 12 end stops**.
3. Lay everything loose on the carrier using the [dimensioned plan](../test-bench.md#layout-and-illustrations). The 317 rear outer rail and 305 left outer rail make the outside corner. The 275 rear inner and 263 left inner rails butt together at the inside corner.
4. Keep a **30 mm clear lane** between the rails. The stops close the trough's front end and the shooter's outer end. Do not leave a gap at the inner corner.

**Check before fixing:** run an actual approximately 27 mm ball through the lane and around the corner. If balls are not yet available, use a 27 mm template to check space, but leave the rails unglued until a rolling test is possible. The render is level to show the joinery; the next step sets the slope.

## 4. Set the slope and trial sensor pads — part set D

![Part set D: support and shim diagrams with an exploded isometric view of example stacks.](./media/build-steps-supports.png)

1. Make **six or more 30 × 30 support pads** from 12/6 mm offcuts. Stack, trim and shim them to support the course without rocking or bending it. The example layers in the render are not final stack heights.
2. Position the course at x=10, y=10. Its running surface targets approximately **z=41 at the shooter** and **z=22.5 at T1**, measured from the original inner bottom. This produces the planned roughly 2° fall towards the left and front. See the [slope formula](../test-bench.md#dimensions-and-placement) for intermediate points. Subtract the 6 mm course thickness and 6 mm carrier when determining support-stack height.
3. Trial one Treedix emitter/receiver pair on adjustable offcut pads outside the rails. Aim initially for an optical axis **24 mm above the local running surface**. Measure the actual lens centre; the pad footprint and screw holes are not yet specified.
4. Establish the beam-hole size on scrap rail material first. Keep the final rail apertures undrilled until alignment and ball detection have been proved. Follow the [sensor output check](wiring.md#direct-sensor-connections) before attaching signals to the ESP.

**Check before gluing:** repeat the ball run through the full L-course, including touching balls at the trough. Glue the proven supports and rails only after the mechanical and sensor checks pass; otherwise keep this as a dry layout. Clamp and let the wood glue cure according to its label.

## 5. Trial the gate and cover — part set E

![Part set E: gate, guide-cheek, cover and keeper diagrams with an exploded isometric assembly sketch.](./media/build-steps-gate.png)

1. Cut the **29 × 40 × 6 manual gate** and round its finger edge. Prepare four guide cheeks, approximately **12 × 40**, from offcuts.
2. Position the cheeks outside the clear lane to provide a **7 mm guide gap** for the 6 mm gate. Trial the complete guide arrangement before gluing. The gate needs **30 mm lift** to clear the ball; allow for the eventual finish and keep it free-sliding.
3. Cut a **110 × 54 × 6 trough cover** and **29 × 12 × 12 keeper**. Trial them over the trough using the [cover positions and cut list](construction.md#cut-list).

**Leave for later:** the design calls for 3 mm padding beneath the cover, and its retention still needs specifying. Make the wooden parts now, but do not treat the unfinished cover as secure ball retention for carrying the bench.

## 6. Fit the closure hardware after a clearance check — part set F

![Part set F: provisional catch and stay backing diagrams, with an exploded backing-at-the-seam render.](./media/build-steps-closure.png)

1. Close the lid over the dry assembly and check the tallest controls, cable routes and fittings. Nothing should force the lid upward.
2. Offer up the **two catches on the front** and **one locking stay outside the right-rear side**. Use the supplied hardware as the marking template. The render shows backing placement only; it does not define catch or stay hole positions.
3. Cut MDF backing from offcuts where the thin lid needs load spreading. **About 50 × 30** is a starting envelope, not a confirmed cut size: adjust it to the real fitting and keep it clear of the internal components.
4. Trial the stay's pivot positions through the full opening/closing movement before drilling. Confirm it locks and folds without binding. Select screw lengths for the actual wood/backing stack; supplied screws are not automatically suitable.
5. After all positions are settled, fit the carrier cleats and specify the removable console-top fixings. Preserve the carrier's full thickness and do not leave screw tips projecting beneath it.

**Finish this stage with:** a removable carrier, square console frame with lift-off top, dry or proven course assembly, trial gate, and checked lid movement. Keep electronics unpowered during layout. Final board standoffs, LCD retainers, cable inlet, wiring, finish and cover retention can follow as their parts and fixing details become available.

## Glue and finishing notes

Use wood glue for the MDF joints and retain its clamping/cure time. Optional Mitre Fast goes only in small separate tack spots to hold alignment; do not mix it into the wood glue or use it as the structural bond. Trial both on offcuts first. Keep glue away from removable panels, sensors and electronics.

Seal and finish standard MDF once the mechanical fit is proved, allowing for coating thickness at the gate and other close fits. Finish materials are outside this first-stage list. For the full assembly and remaining electrical work, continue with [Materials & construction](construction.md), [Lighting & wiring](wiring.md) and [Checks & next steps](checks.md).
