import json
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import unittest
from pinballctl.game import runtime as game
from pinballctl.game import store


def concurrent_start(args):
    instance, ident = args
    return game.execute(instance, "REQUEST_START_GAME", {}, ident, authority="operator")


def crash_uncommitted(instance):
    import os

    with store.transaction(instance) as db:
        store.write(db, "game", {"credits": 999})
        os._exit(23)


class GameManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        game.configure(
            self.root,
            "game",
            {
                "freePlay": False,
                "testCredits": True,
                "unitsPerCredit": 100,
                "denominations": [25, 100],
            },
        )
        game.configure(
            self.root,
            "ball",
            {
                "inventory": 3,
                "sensors": [
                    {"source": "launch", "role": "launch", "debounceMs": 0},
                    {"source": "drain", "role": "drain", "debounceMs": 0},
                ],
            },
        )

    def command(self, name, params=None, ident=None, authority="operator"):
        return game.execute(
            self.root,
            name,
            params or {},
            ident or __import__("uuid").uuid4().hex,
            authority=authority,
        )

    def credit(self):
        self.assertTrue(self.command("REQUEST_AWARD_CREDIT", {"units": 100})["ok"])

    def sensor(self, sensor, active=True):
        return self.command(
            "OBSERVE", {"sensor": sensor, "active": active}, authority="hardware"
        )

    def test_denominations_and_trust(self):
        self.assertFalse(
            self.command("REQUEST_AWARD_CREDIT", {"units": 100}, authority="rules")[
                "ok"
            ]
        )
        for _ in range(3):
            self.command("REQUEST_AWARD_CREDIT", {"units": 25}, authority="coin")
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)
        self.command("REQUEST_AWARD_CREDIT", {"units": 25}, authority="coin")
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 1)
        self.assertFalse(
            self.command("REQUEST_AWARD_CREDIT", {"units": 30}, authority="coin")["ok"]
        )

    def test_command_retry_and_conflict(self):
        a = self.command("REQUEST_AWARD_CREDIT", {"units": 100}, "credit-1")
        self.assertEqual(
            a, self.command("REQUEST_AWARD_CREDIT", {"units": 100}, "credit-1")
        )
        with self.assertRaises(ValueError):
            self.command("REQUEST_AWARD_CREDIT", {"units": 200}, "credit-1")
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 1)

    def test_multi_process_start_spends_once(self):
        self.credit()
        self.credit()
        with ProcessPoolExecutor(2) as pool:
            results = list(
                pool.map(
                    concurrent_start,
                    [(str(self.root), "start-a"), (str(self.root), "start-b")],
                )
            )
        self.assertEqual(sum(r["ok"] for r in results), 1)
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 1)

    def test_two_sensor_flow_and_player_turns(self):
        self.credit()
        self.credit()
        self.assertTrue(self.command("REQUEST_START_GAME")["ok"])
        self.assertTrue(self.command("REQUEST_ADD_PLAYER")["ok"])
        self.sensor("launch")
        view = game.snapshot(self.root)
        self.assertEqual(view["game"]["status"], "BALL_ACTIVE")
        self.assertEqual(view["ball"]["confidence"], "inferred")
        self.sensor("drain")
        view = game.snapshot(self.root)
        self.assertEqual(view["game"]["currentPlayer"], 2)
        self.assertEqual(view["game"]["status"], "PREPARING")
        self.assertNotEqual(
            view["scores"]["1"]["finalizedTurn"], view["game"]["turnId"]
        )

    def test_multiball_and_unknown_drain(self):
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        self.sensor("launch", False)
        self.sensor("launch")
        self.sensor("drain")
        self.assertEqual(game.snapshot(self.root)["game"]["status"], "BALL_ACTIVE")
        self.sensor("drain", False)
        self.sensor("drain")
        self.assertEqual(game.snapshot(self.root)["game"]["status"], "PREPARING")
        self.sensor("drain", False)
        self.sensor("drain")
        self.assertEqual(
            game.snapshot(self.root)["game"]["status"], "RECOVERY_REQUIRED"
        )

    def test_extra_ball_precedence_and_configuration_guard(self):
        self.credit()
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_AWARD_EXTRA_BALL", {"count": 1})
        self.sensor("launch")
        self.sensor("drain")
        self.assertEqual(game.snapshot(self.root)["game"]["ballNumber"], 1)
        with self.assertRaises(ValueError):
            game.configure(self.root, "game", {"freePlay": True})

    def test_recovery_requires_operator_and_explicit_resume(self):
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        self.command("RECOVER", authority="internal")
        self.assertIsNone(game.snapshot(self.root)["ball"]["inPlay"])
        self.assertFalse(self.command("REQUEST_RESUME_GAME")["ok"])
        self.assertFalse(
            self.command(
                "RECONCILE", {"inPlay": 1, "reason": "checked"}, authority="rules"
            )["ok"]
        )
        self.assertTrue(
            self.command("RECONCILE", {"inPlay": 1, "reason": "checked physically"})[
                "ok"
            ]
        )
        self.assertEqual(game.snapshot(self.root)["game"]["status"], "PAUSED")
        self.assertTrue(self.command("REQUEST_RESUME_GAME")["ok"])

    def test_transaction_rollback_after_crash(self):
        with self.assertRaises(RuntimeError):
            with store.transaction(self.root) as db:
                store.write(db, "game", {"credits": 999})
                raise RuntimeError("crash")
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)

    def test_scoring_is_per_player_and_duplicate_safe(self):
        from pinballctl.scoring.runtime import save_scoring_config

        save_scoring_config(
            self.root,
            {
                "settings": {"enabled": True},
                "scoreRules": [
                    {
                        "id": "hits",
                        "name": "Hits",
                        "eventName": "HIT",
                        "basePoints": 100,
                        "enabled": True,
                    }
                ],
                "combos": [],
            },
        )
        self.credit()
        self.credit()
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_ADD_PLAYER")
        self.sensor("launch")
        game.ingest(self.root, "HIT", "switch", {"_eventId": "hit-a"})
        game.ingest(self.root, "HIT", "switch", {"_eventId": "hit-a"})
        self.assertEqual(game.snapshot(self.root)["scores"]["1"]["score"], 100)
        old_turn = game.snapshot(self.root)["game"]["turnId"]
        self.sensor("drain")
        self.sensor("launch", False)
        self.sensor("launch")
        game.ingest(
            self.root, "HIT", "switch", {"_eventId": "late", "_turnId": old_turn}
        )
        self.assertEqual(game.snapshot(self.root)["scores"]["2"]["score"], 0)
        game.ingest(self.root, "HIT", "switch", {"_eventId": "hit-b"})
        self.assertEqual(game.snapshot(self.root)["scores"]["2"]["score"], 100)

    def test_manager_condition_unknown_fails_closed(self):
        from pinballctl.rules.evaluation import condition_matches

        state = {"managers": {"ball": {"inPlay": None}}}
        self.assertFalse(
            condition_matches(
                {"type": "ball", "key": "inPlay", "op": "==", "value": 0}, state, 0
            )
        )
        self.assertFalse(
            condition_matches(
                {"type": "ball", "key": "inPlay", "op": "!=", "value": 0}, state, 0
            )
        )

    def test_rejected_reconcile_does_not_mutate_ball(self):
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        prior = game.snapshot(self.root)["ball"]
        self.assertFalse(
            self.command(
                "RECONCILE", {"inPlay": 3, "reason": "invalid active reconciliation"}
            )["ok"]
        )
        self.assertEqual(game.snapshot(self.root)["ball"], prior)

    def test_ball_save_does_not_extend_on_relaunch(self):
        game.configure(self.root, "game", {"freePlay": True, "ballSaveMs": 1000})
        from unittest.mock import patch

        with patch.object(game, "now_ms", return_value=10000):
            self.command("REQUEST_START_GAME")
            self.sensor("launch")
        self.assertEqual(game.snapshot(self.root)["game"]["ballSaveUntil"], 11000)
        with patch.object(game, "now_ms", return_value=10500):
            self.sensor("drain")
            self.sensor("launch", False)
            self.sensor("launch")
        self.assertEqual(game.snapshot(self.root)["game"]["ballSaveUntil"], 11000)
        with patch.object(game, "now_ms", return_value=11500):
            self.sensor("drain", False)
            self.sensor("drain")
        self.assertEqual(game.snapshot(self.root)["game"]["ballNumber"], 2)

    def test_individual_occupancy_sensors_and_timeout(self):
        game.configure(
            self.root,
            "ball",
            {
                "inventory": 3,
                "devices": [
                    {
                        "id": "trough",
                        "capacity": 2,
                        "destination": "shooter",
                        "timeoutMs": 250,
                    },
                    {"id": "shooter", "capacity": 1},
                ],
                "sensors": [
                    {
                        "source": "t1",
                        "role": "occupancy",
                        "zone": "trough",
                        "debounceMs": 0,
                    },
                    {
                        "source": "t2",
                        "role": "occupancy",
                        "zone": "trough",
                        "debounceMs": 0,
                    },
                    {"source": "launch", "role": "launch", "debounceMs": 0},
                ],
            },
        )
        self.sensor("t1")
        self.assertIsNone(game.snapshot(self.root)["ball"]["zones"]["trough"]["count"])
        self.sensor("t2")
        self.assertEqual(
            game.snapshot(self.root)["ball"]["zones"]["trough"]["count"], 2
        )
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        self.assertTrue(
            self.command("REQUEST_BALL_MOVEMENT", {"deviceId": "trough"})["ok"]
        )
        with __import__("unittest").mock.patch.object(
            game, "now_ms", return_value=game.now_ms() + 1000
        ):
            self.command("TICK", authority="internal")
        self.assertEqual(
            game.snapshot(self.root)["game"]["status"], "RECOVERY_REQUIRED"
        )

    def test_backup_restores_into_reconciliation_without_replaying_commands(self):
        from pinballctl.backup import service
        import os
        from unittest.mock import patch

        with (
            tempfile.TemporaryDirectory() as library,
            patch.dict(os.environ, {"PINBALLCTL_BACKUP_DIR": library}),
        ):
            self.credit()
            self.command("REQUEST_START_GAME")
            self.sensor("launch")
            (self.root / "hardware").mkdir(exist_ok=True)
            (self.root / "hardware/mapping.json").write_text(
                json.dumps(
                    {
                        "launch": {"function": "Button", "friendly": "Launch"},
                        "drain": {"function": "Switch", "friendly": "Drain"},
                    }
                )
            )
            saved = service.create(self.root, ["game", "ball", "scoring"])
            seq = [{"id": saved["id"], "components": ["game", "ball", "scoring"]}]
            preview = service.preview(self.root, seq)
            service.restore(self.root, seq, False, preview)
            view = game.snapshot(self.root)
            self.assertEqual(view["game"]["status"], "RECOVERY_REQUIRED")
            self.assertIsNone(view["ball"]["inPlay"])
            with store.transaction(self.root) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM outbox").fetchone()[0], 0
                )

    def test_event_api_cannot_forge_physical_or_manager_events(self):
        game.configure(
            self.root,
            "game",
            {"freePlay": True, "coinInputs": [{"source": "coin", "units": 100}]},
        )
        game.ingest(
            self.root, "COIN", "coin", {"eventType": "PRESSED", "_eventId": "fake"}
        )
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)
        game.ingest(
            self.root,
            "COIN",
            "coin",
            {
                "eventType": "PRESSED",
                "_eventId": "physical",
                "_hardwareIngress": True,
                "seq": 1,
                "payload": {"tsMs": 5},
            },
        )
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 1)

    def test_outbox_redelivery_does_not_repeat_state_actions(self):
        from unittest.mock import patch
        from pinballctl.rules.runtime import apply_rules_for_event

        self.credit()
        self.command("REQUEST_START_GAME")
        with store.transaction(self.root) as db:
            row = db.execute(
                "SELECT id,name,params FROM outbox WHERE name='GAME_STARTED'"
            ).fetchone()
        params = json.loads(row[2])
        rule = {
            "id": "test",
            "enabled": True,
            "triggers": [{"type": "game", "event": "GAME_STARTED"}],
            "actions": [
                {"type": "inc_counter", "target": "STARTS", "params": {"delta": 1}}
            ],
        }
        with patch("pinballctl.rules.runtime._load_rules", return_value=[rule]):
            apply_rules_for_event(
                self.root, name=row[1], source="pi.game", params=params
            )
            apply_rules_for_event(
                self.root, name=row[1], source="pi.game", params=params
            )
        from pinballctl.rules.evaluation import snapshot

        self.assertEqual(snapshot(self.root)["counters"]["STARTS"], 1)

    def test_no_turn_switch_before_bonus_finalisation(self):
        game.configure(
            self.root,
            "game",
            {"freePlay": True, "ballsPerPlayer": 1, "bonusPoints": 500},
        )
        self.command("REQUEST_START_GAME")
        self.command("REQUEST_ADD_PLAYER")
        self.sensor("launch")
        self.sensor("drain")
        view = game.snapshot(self.root)
        self.assertEqual(view["scores"]["1"]["score"], 500)
        self.assertEqual(view["game"]["currentPlayer"], 2)
        self.sensor("launch", False)
        self.sensor("launch")
        self.sensor("drain", False)
        self.sensor("drain")
        view = game.snapshot(self.root)
        self.assertEqual(view["game"]["status"], "GAME_ENDED")
        self.assertEqual(view["scores"]["2"]["score"], 500)
        from pinballctl.scoring.runtime import load_game_history, load_high_scores

        self.assertEqual(len(load_game_history(self.root)["games"]), 1)
        self.assertEqual(len(load_high_scores(self.root)["scores"]), 2)
        self.assertFalse(self.command("REQUEST_END_GAME")["ok"])
        self.assertEqual(len(load_game_history(self.root)["games"]), 1)

    def test_config_limits_and_command_schema(self):
        for change in (
            {"maxPlayers": 0},
            {"unitsPerCredit": 0},
            {"freePlay": "yes"},
            {"coinInputs": [{"source": "coin", "units": 3}]},
        ):
            with self.assertRaises(ValueError):
                game.configure(self.root, "game", change)
        self.assertFalse(
            self.command("REQUEST_AWARD_EXTRA_BALL", {"count": True})["ok"]
        )
        self.assertFalse(
            self.command(
                "OBSERVE", {"sensor": "launch", "active": "true"}, authority="hardware"
            )["ok"]
        )

    def test_recovery_and_clock_guard_prevent_release_replay(self):
        from unittest.mock import patch

        game.configure(
            self.root,
            "ball",
            {
                "inventory": 1,
                "devices": [
                    {
                        "id": "trough",
                        "capacity": 1,
                        "destination": "shooter",
                        "timeoutMs": 5000,
                        "releaseOutput": "board__GPIO__5",
                        "pulseMs": 30,
                    },
                    {"id": "shooter", "capacity": 1},
                ],
                "sensors": [
                    {
                        "source": "slot",
                        "role": "occupancy",
                        "zone": "trough",
                        "debounceMs": 0,
                    },
                    {"source": "launch", "role": "launch", "debounceMs": 0},
                ],
            },
        )
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("slot")
        self.sensor("launch")
        self.command("REQUEST_BALL_MOVEMENT", {"deviceId": "trough"})
        with store.transaction(self.root) as db:
            row = db.execute(
                "SELECT id,params FROM outbox WHERE name='BALL_MOVEMENT_REQUESTED'"
            ).fetchone()
        with (
            patch(
                "pinballctl.bridge.state.commands_path",
                return_value=self.root / "bridge/commands.json",
            ),
            patch(
                "pinballctl.bridge.state.read_state", return_value={"connected": True}
            ),
            patch(
                "pinballctl.bridge.state.rpc_command",
                side_effect=[{"tsMs": 1000}, {"accepted": False}],
            ) as rpc,
        ):
            game._send_release_once(self.root, row[0], json.loads(row[1]))
            game._send_release_once(self.root, row[0], json.loads(row[1]))
            self.assertEqual(rpc.call_count, 2)
            self.assertEqual(rpc.call_args.args[0]["triggeredAtMs"], 1000)
        self.assertEqual(
            game.snapshot(self.root)["game"]["status"], "RECOVERY_REQUIRED"
        )

    def test_static_input_watches_have_no_output_actions(self):
        mapping = {
            "launch": {"function": "Button", "friendly": "Launch"},
            "drain": {"function": "Switch", "friendly": "Drain"},
        }
        rules = game.observation_rules(self.root, mapping=mapping)
        self.assertEqual(len(rules), 2)
        self.assertTrue(all(not rule["actions"] for rule in rules))
        self.assertEqual(
            {t["source"] for r in rules for t in r["triggers"]}, {"launch", "drain"}
        )

    def test_private_score_context_is_not_game_state(self):
        from pinballctl.scoring.runtime import save_scoring_config

        save_scoring_config(
            self.root,
            {"scoreRules": [{"eventName": "HIT", "basePoints": 10}], "combos": []},
        )
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        game.ingest(self.root, "HIT", "input", {"_eventId": "once"})
        self.assertNotIn("game", game.snapshot(self.root)["scores"]["1"])

    def test_process_death_releases_transaction_claim(self):
        from multiprocessing import get_context

        process = get_context("spawn").Process(
            target=crash_uncommitted, args=(str(self.root),)
        )
        process.start()
        process.join(10)
        self.assertEqual(process.exitcode, 23)
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)
        self.credit()
        self.assertTrue(self.command("REQUEST_START_GAME")["ok"])

    def test_multiple_processes_retry_same_request(self):
        self.credit()
        with ProcessPoolExecutor(2) as pool:
            results = list(
                pool.map(concurrent_start, [(str(self.root), "same-start")] * 2)
            )
        self.assertEqual(results[0], results[1])
        self.assertTrue(results[0]["ok"])
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)
        with store.transaction(self.root) as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM outbox WHERE name='GAME_STARTED'"
                ).fetchone()[0],
                1,
            )

    def test_unmapped_physical_inputs_do_not_become_ball_sensors(self):
        self.sensor("unrelated-switch")
        self.assertNotIn(
            "unrelated-switch", game.snapshot(self.root)["ball"]["sensors"]
        )

    def test_out_of_order_physical_event_cannot_change_next_turn(self):
        game.configure(self.root, "game", {"freePlay": True})
        self.command("REQUEST_START_GAME")

        def event(name, source, seq, stamp):
            game.ingest(
                self.root,
                name,
                source,
                {
                    "eventType": "CLOSED",
                    "_hardwareIngress": True,
                    "seq": seq,
                    "payload": {"tsMs": stamp},
                },
            )

        event("LAUNCH", "launch", 1, 100)
        event("DRAIN", "drain", 2, 200)
        turn = game.snapshot(self.root)["game"]["turnId"]
        event("LAUNCH", "launch", 3, 150)
        self.assertEqual(game.snapshot(self.root)["game"]["turnId"], turn)
        self.assertEqual(game.snapshot(self.root)["game"]["status"], "PREPARING")

    def test_payment_settlement_is_idempotent_and_identity_is_not_credit(self):
        game.ingest(
            self.root,
            "NFC_MATCHED",
            "reader",
            {"identity": "example", "_eventId": "identity-only"},
        )
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 0)
        first = game.award_verified_settlement(self.root, "verified-1", 100)
        self.assertEqual(
            first, game.award_verified_settlement(self.root, "verified-1", 100)
        )
        self.assertEqual(game.snapshot(self.root)["game"]["credits"], 1)

    def test_manager_rule_output_uses_fresh_firmware_clock(self):
        from unittest.mock import patch
        from pinballctl.rules.runtime import apply_rules_for_event

        self.credit()
        self.command("REQUEST_START_GAME")
        with store.transaction(self.root) as db:
            row = db.execute(
                "SELECT name,params FROM outbox WHERE name='GAME_STARTED'"
            ).fetchone()
        rule = {
            "id": "lamp",
            "enabled": True,
            "triggers": [{"type": "game", "event": "GAME_STARTED"}],
            "actions": [{"type": "pulse", "target": "lamp", "params": {"ms": 10}}],
        }
        sent = []
        with (
            patch("pinballctl.rules.runtime._load_rules", return_value=[rule]),
            patch("pinballctl.bridge.state.rpc_command", return_value={"tsMs": 1234}),
        ):
            apply_rules_for_event(
                self.root,
                name=row[0],
                source="pi.game",
                params=json.loads(row[1]),
                enqueue_bridge_event=lambda cmd: (sent.append(cmd) or True, None),
            )
        self.assertEqual(sent[0]["triggeredAtMs"], 1234)

    def test_registry_editor_wizard_parity_gate(self):
        import runpy

        report = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "utils/audit-management.py")
        )["audit"]()
        self.assertEqual(report["wizardCounts"], {"available": 30, "unavailable": 137})

    def test_paused_drain_finalizes_only_on_explicit_resume(self):
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        self.command("REQUEST_PAUSE_GAME")
        self.sensor("drain")
        self.assertEqual(game.snapshot(self.root)["game"]["ballNumber"], 1)
        self.assertTrue(self.command("REQUEST_RESUME_GAME")["ok"])
        self.assertEqual(game.snapshot(self.root)["game"]["ballNumber"], 2)
        self.assertEqual(game.snapshot(self.root)["game"]["status"], "PREPARING")

    def test_destination_departure_is_not_movement_confirmation(self):
        from pinballctl.ball import runtime as physical

        state = physical.initial()
        state["pending"] = [
            {
                "id": "move",
                "deviceId": "trough",
                "destination": "shooter",
                "deadline": 5000,
            }
        ]
        config = {
            "sensors": [
                {
                    "source": "shooter",
                    "role": "occupancy",
                    "zone": "shooter",
                    "debounceMs": 0,
                }
            ]
        }
        physical.observe(state, config, "shooter", False, 100, lambda *a: None)
        self.assertEqual(len(state["pending"]), 1)
        physical.observe(state, config, "shooter", True, 200, lambda *a: None)
        self.assertEqual(state["pending"], [])

    def test_delayed_api_confirmation_retains_original_turn(self):
        from flask import Flask
        from unittest.mock import patch
        from pinballctl.app.modules.events import api as events_api
        from pinballctl.scoring.runtime import save_scoring_config

        save_scoring_config(
            self.root,
            {"scoreRules": [{"eventName": "HIT", "basePoints": 10}], "combos": []},
        )
        self.credit()
        self.command("REQUEST_START_GAME")
        self.sensor("launch")
        app = Flask(__name__, instance_path=str(self.root))
        app.register_blueprint(events_api.api_bp, url_prefix="/api/events")
        with (
            patch.object(events_api, "_validate_event", return_value=(True, None)),
            patch.object(
                events_api, "_enqueue_bridge_event_fast", return_value=(True, None)
            ) as enqueue,
            patch.object(events_api, "append_event_log"),
        ):
            response = app.test_client().post(
                "/api/events/fire", json={"name": "HIT", "source": "switch"}
            )
            self.assertEqual(response.status_code, 200)
            context = enqueue.call_args.args[0]["_bridge_event_context"]["params"]
        first_turn = context["_turnId"]
        self.sensor("drain")
        self.sensor("launch", False)
        self.sensor("launch")
        self.assertNotEqual(first_turn, game.snapshot(self.root)["game"]["turnId"])
        game.ingest(self.root, "HIT", "switch", context)
        self.assertEqual(game.snapshot(self.root)["scores"]["1"]["score"], 0)
