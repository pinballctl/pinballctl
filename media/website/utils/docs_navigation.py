"""Render the manual hierarchy without tying reading order to source filenames."""
from html import escape

REDIRECTS = {
    '/docs/developer-notes/backglass-motion/': '/docs/user-guide/godot/',
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
    '/docs/user-guide/events/': '/docs/user-guide/logs/#find-and-inspect-an-event',
    '/docs/user-guide/rules-wizards/': '/docs/user-guide/rules/#rules-wizard',
    '/docs/user-guide/live-view/': '/docs/user-guide/layout/#live-view',
    '/docs/user-guide/quick-start/': '/docs/user-guide/getting-started/#quick-start',
    '/docs/user-guide/integraty-check/': '/docs/user-guide/integrity-check/',
    '/docs/user-guide/supported-components/': '/docs/developer-guide/supported-components/',
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


def reading_groups(groups):
    """Yield groups that supply a topic title for breadcrumbs."""
    for group in groups:
        if group.get('reading_order'):
            yield group
        yield from reading_groups(item for item in group['links'] if isinstance(item, dict))


def complete_navigation(groups, pages):
    """Append unlisted pages in the same order as the sidebar."""
    listed = {slug for _, slug in navigation_links(groups)}
    additional = [[page['title'], page['slug']] for page in pages if page['slug'] not in listed]
    return [*groups, {'title': 'Additional guides', 'links': additional}] if additional else groups


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

    return ''.join(render_group(group)[0] for group in complete_navigation(groups, pages))


def topic_navigation(links, mapping, current_slug):
    """Link to the pages immediately before and after this page in the menu."""
    index = next(i for i, (_, slug) in enumerate(links) if slug == current_slug)
    adjacent = []
    for target, direction, relation in ((index - 1, 'Previous', 'prev'), (index + 1, 'Next', 'next')):
        if 0 <= target < len(links):
            label, slug = links[target]
            adjacent.append(f'<a rel="{relation}" href="{escape(mapping[slug], quote=True)}">'
                            f'<span>{direction}</span>{escape(label)}</a>')
    if not adjacent:
        return ''
    return f'<nav class="topic-navigation" aria-label="Documentation pages"><div>{"".join(adjacent)}</div></nav>'
