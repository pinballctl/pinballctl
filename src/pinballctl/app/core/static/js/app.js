// Global UI helpers (vanilla) for theme toggling and nav behaviors.
(function () {
  const THEME_KEY = "theme";

  function preferredTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored) return stored;
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : "light";
  }

  function applyTheme(theme) {
    const mode = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", mode);
    document.documentElement.setAttribute("data-bs-theme", mode); // Bootstrap v5.3 theme hook
    try { localStorage.setItem(THEME_KEY, mode); } catch (_) {}
  }

  // Apply immediately to avoid flash
  applyTheme(preferredTheme());

  function wireThemeToggle() {
    const btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    const iconSpan = btn.querySelector("[data-theme-icon]");

    function updateLabel(mode) {
      if (iconSpan) {
        iconSpan.classList.remove("fa-moon", "fa-sun");
        iconSpan.classList.add(mode === "dark" ? "fa-moon" : "fa-sun");
      }
      btn.setAttribute("aria-label", mode === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }

    btn.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      updateLabel(next);
    });

    updateLabel(document.documentElement.getAttribute("data-theme") || preferredTheme());
  }

  function wireMenuActiveState() {
    const path = window.location.pathname;
    document.querySelectorAll("[data-nav-link]").forEach((link) => {
      if (!link.getAttribute("href")) return;
      const href = link.getAttribute("href") || "";
      const cleanHref = href.split("#")[0].split("?")[0];
      if (cleanHref && path.startsWith(cleanHref)) {
        link.classList.add("active");
      }
    });
  }

  function wireTooltips() {
    if (typeof bootstrap === "undefined" || !bootstrap.Tooltip) return;
    const tooltipTriggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggers.forEach((el) => {
      bootstrap.Tooltip.getOrCreateInstance(el);
    });
  }

  function wireFloodMenu() {
    const toggleBtn = document.querySelector("[data-menu-toggle]");
    const overlay = document.querySelector("[data-flood-overlay]");
    const menu = document.querySelector("[data-flood-menu]");
    const closeBtn = document.querySelector("[data-flood-close]");
    const searchEl = document.getElementById("flood-search");
    const body = document.getElementById("flood-menu-body");
    const favBar = document.getElementById("fav-bar");
    const dataEl = document.getElementById("menu-modules-data");
    if (!toggleBtn || !overlay || !menu || !body || !dataEl) return;

    const FAV_KEY = "pinballctl.menu.favorites.v1";
    const RECENT_KEY = "pinballctl.menu.recent.v1";
    const FAV_MAX = 15;
    const RECENT_MAX = 5;
    const DESKTOP_W = 992;
    let searchQuery = "";
    const nameIconMap = {
      dashboard: "house",
      logs: "file-lines",
      firmware: "download",
      rules: "sitemap",
      scoring: "trophy",
      audio: "music",
      media: "film",
      hardware: "microchip",
      playfield: "gamepad",
      liveview: "tower-broadcast",
      esplink: "gear",
      wifi: "wifi",
      service: "gear",
      settings: "sliders",
    };
    const categories = {
      overview: {
        title: "Overview and System",
        description: "Status, at-a-glance operational pages, and system configuration.",
        icon: "cubes-stacked",
        order: 0,
      },
      authoring: {
        title: "Authoring",
        description: "Build and tune gameplay behavior and layout.",
        icon: "wand-magic-sparkles",
        order: 1,
      },
      platform: {
        title: "Platform",
        description: "Hardware, firmware, and controller integration.",
        icon: "microchip",
        order: 2,
      },
      operations: {
        title: "Operations",
        description: "Runtime logs and service diagnostics.",
        icon: "gear",
        order: 3,
      },
      system: {
        title: "System",
        description: "Project and installation-wide configuration.",
        icon: "sliders",
        order: 4,
      },
      other: {
        title: "Other",
        description: "Additional modules.",
        icon: "window-restore",
        order: 99,
      },
    };

    let modules = [];
    try {
      modules = JSON.parse(dataEl.textContent || "[]");
    } catch (_) {
      modules = [];
    }
    modules.push({
      name: "documentation",
      title: "Documentation",
      icon: "book-open",
      href: "https://docs.pinballctl.com/",
      category: "operations",
      order: 98,
    });

    function moduleCategory(m) {
      const name = String(m?.name || "").trim().toLowerCase();
      if (name === "wifi" || name === "settings") return "overview";
      const byMeta = (m && m.category) ? String(m.category).trim().toLowerCase() : "";
      if (byMeta && categories[byMeta]) return byMeta;
      const byName = {
        dashboard: "overview",
        rules: "authoring",
        scoring: "authoring",
        playfield: "authoring",
        hardware: "platform",
        esplink: "platform",
        firmware: "platform",
        wifi: "overview",
        logs: "operations",
        service: "operations",
        settings: "overview",
      };
      return byName[name] || "other";
    }

    function normalizeIcon(raw, name) {
      if (name && nameIconMap[name]) return nameIconMap[name];
      const icon = String(raw || "").replace(/^fa-/, "");
      const aliases = {
        "file-text": "file-lines",
        home: "house",
        cog: "gear",
        wrench: "gear",
        gauge: "house",
        toolbox: "sitemap",
      };
      return aliases[icon] || icon || "window-restore";
    }

    function isDesktop() {
      return window.innerWidth >= DESKTOP_W;
    }

    function loadFavorites() {
      try {
        const parsed = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
        if (!Array.isArray(parsed)) return [];
        return parsed.map((v) => String(v)).filter(Boolean).slice(0, FAV_MAX);
      } catch (_) {
        return [];
      }
    }

    function saveFavorites(list) {
      try { localStorage.setItem(FAV_KEY, JSON.stringify(list.slice(0, FAV_MAX))); } catch (_) {}
    }

    function loadRecent() {
      try {
        const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
        if (!Array.isArray(parsed)) return [];
        return parsed.map((v) => String(v)).filter(Boolean).slice(0, RECENT_MAX);
      } catch (_) {
        return [];
      }
    }

    function saveRecent(list) {
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX))); } catch (_) {}
    }

    function recordRecent(name) {
      if (!name) return;
      const current = loadRecent().filter((v) => v !== name);
      current.unshift(name);
      saveRecent(current);
    }

    function showHint(text) {
      const el = document.getElementById("flood-hint");
      if (!el) return;
      el.textContent = text;
      el.classList.add("show");
      window.clearTimeout(showHint._t);
      showHint._t = window.setTimeout(() => el.classList.remove("show"), 1800);
    }

    function modulesByName() {
      const map = new Map();
      modules.forEach((m) => map.set(String(m.name), m));
      return map;
    }

    function moduleHref(m) {
      const custom = String(m?.href || "").trim();
      if (custom) return custom;
      return `/${m.name}`;
    }

    function groupedModules() {
      const grouped = new Map();
      modules.forEach((m) => {
        const cat = moduleCategory(m);
        if (!grouped.has(cat)) grouped.set(cat, []);
        grouped.get(cat).push(m);
      });
      const sortOrder = (v, fallback) => {
        const n = Number(v);
        return Number.isFinite(n) ? n : fallback;
      };
      return Array.from(grouped.entries())
        .map(([key, mods]) => ({ key, meta: categories[key] || categories.other, mods }))
        .sort((a, b) => sortOrder(a.meta.order, 99) - sortOrder(b.meta.order, 99));
    }

    function renderFlood() {
      const groups = groupedModules();
      const moduleMap = modulesByName();
      const favSet = new Set(loadFavorites());
      const q = String(searchQuery || "").trim().toLowerCase();
      const recentItems = loadRecent()
        .map((name) => moduleMap.get(name))
        .filter(Boolean);
      const recentHtml = recentItems.length ? `
        <section class="flood-recent mb-3">
          <div class="d-flex align-items-center gap-2 fw-semibold mb-2"><i class="fa fa-clock"></i><span>Recently Visited</span></div>
          <div class="d-flex flex-wrap gap-2">
            ${recentItems.map((m) => {
              const icon = normalizeIcon(m.icon, m.name);
              const title = m.title || m.name;
              return `<a class="fav-pill flood-recent-pill" data-nav-link data-module-name="${m.name}" href="${moduleHref(m)}"><i class="fa fa-fw fa-${icon}"></i><span>${title}</span></a>`;
            }).join("")}
          </div>
        </section>
      ` : "";
      const html = groups.map((g) => {
        const items = g.mods.sort((a, b) => {
          const ao = Number.isFinite(Number(a.order)) ? Number(a.order) : 100;
          const bo = Number.isFinite(Number(b.order)) ? Number(b.order) : 100;
          return ao - bo;
        }).map((m) => {
          const title = m.title || m.name;
          const hay = `${title} ${m.name} ${g.meta.title}`.toLowerCase();
          if (q && !hay.includes(q)) return "";
          const icon = normalizeIcon(m.icon, m.name);
          const isSaved = favSet.has(m.name);
          return `
            <div class="flood-item">
              <a class="flood-link" data-nav-link href="${moduleHref(m)}" data-module-name="${m.name}" data-module-title="${title}" data-module-icon="${icon}">
                <i class="fa fa-fw fa-${icon}"></i>
                <span>${title}</span>
              </a>
              <button type="button" class="btn btn-link p-0 flood-bookmark ${isSaved ? "is-saved" : ""}" data-fav-toggle data-module-name="${m.name}" aria-label="Toggle favorite">
                <i class="fa fa-bookmark"></i>
              </button>
            </div>
          `;
        }).filter(Boolean).join("");
        if (!items) return "";
        return `
          <section class="flood-category">
            <div class="flood-category-head">
              <div class="d-flex align-items-center gap-2 fw-semibold mb-1"><i class="fa fa-fw fa-${g.meta.icon}"></i><span>${g.meta.title}</span></div>
              <div class="flood-category-desc">${g.meta.description || ""}</div>
            </div>
            <div class="flood-category-items">${items}</div>
          </section>
        `;
      }).filter(Boolean).join("");
      body.innerHTML = `
        ${recentHtml}
        <div class="flood-grid">${html || '<div class="text-white-50 small px-1">No modules match your search.</div>'}</div>
      `;
    }

    function renderFavorites() {
      if (!favBar) return;
      const map = modulesByName();
      const favs = loadFavorites();
      const html = favs.map((name) => {
        const m = map.get(name);
        if (!m) return "";
        const title = m.title || m.name;
        const icon = normalizeIcon(m.icon, m.name);
        return `<a class="fav-pill" data-nav-link data-module-name="${m.name}" draggable="false" href="${moduleHref(m)}"><span class="fav-drag-handle" draggable="true" title="Drag to reorder" aria-hidden="true"></span><i class="fa fa-fw fa-${icon}"></i><span>${title}</span></a>`;
      }).join("");
      favBar.innerHTML = html;
    }

    function refreshBookmarkStates() {
      const favs = new Set(loadFavorites());
      body.querySelectorAll("[data-fav-toggle]").forEach((btn) => {
        const name = btn.getAttribute("data-module-name") || "";
        btn.classList.toggle("is-saved", favs.has(name));
      });
    }

    function openMenu() {
      document.body.classList.add("flood-open");
      menu.setAttribute("aria-hidden", "false");
    }

    function closeMenu() {
      document.body.classList.remove("flood-open");
      menu.setAttribute("aria-hidden", "true");
    }

    toggleBtn.addEventListener("click", () => {
      if (document.body.classList.contains("flood-open")) closeMenu();
      else openMenu();
    });
    searchEl?.addEventListener("input", (e) => {
      searchQuery = e.target.value || "";
      renderFlood();
      refreshBookmarkStates();
    });
    overlay.addEventListener("click", closeMenu);
    closeBtn?.addEventListener("click", closeMenu);
    window.addEventListener("keydown", (e) => {
      const target = e.target;
      const typingContext = target
        && (target.closest("input, textarea, select, [contenteditable='true']"));
      if (typingContext) return;
      if (e.key === "Escape") {
        closeMenu();
        return;
      }
      if (e.key && e.key.toLowerCase() === "m") {
        openMenu();
      }
    });
    document.addEventListener("click", (e) => {
      if (!document.body.classList.contains("flood-open")) return;
      const insideMenu = e.target.closest("[data-flood-menu]");
      const onToggle = e.target.closest("[data-menu-toggle]");
      if (!insideMenu && !onToggle) closeMenu();
    });

    body.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-fav-toggle]");
      if (!btn || !isDesktop()) return;
      e.preventDefault();
      e.stopPropagation();
      const name = btn.getAttribute("data-module-name");
      if (!name) return;
      const current = loadFavorites();
      const idx = current.indexOf(name);
      if (idx >= 0) {
        current.splice(idx, 1);
      } else if (current.length < FAV_MAX) {
        current.push(name);
      } else {
        showHint(`Favorites are full (${FAV_MAX}). Remove one first.`);
        return;
      }
      saveFavorites(current);
      refreshBookmarkStates();
      renderFavorites();
      wireMenuActiveState();
    }, true);

    body.addEventListener("click", (e) => {
      const link = e.target.closest(".flood-link, .flood-recent-pill");
      if (!link) return;
      const name = link.getAttribute("data-module-name");
      recordRecent(name);
    });

    favBar?.addEventListener("click", (e) => {
      const link = e.target.closest("a[data-module-name]");
      if (!link) return;
      recordRecent(link.getAttribute("data-module-name"));
    });

    let dragName = null;
    let dragFromIndex = -1;
    let dragSize = null;
    let dragPlaceholder = null;
    function removeDragPlaceholder() {
      if (!dragPlaceholder) return;
      dragPlaceholder.remove();
      dragPlaceholder = null;
    }
    favBar?.addEventListener("dragstart", (e) => {
      const handle = e.target.closest(".fav-drag-handle");
      if (!handle) {
        e.preventDefault();
        return;
      }
      const link = handle.closest("a[data-module-name]");
      if (!link) return;
      dragName = link.getAttribute("data-module-name");
      dragFromIndex = loadFavorites().indexOf(dragName);
      const rect = link.getBoundingClientRect();
      dragSize = {
        width: `${Math.max(56, Math.round(rect.width))}px`,
        height: `${Math.max(26, Math.round(rect.height))}px`,
      };
      try { e.dataTransfer.setData("text/plain", dragName || ""); } catch (_) {}
      e.dataTransfer.effectAllowed = "move";
      const ghost = link.cloneNode(true);
      ghost.classList.add("drag-ghost");
      ghost.style.position = "fixed";
      ghost.style.top = "-1000px";
      ghost.style.left = "-1000px";
      document.body.appendChild(ghost);
      try { e.dataTransfer.setDragImage(ghost, ghost.offsetWidth / 2, ghost.offsetHeight / 2); } catch (_) {}
      window.setTimeout(() => ghost.remove(), 0);
      link.classList.add("is-dragging");
    });
    favBar?.addEventListener("dragend", (e) => {
      const link = e.target.closest("a[data-module-name]");
      if (link) link.classList.remove("is-dragging");
      removeDragPlaceholder();
      dragName = null;
      dragFromIndex = -1;
      dragSize = null;
    });
    favBar?.addEventListener("dragover", (e) => {
      if (!dragName) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const items = Array.from(favBar.querySelectorAll("a[data-module-name]:not(.is-dragging)"));
      if (!items.length) {
        removeDragPlaceholder();
        return;
      }
      const nextIndex = items.findIndex((item) => {
        const rect = item.getBoundingClientRect();
        return e.clientX < rect.left + (rect.width / 2);
      });
      const insertIndex = nextIndex >= 0 ? nextIndex : items.length;
      if (insertIndex === dragFromIndex) {
        removeDragPlaceholder();
        return;
      }
      if (!dragPlaceholder) {
        dragPlaceholder = document.createElement("span");
        dragPlaceholder.className = "fav-pill drag-placeholder";
        dragPlaceholder.setAttribute("aria-hidden", "true");
        if (dragSize) {
          dragPlaceholder.style.width = dragSize.width;
          dragPlaceholder.style.height = dragSize.height;
        }
      }
      const next = nextIndex >= 0 ? items[nextIndex] : null;
      if (next) {
        if (dragPlaceholder !== next.previousElementSibling) favBar.insertBefore(dragPlaceholder, next);
      } else if (favBar.lastElementChild !== dragPlaceholder) {
        favBar.appendChild(dragPlaceholder);
      }
    });
    favBar?.addEventListener("drop", (e) => {
      if (!dragName || !dragPlaceholder) return;
      e.preventDefault();
      const cur = loadFavorites();
      const from = cur.indexOf(dragName);
      if (from < 0) return;
      cur.splice(from, 1);
      const children = Array.from(favBar.children);
      const slot = children.indexOf(dragPlaceholder);
      if (slot < 0) return;
      let insertIndex = 0;
      for (let i = 0; i < slot; i += 1) {
        const el = children[i];
        if (el.matches && el.matches("a[data-module-name]") && !el.classList.contains("is-dragging")) {
          insertIndex += 1;
        }
      }
      cur.splice(insertIndex, 0, dragName);
      saveFavorites(cur);
      renderFavorites();
      wireMenuActiveState();
      removeDragPlaceholder();
    });

    window.addEventListener("resize", () => {
      if (!isDesktop()) {
        renderFavorites();
      } else {
        renderFavorites();
        refreshBookmarkStates();
      }
      syncFloodTop();
    });

    function syncFloodTop() {
      const nav = document.querySelector(".navbar");
      const h = nav ? Math.max(0, Math.round(nav.getBoundingClientRect().height)) : 56;
      document.documentElement.style.setProperty("--flood-top", `${h}px`);
    }

    renderFlood();
    renderFavorites();
    refreshBookmarkStates();
    syncFloodTop();
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireThemeToggle();
    wireFloodMenu();
    wireMenuActiveState();
    wireTooltips();
    // wireDataConfirm is defined in the confirm IIFE below; call if available
    if (window.pinballctlConfirm && typeof window.pinballctlConfirm.wireDataConfirm === "function") {
      window.pinballctlConfirm.wireDataConfirm();
    }
  });
})();

// ------------------------------------------------------------
// Generic data-confirm handling (Bootstrap modal, vanilla JS)
// ------------------------------------------------------------
(function () {
  function confirmModal(el) {
    if (el.dataset.confirmChecked === "true") {
      delete el.dataset.confirmChecked;
      return true;
    }

    const text = el.dataset.confirm || "Are you sure?";
    const label = el.dataset.confirmLabel || "Confirm";
    const title = el.dataset.confirmTitle || "Confirm";
    const labelClass = el.dataset.confirmClass || "btn-danger";

    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) {
      return window.confirm(text);
    }

    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");

    if (body) body.textContent = text;
    if (titleEl) titleEl.textContent = title;
    if (confirmBtn) {
      confirmBtn.textContent = label;
      confirmBtn.className = `btn ${labelClass}`;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    modal.show();

    const onConfirm = () => {
      if (confirmBtn) confirmBtn.removeEventListener("click", onConfirm);
      el.dataset.confirmChecked = "true";
      modal.hide();
      setTimeout(() => { el.click(); }, 0);
    };
    if (confirmBtn) confirmBtn.addEventListener("click", onConfirm, { once: true });

    return false;
  }

  function wireDataConfirm() {
    document.addEventListener("click", (e) => {
      const target = e.target.closest("[data-confirm]");
      if (!target) return;
      const proceed = confirmModal(target);
      if (!proceed) {
        e.preventDefault();
        e.stopPropagation();
        if (typeof e.stopImmediatePropagation === "function") e.stopImmediatePropagation();
      }
    }, true); // capture so we intercept before element handlers
  }

  window.pinballctlConfirm = { confirmModal, wireDataConfirm };
})();
