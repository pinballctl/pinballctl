# Pinball CTL website

Static marketing site and documentation for **GitHub Pages**. No application server, database or client-side router is required. Each page has its own HTML file, canonical URL and search entry.

The original website and docs repositories still serve the live domains. Pushing commits to `main` automatically builds, validates and deploys the main website through GitHub Actions. Local commits alone do not publish. The entry point is `utils/build-site.py`; there is no source-root `index.html`. Open the generated site through the preview server below. Superseded website files remain recoverable in Git history.

## Build and preview

From the main repository root, with Python 3.10 or later:

```sh
python -m pip install Markdown==3.7
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
- Individual marketing pages: `content/feature-details.json`.
- Categorised feature navigation: `content/navigation.json`. Feature menu entries point to marketing pages; technical instructions remain in `/docs/`.
- Shared layout, homepage and page generation: `utils/build-site.py`.
- Styles and browser behaviour: `assets/css/site.css`, `assets/js/site.js`.
- Header illustration: `templates/banner.svg`.
- Documentation: `../docs/docs/**/*.md`; existing docs renderer and media are reused.
- Contact, privacy and terms: HTML content fragments in `templates/`.

The builder generates `index.html`, `CNAME`, robots and sitemap files in the output directories; do not maintain duplicate copies here.

Rebuild after editing. The link checker rejects missing local page/image/script destinations. It does not validate external websites or the accuracy of documentation prose.

## Refresh application screenshots

Run the local application, then use the existing screenshot utility with the focused manifest:

```sh
python -m pip install playwright
python -m playwright install chromium
python website/utils/build-screenshots.py --manifest website/utils/site-screenshots.txt --domain http://127.0.0.1:8888 --overwrite
python website/utils/build-site.py
```

Use the utility's `--username` and `--password` options if your login differs from its defaults. Review captures for machine-specific information before publishing. This manifest navigates the UI without firing outputs or syncing hardware. Documentation images continue to use the docs screenshot manifest and utility; the seven marketing captures do not refresh every documentation image.

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
