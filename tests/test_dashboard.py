import json
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from flask import Flask

from pinballctl.webapp.modules.dashboard import api as dashboard_api
from pinballctl.webapp.modules.service import api as service_api
from pinballctl.webapp.modules.service.store import log_path


class DashboardMachineTests(TestCase):
    def setUp(self):
        instance = self.enterContext(TemporaryDirectory())
        self.log = log_path(instance)
        app = Flask(__name__, instance_path=instance)
        app.register_blueprint(dashboard_api.api_bp, url_prefix="/api/dashboard")
        app.register_blueprint(service_api.api_bp, url_prefix="/api/service")
        self.client = app.test_client()
        self.enterContext(patch.object(dashboard_api, "get_dashboard_status", return_value={"bridge": {}}))

    def test_machine_summary_uses_saved_service_and_repair_entries(self):
        response = self.client.post("/api/service/log", json={
            "service_type": "SERVICE", "title": "Inspection",
            "engineer": "Test operator", "description": "Test description",
        })
        self.assertEqual(response.status_code, 200)
        service_entry = response.get_json()["entry"]
        self.log.write_text(json.dumps([
            service_entry,
            {"service_type": "REPAIR", "created_at": "2026-01-15T12:00:00+02:00"},
            {"service_type": "REPAIR", "created_at": "2026-01-15T11:30:00+00:00"},
            {"service_type": "WARRANTY", "created_at": "2026-01-16T12:00:00+00:00"},
            {"service_type": "REPAIR", "created_at": "invalid"},
        ]))

        status = self.client.get("/api/dashboard/status").get_json()
        self.assertEqual(status["machine"], {
            "lastServiceAt": service_entry["created_at"],
            "lastRepairAt": "2026-01-15T11:30:00+00:00",
            "logEntries": 5,
        })
        self.assertEqual(self.client.get("/api/service/log").get_json()["count"], 5)

    def test_missing_and_unreadable_service_history(self):
        self.assertEqual(self.client.get("/api/dashboard/status").get_json()["machine"], {
            "lastServiceAt": None, "lastRepairAt": None, "logEntries": 0,
        })
        self.assertFalse(self.log.parent.exists())
        self.log.parent.mkdir()
        self.log.write_text("invalid JSON")
        with self.assertLogs(level="ERROR"):
            response = self.client.get("/api/dashboard/status")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["machine"])
        self.assertEqual(response.get_json()["bridge"], {})
