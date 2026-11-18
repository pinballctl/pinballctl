# Test Bench

The test bench is a small physical development rig for exercising switch events,
ball tracking, lighting, displays and output indicators before building a complete
pinball machine. The work includes enclosure studies, CAD, wiring and power
planning, component shortlists and a real-ball sensing course. It is still design
work, not a finished hardware product.

**Current proposal, 18 November 2026:** a wooden box containing a three-ball gravity
course and a removable control console. The WooDeeDoo 400 × 400 × 135 mm enclosure
is selected. This layout has not been physically built or approved for manufacture.

![Proposed wooden-box course, console, electronics bays and closed-height section.](./media/bench-course-layout.png)

## How the design developed

| Study | Decisions and remaining limits |
| --- | --- |
| Printed enclosure | Revision 8 received visual approval on 10 November: a charcoal sloping enclosure, retail-style controls, RGB lighting, LCD and recessed breadboard. Approval covered appearance; component fit and manufacture remained open. |
| Preliminary mechanics | `mechanical-v2` explored printed parts, hinge/latch coupons, a carrier connection schedule, ESP identification and internal clearance. A custom carrier PCB was proposed but not released. |
| CAD and FreeCAD | `cad-v8` retained STEP/STL geometry and shell checks. `freecad-v8` became the editable native master. Shell validity and sampled movement did not prove populated clearance, wiring movement or print fit. |
| Stock wooden bench | The 15 November KNAGGLIG study and wooden-panel diagrams explored off-the-shelf controls, wiring and lamp indication on an open wooden base. This reduced dependence on custom printing but remained a layout study. |
| Other enclosures | Creative Deco fit studies explored a shallow closed case with limited power/service space. The shortlist recorded Hammond 1456KG4BKBU as a metal candidate with unverified final fit. |
| Wooden-box ball course | The 18 November `woodeedoo-course-v1` proposal combines real rolling balls and a removable console in the selected 400 mm box. Its drawings and parts list define the latest proposal, pending physical checks. |

The [printed enclosure study](test-bench-enclosure-study.md) retains its visual
baseline and detailed CAD context. Earlier controls, LED counts, custom carrier
requirements and pin allocations do not automatically carry into the wooden-box
version. Engineering originals remain under `docs/design/test-bench/` and
`docs/media/`; they are design work and must be preserved during build cleanup.

## Current layout

The nominal cavity is 380 × 380 × 125 mm. A low L-shaped course follows the rear
and left sides. A 240 × 240 mm removable console occupies the front-right, with
the Raspberry Pi, ESP32-S3, power conversion and interfaces underneath. The lid
stays a plain cover. Measure the real box and hinge intrusion before cutting.

| Part | Proposal and checks |
| --- | --- |
| Carrier | Separate 370 mm square of 6 mm plywood, trimmed to fit. Sidewall cleats carry the load; do not rely on screws held only in the original 3 mm bottom. |
| Course floor | Cut a 260 mm square from the front-right of a 360 mm square of 6 mm plywood. The waste supplies the 240 mm console, allowing for saw kerf. |
| Rails | 12 mm plywood, 30 mm high, with 30 mm clear lane width for 27 mm balls. |
| Slope and corner | Approximately 2° toward the left and 2° toward the front, using blocks and shims. A wider corner pocket and 45° guide avoid a tight square bend. Prototype rolling before permanent fixing. |
| Console height | Top at 95 mm above the original inner bottom. A 20 mm lamp-cap allowance leaves 10 mm nominal lid clearance; actual caps, nuts and wiring need checking. |
| Controllers | Pi bay 110 × 70 mm and ESP bay 95 × 70 mm including nominal access. These are allocated rectangles, not verified models of populated boards, coolers or cables. |

The proposal uses ordinary woodworking and soldered interfaces. It does not
require a 3D printer, custom PCB or machined metal trough.

## Ball cycle and sensing

1. Three 27 mm steel balls queue in the front-left trough, one per optical position.
2. Move the front ball **by hand** into the higher rear-right shooter pocket. The
   other two roll forward: after settling, T1/T2 are occupied and T3 is empty.
3. The loaded ball blocks shooter-ready. Lift the sliding gate manually to release
   it. The Fire button is a separate input and does not actuate the gate.
4. The ball clears ready, crosses onfield, two bumper-trigger stations and drain,
   then returns to the vacant trough position. All three trough sensors become
   occupied after settling.

There are **eight optical stations**: three trough positions, ready, onfield, two
bumper triggers and drain. Bumper stations sense passage without kicking the ball.
Launch detection uses ready departure and onfield, not just a Fire press. Gravity
cannot return the ball to the higher shooter: each cycle needs the hand transfer.

Proposed trough beams are 27 mm apart, initially 21 mm above the running surface.
The saved calculation gives approximately 4.55 mm of clear travel between touching
balls for ideal point beams. Real beam width, alignment, ambient light and firmware
debounce still need testing with two touching balls. Prototype one sensor station
before completing the eight-station course.

## Controls, lighting and power

| Area | Current proposal |
| --- | --- |
| Momentary controls | Ten: Start, Fire, Lock, Ramp, Orbit, Target, Bump 1, Bump 2 and left/right flippers. |
| Output indication | Two 46 mm amber 12 V lamps through separate driver modules. Their integral switches are unused. |
| Display | One 16×2 LCD with a PCF8574-style backpack and a separate bidirectional I²C level interface. |
| Addressable LEDs | 60 WS2812B pixels: four 200 mm effect runs (48), one 100 mm status row (six) and one 100 mm key-light row (six). |
| LED data | AHCT buffer for 3.3 V to 5 V data, with suitable decoupling and wiring. The LCD interface is a different circuit. |
| Host/controller | Pi uses an external USB-C supply; ESP uses USB from the Pi. Identify the exact ESP board, power paths and pin restrictions before wiring. |
| Lamps and lighting | Separate external 12 V adapter, protected branches and a proposed 5 V/10 A converter for LEDs/LCD. Continuous output and temperature need verification. |

The conservative LED allowance is 60 × 60 mA = **3.6 A at 5 V**, before other loads.
The converter rating alone does not validate the installed system. Keep both mains
adapters and wall leads outside during use; internal adapter storage is not
allocated. Keep the separate buck output off USB VBUS. Select branch fuses,
connectors, wire and protection against actual loads before wiring.

## Mounting and service

![Proposed carrier support, removable console, lamp clearance and optical trough sections.](./media/bench-course-mounting.png)

Use through-fastened board standoffs and four console supports outside the module
bays. Retain a detachable, relaxed service harness. Keep each 60 × 60 mm lamp-tail
area clear: the drawing reserves 65 mm below the panel plus 12 mm for wire bend,
ending at z=18 mm. Actual lamp depth, thread grip and terminal access need sample
checks. Transfer LCD and board holes from the real parts.

Mount optical heads on adjustable pads outside the rails and set beam heights
from the actual lenses. Provide cable clamps, accessible low-voltage terminals
and ventilation around the Pi and converter. Fit catches, a positive lid prop and
a captive padded ball holder for transport. A chain limits travel but does not
hold the lid open. Back fittings where they would otherwise load the thin lid.

## Parts and engineering records

The current engineering folder is `docs/design/test-bench/woodeedoo-course-v1/`:

| Record | Purpose |
| --- | --- |
| `README.md` | Detailed assumptions, ball cycle, mounting and remaining checks. |
| `layout.json` and `render.py` | Coordinates and reproducible dimensioned diagrams. |
| `validation.json` | Nominal envelope checks, clearances and their limits. |
| `shopping-list.md` | Dated shortlist, variants, quantities and unresolved sourcing. |

The selected box is WooDeeDoo B0973KZMGK. Other items remain candidates: balls,
optical pairs, plywood, buttons, lamps, LCD, LED strip, converter, lamp drivers,
branch protection and logic interfaces. Fixings, connectors, low-voltage entries,
USB leads, lid support and ball restraint still need final selection. This is not
a complete order-ready BOM. Recorded prices and availability are historical;
no orders were placed by this design work. Private purchasing details are omitted.

## Validation and next steps

The saved checks report non-overlapping nominal module envelopes, 10 mm nominal
lid clearance, 3 mm lane clearance and 60 pixels. They do not validate real parts,
cable bends, loaded deflection, transport, temperature or sensing performance.

Before drilling, measure the box, lamps, buttons, LCD, controller assemblies and
converter. Prototype the gate, corner, touching-ball sensing and full trough cycle.
Check repeated events with the actual debounce configuration, then verify power-up
OFF, load, voltage and temperature with installed interfaces.

Output lamps demonstrate commands and light-load switching. They do not validate
solenoid current, flyback, pulse accuracy or flipper mechanics. Preserve arming,
pulse limits, watchdogs and fault handling. No application, bridge, firmware or
runtime pin-map changes are included in this design work.
