# Test Bench: Interface board

The proposed perfboard, component schedule, harness and solder-side links.

**Provisional design.** Read the [remaining checks](checks.md) before ordering, cutting or wiring. No physical build or load test has validated this proposal.

## Single soldered interface board

All the small interface circuits fit on **one proposed 70 × 50 mm isolated-pad perfboard**: ten button pull-ups, two lamp-control pull-downs, LED data conditioning, LCD level shifting and LED reservoir capacitors. The Pi, ESP, converters, fuses and two ready-made lamp drivers remain on their existing mounts. The eight optical receivers connect directly to ESP inputs with internal pull-ups.

![Proposed 70 by 50 mm interface board with ten button resistors, LED buffer, LCD level converter and two reservoir capacitors.](./media/bench-interface-realistic-v1.png)

This AI-generated close-up illustrates component appearance and assembly. **Use the drawings and connection tables below for wiring.** The received P21 board must provide at least **24 × 16 usable isolated pads at 2.54 mm pitch**; its hole count, fixing pattern and component clearances have not been verified. The design is not yet a solder-ready template or tested circuit.

### Board layout and fitted parts

![Dimensioned component-side layout of the single interface perfboard.](./media/bench-interface-layout-v1.png)

Use design columns **A–X** and rows **1–16**; these are our labels, not the kit manufacturer's markings. A1 is nominally **5.79 mm from the left and 5.95 mm from the top** of the 70 × 50 outline. Translate the complete grid to the received board only after checking edge and fixing clearances. U1's notch points left; pin 1 is **C14**, not C11. R1–R10 lie flat; R11–R14 stand upright, with their long return leads insulated. U2 mounts on its supplied two six-pin headers, soldered at both ends.

| Fitted item | Quantity / lead positions | Existing Amazon purchase / fit requirement |
| --- | --- | --- |
| Isolated-pad perfboard | 1 × **70 × 50 mm**, nominal 1.6 mm thick | [P21 electronics kit](https://www.amazon.co.uk/dp/B0FFTDD9JQ). Verify grid, insulation between pads and actual thickness. No connected stripboard. |
| R1–R10, **4.7 kΩ** | 10; columns **B D F H J L N P R T**, each from row **2 to 6** | P21; 10.16 mm lead span. Allow body up to about 6.3 × 2.5 mm; measure supplied parts. |
| R11 / R12, **10 kΩ** | **K11–K12 / K14–K15** | P21; left/right lamp controls. Fit only for verified active-high P16 inputs. |
| R13, **10 kΩ** | **A12–A13** | P21; holds LED input low when ESP pin is undriven. |
| R14, **330 Ω** | **V12–V13** | P21; series LED-data resistor. Keep the last lead to the first pixel short. |
| U1, **74AHCT125 DIP14** | Pins **1–7 = C14–I14**; **14–8 = C11–I11** | [P19 PENGLIN SN74AHCT125N](https://www.amazon.co.uk/dp/B0GKNSSDD7) (one from the ten-pack); 2.54 mm lead pitch, 7.62 mm row spacing. Direct soldering; no socket allocated. |
| U2, **bidirectional I²C module** | HV row **N10–S10**; LV row **N14–S14** | [P20 RUNCCI-YUN](https://www.amazon.co.uk/dp/B082F6BSB5); PCB 15 × 13 mm in this orientation. **10.16 mm row spacing is a design assumption**: verify before soldering. |
| C1, **100 nF ceramic** | **C9–D9**; non-polarised | P21; short links to U1 VCC/GND, close to pin 14. |
| C2 / C3, **470 µF / 16 V each** | C2 **+V2, −X2**; C3 **+V7, −X7** | P21; **940 µF in parallel**. Each must fit **Ø10 × 16 mm maximum above the component face**. Measure actual size/lead pitch; stripe marks negative. |
| Board mounting and harness | Four **10 mm** nylon spacers; insulated leads, ties, heat-shrink and solder | Existing F01, F05/F06, F08, F10 and F14 rows. No additional purchased interface module or connector kit. Final panel attachment hardware remains unselected. |

All purchases are already on the priced shopping list; this design adds no item to its subtotal. That does **not** resolve the existing unselected MDF mounting hardware or prove the kit's delivered footprint. The P20 module photograph shows its pull-up network; confirm its resistor markings and low/high-side rails before use. Do not add a second set of I²C pull-ups by default.

### Wiring diagram and harness

![Electrical schematic showing button pull-ups, lamp pull-downs, LED buffer and capacitors, and LCD level shifting.](./media/bench-interface-wiring-v1.png)

The LED buffer and C2/C3 use **5V_LED**, from the protected lighting branch. U2's high side and LCD use **5V_LOGIC**, from the separate logic branch. **Never join these positive rails or feed either into ESP USB VBUS.** Their grounds are common; the board's 3V3 comes from the USB-powered ESP. U1 channel 1 is enabled by grounding pin 1; this is not an output safety interlock. Firmware still controls safe output operation.

| Connection | Board pad(s) | Other end |
| --- | --- | --- |
| ESP supply reference | **P15 = 3V3**, **Q15 = GND** | ESP 3.3 V and GND terminals; no external feed into ESP 5 V. |
| Logic supply | **M9 = 5V_LOGIC** | Fused logic branch; LCD supply leaves at P9. |
| Lighting supply / reservoir spur | **V7 (+), X7 (−)** capacitor-lead joints | Short paired feed from the lighting distribution near the first pixel. Use retained 18 AWG leads joined to the capacitor leads; do not force thick wire into a small pad hole or remove strands. |
| LED data | **A11** input; **X13** output and **X12** companion GND | ESP LED output → A11; X13/X12 → first pixel DIN/GND. X10/X11 are lighting-rail test pads, not a high-current output connector. |
| LCD low side | **N15 = SDA**, **O15 = SCL** | ESP I²C pins. Start at 100 kHz; confirm address/driver. |
| LCD high side | **N9 = SDA**, **O9 = SCL**, **P9 = 5V_LOGIC**, **Q9 = GND** | LCD's matching labelled pins. Follow its markings, not a guessed cable order. |
| Left lamp control | **K9** from ESP; **K10** to driver | P16's verified active-high control input; connect its control return to common GND as required by the received module. |
| Right lamp control | **K16** from ESP; **L16** to driver | Second P16 control input, with the same polarity/return checks. |
| Button return | **A8 = GND** | Daisy-chain only the ten switch-return contacts. The blue LED rings have their own 12 V supply/return wiring. |

| Input / resistor | ESP harness pad | Button contact pad | Panel function |
| --- | --- | --- | --- |
| BTN01 / R1 | B7 | B8 | Start |
| BTN02 / R2 | D7 | D8 | Fire |
| BTN03 / R3 | F7 | F8 | Lock |
| BTN04 / R4 | H7 | H8 | Ramp |
| BTN05 / R5 | J7 | J8 | Orbit |
| BTN06 / R6 | L7 | L8 | Target |
| BTN07 / R7 | N7 | N8 | Bump 1 manual trigger |
| BTN08 / R8 | P7 | P8 | Bump 2 manual trigger |
| BTN09 / R9 | R7 | R8 | Left flipper input |
| BTN10 / R10 | T7 | T8 | Right flipper input |

The sensor Bumper 1/2 events and manual Bump 1/2 buttons remain distinct inputs. Names here identify wires, **not ESP GPIO numbers**; the final pin assignment must check the actual breakout, boot pins and firmware manifest.

### Copper-side links

![Mirrored solder-side connection map with separate supply rails and insulated point-to-point links.](./media/bench-interface-solder-v1.png)

View the copper side by flipping the component drawing left-to-right: **X is now on the left, A on the right**. Join only the pads listed on each table row. Lines are connection guides, not etched tracks; use insulated wire over crossings and intermediate pads. A crossing does not make a junction. Do not solder the unused output/channel pads to a passing link.

<!-- interface-net-table:start -->
| Net | Join these pads with insulated links |
| --- | --- |
| 3V3 | B2, D2, F2, H2, J2, L2, N2, P2, R2, T2, P14, P15 |
| GND | D9, C14, G14, I14, E11, H11, K12, K15, A13, X2, X7, X11, X12, Q10, Q9, Q14, Q15, A8 |
| 5V_LED | V2, V7, X10, C9, C11, D11, F14, G11 |
| 5V_LOGIC | M9, P9, P10 |
| LED_IN | A11, A12, D14 |
| LED_BUFFER | E14, V12 |
| LED_DIN | V13, X13 |
| LAMP_L | K9, K10, K11 |
| LAMP_R | K14, K16, L16 |
| SDA_3V3 | N14, N15 |
| SCL_3V3 | O14, O15 |
| SDA_5V | N9, N10 |
| SCL_5V | O9, O10 |
| BTN01 | B6, B7, B8 |
| BTN02 | D6, D7, D8 |
| BTN03 | F6, F7, F8 |
| BTN04 | H6, H7, H8 |
| BTN05 | J6, J7, J8 |
| BTN06 | L6, L7, L8 |
| BTN07 | N6, N7, N8 |
| BTN08 | P6, P7, P8 |
| BTN09 | R6, R7, R8 |
| BTN10 | T6, T7, T8 |
| No connection | H14, I11, F11, R10, S10, R14, S14 |
<!-- interface-net-table:end -->

The U2 high row is **HV1, HV2, HV, GND, HV3, HV4** from N10 to S10; the low row is **LV1, LV2, LV, GND, LV3, LV4** from N14 to S14. Match the delivered module's labels before mapping it to the grid. Unused U1 outputs are pins **6, 8 and 11**; unused inputs **5, 9 and 12** go to GND and unused enables **4, 10 and 13** go to 5V_LED. The [TI pinout and operating specifications](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf) support this connection schedule. [Adafruit's I²C level-shifter explanation](https://www.adafruit.com/product/757) describes the circuit type, not a certification of the selected third-party module.

### Mounting, assembly and checks

The board mounts **components downward** under the removable panel, in the **80 × 50 mm bay at x=273, y=260**; the PCB itself occupies **x=278–348, y=260–310**. Put the capacitor/data-output edge nearest the right box wall. The nominal 10 mm spacers put the solder face at z=79; with 1.6 mm board thickness and 16 mm components, the lowest part is **z=61.4**. This remains within the z=60–89 reservation and above the converter's z≤45 allowance. Keep copper-side links below 3 mm high. Corner holes and spacer/nut clearance must be checked on the delivered board; do not drill from the illustration.

Retain the four spacers with through-fixings or adequately sized glued MDF pads after checking the actual kit's threads and panel clearances. F01 does not yet establish the complete panel attachment. Fit harness restraints to the MDF next to the board so no cable load reaches a solder pad. Keep the main LED supply/return in the external WAGO/18 AWG distribution. The capacitor spur carries charging/transient current, so it needs robust joints and restraint too; it is not a strip-power pass-through.

The right-edge route through the existing wall passage gives a target of **about 100 mm** from R14 to the first pixel, with a GND companion wire. This is a packaging target, not a guaranteed signalling limit. [Adafruit recommends the resistor at the first-pixel end and a reservoir at the strip input](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices). Prove this short connection at full effects/current; if the actual route must be substantially longer, revise the board position or put R14 at the pixel rather than claiming this layout is equivalent. Do not add the normal 150–200 mm service loop to this data lead: disconnect its labelled, existing strip connector (data/GND only; keep its +5 V contact unused and insulated) with both supplies off before fully lifting the panel. Label and disconnect other short power leads as needed.

1. **Dry-fit:** measure the board grid, corner holes, capacitor envelopes, U2 header spacing and the installed stack. Check all three positive rails remain separate. Do not solder against an unverified module footprint.
2. **Assemble:** fit the ten flat resistors, U1 and C1, then upright resistors, U2 and capacitors. Keep IC notch/pin 1 and capacitor polarity visible. Use short, insulated links; add labelled harness tails and strain relief last. The copper-side map and component drawing share the same pad names.
3. **Unpowered checks:** inspect every joint; check net continuity and no supply shorts with the IC/module behaviour in mind. Confirm each button shorts only its input to GND, not its 12 V light pins. Confirm R11/R12 suit the actual P16 active level before connecting the drivers.
4. **Initial power:** leave lamp loads and the strip disconnected, apply appropriately fused bench supplies and verify 3.3 V/5 V rails and LCD low-side levels. No ESP input should be pulled to 5 V. Verify button states, LCD communication and buffer output, then power down before connecting the loads.
5. **Full bench:** check lamps remain OFF at boot/reset, sensor transitions, LED effects/full-white voltage drop and temperatures. Make/break connections with power off; stop outputs before shutdown or host swapping. Power sequencing and disconnected-harness behaviour have not been validated. Board-mounted pull-downs cannot control a driver whose signal lead is unplugged.

The generated connection check covers all 14 resistors, three capacitors, U1's 14 pins and U2's 12 pins: no duplicate component-lead holes, conflicting pad assignments or joined positive rails are present in the model. It does not inspect soldering, prove a delivered footprint, choose protective fuse values or replace a physical test.
