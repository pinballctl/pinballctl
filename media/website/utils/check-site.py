#!/usr/bin/env python3
"""Check a generated Pages site, including temporary builds before promotion."""
import argparse
import json
import re
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

from PIL import Image

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]


def check_tree(root):
    if not (root / 'index.html').is_file():
        raise SystemExit('Build the site first.')
    broken = set()
    anchors = []
    page_ids = {}

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if values.get('id'):
                self.ids.add(values['id'])
            if values.get('srcset'):
                assert values.get('width') and values.get('height'), f'Missing dimensions: {self.file}'
                for candidate in values['srcset'].split(','):
                    image_url = candidate.strip().split()[0]
                    assert (root / image_url.lstrip('/')).is_file(), f'Missing responsive image: {image_url}'
            for key, value in attrs:
                if key not in ('href', 'src') or not value:
                    continue
                url = urlsplit(urljoin('/' + str(self.file.relative_to(root)), value))
                if url.netloc or url.scheme:
                    continue
                target = root / unquote(url.path).lstrip('/')
                if target.is_dir():
                    target = target / 'index.html'
                if not target.exists():
                    broken.add((str(self.file.relative_to(root)), value))
                elif url.fragment and target.suffix == '.html':
                    anchors.append((self.file, value, target.resolve(), unquote(url.fragment)))

    for file in root.rglob('*.html'):
        parser = Links()
        parser.file = file
        parser.ids = set()
        parser.feed(file.read_text())
        page_ids[file.resolve()] = parser.ids
    for source, link, target, fragment in anchors:
        if fragment not in page_ids.get(target, set()):
            broken.add((str(source.relative_to(root)), link))
    for file, link in sorted(broken):
        print(f'{file}: missing {link}')
    if broken:
        raise SystemExit(f'{len(broken)} broken local links in {root}')
    assert (root / '.nojekyll').is_file()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT / 'build/site', help='Generated site directory')
    site = parser.parse_args().site.resolve()
    check_tree(site)
    assert (site / 'CNAME').read_text().strip() == 'www.pinballctl.com'
    homepage = (site / 'index.html').read_text()
    assert '<link rel="icon" type="image/png" sizes="96x96" href="/assets/img/favicon.png">' in homepage
    with Image.open(site / 'assets/img/favicon.png') as favicon:
        assert favicon.format == 'PNG' and favicon.size == (96, 96)
        assert favicon.convert('RGBA').getpixel((0, 0)) == (9, 15, 23, 255)
    index = json.loads((site / 'search-index.json').read_text())
    urls = [row['url'] for row in index]
    assert len(urls) == len(set(urls)), 'Duplicate search URLs'
    sitemap = ElementTree.parse(site / 'sitemap.xml')
    namespace = {'map': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = sitemap.findall('map:url', namespace)
    assert [entry.findtext('map:loc', namespaces=namespace) for entry in entries] == [
        'https://www.pinballctl.com' + url for url in urls], 'Sitemap URLs must match the search index'
    for entry in entries:
        modified = entry.findtext('map:lastmod', namespaces=namespace)
        if modified is not None:
            assert date.fromisoformat(modified).isoformat() == modified, modified
    retired_hardware = '/features/hardware-mapping/'
    assert retired_hardware not in urls, 'Retired hardware page must not be indexed'
    redirect = (site / retired_hardware.lstrip('/') / 'index.html').read_text()
    assert '<meta http-equiv="refresh" content="0;url=/features/hardware/">' in redirect
    assert '<link rel="canonical" href="https://www.pinballctl.com/features/hardware/">' in redirect
    assert '<meta name="robots" content="noindex,follow">' in redirect
    assert 'href="/features/hardware/"' in redirect, 'Redirect needs a usable fallback link'
    retired_components = '/features/supported-components/'
    components_guide = '/docs/developer-guide/supported-components/'
    assert retired_components not in urls and components_guide in urls
    redirect = (site / retired_components.lstrip('/') / 'index.html').read_text()
    assert f'<meta http-equiv="refresh" content="0;url={components_guide}">' in redirect
    assert f'<link rel="canonical" href="https://www.pinballctl.com{components_guide}">' in redirect
    assert '<meta name="robots" content="noindex,follow">' in redirect
    assert f'href="{components_guide}"' in redirect
    for slug in ('audio-media', 'godot'):
        retired = f'/features/{slug}/'
        target = '/features/media/'
        assert retired not in urls and target in urls
        redirect = (site / retired.lstrip('/') / 'index.html').read_text()
        assert f'<meta http-equiv="refresh" content="0;url={target}">' in redirect
        assert f'<link rel="canonical" href="https://www.pinballctl.com{target}">' in redirect
        assert '<meta name="robots" content="noindex,follow">' in redirect
        assert f'href="{target}"' in redirect
    for url in urls:
        assert (site / url.lstrip('/') / 'index.html').is_file(), url
    # Check the metadata on every canonical page, not just the homepage.
    for url in urls:
        html = (site / url.lstrip('/') / 'index.html').read_text()
        graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))['@graph']
        page = graph[0]
        assert page['url'] == 'https://www.pinballctl.com' + url
        assert page['name'] and page['description']
        for node in graph:
            if node['@type'] == 'BreadcrumbList':
                items = node['itemListElement']
                assert len(items) >= 2
                assert [item['position'] for item in items] == list(range(1, len(items) + 1))
                assert items[-1]['item'] == page['url']
                for item in items:
                    assert item['item'].removeprefix('https://www.pinballctl.com') in urls
            if node['@type'] == 'ItemList':
                assert node['numberOfItems'] == len(node['itemListElement'])
                for item in node['itemListElement']:
                    assert item['url'].removeprefix('https://www.pinballctl.com') in urls
        if url == '/':
            assert any(node['@type'] == 'WebSite' and node['name'] == 'pinballCTL' for node in graph)
    navigation = json.loads((WEB / 'content/navigation.json').read_text())
    assert [group['title'] for group in navigation] == ['Overview and System', 'Authoring', 'Platform', 'Operations']
    module_urls = [url for group in navigation for _,url in group['links']]
    catalog = json.loads((WEB / 'content/features.json').read_text()) + json.loads((WEB / 'content/feature-details.json').read_text())
    assert len(module_urls) == len(set(module_urls)) == len(catalog)
    assert {f'/features/{feature["slug"]}/' for feature in catalog} == set(module_urls)
    tours = json.loads((WEB / 'content/feature-tours.json').read_text())
    for feature in catalog:
        slug = feature['slug']
        html = (site / f'features/{slug}/index.html').read_text()
        journey = re.search(r'<section class="tour-journey">.*?<ol>(.*?)</ol>', html, re.S)
        assert journey, f'Missing workflow: {slug}'
        steps = tours[slug]['steps']
        assert journey[1].count('<li>') == len(steps), f'Malformed workflow steps: {slug}'
        for step in steps:
            assert f'<h3>{escape(step["title"])}</h3>' in journey[1], f'Missing workflow heading: {slug}'
            assert f'<p>{escape(step["text"])}</p>' in journey[1], f'Missing workflow description: {slug}'
    assert '/features/events-system/' not in module_urls and '/features/events-system/' in urls
    for slug, target in [('rules-scoring','rule-editor'), ('diagnostics','performance'), ('live-view','playfield-layout')]:
        assert f'/features/{slug}/' not in urls
        redirect = (site / f'features/{slug}/index.html').read_text()
        assert f'content="0;url=/features/{target}/"' in redirect
        assert f'<link rel="canonical" href="https://www.pinballctl.com/features/{target}/">' in redirect
        assert 'noindex,follow' in redirect and f'href="/features/{target}/"' in redirect
    for category in navigation:
        for label, url in category['links']:
            assert url.startswith('/features/'), f'{label} must link to a marketing page'
            assert url in urls, url
    bookmarks = json.loads((site / 'docs/legacy-links.json').read_text())
    for target in bookmarks.values():
        assert urlsplit(target).path in urls, target
    # Manual reading paths, canonical corrections and legacy destinations.
    from docs_navigation import REDIRECTS, complete_navigation, navigation_links
    from docs_renderer import _scan_pages
    groups = json.loads((WEB / 'content/docs-navigation.json').read_text())
    assert [group['title'] for group in groups] == [
        'Getting Started', 'Features', 'Tutorials', 'Developer Guide']
    features = groups[1]['links']
    assert [group['title'] for group in features] == [
        'Connect & Configure', 'Build Your Game', 'Lights, Sound & Displays', 'Maintenance']
    dashboard = (site / 'docs/user-guide/dashboard/index.html').read_text()
    assert ('<details class="docs-nav-group" open><summary>Features</summary><div class="docs-nav-links">'
            '<details class="docs-nav-branch" open><summary>Connect &amp; Configure</summary>') in dashboard
    assert 'href="/docs/user-guide/dashboard/" aria-current="page"' in dashboard
    guide = groups[-1]
    guide_overview, *guide_submenus = guide['links']
    assert guide_overview == ['Overview', 'developer-guide/index']
    assert [item['title'] for item in guide_submenus] == [
        'Development & Releases', 'Architecture & APIs', 'Bridge, Firmware & Coil Safety',
        'Godot & Backglass', 'Test Bench & Hardware']
    components, test_bench, inventory = guide_submenus[-1]['links']
    assert components == ['Supported Components', 'developer-guide/supported-components']
    assert all(slug != components[1] for _, slug in navigation_links(features))
    assert test_bench['title'] == 'Test Bench'
    assert inventory == ['Hardware Inventory', 'developer-notes/hardware-inventory']
    assert guide_submenus[0]['links'][-1] == ['Website', 'developer-notes/website-and-search']
    assert 'developer-notes/index' not in {slug for _, slug in navigation_links([guide])}
    assert bookmarks['developer-notes/index'] == '/docs/developer-notes/test-bench/'
    welcome = (site / 'docs/index.html').read_text()
    assert '<h1>Your machine.<br>Your rules.<br>Your game.</h1>' in welcome
    assert 'aria-controls="documentation-subview"' in welcome
    assert 'Browse documentation ☰' not in welcome
    assert '<summary>Advanced Reference</summary>' not in welcome
    advanced = (site / 'docs/technical-notes/architecture/index.html').read_text()
    assert '<details class="docs-nav-group" open><summary>Developer Guide</summary>' in advanced
    assert '<details class="docs-nav-branch" open><summary>Architecture &amp; APIs</summary>' in advanced
    assert bookmarks['technical-notes/index'] == '/docs/technical-notes/'
    assert bookmarks['technical-notes/readme'] == '/docs/technical-notes/'
    overview = (site / 'docs/technical-notes/index.html').read_text()
    assert '<h1 id="system-overview">System Overview</h1>' in overview
    assert 'id="technical-notes"' in overview
    assert 'href="/docs/technical-notes/coil-safety/"' in overview
    coil_safety = (site / 'docs/technical-notes/coil-safety/index.html').read_text()
    assert '<h1 id="coil-safety">Coil Safety</h1>' in coil_safety
    for group in groups:
        assert escape(group['title']) in welcome
        for label, slug in navigation_links([group]):
            target = bookmarks[slug]
            assert target in urls
            assert f'>{escape(label)}</a>' in welcome
    ordered_pages = list(navigation_links(complete_navigation(groups, _scan_pages(WEB / 'docs'))))
    for index, (_, slug) in enumerate(ordered_pages):
        target = bookmarks[slug]
        html = (site / target.lstrip('/') / 'index.html').read_text()
        navigation = re.findall(r'<nav class="topic-navigation" aria-label="Documentation pages">.*?</nav>', html)
        assert len(navigation) == 1, target
        expected = []
        for adjacent, rel, direction in ((index - 1, 'prev', 'Previous'), (index + 1, 'next', 'Next')):
            if 0 <= adjacent < len(ordered_pages):
                label, neighbour = ordered_pages[adjacent]
                expected.append((rel, escape(bookmarks[neighbour], quote=True), direction, escape(label)))
        actual = re.findall(r'<a rel="(prev|next)" href="([^"]+)"><span>(Previous|Next)</span>(.*?)</a>', navigation[0])
        assert actual == expected, (target, actual, expected)
    bench = (site / 'docs/developer-notes/test-bench/index.html').read_text()
    assert '<details class="docs-nav-group" open><summary>Developer Guide</summary>' in bench
    assert '<details class="docs-nav-branch" open><summary>Test Bench &amp; Hardware</summary>' in bench
    assert '<details class="docs-nav-branch" open><summary>Test Bench</summary>' in bench
    assert '<span class="eyebrow">Developer Guide</span>' in bench
    assert 'id="how-the-ball-course-works"' in bench
    assert 'data-parts-checklist' not in bench
    assert 'data-section-redirect href="/docs/developer-notes/test-bench/shopping-list/#amazoncouk-shopping-list"' in bench
    assert not (site / 'docs/developer-notes/test-bench/construction/index.html').exists()
    for slug in ('wiring', 'interface-board', 'power', 'shopping-list'):
        url = f'/docs/developer-notes/test-bench/{slug}/'
        assert url in urls
        html = (site / url.lstrip('/') / 'index.html').read_text()
        assert f'href="{url}" aria-current="page"' in html
    shopping = (site / 'docs/developer-notes/test-bench/shopping-list/index.html').read_text()
    assert 'data-parts-checklist="test-bench"' in shopping
    assert 'data-parts-shop' in shopping
    assert 'data-parts-shopping-items' in shopping
    assert 'gp/aws/cart/add.html' not in shopping
    assert 'href="#selected-shopping-heading"' not in shopping
    for old, target in REDIRECTS.items():
        assert old not in urls
        html = (site / old.lstrip('/') / 'index.html').read_text()
        assert f'content="0;url={target}"' in html
        assert f'href="https://www.pinballctl.com{urlsplit(target).path}"' in html
        assert 'noindex,follow' in html
    assert bookmarks['1-user-guide/19-integraty-check'] == '/docs/user-guide/integrity-check/'
    assert bookmarks['1-user-guide/3-featured'] == '/docs/#feature-guides'
    # Source moves must preserve old bookmarks and deep links.
    previous = json.loads((WEB / 'content/docs-legacy.json').read_text())
    for slug, target in previous.items():
        assert bookmarks[slug] == target, slug
    assert not list((site / 'docs').rglob('*.pyc'))
    assert not list((site / 'docs/media').glob('*.json'))
    assert not list((site / 'docs/media').glob('*.prompt.txt'))
    for file in (site / 'docs').rglob('*.html'):
        assert not re.search(r'\[\[(?:DOCS|DEVELOPER)_', file.read_text()), file
    print(f'Validated {len(urls)} searchable pages, local links and the Pages site.')


if __name__ == '__main__':
    main()
