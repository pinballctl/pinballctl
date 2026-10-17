# Pinball CTL website

Static marketing site and documentation for **GitHub Pages**. No application server, database or client-side router is required. Each page has its own HTML file, canonical URL and search entry.

The original website and docs repositories still serve the live domains. Pushing commits to `main` automatically builds, validates and deploys the main website through GitHub Actions. Local commits alone do not publish. The entry point is `utils/build-site.py`; there is no source-root `index.html`. Open the generated site through the preview server below. Superseded website files remain recoverable in Git history.

## Build and preview

From the main repository root, with Python 3.10 or later:

```sh
python -m pip install Markdown==3.7 Pillow==12.0.0
python website/utils/build-site.py
python website/utils/check-site.py
python -m http.server 8090 --directory dist/site
```

Open `http://localhost:8090`. The builder creates ignored outputs:

- `dist/site/`: main site including `/features/`, `/docs/`, search, sitemap, legal pages and 404.
- `dist/docs-holding/`: the old docs domain holding page, including matching destinations for existing `/pages/*.html` links and `#doc=` bookmarks.

Preview the holding site separately with `python -m http.server 8091 --directory dist/docs-holding`.

## Editing

- Homepage feature summaries: `content/features.json`.
- Marketing page summaries: `content/features.json` and `content/feature-details.json`.
- Detailed feature tours, workflows and related links: `content/feature-tours.json`; layouts and screenshot captions: `utils/feature_pages.py`. Benefit illustrations and their per-page assignments: `utils/benefit_art.py`.
- Categorised feature navigation: `content/navigation.json`. Feature menu entries point to marketing pages; technical instructions remain in `/docs/`.
- Shared layout, homepage and page generation: `utils/build-site.py`.
- Styles and browser behaviour: `assets/css/site.css`, `assets/js/site.js`.
- Header illustration: `templates/banner.svg`.
- Documentation: `../docs/docs/**/*.md`; existing docs renderer and media are reused.
- Contact, privacy and terms: HTML content fragments in `templates/`.

Screenshots are resized automatically during the build into 400, 800 and 1200 pixel WebP variants where smaller than the original. Generated HTML includes responsive image choices and intrinsic dimensions; the zoom dialog loads the original screenshot. Keep source screenshots at full resolution and regenerate them with the existing screenshot utilities when the UI changes.

The builder generates `index.html`, `CNAME`, robots and sitemap files in the output directories; do not maintain duplicate copies here.

Rebuild after editing. The link checker rejects missing local page/image/script destinations. It does not validate external websites or the accuracy of documentation prose.

## Refresh application screenshots

Run the local application, then use the existing screenshot utility with the focused manifest:

```sh
python -m pip install playwright
python -m playwright install chromium
python docs/utils/build-screenshots.py --overwrite
python website/utils/build-screenshots.py --manifest website/utils/site-screenshots.txt --domain http://127.0.0.1:8888 --overwrite
python website/utils/build-screenshots.py --manifest website/utils/marketing-screenshots.txt --domain http://127.0.0.1:8888 --overwrite
python website/utils/build-site.py
```

Use the utility's `--username` and `--password` options if your login differs from its defaults. Review captures for machine-specific information before publishing. This manifest navigates the UI without firing outputs or syncing hardware. Documentation images continue to use the docs screenshot manifest and utility; these marketing captures do not refresh documentation images. The detailed marketing manifest captures tabs, open navigation and existing configuration dialogs without saving changes. Some selectors refer to the current example project (including a coil row and a Godot layer); adapt those selectors if the example project changes. Review no-device and platform-specific views as well as populated screens.

## GitHub Pages rollout

1. Review and commit the source changes. Every push to `main` runs **Build website and docs** and deploys after validation succeeds. For a manual build without publication, run it with **deploy unchecked**.
2. When ready to switch the main site, configure this repository's Pages source as **GitHub Actions**. Coordinate removing `www.pinballctl.com` from the old website repository and assigning it to this repository; GitHub cannot assign one custom domain to both simultaneously. Keep the old repository available for rollback. Verify the account/domain ownership and DNS settings in Pages, and enable HTTPS.
3. Push the reviewed changes to `main`, or run the workflow manually with **deploy checked**. It publishes only `dist/site`, which contains `CNAME` and `.nojekyll`. Check the homepage, a feature URL, a deep docs URL, search and images on the public domain.
4. **Only after the new `/docs/` is live**, download `docs-domain-holding-page` and publish its contents to the existing docs repository's Pages root. Retain `docs.pinballctl.com` there. This workflow deliberately does not write to that separate repository.
5. Submit the new main sitemap in Search Console and verify analytics in GA Realtime/DebugView with analytics enabled. Keep old docs URLs accessible while search engines recrawl them.

The holding pages link to the new documentation and declare matching canonical URLs. They do not automatically redirect visitors. Canonicals are search-engine hints, not HTTP 301 redirects or a guarantee of index migration. See [Google's canonical guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

## Analytics

The rebuilt site uses the existing main property `G-V8YD2KZZ9W` across marketing and docs. Each HTML navigation produces one automatic page view. Named events cover getting started, GitHub links, search opening/result selection and screenshot previews; raw search text is not sent as a custom event. Analytics loads by default only on `www.pinballctl.com`, unless a saved opt-out exists; localhost previews do not send traffic. A visible first-visit notice and Cookie settings allow opting out. Saved opt-outs are honoured across pages and visits. Opting out disables subsequent tracking and clears accessible GA cookies; it cannot retract earlier transmissions. Default-on behaviour is a product choice, not confirmation of a legal consent exemption.

Check the GA property's enhanced-measurement configuration before rollout, particularly history-based page views and site-search settings. Do not add a second manual page-view handler. See [GA4 page-view guidance](https://developers.google.com/analytics/devguides/collection/ga4/views). Historical data in the old docs property is not migrated. The holding domain itself does not load analytics.

## Search metadata

Feature records support `seo_title` and `seo_description` independently of the short navigation labels. Titles describe the actual tool and its homebrew pinball use; primary pages explain browser authoring, Raspberry Pi orchestration and ESP32 control. Open Graph and Twitter metadata share those descriptions and use the page's first feature screenshot when available. Canonical URLs remain on www.pinballctl.com.

The positioning review compared [Mission Pinball Framework](https://missionpinball.org/latest/start/) and [FAST Pinball](https://fastpinball.com/learning/). The emphasis here is the integrated visual authoring workflow, not claims of hardware compatibility or superiority over those projects. Follow [Google's descriptive title guidance](https://developers.google.com/search/docs/appearance/title-link); metadata improves clarity but does not guarantee rankings.

The development-platform cost tables use the existing `docs/assets/js/components.js` calculator, included only when the summary is present. When modifying that page, verify the total, category filter, sorting and category breakdown in a browser, in addition to the static link checker.


## Search appearance

The homepage targets homebrew pinball controller searches with descriptive copy and a matching title. Shared metadata in `utils/search_metadata.py` adds the pinballCTL site identity, canonical page entities, breadcrumbs and the feature directory's visible categories. Keep those categories in `content/navigation.json` accurate; the markup uses the same source as the navigation.

Google chooses sitelinks automatically. Category lists describe the site but do not guarantee a rich result. Do not add fabricated ratings, reviews, product prices, company identities or keyword-stuffed pages. The site does not currently qualify for a rated software-app listing.

After publishing, inspect the homepage and a feature page with Google's Rich Results Test and Search Console URL Inspection. Request indexing for changed key pages and keep `https://www.pinballctl.com/sitemap.xml` submitted. Monitor queries such as “pinball controller”, “homebrew pinball controller” and “Raspberry Pi pinball controller”; compare impressions and clicks over time, not individual personalized search results.

Guidance: [Google sitelinks](https://developers.google.com/search/docs/appearance/sitelinks), [site names](https://developers.google.com/search/docs/appearance/site-names), [breadcrumbs](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb) and [structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies).
