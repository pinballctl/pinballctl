import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from pinballctl.backup import lifecycle


class BridgeRestoreTests(unittest.TestCase):
    def run_restore(self, running=True, failure=None, restart=True):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('pinballctl.bridge.state.commands_path',return_value=root/'bridge/commands.json'), \
                 patch('pinballctl.bridge.state.write_state') as state, \
                 patch('pinballctl.cli._bridge_running_via_lock',side_effect=[(running,123),(False,None),(False,None),(restart,456)] if running else [(False,None)]), \
                 patch.object(lifecycle,'bridge_options',return_value=('/dev/example',115200)), \
                 patch('pinballctl.cli._stop_bridge_process') as stop, \
                 patch('pinballctl.cli._start_bridge_background',return_value=456 if restart else None) as start, \
                 patch.object(lifecycle.service,'restore',return_value={'recoveryId':'recovery'},side_effect=failure) as restore:
                if failure or not restart:
                    with self.assertRaisesRegex(ValueError,'remains stopped' if failure else 'Restore completed; bridge restart failed'):
                        lifecycle.restore(root,[],False,{},lambda **kw:None)
                else:
                    result=lifecycle.restore(root,[],False,{},lambda **kw:None)
                    self.assertEqual(result['bridgeRestarted'],running)
                self.assertEqual(stop.call_count,int(running))
                self.assertEqual(start.call_count,int(running and not failure))
                if running and not failure:
                    self.assertEqual(start.call_args.args[:2],('/dev/example',115200))
                restore.assert_called_once()

    def test_running_bridge_restarts(self):self.run_restore()
    def test_stopped_bridge_stays_stopped(self):self.run_restore(running=False)
    def test_failed_restore_does_not_restart(self):self.run_restore(failure=ValueError('rollback required'))
    def test_restart_failure_reports_completed_restore(self):self.run_restore(restart=False)

    def test_isolated_instance_never_manages_bridge(self):
        with patch('pinballctl.bridge.state.commands_path',return_value=Path('/real/bridge/commands.json')),patch('pinballctl.cli._bridge_running_via_lock') as running,patch.object(lifecycle.service,'restore',return_value={}) as restore:
            lifecycle.restore('/isolated',[],False,{},lambda **kw:None)
            running.assert_not_called();restore.assert_called_once()

    def test_capture_only_explicit_settings(self):
        with patch.object(lifecycle.subprocess,'run') as run:
            run.return_value.stdout='/venv/bin/python /venv/bin/pinballctl bridge --port /dev/serial/by-id/esp --baud 230400'
            self.assertEqual(lifecycle.bridge_options(123),('/dev/serial/by-id/esp',230400))
            run.return_value.stdout='unexpected --port /dev/tty --baud 1'
            with self.assertRaises(ValueError):lifecycle.bridge_options(123)
            run.return_value.stdout='pinballctl bridge --port /dev/tty'
            with self.assertRaises(ValueError):lifecycle.bridge_options(123)
