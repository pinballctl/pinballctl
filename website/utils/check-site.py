#!/usr/bin/env python3
"""Check the generated Pages artifacts without third-party dependencies."""
import json
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
    for url in urls:
        assert (site / url.lstrip('/') / 'index.html').is_file(), url
    navigation = json.loads((ROOT / 'website/content/navigation.json').read_text())
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
