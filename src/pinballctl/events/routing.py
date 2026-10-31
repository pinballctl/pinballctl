"""Conservative routing for host-generated scoring notifications."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from pinballctl.bridge.state import read_state
from pinballctl.ops.rules_blob import decode_rules_pd_bytes


def _signature(path):
    st = path.stat()
    return str(path), st.st_mtime_ns, st.st_ctime_ns, st.st_size


@lru_cache(maxsize=16)
def _listeners(authored_signature, deployed_signature):
    authored = json.loads(Path(authored_signature[0]).read_text())
    blob = Path(deployed_signature[0]).read_bytes()
    deployed = decode_rules_pd_bytes(blob)
    if not isinstance(authored, list):
        raise ValueError('invalid authored rules')
    names = set()
    for rule in authored + deployed.rules:
        if not isinstance(rule, dict):
            raise ValueError('invalid rule')
        if not rule.get('enabled', True):
            continue
        groups = rule.get('triggerGroups')
        triggers = list(rule.get('triggers') or [])
        if isinstance(groups, dict):
            for group in groups.get('groups', []):
                triggers.extend(group.get('items', []))
        conditions = list(rule.get('conditions') or [])
        for group in (rule.get('conditionGroups') or {}).get('groups', []):
            conditions.extend(group.get('items', []))
        transitions = {'GAME_ACTIVE': ['GAME_STARTED', 'GAME_ENDED'],
                       'BALL_IN_PLAY': ['BALL_STARTED', 'BALL_ENDED'],
                       'ENABLED': ['ENABLE_GRANTED', 'ENABLE_REVOKED'],
                       'HAS_CREDIT': ['HAS_CREDIT_TRUE', 'HAS_CREDIT_FALSE'],
                       'IDLE': ['IDLE_ENTERED', 'IDLE_EXITED'],
                       'CREDITS': ['CREDITS_CHANGED'], 'BALL_NUMBER': ['BALL_STARTED'],
                       'PLAYER_COUNT': ['PLAYER_ADDED']}
        for condition in conditions:
            if condition.get('type') == 'time_since_event' and condition.get('key'):
                names.add(str(condition['key']).upper())
            elif condition.get('type') in ('flag', 'counter'):
                names.update(transitions.get(condition.get('key'), []))
        for trigger in triggers:
            name = trigger.get('event')
            if not isinstance(name, str) or not name.strip():
                raise ValueError('ambiguous trigger')
            names.add(name.strip().upper())
    # The manifest identifies the entire deployed file, not its inner payload.
    return frozenset(names), hashlib.sha256(blob).hexdigest()


def scoring_event_needs_esp(instance_path, name):
    """Only suppress when both authoring and confirmed deployment have no listener.

    Missing files, unknown deployment and unsynced bundles retain forwarding.
    No coil command or release event passes through this decision.
    """
    try:
        root = Path(instance_path) / 'rules'
        names, sha = _listeners(_signature(root / 'rules.json'), _signature(root / 'rules.pd'))
        if str(name).strip().upper() in names:
            return True
        state = read_state()
        manifest = state.get('manifest', {}).get('data', {}).get('rules.pd', {})
        status = state.get('rules_status', {})
        if (not state.get('connected') or manifest.get('sha256') != sha
                or status.get('status') != 'ok'
                or status.get('t') not in ('RULES_APPLY', 'RULES_BOOT')
                or state.get('manifest_at', 0) < state.get('rules_at', 0)):
            return True
        return False
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return True


def scoring_wire_event(name, params):
    """Keep the fields consumed by the current ESP EVENT_FIRE handler.

    Full award/score metadata remains on the local bus and in the audit log.
    Preserve the legacy gesture embedded in lastAward, which the firmware's
    string extractor previously found inside params.
    """
    command = {'cmd': 'EVENT_FIRE', 'name': name, 'source': 'pi.scoring'}
    award = params.get('lastAward') if isinstance(params.get('lastAward'), dict) else {}
    event_type = params.get('eventType', award.get('eventType'))
    if isinstance(event_type, str):
        command['eventType'] = event_type
    if isinstance(params.get('detailMs'), int):
        command['detailMs'] = params['detailMs']
    return command
