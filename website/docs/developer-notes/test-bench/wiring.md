# Test Bench: Lighting & wiring

Sensor connections, flipper inputs, output lamps and LED interfaces.

**Provisional design.** Read the [remaining checks](checks.md) before ordering, cutting or wiring. No physical build or load test has validated this proposal.

## Lighting and electrical connections

### Direct sensor connections

**P05 uses Adafruit 2167**, using the ESP's internal pull-ups to avoid a separate sensor interface circuit. Adafruit documents the receiver's open-collector output and the option to use a microcontroller's built-in pull-up ([product specification](https://www.adafruit.com/product/2167), [wiring guide](https://learn.adafruit.com/ir-breakbeam-sensors/arduino)).

- **Emitter:** red lead to the protected **5 V logic supply**, black to ground. It needs power but no ESP GPIO.
- **Receiver:** red lead to the same protected **5 V logic supply**, black to common ground, and white/yellow signal lead directly to one ESP input. Enable that input's **3.3 V internal pull-up** (`INPUT_PULLUP`); do not pull the signal up to 5 V.

Eight stations therefore use **eight ESP inputs**, with power distributed to all sixteen heads. The sensors draw power from the supply rail, never from an output GPIO. No additional sensor resistors, level converters or custom sensor PCB are planned. The firmware supports internal pull-ups; confirm each chosen pin is configured with one enabled and check the blocked/clear states. Test transitions with the final cable lengths, LED effects and touching balls before fixing the debounce settings.

### Flipper inputs and coil-output lamps

Each side has **one blue momentary input button and one dedicated yellow output lamp** on the top panel. The [P07 yellow indicator lamps](https://www.amazon.co.uk/dp/B0FBGLDVNQ) have no push switch; the shopping list includes **one pack of two**, directly below the P06 blue buttons. Their Ø24.8 faces are larger than the blue buttons' Ø14 faces.

| Path | Connection and purpose |
| --- | --- |
| Input | Blue button's normally-open contacts → ESP switch input → configured flipper rule. Releasing the button opens the input again. |
| Output | ESP output → that side's P16 MOSFET control input. Protected 12 V supplies the module's load circuit and its separate yellow lamp, connected according to the module's terminal labels. Each lamp's power must pass through its own MOSFET-switched output. |
| Button lighting | Blue ring → steady protected 12 V backlight bus. It does not indicate the MOSFET output, and its LED pins remain separate from the switch contacts. |

The yellow lamp therefore shows the switched electrical output under a small load, including when an output test activates it without a button press. Configure the ESP rule and output safety limits; do not connect the button directly to the lamp or substitute a GPIO status LED. Check P16's terminal labels, active level and reset-OFF behaviour before connecting it; no board-specific terminal or GPIO assignment is implied here.

P07 is listed as **12–24 V AC/DC, 20 mA**. On this bench it uses 12 V. It represents a coil firing visually but cannot test coil current, inductive kick, flyback protection or mechanical movement. Its pulse/PWM response is unspecified: a visible flash is not a measurement of output pulse duration.

### LED strip and signal interfaces

**P09 uses one 2 m Tesfish roll.** At 60 pixels/m, the nominal cuts are **89 pixels / 1.483 m** for the perimeter and **6 pixels / 0.100 m** for each console row: **101 pixels / 1.683 m total**. That leaves **19 pixels / 0.317 m** spare, or **18 pixels / 0.300 m** if final fitting needs 102 pixels. Cut the continuous perimeter first, then the two short rows; dry-fit before cutting.

Use **one continuous perimeter strip** on the inside walls at about **z=110**, with a feed gap on the **right near y=285**. The nominal path is 1.495 m with 10 mm-radius corners: 89 pixels / 1.483 m leaves about 11.5 mm for the gap. These bends are design allowances, not a manufacturer-specified minimum radius. Dry-fit before cutting; keep pixels and any factory joins off bends, and never crease the strip.

Retain feed/data wires down the inner right wall to the console-side passage near **z=60**, clear of button tails and the converter. Feed power at the strip start and approximately opposite side. The end-of-strip data continues to the console's **six status pixels and six key-light pixels**, each row about 100 mm. Nominal total **101 pixels**; the power budget allows **102** after final trimming. Use the supplied adhesive on clean, smooth timber, supplemented by clips where needed.

The two level-shifting parts have different jobs:

| Part | Connection | Why it is included |
| --- | --- | --- |
| P19 **74AHCT125** | ESP 3.3 V output → 5 V LED data | Actively drives the precisely timed, one-way WS2812 signal. It is a bare IC soldered to the interface board. |
| P20 **bidirectional I²C module** | ESP ↔ LCD SDA/SCL, 3.3 V ↔ 5 V | Allows the LCD bus to work in both directions. Neither part supplies LED load power. |

P19 provides the LED strip's 5 V data signal from the ESP's 3.3 V output ([Adafruit's AHCT125 guidance](https://www.adafruit.com/product/1787)). P20 handles the bidirectional LCD I²C bus; its pull-up-based signals have different drive characteristics ([Adafruit's explanation](https://www.adafruit.com/product/757)).

The component schedule uses **one chained LED data stream**, one AHCT125 channel and one 330 Ω resistor; it does not assign a GPIO. Use the IC datasheet for pinout/enables, define unused inputs and leave unused outputs disconnected. Verify the LCD's actual I²C device/address and driver.
