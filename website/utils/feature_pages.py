"""Render editorial feature tours from content; shared by the static site builder."""
from html import escape
from benefit_art import illustration


def picture(key, caption, eager=False):
    loading = 'eager' if eager else 'lazy'
    return (
        '<figure class="tour-figure"><div class="screenshot">'
        f'<button data-image-open aria-label="Enlarge {escape(caption, quote=True)}">'
        f'<img src="/assets/img/tour-{key}.webp" alt="{escape(caption, quote=True)}" '
        f'loading="{loading}" decoding="async"></button></div>'
        f'<figcaption>{escape(caption)} · Select to enlarge</figcaption></figure>'
    )


CAPTIONS = {
    'hardware': 'Hardware mapping with named components and pin functions',
    'coil-options': 'Saved coil driver configuration and safety options',
    'esplink': 'ESPLink device, bridge and firmware overview',
    'firmware': 'Firmware versions and local download status',
    'accelerometer': 'Accelerometer module with no sensor connected in this development setup',
    'rules': 'Rules overview with names, tags and action counts',
    'rule-triggers': 'An existing rule opened on its Triggers tab',
    'rule-actions': 'An existing rule opened on its Actions tab',
    'rule-conditions': 'An existing rule opened on its Conditions tab',
    'scoring': 'Scoring base-points editor',
    'scoring-rules': 'Scoring Rules tab',
    'combos': 'Scoring Combos tab',
    'playfield': 'Playfield layout editor',
    'audio': 'Audio asset library',
    'audio-cues': 'Audio Cues tab with playback configuration',
    'audio-outputs': 'Audio Outputs tab',
    'audio-usage': 'Audio Usage Map tab',
    'media': 'Media scene composition workspace',
    'media-library': 'Media Library tab',
    'media-displays': 'Media Displays tab',
    'media-fonts': 'Media Fonts tab',
    'media-runtime': 'Media Runtime tab in the development setup',
    'godot': 'Media scene with an existing Godot layer selected',
    'dashboard': 'Application dashboard and status cards',
    'control-centre': 'Application control centre with module navigation open',
    'logs': 'Runtime log viewer',
    'service': 'Machine service history workspace',
    'integrity': 'Project integrity report',
    'settings': 'Settings Project tab',
    'settings-transfer': 'Settings Import/Export tab',
    'wifi': 'Host Wi-Fi status in the development environment',
    'lighting': 'Lighting stage and scene editor',
    'lighting-fixtures': 'Lighting Fixtures tab',
    'lighting-runtime': 'Lighting Runtime tab',
    'liveview': 'Live View playfield and runtime controls',
    'performance': 'Full Performance module with throughput, backlog and latency charts',
}


def render_feature(feature, tour, catalog):
    e = escape
    if tour['layout'] == 'explanation':
        sections = []
        for section in tour['sections']:
            diagram = ''
            if section.get('diagram'):
                diagram = (f'<figure class="event-diagram"><img src="/assets/img/{e(section["diagram"])}.svg" '
                           f'alt="{e(section["alt"], quote=True)}" width="400" height="570"></figure>')
            sections.append(f'<section class="event-section{" illustrated" if diagram else ""}">'
                            f'<div><h2>{e(section["title"])}</h2><p>{e(section["text"])}</p></div>{diagram}</section>')
        cta = tour['cta']
        return (f'<main id="main" class="wrap feature-tour event-explanation"><header class="tour-heading">'
                f'<span class="eyebrow">{e(tour["eyebrow"])}</span><h1>{e(feature["heading"])}</h1>'
                f'<p>{e(feature["intro"])}</p></header>'+''.join(sections)+
                f'<div class="actions"><a class="button" href="{e(cta["href"], quote=True)}">{e(cta["text"])}</a></div></main>')
    doc = feature['doc'] if feature['doc'].startswith('/') else '/docs/' + feature['doc'] + '/'
    actions = f'<div class="actions"><a class="tour-guide-link" href="{doc}">Technical guide →</a></div>'
    intro = f'<div class="tour-heading"><a class="eyebrow" href="/features/">Features / {e(feature["title"])}</a><h1>{e(feature["heading"])}</h1><p>{e(feature["intro"])}</p>{actions}</div>'
    if tour['hero']:
        hero = picture(tour['hero'], CAPTIONS[tour['hero']], eager=True)
    else:
        hero = '<div class="tour-system"><span class="eyebrow">A connected platform</span><div><b>Raspberry Pi</b><span>Authoring &amp; orchestration</span></div><span class="tour-arrow">↓ USB bridge</span><div><b>ESP32-S3</b><span>Real-time inputs &amp; outputs</span></div><p>Choose peripherals and drivers for your particular machine.</p></div>'
    art = feature.get('point_art', [[feature['slug'], i] for i in range(len(feature['points']))])
    benefits = ''.join(f'<article>{illustration(*art[i])}<div class="benefit-copy"><h3>{e(title)}</h3><p>{e(text)}</p></div></article>' for i,(title,text) in enumerate(feature['points']))
    sections = []
    for i, section in enumerate(tour['sections']):
        text_only = section.get('text_only', False)
        bullets = ''.join(f'<li>{e(item)}</li>' for item in section['items'])
        after = f'<p>{e(section["after_text"])}</p>' if section.get('after_text') else ''
        if section.get('guide'):
            guide = section['guide']
            after += f'<a class="tour-guide-link" href="{e(guide["href"], quote=True)}">{e(guide["text"])} →</a>'
        copy = f'<div class="tour-copy"><h2>{e(section["title"])}</h2><p>{e(section["text"])}</p><ul class="tour-checks">{bullets}</ul>{after}</div>'
        if text_only:
            visual = ''
        elif section['image']:
            visual = picture(section['image'], CAPTIONS[section['image']])
        else:
            visual = '<div class="tour-notes"><span class="eyebrow">Keep in view</span>'+''.join(f'<div><span>0{j+1}</span><strong>{e(item)}</strong></div>' for j,item in enumerate(section['items']))+'</div>'
        sections.append(f'<section class="tour-section {"reverse" if i % 2 else ""}{" text-only" if text_only else ""}">{copy}{visual}</section>')
    steps = ''.join(f'<li><span>0{i+1}</span><h3>{e(step["title"])}</h3><p>{e(step["text"])}</p></li>' for i,step in enumerate(tour['steps']))
    related = ''.join(f'<a href="/features/{slug}/"><span class="eyebrow">Explore next</span><h3>{e(catalog[slug]["title"])} ↗</h3><p>{e(catalog[slug]["intro"])}</p></a>' for slug in tour['related'])
    walkthrough = ''
    if tour.get('walkthrough'):
        example = tour['walkthrough']
        routes = []
        for i, steps in enumerate((example['steps'][:1], example['steps'][1:])):
            sequence = ''.join(
                '<article>'+('<span class="eyebrow">Planned counter/threshold functionality</span>' if step.get('planned') else '')+
                f'<h3>{e(step["title"])}</h3><p>{e(step["text"])}</p></article>' for step in steps)
            route = example['routes'][i]
            routes.append(f'<div class="walkthrough-route"><div>{sequence}</div><figure><picture>'
                          f'<source media="(min-width:761px)" srcset="{e(route["wide_image"], quote=True)}" width="700" height="{280 if i == 0 else 370}">'
                          f'<img src="{e(route["image"], quote=True)}" alt="{e(route["alt"], quote=True)}" '
                          f'width="400" height="{390 if i == 0 else 540}" loading="lazy"></picture></figure></div>')
        walkthrough = (f'<section class="section gameplay-walkthrough"><h2>{e(example["title"])}</h2><p>{e(example["intro"])}</p>'
                       +''.join(routes)+f'<p>{e(example["closing"])}</p></section>')
    return (
        f'<main id="main" class="wrap feature-tour tour-{tour["layout"]}">'
        f'<section class="tour-hero">{intro}{hero}</section>'
        f'<section class="tour-overview" id="explore"><h2>{e(tour["headline"])}</h2><p>{e(tour["body"])}</p></section>'
        f'<div class="tour-benefits">{benefits}</div>'+''.join(sections)+
        f'<section class="tour-journey"><span class="eyebrow">A practical workflow</span><h2>From idea to working behaviour.</h2><ol>{steps}</ol></section>'
        f'<aside class="tour-example"><span class="eyebrow">In your machine</span><h2>{e(tour["example"]["title"])}</h2><p>{e(tour["example"]["text"])}</p></aside>'
        f'<section class="tour-related"><h2>Keep exploring.</h2><div>{related}</div></section>'
        +walkthrough+f'<section class="feature-guide"><h2>Ready for the details?</h2><p>Find setup instructions, controls and technical reference in the documentation.</p><div class="feature-guide-actions"><a class="button" href="{doc}">Read the {e(feature["title"])} guide →</a><a href="/start-building/">New to pinballCTL? Start here →</a></div></section></main>'
    )
