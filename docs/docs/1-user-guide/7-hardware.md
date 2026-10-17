# Hardware

Hardware is the feature for physical I/O mapping and controller integration setup.

It manages pin-level mapping, safety defaults, friendly names, and function assignment. The assigned function will define how this pin behaves and the options available throughout the Pinball CTL application.

<img src="./media/screenshot-feature-hardware.webp" data-source='{"url":"/login","next_url":"/hardware","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Hardware feature overview" style="width: 100%;height: auto;">

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

- If mapping is not synced, the sync action shows the orange warning state.
- If mapping is synced, the sync action shows the blue disabled OK state.


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
- [Rules](7-rules.md)
- [Lighting](8-lighting.md)
