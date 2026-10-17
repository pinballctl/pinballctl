import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from pinballctl.bridge.serial_connection import open_runtime_serial
from pinballctl.bridge.state import connection_live, probe_connection
from pinballctl.app.modules.esplink import api


class ConnectionTests(unittest.TestCase):
    def test_launcher_uses_environment_executable_without_path(self):
        from pinballctl.cli import _pinballctl_bin
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / 'pinballctl'
            executable.touch()
            executable.chmod(0o755)
            with patch('pinballctl.cli.sys.executable', str(Path(tmp) / 'python')), \
                    patch('pinballctl.cli.sys.argv', ['gunicorn']), \
                    patch('pinballctl.cli.shutil.which', return_value=None):
                self.assertEqual(_pinballctl_bin(), str(executable))

    def test_control_lines_are_deasserted_before_open(self):
        history=[]
        class Port:
            def __setattr__(self,key,value): history.append((key,value))
            def open(self): history.append(('open',None))
            def close(self): history.append(('close',None))
        with patch('pinballctl.bridge.serial_connection.serial.Serial',return_value=Port()) as constructor:
            open_runtime_serial('/dev/test',460800)
        self.assertIsNone(constructor.call_args.kwargs['port'])
        self.assertEqual(history,[('dtr',False),('rts',False),('port','/dev/test'),('open',None)])

    def test_metadata_updates_do_not_make_a_stale_connection_live(self):
        with patch('pinballctl.bridge.state.time.time',return_value=100):
            self.assertFalse(connection_live(dict(connected=True,updated_at='now',info_at=100,last_rx_at=1)))
            self.assertFalse(connection_live(dict(connected=False,last_rx_at=99)))
            self.assertTrue(connection_live(dict(connected=True,last_rx_at=99)))
            self.assertFalse(connection_live(dict(connected=True,last_rx_at=101)))

    def test_probe_requires_a_matching_echo_not_socket_presence(self):
        with patch('pinballctl.bridge.state.bridge_enqueue_ready',return_value=True), \
                patch('pinballctl.bridge.state.rpc_command') as rpc:
            rpc.return_value={'t':'INFO','ok':True}
            self.assertFalse(probe_connection())
            rpc.return_value={'t':'ECHO','ok':True}
            self.assertTrue(probe_connection())
            rpc.assert_called_with({'cmd':'ECHO'},'ECHO',timeout_s=2.0)

    def test_device_discovery_never_stops_a_running_bridge(self):
        with patch.object(api,'_is_upload_active',return_value=False), \
                patch.object(api,'_bridge_running_on',return_value=True), \
                patch.object(api,'read_bridge_state',return_value={'port':'/dev/test'}), \
                patch.object(api,'_stop_bridge') as stop, patch.object(api,'_start_bridge') as start, \
                patch.object(api,'_bridge_last_action_at',0), patch.object(api,'_bridge_reconcile_suspended_until',0):
            api._bridge_reconcile([])
            api._bridge_reconcile([{'id':'/dev/different'}])
            stop.assert_not_called(); start.assert_not_called()

    def test_parent_start_does_not_overwrite_child_connected_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            events=[]
            process=MagicMock(pid=42)
            def launch(*args,**kwargs): events.append('child'); return process
            with patch.object(api,'_bridge_pidfile',return_value=Path(tmp)/'bridge.pid'), \
                    patch.object(api,'_bridge_logfile',return_value=Path(tmp)/'bridge.log'), \
                    patch.object(api,'_bridge_running_on',return_value=False), \
                    patch.object(api,'read_bridge_state',return_value={}), \
                    patch.object(api,'write_bridge_state',side_effect=lambda **kw:events.append('state')), \
                    patch.object(api.subprocess,'Popen',side_effect=launch), patch.object(api,'_pinballctl_bin',return_value='pinballctl'):
                self.assertEqual(api._start_bridge('/dev/test'),42)
            self.assertEqual(events,['state','child'])
