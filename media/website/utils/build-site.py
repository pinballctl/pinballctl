#!/usr/bin/env python3
"""Build and validate in build/, cleaning temporary website files afterwards."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from html import escape as e, unescape
from urllib.parse import urlsplit, unquote
import argparse, hashlib, json, re, shutil, subprocess, sys, tempfile
sys.dont_write_bytecode = True
from feature_pages import render_feature, picture, CAPTIONS, zoom_icon
from benefit_art import illustration
from responsive_images import responsive_images
from sitemap_dates import SitemapDates
from search_metadata import breadcrumbs, breadcrumb_html, structured_data
from docs_navigation import REDIRECTS, reading_groups, sidebar as docs_sidebar, topic_navigation
import docs_renderer as docs
from docs_renderer import doc_url

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]
DOMAIN = 'https://www.pinballctl.com'
FEATURES = json.loads((WEB / 'content/features.json').read_text())
# Content-based URLs prevent browsers retaining styles from an earlier build.
CSS_VERSION = hashlib.sha256((WEB / 'assets/css/site.css').read_bytes()).hexdigest()[:12]
JS_VERSION = hashlib.sha256((WEB / 'assets/js/site.js').read_bytes()).hexdigest()[:12]
NAVIGATION = json.loads((WEB / 'content/navigation.json').read_text())
DOC_GROUPS = json.loads((WEB / 'content/docs-navigation.json').read_text())
DOC_PAGES = docs._scan_pages(WEB / 'docs')
DOC_MAPPING = {page['slug']: doc_url(page['slug']) for page in DOC_PAGES}
DOC_TITLES = {DOC_MAPPING[page['slug']]: page['title'] for page in DOC_PAGES}
for group in reading_groups(DOC_GROUPS):
    DOC_TITLES[DOC_MAPPING[group['links'][0][1]]] = group['title']
SEARCH = []
URLS = {}

def nav(path):
    categories=json.loads((WEB/'content/navigation.json').read_text())
    groups=[]
    for category in categories:
        links=''.join(f'<a href="{e(url,quote=True)}">{e(label)}</a>' for label,url in category['links'])
        intro = f'<p>{e(category["intro"])}</p>' if category.get('intro') else ''
        groups.append(f'<section class="feature-menu-group"><h2>{e(category["title"])}</h2>{intro}{links}</section>')
    menu='<div class="wrap feature-menu-grid">'+''.join(groups)+'</div><div class="feature-menu-footer wrap"><a href="/features/">Explore all features →</a><a href="/start-building/">New here? Start building →</a></div>'
    current_slug = next((slug for slug, url in DOC_MAPPING.items() if url == path), '')
    documentation = docs_sidebar(DOC_GROUPS, DOC_PAGES, DOC_MAPPING, current_slug)
    docs_menu = f'<details class="documentation-dropdown"><summary aria-controls="documentation-subview" aria-expanded="false">Documentation</summary><div class="documentation-menu nav-subview" id="documentation-subview"><div class="feature-subview-header"><button type="button" class="documentation-back">← Back</button><h2>Documentation</h2></div><div class="documentation-menu-content"><a class="documentation-home" href="/docs/">Documentation home →</a>{documentation}</div></div></details>'
    return f'''<a class="skip" href="#main">Skip to content</a><header class="site-header"><div class="wrap header-inner"><a class="brand" href="/" aria-label="Pinball CTL home"><img class="brand-mark" src="/assets/img/brand-mark.svg" alt="" width="36" height="36"><span class="brand-wordmark">pinball<span class="brand-suffix">CTL</span></span></a><button class="search-trigger" data-search-open aria-label="Search site" title="Search site"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg></button><button class="menu-toggle" aria-controls="site-nav" aria-expanded="false">Menu ☰</button><nav class="nav" id="site-nav" aria-label="Main navigation"><div class="nav-primary"><details class="features-dropdown"><summary aria-controls="feature-subview" aria-expanded="false">Features</summary><div class="feature-menu nav-subview" id="feature-subview"><div class="feature-subview-header"><button type="button" class="features-back">← Back</button><h2>Features</h2></div>{menu}</div></details><a class="documentation-link" href="/docs/">Documentation</a>{docs_menu}<a href="https://github.com/pinballctl/pinballctl" data-track="github" target="_blank" rel="noopener noreferrer">GitHub ↗</a><a class="nav-cta" href="/start-building/" data-track="get_started">Start building →</a></div></nav></div></header><div class="menu-backdrop" hidden aria-hidden="true"></div>'''

def shell(title, desc, path, body, section='Website', noindex=False):
    canonical=DOMAIN+path
    social_image=DOMAIN+'/assets/img/dashboard.webp'
    image_match=re.search(r'<img[^>]+src="(/assets/img/(?:tour-|feature-)[^"]+)"',body)
    if image_match: social_image=DOMAIN+image_match[1]
    extra_scripts='<script defer src="/docs/assets/js/components.js"></script>' if 'project-cost-summary-table' in body else ''
    structured=structured_data(DOMAIN,path,title,desc,social_image,NAVIGATION,noindex,doc_titles=DOC_TITLES)
    trail = ''
    if path != '/' and not noindex:
        width_toggle = ''
        if section == 'Documentation':
            width_toggle = '<button class="docs-width-toggle" type="button" data-docs-width-toggle aria-label="Full-width documentation" aria-pressed="false" title="Use full-width documentation" hidden><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="docs-width-expand" d="M8 8 4 12l4 4M4 12h16m-4-4 4 4-4 4"/><path class="docs-width-contract" d="m3 8 4 4-4 4m4-4H1m20-4-4 4 4 4m-4-4h6"/></svg></button>'
        trail_class = 'wrap breadcrumb-wrap docs-breadcrumb-wrap' if width_toggle else 'wrap breadcrumb-wrap'
        trail = f'<div class="{trail_class}">' + breadcrumb_html(breadcrumbs(path,title,NAVIGATION,doc_titles=DOC_TITLES)) + width_toggle + '</div>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | Pinball CTL</title><meta name="description" content="{e(desc,quote=True)}"><link rel="canonical" href="{canonical}"><meta name="robots" content="{'noindex,follow' if noindex else 'index,follow,max-image-preview:large'}"><meta name="theme-color" content="#090f17"><link rel="icon" type="image/png" sizes="96x96" href="/assets/img/favicon.png"><meta property="og:type" content="website"><meta property="og:title" content="{e(title,quote=True)}"><meta property="og:description" content="{e(desc,quote=True)}"><meta property="og:url" content="{canonical}"><meta property="og:image" content="{social_image}"><meta property="og:site_name" content="pinballCTL"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title,quote=True)}"><meta name="twitter:description" content="{e(desc,quote=True)}"><meta name="twitter:image" content="{social_image}"><link rel="stylesheet" href="/assets/css/site.css?v={CSS_VERSION}"><script defer src="/assets/js/site.js?v={JS_VERSION}"></script>{extra_scripts}<script type="application/ld+json">{json.dumps(structured).replace('<','\\u003c')}</script></head><body data-section="{section}">{nav(path)}{trail}{body}<div class="development-ribbon"><a href="/in-development/" aria-label="In Development: project status and how to help">In Development</a></div><footer class="footer"><div class="wrap footer-inner"><div><a class="brand" href="/"><img class="brand-mark" src="/assets/img/brand-mark.svg" alt="" width="36" height="36"><span class="brand-wordmark">pinball<span class="brand-suffix">CTL</span></span></a><p>Your machine. Your rules. Your game.</p><p>Built for homebrew pinball. Raspberry Pi + ESP32-S3.</p></div><div class="footer-links"><a href="/docs/">Documentation</a><a href="/contact/">Contact</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a><button class="settings-link" data-cookie-settings>Cookie settings</button></div></div></footer><dialog class="search-dialog" aria-labelledby="search-title"><div class="search-top"><h2 id="search-title">Find your next step.</h2><button class="close" data-search-close aria-label="Close search">✕</button></div><label for="site-search">Search features and documentation</label><input class="search-input" id="site-search" type="search" autocomplete="off" placeholder="Try lighting, coils or scoring…"><label class="search-scope"><input type="checkbox" id="search-docs-only"> Docs only</label><p class="search-meta" role="status" data-search-status>Type to search the site.</p><ul class="search-results"></ul></dialog><dialog class="image-dialog" aria-label="Screenshot preview"><div class="image-toolbar"><div class="image-zoom-controls" role="group" aria-label="Screenshot zoom"><button class="close" data-image-zoom-out aria-label="Zoom out">−</button><output data-image-zoom-level aria-label="Zoom level">Fit</output><button class="close" data-image-zoom-in aria-label="Zoom in">+</button></div><button class="close" data-image-close aria-label="Close image" autofocus>Close ✕</button></div><div class="image-scroll" tabindex="0" role="region" aria-label="Scrollable screenshot"><img alt=""></div></dialog><aside class="consent" aria-label="Analytics preferences" hidden><strong>A little insight helps us improve.</strong><p>Google Analytics is enabled by default to measure page visits and feature interest. You can turn it off and still browse and search. <a href="/privacy/">Privacy details</a></p><button data-consent="yes">Keep analytics enabled</button><button data-consent="no">Turn analytics off</button></aside></body></html>'''

def write(out,history,path,title,desc,body,section='Website',plain=None,noindex=False,*,sources=(),record_dates=()):
    dest=out/path.lstrip('/')
    if not path.endswith('.html'): dest=dest/'index.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(shell(title,desc,path,responsive_images(body, out),section,noindex))
    if not noindex:
        URLS[path] = history.page(body, sources, record_dates)
        SEARCH.append(dict(title=title,url=path,section=section,text=plain or re.sub('<[^>]+>',' ',body),description=desc))

def shot(image,title):
    return f'<div class="screenshot"><button data-image-open aria-label="Enlarge {e(title,quote=True)} screenshot"><img src="/assets/img/{image}" alt="{e(title,quote=True)} in the Pinball CTL application" loading="lazy" width="1440" height="900">{zoom_icon()}</button></div><p class="caption">The real Pinball CTL interface. Select the screenshot to explore.</p>'

HOMEPAGE_FEATURE_COPY = json.loads((WEB / 'content/homepage-features.json').read_text())

def feature_showcase():
    rows=[]
    for feature in FEATURES:
        feature = dict(feature, **HOMEPAGE_FEATURE_COPY[feature['slug']])
        titles = feature.get('bullets', [title for title,_ in feature['points']])
        bullets=''.join(f'<li>{e(title)}</li>' for title in titles)
        rows.append(f'<section class="feature-showcase-row"><div class="feature-showcase-image screenshot"><button data-image-open aria-label="Enlarge {e(feature["title"])} screenshot"><img src="/assets/img/{feature["image"]}" alt="{e(feature["title"])} in the pinballCTL application" loading="lazy">{zoom_icon()}</button></div><div><span class="eyebrow">{e(feature["title"])}</span><h2>{e(feature["heading"])}</h2><p>{e(feature["intro"])}</p><ul class="tour-checks">{bullets}</ul><a class="button secondary" href="/features/{feature["slug"]}/">Explore {e(feature["title"])} →</a></div></section>')
    return '<div class="feature-showcase">'+''.join(rows)+'</div>'

def feature_directory(catalog):
    groups = json.loads((WEB/'content/navigation.json').read_text())
    sections = []
    listed = set()
    for group in groups:
        cards = []
        for label, url in group['links']:
            slug = url.strip('/').split('/')[-1]
            if slug in listed:
                raise ValueError(f'Duplicate feature summary: {slug}')
            listed.add(slug)
            summary = catalog[slug]['intro']
            cards.append(
                f'<article class="feature-summary"><h3><a href="{e(url, quote=True)}">'
                f'{e(label)} <span aria-hidden="true">→</span></a></h3><p>{e(summary)}</p></article>'
            )
        sections.append(
            f'<section class="feature-summary-group"><h2>{e(group["title"])}</h2>'
            f'<div class="feature-summary-grid">{"".join(cards)}</div></section>'
        )
    if listed != set(catalog):
        raise ValueError(f'Features missing from summary: {sorted(set(catalog) - listed)}')
    return '<div class="feature-directory">' + ''.join(sections) + '</div>'


def cta(*, homepage=False):
    heading = 'Ready to build<br>your own pinball machine?' if homepage else 'Start with an idea.<br>Build something that plays.'
    description = 'Explore the tools, see what hardware you need and find out how to get started with Pinball CTL.' if homepage else 'Explore what you need and find your first steps.'
    button = 'Start building' if homepage else 'Start building →'
    return f'<section class="section wrap"><div class="cta"><div><h2>{heading}</h2><p>{description}</p></div><a class="button" href="/start-building/" data-track="get_started">{button}</a></div></section>'

def validate_output(out):
    """Never replace sources, the whole build tree, or unrecognised artifacts."""
    if out == ROOT/'build' or not out.is_relative_to(ROOT/'build'):
        raise ValueError('Build output must be a directory inside repository build/')
    if out.exists():
        if not out.is_dir() or (any(out.iterdir()) and not (out/'.pinballctl-site-build').is_file()):
            raise ValueError(f'Unrecognised output: {out}')


def serve_preview(site, port):
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    with ThreadingHTTPServer(('127.0.0.1', port), handler) as server:
        print(f'Preview at http://localhost:{server.server_address[1]}; Ctrl+C stops it and removes the files.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def build_site(out=None, preview_port=None):
    if out is not None and preview_port is not None:
        raise ValueError('Choose retained output or a temporary preview, not both')
    if out is not None:
        out = out.resolve()
        validate_output(out)
    build_root = ROOT/'build'
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='website-', dir=build_root) as directory:
        workspace = Path(directory)
        staged = workspace/'site'
        render_site(staged)
        subprocess.run([sys.executable, str(WEB/'utils/check-site.py'), '--site', str(staged)], check=True)
        if preview_port is not None:
            serve_preview(staged, preview_port)
        elif out is not None:
            validate_output(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            previous = workspace/'previous-site'
            # Preserve an explicitly retained build if its replacement fails.
            try:
                if out.exists():
                    out.rename(previous)
                staged.rename(out)
            except BaseException:
                if previous.exists() and not out.exists():
                    previous.rename(out)
                raise
    destination = f' → {out}' if out is not None else ''
    print(f'Built and validated {len(URLS)} pages plus 404{destination}; temporary build files cleaned.')


def render_illustrations(content):
    return re.sub(r'\[\[art:([a-z-]+):(\d+)\]\]', lambda m: illustration(m[1], int(m[2])), content)


def render_site(out):
    SEARCH.clear()
    URLS.clear()
    history = SitemapDates(ROOT, WEB)
    write_page = partial(write, out, history)
    out.mkdir(parents=True)
    (out/'.pinballctl-site-build').write_text('generated\n')
    (out/'.nojekyll').touch()
    shutil.copytree(WEB/'assets',out/'assets',ignore=shutil.ignore_patterns('docs', '.DS_Store'))
    (out/'CNAME').write_text('www.pinballctl.com\n')
    write_page('/start-building/','Start building your pinball machine','Plan your first Pinball CTL setup: Raspberry Pi, ESP32-S3, hardware mapping and your first game response.',render_illustrations((WEB/'templates/start-building.html').read_text()),sources=('templates/start-building.html',))
    banner=(WEB/'templates/banner.svg').read_text()
    home=(WEB/'templates/home.html').read_text().rstrip()
    body=(home.replace('[[BANNER]]', banner)
          .replace('[[FEATURE_SHOWCASE]]', feature_showcase())
          .replace('[[DASHBOARD]]', picture('dashboard',CAPTIONS['dashboard']))
          .replace('[[CTA]]', cta(homepage=True)))
    body=render_illustrations(body)
    write_page('/','Homebrew Pinball Controller for Raspberry Pi & ESP32','Pinball controller software for homebrew machines. Build hardware maps, rules, scoring, lighting and Godot media with Raspberry Pi and ESP32-S3.',body,
               sources=('templates/home.html', 'templates/banner.svg', 'content/homepage-features.json', 'content/features.json'))
    details=json.loads((WEB/'content/feature-details.json').read_text())
    tours=json.loads((WEB/'content/feature-tours.json').read_text())
    catalog={feature['slug']:feature for feature in FEATURES+details}
    if set(catalog)!=set(tours):
        raise ValueError('Every feature must have an editorial tour')
    features_body = ((WEB/'templates/features.html').read_text().rstrip()
                     .replace('[[FEATURE_DIRECTORY]]', feature_directory(catalog))
                     .replace('[[CTA]]', cta()))
    def feature_records(rows):
        records = {}
        for row in rows:
            slug = row['slug']
            records[slug] = row
            records[('summary', slug)] = (row['title'], row['intro'])
        return records

    feature_dates = {**history.records('content/features.json', feature_records),
                     **history.records('content/feature-details.json', feature_records)}
    tour_dates = history.records('content/feature-tours.json', dict)
    write_page('/features/', 'Pinball Controller Features & Visual Game Tools',
          'Explore PinballCTL’s hardware, rules, game and ball management, scoring, lighting, sound, displays and diagnostic tools.',
          features_body, sources=('templates/features.html', 'content/navigation.json'),
          record_dates=(feature_dates.get(('summary', slug)) for slug in catalog))
    for slug,feature in catalog.items():
        body=render_feature(feature,tours[slug],catalog)
        related_dates = [feature_dates.get(('summary', related)) for related in tours[slug].get('related', ())]
        write_page(f'/features/{slug}/',feature.get('seo_title',feature['title']+' for Homebrew Pinball'),feature.get('seo_description',feature['intro']),body,'Features',
                   record_dates=(feature_dates.get(slug), tour_dates.get(slug), *related_dates))
    explainer_dates = history.records('content/explainers.json', lambda rows: {row['feature']['slug']: row for row in rows})
    for explainer in json.loads((WEB/'content/explainers.json').read_text()):
        feature, tour = explainer['feature'], explainer['tour']
        write_page(f'/features/{feature["slug"]}/',feature['seo_title'],feature['seo_description'],render_feature(feature,tour,catalog),'Explanation',record_dates=(explainer_dates.get(feature['slug']),))
    for slug, target_slug in (('rules-scoring','rule-editor'), ('diagnostics','performance'), ('live-view','playfield-layout')):
        target = f'/features/{target_slug}/'
        feature = catalog[target_slug]
        retired = out/f'features/{slug}/index.html'
        retired.parent.mkdir(parents=True,exist_ok=True)
        redirect_body = f'<main id="main" class="wrap"><h1>{e(feature["title"])}</h1><p><a href="{target}">{e(feature["title"])} →</a></p></main>'
        retired.write_text(shell(feature['title'],feature['intro'],target,redirect_body,'Features',True).replace('</head>',f'<meta http-equiv="refresh" content="0;url={target}"></head>'))
    # Keep bookmarks to the retired duplicate working on static GitHub Pages.
    hardware = catalog['hardware']
    retired = out/'features/hardware-mapping/index.html'
    retired.parent.mkdir(parents=True,exist_ok=True)
    redirect_body = '<main id="main" class="wrap"><h1>Hardware</h1><p><a href="/features/hardware/">Hardware →</a></p></main>'
    retired.write_text(shell(hardware['title'],hardware['seo_description'],'/features/hardware/',redirect_body,'Features',True).replace('</head>','<meta http-equiv="refresh" content="0;url=/features/hardware/"></head>'))
    # Compatibility is a documentation topic, not an application feature.
    retired = out/'features/supported-components/index.html'
    retired.parent.mkdir(parents=True,exist_ok=True)
    target = '/docs/user-guide/supported-components/'
    redirect_body = f'<main id="main" class="wrap"><h1>Supported Components</h1><p><a href="{target}">Supported Components →</a></p></main>'
    retired.write_text(shell('Supported Components','Hardware and platform support for Pinball CTL.',target,redirect_body,'Documentation',True).replace('</head>',f'<meta http-equiv="refresh" content="0;url={target}"></head>'))
    # Retired audio/backglass group and integration page now live under Media.
    for slug in ('audio-media', 'godot'):
        retired = out/f'features/{slug}/index.html'
        retired.parent.mkdir(parents=True,exist_ok=True)
        target = '/features/media/'
        redirect_body = f'<main id="main" class="wrap"><h1>Media</h1><p><a href="{target}">Media →</a></p></main>'
        retired.write_text(shell('Media',catalog['media']['intro'],target,redirect_body,'Features',True).replace('</head>',f'<meta http-equiv="refresh" content="0;url={target}"></head>'))
    source=WEB/'docs';pages=docs._scan_pages(source)
    mapping={p['slug']:doc_url(p['slug']) for p in pages}
    legacy_mapping=json.loads((WEB/'content/docs-legacy.json').read_text())
    bookmark_mapping={**legacy_mapping, **mapping}
    oldmap={docs._slug_to_page_href(slug):target for slug,target in legacy_mapping.items()}
    shutil.copytree(WEB/'assets/docs/assets',out/'docs/assets')
    shutil.copytree(WEB/'assets/docs/media',out/'docs/media')
    def rewrite(content):
        def replace(m):
            attr,url=m.group(1),m.group(2);url=unquote(url)
            parts=urlsplit(url)
            suffix=('#'+parts.fragment) if parts.fragment else ''
            if parts.path in oldmap: new=oldmap[parts.path]+suffix
            elif parts.path.endswith('.md') and not parts.scheme:
                name=re.sub(r'^\d+(?:\.\d+)*-', '', Path(parts.path).stem).lower()
                matches=[value for key,value in mapping.items() if re.sub(r'^\d+(?:\.\d+)*-', '', key.split('/')[-1]).lower()==name]
                if len(matches)!=1: return m.group(0)
                new=matches[0]+suffix
            elif url.startswith(('./assets/','/assets/')): new='/docs/assets/'+url.split('assets/',1)[1]
            elif url.startswith(('./media/','/media/')): new='/docs/media/'+url.split('media/',1)[1]
            elif url.startswith('https://docs.pinballctl.com'):
                parts=urlsplit(url);new=oldmap.get(parts.path,'/docs/')
            else: return m.group(0)
            return f'{attr}="{e(new,quote=True)}"'
        return re.sub(r'(href|src)="([^"]+)"',replace,content)
    doc_groups = DOC_GROUPS
    for page in pages:
        slug=page['slug'];path=mapping[slug];raw=page['md_path'].read_text()
        if slug == 'index':
            raw=raw.replace('[[DOCS_ART]]', (WEB/'templates/docs-banner.svg').read_text())
        content=docs._render_markdown(raw,page['md_path'],source,WEB/'assets/docs/assets')
        if slug != 'index':
            content=rewrite(content)
        # Apply the same document header to every guide, without editing its source.
        if slug != 'index':
            category = {'user-guide': 'User guide', 'technical-notes': 'Developer Guide', 'build-notes': 'Developer Guide', 'developer-guide': 'Developer Guide', 'developer-notes': 'Developer Guide'}.get(slug.split('/')[0], 'Documentation')
            content = re.sub(r'(<h1\b[^>]*>.*?</h1>)',
                             lambda m: f'<header class="doc-title"><span class="eyebrow">{category}</span>{m.group(1)}</header>',
                             content, count=1, flags=re.S)
        toc=[]
        main_headings_only = slug in {'index', 'user-guide/getting-started'}
        def heading(m):
            tag,attrs,text=m.groups();label=unescape(re.sub('<[^>]+>','',text))
            match=re.search(r'id="([^"]+)"',attrs);ident=match.group(1) if match else re.sub('[^a-z0-9]+','-',label.lower()).strip('-')
            # Interactive panels can exclude headings that are initially hidden.
            if 'data-toc-exclude' not in attrs and (not main_headings_only or tag == 'h2'):
                toc.append((ident,label))
            return f'<{tag}{attrs if match else attrs+" id="+chr(34)+ident+chr(34)}>{text}</{tag}>'
        content=re.sub(r'<(h[23])([^>]*)>(.*?)</\1>',heading,content,flags=re.S)
        content = re.sub(
            r'<table\b[^>]*>.*?</table>',
            lambda match: '<div class="doc-table-frame"><div class="doc-table-scroll">' +
                          match.group() + '</div></div>',
            content, flags=re.S,
        )
        sidebar = docs_sidebar(doc_groups, pages, mapping, slug)
        toc_html=''.join(f'<a href="#{e(i)}">{e(t)}</a>' for i,t in toc)
        body=f'<main id="main" class="docs-shell"><nav class="docs-nav" id="docs-nav" aria-label="Documentation">{sidebar}</nav><article class="doc-body{' doc-guide' if slug != 'index' else ''}">{content}{topic_navigation(doc_groups, mapping, slug)}</article><aside class="toc" aria-label="On this page"><h2>On this page</h2>{toc_html}</aside></main>'
        plain = re.sub('<[^>]+>', ' ', content) if slug == 'index' else docs._plain_text_from_markdown(raw)
        sources = [page['md_path'].relative_to(WEB).as_posix()]
        if slug == 'index':
            sources.append('templates/docs-banner.svg')
        write_page(path,'Documentation & Setup Guides' if slug == 'index' else page['title'],'Set up and use your pinballCTL homebrew pinball controller. Browse hardware, rules, lighting, media and diagnostics guides, plus technical documentation.' if slug == 'index' else docs._extract_excerpt(raw),body,'Documentation',plain,sources=sources)
    for old, target in REDIRECTS.items():
        dest = out/old.lstrip('/')/'index.html'
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = f'<main id="main" class="wrap"><h1>Continue to the manual</h1><p>This guide has moved.</p><a href="{e(target, quote=True)}">Open the current guide →</a></main>'
        dest.write_text(shell('Guide moved', 'Continue to the current Pinball CTL guide.',
                              target.split('#')[0], body, 'Documentation', True).replace(
            '</head>', f'<meta http-equiv="refresh" content="0;url={e(target, quote=True)}"></head>'))
    # Keep source slugs and old-domain bookmarks pointing to canonical destinations.
    for name in ['contact','terms','privacy','in-development']:
        content=(WEB/'templates'/f'{name}.html').read_text()
        content=render_illustrations(content)
        descriptions={
            'in-development': 'Pinball CTL is in active development, not a stable release. Help shape the project through feedback, bug reports, testing and contributions on GitHub.',
            'contact': 'Contact pinballCTL for bug reports, feature ideas, private enquiries and commercial licensing. Find the right support route for your homebrew pinball project.',
            'terms': 'Understand pinballCTL website terms, the non-commercial Community Licence, commercial licensing and responsibilities when building a physical pinball machine.',
            'privacy': 'How the pinballCTL website uses Google Analytics, browser storage and GitHub Pages hosting, plus your choices and the distinction from local machine data.',
        }
        write_page(f'/{name}/',{'contact':'Contact & Support','terms':'Terms of Use','privacy':'Privacy & Cookie Choices','in-development':'In Development — Help Build Pinball CTL'}[name],descriptions[name],f'<main id="main" class="wrap info-page">{content}</main>',sources=(f'templates/{name}.html',))
        # Keep existing public legal URLs working with the new layout.
        if name != 'in-development':
            shutil.copyfile(out/name/'index.html',out/f'{name}.html')
    write_page('/404.html','Page not found','Find features and documentation on Pinball CTL.', '<main id="main" class="wrap"><div class="feature-hero"><span class="eyebrow">404</span><h1>That ball went astray.</h1><p>This page could not be found. Try the site search or return to the homepage.</p><a class="button" href="/">Back to home →</a></div></main>',noindex=True)
    (out/'search-index.json').write_text(json.dumps(SEARCH,separators=(',',':')))
    (out/'docs/legacy-links.json').write_text(json.dumps(bookmark_mapping))
    (out/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n')
    entries = []
    for path, date in URLS.items():
        lastmod = f'<lastmod>{date}</lastmod>' if date else ''
        entries.append(f'<url><loc>{e(DOMAIN + path)}</loc>{lastmod}</url>')
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                  + '\n'.join(entries) + '\n</urlset>\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path, help='Retain output inside build/ for upload; caller must remove it afterwards')
    mode.add_argument('--preview', type=int, nargs='?', const=8090, metavar='PORT', help='Serve a temporary local preview (default port 8090); clean up when stopped')
    args = parser.parse_args()
    build_site(args.output, args.preview)


if __name__ == '__main__':
    main()
