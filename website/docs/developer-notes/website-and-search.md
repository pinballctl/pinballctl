# Website and Search

## One documentation home

The main GitHub Pages site at [www.pinballctl.com](https://www.pinballctl.com/)
hosts the website and manual together. Authored documentation belongs in
`website/docs/`; component READMEs are short signposts. Developer Notes collect
key topics on maintained pages, with the current position and evidence together.

Engineering source, CAD and working test-bench records remain separate from
website output. Only reviewed text and selected illustrations are published.

## Old documentation site

The decision on 18 November 2026 is to retire the separate `docs.pinballctl.com`
site completely, including its holding homepage. Its repository retirement is
prepared separately; the project owner handles removing the domain. The main
website does not depend on that site or on a local `dist/docs-holding` directory.

The former main workflow generated and uploaded a duplicate holding artifact but
did not deploy it. That build output and upload are removed. The main site's
existing URL and source-bookmark compatibility mappings remain useful locally.

Removing old-domain DNS makes its URLs unreachable. Those mappings cannot catch
requests to a hostname that no longer resolves. Search results still included old
docs URLs during the review; retirement therefore gives up those entry points.
Google's preferred migration approach is page-specific permanent redirects kept
for at least a year. See [Google's site-move guidance](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes).

## Build output

Build in a temporary `build/website-*` workspace, validate it, then replace
`dist/site/` with the successful result. Temporary rendering files and the previous
generated site are cleaned up. A rendering or validation failure preserves the
last successful site. Keep `dist/site/` for preview and Pages upload; unrelated
package and firmware output stays outside this cleanup.

Run these commands from the repository root using the project Python environment:

```sh
.venv/bin/python website/utils/build-site.py
.venv/bin/python website/utils/check-site.py
.venv/bin/python -m http.server 8090 --directory dist/site
```

Preview at `http://localhost:8090`. The workflow in `.github/workflows/website.yml`
builds, checks and deploys `dist/site/` on pushes to `main`. After an authorised
push, check the workflow result and the changed live pages, links and assets.

## Search visibility review

The live checks on **18 November 2026** found:

- All 90 URLs in the live sitemap returned HTTP 200, with matching canonicals and
  no `noindex` directives in their HTML or HTTP headers.
- The homepage canonical was `https://www.pinballctl.com/`. Its title described a
  homebrew pinball controller for Raspberry Pi and ESP32.
- HTTP and non-`www` homepage variants returned permanent redirects to that URL.
- `robots.txt` allowed crawling and referenced the live sitemap. A nonexistent
  page returned HTTP 404.
- Public search results included the main site and some old docs-domain URLs.
  The old domain stopped resolving during the review.

These checks found no general technical indexing block. They do not establish
Google ranking, prove a penalty or explain a reported position change. The timing
and extent of any drop have not been confirmed with Search Console data.

Use Search Console to compare clicks, impressions, average position and affected
pages for `pinballctl` and `homebrew pinball controller`. Inspect Google's selected
canonical and indexing status for affected URLs, along with any manual-action or
security reports. Compare a known period before and after the drop before changing
titles or content again. See [Google's traffic-drop investigation guide](https://developers.google.com/search/docs/monitor-debug/debugging-search-traffic-drops).
