"""Transactional Pi rule evaluation shared by bridge and offline event ingress.

State is per installation, not per web worker. Unknown conditions fail closed.
"""
from contextlib import contextmanager
import json
import math
import logging
from pathlib import Path
import sqlite3
import time

STATE_ACTIONS = {'set_flag', 'set_counter', 'inc_counter'}
NATIVE_ACTIONS = {'set_output', 'pulse', 'set_lighting_pixels', 'set_lcd_text'}
LIMIT = 2**31 - 1
MINIMUM = -(2**31)


SUPPORTED_ACTIONS = NATIVE_ACTIONS | STATE_ACTIONS | {
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
        if kind in STATE_ACTIONS:
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


def host_only(rule):
    _, conditions = groups(rule, 'condition')
    if any(g.get('items') for g in conditions if isinstance(g, dict)):
        return True
    if any(a.get('type') not in NATIVE_ACTIONS for a in rule.get('actions', []) if isinstance(a, dict)):
        return True
    logic, triggers = groups(rule, 'trigger')
    if any(t.get('type') != 'hardware' or t.get('fn') == 'NFC_MATCHED' for g in triggers for t in g.get('items', [])):
        return True
    return (logic != 'ANY' and len(triggers) > 1) or any(
        g.get('logic', 'ALL') != 'ANY' and len(g.get('items', [])) > 1 for g in triggers if isinstance(g, dict))


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
def state_transaction(instance):
    path = Path(instance) / 'rules' / 'runtime.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS runtime (id INTEGER PRIMARY KEY, state TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state FROM runtime WHERE id=1').fetchone()
        state = json.loads(row[0]) if row else {}
        for key in ('flags', 'counters', 'events', 'devices', 'triggers', 'seen'):
            state.setdefault(key, {})
        yield state
        db.execute('INSERT OR REPLACE INTO runtime VALUES (1,?)', (json.dumps(state, allow_nan=False),))
        db.execute('COMMIT')
    except Exception:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def condition_matches(condition, state, now):
    if not isinstance(condition, dict):
        return False
    kind, key = condition.get('type'), condition.get('key')
    op, value = condition.get('op') or ('>=' if kind == 'time_since_event' else '=='), condition.get('value')
    if not isinstance(key, str) or not key:
        return False
    try:
        if kind == 'flag':
            if not (type(value) is bool or value in ('true', 'false')):
                return False
            return op == '==' and state['flags'].get(key, False) == (value is True or value == 'true')
        if kind == 'counter':
            return compare(op, state['counters'].get(key, 0), integer(value))
        if kind == 'time_since_event':
            previous = state['events'].get(key)
            return previous is not None and compare(op, max(0, now - previous), integer(value))
        if kind == 'device_state':
            return op == '==' and key in state['devices'] and state['devices'][key] == value
    except (ValueError, TypeError, OverflowError):
        pass
    return False


def conditions_match(rule, state, now):
    logic, condition_groups = groups(rule, 'condition')
    condition_groups = [g for g in condition_groups if isinstance(g, dict) and g.get('items')]
    if not condition_groups:
        return True
    return combine(logic, (combine(g.get('logic', 'ALL'),
        (condition_matches(c, state, now) for c in g.get('items', [])))
        for g in condition_groups if isinstance(g, dict) and g.get('items')))


def observe(state, name, source, params):
    # System events establish built-in flags; authored flags never arm the ESP.
    transitions = {'GAME_STARTED': ('GAME_ACTIVE', True), 'GAME_ENDED': ('GAME_ACTIVE', False),
                   'BALL_STARTED': ('BALL_IN_PLAY', True), 'BALL_ENDED': ('BALL_IN_PLAY', False),
                   'ENABLE_GRANTED': ('ENABLED', True), 'ENABLE_REVOKED': ('ENABLED', False),
                   'HAS_CREDIT_TRUE': ('HAS_CREDIT', True), 'HAS_CREDIT_FALSE': ('HAS_CREDIT', False),
                   'IDLE_ENTERED': ('IDLE', True), 'IDLE_EXITED': ('IDLE', False),
                   'TILT_LIFTED': ('TILT', True)}
    semantic = name if name in transitions else str(params.get('eventType', '')).upper()
    if semantic in transitions:
        key, value = transitions[semantic]
        state['flags'][key] = value
    for event, param, counter in [('CREDITS_CHANGED', 'credits', 'CREDITS'),
                                   ('BALL_STARTED', 'ball', 'BALL_NUMBER'),
                                   ('PLAYER_ADDED', 'playerCount', 'PLAYER_COUNT')]:
        if name == event and param in params:
            try:
                state['counters'][counter] = integer(params[param])
            except (ValueError, TypeError, OverflowError):
                pass
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


def plan(instance, rules, name, source, params, matcher, now=None):
    """Select once and update state atomically; perform external effects afterwards."""
    now = time.time() * 1000 if now is None else now
    result = []
    depth = params.get("_rulesDepth", 0)
    if not isinstance(depth, int) or depth > 16:
        return result
    if not rules:
        return result
    with state_transaction(instance) as state:
        seq = params.get('seq')
        if isinstance(seq, int) and seq > 0:
            identity = f'{source}:{name}'
            # Bounded recent exact identities; counters may restart on reconnect.
            token = f'{identity}:{seq}:{params.get("payload", {}).get("tsMs", "")}'
            if token in state['seen']:
                return []
            state['seen'][token] = now
            state['seen'] = dict(list(state['seen'].items())[-512:])
        if name == 'BOOT_COMPLETED':
            state['seen'].clear()
            state['triggers'].clear()
            state['devices'].clear()
            state['events'].clear()
        observe(state, name, source, params)
        for index, rule in enumerate(rules):
            if not rule.get('enabled', True):
                continue
            if not valid_actions(rule.get('actions', [])):
                logging.getLogger(__name__).warning('Skipping rule %s: unsupported or invalid action', index)
                continue
            root_logic, trigger_groups = groups(rule, 'trigger')
            signature = json.dumps(rule, sort_keys=True)
            rule_key = f'{index}:{signature}'
            history = state['triggers'].setdefault(rule_key, {})
            group_matches, current = [], False
            for gi, group in enumerate(trigger_groups):
                checks = []
                for ti, trigger in enumerate(group.get('items', [])):
                    key = f'{gi}:{ti}'
                    single = {'enabled': True, 'triggers': [dict(trigger, __groupWindowMs=group.get('windowMs', 750))]}
                    matched = matcher(single, name, source, params)
                    if matched:
                        history[key] = now
                        current = True
                    checks.append(key in history and 0 <= now - history[key] <= max(0, integer(group.get('windowMs', 750))))
                group_matches.append(combine(group.get('logic', 'ALL'), checks))
            if not current or not combine(root_logic, group_matches) or not conditions_match(rule, state, now):
                continue
            history.clear()  # Consume a match so previous inputs cannot repeatedly satisfy ALL.
            actions = []
            for action in rule.get('actions', []):
                if not isinstance(action, dict):
                    continue
                kind, target, values = action.get('type'), action.get('target'), action.get('params') or {}
                if kind in STATE_ACTIONS:
                    if not isinstance(target, str) or not target:
                        continue
                    try:
                        if kind == 'set_flag':
                            value = values.get('value')
                            if not (type(value) is bool or value in ('true', 'false')):
                                continue
                            state['flags'][target] = value is True or value == 'true'
                        else:
                            value = integer(values.get('delta', 1) if kind == 'inc_counter' else values.get('value'))
                            if kind == 'inc_counter':
                                value = max(MINIMUM, min(LIMIT, state['counters'].get(target, 0) + value))
                            state['counters'][target] = value
                    except (ValueError, TypeError, OverflowError):
                        continue
                else:
                    actions.append(action)
            result.append({**rule, 'actions': actions, '_hostOnly': host_only(rule)})
        state['events'][name] = now
        # Bound event/device/trigger history; retain only currently configured rules.
        state['events'] = dict(list(state['events'].items())[-1024:])
        state['devices'] = dict(list(state['devices'].items())[-1024:])
        active_keys = {f'{i}:{json.dumps(r, sort_keys=True)}' for i, r in enumerate(rules)}
        state['triggers'] = {k: v for k, v in state['triggers'].items() if k in active_keys}
    return result


def snapshot(instance):
    """Return only useful runtime values, without internal matching/dedup history."""
    with state_transaction(instance) as state:
        return {key: dict(state[key]) for key in ('flags', 'counters', 'devices')}
