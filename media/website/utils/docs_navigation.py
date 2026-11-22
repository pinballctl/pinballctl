"""Render the manual hierarchy without tying reading order to source filenames."""
from html import escape

REDIRECTS = {
    '/docs/developer-notes/test-bench-enclosure-study/': '/docs/developer-notes/test-bench/',
    '/docs/developer-notes/': '/docs/developer-notes/test-bench/',
    '/docs/developer-log/': '/docs/developer-notes/test-bench/',
    '/docs/developer-log/2026-10-17-repository-consolidation/': '/docs/developer-notes/test-bench/',
    '/docs/developer-log/2026-11-18-documentation-home/': '/docs/developer-notes/website-and-search/',
    '/docs/developer-log/tags/website/': '/docs/developer-notes/website-and-search/',
    '/docs/developer-log/tags/documentation/': '/docs/developer-notes/website-and-search/',
    '/docs/developer-log/tags/repository/': '/docs/developer-notes/test-bench/',
    '/docs/developer-log/tags/backglass/': '/docs/developer-guide/backglass/',
    '/docs/developer-guide/writing-the-log/': '/docs/developer-notes/test-bench/',
    '/docs/developer-guide/website/': '/docs/developer-notes/website-and-search/',
    '/docs/build-notes/test-bench/': '/docs/developer-notes/test-bench/',
    '/docs/changelog/': '/docs/developer-guide/releases/',
    '/docs/technical-notes/readme/': '/docs/technical-notes/',
    '/docs/technical-notes/esp-plan/': '/docs/technical-notes/',
    '/docs/user-guide/live-view/': '/docs/user-guide/layout/#live-view',
    '/docs/user-guide/quick-start/': '/docs/user-guide/getting-started/#quick-start',
    '/docs/user-guide/integraty-check/': '/docs/user-guide/integrity-check/',
    '/docs/user-guide/hardware-inventory/': '/docs/developer-notes/hardware-inventory/',
    '/docs/user-guide/featured/': '/docs/#feature-guides',
}


def navigation_links(groups):
    """Yield leaves in reading order, including nested topic groups."""
    for group in groups:
        for item in group['links']:
            if isinstance(item, dict):
                yield from navigation_links([item])
            else:
                yield item


def sidebar(groups, pages, mapping, current_slug):
    available = {page['slug']: page for page in pages}
    used = set()

    def render_group(group, nested=False):
        links = []
        active = False
        for item in group['links']:
            if isinstance(item, dict):
                markup, child_active = render_group(item, nested=True)
                links.append(markup)
                active = active or child_active
                continue
            label, slug = item
            if slug not in available:
                raise ValueError(f'Documentation navigation source missing: {slug}')
            if slug in used:
                raise ValueError(f'Duplicate documentation navigation source: {slug}')
            used.add(slug)
            current = slug == current_slug
            active = active or current
            links.append(f'<a href="{escape(mapping[slug], quote=True)}"' +
                         (' aria-current="page"' if current else '') +
                         f'>{escape(label)}</a>')
        css = 'docs-nav-branch' if nested else 'docs-nav-group'
        return (f'<details class="{css}"' + (' open' if active else '') +
                f'><summary>{escape(group["title"])}</summary><div class="docs-nav-links">' +
                ''.join(links) + '</div></details>', active)

    sections = [render_group(group)[0] for group in groups]
    extra = [p for p in pages if p['slug'] not in used]
    if extra:
        sections.append(render_group({'title': 'Additional guides', 'links': [
            [p['title'], p['slug']] for p in extra]})[0])
    return ''.join(sections)


def topic_navigation(groups, mapping, current_slug):
    """Add adjacent-page links within an authored topic group."""
    for group in groups:
        for item in group['links']:
            if not isinstance(item, dict):
                continue
            links = list(navigation_links([item]))
            slugs = [slug for _, slug in links]
            if current_slug not in slugs:
                continue
            index = slugs.index(current_slug)
            adjacent = []
            for target, direction in ((index - 1, 'Previous'), (index + 1, 'Next')):
                if 0 <= target < len(links):
                    label, slug = links[target]
                    adjacent.append(f'<a href="{escape(mapping[slug], quote=True)}"><span>{direction}</span>{escape(label)}</a>')
            return f'<nav class="topic-navigation" aria-label="{escape(item["title"], quote=True)} pages"><div>{"".join(adjacent)}</div></nav>'
    return ''
