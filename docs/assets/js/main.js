(function () {
  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function stripOrderPrefix(text) {
    const s = String(text || "").trim();
    return s.replace(/^\s*\d+\s*[-_. )]+\s*/i, "").trim() || s;
  }

  function menuTitleFor(slug, title) {
    return String(slug || "").toLowerCase() === "readme" ? "Home" : stripOrderPrefix(title || slug);
  }

  const BOOKMARKS_KEY = "pinballctl.docs.bookmarks.v1";
  const EXPANDED_KEY = "pinballctl.docs.expanded.v1";

  const state = {
    tree: [],
    pagesBySlug: new Map(),
    hrefBySlug: new Map(),
    slugByPath: new Map(),
    pageOrder: [],
    activeSlug: "",
    bookmarks: [],
    expanded: new Set(),
    searchTerm: "",
    lastResults: [],
    lastTrackedSearchTerm: "",
    mobileNavStack: [],
    mobileNavSlide: "",
    mobileMenuScrollY: 0,
  };

  function saveCurrentMobileNavScroll() {
    const list = document.getElementById("docs-mobile-nav-list");
    if (!(list instanceof HTMLElement)) return;
    const frame = currentMobileNavFrame();
    if (!frame || typeof frame !== "object") return;
    frame.scrollTop = Math.max(0, list.scrollTop || 0);
  }

  function restoreCurrentMobileNavScroll() {
    const list = document.getElementById("docs-mobile-nav-list");
    if (!(list instanceof HTMLElement)) return;
    const frame = currentMobileNavFrame();
    const scrollTop = frame && typeof frame.scrollTop === "number" ? frame.scrollTop : 0;
    window.requestAnimationFrame(() => {
      list.scrollTop = scrollTop;
    });
  }

  function flattenTreeSlugs(nodes, out) {
    if (!Array.isArray(nodes)) return;
    nodes.forEach((n) => {
      if (!n || typeof n !== "object") return;
      if (n.type === "folder") {
        flattenTreeSlugs(n.children || [], out);
        return;
      }
      const slug = String(n.slug || "");
      if (!slug || out.includes(slug)) return;
      out.push(slug);
    });
  }

  function buildPageOrder() {
    const ordered = [];
    flattenTreeSlugs(state.tree, ordered);
    state.pagesBySlug.forEach((_page, slug) => {
      if (!ordered.includes(slug)) ordered.push(slug);
    });
    state.pageOrder = ordered;
  }

  function sectionForSlug(slug) {
    const parts = String(slug || "").split("/").filter(Boolean);
    return parts.length > 1 ? parts[0] : "";
  }

  function renderBottomNav(slug) {
    const idx = state.pageOrder.indexOf(slug);
    const section = sectionForSlug(slug);

    let prevSlug = "";
    for (let i = idx - 1; i >= 0; i -= 1) {
      const candidate = state.pageOrder[i];
      if (sectionForSlug(candidate) === section) {
        prevSlug = candidate;
        break;
      }
    }

    let nextSlug = "";
    for (let i = idx + 1; i < state.pageOrder.length; i += 1) {
      const candidate = state.pageOrder[i];
      if (sectionForSlug(candidate) === section) {
        nextSlug = candidate;
        break;
      }
    }

    const prevPage = prevSlug ? state.pagesBySlug.get(prevSlug) : null;
    const nextPage = nextSlug ? state.pagesBySlug.get(nextSlug) : null;
    if (!prevPage && !nextPage) return null;

    const wrap = document.createElement("nav");
    wrap.className = "docs-page-nav";
    wrap.setAttribute("aria-label", "Document navigation");
    if (prevPage && !nextPage) wrap.classList.add("has-prev-only");
    if (!prevPage && nextPage) wrap.classList.add("has-next-only");

    const prevTitle = prevPage ? stripOrderPrefix(prevPage.title || prevSlug) : "No previous document";
    const nextTitle = nextPage ? stripOrderPrefix(nextPage.title || nextSlug) : "No next document";

    wrap.innerHTML = [
      prevPage ? `
        <a href="${slugHref(prevSlug)}" data-doc-slug="${esc(prevSlug)}" class="docs-page-nav-btn docs-page-nav-btn-prev" aria-label="Previous document: ${esc(prevTitle)}">
          <span class="docs-page-nav-dir">Back</span>
          <span class="docs-page-nav-title">${esc(prevTitle)}</span>
        </a>
      ` : "",
      nextPage ? `
        <a href="${slugHref(nextSlug)}" data-doc-slug="${esc(nextSlug)}" class="docs-page-nav-btn docs-page-nav-btn-next" aria-label="Next document: ${esc(nextTitle)}">
          <span class="docs-page-nav-dir">Next</span>
          <span class="docs-page-nav-title">${esc(nextTitle)}</span>
        </a>
      ` : "",
    ].join("");

    return wrap;
  }

  function trackEvent(eventName, params) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", eventName, params || {});
        return;
      }
      if (Array.isArray(window.dataLayer)) {
        window.dataLayer.push(Object.assign({ event: eventName }, params || {}));
      }
    } catch (_) {}
  }

  function getSearchInputs() {
    return Array.from(document.querySelectorAll("[data-docs-search]"));
  }

  function getSearchStatuses() {
    return Array.from(document.querySelectorAll("[data-docs-search-status]"));
  }

  function isMobileViewport() {
    return window.innerWidth <= 1080;
  }

  function syncHeaderHeightVar() {
    const header = document.querySelector(".site-header");
    if (!(header instanceof HTMLElement)) return;
    const h = Math.max(1, Math.round(header.getBoundingClientRect().height));
    document.documentElement.style.setProperty("--site-header-height", `${h}px`);
  }

  function wireHeaderMenu() {
    const menuBtn = document.querySelector(".menu-toggle");
    const nav = document.querySelector(".site-nav");
    if (!(menuBtn instanceof HTMLElement) || !(nav instanceof HTMLElement)) return;

    function setOpen(open) {
      if (open) {
        state.mobileMenuScrollY = window.scrollY || window.pageYOffset || 0;
        document.body.style.top = `-${state.mobileMenuScrollY}px`;
      } else {
        document.body.style.top = "";
      }
      nav.classList.toggle("open", open);
      document.body.classList.toggle("menu-open", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      if (!open) {
        window.scrollTo(0, state.mobileMenuScrollY || 0);
      }
    }

    menuBtn.addEventListener("click", () => {
      const open = !nav.classList.contains("open");
      if (open) resetMobileNavStack();
      setOpen(open);
    });

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (!nav.classList.contains("open")) return;
      if (t.closest(".site-nav") || t.closest(".menu-toggle")) return;
      setOpen(false);
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 920) setOpen(false);
      syncHeaderHeightVar();
    });
  }

  function wireDocsSidebarMenu() {
    const toggleBtns = Array.from(document.querySelectorAll("[data-docs-sidebar-toggle]"));
    const sidebar = document.getElementById("docs-sidebar");
    const closeBtn = document.getElementById("docs-sidebar-close");
    if (!(sidebar instanceof HTMLElement) || !toggleBtns.length) return;

    function setOpen(open) {
      sidebar.classList.toggle("open", open);
      toggleBtns.forEach((btn) => btn.setAttribute("aria-expanded", open ? "true" : "false"));
      document.body.classList.toggle("docs-sidebar-open", open && window.innerWidth <= 1080);
    }

    toggleBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        setOpen(!sidebar.classList.contains("open"));
        const nav = document.querySelector(".site-nav");
        if (nav instanceof HTMLElement) nav.classList.remove("open");
        document.body.classList.remove("menu-open");
      });
    });

    closeBtn?.addEventListener("click", () => setOpen(false));

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (!sidebar.classList.contains("open")) return;
      if (window.innerWidth > 1080) return;
      if (t.closest("#docs-sidebar") || t.closest("[data-docs-sidebar-toggle]")) return;
      setOpen(false);
    });

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (!t.closest("[data-doc-slug]")) return;
      if (window.innerWidth <= 1080) setOpen(false);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && window.innerWidth <= 1080) setOpen(false);
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 1080) setOpen(false);
    });
  }

  function wireMobileSearchModal() {
    const modal = document.getElementById("docs-search-modal");
    const toggle = document.getElementById("docs-mobile-search-toggle");
    const closeBtn = document.getElementById("docs-search-modal-close");
    const input = document.getElementById("docs-search-modal-input");
    if (!(modal instanceof HTMLElement) || !(toggle instanceof HTMLElement) || !(input instanceof HTMLElement)) return;

    function setOpen(open) {
      if (open) {
        state.mobileMenuScrollY = window.scrollY || window.pageYOffset || 0;
        document.body.style.top = `-${state.mobileMenuScrollY}px`;
      } else {
        document.body.style.top = "";
      }
      modal.classList.toggle("open", open);
      modal.setAttribute("aria-hidden", open ? "false" : "true");
      document.body.classList.toggle("docs-search-open", open);
      if (!open) {
        window.scrollTo(0, state.mobileMenuScrollY || 0);
      }
      if (open) {
        window.setTimeout(() => {
          input.focus();
          input.select();
        }, 0);
      }
    }

    toggle.addEventListener("click", () => setOpen(true));
    closeBtn?.addEventListener("click", () => setOpen(false));

    modal.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (t.classList.contains("docs-search-modal__backdrop")) setOpen(false);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.classList.contains("open")) setOpen(false);
    });

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (!t.closest(".docs-search-results-modal [data-doc-slug]")) return;
      setOpen(false);
    });

    window.addEventListener("resize", () => {
      if (!isMobileViewport()) setOpen(false);
    });
  }

  function resetMobileNavStack() {
    state.mobileNavStack = [{
      kind: "root",
      title: "Menu",
      nodes: Array.isArray(state.tree) ? state.tree : [],
      scrollTop: 0,
    }];
    state.mobileNavSlide = "";
  }

  function currentMobileNavFrame() {
    if (!Array.isArray(state.mobileNavStack) || !state.mobileNavStack.length) {
      resetMobileNavStack();
    }
    return state.mobileNavStack[state.mobileNavStack.length - 1];
  }

  function renderMobileNavList() {
    const list = document.getElementById("docs-mobile-nav-list");
    if (!(list instanceof HTMLElement)) return;
    const frame = currentMobileNavFrame();
    const slideClass = state.mobileNavSlide === "back" ? "slide-back" : (state.mobileNavSlide === "forward" ? "slide-forward" : "");
    const canGoBack = state.mobileNavStack.length > 1;

    let rowsHtml = "";
    if (frame.kind === "bookmarks") {
      if (!state.bookmarks.length) {
        rowsHtml = `<div class="docs-mobile-empty">You do not have any saved bookmarks.<br/>Click the <span class="docs-mobile-empty-icon" aria-hidden="true"><svg class="docs-bookmark-icon" viewBox="0 0 24 24" focusable="false"><path d="M7 3h10a1 1 0 0 1 1 1v17l-6-3.8L6 21V4a1 1 0 0 1 1-1z"></path></svg></span> on a page to save it here.</div>`;
      } else {
        rowsHtml = state.bookmarks.map((b) => `
          <div class="docs-mobile-bookmark-row">
            <a href="${slugHref(b.slug)}" data-doc-slug="${esc(b.slug)}" class="docs-mobile-link${state.activeSlug === b.slug ? " active" : ""}">${esc(menuTitleFor(b.slug, b.title || b.slug))}</a>
            <button type="button" class="docs-mobile-bookmark-remove" data-bookmark-remove="${esc(b.slug)}" aria-label="Remove bookmark">×</button>
          </div>
        `).join("");
      }
    } else if (frame.kind === "folder") {
      const nodes = Array.isArray(frame.nodes) ? frame.nodes : [];
      rowsHtml = nodes.map((n, idx) => {
        if (n?.type === "folder") {
          return `<button type="button" class="docs-mobile-link docs-mobile-folder" data-mobile-nav-open="folder:${idx}">${esc(stripOrderPrefix(n.name || "Folder"))}</button>`;
        }
        const slug = String(n?.slug || "");
        const title = menuTitleFor(slug, n?.title || slug);
        return `<a href="${slugHref(slug)}" data-doc-slug="${esc(slug)}" class="docs-mobile-link${state.activeSlug === slug ? " active" : ""}">${esc(title)}</a>`;
      }).join("");
    } else {
      const nodes = Array.isArray(frame.nodes) ? frame.nodes : [];
      const topRows = nodes.map((n, idx) => {
        if (n?.type === "folder") {
          return `<button type="button" class="docs-mobile-link docs-mobile-folder" data-mobile-nav-open="folder:${idx}">${esc(stripOrderPrefix(n.name || "Folder"))}</button>`;
        }
        const slug = String(n?.slug || "");
        if (slug.toLowerCase() === "readme") return "";
        const title = menuTitleFor(slug, n?.title || slug);
        return `<a href="${slugHref(slug)}" data-doc-slug="${esc(slug)}" class="docs-mobile-link${state.activeSlug === slug ? " active" : ""}">${esc(title)}</a>`;
      }).join("");

      rowsHtml = [
        `<a href="${slugHref("README")}" data-doc-slug="README" class="docs-mobile-link${state.activeSlug === "README" ? " active" : ""}">Home</a>`,
        `<button type="button" class="docs-mobile-link docs-mobile-folder" data-mobile-nav-open="bookmarks">Bookmarks</button>`,
        topRows,
      ].join("");
    }

    const headHtml = canGoBack
      ? `
      <div class="docs-mobile-nav-head">
        <div class="docs-mobile-nav-title">${esc(frame && frame.title ? frame.title : "Menu")}</div>
        <button type="button" class="docs-mobile-nav-back" data-mobile-nav-back>Back</button>
      </div>
    `
      : "";
    list.innerHTML = `
      ${headHtml}
      <div class="docs-mobile-nav-pane ${slideClass}">
        ${rowsHtml}
      </div>
    `;
    state.mobileNavSlide = "";
    restoreCurrentMobileNavScroll();
  }

  function handleMobileNavInteraction(target, event) {
    if (!(target instanceof Element)) return false;

    const mobileBack = target.closest("[data-mobile-nav-back]");
    if (mobileBack) {
      event.preventDefault();
      event.stopPropagation();
      if (state.mobileNavStack.length > 1) {
        saveCurrentMobileNavScroll();
        state.mobileNavStack.pop();
        state.mobileNavSlide = "back";
        renderMobileNavList();
      }
      return true;
    }

    const mobileOpen = target.closest("[data-mobile-nav-open]");
    if (mobileOpen) {
      event.preventDefault();
      event.stopPropagation();
      const action = String(mobileOpen.getAttribute("data-mobile-nav-open") || "");
      const frame = currentMobileNavFrame();
      saveCurrentMobileNavScroll();
      if (action === "bookmarks") {
        state.mobileNavStack.push({
          kind: "bookmarks",
          title: "Bookmarks",
          nodes: [],
          scrollTop: 0,
        });
        state.mobileNavSlide = "forward";
        renderMobileNavList();
        return true;
      }
      if (action.startsWith("folder:")) {
        const idx = Number(action.split(":")[1]);
        const nodes = Array.isArray(frame?.nodes) ? frame.nodes : [];
        const folder = nodes[idx];
        if (folder && folder.type === "folder") {
          state.mobileNavStack.push({
            kind: "folder",
            title: stripOrderPrefix(String(folder.name || "Folder")),
            nodes: Array.isArray(folder.children) ? folder.children : [],
            scrollTop: 0,
          });
          state.mobileNavSlide = "forward";
          renderMobileNavList();
        }
        return true;
      }
    }

    return false;
  }

  function hashSlug() {
    const m = (window.location.hash || "").match(/doc=([^&]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function docsRootPrefix() {
    const parts = String(window.location.pathname || "")
      .split("/")
      .filter(Boolean);
    const idx = parts.lastIndexOf("pages");
    if (idx < 0) return "./";
    const depth = Math.max(0, parts.length - idx - 1);
    return "../".repeat(depth) || "./";
  }

  function normalisePathname(pathname) {
    const s = String(pathname || "").trim();
    if (!s) return "/";
    const noQuery = s.split("?")[0].split("#")[0] || "/";
    if (noQuery === "/") return "/";
    return noQuery.replace(/\/+$/, "") || "/";
  }

  function toRelativeHref(absHref) {
    const base = docsRootPrefix();
    const clean = String(absHref || "").trim();
    if (!clean || clean === "/") return `${base}index.html`;
    if (clean.startsWith("/")) return `${base}${clean.slice(1)}`;
    return `${base}${clean}`;
  }

  function slugHref(slug) {
    const clean = String(slug || "").trim();
    const mapped = state.hrefBySlug.get(clean);
    if (mapped) return toRelativeHref(mapped);
    return toRelativeHref(clean && clean.toUpperCase() === "README" ? "/" : "/");
  }

  function slugFromPathname(pathname) {
    const key = normalisePathname(pathname);
    if (key === "/" || key === "/index.html") return "README";
    const direct = state.slugByPath.get(key);
    if (direct) return direct;

    // In file:// mode, pathname is an absolute local path
    // (e.g. /Users/.../pages/user-guide-lighting.html), while
    // generated href keys are site-relative (/pages/user-guide-lighting.html).
    // Match by suffix so we still resolve the active slug correctly.
    if (window.location.protocol === "file:") {
      for (const [mappedPath, slug] of state.slugByPath.entries()) {
        if (key.endsWith(mappedPath)) return slug;
      }
    }

    return "";
  }

  function navigateToSlug(slug, options) {
    const target = String(slug || "").trim();
    if (!target) return;
    const opts = options || {};
    const href = slugHref(target);
    const currentUrl = new URL(window.location.href);
    const targetUrl = new URL(href, window.location.href);
    const currentKey = `${currentUrl.pathname}${currentUrl.search}`;
    const targetKey = `${targetUrl.pathname}${targetUrl.search}`;
    if (currentKey === targetKey) {
      renderArticle(target);
      return;
    }
    if (window.location.protocol === "file:") {
      window.location.href = href;
      return;
    }
    if (opts.replace) {
      window.location.replace(href);
      return;
    }
    window.location.href = href;
  }

  function loadState() {
    try {
      const b = JSON.parse(localStorage.getItem(BOOKMARKS_KEY) || "[]");
      state.bookmarks = Array.isArray(b) ? b.filter((x) => x && x.slug) : [];
    } catch (_) {
      state.bookmarks = [];
    }
    try {
      const e = JSON.parse(localStorage.getItem(EXPANDED_KEY) || "[]");
      state.expanded = new Set(Array.isArray(e) ? e : []);
    } catch (_) {
      state.expanded = new Set();
    }
  }

  function persistBookmarks() {
    try {
      localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(state.bookmarks));
    } catch (_) {}
  }

  function persistExpanded() {
    try {
      localStorage.setItem(EXPANDED_KEY, JSON.stringify(Array.from(state.expanded)));
    } catch (_) {}
  }

  function isBookmarked(slug) {
    return state.bookmarks.some((b) => b.slug === slug);
  }

  function renderBookmarks() {
    const wrap = document.getElementById("docs-bookmarks-wrap");
    const el = document.getElementById("docs-bookmarks");
    if (!wrap || !el) {
      renderMobileNavList();
      return;
    }

    if (!state.bookmarks.length) {
      wrap.classList.add("hidden");
      el.innerHTML = "";
      renderMobileNavList();
      return;
    }
    wrap.classList.remove("hidden");
    el.innerHTML = state.bookmarks.map((b) => `
      <div class="docs-bookmark-item">
        <a href="${slugHref(b.slug)}" data-doc-slug="${esc(b.slug)}" class="docs-page-link${state.activeSlug === b.slug ? " active" : ""}">${esc(menuTitleFor(b.slug, b.title || b.slug))}</a>
        <button type="button" class="docs-bookmark-remove" data-bookmark-remove="${esc(b.slug)}" aria-label="Remove bookmark">x</button>
      </div>
    `).join("");
    renderMobileNavList();
  }

  function refreshBookmarkToggle() {
    const btn = document.getElementById("docs-bookmark-toggle");
    if (!btn) return;
    const active = !!state.activeSlug && isBookmarked(state.activeSlug);
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.setAttribute("aria-label", active ? "Remove bookmark" : "Bookmark current page");
    btn.setAttribute("title", active ? "Remove bookmark" : "Bookmark current page");
  }

  function renderTreeNodes(nodes) {
    if (!Array.isArray(nodes) || !nodes.length) return "";
    return `<ul>${nodes.map((n) => {
      if (n.type === "folder") {
        const path = String(n.path || "");
        const open = state.expanded.has(path);
        return `<li class="docs-folder ${open ? "is-open" : ""}">
          <button type="button" class="docs-folder-toggle" data-folder-path="${esc(path)}" aria-expanded="${open ? "true" : "false"}">
            <span class="chev">${open ? "▾" : "▸"}</span>${esc(stripOrderPrefix(n.name || path))}
          </button>
          <div class="docs-folder-children ${open ? "" : "hidden"}">${renderTreeNodes(n.children || [])}</div>
        </li>`;
      }
      return `<li><a href="${slugHref(n.slug)}" data-doc-slug="${esc(n.slug)}" class="docs-page-link${state.activeSlug === n.slug ? " active" : ""}">${esc(menuTitleFor(n.slug, n.title || n.slug))}</a></li>`;
    }).join("")}</ul>`;
  }

  function renderTree() {
    const el = document.getElementById("docs-tree");
    if (!el) return;
    el.innerHTML = renderTreeNodes(state.tree);
  }

  function attachImageModal(articleEl) {
    const modal = document.getElementById("img-modal");
    const modalImg = modal?.querySelector(".img-modal__img");
    const closeBtn = modal?.querySelector(".img-modal__close");
    if (!modal || !modalImg) return;

    function close() {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      modalImg.src = "";
    }

    closeBtn?.addEventListener("click", close);
    modal.addEventListener("click", (e) => {
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (t === modal || t.classList.contains("img-modal__backdrop")) close();
    });

    articleEl.querySelectorAll("img").forEach((img) => {
      const src = img.getAttribute("src") || "";
      if (!src) return;
      img.classList.add("shot-click");
      img.addEventListener("click", () => {
        modalImg.src = src;
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
      });
    });
  }

  function normaliseArticleRelativePaths(articleEl) {
    const prefix = docsRootPrefix();
    const mapUrl = (raw) => {
      const url = String(raw || "").trim();
      if (!url) return url;
      if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("mailto:") || url.startsWith("tel:") || url.startsWith("#")) {
        return url;
      }

      const m = url.match(/^(\.\/)?(media|assets|pages)\/(.*)$/i);
      if (!m) return url;
      const folder = String(m[2] || "").toLowerCase();
      const rest = String(m[3] || "");
      return `${prefix}${folder}/${rest}`;
    };

    articleEl.querySelectorAll("img[src],source[src],video[src],audio[src]").forEach((el) => {
      const src = el.getAttribute("src");
      if (!src) return;
      const next = mapUrl(src);
      if (next !== src) el.setAttribute("src", next);
    });

    articleEl.querySelectorAll("a[href]").forEach((el) => {
      const href = el.getAttribute("href");
      if (!href) return;
      const next = mapUrl(href);
      if (next !== href) el.setAttribute("href", next);
    });
  }

  function renderArticle(slug) {
    const article = document.getElementById("docs-article");
    if (!article) return;
    const page = state.pagesBySlug.get(slug);
    if (!page) return;

    state.activeSlug = slug;
    article.innerHTML = page.html || `<h1>${esc(page.title || slug)}</h1><p>No content.</p>`;
    normaliseArticleRelativePaths(article);
    const bottomNav = renderBottomNav(slug);
    if (bottomNav) article.appendChild(bottomNav);
    attachImageModal(article);

    article.querySelectorAll('a[href^="#doc="]').forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const h = a.getAttribute("href") || "";
        const s = (h.split("#doc=")[1] || "").trim();
        if (s) navigateToSlug(decodeURIComponent(s));
      });
    });

    renderTree();
    renderBookmarks();
    refreshBookmarkToggle();
    document.dispatchEvent(new CustomEvent("docs:article-rendered", { detail: { slug } }));
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function scorePage(page, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return 0;
    const title = String(page.title || "").toLowerCase();
    const body = String(page.plain || "").toLowerCase();
    const excerpt = String(page.excerpt || "").toLowerCase();
    let s = 0;
    if (title.includes(q)) s += 100;
    if (body.includes(q)) s += 30;
    if (excerpt.includes(q)) s += 20;
    const tokens = q.match(/[a-z0-9][a-z0-9_-]*/g) || [];
    tokens.forEach((t) => {
      if (title.includes(t)) s += 22;
      if (body.includes(t)) s += 7;
    });
    return s;
  }

  function queryTokens(query) {
    return (String(query || "").toLowerCase().match(/[a-z0-9][a-z0-9_-]*/g) || []);
  }

  function matchesPage(page, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return true;
    const title = String(page?.title || "").toLowerCase();
    const body = String(page?.plain || "").toLowerCase();
    const excerpt = String(page?.excerpt || "").toLowerCase();
    const hay = `${title}\n${excerpt}\n${body}`;

    const tokens = queryTokens(q);
    if (!tokens.length) return hay.includes(q);

    // AND semantics, order-independent, partial-word matching via substring includes.
    return tokens.every((t) => hay.includes(t));
  }

  function snippetForSearch(page, query) {
    const q = String(query || "").trim();
    const plain = String(page?.plain || "").replace(/\s+/g, " ").trim();
    const fallback = String(page?.excerpt || "").trim();
    const source = plain || fallback;
    if (!source) return "";
    if (!q) return esc(fallback || source.slice(0, 220));

    const lowSource = source.toLowerCase();
    const lowQ = q.toLowerCase();
    let idx = lowSource.indexOf(lowQ);
    if (idx < 0) {
      const tokens = q.match(/[a-z0-9][a-z0-9_-]*/gi) || [];
      for (let i = 0; i < tokens.length; i += 1) {
        const t = tokens[i].toLowerCase();
        idx = lowSource.indexOf(t);
        if (idx >= 0) break;
      }
    }

    const left = 100;
    const right = 140;
    let start = idx >= 0 ? Math.max(0, idx - left) : 0;
    let end = idx >= 0 ? Math.min(source.length, idx + Math.max(q.length, 1) + right) : Math.min(source.length, 240);

    if (start > 0) {
      const ws = source.indexOf(" ", start);
      if (ws > 0) start = ws + 1;
    }
    if (end < source.length) {
      const ws = source.lastIndexOf(" ", end);
      if (ws > start) end = ws;
    }

    let snippet = source.slice(start, end).trim();
    if (start > 0) snippet = `...${snippet}`;
    if (end < source.length) snippet = `${snippet}...`;

    const escaped = esc(snippet);
    const bits = q.match(/[a-z0-9][a-z0-9_-]*/gi) || [];
    if (!bits.length) return escaped;

    const uniq = Array.from(new Set(bits.map((b) => b.toLowerCase()))).sort((a, b) => b.length - a.length);
    const pattern = uniq.map((b) => b.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
    if (!pattern) return escaped;
    const re = new RegExp(`(${pattern})`, "gi");
    return escaped.replace(re, "<mark>$1</mark>");
  }

  function renderSearchResults(results) {
    const tree = document.getElementById("docs-tree");
    const resultsEl = document.getElementById("docs-search-results-top");
    const modal = document.getElementById("docs-search-modal");
    const modalResultsEl = document.getElementById("docs-search-results-modal");
    const layout = document.querySelector(".docs-layout");
    const statusEls = getSearchStatuses();
    if (!tree || !resultsEl || !modalResultsEl || !(layout instanceof HTMLElement)) return;

    const useModal = isMobileViewport() && modal instanceof HTMLElement && modal.classList.contains("open");
    const activeResultsEl = useModal ? modalResultsEl : resultsEl;

    if (!state.searchTerm || state.searchTerm.length < 2) {
      tree.classList.remove("hidden");
      resultsEl.classList.add("hidden");
      resultsEl.innerHTML = "";
      modalResultsEl.innerHTML = "";
      layout.classList.remove("hidden");
      statusEls.forEach((el) => {
        el.textContent = "";
      });
      return;
    }

    if (useModal) {
      tree.classList.remove("hidden");
      layout.classList.remove("hidden");
      resultsEl.classList.add("hidden");
    } else {
      tree.classList.add("hidden");
      layout.classList.add("hidden");
      resultsEl.classList.remove("hidden");
    }
    const statusText = `${results.length} result${results.length === 1 ? "" : "s"}`;
    statusEls.forEach((el) => {
      el.textContent = statusText;
    });

    if (!results.length) {
      activeResultsEl.innerHTML = `<div class="docs-search-empty">No results found. Try a different keyword.</div>`;
      return;
    }

    activeResultsEl.innerHTML = results.map((p) => `
      <a href="${slugHref(p.slug)}" data-doc-slug="${esc(p.slug)}" class="docs-search-result docs-page-link${state.activeSlug === p.slug ? " active" : ""}">
        <div class="docs-search-result-title">${esc(stripOrderPrefix(p.title || p.slug))}</div>
        <div class="docs-result-excerpt">${snippetForSearch(p, state.searchTerm)}</div>
      </a>
    `).join("");
  }

  function runSearch() {
    const query = state.searchTerm;
    if (!query || query.length < 2) {
      state.lastResults = [];
      state.lastTrackedSearchTerm = "";
      renderSearchResults([]);
      return;
    }
    const scored = Array.from(state.pagesBySlug.values())
      .filter((p) => matchesPage(p, query))
      .map((p) => ({ p, score: scorePage(p, query) }))
      .sort((a, b) => b.score - a.score || String(a.p.title).localeCompare(String(b.p.title)))
      .map((x) => x.p)
      .slice(0, 120);
    state.lastResults = scored;
    if (query !== state.lastTrackedSearchTerm) {
      trackEvent("search", {
        search_term: query,
        results_count: scored.length,
        search_provider: "pinballctl_docs_inline",
      });
      state.lastTrackedSearchTerm = query;
    }
    renderSearchResults(scored);
  }

  function wireEvents(defaultSlug) {
    const mobileNavList = document.getElementById("docs-mobile-nav-list");
    if (mobileNavList instanceof HTMLElement) {
      mobileNavList.addEventListener("click", (e) => {
        const target = e.target;
        handleMobileNavInteraction(target, e);
      });
    }

    document.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (handleMobileNavInteraction(target, e)) return;

      const remove = target.closest("[data-bookmark-remove]");
      if (remove) {
        e.preventDefault();
        const slug = remove.getAttribute("data-bookmark-remove") || "";
        state.bookmarks = state.bookmarks.filter((b) => b.slug !== slug);
        persistBookmarks();
        renderBookmarks();
        refreshBookmarkToggle();
        return;
      }

      const folder = target.closest("[data-folder-path]");
      if (folder) {
        e.preventDefault();
        const path = folder.getAttribute("data-folder-path") || "";
        if (state.expanded.has(path)) state.expanded.delete(path);
        else state.expanded.add(path);
        persistExpanded();
        renderTree();
        return;
      }

      const link = target.closest("[data-doc-slug]");
      if (link) {
        const slug = link.getAttribute("data-doc-slug") || "";
        if (link.classList.contains("docs-search-result")) {
          trackEvent("select_content", {
            content_type: "docs_search_result",
            item_id: slug,
            search_term: state.searchTerm || "",
          });
        }
        const nav = document.querySelector(".site-nav");
        const menuBtn = document.querySelector(".menu-toggle");
        if (window.innerWidth <= 920 && nav instanceof HTMLElement && nav.classList.contains("open")) {
          nav.classList.remove("open");
          document.body.classList.remove("menu-open");
          if (menuBtn instanceof HTMLElement) menuBtn.setAttribute("aria-expanded", "false");
        }
      }
    });

    const bookmarkBtn = document.getElementById("docs-bookmark-toggle");
    bookmarkBtn?.addEventListener("click", () => {
      const slug = state.activeSlug;
      if (!slug) return;
      if (isBookmarked(slug)) {
        state.bookmarks = state.bookmarks.filter((b) => b.slug !== slug);
      } else {
        const page = state.pagesBySlug.get(slug);
        state.bookmarks.unshift({ slug, title: page?.title || slug });
      }
      persistBookmarks();
      renderBookmarks();
      refreshBookmarkToggle();
    });

    const searchEls = getSearchInputs();
    let t = null;
    searchEls.forEach((el) => {
      el.addEventListener("input", () => {
        const value = String(el.value || "").trim();
        state.searchTerm = value;
        searchEls.forEach((other) => {
          if (other !== el && other.value !== value) other.value = value;
        });
        window.clearTimeout(t);
        t = window.setTimeout(runSearch, 120);
      });
    });

    window.addEventListener("hashchange", () => {
      const slug = hashSlug();
      if (slug) navigateToSlug(slug);
    });

    window.addEventListener("popstate", () => {
      const slug = hashSlug() || slugFromPathname(window.location.pathname) || defaultSlug;
      if (slug) renderArticle(slug);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const modal = document.getElementById("img-modal");
        modal?.classList.remove("open");
      }
      const target = e.target;
      const inField = target instanceof Element && !!target.closest("input,textarea,select,[contenteditable='true']");
      if (!inField && e.key === "/") {
        e.preventDefault();
        const mobileOpen = isMobileViewport();
        const desktopSearch = document.getElementById("docs-search");
        const mobileSearch = document.getElementById("docs-search-modal-input");
        const searchEl = mobileOpen ? mobileSearch : desktopSearch;
        if (mobileOpen) {
          const modalToggle = document.getElementById("docs-mobile-search-toggle");
          if (modalToggle instanceof HTMLElement) modalToggle.click();
        }
        searchEl?.focus();
        searchEl?.select();
      }
    });
  }

  function readInlineData() {
    const el = document.getElementById("site-data-inline");
    if (!el) return null;
    const raw = String(el.textContent || "").trim();
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  async function loadSiteData() {
    const globalData = window.__PINBALLCTL_SITE_DATA__;
    if (globalData && typeof globalData === "object") return globalData;
    const inline = readInlineData();
    if (inline && typeof inline === "object") return inline;
    if (window.location.protocol === "file:") {
      throw new Error(
        "Missing site data in file mode. Ensure site-data.js is present and loaded via a relative script tag."
      );
    }
    const res = await fetch(`${docsRootPrefix()}site-data.json`, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`Failed to fetch /site-data.json (${res.status})`);
    return res.json();
  }

  async function init() {
    loadState();
    syncHeaderHeightVar();
    wireHeaderMenu();
    wireDocsSidebarMenu();
    wireMobileSearchModal();

    const data = await loadSiteData();
    state.tree = Array.isArray(data.tree) ? data.tree : [];
    const pages = Array.isArray(data.pages) ? data.pages : [];
    pages.forEach((p) => {
      const slug = String(p.slug || "");
      if (!slug) return;
      state.pagesBySlug.set(slug, p);
      const href = String(p.href || "");
      if (href) {
        state.hrefBySlug.set(slug, href);
        state.slugByPath.set(normalisePathname(href), slug);
      }
    });
    buildPageOrder();
    resetMobileNavStack();

    renderTree();
    renderBookmarks();

    const hasReadme = state.pagesBySlug.has("README");
    const defaultSlug = hasReadme ? "README" : String(data.default_slug || pages[0]?.slug || "");
    wireEvents(defaultSlug);

    const slug = hashSlug() || slugFromPathname(window.location.pathname) || defaultSlug;
    if (slug) navigateToSlug(slug, { replace: true });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
