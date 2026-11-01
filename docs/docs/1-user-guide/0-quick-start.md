# Quick Start

Make one physical switch appear in the event log, then use it to fire a custom test event. Keep coils and other high-current outputs disconnected throughout. A successful test proves the input-to-rule path; it does not prove output wiring is safe.

## Before you start

You need a Raspberry Pi 5 running Raspberry Pi OS 64-bit, suitable Pi power, network access, an ESP32-S3 with compatible firmware, a USB **data** cable and one safely wired supported input. Use the pin map and voltage limits for your actual board; this guide does not assign a GPIO number. Have a browser and a Pi terminal available.

This manual follows current committed `main`, including Backup / Restore. The older `v0.10.0` tag lacks that module. The package version number alone cannot identify which code you have. Record the Git revision during installation. If you need the full explanation or service installation, use [Detailed Setup](1-getting-started.md).

## 1. Prepare and reach the Pi

1. In [Raspberry Pi Imager](https://www.raspberrypi.com/software/), choose your Pi model and Raspberry Pi OS 64-bit. Configure your own username, network and SSH access before writing the card.
2. Boot the Pi, then sign in at its console or use SSH with the hostname/address and username you configured.
3. Open a terminal and run `python3 --version`. The application requires Python 3.11 or later.

**Expected result:** you can run commands on the Pi. If you cannot connect, confirm the Pi address at your router or local console. Do not assume every installation is named `raspberrypi.local`.

## 2. Install and identify the development build

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

If installation fails, keep the error message, check Python and network access, and use [Detailed Setup](1-getting-started.md). Do not install a second copy over an existing running service. These commands select a development build; they are not a claim that it has passed target-hardware testing.

## 3. Open the application and secure access

1. Use the Pi's network address with port **8888** for the manual `pinballctl start` above. For example, an address of `192.168.1.50` gives `http://192.168.1.50:8888`; replace that example address with your Pi's address.
2. Sign in. The source defaults are username `admin` and password `password` on an unconfigured installation. Saved or environment-provided credentials can override them.
3. Open **Settings → Access**, set your own credentials and choose **Save Changes**. Verify the new login before relying on unattended access.

**Expected result:** the dashboard opens and your new credentials work. If the interface is unreachable, check `pinballctl status` and the port. An installed `pinball.service` uses **8000** by default; do not start both modes together.

<img src="./media/screenshot-login.webp" alt="Login screen with username and password fields" style="width:100%;height:auto;">

**Screen guide:** enter the installation's credentials in the two fields. Never share screenshots containing a real password or session information.

## 4. Connect and check the ESP

1. Keep output power disconnected. Connect the ESP32-S3 using a USB data cable.
2. Open **ESPLink** and check live connection status, controller identity and firmware information.
3. Resolve version/connection warnings before deploying configuration. Use [Firmware](12-firmware.md) for compatible images and [ESPLink](11-esplink.md) for connection checks.

**Expected result:** a live connected controller, not merely cached identity details. If offline, check the cable, serial port, permissions and bridge status; a charge-only cable cannot work.

<img src="./media/screenshot-feature-esplink.webp" alt="ESPLink workspace showing connection, controller and firmware information" style="width:100%;height:auto;">

**Screen guide:** check the connection state first, then identity and version. A development screenshot cannot confirm your connected hardware.

## 5. Name and observe one input

1. Open **Hardware**, then **Reload Pins** with the ESP connected.
2. Identify your safely wired input from its board/channel and UID. Give it a friendly name such as **Test target** and select the matching input function. Check polarity and supported input options against the circuit.
3. Choose **Save Changes**, then **Sync to ESP**. Wait for the reported result.
4. Open **Logs**, select the event log and operate the switch once. Record the actual event name and source UID. Confirm a release event as well when that input type provides one.

**Expected result:** the event identifies your input and occurs when you operate it. If silent, check the live connection, pin identity, input polarity, saved mapping and sync result before creating a rule. Do not guess an event name from a screenshot.

<img src="./media/screenshot-feature-hardware.webp" alt="Hardware Mapping table showing pin UIDs, channels, friendly names and functions" style="width:100%;height:auto;">

**Screen guide:** board/channel identifies the physical connection; the UID identifies it to rules. Friendly names make the same device easier to find elsewhere.

## 6. Create and test a safe rule

1. Open **Rules → Add Rule** and name it **Test target** in **Metadata**. Keep it enabled.
2. In **Triggers**, choose the actual hardware source and event observed in step 5. Leave **Conditions** empty for this first test.
3. In **Actions**, choose the System event action (**Fire Event** / **Emit Event**), set **Event Type** to **Custom** and enter `TEST_TARGET_SEEN` as its event name. Do not select a pulse, output, coil or existing gameplay event. Check that no other rule listens for this new name.
4. Review **Summary**, correct validation errors, then **Save**. Check sync status and use **Sync to ESP** when required for deployed behaviour. The custom event action runs on the Pi, so the application and bridge must remain running.
5. Operate the physical switch once and find both the original input event and `TEST_TARGET_SEEN` in the event log.

**Expected result:** the custom event follows your switch event without energising an output. If it does not, check the exact trigger/source, enabled state, saved rule, validation and sync status. Do not use the custom result event as its own trigger: that would create a loop.

<img src="./media/screenshot-feature-rules-tab-actions.webp" alt="Rules Actions tab where an action type and its parameters are configured" style="width:100%;height:auto;">

**Screen guide:** choose the event action and its Custom event type for this exercise. Other configured actions in a sample project are not instructions to operate hardware.

## What next?

Keep the test rule clearly named, or disable it after testing. Create and download a [backup](25-backup-restore.md), then learn [Rules](7.1-rules.md), [Lighting](8-lighting.md) or [Audio](17-audio.md). Use [Troubleshooting](26-troubleshooting.md) when the observed result differs from the expected result.
