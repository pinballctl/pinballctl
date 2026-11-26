# Interface Tour

The Pinball CTL web interface is where you configure your machine, build your game and check how it’s running. Pages share a consistent layout, and the Control Centre groups tools by purpose so you can find what you need and bookmark the pages you use most.

Switch between light and dark mode from the top bar. The layout adapts to desktops, tablets and phones, with compact controls on smaller screens.

## Before you start

To set up Pinball CTL, follow [Quick Start](getting-started.md#quick-start) or [Detailed Setup](getting-started.md#detailed-setup).

## Login

Open Pinball CTL in your browser and sign in.

<img src="./media/screenshot-login.webp" data-source='{"url":"/login","dark_mode":true}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

Default login credentials:

- Username: `admin`
- Password: `password`

Change the default password after your first login under **Settings → Access**.

## Navigation and page controls

### Shared layout and settings

Every module uses the same header, table, form and panel styling. Saved favourites remain in the top bar; scroll the favourites strip horizontally when it contains more shortcuts than fit on screen.

Configuration editors such as Hardware driver settings, Scoring rules and combos, Service Log entries and Lighting frame tags/cast selection open in a panel on the right, with a blurred backdrop. Long forms scroll inside the panel while its header and actions remain available. Existing save, close and validation behaviour is unchanged; confirmation and status dialogs remain centred.

The right-side editors share the same desktop width and theme background, and fit the screen on mobile. Sliders icons open settings; trash icons remove an item. Tooltips identify icon-only actions. Compact action buttons share a consistent height and icon size across tables and settings panels; page headers and form controls use the shared application styles.

Hardware, Rules and Lighting sync buttons stay muted while their status is loading or the ESP is already in sync. A green outline means a sync is needed. Save your draft changes before syncing.

### Light / Dark Mode

Light and dark mode can be toggled using the icon in the top right. Light mode uses dark blue card headers, white editing surfaces and stronger field borders to make sections and controls easier to distinguish.

<img src="./media/screenshot-login-light.webp" data-source='{"url":"/login","dark_mode":false}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

### Dashboard Overview

After login, you land on the Dashboard.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"full_page":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Pinball CTL dashboard" style="width: 100%;height: auto;">

The dashboard cards show Wi-Fi, bridge state and host uptime together in Bridge & Uptime, ESP32 connectivity, dependencies, recent game and player activity in Gameplay, and saved maintenance activity in Machine.

### Control Centre

Use **All Tools** (the grid icon on smaller screens) in the top bar to open the Control Centre.

<img src="./media/screenshot-control-center.webp"
     data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":"#flood-menu-body .flood-grid"}]}'
     alt="Control Centre with Game Management, Ball Management and High Scores under Authoring and Backup / Restore under Overview and System" style="width: 100%;height: auto;">

The Control Centre groups pages by purpose:

- **Overview and System** includes Dashboard, Wi-Fi, Settings and Backup / Restore.
- **Authoring** includes Rules, Scoring, Game Management, Ball Management, High Scores, Lighting and Playfield.
- **Platform** includes Hardware, Firmware and ESPLink.
- **Operations** includes Logs, Service Log and Documentation.

### Find and bookmark a module

1. Open the dashboard after login and check connection/service status. **Expected:** you know whether you are authoring offline or connected to the machine.

2. Choose **All Tools** in the header to open the Control Centre. Search for a module, then select it. **Expected:** the intended workspace opens.

3. Use bookmarks/recent pages for repeated work, and theme controls for the application display where available. **Expected:** navigation preferences make the workspace easier to use without changing project behaviour.

4. After editing a module, use its Save action and inspect any separate sync/runtime status. **Expected:** you can distinguish a saved draft, deployed configuration and live effect.

### Search

Use the search box (top right of Control Centre) to filter the available pages.

<img src="./media/screenshot-control-center-search.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":"#flood-menu-body .flood-grid"}],"highlight":{"selector":".flood-menu-head-actions","style":"border: 4px solid red; border-radius: 8px;"}}' alt="Control Centre search box" style="width: 100%;height: auto;">

Search is best when you type the page name directly, for example: `lighting`, `rules`, or `hardware`, then click the page you want.

### Recently Visited

The Recently Visited row gives one-click access to pages you opened recently.

<img src="./media/screenshot-control-center-recent.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"rules\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"hardware\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"click","selector":"[data-nav-link][data-module-name=\"settings\"]","wait_for":"h1"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"wait","wait_for":".flood-recent"}],"highlight":{"selector":".flood-recent","style":"border: 4px solid red; border-radius: 8px; padding: 6px;"}}' alt="Recently visited pages" style="width: 100%;height: auto;">

### Bookmarks

When you hover over a link, a yellow bookmark icon appears.

Clicking the icon adds that link to the top bookmarks menu for faster access to frequently used areas.

<img src="./media/screenshot-control-center-bookmarks-hover.webp" data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"hover","selector":".flood-link[data-module-name=\"rules\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"rules\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"hardware\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"hardware\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"settings\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"settings\"]"},{"action":"wait","wait_for":"button[data-fav-toggle].is-saved"}],"highlight":{"selector":"button[data-fav-toggle].is-saved","style":"border: 4px solid red; border-radius: 8px;"}}' alt="Bookmark icons highlighted in menu" style="width: 100%;height: auto;">

Drag a bookmark along the top bar to reorder it. The dashed outline shows where the bookmark will land.

<img src="./media/screenshot-control-center-bookmarks.webp"
     data-source='{"url":"/login","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"},{"action":"click","selector":"[data-menu-toggle]","wait_for":"body.flood-open"},{"action":"hover","selector":".flood-link[data-module-name=\"rules\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"rules\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"hardware\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"hardware\"]"},{"action":"hover","selector":".flood-link[data-module-name=\"settings\"]"},{"action":"click","selector":"button[data-fav-toggle][data-module-name=\"settings\"]"},{"action":"click","selector":"[data-menu-toggle]"},{"action":"wait","wait_for":"#fav-bar .fav-pill"}],"target":"#fav-bar","target_content":true,"target_padding":12,"before_capture_js":"function () { const bar = document.querySelector(\"#fav-bar\"); const handle = bar.querySelector(\"[data-module-name=settings] .fav-drag-handle\"); const hardware = bar.querySelector(\"[data-module-name=hardware]\").getBoundingClientRect(); const dataTransfer = new DataTransfer(); handle.dispatchEvent(new DragEvent(\"dragstart\", {bubbles: true, dataTransfer})); bar.dispatchEvent(new DragEvent(\"dragover\", {bubbles: true, cancelable: true, dataTransfer, clientX: hardware.left + 1})); if (!bar.querySelector(\".drag-placeholder\")) throw new Error(\"Bookmark drop position did not appear\"); }"}'
     alt="Settings bookmark being dragged into the dashed drop position between Rules and Hardware">

Remove actions use a trash icon with a hover tooltip and an accessible label. Existing confirmation dialogs still identify the action before removal.

Table sections place their title, count and controls above the table, leaving one coloured row for column headings.

Firmware, Scoring and Integrity Check keep filters and actions above their tables. Runtime tables follow the same layout; compact sliders buttons open Service entry and Lighting cast settings.

## Troubleshooting

If a module is not visible, clear Control Centre search and check the current build. For login or page-load issues, use the start mode/port and logs from Detailed Setup.

## Related guides

Next: [Dashboard](dashboard.md), [Quick Start](getting-started.md#quick-start), [Settings](settings.md).
