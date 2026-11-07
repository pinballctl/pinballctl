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


LAUNCH_HANDOFF_MS = 500


def infer_trough(state, config, evidence, game_status, settling, now):
    """Display-only estimate. Keep inferred counts out of the movement safety state."""
    trough_id = config.get("inferredTrough")
    if not trough_id:
        return None
    unknown = {"location": trough_id, "count": None, "confidence": "unknown"}
    if settling or state["pending"] or game_status in ("RECOVERY_REQUIRED", "FAULT"):
        return unknown
    roles = {sensor["role"] for sensor in config["sensors"]}
    if not {"launch", "drain"} <= roles:
        return unknown
    in_play = state["inPlay"]
    if in_play is None and game_status in ("IDLE", "GAME_ENDED"):
        in_play = 0
    if in_play is None:
        return unknown
    elsewhere = in_play
    for location in config["devices"]:
        ident = location["id"]
        if ident == trough_id:
            continue
        reading = evidence[ident]
        if (not reading["configured"] or reading["read"] != reading["configured"]
                or reading["active"] > location["capacity"]):
            return unknown
        elsewhere += reading["active"]
    handoff = state.get("troughHandoff")
    if handoff:
        if now - handoff["at"] > LAUNCH_HANDOFF_MS:
            return unknown
        # During either ordering of the edges, count the ball exactly once.
        elsewhere += 1 if handoff["waitingFor"] == "launch" else -1
    count = config["inventory"] - elsewhere
    capacity = next(d["capacity"] for d in config["devices"] if d["id"] == trough_id)
    if elsewhere < 0 or not 0 <= count <= capacity:
        return unknown
    return {"location": trough_id, "count": count, "confidence": "inferred"}


def update_trough_handoff(state, config, role, zone, prior, count, now):
    if not config.get("inferredTrough"):
        return
    launcher = config["inferredLauncher"]
    handoff = state.get("troughHandoff", {})
    if role == "launch":
        if handoff.get("waitingFor") == "launch":
            state.pop("troughHandoff", None)
        elif state["zones"].get(launcher, {}).get("count") == 1:
            state["troughHandoff"] = {"waitingFor": "clear", "at": now}
    elif role == "occupancy" and zone == launcher:
        if count == 1:
            state.pop("troughHandoff", None)
        elif prior == 1 and count == 0:
            if handoff.get("waitingFor") == "clear":
                state.pop("troughHandoff", None)
            else:
                state["troughHandoff"] = {"waitingFor": "launch", "at": now}


def observe(state, config, sensor, active, now, event, *, track_play=True):
    mappings = [m for m in config.get("sensors", []) if m["source"] == sensor]
    if not mappings:
        return None
    previous = state["sensors"].get(sensor)
    state["sensors"][sensor] = {"active": active, "at": now}
    if previous and previous["active"] == active:
        mapping = mappings[0]
        zone = mapping.get("zone", "")
        observed = state["zones"].get(zone)
        if mapping["role"] == "occupancy" and observed and observed["confidence"] == "confirmed":
            observed["at"] = min(
                state["sensors"].get(m["source"], {}).get("at", 0)
                for m in config["sensors"]
                if m.get("zone", "") == zone and m["role"] == "occupancy"
            )
        return None
    for mapping in mappings:
        if active != mapping.get("active", True) and mapping["role"] != "occupancy":
            continue
        if previous and now - previous["at"] < mapping.get("debounceMs", 50):
            continue
        role = mapping["role"]
        if not track_play and role in ("launch", "drain"):
            continue
        zone = mapping.get("zone", "")
        state["lastObservation"] = now
        if role == "launch":
            state["inPlay"] = (state["inPlay"] or 0) + 1
            state["confidence"] = "inferred"
            state["reason"] = "Shooter departure observed; destination inferred"
            update_trough_handoff(state, config, role, zone, None, None, now)
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
            observed_at = min(state["sensors"][m["source"]]["at"] for m in sensors) if confidence == "confirmed" else now
            state["zones"][zone] = {"count": count, "confidence": confidence, "at": observed_at}
            update_trough_handoff(state, config, role, zone, prior, count, now)
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
