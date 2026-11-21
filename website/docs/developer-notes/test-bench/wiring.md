# Test Bench: Lighting & wiring

## Lighting and electrical connections

### Direct sensor connections

Eight break-beam pairs use **eight ESP inputs**. See [P05 in the shopping list](shopping-list.md#sensors-controls-and-lighting).

| Connection | Wiring |
| --- | --- |
| Emitter | Red → protected **5 V logic supply**; black → common ground. |
| Receiver power | Red → the same **5 V logic supply**; black → common ground. |
| Receiver signal | White → ESP input with a **3.3 V pull-up**, **only after checking compatibility**. |

Confirm the received wire colours and output voltage with the ESP disconnected. The signal must stay within **0–3.3 V**, including startup; otherwise fit a suitable level interface. Never pull an ESP input up to 5 V.

Test touching-ball detection before setting debounce or drilling the final beam holes. Sensor power comes from the supply rail, not a GPIO.

### Flipper inputs and coil-output lamps

Each flipper has a blue input button and a separate yellow output lamp.

| Path | Connection |
| --- | --- |
| Button | Normally-open contacts → ESP input and ground through the [interface board](interface-board.md#input-connections). |
| Yellow lamp | ESP output → MOSFET control input; protected **12 V** → the module's lamp-load circuit. Follow the module's terminal labels. |
| Blue button ring | Separate, steady **12 V** backlight supply. Keep its terminals separate from the switch contacts. |

Use one MOSFET per yellow lamp. Confirm input polarity and that the lamps stay off during boot/reset. Retain ESP arming, watchdog and pulse limits. The lamps show output activity; they do not test real coil current, flyback or pulse timing.

### LED strip and signal interfaces

| Strip section | Pixels | Nominal length |
| --- | ---: | ---: |
| Continuous perimeter | 89 | 1.483 m |
| Console status row | 6 | 100 mm |
| Console key-light row | 6 | 100 mm |
| Total | **101** | **1.683 m** |

The 2 m roll leaves 19 spare pixels. The power budget allows **102 pixels** for final fitting.

Fit the perimeter inside the walls at **z≈110**, with its feed gap on the right near **y=285**. Dry-fit before cutting; keep pixels and factory joins off bends. Route retained leads down the right wall through the console passage. Inject power at the start and roughly opposite side. Chain data from the perimeter to the two console rows.

| Interface | Connection |
| --- | --- |
| **74AHCT125** buffer | ESP 3.3 V LED data → 5 V strip data, through **330 Ω**. Use one channel for the chained strip. |
| **Bidirectional I²C level shifter** | ESP SDA/SCL at 3.3 V ↔ LCD SDA/SCL at 5 V. |

The [interface-board drawings](interface-board.md#board-layout-and-fitted-parts) give component pinouts, unused-input connections and decoupling. Check the LCD address and driver before use.

### Panel status indicators

The ten fixed-colour [P25 indicators](shopping-list.md#additional-panel-status-indicators) use one [P26 controller](shopping-list.md#additional-panel-status-indicators), with six channels spare. The plan uses **5 V lamps**, **3.3 V I²C logic** and open-drain outputs.

Measure lamp current before connecting it to the controller; add resistors or a driver stage if its ratings require them. Keep I²C pull-ups at 3.3 V and all grounds common. Controller integration, final wiring and panel positions remain [open checks](checks.md).
