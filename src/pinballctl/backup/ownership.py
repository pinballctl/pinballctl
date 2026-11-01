"""Explicit ownership: shared JSON documents are partitioned by logical keys."""
import copy
from contextlib import closing
import json
from pathlib import Path, PurePosixPath
import sqlite3
import stat

COMPONENTS = {
    'rules': 'Rules and persistent flags/counters',
    'scoring': 'Scoring and score history',
    'combos': 'Combos',
    'lighting': 'Lighting',
    'hardware': 'Hardware and accelerometer calibration',
    'playfield': 'Playfield and layout',
    'media': 'Media scenes, assets and fonts',
    'displays': 'Display configuration',
    'audio': 'Audio cues and assets',
    'settings': 'Public project settings',
    'service': 'Service history and attachments',
    'wizards': 'User wizard definitions',
}
# Entirely owned trees. Unknown files in these trees belong to the component;
# volatile files, links and special files are never treated as project content.
TREES = {'rules': ('rules',), 'lighting': ('lighting',), 'hardware': ('hardware','accelerometer'),
         'playfield': ('playfield',), 'audio': ('audio/assets',),
         'media': ('media/assets','media/fonts','media/godot/scenes'),
         'service': ('service',), 'wizards': ('wizards/user',)}
FILES = {'scoring': ('scoring/high_scores.json','scoring/history.json'),
         'audio': ('audio/audio.json',), 'media': ('media/godot/scene_registry.json',)}
VIRTUAL = {'scoring': 'scoring/config.json', 'combos': 'combos/config.json',
           'media': 'media/config.json', 'displays': 'displays/config.json',
           'settings': 'settings/public.json'}
DISPLAY_SETTINGS = {'defaultDisplayRole','defaultScenesByDisplay','autoplayByDisplay','windowScale','godot','runtimePollMs'}
PUBLIC_SETTINGS = {'name','LOG_LEVEL','CURRENCY'}
VOLATILE_NAMES = {'state.json','runtime.json','runtime_state.json','lighting_state.json','events.log'}


def read_json(path, default=None):
    if not path.exists():
        return copy.deepcopy({} if default is None else default)
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def eligible(relative):
    path = PurePosixPath(relative)
    return (all(not p.startswith('.') for p in path.parts)
            and path.name not in VOLATILE_NAMES
            and not path.name.endswith(('.lock','.tmp','-wal','-shm','.log','.sock')))


def paths(instance, component):
    root = Path(instance).resolve()
    result = set()
    for prefix in TREES.get(component, ()):
        directory = root / prefix
        if directory.is_symlink(): raise ValueError('Component directory is a symlink: '+prefix)
        if directory.exists():
            for path in directory.rglob('*'):
                rel = path.relative_to(root).as_posix()
                if not eligible(rel): continue
                mode = path.lstat().st_mode
                if stat.S_ISDIR(mode): continue
                if not stat.S_ISREG(mode) or not path.resolve().is_relative_to(root):
                    raise ValueError('Unsafe component file: '+rel)
                result.add(rel)
    for rel in FILES.get(component, ()):
        path = root / rel
        if path.is_symlink(): raise ValueError('Component file is a symlink: '+rel)
        if path.is_file(): result.add(rel)
    return sorted(result)


def public_part(instance, component):
    root = Path(instance)
    if component in ('scoring','combos'):
        data = read_json(root/'scoring/scoring.json')
        if component == 'combos': return {'combos': data.get('combos', [])}
        return {k:v for k,v in data.items() if k != 'combos'}
    if component in ('media','displays'):
        data = read_json(root/'media/media.json')
        settings = data.get('settings', {})
        if component == 'displays':
            return {'displays': data.get('displays', []),
                    'settings': {k:({a:b for a,b in v.items() if a in ('autoRestart','debugVisible')} if k == 'godot' else v) for k,v in settings.items() if k in DISPLAY_SETTINGS}}
        return {**{k:v for k,v in data.items() if k not in ('displays','settings')},
                'settings': {k:v for k,v in settings.items() if k not in DISPLAY_SETTINGS}}
    if component == 'settings':
        data = read_json(root/'settings/settings.json')
        return {k:v for k,v in data.items() if k in PUBLIC_SETTINGS}
    raise ValueError('No logical document for '+component)


def apply_parts(instance, parts):
    """Replace selected logical records, preserving unselected sibling records."""
    root = Path(instance)
    writes = {}
    if {'scoring','combos'} & parts.keys():
        data = read_json(root/'scoring/scoring.json')
        if 'scoring' in parts: data = {**parts['scoring'], 'combos': data.get('combos', [])}
        if 'combos' in parts: data['combos'] = parts['combos'].get('combos', [])
        writes['scoring/scoring.json'] = data
    if {'media','displays'} & parts.keys():
        data = read_json(root/'media/media.json')
        display = {'displays': data.get('displays', []), 'settings': {k:v for k,v in data.get('settings', {}).items() if k in DISPLAY_SETTINGS}}
        media = {**{k:v for k,v in data.items() if k not in ('displays','settings')}, 'settings': {k:v for k,v in data.get('settings', {}).items() if k not in DISPLAY_SETTINGS}}
        if 'media' in parts: media = parts['media']
        host_godot={k:v for k,v in data.get('settings',{}).get('godot',{}).items() if k in ('binary','port')}
        if 'displays' in parts: display = parts['displays']
        display=copy.deepcopy(display)
        if host_godot:
            display.setdefault('settings',{}).setdefault('godot',{}).update(host_godot)
        writes['media/media.json'] = {**media, 'displays': display.get('displays', []), 'settings': {**media.get('settings', {}), **display.get('settings', {})}}
    if 'settings' in parts:
        data = read_json(root/'settings/settings.json')
        writes['settings/settings.json'] = {**{k:v for k,v in data.items() if k not in PUBLIC_SETTINGS}, **parts['settings']}
    return writes


def valid_owned_path(component, relative):
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or str(path) != relative or '..' in path.parts or '\\' in relative:
        return False
    if relative == VIRTUAL.get(component): return True
    return eligible(relative) and (relative in FILES.get(component, ()) or any(relative.startswith(prefix+'/') for prefix in TREES.get(component, ())))


def snapshot_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix in ('.sqlite3','.sqlite','.db'):
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True, timeout=10)) as src, closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok': raise ValueError('Database integrity check failed')
    else:
        import shutil
        shutil.copyfile(source, destination)
