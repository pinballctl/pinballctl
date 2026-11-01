"""Versioned owner contract shared by Rules, API and manager execution."""

VERSION = 1
LEGACY = {
    "GAME_ACTIVE",
    "BALL_IN_PLAY",
    "HAS_CREDIT",
    "CREDITS",
    "BALL_NUMBER",
    "PLAYER_COUNT",
    "BALL_STARTED",
    "BALL_ENDED",
    "CREDITS_CHANGED",
    "HAS_CREDIT_TRUE",
    "HAS_CREDIT_FALSE",
}
GAME_EVENTS = (
    "GAME_STARTED",
    "GAME_ENDED",
    "GAME_START_REJECTED",
    "PLAYER_ADDED",
    "PLAYER_ADD_REJECTED",
    "PLAYER_CHANGED",
    "BALL_TURN_STARTED",
    "BALL_TURN_ENDED",
    "CREDIT_ADDED",
    "CREDIT_SPENT",
    "CREDIT_BALANCE_CHANGED",
    "EXTRA_BALL_AWARDED",
    "BALL_SAVE_ACTIVATED",
    "BALL_SAVE_EXPIRED",
    "RECOVERY_REQUIRED",
    "GAME_PAUSED",
    "GAME_RESUMED",
)
BALL_EVENTS = (
    "BALL_OBSERVED",
    "BALL_LAUNCHED",
    "BALL_DRAINED",
    "BALL_MOVEMENT_REQUESTED",
    "BALL_MOVEMENT_CONFIRMED",
    "BALL_MOVEMENT_TIMEOUT",
    "BALL_RECONCILED",
    "BALL_SENSOR_STALE",
)
COMMANDS = {
    "REQUEST_START_GAME": {},
    "REQUEST_ADD_PLAYER": {},
    "REQUEST_AWARD_CREDIT": {"units": "integer"},
    "REQUEST_AWARD_EXTRA_BALL": {"count": "integer"},
    "REQUEST_BALL_SAVE": {"durationMs": "integer"},
    "REQUEST_END_GAME": {},
    "REQUEST_PAUSE_GAME": {},
    "REQUEST_RESUME_GAME": {},
    "REQUEST_BALL_MOVEMENT": {"deviceId": "text"},
}
GAME_FIELDS = {
    "status": "text",
    "currentPlayer": "integer",
    "playerCount": "integer",
    "ballNumber": "integer",
    "credits": "integer",
    "freePlay": "boolean",
    "extraBalls": "integer",
    "ballSave": "boolean",
}
BALL_FIELDS = {
    "inPlay": "integer",
    "confidence": "text",
    "pending": "integer",
    "sensorFresh": "boolean",
    "observedCount": "integer",
    "occupancyConfidence": "text",
}
RESERVED = set(GAME_EVENTS + BALL_EVENTS) | LEGACY | set(COMMANDS)
PRIVILEGED = {
    "REQUEST_AWARD_CREDIT",
    "REQUEST_END_GAME",
    "REQUEST_PAUSE_GAME",
    "REQUEST_RESUME_GAME",
}


def command_valid(command, params):
    if (
        command not in COMMANDS
        or not isinstance(params, dict)
        or set(params) - set(COMMANDS[command])
    ):
        return False
    for key, kind in COMMANDS[command].items():
        value = params.get(key)
        if kind == "integer" and (type(value) is not int or not 0 < value <= 10000000):
            return False
        if kind == "text" and (not isinstance(value, str) or not 0 < len(value) <= 100):
            return False
    return True


def contract():
    return {
        "version": VERSION,
        "commands": COMMANDS,
        "events": {"game": GAME_EVENTS, "ball": BALL_EVENTS},
        "conditions": {"game": GAME_FIELDS, "ball": BALL_FIELDS},
        "reserved": sorted(RESERVED),
    }


def extend_rules_registry(base):
    import copy

    data = copy.deepcopy(base)
    categories = data.get("triggers", {}).get("system", {}).get("categories", {})
    for key in ("game", "credits"):
        categories.pop(key, None)
    for kind, events in (("game", GAME_EVENTS), ("ball", BALL_EVENTS)):
        data["triggers"][kind] = {
            "label": kind.title() + " Management",
            "events": list(events),
        }
        fields = GAME_FIELDS if kind == "game" else BALL_FIELDS
        data["conditions"][kind] = {
            "label": kind.title() + " Management",
            "fields": fields,
            "operators": ["==", "!=", ">", ">=", "<", "<="],
        }
    for key in ("flag", "counter"):
        plural = "flags" if key == "flag" else "counters"
        data["conditions"][key][plural] = [
            x for x in data["conditions"][key].get(plural, []) if x not in LEGACY
        ]
    for command, params in COMMANDS.items():
        if command in PRIVILEGED:
            continue
        fields = [
            {
                "bind": "params." + key,
                "label": key,
                "kind": "number" if typ == "integer" else "text",
                "default": 1 if typ == "integer" else "",
            }
            for key, typ in params.items()
        ]
        owner = "ball" if command == "REQUEST_BALL_MOVEMENT" else "game"
        data["actions"][command.lower()] = {
            "label": command.removeprefix("REQUEST_").replace("_", " ").title(),
            "ui": {
                "module": owner,
                "pathKey": command.lower(),
                "actionLabel": command.removeprefix("REQUEST_")
                .replace("_", " ")
                .title(),
                "fields": fields,
            },
            "description": "Request validated "
            + owner
            + " operation; the manager may reject it.",
        }
    data["managerContract"] = contract()
    return data


def rule_issues(rule):
    issues = []

    def items(kind):
        return list(rule.get(kind + "s") or []) + [
            item
            for group in (rule.get(kind + "Groups") or {}).get("groups", [])
            for item in group.get("items", [])
        ]

    for action in rule.get("actions", []):
        kind = action.get("type")
        target = action.get("target", "")
        if kind in ("set_flag", "set_counter", "inc_counter") and target in LEGACY:
            issues.append("Manager state is read-only: " + target)
        if kind == "emit_event" and (
            target in RESERVED or (action.get("params") or {}).get("name") in RESERVED
        ):
            issues.append("Manager result events cannot be emitted manually")
        if str(kind).upper() in COMMANDS and not command_valid(
            kind.upper(), action.get("params") or {}
        ):
            issues.append("Invalid manager command: " + kind)
    for condition in items("condition"):
        kind = condition.get("type")
        key = condition.get("key")
        if kind in ("flag", "counter") and key in LEGACY:
            issues.append("Use the manager read-only condition for " + key)
        if kind in ("game", "ball"):
            fields = GAME_FIELDS if kind == "game" else BALL_FIELDS
            typ = fields.get(key)
            value = condition.get("value")
            if (
                not typ
                or (typ == "integer" and type(value) is not int)
                or (typ == "boolean" and type(value) is not bool)
                or (typ == "text" and not isinstance(value, str))
            ):
                issues.append("Invalid manager condition")
    for trigger in items("trigger"):
        if trigger.get("event") in LEGACY:
            issues.append("Obsolete game event: " + trigger["event"])
        if trigger.get("event") in GAME_EVENTS + BALL_EVENTS and trigger.get(
            "type"
        ) not in ("game", "ball"):
            issues.append("Use a manager event trigger")
    return list(dict.fromkeys(issues))
