# Coil Safety

The ESP32-S3 decides when configured coils can operate. The Pi bridge supplies a heartbeat and deploys the settings you save in Hardware. The Dashboard reports the ESP's state in the **ESP32** card, and Hardware shows the reported fault reason.

## Configure each coil

In Hardware, assign the pin to **Coil** and open its driver settings. **Coil operation** defaults to **Disabled**. Enabling it makes that output eligible when the ESP is armed. **PIN Safe** is the electrical off level, either HIGH or LOW, and must match the driver circuit. Rule ON and OFF requests describe activation and release.

Save the mapping on the Pi, then use **Sync to ESP**. Hardware Sync applies and checks the coil configuration before deploying the mapping. For driver modes and limits, follow [Coil operating modes](coil-operating-modes.md).

## Automatic arming

On startup and after deployment, the ESP waits for the coil configuration and PIN Safe levels to agree with the mapping. It also requires loaded rules, a healthy firmware loop and safety timer, about one second of fresh bridge heartbeats, elapsed cooldowns, and at least one enabled primary coil output. The admin webapp and game start control are independent of arming.

The bridge normally sends a challenge-response heartbeat every **250 ms**. After **one second** without a valid heartbeat, the ESP disarms and drives configured outputs to PIN Safe. When the heartbeat returns, the ESP runs the arming checks again. Recovery clears stale gestures so arming itself leaves the coils off.

| Dashboard state | Meaning |
| --- | --- |
| **Armed** | The ESP can accept eligible output actions for enabled channels. |
| **Disarmed** | The ESP has inhibited coil activation and holds configured coil outputs at PIN Safe. |
| **Fault** | The ESP reports a latched safety fault. Check the reason in Hardware. |
| **Unknown** | The Dashboard has no fresh safety report from the ESP. |

## Routine input and latched faults

A press during a coil's cooldown is discarded. A fresh press can fire after the interval, and other coils remain available. Holding a button follows the configured driver mode and its hard limits. Repeated activation requests cannot extend an existing pulse or hold.

Firmware watchdog trips, overlong pulses or holds, invalid pulse requests and some invalid coil configurations latch a fault. Correct the cause before issuing an explicit fault reset or restarting the ESP. A direct firmware `DISABLE` command inhibits arming for the rest of that ESP boot. The dashboard badge is read-only.

Hardware and rules sync disarm the ESP while deployment runs. The bridge drains outstanding event confirmations and suppresses stale presses during startup and transfer. Genuine event delivery stalls still trigger the [bridge overload checks](bridge-performance.md).

## Bench verification

Start with coil power disconnected. Check the configured PIN Safe levels, the enabled and disabled channels, and press/release behavior. Test quick taps and a brief bridge interruption, then confirm that the ESP disarms and rearms without replaying old presses. The driver and power circuit need a safe off state during reset and before firmware configures the GPIO.

Bench checks with LEDs can validate response and recovery. Choose coil limits for the actual coil and driver, then verify pulse timing, hold behavior, current, temperature and shutdown under load on the target machine. Use a suitable driver, fusing and protection for the circuit. [Firmware regression checks](../developer-guide/firmware-checks.md)
