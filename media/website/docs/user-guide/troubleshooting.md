# Troubleshooting

Record when the problem occurred and use that time to find the relevant entries in **Logs**.

## At a glance

**Dashboard and ESPLink**. Establish which processes and devices are online.

**Logs → Events**. Record the actual input name, source and time.

**Hardware / Rules**. Compare that evidence with the saved mapping and trigger.

## Before you start

Record the firmware version, web port, time of the failure and exact error text. Have local console or Ethernet access if changing networks. Keep a project backup before cleanup, restore or upgrades. Do not share credentials or unredacted private project data in diagnostic screenshots.

## Web interface is unreachable

1. **First safe check:** confirm the Pi is powered and reachable at its current network address.
2. Run `pinballctl status` from the active checkout environment. The manual web server defaults to **8888**. The systemd web service uses **8000**. Confirm that the address and port match your running mode.
3. For systemd, inspect `systemctl status pinball-web.service` and `journalctl -u pinball-web.service`. Use `pinballctl status` to find the web error log in either mode.
4. Correct the address, failed service or network issue and reload. Do not start duplicate web/bridge instances to hide a failure.

**Recovery result:** login loads using the existing installation credentials. Continue with [Detailed Setup](getting-started.md) or [Wi-Fi](wifi.md).

## ESP is offline

1. **First safe check:** remove output power and confirm a USB data cable is firmly connected.
2. Inspect live ESPLink connection/serial port and bridge status. Cached chip/version details are not a live link.
3. Check cable, Linux serial permissions, device identity and Bridge logs. Resolve compatibility errors before deploying anything.
4. Reconnect/start the intended bridge and confirm fresh status. Do not re-arm to work around a persistent disconnect or fault.

**Recovery result:** the intended ESP answers live status/utility checks. Continue with [ESPLink](esplink.md) and [Firmware](firmware.md).

## A physical input is silent or inverted

1. **First safe check:** keep outputs disabled and verify input wiring/voltage/polarity against the actual board.
2. Confirm its UID/board/channel, selected function and saved Hardware mapping.
3. Check Hardware sync and observe an unfiltered **Events** log while operating only that input.
4. Correct one mapping/wiring issue, save/sync and repeat a single press/release test. Avoid using Show all Pins to reassign reserved pins.

**Recovery result:** the input's actual event and source appear at the expected transition. Continue with [Hardware](hardware.md) and [Events in Logs](logs.md#find-and-inspect-an-event).

## An input arrives but its rule does not run

1. **First safe check:** keep coil power disconnected and read the actual event name/source from Logs.
2. Match that source/event in the rule, verify enabled state and correct validation errors.
3. Check saved state, sync status and each condition. A counter/flag must be changed by a real producer; a time-since condition does not schedule a timer.
4. Retest with a distinct non-coil custom event, then reintroduce conditions one at a time. Check duplicate rules/self-triggering events if the response repeats.

**Recovery result:** one input gives the intended derived event/effect. Continue with [Rules](rules.md) and [Rules Wizard](rules.md#rules-wizard).

## Save or sync fails

1. **First safe check:** preserve the exact validation/transfer error before retrying.
2. Fix missing required fields and broken references in the owning module. Check free storage and service-user write access for save errors.
3. For sync, check the live ESP connection, firmware compatibility and Bridge logs. Saving and deploying are separate operations.
4. Save again, then sync and inspect the completion status. Do not claim deployment from a saved timestamp alone.

**Recovery result:** authored configuration is saved and the appropriate deployed status is confirmed. Continue with [Integrity Check](integrity-check.md), [Logs](logs.md) and [ESPLink](esplink.md).

## Lighting, audio or display content is missing

1. **First safe check:** stop unintended looping content, lower audio volume and keep physical outputs disabled during event tests.
2. Preview one saved scene/cue directly. Check fixture cast and lighting sync, audio output/mute/device access, or Media asset/layer/display target respectively.
3. If direct preview works, inspect the Rules trigger and saved scene/cue reference. If only the browser preview works, inspect the actual Godot runtime, executable/display session and logs.
4. Test one layer/cue/fixture first, then restore the intended composition and playback policy.

**Recovery result:** the intended real output is observed, not merely a successful upload. Continue with [Lighting](lighting.md), [Audio](audio.md), [Media](media.md) or [Godot](godot.md).

## Restore fails or leaves the bridge stopped

1. **First safe check:** leave gameplay and outputs stopped. Preserve the backup store, recovery journal and reported recovery archive reference.
2. Read whether the failure happened before publication, during rollback or after successful data restoration but failed bridge restart.
3. Follow the [Backup / Restore recovery procedure](backup-restore.md#maintenance-recovery-and-limits). Do not delete recovery markers/journals to force the UI open.
4. Finish recovery, verify project configuration and restart the bridge manually only when the reported outcome permits it.

**Recovery result:** project access and data consistency are restored before any ESP sync or re-arming.

## Physical ball position is uncertain

1. **First safe check:** stop gameplay and remove output power before entering the playfield or mechanisms.
2. Inspect the physical machine and sensor state; do not treat a drawn ball, logical counter or estimated position as a confirmed physical observation.
3. Reconcile the actual situation using the recovery workflow for the installed implementation. See [Ball Management](ball-management.md) for observation confidence and reconciliation. A search or launch request is not proof of a safe physical state.
4. Retest sensors and interlocks before restarting. Do not blindly pulse eject/launch coils to find a missing ball.

**Recovery result:** physical state is understood and hardware can be restarted deliberately. Continue with [Hardware](hardware.md), [Logs](logs.md) and your mechanism's electrical documentation.

## Keep useful evidence

Record the symptom, time, revision, firmware identity, error text and result of each safe check in [Service Log](service-log.md). Use [Performance](performance.md) for rate/backlog/latency evidence. For help, share the smallest relevant redacted extract; do not publish private archives or credentials.
