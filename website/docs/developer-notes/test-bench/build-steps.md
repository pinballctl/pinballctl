# Test Bench: Build steps

All dimensions are **millimetres**. Measure the actual box and components before cutting. Use the [cut list](construction.md#cut-list) and [layout plan](../test-bench.md#layout-and-illustrations).

## Before cutting: mark the sheets

1. Measure the clear cavity, hinges and closed-lid height. Mark the box's front and rear.
2. Reserve the **370 × 370 carrier** on the first 6 mm sheet.
3. Reserve the **360 × 360 course** on the second 6 mm sheet; its cutout supplies the console top.
4. Mark the console walls and rails on the 12 mm sheet, allowing for saw kerf. Keep offcuts for pads, backing and guides.

Use a square, saw, drill, clamps and sanding block, with suitable MDF dust control. Leave component holes and the inlet cutout until the parts can be fitted.

## 1. Fit the carrier — part set A

![Carrier and cleat dimensions with an assembly view.](./media/build-steps-carrier.png)

1. Cut, trim and sand the carrier until it sits flat and lifts out freely.
2. Prepare four **30 × 12 × 12 cleats**. Fit them later, clear of the course and wiring, with screws into the pine sidewalls.
3. Check lid clearance. Keep the carrier removable; do not glue it to the box or screw into the thin base.

## 2. Dry-fit the console — part set B

![Console top and wall dimensions with an exploded assembly view.](./media/build-steps-console.png)

1. Cut two **240 × 83 × 12 sides**, one **216 × 83 × 12 rear wall** and the **240 × 240 × 6 top**.
2. Place the U-frame at **x=125, y=125**, measured from the box's inside rear-left corner. The rear wall fits between the sides; the front stays open.
3. Clamp square and lay the top on loosely. Its surface sits at **z=95** above the original inner bottom.
4. Check boards, connectors, cooler and closed-lid clearance. Reserve all ten buttons and the display before marking holes.
5. Glue the frame joints and its attachment to the carrier once the fit is checked. **Leave the top unglued.**

## 3. Make the L-course and dry-fit its rails — part set C

![L-course and rail dimensions with an assembly view.](./media/build-steps-course.png)

1. Cut the **360 × 360 × 6 course blank** and remove its front-right **260 × 260** area. Cut the console top from the waste.
2. Cut four **12 mm-thick, 30 mm-high rails**: **317, 305, 275 and 263 mm** long, plus two **30 × 30 × 12 stops**.
3. Lay them out with a **30 mm clear lane**. Butt the inner rails together without a corner gap; fit stops at the trough front and shooter end.
4. Roll an actual 27 mm ball through the lane and corner before fixing the rails. Set the slope in the next step.

## 4. Set the slope and trial sensor pads — part set D

![Support-pad and shim dimensions with example stacks.](./media/build-steps-supports.png)

1. Make at least six **30 × 30 support pads** from 6/12 mm offcuts. Stack and shim them without bending the course.
2. Place the course at **x=10, y=10**. Target running-surface heights are **z≈41 at the shooter** and **z≈22.5 at T1**. Subtract the 6 mm course and 6 mm carrier when sizing the support stacks.
3. Trial one sensor pair outside the rails with its beam **24 mm above the local running surface**. Adjust for the actual lens position.
4. Prove alignment and detection through scrap rail apertures before drilling the final holes. Follow the [sensor signal check](wiring.md#direct-sensor-connections) before connecting to the ESP.
5. Test the full ball run, including touching balls in the trough. Glue and clamp the proven supports and rails, then allow the glue to cure.

## 5. Trial the gate and cover — part set E

![Gate, guides, transport cover and keeper dimensions.](./media/build-steps-gate.png)

1. Cut the **29 × 40 × 6 gate**, round its finger edge and prepare four guide cheeks, approximately **12 × 40**.
2. Set a **7 mm guide gap** outside the clear lane. The gate must slide freely and lift **30 mm** to release the ball; allow for finish thickness.
3. Cut the **110 × 54 × 6 cover** and **29 × 12 × 12 keeper**. Fit the keeper beneath the rear end and add **3 mm padding** over the balls.
4. Specify and test cover retention before carrying the bench with balls inside.

## 6. Fit the closure hardware after a clearance check — part set F

![Catch and stay backing with an exploded mounting view.](./media/build-steps-closure.png)

1. Close the lid over the assembled structure and confirm it clears controls and cables.
2. Fit two catches at the front and one locking stay outside the right-rear side. Mark holes from the actual fittings.
3. Add load-spreading backing at the thin lid; **50 × 30 mm** is a starting size to adjust to each fitting.
4. Trial the stay through its full travel. Check locking, screw engagement and clearance before drilling.
5. Fit the carrier cleats and removable console-top fixings. Keep screw tips inside the material stack.

## Glue and finishing notes

Use wood glue for structural joints and optional separate super-glue tacks for alignment. Keep removable panels unglued. Seal and finish the MDF after fit checks, allowing for coating thickness in close clearances.

Keep electronics unpowered during mechanical assembly. Continue with [wiring](wiring.md) and [Checks before use](checks.md).
