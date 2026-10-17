"""Accurate search metadata derived from the site's visible navigation."""
from html import escape
import re


def breadcrumbs(path, title, navigation):
    if path == '/':
        return []
    labels = {url: label for group in navigation for label, url in group['links']}
    trail = [('Home', '/')]
    if path.startswith('/features/') and path != '/features/':
        trail.append(('Features', '/features/'))
    elif path.startswith('/docs/') and path != '/docs/':
        trail.append(('Documentation', '/docs/'))
    trail.append((labels.get(path, 'Documentation' if path == '/docs/' else title), path))
    return trail


def breadcrumb_html(trail):
    parts = [f'<a href="{escape(url, quote=True)}">{escape(label)}</a>' for label, url in trail[:-1]]
    parts.append(f'<span aria-current="page">{escape(trail[-1][0])}</span>')
    return '<nav class="breadcrumbs page-breadcrumbs" aria-label="Breadcrumb">' + ' / '.join(parts) + '</nav>'


def structured_data(domain, path, title, description, image, navigation, noindex=False):
    url = domain + path
    site_id = domain + '/#website'
    page = {'@type': 'CollectionPage' if path in ('/features/', '/docs/') else 'WebPage',
            '@id': url + '#webpage', 'url': url, 'name': title, 'description': description,
            'inLanguage': 'en', 'isPartOf': {'@id': site_id},
            'primaryImageOfPage': {'@type': 'ImageObject', 'url': image}}
    graph = [page]
    if path == '/':
        graph.append({'@type': 'WebSite', '@id': site_id, 'url': domain + '/',
                      'name': 'pinballCTL', 'alternateName': ['Pinball CTL', 'pinballctl'],
                      'description': description, 'inLanguage': 'en'})
    trail = breadcrumbs(path, title, navigation)
    if trail and not noindex:
        crumb_id = url + '#breadcrumbs'
        page['breadcrumb'] = {'@id': crumb_id}
        graph.append({'@type': 'BreadcrumbList', '@id': crumb_id, 'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'name': label, 'item': domain + link}
            for i, (label, link) in enumerate(trail, 1)]})
    if path == '/features/':
        page['mainEntity'] = []
        for group in navigation:
            ident = url + '#' + re.sub('[^a-z0-9]+', '-', group['title'].lower()).strip('-')
            page['mainEntity'].append({'@id': ident})
            graph.append({'@type': 'ItemList', '@id': ident, 'name': group['title'],
                          'numberOfItems': len(group['links']), 'itemListElement': [
                              {'@type': 'ListItem', 'position': i, 'name': label, 'url': domain + link}
                              for i, (label, link) in enumerate(group['links'], 1)]})
    return {'@context': 'https://schema.org', '@graph': graph}
