import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pinballctl.runtime.events import get_bus, ingress
from pinballctl.runtime.game import store
from pinballctl.runtime.media import backglass_api, godot_runtime, runtime
from pinballctl.runtime.scoring.runtime import finalize_game


class BackglassRuntimeApiTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.instance = Path(directory)
        self.url, self.token = self.enterContext(backglass_api.serve(self.instance))
        self.enterContext(patch.object(backglass_api, "_ensure_local_workers"))

    def post(self, payload, *, scores=False, authenticated=True, path=None):
        if scores:
            path = backglass_api.SCORES_PATH
        url = self.url.removesuffix(backglass_api.EVENT_PATH) + path if path else self.url
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, data=json.dumps(payload).encode(), headers=headers)
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, json.load(response)

    def test_event_requires_token_and_uses_normal_validation(self):
        with patch.object(ingress, "_enqueue_bridge_event_fast") as enqueue:
            self.assertEqual(self.post({"name": "MODE_ENDED"}, authenticated=False)[0], 401)
            self.assertEqual(self.post({"name": "BACKGLASS_START_REQUESTED", "params": {"quest": 99}})[0], 400)
            self.assertEqual(self.post({"name": "MODE_ENDED", "params": {"_hardwareIngress": True}})[0], 400)
        enqueue.assert_not_called()

    def test_online_event_goes_to_bridge_once_and_waits_for_confirmation(self):
        payload = {"quest": 2, "quest_name": "Test Quest"}
        with (
            patch.object(ingress, "_enqueue_bridge_event_fast", return_value=(True, None)) as enqueue,
            patch.object(ingress, "_process_event_local") as fallback,
            patch.object(ingress, "append_event_log"),
        ):
            status, body = self.post({"name": "BACKGLASS_START_REQUESTED", "params": payload, "source": "fake-hardware"})
        self.assertEqual(status, 200)
        self.assertTrue(body["bridge"]["enqueued"])
        fallback.assert_not_called()
        enqueue.assert_called_once()
        command = enqueue.call_args.args[0]
        self.assertEqual(command["cmd"], "EVENT_FIRE")
        self.assertEqual(command["source"], "pi.api")
        self.assertEqual(command["params"], payload)

    def test_offline_event_reaches_the_host_bus_once(self):
        bus = get_bus()
        events = bus.subscribe()
        try:
            with patch.dict("os.environ", {"PINBALLCTL_HEADLESS": "1"}), patch.object(ingress, "append_event_log") as log:
                status, body = self.post({"name": "MODE_ENDED"})
            self.assertEqual(status, 200)
            self.assertFalse(body["bridge"]["enqueued"])
            event = events.get(timeout=2)
            self.assertEqual(event.name, "MODE_ENDED")
            self.assertEqual(event.id, body["event"]["id"])
            self.assertTrue(events.empty())
            log.assert_called_once()
            self.assertTrue(log.call_args.kwargs["meta"]["local_processed"])
        finally:
            bus.unsubscribe(events)

    def test_scene_completion_promotes_a_different_queued_cue(self):
        def request_scene(state, name):
            return state.play_display_scene(
                scene_id=name,
                display_id="display_1",
                launch_mode=runtime.LAUNCH_MODE_FULLSCREEN,
                runtime_url="",
                preview_viewport=None,
                stack_behavior=runtime.STACK_BEHAVIOR_REPLACE,
                interrupt_policy=runtime.INTERRUPT_QUEUE,
                queue_enabled=True,
            )

        with runtime._scene_session_change(self.instance) as state:
            session = request_scene(state, "bonus")
            self.assertTrue(request_scene(state, "game_over")["queued"])

        # The display supervisor can read stack state written by another process.
        supervisor = runtime._MediaRuntimeState(self.instance)
        payload = {"displayId": "display_1", "sessionId": session["id"]}
        path = backglass_api.COMPLETE_PATH
        with (
            patch.object(runtime, "_get_runtime_state", return_value=supervisor),
            patch.object(godot_runtime, "_apply_runtime_state", return_value={"ok": True}),
        ):
            self.assertEqual(self.post(payload, path=path, authenticated=False)[0], 401)
            self.assertEqual(self.post({"displayId": "display_1"}, path=path)[0], 400)
            self.assertEqual(self.post(payload, path=path), (200, {"ok": True}))
            self.assertEqual(self.post(payload, path=path)[0], 409)
            active = supervisor.snapshot()
            self.assertEqual([row["sceneId"] for row in active["sessions"]], ["game_over"])
            self.assertEqual(active["queue"], [])

    def test_leaderboard_reads_and_updates_pending_initials(self):
        ended_at = int(time.time() * 1000)
        game = {
            "gameId": "test-game", "startedAtMs": ended_at - 100, "endedAtMs": ended_at,
            "status": "GAME_ENDED", "reason": "All player turns complete",
            "players": [{"id": "1", "name": "Player 1"}, {"id": "2", "name": "Player 2"}],
        }
        with store.transaction(self.instance) as db:
            finalize_game(db, game, {"1": {"score": 500}, "2": {"score": 1000}})
            store.write(db, "game", game)

        status, body = self.post({"action": "state"}, scores=True)
        self.assertEqual(status, 200)
        self.assertEqual(body["leaderboard"]["prompt"]["playerId"], "1")
        status, body = self.post({"action": "submit", "gameId": "test-game", "playerId": "1", "initials": "ACE"}, scores=True)
        self.assertEqual(status, 200)
        self.assertEqual(body["leaderboard"]["prompt"]["playerId"], "2")
        status, body = self.post({"action": "skip", "gameId": "test-game", "playerId": "2"}, scores=True)
        self.assertEqual(status, 200)
        self.assertIsNone(body["leaderboard"]["prompt"])
        self.assertEqual(
            [(row["score"], row["initials"]) for row in body["leaderboard"]["boards"]["all-time"]],
            [(1000, "---"), (500, "ACE")],
        )
