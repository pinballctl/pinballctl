"""Describe mapped hardware for rule triggers and actions."""

from typing import Any, Dict


def normalize_event_name(raw: Any) -> str:
    s = str(raw or "").upper()
    out = []
    prev_us = False
    for ch in s:
        if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    while out and out[0] == "_":
        out.pop(0)
    while out and out[-1] == "_":
        out.pop()
    return "".join(out)


def _parse_gpio_pin(uid: str) -> int | None:
    parts = str(uid or "").split("__")
    if len(parts) < 4:
        return None
    if parts[-2] != "GPIO":
        return None
    chan = str(parts[-1] or "").strip()
    if not chan.isdigit():
        return None
    try:
        pin = int(chan)
    except Exception:
        return None
    return pin if pin >= 0 else None


def build_hardware_devices(mapping_data: Dict[str, Any]) -> tuple[list[dict], Dict[str, Dict[str, Any]]]:
    function_map = {
        "Button": ("button", "input"),
        "Switch": ("switch", "input"),
        "Accelerometer": ("accelerometer", "input"),
        "NFC": ("nfc", "input"),
        "Solenoid": ("coil", "output"),
        "Coil": ("coil", "output"),
        "LED": ("output", "output"),
        "RGB Strip": ("led", "output"),
    }
    devices: list[dict] = []
    lcd_by_id: Dict[str, Dict[str, Any]] = {}
    lcd_groups: Dict[str, list[dict]] = {}
    linked_component_ids: set[str] = set()
    primary_uids: set[str] = set()
    for uid, row in mapping_data.items():
        if not isinstance(row, dict):
            continue
        comp_id = str(row.get("componentId") or "").strip()
        if comp_id and (row.get("secondaryPinUid") or row.get("linkedPrimaryUid") or row.get("componentRole")):
            linked_component_ids.add(comp_id)
        linked_primary = str(row.get("linkedPrimaryUid") or "").strip()
        if linked_primary:
            primary_uids.add(linked_primary)

    seen_linked_entries: set[str] = set()

    for uid, row in mapping_data.items():
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        if not fn:
            continue
        if fn in ("Coil", "Solenoid") and row.get("coilMode") == "Hold winding":
            # A hold winding is controlled through its paired power pin only.
            continue
        friendly = str(row.get("friendly") or "").strip() or str(uid)
        if fn in ("LCD Display", "LCD1602"):
            comp_id = str(row.get("componentId") or "").strip()
            role = str(row.get("componentRole") or "").strip().upper()
            if not comp_id or role not in ("SDA", "SCL"):
                continue
            lcd_groups.setdefault(comp_id, []).append(
                {
                    "uid": str(uid),
                    "friendly": friendly,
                    "role": role,
                    "pin": _parse_gpio_pin(str(uid)),
                    "address": str(row.get("i2cAddress") or "0x27").strip() or "0x27",
                    "cols": row.get("lcdCols", 16),
                    "rows": row.get("lcdRows", 2),
                    "driver": str(row.get("driver") or "Default").strip() or "Default",
                }
            )
            continue

        linked_primary = str(row.get("linkedPrimaryUid") or "").strip()
        if linked_primary:
            # Secondary rows of linked components should never appear separately.
            continue

        comp_id = str(row.get("componentId") or "").strip()
        dedupe_key = ""
        if comp_id and comp_id in linked_component_ids:
            dedupe_key = f"comp:{comp_id}"
        elif str(uid) in primary_uids:
            dedupe_key = f"uid:{uid}"
        if dedupe_key:
            if dedupe_key in seen_linked_entries:
                continue
            seen_linked_entries.add(dedupe_key)

        device_class, direction = function_map.get(fn, ("other", "unknown"))
        devices.append({
            "id": str(uid),
            "friendly": friendly,
            "function": fn,
            "deviceClass": device_class,
            "direction": direction,
            "eventBase": (normalize_event_name(friendly) or normalize_event_name(uid)).removesuffix("_N"),
        })

    for comp_id, rows in lcd_groups.items():
        if len(rows) < 2:
            continue
        sda = next((r for r in rows if r.get("role") == "SDA"), None)
        scl = next((r for r in rows if r.get("role") == "SCL"), None)
        if not sda or not scl:
            continue
        sda_pin = sda.get("pin")
        scl_pin = scl.get("pin")
        if not isinstance(sda_pin, int) or not isinstance(scl_pin, int):
            continue
        if sda_pin == scl_pin:
            continue
        address_raw = str(sda.get("address") or scl.get("address") or "0x27").strip() or "0x27"
        try:
            address_val = int(address_raw, 0)
        except Exception:
            address_val = 0x27
        if address_val < 0x03 or address_val > 0x77:
            address_val = 0x27
        try:
            cols = int(sda.get("cols", 16))
        except Exception:
            cols = 16
        try:
            rows_count = int(sda.get("rows", 2))
        except Exception:
            rows_count = 2
        cols = max(8, min(40, cols))
        rows_count = max(1, min(4, rows_count))
        friendly = next((str(r.get("friendly") or "").strip() for r in rows if str(r.get("friendly") or "").strip()), comp_id)
        did = f"LCD_DISPLAY::{comp_id}"
        entry = {
            "id": did,
            "friendly": friendly,
            "function": "LCD Display",
            "deviceClass": "lcd",
            "direction": "display",
            "eventBase": (normalize_event_name(friendly) or normalize_event_name(comp_id)).removesuffix("_N"),
            "config": {
                "componentId": comp_id,
                "sdaPin": sda_pin,
                "sclPin": scl_pin,
                "address": f"0x{address_val:02x}",
                "cols": cols,
                "rows": rows_count,
                "driver": str(sda.get("driver") or scl.get("driver") or "Default").strip() or "Default",
                "sdaUid": str(sda.get("uid") or ""),
                "sclUid": str(scl.get("uid") or ""),
            },
        }
        devices.append(entry)
        lcd_by_id[did] = entry["config"]

    devices.sort(key=lambda d: str(d.get("friendly") or d.get("id") or "").lower())
    return devices, lcd_by_id
