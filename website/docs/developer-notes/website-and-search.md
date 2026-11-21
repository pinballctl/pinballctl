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

Documentation uses the full viewport width by default. The width icon at the
right of the breadcrumbs toggles between full width and a **1440 px** maximum.
Your saved preference applies across documentation pages and overrides the default.

At mobile widths, all documentation pages use one **16 px content gutter** and
a full-width reading surface. Breadcrumbs sit directly above the content, with
compact title spacing and no extra outer card padding.

Documentation pages stay within the viewport. Wide tables scroll inside their
own frame, with a dashed edge while columns remain off-screen; horizontal gestures
at a table edge must not move the whole page sideways. The shopping table includes
a Type column and uses the wide parts layout; other tables retain their normal sizing.

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

**Developer Notes → Test Bench → topic pages** is the navigation hierarchy.
Test Bench opens on **Course & layout**, followed by Materials & construction,
Lighting & wiring, Interface board, Power & USB and Shopping list.
Hardware inventory and Website are sibling topics under Developer Notes. The `/docs/developer-notes/`
URL redirects to Test Bench.

`website/content/docs-navigation.json` owns both navigation views and the order
of previous/next links. A group's `links` can contain another `{title, links}`
group. Desktop uses a collapsible sidebar. On mobile, **Menu → Documentation**
shows the categories; selecting a category or nested topic slides its child
panel into view. Each level has a Back button. Back, Escape or a left-to-right
swipe across the panel returns one level, restoring focus to the selected
category; Escape from the main menu closes it. The swipe gesture also works in
Features. Vertical swipes scroll the panel, and short drags do not change levels.
Panels scroll independently, and returning to a parent preserves its scroll
position. The current page and its parent categories are highlighted. Selecting
a page closes the menu; closing without navigating restores the page's scroll
position. Breadcrumbs and previous/next links provide additional routes between
related pages.

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

## Shopping-list purchase panel

**21 November 2026:** **Shop selected items** beside the Test Bench subtotal opens
a local panel containing only the products ticked **Need**, with their variants,
purchase quantities and individual Amazon links. Links open in a new tab; the
visitor adds each product to their basket on Amazon. P03 needs one pack of two sheets, P05
eight sensor pairs and P06 three packs of buttons. Whole-pack quantities are
preserved, including notes about how many pieces are actually fitted. The button
is disabled with no selections. Saved selections, subtotals and Need sorting
continue to work; opening a product does not clear its selection. The current
24 first-purchase items are grouped by type, starting with the box and MDF;
the remaining 15 items follow in their own type groups. Need sorting acts within
each table, while subtotals and the selected-items panel cover all groups.

This replaces the bulk basket button introduced earlier that day. It used
Amazon's [historically documented cart form](https://s3.amazonaws.com/awsdocs/ECS/20071029/ecs-dg-20071029.pdf#page=169),
but a reported empty basket was reproduced in a signed-in browser for both a
selected list and a single-product request. Correct outgoing product IDs and
quantities, and reaching a sign-in page, did not demonstrate successful insertion.
The individual product page still offered its normal Add to basket control.

The old form was removed instead of retaining an unreliable action. Amazon's
[current Creators API reference](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference)
lists product-catalogue operations, without a basket-writing operation. No
verified replacement bulk handoff has been established. Reconsider automatic
adding only after a supported route is confirmed and its actual basket result
is tested. The panel needs no affiliate identifier, API credentials, shopper
login or payment details. Prices, availability and sellers must still be checked
on Amazon; the documentation estimates are not refreshed by opening the panel.
