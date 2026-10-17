"""Regression coverage for the system review, using temporary instance data."""
import io
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash
from pinballctl.app import _auth_enabled, _get_user_pass_from_config
from pinballctl.app.auth import session_secret
from pinballctl.app.core import core_bp
from pinballctl.app.settings_store import load_settings, save_settings
from pinballctl.app.modules.settings.api import api_bp as settings_api
from pinballctl.bridge import state as bridge
from pinballctl.media import godot_daemon
from pinballctl.ops.service import UNIT_TEMPLATE, _render
from pinballctl.scoring import runtime as scoring


class AuthSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = Flask(__name__, instance_path=str(self.root))
        self.app.secret_key = 'test-only'
        self.app.config.update(AUTH_USER='admin', AUTH_PASSWORD='old', AUTH_ENABLED=True)
        self.app.register_blueprint(core_bp)
        self.app.register_blueprint(settings_api, url_prefix='/settings/api')
        self.client = self.app.test_client()
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_secret_is_private_stable_and_shared_by_concurrent_workers(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            keys = list(pool.map(lambda _: session_secret(self.root), range(16)))
        self.assertEqual(len(set(keys)), 1)
        self.assertEqual(len(keys[0]), 64)
        self.assertEqual((self.root / 'settings/.session-secret').stat().st_mode & 0o777, 0o600)
        self.assertEqual(session_secret(self.root, 'dev-not-secret-change-me'), keys[0])
        with patch.dict(os.environ, {'PINBALLCTL_SECRET': 'explicit-secret'}):
            self.assertEqual(session_secret(self.root, 'configured-secret'), 'explicit-secret')

    def test_environment_credentials_and_auth_toggle_take_precedence(self):
        save_settings(self.root, {'AUTH_PASSWORD_HASH': generate_password_hash('saved')})
        with patch.dict(os.environ, {'PINBALLCTL_USER': 'operator', 'PINBALLCTL_PASSWORD': 'environment', 'PINBALLCTL_AUTH': 'off'}):
            user, check = _get_user_pass_from_config(self.app)
            self.assertEqual(user, 'operator')
            self.assertTrue(check('environment'))
            self.assertFalse(check('old'))
            self.assertFalse(_auth_enabled(self.app))

    def test_saved_password_is_hashed_redacted_and_visible_to_other_worker(self):
        response = self.client.post('/settings/api/save', json={'AUTH_PASSWORD': 'changed'})
        self.assertEqual(response.status_code, 200)
        data = load_settings(self.root)
        self.assertTrue(check_password_hash(data['AUTH_PASSWORD_HASH'], 'changed'))
        self.assertNotIn('AUTH_PASSWORD', data)
        self.assertNotIn('AUTH_PASSWORD_HASH', response.get_json()['data'])
        self.assertNotIn('AUTH_PASSWORD_HASH', self.client.get('/settings/api/data').get_json())
        other = Flask('other', instance_path=str(self.root))
        other.config.update(AUTH_USER='admin', AUTH_PASSWORD='old')
        self.assertTrue(_get_user_pass_from_config(other)[1]('changed'))
        self.assertFalse(_get_user_pass_from_config(other)[1]('old'))

    def test_login_fallback_rejects_wrong_password_and_external_redirect(self):
        with patch('pinballctl.app.core.render_template', return_value='login'):
            response = self.client.post('/login', data={'username': 'admin', 'password': 'anything'})
        with self.client.session_transaction() as sess:
            self.assertNotIn('user', sess)
        for destination in ('https://example.com', '//example.com', '/\\example.com', 'http://['):
            response = self.client.post('/login', data={'username': 'admin', 'password': 'old', 'next': destination})
            self.assertEqual(response.headers['Location'], '/')
        response = self.client.post('/login', data={'username': 'admin', 'password': 'old', 'next': '/logs/'})
        self.assertEqual(response.headers['Location'], '/logs/')

    def test_import_cannot_follow_existing_symlink_outside_instance(self):
        with tempfile.TemporaryDirectory() as outside:
            self.root.joinpath('linked').symlink_to(outside, target_is_directory=True)
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as archive:
                archive.writestr('normal.txt', 'normal')
                archive.writestr('linked/escaped.txt', 'bad')
            data.seek(0)
            response = self.client.post('/settings/api/import', data={'file': (data, 'backup.zip')})
            self.assertEqual(response.status_code, 400)
            self.assertFalse(Path(outside, 'escaped.txt').exists())
            self.assertFalse((self.root / 'normal.txt').exists())

    def test_export_and_import_keep_installation_secret_local(self):
        secret = session_secret(self.root)
        (self.root / 'config.json').write_text('{}')
        response = self.client.get('/settings/api/export')
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn('config.json', archive.namelist())
            self.assertNotIn('settings/.session-secret', archive.namelist())
        response.close()
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('settings/.session-secret', 'injected')
        data.seek(0)
        self.assertEqual(self.client.post('/settings/api/import', data={'file': (data, 'backup.zip')}).status_code, 200)
        self.assertEqual(session_secret(self.root), secret)


class BridgeReliabilityTests(unittest.TestCase):
    def test_concurrent_state_updates_keep_independent_fields(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge, 'state_path', return_value=Path(tmp) / 'state.json'):
            with ThreadPoolExecutor(max_workers=8) as pool:
                tasks = [pool.submit(bridge.write_state, **{key: val}) for key, val in (
                    ('firmware', 'v1'), ('port', '/dev/example'), ('chip', 'esp32'), ('connected', True),
                    ('rules_status', {'ok': True}), ('lighting_status', {'ok': True}), ('echo_seq', 10), ('proto', 2))]
                for task in tasks:
                    task.result()
            data = bridge.read_state()
            for key in ('firmware', 'port', 'chip', 'connected', 'rules_status', 'lighting_status', 'echo_seq', 'proto'):
                self.assertIn(key, data)

    def test_command_send_failure_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'socket'
            path.touch()
            with patch.object(bridge, 'command_socket_path', return_value=path), patch.object(bridge.socket, 'socket') as factory:
                conn = factory.return_value.__enter__.return_value
                conn.sendall.side_effect = BrokenPipeError()
                with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                    bridge._enqueue_via_socket([{'cmd': 'EVT'}])
                self.assertEqual(conn.sendall.call_count, 1)

    def test_rpc_disconnect_after_send_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'socket'
            path.touch()
            with patch.object(bridge, 'rpc_socket_path', return_value=path), patch.object(bridge.socket, 'socket') as factory:
                conn = factory.return_value.__enter__.return_value
                conn.recv.side_effect = ConnectionResetError()
                with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                    bridge.rpc_command({'cmd': 'EVT'}, 'EVT_ACK')
                self.assertEqual(conn.sendall.call_count, 1)

    def test_score_guard_serializes_separate_process_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = '''import sys, json, time
from pathlib import Path
from pinballctl.scoring.runtime import _state_guard
p=Path(sys.argv[1]) / "counter.json"
for _ in range(15):
    with _state_guard(sys.argv[1]):
        n=json.loads(p.read_text()) if p.exists() else 0
        time.sleep(.001)
        p.write_text(json.dumps(n+1))
'''
            processes = [subprocess.Popen([sys.executable, '-B', '-c', script, tmp]) for _ in range(4)]
            for proc in processes:
                self.assertEqual(proc.wait(timeout=15), 0)
            self.assertEqual(json.loads(Path(tmp, 'counter.json').read_text()), 60)


class DaemonAndServiceTests(unittest.TestCase):
    def test_daemon_survives_dispatch_failure_then_answers_ping(self):
        for payload in ({'op': 'launch_runtime'}, {'op': 'ping'}):
            client, server = socket.socketpair()
            with client, server:
                client.sendall((json.dumps(payload) + '\n').encode())
                if payload['op'] == 'launch_runtime':
                    with patch.object(godot_daemon, '_dispatch', side_effect=ValueError('bad request')), self.assertLogs(godot_daemon.LOG, 'ERROR'):
                        godot_daemon._serve_connection(server, Path('/unused'))
                else:
                    godot_daemon._serve_connection(server, Path('/unused'))
                result = json.loads(client.recv(4096))
                self.assertEqual(result['ok'], payload['op'] == 'ping')

    def test_daemon_bounds_client_reads(self):
        conn = MagicMock()
        conn.recv.side_effect = TimeoutError('stalled')
        with self.assertLogs(godot_daemon.LOG, 'WARNING'):
            godot_daemon._serve_connection(conn, Path('/unused'))
        conn.settimeout.assert_called_once_with(5.0)
        conn.recv.side_effect = None
        conn.recv.return_value = b'x' * 10
        with patch.object(godot_daemon, 'MAX_REQUEST_BYTES', 5):
            with self.assertRaisesRegex(ValueError, 'request_too_large'):
                godot_daemon._read_request(conn)

    def test_systemd_start_arguments_are_accepted_by_cli(self):
        rendered = _render(UNIT_TEMPLATE, SERVICE_USER='pi', WORKDIR='/tmp/project', PATH_PREFIX='/tmp/venv/bin', PINBALLCTL_BIN='/tmp/venv/bin/pinballctl')
        start = next(line.removeprefix('ExecStart=') for line in rendered.splitlines() if line.startswith('ExecStart='))
        args = shlex.split(start)[1:]
        result = subprocess.run([sys.executable, '-B', '-c', 'from pinballctl.cli import main; main()', *args, '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage: pinballctl start', result.stdout)
        self.assertIn('Type=forking', rendered)
        self.assertIn('PIDFile=/run/pinball/gunicorn.pid', rendered)


class DownloadsAndWifiTests(unittest.TestCase):
    def test_failed_firmware_hash_keeps_existing_image(self):
        import hashlib
        from pinballctl.app.modules.esplink import api
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.bin'
            target = Path(tmp) / 'firmware.bin'
            source.write_bytes(b'new firmware')
            target.write_bytes(b'working firmware')
            with patch.object(api, '_resolve_same_origin_firmware_asset', return_value=source):
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    api._download_asset_to_file('http://localhost/image', target, '0' * 64)
                self.assertEqual(target.read_bytes(), b'working firmware')
                api._download_asset_to_file('http://localhost/image', target, hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(target.read_bytes(), b'new firmware')
                self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_wifi_save_does_not_claim_success(self):
        from pinballctl.app.modules.wifi import api
        app = Flask('wifi-test')
        app.register_blueprint(api.api_bp)
        with patch.object(api.subprocess, 'check_output') as command:
            response = app.test_client().post('/save', data={'ssid': 'test', 'psk': 'test'})
            self.assertEqual(response.status_code, 501)
            self.assertFalse(response.get_json()['ok'])
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
