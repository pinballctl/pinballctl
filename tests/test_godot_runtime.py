import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pinballctl.media.godot_runtime import (
    _godot_runtime_state_path,
    _write_json,
    launch_runtime,
    load_media_state,
    play_scene,
    renderer_enabled,
    run_media_maintenance,
    runtime_status,
    upload_dynamic_scene,
)


class _UploadStub:
    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self._payload = payload

    def save(self, path: Path) -> None:
        Path(path).write_bytes(self._payload)


class GodotRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.instance_path = Path(self.tmp.name)
        media_dir = self.instance_path / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "assets").mkdir(parents=True, exist_ok=True)
        (media_dir / "assets" / "main.mp4").write_bytes(b"video")
        (media_dir / "media.json").write_text(
            """
            {
              "settings": {
                "renderer": "godot",
                "godot": {
                  "binary": "/usr/local/bin/godot4",
                  "port": 18700,
                  "autoRestart": true
                }
              },
              "displays": [
                {
                  "id": "display_1",
                  "name": "Primary Display",
                  "width": 1920,
                  "height": 1080,
                  "x": 0,
                  "y": 0,
                  "role": "backbox",
                  "enabled": true,
                  "screenIndex": 1
                }
              ],
              "assets": [
                {
                  "id": "asset_main",
                  "filename": "main.mp4",
                  "kind": "video"
                }
              ],
              "scenes": [
                {
                  "id": "scene_main",
                  "screens": ["display_1"],
                  "baseAssetId": "asset_main",
                  "loop": true
                }
              ]
            }
            """.strip(),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_renderer_enabled_from_media_config(self) -> None:
        self.assertTrue(renderer_enabled(self.instance_path))

    @patch("pinballctl.media.godot_runtime.configure_display", return_value={"ok": True})
    @patch("pinballctl.media.godot_runtime._request_status", return_value={"ok": True, "status": {"health": "ok"}})
    @patch("pinballctl.media.godot_runtime.subprocess.Popen")
    def test_launch_runtime_persists_running_process(self, popen_mock, *_args) -> None:
        popen_mock.return_value.pid = 4412
        with patch("pinballctl.media.godot_runtime._pid_alive", side_effect=lambda pid: int(pid or 0) == 4412):
            result = launch_runtime(self.instance_path, scene_id="scene_main")
            self.assertTrue(result["ok"])
            state = runtime_status(self.instance_path)
            self.assertTrue(state["running"])
            self.assertEqual(state["pid"], 4412)

    @patch("pinballctl.media.godot_runtime.play_video", return_value={"ok": True})
    @patch("pinballctl.media.godot_runtime.set_scene", return_value={"ok": True})
    @patch("pinballctl.media.godot_runtime.launch_runtime", return_value={"ok": True, "pid": 5511, "status": {"display": {"displayId": "display_1"}}})
    def test_play_scene_routes_scene_and_asset_to_godot(self, _launch_mock, set_scene_mock, play_video_mock) -> None:
        result = play_scene(self.instance_path, "scene_main")
        self.assertTrue(result["ok"])
        set_scene_mock.assert_called_once()
        play_video_mock.assert_called_once_with(self.instance_path, "asset_main", loop=True)

    def test_upload_dynamic_scene_indexes_uploaded_file(self) -> None:
        result = upload_dynamic_scene(self.instance_path, _UploadStub("bonus_mode.tscn", b"[gd_scene]"), scene_key="custom_bonus")
        self.assertTrue(result["ok"])
        self.assertEqual(result["scene"]["key"], "custom_bonus")

    @patch("pinballctl.media.godot_runtime.restart_runtime", return_value={"ok": True})
    @patch("pinballctl.media.godot_runtime._pid_alive", return_value=False)
    def test_maintenance_restarts_dead_runtime(self, _alive_mock, restart_mock) -> None:
        _write_json(
            _godot_runtime_state_path(self.instance_path),
            {
                "process": {"pid": 9911, "startedAtMs": 1},
                "runtime": {"autoRestart": True, "state": "running", "health": "ok", "wsUrl": "ws://127.0.0.1:18700"},
            },
        )
        result = run_media_maintenance(self.instance_path)
        self.assertTrue(result["ok"])
        restart_mock.assert_called_once()

    def test_load_media_state_reports_godot_backend(self) -> None:
        state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(state["engine"]["backend"], "godot")
