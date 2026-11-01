# Rules Wizard

<img src="./media/screenshot-feature-rules-wizard.webp" data-source='{"url":"/login","next_url":"/rules/","dark_mode":true,"settle_ms":600,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#rules-wizard-open","wait_for":"#wizard-content .wizard-tile"}]}' alt="Rules Wizard catalogue in the existing right sidebar" style="width:100%;height:auto;">

The **Wizard** button on Rules opens a searchable catalogue in the same style of right-hand sidebar as the rule editor. Filter by category, select a wizard, answer its questions, then preview the exact rules before choosing **Create rules**. Back preserves visible answers; changing an earlier answer removes answers and generated actions that are no longer relevant. Close preserves your answers until the page is reloaded. Save existing Rules drafts before opening the wizard.

Creation adds independent ordinary rules to the existing Rules list. It does not create a rule hierarchy, modify Scoring settings, enable outputs, or sync to the ESP. Every new rule is **disabled**. Open Rules, review each trigger, condition, action and tag, then explicitly enable, save and sync when ready. Delete unwanted generated rules through the normal editor. Generated rules have the `Wizard` tag; their counters and flags have unique names per creation. Their origin note is informational, with no ongoing dependency on a definition file.

The catalogue includes 166 candidate behaviours plus a Bumper hit reward example: **26 available definitions and 141 unavailable definitions**. Unavailable entries show the prerequisites and cannot create rules. Availability means the authoring path is supported, not that a connected machine has been physically tested. Ball management, player turns, cancellable timers, arbitrary coil mechanisms and direct points awards are not invented by wizard names. Several narrowly scoped sensor/flag/counter wizards only emit an event: read their warnings and exact preview.

## Bumper hit reward

Choose a mapped switch/button, hits per reward and the event that resets its counter. Optionally select existing Audio and Lighting scenes; answering No removes both the selector and the associated action. The generated rules increment a unique counter, check its threshold, emit `BUMPER_REWARD_REQUESTED`, run selected effects and reset the counter. A separate reset rule runs on your chosen event, normally `GAME_STARTED`.

This counter is global, not per player, and persists until reset. Configure points separately in **Scoring** for `BUMPER_REWARD_REQUESTED`; this wizard does not award points by itself. Reset events need a real producer. Preview explicitly shows these limitations. Effects use existing cue/scene settings; the wizard does not create media assets or change their duration, looping or stop behaviour.

## Counters, flags and named choices

Counter and flag selectors default to **Create new**. You can instead select an existing value to reuse it without resetting it. Preview shows the new value's friendly name and starting value; it creates nothing. **Create rules** saves a uniquely identified counter starting at **0**, or flag starting as **false**, together with the generated rules. New values and their friendly names persist across restarts and are available to later wizards. Hidden optional fields do not create state.

A newly created counter only increases if a rule includes an increment action; a flag only changes when a rule or event sets it. Threshold/monitor wizards keep their stated behaviour rather than inventing events or changing an existing value. Media, Lighting and Audio choices and the preview summary display friendly names; internal IDs remain in the exact JSON preview.

## Compatibility and safety

Both Pi and ESP need the version 2 rules runtime. A connected ESP reporting an older version blocks preview and creation. Disconnected authoring can create disabled drafts; the normal Rules sync compatibility check still applies. No physical Pi/ESP integration test is implied by desktop validation. Verify event timing, sensor polarity, reset behaviour and release/fault handling on the target before gameplay.

The initial compiler deliberately refuses raw `pulse`, `set_output`, pixel targeting and unsupported action parameters. Output/coil field types are reserved selectors with no available targets. Mechanism and safety candidates stay unavailable until a device-aware generator can validate real mapping, driver, pulse/hold limits and interlocks. Logical flags do not arm or disarm ESP safety.

Available primitives include flags, counters, grouped conditions, elapsed-time comparisons, mapped button/switch events, custom/system events and existing audio/lighting/media scenes. An elapsed-time condition checks when an event arrives; it does **not** schedule a timer. NFC, random selection, per-player state, automatic ball search, new device drivers and game/mode services are not provided by the wizard engine.

## Installing a JSON definition

Bundled definitions are packaged under `pinballctl/app/modules/rules/wizards/bundled/`. Place user definitions in **the installation's instance directory** at `wizards/user/*.json`. New files are discovered when the catalogue opens; no application code change or restart is required. Do not put files in the source tree of a deployed installation. Files are untrusted data and cannot contain HTML, JavaScript, Python, shell commands, expressions, dynamic imports or network resources.

The structural JSON Schema is `pinballctl/app/modules/rules/wizards/schema-v1.json`. The compiler additionally checks references, ordered dependencies, runtime support and current machine objects. Unknown properties fail closed. Schema v1 optionally accepts `illustration: {"asset":"rules-flow","alt":"Descriptive text"}`. This maps to a vetted, bundled SVG; arbitrary paths, URLs and executable extensions are rejected. Icon names come from a small allowlist rendered by bundled SVGs, so every wizard has a visible icon without depending on an optional font glyph. Icons remain decorative beside text labels. Upgrading schema versions requires an explicit compiler migration; versions are never silently converted.

Each file is limited to 128 KiB, nesting depth 20, 20 steps, 30 fields per step, 50 generated rules and 200 entries per array. Discovery considers up to 500 files per directory. Symlinks and directories escaping the instance root are rejected. Duplicate IDs disable **all** conflicting definitions, including bundled/user conflicts, rather than silently overriding one version. Diagnostics are returned by `GET /api/rules/wizards` with the file name and reason.

Metadata includes `schemaVersion: 1`, a namespaced `id` such as `user.lane-reward`, `name`, `description`, `category`, an allowed `icon`, `version` and `minimumAppVersion` in major.minor.patch format, `minimumRuntimeVersion`, `availability`, `prerequisites`, `steps` and `rules`. Optional `author`, `warnings` and `tags` are text/list metadata. Unavailable definitions require concrete prerequisites and an empty rule list.

### Questions and conditions

A step has `title`, optional `description` and `when`, and a `fields` array. A field has a unique `id`, `label`, `type`, optional `default`, `required` (defaults to true), `min`, `max`, `help`, `icon`, `options` and `when`.

Supported field types are `boolean`, `radio`, `select`, `multi-select`, `integer`, `number`, `duration` (milliseconds), `text`, `event`, `input`, `switch`, `sound`, `lighting`, `media`, `flag` and `counter`. `radio` is rendered as an accessible single-choice select in v1. Reference selectors bind to actual current objects; `flag` and `counter` also accept the reserved `__wizard_create_new__` answer, which is their default unless the definition explicitly supplies another default. New references are bound to a unique value per creation; input references resolve their mapped event name on the server. Events are explicit uppercase names, not evidence that a producer exists. Numeric defaults are bounded to 0–2147483647 unless narrower limits are provided. Empty optional fields are omitted.

A predicate uses an allowlisted `op`: `eq`, `ne`, `in`, `gt`, `gte`, `lt`, `lte`, `exists`, `all`, `any` or `not`. For example:

```json
{"op": "eq", "field": "soundOn", "value": true}
```

`all`/`any` use an `items` array; `not` uses one `item`. Predicates may reference **earlier** fields only, preventing cycles and forward dependencies. Step visibility is evaluated before its fields. Hidden values are removed server-side, even if a client submits stale answers.

### Rule templates

Templates use the normal Rules schema. A complete JSON value `{"$answer":"sound"}` substitutes a typed answer, preserving numbers and booleans without string interpolation. `{"$local":"HITS"}` creates a unique uppercase local counter/flag identifier shared across that wizard's generated rules. State actions must use a private `$local` or a value chosen through a typed existing flag/counter selector; raw global state names are rejected. This is the only local-reference mechanism; there is no arbitrary expression language or executable formatting.

Any ordinary template object can contain `$when` with a predicate. A false predicate omits that object, including an entire rule, trigger, condition group or action. An unconditional reference to a hidden/missing answer is an error. Generated rules must retain at least one trigger and action. Unknown conditions/actions, unsafe hardware output adapters and stale references are rejected. Do not create feedback loops; direct self-triggering events are rejected and the runtime's event-chain limit remains in force.

Use the bundled Bumper hit reward definition as a complete example. All available bundled definitions have generation tests; their preview output is designed to round-trip through the existing Rules editor.

## API and concurrency

Authenticated application endpoints:

- `GET /api/rules/wizards`: definitions, available machine choices and validation diagnostics.
- `POST /api/rules/wizards/preview`: `{id, answers}` for exact generated rules and a signed, 30-minute preview token. `{id, answers, partial: true}` returns currently visible steps and cleaned answers without creating rules.
- `POST /api/rules/wizards/create`: `{token}` creates the reviewed, disabled rules only if the definition, current rules and referenced objects still match the preview. A changed configuration requires another preview. Replaying a successful token cannot create duplicate rules.
- `GET /api/rules/wizards/export/<id>`: portable definition JSON.
- `POST /api/rules/wizards/import`: validate and install definition JSON with a new unique ID; existing definitions are never overwritten. Import/export are advanced API/file workflows, not a visual template editor.

Creation locks the Rules store, compiles all output before publishing and restores prior files on an exception. The ordinary Save endpoint uses the same authoring lock. `rules.json` remains authoritative; no runtime or hardware operation occurs during creation. Preview revision checks protect against a stale wizard overwriting another editor. Filesystem/process failure during multi-file publication still requires the normal Rules recompile/sync recovery; this is not a transactional database across three artifacts.

There is no automatic bulk undo that could remove rules edited after creation. Delete generated rules individually in the existing Rules list. They remain independent after export/import, deletion of the definition or upgrades.
