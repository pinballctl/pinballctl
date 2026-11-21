# Test Bench: Checks before use

<span id="readable-engineering-checks-and-unresolved-evidence"></span>

## Checks

The layout has been checked for modelled overlaps. Physical fit, wiring and operation still need validation.

| Check | Required result |
| --- | --- |
| Box and carrier | Measure the cavity, hinges and lid clearance; the carrier fits flat and lifts out freely. |
| Controls and LCD | Confirm panel grip, rear depth, wire bends and closed-lid clearance using the received parts. |
| Pi and power board | Check cooler airflow, control access and the complete **110 × 70 × 52 mm** bay, including connectors. |
| Mounting | Size carrier fixings, console/LCD retainers and sensor pads. No screw tips project through the base. |
| Interface board | Check pad grid, fixing holes, level-shifter footprint and capacitor size before soldering. Verify the [connection table](interface-board.md#copper-side-links). |
| Ball course | Balls pass the corner and manual gate freely; touching balls produce distinct trough events. |
| Sensor signals | Verify **0–3.3 V** at each ESP input, including startup. Fit an interface if required; check all eight stations with final wiring and debounce. |
| Panel indicators | Confirm lamp current, controller output limits, firmware support, wiring and mounting positions. These additions are not yet in the dimensioned layout. |
| Supply and protection | Select the external **12 V** supply, inlet and Pi DC lead. Confirm connector polarity, fuse-block isolation, fuse ratings, wire sizes and strain relief. |
| Power under load | Measure total current, 5 V voltage drop and converter/cable/Pi temperatures with full lighting. Check Pi power detection and cooling. |
| Outputs and controls | Lamps remain off at boot/reset; buttons, LCD and lighting work. Verify GPIO assignments and ESP arming, watchdog, pulse-limit and fault handling. |
| Closure and transport | Lid opens, locks and closes freely. The retained padded cover secures all three balls before carrying. |

Keep power off while making connections. Complete these checks before treating the bench as ready for use.
