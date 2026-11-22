# Test Bench: Interface board

## Single soldered interface board

A **70 × 50 mm isolated-pad perfboard** carries the button pull-ups, lamp-control pull-downs, LED buffer, LCD level shifter and reservoir capacitors. Sensors connect separately to the ESP under the [sensor wiring requirements](wiring.md#direct-sensor-connections).

![Interface-board assembly illustration.](./media/bench-interface-realistic-v1.png)

The drawings and tables show wiring on a **24 × 16 isolated-pad grid at 2.54 mm pitch**. The perfboard must accommodate this grid and the corner fixings.

### Board layout and fitted parts

![Dimensioned component-side layout.](./media/bench-interface-layout-v1.png)

Grid labels are **A–X** and **1–16**. A1 is nominally **5.79 mm from the left and 5.95 mm from the top**; fixing holes sit outside the usable pad grid.

U1's notch points left; **pin 1 is C14**. R1–R10 lie flat; R11–R14 stand upright with insulated return leads. U2 uses two six-pin headers soldered at both ends. I²C pull-ups must match the module's existing pull-ups and the 3.3 V/5 V sides.

| Fitted item | Quantity / lead positions | Parts and mounting |
| --- | --- | --- |
| Isolated-pad perfboard | 1 × **70 × 50 mm**, nominal 1.6 mm thick | [P21 kit](shopping-list.md#controllers-and-connections). Each pad is electrically isolated; connected stripboard is unsuitable. |
| R1–R10, **4.7 kΩ** | 10; columns **B D F H J L N P R T**, each from row **2 to 6** | P21; 10.16 mm lead span, with a body allowance of 6.3 × 2.5 mm. |
| R11 / R12, **10 kΩ** | **K11–K12 / K14–K15** | P21; left/right lamp controls. Pull-downs require verified active-high P16 inputs. |
| R13, **10 kΩ** | **A12–A13** | P21; holds LED input low when ESP pin is undriven. |
| R14, **330 Ω** | **V12–V13** | P21; series LED-data resistor close to the first pixel. |
| U1, **74AHCT125 DIP14** | Pins **1–7 = C14–I14**; **14–8 = C11–I11** | [P19 buffer](shopping-list.md#power-and-interfaces); 2.54 mm lead pitch, 7.62 mm row spacing. Soldered directly to the board. |
| U2, **bidirectional I²C module** | HV row **N10–S10**; LV row **N14–S14** | [P20 level shifter](shopping-list.md#power-and-interfaces); PCB 15 × 13 mm in this orientation. This layout requires **10.16 mm header-row spacing**; the module must match the footprint. |
| C1, **100 nF ceramic** | **C9–D9**; non-polarised | P21; short links to U1 VCC/GND, close to pin 14. |
| C2 / C3, **470 µF / 16 V each** | C2 **+V2, −X2**; C3 **+V7, −X7** | P21; **940 µF in parallel**. Maximum envelope per capacitor: **Ø10 × 16 mm above the component face**. The stripe marks negative. |
| Board mounting and harness | Four **10 mm** nylon spacers; insulated leads, ties, heat-shrink and solder | F01, F05/F06, F08, F10 and F14. |

### Wiring diagram and harness

![Electrical schematic for buttons, lamp controls, LED data and LCD level shifting.](./media/bench-interface-wiring-v1.png)

**5V_LED** supplies the buffer and reservoir capacitors; **5V_LOGIC** supplies the LCD and level-shifter high side. These fused feeds and **ESP USB VBUS** remain separate. Ground is common; **3V3** comes from the USB-powered ESP.

U1 channel 1 is enabled by grounding pin 1. This is not a safety interlock; output protection remains in the ESP firmware.

| Connection | Board pad(s) | Other end |
| --- | --- | --- |
| ESP supply reference | **P15 = 3V3**, **Q15 = GND** | ESP 3.3 V and GND terminals; no external feed into ESP 5 V. |
| Logic supply | **M9 = 5V_LOGIC** | Fused logic branch; LCD supply leaves at P9. |
| Lighting supply / reservoir spur | **V7 (+), X7 (−)** capacitor-lead joints | Short, retained 18 AWG feed from the lighting distribution near the first pixel, joined directly to the capacitor leads. Full conductor cross-section is maintained. |
| LED data | **A11** input; **X13** output and **X12** companion GND | ESP LED output → A11; X13/X12 → first pixel DIN/GND. X10/X11 are lighting-rail test pads, not a high-current output connector. |
| LCD low side | **N15 = SDA**, **O15 = SCL** | ESP I²C pins at an initial 100 kHz; address and driver match the display. |
| LCD high side | **N9 = SDA**, **O9 = SCL**, **P9 = 5V_LOGIC**, **Q9 = GND** | LCD's matching labelled pins. |
| Left lamp control | **K9** from ESP; **K10** to driver | P16's verified active-high control input, with its control return connected to common GND as required by the module. |
| Right lamp control | **K16** from ESP; **L16** to driver | Second P16 control input, with the same active-high and ground-return requirements. |
| Button return | **A8 = GND** | Daisy-chain of the ten switch-return contacts. The blue LED rings have separate 12 V supply/return wiring. |

### Input connections

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

Bumper sensors and manual Bump buttons are separate inputs. Pad labels identify harness connections, not GPIO numbers. GPIO assignments must match the firmware manifest and the board's boot/memory restrictions.

### Copper-side links

![Mirrored solder-side connection map.](./media/bench-interface-solder-v1.png)

The copper-side drawing mirrors the component side: **X is on the left, A on the right**. Insulated links join only the listed pads; crossings and intermediate pads are not junctions.

<!-- interface-net-table:start -->
| Net | Connected pads |
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

U2's N10–S10 row is **HV1, HV2, HV, GND, HV3, HV4**; N14–S14 is **LV1, LV2, LV, GND, LV3, LV4**. The fitted module must match these labels and spacing.

Unused U1 outputs **6, 8, 11** remain disconnected; inputs **5, 9, 12** go to GND; enables **4, 10, 13** go to 5V_LED. See the [buffer datasheet](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf).

<span id="mounting-assembly-and-checks"></span>

### Mounting

Components face downward in the **80 × 50 mm bay at x=273, y=260**. The board occupies **x=278–348, y=260–310**. With 10 mm spacers, a 1.6 mm board and 16 mm components, the lowest part is **z=61.4**, inside the **z=60–89** allowance. Copper-side links stay below 3 mm high and clear of corner fixings.

Cable restraints sit beside the board. Main LED current stays in the external WAGO/18 AWG distribution; the capacitor spur has restrained joints. The data resistor sits close to the first pixel, with a target lead length of **about 100 mm** and a ground companion ([LED wiring guidance](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices)).

The short LED data lead disconnects before the panel lifts. Its strip connector carries only data/GND; the +5 V contact remains unused and insulated.

The control circuits require isolated supply rails, button contacts that connect inputs only to ground, and ESP inputs limited to **0–3.3 V**. Lamp pull-downs require verified active-high driver inputs and an OFF state during boot/reset; they do not protect a driver with an unplugged signal lead. Connection changes require power to be disconnected.
