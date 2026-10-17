"""Exercise the daemon's transfer state machine without opening serial hardware."""
import hashlib
import tempfile
import ast
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class BlobTransferTests(unittest.TestCase):
    def driver(self, state, responses=None):
        source = (Path(__file__).parents[1] / 'src/pinballctl/bridge/daemon.py').read_text()
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
        from pinballctl.bridge import state
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
        from pinballctl.bridge import state
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(state, '_instance_dir', return_value=Path(directory)):
                state.write_state(blob_status={'state': 'queued', 'blobType': 'lighting', 'jobId': 'new'})
                state.write_state(blob_status={'state': 'done', 'blobType': 'rules', 'jobId': 'rules'})
                state.write_state(blob_status={'state': 'done', 'blobType': 'lighting', 'jobId': 'old'})
                statuses = state.read_state()['blob_status_by_type']
                self.assertEqual(statuses['lighting']['state'], 'queued')
                self.assertEqual(statuses['rules']['state'], 'done')
