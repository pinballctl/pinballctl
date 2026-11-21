# Test Bench: Checks & next steps

Unresolved fit, wiring and validation work before ordering or drilling.

## Readable engineering checks and unresolved evidence

The geometry check finds no overlapping **modelled** module/keepout envelopes, including all ten buttons' **24 × 24 × 35 mm** wiring reservations. It includes conditional reservations for the Pi/GeeekPi assembly, three inline holders and right-side inlet/passage. It excludes individual wire routing, final fixing details, deflection and lid motion. No physical build, rolling, closure, transport or load test has been performed.

| Item | Current evidence / required next check |
| --- | --- |
| Box and carrier | 370 carrier in approximate 380 cavity leaves **5 mm each side**. Measure the delivered box, hinge intrusion and wall/base thickness before cutting. |
| Console and lamps | Stack **6 + 83 + 6 = 95 mm**. P07's conditional 5 mm cap ends at **z=100**, leaving 25 mm to nominal lid; 35 mm wired rear allowance ends at **z=60**. Published 15 mm thread does not establish complete depth or panel grip. Measure the received lamp and nut engagement. The taller button allowance ends at z=105, leaving **20 mm** overall nominal lid clearance. |
| Small buttons | Published Ø14 face / Ø12 hole / 8 mm maximum panel suit 6 mm sheet. Assumed 35 mm rear ends at **z=60**, 9 above fuse envelope; 10 mm cap ends at z=105. Actual overall depth and wired clearance remain unknown. |
| LCD and interface | LCD reservation z=65–100; Pi/GeeekPi reservation ends at z=58, leaving **7 mm nominal gap**. Interface z=60–89 clears the converter z≤45 by 15 mm; the proposed component bottom is z=61.4. Its pad grid, corner fixings, U2 row spacing and capacitor dimensions need measurement. Verify actual depths, cable bends, airflow and retention; these gaps are conditional. |
| Pi power and inlet | P24 is the **87 × 57 mm GeeekPi / 52Pi EP-0225**. The **110 × 70 × 52** envelope is an allowance for both boards, mounting, cooler, DC plug and USB-C cable bends; the final arrangement is unverified. Check switch access and actual assembly/cooling with the panel closed. Confirm DC socket size/polarity and select a rated input lead. Inlet and three holders have conditional bays; verify bodies, wall passage, flange/cutout, attachment and strain relief. Supply/inlet selection, fuse ratings, wire sizes and distribution remain open. |
| MDF | P03/P04 supply 6/12 mm MDF. Carrier standoff retention, LCD retainers, console/sensor pads and transport-cover fixings need dimensioning and a clearance check. Additional hardware and finish are not selected. |
| Ball sensing | P05 supplies **eight Treedix pairs from four two-pair packs**. Published head size is **20 × 10 × 9 mm**, with **5 mm optics** and **300 mm leads**. Check lens centres, fixing holes and rail apertures using one pair first. **30 − 27 = 3 mm** total lane clearance and the ideal **10.03 mm** touching-ball clear window at h=24 are geometry only. Test all eight stations at realistic speed/debounce, including corner and gate; advertised 2 ms response is not measured performance. |
| Sensor inputs | The Treedix NPN description does not establish an open-collector output without a 5 V pull-up. Qualify voltage and polarity with the ESP disconnected before using direct 3.3 V inputs; see the [sensor procedure](wiring.md#direct-sensor-connections). Specify any required interface before wiring. Measure total sensor current and revisit the provisional logic-power budget. |
| Lighting | **89 + 6 + 6 = 101** nominal pixels; budget **102**, within P09’s 120-pixel / 2 m roll. Width is 10 mm; thickness, minimum bend radius and factory-join spacing are unpublished. Verify these, adhesive and clip engagement before cutting. |
| Closure fittings | Catch pattern/projection unpublished; stay text says 190 mm open versus 195 mm drawing. Set holes/pivots from actual parts and prove locking/closure with lid backing clear of lamps. |
| Electrical validation | Verify driver reset-OFF/input polarity, sensor logic, LCD operation, Pi power detection, full-white voltage drop, current and cable/converter/Pi temperatures with intended ventilation. Fuse sizing must protect the actual conductors/connectors. |

The ESP must enforce arming, watchdog, pulse-limit and fault protections. GPIO assignments and firmware configuration must be verified for the fitted hardware.
