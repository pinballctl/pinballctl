#!/usr/bin/env python3
"""Build two static GitHub Pages artifacts; never deploy or alter legacy sources."""
from pathlib import Path
from html import escape as e, unescape
from urllib.parse import urlsplit, unquote
import argparse, hashlib, importlib.util, json, re, shutil, sys
sys.dont_write_bytecode = True
from feature_pages import render_feature, picture, CAPTIONS
from benefit_art import illustration
from responsive_images import responsive_images
from search_metadata import breadcrumbs, breadcrumb_html, structured_data

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'website'
DOMAIN = 'https://www.pinballctl.com'
FEATURES = json.loads((WEB / 'content/features.json').read_text())
# Content-based URLs prevent browsers retaining styles from an earlier build.
CSS_VERSION = hashlib.sha256((WEB / 'assets/css/site.css').read_bytes()).hexdigest()[:12]
JS_VERSION = hashlib.sha256((WEB / 'assets/js/site.js').read_bytes()).hexdigest()[:12]
NAVIGATION = json.loads((WEB / 'content/navigation.json').read_text())
SEARCH = []
URLS = []

def doc_url(slug):
    if slug == 'README': return '/docs/'
    return '/docs/' + '/'.join(re.sub(r'^\d+(?:\.\d+)*-', '', p).lower() for p in slug.split('/')) + '/'

def nav():
    categories=json.loads((WEB/'content/navigation.json').read_text())
    groups=[]
    for category in categories:
        links=''.join(f'<a href="{e(url,quote=True)}">{e(label)}</a>' for label,url in category['links'])
        groups.append(f'<section class="feature-menu-group"><h2>{e(category["title"])}</h2><p>{e(category["intro"])}</p>{links}</section>')
    menu='<div class="wrap feature-menu-grid">'+''.join(groups)+'</div><div class="feature-menu-footer wrap"><a href="/features/">Explore all features →</a><a href="/start-building/">New here? Start building →</a></div>'
    return f'''<a class="skip" href="#main">Skip to content</a><header class="site-header"><div class="wrap header-inner"><a class="brand" href="/" aria-label="Pinball CTL home"><img class="brand-mark" src="/assets/img/brand-mark.svg" alt="" width="36" height="36"><span class="brand-wordmark">pinball<span class="brand-suffix">CTL</span></span></a><button class="search-trigger" data-search-open aria-label="Search site" title="Search site"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg></button><button class="menu-toggle" aria-controls="site-nav" aria-expanded="false">Menu ☰</button><nav class="nav" id="site-nav" aria-label="Main navigation"><details class="features-dropdown"><summary>Features</summary><div class="feature-menu">{menu}</div></details><a href="/docs/">Documentation</a><a href="https://github.com/pinballctl/pinballctl" data-track="github" target="_blank" rel="noopener noreferrer">GitHub ↗</a><a class="nav-cta" href="/start-building/" data-track="get_started">Start building →</a></nav></div></header><div class="menu-backdrop" hidden aria-hidden="true"></div>'''

def shell(title, desc, path, body, section='Website', noindex=False):
    canonical=DOMAIN+path
    social_image=DOMAIN+'/assets/img/dashboard.webp'
    image_match=re.search(r'<img[^>]+src="(/assets/img/(?:tour-|feature-)[^"]+)"',body)
    if image_match: social_image=DOMAIN+image_match[1]
    extra_scripts='<script defer src="/docs/assets/js/components.js"></script>' if 'project-cost-summary-table' in body else ''
    structured=structured_data(DOMAIN,path,title,desc,social_image,NAVIGATION,noindex)
    trail = ''
    if path != '/' and not noindex:
        trail = '<div class="wrap breadcrumb-wrap">' + breadcrumb_html(breadcrumbs(path,title,NAVIGATION)) + '</div>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | Pinball CTL</title><meta name="description" content="{e(desc,quote=True)}"><link rel="canonical" href="{canonical}"><meta name="robots" content="{'noindex,follow' if noindex else 'index,follow,max-image-preview:large'}"><meta name="theme-color" content="#090f17"><link rel="icon" href="/assets/img/favicon.svg"><meta property="og:type" content="website"><meta property="og:title" content="{e(title,quote=True)}"><meta property="og:description" content="{e(desc,quote=True)}"><meta property="og:url" content="{canonical}"><meta property="og:image" content="{social_image}"><meta property="og:site_name" content="pinballCTL"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title,quote=True)}"><meta name="twitter:description" content="{e(desc,quote=True)}"><meta name="twitter:image" content="{social_image}"><link rel="stylesheet" href="/assets/css/site.css?v={CSS_VERSION}"><script defer src="/assets/js/site.js?v={JS_VERSION}"></script>{extra_scripts}<script type="application/ld+json">{json.dumps(structured).replace('<','\\u003c')}</script></head><body data-section="{section}">{nav()}{trail}{body}<footer class="footer"><div class="wrap footer-inner"><div><a class="brand" href="/"><img class="brand-mark" src="/assets/img/brand-mark.svg" alt="" width="36" height="36"><span class="brand-wordmark">pinball<span class="brand-suffix">CTL</span></span></a><p>Your machine. Your rules. Your game.</p><p>Built for homebrew pinball. Raspberry Pi + ESP32-S3.</p></div><div class="footer-links"><a href="/docs/">Documentation</a><a href="/contact/">Contact</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a><button class="settings-link" data-cookie-settings>Cookie settings</button></div></div></footer><dialog class="search-dialog" aria-labelledby="search-title"><div class="search-top"><h2 id="search-title">Find your next step.</h2><button class="close" data-search-close aria-label="Close search">✕</button></div><label for="site-search">Search features and documentation</label><input class="search-input" id="site-search" type="search" autocomplete="off" placeholder="Try lighting, coils or scoring…"><label class="search-scope"><input type="checkbox" id="search-docs-only"> Docs only</label><p class="search-meta" role="status" data-search-status>Type to search the site.</p><ul class="search-results"></ul></dialog><dialog class="image-dialog" aria-label="Screenshot preview"><button class="close" data-image-close aria-label="Close image">Close ✕</button><img alt=""></dialog><aside class="consent" aria-label="Analytics preferences" hidden><strong>A little insight helps us improve.</strong><p>Google Analytics is enabled by default to measure page visits and feature interest. You can turn it off and still browse and search. <a href="/privacy/">Privacy details</a></p><button data-consent="yes">Keep analytics enabled</button><button data-consent="no">Turn analytics off</button></aside></body></html>'''

def write(out,path,title,desc,body,section='Website',plain=None,noindex=False):
    dest=out/path.lstrip('/')
    if not path.endswith('.html'): dest=dest/'index.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(shell(title,desc,path,responsive_images(body, out),section,noindex))
    if not noindex:
        URLS.append(path)
        SEARCH.append(dict(title=title,url=path,section=section,text=plain or re.sub('<[^>]+>',' ',body),description=desc))

def shot(image,title):
    return f'<div class="screenshot"><button data-image-open aria-label="Enlarge {e(title,quote=True)} screenshot"><img src="/assets/img/{image}" alt="{e(title,quote=True)} in the Pinball CTL application" loading="lazy" width="1440" height="900"></button></div><p class="caption">The real Pinball CTL interface. Select the screenshot to explore.</p>'

HOMEPAGE_FEATURE_COPY = {
    "hardware": {
        "heading": "Connect and configure your hardware.",
        "intro": "Set up switches, coils and lights using the hardware editor. Give each connection a name, choose its function and configure the appropriate output settings.",
        "bullets": [
            "Map switches, coils and lights to your hardware.",
            "Configure coil pulse, hold and safety limits.",
            "Deploy supported hardware settings to the ESP32-S3."
        ]
    },
    "rules-scoring": {
        "heading": "Create your own game rules.",
        "intro": "Use the rule editor to decide what happens when switches are triggered. Create scoring rules, combinations and multipliers, and control how your machine responds during gameplay.",
        "bullets": [
            "Create rules using events, conditions and actions.",
            "Set up scoring, combinations and multipliers.",
            "Run supported hardware rules directly on the ESP32-S3."
        ]
    },
    "lighting": {
        "heading": "Design your playfield lighting.",
        "intro": "Arrange lights on a visual representation of your playfield and create lighting effects for different events and game modes. Preview your designs as you work.",
        "bullets": [
            "Position lights on your playfield layout.",
            "Create lighting effects and scenes.",
            "Preview your lighting before deploying supported configurations."
        ]
    },
    "audio-media": {
        "heading": "Add sound and displays to your game.",
        "intro": "Manage sound effects, music and display content from Pinball CTL. Create scenes for your backglass and other displays, including custom animated content built with Godot.",
        "bullets": [
            "Upload and organise your sound library.",
            "Configure audio cues and playback.",
            "Create display scenes and integrate Godot content."
        ]
    },
    "live-view": {
        "heading": "Build and test without a complete machine.",
        "intro": "Live View gives you a visual representation of your playfield where you can test configured inputs and preview lighting. It's useful when developing a new game, experimenting with layouts or working on your project before all the hardware is installed. Connected event-path testing requires an ESP32-S3; physical outputs and hardware timing still need testing on the real machine.",
        "bullets": [
            "Create and work with a visual playfield layout.",
            "Trigger configured inputs and preview lighting responses.",
            "Test the connected event path when an ESP32-S3 is available."
        ]
    },
    "diagnostics": {
        "heading": "See what your machine is doing.",
        "intro": "Monitor events, check communication between the Raspberry Pi and ESP32-S3, and investigate problems using built-in performance tools and logs.",
        "bullets": [
            "Monitor event activity and delivery times.",
            "Check queues and controller communication.",
            "View logs to help diagnose problems."
        ]
    }
}

def feature_showcase(*, homepage=False):
    rows=[]
    for i, feature in enumerate(FEATURES):
        if homepage:
            feature = dict(feature, **HOMEPAGE_FEATURE_COPY[feature['slug']])
        titles = feature.get('bullets', [title for title,_ in feature['points']])
        bullets=''.join(f'<li>{e(title)}</li>' for title in titles)
        rows.append(f'<section class="feature-showcase-row"><div class="feature-showcase-image screenshot"><button data-image-open aria-label="Enlarge {e(feature["title"])} screenshot"><img src="/assets/img/{feature["image"]}" alt="{e(feature["title"])} in the pinballCTL application" loading="lazy"></button></div><div><span class="eyebrow">{e(feature["title"])}</span><h2>{e(feature["heading"])}</h2><p>{e(feature["intro"])}</p><ul class="tour-checks">{bullets}</ul><a class="button secondary" href="/features/{feature["slug"]}/">Explore {e(feature["title"])} →</a></div></section>')
    return '<div class="feature-showcase">'+''.join(rows)+'</div>'

def feature_directory():
    groups=json.loads((WEB/'content/navigation.json').read_text())
    result='<section class="feature-directory"><h2>Explore every tool.</h2><div class="feature-menu-grid">'
    for group in groups:
        links=''.join(f'<a href="{url}">{e(label)} →</a>' for label,url in group['links'])
        result+=f'<section><h3>{e(group["title"])}</h3>{links}</section>'
    return result+'</div></section>'

def cta(*, homepage=False):
    heading = 'Ready to build<br>your own pinball machine?' if homepage else 'Start with an idea.<br>Build something that plays.'
    description = 'Explore the tools, see what hardware you need and find out how to get started with Pinball CTL.' if homepage else 'Explore what you need and find your first steps.'
    button = 'Start building' if homepage else 'Start building →'
    return f'<section class="section wrap"><div class="cta"><div><h2>{heading}</h2><p>{description}</p></div><a class="button" href="/start-building/" data-track="get_started">{button}</a></div></section>'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'dist/site');parser.add_argument('--holding-output',type=Path,default=ROOT/'dist/docs-holding');args=parser.parse_args()
    out=args.output.resolve();holding=args.holding_output.resolve()
    if out == holding or out.is_relative_to(holding) or holding.is_relative_to(out):
        raise ValueError('Output directories must be separate and non-nested')
    # Refuse to overwrite sources; clean only directories marked by this builder.
    for dest in (out,holding):
        if dest==ROOT or not dest.is_relative_to(ROOT/'dist'): raise ValueError('Build outputs must be inside repository dist/')
        if dest.exists() and any(dest.iterdir()) and not (dest/'.pinballctl-site-build').exists(): raise ValueError(f'Unrecognised output: {dest}')
    for dest in (out,holding):
        if dest.exists(): shutil.rmtree(dest)
        dest.mkdir(parents=True);(dest/'.pinballctl-site-build').write_text('generated\n');(dest/'.nojekyll').touch()
    shutil.copytree(WEB/'assets',out/'assets')
    (out/'CNAME').write_text('www.pinballctl.com\n')
    write(out,'/start-building/','Start building your pinball machine','Plan your first Pinball CTL setup: Raspberry Pi, ESP32-S3, hardware mapping and your first game response.',re.sub(r'\[\[art:([a-z-]+):(\d+)\]\]', lambda m: illustration(m[1], int(m[2])), (WEB/'templates/start-building.html').read_text()))
    banner=(WEB/'templates/banner.svg').read_text()
    body=f'''<main id="main"><section class="hero"><div class="wrap"><div class="hero-top"><div><span class="eyebrow">Build and control your own pinball machine</span><h1>Build your own<br>pinball machine.<br><em>Your game. Your rules.</em></h1><p class="intro">Pinball CTL is software for building and running a homebrew pinball machine. It runs on a Raspberry Pi and works with an ESP32-S3 controller to connect switches, coils and lights. Use your browser to configure hardware, create game rules and scoring, and add lighting, sound and displays. Whether you're starting a new build or developing an existing machine, Pinball CTL brings the tools together in one place.</p><div class="actions"><a class="button" href="/start-building/" data-track="get_started">Start building →</a><a class="button secondary" href="/features/">Explore the features</a></div></div><div class="hero-art">{banner}<span class="art-label">DESIGNED TO MAKE YOUR IDEAS PLAYABLE</span></div></div><div class="hero-bottom"><img src="/assets/img/tour-control-centre.webp" alt="pinballCTL dashboard with the navigation menu open, showing hardware, game authoring, media and diagnostic tools" width="1440" height="900" fetchpriority="high"></div></div></section><section class="platform-overview wrap" aria-labelledby="platform-title"><div class="platform-heading"><span class="eyebrow">How it works</span><h2 id="platform-title">Three parts.<br>One pinball controller.</h2><p>Pinball CTL uses a Raspberry Pi, an ESP32-S3 and a browser-based interface. Each has a different job, working together to run your machine.</p></div><div class="platform-roles"><article>{illustration('platform',0)}<span class="eyebrow">Runs your game</span><h3>Raspberry Pi</h3><p>Runs the Pinball CTL software, including game rules, scoring, sound, displays and the web interface.</p></article><article>{illustration('platform',1)}<span class="eyebrow">Controls your hardware</span><h3>ESP32-S3</h3><p>Reads switches, controls supported outputs and handles time-critical hardware responses. It also enforces configured coil safety limits.</p></article><article>{illustration('platform',2)}<span class="eyebrow">Where you build</span><h3>Your browser</h3><p>Configure hardware, create game rules, design lighting and manage your machine from a single interface.</p></article></div></section><section class="section wrap"><div class="section-head"><div><span class="eyebrow">Hardware, game rules, lighting and more</span><h2>Everything you need<br>to build your game.</h2><p class="feature-section-subtitle">Pinball CTL brings together the tools for configuring your machine and creating your own gameplay.</p></div></div>{feature_showcase(homepage=True)}</section><section class="section home-workspace-band"><div class="wrap home-workspace"><div><span class="eyebrow">From configuration to testing</span><h2>Set it up.<br>See it in action.</h2><p>Use the dashboard to check your controller connection and system status, then move between hardware configuration, game rules, lighting and media. Live View lets you work with your playfield layout and test ideas as you develop them. You don't need a finished machine to start creating your game.</p></div>{picture('dashboard',CAPTIONS['dashboard'])}</div></section><section class="section tinted"><div class="wrap split"><div><span class="eyebrow">Raspberry Pi + ESP32-S3</span><h2>Built for real-time control.<br>Made for homebrew.</h2><p>The Raspberry Pi runs your game software, scoring, sound and displays. The ESP32-S3 handles switches and supported real-time hardware responses, including coil safety limits. This separates the time-critical hardware control from the rest of your game software.</p><a href="/docs/technical-notes/architecture/">Explore the architecture →</a></div><div class="flow"><div class="flow-item">{illustration('home', 0)}<div><h3>Connect your hardware</h3><p>Configure switches, coils and lights, assign their functions and set appropriate safety limits.</p></div></div><div class="flow-item">{illustration('home', 1)}<div><h3>Create your game</h3><p>Build rules and scoring, then add lighting, sound and displays.</p></div></div><div class="flow-item">{illustration('home', 2)}<div><h3>Test and improve</h3><p>Deploy supported configurations, test how your machine responds and use the built-in tools to investigate problems.</p></div></div></div></div></section>{cta(homepage=True)}</main>'''
    write(out,'/','Homebrew Pinball Controller for Raspberry Pi & ESP32','Pinball controller software for homebrew machines. Build hardware maps, rules, scoring, lighting and Godot media with Raspberry Pi and ESP32-S3.',body)
    write(out,'/features/','Pinball Controller Features & Visual Game Tools','Explore browser-based tools for homebrew pinball: hardware mapping, ESP32 coil control, rules, scoring, LED lighting, audio and Godot backglass scenes.',f'<main id="main" class="wrap"><div class="feature-hero"><span class="eyebrow">The platform</span><h1>Explore your<br>pinball controller.</h1><p>Get to know the tools that turn a collection of parts into your pinball game.</p></div>{feature_showcase()}{feature_directory()}{cta()}</main>')
    details=json.loads((WEB/'content/feature-details.json').read_text())
    tours=json.loads((WEB/'content/feature-tours.json').read_text())
    catalog={feature['slug']:feature for feature in FEATURES+details}
    if set(catalog)!=set(tours):
        raise ValueError('Every feature must have an editorial tour')
    for slug,feature in catalog.items():
        body=render_feature(feature,tours[slug],catalog)
        write(out,f'/features/{slug}/',feature.get('seo_title',feature['title']+' for Homebrew Pinball'),feature.get('seo_description',feature['intro']),body,'Features')
    # Keep bookmarks to the retired duplicate working on static GitHub Pages.
    hardware = catalog['hardware']
    retired = out/'features/hardware-mapping/index.html'
    retired.parent.mkdir(parents=True,exist_ok=True)
    redirect_body = '<main id="main" class="wrap"><h1>Hardware</h1><p><a href="/features/hardware/">Hardware →</a></p></main>'
    retired.write_text(shell(hardware['title'],hardware['seo_description'],'/features/hardware/',redirect_body,'Features',True).replace('</head>','<meta http-equiv="refresh" content="0;url=/features/hardware/"></head>'))
    spec=importlib.util.spec_from_file_location('docs_builder',ROOT/'docs/utils/build-docs.py');docs=importlib.util.module_from_spec(spec);spec.loader.exec_module(docs)
    source=ROOT/'docs/docs';pages=docs._scan_pages(source)
    def natural_order(page):
        return tuple((0, float(part)) if re.fullmatch(r'\d+(?:\.\d+)?', part) else (1,part.lower()) for part in re.split(r'(\d+(?:\.\d+)?)',page['slug']))
    pages.sort(key=natural_order)
    mapping={p['slug']:doc_url(p['slug']) for p in pages}
    oldmap={docs._slug_to_page_href(p['slug']):mapping[p['slug']] for p in pages}
    for directory in ['assets','media']:
        if (ROOT/'docs'/directory).exists(): shutil.copytree(ROOT/'docs'/directory,out/'docs'/directory,dirs_exist_ok=True)
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
    for page in pages:
        slug=page['slug'];path=mapping[slug];raw=page['md_path'].read_text()
        content=rewrite(docs._render_markdown(raw,page['md_path'],source,ROOT/'docs/assets'))
        if slug == 'README':
            content=(WEB/'templates/docs-home.html').read_text().replace('[[DOCS_ART]]', (WEB/'templates/docs-banner.svg').read_text())
        # Apply the same document header to every guide, without editing its source.
        if slug != 'README':
            category = {'1-user-guide': 'User guide', '2-technical-notes': 'Technical reference', '3-build-notes': 'Build notes'}.get(slug.split('/')[0], 'Documentation')
            content = re.sub(r'(<h1\b[^>]*>.*?</h1>)',
                             lambda m: f'<header class="doc-title"><span class="eyebrow">{category}</span>{m.group(1)}</header>',
                             content, count=1, flags=re.S)
        toc=[]
        def heading(m):
            tag,attrs,text=m.groups();label=unescape(re.sub('<[^>]+>','',text))
            match=re.search(r'id="([^"]+)"',attrs);ident=match.group(1) if match else re.sub('[^a-z0-9]+','-',label.lower()).strip('-')
            if slug != 'README' or tag == 'h2': toc.append((ident,label))
            return f'<{tag}{attrs if match else attrs+" id="+chr(34)+ident+chr(34)}>{text}</{tag}>'
        content=re.sub(r'<(h[23])([^>]*)>(.*?)</\1>',heading,content,flags=re.S)
        sidebar=''
        for group,label in [('README','Start here'),('1-user-guide/','User guides'),('2-technical-notes/','Technical documentation'),('3-build-notes/','Build notes')]:
            links=[p for p in pages if (p['slug']==group if group=='README' else p['slug'].startswith(group))]
            sidebar+=f'<h2>{label}</h2>'+''.join(f'<a href="{mapping[p["slug"]]}"'+(' aria-current="page"' if p['slug']==slug else '')+f'>{e(p["title"])}</a>' for p in links)
        toc_html=''.join(f'<a href="#{e(i)}">{e(t)}</a>' for i,t in toc)
        body=f'<main id="main" class="docs-shell"><button class="doc-mobile" aria-expanded="false" aria-controls="docs-nav">Browse documentation ☰</button><nav class="docs-nav" id="docs-nav" aria-label="Documentation">{sidebar}</nav><article class="doc-body{' doc-guide' if slug != 'README' else ''}">{content}</article><aside class="toc" aria-label="On this page"><h2>On this page</h2>{toc_html}</aside></main>'
        write(out,path,'Documentation & Setup Guides' if slug == 'README' else page['title'],'Set up and use your pinballCTL homebrew pinball controller. Browse hardware, rules, lighting, media and diagnostics guides, plus technical documentation.' if slug == 'README' else docs._extract_excerpt(raw),body,'Documentation',re.sub('<[^>]+>', ' ', content) if slug == 'README' else docs._plain_text_from_markdown(raw))
    for name in ['contact','terms','privacy']:
        content=(WEB/'templates'/f'{name}.html').read_text()
        content=re.sub(r'\[\[art:([a-z-]+):(\d+)\]\]', lambda m: illustration(m[1], int(m[2])), content)
        descriptions={
            'contact': 'Contact pinballCTL for bug reports, feature ideas, private enquiries and commercial licensing. Find the right support route for your homebrew pinball project.',
            'terms': 'Understand pinballCTL website terms, the non-commercial Community Licence, commercial licensing and responsibilities when building a physical pinball machine.',
            'privacy': 'How the pinballCTL website uses Google Analytics, browser storage and GitHub Pages hosting, plus your choices and the distinction from local machine data.',
        }
        write(out,f'/{name}/',{'contact':'Contact & Support','terms':'Terms of Use','privacy':'Privacy & Cookie Choices'}[name],descriptions[name],f'<main id="main" class="wrap info-page">{content}</main>')
        # Keep existing public legal URLs working with the new layout.
        shutil.copyfile(out/name/'index.html',out/f'{name}.html')
    write(out,'/404.html','Page not found','Find features and documentation on Pinball CTL.', '<main id="main" class="wrap"><div class="feature-hero"><span class="eyebrow">404</span><h1>That ball went astray.</h1><p>This page could not be found. Try the site search or return to the homepage.</p><a class="button" href="/">Back to home →</a></div></main>',noindex=True)
    (out/'search-index.json').write_text(json.dumps(SEARCH,separators=(',',':')))
    (out/'docs/legacy-links.json').write_text(json.dumps(mapping))
    (out/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n')
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{DOMAIN}{u}</loc></url>' for u in URLS)+'</urlset>')
    # Legacy domain: a shared holding design with per-old-URL canonical targets.
    shutil.copytree(out/'assets/css',holding/'assets/css');(holding/'assets/img').mkdir(parents=True);shutil.copyfile(WEB/'assets/img/brand-mark.svg',holding/'assets/img/brand-mark.svg');shutil.copyfile(WEB/'assets/img/favicon.svg',holding/'assets/img/favicon.svg');shutil.copyfile(WEB/'templates/docs-banner.svg',holding/'assets/img/docs-banner.svg');(holding/'CNAME').write_text('docs.pinballctl.com\n')
    def hold(target='/docs/',notfound=False):
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Documentation has a new home | Pinball CTL</title><meta name="description" content="Pinball CTL documentation is now part of the main website. Find guides, setup instructions and technical documentation."><link rel="canonical" href="{DOMAIN}{target}"><meta name="robots" content="{'noindex,follow' if notfound else 'index,follow'}"><link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml"><meta name="theme-color" content="#090f17"><link rel="stylesheet" href="/assets/css/site.css?v={CSS_VERSION}"></head><body><main class="holding"><a class="brand" href="{DOMAIN}"><img class="brand-mark" src="/assets/img/brand-mark.svg" alt="" width="36" height="36"><span class="brand-wordmark">pinball<span class="brand-suffix">CTL</span></span></a><div class="holding-layout"><div><span class="eyebrow">Same project. One home.</span><h1>A new home<br>for the docs.</h1><p>Setup guides, hardware references and everything you need to build your machine now live on the main pinballCTL website.</p><a class="button" id="docs-link" href="{DOMAIN}{target}">Continue to documentation →</a><p>You can update your bookmark to <a href="{DOMAIN}/docs/">www.pinballctl.com/docs/</a>.</p><a class="holding-home" href="{DOMAIN}/">Explore pinballCTL →</a></div><div class="holding-art"><img src="/assets/img/docs-banner.svg" width="540" height="420" alt="An open documentation book with a circuit diagram and a silver pinball"><span>YOUR MACHINE. YOUR RULES.</span></div></div><footer class="holding-footer">New location. Same project. Keep building.</footer></main><script src="/legacy.js"></script></body></html>'''
    (holding/'index.html').write_text(hold());(holding/'404.html').write_text(hold(notfound=True))
    for old,target in oldmap.items():
        if old=='/':continue
        dest=holding/old.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(hold(target))
    (holding/'legacy-links.json').write_text(json.dumps({'slugs':mapping,'paths':oldmap}))
    (holding/'legacy.js').write_text('''fetch('/legacy-links.json').then(r=>r.json()).then(m=>{const p=new URLSearchParams(location.hash.slice(1));const slug=p.get('doc');const target=m.slugs[slug]||m.paths[location.pathname];if(target){document.querySelector('#docs-link').href='https://www.pinballctl.com'+target;document.querySelector('[rel=canonical]').href='https://www.pinballctl.com'+target;}}).catch(()=>{});''')
    (holding/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n')
    print(f'Built {len(URLS)} pages plus 404 → {out}; legacy holding site → {holding}')

if __name__=='__main__':main()
