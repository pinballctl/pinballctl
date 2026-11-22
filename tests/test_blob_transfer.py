"""Exercise the daemon's transfer state machine without opening serial hardware."""
import hashlib
import tempfile
import ast
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pinballctl.runtime.bridge.performance import EventDelivery


class BlobTransferTests(unittest.TestCase):
    def dispatch(self):
        source = (Path(__file__).parents[1] / 'src/pinballctl/runtime/bridge/daemon.py').read_text()
        tree = ast.parse(source)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Try) and
                    any(isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and
                        isinstance(s.value.func, ast.Name) and s.value.func.id == '_prune_pending' for s in n.body))
        code = compile(ast.Module(body=[node], type_ignores=[]), '<bridge dispatch>', 'exec')
        clock = SimpleNamespace(now=10)
        env = dict(
            deferred_payloads=[], blob_state=None, maintenance_request=None,
            event_ready_at=10, delivery=EventDelivery(),
            maintenance_replies={'COIL_CONFIG': 'COIL_STATUS', 'SET_ACCEL_CONFIG': 'ACCEL_CONFIG'},
            time=SimpleNamespace(monotonic=lambda: clock.now), pending={}, responses={},
            _prune_pending=Mock(), _log_err=Mock(), _complete_pending=Mock(),
            _disarm_for_overload=Mock(), _register_pending=Mock(),
            _bridge_req_id=lambda: 'maintenance', _prepare_cmd_for_send=lambda payload: payload,
            _send_cmd=Mock(), ser=object(), use_v2=True,
        )
        env['_start_blob_put'] = Mock(side_effect=lambda _: env.update(blob_state={'state': 'await_ready'}))

        def dispatch(now, *payloads):
            clock.now = now
            env['_poll_socket_payloads'] = lambda **_: list(payloads)
            exec(code, env)
            self.assertFalse([call for call in env['_log_err'].call_args_list
                              if call.args[0].startswith('cmd check failed')])

        return dispatch, env

    def test_sync_drains_confirmations_and_discards_activations_queued_during_transfer(self):
        dispatch, env = self.dispatch()
        delivery = env['delivery']
        press = dict(cmd='EVENT_FIRE', name='FLIPPER', source='button', eventType='PRESSED')
        first = dict(press, seq=1, _bridge_queued_at=10)
        released = dict(press, eventType='RELEASED', seq=3, _bridge_queued_at=10.02)
        job = dict(cmd='BLOB_PUT', blobType='hardware')
        dispatch(10.01, first, job, dict(press, seq=2, reqId='during-sync'), released)
        env['_start_blob_put'].assert_not_called()
        self.assertIn(delivery.key(first), delivery.pending)
        self.assertEqual(env['_complete_pending'].call_args.args[1]['error'], 'bridge_maintenance')

        delivery.receive(dict(first, t='EVT'), 10.05)
        dispatch(10.06)
        env['_start_blob_put'].assert_called_once_with(job)
        self.assertFalse(delivery.pending)
        dispatch(10.6, dict(press, seq=4, _bridge_queued_at=10.6))
        self.assertFalse(delivery.check_overload(10.6))
        self.assertEqual(len(env['deferred_payloads']), 1)

        env.update(blob_state=None, event_ready_at=10.7)
        dispatch(10.71, dict(press, seq=5, _bridge_queued_at=10.65),
                 dict(press, seq=6, _bridge_queued_at=10.71))
        self.assertEqual([call.args[1]['seq'] for call in env['_send_cmd'].call_args_list], [1, 3, 6])
        self.assertFalse(delivery.check_overload(10.72))
        self.assertEqual(delivery.overload_count, 0)

    def test_events_queued_during_startup_are_not_gameplay_overload(self):
        dispatch, env = self.dispatch()
        event = dict(cmd='EVENT_FIRE', name='FLIPPER', source='button')
        dispatch(10.02, dict(event, eventType='PRESSED', seq=1, _bridge_queued_at=9.6),
                 dict(event, eventType='RELEASED', seq=2, _bridge_queued_at=9.7))
        self.assertEqual([call.args[1]['seq'] for call in env['_send_cmd'].call_args_list], [2])
        self.assertEqual(env['delivery'].overload_count, 0)
        env['delivery'].receive(dict(event, seq=2, t='EVT'), 10.04)

        dispatch(10.2, dict(event, eventType='PRESSED', seq=3, _bridge_queued_at=10.05))
        self.assertEqual(env['delivery'].overload_reason, 'event_queue_delay')
        env['_disarm_for_overload'].assert_called_once()

    def test_hardware_config_commands_wait_for_pending_events_and_block_new_activations(self):
        for cmd, response in (('COIL_CONFIG', 'COIL_STATUS'), ('SET_ACCEL_CONFIG', 'ACCEL_CONFIG')):
            with self.subTest(cmd=cmd):
                dispatch, env = self.dispatch()
                delivery = env['delivery']
                event = dict(cmd='EVENT_FIRE', name='FLIPPER', source='button', seq=1)
                delivery.track(event, 10)
                dispatch(10.02, dict(cmd=cmd), dict(event, seq=2))
                env['_send_cmd'].assert_not_called()
                self.assertTrue(delivery.check_overload(10.26))
                self.assertEqual(delivery.overload_reason, 'event_confirmation_delay')
                delivery.receive(dict(event, t='EVT'), 10.28)
                dispatch(10.29)
                env['_register_pending'].assert_called_once_with('maintenance', response, cmd)
                env['_send_cmd'].assert_called_once()
                self.assertEqual(env['_send_cmd'].call_args.args[1]['cmd'], cmd)

    def driver(self, state, responses=None):
        source = (Path(__file__).parents[1] / 'src/pinballctl/runtime/bridge/daemon.py').read_text()
        node = next(n for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef) and n.name == '_drive_blob_transfer')
        function = textwrap.dedent(ast.get_source_segment(source, node))
        namespace = dict(time=SimpleNamespace(time=lambda: 100), responses=responses or {},
                         _log=Mock(), _log_err=Mock(), write_state=Mock(),
                         _send_raw_frame=Mock(), _send_cmd=Mock(),
                         _register_pending=Mock(), _emit_blob_progress=Mock(),
                         hashlib=hashlib, _bridge_req_id=lambda: "manifest", read_state=lambda: {},
                         ser=object(), use_v2=True, os=SimpleNamespace(environ={}))
        exec('def harness(blob_state):\n' + textwrap.indent(function, '    ') +
             '\n    return _drive_blob_transfer, lambda: blob_state\n', namespace)
        drive, current = namespace['harness'](state)
        return drive, current, namespace

    def test_ack_timeout_stops_without_sending_rest_and_identifies_lighting(self):
        drive, current, env = self.driver(dict(state='await_ack', state_at=90,
                                              blobType='lighting', sent=1024, acked=0))
        drive()
        self.assertIsNone(current())
        env['_send_raw_frame'].assert_not_called()
        status = env['write_state'].call_args.kwargs['blob_status']
        self.assertEqual(status['blobType'], 'lighting')
        self.assertEqual(status['error'], 'blob_ack_timeout')

    def test_ready_sends_only_one_ack_interval_before_waiting(self):
        state = dict(state='await_ready', state_at=100, blobType='lighting',
                     begin_req_id='upload', size=8192, blob_bytes=b'x' * 8192,
                     chunk_size=2048, use_v2_chunks=True)
        drive, current, env = self.driver(state, {'upload': {'payload': {'ok': True}}})
        drive()
        self.assertEqual(sum(len(c.args[1]) for c in env['_send_raw_frame'].call_args_list), 1024)
        self.assertEqual(current()['state'], 'await_ack')
        self.assertEqual(current()['ack_target'], 1024)

    def test_transfer_success_is_not_completion_until_apply_and_manifest(self):
        state = dict(state='await_result', state_at=100, blobType='lighting',
                     result_req_id='upload', sent=7, size=7, blob_bytes=b'payload',
                     remote_path='/cfg/lighting.pd')
        drive, current, env = self.driver(state, {'upload': {'payload': {'ok': True}}})
        drive()
        self.assertEqual(current()['state'], 'await_apply')
        env['write_state'].assert_not_called()
        drive()
        env['_send_cmd'].assert_not_called()
        state['apply_result'] = {'status': 'ok'}
        drive()
        self.assertEqual(current()['state'], 'await_manifest')
        self.assertEqual(state['sha256'], hashlib.sha256(b'payload').hexdigest())
        env['responses']['manifest'] = {'payload': {'ok': True}}
        drive()
        status = env['write_state'].call_args.kwargs['blob_status']
        self.assertEqual(status['state'], 'done')
        self.assertEqual(status['sha256'], hashlib.sha256(b'payload').hexdigest())
        self.assertIsNone(current())

    def test_apply_and_manifest_failures_never_report_success(self):
        for phase, extra in [('await_apply', {'apply_result': {'status': 'error', 'reason': 'bad_file'}}),
                             ('await_manifest', {'manifest_req_id': 'manifest'})]:
            with self.subTest(phase=phase):
                state = dict(state=phase, state_at=100, blobType='lighting', **extra)
                drive, current, env = self.driver(state, {'manifest': {'payload': {'ok': False}}})
                drive()
                self.assertEqual(env['write_state'].call_args.kwargs['blob_status']['state'], 'error')
                self.assertIsNone(current())

    def test_queue_snapshot_survives_source_recompile(self):
        from pinballctl.runtime.bridge import state
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'lighting.pd'
            source.write_bytes(b'original')
            with patch.object(state, '_bridge_dir', return_value=root), \
                    patch.object(state, 'write_state'), patch.object(state, 'enqueue_command') as enqueue:
                state.queue_blob_put('lighting', str(source), '/cfg/lighting.pd')
                source.write_bytes(b'new compilation')
                snapshot = Path(enqueue.call_args.args[0]['localPath'])
                self.assertEqual(snapshot.read_bytes(), b'original')
                state.remove_blob_snapshot(snapshot)
                self.assertFalse(snapshot.exists())

    def test_status_keeps_types_separate_and_ignores_superseded_jobs(self):
        from pinballctl.runtime.bridge import state
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(state, '_instance_dir', return_value=Path(directory)):
                state.write_state(blob_status={'state': 'queued', 'blobType': 'lighting', 'jobId': 'new'})
                state.write_state(blob_status={'state': 'done', 'blobType': 'rules', 'jobId': 'rules'})
                state.write_state(blob_status={'state': 'done', 'blobType': 'lighting', 'jobId': 'old'})
                statuses = state.read_state()['blob_status_by_type']
                self.assertEqual(statuses['lighting']['state'], 'queued')
                self.assertEqual(statuses['rules']['state'], 'done')
