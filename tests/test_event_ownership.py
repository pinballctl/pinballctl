import unittest
from unittest.mock import patch, Mock
from pinballctl.bridge.performance import EventDelivery
from pinballctl.rules import runtime


class EventOwnershipTests(unittest.TestCase):
    def test_confirmation_retains_local_delivery_context_and_full_parameters(self):
        delivery=EventDelivery(); event=dict(seq=1,name='SCORE_CHANGED',source='pi.scoring')
        context={'local_dispatched':True,'params':{'score':123}}
        delivery.track(event,1,context=context)
        self.assertIsNone(delivery.receive(dict(t='EVT',**dict(event,seq=2)),1.01))
        self.assertEqual(delivery.receive(dict(t='EVT',**event),1.02),context)
        self.assertEqual(delivery.confirmed,1)

    def test_late_confirmation_keeps_context_but_storage_is_bounded(self):
        delivery=EventDelivery()
        for n in range(300):delivery.track(dict(seq=n,name='x'),n,context={'local_dispatched':True})
        delivery.expire(400)
        self.assertEqual(len(delivery.contexts),256)
        self.assertTrue(delivery.receive(dict(t='EVT',seq=299,name='x'),401)['local_dispatched'])

    def test_mixed_audio_and_pixel_rule_is_owned_by_host_once(self):
        actions=[{'type':'set_lighting_pixels','target':'board__GPIO__5','params':{'pixelIndexes':[0]}},
                 {'type':'play_audio_cue','target':'cue'}]
        rule={'triggers':[{'event':'HIT'}],'actions':actions}
        for firmware in (True,False):
            enqueue=Mock(return_value=(True,None))
            with patch.object(runtime,'_load_rules',return_value=[rule]), patch.object(runtime,'_build_lighting_fixture_config_map',return_value={}), patch.object(runtime,'play_cue',return_value={'ok':True}) as audio, patch.object(runtime,'append_event_log'):
                runtime.apply_rules_for_event('/tmp',name='HIT',source='switch',params={},enqueue_bridge_event=enqueue,esp_rules_applied=firmware)
                audio.assert_called_once()
                self.assertEqual(enqueue.call_count,1)

    def test_derived_event_marks_local_delivery_for_its_echo(self):
        bus=Mock();bus.emit.return_value=Mock(id='id',ts=1,name='DERIVED',source='pi.rules',params={'points':10})
        enqueue=Mock(return_value=(True,None))
        with patch.object(runtime,'get_bus',return_value=bus),patch.object(runtime,'get_event_manager'),patch.object(runtime,'append_event_log'):
            runtime._emit_derived_event('/tmp','DERIVED','pi.rules',{'points':10},origin='rules',logger=None,enqueue_bridge_event=enqueue)
        bus.emit.assert_called_once()
        self.assertEqual(enqueue.call_args.args[0]['_bridge_event_context'],{'local_dispatched':True,'params':{'points':10}})
