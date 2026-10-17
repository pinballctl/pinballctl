import unittest
from unittest.mock import patch
from flask import Flask
from pinballctl.app.modules.events.api import fire_event


class FireOnceTests(unittest.TestCase):
    def test_online_waits_for_echo_offline_runs_fallback_once(self):
        app=Flask(__name__)
        for online in (True,False):
            with app.test_request_context('/fire',method='POST',json={'name':'TEST','source':'button','simulated':True,'params':{'eventType':'RELEASED'}}), patch('pinballctl.app.modules.events.api._validate_event',return_value=(True,None)), patch('pinballctl.app.modules.events.api._canonical_source',side_effect=lambda s:s), patch('pinballctl.app.modules.events.api._enqueue_bridge_event_fast',return_value=(online,None)) as enqueue, patch('pinballctl.app.modules.events.api._process_event_local',return_value=('id','ts',[])) as local, patch('pinballctl.app.modules.events.api.append_event_log') as log:
                response=fire_event()
                self.assertTrue(response.json['ok'])
                enqueue.assert_called_once()
                self.assertEqual(enqueue.call_args.args[0]['eventType'],'RELEASED')
                self.assertEqual(local.call_count,0 if online else 1)
                self.assertEqual(log.call_args.kwargs['meta']['local_processed'],not online)
