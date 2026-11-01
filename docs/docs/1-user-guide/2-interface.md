# Interface Tour

Find the tool you need, move between modules and recognise the difference between a saved project and a running machine.

## Before you start

Open the application using the actual configured address/port and sign in. For first installation, use Detailed Setup.

## Try it step by step

1. Open the dashboard after login and check connection/service status. **Expected:** you know whether you are authoring offline or connected to the machine.

2. Choose **All Tools** in the header to open the Control Centre. Search for a module, then select it. **Expected:** the intended workspace opens.

3. Use bookmarks/recent pages for repeated work, and theme controls for the application display where available. **Expected:** navigation preferences make the workspace easier to use without changing project behaviour.

4. After editing a module, use its Save action and inspect any separate sync/runtime status. **Expected:** you can distinguish a saved draft, deployed configuration and live effect.

<img src="./media/screenshot-login.webp" data-source='{"url":"/login","dark_mode":true}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

**Screen guide:** 1. Sign-in opens the dashboard. 2. All Tools opens navigation. 3. Save and sync remain module-specific operations.

## Helpful checks

Application navigation and the public manual sidebar are different controls. On small screens, some application buttons use an icon instead of their desktop text label.

**Safety:** A module opening successfully does not make a connected output safe to test. Keep output power off while learning event/test controls.

## If the result is different

If a module is not visible, clear Control Centre search and check the current build. For login or page-load issues, use the start mode/port and logs from Detailed Setup.

## Continue your build

Next: [Dashboard](5-dashboard.md), [Quick Start](0-quick-start.md), [Settings](16-settings.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## Login

Open Pinball CTL in your browser and sign in.




Default login credentials:

- Username: `admin`
- Password: `password`

Change the default password after your first login via `System -> Settings`.

## Shared layout and settings

Every module uses the same header, table, form and panel styling. Saved favourites remain in the top bar; scroll the favourites strip horizontally when it contains more shortcuts than fit on screen.

Configuration editors such as Hardware driver settings, Scoring rules and combos, Service Log entries and Lighting frame tags/cast selection open in a panel on the right, with a blurred backdrop. Long forms scroll inside the panel while its header and actions remain available. Existing save, close and validation behaviour is unchanged; confirmation and status dialogs remain centred.

The right-side editors share the same desktop width and theme background, and fit the screen on mobile. Sliders icons open settings; trash icons remove an item. Tooltips identify icon-only actions. Compact action buttons share a consistent height and icon size across tables and settings panels; page headers and form controls use the shared application styles.

Hardware, Rules and Lighting sync buttons stay muted while their status is loading or the ESP is already in sync. A green outline means a sync is needed. Save your draft changes before syncing.

## Light / Dark Mode

Light and dark mode can be toggled using the icon in the top right. Light mode uses dark blue card headers, white editing surfaces and stronger field borders to make sections and controls easier to distinguish.

<img src="./media/screenshot-login-light.webp" data-source='{"url":"/login","dark_mode":false}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

## Dashboard Overview

After login, you land on the Dashboard. This is your at-a-glance machine status page.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Pinball CTL dashboard" style="width: 100%;height: auto;">

The dashboard cards show key status areas such as Wi-Fi, bridge state, ESP32 connectivity, dependencies, uptime, and gameplay or machine metrics.

Use this page first when checking whether your system is healthy.

## Control Centre

Use **All Tools** (the grid icon on smaller screens) in the top bar to open the Control Centre. This is the main navigation hub for all areas.

<img src="./media/screenshot-control-center.webp"
     data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":"#flood-menu-body .flood-grid"}]}'
     alt="Pinball CTL control centre" style="width: 100%;height: auto;">

The Control Centre groups pages by purpose:

- Overview & System: high-level operational pages and settings such as Wi-Fi and install-wide options.
- Authoring: Rules, Lighting, and playfield-related work.
- Platform: hardware, firmware, and ESPLink.
- Operations: logs and service diagnostics.

## Search

Use the search box (top right of Control Centre) to filter the available pages.

<img src="./media/screenshot-control-center-search.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":"#flood-menu-body .flood-grid"}],"highlight":{"selector":".flood-menu-head-actions","style":"border: 4px solid red; border-radius: 8px;"}}' alt="Control Centre search box" style="width: 100%;height: auto;">

Search is best when you type the page name directly, for example: `lighting`, `rules`, or `hardware`, then click the page you want.

## Recently Visited

Pinball CTL keeps quick shortcuts so you can get back to pages you use most.

The Recently Visited row gives one-click access to pages you opened recently.

<img src="./media/screenshot-control-center-recent.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"rules\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"hardware\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"settings\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":".flood-recent"}],"highlight":{"selector":".flood-recent","style":"border: 4px solid red; border-radius: 8px; padding: 6px;"}}' alt="Recently visited pages" style="width: 100%;height: auto;">

## Bookmarks

When you hover over a link, a yellow bookmark icon appears.

Clicking the icon adds that link to the top bookmarks menu for faster access to frequently used areas.

<img src="./media/screenshot-control-center-bookmarks-hover.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"hover","selector":".flood-link[data-module-name=\"rules\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"rules\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"hardware\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"hardware\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"settings\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"settings\"]"},{"action":"wait","wait_for":"button[data-fav-toggle].is-saved"}],"highlight":{"selector":"button[data-fav-toggle].is-saved","style":"border: 4px solid red; border-radius: 8px;"}}' alt="Bookmark icons highlighted in menu" style="width: 100%;height: auto;">

You can also drag and drop items in the top bookmarks menu to arrange them in your preferred order.

<img src="./media/screenshot-control-center-bookmarks.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"hover","selector":".flood-link[data-module-name=\"rules\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"rules\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"hardware\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"hardware\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"settings\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"settings\"]"},{"action":"click","selector":"[data-menu-toggle]"},{"action":"wait","wait_for":"#fav-bar .fav-pill"}],"highlight":{"selector":"#fav-bar","style":"border: 4px solid red; border-radius: 8px; padding: 4px;"}}' alt="Bookmarked pages in top bar" style="width: 100%;height: auto;">

Remove actions use a trash icon with a hover tooltip and an accessible label. Existing confirmation dialogs still identify the action before removal.

Table sections place their title, count and controls above the table, leaving one coloured row for column headings.

Firmware, Scoring and Integrity Check keep filters and actions above their tables. Runtime tables follow the same layout; compact sliders buttons open Service entry and Lighting cast settings.
