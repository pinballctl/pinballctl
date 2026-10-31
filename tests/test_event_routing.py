import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from pinballctl.events import routing
from pinballctl.ops.rules_blob import build_rules_pd_bytes
from pinballctl.scoring import runtime as scoring


class ScoringRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'rules').mkdir()
        self.rules = self.root / 'rules/rules.json'
        self.rules.write_text('[]')
        self.deploy()

    def deploy(self):
        blob = build_rules_pd_bytes(self.rules)
        (self.root / 'rules/rules.pd').write_bytes(blob)
        self.state = dict(connected=True, rules_status={'status':'ok','t':'RULES_APPLY'},
                          rules_at=1, manifest_at=2,
                          manifest={'data': {'rules.pd': {'sha256': hashlib.sha256(blob).hexdigest()}}})

    def needs_esp(self):
        with patch.object(routing, 'read_state', return_value=self.state):
            return routing.scoring_event_needs_esp(self.root, 'SCORE_CHANGED')

    def test_only_confirmed_unreferenced_notifications_stay_local(self):
        self.assertFalse(self.needs_esp())
        for key, value in [('connected',False), ('manifest_at',0), ('rules_status', {'status':'ok','t':'RULES_STATUS'})]:
            original=self.state[key];self.state[key]=value
            self.assertTrue(self.needs_esp());self.state[key]=original
        self.state['manifest']['data']['rules.pd']['sha256']='different'
        self.assertTrue(self.needs_esp())

    def test_new_and_old_deployed_listeners_both_preserve_forwarding(self):
        rule={'enabled':True,'triggers':[{'event':'SCORE_CHANGED'}],'actions':[]}
        self.rules.write_text(json.dumps([rule]))
        self.assertTrue(self.needs_esp())
        self.deploy()
        self.rules.write_text('[]')
        self.assertTrue(self.needs_esp())

    def test_missing_corrupt_or_wildcard_rules_keep_forwarding(self):
        for content in ['invalid', '{}', '[{"triggers":[{}]}]']:
            self.rules.write_text(content)
            self.assertTrue(self.needs_esp())
        self.rules.unlink()
        self.assertTrue(self.needs_esp())

    def test_compact_notification_preserves_trigger_but_keeps_full_local_data(self):
        params={'score':100,'lastAward':{'eventType':'PRESSED','pointsAwarded':25},'detailMs':12}
        command=routing.scoring_wire_event('SCORE_CHANGED',params)
        self.assertEqual(command,dict(cmd='EVENT_FIRE',name='SCORE_CHANGED',source='pi.scoring',eventType='PRESSED',detailMs=12))
        self.assertEqual(params['lastAward']['pointsAwarded'],25)
        for required in [False,True]:
            bus=Mock(); bus.emit.return_value=Mock(id='id',ts=1,name='SCORE_CHANGED',source='pi.scoring',params=params)
            with patch.object(routing,'scoring_event_needs_esp',return_value=required), patch.object(scoring,'get_bus',return_value=bus), patch.object(scoring,'get_event_manager'), patch.object(scoring,'_bridge_enqueue_ready',return_value=True), patch.object(scoring,'enqueue_command') as enqueue, patch.object(scoring,'append_event_log') as log, patch.object(scoring,'_BRIDGE_ENQUEUE_SKIP_UNTIL_MONO',0):
                scoring._emit_runtime_event(self.root,name='SCORE_CHANGED',params=params)
                bus.emit.assert_called_once_with(name='SCORE_CHANGED',source='pi.scoring',params=params)
                self.assertEqual(enqueue.call_count,int(required))
                if required:
                    enqueue.assert_called_once_with({**command, '_bridge_event_context': {
                        'local_dispatched': True, 'params': params}})
                self.assertEqual(log.call_args.kwargs['direction'],'pi->esp' if required else 'pi->pi')

    def test_elapsed_time_condition_keeps_notification_forwarding(self):
        self.rules.write_text(json.dumps([{'triggers':[{'event':'OTHER'}],
            'conditions':[{'type':'time_since_event','key':'SCORE_CHANGED','value':500}]}]))
        self.deploy()
        self.assertTrue(self.needs_esp())
