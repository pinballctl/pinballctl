import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from pinballctl.app.modules.rules import api_bp
from pinballctl.app.modules.rules.wizards import engine, api
from pinballctl.rules.runtime import _rule_matches_event


NATIVE_NORMALIZE = api.rules_api._normalize_rules


class WizardEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.definitions, errors = engine.discover(self.tmp.name)
        self.assertEqual(errors, [])
        self.bumper = self.definitions['pinballctl.bumper-hit-reward']
        self.choices = {kind: [{'id': kind.upper() if kind in ('counter','flag') else kind+'-1', 'name': 'Test', 'eventBase': 'BUMPER', 'deviceClass': 'button'}]
                        for kind in ('input','switch','sound','lighting','media','flag','counter')}

    def answers(self, d):
        a = {}
        for step in d['steps']:
            for f in step['fields']:
                kind = f['type']
                a[f['id']] = f.get('default', (self.choices[kind][0]['id'] if kind in self.choices else 'TEST_EVENT'))
        return a

    def test_catalogue_has_every_candidate_and_reference(self):
        self.assertEqual(len(self.definitions), 167)
        self.assertEqual(sum(d['availability']=='available' for d in self.definitions.values()),26)
        for d in self.definitions.values():
            if d['availability']=='unavailable':
                self.assertTrue(d['prerequisites']); self.assertEqual(d['rules'],[])
                with self.assertRaises(engine.InvalidWizard):engine.generate(d,{},self.choices)

    def test_all_available_generate_valid_disabled_independent_rules(self):
        for d in self.definitions.values():
            if d['availability']!='available':continue
            with self.subTest(wizard=d['id']):
                generated,clean,_=engine.generate(d,self.answers(d),self.choices)
                self.assertTrue(generated)
                for rule in generated:
                    self.assertFalse(rule['enabled']);self.assertTrue(rule['actions']);self.assertIn('Wizard',rule['tags'])
                    for action in rule['actions']:
                        if action['type'] in ('set_counter','inc_counter'):
                            self.assertRegex(action['target'], r'^[A-Z0-9_]{1,32}$')
                    self.assertNotIn('$',json.dumps(rule))

    def test_hidden_answers_are_erased_and_actions_omitted(self):
        raw=self.answers(self.bumper);raw.update(soundOn=False,lightOn=False,sound='deleted-sound',lighting='deleted-scene')
        rules,clean,_=engine.generate(self.bumper,raw,self.choices)
        self.assertNotIn('sound',clean);self.assertNotIn('lighting',clean)
        self.assertEqual([a['type'] for a in rules[1]['actions']],['emit_event','set_counter'])
        raw.update(soundOn=True,lightOn=True,sound='sound-1',lighting='lighting-1')
        rules,clean,_=engine.generate(self.bumper,raw,self.choices)
        self.assertEqual([a['type'] for a in rules[1]['actions']],['emit_event','play_audio_cue','apply_lighting_scene','set_counter'])

    def test_bumper_executes_counter_reward_and_reset(self):
        from pinballctl.rules.evaluation import plan,snapshot
        rules,_,_=engine.generate(self.bumper,dict(self.answers(self.bumper),threshold=2),self.choices)
        for r in rules:r['enabled']=True
        params={'eventType':'PRESSED'}
        first=plan(self.tmp.name,rules,'BUMPER','input-1',params,_rule_matches_event)
        second=plan(self.tmp.name,rules,'BUMPER','input-1',params,_rule_matches_event)
        self.assertEqual(len(first),1);self.assertEqual(len(second),2)
        self.assertEqual(list(snapshot(self.tmp.name)['counters'].values()),[0])
        plan(self.tmp.name,rules,'BUMPER','input-1',params,_rule_matches_event)
        plan(self.tmp.name,rules,'GAME_STARTED',None,{},_rule_matches_event)
        self.assertEqual(list(snapshot(self.tmp.name)['counters'].values()),[0])

    def test_unique_namespaces_and_stable_preview(self):
        r,_,n=engine.generate(self.bumper,self.answers(self.bumper),self.choices)
        other,_,_=engine.generate(self.bumper,self.answers(self.bumper),self.choices)
        self.assertNotEqual(r[0]['actions'][0]['target'],other[0]['actions'][0]['target'])
        same,_,_=engine.generate(self.bumper,self.answers(self.bumper),self.choices,n)
        self.assertEqual(r,same)

    def test_types_references_limits_unknown_keys_fail_closed(self):
        for changes in ({'threshold':True},{'threshold':float('inf')},{'threshold':0},{'threshold':2.5}, {'input':'missing'}, {'unknown':'x'}):
            with self.subTest(changes=changes),self.assertRaises(engine.InvalidWizard):
                engine.generate(self.bumper,dict(self.answers(self.bumper),**changes),self.choices)
        for changes in ({'code':'eval(...)'},{'schemaVersion':2},{'icon':'../../bad'},{'illustration':'https://external'}):
            with self.assertRaises(engine.InvalidWizard):engine.validate(dict({k:v for k,v in self.bumper.items() if k!='origin'},**changes))

    def test_cycles_forward_references_and_unknown_predicates(self):
        for predicate in ({'op':'eq','field':'future','value':True},{'op':'exec','field':'input'}):
            d=copy.deepcopy(self.bumper);d.pop('origin');d['steps'][0]['when']=predicate
            with self.assertRaises(engine.InvalidWizard):engine.validate(d)

    def test_all_predicates_and_nested_omission(self):
        self.assertTrue(engine.predicate({'op':'all','items':[{'op':'gte','field':'n','value':2},{'op':'not','item':{'op':'eq','field':'n','value':3}}]}, {'n':2}))
        node=[{'$when':{'op':'eq','field':'yes','value':True},'nested':[{'x':1}]}]
        self.assertEqual(engine.render(node,{'yes':False},'0'*32),[])
        self.assertEqual(engine.render({'groups':node},{'yes':False},'0'*32),{'groups':[]})

    def test_safe_discovery_duplicate_symlink_bad_json(self):
        folder=Path(self.tmp.name)/'wizards/user';folder.mkdir(parents=True)
        original=dict(self.bumper);original.pop('origin')
        (folder/'duplicate.json').write_text(json.dumps(original))
        (folder/'bad.json').write_text('{')
        (folder/'link.json').symlink_to(folder/'duplicate.json')
        found,errors=engine.discover(self.tmp.name)
        self.assertNotIn(original['id'],found);self.assertEqual(len(errors),3)

    def test_definition_limits_and_safe_illustration(self):
        raw={k:v for k,v in self.bumper.items() if k!='origin'}
        engine.validate(raw)
        for change in ({'illustration': {'asset':'../../secret','alt':'x'}},
                       {'minimumAppVersion':'0.2.invalid'}, {'steps': raw['steps']*10}):
            with self.assertRaises(engine.InvalidWizard):engine.validate(dict(raw,**change))
        node={}
        for _ in range(22):node={'nested':node}
        with self.assertRaises(engine.InvalidWizard):engine.bounded(node)

    def test_generic_output_safety_and_unknown_action_parameters(self):
        raw=copy.deepcopy(self.bumper)
        for bad in ({'type':'pulse','target':'GPIO1','params':{'durationMs':10}},
                    {'type':'emit_event','params':{'name':'SAFE_EVENT','code':'x'}},
                    {'type':'set_counter','target':'bad-counter','params':{'value':1}}):
            definition=copy.deepcopy(raw);definition['rules'][0]['actions']=[bad]
            with self.assertRaises(engine.InvalidWizard):engine.generate(definition,self.answers(raw),self.choices)

    def test_native_editor_normalization_round_trip(self):
        from pinballctl.app.modules.rules import api as native
        app=Flask(__name__,instance_path=self.tmp.name)
        generated,_,_=engine.generate(self.bumper,self.answers(self.bumper),self.choices)
        with app.app_context(), patch.object(native,'_hardware_map_by_id',return_value={}), patch.object(native,'_load_mapping_rows',return_value={}):
            normalized=NATIVE_NORMALIZE(copy.deepcopy(generated))
            again=NATIVE_NORMALIZE(copy.deepcopy(normalized))
        self.assertEqual(normalized,again)
        self.assertEqual(len(again),3)
        self.assertTrue(all(r['triggerGroups']['groups'] for r in again))
        self.assertTrue(all(r['id'].startswith('wizard-') and not r['enabled'] for r in again))


class WizardApiTests(WizardEngineTests):
    def setUp(self):
        super().setUp()
        self.app=Flask(__name__,instance_path=self.tmp.name);self.app.secret_key='test'
        self.app.register_blueprint(api_bp,url_prefix='/api/rules')
        self.client=self.app.test_client()
        self.current=[]
        self.patches=[patch.object(api.rules_api,'read_bridge_state',return_value={}),patch.object(api,'choices',return_value=self.choices),
                      patch.object(api.rules_api,'_normalize_rules',side_effect=lambda r:r),
                      patch.object(api.rules_api,'_validate_rules_before_save',return_value=[]),
                      patch.object(api.rules_api,'_load_rules_list',side_effect=lambda:copy.deepcopy(self.current))]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def preview(self):
        r=self.client.post('/api/rules/wizards/preview',json={'id':self.bumper['id'],'answers':self.answers(self.bumper)})
        self.assertEqual(r.status_code,200,r.json)
        return r.json

    def test_preview_no_write_create_then_replay_rejected(self):
        preview=self.preview()
        with patch.object(api,'save_atomically',side_effect=lambda r:self.current.extend(r)) as save:
            response=self.client.post('/api/rules/wizards/create',json={'token':preview['token']})
            self.assertEqual(response.status_code,200,response.json);self.assertEqual(len(self.current),3)
            self.assertEqual(self.client.post('/api/rules/wizards/create',json={'token':preview['token']}).status_code,409)
            self.assertEqual(save.call_count,1)

    def test_stale_revision_or_tampered_token_cannot_write(self):
        preview=self.preview();self.current=[{'id':'new'}]
        with patch.object(api,'save_atomically') as save:
            self.assertEqual(self.client.post('/api/rules/wizards/create',json={'token':preview['token']}).status_code,409)
            self.assertEqual(self.client.post('/api/rules/wizards/create',json={'token':preview['token']+'bad'}).status_code,409)
            save.assert_not_called()

    def test_import_export_and_no_override(self):
        exported=self.client.get('/api/rules/wizards/export/'+self.bumper['id']).json
        exported['id']='user.reward'
        self.assertEqual(self.client.post('/api/rules/wizards/import',json=exported).status_code,200)
        self.assertEqual(self.client.post('/api/rules/wizards/import',json=exported).status_code,400)
        self.assertEqual(self.client.get('/api/rules/wizards/export/user.reward').json,exported)

    def test_compile_failure_leaves_existing_rules(self):
        with self.app.app_context():
            path=api.rules_api._rules_path();path.write_text('[{"id":"original"}]')
            with patch.object(api.rules_api,'_build_rules_pd_from_path',side_effect=ValueError('compile failed')):
                with self.assertRaises(ValueError):api.save_atomically([{'id':'new'}])
            self.assertEqual(json.loads(path.read_text()),[{'id':'original'}])

    def test_connected_old_firmware_blocks_preview_and_create(self):
        token=self.preview()['token']
        with patch.object(api.rules_api,'read_bridge_state',return_value={'connected':True,'rules_runtime_version':1}), patch.object(api,'save_atomically') as save:
            response=self.client.post('/api/rules/wizards/preview',json={'id':self.bumper['id'],'answers':self.answers(self.bumper)})
            self.assertEqual(response.status_code,400)
            self.assertEqual(self.client.post('/api/rules/wizards/create',json={'token':token}).status_code,409)
            save.assert_not_called()

    def test_concurrent_create_is_once_only(self):
        from concurrent.futures import ThreadPoolExecutor
        token=self.preview()['token']
        def create(_):
            with self.app.test_client() as client:
                return client.post('/api/rules/wizards/create',json={'token':token}).status_code
        with patch.object(api,'save_atomically',side_effect=lambda r:self.current.extend(r)):
            with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(create,range(2)))
        self.assertEqual(sorted(statuses),[200,409]);self.assertEqual(len(self.current),3)

    def test_publication_failure_rolls_back_all_artifacts(self):
        with self.app.app_context():
            paths=[api.rules_api._rules_path(),api.rules_api._rules_pd_path(),api.rules_api._rules_meta_path()]
            for i,path in enumerate(paths):path.write_bytes(('original'+str(i)).encode())
            originals=[p.read_bytes() for p in paths]
            with patch.object(api.rules_api,'_build_rules_pd_from_path',return_value=b'new'),patch.object(api.rules_api,'_write_rules_meta',side_effect=OSError('disk error')):
                with self.assertRaises(OSError):api.save_atomically([{'id':'new'}])
            self.assertEqual([p.read_bytes() for p in paths],originals)


class WizardSelectorTests(unittest.TestCase):
    def setUp(self):
        WizardEngineTests.setUp(self)
        self.app=Flask(__name__,instance_path=self.tmp.name);self.app.secret_key='test'
        self.app.register_blueprint(api_bp,url_prefix='/api/rules')
        self.client=self.app.test_client()
        patcher=patch.object(api.rules_api,'read_bridge_state',return_value={});patcher.start();self.addCleanup(patcher.stop)

    def preview(self, wizard='pinballctl.counter-threshold-test', **answers):
        values={'event':'HIT','threshold':3,'notification':'REACHED'} if 'counter' in wizard else {'event':'HIT','value':True,'notification':'FLAG_MATCHED'}
        values.update(answers)
        response=self.client.post('/api/rules/wizards/preview',json={'id':wizard,'answers':values})
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def test_new_counter_is_default_and_preview_has_no_state_side_effects(self):
        from pinballctl.rules.evaluation import snapshot
        preview=self.preview();new=preview['stateCreations'][0]
        self.assertEqual(preview['answers']['counter'],engine.CREATE_NEW)
        self.assertEqual(new['type'],'counter');self.assertEqual(new['initialValue'],0)
        self.assertRegex(new['key'],r'^W[A-F0-9]{30}$')
        self.assertEqual(preview['rules'][0]['conditions'][0]['key'],new['key'])
        self.assertEqual(snapshot(self.tmp.name)['counters'],{})
        self.assertFalse((Path(self.tmp.name)/'rules/rules.json').exists())

    def test_creating_counter_and_flag_persists_defaults_and_friendly_names(self):
        from pinballctl.rules.evaluation import snapshot
        for wizard,kind in [('pinballctl.counter-threshold-test','counter'),('pinballctl.flag-monitor','flag')]:
            preview=self.preview(wizard);new=preview['stateCreations'][0]
            response=self.client.post('/api/rules/wizards/create',json={'token':preview['token']})
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(snapshot(self.tmp.name)[kind+'s'][new['key']],0 if kind=='counter' else False)
            with self.app.app_context():options=api.choices()
            option=next(x for x in options[kind] if x['id']==new['key'])
            self.assertEqual(option['name'],new['name']);self.assertNotEqual(option['name'],option['id'])

    def test_existing_counter_reused_without_reset(self):
        from pinballctl.rules.evaluation import state_transaction,snapshot
        with state_transaction(self.tmp.name) as state:state['counters']['HITS']=17
        preview=self.preview(counter='HITS')
        self.assertEqual(preview['stateCreations'],[])
        self.assertEqual(preview['rules'][0]['conditions'][0]['key'],'HITS')
        self.assertEqual(self.client.post('/api/rules/wizards/create',json={'token':preview['token']}).status_code,200)
        self.assertEqual(snapshot(self.tmp.name)['counters']['HITS'],17)

    def test_failed_publication_rolls_back_new_state_and_rules(self):
        from pinballctl.rules.evaluation import snapshot
        preview=self.preview()
        with self.app.app_context(),patch.object(api.rules_api,'_write_rules_meta',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                api.save_atomically(preview['rules'],initial_state=preview['stateCreations'])
        self.assertEqual(snapshot(self.tmp.name)['counters'],{})
        self.assertFalse((Path(self.tmp.name)/'rules/rules.json').exists())

    def test_names_are_unique_and_bindings_stable_for_preview(self):
        d=self.definitions['pinballctl.counter-threshold-test'];answers={'event':'HIT','threshold':3,'notification':'REACHED'}
        first,clean,namespace=engine.generate(d,answers,self.choices)
        repeated,_,_=engine.generate(d,clean,self.choices,namespace)
        self.assertEqual(first,repeated)
        new=engine.state_creations(d,clean,self.choices,namespace)[0]
        used=copy.deepcopy(self.choices);used['counter'].append({'id':'OTHER','name':new['name']})
        self.assertTrue(engine.state_creations(d,clean,used,'0'*32)[0]['name'].endswith('(2)'))

    def test_scene_names_normalized_from_real_catalogue_shapes(self):
        for folder,data in [('lighting',{'scenes':[{'id':'light_token','title':'Launch glow'}]}),('media',{'scenes':[{'id':'media_token','name':'Launch animation'}]})]:
            path=Path(self.tmp.name)/folder/(folder+'.json');path.parent.mkdir(parents=True);path.write_text(json.dumps(data))
        with self.app.app_context():options=api.choices()
        self.assertEqual(options['lighting'][0]['name'],'Launch glow')
        self.assertEqual(options['media'][0]['name'],'Launch animation')

    def test_hidden_state_field_is_not_created(self):
        d=copy.deepcopy(self.bumper)
        d['steps'][2]['fields'].append({'id':'optionalCounter','label':'Counter','type':'counter','when':{'op':'eq','field':'soundOn','value':True}})
        answers={'input':'input-1','threshold':2,'resetEvent':'GAME_STARTED','soundOn':False,'lightOn':False,'optionalCounter':engine.CREATE_NEW}
        _,clean,n=engine.generate(d,answers,self.choices)
        self.assertNotIn('optionalCounter',clean)
        self.assertEqual(engine.state_creations(d,clean,self.choices,n),[])
