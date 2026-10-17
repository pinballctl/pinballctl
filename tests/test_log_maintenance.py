import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pinballctl import log_maintenance as logs


class LogRotationTests(unittest.TestCase):
    def test_competing_rotator_does_not_copy_or_truncate_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.log"
            path.write_bytes(b"original\n")
            inode = path.stat().st_ino
            copying = threading.Event()
            release = threading.Event()
            original_copy = logs.shutil.copy2
            def paused_copy(*args):
                copying.set()
                if not release.wait(5):
                    raise RuntimeError("rotation test timed out")
                return original_copy(*args)
            with patch.object(logs, "_log_rotate_bytes", return_value=1), \
                 patch.object(logs, "_archive_dir", return_value=Path(tmp)), \
                 patch.object(logs.shutil, "copy2", side_effect=paused_copy), \
                 ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(logs.rotate_if_needed, "bridge", path)
                try:
                    self.assertTrue(copying.wait(5))
                    self.assertIsNone(logs.rotate_if_needed("bridge", path))
                    self.assertEqual(path.read_bytes(), b"original\n")
                finally:
                    release.set()
                archive = first.result(timeout=5)
            self.assertEqual(archive.read_bytes(), b"original\n")
            self.assertEqual(path.read_bytes(), b"")
            self.assertEqual(path.stat().st_ino, inode)

    def test_missing_log_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.log"
            self.assertIsNone(logs.rotate_if_needed("bridge", path))
            self.assertFalse(path.exists())
