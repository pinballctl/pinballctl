"""Pure physical-ball transitions, called only inside the manager transaction."""

from uuid import uuid4


def initial():
    return {
        "inPlay": None,
        "confidence": "unknown",
        "zones": {},
        "pending": [],
        "sensors": {},
        "reason": "No physical observations yet",
        "lastObservation": None,
        "alerts": {},
    }


def observe(state, config, sensor, active, now, event):
    mappings = [m for m in config.get("sensors", []) if m["source"] == sensor]
    if not mappings:
        return None
    previous = state["sensors"].get(sensor)
    state["sensors"][sensor] = {"active": active, "at": now}
    if previous and previous["active"] == active:
        return None
    for mapping in mappings:
        if active != mapping.get("active", True) and mapping["role"] != "occupancy":
            continue
        if previous and now - previous["at"] < mapping.get("debounceMs", 50):
            continue
        role = mapping["role"]
        zone = mapping.get("zone", "")
        state["lastObservation"] = now
        if role == "launch":
            state["inPlay"] = (state["inPlay"] or 0) + 1
            state["confidence"] = "inferred"
            state["reason"] = "Shooter departure observed; destination inferred"
            event("BALL_LAUNCHED", {"sensor": sensor})
            result = "launch"
        elif role == "drain":
            if state["inPlay"] is None or state["inPlay"] <= 0:
                state["confidence"] = "unknown"
                state["reason"] = "Drain without a corresponding in-play estimate"
                result = "uncertain"
            else:
                state["inPlay"] -= 1
                state["reason"] = "Drain passage observed; trough occupancy unknown"
                result = "drain"
            event("BALL_DRAINED", {"sensor": sensor, "inPlay": state["inPlay"]})
        elif role in ("occupancy", "entrance", "exit", "lock"):
            prior = state["zones"].get(zone, {"count": None})["count"]
            count = (
                None
                if prior is None
                else prior + (1 if role in ("entrance", "lock") else -1)
            )
            confidence = "inferred"
            if role == "occupancy":
                sensors = [
                    m
                    for m in config["sensors"]
                    if m.get("zone") == zone and m["role"] == "occupancy"
                ]
                known = all(m["source"] in state["sensors"] for m in sensors)
                count = (
                    sum(
                        state["sensors"].get(m["source"], {}).get("active")
                        == m.get("active", True)
                        for m in sensors
                    )
                    if known
                    else None
                )
                confidence = "confirmed" if known else "unknown"
            state["zones"][zone] = {"count": count, "confidence": confidence, "at": now}
            result = "observation"
        else:
            continue
        for movement in list(state["pending"]):
            arrival = role in ("entrance", "lock") or (
                role == "occupancy" and active == mapping.get("active", True)
            )
            if arrival and zone and movement["destination"] == zone:
                state["pending"].remove(movement)
                event("BALL_MOVEMENT_CONFIRMED", {"movementId": movement["id"]})
        event("BALL_OBSERVED", {"sensor": sensor, "role": role, "zone": zone})
        return result
    return None


def movement(state, config, device_id, now, event):
    device = next((d for d in config.get("devices", []) if d["id"] == device_id), None)
    if not device:
        raise ValueError("Unknown ball device")
    if not device.get("destination"):
        raise ValueError("Configure an expected destination before requesting movement")
    observed = state["zones"].get(device_id, {})
    if now - observed.get("at", 0) > config.get("staleMs", 30000):
        raise ValueError("Occupancy observation is stale")
    if observed.get("confidence") != "confirmed" or not observed.get("count"):
        raise ValueError("Release requires confirmed occupancy")
    if any(p["deviceId"] == device_id for p in state["pending"]):
        raise ValueError("Movement already pending")
    item = {
        "id": uuid4().hex,
        "deviceId": device_id,
        "destination": device.get("destination", ""),
        "deadline": now + device.get("timeoutMs", 5000),
    }
    state["pending"].append(item)
    event("BALL_MOVEMENT_REQUESTED", dict(item))
    return item


def tick(state, config, now, event):
    expired = [p for p in state["pending"] if p["deadline"] <= now]
    for item in expired:
        state["pending"].remove(item)
        event("BALL_MOVEMENT_TIMEOUT", {"movementId": item["id"]})
        state["confidence"] = "unknown"
        state["reason"] = "Movement timed out; manual reconciliation required"
    alerts = state.setdefault("alerts", {})
    for source, sensor in state["sensors"].items():
        if (
            sensor["active"]
            and now - sensor["at"] > config.get("staleMs", 30000)
            and source not in alerts
        ):
            alerts[source] = "Input active beyond configured freshness limit"
            event("BALL_SENSOR_STALE", {"sensor": source, "reason": alerts[source]})
        elif not sensor["active"]:
            alerts.pop(source, None)
    stale = bool(alerts)
    return bool(expired), not stale if state["sensors"] else False
