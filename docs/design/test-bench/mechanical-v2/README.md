# Test bench mechanical prototype v2

Editable **solid CAD**, not a manufacturing release. Units: millimetres. The selected enclosure approach is a separately printed base and lid with integral snap-assembled hinges and front cantilever clips. No hinge rods or enclosure screws are used.

## Current visual baseline

The project owner approved `docs/media/test-bench-concepts-v8.png` on 10 November 2026. Use this image as the reference/edit base for subsequent mockups, preserving its enclosure style, charcoal/teal/orange palette and retail control appearance unless explicitly requested otherwise. It is the current banner on the Test Bench documentation page. This is visual approval, not manufacturing approval; the CAD and measured components govern dimensions.

## Files and reproduction

- `design.py`: CadQuery 2.8.0 source; exports valid single-solid STEP/STL base, lid and four mating coupon parts, plus a closed STEP assembly.
- `validation.json`: geometric sweep results and preliminary elastic beam estimates.
- `components.json`: supplier-linked component dimensions, prices and explicitly provisional allowances.
- `component_plan.py`: scaled component layout and recessed breadboard section.
- `render.py`: actual CAD views, including exploded hinge and assembled latch detail.

Use a separate Python 3.11 environment with `cadquery==2.8.0` and `Pillow`. These are design-tool dependencies, not application dependencies. Run `design.py`, then `render.py` and `component_plan.py`. The two image scripts currently use the Arial font available on macOS for labels; substitute an available font path on another platform. Images are written to `docs/media/`.

## Hinge

Two hinge units start at x=48 and x=278. The common axis is y=286, z=94: 6mm behind the 280mm-deep shell and 4mm above its rear top. Fixed cheeks have Ø6.6mm bores. Each moving unit has two outward Ø6mm trunnions with 0.5mm nose chamfers. The 0.3mm radial running clearance is a **coupon starting value**, not a printer-independent tolerance.

Each 2mm-thick arm has approximately 26mm free length and 4mm width. Squeeze the two arms towards one another to align the pins between the cheeks, then release into the bores. Nominal pin engagement is 2.2mm per side; estimated assembly displacement is 2.6mm per arm including clearance. The rounded root transition and central spine are modelled. Access to both arms remains required when installing/removing the lid.

A central moving tongue meets an integral fixed travel stop between 78° and 79° in the sampled rigid geometry. Normal service opening is 75°. The stop is **not a support stay**: support the lid during use; the final stay and loaded-lid proof test remain pending. The fixed hinge adds rear projection to y=295 and reaches z=113; these are outside the 360×280×90 shell envelope. The actual footprint must include protruding controls and hinge features.

## Front clips

Two bottom-rooted cantilever clips at x=65 and x=280 are built into the base front. Each is 14mm wide, 1.8mm thick with 27mm nominal free length and a 0.6mm internal root fillet. A ramped hook projects 1.4mm outward into a 14.8×4mm receiver window in the lid skirt. The hook is unloaded when closed. Press both tabs inward, approximately 1.6mm design travel, while lifting the lid front. Clip release ergonomics need a physical sample; do not pry against the top skin.

The latch coupons reproduce the actual hook/window dimensions. Coupon parts are individually translated to positive coordinates for printing; their shared original assembly coordinates are in the source. Use the source/full assembly to understand engagement, not the coupon origin positions.

## Validation performed

- Each exported individual solid passes the CAD kernel validity check and has exactly one solid.
- Closed base/lid intersection is zero.
- Opening samples every 0.5° from 0° through 75° have zero rigid overlap **with the flexible front clip bodies excluded**. This is a clearance check, not a deformation simulation.
- Without releasing the clips, initial opening has intentional hook/catch interference. Beyond 78°, the travel stop creates intentional interference.
- The simple cantilever screening estimate `strain = 1.5 × thickness × displacement / length²` gives approximately 1.15% for hinge installation and 0.59% for clip release. Fillets, large-deflection effects, local stress, actual material properties, moisture and fatigue are not resolved by that calculation. No force or cycle-life rating is claimed.

## Prototype sequence

1. Ask the print service to review the selected PA12 process, orientation, snap strain and fit tolerances. Print the four small coupon pieces first. FDM/PLA results do not validate an MJF/SLS nylon design.
2. Measure pin/bore sizes and engagement; test assembly, free rotation, release and repeated clip operation. Record forces and damage/whitening. Adjust clearance/thickness in the source; do not force brittle samples.
3. Check the actual selected switches and breadboard. The pocket uses the vendor's 83×56mm footprint but a **9.7mm assumed height**. Change floor depth/shims after measuring the sample.
4. Complete removable switch carriers, LCD mounting/window, cable access, power protection, expansion pinout, wiring service loop, antenna clearance, electronics retention, feet and lid stay.
5. Only then print a complete enclosure prototype and perform loaded opening, retention and thermal tests. These full-size STL files are for mechanical review/prototype planning, not an order-ready approved product.

## Control and breadboard changes

Three 24mm orange Sanwa bumpers replace the uniform small switches in the component proposal. Five lane/shooter inputs use actual exposed D2F-01L levers with printed carriers. Skill and standup use real 16mm-mount rectangular switches. Seven small round controls remain for four front inputs, two flippers and drain. The custom switch carriers and RGB diffusers have **not** been released as manufacturing parts.

The half-size breadboard pocket is integrated into the lid. Expansion and 3.3V/GND, 5V/GND connector windows are provisional; a prototype power switch is reserved in the layout but not yet detailed as lid cutouts or electrical circuits. The main strip, LCD and other peripherals remain component-placement allowances. Neither expansion pins nor power outputs are implemented in firmware/PCB by this change.

## Right-side cable entry

USB and12V adapter input are on the fixed RIGHT side, centres y230/z40 and y190/z40 respectively. The right flipper remains y35/z34. USB retains a provisional 24mm CAD opening, but the former Micro-B candidate is rejected: the photographed Freenove board uses USB-C. Select and measure its replacement before releasing this opening. DC uses the8mm hole from the Switchcraft721AU drawing. No top-panel 12V connection is included.

## Internal placement study

`internal-layout.json` records proposed carrier/module/keepout envelopes in closed-case coordinates. `internal_plan.py` draws the dimensioned plan and checks module rectangles against the proposed PCB outline. It does not alter the solid enclosure CAD or establish populated opening clearance. The 3.3V module, carrier circuitry, module sockets, harness connectors, retention supports and lid stay remain unselected/undesigned. The generated open/closed illustration is a visual aid based on exterior revision 8; JSON/plan dimensions govern this placement study.

## Existing board identification

See `esp-board-identification.json` for the project-photo match to Freenove FNK0085, manufacturer header order and unresolved memory/revision/mechanical dimensions. The current saved GPIO37 and GPIO48 assignments need review before carrier routing. USB-C replaces the former Micro-B candidate; existing CAD port opening is a placeholder only. No runtime mapping changed.
