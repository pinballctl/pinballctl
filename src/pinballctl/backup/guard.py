"""Cross-process project access barrier; bridge lifetime separately blocks restore."""
from contextlib import contextmanager
from functools import wraps
import fcntl
from pathlib import Path
from threading import local, Lock
import json
import sys
import time

_LOCAL = local()
_GENERATIONS = {}
_COMPONENT_GENERATIONS = {}
_GENERATION_LOCK = Lock()


def refresh_caches(instance):
    """Each process invalidates only restored components at its next access."""
    root=Path(instance).resolve();key=str(root);path=root/'.project-locks/generation'
    try:
        meta=path.stat();signature=(meta.st_mtime_ns,meta.st_ino,meta.st_size)
    except FileNotFoundError:return
    from flask import has_app_context, current_app
    if has_app_context() and current_app.config.get('_RESTORE_SETTINGS_GENERATION') != signature:
        metadata=json.loads(path.read_text())
        settings_version=metadata.get('components',{}).get('settings') or (metadata.get('id') if 'settings' in metadata.get('affected',[]) else None)
        if settings_version and current_app.config.get('_RESTORE_SETTINGS_VERSION') != settings_version:
            from pinballctl.app.settings_store import load_settings
            data=load_settings(root)
            current_app.config['USER_SETTINGS']=data
            current_app.config['_RESTORE_SETTINGS_VERSION']=settings_version
            for name in ('LOG_LEVEL','CURRENCY'):
                if name in data:current_app.config[name]=data[name]
                else:current_app.config.pop(name,None)
        current_app.config['_RESTORE_SETTINGS_GENERATION']=signature
    with _GENERATION_LOCK:
        if _GENERATIONS.get(key)==signature:return
        metadata=json.loads(path.read_text())
        versions=metadata.get('components') or {name:metadata['id'] for name in metadata['affected']}
        previous=_COMPONENT_GENERATIONS.get(key,{})
        affected={name for name,version in versions.items() if previous.get(name)!=version}
        rules=sys.modules.get('pinballctl.rules.runtime')
        if rules and affected & {'rules','hardware'}:
            with rules._CONFIG_CACHE_LOCK:
                for slot in list(rules._CONFIG_CACHE):
                    if key in slot:rules._CONFIG_CACHE.pop(slot,None)
        audio=sys.modules.get('pinballctl.audio.runtime')
        if audio and 'audio' in affected:
            with audio._CFG_LOCK:audio._CFG_CACHE.pop(str(root/'audio/audio.json'),None)
            with audio._ENGINE_LOCK:audio._ENGINES.pop(key,None)
        media=sys.modules.get('pinballctl.media.runtime')
        if media and affected & {'media','displays'}:
            with media._RUNTIMES_LOCK:media._RUNTIMES.pop(key,None)
        _COMPONENT_GENERATIONS[key]=versions
        _GENERATIONS[key]=signature



@contextmanager
def access(instance, *, exclusive=False, runtime=False, timeout=10):
    root = Path(instance).resolve()
    key = str(root) + (':runtime' if runtime else ':data')
    held = getattr(_LOCAL, 'held', {})
    if key in held:
        if exclusive and not held[key]:
            raise RuntimeError('Cannot upgrade a project read lock')
        yield
        return
    folder = root / '.project-locks'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ('runtime.lock' if runtime else 'data.lock')).open('a') as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Project busy. Stop bridge/playback before restore, or retry after the current operation.')
                time.sleep(.05)
        if not exclusive and not runtime and (folder/'restore-pending').exists():
            raise RuntimeError('Project restore requires recovery. Reload the web service before continuing.')
        held[key] = exclusive
        _LOCAL.held = held
        try:
            if not exclusive and not runtime:refresh_caches(root)
            yield
        finally:
            held.pop(key, None)
            fcntl.flock(stream, fcntl.LOCK_UN)


def guarded(function):
    """Guard a runtime entry point whose first argument is instance_path."""
    @wraps(function)
    def call(instance_path, *args, **kwargs):
        with access(instance_path):
            return function(instance_path, *args, **kwargs)
    return call


def bridge_lease(function):
    @wraps(function)
    def call(*args, **kwargs):
        from pinballctl.bridge.state import commands_path
        with access(commands_path().parent.parent, runtime=True):
            return function(*args, **kwargs)
    return call


def playback_lease(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        with access(self.instance_path, runtime=True):
            return function(self, *args, **kwargs)
    return call


def install(app):
    """All HTTP access participates; restore jobs run outside request locks."""
    from flask import g, request

    @app.before_request
    def project_barrier():
        if request.path.startswith(('/api/backups', '/backups', '/assets/')) or str(request.endpoint).endswith('.static'):
            return
        manager = access(app.instance_path)
        try:
            manager.__enter__()
        except RuntimeError as exc:
            from flask import jsonify
            return jsonify(ok=False, error='project_maintenance', detail=str(exc)), 503
        g._project_backup_access = manager

    @app.teardown_request
    def release_project_barrier(error):
        manager = g.pop('_project_backup_access', None)
        if manager is not None: manager.__exit__(None, None, None)
