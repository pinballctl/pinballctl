# Website

## Current setup

[www.pinballctl.com](https://www.pinballctl.com/) is a static GitHub Pages site
containing the project website and documentation. Sources live in this repository;
the published site is generated from them.

- `website/docs/`: user guides, technical references, Developer Guide and Developer Notes.
- `website/content/`: navigation, feature content and documentation URL mappings.
- `website/templates/`: shared page content and illustrations.
- `website/assets/`: styles, browser scripts, screenshots and documentation images.
- `website/utils/`: site builder, Markdown renderer, link checker and screenshot tools.
- `.github/workflows/website.yml`: GitHub Actions build and Pages deployment.

Edit source files rather than generated HTML. Update navigation and links when
pages change, and review text and images before publication to exclude personal
information, credentials and private machine data.

## Build output

Run commands from the repository root. Use the project's `.venv` with Python 3.12
or later; see [Development and testing](../developer-guide/development.md) for the
checkout setup. Install the website dependencies if needed:

```sh
.venv/bin/python -m pip install Markdown==3.7 Pillow==12.0.0
```

Build and validate the site:

```sh
.venv/bin/python website/utils/build-site.py
```

The builder renders into a temporary `build/website-*` workspace, runs the site
checker and removes the generated files when finished. Failed builds also clean
their temporary output. No final website directory is retained by this command.
The checker validates local page, image and section links, redirects and metadata;
it does not verify external websites or the technical accuracy of the prose.

To preview locally:

```sh
.venv/bin/python website/utils/build-site.py --preview
```

Open `http://localhost:8090`. Check changed pages, navigation and images at desktop
and mobile widths. Stop with **Ctrl+C** to close the server and remove the preview
files. Use `--preview 8091` if another port is needed.

Documentation pages stay within the viewport. Wide tables scroll inside their
own frame, with a dashed edge while columns remain off-screen; horizontal gestures
at a table edge must not move the whole page sideways. Only six-column shopping
tables receive the wide parts layout, not every table containing a thumbnail.

Automation that needs files for upload can use `--output build/site`, followed by
`website/utils/check-site.py --site build/site`. This explicitly retains a checked
artifact; the caller must remove it after use. Outputs must stay inside `build/`,
and existing nonempty directories need the website build marker before replacement.
Unrelated package and firmware output is left alone.

## Publishing

Commit the intended source changes and push `main`. The **Build website and docs**
workflow then:

1. Sets up Python 3.12 and installs the website dependencies.
2. Builds and checks the site.
3. Uploads `build/site/` as the GitHub Pages artifact.
4. Removes `build/site/` in an unconditional cleanup step, including after a failed upload.
5. Deploys the checked artifact to [www.pinballctl.com](https://www.pinballctl.com/).

The workflow also supports a manual run from GitHub Actions. Leave **deploy**
unchecked to build and validate only, or enable it to publish the result.

After publishing, check that both the build and deploy jobs succeeded. Open the
live homepage and changed documentation pages, check their links and images, and
verify any redirects for moved or removed pages. A local build or commit alone
does not update the live site.

## Documentation navigation

**21 November 2026:** Larger Developer Notes topics can have focused pages inside
one menu group. **Developer Notes → Test Bench → topic pages** is the navigation
hierarchy; Developer Notes has no overview page or Overview menu item. Test Bench
opens directly on **Course & layout**, followed by
Materials & construction, Lighting & wiring, Interface board, Power & host
connections, Shopping list, and Checks & next steps. The earlier enclosure study
stays in that group at its existing URL. Overview pages were removed because they
added an extra step before the useful content. Website remains a sibling topic
under Developer Notes. The retired `/docs/developer-notes/` URL redirects directly
to Test Bench, and authored links point straight to the relevant topic.
Each topic retains one maintained source; the engineering design, historical
price checks and outstanding physical validation requirements are unchanged.

`website/content/docs-navigation.json` owns both navigation views and the order
of previous/next links. A group's `links` can contain another `{title, links}`
group. Desktop uses a collapsible sidebar. On mobile, **Menu → Documentation**
opens the same hierarchy inside the main navigation panel, with the current
group expanded, a highlighted page and a Back button. There is no separate
Browse documentation button above the article. The panel scrolls independently;
Back or Escape returns to the main menu, and closing it restores the page's
scroll position. Page breadcrumbs and previous/next links provide additional
routes between related pages.

The original Test Bench URL now contains the course and layout. Its old section
bookmarks link to the moved sections and forward there when JavaScript is
available. With JavaScript disabled, the original page retains an expandable
list of direct section links. The shopping checklist keeps its existing browser
storage key, so moving its page does not reset saved Need selections.

When adding or moving topics, validate the build and check desktop/mobile menu
navigation, keyboard focus, old section bookmarks, search results and any page
interactions. The build checks local links and destinations; browser checks are
still needed for focus, scrolling and responsive layout.

Validation for this change passed the complete site/link check and 14 documentation
tests. Chromium and WebKit checks covered 320, 390, 740 and 1440 px widths, keyboard
navigation, menu back/close controls, scroll restoration, all 21 moved section
bookmarks, search and saved shopping selections. Direct section links and the
shopping table also remained readable with JavaScript disabled. These checks do
not validate the bench hardware or refresh supplier prices.

## Shopping-list basket handoff

**21 November 2026:** The Test Bench shopping list offers **Add selected to Amazon
basket** beside the selected-items subtotal. It uses the same Need selections and
the leading purchase quantity in each row: P03 sends two sheets, P05 eight sensor
pairs and P06 three packs of buttons. Pack contents and the number actually fitted
are not separate Amazon quantities. The button is disabled when nothing is
selected, and saved selections and Need sorting continue to work.

The browser submits a GET form to Amazon.co.uk in a new tab, containing numbered
`ASIN.x` and `Quantity.x` fields for every selected product. This follows Amazon's
[documented cart form](https://s3.amazonaws.com/awsdocs/ECS/20071029/ecs-dg-20071029.pdf#page=169)
(historical documentation), also referenced by its
[Associates help](https://affiliate-program.amazon.com/help/node/topic/GUVFJTV7MGMMNY94).
No affiliate identifier, API credentials, shopper login or payment details are
stored by the site. A server-side cart integration was unnecessary for this
handoff; the website does not submit an order or report that Amazon accepted the
items. Selections remain ticked when the visitor returns.

Browser checks in Chromium and WebKit covered empty, partial and all-39 selections,
whole-pack quantities, sorting, saved selections and 320, 390 and 1440 px layouts.
A signed-out check reached Amazon's sign-in page with all 39 product IDs and
quantities preserved in its return destination. Authenticated basket insertion,
current offers and variant availability must still be reviewed on Amazon; they
cannot be confirmed by the static site's local checks. The individual product
links remain available if Amazon cannot add an item. The cited cart documentation
is historical, so recheck the live handoff if Amazon changes this route.
