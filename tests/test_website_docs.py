"""Regression checks for documentation links and validated website builds."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'website/utils'))
import docs_renderer

spec = importlib.util.spec_from_file_location('website_builder', Path(__file__).resolve().parents[1] / 'website/utils/build-site.py')
website_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(website_builder)


class DocumentationTests(unittest.TestCase):
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



class WebsiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.output = self.root / 'dist/site'
        self.output.mkdir(parents=True)
        (self.output / '.pinballctl-site-build').write_text('generated\n')
        (self.output / 'index.html').write_text('previous successful site')
        (self.output / 'stale.html').write_text('old page')
        (self.root / 'build/lib').mkdir(parents=True)
        (self.root / 'build/lib/package.txt').write_text('unrelated packaging output')
        patcher = patch.object(website_builder, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def render(self, destination):
        destination.mkdir()
        (destination / '.pinballctl-site-build').write_text('generated\n')
        (destination / 'index.html').write_text('replacement site')

    def assert_clean_workspace(self):
        self.assertEqual(list((self.root / 'build').iterdir()), [self.root / 'build/lib'])
        self.assertEqual((self.root / 'build/lib/package.txt').read_text(), 'unrelated packaging output')

    def test_success_validates_before_replacing_and_cleans_temporary_files(self):
        def validate(command, **kwargs):
            self.assertTrue(kwargs['check'])
            staged = Path(command[-1])
            self.assertTrue(staged.is_relative_to(self.root / 'build'))
            self.assertEqual((staged / 'index.html').read_text(), 'replacement site')
            self.assertEqual((self.output / 'index.html').read_text(), 'previous successful site')
        with patch.object(website_builder, 'render_site', side_effect=self.render), patch.object(website_builder.subprocess, 'run', side_effect=validate):
            website_builder.build_site(self.output)
        self.assertEqual((self.output / 'index.html').read_text(), 'replacement site')
        self.assertFalse((self.output / 'stale.html').exists())
        self.assert_clean_workspace()

    def test_render_or_validation_failure_keeps_previous_site(self):
        for phase in ('render', 'validate'):
            with self.subTest(phase=phase):
                def render(destination):
                    self.render(destination)
                    if phase == 'render':
                        raise ValueError('broken source')
                with patch.object(website_builder, 'render_site', side_effect=render), patch.object(website_builder.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'check-site')):
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        website_builder.build_site(self.output)
                self.assertEqual((self.output / 'index.html').read_text(), 'previous successful site')
                self.assertTrue((self.output / 'stale.html').exists())
                self.assert_clean_workspace()

    def test_failed_replacement_restores_previous_site(self):
        rename = Path.rename
        def fail_publish(source, destination):
            if source.parent.name.startswith('website-') and source.name == 'site':
                raise OSError('replacement failed')
            return rename(source, destination)
        with patch.object(website_builder, 'render_site', side_effect=self.render), patch.object(website_builder.subprocess, 'run'), patch.object(Path, 'rename', fail_publish):
            with self.assertRaisesRegex(OSError, 'replacement failed'):
                website_builder.build_site(self.output)
        self.assertEqual((self.output / 'index.html').read_text(), 'previous successful site')
        self.assert_clean_workspace()

    def test_sources_dist_root_and_unmarked_outputs_are_rejected(self):
        unrelated = self.root / 'dist/firmware'
        unrelated.mkdir()
        (unrelated / 'firmware.bin').write_bytes(b'preserve')
        for destination in (self.root, self.root / 'dist', self.root / 'website', unrelated):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                website_builder.build_site(destination)
        self.assertEqual((unrelated / 'firmware.bin').read_bytes(), b'preserve')
        self.assert_clean_workspace()


if __name__ == '__main__':
    unittest.main()
