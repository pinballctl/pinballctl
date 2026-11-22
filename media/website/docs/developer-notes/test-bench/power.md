# Test Bench: Power & USB

## Power and host connections

### Single power inlet

**External 12 V supply → inlet → main fuse → separately protected branches.** Mains remains outside the box.

The [external supply and XT60 connector set](shopping-list.md#power-and-interfaces) include the UK mains lead, panel inlet and matching cable connector. The supply's low-voltage car socket is replaced by the **XT60H-M male cable plug**, with insulated joints and strain relief. The capped **XT60E-F female inlet** mounts on the right side of the box; the mains lead remains unchanged. The supply is unplugged from mains before connecting or disconnecting the XT60, so the exposed cable contacts are unpowered.

| Branch | Connection |
| --- | --- |
| Pi | Protected 12 V → Pi power board **VIN solder pads** → USB-C output → Pi. |
| Lighting | Protected 12 V → 5 V converter → lighting fuse → LED strip and data buffer. |
| Logic | 5 V converter → separate logic fuse → LCD, I²C high side and sensor power. |
| Yellow output lamps | Protected 12 V → two independent MOSFET lamp circuits. |
| Blue button rings | Protected 12 V → steady backlight bus. |

All low-voltage circuits share a common ground. LED load current returns directly to the converter, not through the ESP or USB. The Pi supply, fused lighting/logic feeds and USB VBUS remain separate: converter outputs are not paralleled and branch fuses are not bridged. Each five-way WAGO joins all five ports into one node.

The four-way fuse block uses three positions for the **Pi converter, lighting/logic converter and 12 V indicators**; one is spare. Three inline holders provide the **main 12 V**, **5 V lighting** and **5 V logic** fuses. Fuse ratings and wire sizes must match the loads, cables and connectors.

### Pi power board

The Pi power board is listed as [P24 in the shopping list](shopping-list.md#power-and-interfaces).

- Protected **12 V** is soldered directly to the **VIN** pad group: **V = +12 V**, **G = ground**, with strain relief for the wires. The barrel socket and USB-C input remain unused.
- The supplied USB-C output cable powers the Pi.
- The board handles the voltage conversion. The [manufacturer's connection diagram](https://wiki.52pi.com/images/thumb/9/90/EP-0225-4.jpg/800px-EP-0225-4.jpg) identifies **VIN as DC input**; the separate **+5 V** pad group is an output.
- **Always-ON** enables startup when power returns; **POWERON** provides manual startup. Both controls remain accessible. The operating system requires shutdown before power is removed.

The [Pi bay](../test-bench.md#layout-and-illustrations) includes clearance for the cooler and cable bends.

### Power budget

| Load | Planning allowance |
| --- | ---: |
| Pi and USB peripherals | 25.5 W |
| Up to 102 addressable pixels | 30.6 W / 6.12 A at 5 V |
| Sensors, LCD and interfaces | 5 W |
| 12 V lamps and button rings | 10 W |

At 80–90% converter efficiency, the estimated demand is **6.5–7.2 A at 12 V**. The supply specification is an enclosed **12 V / 10 A** unit. These are design allowances rather than measured consumption; real coils are outside this budget.

<span id="normal-mac-use-and-portable-pi-demos"></span>

### USB connection

A data-capable cable connects the control host to the ESP's serial/programming USB-C port. USB also powers the ESP. There is one host connection and no parallel feed into the ESP's USB-powered 5 V rail.
