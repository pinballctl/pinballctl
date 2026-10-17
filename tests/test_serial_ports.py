import json
import subprocess
import unittest
from unittest.mock import patch

from pinballctl.serial_ports import comports


class SerialPortsTests(unittest.TestCase):
    def test_macos_preserves_metadata_without_calling_native_discovery(self):
        port = dict(device="/dev/cu.usbmodem1", description="ESP32", hwid="USB",
                    vid=0x303A, pid=0x1001, manufacturer="Espressif",
                    product="USB JTAG", serial_number="123")
        with patch("pinballctl.serial_ports.sys.platform", "darwin"), \
             patch("pinballctl.serial_ports.subprocess.run") as run, \
             patch("serial.tools.list_ports.comports") as native:
            run.return_value.stdout = json.dumps([port])
            self.assertEqual(vars(comports()[0]), port)
            native.assert_not_called()
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            self.assertTrue(run.call_args.kwargs["check"])

    def test_linux_uses_native_discovery(self):
        with patch("pinballctl.serial_ports.sys.platform", "linux"), \
             patch("serial.tools.list_ports.comports", return_value=["port"]) as native, \
             patch("pinballctl.serial_ports.subprocess.run") as run:
            self.assertEqual(comports(), ["port"])
            native.assert_called_once_with()
            run.assert_not_called()

    def test_failed_scan_is_not_reported_as_no_devices(self):
        for error in (subprocess.TimeoutExpired("python", 5),
                      subprocess.CalledProcessError(1, "python")):
            with self.subTest(error=error), \
                 patch("pinballctl.serial_ports.sys.platform", "darwin"), \
                 patch("pinballctl.serial_ports.subprocess.run", side_effect=error):
                with self.assertRaises(type(error)):
                    comports()


if __name__ == "__main__":
    unittest.main()
