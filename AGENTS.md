# AGENTS: pinballctl

This file defines how AI assistants (like Codex) should behave when working in this repository.

---

## 0. Precedence & Reality Check

- If any section conflicts with **Update 1 (FRAMES-ONLY transport)**, **Update 1 takes precedence**.
- Repository layout has evolved; assistants should prefer the current on-disk structure over older examples.
- Current key paths:
  - `src/firmware/` (ESP firmware is in this repo)
  - `utils/` (project utility scripts; previously `scripts/`)
  - `src/instance/` (runtime/generated instance data; avoid bulk edits unless explicitly requested)

---

## 1. Project Overview

**Name:** `pinballctl`
**Domain:** Homebrew pinball controller stack
**Target hardware & environment:**

- **Raspberry Pi 5** (primary brain)
  - Runs:
	- `pinballctl` Python services
	- Flask-based web UI (served via Gunicorn)
	- Serial daemon (pyserial) to talk to ESP32-S3
- **ESP32-S3**
  - Real-time I/O for:
	- Switches
	- Coils
	- LEDs
	- Sensors (e.g. gyro, tilt, etc.)
  - Communicates with Pi over USB serial

**High-level goals:**

- Provide a robust, testable, and maintainable control layer between MPF and the ESP32 firmware.
- Keep **coil control and safety** enforced on the ESP32 side, with clear commands and state from `pinballctl`.
- Expose an HTTP/Web UI for configuration, status, diagnostics, and onboarding.
- Support a **manifest-based configuration** and simple, debuggable protocols.

---

## 2. Architecture (Target / Intended)

### 2.1 Components

1. **Serial Daemon (`pinballctl` core)**
   - Python (3.x)
   - Uses `pyserial` to talk to `/dev/ttyUSB*` (ESP32-S3).
   - Responsibilities:
		 - Perform startup handshake/status exchange using framed JSON.
		 - Transmit a manifest / configuration to the ESP32.
		 - Send runtime commands (e.g., enable/disable and output control) via framed JSON.
		 - Listen to framed status/events from the ESP32.
		 - Reconnect gracefully if the USB device disappears and reappears.
		 - Feed data into the web layer and, optionally, MPF.

2. **Web API & UI**
   - Python + Flask (run under Gunicorn).
   - Responsibilities:
	 - Provide HTTP API endpoints (JSON) for status and control.
	 - Provide a web UI (HTML + JS + CSS) for:
	   - Onboarding (Wi-Fi setup, captive portal style)
	   - Diagnostics (coil fire tests, switch states, logs)
	   - Configuration (manifest, profiles, etc.)

3. **ESP32-S3 Firmware (in this repo at `src/firmware/`)**
   - Enforces **hard safety limits** (coil timeouts, watchdogs).
   - Requires `ENABLE` before allowing coil activation.
   - Emits structured telemetry/status over serial via framed transport.

4. **Manifest / Protocol Description**
   - JSON (or related) describing:
	 - Hardware layout (coils, switches, LEDs, boards).
	 - Versioning and hashes.
   - Used by both Pi and ESP32 as a contract.

---

## 3. Coding & Design Conventions

### 3.1 General Style

- Prefer **clear, explicit code** over overly clever shortcuts.
- Avoid introducing unnecessary abstractions or generic frameworks.
- When in doubt, optimize for **maintainability and debuggability**.

### 3.2 Python

- Target Python 3.x (latest stable on Raspberry Pi OS).
- Use:
  - `logging` module for logging (not `print` in production paths).
  - Type hints where they add clarity, especially in public functions.
  - `venv` / virtual environments assumed but do not hard-code paths.
- Structure modules logically (examples, may or may not exist yet):
  - `app/main.py` – entry point / web server bootstrap.
  - `app/serial_daemon.py` – serial I/O handling.
  - `app/config.py` – configuration loading, manifest paths.
  - `app/protocol/` – protocol encoding/decoding helpers.
  - `web/` – templates and static assets for the UI.

If these files or folders do not exist, **do not assume**; instead, propose additions or adjustments.

### 3.3 Web / Flask

- Use Flask Blueprints if the project starts to grow.
- Keep routes small and focused.
- JSON responses should be explicit and stable (no surprise structure changes without good reason).

### 3.4 Protocols & Safety

- The ESP32 firmware is the ultimate safety gate for:
  - Coil timeouts
  - Watchdogs
  - Fault handling
- `pinballctl` should:
  - Treat coils and high-current outputs as **dangerous**.
  - Avoid sending repeated rapid-fire commands that could bypass safety in buggy firmware.
  - Maintain clear state about:
	- Whether the system is ENABLED / DISABLED.
	- Fault conditions reported from the firmware.

When implementing or modifying code that interacts with coils or other high-power elements, **prefer being conservative and explicit**.

---

## 4. How AI (Codex) Should Behave

### 4.1 General Guidelines

- **Never silently discard or rewrite large sections of code.**
- Before large changes, **summarize the intent** and propose the approach.
- Prefer **incremental, reviewable changes**.
- Respect the existing structure where it’s reasonable; only introduce new layers/modules when there is a clear benefit.

### 4.2 File & Repo Operations

When asked to modify code:

1. Identify the relevant files.
2. Explain what you intend to do.
3. Show the diff or a summary of changes.
4. Apply changes only after user approval (if the workflow supports it).

Do **not**:
- Delete files without strong justification and clear explanation.
- Introduce new heavy dependencies casually (e.g., large frameworks) without user request.

### 4.3 Logging & Errors

- Use Python’s `logging` module with clear log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- For serial I/O and hardware communication:
  - Log connection/disconnection.
  - Log malformed messages and how they are handled.
  - Avoid crashing on transient serial errors; prefer robust recovery.

---

## 5. Serial & Protocol Expectations

(These may evolve; treat them as guiding principles rather than fixed facts.)

- Communication is **frames-only JSON**:
  - 4-byte big-endian length header
  - followed by UTF-8 JSON payload
- ESP32 emits framed responses/events; Pi sends framed JSON commands.
- Do not introduce newline-delimited command transport.

When altering protocol-related code:

- Keep backwards compatibility where possible.
- If breaking changes are necessary, clearly comment and version the protocol.

---

## 6. Testing & Reliability

- Prefer adding or preserving **unit tests** where they exist.
- For serial-daemon behavior:
  - Consider adding tests that simulate:
	- Device disconnect.
	- Garbled input from the ESP32.
	- Timeouts waiting for responses.

If tests do not yet exist:

- Suggest appropriate test locations and basic test scaffolding, but avoid creating huge test frameworks unprompted.

---

## 7. Things to Avoid

AI assistants working in this repo should **avoid**:

- Introducing cutting-edge or obscure dependencies unless specifically requested.
- Implementing complex meta-frameworks over the existing code.
- Making assumptions about hardware pinouts or coil wiring without explicit config/manifest data.
- Weakening safety behavior (e.g., removing checks around ENABLE/DISABLE, watchdogs, or coil timeouts).
- Editing generated/runtime data trees unless explicitly requested (e.g., `src/instance/**`, `dist/**`, build artifacts, `__pycache__`).

---

## 8. How to Treat This File

- This file is a **living contract** for AI behavior in `pinballctl`.
- It may be updated by the user to refine instructions.
- When in doubt, **prioritize safety, clarity, and maintainability** over “fancy” solutions.


## Update 1
The ESP32 firmware and Pi bridge protocol has been updated to be FRAMES-ONLY.

Summary of changes:

1) Communication model
- All Pi → ESP commands are now sent as framed JSON:
  - 4-byte big-endian length header
  - followed by UTF-8 encoded JSON
- Newline-delimited / line-based commands have been fully removed.
- ESP → Pi responses continue to use framed output (FramedSerial).

2) Bridge (Python)
- src/pinballctl/bridge/daemon.py
- _send_cmd() now ALWAYS:
  - JSON.dumps(payload, separators=(",", ":"))
  - UTF-8 encode
  - prepend struct.pack(">I", len(body))
  - write header + body (no newline)
- The _framed flag is no longer used or supported.

3) Firmware receive logic (ESP32)
- src/firmware/src/System.cpp
- LineCommandParser has been removed entirely.
- Firmware now implements a non-blocking, stateful framed receiver:
  - Reads 4-byte big-endian length header
  - Validates 1 ≤ length ≤ FramedSerial::kFrameMax (8192)
  - Reads payload incrementally across loop() calls
  - Calls protocol_.handleLine(payload) once a full frame is received
- No heap allocation is used; a static buffer sized
  FramedSerial::kFrameMax + 1 is used instead.

4) Protocol layer
- ProtocolHandler::handleLine(String payload) remains unchanged.
- New command supported:
  - {"cmd":"SET_RULES","rules":[...]}
  - ESP stores the rules payload and replies with:
    {"t":"RULES_STATUS","status":"ok"}

5) App rules module
- After saving rules.json, the API now enqueues:
  {"cmd":"SET_RULES","rules": rules}
- Rules are pushed immediately to the ESP after save.


The end game

1) The Pi is the authoring + orchestration layer
  •	Web UI lets you discover hardware, create rules, edit configs, and deploy.
  •	Pi persists:
  •	discovered hardware snapshot(s)
  •	UI-friendly rules (rules.json)
  •	an ESP-friendly compiled ruleset (eventually)
  •	Pi pushes updates to the ESP over the bridge (USB serial).

2) The ESP is the runtime / real-time rules engine
  •	ESP receives:
  •	hardware manifest / pin map
  •	compiled ruleset (or rules in chunks)
  •	config parameters (timeouts, coil safety, etc.)
  •	ESP processes:
  •	switch events / button presses
  •	timers / debouncing
  •	executes actions (coil fire/hold, LEDs, emit events back)
  •	ESP enforces safety:
  •	enable/arm requirement
  •	watchdogs and max pulse times
  •	fault states that require re-enable

3) The file flow you’re heading toward

Right now you have:
  •	UI rules file (human/editor-friendly):
  •	src/instance/rules/rules.json

What you’ll want next (end game):
  •	ESP deployed rules file (runtime-friendly):
  •	e.g. src/instance/rules/rules.compiled.json (or .bin)
  •	created by Pi by compiling/normalizing UI rules
  •	prunes UI-only fields (friendly, colors, tags, etc.)
  •	expands references (hardware sources → pin IDs)
  •	assigns compact IDs for speed

Then the bridge deploys that to the ESP:
  •	chunked transport
  •	optional hash/revision
  •	optional flash persistence on ESP (LittleFS)

4) Versioning / lifecycle

The end game also usually includes:
  •	ruleset_rev / sha256 tracked on both ends
  •	Pi can ask: GET_RULES_STATUS
  •	Pi only pushes if rev differs
  •	ESP can survive reboot with the same ruleset loaded from flash


Important constraints going forward:
- Do NOT reintroduce newline or line-based parsing.
- All new commands must use framed JSON.
- Changes should assume frames-only transport.
