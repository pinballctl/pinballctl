import tempfile
import unittest
from pathlib import Path

from pinballctl.audio.runtime import play_cue, process_event as process_audio_event, save_audio_config
from pinballctl.media.runtime import play_scene, save_media_config
from pinballctl.events import get_bus


def _audio_config() -> dict:
    return {
        "settings": {
            "enabled": True,
            "masterVolume": 1.0,
            "defaultOutput": "default",
            "maxGlobalConcurrent": 24,
            "previewVolume": 0.9,
            "autoDetectOutputs": True,
            "filePolicy": {"allowExtensions": [".wav"], "maxUploadMb": 64},
        },
        "buses": {
            "music": {"enabled": True, "volume": 1.0, "maxConcurrent": 2},
            "sfx": {"enabled": True, "volume": 1.0, "maxConcurrent": 12},
            "voice": {"enabled": True, "volume": 1.0, "maxConcurrent": 4},
            "ambient": {"enabled": True, "volume": 0.85, "maxConcurrent": 4},
        },
        "ducking": [],
        "assets": [{"id": "asset_music", "displayName": "Music", "filename": "music.wav", "format": "wav", "sizeBytes": 4, "durationMs": 0, "sampleRate": 0, "channels": 0, "createdAt": "2026-03-18T00:00:00Z", "tags": []}],
        "cues": [{"id": "cue_music", "name": "Music", "enabled": True, "assetId": "asset_music", "bus": "music", "volume": 1.0, "loop": False, "repeatCount": 1, "cooldownMs": 0, "maxConcurrent": 1, "restartPolicy": "restart", "targetOutput": "default", "notes": ""}],
        "mappings": [],
    }


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
        "displays": [{"id": "display_1", "name": "Primary Display", "width": 1920, "height": 1080, "x": 0, "y": 0, "role": "backbox", "enabled": True, "screenIndex": 1}],
        "assets": [
            {"id": "asset_main", "displayName": "Main", "filename": "main.mp4", "kind": "video", "sizeBytes": 4, "durationMs": 0, "createdAt": "2026-03-18T00:00:00Z"},
            {"id": "asset_bonus", "displayName": "Bonus", "filename": "bonus.mp4", "kind": "video", "sizeBytes": 4, "durationMs": 0, "createdAt": "2026-03-18T00:00:00Z"},
        ],
        "scenes": [
            {"id": "scene_main", "name": "Main", "screens": ["display_1"], "baseAssetId": "asset_main", "priority": 10, "blendMode": "PLAY_OVER", "loop": True, "mute": True, "audioBehaviour": {"pause": [], "duck": [], "allow": ["music", "sfx", "voice", "ambient"], "resumeOnEnd": True}, "overlays": []},
            {"id": "scene_bonus", "name": "Bonus", "screens": ["display_1"], "baseAssetId": "asset_bonus", "priority": 200, "blendMode": "PAUSE_LOWER", "loop": False, "mute": True, "audioBehaviour": {"pause": ["music"], "duck": [], "allow": ["sfx", "voice", "ambient"], "resumeOnEnd": True}, "overlays": []},
        ],
    }


class AudioMediaIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.instance_path = Path(self.tmp.name)
        save_audio_config(self.instance_path, _audio_config())
        save_media_config(self.instance_path, _media_config())
        (self.instance_path / "audio" / "assets").mkdir(parents=True, exist_ok=True)
        (self.instance_path / "audio" / "assets" / "music.wav").write_bytes(b"RIFF")
        (self.instance_path / "media" / "assets").mkdir(parents=True, exist_ok=True)
        (self.instance_path / "media" / "assets" / "main.mp4").write_bytes(b"main")
        (self.instance_path / "media" / "assets" / "bonus.mp4").write_bytes(b"bonus")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_media_play_emits_audio_apply_event(self) -> None:
        q = get_bus().subscribe()
        try:
            play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="interrupt")
            seen = []
            for _ in range(6):
                env = q.get(timeout=1.0)
                seen.append(env.name)
                if env.name == "MEDIA_AUDIO_APPLY":
                    self.assertEqual(env.params.get("sceneId"), "scene_bonus")
                    self.assertEqual(env.params.get("displayId"), "display_1")
                    return
            self.fail(f"MEDIA_AUDIO_APPLY not seen, saw {seen}")
        finally:
            get_bus().unsubscribe(q)

    def test_audio_rejects_paused_bus_from_media_intent(self) -> None:
        res = process_audio_event(
            self.instance_path,
            name="MEDIA_AUDIO_APPLY",
            source="pi.media",
            params={
                "displayId": "display_1",
                "sceneId": "scene_bonus",
                "layerId": "layer_bonus",
                "audioBehaviour": {"pause": ["music"], "duck": [], "allow": ["sfx", "voice", "ambient"], "resumeOnEnd": True},
            },
        )
        self.assertTrue(res["ok"])

        play = play_cue(self.instance_path, "cue_music")
        self.assertFalse(play["ok"])
        self.assertEqual(play["error"], "bus_paused_by_media")


if __name__ == "__main__":
    unittest.main()
