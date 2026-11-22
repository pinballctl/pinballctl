# AGENTS: pinballctl

This file defines how AI assistants (like Codex) should behave when working in this repository.

---

## 0. Repository layout

- `src/pinballctl/webapp/` contains the Flask admin app, HTTP routes, templates and browser assets.
- `src/pinballctl/runtime/` contains the bridge, event ingress, rules, Game, Ball, Scoring, audio, lighting, media and packaged Godot player.
- `src/firmware/` contains the ESP32-S3 firmware.
- `src/instance/` holds machine-specific and generated data.
- `media/backglass/` holds the editable backglass example. `media/website/` holds the published documentation sources.
- `utils/` contains project build and maintenance commands. Tests are under `tests/`.

---

## 1. Project Overview

Pinball CTL is a homebrew pinball controller stack for a Raspberry Pi and an ESP32-S3. The browser is the administration interface. The Pi runs machine logic and presentation, and the ESP handles real-time I/O and coil safety.

---

## 2. Architecture

- **Webapp.** The Flask factory in `src/pinballctl/webapp/__init__.py` loads feature blueprints from `webapp/modules/`. Gunicorn serves the admin UI and APIs for authoring, status, diagnostics and deployment.
- **Runtime.** Reusable services live under `src/pinballctl/runtime/` and must be usable with the webapp stopped. The serial bridge in `runtime/bridge/daemon.py` owns the USB connection, framed commands, reply correlation, heartbeat and event ingress. Game, Ball, Scoring and host rule processing use the runtime's shared event path. The Godot supervisor in `runtime/media/godot_daemon.py` provides display autoplay and a private loopback interface for scene events and leaderboard requests.
- **Service boundaries.** On systemd, `pinball-web.service` runs Gunicorn. `pinball-runtime.target` groups `pinball-bridge.service` and `pinball-media.service`. Unit definitions live in `runtime/ops/service.py`. Manual CLI start, reload and stop support `--web-only` for managing Gunicorn independently.
- **ESP32-S3.** The controller reads switches and sensors, runs supported local rule actions and drives mapped outputs. Coil arming, PIN Safe, cooldown, watchdogs, output limits and latched faults are enforced in firmware.

---

## 3. Coding & Design Conventions

### 3.1 General Style

- Prefer **clear, explicit code** over overly clever shortcuts.
- Avoid introducing unnecessary abstractions or generic frameworks.
- When in doubt, optimize for **maintainability and debuggability**.

### 3.2 Python

- Target Python 3.11 or later, as declared in `pyproject.toml`.
- Use the `logging` module in production paths and type hints where they clarify public functions.
- Use a virtual environment and avoid hard-coded paths.
- Keep HTTP validation and presentation in the webapp. Share event routing, compilation, device communication and other machine operations through runtime modules.

### 3.3 Web / Flask

- Use the existing Flask Blueprints for feature pages and APIs.
- Keep routes small and focused.
- JSON responses should be explicit and stable (no surprise structure changes without good reason).

### 3.4 Protocols & Safety

- The ESP32 firmware is the ultimate safety gate for:
  - Coil timeouts
  - Watchdogs
  - Fault handling
- Treat coils and high-current outputs as dangerous. Keep output requests subject to the firmware's safety limits.
- The ESP arms automatically when its configuration, runtime and heartbeat checks pass. A heartbeat timeout disarms to PIN Safe. Fresh heartbeats can restore eligibility. Latched firmware faults require a reset.
- Report firmware arming and fault state separately from each coil's configured **Coil operation** setting.

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

## 5. Serial protocol and Rules Sync

### Serial framing

Use frames for all Pi–ESP traffic. A four-byte unsigned big-endian length precedes the payload. Untyped commands carry UTF-8 JSON. Negotiated v2 frames include a type byte in the length, with type 1 for JSON, 2 for binary blob data and 3 for diagnostic text. Keep newline-delimited commands out of the serial transport.

The bridge sends commands through `runtime/bridge/daemon.py`. `src/firmware/src/System.cpp` incrementally receives frames and enforces the `FramedSerial` payload limit. Correlate explicit replies using `reqId`, and handle unsolicited events and heartbeat status independently. Preserve compatibility where possible and version protocol changes.

### Save and deploy rules

1. **Save** validates and normalizes the authored rules in `webapp/modules/rules/api.py`. It persists `src/instance/rules/rules.json` and compiles a local `rules.pd` with metadata. Saving changes only the Pi files.
2. **Rules Sync** checks the connected bridge and firmware compatibility, rebuilds `rules.pd` and includes manager input watches. The shared compiler lives in `runtime/ops/rules_blob.py`.
3. The bridge queues an immutable blob snapshot, then transfers it with `BLOB_BEGIN`, binary chunks and `BLOB_END` to `/cfg/rules.pd` on the ESP. Confirm the firmware's `RULES_APPLY` result and manifest update before treating the deployment as complete. The ESP loads the stored blob from LittleFS on boot.
4. Rules runtime v3 lets one authored rule run eligible hardware actions on the ESP and host actions on the Pi from the same event. Rules requiring Pi-side conditions or trigger history wait for the Pi's decision. Any resulting output request still passes the ESP's freshness and coil safety checks. Keep input watches for host-evaluated rules and manager observations.

Hardware mapping and lighting have their own sync flows. See [App layout and services](media/website/docs/technical-notes/app-layout.md), [Bridge Protocol](media/website/docs/technical-notes/bridge-protocol.md) and [Coil Safety](media/website/docs/technical-notes/coil-safety.md).

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
- Weakening safety behavior (e.g., bypassing arming checks, watchdogs, or coil timeouts).
- Editing generated/runtime data trees unless explicitly requested (e.g., `src/instance/**`, `dist/**`, build artifacts, `__pycache__`).

---

## 8. How to Treat This File

- This file is a **living contract** for AI behavior in `pinballctl`.
- It may be updated by the user to refine instructions.
- When in doubt, **prioritize safety, clarity, and maintainability** over “fancy” solutions.


## Website and documentation maintenance

- The project owner authorises documentation changes to be committed and pushed automatically after validation. This overrides the default stage-only workflow for documentation and its necessary navigation, link and asset updates. Commit only the completed change; preserve unrelated application, firmware, engineering and unfinished documentation work. Use the existing branch/remote workflow without force-pushing or amending, and verify GitHub Pages after a deployment.
- Treat website and documentation updates as part of feature work. Whenever a feature is added, changed, or removed in the application, bridge, firmware, or backglass, review and update the affected documentation and website content in the same change.
- Keep technical guides in `media/website/docs/` accurate for setup, configuration, behaviour, limitations, and safety requirements. Keep the marketing content in `media/website/` aligned with the actual capabilities, with technical detail linked to the relevant `/docs/` pages.
- Keep current development instructions in `media/website/docs/developer-guide/` and key project topics in `media/website/docs/developer-notes/`. Use one maintained page per topic, such as Test Bench; do not recreate a dated Developer Log, tag system or public changelog. Keep root/component READMEs as short signposts. Test-bench documentation belongs here too; keep reviewed images in `media/website/assets/docs/media/` and preserve current engineering sources in `media/website/design/test-bench/`. Do not recreate the retired top-level `docs/` directory.
- Record all key project discussions and decisions in the relevant Developer Notes page as part of the related work. Include alternatives considered, the current decision and rationale, evidence, validation limits and next steps. Update the topic page as decisions change, retaining useful context and dates where they explain the design. This authorises public-safe project summaries, not publication of raw private chats, briefs, logs or configuration.
- Never publish personal information, passwords, API/access keys, tokens, private keys, credentials, private account/order details or identifying machine data in documentation or log entries. Review prose, examples, links, screenshots, diagrams and embedded metadata before staging public content. Use neutral descriptions and clearly fictional placeholders; omit sensitive material rather than copying it into a public summary. Keep the engineering source records intact unless their modification is part of the approved task.
- Refresh affected screenshots using the existing screenshot utilities when visible UI changes make them outdated. Update relevant navigation, feature listings, and links when features are added, renamed, or removed.
- Edit source content and shared templates/styles, not generated `dist/` files. Apply layout changes consistently through the shared website system.
- For website or documentation changes, run `media/website/utils/build-site.py` with the project Python environment. It runs `media/website/utils/check-site.py` on temporary output before cleanup. Use `--preview` for a local preview that cleans up on exit. CI uses `--output build/site`, checks it, uploads the artifact and removes `build/site` even if the job fails. Do not use `dist/` for website output or remove unrelated build/package files. Check affected layouts at desktop and mobile widths when presentation changes.
- Include documentation/website updates and validation in the handoff. If no public-facing update is needed, briefly explain why; if an update is blocked, identify what remains instead of silently leaving it stale.

## Personal-name privacy

- Do not include the project owner's personal name in repository content, public issues, commit messages, generated documentation or other public-facing project material. Use neutral wording such as "the project owner" or "the user".
