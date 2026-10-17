# Pinball CTL

Pinball CTL is a browser-based control platform for homebrew pinball machines.

It combines:
- A Raspberry Pi authoring/orchestration layer
- An ESP32-S3 real-time runtime layer

From one interface, you can map hardware, author rules and scoring, build lighting/media scenes, and sync deterministic runtime behavior to ESP.

## Repository layout

This repository contains the controller application and its companion projects:

| Folder | Purpose |
| --- | --- |
| `src/pinballctl/` | Python application, web UI and bridge |
| `src/firmware/` | ESP32 firmware |
| `src/godot/` | Godot media runtime |
| `backglass/` | Independently editable Godot backglass/menu scene |
| `website/` | Existing public website sources |
| `docs/` | Existing documentation sources, assets and build tools |

Website and documentation deployment has **not** moved. The original repositories
continue to serve `www.pinballctl.com` and `docs.pinballctl.com`. Changes under
`website/` or `docs/` here do not publish to those sites. Their integration and
redesign are a separate step. See [the maintainer guide](docs/MAINTAINER.md#repository-import--2026-10-17)
for preserved histories, build commands and deployment boundaries.

## Why Pinball CTL

This project was created to make pinball control workflows clearer and less cumbersome for builders.
The goal is practical: faster iteration, approachable tooling, and safer machine operation.

## How It Works

1. Discover and map hardware in the web UI.
2. Build gameplay behavior in Rules and Scoring.
3. Design visuals in Lighting and Media.
4. Save and sync state to ESP runtime.
5. Monitor health and diagnostics in Dashboard and Logs.

Architecture flow:

`Browser UI -> Pi Services -> Bridge -> ESP Runtime`

## Key Modules

- Dashboard: machine status, sync state, dependency checks
- Rules: trigger/condition/action logic with sync workflow
- Scoring: base points, rules, combos
- Playfield: table layout authoring and test workflows
- Lighting: stage + fixtures authoring and preview
- Media: stage/library/displays/runtime with kiosk launch modes
- Audio: assets, cues, outputs, usage map
- Hardware: I/O mapping and safe-state configuration
- ESPLink + Firmware: connectivity and firmware lifecycle
- Settings + Import/Export: installation config and migration
- Logs + Service Log: diagnostics and maintenance history

## Safety Model

- ESP runtime enforces output safety constraints.
- Pi/UI provides authoring, visibility, and controlled sync.
- Faults and state transitions are surfaced in runtime and dashboard views.

## Requirements

- Raspberry Pi 5 (recommended host)
- ESP32-S3 (real-time controller)
- USB serial connection between Pi and ESP
- Modern browser on local network

## Quick Setup

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git
mkdir -p ~/pinballctl && cd ~/pinballctl
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/pinballctl/pinballctl.git@vX.Y.Z"
pinballctl start
```

Then open:

`http://<pi-ip>:8888`

Default login:
- Username: `admin`
- Password: `password`

## Coil operating modes

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

## Development Notes

### Bridge performance and overload

Platform → Performance shows throughput, outstanding work, and event confirmation
latency, including a separate measurement of time spent in the bridge queue.
Scoring notifications retain their full data on the host bus and in event logs.
They stay local when neither authored nor confirmed deployed rules reference them;
unknown or changed deployments keep forwarding. Forwarded scoring notifications
carry only the event identity and trigger fields used by the ESP, rather than the
full award breakdown. This reduces traffic without changing safety thresholds.
Connected Live View events run on the ESP and enter the host event bus on their
confirmation, just like real switch notifications. Offline Live View uses the
local fallback. Host-derived/scoring notifications already published locally
carry bridge-only context: their confirmation runs dependent host rules without
publishing the same notification to scoring/audio/media again. This context also
retains parameters that the compact ESP echo does not include; it is not sent on
the serial wire and its history is bounded to 256 events (not durable across a
bridge restart).

Firmware v0.0.10 marks events whose deployed rules were evaluated. For those
events the host does not repeat pixel-lighting actions or statically configured
LCD actions that the firmware can execute. LCD placeholders are expanded only
on the host. Older firmware and offline simulation retain host fallbacks.
Confirmations acknowledge ESP event handling, not physical output movement.
Firmware advertises its supported event window: older firmware defaults to eight;
v0.0.9 supports sixteen with enlarged serial buffers and bounded output pumping.

If an event waits over 100 ms in the bridge queue, or a pending confirmation takes
over 250 ms, the bridge stops gameplay activations and disarms coils. Firmware
v0.0.11 adds a confirmed runtime pause: output timers and old button gestures are
cleared, while releases and physical switch levels remain tracked. After at least
two seconds and a continuous quiet second with drained queues, the bridge requests
recovery. Previously armed coils are re-armed through the existing generation and
heartbeat checks; recovery itself does not activate outputs. Inputs held across
the pause must release and press again. Rejected events are never replayed.

Three overloads within 60 seconds, a firmware fault, or an unconfirmed recovery
leave the system disarmed. Firmware faults are never automatically cleared. The
Performance diagnostic reset requests the same handshake with coils left disarmed;
normal isolated recovery needs no UI or game-specific Start event. Older firmware
without the pause handshake cannot recover automatically. Platform notifications
`PLATFORM_OVERLOAD`, `PLATFORM_OVERLOAD_FAULT` and
`PLATFORM_OVERLOAD_RECOVERED` are emitted on the host bus
and recorded in the event log.

`utils/bridge-load-test.py --mode fire` runs bounded diagnostic events that do not
match configured rules and stops escalating on overload. Use the project Python
environment and provide `--output /path/to/report.json`. Its ECHO round trips measure
host IPC and serial responsiveness, not switch-to-coil latency. Dev-board results
do not establish electrical timing or performance with a complete machine attached.

- You can iterate on macOS and deploy the same project config to Raspberry Pi.

## Links

- Website: [pinballctl.com](https://www.pinballctl.com)
- Documentation: [docs.pinballctl.com](https://docs.pinballctl.com)

## Documentation

- Website source: [website/](website/README.md)
- Documentation source: [docs/](docs/README.md)
- Maintainer guide: [docs/MAINTAINER.md](docs/MAINTAINER.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
