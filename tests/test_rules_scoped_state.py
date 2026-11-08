import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from pinballctl.game import runtime as game
from pinballctl.rules import play_clock, scoped_state
from pinballctl.rules.evaluation import plan, snapshot, state_transaction
from pinballctl.rules.runtime import _rule_matches_event, dispatch_timer_expirations


def rule(event, *actions, trigger_type="custom", params=None):
    return {"triggers": [{"event": event, "type": trigger_type, "params": params or {}}],
            "actions": list(actions)}


def action(kind, target, **params):
    return {"type": kind, "target": target, "params": params}


class ScopedRulesTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.clock = 100_000
        self.monotonic = 50_000
        self.addCleanup(patch.stopall)
        patch.object(game, "now_ms", side_effect=lambda: self.clock).start()
        patch.object(play_clock, "now_ms", side_effect=lambda: self.monotonic).start()
        game.configure(self.root, "game", {"ballsPerPlayer": 2, "freePlay": True})
        game.configure(self.root, "ball", {"inventory": 2, "sensors": [
            {"source": "launch", "role": "launch", "debounceMs": 0},
            {"source": "drain", "role": "drain", "debounceMs": 0},
        ]})

    def configure(self, kind, key, scope, **extra):
        config = scoped_state.definition(kind, key, {"scope": scope, **extra})
        with state_transaction(self.root) as state:
            scoped_state.set_definition(state, kind, key, config)

    def advance(self, milliseconds, wall=None):
        self.monotonic += milliseconds
        self.clock += milliseconds if wall is None else wall

    def command(self, name, authority="operator", **params):
        result = game.execute(self.root, name, params, uuid4().hex, authority=authority)
        self.assertTrue(result["ok"], result)

    def sensor(self, name):
        self.command("OBSERVE", authority="hardware", sensor=name, active=True)
        self.command("OBSERVE", authority="hardware", sensor=name, active=False)

    def send(self, name, rules, **params):
        return plan(self.root, rules, name, None, params, _rule_matches_event, self.clock)

    def value(self, key, player=None):
        rows = snapshot(self.root)["values"]
        return next(row["value"] for row in rows if row["key"] == key and row["player"] == player)

    def test_shared_and_per_player_values_reset_on_new_game(self):
        self.configure("counter", "SHARED", "game")
        self.configure("counter", "PERSONAL", "player")
        self.configure("flag", "LIT", "player")
        hits = [rule("HIT", action("inc_counter", "SHARED"), action("inc_counter", "PERSONAL"),
                     action("inc_counter", "LEGACY"), action("set_flag", "LIT", value=True))]
        self.send("HIT", hits)
        self.assertEqual(self.value("LEGACY"), 1)
        self.assertIsNone(self.value("SHARED"))
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_ADD_PLAYER")
        self.sensor("launch")
        turn = game.read_rules_game(self.root)["turnId"]
        self.send("HIT", hits, _turnId=turn)
        self.send("HIT", hits, _turnId=turn)
        self.sensor("drain")
        self.sensor("launch")
        self.send("HIT", hits, _turnId=turn)  # Stale event must not mutate scoped values.
        self.send("HIT", hits)
        self.assertEqual(self.value("SHARED"), 3)
        self.assertEqual(self.value("PERSONAL", "Player 1"), 2)
        self.assertEqual(self.value("PERSONAL", "Player 2"), 1)
        self.assertTrue(self.value("LIT", "Player 2"))
        self.sensor("drain")
        self.command("REQUEST_END_GAME")
        self.command("REQUEST_START_GAME")
        self.assertEqual(self.value("SHARED"), 0)
        self.assertEqual(self.value("PERSONAL", "Player 1"), 0)
        self.assertFalse(self.value("LIT", "Player 1"))
        self.assertEqual(self.value("LEGACY"), 5)

    def test_player_countdown_pauses_during_other_players_and_operator_pause(self):
        self.configure("timer", "MODE", "player", clock="play", durationMs=3000)
        self.configure("flag", "DONE", "player")
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_ADD_PLAYER")
        self.send("START", [rule("START", action("start_timer", "MODE"))])
        self.advance(5000)
        self.assertEqual(self.value("MODE", "Player 1"), {"remainingMs": 3000, "status": "Paused"})
        self.sensor("launch")
        self.advance(1000, wall=-3000)  # Active time is monotonic.
        self.command("REQUEST_PAUSE_GAME")
        self.advance(3000)
        self.assertEqual(self.value("MODE", "Player 1")["remainingMs"], 2000)
        self.command("REQUEST_RESUME_GAME")
        self.sensor("drain")
        self.sensor("launch")
        self.advance(5000)
        self.assertEqual(self.value("MODE", "Player 1")["remainingMs"], 2000)
        self.sensor("drain")
        self.sensor("launch")
        self.advance(1999)
        self.assertEqual(self.value("MODE", "Player 1")["remainingMs"], 1)
        self.advance(1)
        authored = [rule(scoped_state.TIMER_EVENT, action("set_flag", "DONE", value=True),
                         trigger_type="timer", params={"timer": "MODE"})]
        (self.root / "rules" / "rules.json").write_text(json.dumps(authored))
        with patch("pinballctl.rules.runtime.get_bus") as bus, patch("pinballctl.rules.runtime.get_event_manager"), patch("pinballctl.rules.runtime.append_event_log"):
            dispatch_timer_expirations(self.root, now=self.clock)
            dispatch_timer_expirations(self.root, now=self.clock)
        self.assertTrue(self.value("DONE", "Player 1"))
        self.assertFalse(self.value("DONE", "Player 2"))
        self.assertEqual(bus.return_value.emit.call_count, 1)

    def test_continuous_timer_manual_pause_resume_and_reset(self):
        self.configure("timer", "SHARED", "game", clock="wall", durationMs=1000)
        self.command("REQUEST_START_GAME")
        for event, delta, remaining in [
            ("start", 200, 800), ("pause", 6000, 800), ("resume", 100, 700), ("reset", 0, 0)
        ]:
            self.send(event, [rule(event, action(event + "_timer", "SHARED"))])
            self.advance(delta)
            # Supply the same clock to the readout as the runtime.
            with patch("pinballctl.rules.evaluation.time.time", return_value=self.clock / 1000):
                self.assertEqual(self.value("SHARED")["remainingMs"], remaining)

    def test_expiry_at_turn_boundary_keeps_outgoing_owner_and_skips_output(self):
        self.configure("timer", "MODE", "player", clock="play", durationMs=1000)
        self.configure("flag", "DONE", "player")
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_ADD_PLAYER")
        self.sensor("launch")
        self.send("START", [rule("START", action("start_timer", "MODE"))])
        self.advance(1000)
        self.sensor("drain")
        expiry = [rule(scoped_state.TIMER_EVENT, action("set_flag", "DONE", value=True),
                       action("pulse", "coil"), trigger_type="timer", params={"timer": "MODE"})]
        with state_transaction(self.root) as state:
            pending = scoped_state.collect_expired(state, game.read_rules_game(self.root), self.clock)
        self.assertEqual(pending[0]["playerId"], 1)
        selected = self.send(scoped_state.TIMER_EVENT, expiry, **pending[0])
        self.assertEqual(selected[0]["actions"], [])
        self.assertTrue(self.value("DONE", "Player 1"))
        self.assertFalse(self.value("DONE", "Player 2"))

    def test_global_play_clock_keeps_progress_across_games(self):
        self.configure("timer", "LIFETIME", "global", clock="play", durationMs=3000)
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        self.send("START", [rule("START", action("start_timer", "LIFETIME"))])
        self.advance(1000)
        self.sensor("drain")
        self.command("REQUEST_END_GAME")
        self.advance(5000)
        self.command("REQUEST_START_GAME")
        self.assertEqual(self.value("LIFETIME")["remainingMs"], 2000)
        self.sensor("launch")
        self.advance(1000)
        self.assertEqual(self.value("LIFETIME")["remainingMs"], 1000)
