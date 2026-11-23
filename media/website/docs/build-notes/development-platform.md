# Development Platform

The development setup supports two kinds of testing. Run the webapp and runtime from a local checkout for fast iteration. Use the Raspberry Pi and ESP32-S3 bench to check deployment, serial timing, input and output behavior.

## Software and targets

| Area | Setup |
| --- | --- |
| Local development | Python 3.11 or later in a virtual environment, with the project installed in editable mode. The webapp runs through Flask and Gunicorn, and the bridge uses pyserial. |
| Cabinet host | Raspberry Pi and Linux. On a systemd installation, the admin web service can be managed separately from the runtime target and its bridge and media services. |
| Controller | ESP32-S3 over USB serial. The Arduino build toolchain produces the application, bootloader and partition images used by ESPLink. |
| Backglass | Godot player and Pi media supervisor. Sample projects live in `media/backglass/`. |
| Tests and website | Python unit tests, Node tests for browser utilities, native C++ policy tests for firmware, and the repository's Python website build. Website CI uses Python 3.12. |

[Development and testing](../developer-guide/development.md) covers installation and test commands. [App layout and services](../technical-notes/app-layout.md) explains the cabinet's process boundaries.

## Test in stages

1. Use a local checkout to verify the webapp, runtime contracts and configuration flow. Run the relevant automated tests before relying on the change.
2. Use the ESP dev board with coil power disconnected to check switch mapping, LED responses, firmware sync, auto-arming and heartbeat recovery. ESPLink reports the running firmware and installed local versions.
3. Use the cabinet bench to verify the actual switches, drivers and loads. Check timing, power and shutdown behavior with a commissioning setup suited to those parts.

[Coil Safety](../technical-notes/coil-safety.md) · [Firmware regression checks](../developer-guide/firmware-checks.md)

## Bench equipment and layout

The bench uses an ESP32-S3 development board, switches, indicator LEDs and supported peripherals such as RGB lighting, an LCD and an accelerometer. The host and controller communicate over a USB data connection.

See [Test Bench](../developer-notes/test-bench.md) for the current ball-course proposal and validation work. The [hardware inventory](../developer-notes/hardware-inventory.md) records the configured components.
