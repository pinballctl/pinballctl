# Supported Components

This page tracks hardware and platform support for Pinball CTL.

At this stage, support is naturally based on the equipment used during development and testing.

## Support Levels

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Status</th>
        <th>Meaning</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>✅ Supported</td><td>Used and verified in this project</td></tr>
      <tr><td>⚠️ Limited</td><td>Partially tested or expected to work, but not fully validated</td></tr>
      <tr><td>❓ Unknown</td><td>Not tested yet</td></tr>
    </tbody>
  </table>
</div>

## Core Platform

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Component</th>
        <th>Status</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Raspberry Pi 5</td><td>✅ Supported</td><td>Main runtime platform</td></tr>
      <tr><td>Raspberry Pi OS (64-bit)</td><td>✅ Supported</td><td>Recommended for Pi 5</td></tr>
      <tr><td>macOS (development host)</td><td>✅ Supported</td><td>Used for development workflow</td></tr>
      <tr><td>Other Linux distributions</td><td>⚠️ Limited</td><td>Likely workable but not formally tested</td></tr>
      <tr><td>Windows development host</td><td>❓ Unknown</td><td>Not validated yet</td></tr>
    </tbody>
  </table>
</div>

## Control Hardware

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Component</th>
        <th>Status</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>ESP32-S3 board used by this project</td><td>✅ Supported</td><td>Primary real-time controller</td></tr>
      <tr><td>Other ESP32 variants</td><td>⚠️ Limited</td><td>May require firmware/protocol adjustments</td></tr>
      <tr><td>USB serial bridge (Pi &lt;-&gt; ESP32)</td><td>✅ Supported</td><td>Required for normal operation</td></tr>
    </tbody>
  </table>
</div>

## I/O Expansion and Devices

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Component</th>
        <th>Status</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>MCP23017 I2C expanders</td><td>✅ Supported</td><td>Used in current hardware stack</td></tr>
      <tr><td>Basic switches/buttons</td><td>✅ Supported</td><td>Via mapped input flow</td></tr>
      <tr><td>Solenoids/coils</td><td>✅ Supported</td><td>Safety controls expected on ESP side</td></tr>
      <tr><td>RGB strips (configured in mapping)</td><td>✅ Supported</td><td>Supported in current lighting flow</td></tr>
      <tr><td>Other lighting drivers/chipsets</td><td>⚠️ Limited</td><td>Depends on firmware support</td></tr>
    </tbody>
  </table>
</div>

## Notes

- This list will grow as more boards and devices are tested.
- If your setup differs from the list above, Pinball CTL may still work, but behaviour can vary.
