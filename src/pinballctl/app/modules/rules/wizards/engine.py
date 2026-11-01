"""Bounded declarative wizard compiler. Definitions never execute code."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

from pinballctl.rules.evaluation import valid_actions

ID = re.compile(r'^[a-z][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$')
KEY = re.compile(r'^[a-z][a-zA-Z0-9_]{0,39}$')
ICONS = {'wand-magic-sparkles', 'bolt', 'bullseye', 'music', 'lightbulb', 'flag', 'gear', 'shield', 'circle'}
TYPES = {'boolean', 'radio', 'select', 'multi-select', 'integer', 'number', 'duration', 'text',
         'input', 'output', 'switch', 'coil', 'sound', 'lighting', 'media', 'event', 'flag', 'counter'}
OPS = {'eq', 'ne', 'in', 'gt', 'gte', 'lt', 'lte', 'exists', 'all', 'any', 'not'}
OMIT = object()
CREATE_NEW = '__wizard_create_new__'


class InvalidWizard(ValueError):
    pass


def require(test, message):
    if not test:
        raise InvalidWizard(message)


def bounded(value, depth=0):
    require(depth <= 20, 'Definition nesting exceeds 20 levels')
    if isinstance(value, dict):
        require(len(value) <= 100, 'Too many object properties')
        for key, child in value.items():
            require(isinstance(key, str) and len(key) <= 100, 'Invalid object key')
            bounded(child, depth + 1)
    elif isinstance(value, list):
        require(len(value) <= 200, 'Too many array entries')
        for child in value:
            bounded(child, depth + 1)
    elif isinstance(value, str):
        require(len(value) <= 4000, 'Text exceeds 4000 characters')
    else:
        require(value is None or type(value) in (bool, int, float), 'Invalid JSON value')
        if type(value) in (int, float):
            require(math.isfinite(value), 'Nonfinite number')


def keys(obj, allowed, required=()):
    require(isinstance(obj, dict), 'Expected an object')
    require(set(obj) <= set(allowed), 'Unknown fields: ' + ', '.join(sorted(set(obj) - set(allowed))))
    require(set(required) <= set(obj), 'Required fields missing: ' + ', '.join(sorted(set(required) - set(obj))))


def predicate(p, answers):
    if p is None:
        return True
    op = p['op']
    if op == 'all':
        return all(predicate(x, answers) for x in p['items'])
    if op == 'any':
        return any(predicate(x, answers) for x in p['items'])
    if op == 'not':
        return not predicate(p['item'], answers)
    field = p['field']
    if op == 'exists':
        return field in answers and answers[field] not in (None, '', [])
    if field not in answers:
        return False
    a, b = answers[field], p.get('value')
    if op == 'eq':
        return type(a) is type(b) and a == b
    if op == 'ne':
        return type(a) is not type(b) or a != b
    if op == 'in':
        return a in b
    if type(a) not in (int, float) or type(b) not in (int, float):
        return False
    return {'gt': a > b, 'gte': a >= b, 'lt': a < b, 'lte': a <= b}[op]


def check_predicate(p, known):
    if p is None:
        return
    require(isinstance(p, dict) and p.get('op') in OPS, 'Unknown predicate operator')
    op = p['op']
    if op in ('all', 'any'):
        keys(p, ('op', 'items'), ('op', 'items'))
        require(isinstance(p['items'], list) and bool(p['items']), 'Predicate needs items')
        for child in p['items']:
            check_predicate(child, known)
    elif op == 'not':
        keys(p, ('op', 'item'), ('op', 'item'))
        check_predicate(p['item'], known)
    else:
        keys(p, ('op', 'field', 'value'), ('op', 'field'))
        require(p['field'] in known, 'Predicate references a later or unknown field')
        if op != 'exists':
            require('value' in p, 'Predicate needs value')
        if op == 'in':
            require(isinstance(p['value'], list), 'in requires an array')


def validate(d):
    bounded(d)
    keys(d, ('schemaVersion', 'id', 'name', 'description', 'category', 'icon', 'author', 'version',
             'minimumAppVersion', 'minimumRuntimeVersion', 'availability', 'prerequisites',
             'steps', 'rules', 'warnings', 'tags', 'illustration'),
         ('schemaVersion', 'id', 'name', 'description', 'category', 'icon', 'version',
          'minimumAppVersion', 'minimumRuntimeVersion', 'availability', 'prerequisites', 'steps', 'rules'))
    require(type(d['schemaVersion']) is int and d['schemaVersion'] == 1, 'Unsupported schema version')
    require(isinstance(d['id'], str) and ID.fullmatch(d['id']), 'Use a namespaced wizard ID')
    for k in ('name', 'description', 'category', 'version', 'minimumAppVersion'):
        require(isinstance(d[k], str) and bool(d[k]), f'{k} must be text')
    if 'author' in d: require(isinstance(d['author'], str), 'Author must be text')
    require(d['icon'] in ICONS, 'Unknown icon')
    require(bool(re.fullmatch(r'\d+\.\d+\.\d+', d['minimumAppVersion'])) and bool(re.fullmatch(r'\d+\.\d+\.\d+', d['version'])), 'Versions must use major.minor.patch')
    require(d['availability'] in ('available', 'unavailable'), 'Invalid availability')
    require(type(d['minimumRuntimeVersion']) is int and 0 <= d['minimumRuntimeVersion'] <= 100, 'Invalid runtime version')
    for k in ('prerequisites', 'warnings', 'tags'):
        require(isinstance(d.get(k, []), list) and all(isinstance(s, str) for s in d.get(k, [])), f'{k} must be text list')
    require(isinstance(d['steps'], list) and len(d['steps']) <= 20, 'Maximum 20 steps')
    require(isinstance(d['rules'], list) and len(d['rules']) <= 50, 'Maximum 50 rules')
    require(d['availability'] == 'available' or (d['prerequisites'] and not d['rules']), 'Unavailable wizards need prerequisites and no output')
    require(d['availability'] != 'available' or (d['steps'] and d['rules']), 'Available wizard needs steps and rules')
    if 'illustration' in d:
        keys(d['illustration'], ('asset', 'alt'), ('asset', 'alt'))
        require(d['illustration']['asset'] == 'rules-flow' and isinstance(d['illustration']['alt'], str) and bool(d['illustration']['alt']), 'Unknown illustration or missing alt text')
    known = set()
    for step in d['steps']:
        keys(step, ('title', 'description', 'when', 'fields', 'icon'), ('title', 'fields'))
        require(isinstance(step['title'], str), 'Step title must be text')
        if 'description' in step: require(isinstance(step['description'], str), 'Step description must be text')
        if 'icon' in step: require(step['icon'] in ICONS, 'Unknown step icon')
        check_predicate(step.get('when'), known)
        require(isinstance(step['fields'], list) and len(step['fields']) <= 30, 'Maximum 30 fields per step')
        for f in step['fields']:
            keys(f, ('id', 'label', 'type', 'required', 'default', 'min', 'max', 'options', 'help', 'when', 'icon'), ('id', 'label', 'type'))
            require(isinstance(f['id'], str) and KEY.fullmatch(f['id']) and f['id'] not in known, 'Invalid or duplicate field ID')
            require(f['type'] in TYPES and isinstance(f['label'], str), 'Unknown field type or invalid label')
            if 'required' in f: require(type(f['required']) is bool, 'Required must be boolean')
            if 'help' in f: require(isinstance(f['help'], str), 'Help must be text')
            check_predicate(f.get('when'), known)
            if 'icon' in f:
                require(f['icon'] in ICONS, 'Unknown field icon')
            if f['type'] in ('radio', 'select', 'multi-select'):
                require(isinstance(f.get('options'), list) and f['options'], 'Choice field needs options')
                for option in f['options']:
                    keys(option, ('value', 'label', 'icon'), ('value', 'label'))
                    require(isinstance(option['label'], str), 'Option label must be text')
                    if 'icon' in option:
                        require(option['icon'] in ICONS, 'Unknown option icon')
            for k in ('min', 'max'):
                if k in f:
                    require(type(f[k]) in (int, float) and math.isfinite(f[k]), 'Invalid numeric limit')
            known.add(f['id'])
    def scan(node):
        if isinstance(node, list):
            for v in node: scan(v)
        elif isinstance(node, dict):
            if '$answer' in node:
                keys(node, ('$answer',), ('$answer',))
                require(node['$answer'] in known, 'Unknown output answer')
            elif '$local' in node:
                keys(node, ('$local',), ('$local',))
                require(isinstance(node['$local'], str) and re.fullmatch('[A-Z][A-Z0-9_]{0,9}', node['$local']), 'Invalid local state key')
            else:
                check_predicate(node.get('$when'), known)
                for k, v in node.items():
                    if k != '$when': scan(v)
    scan(d['rules'])
    return d


def discover(instance):
    found, errors, duplicates = {}, [], set()
    for origin, directory in [('bundled', Path(__file__).parent / 'bundled'), ('user', Path(instance) / 'wizards' / 'user')]:
        if not directory.exists(): continue
        if directory.is_symlink() or (origin == 'user' and not directory.resolve().is_relative_to(Path(instance).resolve())):
            errors.append({'file': directory.name, 'origin': origin, 'error': 'Unsafe definition directory'})
            continue
        for path in sorted(directory.glob('*.json'))[:500]:
            try:
                require(not path.is_symlink() and path.resolve().parent == directory.resolve(), 'Symlinks not allowed')
                require(path.stat().st_size <= 131072, 'Definition exceeds 128 KiB')
                d = validate(json.loads(path.read_text(encoding='utf-8')))
                if d['id'] in found or d['id'] in duplicates:
                    duplicates.add(d['id']); found.pop(d['id'], None)
                    raise InvalidWizard('Duplicate ID; all conflicting definitions disabled')
                found[d['id']] = dict(d, origin=origin)
            except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
                errors.append({'file': path.name, 'origin': origin, 'error': str(exc)})
    return found, errors


def resolve_answers(d, raw, choices, partial=False):
    require(isinstance(raw, dict), 'Answers must be an object')
    known = {f['id'] for step in d['steps'] for f in step['fields']}
    require(set(raw) <= known, 'Unknown answers')
    clean, visible = {}, []
    for step in d['steps']:
        if not predicate(step.get('when'), clean): continue
        fields = []
        for field in step['fields']:
            if not predicate(field.get('when'), clean): continue
            fields.append(field)
            key, kind = field['id'], field['type']
            value = raw.get(key, field.get('default', CREATE_NEW if kind in ('flag', 'counter') else None))
            if value is None or value == '' or value == []:
                require(partial or not field.get('required', True), f"{field['label']} is required")
                continue
            if kind == 'boolean':
                require(type(value) is bool, f'{key}: choose yes or no')
            elif kind in ('integer', 'number', 'duration'):
                require(type(value) in (int, float) and math.isfinite(value), f'{key}: enter a number')
                require(kind == 'number' or int(value) == value, f'{key}: enter an integer')
                require(field.get('min', 0) <= value <= field.get('max', 2147483647), f'{key}: outside allowed range')
                if kind != 'number': value = int(value)
            elif kind in ('radio', 'select', 'multi-select'):
                allowed = [o['value'] for o in field['options']]
                require((isinstance(value, list) and all(x in allowed for x in value)) if kind == 'multi-select' else value in allowed, f'{key}: invalid choice')
            else:
                require(isinstance(value, str) and len(value) <= 200, f'{key}: invalid text')
                if kind not in ('text', 'event') and not (kind in ('flag', 'counter') and value == CREATE_NEW):
                    require(value in {o['id'] for o in choices.get(kind, [])}, f'{key}: reference no longer exists')
                if kind == 'event':
                    require(re.fullmatch('[A-Z][A-Z0-9_]{0,79}', value), f'{key}: use an uppercase event name')
            clean[key] = value
        visible.append(dict(step, fields=fields))
    return clean, visible


def render(node, answers, namespace, references=None):
    references = references or {}
    if isinstance(node, list):
        out = [render(x, answers, namespace, references) for x in node]
        return [x for x in out if x is not OMIT]
    if isinstance(node, dict):
        if '$answer' in node:
            require(node['$answer'] in answers, 'Output references a hidden or missing answer')
            return copy.deepcopy(references.get(node['$answer'], answers[node['$answer']]))
        if '$local' in node:
            return 'W' + hashlib.sha256((namespace + ':' + node['$local']).encode()).hexdigest()[:30].upper()
        if not predicate(node.get('$when'), answers): return OMIT
        result = {}
        for k, v in node.items():
            if k != '$when':
                value = render(v, answers, namespace, references)
                if value is not OMIT: result[k] = value
        return result
    return node


def state_creations(d, answers, choices, namespace):
    """Describe new state without writing it; bindings are stable for a preview."""
    result = []
    used = {kind: {str(item.get('name') or item['id']) for item in choices.get(kind, [])}
            for kind in ('counter', 'flag')}
    for step in d['steps']:
        for field in step['fields']:
            kind = field['type']
            if kind not in used or answers.get(field['id']) != CREATE_NEW:
                continue
            label = field['label']
            if label.lower().startswith('existing '): label = label[9:]
            base = f"{d['name']} — {label}"
            name, count = base, 2
            while name in used[kind]:
                name = f'{base} ({count})'; count += 1
            used[kind].add(name)
            key = 'W' + hashlib.sha256(f"{namespace}:field:{kind}:{field['id']}".encode()).hexdigest()[:30].upper()
            result.append({'field': field['id'], 'type': kind, 'key': key,
                           'name': name, 'initialValue': 0 if kind == 'counter' else False})
    return result


def generate(d, raw, choices, namespace=None):
    require(d['availability'] == 'available', '; '.join(d['prerequisites']))
    require(tuple(int(x) for x in d['minimumAppVersion'].split('.')) <= (0, 10, 0) and d['minimumRuntimeVersion'] <= 2, 'Definition requires a newer runtime')
    answers, _ = resolve_answers(d, raw, choices)
    namespace = namespace or uuid.uuid4().hex
    require(bool(re.fullmatch('[a-f0-9]{32}', namespace)), 'Invalid instance token')
    creations = state_creations(d, answers, choices, namespace)
    references = {item['field']: item['key'] for item in creations}
    rules = render(d['rules'], answers, namespace, references)
    local_names = set(references.values())
    def collect_locals(node):
        if isinstance(node, list):
            for value in node: collect_locals(value)
        elif isinstance(node, dict):
            if '$local' in node: local_names.add(render(node, answers, namespace))
            else:
                for value in node.values(): collect_locals(value)
    collect_locals(d['rules'])
    named_state = {references.get(f['id'], answers[f['id']]) for step in d['steps'] for f in step['fields']
                   if f['type'] in ('flag', 'counter') and f['id'] in answers}
    existing_state = {item['id'] for kind in ('flag', 'counter') for item in choices.get(kind, [])}
    require(not local_names & existing_state, 'Local state namespace already exists; preview a new instance')
    for i, rule in enumerate(rules):
        keys(rule, ('name', 'triggers', 'triggerGroups', 'conditions', 'conditionGroups', 'actions', 'notes', 'tags', 'enabled', 'logic', 'conditionLogic'), ('name', 'actions'))
        require(isinstance(rule['name'], str) and bool(rule['name'].strip()) and len(rule['name']) <= 200, 'Invalid rule name')
        require(isinstance(rule.get('tags', []), list) and all(isinstance(t, str) for t in rule.get('tags', [])), 'Invalid rule tags')
        for group_key in ('triggerGroups', 'conditionGroups'):
            if group_key not in rule: continue
            grouped = rule[group_key]
            keys(grouped, ('logic', 'groups'), ('logic', 'groups'))
            require(grouped['logic'] in ('ALL', 'ANY') and isinstance(grouped['groups'], list), 'Invalid group logic')
            for g in grouped['groups']:
                keys(g, ('logic', 'items', 'windowMs'), ('logic', 'items'))
                require(g['logic'] in ('ALL', 'ANY') and isinstance(g['items'], list) and bool(g['items']), 'Empty or invalid group')
                if 'windowMs' in g: require(type(g['windowMs']) is int and 0 <= g['windowMs'] <= 60000, 'Invalid group window')
        require(valid_actions(rule['actions']) and bool(rule['actions']), 'Unsupported or empty action list')
        triggers = rule.get('triggers', []) + [t for g in rule.get('triggerGroups', {}).get('groups', []) for t in g.get('items', [])]
        require(bool(triggers), 'Generated rule has no triggers')
        for trigger in triggers:
            keys(trigger, ('type', 'source', 'event', 'fn', 'params', 'deviceClass'), ('type', 'event'))
            require(trigger['type'] in ('hardware', 'custom', 'system') and isinstance(trigger['event'], str) and bool(trigger['event']), 'Invalid trigger')
            if trigger['type'] == 'hardware':
                devices = {o['id']: o for o in choices.get('input', [])}
                require(trigger.get('source') in devices, 'Hardware input no longer mapped')
                trigger['event'] = devices[trigger['source']]['eventBase']
                require(trigger.get('fn') in ('PRESSED', 'RELEASED', 'CLICKED', 'DOUBLE_CLICKED', 'HELD', 'CLOSED', 'OPENED', 'CHANGED', 'ACTIVE_FOR_MS', 'INACTIVE_FOR_MS'), 'Unsupported hardware event')
                if trigger.get('fn') in ('CLICKED', 'DOUBLE_CLICKED', 'HELD'):
                    require(devices[trigger['source']]['deviceClass'] == 'button', 'This gesture requires a Button mapping')
                keys(trigger.get('params', {}), ('minMs', 'windowMs', 'repeatMs'))
                for number in trigger.get('params', {}).values():
                    require(type(number) is int and 1 <= number <= 60000, 'Invalid trigger duration')
        conditions = rule.get('conditions', []) + [c for g in rule.get('conditionGroups', {}).get('groups', []) for c in g.get('items', [])]
        for c in conditions:
            keys(c, ('type', 'key', 'op', 'value'), ('type', 'key', 'value'))
            require(c['type'] in ('flag', 'counter', 'time_since_event', 'device_state'), 'Unsupported condition')
            require(isinstance(c['key'], str) and bool(c['key']), 'Condition requires a key')
            require(c.get('op', '==') in (('==',) if c['type'] in ('flag', 'device_state') else ('==','!=','<','<=','>','>=')), 'Unsupported condition comparison')
            if c['type'] in ('counter', 'time_since_event'):
                require(type(c['value']) is int and -(2**31) <= c['value'] < 2**31, 'Invalid numeric condition')
            if c['type'] == 'flag': require(type(c['value']) is bool, 'Flag condition needs a boolean')
            if c['type'] == 'device_state':
                require(c['value'] in ('OPEN','CLOSED','HIGH','LOW','ACTIVE','INACTIVE'), 'Invalid device state')
                require(c['key'] in {item['id'] for item in choices.get('input', [])}, 'Condition device no longer mapped')
            if c['type'] == 'time_since_event': require(c['value'] >= 0, 'Elapsed time cannot be negative')
        for action in rule['actions']:
            keys(action, ('type', 'target', 'params'), ('type',))
            allowed_params = {
                'set_flag': ('value',), 'set_counter': ('value',), 'inc_counter': ('delta',),
                'emit_event': ('name',), 'play_audio_cue': (), 'stop_audio_cue': (), 'toggle_audio_cue': (),
                'apply_lighting_scene': (), 'stop_lighting_scene': (), 'media_play_scene': (), 'media_stop_scene': (),
            }
            require(action['type'] in allowed_params, 'Action requires an audited wizard adapter')
            keys(action.get('params', {}), allowed_params[action['type']])
            if action['type'] == 'emit_event':
                event = action.get('params', {}).get('name', '')
                require(isinstance(event, str) and bool(re.fullmatch('[A-Z][A-Z0-9_]{0,79}', event)), 'Invalid emitted event name')
                require(event not in {t.get('event') for t in triggers}, 'Event would trigger itself')
            if action['type'] in ('set_counter', 'inc_counter', 'set_flag'):
                require(bool(re.fullmatch('[A-Z][A-Z0-9_]{0,31}', action.get('target', ''))), 'Invalid state identifier')
                require(action['target'] in local_names | named_state, 'Use $local for private state or a typed existing state selector')
            # No generic wizard path may invent a safe coil/arming configuration.
            require(action['type'] not in ('pulse', 'set_output'), 'Hardware outputs require a separately audited safety-aware wizard')
            refs = {'play_audio_cue': 'sound', 'stop_audio_cue': 'sound', 'toggle_audio_cue': 'sound',
                    'apply_lighting_scene': 'lighting', 'stop_lighting_scene': 'lighting',
                    'media_play_scene': 'media', 'media_stop_scene': 'media'}
            if action['type'] in refs:
                require(action.get('target') in {o['id'] for o in choices.get(refs[action['type']], [])}, 'Action reference no longer exists')
            require(action['type'] != 'set_lighting_pixels', 'Pixel targeting requires a fixture-aware wizard')
        rule.update(id=f'wizard-{namespace}-{i}', enabled=False,
                    tags=list(dict.fromkeys(rule.get('tags', []) + d.get('tags', []) + ['Wizard'])),
                    notes=(rule.get('notes', '') + '\nCreated by ' + d['id'] + '. Review, enable and sync explicitly.').strip())
    require(bool(rules), 'No rules remain after optional choices')
    return rules, answers, namespace


def fingerprint(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
