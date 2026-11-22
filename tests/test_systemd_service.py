import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from flask import Flask

from pinballctl.runtime.ops import flash_lifecycle
from pinballctl.runtime.ops import service
from pinballctl.webapp.modules.esplink import api as esplink


class SystemdServiceTests(unittest.TestCase):
    def test_web_actions_target_only_the_web_service(self):
        with (
            patch.object(service, "_unit_exists", return_value=True),
            patch.object(service, "_systemctl") as systemctl,
            patch.object(service, "print_service_status"),
        ):
            for action in ("start", "reload", "stop"):
                service.service_action(action, "web")
        self.assertEqual(systemctl.call_args_list, [
            call("start", service.WEB_UNIT),
            call("reload", service.WEB_UNIT),
            call("stop", service.WEB_UNIT),
        ])

    def test_runtime_stop_also_handles_members_started_individually(self):
        with (
            patch.object(service, "_unit_exists", return_value=True),
            patch.object(service, "_systemctl") as systemctl,
            patch.object(service, "print_service_status"),
        ):
            service.service_action("stop", "runtime")
        systemctl.assert_called_once_with("stop", service.RUNTIME_TARGET, service.BRIDGE_UNIT, service.MEDIA_UNIT)

    def test_systemd_webapp_does_not_manage_bridge_processes(self):
        app = Flask(__name__)
        app.register_blueprint(esplink.api_bp)
        with (
            patch.dict("os.environ", {"PINBALLCTL_SYSTEMD": "1"}),
            patch.object(esplink, "unit_active", return_value=True),
            patch.object(esplink, "read_bridge_state", return_value={"port": "/dev/ttyACM0"}),
            patch.object(esplink, "_start_bridge") as start,
            patch.object(esplink, "_stop_bridge") as stop,
            patch.object(esplink, "_bridge_reconcile") as reconcile,
            app.test_client() as client,
        ):
            self.assertTrue(client.get("/bridge/status").json["running"])
            for action in ("start", "stop", "restart"):
                response = client.post(f"/bridge/{action}")
                self.assertEqual(response.status_code, 409)
                self.assertIn("pinballctl service", response.json["error"])
            start.assert_not_called()
            stop.assert_not_called()
            reconcile.assert_not_called()

    def test_firmware_maintenance_leaves_systemd_bridge_to_its_supervisor(self):
        with (
            patch.object(service, "unit_active", return_value=True),
            patch.object(flash_lifecycle, "claim_upload_lock") as claim_lock,
            patch.object(flash_lifecycle, "stop_bridge") as stop_bridge,
        ):
            with self.assertRaisesRegex(RuntimeError, "service stop bridge"):
                flash_lifecycle.flash_begin("/dev/ttyACM0")
            claim_lock.assert_not_called()
            stop_bridge.assert_not_called()

    def test_legacy_web_stop_requires_migration(self):
        with (
            patch.object(service, "_unit_exists", side_effect=lambda unit: unit == service.LEGACY_UNIT),
            patch.object(service, "_systemctl") as systemctl,
            patch.object(service, "print_service_status"),
        ):
            with self.assertRaisesRegex(SystemExit, "migrate"):
                service.service_action("stop", "web")
            service.service_action("stop", "all")
        systemctl.assert_called_once_with("stop", service.LEGACY_UNIT)

    def test_install_disables_legacy_before_starting_split_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for executable in ("pinballctl", "python"):
                (bin_dir / executable).touch()
            installed = {}

            def copy_unit(command):
                if command[:2] == ["sudo", "install"]:
                    installed[Path(command[-1]).name] = Path(command[-2]).read_text()

            with (
                patch.object(service.pwd, "getpwnam", return_value=SimpleNamespace(pw_dir=str(root))),
                patch.object(service.subprocess, "check_call", side_effect=copy_unit),
                patch.object(service, "_unit_exists", return_value=True),
                patch.object(service, "_systemctl") as systemctl,
                patch.object(service, "print_service_status"),
                patch("builtins.print"),
            ):
                service.service_install(workdir=directory, venv_bin=str(bin_dir))

        self.assertEqual(set(installed), set(service.STATUS_UNITS))
        self.assertIn("pinballctl.webapp:create_app()", installed[service.WEB_UNIT])
        self.assertIn("Wants=pinball-bridge.service pinball-media.service", installed[service.RUNTIME_TARGET])
        self.assertIn("PartOf=pinball-runtime.target", installed[service.BRIDGE_UNIT])
        self.assertIn("PartOf=pinball-runtime.target", installed[service.MEDIA_UNIT])
        self.assertNotIn("PartOf=", installed[service.WEB_UNIT])
        self.assertEqual(systemctl.call_args_list, [
            call("daemon-reload"),
            call("disable", "--now", service.LEGACY_UNIT),
            call("enable", service.RUNTIME_TARGET, service.WEB_UNIT),
            call("restart", service.RUNTIME_TARGET, service.WEB_UNIT),
        ])
