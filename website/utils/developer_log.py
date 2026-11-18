"""Dated development notes with static topic pages and explicit related entries."""
from datetime import date
from html import escape
import json
import re


def tag_url(tag):
    return f'/docs/developer-log/tags/{tag}/'


def load_entries(path, pages, mapping):
    pages_by_slug = {page['slug']: page for page in pages}
    entries = json.loads(path.read_text())
    ids = set()
    slugs = set()
    for entry in entries:
        ident = entry['id']
        slug = entry['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', ident) or ident in ids:
            raise ValueError(f'Invalid or duplicate developer log ID: {ident}')
        ids.add(ident)
        if slug in slugs or slug not in pages_by_slug:
            raise ValueError(f'Missing or duplicate developer log source: {slug}')
        slugs.add(slug)
        day = date.fromisoformat(entry['date'])
        if entry['date'] != day.isoformat() or slug != f'developer-log/{day.isoformat()}-{ident}':
            raise ValueError(f'Developer log filename/date mismatch: {slug}')
        tags = entry['tags']
        if not tags or len(tags) != len(set(tags)) or any(
            not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', tag) for tag in tags
        ):
            raise ValueError(f'Invalid developer log tags: {ident}')
        if not entry.get('summary', '').strip():
            raise ValueError(f'Missing developer log summary: {ident}')
        entry['title'] = pages_by_slug[slug]['title']
        entry['url'] = mapping[slug]
        entry['date_label'] = f'{day.day} {day:%B %Y}'
    authored = {slug for slug in pages_by_slug if slug.startswith('developer-log/') and slug != 'developer-log/index'}
    if authored != slugs:
        raise ValueError(f'Developer log metadata/source mismatch: {authored ^ slugs}')
    for entry in entries:
        related = entry.get('related', [])
        if len(related) != len(set(related)) or any(ident not in ids or ident == entry['id'] for ident in related):
            raise ValueError(f'Invalid related developer log entry: {entry["id"]}')
    return sorted(entries, key=lambda entry: (entry['date'], entry['id']), reverse=True)


def tags_html(tags):
    return '<ul class="devlog-tags" aria-label="Topics">' + ''.join(
        f'<li><a href="{tag_url(tag)}">{escape(tag.replace("-", " "))}</a></li>' for tag in tags
    ) + '</ul>'


def overview(entries):
    return '<div class="devlog-list">' + ''.join(
        f'<section class="devlog-entry"><time datetime="{entry["date"]}">{entry["date_label"]}</time>'
        f'<h2><a href="{entry["url"]}">{escape(entry["title"])}</a></h2>'
        f'<p>{escape(entry["summary"])}</p>{tags_html(entry["tags"])}</section>'
        for entry in entries
    ) + '</div>'


def entry_details(entry, entries):
    by_id = {item['id']: item for item in entries}
    related = [by_id[ident] for ident in entry.get('related', [])]
    metadata = f'<div class="devlog-meta"><time datetime="{entry["date"]}">{entry["date_label"]}</time>{tags_html(entry["tags"])}</div>'
    links = ''.join(f'<li><a href="{item["url"]}">{escape(item["title"])}</a></li>' for item in related)
    footer = f'<aside class="docs-next"><h2>Related entries</h2><ul>{links}</ul></aside>' if links else ''
    return metadata, footer
