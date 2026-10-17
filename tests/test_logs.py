import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from pinballctl.app.modules.logs import api


class LogReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.log"
        self.path.write_bytes(b"first\nsecond\n")
        app = Flask(__name__)
        app.register_blueprint(api.api_bp)
        self.client = app.test_client()
        for name, value in (("_resolve_single_log_path", self.path), ("maintain_logs_once", None)):
            mock = patch.object(api, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_tail_preserves_last_line_terminator(self):
        self.assertEqual(api._tail_last_lines(self.path, lines=1), ("second\n", 13))

    def test_zero_lines_returns_empty_tail_at_eof(self):
        self.assertEqual(api._tail_last_lines(self.path, lines=0), ("", 13))

    def test_tail_respects_cap_and_omits_leading_fragment(self):
        self.assertEqual(api._tail_last_lines(self.path, max_bytes=10), ("second\n", 13))

    def test_cap_on_line_boundary_keeps_complete_line(self):
        self.assertEqual(api._tail_last_lines(self.path, max_bytes=7), ("second\n", 13))

    def test_tail_preserves_unterminated_line(self):
        self.path.write_bytes(b"first\npartial")
        self.assertEqual(api._tail_last_lines(self.path, lines=1), ("partial", 13))

    def test_initial_offset_does_not_skip_concurrent_append(self):
        original = api._tail_last_lines
        def tail_then_append(*args, **kwargs):
            result = original(*args, **kwargs)
            with self.path.open("ab") as f:
                f.write(b"new line\n")
            return result
        with patch.object(api, "_tail_last_lines", side_effect=tail_then_append):
            response = self.client.get("/chunk").get_json()
        self.assertEqual(response["next_offset"], 13)
        following = self.client.get("/chunk?offset=13").get_json()
        self.assertEqual(following["data"], "new line\n")

    def test_truncation_resumes_at_consumed_offset(self):
        result = self.client.get("/chunk?offset=100").get_json()
        self.assertTrue(result["rotated"])
        self.assertEqual(result["data"], "first\nsecond\n")
        self.assertEqual(result["next_offset"], 13)

    def test_incremental_read_respects_cap(self):
        result = self.client.get("/chunk?offset=6&max_bytes=4").get_json()
        self.assertEqual(result["data"], "seco")
        self.assertEqual(result["next_offset"], 10)


if __name__ == "__main__":
    unittest.main()
