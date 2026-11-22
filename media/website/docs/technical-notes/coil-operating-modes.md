# Coil operating modes

Under Hardware, set **Function → Coil**, **Driver → Default**, then open that
pin's driver options. **PIN Safe** remains the electrical OFF level. Rule ON/OFF
is logical activation/release for coils, regardless of that electrical level.

New coils default to **Disabled**, **Pulse only**, a **10 ms normal pulse**, a
**20 ms hard pulse limit**, and **1,000 ms cooldown**. These are starting values,
not ratings for an unknown coil or power driver. Save Changes persists the
mapping on the Pi; Sync to ESP deploys the limits and requires an acknowledgement
before uploading the mapping. Deployment leaves the ESP disarmed.

| Mode | Rule ON | Rule OFF |
|---|---|---|
| Pulse only | Run the configured pulse, then turn off automatically | Stop immediately |
| Pulse + PWM hold | Initial pulse, then configured PWM duty | Stop both pulse and hold |
| Separate power and hold | Pulse the power winding, turn it off, then energize the linked hold winding | Turn both windings off |
| Continuous duty | Activate an explicitly continuous-rated output | Turn off |
| Hold winding | Independent activation is rejected; controlled by the paired power pin | Release the whole pair |

A **PULSE** rule always performs a finite pulse without entering hold, including
on a hold-capable primary output. Its duration must not exceed the hard pulse
limit. Repeated ON/PULSE commands do not extend an existing activation. A hold or
continuous timeout latches a fault and shuts all coils down; it never becomes an
unlimited hold. Hold time is measured after the initial pulse; continuous time
is measured from activation. Limits range from 1–1,000 ms for a pulse and
1–60,000 ms for hold/continuous activation. Cooldown is 1–60,000 ms and must be
at least the hard pulse limit.

For a paired coil, configure one pin as **Hold winding**, then select it in the
power pin's **Separate power and hold** options. Configure both rows before
saving. Each retains its own PIN Safe and cooldown; the assembly's hold limit
cannot exceed the secondary winding's limit. Both must be enabled before the
primary can be enabled. Only the primary appears as an output in the rules
editor. Sharing a hold winding between assemblies is rejected.

PWM has no assumed safe duty: its default is **0%**, and enabling PWM hold
requires choosing 5–95% in 5% steps. Default firmware supports 50, 100, 250 and
500 Hz using a 100 µs interrupt tick. This is switching duty, not measured current
or power. A board with internal pulse/hold control requires a dedicated driver;
Default does not claim board-managed hold or higher-frequency PWM support.

The firmware enforces arming, pin ownership, deadlines, cooldown and host/loop
watchdogs independently of rule timers. Removing a reserved coil pin or changing
its PIN Safe during a live boot is rejected. Native policy tests and ESP32-S3
compilation do not qualify the electrical hardware: actual PWM timing, current,
thermal behaviour and shutdown under load still need hardware validation.
