"""Wi-Fi configuration contract; never changes the host network."""
import subprocess
import unittest
from unittest.mock import patch
from flask import Flask
from pinballctl.app.modules.wifi import api


class WifiConfigurationTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(api.api_bp)
        self.client = app.test_client()

    def test_mac_rejected_without_running_commands(self):
        with patch.object(api, '_os', return_value='darwin'), patch.object(api.subprocess, 'run') as run:
            self.assertEqual(self.client.post('/save').status_code, 501)
            run.assert_not_called()

    def test_linux_connects_and_updates_password_without_shell(self):
        with patch.object(api, '_os', return_value='linux'), patch.object(api.shutil, 'which', return_value='/usr/bin/nmcli'), patch.object(api, '_linux_iface', return_value='wlan0'), patch.object(api.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            for password in ['first-password', 'changed-password']:
                response = self.client.post('/save', data={'ssid': 'Cabinet Wi-Fi', 'psk': password})
                self.assertTrue(response.json['ok'])
                args, kwargs = run.call_args
                self.assertEqual(args[0][-2:], ['password', password])
                self.assertIn('Cabinet Wi-Fi', args[0])
                self.assertNotIn('shell', kwargs)
                self.assertNotIn(password, response.get_data(as_text=True))

    def test_invalid_inputs_never_run(self):
        with patch.object(api, '_os', return_value='linux'), patch.object(api.shutil, 'which', return_value='nmcli'), patch.object(api.subprocess, 'run') as run:
            for data in [{'ssid': ''}, {'ssid': 'x'*33}, {'ssid': 'x\ny'}, {'ssid': 'valid', 'psk': 'short'}, {'ssid': 'valid', 'psk': 'password\nextra'}]:
                self.assertEqual(self.client.post('/save', data=data).status_code, 400)
            run.assert_not_called()

    def test_missing_networkmanager(self):
        with patch.object(api, '_os', return_value='linux'), patch.object(api.shutil, 'which', return_value=None):
            self.assertEqual(self.client.post('/save').status_code, 503)

    def test_open_network_and_failures(self):
        with patch.object(api, '_os', return_value='linux'), patch.object(api.shutil, 'which', return_value='nmcli'), patch.object(api, '_linux_iface', return_value='wlan0'), patch.object(api.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            self.assertEqual(self.client.post('/save', data={'ssid': 'open'}).status_code, 200)
            self.assertNotIn('password', run.call_args.args[0])
            run.return_value = subprocess.CompletedProcess([], 10, stderr='secret-password')
            response = self.client.post('/save', data={'ssid': 'open'})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('secret-password', response.get_data(as_text=True))
            run.side_effect = subprocess.TimeoutExpired('nmcli', 25)
            self.assertEqual(self.client.post('/save', data={'ssid': 'open'}).status_code, 504)

    def test_networkmanager_status_preserves_ssid_colons(self):
        with patch.object(api, '_run', side_effect=['', '', 'no:Other\nyes:Cabinet: Wi-Fi']):
            self.assertEqual(api._linux_ssid('wlan0'), 'Cabinet: Wi-Fi')
