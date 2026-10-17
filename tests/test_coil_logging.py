import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from pinballctl.bridge import daemon


class CoilLoggingTests(unittest.TestCase):
    def setUp(self):
        daemon._coil_log_signatures.clear()
        self.status = dict(t='COIL_STATUS', ok=True, armed=False, fault='none',
                           ready=True, generation=1, challenge=10, coils=[])

    def test_changes_are_visible_at_info_and_repeated_challenges_are_quiet(self):
        with patch.object(daemon, '_current_log_level', return_value='INFO'), patch.object(daemon, '_log') as log:
            daemon._log_in(self.status)
            daemon._log_in(dict(self.status, challenge=20, reqId='new'))
            self.assertEqual(log.call_count, 1)
            for change in [dict(armed=True), dict(fault='host_timeout',ok=False), dict(generation=2), dict(coils=[{'pin':6}])]:
                daemon._log_in(dict(self.status, **change))
            self.assertEqual(log.call_count, 5)

    def test_raw_log_deduplicates_without_hiding_other_frames(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(daemon, '_raw_log_path', Path(directory)/'raw.log'), patch.object(daemon, 'rotate_if_needed'), patch.object(daemon, 'prune_archives'):
            for msg in [self.status, dict(self.status, challenge=20), dict(self.status, fault='watchdog'), {'t':'ECHO'}]:
                daemon._raw_log_write('RX_JSON', json.dumps(msg))
            text=(Path(directory)/'raw.log').read_text()
            self.assertEqual(len(text.splitlines()), 3)
            self.assertIn('watchdog', text)
            self.assertIn('ECHO', text)

    def test_heartbeat_is_transmitted_but_not_logged_even_at_verbose(self):
        serial=Mock();serial.write.side_effect=lambda data:len(data)
        with patch.object(daemon, '_current_log_level', return_value='VERBOSE'), patch.object(daemon, '_log') as log:
            daemon._send_cmd(serial, {'cmd':'COIL_HEARTBEAT','challenge':1})
            daemon._send_cmd(serial, {'cmd':'COIL_STATUS'})
            self.assertEqual(serial.write.call_count, 2)
            log.assert_not_called()
            daemon._send_cmd(serial, {'cmd':'DISABLE'})
            log.assert_called_once()
