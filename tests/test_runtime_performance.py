import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sqlite3
from unittest.mock import patch, Mock


class RuntimeCacheTests(unittest.TestCase):
    def test_video_probe_reuses_metadata_and_invalidates_on_file_change(self):
        from pinballctl.runtime.media import godot_runtime as runtime
        runtime._probe_video_dimensions_cached.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.ogv'
            path.write_bytes(b'video')
            with patch.object(runtime.shutil, 'which', return_value='/usr/bin/ffprobe'), patch.object(
                    runtime.subprocess, 'run', return_value=Mock(returncode=0, stdout='640x480')) as probe:
                self.assertEqual(runtime._probe_video_dimensions(path), (640, 480))
                self.assertEqual(runtime._probe_video_dimensions(path), (640, 480))
                self.assertEqual(probe.call_count, 1)
                path.write_bytes(b'changed video')
                runtime._probe_video_dimensions(path)
                self.assertEqual(probe.call_count, 2)
                path.unlink()
                self.assertEqual(runtime._probe_video_dimensions(path), (0, 0))

    def test_font_cache_returns_independent_lists(self):
        from pinballctl.runtime.media import runtime
        runtime._detect_system_fonts_cached.cache_clear()
        with patch.object(runtime.shutil, 'which', return_value='/usr/bin/fc-list'), patch.object(
                runtime.subprocess, 'run', return_value=Mock(stdout='Arial\nHelvetica\n')) as probe:
            fonts = runtime._detect_system_fonts()
            fonts.clear()
            self.assertIn('Arial', runtime._detect_system_fonts())
            self.assertEqual(probe.call_count, 1)
        runtime._detect_system_fonts_cached.cache_clear()

    def test_audio_cache_invalidates_for_config_and_asset_directory(self):
        from pinballctl.runtime.audio import runtime
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runtime, '_reindex_assets_from_disk', wraps=runtime._reindex_assets_from_disk) as scan:
                first = runtime.load_audio_config(directory)
                first['settings']['enabled'] = False
                self.assertTrue(runtime.load_audio_config(directory)['settings']['enabled'])
                self.assertEqual(scan.call_count, 1)
                runtime.save_audio_config(directory, first)
                self.assertFalse(runtime.load_audio_config(directory)['settings']['enabled'])
                self.assertEqual(scan.call_count, 2)
                # Even an unrecognised file changes the directory signature.
                (runtime._assets_dir(directory) / 'new.txt').write_text('new')
                runtime.load_audio_config(directory)
                self.assertEqual(scan.call_count, 3)

    def test_manager_connection_reuse_preserves_commit_and_rollback_boundaries(self):
        from pinballctl.runtime.game import store

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(store, "_connect", wraps=store._connect) as connect:
                with store.reuse_connection(directory):
                    with store.transaction(directory) as db:
                        store.write(db, "fixture", "committed")
                    with self.assertRaisesRegex(ValueError, "fixture failure"):
                        with store.transaction(directory) as db:
                            store.write(db, "fixture", "uncommitted")
                            raise ValueError("fixture failure")
                    with closing(sqlite3.connect(store.path(directory))) as other:
                        self.assertEqual(store.read(other, "fixture", None), "committed")
                    with store.transaction(directory, write=False) as db:
                        self.assertEqual(store.read(db, "fixture", None), "committed")
                connect.assert_called_once()

    def test_audio_only_defers_status_for_events_without_actions(self):
        from pinballctl.runtime.audio import runtime

        config = {
            "mappings": [{"eventName": "STOP_ALL", "action": "stop_all"}],
        }
        engine = Mock()
        engine.stop.return_value = 1
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(runtime, "load_audio_config", return_value=config), \
                patch.object(runtime, "_get_engine", return_value=engine), \
                patch.object(runtime, "_publish_event_state") as publish:
            idle = runtime.process_event(directory, name="CLOSED", source="switch", _defer_idle_state=True)
            self.assertEqual(idle["idleEvent"]["name"], "CLOSED")
            publish.assert_not_called()
            result = runtime.process_event(directory, name="STOP_ALL", source=None, _defer_idle_state=True)
            self.assertTrue(result["processed"])
            engine.stop.assert_called_once_with(cue_id=None)
            publish.assert_called_once()
