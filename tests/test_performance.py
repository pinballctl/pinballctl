import unittest
from pinballctl.bridge.performance import EventDelivery


class DeliveryTests(unittest.TestCase):
    def test_window_requires_matching_confirmation_and_never_replays_timeouts(self):
        delivery = EventDelivery(window=1)
        event = dict(seq=1, name='test', source='host')
        delivery.track(event, 10)
        self.assertFalse(delivery.available())
        delivery.receive(dict(t='EVT', **dict(event, source='other')), 10.1)
        self.assertFalse(delivery.available())
        delivery.receive(dict(t='EVT', **event), 10.2)
        self.assertEqual(delivery.confirmed, 1)
        self.assertTrue(delivery.available())
        delivery.track(dict(event, seq=2), 11)
        delivery.expire(14)
        self.assertEqual(delivery.timed_out, 1)
        self.assertEqual(delivery.sent, 2)
        self.assertTrue(delivery.available())

    def test_rejections_are_not_confirmations(self):
        delivery = EventDelivery()
        event = dict(seq=1, name='test', source='host')
        delivery.track(event, 10)
        delivery.receive(dict(t='EVENT_DROP', **event), 10.1)
        self.assertEqual(delivery.dropped, 1)
        self.assertEqual(delivery.confirmed, 0)

    def test_history_uses_real_elapsed_time_and_is_bounded(self):
        delivery = EventDelivery()
        delivery.sample(1, 0, 0, 0, 0)
        delivery.sample(3, 100, 80, 20, 2)
        self.assertEqual(delivery.snapshot()['latest']['rx_rate'], 50)
        self.assertEqual(delivery.snapshot()['latest']['completed_rate'], 40)
        self.assertIsNone(delivery.snapshot()['latest']['latency_p95_ms'])
        for i in range(4, 400): delivery.sample(i, 100, 100, 0, 0)
        self.assertEqual(len(delivery.snapshot()['history']), 300)

    def test_partial_rpc_reply_is_retained_for_writable_selector(self):
        import ast
        import textwrap
        import json
        import selectors
        from pathlib import Path
        from unittest.mock import Mock
        from types import SimpleNamespace
        source = (Path(__file__).parents[1] / 'src/pinballctl/bridge/daemon.py').read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == '_rpc_send')
        sock = Mock()
        sock.send.return_value = 5
        namespace = dict(json=json, selectors=selectors, time=SimpleNamespace(time=lambda: 1),
                         rpc_clients={sock: {}}, sock_selector=Mock(), _rpc_close_client=Mock())
        exec(textwrap.dedent(ast.get_source_segment(source, node)), namespace)
        obj = {'ok': True, 'payload': 'x' * 10000}
        namespace['_rpc_send'](sock, obj)
        remaining = namespace['rpc_clients'][sock]['outgoing']
        expected = (json.dumps(obj, separators=(',', ':')) + '\n').encode()
        self.assertEqual(bytes(remaining), expected[5:])
        namespace['_rpc_close_client'].assert_not_called()
        namespace['sock_selector'].modify.assert_called_with(sock, selectors.EVENT_WRITE, data='rpc_write')

    def test_performance_api_marks_stale_data_and_errors(self):
        from flask import Flask
        from unittest.mock import patch
        from pinballctl.app.modules.performance.api import api_bp
        app = Flask(__name__)
        app.register_blueprint(api_bp, url_prefix='/api/performance')
        prefix = 'pinballctl.app.modules.performance.api.'
        with patch(prefix+'rpc_command', return_value={'latest': {'at': 1}, 'history': []}), patch(prefix+'read_state', return_value={}):
            response = app.test_client().get('/api/performance/status')
            self.assertTrue(response.json['stale'])
            self.assertFalse(response.json['connected'])
        with patch(prefix+'rpc_command', side_effect=RuntimeError('offline')):
            response = app.test_client().get('/api/performance/status')
            self.assertEqual(response.status_code, 503)


class OverloadTests(unittest.TestCase):
    def test_overload_latches_and_preserves_release_and_disable(self):
        delivery = EventDelivery()
        self.assertFalse(delivery.check_overload(1.05, 1))
        self.assertTrue(delivery.check_overload(1.11, 1))
        self.assertTrue(delivery.rejects({'cmd': 'EVENT_FIRE', 'eventType': 'PRESSED'}))
        self.assertFalse(delivery.rejects({'cmd': 'EVENT_FIRE', 'eventType': 'RELEASED'}))
        self.assertFalse(delivery.rejects({'cmd': 'EVENT_FIRE', 'params': {'eventType': 'RELEASED'}}))
        self.assertFalse(delivery.rejects({'cmd': 'DISABLE'}))
        self.assertTrue(delivery.rejects({'cmd': 'ENABLE'}))
        self.assertFalse(delivery.check_overload(20))
        self.assertEqual(delivery.overload_count, 1)
        self.assertFalse(delivery.reset_overload())
        delivery.disable_req_id = 'off-1'
        delivery.observe_coil_status({'armed': False, 'reqId': 'old-status'})
        self.assertFalse(delivery.reset_overload())
        delivery.observe_coil_status({'armed': False, 'reqId': 'off-1', 'recoverySupported': True})
        self.assertTrue(delivery.reset_overload())
        self.assertTrue(delivery.rejects({'cmd': 'EVENT_FIRE'}))  # handshake still required

    def test_confirmation_stall_faults_before_timeout_and_reset_waits_for_drain(self):
        delivery = EventDelivery()
        event = dict(seq=1, name='test', source='host')
        delivery.track(event, 10)
        self.assertTrue(delivery.check_overload(10.26))
        self.assertEqual(delivery.overload_reason, 'event_confirmation_delay')
        delivery.disabled_confirmed = True
        delivery.coil_status = {'recoverySupported': True}
        self.assertFalse(delivery.reset_overload())
        delivery.receive(dict(t='EVT', **event), 10.3)
        self.assertTrue(delivery.reset_overload())

    def test_latency_includes_queue_and_old_firmware_window_is_conservative(self):
        delivery = EventDelivery()
        event = dict(seq=1, name='test', source='host')
        delivery.track(event, 10, queued_at=9.9)
        delivery.receive(dict(t='EVT', **event), 10.05)
        delivery.sample(10.05, 1, 1, 0, 0)
        self.assertAlmostEqual(delivery.snapshot()['latest']['delivery_p95_ms'], 150)
        self.assertAlmostEqual(delivery.snapshot()['latest']['latency_p95_ms'], 50)
        self.assertEqual(EventDelivery.supported_window({}), 8)
        self.assertEqual(EventDelivery.supported_window({'eventWindow': '16'}), 8)
        self.assertEqual(EventDelivery.supported_window({'eventWindow': 10000}), 16)

    def test_rpc_activation_uses_the_shared_dispatch_queue(self):
        import ast
        import json
        import textwrap
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = (Path(__file__).parents[1] / 'src/pinballctl/bridge/daemon.py').read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == '_poll_socket_payloads')
        sock = Mock()
        sock.recv.return_value = b'{"cmd":"ENABLE","reqId":"test","match_t":"COIL_STATUS"}\n'
        selector = Mock()
        selector.select.return_value = [(SimpleNamespace(data='rpc_client', fileobj=sock), 1)]
        namespace = dict(json=json, time=SimpleNamespace(time=lambda: 1), recent_batches={},
                         rpc_clients={sock: {'deadline': 0}}, rpc_by_req={}, sock_selector=selector,
                         _register_pending=Mock(), _send_cmd=Mock())
        exec(textwrap.dedent(ast.get_source_segment(source, node)), namespace)
        result = namespace['_poll_socket_payloads']()
        self.assertEqual(result, [{'cmd': 'ENABLE', 'reqId': 'test', 'match_t': 'COIL_STATUS'}])
        namespace['_send_cmd'].assert_not_called()
        namespace['_register_pending'].assert_not_called()

    def test_legacy_metrics_queries_do_not_wait_for_nonexistent_event_echo(self):
        self.assertFalse(EventDelivery.tracks({'cmd': 'EVENT_FIRE', 'name': 'ACCEL_QUERY'}))
        self.assertFalse(EventDelivery.tracks({'cmd': 'EVENT_FIRE', 'name': 'ACCEL_STATUS_REQUEST'}))
        self.assertTrue(EventDelivery.tracks({'cmd': 'EVENT_FIRE', 'name': 'FLIPPER'}))
