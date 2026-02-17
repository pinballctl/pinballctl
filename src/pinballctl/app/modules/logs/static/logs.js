// Vanilla log tailer (replaces Alpine version).
(function () {
  const root = document.getElementById("logs-root");
  if (!root) return;
  const SOURCE_STORAGE_KEY = "pinballctl.logs.source";
  const VALID_TARGETS = new Set(["error", "access", "bridge", "events", "espraw"]);

  function getSavedTarget() {
    try {
      const v = window.localStorage.getItem(SOURCE_STORAGE_KEY);
      if (v && VALID_TARGETS.has(v)) return v;
    } catch (_) {}
    return null;
  }

  function saveTarget(v) {
    try {
      if (v && VALID_TARGETS.has(v)) window.localStorage.setItem(SOURCE_STORAGE_KEY, v);
    } catch (_) {}
  }

  const sourceTabs = Array.from(root.querySelectorAll("[data-log-target]"));
  const viewSel = root.querySelector("#log-view");
  const linesInput = root.querySelector("#log-lines");
  const keywordInput = root.querySelector("#log-keyword");
  const viewport = root.querySelector("#log-viewport");
  const jsonModal = root.querySelector("#log-json-modal");
  const jsonModalLine = root.querySelector("#log-json-line");
  const jsonModalBody = root.querySelector("#log-json-body");
  const toggleBtn = root.querySelector('[data-action="toggle-tail"]');
  const refreshBtn = root.querySelector('[data-action="refresh"]');
  const clearBtn = root.querySelector('[data-action="clear"]');
  const purgeBtn = root.querySelector('[data-action="purge"]');

  const initialTarget = getSavedTarget() || "error";

  function setActiveSourceTab(target) {
    sourceTabs.forEach((tab) => {
      const tabTarget = String(tab.getAttribute("data-log-target") || "");
      const active = tabTarget === target;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  let state = {
    target: initialTarget,
    lines: parseInt(linesInput?.value || "200", 10) || 200,
    keyword: "",
    tailing: true,
    buffer: [],
    visible: [],
    offset: 0,
    controller: null,
    timer: null,
    carry: "",
    view: viewSel?.value || "current",
    archives: [],
    pendingRender: false,
  };
  setActiveSourceTab(state.target);

  const intervalMs = 1000;
  const ARCHIVE_MAX_LOOPS = 2048;

  function maxKeep() { return Math.max(5000, state.lines); }

  function appendChunk(text) {
    if (!text) return;
    if (state.carry && text.startsWith("[")) {
      // Treat previous carry as a complete line if the new chunk starts a log line.
      state.buffer.push(state.carry);
      state.carry = "";
    }
    let chunk = state.carry + text;
    const endsWithNewline = /\r?\n$/.test(chunk);
    const parts = chunk.split(/\r?\n/);
    if (!endsWithNewline) state.carry = parts.pop() || ""; else state.carry = "";
    if (endsWithNewline && parts.length && parts[parts.length - 1] === "") {
      parts.pop(); // avoid synthetic blank line when chunk ends with newline
    }
    for (const ln of parts) state.buffer.push(ln);
    const maxSize = maxKeep();
    if (state.buffer.length > maxSize) state.buffer.splice(0, state.buffer.length - maxSize);
  }

  function applyFilter() {
    const kw = (state.keyword || "").toLowerCase().trim();
    let arr = state.buffer;
    if (kw) arr = arr.filter(ln => ln.toLowerCase().includes(kw));
    if (state.view.startsWith("archive:")) {
      state.visible = arr.slice();
    } else {
      const subset = arr.slice(-state.lines);
      state.visible = subset.slice().reverse();
    }
    render();
  }

  function archiveMode() {
    return state.view.startsWith("archive:");
  }

  function updateArchiveControls() {
    const isArchive = archiveMode();
    if (purgeBtn) purgeBtn.classList.toggle("d-none", isArchive);
    if (clearBtn) clearBtn.classList.toggle("d-none", isArchive);
    if (toggleBtn) toggleBtn.classList.toggle("d-none", isArchive);
    if (isArchive) {
      state.tailing = false;
      stopTail();
    }
  }

  function extractJsonFromLine(line) {
    if (!line) return null;
    const candidates = [];
    const trimmed = line.trim();
    if (trimmed) candidates.push(trimmed);
    const firstObj = line.indexOf("{");
    if (firstObj >= 0) candidates.push(line.slice(firstObj).trim());
    const firstArr = line.indexOf("[");
    if (firstArr >= 0) candidates.push(line.slice(firstArr).trim());
    for (const c of candidates) {
      if (!c) continue;
      try {
        const obj = JSON.parse(c);
        return { raw: c, obj };
      } catch (_) {}
    }
    return null;
  }

  function selectionInsideViewport() {
    if (!viewport || !document.getSelection) return false;
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return false;
    const anchorNode = sel.anchorNode;
    const focusNode = sel.focusNode;
    return !!(anchorNode && focusNode && viewport.contains(anchorNode) && viewport.contains(focusNode));
  }

  function hasActiveSelection() {
    if (!document.getSelection) return false;
    const sel = document.getSelection();
    return !!(sel && !sel.isCollapsed && sel.rangeCount > 0);
  }

  function maybeRenderDeferred() {
    if (!state.pendingRender) return;
    if (selectionInsideViewport()) return;
    state.pendingRender = false;
    render();
  }

  function openJsonModal(line, parsed) {
    if (!jsonModal || !jsonModalBody || !jsonModalLine) return;
    jsonModal.classList.remove("is-raw");
    if (parsed !== null && parsed !== undefined) {
      jsonModalLine.textContent = line || "";
      jsonModalLine.classList.remove("d-none");
      jsonModalBody.innerHTML = syntaxHighlightJson(parsed);
    } else {
      jsonModal.classList.add("is-raw");
      jsonModalLine.textContent = "";
      jsonModalLine.classList.add("d-none");
      jsonModalBody.textContent = line || "";
    }
    jsonModal.classList.remove("d-none");
    jsonModal.setAttribute("aria-hidden", "false");
  }

  function closeJsonModal() {
    if (!jsonModal) return;
    jsonModal.classList.add("d-none");
    jsonModal.setAttribute("aria-hidden", "true");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function syntaxHighlightJson(obj) {
    const json = JSON.stringify(obj, null, 2);
    const escaped = escapeHtml(json);
    return escaped.replace(
      /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?\b/g,
      (m, str, colon, boolNull) => {
        if (str) {
          if (colon) return `<span class="json-key">${str}</span><span class="json-punc">:</span>`;
          return `<span class="json-string">${str}</span>`;
        }
        if (boolNull) {
          if (boolNull === "null") return `<span class="json-null">${boolNull}</span>`;
          return `<span class="json-bool">${boolNull}</span>`;
        }
        return `<span class="json-number">${m}</span>`;
      }
    );
  }

  function render() {
    if (!viewport) return;
    if (state.tailing && selectionInsideViewport()) {
      state.pendingRender = true;
      return;
    }
    viewport.textContent = "";
    const frag = document.createDocumentFragment();
    state.visible.forEach((line) => {
      const row = document.createElement("div");
      row.className = "logs-line";

      const actions = document.createElement("span");
      actions.className = "logs-line-actions";

      const parsed = extractJsonFromLine(line);
      const viewBtn = document.createElement("button");
      viewBtn.type = "button";
      viewBtn.className = parsed ? "btn btn-outline-info" : "btn btn-outline-secondary";
      viewBtn.title = parsed ? "Inspect JSON" : "View line";
      viewBtn.textContent = parsed ? "JSON" : "VIEW";
      viewBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openJsonModal(line, parsed ? parsed.obj : null);
      });
      actions.appendChild(viewBtn);
      row.appendChild(actions);

      const text = document.createElement("span");
      text.className = "logs-line-text";
      text.textContent = line;
      row.appendChild(text);

      if (parsed) row.classList.add("logs-line-json");
      row.setAttribute("role", "button");
      row.setAttribute("tabindex", "0");
      row.title = parsed ? "Inspect JSON" : "View line";
      row.addEventListener("click", (e) => {
        if (e.target && e.target.closest && e.target.closest("button")) return;
        if (hasActiveSelection()) return;
        openJsonModal(line, parsed ? parsed.obj : null);
      });
      row.addEventListener("keydown", (e) => {
        const k = String(e.key || "").toLowerCase();
        if (k !== "enter" && k !== " " && k !== "spacebar") return;
        if (hasActiveSelection()) return;
        e.preventDefault();
        openJsonModal(line, parsed ? parsed.obj : null);
      });

      frag.appendChild(row);
    });
    viewport.appendChild(frag);
  }

  async function purgeLog() {
    const target = state.target || "error";
    try {
      const res = await fetch(`/logs/api/purge?target=${encodeURIComponent(target)}`, { method: "POST" });
      const j = await res.json();
      if (!res.ok || j.ok === false) throw new Error(j.error || "Purge failed");
      state.buffer = [];
      state.visible = [];
      state.carry = "";
      state.offset = 0;
      render();
    } catch (e) {
      alert(e.message || "Purge failed");
    }
  }

  function abortInFlight() {
    if (state.controller) {
      try { state.controller.abort(); } catch (_) {}
      state.controller = null;
    }
  }

  async function reload() {
    stopTail();
    state.buffer = [];
    state.visible = [];
    state.carry = "";
    state.offset = 0;
    updateArchiveControls();
    render();
    await loadArchives();
    if (archiveMode()) {
      await fetchArchiveAll(true);
      return;
    }
    await fetchChunk(true);
    if (state.tailing) startTail();
  }

  function refreshViewOptions() {
    if (!viewSel) return;
    const previous = state.view || "current";
    viewSel.innerHTML = "";
    const currentOpt = document.createElement("option");
    currentOpt.value = "current";
    currentOpt.textContent = "Current Log File";
    viewSel.appendChild(currentOpt);
    state.archives.forEach((a) => {
      const ts = a.mtime ? new Date(a.mtime * 1000).toLocaleString() : "";
      const kb = a.size ? `${Math.round(a.size / 1024)} KB` : "";
      const opt = document.createElement("option");
      opt.value = `archive:${a.name}`;
      opt.textContent = `Historic: ${a.name} Log File${ts || kb ? " (" : ""}${ts}${ts && kb ? ", " : ""}${kb}${ts || kb ? ")" : ""}`;
      viewSel.appendChild(opt);
    });
    const valid = previous === "current" || state.archives.some((a) => `archive:${a.name}` === previous);
    state.view = valid ? previous : "current";
    viewSel.value = state.view;
  }

  async function loadArchives() {
    state.archives = [];
    try {
      const res = await fetch(`/logs/api/archives?target=${encodeURIComponent(state.target)}&limit=200`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (json && json.ok && Array.isArray(json.archives)) {
        state.archives = json.archives;
      }
    } catch (_) {}
    refreshViewOptions();
  }

  async function fetchChunk(initial = false, opts = {}) {
    const silent = !!opts.silent;
    abortInFlight();
    state.controller = new AbortController();

    const url = new URL("/logs/api/chunk", window.location.origin);
    url.searchParams.set("target", state.target);
    if (state.view.startsWith("archive:")) {
      url.searchParams.set("archive", state.view.slice("archive:".length));
    }
    url.searchParams.set("lines", String(state.lines));
    url.searchParams.set("filter", state.keyword || "");
    url.searchParams.set("suppress_internal", "1");

    url.searchParams.set("offset", String(state.offset || 0));

    try {
      const res = await fetch(url.toString(), { signal: state.controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (json.data) appendChunk(json.data);

      state.offset = json.next_offset ?? state.offset;

      if (!silent) {
        applyFilter();
        if (initial && viewport) viewport.scrollTop = 0;
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        state.buffer.push(`[logs] poll error: ${e}`);
        if (!silent) applyFilter();
      }
    } finally {
      state.controller = null;
    }
  }

  async function fetchArchiveAll(initial = false) {
    let lastOffset = -1;
    let loops = 0;
    while (loops < ARCHIVE_MAX_LOOPS) {
      loops += 1;
      const before = state.offset || 0;
      await fetchChunk(initial && loops === 1, { silent: true });
      const after = state.offset || 0;
      if (after <= before || after === lastOffset) break;
      lastOffset = after;
    }
    applyFilter();
    if (initial && viewport) viewport.scrollTop = 0;
  }

  async function pollLoop() {
    await fetchChunk();
    state.timer = setTimeout(pollLoop, intervalMs);
  }

  function startTail() { stopTail(); pollLoop(); }
  function stopTail() { if (state.timer) clearTimeout(state.timer); state.timer = null; abortInFlight(); }

  function setScrollHeight() {
    const cardBody = document.querySelector(".card-body");
    const scrollArea = document.querySelector(".scroll-area");
    if (!cardBody || !scrollArea) return;
    const cardBodyHeight = cardBody.clientHeight - 74;
    scrollArea.style.display = "";
    scrollArea.style.maxHeight = `${cardBodyHeight}px`;
  }

  // Event wiring
  sourceTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const next = String(tab.getAttribute("data-log-target") || "").trim();
      if (!VALID_TARGETS.has(next)) return;
      if (next === state.target) return;
      state.target = next;
      saveTarget(state.target);
      setActiveSourceTab(state.target);
      state.view = "current";
      reload();
    });
  });
  viewSel?.addEventListener("change", () => {
    const nextView = viewSel.value || "current";
    const wasArchive = archiveMode();
    state.view = nextView;
    if (wasArchive && !archiveMode()) {
      state.tailing = true;
    }
    reload();
  });
  linesInput?.addEventListener("change", () => {
    state.lines = Math.max(50, parseInt(linesInput.value || "0", 10) || 200);
    reload();
  });
  keywordInput?.addEventListener("input", () => {
    state.keyword = keywordInput.value || "";
    applyFilter();
  });
  refreshBtn?.addEventListener("click", reload);
  clearBtn?.addEventListener("click", () => {
    state.buffer = [];
    state.visible = [];
    render();
  });
  purgeBtn?.addEventListener("click", purgeLog);
  toggleBtn?.addEventListener("click", () => {
    state.tailing = !state.tailing;
    toggleBtn.innerHTML = state.tailing
      ? '<i class="fa fa-pause"></i><span>Tailing</span>'
      : '<i class="fa fa-play"></i><span>Tail</span>';
    if (state.tailing) startTail(); else stopTail();
  });
  root.querySelectorAll('[data-action="json-close"]').forEach((el) => {
    el.addEventListener("click", closeJsonModal);
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeJsonModal();
  });
  document.addEventListener("selectionchange", maybeRenderDeferred);
  window.addEventListener("mouseup", maybeRenderDeferred);
  window.addEventListener("keyup", maybeRenderDeferred);

  reload();
  setScrollHeight();

  // Run on window resize
  window.addEventListener("resize", setScrollHeight);





})();
