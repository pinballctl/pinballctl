from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from pinballctl.game import store
from pinballctl.scoring import leaderboard
from pinballctl.scoring.runtime import finalize_game, load_game_history, load_high_scores


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        instance = TemporaryDirectory()
        self.addCleanup(instance.cleanup)
        self.root = Path(instance.name)
        self.now = int(time.time() * 1000)

    def record(self, game_id, ended, *scores, reason="All player turns complete"):
        game = {
            "gameId": game_id, "startedAtMs": ended - 100, "endedAtMs": ended,
            "status": "GAME_ENDED", "reason": reason,
            "players": [{"id": str(n), "name": f"Player {n}"} for n in range(1, len(scores) + 1)],
        }
        with store.transaction(self.root) as db:
            finalize_game(db, game, {str(n): {"score": score} for n, score in enumerate(scores, 1)})
            store.write(db, "game", game)

    def test_initials_follow_player_order_and_cannot_change_scores(self):
        self.record("first", self.now, 500, 1000)
        state = leaderboard.backglass_request(self.root, "state", {})
        self.assertEqual(state["prompt"]["playerId"], "1")
        state = leaderboard.backglass_request(self.root, "submit", {
            "gameId": "first", "playerId": "2", "initials": "BOB",
        })
        self.assertEqual(state["prompt"]["playerId"], "1")
        first = {"gameId": "first", "playerId": "1", "initials": "ann", "score": 999999}
        state = leaderboard.backglass_request(self.root, "submit", first)
        self.assertEqual(state["prompt"]["playerId"], "2")
        leaderboard.backglass_request(self.root, "submit", first)
        state = leaderboard.backglass_request(self.root, "skip", {"gameId": "first", "playerId": "2"})
        self.assertIsNone(state["prompt"])
        self.assertEqual([(r["initials"], r["score"]) for r in state["boards"]["all-time"]],
                         [("---", 1000), ("ANN", 500)])

    def test_period_order_and_latest_are_independent_of_history(self):
        def date(year, month, day):
            return int(datetime(year, month, day, 12).timestamp() * 1000)

        self.record("old", date(2025, 12, 31), 900)
        self.record("month", date(2026, 1, 31), 800)
        self.record("tie1", date(2026, 2, 1), 750)
        self.record("tie2", date(2026, 2, 2), 750)
        self.record("aborted", date(2026, 2, 3), 5000, reason="Ended by operator")
        with store.transaction(self.root) as db:
            store.write(db, "history", {"games": []})
            state = leaderboard.backglass_state(db, date(2026, 2, 4))
            self.assertEqual([r["gameId"] for r in state["boards"]["all-time"]], ["old", "month", "tie1", "tie2"])
            self.assertEqual([r["gameId"] for r in state["boards"]["year"]], ["month", "tie1", "tie2"])
            self.assertEqual([r["gameId"] for r in state["boards"]["month"]], ["tie1", "tie2"])
            self.assertEqual([r["gameId"] for r in state["boards"]["latest"]], ["tie2", "tie1", "month", "old"])
            self.assertIsNone(state["prompt"])

    def test_legacy_migration_edit_reset_and_restore(self):
        with store.transaction(self.root) as db:
            result = {"playerId": "1", "name": "Player 1", "score": 700}
            store.write(db, "history", {"games": [{"gameId": "legacy", "endedAtMs": self.now, "players": [result]}]})
            store.write(db, "highScores", {"scores": [{**result, "gameId": "legacy", "endedAtMs": self.now}]})
        self.assertEqual(len(load_high_scores(self.root)["scores"]), 1)
        with store.transaction(self.root) as db:
            leaderboard.edit(db, "legacy", "1", "Ada", "ada", 750)
            snapshot = {"leaderboard": leaderboard.export_rows(db), "leaderboardRows": 8}
            db.execute("DELETE FROM leaderboard")
        self.assertEqual(load_high_scores(self.root)["scores"], [])
        self.assertEqual(load_game_history(self.root)["games"][0]["players"][0]["score"], 700)
        with store.transaction(self.root) as db:
            leaderboard.restore_rows(db, snapshot)
            self.assertEqual(leaderboard.display_rows(db), 8)
        row = load_high_scores(self.root)["scores"][0]
        self.assertEqual((row["name"], row["initials"], row["score"]), ("Ada", "ADA", 750))

    def test_competition_copies_results_and_resets_independently(self):
        self.record("before", self.now - 10_000, 900)
        with store.transaction(self.root) as db:
            leaderboard.change_competition(db, "start", "Friday League")
        self.record("during", self.now, 500, 1000)
        state = leaderboard.backglass_request(self.root, "submit", {
            "gameId": "during", "playerId": "1", "initials": "ACE",
        })
        self.assertEqual(state["competition"], {"title": "Friday League", "active": True})
        self.assertEqual([r["initials"] for r in state["boards"]["competition"]], ["---", "ACE"])
        with store.transaction(self.root) as db:
            leaderboard.edit(db, "during", "1", "Player 1", "ACE", 600, leaderboard.COMPETITION)
            regular = leaderboard.board(db, "all-time", 5)
            self.assertEqual(regular[-1]["score"], 500)
            leaderboard.change_competition(db, "stop", None)
        self.record("after", self.now + 1, 800)
        with store.transaction(self.root) as db:
            self.assertNotIn("competition", leaderboard.backglass_state(db, self.now)["boards"])
            self.assertEqual(len(leaderboard.board(db, leaderboard.COMPETITION, 5)), 2)
            leaderboard.change_competition(db, "start", "Saturday League")
            self.assertEqual(leaderboard.board(db, leaderboard.COMPETITION, 5), [])
            self.assertEqual(len(leaderboard.board(db, "all-time", 5)), 4)
        self.assertEqual(len(load_game_history(self.root)["games"]), 3)

    def test_competition_configuration_and_results_restore(self):
        with store.transaction(self.root) as db:
            leaderboard.prepare(db)
            leaderboard.change_competition(db, "start", "Finals")
        self.record("round", self.now, 300)
        with store.transaction(self.root) as db:
            archive = {
                "leaderboard": leaderboard.export_rows(db),
                "competition": leaderboard.competition(db),
                "competitionScores": leaderboard.export_rows(db, leaderboard.COMPETITION),
            }
            leaderboard.change_competition(db, "reset", None)
            leaderboard.restore_rows(db, archive)
            self.assertEqual(leaderboard.competition(db)["title"], "Finals")
            self.assertEqual(leaderboard.board(db, leaderboard.COMPETITION, 5)[0]["score"], 300)
