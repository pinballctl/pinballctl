# Getting Started

## Quick start

### What you need

You need a Raspberry Pi 5 running Raspberry Pi OS 64-bit, suitable Pi power, network access, an ESP32-S3 with compatible firmware, a USB **data** cable and one safely wired supported input. Use the pin map and voltage limits for your actual board; this guide does not assign a GPIO number. Have a browser and a Pi terminal available.

This manual follows current committed `main`, including Backup / Restore. The older `v0.10.0` tag lacks that module. The package version number alone cannot identify which code you have. Record the Git revision during installation.

### 1. Prepare and reach the Pi

1. In [Raspberry Pi Imager](https://www.raspberrypi.com/software/), choose your Pi model and Raspberry Pi OS 64-bit. Configure your own username, network and SSH access before writing the card.
2. Boot the Pi, then sign in at its console or use SSH with the hostname/address and username you configured.
3. Open a terminal and run `python3 --version`. The application requires Python 3.11 or later.

**Expected result:** you can run commands on the Pi. If you cannot connect, confirm the Pi address at your router or local console. Do not assume every installation is named `raspberrypi.local`.

### 2. Install and identify the development build

Run on the Pi in a directory where you have not already installed the project:

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
pinballctl start
pinballctl status
```

**Expected result:** installation succeeds and status shows the web process and its address. Record the revision printed by `git rev-parse HEAD`; development builds can differ while reporting the same package version. A missing bridge/device is expected until the controller is connected.

If installation fails, keep the error message, check Python and network access, and use [Detailed setup](#detailed-setup). Do not install a second copy over an existing running service. These commands select a development build; they are not a claim that it has passed target-hardware testing.

### 3. Open the application and secure access

1. Use the Pi's network address with port **8888** for the manual `pinballctl start` above. For example, an address of `192.168.1.50` gives `http://192.168.1.50:8888`; replace that example address with your Pi's address.
2. Sign in. The source defaults are username `admin` and password `password` on an unconfigured installation. Saved or environment-provided credentials can override them.
3. Open **Settings → Access**, set your own credentials and choose **Save Changes**. Verify the new login before relying on unattended access.

**Expected result:** the dashboard opens and your new credentials work. If the interface is unreachable, check `pinballctl status` and the port. An installed `pinball.service` uses **8000** by default; do not start both modes together.

<img src="./media/screenshot-login.webp" alt="Login screen with username and password fields" style="width:100%;height:auto;">

**Screen guide:** enter the installation's credentials in the two fields. Never share screenshots containing a real password or session information.

### 4. Connect and check the ESP

1. Disconnect power to coils and other high-current outputs before connecting the ESP32-S3 with a USB data cable. Leave that power disconnected through the switch and rule tests.
2. Open **ESPLink** and check live connection status, controller identity and firmware information.
3. Resolve version/connection warnings before deploying configuration. Use [Firmware](12-firmware.md) for compatible images and [ESPLink](11-esplink.md) for connection checks.

**Expected result:** a live connected controller, not merely cached identity details. If offline, check the cable, serial port, permissions and bridge status; a charge-only cable cannot work.

<img src="./media/screenshot-feature-esplink.webp" alt="ESPLink workspace showing connection, controller and firmware information" style="width:100%;height:auto;">

**Screen guide:** check the connection state first, then identity and version. A development screenshot cannot confirm your connected hardware.

### 5. Name and observe one input

1. Open **Hardware**, then **Reload Pins** with the ESP connected.
2. Identify your safely wired input from its board/channel and UID. Give it a friendly name such as **Test target** and select the matching input function. Check polarity and supported input options against the circuit.
3. Choose **Save Changes**, then **Sync to ESP**. Wait for the reported result.
4. Open **Logs**, select the event log and operate the switch once. Record the actual event name and source UID. Confirm a release event as well when that input type provides one.

**Expected result:** the event identifies your input and occurs when you operate it. If silent, check the live connection, pin identity, input polarity, saved mapping and sync result before creating a rule. Do not guess an event name from a screenshot.

<img src="./media/screenshot-feature-hardware.webp" alt="Hardware Mapping table showing pin UIDs, channels, friendly names and functions" style="width:100%;height:auto;">

**Screen guide:** board/channel identifies the physical connection; the UID identifies it to rules. Friendly names make the same device easier to find elsewhere.

### 6. Create and test a safe rule

1. Open **Rules → Add Rule** and name it **Test target** in **Metadata**. Keep it enabled.
2. In **Triggers**, choose the actual hardware source and event observed in step 5. Leave **Conditions** empty for this first test.
3. In **Actions**, choose the System event action (**Fire Event** / **Emit Event**), set **Event Type** to **Custom** and enter `TEST_TARGET_SEEN` as its event name. Do not select a pulse, output, coil or existing gameplay event. Check that no other rule listens for this new name.
4. Review **Summary**, correct validation errors, then **Save**. Check sync status and use **Sync to ESP** when required for deployed behaviour. The custom event action runs on the Pi, so the application and bridge must remain running.
5. Operate the physical switch once and find both the original input event and `TEST_TARGET_SEEN` in the event log.

**Expected result:** the custom event follows your switch event without energising an output. If it does not, check the exact trigger/source, enabled state, saved rule, validation and sync status. Do not use the custom result event as its own trigger: that would create a loop.

<img src="./media/screenshot-feature-rules-tab-actions.webp" alt="Rules Actions tab where an action type and its parameters are configured" style="width:100%;height:auto;">

**Screen guide:** choose the event action and its Custom event type for this exercise. Other configured actions in a sample project are not instructions to operate hardware.

### What next?

Keep the test rule clearly named, or disable it after testing. Create and download a [backup](25-backup-restore.md), then learn [Rules](7.1-rules.md), [Lighting](8-lighting.md) or [Audio](17-audio.md). Use [Troubleshooting](26-troubleshooting.md) when the observed result differs from the expected result.

## Detailed setup

### Outcome and prerequisites

You need a Raspberry Pi 5, suitable power supply, microSD storage (32 GB recommended), network access, Raspberry Pi OS 64-bit, Python 3.11 or later, an ESP32-S3 and USB data cable. For the first test, use one supported input with wiring appropriate to the board. See [Supported Components](99-supported-components.md) for the scope of testing; support does not mean every peripheral combination is verified.

This edition documents current committed `main`, including Backup / Restore. It is a development baseline, not a promise that an older tagged release contains the same features. `v0.10.0` predates Backup / Restore, despite the current code sharing that package version. Record the exact Git revision you install.

<img src="./media/manual-topology.svg" alt="Browser, Raspberry Pi application and bridge, and ESP32-S3 responsibilities connected by network and framed USB transport" style="width:100%;height:auto;">

**Diagram guide:** the Pi hosts authoring and host services; the ESP handles physical I/O and output safety limits. This is a responsibility map, not an electrical wiring diagram.

### 1. Plan the electrical boundary

1. Identify the Pi supply, controller supply and load supplies from your actual design.
2. Disconnect coil/high-current output power before wiring. Check input voltage limits and grounding against the board and driver documentation.
3. Keep coils, motors and lamps off GPIO. Use suitable drivers, fuses and flyback protection for the actual loads, plus a physical means to disconnect output power.

**Expected result:** a powered Pi/ESP can be tested without energising a high-current output. If you cannot identify the power and driver arrangement, stop the output setup and resolve the circuit first. Firmware arming, watchdogs and pulse limits are additional safeguards, not replacements for electrical design.

### 2. Write the SD card and start the Pi

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your computer. Insert the microSD card. Check its name and size before selecting it because writing the image erases that card.
2. In Imager choose your Pi model, **Raspberry Pi OS (64-bit)**, and the microSD card. Open the OS customisation options. Set a hostname such as `pinball-pi`, create a username and password, and configure your Wi-Fi if you are using it. Enable SSH if you plan to connect without a monitor. Save the settings and write the card.
3. Eject the card, put it in the Pi and power the Pi on. The first boot can take a few minutes. Connect Ethernet if you have not configured Wi-Fi.
4. For a local console, connect a monitor and keyboard. Sign in with your Pi username and open **Terminal** from the desktop menu. If you installed Raspberry Pi OS Lite, the login prompt itself is the console.

### Connect by SSH for the first time

SSH opens a terminal **on the Pi** from another computer. On macOS open **Terminal** from Spotlight. On Windows open **PowerShell** or **Windows Terminal**. On Linux open **Terminal** from the applications menu. Put both devices on the same network.

Run the command below with your own username and hostname. The examples use the username `builder` and hostname `pinball-pi`.

```bash
ssh builder@pinball-pi.local
```

If the hostname does not resolve, use the Pi’s network address from your router’s connected-devices list. With a keyboard and screen on the Pi, `hostname -I` also lists its addresses. For example, if the Pi is at `192.168.1.50`, run `ssh builder@192.168.1.50`.

- On the first connection, SSH may ask whether you trust the host key. Verify it is your Pi before accepting. From the Pi’s local console you can run `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` to compare the ED25519 fingerprint when that key type is shown.
- Type the **Pi account** password when prompted and press Enter. The terminal hides each character as you type.
- A prompt such as `builder@pinball-pi:~ $` means you are on the Pi. Run `hostname` and `python3 --version` to check where you are and that Python is at least 3.11. To disconnect, type `exit`.

Run the install commands below **after** the Pi prompt appears. Copy the command text without a leading prompt, press Enter and wait for each command to finish. `sudo` requests administrator privileges and may ask for your Pi password again. If a command fails, stop and read its error before continuing.

### 3. Install a recorded development revision

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

### 4. Start manually for the first test

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

### 5. Connect the ESP and verify compatibility

1. Keep output power off and connect the ESP32-S3 with a USB data cable.
2. Open **ESPLink** and verify live connection state, controller identity and firmware information. Cached identity alone is not a live connection.
3. If firmware needs updating, use the [Firmware](12-firmware.md) and [ESPLink](11-esplink.md) workflows with images intended for your controller. Do not guess a compatible image from its filename alone.
4. If disconnected, check cable, the detected serial device, bridge logs and Linux device access. Recheck after reconnecting.

**Expected result:** the bridge exchanges live status with the intended ESP. Stop here if compatibility or transport errors remain. Communication is framed JSON; serial terminal text commands are not a supported configuration method.

<img src="./media/screenshot-feature-esplink.webp" alt="ESPLink connection and controller information used to check a connected ESP32-S3" style="width:100%;height:auto;">

**Screen guide:** inspect connection state before relying on the identity/version fields. Use the detailed connection guide for no-device and reconnect states.

### 6. Map and observe a physical input

1. Open **Hardware → Reload Pins** with the controller connected.
2. Match the input's UID, board and channel to your wiring. Give it a meaningful friendly name and choose its input function.
3. Open its settings where available and check polarity, pull configuration and supported debounce/gesture options against the circuit. Do not unhide reserved pins just to obtain more outputs.
4. Choose **Save Changes**, then **Sync to ESP**. Wait for completion and inspect any error.
5. Operate the input once and use **Logs** to confirm the actual event name and source. Confirm press/release or open/closed behaviour appropriate to the input.

**Expected result:** the physical input produces the intended event without false repeats. If silent or inverted, check pin identity, voltage/polarity, saved mapping, sync and connection before changing a rule. Use [Hardware](7-hardware.md) and [Events](27-events.md) to investigate.

<img src="./media/screenshot-feature-hardware.webp" alt="Hardware Mapping table for identifying pins and assigning names and functions" style="width:100%;height:auto;">

**Screen guide:** use board/channel and UID together. The friendly label helps authoring but is not an electrical pin specification.

### 7. Build the first rule

Follow [Quick start step 6](#6-create-and-test-a-safe-rule): create **Test target**, use the observed input trigger and fire a distinct Custom event named `TEST_TARGET_SEEN`. Leave conditions empty initially; validate, save, review sync status and operate the input again.

**Expected result:** the log shows the input and derived event. Check exact event/source, enabled state, validation and saved configuration if it fails. Keep the Pi running: host event, state, scoring and media actions require it. Review [Rules](7.1-rules.md) before adding conditions or output actions.

### 8. Configure an output only after the input test

1. Keep load power disconnected while identifying the output UID and driver circuit.
2. Configure the correct output function, polarity and safe state in Hardware. For a coil, configure pulse/hold/cooldown limits appropriate to its specifications and driver.
3. Save and sync, then inspect the resulting status. Verify physical power removal and fault behaviour before any powered test.
4. Perform a controlled hardware test only when you can safely observe and stop it. Recheck arming, watchdog and maximum-on behaviour on the actual Pi/ESP.

**Expected result:** the output has explicit limits and a known safe state. A successful save or preview is not a powered safety test. Do not choose example pulse times or hold duty values from screenshots: they may damage a different coil.

### 9. Choose service operation when ready

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

### 10. Record data locations and recovery

In this editable checkout, managed project data lives in `src/instance/`. It includes mapping, rules, media and audio data plus protected local settings. Do not replace it by extracting arbitrary ZIP files. The [Backup / Restore](25-backup-restore.md) library normally lives outside it at `~/.local/share/pinballctl/backups/`, or the configured XDG/dedicated backup directory under the service user's account.

1. Create an **Everything** backup and download an off-machine copy after the first working setup.
2. Record the Git revision, start mode/port, firmware identity and log locations.
3. Before upgrades or recovery, stop gameplay and playback, preserve data and follow the backup guide. Never assume a restore automatically syncs the ESP or arms outputs.

**Expected result:** you can identify what is installed and recover project content without losing credentials or accidentally publishing old hardware configuration.

### Troubleshooting and next steps

Use [Troubleshooting](26-troubleshooting.md) for UI access, ESP offline, silent inputs, failed rules or missing assets. Keep one-input tests small: changing wiring, mapping, firmware and rules together makes faults harder to isolate.

Next: [Interface Tour](2-interface.md), [Rules Wizard](24-rules-wizards.md), [Lighting](8-lighting.md), [Audio](17-audio.md), [Media](18-media.md). Physical Pi/ESP installation, power-loss and coil safety checks remain target-hardware work; desktop documentation checks cannot verify them.

## Run directly on a Mac

<aside class="docs-next">
<h3>Develop on your Mac</h3>
<p>Pinball CTL runs directly on macOS. Use it to build rules, set up scoring, and preview displays before transferring a project to a Raspberry Pi. You can open the web interface without an ESP32 attached.</p>
</aside>

Open **Terminal** on the Mac. Check `git --version` and `python3 --version`. Install Git and Python 3.11 or later if either is missing. Run these commands in a folder where you keep projects:

```bash
git clone --branch main https://github.com/pinballctl/pinballctl.git
cd pinballctl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
pinballctl start --host 127.0.0.1
pinballctl status
```

Open `http://127.0.0.1:8888` on the Mac. Set your own application login under **Settings → Access**. When you are finished, run `pinballctl stop` from the active environment. In a new Terminal window, return to the checkout and run `source .venv/bin/activate` before using the CLI again.

Use an appropriate USB data cable if you attach an ESP32 for bench development. The Linux `pinball.service` installer and Pi Wi-Fi controls are specific to Linux. For actual Godot playback, install a compatible Godot executable separately. See the [Development Platform](../3-build-notes/1-development-platform.md) notes for the Mac development setup.

## Windows, WSL and Docker

The easiest Windows setup is to run Pinball CTL on the Pi and use a browser on Windows. Use Windows Terminal or PowerShell for the SSH steps above.

If you want the development app to run on the Windows computer itself, **WSL 2 with Ubuntu** is an experimental option. Pinball CTL does not ship a native Windows build or a supported Docker image.

1. Follow [Microsoft’s WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install) to install WSL 2 and Ubuntu. Open **Ubuntu** from the Start menu and create the Linux account when prompted.
2. In Ubuntu, check `python3 --version`. Use a distribution with Python 3.11 or later. Run the Linux install commands above from your Ubuntu home directory (`cd ~`), then run `pinballctl start`. Open `http://localhost:8888` in the Windows browser.
3. Start with browser authoring and simulation. An attached ESP32 needs separate USB forwarding through [Microsoft’s USB/IP instructions](https://learn.microsoft.com/en-us/windows/wsl/connect-usb). That controller path, display and audio output, and cabinet operation have not been verified here.

A Linux virtual machine is another experimental way to try authoring. Docker Desktop requires a custom container and separate handling of persistent project data and devices. Its [USB/IP setup](https://docs.docker.com/desktop/features/usbip/) depends on the backend and device. For a machine that will control physical coils, use the Raspberry Pi setup and verify the actual hardware there.
