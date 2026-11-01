"""Render the manual hierarchy without tying reading order to source filenames."""
from html import escape

REDIRECTS = {
    '/docs/user-guide/integraty-check/': '/docs/user-guide/integrity-check/',
    '/docs/user-guide/featured/': '/docs/#feature-guides',
}


def sidebar(groups, pages, mapping, current_slug):
    available = {page['slug']: page for page in pages}
    used = set()
    sections = []
    for group in groups:
        links = []
        active = False
        for label, slug in group['links']:
            if slug not in available:
                raise ValueError(f'Documentation navigation source missing: {slug}')
            if slug in used:
                raise ValueError(f'Duplicate documentation navigation source: {slug}')
            used.add(slug)
            current = slug == current_slug
            active |= current
            links.append(f'<a href="{escape(mapping[slug], quote=True)}"' +
                         (' aria-current="page"' if current else '') +
                         f'>{escape(label)}</a>')
        title = escape(group['title'])
        if group.get('advanced'):
            sections.append(f'<details class="docs-advanced"' + (' open' if active else '') +
                            f'><summary>{title}</summary>' + ''.join(links) + '</details>')
        else:
            sections.append(f'<h2>{title}</h2>' + ''.join(links))
    extra = [p for p in pages if p['slug'] not in used and
             p['slug'] != '1-user-guide/3-featured']
    if extra:
        sections.append('<h2>Additional guides</h2>' + ''.join(
            f'<a href="{escape(mapping[p["slug"]], quote=True)}"' +
            (' aria-current="page"' if p['slug'] == current_slug else '') +
            f'>{escape(p["title"])}</a>' for p in extra))
    return ''.join(sections)
