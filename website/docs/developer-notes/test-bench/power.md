# Test Bench: Power & USB

## Power and host connections

### Single power inlet

**External 12 V supply → inlet → main fuse → separately protected branches.** Keep mains outside the box.

| Branch | Connection |
| --- | --- |
| Pi | Protected 12 V → Pi power board **DC input** → USB-C output → Pi. |
| Lighting | Protected 12 V → 5 V converter → lighting fuse → LED strip and data buffer. |
| Logic | 5 V converter → separate logic fuse → LCD, I²C high side and sensor power. |
| Yellow output lamps | Protected 12 V → two independent MOSFET lamp circuits. |
| Blue button rings | Protected 12 V → steady backlight bus. |

Use a common low-voltage ground. Return LED load current directly to the converter, not through the ESP or USB. Keep the Pi supply, fused lighting/logic feeds and USB VBUS separate; do not parallel converter outputs or bridge the branch fuses. Each five-way WAGO joins all five ports into one node.

The four-way fuse block uses three positions for the **Pi converter, lighting/logic converter and 12 V indicators**; one is spare. Three inline holders provide the **main 12 V**, **5 V lighting** and **5 V logic** fuses. Fuse ratings and the main-feed wire size must be selected for the actual loads, cables and connectors.

### Pi power board

See [P24 in the shopping list](shopping-list.md#power-and-interfaces).

- Feed its **DC input** from protected 12 V; leave its separate USB-C input disconnected.
- Use the supplied USB-C output cable to power the Pi.
- Verify the DC socket before selecting a lead: the current specification is **3.5 mm outer / 1.35 mm inner, centre-positive**.
- Keep **POWERON** and **Always-ON** accessible. Always-ON enables startup when power returns; otherwise use POWERON. Shut down the operating system before cutting power.

Keep the Pi cooler and cable bends clear within the [reserved bay](../test-bench.md#dimensions-and-placement).

### Power budget

| Load | Planning allowance |
| --- | ---: |
| Pi and USB peripherals | 25.5 W |
| Up to 102 addressable pixels | 30.6 W / 6.12 A at 5 V |
| Sensors, LCD and interfaces | 5 W; measure with the panel indicators fitted |
| 12 V lamps and button rings | 10 W |

Allowing 80–90% converter efficiency gives approximately **6.5–7.2 A at 12 V**. The supply target is an enclosed **12 V / 10 A** unit. This is a planning budget, excludes real coils and needs a full-load measurement. The external supply, inlet and Pi DC lead are not yet selected or included in the shopping total.

<span id="normal-mac-use-and-portable-pi-demos"></span>

### USB connection

Connect the control host to the ESP's serial/programming USB-C port with a data-capable cable. USB also powers the ESP. Use one host connection and do not add a parallel feed to the ESP's USB-powered 5 V rail.
