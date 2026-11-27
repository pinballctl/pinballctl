# Hardware

Use **Hardware → Mapping** to name connections and assign their functions. Save the mapping on the Pi before syncing it to the ESP. Use **Hardware → Test** to check inputs and outputs directly, without rules.

## Before you start

Have a connected compatible ESP, the correct board pin map and a safely wired input. Keep coil/high-current supply power disconnected.

<span id="map-and-verify-one-input"></span>

## Map and verify inputs

1. Choose **Reload Pins** with the ESP connected. Match board/channel and UID to the actual connection. **Expected:** you can identify the intended pin without guessing.

2. Give the pin a friendly name and select its function. Check its settings, including polarity and supported input options. **Expected:** the function matches the circuit rather than merely the desired gameplay role.

3. Choose **Save Changes**, then **Sync to ESP**. Read validation and transfer results. **Expected:** the saved mapping is deployed successfully.

4. Open **Test** and operate the input. **Expected:** the live level changes on press and release, and the hit count increments.

5. For an output, open the driver settings with load power off. Set safe state and appropriate pulse/hold/cooldown limits before saving and syncing. **Expected:** explicit settings exist for the actual driver and load; powered validation is still required.

<img src="./media/screenshot-feature-hardware.webp" data-source='{"url":"/login","next_url":"/hardware","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Hardware Mapping tab showing pin defaults, assigned functions and drivers" style="width: 100%;height: auto;">

1. UID and board/channel identify the circuit. 2. Friendly Name and Function identify its software role. 3. Save Changes persists edits; Sync to ESP deploys them.

## Check the result

Use names that describe the machine, such as a target or cabinet button, while preserving UID identity. Reserved pins are hidden for a reason; Show all Pins does not make them safe to reassign.

For mapped buttons, use **Safe / Idle** to select **LOW** (pull-down, pressed HIGH), **HIGH** (pull-up, pressed LOW), or **AUTO** (pull-up, sample the resting level at startup). Existing mappings use AUTO until an idle level is selected. Explicit levels require firmware v0.0.15 or later. Save and sync the hardware mapping once. The ESP restores the saved setting from flash before waiting for USB, and **Reload** samples the button without changing its pull direction. External circuitry can override the internal pull and determines the level before firmware starts.

For coils, the ESP loads the saved electrical OFF levels before waiting for USB. The coil driver circuit still needs to stay off during power-up and reset, before firmware takes control.

**Safety:** Never attach high-current loads directly to GPIO. Use suitable driver stages, fuses and flyback protection, and a physical power cutoff. Do not copy sample pulse or duty values to a different coil.

## Troubleshooting

When a saved mapping is carried over to a different controller ID, Hardware matches the saved pins and their linked partners by board, pin type and channel. Verify those assignments match the replacement board before syncing.

For a silent input, check connection, actual channel, polarity, saved mapping and sync before changing Rules. For an output fault, remove load power and inspect the circuit/limits; do not repeat rapid pulses to diagnose it.

## Related guides

Next: [Events in Logs](logs.md#find-and-inspect-an-event), [Rules](rules.md), [ESPLink](esplink.md), [Troubleshooting](troubleshooting.md).

## Hardware controls

The mapping gives each input and output a name and a function. Rules use it to find triggers and action targets, and Lighting uses it to associate pins with fixtures. These tools can use the saved mapping on the Pi while the ESP is disconnected.

Use **Reload Pins** with the ESP connected during initial setup or after a hardware change. It refreshes the controller’s pin list and discovers additional pins or expansion modules where supported. **Show all Pins** reveals entries that are normally hidden so you can inspect them.

The **Unsaved changes** badge appears after you edit the mapping. Select **Save Changes** to validate and save your edits on the Pi, then select **Sync to ESP** to deploy them to the controller. If you try to sync while edits are pending, Hardware prompts you to save first. Check the progress and result before testing.

### Mapping Table Columns

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
        <td>Configured default (High/Low), or the last discovery sample when no default is set.</td>
      </tr>
      <tr>
        <td nowrap="nowrap">PIN Safe</td>
        <td>Electrical off level applied by firmware when an output is inactive. Configured coils are held at this level while disarmed.</td>
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

For a coil, open its driver settings to find **Coil operation**. It defaults
to **Disabled**. An enabled coil can respond to rules after the ESP arms
automatically. The **Coil safety** badge above the table shows the ESP's
reported state and any latched fault. [Coil Safety](../technical-notes/coil-safety.md) · [Coil operating modes](../technical-notes/coil-operating-modes.md)

### Show All Pins Toggle

`Show all Pins` displays normally-hidden reserved/limited pins.

Default view filters to safer, mappable pin rows.

### Sync to ESP

The Sync button indicates whether the configuration is in sync with the ESP.

- A green outline means the saved configuration differs from the ESP and needs syncing.
- The button stays muted while checking status or when already in sync.


### Reload Pins

`Reload Pins` refreshes discovered pin set from ESP source.

Use when:

- firmware pin definitions changed
- hardware board changed
- UID/channel set needs refresh

### Practical Setup Examples

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

- [ESPLink](esplink.md)
- [Rules](rules.md)
- [Lighting](lighting.md)

### Driver settings panel

Select the settings button beside a configured driver to open its options in the right-hand panel. The pin context stays visible at the top; labels, units and safety guidance accompany each field. Scroll within the panel to reach longer configurations, then close it to return to the mapping table. Use **Save Changes** on the Hardware page to persist edits, and **Sync to ESP** to deploy them. Opening the panel alone does not change coil settings or arm outputs.

## Test wiring without rules

With the game idle, save and sync the mapping, then open **Hardware → Test**. The table lists the mapped devices on the ESP with the actions supported by each driver.

<img src="./media/screenshot-feature-hardware-test.webp" data-source='{"url":"/login","next_url":"/hardware/","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#hardware-test-tab","wait_for":"#hardware-test-devices tr"}]}' alt="Hardware Test tab showing example live input levels, hit counts, and driver-specific test buttons" style="width: 100%;height: auto;">

Green means **High**, red means **Low**, and grey means the level is unavailable or the driver reports another kind of state. When the ESP is unavailable, the tab shows the last saved mapping with controls disabled. Live monitoring reconnects automatically while the Test tab is visible. Refreshing keeps the selected Hardware tab. If a connected ESP does not answer test requests, verify the firmware version in **ESPLink**.

| Device | Wiring check |
| --- | --- |
| Button or switch | Press and release the physical switch and check its High/Low level. Watch the hit count and the brief outline for quick taps. For an AUTO input, leave the switch at rest when opening the tab so the test can establish its idle level. |
| Single LED or lamp | Use **On** and **Off**, or press and hold **Hold**. The dot shows the level read at the ESP pin. Check the lamp itself to confirm the load responds. |
| RGB strip | Use **Flash** to run two short flashes. The test uses the pixel count in the ESP's applied lighting configuration, or tests the first pixel if no fixture has been synced. |
| Coil | Use **Pulse** for a single configured pulse. The ESP still requires an enabled, armed coil with a valid configuration and applies its existing limits and cooldown. |
| LCD display | Use **Show text** and check for the test message on the display. |
| Accelerometer | Move or tap the sensor and watch the three live axes. |

The ESP pauses rule actions and lighting playback during the test. Switching to **Mapping**, hiding the browser tab or leaving the page stops live updates. If the browser or link drops, the device times out the session and returns any test outputs to idle. **PIN State** on the Mapping tab shows the configured default or the discovery sample when no default has been set.
