# Detailed Setup

Prepare a Raspberry Pi, install the current development build and check the path from a physical input to a rule. Work through one connection at a time; keep output power disconnected until the input path is reliable.

## Outcome and prerequisites

You need a Raspberry Pi 5, suitable power supply, microSD storage (32 GB recommended), network access, Raspberry Pi OS 64-bit, Python 3.11 or later, an ESP32-S3 and USB data cable. For the first test, use one supported input with wiring appropriate to the board. See [Supported Components](99-supported-components.md) for the scope of testing; support does not mean every peripheral combination is verified.

This edition documents current committed `main`, including Backup / Restore. It is a development baseline, not a promise that an older tagged release contains the same features. `v0.10.0` predates Backup / Restore, despite the current code sharing that package version. Record the exact Git revision you install.

<img src="./media/manual-topology.svg" alt="Browser, Raspberry Pi application and bridge, and ESP32-S3 responsibilities connected by network and framed USB transport" style="width:100%;height:auto;">

**Diagram guide:** the Pi hosts authoring and host services; the ESP handles physical I/O and output safety limits. This is a responsibility map, not an electrical wiring diagram.

## 1. Plan the electrical boundary

1. Identify the Pi supply, controller supply and load supplies from your actual design.
2. Disconnect coil/high-current output power before wiring. Check input voltage limits and grounding against the board and driver documentation.
3. Keep coils, motors and lamps off GPIO. Use suitable drivers, fuses and flyback protection for the actual loads, plus a physical means to disconnect output power.

**Expected result:** a powered Pi/ESP can be tested without energising a high-current output. If you cannot identify the power and driver arrangement, stop the output setup and resolve the circuit first. Firmware arming, watchdogs and pulse limits are additional safeguards, not replacements for electrical design.

## 2. Prepare Raspberry Pi OS

1. Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to select your Pi model and Raspberry Pi OS 64-bit.
2. Configure a hostname, your own login, network and SSH access in Imager before writing the card. Store those credentials securely.
3. Boot the Pi. Open a local terminal or connect by SSH using your configured username and hostname/IP address.
4. Run `python3 --version` and check that it is at least 3.11.

**Expected result:** you have terminal access and a network connection. If SSH is unreachable, use the router's device list or a local console to find the address; hostname resolution is not available on every network. Writing a card erases its existing contents, so preserve anything you need first.

## 3. Install a recorded development revision

Run on the Pi, outside any existing project checkout:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
git clone --branch main https://github.com/pinballctl/pinballctl.git
cd pinballctl
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
pinballctl --version
pinballctl --help
```

**Expected result:** the command-line tool runs from this checkout's virtual environment. Save the revision printed by Git alongside your installation notes. If the `pinballctl` command is missing, activate this checkout's `.venv` and check the installation error rather than installing globally.

The checkout keeps the Godot host project available under `src/godot`; a standalone Python package does not bundle a complete Godot installation. Display playback needs a compatible local Godot executable and display environment; follow [Media](18-media.md) and [Godot](22-godot.md) when you reach that stage.

## 4. Start manually for the first test

From the checkout with its environment active:

```bash
pinballctl start
pinballctl status
```

The manual start binds the web interface on port **8888** by default, starts the host processes and attempts bridge auto-detection at **460800** baud. If no ESP is present, the web interface can still be used for authoring, but physical event testing must wait.

1. Read status for the actual address, processes, serial ports and log locations.
2. Open the Pi address at port 8888 in a browser on the same trusted network.
3. Sign in using your installation's credentials. An unconfigured source installation defaults to `admin` / `password`; saved settings and `PINBALLCTL_USER`, `PINBALLCTL_PASSWORD` or hashed-password environment settings may override them.
4. Open **Settings → Access**, save your own credentials and verify them in a fresh login.

**Expected result:** the dashboard loads and access uses your own credentials. Keep the interface on a trusted network; configure HTTPS before transmitting credentials across an untrusted network. If unreachable, check address, port, process status and network/firewall rules.

<img src="./media/screenshot-login.webp" alt="Pinball CTL sign-in screen before opening the dashboard" style="width:100%;height:auto;">

**Screen guide:** the login protects the application; changing the Pi operating-system password does not change this application login.

## 5. Connect the ESP and verify compatibility

1. Keep output power off and connect the ESP32-S3 with a USB data cable.
2. Open **ESPLink** and verify live connection state, controller identity and firmware information. Cached identity alone is not a live connection.
3. If firmware needs updating, use the [Firmware](12-firmware.md) and [ESPLink](11-esplink.md) workflows with images intended for your controller. Do not guess a compatible image from its filename alone.
4. If disconnected, check cable, the detected serial device, bridge logs and Linux device access. Recheck after reconnecting.

**Expected result:** the bridge exchanges live status with the intended ESP. Stop here if compatibility or transport errors remain. Communication is framed JSON; serial terminal text commands are not a supported configuration method.

<img src="./media/screenshot-feature-esplink.webp" alt="ESPLink connection and controller information used to check a connected ESP32-S3" style="width:100%;height:auto;">

**Screen guide:** inspect connection state before relying on the identity/version fields. Use the detailed connection guide for no-device and reconnect states.

## 6. Map and observe a physical input

1. Open **Hardware → Reload Pins** with the controller connected.
2. Match the input's UID, board and channel to your wiring. Give it a meaningful friendly name and choose its input function.
3. Open its settings where available and check polarity, pull configuration and supported debounce/gesture options against the circuit. Do not unhide reserved pins just to obtain more outputs.
4. Choose **Save Changes**, then **Sync to ESP**. Wait for completion and inspect any error.
5. Operate the input once and use **Logs** to confirm the actual event name and source. Confirm press/release or open/closed behaviour appropriate to the input.

**Expected result:** the physical input produces the intended event without false repeats. If silent or inverted, check pin identity, voltage/polarity, saved mapping, sync and connection before changing a rule. Use [Hardware](7-hardware.md) and [Events](27-events.md) to investigate.

<img src="./media/screenshot-feature-hardware.webp" alt="Hardware Mapping table for identifying pins and assigning names and functions" style="width:100%;height:auto;">

**Screen guide:** use board/channel and UID together. The friendly label helps authoring but is not an electrical pin specification.

## 7. Build the first rule

Follow [Quick Start step 6](0-quick-start.md#6-create-and-test-a-safe-rule): create **Test target**, use the observed input trigger and fire a distinct Custom event named `TEST_TARGET_SEEN`. Leave conditions empty initially; validate, save, review sync status and operate the input again.

**Expected result:** the log shows the input and derived event. Check exact event/source, enabled state, validation and saved configuration if it fails. Keep the Pi running: host event, state, scoring and media actions require it. Review [Rules](7.1-rules.md) before adding conditions or output actions.

## 8. Configure an output only after the input test

1. Keep load power disconnected while identifying the output UID and driver circuit.
2. Configure the correct output function, polarity and safe state in Hardware. For a coil, configure pulse/hold/cooldown limits appropriate to its specifications and driver.
3. Save and sync, then inspect the resulting status. Verify physical power removal and fault behaviour before any powered test.
4. Perform a controlled hardware test only when you can safely observe and stop it. Recheck arming, watchdog and maximum-on behaviour on the actual Pi/ESP.

**Expected result:** the output has explicit limits and a known safe state. A successful save or preview is not a powered safety test. Do not choose example pulse times or hold duty values from screenshots: they may damage a different coil.

## 9. Choose service operation when ready

Use a single operating mode. The installed service is **pinball.service**, not separate web/bridge units. From the checkout with its virtual environment active:

```bash
pinballctl stop
pinballctl service install --user "$(id -un)" --workdir "$PWD" --venv-bin "$PWD/.venv/bin"
pinballctl status
systemctl status pinball.service
```

Installation requires Linux/systemd and sudo permission; it installs, enables and restarts the unit. Its template binds port **8000**, so reopen your Pi address at port 8000 after switching. The service user must be able to read the checkout, write project data and access the serial device. Media requires its own suitable display/audio environment.

Supported CLI actions include `pinballctl service start all`, `pinballctl service stop all` and `pinballctl service reload all`; the final selector is retained for compatibility but controls the single unit. For a full systemd restart use `sudo systemctl restart pinball.service`. The CLI does not expose a `service restart` subcommand in this baseline.

**Expected result:** systemd reports the unit running and the UI responds on its configured port. On failure, inspect `journalctl -u pinball.service` and `pinballctl status`. Do not start an extra manual bridge to work around a service failure.

## 10. Record data locations and recovery

In this editable checkout, managed project data lives in `src/instance/`. It includes mapping, rules, media and audio data plus protected local settings. Do not replace it by extracting arbitrary ZIP files. The [Backup / Restore](25-backup-restore.md) library normally lives outside it at `~/.local/share/pinballctl/backups/`, or the configured XDG/dedicated backup directory under the service user's account.

1. Create an **Everything** backup and download an off-machine copy after the first working setup.
2. Record the Git revision, start mode/port, firmware identity and log locations.
3. Before upgrades or recovery, stop gameplay and playback, preserve data and follow the backup guide. Never assume a restore automatically syncs the ESP or arms outputs.

**Expected result:** you can identify what is installed and recover project content without losing credentials or accidentally publishing old hardware configuration.

## Troubleshooting and next steps

Use [Troubleshooting](26-troubleshooting.md) for UI access, ESP offline, silent inputs, failed rules or missing assets. Keep one-input tests small: changing wiring, mapping, firmware and rules together makes faults harder to isolate.

Next: [Interface Tour](2-interface.md), [Rules Wizard](24-rules-wizards.md), [Lighting](8-lighting.md), [Audio](17-audio.md), [Media](18-media.md). Physical Pi/ESP installation, power-loss and coil safety checks remain target-hardware work; desktop documentation checks cannot verify them.
