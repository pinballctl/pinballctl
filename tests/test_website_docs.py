"""Regression checks for documentation links and validated website builds."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'media/website/utils'))
import docs_renderer
from docs_navigation import sidebar, topic_navigation
from search_metadata import breadcrumbs

spec = importlib.util.spec_from_file_location('website_builder', Path(__file__).resolve().parents[1] / 'media/website/utils/build-site.py')
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


class DocumentationNavigationTests(unittest.TestCase):
    def setUp(self):
        self.groups = [{'title': 'Notes', 'links': [
            ['Other', 'other'], {'title': 'Test Bench', 'links': [
                ['Course', 'bench'], ['Wiring', 'bench/wiring'], ['Checks', 'bench/checks']]}]}]
        self.pages = [{'slug': slug, 'title': slug} for slug in ('other', 'bench', 'bench/wiring', 'bench/checks')]
        self.mapping = {page['slug']: '/docs/' + page['slug'] + '/' for page in self.pages}

    def test_current_page_opens_ancestors_without_duplicating_links(self):
        html = sidebar(self.groups, self.pages, self.mapping, 'bench/wiring')
        self.assertIn('<details class="docs-nav-group" open>', html)
        self.assertIn('<details class="docs-nav-branch" open>', html)
        self.assertEqual(html.count('aria-current="page"'), 1)
        for url in self.mapping.values():
            self.assertEqual(html.count(f'href="{url}"'), 1)
        self.assertNotIn(' open', sidebar(self.groups, self.pages, self.mapping, ''))

    def test_nested_missing_and_duplicate_sources_fail(self):
        self.groups[0]['links'][1]['links'].append(['Duplicate', 'other'])
        with self.assertRaisesRegex(ValueError, 'Duplicate documentation'):
            sidebar(self.groups, self.pages, self.mapping, 'bench')
        self.groups[0]['links'][1]['links'][-1] = ['Missing', 'missing']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            sidebar(self.groups, self.pages, self.mapping, 'bench')

    def test_adjacent_pages_follow_topic_order_and_stop_at_ends(self):
        middle = topic_navigation(self.groups, self.mapping, 'bench/wiring')
        self.assertIn('href="/docs/bench/"', middle)
        self.assertIn('href="/docs/bench/checks/"', middle)
        self.assertNotIn('Previous', topic_navigation(self.groups, self.mapping, 'bench'))
        self.assertNotIn('Next', topic_navigation(self.groups, self.mapping, 'bench/checks'))
        self.assertEqual(topic_navigation(self.groups, self.mapping, 'other'), '')

    def test_breadcrumbs_include_only_real_parent_pages(self):
        trail = breadcrumbs('/docs/notes/bench/wiring/', 'Wiring', [], {
            '/docs/notes/bench/': 'Test Bench',
        })
        self.assertEqual(trail, [('Home', '/'), ('Documentation', '/docs/'),
                                ('Test Bench', '/docs/notes/bench/'),
                                ('Wiring', '/docs/notes/bench/wiring/')])


class WebsiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.output = self.root / 'build/site'
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
        self.assertEqual(set((self.root / 'build').iterdir()), {self.output, self.root / 'build/lib'})
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

    def test_default_build_validates_and_discards_its_output(self):
        def validate(command, **kwargs):
            self.assertTrue(kwargs['check'])
            self.assertEqual((Path(command[-1]) / 'index.html').read_text(), 'replacement site')
        with patch.object(website_builder, 'render_site', side_effect=self.render), patch.object(website_builder.subprocess, 'run', side_effect=validate):
            website_builder.build_site()
        self.assertEqual((self.output / 'index.html').read_text(), 'previous successful site')
        self.assertFalse((self.root / 'dist').exists())
        self.assert_clean_workspace()

    def test_default_failed_build_cleans_partial_output(self):
        for phase in ('render', 'validate'):
            with self.subTest(phase=phase):
                def render(destination):
                    self.render(destination)
                    if phase == 'render':
                        raise ValueError('broken source')
                with patch.object(website_builder, 'render_site', side_effect=render), patch.object(website_builder.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'check-site')):
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        website_builder.build_site()
                self.assert_clean_workspace()

    def test_preview_files_exist_while_serving_and_are_cleaned_afterwards(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted):
                def preview(site, port):
                    self.assertEqual(port, 8090)
                    self.assertEqual((site / 'index.html').read_text(), 'replacement site')
                    if interrupted:
                        raise KeyboardInterrupt()
                with patch.object(website_builder, 'render_site', side_effect=self.render), patch.object(website_builder.subprocess, 'run'), patch.object(website_builder, 'serve_preview', side_effect=preview):
                    if interrupted:
                        with self.assertRaises(KeyboardInterrupt):
                            website_builder.build_site(preview_port=8090)
                    else:
                        website_builder.build_site(preview_port=8090)
                self.assert_clean_workspace()

    def test_retained_output_and_preview_cannot_be_combined(self):
        with self.assertRaises(ValueError):
            website_builder.build_site(self.output, preview_port=8090)
        self.assert_clean_workspace()

    def test_sources_build_root_dist_and_unmarked_outputs_are_rejected(self):
        unrelated = self.root / 'dist/firmware'
        unrelated.mkdir(parents=True)
        (unrelated / 'firmware.bin').write_bytes(b'preserve')
        for destination in (self.root, self.root / 'build', self.root / 'dist/site', self.root / 'website', unrelated, self.root / 'build/lib'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                website_builder.build_site(destination)
        self.assertEqual((unrelated / 'firmware.bin').read_bytes(), b'preserve')
        self.assert_clean_workspace()


if __name__ == '__main__':
    unittest.main()
