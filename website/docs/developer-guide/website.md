# Website and documentation

The public website and manual are one static GitHub Pages site. Each page has its
own HTML file, canonical URL and search entry. The source is `website/`; documentation
is authored under `website/docs/`. Run commands below from the repository root.

## Build and preview

Use the project environment with Python 3.12 or later:

```sh
.venv/bin/python -m pip install Markdown==3.7 Pillow==12.0.0
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/check-site.py
.venv/bin/python -m http.server 8090 --directory dist/site
```

Open `http://localhost:8090`. The builder only replaces its marked output directories:

- `dist/site/`: website, `/docs/`, search, sitemap, legal pages and 404.
- `dist/docs-holding/`: old documentation-domain holding pages with destinations for legacy `/pages/*.html` links and `#doc=` bookmarks.

Preview the holding artifact with a separate server on port 8091. It remains part
of the build and checks; it is not an abandoned review snapshot. Never edit generated
HTML or commit `dist/`. Keep temporary visual comparisons outside the source tree.

## Editing sources

| Content | Source |
| --- | --- |
| Guides, manual home and changelog | `website/docs/` |
| Dated log entries and log overview | `website/docs/developer-log/` |
| Log dates, tags and related entry IDs | `website/content/developer-log.json` |
| Docs reading order | `website/content/docs-navigation.json` |
| Old source bookmark mapping | `website/content/docs-legacy.json` |
| Feature summaries and tours | `website/content/features.json`, `feature-details.json`, `feature-tours.json` |
| Feature navigation | `website/content/navigation.json` |
| Shared page generation and docs renderer | `website/utils/build-site.py`, `docs_renderer.py` |
| Layout and browser behaviour | `website/assets/css/site.css`, `website/assets/js/site.js` |
| Documentation images and calculator | `website/assets/docs/` |
| Marketing illustrations and screenshots | `website/assets/img/` |
| Contact, terms, privacy and status content | `website/templates/` |

Use explicit relative Markdown links between guides. Existing public URLs stay stable
when a source moves; add redirects for intentional URL changes and keep legacy bookmark
mappings. The builder checks missing Markdown targets. The site checker validates page,
asset, log/tag and canonical destinations; it does not verify external websites or the
technical truth of prose.

The test-bench renderers retain `docs/media/test-bench-*` output paths. Only preview
images referenced by authored guides are copied into the website. CAD sources, local
reports, prompt records and unrelated working images are not bulk-published.

Shared components include navigation, the In Development ribbon, search, screenshot
zoom and responsive images. Preserve their behaviour when editing guides. Check the
changed pages on desktop and mobile, including navigation and keyboard interaction.

## Refresh application screenshots

Run the local application, then use the existing capture tools:

```sh
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python website/utils/build-doc-screenshots.py --dry-run
.venv/bin/python website/utils/build-doc-screenshots.py --overwrite
.venv/bin/python website/utils/build-screenshots.py --manifest website/utils/site-screenshots.txt --domain http://127.0.0.1:8888 --overwrite
.venv/bin/python website/utils/build-screenshots.py --manifest website/utils/marketing-screenshots.txt --domain http://127.0.0.1:8888 --overwrite
.venv/bin/python website/utils/build-site.py
```

Documentation capture instructions live in `pinballctl-shot` comments or image
`data-source` JSON. Outputs such as `media/screenshot-login.webp` resolve under
`website/assets/docs/`. The default domain is `http://127.0.0.1:8888`; default login
is `admin` / `password`. Use `--username` and `--password` when appropriate. Review
captures for machine-specific information before publishing.

The marketing manifests navigate the UI without firing outputs or syncing hardware.
Some selectors depend on the local example project; adapt them to your configuration.
An application screenshot refresh is needed when application UI changes, not for a
source-folder move. The site build generates responsive variants from source images.

## GitHub Pages deployment

`.github/workflows/website.yml` builds and validates each push to `main`, then deploys
`dist/site/` to GitHub Pages. It also supports a manual run with a `deploy` option;
unchecked builds without publication. GitHub Pages hosts `www.pinballctl.com`.
Local commits alone do not publish. After an authorised push, check the workflow
result and the live homepage, changed guide URLs, navigation and assets.

The workflow uploads `dist/docs-holding/` as the `docs-domain-holding-page` artifact.
It does not deploy that artifact to the separate old-domain repository. Preserve
its mappings while old links remain useful. The holding pages offer links and
canonical destinations; they do not issue HTTP 301 redirects. No DNS, custom-domain
or Pages source changes are needed for normal guide updates.

## Analytics

The rebuilt site uses the existing main property `G-V8YD2KZZ9W` across marketing and docs. Each HTML navigation produces one automatic page view. Named events cover getting started, GitHub links, search opening/result selection and screenshot previews; raw search text is not sent as a custom event. Analytics loads by default only on `www.pinballctl.com`, unless a saved opt-out exists; localhost previews do not send traffic. A visible first-visit notice and Cookie settings allow opting out. Saved opt-outs are honoured across pages and visits. Opting out disables subsequent tracking and clears accessible GA cookies; it cannot retract earlier transmissions. Default-on behaviour is a product choice, not confirmation of a legal consent exemption.

Check the GA property's enhanced-measurement configuration before rollout, particularly history-based page views and site-search settings. Do not add a second manual page-view handler. See [GA4 page-view guidance](https://developers.google.com/analytics/devguides/collection/ga4/views). Historical data in the old docs property is not migrated. The holding domain itself does not load analytics.

## Search metadata

Feature records support `seo_title` and `seo_description` independently of the short navigation labels. Titles describe the actual tool and its homebrew pinball use; primary pages explain browser authoring, Raspberry Pi orchestration and ESP32 control. Open Graph and Twitter metadata share those descriptions and use the page's first feature screenshot when available. Canonical URLs remain on www.pinballctl.com.

The positioning review compared [Mission Pinball Framework](https://missionpinball.org/latest/start/) and [FAST Pinball](https://fastpinball.com/learning/). The emphasis here is the integrated visual authoring workflow, not claims of hardware compatibility or superiority over those projects. Follow [Google's descriptive title guidance](https://developers.google.com/search/docs/appearance/title-link); metadata improves clarity but does not guarantee rankings.

The development-platform cost tables use the existing `website/assets/docs/assets/js/components.js` calculator, included only when the summary is present. When modifying that page, verify the total, category filter, sorting and category breakdown in a browser, in addition to the static link checker.


## Search appearance

The homepage targets homebrew pinball controller searches with descriptive copy and a matching title. Shared metadata in `utils/search_metadata.py` adds the pinballCTL site identity, canonical page entities, breadcrumbs and the feature directory's visible categories. Keep those categories in `content/navigation.json` accurate; the markup uses the same source as the navigation.

Google chooses sitelinks automatically. Category lists describe the site but do not guarantee a rich result. Do not add fabricated ratings, reviews, product prices, company identities or keyword-stuffed pages. The site does not currently qualify for a rated software-app listing.

After publishing, inspect the homepage and a feature page with Google's Rich Results Test and Search Console URL Inspection. Request indexing for changed key pages and keep `https://www.pinballctl.com/sitemap.xml` submitted. Monitor queries such as “pinball controller”, “homebrew pinball controller” and “Raspberry Pi pinball controller”; compare impressions and clicks over time, not individual personalized search results.

Guidance: [Google sitelinks](https://developers.google.com/search/docs/appearance/sitelinks), [site names](https://developers.google.com/search/docs/appearance/site-names), [breadcrumbs](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb) and [structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies).
