import tempfile
import unittest
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from pinballctl.media.runtime import (
    _media_state_path,
    attach_runtime_surface,
    complete_scene,
    detach_surface,
    heartbeat_runtime_surface,
    load_media_state,
    play_scene,
    process_event,
    run_media_maintenance,
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

    def test_scene_stack_behavior_preserves_authored_blend_mode(self) -> None:
        cfg = _media_config()
        cfg["scenes"][1]["blendMode"] = "PLAY_OVER"
        save_media_config(self.instance_path, cfg)
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="scene")
        payload = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual([layer["scene"]["id"] for layer in payload["layers"]], ["scene_main", "scene_bonus"])
        self.assertEqual(payload["layers"][0]["state"], "playing")
        self.assertEqual(payload["layers"][1]["state"], "playing")

    def test_equal_priority_later_scene_wins_tie_without_dropping_lower_layer(self) -> None:
        cfg = _media_config()
        cfg["scenes"][0]["priority"] = 100
        cfg["scenes"][1]["priority"] = 100
        save_media_config(self.instance_path, cfg)
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="interrupt")
        payload = runtime_display_payload(self.instance_path, "display_1")
        self.assertEqual([layer["scene"]["id"] for layer in payload["layers"]], ["scene_main", "scene_bonus"])
        self.assertEqual(payload["layers"][0]["state"], "paused")
        self.assertEqual(payload["layers"][1]["state"], "playing")

    def test_embedded_payload_follows_display_stack_not_attached_instance(self) -> None:
        first = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        first_instance_id = str(first.get("instanceId") or "")
        payload = runtime_display_payload(
            self.instance_path,
            "display_1",
            instance_id=first_instance_id,
            surface_id="surface_a",
            surface_type="embedded",
        )
        self.assertEqual(payload["scene"]["id"], "scene_main")

        play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="scene")
        payload = runtime_display_payload(
            self.instance_path,
            "display_1",
            instance_id=first_instance_id,
            surface_id="surface_a",
            surface_type="embedded",
        )
        self.assertEqual(payload["scene"]["id"], "scene_bonus")
        self.assertEqual([layer["scene"]["id"] for layer in payload["layers"]], ["scene_main", "scene_bonus"])

    def test_embedded_poll_keeps_paused_lower_stack_alive(self) -> None:
        first = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        first_instance_id = str(first.get("instanceId") or "")
        second = play_scene(self.instance_path, "scene_bonus", launch_mode="embedded", stack_behavior="interrupt")
        second_instance_id = str(second.get("instanceId") or "")

        initial = load_media_state(self.instance_path, persist=False)
        first_row = next(inst for inst in initial["instances"] if str(inst.get("instance_id") or "") == first_instance_id)
        base_hb = int(((first_row.get("surface") or {}).get("last_heartbeat_at") or 0))
        future_ms = base_hb + 6000

        with patch("pinballctl.media.runtime_isolated._now_ms", return_value=future_ms):
            payload = runtime_display_payload(
                self.instance_path,
                "display_1",
                instance_id=second_instance_id,
                surface_id="surface_a",
                surface_type="embedded",
            )
            state = load_media_state(self.instance_path, persist=False)

        self.assertEqual(payload["scene"]["id"], "scene_bonus")
        self.assertEqual([layer["scene"]["id"] for layer in payload["layers"]], ["scene_main", "scene_bonus"])
        refreshed_rows = {
            str(inst.get("instance_id") or ""): inst
            for inst in state["instances"]
            if str(inst.get("instance_id") or "") in {first_instance_id, second_instance_id}
        }
        self.assertEqual(set(refreshed_rows.keys()), {first_instance_id, second_instance_id})
        self.assertGreaterEqual(int(((refreshed_rows[first_instance_id].get("surface") or {}).get("last_heartbeat_at") or 0)), future_ms)
        self.assertGreaterEqual(int(((refreshed_rows[second_instance_id].get("surface") or {}).get("last_heartbeat_at") or 0)), future_ms)

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

    def test_windowed_surface_coexists_with_embedded_display_session(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=43210),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            embedded = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
            self.assertTrue(embedded["ok"])
            windowed = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            self.assertTrue(windowed["ok"])
            state = load_media_state(self.instance_path, persist=False)
            surfaces = state["surfaceSessions"]
            self.assertEqual(
                sorted((row["launchMode"], row["sceneId"]) for row in surfaces),
                [("embedded", "scene_main"), ("windowed", "scene_main")],
            )

    def test_play_scene_can_override_target_display(self) -> None:
        cfg = _media_config()
        cfg["displays"].append(
            {
                "id": "display_2",
                "name": "Secondary Display",
                "width": 1280,
                "height": 720,
                "x": 1920,
                "y": 0,
                "role": "topper",
                "enabled": True,
                "screenIndex": 2,
            }
        )
        cfg["scenes"][0]["screens"] = ["display_2"]
        save_media_config(self.instance_path, cfg)
        launched = play_scene(self.instance_path, "scene_main", launch_mode="embedded", display_id="display_1")
        self.assertTrue(launched["ok"])
        self.assertEqual(str(launched.get("displayId") or ""), "display_1")
        state = load_media_state(self.instance_path, persist=False)
        self.assertEqual([row["displayId"] for row in state["surfaceSessions"] if row["launchMode"] == "embedded"], ["display_1"])

    def test_windowed_runtime_url_uses_registered_instance_id(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=43212),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        self.assertTrue(launched["ok"])
        row = launched["results"][0]
        instance_id = str(row.get("instanceId") or "")
        runtime_url = str(row.get("runtimeUrl") or "")
        query = parse_qs(urlparse(runtime_url).query or "")
        self.assertEqual(str((query.get("instanceId") or [""])[0] or ""), instance_id)

    def test_duplicate_windowed_play_reuses_existing_window(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=43213) as launch_mock,
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            first = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            second = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            state = load_media_state(self.instance_path, persist=False)
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertTrue(bool(second.get("reused")))
        self.assertEqual(launch_mock.call_count, 1)
        windowed = [row for row in state["surfaceSessions"] if row.get("launchMode") == "windowed"]
        self.assertEqual(len(windowed), 1)

    def test_stopping_windowed_surface_does_not_clear_embedded_display_session(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=43211),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
            patch("pinballctl.media.runtime_isolated._is_managed_media_pid", return_value=True),
            patch("pinballctl.media.runtime_isolated._stop_pid", return_value=True),
        ):
            play_scene(self.instance_path, "scene_main", launch_mode="embedded")
            play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            state = load_media_state(self.instance_path, persist=False)
            windowed_row = next(row for row in state["surfaceSessions"] if row["launchMode"] == "windowed")
            stopped = stop_scene(self.instance_path, session_id=windowed_row["id"])
            self.assertTrue(stopped["ok"])
            state = load_media_state(self.instance_path, persist=False)
            self.assertEqual([row["launchMode"] for row in state["surfaceSessions"]], ["embedded"])
            self.assertEqual(runtime_display_payload(self.instance_path, "display_1")["scene"]["id"], "scene_main")

    def test_windowed_then_embedded_keeps_both_surfaces(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=53211),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            play_scene(self.instance_path, "scene_main", launch_mode="embedded")
            state = load_media_state(self.instance_path, persist=False)
            self.assertEqual(
                sorted((row["launchMode"], row["sceneId"]) for row in state["surfaceSessions"]),
                [("embedded", "scene_main"), ("windowed", "scene_main")],
            )

    def test_runtime_sessions_group_outputs_under_single_runtime_id(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=53212),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            embedded = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
            runtime_id = str(embedded.get("runtimeId") or "")
            self.assertTrue(runtime_id.startswith("RT-"))

            windowed = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            self.assertNotEqual(runtime_id, str(windowed.get("runtimeId") or ""))

            state = load_media_state(self.instance_path, persist=False)
            embedded_runtime = next(row for row in state["runtimeSessions"] if row["runtimeId"] == runtime_id)
            self.assertEqual(embedded_runtime["sceneId"], "scene_main")
            self.assertEqual(len(embedded_runtime["outputs"]), 1)
            self.assertEqual(embedded_runtime["outputs"][0]["type"], "embedded")

    def test_runtime_sessions_exclude_stopped_rows(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=53213),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
            patch("pinballctl.media.runtime_isolated._is_managed_media_pid", return_value=True),
            patch("pinballctl.media.runtime_isolated._stop_pid", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            stop_scene(self.instance_path, session_id=str(launched.get("runtimeId") or ""))
            state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(state["runtimeSessions"], [])

    def test_load_media_state_does_not_overwrite_runtime_store(self) -> None:
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        load_media_state(self.instance_path)
        payload = json.loads(_media_state_path(self.instance_path).read_text(encoding="utf-8"))
        self.assertIn("runtimeIsolated", payload)

    def test_load_media_state_reloads_persisted_runtime_store(self) -> None:
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        payload = json.loads(_media_state_path(self.instance_path).read_text(encoding="utf-8"))
        payload["runtimeIsolated"] = {
            "sessions": [],
            "instances": [],
            "displayStacks": {},
            "cooldowns": {},
            "queueDepths": {},
        }
        _media_state_path(self.instance_path).write_text(json.dumps(payload), encoding="utf-8")
        state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(state["runtimeSessions"], [])

    def test_runtime_display_payload_updates_surface_liveness(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=62002),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        instance_id = str(launched["results"][0].get("instanceId") or "")
        attach_runtime_surface(self.instance_path, instance_id=instance_id, surface_id="surface_a")
        before = load_media_state(self.instance_path, persist=False)
        row_before = next(inst for inst in before["instances"] if str(inst.get("instance_id") or "") == instance_id)
        last_before = int(((row_before.get("surface") or {}).get("last_heartbeat_at") or 0))
        runtime_display_payload(self.instance_path, "display_1", instance_id=instance_id, surface_id="surface_a", surface_type="windowed")
        state = load_media_state(self.instance_path, persist=False)
        row = next(inst for inst in state["instances"] if str(inst.get("instance_id") or "") == instance_id)
        self.assertTrue(bool((row.get("surface") or {}).get("attached")))
        self.assertGreaterEqual(int(((row.get("surface") or {}).get("last_heartbeat_at") or 0)), last_before)

    def test_windowed_first_poll_can_claim_surface_before_attach(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=62006),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        instance_id = str(launched["results"][0].get("instanceId") or "")
        runtime_display_payload(self.instance_path, "display_1", instance_id=instance_id, surface_id="surface_a", surface_type="windowed")
        state = load_media_state(self.instance_path, persist=False)
        row = next(inst for inst in state["instances"] if str(inst.get("instance_id") or "") == instance_id)
        self.assertTrue(bool((row.get("surface") or {}).get("attached")))
        self.assertEqual(str((row.get("surface") or {}).get("surface_id") or ""), "surface_a")
        self.assertGreater(int(((row.get("surface") or {}).get("last_heartbeat_at") or 0)), 0)

    def test_stopping_embedded_keeps_windowed_instance_visible(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=54001),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            play_scene(self.instance_path, "scene_main", launch_mode="embedded")
            stopped = stop_scene(self.instance_path, session_id=runtime_display_payload(self.instance_path, "display_1")["active"]["instanceId"])
            self.assertTrue(stopped["ok"])
            state = load_media_state(self.instance_path, persist=False)
            self.assertEqual([row["launchMode"] for row in state["surfaceSessions"]], ["windowed"])

    def test_closed_windowed_surface_is_removed_on_maintenance_timeout(self) -> None:
        with patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=60001):
            play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        with patch("pinballctl.media.runtime_isolated._now_ms", return_value=9_999_999_999_999):
            run_media_maintenance(self.instance_path)
            state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(state["surfaceSessions"], [])

    def test_closed_windowed_surface_persists_on_read_until_maintenance_runs(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=61001),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        with patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=False):
            state = load_media_state(self.instance_path, persist=False)
        self.assertEqual(len([row for row in state["surfaceSessions"] if row.get("launchMode") == "windowed"]), 1)
        with (
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=False),
            patch("pinballctl.media.runtime_isolated._now_ms", return_value=9_999_999_999_999),
        ):
            run_media_maintenance(self.instance_path)
            state = load_media_state(self.instance_path, persist=False)
        self.assertEqual([row for row in state["surfaceSessions"] if row.get("launchMode") == "windowed"], [])

    def test_stale_surface_heartbeat_does_not_revive_detached_window(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=62001),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
        row = launched["results"][0]
        instance_id = str(row.get("instanceId") or row.get("id") or "")
        attached = attach_runtime_surface(self.instance_path, instance_id=instance_id, surface_id="surface_a")
        self.assertTrue(attached["ok"])
        detached = detach_surface(self.instance_path, session_id=instance_id, surface_id="surface_a")
        self.assertTrue(detached["ok"])
        stale = heartbeat_runtime_surface(self.instance_path, instance_id=instance_id, surface_id="surface_a")
        self.assertFalse(stale["ok"])

    def test_windowed_surface_stale_without_heartbeat(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=62003),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            instance_id = str(launched["results"][0].get("instanceId") or "")
            attach_runtime_surface(self.instance_path, instance_id=instance_id, surface_id="surface_a")

        with patch("pinballctl.media.runtime_isolated._now_ms", return_value=9_999_999_999_999):
            run_media_maintenance(self.instance_path)
            state = load_media_state(self.instance_path, persist=False)

        windowed = [row for row in state["surfaceSessions"] if row.get("id") == instance_id]
        self.assertEqual(windowed, [])

    def test_windowed_live_pid_survives_without_surface_attach(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=62004),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
            patch("pinballctl.media.runtime_isolated._now_ms", return_value=9_999_999_999_999),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            run_media_maintenance(self.instance_path)
            state = load_media_state(self.instance_path, persist=False)
        instance_id = str(launched["results"][0].get("instanceId") or "")
        windowed = [row for row in state["surfaceSessions"] if row.get("id") == instance_id]
        self.assertEqual(len(windowed), 1)
        self.assertEqual(windowed[0]["launchMode"], "windowed")

    def test_windowed_payload_scene_id_remains_authoritative(self) -> None:
        with patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=False):
            payload = runtime_display_payload(self.instance_path, "display_1", scene_id="scene_main")
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["scene"]["id"], "scene_main")
            self.assertTrue(any(str(layer.get("scene", {}).get("id") or "") == "scene_main" for layer in payload["layers"]))

    def test_stop_clears_cooldown_for_immediate_replay(self) -> None:
        cfg = _media_config()
        cfg["scenes"][0]["cooldownMs"] = 10000
        save_media_config(self.instance_path, cfg)
        first = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        self.assertTrue(first["ok"])
        stopped = stop_scene(self.instance_path, scene_id="scene_main")
        self.assertTrue(stopped["ok"])
        replay = play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        self.assertTrue(replay["ok"])
        self.assertFalse(bool(replay.get("dropped")))

    def test_windowed_surface_detach_removes_runtime_row(self) -> None:
        with (
            patch("pinballctl.media.runtime_isolated._launch_browser_instance", return_value=70001),
            patch("pinballctl.media.runtime_isolated._is_pid_alive", return_value=True),
        ):
            launched = play_scene(self.instance_path, "scene_main", launch_mode="windowed")
            self.assertTrue(launched["ok"])
            row = launched["results"][0]
            detached = detach_surface(self.instance_path, session_id=str(row.get("surfaceId") or row.get("id") or ""))
            self.assertTrue(detached["ok"])
            state = load_media_state(self.instance_path, persist=False)
            self.assertEqual(len([r for r in state["surfaceSessions"] if r.get("launchMode") == "windowed"]), 0)

    def test_embedded_surface_stale_without_heartbeat(self) -> None:
        play_scene(self.instance_path, "scene_main", launch_mode="embedded")
        with patch("pinballctl.media.runtime_isolated._now_ms", return_value=9_999_999_999_999):
            run_media_maintenance(self.instance_path)
            state = load_media_state(self.instance_path, persist=False)
        embedded = [row for row in state["surfaceSessions"] if row.get("launchMode") == "embedded"]
        self.assertEqual(embedded, [])


if __name__ == "__main__":
    unittest.main()
