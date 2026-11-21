# Test Bench: Power & host connections

The 12 V inlet, protected supply branches and Mac/Pi host switching.

**Provisional design.** Read the [remaining checks](checks.md) before ordering, cutting or wiring. No physical build or load test has validated this proposal.

## Power and host connections

### Single power inlet

**Power path:** external enclosed 12 V supply → right-side XT60 inlet → main fuse → separately protected Pi-converter, lighting/logic-converter and 12 V indicator branches. Mains stays outside the box. P24 GeeekPi / 52Pi EP-0225 powers the Pi through its supplied USB-C power cable; P15 powers the lighting/display. Do not parallel their 5 V outputs or join the lighting rail to USB VBUS.

P24 is the selected Pi power board. The supply and inlet below are **awaiting confirmation and excluded from the shopping subtotal**. Prices were checked on 18 November 2026; listing claims are not independent load tests.

| Part awaiting confirmation | Item price | Required checks |
| --- | ---: | --- |
| [Weishuo 12 V / 20 A / 240 W car-socket adapter, B0HB4BXY3T](https://www.amazon.co.uk/dp/B0HB4BXY3T) | £26.16 | Advertised capacity is sufficient. Sustained output, cable rating and protection remain unverified. Replacing its low-voltage socket with XT60 would require proper termination; no mains modification. |
| [RUNCCI-YUN XT60E-M panel / female cable set, B0D46FPJ6D](https://www.amazon.co.uk/dp/B0D46FPJ6D), 5 pairs | £6.99 | Preferred contact arrangement: recessed female contacts on the live supply lead. Flange, cutout, screws, wooden-wall attachment and strain relief still need checking. |

The [GeeekPi Pi 5 PD board, B0CYNV8YMV](https://www.amazon.co.uk/dp/B0CYNV8YMV) accepts **9–24 V DC** and provides **5.15 V / 5 A USB-PD 3.0** ([52Pi EP-0225 manual](https://wiki-md.52pi.com/docs/EP-0225)). Connect protected 12 V to its **DC input**, and its **USB-C output** to the Pi. Leave the board's separate USB-C **input** disconnected: the two input sources must not be used together. Check Pi power detection and available USB power against [Raspberry Pi's power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply).

**DC connection still to select:** the current 52Pi manual specifies a **3.5 mm outer / 1.35 mm inner, centre-positive** barrel connector; older listing text gives a different size. Verify the received socket, polarity and current rating before buying the mating lead, then provide strain relief. The supplied USB-C cable is the Pi output connection, not a 12 V input lead. The additional DC lead/plug is excluded from the shopping subtotal.

The board's **Always-ON** switch enables automatic startup when external power returns; it is disabled by default. With it disabled, press **POWERON** to start. Holding POWERON for more than three seconds cuts power; shut down the Pi operating system first. Keep both controls accessible in the final mounting.

The **5 W sensors/LCD/interface allowance** below remains provisional: measure the Treedix pairs’ current because the listing gives inconsistent figures, and revise the budget if needed.

Planning allowances are **25.5 W Pi/USB peripherals**, **30.6 W for 102 pixels at 60 mA each**, **5 W sensors/LCD/interface**, and a provisional **10 W for 12 V lamps/rings**. At 90% converter efficiency, `(25.5 + 30.6 + 5) / 0.90 + 10 = 77.9 W`, or **6.5 A at 12 V**; at 80%, **7.2 A**. An enclosed **12 V / 10 A** supply is a reasonable target; a verified Amazon supply is not yet selected. This budget excludes real coils.

**Fuse values and wire sizes remain pending.** P17 allocates three positions to the protected 12 V branches: Pi converter, lighting/logic converter and indicators; the fourth is spare. Three P18 inline holders provide the main 12 V fuse and separate 5 V lighting/logic fuses. Their body-and-lead reservations are shown in the [layout plan](../test-bench.md#layout-and-illustrations), but actual holder fit and distribution wiring remain unverified. Check P17 circuit isolation and terminal identity before wiring.

| Branch / connection | Intended wiring |
| --- | --- |
| Pi | Protected 12 V → P24 DC input → supplied USB-C output cable → Pi. Complete mounting, cooler, plug and bends must fit the conditional 110 × 70, z=6–58 reservation; final board arrangement remains to be checked. |
| Lighting | Protected 12 V → P15 → separately fused 5 V strip/console feeds and AHCT125 buffer. **6.12 A / 30.6 W** is a conservative planning maximum, not measured demand. |
| Logic | Separately protected P15 5 V → LCD, I²C high side and proposed Treedix head supply. Keep receiver signals disconnected until the [3.3 V compatibility check](wiring.md#direct-sensor-connections) passes or a suitable interface is validated. I²C low side and compatible input pull-ups use ESP 3.3 V. |
| Indicators | Protected 12 V → two independent P16 MOSFET load circuits → left/right P07 yellow lamps. Separate parallel 12 V bus powers the steady blue button rings. Verify terminal labels, input polarity and reset-OFF behaviour. |
| Returns/distribution | Common low-voltage ground, with main LED return directly to the converter. No strip current through ESP, sensor wiring or USB. Six WAGOs are reserved; each joins all five ports into one node. Use one conductor per port and retained insulated splices for branching. Confirm node allocation, including the Pi branch. |
| I/O | Ten buttons + eight optical receivers = **18 inputs**, plus two lamp outputs, LCD I²C and LED data. Confirm available pins and boot/flash restrictions before assigning GPIOs. |

### Normal Mac use and portable Pi demos

The **Mac is the normal host**; the **Pi is for portable demos**. Connect the Mac data cable directly to the ESP serial/programming USB-C port. For demos, open the box, unplug it and connect P23 from Pi USB-A to **the same ESP port**. No USB switch, hub, selector or extra panel USB socket is included.

Disable outputs and stop the current bridge/flashing process before swapping, then start the new host's bridge. USB supplies the ESP as well as data; expect a disconnect and possible restart. Do not connect both hosts through different ESP sockets or add a parallel 5 V feed to its USB-powered rail. Keep configuration/media on both hosts consistent; cable swapping does not synchronise them. The existing Mac cable is assumed available.
