# Interface board render

Mode: built-in image generation, using the dimensioned component drawing and the selected P20 product photograph as references. The generated image illustrates appearance, not electrical connectivity; use the pad table and solder-side drawing to wire the board.

## Prompt

Use case: product-mockup, sketch-to-render.
Create a realistic engineering product photograph of the proposed PinballCTL interface perfboard. Reference image 1 is the authoritative component placement drawing, reference image 2 shows the actual blue P20 bidirectional level-shifter module. Preserve the 70 mm wide by 50 mm deep rectangular board proportions and the placement in image 1. Do not copy its legend or diagram page into the photo.

Show one green isolated-pad perfboard, a 24-column by 16-row usable 2.54 mm hole grid, viewed from a shallow front-right angle with a long-lens camera to avoid perspective distortion. It is raised on four white 10 mm nylon standoffs on a plain light neutral workshop surface. This is a separate close-up of the board, not the whole box. Use crisp realistic soldered component leads, believable small electronic parts, restrained lighting and clear detail. No breadboard, terminal blocks, Pi, ESP, power converter, sockets, extra chips or extra boards.

Exact components: one neat bank of TEN blue axial 4.7 kΩ resistors across the rear-left area, lying flat and parallel, 5.08 mm apart with 10.16 mm lead spans. Two black radial 470 µF 16 V capacitors stand at the right edge one behind the other, each realistically about 10 mm diameter and 14 mm tall, with the negative stripes visible. Front-left: one black 14-pin DIP 74AHCT125 IC, long axis left-to-right, notch LEFT; one small tan 100 nF ceramic just behind it. Front-centre: one blue 15 by 13 mm BSS138 four-channel module mounted on two short six-pin soldered header rows, label HV at its rear edge and LV at the front, matching reference 2. Exactly FOUR additional small resistors stand upright: R13 to the left of the DIP; R11 and R12 between the DIP and blue module; R14 to the right of the blue module. These make fourteen resistors total. Follow the reference layout rather than inventing traces.

Attach two modest bundles of ten thin labelled signal wires at the two rows of button signal pads between the flat resistor bank and chips, routed upward/back so they do not obscure the components. A short labelled data/ground pair exits the right edge. Other few signal leads exit forward. Show the thicker red/black capacitor power spur attached securely by the capacitors, without a high-current input/output terminal bus. Small removable paper harness labels are fine; no large branding or elaborate decoration. Keep wires restrained at the edge with a tie outside the board; do not pretend that bare solder joints provide strain relief.

Put only a clean title above: “70 × 50 mm interface board” and a small footer: “Proposed assembly • use the wiring drawing for connections”. The photo must remain a plausible handmade perfboard assembly, not a manufactured custom PCB. Preserve all four corner fixing clearances. No exaggerated giant connectors or impossible floating components.

## Review limits

The source drawing fixes positions and electrical records fix connectivity. Capacitor envelopes, usable hole grid, module header spacing and the delivered board's fixing holes remain to be checked. The picture is an AI-generated proposed assembly, not a photograph of tested hardware.

## Targeted correction

Edit this proposed interface-board photograph only to correct the four front wires attached to the blue I2C module. Keep every component, resistor count, board proportions, lighting, standoffs, capacitors, title, footer and other harnesses unchanged. The six front module pads, from LEFT to RIGHT, are labelled LV1, LV2, LV, GND, LV3, LV4. Attach exactly four wires at the FIRST FOUR of these pads, left to right: green wire label SDA at LV1, yellow wire label SCL at LV2, purple wire label 3V3 at LV, black wire label GND at GND. The rightmost two pads LV3 and LV4 must have no outgoing wires. Remove the existing four incorrect front wires and labels, including the LED label. Do not change the right-edge DATA/GND pair. This is a targeted wiring-label correction, not a redesign.

Final asset: [proposed board render](../../../assets/docs/media/bench-interface-realistic-v1.png). Reviewed for ten flat resistors, four upright resistors, one DIP14, one blue I²C module, one ceramic and two electrolytics. Harness routing/pad accuracy remains illustrative; the electrical drawings and tables control assembly.
