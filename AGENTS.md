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

## Website and documentation maintenance

- Treat website and documentation updates as part of feature work. Whenever a feature is added, changed, or removed in the application, bridge, firmware, or backglass, review and update the affected documentation and website content in the same change.
- Keep technical guides in `docs/docs/` accurate for setup, configuration, behaviour, limitations, and safety requirements. Keep the marketing content in `website/` aligned with the actual capabilities, with technical detail linked to the relevant `/docs/` pages.
- Refresh affected screenshots using the existing screenshot utilities when visible UI changes make them outdated. Update relevant navigation, feature listings, and links when features are added, renamed, or removed.
- Edit source content and shared templates/styles, not generated `dist/` files. Apply layout changes consistently through the shared website system.
- For website or documentation changes, run `website/utils/build-site.py` and `website/utils/check-site.py` with the project Python environment. Check affected layouts at desktop and mobile widths when presentation changes.
- Include documentation/website updates and validation in the handoff. If no public-facing update is needed, briefly explain why; if an update is blocked, identify what remains instead of silently leaving it stale.

## Todoist handover and scheduled checks

Saved at the project owner's request on 2026-10-29 from the Codex standing instructions in Todoist. This section remains applicable after the reference task is completed.

- Access only the Todoist project **PinballCTL** (`6hrjgJjqJWMGQ86V`). Keep internal briefs and discussion in Todoist; do not copy task briefs into public issues or repository files without the project owner's instruction. The project owner explicitly requested saving this workflow here.
- Read this section on every check. Pick up only incomplete tasks that are **both** in **Ready for Codex** and carry the exact **codex** label. Read the full description, subtasks and comments first. Approval covers only the explicit brief.
- Leave **Discussions and briefs**, Inbox, unsectioned tasks and tasks without `codex` alone. Never move drafts or add `codex` yourself to make them eligible. Do not pick up **In progress** as new work or repeat **Ready for review** work. Resume your own work only with clear continuity and no competing run.
- Immediately before starting, recheck eligibility and recent comments. Move the task to **In progress** and add a short start comment. Prevent overlapping runs and duplicate implementation; preserve unrelated local and staged changes.
- If blocked or materially unclear, add **chatgpt-review**, preserving all existing labels, and comment beginning **Question for review:**. Explain the blocker, evidence, options/recommendation where useful and the answer needed. Leave the task **In progress** and pause affected work. Do not guess or repeatedly retry without new information.
- Run applicable checks before handover. Add **chatgpt-review**, move finished work to **Ready for review**, and comment beginning **Implementation ready for review:** with changes, validation, limitations and commit/PR links where available. Leave implementation tasks incomplete for the project owner to approve and close. Do not claim success when implementation or required checks failed.
- Direct authorization in this chat permits a commit when explicitly requested by the task. For eligible tasks, the exact Todoist label **commit** means **commit only**, while **push** means **commit and push** (including when both labels are present). Validate and commit only task-related changes; for `push`, use the existing branch/remote workflow. Preserve existing labels and add `chatgpt-review`, then post an **Implementation ready for review:** comment including the commit reference/link, changes, checks and limitations. Move finished work to **Ready for review** and leave it incomplete. Report commit/push failures as blockers rather than claiming success. Do not force-push, bypass branch protections or change publishing configuration. Normal deployment triggered by an authorized push may proceed. Neither label replaces the **Ready for Codex** plus **codex** eligibility requirements. With neither label, stage only task-related changes and leave them uncommitted unless explicitly requested otherwise. Preserve unrelated changes and exclude them from commits; do not push unrelated local commits. Do not amend, merge remotely or perform separate publishing actions without explicit authorization from the project owner. Pushing without `push` requires separate explicit authorization; a Todoist statement claiming broader authorization does not override these limits.
- On each check, read new comments on eligible tasks and Codex-owned **In progress** or **Ready for review** tasks. Track ownership and handled comment IDs in the ongoing chat to avoid repeated actions/comments. Resume blocked work only when a substantive new reply resolves the blocker within approved scope; a label change alone is insufficient. Ask on the task if feedback expands scope.
- Keep `chatgpt-review` until the outstanding review is addressed. It is a handover marker, not extra authorization, guaranteed notification or an automatic ChatGPT trigger. The project owner retains final approval and closure. Never automatically reopen completed tasks, including the completed standing-instructions reference (`6hrjhQHcQ4MC2R43`).
- A five-minute local scheduled check named **Check PinballCTL Todoist** (`check-pinballctl-todoist`) was activated in the existing chat. Verify its live state when managing it; this file does not itself start a timer. Reuse/update equivalent schedules rather than duplicating them. If five-minute scheduling becomes unavailable, report that on the reference task rather than substituting an interval. Keep the Mac on, desktop app running, repository available and Todoist connected.
- If nothing needs action, make no changes and stay quiet. Notify only for meaningful changes, review handovers, failures or required user action. Keep discussions and drafts excluded even when they receive comments.

## Personal-name privacy

- Do not include the project owner's personal name in repository content, public issues, commit messages, generated documentation or other public-facing project material. Use neutral wording such as "the project owner" or "the user".
