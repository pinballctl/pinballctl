#!/usr/bin/env python3
"""Build and install Hyrule scenes. --replace-existing backs up and clears media."""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from pinballctl.media import runtime, godot_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', type=Path, default=ROOT / 'src/instance')
    parser.add_argument('--godot', default='godot')
    parser.add_argument('--replace-existing', action='store_true')
    args = parser.parse_args()
    instance = args.instance.resolve()
    media = instance / 'media'
    cfg = json.loads((media / 'media.json').read_text())
    entries = sorted((ROOT / 'backglass/zelda/entries').glob('*.tscn'))
    pack = ROOT / '.local/backglass-export/hyrule.pck'
    pack.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.godot, '--headless', '--path', str(ROOT / 'backglass'), '--editor', '--import'], check=True)
    subprocess.run([args.godot, '--headless', '--path', str(ROOT / 'backglass'), '--export-pack', 'Linux', str(pack)], check=True)
    hardware = json.loads((instance / 'hardware/mapping.json').read_text()).get('data', {})
    mappings = []
    for friendly, action in [('Left Flipper Button', 'ui_left'), ('Right Flipper Button', 'ui_right'), ('Launch Button', 'ui_accept')]:
        sources = [uid for uid, item in hardware.items() if item.get('friendly') == friendly]
        if len(sources) != 1:
            raise ValueError('Expected exactly one hardware mapping for ' + friendly)
        mappings.append(dict(id='hyrule_' + action, name='Select' if action == 'ui_accept' else friendly, triggerType='hardware', triggerFn='CLICKED', source=sources[0], eventName=friendly.upper().replace(' ', '_') + '_PRESSED', eventType='CLICKED', inputKind='action', inputValue=action, phase='tap'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / '.local/media-backups' / stamp
    backup.mkdir(parents=True)
    shutil.copy2(media / 'media.json', backup / 'media.json')
    # Stop only application-managed runtimes; never kill arbitrary Godot processes.
    for display in cfg.get('displays', []):
        godot_runtime.stop_runtime(instance, runtime_id=display['id'])
    godot_runtime.stop_scene(instance)
    if args.replace_existing:
        for relative in ('assets', 'godot/cache/assets'):
            source = media / relative
            if source.exists():
                target = backup / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
        cfg['assets'] = []
        cfg['scenes'] = []
    assets = media / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pack, assets / 'hyrule.pck')
    paths = ['res://zelda/entries/' + p.name for p in entries]
    cfg['assets'] = [a for a in cfg.get('assets', []) if a['id'] != 'asset_hyrule']
    cfg['assets'].append(dict(id='asset_hyrule', displayName='Hyrule — The Hero of Time', filename='hyrule.pck', kind='godot_scene', sizeBytes=pack.stat().st_size, durationMs=0, createdAt=datetime.now(timezone.utc).isoformat(), sourceFormat='pck', playbackFormat='pck', sceneEntries=paths, defaultSceneEntry='res://zelda/entries/attract.tscn'))
    cfg['scenes'] = [s for s in cfg.get('scenes', []) if not s['id'].startswith('hyrule_')]
    for entry, path in zip(entries, paths):
        cfg['scenes'].append(dict(id='hyrule_' + entry.stem, name='Hyrule · ' + entry.stem.replace('_', ' ').title(), screens=['display_1'], priority=100, loop=True, layers=[dict(id='hyrule_layer_' + entry.stem, name='Hyrule', type='godot_scene', assetId='asset_hyrule', sceneEntryPath=path, renderMode='primary', xPct=0, yPct=0, wPct=100, hPct=100, scale=1, opacity=1, zIndex=1, godotInputMappings=mappings)]))
    if args.replace_existing:
        cfg['settings']['defaultScenesByDisplay'] = {'display_1': 'hyrule_attract'}
        cfg['settings']['autoplayByDisplay'] = {}
        # Retire the old Main Scene reference without leaving a broken rule.
        rules_path = instance / 'rules/rules.json'
        if rules_path.exists():
            original = rules_path.read_text()
            updated = original.replace('scene_a7fafb25', 'hyrule_bonus')
            if updated != original:
                shutil.copy2(rules_path, backup / 'rules.json')
                rules_path.write_text(updated)
    runtime.save_media_config(instance, cfg)
    print(f'Installed {len(entries)} Hyrule scenes. Backup: {backup}')
    print('Application runtimes stopped to clear resource caches; launch a scene from Media.')


if __name__ == '__main__':
    main()
