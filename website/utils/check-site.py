#!/usr/bin/env python3
"""Check the generated Pages artifacts without third-party dependencies."""
import json
import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def check_tree(root):
    if not (root / 'index.html').is_file():
        raise SystemExit('Build the site first.')
    broken = set()

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
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

    for file in root.rglob('*.html'):
        parser = Links()
        parser.file = file
        parser.feed(file.read_text())
    for file, link in sorted(broken):
        print(f'{file}: missing {link}')
    if broken:
        raise SystemExit(f'{len(broken)} broken local links in {root}')
    assert (root / '.nojekyll').is_file()


def main():
    site = ROOT / 'dist/site'
    holding = ROOT / 'dist/docs-holding'
    check_tree(site)
    check_tree(holding)
    assert (site / 'CNAME').read_text().strip() == 'www.pinballctl.com'
    assert (holding / 'CNAME').read_text().strip() == 'docs.pinballctl.com'
    index = json.loads((site / 'search-index.json').read_text())
    urls = [row['url'] for row in index]
    assert len(urls) == len(set(urls)), 'Duplicate search URLs'
    retired_hardware = '/features/hardware-mapping/'
    assert retired_hardware not in urls, 'Retired hardware page must not be indexed'
    redirect = (site / retired_hardware.lstrip('/') / 'index.html').read_text()
    assert '<meta http-equiv="refresh" content="0;url=/features/hardware/">' in redirect
    assert '<link rel="canonical" href="https://www.pinballctl.com/features/hardware/">' in redirect
    assert '<meta name="robots" content="noindex,follow">' in redirect
    assert 'href="/features/hardware/"' in redirect, 'Redirect needs a usable fallback link'
    retired_components = '/features/supported-components/'
    components_guide = '/docs/user-guide/supported-components/'
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
    navigation = json.loads((ROOT / 'website/content/navigation.json').read_text())
    assert [group['title'] for group in navigation] == ['Overview and System', 'Authoring', 'Platform', 'Operations']
    module_urls = [url for group in navigation for _,url in group['links']]
    catalog = json.loads((ROOT / 'website/content/features.json').read_text()) + json.loads((ROOT / 'website/content/feature-details.json').read_text())
    assert len(module_urls) == len(set(module_urls)) == len(catalog)
    assert {f'/features/{feature["slug"]}/' for feature in catalog} == set(module_urls)
    tours = json.loads((ROOT / 'website/content/feature-tours.json').read_text())
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
    for slug, target in [('rules-scoring','rule-editor'), ('diagnostics','performance')]:
        assert f'/features/{slug}/' not in urls
        redirect = (site / f'features/{slug}/index.html').read_text()
        assert f'content="0;url=/features/{target}/"' in redirect
        assert f'<link rel="canonical" href="https://www.pinballctl.com/features/{target}/">' in redirect
        assert 'noindex,follow' in redirect and f'href="/features/{target}/"' in redirect
    for category in navigation:
        for label, url in category['links']:
            assert url.startswith('/features/'), f'{label} must link to a marketing page'
            assert url in urls, url
    legacy = json.loads((holding / 'legacy-links.json').read_text())
    for target in legacy['paths'].values():
        assert target in urls, target
    print(f'Validated {len(urls)} searchable pages, local links and both Pages artifacts.')


if __name__ == '__main__':
    main()
