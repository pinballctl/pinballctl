# Test Bench: Lighting & wiring

## Lighting and electrical connections

### Direct sensor connections

Eight break-beam pairs connect to **eight ESP inputs**. The sensors are listed as [P05 in the shopping list](shopping-list.md#sensors-controls-and-lighting).

| Connection | Wiring |
| --- | --- |
| Emitter | Red → protected **5 V logic supply**; black → common ground. |
| Receiver power | Red → the same **5 V logic supply**; black → common ground. |
| Receiver signal | White → ESP input with a **3.3 V pull-up**; requires verified **0–3.3 V compatibility**. |

Wire identification and signal voltage are checked with the ESP disconnected. The signal must stay within **0–3.3 V**, including startup. An output that drives or pulls up to 5 V requires a level interface; ESP inputs must not be pulled up to 5 V.

Separate transitions between touching balls determine the beam alignment and debounce setting. Sensor power comes from the supply rail, not a GPIO.

### Flipper inputs and coil-output lamps

Each flipper has a blue input button and a separate yellow output lamp.

| Path | Connection |
| --- | --- |
| Button | Normally-open contacts → ESP input and ground through the [interface board](interface-board.md#input-connections). |
| Yellow lamp | ESP output → MOSFET control input; protected **12 V** → the module's labelled lamp-load terminals. |
| Blue button ring | Separate, steady **12 V** backlight supply, electrically separate from the switch contacts. |

Each yellow lamp has its own MOSFET. The control circuit requires the correct input polarity and an OFF state during boot/reset. ESP arming, watchdog and pulse limits remain active. The lamps show output activity; they do not reproduce real coil current, flyback or pulse timing.

### LED strip and signal interfaces

| Strip section | Pixels | Nominal length |
| --- | ---: | ---: |
| Continuous perimeter | 89 | 1.483 m |
| Console status row | 6 | 100 mm |
| Console key-light row | 6 | 100 mm |
| Total | **101** | **1.683 m** |

The 2 m roll leaves 19 spare pixels. The power budget allows **102 pixels** for final fitting.

The perimeter strip runs inside the walls at **z≈110**, with its feed gap on the right near **y=285**. Pixels and factory joins sit clear of bends. Retained leads run down the right wall through the console passage. Power enters at the start and roughly opposite side; data chains from the perimeter to the two console rows.

| Interface | Connection |
| --- | --- |
| **74AHCT125** buffer | ESP 3.3 V LED data → 5 V strip data, through **330 Ω**. One channel serves the chained strip. |
| **Bidirectional I²C level shifter** | ESP SDA/SCL at 3.3 V ↔ LCD SDA/SCL at 5 V. |

The [interface-board drawings](interface-board.md#board-layout-and-fitted-parts) show component pinouts, unused-input connections and decoupling. LCD configuration must match the display's I²C address and driver.

### Panel status indicators

The ten fixed-colour [P25 indicators](shopping-list.md#additional-panel-status-indicators) use one [P26 controller](shopping-list.md#additional-panel-status-indicators), with six channels spare. The circuit uses **5 V lamps**, **3.3 V I²C logic** and open-drain outputs.

Lamp current must remain within the controller's output ratings; resistors or a separate driver stage are required where it exceeds those ratings. I²C pull-ups stay at **3.3 V**, with a common ground.
