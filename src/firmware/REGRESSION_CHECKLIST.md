# Firmware Regression Checklist

Use this quick checklist before/after firmware changes that affect input/output runtime behavior.

## 1) Button Drivers (`Button/Default`)
- Verify each mapped button pin emits `PRESSED` then `RELEASED` for a single press.
- Verify `CLICKED` emits only after press+release completes.
- Verify `DOUBLE_CLICKED` respects configured `windowMs`.
- Verify `HELD` starts after `minMs` and repeats only when `repeatWhileHeld=true` at `repeatMs` cadence.
- Verify stale/out-of-sequence events are dropped and affected outputs return to mapping safe state.

## 2) LCD Drivers (`LcdDisplay/LCD1602I2C`)
- On boot, confirm `DRIVER_WIRING` log includes LCD target, function, driver, and impl.
- Trigger `LCD_SET` and verify both lines render with expected truncation by `cols`.
- Verify declared SDA/SCL mapping works; if fallback swap is used, `LCD_STATUS.swappedPins=true` is reported.
- Verify backlight auto-sleeps after 60s of no text update.
- Verify next `LCD_SET` wakes display immediately and writes both lines.

## 3) Coil/Output Drivers (`Coil/Default`, `LED/Default`)
- Verify `PIN_SET` / rule-driven output changes resolve correct function+driver (from mapping).
- Verify coil output transitions match rule action timing (pulse/high/low) and no stuck-high after release.
- Verify dropped events restore all touched outputs to safe state from mapping.
- Verify manual event fire from UI and physical ESP input both produce identical runtime behavior.

## 4) Boot Wiring Self-Check
- On each firmware boot with mapping present, verify:
  - `MAP_BOOT` status is `ok`.
  - One `DRIVER_WIRING` frame is emitted.
  - `count` matches expected mapped driver bindings.
  - Each binding reports `target`, `function`, `driver`, and resolved `impl`.
