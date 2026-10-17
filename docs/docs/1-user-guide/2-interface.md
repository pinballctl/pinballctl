# Interface Tour

This page gives you a quick tour of the Pinball CTL interface so you can find what you need fast.

## Login

Open Pinball CTL in your browser and sign in.


<img src="./media/screenshot-login.webp" data-source='{"url":"/login","dark_mode":true}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

Default login credentials:

- Username: `admin`
- Password: `password`

Change the default password after your first login via `System -> Settings`.

## Light / Dark Mode

Light and dark mode can be toggled using the icon in the top right.

<img src="./media/screenshot-login-light.webp" data-source='{"url":"/login","dark_mode":false}' alt="Pinball CTL login screen" style="width: 100%;height: auto;">

## Dashboard Overview

After login, you land on the Dashboard. This is your at-a-glance machine status page.

<img src="./media/screenshot-dashboard.webp" data-source='{"url":"/login","next_url":"/dashboard","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Pinball CTL dashboard" style="width: 100%;height: auto;">

The dashboard cards show key status areas such as Wi-Fi, bridge state, ESP32 connectivity, dependencies, uptime, and gameplay or machine metrics.

Use this page first when checking whether your system is healthy.

## Control Centre

Use the grid icon in the top bar to open the Control Centre. This is the main navigation hub for all areas.

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
