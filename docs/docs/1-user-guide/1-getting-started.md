# Getting Started

This guide helps you get Pinball CTL running from a clean Raspberry Pi setup.

## Before You Start

Pinball CTL is under active development. It runs well on the hardware used in this project, but it has not yet been broadly tested across all Raspberry Pi and peripheral combinations.

In plain terms: if your setup is different, your mileage may vary.

## Requirements

The table below shows what is required and what has been tested in this project.

<div class="manual-table-wrap">
  <table class="manual-table manual-requirements-table">
    <thead>
      <tr>
        <th nowrap="nowrap">Item</th>
        <th nowrap="nowrap">Required</th>
        <th nowrap="nowrap">Tested</th>
        <th nowrap="nowrap">Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Raspberry Pi 5</td><td>✅</td><td>✅</td><td>Main target platform</td></tr>
      <tr><td>ESP32-S3 controller board</td><td>✅</td><td>✅</td><td>Real-time I/O and safety layer</td></tr>
      <tr><td>microSD card (32GB recommended)</td><td>✅</td><td>✅</td><td>Raspberry Pi OS and local storage</td></tr>
      <tr><td>Stable Pi power supply</td><td>✅</td><td>✅</td><td>Use a suitable PSU for Pi 5</td></tr>
      <tr><td>USB data cable (Pi &lt;-&gt; ESP32-S3)</td><td>✅</td><td>✅</td><td>Must be a data cable, not charge-only</td></tr>
      <tr><td>Network connection (Ethernet or Wi-Fi)</td><td>✅</td><td>✅</td><td>Needed for package install and web UI access</td></tr>
      <tr><td>Raspberry Pi OS 64-bit</td><td>✅</td><td>✅</td><td>Recommended by Raspberry Pi for Pi 5</td></tr>
      <tr><td>Python 3.11+</td><td>✅</td><td>✅</td><td>Required by Pinball CTL</td></tr>
      <tr><td><code>python3-venv</code></td><td>✅</td><td>✅</td><td>For isolated environment install</td></tr>
      <tr><td><code>pip</code></td><td>✅</td><td>✅</td><td>Package installation</td></tr>
      <tr><td><code>git</code></td><td>⚠️ If installing from Git URL</td><td>✅</td><td>Needed for tag-based Git install</td></tr>
      <tr><td>macOS dev machine</td><td>❌</td><td>✅</td><td>Development was done on macOS; runtime target is Pi</td></tr>
      <tr><td>Web browser (Chrome, Edge, Safari, Firefox)</td><td>✅</td><td>✅</td><td>For Pinball CTL web interface</td></tr>
    </tbody>
  </table>
</div>

For hardware-specific status, see:

- [Supported Components](99-supported-components.md)

## Prepare Raspberry Pi OS

You can use an existing Raspberry Pi installation if preferred, however be aware that installed packages, libraries, and system configurations may differ depending on what has previously been set up.
If starting from scratch, download the latest Raspberry Pi OS image and flash it to your SD card.

Official Raspberry Pi references:

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- [Install an operating system](https://www.raspberrypi.com/documentation/installation/installing-images/)
- [Raspberry Pi OS downloads](https://www.raspberrypi.com/software/operating-systems/)

Recommended for Pi 5:

- Use the current recommended **Raspberry Pi OS (64-bit)** entry in Raspberry Pi Imager.
- As of **4 December 2025**, Raspberry Pi lists Raspberry Pi OS 64-bit based on Debian 13 (Trixie) for Pi 5.

Tip:

- Raspberry Pi Imager is the quickest way to get started for most users.
- In Raspberry Pi Imager, open OS customisation before writing the card.
- Preconfigure Wi-Fi, username/password, locale, and SSH so these settings are baked into the image for easier remote setup.

## Boot and Connect to the Pi

You can continue setup in either of these ways:

1. SSH from another machine (recommended for headless setups).
2. Directly on the Pi using keyboard + monitor.

### Option A: SSH

If SSH was enabled in Imager:

```bash
ssh <your-user>@raspberrypi.local
```

If mDNS is not available on your network, use the Pi IP address instead:

```bash
ssh <your-user>@<pi-ip-address>
```

### Option B: Keyboard + Monitor

Log in locally and open Terminal.

## Install Pinball CTL in a Virtual Environment

Run the following on your Pi.

### Install base tools

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
```

### Create and activate a venv

A venv keeps each project self-contained, portable, and much easier to manage—especially as projects grow or when working across multiple machines.

```bash
mkdir -p ~/pinballctl
cd ~/pinballctl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Install from a Git tag (recommended)

If you know the release tag:

```bash
python -m pip install "git+https://github.com/pinballctl/pinballctl.git@vX.Y.Z"
```

View available tags [here](https://github.com/pinballctl/pinballctl/tags)

If you want to resolve and install the latest tag automatically:

```bash
REPO_URL="https://github.com/pinballctl/pinballctl.git"
LATEST_TAG="$(git ls-remote --refs --sort='version:refname' --tags "$REPO_URL" | tail -n1 | sed 's|.*refs/tags/||')"
python -m pip install "git+$REPO_URL@$LATEST_TAG"
```

Then verify:

```bash
pinballctl --version
```

Note:

- Installing from a tag gives you a reproducible version aligned to a release point.

## Run Pinball CTL

For most users, this is all you need:

```bash
pinballctl start
```

This starts Pinball CTL with the default runtime setup.

You can check status at any time:

```bash
pinballctl status
```

Advanced:

- If you need manual control of individual services and options, use:

```bash
pinballctl --help
```

## Open the Web Interface

From a browser on your network, open:

```text
http://<pi-ip-address>:8888
```

If local hostname resolution works on your network, this may also work:

```text
http://raspberrypi.local:8888
```

You should see the Pinball CTL login screen in your browser:


<img src="./media/screenshot-login.webp" data-source='{"url":"/login","dark_mode":true}' alt="Pinball CTL login screen" style="width: 100%; max-width: 900px; height: auto;">

Default login credentials:

- Username: `admin`
- Password: `password`

For safety, change the default password as soon as you log in.

## Optional: Run as Services

For auto-start on boot and easier long-running use:

```bash
pinballctl service install
pinballctl service start all
pinballctl status
```

## Command Overview

Use `pinballctl --help` at any time for the full command tree.

<div class="manual-table-wrap">
  <table class="manual-table">
    <thead>
      <tr>
        <th>Command</th>
        <th>What it does</th>
      </tr>
    </thead>
    <tbody>
      <tr><td><code>pinballctl start</code></td><td>Starts Pinball CTL with the default runtime setup</td></tr>
      <tr><td><code>pinballctl status</code></td><td>Shows system, service, network, and port status</td></tr>
      <tr><td><code>pinballctl --version</code></td><td>Shows installed Pinball CTL version</td></tr>
      <tr><td><code>pinballctl --help</code></td><td>Shows top-level help</td></tr>
      <tr><td><code>pinballctl web --help</code></td><td>Shows web command options</td></tr>
      <tr><td><code>pinballctl bridge --help</code></td><td>Shows bridge command options</td></tr>
      <tr><td><code>pinballctl service install</code></td><td>Installs and enables systemd services</td></tr>
      <tr><td><code>pinballctl service start all</code></td><td>Starts web + bridge services</td></tr>
      <tr><td><code>pinballctl service restart all</code></td><td>Restarts all services</td></tr>
      <tr><td><code>pinballctl service --help</code></td><td>Shows service command options</td></tr>
    </tbody>
  </table>
</div>

## Troubleshooting Quick Checks

If something is not working, check these first:

1. Is your venv active (`source .venv/bin/activate`)?
2. Does `pinballctl --version` work?
3. Is your Pi reachable on the network?
