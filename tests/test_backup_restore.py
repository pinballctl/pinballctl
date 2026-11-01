import copy
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from pinballctl.backup import service as backup
from pinballctl.backup.ownership import COMPONENTS


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'instance';self.root.mkdir()
        self.store=Path(self.tmp.name)/'backups'
        self.env=patch.dict(os.environ,{'PINBALLCTL_BACKUP_DIR':str(self.store)})
        self.env.start();self.addCleanup(self.env.stop)
        self.write('rules/rules.json',[{'id':'original','name':'Test','triggers':[{'type':'custom','event':'HIT'}],'actions':[{'type':'emit_event','params':{'name':'REWARD'}}]}])
        self.write('scoring/scoring.json',{'settings':{'enabled':True},'scoreRules':[{'id':'score-original'}],'combos':[{'id':'combo-original'}]})
        self.write('media/media.json',{'settings':{'enabled':True,'autoplayByDisplay':{'main':False}},'displays':[{'id':'main'}],'assets':[],'scenes':[]})
        self.write('audio/audio.json',{'assets':[],'cues':[]})
        self.write('lighting/lighting.json',{'fixtures':{},'scenes':[]})
        self.write('settings/settings.json',{'name':'Project','AUTH_PASSWORD_HASH':'private','SECRET_KEY':'private','CURRENCY':'GBP'})
        (self.root/'settings/.session-secret').write_text('private')

    def write(self,relative,value):
        path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return path

    def restore(self,ident,components,clear=False):
        sequence=[{'id':ident,'components':components}]
        report=backup.preview(self.root,sequence,clear)
        return backup.restore(self.root,sequence,clear,report)

    def test_full_and_partial_scopes_comments_and_external_library(self):
        full=backup.create(self.root,list(COMPONENTS),'Baseline')
        partial=backup.create(self.root,['rules','lighting'],'Small update')
        self.assertEqual(partial['components'],['lighting','rules']);self.assertEqual(full['comment'],'Baseline')
        rows,errors=backup.list_backups(self.root);self.assertEqual(len(rows),2);self.assertEqual(errors,[])
        self.assertFalse(self.store.is_relative_to(self.root))
        with backup.validated_archive(backup.archive_path(self.root,full['id'])) as (archive,manifest):
            content=archive.read('payload/settings/settings/public.json').decode()
            self.assertNotIn('private',content);self.assertNotIn('AUTH',content)
            self.assertFalse(any('session-secret' in name for name in archive.namelist()))

    def test_rules_replacement_removes_extras_keeps_other_components(self):
        snap=backup.create(self.root,['rules'])
        extra=self.root/'rules/extra.json';extra.write_text('{}')
        self.write('rules/rules.json',[])
        media_before=(self.root/'media/media.json').read_bytes()
        result=self.restore(snap['id'],['rules'])
        self.assertTrue(result['recoveryId']);self.assertFalse(extra.exists())
        self.assertEqual(json.loads((self.root/'rules/rules.json').read_text())[0]['id'],'original')
        self.assertEqual((self.root/'media/media.json').read_bytes(),media_before)

    def test_restore_subset_of_full_backup(self):
        snap=backup.create(self.root,list(COMPONENTS))
        self.write('rules/rules.json',[]);self.write('audio/audio.json',{'assets':[],'cues':[],'changed':True})
        self.restore(snap['id'],['rules'])
        self.assertTrue(json.loads((self.root/'audio/audio.json').read_text())['changed'])

    def test_shared_scoring_and_combos_are_independent(self):
        snap=backup.create(self.root,['scoring','combos'])
        self.write('scoring/scoring.json',{'scoreRules':[{'id':'new-score'}],'combos':[{'id':'new-combo'}]})
        self.restore(snap['id'],['combos'])
        config=json.loads((self.root/'scoring/scoring.json').read_text())
        self.assertEqual(config['scoreRules'][0]['id'],'new-score');self.assertEqual(config['combos'][0]['id'],'combo-original')

    def test_shared_media_and_displays_are_independent(self):
        snap=backup.create(self.root,['media','displays'])
        self.write('media/media.json',{'settings':{'enabled':False,'autoplayByDisplay':{'other':True}},'displays':[{'id':'other'}],'assets':[],'scenes':[]})
        self.restore(snap['id'],['displays'])
        config=json.loads((self.root/'media/media.json').read_text())
        self.assertFalse(config['settings']['enabled']);self.assertEqual(config['displays'][0]['id'],'main')
        self.assertEqual(config['settings']['autoplayByDisplay'],{'main':False})

    def test_destructive_clear_preserves_protected_secrets_and_backups(self):
        snap=backup.create(self.root,['rules'])
        self.write('audio/assets/extra.json',{'asset':'unneeded'})
        self.restore(snap['id'],['rules'],True)
        self.assertFalse((self.root/'audio/assets/extra.json').exists())
        self.assertFalse((self.root/'audio/audio.json').exists())
        self.assertEqual((self.root/'settings/.session-secret').read_text(),'private')
        settings=json.loads((self.root/'settings/settings.json').read_text())
        self.assertEqual(settings['AUTH_PASSWORD_HASH'],'private');self.assertNotIn('name',settings)
        self.assertTrue(backup.archive_path(self.root,snap['id']).exists())

    def test_baseline_then_partial_applies_latest_component(self):
        baseline=backup.create(self.root,list(COMPONENTS))
        self.write('rules/rules.json',[]);latest=backup.create(self.root,['rules'])
        self.write('rules/rules.json',[{'id':'discard','actions':[]}])
        sequence=[{'id':baseline['id'],'components':list(COMPONENTS)},{'id':latest['id'],'components':['rules']}]
        report=backup.preview(self.root,sequence)
        backup.restore(self.root,sequence,False,report)
        self.assertEqual(json.loads((self.root/'rules/rules.json').read_text()),[])

    def test_sqlite_backup_is_consistent_and_restorable(self):
        path=self.root/'rules/runtime.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE state (value INTEGER)');db.execute('INSERT INTO state VALUES (42)');db.commit()
            snap=backup.create(self.root,['rules'])
        with closing(sqlite3.connect(path)) as db, db:db.execute('UPDATE state SET value=99')
        self.restore(snap['id'],['rules'])
        with closing(sqlite3.connect(path)) as db, db:self.assertEqual(db.execute('SELECT value FROM state').fetchone()[0],42)

    def test_upload_recovers_manifest_but_never_restores(self):
        snap=backup.create(self.root,['rules'],'Uploaded comment')
        self.write('rules/rules.json',[])
        with backup.archive_path(self.root,snap['id']).open('rb') as stream:uploaded=backup.upload(self.root,stream)
        self.assertEqual(uploaded['comment'],'Uploaded comment')
        self.assertEqual(json.loads((self.root/'rules/rules.json').read_text()),[])

    def rewrite_zip(self,ident,transform):
        path=backup.archive_path(self.root,ident);out=io.BytesIO()
        with zipfile.ZipFile(path) as source,zipfile.ZipFile(out,'w') as dest:
            data={n:source.read(n) for n in source.namelist()};transform(data)
            for name,content in data.items():dest.writestr(name,content)
        out.seek(0);return out

    def test_corruption_traversal_duplicates_and_legacy_are_rejected(self):
        snap=backup.create(self.root,['rules'])
        def corrupt(data):data['payload/rules/rules/rules.json']=b'corrupt'
        def escape(data):data['../escaped']=b'bad'
        for transform in (corrupt,escape):
            with self.assertRaises(backup.BackupError):backup.upload(self.root,self.rewrite_zip(snap['id'],transform))
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:archive.writestr('rules/rules.json','[]')
        data.seek(0)
        with self.assertRaises(backup.BackupError):backup.upload(self.root,data)
        self.assertFalse((Path(self.tmp.name)/'escaped').exists())

    def test_archive_symlinks_and_zip_bombs_are_rejected(self):
        for symlink in (True,False):
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                if symlink:
                    info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=0o120777 << 16;archive.writestr(info,'/etc/passwd')
                else:archive.writestr('huge',b'0'*(2*1024**2))
            data.seek(0)
            with self.assertRaises(backup.BackupError):backup.upload(self.root,data)

    def test_stale_preview_is_rejected_without_live_changes(self):
        snap=backup.create(self.root,['rules']);sequence=[{'id':snap['id'],'components':['rules']}]
        preview=backup.preview(self.root,sequence);self.write('rules/extra.json',{})
        with self.assertRaises(backup.BackupError):backup.restore(self.root,sequence,False,preview)
        self.assertTrue((self.root/'rules/extra.json').exists())

    def test_reference_breaking_selection_is_blocked(self):
        self.write('rules/rules.json',[{'actions':[{'type':'play_audio_cue','target':'missing'}]}])
        snap=backup.create(self.root,['rules'])
        with self.assertRaises(backup.BackupError):backup.preview(self.root,[{'id':snap['id'],'components':['rules']}])

    def test_restore_refuses_running_bridge_and_preserves_data(self):
        snap=backup.create(self.root,['rules']);sequence=[{'id':snap['id'],'components':['rules']}]
        preview=backup.preview(self.root,sequence);self.write('bridge/bridge_state.json',{'connected':True})
        with self.assertRaises(backup.BackupError):backup.restore(self.root,sequence,False,preview)

    def test_publication_failure_rolls_back(self):
        snap=backup.create(self.root,['rules']);self.write('rules/rules.json',[])
        sequence=[{'id':snap['id'],'components':['rules']}];preview=backup.preview(self.root,sequence)
        original=(self.root/'rules/rules.json').read_bytes()
        real=backup.write_json
        def fail_commit(path,data):
            if path.name=='journal.json' and data.get('state')=='committed':raise OSError('disk failure')
            return real(path,data)
        with patch.object(backup,'write_json',side_effect=fail_commit):
            with self.assertRaises(OSError):backup.restore(self.root,sequence,False,preview)
        self.assertEqual((self.root/'rules/rules.json').read_bytes(),original)

    def test_interrupted_journal_rolls_back_on_recovery(self):
        transaction=self.store/'transactions'/'interrupted';transaction.mkdir(parents=True)
        original=(self.root/'rules/rules.json').read_bytes();old=transaction/'old/rules/rules.json';old.parent.mkdir(parents=True);old.write_bytes(original)
        backup.write_json(transaction/'journal.json',{'state':'applying','instance':str(self.root.resolve()),'files':[{'path':'rules/rules.json','existed':True}]})
        self.write('rules/rules.json',[]);backup.recover(self.root)
        self.assertEqual((self.root/'rules/rules.json').read_bytes(),original)


class BackupApiTests(unittest.TestCase):
    write=BackupRestoreTests.write
    def setUp(self):
        BackupRestoreTests.setUp(self)
        from flask import Flask
        from pinballctl.app.modules.backups import api_bp
        from pinballctl.app.modules.backups import api as backup_api
        self.app=Flask(__name__,instance_path=str(self.root));self.app.secret_key='test'
        self.app.register_blueprint(api_bp,url_prefix='/api/backups')
        self.client=self.app.test_client()

    def wait_job(self,response):
        import time
        self.assertEqual(response.status_code,202,response.json)
        ident=response.json['jobId'];deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            status=self.client.get('/api/backups/jobs/'+ident).json['job']
            if status['state']!='running':
                self.assertEqual(status['state'],'done',status)
                return status['result']
            time.sleep(.02)
        self.fail('Backup job timed out')

    def test_create_list_view_download_and_delete(self):
        snapshot=self.wait_job(self.client.post('/api/backups/create',json={'components':['rules'],'comment':'API snapshot'}))
        ident=snapshot['id']
        rows=self.client.get('/api/backups/list').json['backups'];self.assertEqual(rows[0]['comment'],'API snapshot')
        self.assertEqual(self.client.get('/api/backups/view/'+ident).json['backup']['components'],['rules'])
        response=self.client.get('/api/backups/download/'+ident);self.assertEqual(response.data,backup.archive_path(self.root,ident).read_bytes());response.close()
        self.assertEqual(self.client.post('/api/backups/delete/'+ident,json={}).status_code,400)
        self.assertEqual(self.client.post('/api/backups/delete/'+ident,json={'confirmation':'DELETE'}).status_code,200)
        self.assertEqual(self.client.get('/api/backups/list').json['backups'],[])

    def test_preview_requires_confirmation_and_replaces_on_explicit_restore(self):
        snapshot=backup.create(self.root,['rules']);self.write('rules/extra.json',{})
        preview=self.wait_job(self.client.post('/api/backups/preview',json={'sequence':[{'id':snapshot['id'],'components':['rules']}],'removeOtherContent':False}))
        self.assertIn('rules/extra.json',preview['preview']['deletePaths'])
        self.assertEqual(self.client.post('/api/backups/restore',json={'token':preview['token'],'confirmation':'wrong'}).status_code,400)
        self.assertTrue((self.root/'rules/extra.json').exists())
        done=self.wait_job(self.client.post('/api/backups/restore',json={'token':preview['token'],'confirmation':'REPLACE'}))
        self.assertTrue(done['recoveryId']);self.assertFalse((self.root/'rules/extra.json').exists())

    def test_upload_adds_to_library_without_restore(self):
        snapshot=backup.create(self.root,['rules'],'upload test')
        content=backup.archive_path(self.root,snapshot['id']).read_bytes();self.write('rules/rules.json',[])
        uploaded=self.wait_job(self.client.post('/api/backups/upload',data={'file':(io.BytesIO(content),'snapshot.zip')}))
        self.assertEqual(uploaded['comment'],'upload test')
        self.assertEqual(json.loads((self.root/'rules/rules.json').read_text()),[])
        self.assertEqual(len(self.client.get('/api/backups/list').json['backups']),2)

    def test_tampered_tokens_and_paths_never_write(self):
        self.assertEqual(self.client.post('/api/backups/restore',json={'token':'tampered','confirmation':'REPLACE'}).status_code,400)
        self.assertEqual(self.client.get('/api/backups/download/not-an-id').status_code,400)
        self.assertEqual(self.client.post('/api/backups/pause-bridge',json={}).status_code,400)


class BackupBarrierTests(unittest.TestCase):
    def test_runtime_lease_blocks_restore_and_barrier_blocks_other_requests(self):
        from pinballctl.backup.guard import access
        from threading import Event,Thread
        with tempfile.TemporaryDirectory() as tmp:
            ready=Event();release=Event()
            def hold():
                with access(tmp,runtime=True):ready.set();release.wait(3)
            thread=Thread(target=hold);thread.start();self.assertTrue(ready.wait(2))
            try:
                with self.assertRaises(RuntimeError):
                    with access(tmp,runtime=True,exclusive=True,timeout=0):pass
            finally:release.set();thread.join()
            marker=Path(tmp)/'.project-locks/restore-pending';marker.write_text('{}')
            with self.assertRaises(RuntimeError):
                with access(tmp):pass


class BackupSecurityTests(unittest.TestCase):
    write=BackupRestoreTests.write
    rewrite_zip=BackupRestoreTests.rewrite_zip
    def setUp(self):BackupRestoreTests.setUp(self)

    def test_case_collisions_and_file_directory_collisions_are_rejected(self):
        snapshot=backup.create(self.root,['rules'])
        def collide(data):data['PAYLOAD/rules/rules/rules.json']=b'other'
        with self.assertRaises(backup.BackupError):backup.upload(self.root,self.rewrite_zip(snapshot['id'],collide))
        with backup.validated_archive(backup.archive_path(self.root,snapshot['id'])) as (_,manifest):
            manifest=copy.deepcopy(manifest)
        manifest['inventory'] += [{'component':'rules','path':'rules/folder','size':0,'sha256':'0'*64},{'component':'rules','path':'rules/folder/file','size':0,'sha256':'0'*64}]
        with self.assertRaises(backup.BackupError):backup.validate_manifest(manifest)

    def test_settings_secrets_are_rejected_during_upload(self):
        snapshot=backup.create(self.root,['settings'])
        def secret(data):
            content=json.dumps({'SECRET_KEY':'private'}).encode();data['payload/settings/settings/public.json']=content
            manifest=json.loads(data['manifest.json']);manifest['inventory'][0].update(size=len(content),sha256=backup.hashlib.sha256(content).hexdigest());data['manifest.json']=json.dumps(manifest).encode()
        with self.assertRaises(backup.BackupError):backup.upload(self.root,self.rewrite_zip(snapshot['id'],secret))

    def test_library_cannot_be_inside_instance(self):
        with patch.dict(os.environ,{'PINBALLCTL_BACKUP_DIR':str(self.root/'backups')}):
            with self.assertRaises(backup.BackupError):backup.create(self.root,['rules'])

    def test_host_godot_paths_stay_local(self):
        self.write('media/media.json',{'settings':{'godot':{'binary':'private-host-binary','port':17342,'debugVisible':False}},'displays':[]})
        snapshot=backup.create(self.root,['displays'])
        with backup.validated_archive(backup.archive_path(self.root,snapshot['id'])) as (archive,_):
            value=json.loads(archive.read('payload/displays/displays/config.json'))
            self.assertNotIn('binary',value['settings']['godot']);self.assertNotIn('port',value['settings']['godot'])
        self.write('media/media.json',{'settings':{'godot':{'binary':'current-host-binary','port':17400,'debugVisible':True}},'displays':[]})
        sequence=[{'id':snapshot['id'],'components':['displays']}];report=backup.preview(self.root,sequence);backup.restore(self.root,sequence,False,report)
        settings=json.loads((self.root/'media/media.json').read_text())['settings']['godot']
        self.assertEqual(settings['binary'],'current-host-binary');self.assertEqual(settings['port'],17400);self.assertFalse(settings['debugVisible'])

    def test_sqlite_uri_characters_are_literal_filenames(self):
        path=self.root/'rules/literal%3F?.db'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE value (number INTEGER)');db.execute('INSERT INTO value VALUES (73)')
        snapshot=backup.create(self.root,['rules'])
        path.unlink()
        sequence=[{'id':snapshot['id'],'components':['rules']}];report=backup.preview(self.root,sequence)
        backup.restore(self.root,sequence,False,report)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT number FROM value').fetchone()[0],73)

    def test_restore_invalidates_selected_process_caches(self):
        from pinballctl.backup.guard import access
        from pinballctl.audio import runtime as audio
        from pinballctl.media import runtime as media
        snapshot=backup.create(self.root,['audio'])
        key=str(self.root.resolve());config_key=str((self.root/'audio/audio.json').resolve())
        audio._CFG_CACHE[config_key]=('stale',{});audio._ENGINES[key]=object();media._RUNTIMES[key]=object()
        self.addCleanup(audio._CFG_CACHE.pop,config_key,None);self.addCleanup(audio._ENGINES.pop,key,None);self.addCleanup(media._RUNTIMES.pop,key,None)
        sequence=[{'id':snapshot['id'],'components':['audio']}];report=backup.preview(self.root,sequence);backup.restore(self.root,sequence,False,report)
        with access(self.root):
            self.assertNotIn(config_key,audio._CFG_CACHE);self.assertNotIn(key,audio._ENGINES)
            self.assertIn(key,media._RUNTIMES)

    def test_cache_generation_tracks_multiple_unobserved_restores(self):
        from pinballctl.backup.guard import access
        from pinballctl.audio import runtime as audio
        key=str(self.root.resolve());audio._ENGINES[key]=object();self.addCleanup(audio._ENGINES.pop,key,None)
        for component in ('audio','rules'):
            snapshot=backup.create(self.root,[component]);sequence=[{'id':snapshot['id'],'components':[component]}]
            report=backup.preview(self.root,sequence);backup.restore(self.root,sequence,False,report)
        with access(self.root):self.assertNotIn(key,audio._ENGINES)
