"""Regression checks for moved guide links and dated development notes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'website/utils'))
import developer_log
import docs_renderer


class DocumentationTests(unittest.TestCase):
    def test_dated_entry_url_keeps_the_full_date(self):
        self.assertEqual(
            docs_renderer.doc_url('developer-log/2026-11-18-documentation-home'),
            '/docs/developer-log/2026-11-18-documentation-home/',
        )
        self.assertEqual(docs_renderer.doc_url('developer-guide/index'), '/docs/developer-guide/')

    def test_relative_links_resolve_by_directory_and_preserve_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for section in ('user-guide', 'developer-guide'):
                (root / section).mkdir()
                (root / section / 'setup.md').write_text('# Setup')
            source = root / 'developer-guide' / 'index.md'
            rendered = docs_renderer._render_markdown(
                '[User](../user-guide/setup.md#first-step) [Developer](setup.md)',
                source, root, root / 'assets',
            )
            self.assertIn('href="/docs/user-guide/setup/#first-step"', rendered)
            self.assertIn('href="/docs/developer-guide/setup/"', rendered)

    def test_missing_source_link_fails_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Missing documentation link'):
                docs_renderer._render_markdown('[Lost](missing.md)', root / 'index.md', root, root / 'assets')

    def test_invalid_log_metadata_cannot_silently_hide_an_entry(self):
        entry = {'id': 'note', 'slug': 'developer-log/2026-11-18-note',
                 'date': '2026-11-18', 'tags': ['website'], 'summary': 'A note.', 'related': []}
        pages = [{'slug': entry['slug'], 'title': 'A note'}]
        mapping = {entry['slug']: docs_renderer.doc_url(entry['slug'])}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'log.json'
            for changes in ({'related': ['missing']}, {'date': '2026-11-17'}, {'tags': ['bad tag']}):
                with self.subTest(changes=changes):
                    path.write_text(json.dumps([{**entry, **changes}]))
                    with self.assertRaises(ValueError):
                        developer_log.load_entries(path, pages, mapping)
            path.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'metadata/source mismatch'):
                developer_log.load_entries(path, pages, mapping)


if __name__ == '__main__':
    unittest.main()
