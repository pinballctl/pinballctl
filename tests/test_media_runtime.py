import tempfile
import unittest
from pathlib import Path

from pinballctl.media.runtime import (
    complete_scene,
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
            "defaultScenesByDisplay": {"display_1": "scene_main"},
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
                "screens": ["display_1"],
                "baseAssetId": "asset_main",
                "priority": 10,
                "blendMode": "PLAY_OVER",
                "loop": True,
                "mute": True,
                "overlays": [],
            },
            {
                "id": "scene_bonus",
                "name": "Bonus",
                "screens": ["display_1"],
                "baseAssetId": "asset_bonus",
                "priority": 200,
                "blendMode": "PAUSE_LOWER",
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
        self.assertEqual(len(resumed["layers"]), 1)

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

    def test_layers_include_fallback_and_pause_lower(self) -> None:
        cfg = _media_config()
        cfg["settings"]["autoplayByDisplay"] = {"display_1": True}
        save_media_config(self.instance_path, cfg)
        play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="interrupt")
        payload = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual([layer["scene"]["id"] for layer in payload["layers"]], ["scene_main", "scene_bonus"])
        self.assertEqual(payload["layers"][0]["state"], "paused")
        self.assertEqual(payload["layers"][1]["state"], "playing")

    def test_complete_scene_promotes_next_visible_layer(self) -> None:
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        res = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="interrupt")
        payload = runtime_display_payload(self.instance_path, "display_1")
        top = payload["layers"][-1]
        self.assertEqual(top["scene"]["id"], "scene_bonus")
        complete = complete_scene(self.instance_path, display_id="display_1", session_id=top["sessionId"])
        self.assertTrue(complete["ok"])
        payload = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual(payload["layers"][-1]["scene"]["id"], "scene_main")

    def test_queue_settings_limit_and_dedupe_queued_retriggers(self) -> None:
        cfg = _media_config()
        cfg["scenes"][1]["interruptPolicy"] = "QUEUE"
        cfg["scenes"][1]["duplicatePolicy"] = "ALLOW"
        cfg["scenes"][1]["queue"] = {"enabled": True, "maxLength": 1, "dedupe": True}
        save_media_config(self.instance_path, cfg)

        first = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(first["ok"])

        second = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(second["ok"])
        self.assertTrue(second["queued"])

        third = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(third["ok"])
        self.assertTrue(third["queued"])
        self.assertEqual(third["sceneId"], "scene_bonus")

    def test_queue_max_length_drops_when_full(self) -> None:
        cfg = _media_config()
        cfg["scenes"][1]["interruptPolicy"] = "QUEUE"
        cfg["scenes"][1]["duplicatePolicy"] = "ALLOW"
        cfg["scenes"][1]["queue"] = {"enabled": True, "maxLength": 1, "dedupe": False}
        save_media_config(self.instance_path, cfg)

        first = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(first["ok"])

        second = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(second["ok"])
        self.assertTrue(second["queued"])

        third = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(third["ok"])
        self.assertTrue(third["dropped"])

    def test_coalesce_duplicate_policy_merges_retriggers(self) -> None:
        cfg = _media_config()
        cfg["scenes"][1]["duplicatePolicy"] = "COALESCE"
        save_media_config(self.instance_path, cfg)

        first = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(first["ok"])

        second = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded")
        self.assertTrue(second["ok"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["sceneId"], "scene_bonus")


if __name__ == "__main__":
    unittest.main()
