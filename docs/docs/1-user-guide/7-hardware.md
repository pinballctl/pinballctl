# Hardware

Turn physical switches and outputs into named devices that Rules can use. First establish an input you can observe; configure powered outputs only after verifying their driver and safety limits.

## Before you start

Have a connected compatible ESP, the correct board pin map and a safely wired input. Keep coil/high-current supply power disconnected.

## Try it step by step

1. Choose **Reload Pins** with the ESP connected. Match board/channel and UID to the actual connection. **Expected:** you can identify the intended pin without guessing.

2. Give the pin a friendly name and select its function. Check its settings, including polarity and supported input options. **Expected:** the function matches the circuit rather than merely the desired gameplay role.

3. Choose **Save Changes**, then **Sync to ESP**. Read validation and transfer results. **Expected:** the saved mapping is deployed successfully.

4. Operate the input and inspect its event name/source in Logs. **Expected:** the intended press/release or open/closed event follows the physical input.

5. For an output, open the driver settings with load power off. Set safe state and appropriate pulse/hold/cooldown limits before saving and syncing. **Expected:** explicit settings exist for the actual driver and load; powered validation is still required.

<img src="./media/screenshot-feature-hardware.webp" data-source='{"url":"/login","next_url":"/hardware","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Hardware feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. UID and board/channel identify the circuit. 2. Friendly Name and Function identify its software role. 3. Save Changes persists edits; Sync to ESP deploys them.

## Helpful checks

Use names that describe the machine, such as a target or cabinet button, while preserving UID identity. Reserved pins are hidden for a reason; Show all Pins does not make them safe to reassign.

**Safety:** Never attach high-current loads directly to GPIO. Use suitable driver stages, fuses and flyback protection, and a physical power cutoff. Do not copy sample pulse or duty values to a different coil.

## If the result is different

For a silent input, check connection, actual channel, polarity, saved mapping and sync before changing Rules. For an output fault, remove load power and inspect the circuit/limits; do not repeat rapid pulses to diagnose it.

## Continue your build

Next: [Events](27-events.md), [Rules](7.1-rules.md), [ESPLink](11-esplink.md), [Troubleshooting](26-troubleshooting.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Feature Does

Hardware defines machine I/O in a structured form used by:

- Rules trigger/action targeting
- Lighting cast and fixture context
- ESP deployment and runtime mapping

<div class="manual-note">
  <p class="manual-note-title">Please Note</p>
  <p>The ESP must be connected to refresh pins. Once pin assignment is complete, other modules can use this mapping and run headless when the ESP is not connected.</p>
</div>

## Top Controls

- `Reload Pins` - On first setup and hardware changes run this to update the hardware database. Where possible we are able to auto detect additional pins and modules.
- `Sync to ESP` - Any changes to pin defaults will need syncing back to the ESP
- `Save Changes` - After making any changes in the page, make sure to save them

Behaviour:

- unsaved changes show an `Unsaved changes` badge
- save/sync flows include validation and progress states
- sync may request save first when local edits are pending

## Mapping Table Columns

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th nowrap="nowrap">Column</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td nowrap="nowrap">UID</td>
        <td>Unique identifier for this hardware pin (controller + board + type + channel).</td>
      </tr>
      <tr>
        <td nowrap="nowrap">Board</td>
        <td>Physical board or expansion module hosting this pin.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">Type</td>
        <td>Hardware category for the pin (GPIO, I2C device, LED driver, etc.).</td>
      </tr>
      <tr>
        <td nowrap="nowrap">Channel</td>
        <td>Pin number or channel identifier on the board.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">PIN State</td>
        <td>Current observed pin level (High/Low) when available.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">PIN Safe</td>
        <td>Safe state applied when the system is inactive. This defines whether the pin is forced HIGH or LOW on boot, disconnect, or fault.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">Friendly Name</td>
        <td>Human-friendly label used across the UI and rules.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">Function</td>
        <td>Select the logical role for this pin (button, solenoid, LED, etc.). Used by the controller to map behavior and safety rules.</td>
      </tr>
    </tbody>
  </table>
</div>


## Show All Pins Toggle

`Show all Pins` displays normally-hidden reserved/limited pins.

Default view filters to safer, mappable pin rows.

## Sync to ESP

The Sync button indicates whether the configuration is in sync with the ESP.

- A green outline means the saved configuration differs from the ESP and needs syncing.
- The button stays muted while checking status or when already in sync.


## Reload Pins

`Reload Pins` refreshes discovered pin set from ESP source.

Use when:

- firmware pin definitions changed
- hardware board changed
- UID/channel set needs refresh

## Practical Setup Examples

### Initial machine mapping

1. Reload Pins.
2. Name each relevant pin.
3. Assign function roles.
4. Save Mapping.
5. Sync to ESP.

### Safety-first output setup

For output-capable pins:

- set clear Friendly Name
- assign correct output function
- define PIN Safe state for boot/fault behaviour

## Related Features

- [ESPLink](11-esplink.md)
- [Rules](7.1-rules.md)
- [Lighting](8-lighting.md)

## Driver settings panel

Select the settings button beside a configured driver to open its options in the right-hand panel. The pin context stays visible at the top; labels, units and safety guidance accompany each field. Scroll within the panel to reach longer configurations, then close it to return to the mapping table. Use **Save Changes** on the Hardware page to persist edits, and **Sync to ESP** to deploy them. Opening the panel alone does not change coil settings or arm outputs.
