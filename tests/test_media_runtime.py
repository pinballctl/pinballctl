import tempfile
import unittest
from pathlib import Path

from pinballctl.media.runtime import (
    load_media_state,
    play_scene,
    process_event,
    runtime_display_payload,
    save_media_config,
    stop_scene,
)


def _media_config() -> dict:
    return {
        "settings": {
            "enabled": True,
            "renderer": "chromium",
            "previewScale": 0.35,
            "windowScale": 0.25,
            "defaultDisplayRole": "backbox",
            "runtimePollMs": 150,
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
                "enabled": True,
                "screenIndex": 1,
            }
        ],
        "assets": [
            {
                "id": "asset_main",
                "displayName": "Main",
                "filename": "main.mp4",
                "kind": "video",
                "sizeBytes": 4,
                "durationMs": 0,
                "createdAt": "2026-03-18T00:00:00Z",
            },
            {
                "id": "asset_bonus",
                "displayName": "Bonus",
                "filename": "bonus.mp4",
                "kind": "video",
                "sizeBytes": 4,
                "durationMs": 0,
                "createdAt": "2026-03-18T00:00:00Z",
            },
        ],
        "scenes": [
            {
                "id": "scene_main",
                "name": "Main",
                "targetDisplay": "display_1",
                "baseAssetId": "asset_main",
                "loop": True,
                "mute": True,
                "overlays": [],
            },
            {
                "id": "scene_bonus",
                "name": "Bonus",
                "targetDisplay": "display_1",
                "baseAssetId": "asset_bonus",
                "loop": False,
                "mute": True,
                "overlays": [],
            },
        ],
    }


class MediaRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.instance_path = Path(self.tmp.name)
        save_media_config(self.instance_path, _media_config())
        assets_dir = self.instance_path / "media" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "main.mp4").write_bytes(b"main")
        (assets_dir / "bonus.mp4").write_bytes(b"bonus")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_interrupt_scene_resumes_previous_scene(self) -> None:
        first = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        self.assertTrue(first["ok"])

        second = play_scene(
            self.instance_path,
            "scene_bonus",
            launch_mode="embedded",
            stack_behavior="interrupt",
        )
        self.assertTrue(second["ok"])

        payload = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual(payload["scene"]["id"], "scene_bonus")

        stopped = stop_scene(self.instance_path, "scene_bonus")
        self.assertTrue(stopped["ok"])
        self.assertGreaterEqual(stopped["stopped"], 1)

        resumed = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual(resumed["scene"]["id"], "scene_main")

    def test_scoring_eval_updates_overlay_values(self) -> None:
        res = process_event(
            self.instance_path,
            name="SCORING_EVAL",
            source="pi.scoring",
            params={"score": 25},
        )
        self.assertTrue(res["ok"])

        state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(state["overlayValues"]["score"], "00000025")


if __name__ == "__main__":
    unittest.main()
