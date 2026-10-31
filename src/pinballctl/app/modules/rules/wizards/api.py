"""Authoring-only wizard endpoints; never sync or operate hardware."""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, jsonify, request
from itsdangerous import URLSafeTimedSerializer, BadSignature

from .. import api_bp
from .. import api as rules_api
from .engine import InvalidWizard, discover, fingerprint, generate, require, resolve_answers, validate


@contextmanager
def rules_lock():
    path = Path(current_app.instance_path) / 'rules' / '.authoring.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def choices():
    devices, _ = rules_api._build_hardware_devices(rules_api._load_mapping_rows())
    inputs = [dict(d, name=d['friendly']) for d in devices if d['deviceClass'] in ('button', 'switch')]
    from pinballctl.rules.evaluation import snapshot
    state = snapshot(current_app.instance_path)
    result = {'input': inputs, 'switch': [d for d in inputs if d['deviceClass'] == 'switch'],
              'output': [], 'coil': [], 'sound': [c for c in rules_api._audio_cue_ids() if c.get('enabled', True)],
              'lighting': rules_api._lighting_scene_ids(), 'media': rules_api._media_scene_ids()}
    for kind in ('flag', 'counter'):
        names = set(state[kind + 's'])
        for rule in rules_api._load_rules_list():
            for action in rule.get('actions', []):
                if action.get('type') in (('set_flag',) if kind == 'flag' else ('set_counter', 'inc_counter')):
                    names.add(action.get('target', ''))
        result[kind] = [{'id': n, 'name': n} for n in sorted(names) if n]
    return result


def definition(wizard_id):
    definitions, _ = discover(current_app.instance_path)
    require(wizard_id in definitions, 'Wizard not found or invalid')
    return definitions[wizard_id]


def signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='rules-wizard-preview-v1')


def save_atomically(rules):
    """Compile everything before replacing; rules.json is authoritative."""
    target = rules_api._rules_path()
    artifacts = [target, rules_api._rules_pd_path(), rules_api._rules_meta_path()]
    previous = {path: path.read_bytes() if path.exists() else None for path in artifacts}
    fd, name = tempfile.mkstemp(prefix='.wizard-', suffix='.json', dir=target.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(rules, output, ensure_ascii=False, indent=2)
            output.flush(); os.fsync(output.fileno())
        blob = rules_api._build_rules_pd_from_path(temp)
        # Publish compiled output only after compilation succeeds. Nothing syncs.
        rules_api._rules_pd_path().write_bytes(blob)
        rules_api._write_rules_meta(blob)
        temp.replace(target)
    except Exception:
        for path, data in previous.items():
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)
        raise
    finally:
        temp.unlink(missing_ok=True)


@api_bp.get('/wizards')
def wizard_catalogue():
    definitions, errors = discover(current_app.instance_path)
    return jsonify(ok=True, wizards=list(definitions.values()), diagnostics=errors, choices=choices())


@api_bp.post('/wizards/preview')
def wizard_preview():
    try:
        require((request.content_length or 0) <= 131072, 'Request too large')
        body = request.get_json(silent=True) or {}
        d = definition(body.get('id'))
        options = choices()
        if body.get('partial') is True:
            answers, steps = resolve_answers(d, body.get('answers', {}), options, partial=True)
            return jsonify(ok=True, answers=answers, steps=steps)
        bridge = rules_api.read_bridge_state()
        require(not bridge.get('connected') or bridge.get('rules_runtime_version', 0) >= d['minimumRuntimeVersion'], 'ESP firmware update required before previewing this wizard')
        generated, answers, namespace = generate(d, body.get('answers', {}), options, body.get('namespace'))
        generated = rules_api._normalize_rules(generated)
        require(not rules_api._validate_rules_before_save(generated), 'Generated rules failed validation')
        existing = rules_api._load_rules_list()
        require(not {r['id'] for r in generated} & {r.get('id') for r in existing}, 'This preview was already created')
        payload = {'id': d['id'], 'definition': fingerprint(d), 'answers': answers,
                   'namespace': namespace, 'revision': fingerprint(existing), 'rules': fingerprint(generated)}
        token = signer().dumps(payload)
        return jsonify(ok=True, rules=generated, answers=answers, namespace=namespace, token=token,
                       warnings=d.get('warnings', []) + ['Rules start disabled. Review before enabling; creation does not sync to ESP.'])
    except (InvalidWizard, TypeError, KeyError) as exc:
        return jsonify(ok=False, error=str(exc)), 400


@api_bp.post('/wizards/create')
def wizard_create():
    try:
        require((request.content_length or 0) <= 131072, 'Request too large')
        body = request.get_json(silent=True) or {}
        payload = signer().loads(body.get('token', ''), max_age=1800)
        with rules_lock():
            d = definition(payload['id'])
            require(fingerprint(d) == payload['definition'], 'Definition changed; preview again')
            bridge = rules_api.read_bridge_state()
            require(not bridge.get('connected') or bridge.get('rules_runtime_version', 0) >= d['minimumRuntimeVersion'], 'ESP firmware changed; update before creating')
            current = rules_api._load_rules_list()
            require(fingerprint(current) == payload['revision'], 'Rules changed; preview again')
            generated, _, _ = generate(d, payload['answers'], choices(), payload['namespace'])
            generated = rules_api._normalize_rules(generated)
            require(fingerprint(generated) == payload['rules'], 'References changed; preview again')
            require(not {r['id'] for r in generated} & {r.get('id') for r in current}, 'Already created')
            issues = rules_api._validate_rules_before_save(generated)
            require(not issues, 'Generated rules failed validation')
            save_atomically(current + generated)
        return jsonify(ok=True, created=[r['id'] for r in generated])
    except (InvalidWizard, BadSignature, TypeError, KeyError) as exc:
        return jsonify(ok=False, error=str(exc)), 409


@api_bp.get('/wizards/export/<wizard_id>')
def wizard_export(wizard_id):
    try:
        data = dict(definition(wizard_id)); data.pop('origin', None)
        return jsonify(data)
    except InvalidWizard as exc:
        return jsonify(ok=False, error=str(exc)), 404


@api_bp.post('/wizards/import')
def wizard_import():
    try:
        require((request.content_length or 0) <= 131072, 'Definition exceeds 128 KiB')
        data = validate(request.get_json(silent=True))
        existing, _ = discover(current_app.instance_path)
        require(data['id'] not in existing, 'ID already installed; no silent overwrite')
        directory = Path(current_app.instance_path) / 'wizards' / 'user'
        directory.mkdir(parents=True, exist_ok=True)
        require(not directory.is_symlink() and directory.resolve().is_relative_to(Path(current_app.instance_path).resolve()), 'Unsafe user definition directory')
        path = directory / (data['id'] + '.json')
        with path.open('x') as output:
            json.dump(data, output, indent=2)
        return jsonify(ok=True, id=data['id'])
    except (InvalidWizard, FileExistsError, TypeError) as exc:
        return jsonify(ok=False, error=str(exc)), 400
