"""Transactional Pi rule evaluation shared by bridge and offline event ingress.

State is per installation, not per web worker. Unknown conditions fail closed.
"""
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import fcntl
import json
import math
import logging
from pathlib import Path
import sqlite3
from threading import local
import time

from . import scoped_state

STATE_ACTIONS = {'set_flag', 'set_counter', 'inc_counter'}
NATIVE_ACTIONS = {'set_output', 'pulse', 'set_lighting_pixels', 'set_lcd_text'}
ESP_ACTION_ROUTING_VERSION = 3
LIMIT = 2**31 - 1
MINIMUM = -(2**31)
_LOCAL = local()


from pinballctl.runtime.game.registry import COMMANDS, PRIVILEGED, LEGACY, rule_issues, command_valid

SUPPORTED_ACTIONS = {key.lower() for key in COMMANDS if key not in PRIVILEGED} | NATIVE_ACTIONS | STATE_ACTIONS | scoped_state.TIMER_ACTIONS | {
    'emit_event', 'apply_lighting_scene', 'stop_lighting_scene', 'play_audio_cue',
    'stop_audio_cue', 'toggle_audio_cue', 'media_play_scene', 'media_stop_scene', 'media_stop_all'}


def valid_actions(actions):
    if not isinstance(actions, list):
        return False
    for action in actions:
        if not isinstance(action, dict) or action.get('type') not in SUPPORTED_ACTIONS:
            return False
        values = action.get('params') or {}
        if not isinstance(values, dict):
            return False
        kind = action['type']
        if kind.upper() in COMMANDS and not command_valid(kind.upper(),values):return False
        if kind in scoped_state.TIMER_ACTIONS and (not isinstance(action.get('target'), str) or not action['target'] or values):
            return False
        if kind in STATE_ACTIONS:
            if action.get('target') in LEGACY:return False
            if not isinstance(action.get('target'), str) or not action['target']:
                return False
            if kind == 'set_flag':
                if not (type(values.get('value')) is bool or values.get('value') in ('true', 'false')):
                    return False
            else:
                try:
                    integer(values.get('delta', 1) if kind == 'inc_counter' else values.get('value'))
                except (ValueError, TypeError, OverflowError):
                    return False
    return True


def groups(rule, kind):
    grouped = rule.get(kind + 'Groups')
    if isinstance(grouped, dict):
        return grouped.get('logic', 'ALL'), grouped.get('groups', [])
    items = rule.get(kind + 's', [])
    logic = rule.get('logic' if kind == 'trigger' else 'conditionLogic', 'ALL')
    return logic, [{'logic': logic, 'items': items, 'windowMs': 750}] if items else []


def requires_host_evaluation(rule):
    _, conditions = groups(rule, 'condition')
    if any(g.get('items') for g in conditions if isinstance(g, dict)):
        return True
    logic, triggers = groups(rule, 'trigger')
    if any(t.get('type') != 'hardware' or t.get('fn') == 'NFC_MATCHED' for g in triggers for t in g.get('items', [])):
        return True
    return (logic != 'ANY' and len(triggers) > 1) or any(
        g.get('logic', 'ALL') != 'ANY' and len(g.get('items', [])) > 1 for g in triggers if isinstance(g, dict))


def _has_host_actions(rule):
    return any(a.get('type') not in NATIVE_ACTIONS for a in rule.get('actions', []) if isinstance(a, dict))


def host_only(rule):
    """Legacy ownership used by firmware before per-action routing."""
    return requires_host_evaluation(rule) or _has_host_actions(rule)


def combine(logic, values):
    values = list(values)
    if logic not in ('ALL', 'ANY') or not values:
        return False
    return all(values) if logic == 'ALL' else any(values)


def integer(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a counter value')
    number = float(value)
    if not math.isfinite(number) or number != int(number) or not MINIMUM <= number <= LIMIT:
        raise ValueError('counter value must be a signed 32-bit integer')
    return int(number)


def compare(op, left, right):
    return {'==': lambda: left == right, '!=': lambda: left != right,
            '<': lambda: left < right, '<=': lambda: left <= right,
            '>': lambda: left > right, '>=': lambda: left >= right}.get(op, lambda: False)()


@contextmanager
def _open_state_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        with path.with_suffix('.init.lock').open('a') as initialization:
            fcntl.flock(initialization, fcntl.LOCK_EX)
            if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS runtime (id INTEGER PRIMARY KEY, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS seen (id INTEGER PRIMARY KEY, token TEXT UNIQUE)")
        yield db
    finally:
        db.close()


@contextmanager
def reuse_state_connection(instance):
    """Keep one Rules connection for the lifetime of a runtime worker."""
    path = Path(instance) / 'rules' / 'runtime.sqlite3'
    previous = getattr(_LOCAL, "connection", None)
    if previous is not None and previous[0] == path:
        yield
        return
    with _open_state_database(path) as db:
        _LOCAL.connection = (path, db)
        try:
            yield
        finally:
            _LOCAL.connection = previous


@contextmanager
def state_transaction(instance, *, include_connection=False):
    path = Path(instance) / 'rules' / 'runtime.sqlite3'
    reusable = getattr(_LOCAL, "connection", None)
    connection = nullcontext(reusable[1]) if reusable is not None and reusable[0] == path else _open_state_database(path)
    with connection as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('SELECT state FROM runtime WHERE id=1').fetchone()
            state = json.loads(row[0]) if row else {}
            for key in ('flags', 'counters', 'events', 'devices', 'triggers'):
                state.setdefault(key, {})
            yield (state, db) if include_connection else state
            after = json.dumps(state, allow_nan=False, separators=(",", ":"))
            if row is None or after != row[0]:
                db.execute('INSERT OR REPLACE INTO runtime VALUES (1,?)', (after,))
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise

def condition_matches(condition, state, now, game=None, owner=(None, None)):
    if not isinstance(condition, dict):
        return False
    kind, key = condition.get('type'), condition.get('key')
    op, value = condition.get('op') or ('>=' if kind == 'time_since_event' else '=='), condition.get('value')
    if not isinstance(key, str) or not key:
        return False
    try:
        if kind in ('game','ball'):
            actual=state.get('managers',{}).get(kind,{}).get(key)
            return actual is not None and compare(op,actual,value)
        if kind in ('flag','counter') and key in LEGACY:return False
        if kind in scoped_state.KINDS:
            config = scoped_state.configuration(state, kind, key)
            bucket = scoped_state.values(state, kind, config["scope"], owner)
            if bucket is None:
                return False
            if kind == "flag":
                return (type(value) is bool or value in ("true", "false")) and op == "==" and bucket.get(key, False) == (value is True or value == "true")
            if kind == "timer":
                if "clock" not in config:
                    return False
                actual = scoped_state.remaining(bucket.get(key), scoped_state.clock_value(config, game, owner, now))
            else:
                actual = bucket.get(key, 0)
            return compare(op, actual, integer(value))
        if kind == 'time_since_event':
            previous = state['events'].get(key)
            return previous is not None and compare(op, max(0, now - previous), integer(value))
        if kind == 'device_state':
            return op == '==' and key in state['devices'] and state['devices'][key] == value
    except (ValueError, TypeError, OverflowError):
        pass
    return False


def conditions_match(rule, state, now, game=None, owner=(None, None)):
    logic, condition_groups = groups(rule, 'condition')
    condition_groups = [g for g in condition_groups if isinstance(g, dict) and g.get('items')]
    if not condition_groups:
        return True
    return combine(logic, (combine(g.get('logic', 'ALL'),
        (condition_matches(c, state, now, game, owner) for c in g.get('items', [])))
        for g in condition_groups if isinstance(g, dict) and g.get('items')))


def observe(state, name, source, params):
    # System events establish built-in flags; authored flags never arm the ESP.
    transitions = {'ENABLE_GRANTED': ('ENABLED', True), 'ENABLE_REVOKED': ('ENABLED', False),
                   'IDLE_ENTERED': ('IDLE', True), 'IDLE_EXITED': ('IDLE', False), 'TILT_LIFTED': ('TILT', True)}
    if name in transitions:
        key,value=transitions[name];state['flags'][key]=value
    observed = (params.get('payload') or {}).get('observedDevices', {})
    if isinstance(observed, dict):
        # A fresh complete ESP snapshot replaces stale observations.
        state['devices'] = {k: v for k, v in observed.items()
                            if isinstance(k, str) and v in ('CLOSED', 'OPEN', 'HIGH', 'LOW', 'ACTIVE', 'INACTIVE')}
    event_type = str(params.get('eventType', '')).upper()
    value = {'CLOSED': 'CLOSED', 'OPENED': 'OPEN', 'PRESSED': 'CLOSED',
             'RELEASED': 'OPEN'}.get(event_type)
    if source and value:
        state['devices'][source] = value



def _scoped_references(rule, trigger_groups):
    references = [
        (item.get("type"), item.get("key"))
        for group in groups(rule, "condition")[1] for item in group.get("items", [])
    ]
    references.extend(
        (action["type"].rsplit("_", 1)[-1], action.get("target"))
        for action in rule.get("actions", [])
    )
    references.extend(
        ("timer", (trigger.get("params") or {}).get("timer"))
        for group in trigger_groups for trigger in group.get("items", [])
        if trigger.get("type") == "timer"
    )
    return tuple(
        (kind, key) for kind, key in references if kind in scoped_state.KINDS and isinstance(key, str)
    )


@dataclass(frozen=True)
class PreparedRule:
    key: str
    rule: dict
    logic: str
    trigger_groups: tuple
    scoped_references: tuple[tuple[str, str], ...]
    event_names: frozenset[str]


@dataclass(frozen=True)
class PreparedRules:
    rules: tuple[PreparedRule, ...]
    history_keys: frozenset[str]


def prepare_rules(rules: list[dict]) -> PreparedRules:
    prepared = []
    history_keys = set()
    for index, rule in enumerate(rules):
        key = f'{index}:{json.dumps(rule, sort_keys=True)}'
        history_keys.add(key)
        if not rule.get('enabled', True):
            continue
        if rule_issues(rule) or not valid_actions(rule.get('actions', [])):
            logging.getLogger(__name__).warning('Skipping rule %s: unsupported or invalid action', index)
            continue
        logic, trigger_groups = groups(rule, 'trigger')
        prepared_groups = []
        event_names = set()
        for group_index, group in enumerate(trigger_groups):
            window = group.get('windowMs', 750)
            checks = tuple(
                (f'{group_index}:{trigger_index}', {
                    'enabled': True,
                    'triggers': [dict(trigger, __groupWindowMs=window)],
                })
                for trigger_index, trigger in enumerate(group.get('items', []))
            )
            prepared_groups.append((group.get('logic', 'ALL'), window, checks))
            event_names.update(item.get('event') for item in group.get('items', []) if isinstance(item.get('event'), str))
        prepared.append(PreparedRule(
            key, rule, logic, tuple(prepared_groups), _scoped_references(rule, trigger_groups), frozenset(event_names)
        ))
    return PreparedRules(tuple(prepared), frozenset(history_keys))


def plan(instance, rules, name, source, params, matcher, now=None):
    """Select once and update state atomically; perform external effects afterwards."""
    now = time.time() * 1000 if now is None else now
    result = []
    depth = params.get("_rulesDepth", 0)
    if not isinstance(depth, int) or depth > 16:
        return result
    if not rules:
        return result
    if not isinstance(rules, PreparedRules):
        rules = prepare_rules(rules)
    if not rules.history_keys:
        return result
    from pinballctl.runtime.game.runtime import read_manager_fields
    with state_transaction(instance, include_connection=True) as (state, db):
        # Keep bounded event identities out of the state JSON read and rewritten
        # for each event. Migrate an existing history in the same transaction.
        old_seen = state.pop("seen", {})
        if old_seen:
            db.executemany("INSERT OR IGNORE INTO seen(token) VALUES (?)", ((key,) for key in old_seen))
        tokens = []
        event_id = params.get('_managerEventId') or params.get('_eventId')
        if event_id:
            tokens.append(event_id)
        seq = params.get('seq')
        if isinstance(seq, int) and seq > 0:
            tokens.append(f'{source}:{name}:{seq}:{params.get("payload", {}).get("tsMs", "")}')
        if any(db.execute("SELECT 1 FROM seen WHERE token=?", (token,)).fetchone() for token in tokens):
            return []
        db.executemany("INSERT INTO seen(token) VALUES (?)", ((token,) for token in dict.fromkeys(tokens)))
        if tokens:
            db.execute("DELETE FROM seen WHERE id <= (SELECT id FROM seen ORDER BY id DESC LIMIT 1 OFFSET 1024)")
        managers = read_manager_fields(instance, rules_context=True)
        game = managers.pop("rulesGame")
        state["managers"] = managers
        scoped_state.prepare(state, game)
        owner = scoped_state.context(game, params)
        late_timer = params.get("_rulesTimerEvent") and params.get("clock") == "play" and (
            game["status"] != "BALL_ACTIVE" or params.get("_turnId") != game["turnId"]
        )
        if name == 'BOOT_COMPLETED':
            db.execute("DELETE FROM seen")
            state['triggers'].clear()
            state['devices'].clear()
            state['events'].clear()
        observe(state, name, source, params)
        for prepared in rules.rules:
            if name not in prepared.event_names and not prepared.scoped_references:
                continue
            rule = prepared.rule
            # Hardware combinations and grouped triggers must not combine
            # hits from different turns for rules using scoped state.
            scoped = any(
                scoped_state.configuration(state, kind, key)["scope"] != "global"
                for kind, key in prepared.scoped_references
            )
            history = state["triggers"].setdefault(prepared.key, {})
            if scoped and history.get("owner") != [*owner, game["turnId"]]:
                history.clear()
                history["owner"] = [*owner, game["turnId"]]
            if name not in prepared.event_names:
                continue
            group_matches, current = [], False
            for logic, window, triggers in prepared.trigger_groups:
                checks = []
                for key, single in triggers:
                    matched = single['triggers'][0].get('event') == name and matcher(single, name, source, params)
                    if matched:
                        history[key] = now
                        current = True
                    checks.append(key in history and 0 <= now - history[key] <= max(0, integer(window)))
                group_matches.append(combine(logic, checks))
            if not current or not combine(prepared.logic, group_matches) or not conditions_match(rule, state, now, game, owner):
                continue
            history.clear()  # Consume a match so previous inputs cannot repeatedly satisfy ALL.
            actions = []
            for action in rule.get('actions', []):
                if not isinstance(action, dict):
                    continue
                kind, target, values = action.get('type'), action.get('target'), action.get('params') or {}
                if kind in scoped_state.TIMER_ACTIONS:
                    scoped_state.timer_action(state, kind, target, game, owner, now)
                elif kind in STATE_ACTIONS:
                    state_kind = "flag" if kind == "set_flag" else "counter"
                    config = scoped_state.configuration(state, state_kind, target)
                    bucket = scoped_state.values(state, state_kind, config["scope"], owner)
                    if bucket is None:
                        continue
                    try:
                        if kind == 'set_flag':
                            value = values.get('value')
                            if not (type(value) is bool or value in ('true', 'false')):
                                continue
                            bucket[target] = value is True or value == 'true'
                        else:
                            value = integer(values.get('delta', 1) if kind == 'inc_counter' else values.get('value'))
                            if kind == 'inc_counter':
                                value = max(MINIMUM, min(LIMIT, bucket.get(target, 0) + value))
                            bucket[target] = value
                    except (ValueError, TypeError, OverflowError):
                        continue
                elif not late_timer:
                    actions.append(action)
            requires_host = requires_host_evaluation(rule)
            result.append({
                **rule, 'actions': actions,
                '_hostOnly': requires_host or _has_host_actions(rule),
                '_requiresHostEvaluation': requires_host,
            })
        state['events'][name] = now
        # Bound event/device/trigger history; retain only currently configured rules.
        state['events'] = dict(list(state['events'].items())[-1024:])
        state['devices'] = dict(list(state['devices'].items())[-1024:])
        state['triggers'] = {k: v for k, v in state['triggers'].items() if v and k in rules.history_keys}
    return result


def snapshot(instance):
    """Return only useful runtime values, without internal matching/dedup history."""
    from pinballctl.runtime.game.runtime import read_rules_game
    with state_transaction(instance) as state:
        game = read_rules_game(instance)
        return {
            **{key: dict(state[key]) for key in ('flags', 'counters', 'devices')},
            "values": scoped_state.visible(state, game, int(time.time() * 1000)),
        }
