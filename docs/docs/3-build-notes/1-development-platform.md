# Development Platform

## Introduction

This development platform is built for rapid iteration between software and hardware, with a tight loop from code change to real-world behaviour on the machine.

The workflow is centred on macOS for authoring, testing, firmware flashing, and diagnostics, with Pinball CTL acting as the bridge between editor tools, runtime services, and ESP-based hardware control.

The sections below list the core software stack and the main hardware components used in the current setup.


## Software Stack

<div class="manual-table-wrap">
<table id="software-stack-table">
  <thead>
    <tr>
      <th>Software</th>
      <th>Purpose</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><a href="https://www.git-tower.com/" target="_blank" rel="noopener noreferrer">Tower</a></td>
      <td>Git client</td>
      <td>Used for day-to-day source control operations.</td>
    </tr>
    <tr>
      <td><a href="https://nova.app/" target="_blank" rel="noopener noreferrer">Nova</a></td>
      <td>Code editor</td>
      <td>Primary IDE/editor for project development.</td>
    </tr>
    <tr>
      <td><a href="https://kaleidoscope.app/" target="_blank" rel="noopener noreferrer">Kaleidoscope</a></td>
      <td>Diff and merge tool</td>
      <td>Used for comparing file versions and resolving merges.</td>
    </tr>
    <tr>
      <td><a href="https://openai.com/codex/" target="_blank" rel="noopener noreferrer">Codex</a></td>
      <td>Coding support</td>
      <td>Used to assist with implementation, reviews, and documentation updates.</td>
    </tr>
    <tr>
      <td><a href="https://www.google.com/chrome/" target="_blank" rel="noopener noreferrer">Chrome</a></td>
      <td>Primary browser</td>
      <td>Primary browser for testing the web UI, though any modern browser should work.</td>
    </tr>
    <tr>
      <td><a href="https://www.python.org/" target="_blank" rel="noopener noreferrer">Python</a></td>
      <td>Runtime and tooling</td>
      <td>
        Version: <code>&gt;=3.11</code><br>
        Core modules/packages used:
        <ul>
          <li><code>flask</code></li>
          <li><code>gunicorn</code></li>
          <li><code>pyserial</code></li>
          <li><code>blinker</code></li>
          <li><code>esptool</code></li>
          <li><code>markdown</code></li>
        </ul>
      </td>
    </tr>
  </tbody>
</table>
</div>

## Hardware Testing Setup

Although this project started as a way to learn more electronics, it has naturally evolved into a software platform. I am still continuing the hardware side as well, just at a steadier pace.

The test rig below serves two goals: exploring hardware integration, and providing a practical bench setup for validating Pinball CTL behaviour against real components.

![Build image 0](./media/build-image0.png)

Primary development currently runs on macOS (with a Raspberry Pi 5 planned as the permanent host). The test rig is a simple box with two compartments. Compartment one contains the mains entry point and switch for the 240V side, and is sealed to isolate anything that could give me a tingle. Compartment two contains the mounted test components and has a lift-off lid so everything is easy to access.

![Build image 1](./media/build-image1.png)

This side includes simple buttons (with and without LEDs), RGB lighting, and an ESP32-S3 mounted on a dev board.

![Build image 2](./media/build-image2.png)

The LCD display is one of the components supported by Pinball CTL and is useful for showing development/debug information. Placeholders are available for status details such as IP address output. The ESP is mounted on a dev board, which makes development easier: pin states are visible and HIGH/LOW behaviour can be verified quickly when triggering events from the UI. New components can be assembled on the breadboard first, then moved to soldered boards and re-tested. Additional mounts are included for different pre-soldered module boards.

![Build image 3](./media/build-image3.png)

Inside the main compartment: 24V input, then converters down to 12V, 5V and 3.3V, plus power distribution rails. This area also includes the accelerometer (for tilt sensing) and a status-light board (visible on the top). One of the ESP boards I use is not a dev variant, so a serial adapter module is wired in for firmware syncing without manually forcing flash mode. That links to a front-mounted connector for easy access, alongside the usual spaghetti of development wiring.

![Build image 4](./media/build-image4.png)

Inside compartment one: a PSU to 48V and a converter from 48V to 24V. This compartment is sealed specifically to isolate higher-voltage hardware from the accessible development area.


## Core Components and Costs

This is a hobby project, and many more components have been bought, tested, and discarded during the learning process than are listed below.

When I started, I had very little electronics tooling, so a lot of early spend was on fundamentals such as a multimeter, soldering consumables, a better toolbox, and far too much wire (until I learned the differences and what was actually needed).

The single largest cost was the Raspberry Pi 5 (8GB). I wanted plenty of headroom while developing, and the dual HDMI outputs were useful. Even though I chose the higher-end option, there is no obvious reason this could not run on a cheaper Raspberry Pi 4GB model or potentially a Pi 4, depending on workload and module usage.

For controllers, I went straight to the ESP32-S3 because of its dual-core capability, giving more flexibility during development. At the moment I am still running single-core logic, so a more basic ESP variant may also be a practical option in future.

<div class="manual-table-wrap">
<table id="component-cost-table" class="js-component-cost-table" style="width: 100%;">
  <thead>
    <tr>
      <th>Name</th>
      <th>Category</th>
      <th>Summary</th>
      <th>Cost</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0BNV39K2R" target="_blank" rel="noopener noreferrer">Lianshi Transformer AC-DC 0-48V Adjustable Power Supply</a></td>
      <td>Power</td>
      <td>Adjustable AC-DC bench power supply providing variable 0-48V output for testing and powering electronics.</td>
      <td data-cost="37.99">£37.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0CCVQBHZH" target="_blank" rel="noopener noreferrer">Multi Channel Switching Power Supply Board</a></td>
      <td>Power</td>
      <td>Multi-channel DC switching board used to distribute and control multiple power outputs.</td>
      <td data-cost="13.06">£13.06</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B08K4G4NP2" target="_blank" rel="noopener noreferrer">Walfront DC-DC Power Converter Module</a></td>
      <td>Power</td>
      <td>DC-DC voltage converter used to step voltage up or down efficiently for electronics.</td>
      <td data-cost="16.65">£16.65</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0814B5P5M" target="_blank" rel="noopener noreferrer">Evemodel Power Distribution Board 2pcs</a></td>
      <td>Power</td>
      <td>Compact power distribution boards for splitting a single power source into multiple outputs.</td>
      <td data-cost="12.99">£12.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0BKZRL166" target="_blank" rel="noopener noreferrer">Xiatiaosann IEC Inlet Module Plug</a></td>
      <td>Power</td>
      <td>Panel-mounted IEC mains inlet with integrated switch and fuse for safe AC power input.</td>
      <td data-cost="7.99">£7.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0CD2512JV" target="_blank" rel="noopener noreferrer">Freenove Breakout Board for ESP32</a></td>
      <td>Controller</td>
      <td>ESP32 breakout board expanding pins to screw terminals for easier wiring and prototyping.</td>
      <td data-cost="11.95">£11.95</td>
    </tr>
    <tr>
      <td><a href="https://amzn.eu/d/0eQctSNP" target="_blank" rel="noopener noreferrer">ESP-S3-N16R8 Development Board</a></td>
      <td>Controller</td>
      <td>ESP32-S3 microcontroller board with Wi-Fi and Bluetooth used as the main controller.</td>
      <td data-cost="31.99">£31.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0CK2FCG1K" target="_blank" rel="noopener noreferrer">Raspberry Pi 5 (8GB)</a></td>
      <td>Controller</td>
      <td>Single-board computer used to run the main pinball control software and interface with hardware.</td>
      <td data-cost="139.99">£139.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0CNVDF2MC" target="_blank" rel="noopener noreferrer">GeeekPi Armor Lite V5 Aluminium Case for Raspberry Pi 5</a></td>
      <td>Controller</td>
      <td>Aluminium protective case for Raspberry Pi 5 providing passive cooling and physical protection.</td>
      <td data-cost="7.99">£7.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0D2DD11FJ" target="_blank" rel="noopener noreferrer">Thsucords Thin Micro HDMI to HDMI Cable</a></td>
      <td>Controller</td>
      <td>Micro HDMI to HDMI cable used to connect the Raspberry Pi display output to a monitor.</td>
      <td data-cost="11.89">£11.89</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0CPDGDMD5" target="_blank" rel="noopener noreferrer">Soldering Iron Kit 80W LCD</a></td>
      <td>Tools</td>
      <td>Adjustable 80W soldering iron kit with accessories for electronics assembly.</td>
      <td data-cost="17.98">£17.98</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B082KY5Y5Z" target="_blank" rel="noopener noreferrer">ElectroCookie Solderable Breadboard PCB</a></td>
      <td>Prototyping</td>
      <td>Solderable prototyping PCB designed like a breadboard for permanent circuits.</td>
      <td data-cost="9.98">£9.98</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0BF5C6114" target="_blank" rel="noopener noreferrer">TSKDKIT A3 MDF Wood Boards Pack of 5</a></td>
      <td>Structure</td>
      <td>A3 MDF boards used to build the prototype enclosure and mounting surfaces.</td>
      <td data-cost="64.95">£64.95</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B09P8VB2G4" target="_blank" rel="noopener noreferrer">M3 Nylon Hex Standoff Assortment Kit</a></td>
      <td>Hardware</td>
      <td>Nylon spacers, screws and nuts for mounting PCBs and insulating electronics.</td>
      <td data-cost="7.99">£7.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0B39554LH" target="_blank" rel="noopener noreferrer">Treedix RGB LED 5050 Kit</a></td>
      <td>Lighting</td>
      <td>RGB LEDs used for visual indicators and lighting effects.</td>
      <td data-cost="9.99">£9.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0DDXX8X3N" target="_blank" rel="noopener noreferrer">DORHEA FT232RL USB to TTL Adapter</a></td>
      <td>Controller</td>
      <td>USB-to-TTL serial adapter used for programming and debugging microcontrollers.</td>
      <td data-cost="5.99">£5.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B09YXPM1TL" target="_blank" rel="noopener noreferrer">ZHENGYYUU Jumper Wire Kit 840pcs</a></td>
      <td>Prototyping</td>
      <td>Large assortment of jumper wires for breadboard and prototype wiring.</td>
      <td data-cost="7.29">£7.29</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0C27VKHHC" target="_blank" rel="noopener noreferrer">Third Hand Soldering Tool</a></td>
      <td>Tools</td>
      <td>Helping-hands tool with clips for holding components during soldering.</td>
      <td data-cost="19.99">£19.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B09ZK34JHZ" target="_blank" rel="noopener noreferrer">BOJACK Breadboard Kit</a></td>
      <td>Prototyping</td>
      <td>Breadboard kit with components and wires for testing circuits.</td>
      <td data-cost="9.99">£9.99</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0071KZVV0" target="_blank" rel="noopener noreferrer">Brimal Stripboard Track Cutter</a></td>
      <td>Tools</td>
      <td>Tool for cutting copper tracks on stripboard when building circuits.</td>
      <td data-cost="6.26">£6.26</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0DXF5Q9ZQ" target="_blank" rel="noopener noreferrer">Non-Insulated Crimping Tool Set</a></td>
      <td>Tools</td>
      <td>Crimping tool set for attaching electrical connectors to wires.</td>
      <td data-cost="25.00">£25.00</td>
    </tr>
    <tr>
      <td><a href="https://www.amazon.co.uk/dp/B0C784G75J" target="_blank" rel="noopener noreferrer">Tesfish WS2812B LED Strip Light</a></td>
      <td>Lighting</td>
      <td>Addressable WS2812B RGB LED strip used for programmable lighting effects.</td>
      <td data-cost="17.99">£17.99</td>
    </tr>
    <tr>
      <td>Miscellaneous</td>
      <td>Other</td>
      <td>Other tools, flux, components such as resistors, MOSFETs, wire, screws, glue, switches, and a mini test coil.</td>
      <td data-cost="200.00">£200.00</td>
    </tr>
  </tbody>
</table>
</div>

## Project Cost Summary

<div class="manual-table-wrap">
<table id="project-cost-summary-table" style="width: 100%;">
  <thead>
    <tr>
      <th>Category</th>
      <th>Items</th>
      <th>Total Cost</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td id="project-total-label">Total Project Cost</td>
      <td id="project-total-items">-</td>
      <td id="project-total-cost">-</td>
    </tr>
  </tbody>
</table>
</div>



<div class="manual-table-wrap">
<table id="project-cost-breakdown-table" style="width: 100%; margin-top: 2rem">
  <thead>
    <tr>
      <th>Category</th>
      <th>Items</th>
      <th>Category Total</th>
    </tr>
  </thead>
  <tbody id="project-cost-breakdown-body">
    <tr>
      <td colspan="3">Cost breakdown will load automatically.</td>
    </tr>
  </tbody>
</table>
</div>
