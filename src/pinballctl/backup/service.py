"""Streaming ZIP snapshots, strict ingestion and journalled replacement restore.

Only explicit owned files/records are managed. No archive path is extracted into
live state, and restore never sends commands to hardware or starts playback.
"""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile

from .guard import access
from .ownership import COMPONENTS, VIRTUAL, PUBLIC_SETTINGS, DISPLAY_SETTINGS, paths, public_part, apply_parts, valid_owned_path, snapshot_file, read_json

FORMAT_VERSION = 1
MAX_TOTAL = 8 * 1024**3
MAX_FILE = 4 * 1024**3
MAX_ENTRIES = 20000
MAX_JSON = 16 * 1024**2
ID = re.compile(r'^[a-f0-9]{32}$')


class BackupError(ValueError):
    pass


def check(value, message):
    if not value: raise BackupError(message)


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024**2), b''): sha.update(chunk)
    return sha.hexdigest()


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        temp.replace(path)
        sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def library_root(instance):
    value = os.environ.get('PINBALLCTL_BACKUP_DIR')
    path = Path(value).expanduser() if value else Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'pinballctl/backups'
    path = path.resolve()
    check(not path.is_relative_to(Path(instance).resolve()), 'Backup library must be outside the instance directory')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def archive_path(instance, ident):
    check(isinstance(ident, str) and ID.fullmatch(ident), 'Invalid backup ID')
    path = library_root(instance) / (ident+'.zip')
    check(path.is_file() and not path.is_symlink(), 'Backup not found')
    return path


def selected_components(components):
    check(isinstance(components, list) and bool(components) and len(components)==len(set(components)), 'Choose one or more distinct components')
    check(set(components) <= COMPONENTS.keys(), 'Unsupported component')
    return sorted(components)


def validate_manifest(data):
    check(isinstance(data, dict) and type(data.get('formatVersion')) is int and data.get('formatVersion') == FORMAT_VERSION, 'Unsupported backup format; legacy Settings exports require explicit migration')
    check(data.get('appVersion') == '0.10.0', 'Backup requires an explicit app-version migration')
    check(isinstance(data.get('project'), str) and len(data['project']) <= 200, 'Invalid project metadata')
    check(isinstance(data.get('createdAt'), str) and len(data['createdAt']) <= 80, 'Invalid timestamp')
    check(isinstance(data.get('comment'), str) and len(data['comment']) <= 2000, 'Invalid backup comment')
    try:
        stamp=datetime.fromisoformat(data['createdAt'].replace('Z','+00:00'))
        check(stamp.tzinfo is not None,'Timestamp must include timezone')
    except ValueError as exc:raise BackupError('Invalid backup timestamp') from exc
    components = selected_components(data.get('components'))
    inventory = data.get('inventory')
    check(isinstance(inventory, list) and len(inventory) <= MAX_ENTRIES, 'Invalid inventory')
    seen = set(); total = 0
    for row in inventory:
        check(isinstance(row, dict) and row.get('component') in components, 'Unknown inventory component')
        component, relative = row['component'], row.get('path')
        check(isinstance(relative, str) and len(relative) <= 400 and valid_owned_path(component, relative), 'Path outside component ownership')
        member = 'payload/'+component+'/'+relative
        check(member.casefold() not in seen, 'Duplicate inventory destination, including case collisions')
        seen.add(member.casefold())
        check(type(row.get('size')) is int and 0 <= row['size'] <= MAX_FILE, 'Invalid file size')
        check(isinstance(row.get('sha256'), str) and re.fullmatch('[a-f0-9]{64}', row['sha256']), 'Invalid checksum')
        total += row['size']
    for member in seen:
        check(not any(str(parent) in seen for parent in PurePosixPath(member).parents), 'Inventory file/directory collision')
    check(total <= MAX_TOTAL, 'Uncompressed backup exceeds 8 GiB')
    # Logical partitions must always be present, even when their snapshot is empty.
    for component in components:
        if component in VIRTUAL:
            check(any(r['component']==component and r['path']==VIRTUAL[component] for r in inventory), 'Missing logical component snapshot')
    return data


@contextmanager
def validated_archive(path, *, verify=True):
    check(path.stat().st_size <= MAX_TOTAL, 'Compressed archive exceeds 8 GiB')
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            check(len(members) <= MAX_ENTRIES+1, 'Too many ZIP entries')
            check(len({m.filename.casefold() for m in members}) == len(members), 'Duplicate ZIP names')
            for member in members:
                name = member.filename
                rel = PurePosixPath(name)
                mode = member.external_attr >> 16
                check(not member.is_dir() and name == str(rel) and not rel.is_absolute() and '..' not in rel.parts and '\\' not in name, 'Unsafe ZIP path')
                check(not member.flag_bits & 1, 'Encrypted archives are unsupported')
                check(stat.S_IFMT(mode) in (0, stat.S_IFREG), 'ZIP symlink or special file rejected')
                check(member.file_size <= MAX_FILE and member.file_size <= max(1024**2, member.compress_size*500), 'ZIP expansion limit exceeded')
            check('manifest.json' in archive.namelist(), 'Versioned manifest required; legacy ZIP import is disabled')
            check(archive.getinfo('manifest.json').file_size <= MAX_JSON, 'Manifest too large')
            manifest = validate_manifest(json.loads(archive.read('manifest.json')))
            expected = {'manifest.json'} | {'payload/'+r['component']+'/'+r['path'] for r in manifest['inventory']}
            check(set(archive.namelist()) == expected, 'ZIP contents do not match manifest')
            for row in manifest['inventory']:
                name = 'payload/'+row['component']+'/'+row['path']
                check(archive.getinfo(name).file_size == row['size'], 'Inventory size mismatch')
                if row['component'] in VIRTUAL and row['path'] == VIRTUAL[row['component']]:
                    check(row['size'] <= MAX_JSON,'Logical component JSON exceeds limit')
                    validate_part(row['component'],json.loads(archive.read(name)))
                if verify:
                    sha = hashlib.sha256()
                    with archive.open(name) as stream:
                        for chunk in iter(lambda: stream.read(1024**2), b''): sha.update(chunk)
                    check(sha.hexdigest() == row['sha256'], 'Checksum mismatch: '+row['path'])
            yield archive, manifest
    except (zipfile.BadZipFile, RuntimeError, KeyError, ValueError, TypeError, RecursionError) as exc:
        raise BackupError('Invalid archive: '+str(exc)) from exc


def create(instance, components, comment='', progress=lambda **kw: None, *, locked=False):
    components = selected_components(components)
    check(isinstance(comment, str) and len(comment) <= 2000, 'Comment must be at most 2000 characters')
    if not locked:
        with access(instance, exclusive=True):
            return create(instance, components, comment, progress, locked=True)
    root = Path(instance).resolve(); store = library_root(root)
    ident = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=store) as temporary:
        temp = Path(temporary); inventory = []; total = 0
        for component in components:
            for relative in paths(root, component):
                source = root/relative; destination = temp/'payload'/component/relative
                progress(message='Snapshotting '+relative)
                snapshot_file(source, destination)
                size = destination.stat().st_size; total += size
                check(size <= MAX_FILE and total <= MAX_TOTAL and len(inventory)<MAX_ENTRIES, 'Snapshot exceeds archive limits')
                inventory.append({'component':component,'path':relative,'size':size,'sha256':digest(destination)})
            if component in VIRTUAL:
                relative = VIRTUAL[component]; destination = temp/'payload'/component/relative
                write_json(destination, public_part(root, component))
                inventory.append({'component':component,'path':relative,'size':destination.stat().st_size,'sha256':digest(destination)})
        project = read_json(root/'settings/settings.json').get('name','Pinball CTL')
        manifest = {'formatVersion':FORMAT_VERSION,'appVersion':'0.10.0','project':str(project)[:200],
                    'createdAt':datetime.now(timezone.utc).isoformat(),'components':components,'comment':comment,
                    'inventory':inventory,'dependencies':'Validated against the final selected project at restore preview',
                    'policy':'Authoring and durable project data only; credentials, session keys, browser profiles, active playback/game state, queues, caches and logs excluded.'}
        validate_manifest(manifest)
        staged = temp/'archive.zip'
        with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
            for row in inventory:
                name = 'payload/'+row['component']+'/'+row['path']; archive.write(temp/name,name)
        check(staged.stat().st_size <= MAX_TOTAL, 'Compressed archive exceeds limit')
        with validated_archive(staged, verify=False): pass
        staged.replace(store/(ident+'.zip'))
        os.chmod(store/(ident+'.zip'),0o600)
    return {'id':ident,**manifest,'archiveSize':(store/(ident+'.zip')).stat().st_size}


def upload(instance, stream):
    store = library_root(instance)
    ident = uuid.uuid4().hex; temp = store/(ident+'.upload')
    total = 0
    try:
        with temp.open('xb') as output:
            os.chmod(temp,0o600)
            while chunk := stream.read(1024**2):
                total += len(chunk); check(total <= MAX_TOTAL, 'Upload exceeds 8 GiB'); output.write(chunk)
        with validated_archive(temp) as (_, manifest):
            result = {'id':ident,**manifest,'archiveSize':total}
        temp.replace(store/(ident+'.zip'))
        return result
    finally:
        temp.unlink(missing_ok=True)


def list_backups(instance):
    result = []; errors = []
    for path in sorted(library_root(instance).glob('*.zip')):
        if not ID.fullmatch(path.stem): continue
        try:
            with validated_archive(path, verify=False) as (_, manifest):
                result.append({'id':path.stem,**manifest,'archiveSize':path.stat().st_size})
        except (BackupError,OSError,ValueError,TypeError,RecursionError) as exc: errors.append({'id':path.stem,'error':str(exc)})
    result.sort(key=lambda row:row['createdAt'],reverse=True)
    return result, errors


def revision(instance):
    root = Path(instance)
    info = []
    for component in COMPONENTS:
        for rel in paths(root,component):
            st = (root/rel).stat(); info.append((rel,st.st_size,st.st_mtime_ns))
        if component in VIRTUAL:
            info.append((component, json.dumps(public_part(root,component),sort_keys=True)))
    return hashlib.sha256(json.dumps(info,sort_keys=True).encode()).hexdigest()


def active_writers(instance):
    root = Path(instance)
    from pinballctl.bridge.state import commands_path
    if root.resolve() == commands_path().parent.parent.resolve():
        from pinballctl.cli import _bridge_running_via_lock
        check(not _bridge_running_via_lock()[0], 'Pause the bridge process before restoring, including offline reconnects')
    bridge = read_json(root/'bridge/bridge_state.json')
    check(not bridge.get('connected'), 'Stop the bridge before restoring. Restore never re-arms or starts it.')
    audio = read_json(root/'audio/runtime.json')
    check(not audio.get('active') and not audio.get('playbacks') and not audio.get('engine',{}).get('active'), 'Stop Audio playback before restoring')
    media = read_json(root/'media/media_state.json')
    check(not media.get('sessions') and not media.get('surfaceSessions') and not media.get('runtimeSessions') and not media.get('engine',{}).get('active'), 'Stop Media playback before restoring')
    for file in [root/'media/godot/runtime_state.json', *(root/'media/godot').glob('instances/*/runtime_state.json')]:
        data = read_json(file)
        pid = data.get('pid') or data.get('runtimePid') or data.get('process',{}).get('pid')
        if type(pid) is int and pid > 0:
            try: os.kill(pid,0)
            except ProcessLookupError: continue
            raise BackupError('Stop the Godot display runtimes before restoring')


def extract_selected(instance, sequence, destination):
    """Latest complete snapshot for a selected component wins in a sequence."""
    check(isinstance(sequence,list) and 1 <= len(sequence) <= 10, 'Choose 1–10 backup steps')
    selected = set(); source_versions = []
    for step in sequence:
        check(isinstance(step,dict), 'Invalid restore step')
        components = selected_components(step.get('components'))
        with validated_archive(archive_path(instance,step.get('id'))) as (archive,manifest):
            check(set(components) <= set(manifest['components']), 'Component absent from this backup')
            for component in components:
                folder = destination/component
                if folder.exists(): shutil.rmtree(folder)
                folder.mkdir(parents=True)
            for row in manifest['inventory']:
                if row['component'] not in components: continue
                target = destination/row['component']/row['path']; target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open('payload/'+row['component']+'/'+row['path']) as source, target.open('wb') as output:
                    shutil.copyfileobj(source,output,1024**2)
            source_versions.append({'id':step['id'],'manifest':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()})
            selected.update(components)
    return selected,source_versions


def validate_part(component, data):
    check(isinstance(data,dict), 'Logical component is not an object')
    if component in ('game','ball'):
        from pinballctl.game.runtime import validate_snapshot
        check(not set(data)-({'config','state','financialIds'} if component=='game' else {'config','state'}),'Invalid manager snapshot')
        if component=='game':
            check(isinstance(data.get('financialIds',[]),list) and len(data.get('financialIds',[]))<=100000,'Invalid financial replay guards')
            for row in data.get('financialIds',[]):
                check(isinstance(row,list) and len(row)==3 and all(isinstance(value,str) for value in row),'Invalid financial replay guard')
                check(isinstance(json.loads(row[2]),dict),'Invalid financial replay result')
        validate_snapshot(component,data)
        check(isinstance(data.get('state',{}),dict),'Invalid manager state')
    if component=='settings':
        check(set(data)<=PUBLIC_SETTINGS and all(isinstance(v,str) and len(v)<=200 for v in data.values()), 'Archive contains invalid or protected settings')
    if component=='scoring': check('combos' not in data, 'Scoring snapshot includes unselected Combos')
    if component=='combos': check(set(data)=={'combos'} and isinstance(data['combos'],list), 'Invalid Combos snapshot')
    if component=='media': check('displays' not in data and not set(data.get('settings',{})) & DISPLAY_SETTINGS, 'Media snapshot contains Displays records')
    if component=='displays':
        check(set(data)=={'displays','settings'} and isinstance(data['displays'],list) and set(data['settings'])<=DISPLAY_SETTINGS, 'Invalid Displays snapshot')
        check(set(data['settings'].get('godot',{})) <= {'autoRestart','debugVisible'}, 'Archive contains protected host runtime settings')


def prepare(instance, sequence, clear_others, stage):
    check(type(clear_others) is bool, 'Destructive option must be boolean')
    root = Path(instance).resolve()
    selected, versions = extract_selected(root,sequence,stage)
    affected = set(COMPONENTS) if clear_others else selected
    writes = {}; deletes = set(); parts = {}; records = []
    for component in sorted(affected):
        current = set(paths(root,component)); incoming = set()
        folder = stage/component
        if component in selected:
            incoming = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        for rel in incoming:
            check(valid_owned_path(component,rel),'Invalid restore path')
            source=folder/rel
            if rel == VIRTUAL.get(component):
                check(source.stat().st_size <= MAX_JSON,'Logical document exceeds JSON limit')
                parts[component]=read_json(source);validate_part(component,parts[component])
            else:
                if source.suffix in ('.sqlite3','.sqlite','.db'):
                    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True)) as database:
                        check(database.execute('PRAGMA quick_check').fetchone()[0] == 'ok', 'Invalid SQLite snapshot')
                writes[rel]=source
        deletes.update(current-incoming)
        if component not in selected and component in VIRTUAL: parts[component]={}
        logical_before=public_part(root,component) if component in VIRTUAL else {}
        logical_after=parts.get(component,{})
        removed_records={}
        for key,values in logical_before.items():
            if isinstance(values,list):
                old_ids={str(row.get('id',index)) for index,row in enumerate(values) if isinstance(row,dict)}
                new_ids={str(row.get('id',index)) for index,row in enumerate(logical_after.get(key,[])) if isinstance(row,dict)}
                removed_records[key]=sorted(old_ids-new_ids)
        records.append({'component':component,'removedRecords':removed_records,'mode':'replace' if component in selected else 'clear',
                        'incomingFiles':len(incoming),'removeFiles':sorted(current-incoming)})
    if {'game','ball','scoring'} & parts.keys():
        from pinballctl.game import store as manager_store
        from pinballctl.game.runtime import initial as initial_game
        from pinballctl.ball.runtime import initial as initial_ball
        target=stage/'.shared/game/management.sqlite';target.parent.mkdir(parents=True,exist_ok=True)
        live=manager_store.path(root)
        if live.exists():snapshot_file(live,target)
        staged_instance=stage/'.shared'
        with manager_store.transaction(staged_instance) as database:
            for kind in ('game','ball'):
                if kind in parts:
                    data=parts[kind]
                    from pinballctl.game.runtime import GAME_DEFAULTS,BALL_DEFAULTS
                    manager_store.write(database,kind+'Config',data.get('config',GAME_DEFAULTS if kind=='game' else BALL_DEFAULTS))
                    manager_store.write(database,kind,data.get('state',initial_game() if kind=='game' else initial_ball()))
                    if kind=='game':
                        for ident,request,result in data.get('financialIds',[]):
                            existing=database.execute('SELECT request FROM financial_ids WHERE id=?',(ident,)).fetchone()
                            check(not existing or existing[0]==request,'Conflicting financial settlement identity')
                            database.execute('INSERT OR IGNORE INTO financial_ids VALUES(?,?,?)',(ident,request,result))
            if 'scoring' in parts:
                managed=parts['scoring'].get('_managedScoring',{})
                for key in ('scores','history','highScores'):manager_store.write(database,key,managed.get(key,{} if key=='scores' else {'games':[]} if key=='history' else {'scores':[]}))
            game=manager_store.read(database,'game',initial_game());ball=manager_store.read(database,'ball',initial_ball())
            if game.get('status') not in ('IDLE','GAME_ENDED'):
                if game.get('status') in ('PREPARING','BALL_ACTIVE'):game['resumeStatus']=game['status']
                game.update(status='RECOVERY_REQUIRED',reason='Backup restored; reconcile physical balls before resuming')
            ball.update(inPlay=None,confidence='unknown',pending=[],sensors={},zones={},reason='Physical observations are invalid after restore')
            manager_store.write(database,'game',game);manager_store.write(database,'ball',ball)
            database.execute('DELETE FROM commands');database.execute('DELETE FROM outbox');database.execute('DELETE FROM receipts');database.execute('DELETE FROM ingress');manager_store.write(database,'ingressClock',{})
        with closing(sqlite3.connect(target)) as database:database.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        writes['game/management.sqlite']=target
    for rel,data in apply_parts(root,parts).items():
        staged=stage/'.shared'/rel;write_json(staged,data);writes[rel]=staged
    for rel in list(writes)+list(deletes):
        dest=root/rel
        check(dest.resolve().is_relative_to(root) and not any(p.is_symlink() for p in [dest,*dest.parents] if p != root.parent), 'Live destination uses a symlink')
        if rel.endswith(('.sqlite3','.sqlite','.db')):
            for suffix in ('-wal','-shm'):
                if (root/(rel+suffix)).exists(): deletes.add(rel+suffix)
    # Build lightweight final configuration view for cross-component validation.
    config_files=('rules/rules.json','hardware/mapping.json','lighting/lighting.json','audio/audio.json','media/media.json','scoring/scoring.json','playfield/layout.json')
    final={}
    for rel in config_files:
        source=writes.get(rel,root/rel)
        if rel in deletes: final[rel]=[] if rel.startswith('rules/') else {};continue
        if source.exists():
            check(source.stat().st_size <= MAX_JSON,'Configuration JSON exceeds limit')
            final[rel]=read_json(source)
        else: final[rel]=[] if rel.startswith('rules/') else {}
    def generated_file(relative, content):
        target=stage/'.compiled'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(content,bytes):target.write_bytes(content)
        else:write_json(target,content)
        writes[relative]=target
    if {'rules','game','ball','hardware'} & selected:
        from pinballctl.ops.rules_blob import build_rules_pd_bytes, decode_rules_pd_bytes
        from pinballctl.game.runtime import observation_rules
        manager_instance=stage/'.shared' if 'game/management.sqlite' in writes else root
        observer=observation_rules(manager_instance,mapping=final['hardware/mapping.json'])
        authored=stage/'.compiled-authored.json';write_json(authored,final['rules/rules.json'])
        blob=build_rules_pd_bytes(authored,observer);bundle=decode_rules_pd_bytes(blob)
        generated_file('rules/rules.pd',blob)
        generated_file('rules/rules_meta.json',{'sha256':hashlib.sha256(blob).hexdigest(),'size':len(blob),'sourceHash':bundle.source_hash,'builtAt':bundle.built_at})
    if 'lighting' in selected and 'lighting/lighting.json' in writes:
        from pinballctl.ops.lighting_blob import build_lighting_pd_bytes, compile_lighting_timeline
        blob=build_lighting_pd_bytes(writes['lighting/lighting.json'])
        generated_file('lighting/lighting.pd',blob)
        generated_file('lighting/lighting.compiled.json',compile_lighting_timeline(writes['lighting/lighting.json']))
        # Normal Sync computes source hashes using the current Hardware mapping.
        generated_file('lighting/lighting_meta.json',{'sha256':hashlib.sha256(blob).hexdigest(),'size':len(blob),'sourceHash':''})
    if 'hardware' in selected and 'hardware/mapping.json' in writes:
        from pinballctl.ops.mapping_blob import build_mapping_blob_bytes
        generated_file('hardware/mapping.pb',build_mapping_blob_bytes(writes['hardware/mapping.json']))
    all_paths = {p for c in COMPONENTS for p in paths(root,c)} | set(writes)
    all_paths -= deletes - set(writes)
    validate_references(final, all_paths)
    return writes,deletes,{'selected':sorted(selected),'affected':sorted(affected),'removeOtherContent':clear_others,
                          'components':records,'writePaths':sorted(writes),'deletePaths':sorted(deletes),
                          'sourceVersions':versions,'revision':revision(root),
                          'warnings':['Every selected component is completely replaced. Unselected managed components '+('are deleted.' if clear_others else 'remain unchanged.'),
                                      'Audio and display playback must be stopped. Restore automatically stops and restarts a previously running bridge, without arming hardware.',
                                      'Public settings only. Credentials, host configuration and browser profiles are preserved.']}


def validate_references(final, all_paths):
    mapping=final['hardware/mapping.json'];mapping=mapping.get('data',mapping) if isinstance(mapping,dict) else {}
    valid_hw=set(mapping)
    valid_hw.update(str(row.get('componentId')) for row in mapping.values() if isinstance(row,dict) and row.get('componentId'))
    lighting=final['lighting/lighting.json'];audio=final['audio/audio.json'];media=final['media/media.json']
    check(all(isinstance(x,dict) for x in (lighting,audio,media)), 'Invalid component configuration')
    ids=lambda data,key:{str(row.get('id')) for row in data.get(key,[]) if isinstance(row,dict)}
    resources={'sound':ids(audio,'cues'),'lighting':ids(lighting,'scenes'),'media':ids(media,'scenes')}
    rules=final['rules/rules.json'];check(isinstance(rules,list),'Rules snapshot must be an array')
    for rule in rules:
        check(isinstance(rule,dict),'Invalid rule record')
        triggers=rule.get('triggers',[])+[t for g in rule.get('triggerGroups',{}).get('groups',[]) for t in g.get('items',[])]
        for trigger in triggers:
            if trigger.get('type')=='hardware':check(trigger.get('source') in valid_hw,'Rule references hardware absent from final project: '+str(trigger.get('source')))
        for action in rule.get('actions',[]):
            kind=action.get('type');params=action.get('params') or {};target=action.get('target')
            if kind in ('pulse','set_output','set_lcd_text'):check(target in valid_hw,'Rule output absent from final Hardware')
            group={'play_audio_cue':'sound','stop_audio_cue':'sound','toggle_audio_cue':'sound','apply_lighting_scene':'lighting','stop_lighting_scene':'lighting','media_play_scene':'media','media_stop_scene':'media'}.get(kind)
            if group:
                ref=params.get({'sound':'cueId','lighting':'sceneId','media':'sceneId'}[group]) or target
                check(ref in resources[group] or (str(kind).startswith('stop_') and ref=='*'),'Rule references a '+group+' item absent from final project: '+str(ref))
    from pinballctl.app.modules.integrity import api as integrity
    components=integrity._component_mapping_data(mapping)
    by_tail={integrity._uid_tail(key):key for key in components}
    hw_refs,cue_refs=integrity._collect_refs(rules,final['playfield/layout.json'],lighting,final['scoring/scoring.json'],set(components),by_tail)
    report=integrity._build_report(components,integrity._collect_lcd_device_ids(mapping),audio.get('assets',[]),audio.get('cues',[]),hw_refs,cue_refs,integrity._collect_asset_refs(audio))
    failures=[item['details']+': '+item['name'] for item in report['items'] if item['status']=='error']
    check(not failures,'Final project integrity check failed: '+'; '.join(failures[:10]))
    for cue in audio.get('cues',[]):
        asset=cue.get('assetId')
        if asset:check(asset in ids(audio,'assets'),'Audio cue references a missing asset')
    for component, config in [('audio',audio),('media',media)]:
        for asset in config.get('assets',[]):
            filename = asset.get('filename') or asset.get('file')
            if filename:
                check(isinstance(filename,str) and Path(filename).name == filename and component+'/assets/'+filename in all_paths, component+' references a missing or unsafe asset file')
    valid_displays=ids(media,'displays')|{str(d.get('role')) for d in media.get('displays',[]) if isinstance(d,dict)}
    for scene in media.get('scenes',[]):
        target=scene.get('targetDisplay')
        if target:check(target in valid_displays or target in ('all','*'),'Media scene references a missing display')


def preview(instance, sequence, clear_others=False):
    with access(instance,exclusive=True):
        with tempfile.TemporaryDirectory(prefix='.preview-',dir=library_root(instance)) as folder:
            _,_,report=prepare(instance,sequence,clear_others,Path(folder))
            return report


def rollback(instance, transaction):
    root=Path(instance).resolve();journal=read_json(transaction/'journal.json')
    check(journal.get('instance')==str(root),'Recovery belongs to another project')
    for row in journal['files']:
        relative=row['path'];dest=root/relative
        check(dest.resolve().is_relative_to(root),'Unsafe recovery destination')
        if row['existed']:
            source=transaction/'old'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            temp=dest.with_name('.restore-'+uuid.uuid4().hex);shutil.copyfile(source,temp)
            os.chmod(temp,row.get('mode',0o600))
            with temp.open('rb') as replacement:os.fsync(replacement.fileno())
            temp.replace(dest);sync_directory(dest.parent)
        else:
            dest.unlink(missing_ok=True)
            if dest.parent.exists(): sync_directory(dest.parent)
    journal['state']='rolled_back';write_json(transaction/'journal.json',journal)


def recover(instance):
    store=library_root(instance)
    pending = [d for d in (store/'transactions').glob('*') if read_json(d/'journal.json').get('instance') == str(Path(instance).resolve()) and read_json(d/'journal.json').get('state') == 'applying']
    if not pending:
        marker=Path(instance)/'.project-locks/restore-pending'
        if marker.exists():
            with access(instance,exclusive=True): marker.unlink(missing_ok=True)
        return
    with access(instance,exclusive=True),access(instance,runtime=True,exclusive=True,timeout=0):
        active_writers(instance)
        for directory in pending:
            journal=read_json(directory/'journal.json')
            if journal.get('instance')==str(Path(instance).resolve()) and journal.get('state')=='applying':rollback(instance,directory)
        (Path(instance)/'.project-locks/restore-pending').unlink(missing_ok=True)


def restore(instance, sequence, clear_others, expected, progress=lambda **kw:None):
    root=Path(instance).resolve();store=library_root(root)
    # Bridge owns a shared runtime lease for its entire lifetime, including reconnects.
    with access(root,exclusive=True),access(root,runtime=True,exclusive=True,timeout=0):
        active_writers(root)
        with tempfile.TemporaryDirectory(prefix='.restore-',dir=store) as folder:
            stage=Path(folder);writes,deletes,report=prepare(root,sequence,clear_others,stage)
            check(report==expected,'Project or archive changed; preview again')
            recovery=create(root,report['affected'],'Automatic pre-restore recovery snapshot',progress,locked=True)
            progress(message='Recovery snapshot saved', recoveryId=recovery['id'])
            transaction=store/'transactions'/uuid.uuid4().hex;transaction.mkdir(parents=True,mode=0o700)
            files=[]
            for relative in sorted(set(writes)|deletes):
                dest=root/relative
                check(not dest.exists() or dest.is_file(),'Restore destination is not a regular file')
                exists=dest.exists();files.append({'path':relative,'existed':exists,'mode':stat.S_IMODE(dest.stat().st_mode) if exists else 0o600})
                if exists:
                    old=transaction/'old'/relative;old.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dest,old);os.chmod(old,0o600)
                    with old.open('rb') as old_stream:os.fsync(old_stream.fileno())
                    sync_directory(old.parent)
            for directory in sorted((p for p in transaction.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):sync_directory(directory)
            sync_directory(transaction);sync_directory(transaction.parent)
            journal={'state':'applying','instance':str(root),'recoveryId':recovery['id'],'files':files}
            write_json(transaction/'journal.json',journal)
            marker=root/'.project-locks/restore-pending'
            write_json(marker,{'transaction':transaction.name})
            sync_directory(root)
            try:
                for relative in sorted(deletes-set(writes)):
                    progress(message='Removing '+relative);(root/relative).unlink(missing_ok=True)
                    sync_directory((root/relative).parent)
                for relative,source in writes.items():
                    progress(message='Replacing '+relative);dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                    temp=dest.with_name('.restore-'+uuid.uuid4().hex)
                    shutil.copyfile(source,temp)
                    os.chmod(temp,stat.S_IMODE(dest.stat().st_mode) if dest.exists() else 0o600)
                    with temp.open('rb') as replacement:os.fsync(replacement.fileno())
                    temp.replace(dest);sync_directory(dest.parent)
                generation_path=root/'.project-locks/generation'
                prior=read_json(generation_path)
                versions=prior.get('components') or {name:prior.get('id','') for name in prior.get('affected',[])}
                generation=uuid.uuid4().hex
                versions.update({name:generation for name in report['affected']})
                write_json(generation_path,{'id':generation,'affected':report['affected'],'components':versions})
                journal['state']='committed';write_json(transaction/'journal.json',journal)
            except Exception:
                rollback(root,transaction)
                raise
            finally:
                if read_json(transaction/'journal.json').get('state') in ('committed','rolled_back'):
                    marker.unlink(missing_ok=True)
                    shutil.rmtree(transaction)
            return {'ok':True,'recoveryId':recovery['id'],'components':report['selected'],'restartRequired':True}
