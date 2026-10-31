"""Behavioural coverage for rules authored by the current editor."""
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from pinballctl.rules import runtime
from pinballctl.rules.evaluation import plan, state_transaction, host_only, condition_matches


def rule(event='HIT', actions=None, conditions=None):
    return {'enabled': True, 'triggers': [{'type': 'custom', 'event': event}],
            'conditions': conditions or [], 'actions': actions or []}


def counter(delta=1):
    return {'type': 'inc_counter', 'target': 'HITS', 'params': {'delta': delta}}


class RuleEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.instance = self.tmp.name

    def evaluate(self, rules, name='HIT', params=None, now=1000):
        return plan(self.instance, rules, name, 'switch', params or {}, runtime._rule_matches_event, now)

    def state(self):
        with state_transaction(self.instance) as state:
            return json.loads(json.dumps(state))

    def test_counter_threshold_and_multiple_actions(self):
        rules = [rule(actions=[counter()]), rule(actions=[{'type': 'play_audio_cue', 'target': 'reward'},
                  {'type': 'media_play_scene', 'target': 'video'}],
                  conditions=[{'type': 'counter', 'key': 'HITS', 'op': '>=', 'value': 3}])]
        for i in range(3):
            matched = self.evaluate(rules, now=1000+i)
            self.assertEqual(len(matched), 2 if i == 2 else 1)
        self.assertEqual(self.state()['counters']['HITS'], 3)
        self.assertEqual(len(matched[-1]['actions']), 2)

    def test_set_increment_negative_and_flag_false(self):
        rules = [rule(actions=[{'type': 'set_counter', 'target': 'HITS', 'params': {'value': 8}}, counter(-3),
                 {'type': 'set_flag', 'target': 'READY', 'params': {'value': False}}])]
        self.evaluate(rules)
        self.assertEqual(self.state()['counters']['HITS'], 5)
        self.assertIs(self.state()['flags']['READY'], False)

    def test_all_counter_comparisons(self):
        state = self.state(); state['counters']['HITS'] = 4
        for op, value, expected in [('==',4,True),('!=',4,False),('<',5,True),('<=',4,True),('>',3,True),('>=',4,True),('?',0,False)]:
            self.assertEqual(condition_matches({'type':'counter','key':'HITS','op':op,'value':value},state,1000), expected)

    def test_nested_all_any_and_unknown_fail_closed(self):
        r=rule(actions=[counter()]);r['conditionGroups']={'logic':'ALL','groups':[
            {'logic':'ANY','items':[{'type':'counter','key':'HITS','op':'==','value':0}, {'type':'unknown','key':'x'}]},
            {'logic':'ALL','items':[{'type':'flag','key':'BLOCKED','op':'==','value':False}]}]}
        self.assertEqual(len(self.evaluate([r])),1)
        self.assertEqual(self.evaluate([r]),[])
        self.assertEqual(self.evaluate([rule(actions=[counter()],conditions=[{'type':'mystery','key':'x'}])]),[])

    def test_empty_editor_condition_group_is_optional(self):
        r=rule(actions=[counter()]); r['conditionGroups']={'logic':'ALL','groups':[{'logic':'ALL','items':[]}]}
        self.assertEqual(len(self.evaluate([r])),1)

    def test_time_since_never_seen_and_previous_occurrence(self):
        r=rule(actions=[counter()],conditions=[{'type':'time_since_event','key':'HIT','op':'>=','value':100}])
        self.assertEqual(self.evaluate([r],now=1000),[])
        self.assertEqual(self.evaluate([r],now=1099),[])
        self.assertEqual(len(self.evaluate([r],now=1200)),1)

    def test_device_state_requires_observation(self):
        r=rule(actions=[counter()],conditions=[{'type':'device_state','key':'coil','op':'==','value':'INACTIVE'}])
        self.assertEqual(self.evaluate([r]),[])
        self.assertEqual(len(self.evaluate([r],params={'payload':{'observedDevices':{'coil':'INACTIVE'}}})),1)
        self.assertEqual(self.evaluate([r],params={'payload':{'observedDevices':{'coil':'ACTIVE'}}}),[])

    def test_trigger_all_window_consumes_inputs(self):
        r=rule(actions=[counter()]);r['triggerGroups']={'logic':'ALL','groups':[{'logic':'ALL','windowMs':100,'items':[{'event':'A'},{'event':'B'}]}]}
        self.assertEqual(self.evaluate([r],name='A',now=1000),[])
        self.assertEqual(self.evaluate([r],name='B',now=1101),[])
        self.assertEqual(len(self.evaluate([r],name='A',now=1102)),1)
        self.assertEqual(self.evaluate([r],name='B',now=1103),[])

    def test_disabled_rule_and_duplicate_sequence(self):
        r=rule(actions=[counter()]);r['enabled']=False
        self.assertEqual(self.evaluate([r]),[])
        r['enabled']=True
        for _ in range(2): self.evaluate([r],params={'seq':1,'payload':{'tsMs':800}})
        self.assertEqual(self.state()['counters']['HITS'],1)

    def test_concurrent_increments_are_not_lost(self):
        r=rule(actions=[counter()])
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _:self.evaluate([r]),range(40)))
        self.assertEqual(self.state()['counters']['HITS'],40)

    def test_hosted_hardware_only_after_conditions_pass(self):
        r=rule(actions=[{'type':'pulse','target':'board__GPIO__5','params':{'durationMs':10}}],
               conditions=[{'type':'flag','key':'READY','value':True}])
        enqueue=Mock(return_value=(True,None))
        with patch.object(runtime,'_load_rules',return_value=[r]):
            runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={},enqueue_bridge_event=enqueue,esp_rules_applied=True)
            enqueue.assert_not_called()
            with state_transaction(self.instance) as state: state['flags']['READY']=True
            runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={'payload':{'tsMs':100}},enqueue_bridge_event=enqueue,esp_rules_applied=True)
        self.assertEqual(enqueue.call_args.args[0]['cmd'],'RULE_ACTIONS')
        self.assertEqual(enqueue.call_args.args[0]['triggeredAtMs'],100)

    def test_native_unconditional_hardware_keeps_esp_ownership(self):
        r=rule(actions=[{'type':'pulse','target':'board__GPIO__5'}]);r['triggers'][0]['type']='hardware'
        self.assertFalse(host_only(r))
        with patch.object(runtime,'_load_rules',return_value=[r]):
            enqueue=Mock(return_value=(True,None))
            runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={},enqueue_bridge_event=enqueue,esp_rules_applied=True)
            enqueue.assert_not_called()

    def test_offline_custom_chain_and_loop_bound(self):
        rules=[rule('HIT',[{'type':'emit_event','target':'NEXT'}]),rule('NEXT',[counter(),{'type':'emit_event','target':'HIT'}])]
        with patch.object(runtime,'_load_rules',return_value=rules),patch.object(runtime,'get_bus') as bus,patch.object(runtime,'get_event_manager'),patch.object(runtime,'append_event_log'):
            bus.return_value.emit.return_value=Mock(id='x',ts=1,name='x',source='pi.rules',params={})
            runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={},enqueue_bridge_event=lambda _: (False,'offline'))
        self.assertEqual(self.state()['counters']['HITS'],8)

    def test_registry_action_and_condition_coverage(self):
        from pinballctl.rules.evaluation import SUPPORTED_ACTIONS
        registry=json.loads(Path('src/pinballctl/app/modules/rules/registry.json').read_text())
        self.assertEqual({k for k,v in registry['actions'].items() if not v.get('planned')}, SUPPORTED_ACTIONS)
        self.assertEqual(set(registry['conditions']), {'flag','counter','time_since_event','device_state'})

    def test_invalid_counter_cannot_partially_fire_hardware(self):
        for value in ['bad',2**40,True]:
            r=rule(actions=[{'type':'set_counter','target':'HITS','params':{'value':value}}, {'type':'pulse','target':'board__GPIO__5'}])
            self.assertEqual(self.evaluate([r]),[])
        self.assertNotIn('HITS',self.state()['counters'])

    def test_instances_do_not_share_state(self):
        self.evaluate([rule(actions=[counter()])])
        with tempfile.TemporaryDirectory() as other:
            with state_transaction(other) as state:
                self.assertEqual(state['counters'],{})

    def test_blank_ui_operator_uses_displayed_default(self):
        r=rule(actions=[counter()],conditions=[{'type':'counter','key':'HITS','op':'','value':0}])
        self.assertEqual(len(self.evaluate([r])),1)

    def test_runtime_state_endpoint_reports_counter_and_flag(self):
        from flask import Flask
        from pinballctl.app.modules.rules import api
        self.evaluate([rule(actions=[counter(),{'type':'set_flag','target':'READY','params':{'value':True}}])])
        app=Flask('rules-state-test',instance_path=self.instance);app.register_blueprint(api.api_bp)
        response=app.test_client().get('/runtime-state')
        self.assertTrue(response.json['ok'])
        self.assertEqual(response.json['counters']['HITS'],1)
        self.assertTrue(response.json['flags']['READY'])
        self.assertNotIn('seen',response.json)

    def test_conditions_gate_all_existing_external_action_families(self):
        from contextlib import ExitStack
        cases = [('apply_lighting_scene','play_scene'),('stop_lighting_scene','stop_scene'),
                 ('play_audio_cue','play_cue'),('stop_audio_cue','stop_cue'),
                 ('toggle_audio_cue','play_cue'),('media_play_scene','media_play_scene'),
                 ('media_stop_scene','media_stop_scene'),('media_stop_all','media_stop_scene')]
        for action_type, handler in cases:
            with self.subTest(action=action_type), ExitStack() as stack:
                r=rule(actions=[{'type':action_type,'target':'configured-asset'}],
                       conditions=[{'type':'flag','key':'QUALIFIED','value':True}])
                stack.enter_context(patch.object(runtime,'_load_rules',return_value=[r]))
                stack.enter_context(patch.object(runtime,'append_event_log'))
                stack.enter_context(patch.object(runtime,'load_audio_state',return_value={}))
                effect=stack.enter_context(patch.object(runtime,handler,return_value={'ok':True}))
                with state_transaction(self.instance) as state: state['flags']['QUALIFIED']=False
                runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={})
                effect.assert_not_called()
                with state_transaction(self.instance) as state: state['flags']['QUALIFIED']=True
                runtime.apply_rules_for_event(self.instance,name='HIT',source='switch',params={})
                effect.assert_called_once()

    def test_conditional_sync_refuses_old_firmware(self):
        from flask import Flask
        from pinballctl.app.modules.rules import api
        path=Path(self.instance)/'rules';path.mkdir(exist_ok=True)
        (path/'rules.json').write_text(json.dumps([rule(actions=[counter()])]))
        app=Flask('rules-sync-test',instance_path=self.instance);app.register_blueprint(api.api_bp)
        with patch.object(api,'read_bridge_state',return_value={'connected':True,'port':'test','rules_runtime_version':0}),patch.object(api,'queue_blob_put') as queue:
            response=app.test_client().post('/sync')
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json['error'],'firmware_update_required')
            queue.assert_not_called()
