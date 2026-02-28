(function () {
  const tableEl = document.getElementById("emu-table");
  const displaysEl = document.getElementById("liveview-displays");
  if (!tableEl) return;

  const COMPACT_LAYOUT_MEDIA = "(max-width: 1200px)";
  const COMPACT_BASE_TABLE_WIDTH_PX = 560;
  const COMPACT_BASE_TABLE_HEIGHT_PX = 1120;
  const LIVEVIEW_SCALE_FACTOR = 0.94;

  const state = {
    options: { width: 700, height: 1400 },
    playfield: { name: "", updatedAt: "", url: "", fit: "cover", position: "center", opacity: 1 },
    elements: [],
    keymap: {},
    tableRect: { width: 0, height: 0 },
    containerRect: { width: 0, height: 0 },
    activeKeyPresses: Object.create(null),
    eventSource: null,
    reconnectTimer: null,
    safetyById: {},
    ruleTriggersBySource: {},
    ruleActionsBySourceGesture: {},
    ruleActionsBySourceEvent: {},
    flipperHeldById: Object.create(null),
    displays: [],
    contextMenu: {
      root: null,
      targetId: "",
    },
  };

  function setStatus(text) {
    void text;
  }

  function gestureSortKey(gesture) {
    const order = ["PRESSED", "RELEASED", "CLICKED", "DOUBLE_CLICKED", "HELD", "REPEAT_WHILE_HELD"];
    const idx = order.indexOf(String(gesture || "").toUpperCase());
    return idx >= 0 ? idx : 999;
  }

  function closeContextMenu() {
    const root = state.contextMenu.root;
    if (!root) return;
    root.classList.remove("is-open");
    root.style.left = "-9999px";
    root.style.top = "-9999px";
    root.innerHTML = "";
    state.contextMenu.targetId = "";
  }

  function ensureContextMenuRoot() {
    if (state.contextMenu.root) return state.contextMenu.root;
    const root = document.createElement("div");
    root.className = "liveview-context-menu";
    root.setAttribute("role", "menu");
    root.addEventListener("click", (e) => e.stopPropagation());
    document.body.appendChild(root);
    state.contextMenu.root = root;
    return root;
  }

  function availableGesturesForElement(el) {
    const source = String(el?.hardwareId || el?.id || "").trim();
    if (!source) return [];
    const bySource = state.ruleTriggersBySource[source];
    if (!bySource || typeof bySource !== "object") return [];
    return Object.keys(bySource)
      .map((g) => String(g || "").trim().toUpperCase())
      .filter((g) => !!g && bySource[g] && bySource[g].name)
      .sort((a, b) => gestureSortKey(a) - gestureSortKey(b));
  }

  function isButtonLikeElement(el) {
    const dc = String(el?.deviceClass || "").trim().toLowerCase();
    if (dc === "button") return true;
    const icon = String(el?.icon || el?.type || "").trim().toLowerCase();
    return icon === "button";
  }

  function openContextMenuForElement(evt, el) {
    if (!el) return;
    const gestures = availableGesturesForElement(el);
    if (!gestures.length) {
      closeContextMenu();
      return;
    }
    evt.preventDefault();
    evt.stopPropagation();
    const root = ensureContextMenuRoot();
    const source = String(el.hardwareId || el.id || "").trim();
    const hasPressedReleased = gestures.includes("PRESSED") && gestures.includes("RELEASED");
    const rows = gestures.map((gesture) => {
      const binding = (state.ruleTriggersBySource[source] || {})[gesture] || {};
      const eventName = String(binding.name || "").trim();
      return `
        <button type="button" class="liveview-context-item" data-gesture="${esc(gesture)}" data-target-id="${esc(el.id)}">
          <span class="liveview-context-item-gesture">${esc(gesture)}</span>
          <span class="liveview-context-item-event">${esc(eventName)}</span>
        </button>`;
    });
    if (isButtonLikeElement(el) && hasPressedReleased) {
      rows.push(`
        <button type="button" class="liveview-context-item" data-gesture="PRESSED_AND_RELEASED" data-target-id="${esc(el.id)}">
          <span class="liveview-context-item-gesture">PRESSED + RELEASED</span>
          <span class="liveview-context-item-event">Combined</span>
        </button>`);
    }
    root.innerHTML = rows.join("");

    root.querySelectorAll(".liveview-context-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = String(btn.getAttribute("data-target-id") || "").trim();
        const gesture = String(btn.getAttribute("data-gesture") || "").trim().toUpperCase();
        closeContextMenu();
        if (!targetId || !gesture) return;
        if (gesture === "PRESSED_AND_RELEASED") {
          fireBoundEventById(targetId, "PRESSED");
          setTimeout(() => fireBoundEventById(targetId, "RELEASED"), 90);
          return;
        }
        fireBoundEventById(targetId, gesture);
      });
    });

    root.classList.add("is-open");
    const vw = window.innerWidth || document.documentElement.clientWidth || 1024;
    const vh = window.innerHeight || document.documentElement.clientHeight || 768;
    root.style.left = "0px";
    root.style.top = "0px";
    const rect = root.getBoundingClientRect();
    const margin = 8;
    const x = Math.max(margin, Math.min((evt.clientX || 0), vw - rect.width - margin));
    const y = Math.max(margin, Math.min((evt.clientY || 0), vh - rect.height - margin));
    root.style.left = `${x}px`;
    root.style.top = `${y}px`;
    state.contextMenu.targetId = String(el.id || "");
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toPositiveInt(value, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return fallback;
    return Math.max(1, Math.round(n));
  }

  function isDisplayEnabled(value) {
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value !== 0;
    const s = String(value || "").trim().toLowerCase();
    return s === "1" || s === "true" || s === "yes" || s === "on";
  }

  function displayTitle(display, index) {
    const role = String(display?.role || "").trim();
    if (role) return role;
    const name = String(display?.name || "").trim();
    if (name) return name;
    const id = String(display?.id || "").trim();
    if (id) return id;
    return `Display ${index + 1}`;
  }

  function renderDisplays() {
    if (!displaysEl) return;
    const rows = Array.isArray(state.displays) ? state.displays : [];
    if (!rows.length) {
      displaysEl.innerHTML = `
        <div class="card emu-card liveview-display-card">
          <div class="card-header">Displays</div>
          <div class="card-body">
            <div class="text-secondary small">No enabled displays configured.</div>
          </div>
        </div>`;
      return;
    }
    displaysEl.innerHTML = rows.map((display, index) => {
      const width = toPositiveInt(display?.width, 1920);
      const height = toPositiveInt(display?.height, 1080);
      const ratio = `${width} / ${height}`;
      const displayId = String(display?.id || "").trim();
      const runtimeSrc = displayId
        ? `/media/runtime/display/${encodeURIComponent(displayId)}`
        : "";
      return `
        <div class="card emu-card liveview-display-card">
          <div class="card-header d-flex justify-content-between align-items-center gap-2">
            <span class="liveview-display-title">${esc(displayTitle(display, index))}</span>
            <span class="liveview-display-size text-secondary">${width}x${height}</span>
          </div>
          <div class="card-body">
            <div class="liveview-display-preview" style="aspect-ratio:${ratio};">
              ${runtimeSrc
    ? `<iframe class="liveview-display-runtime" src="${runtimeSrc}" title="${esc(displayTitle(display, index))} runtime preview" loading="lazy" referrerpolicy="same-origin"></iframe>`
    : `<span class="liveview-display-preview-size">${width} x ${height}</span>`}
            </div>
          </div>
        </div>`;
    }).join("");
  }

  function legacySizeToScale(size) {
    switch (String(size || "m").toLowerCase()) {
      case "s": return 0.5;
      case "l": return 1.5;
      case "xl": return 2;
      default: return 1;
    }
  }

  function normalizeElementVisuals(el) {
    if (!el || typeof el !== "object") return;
    if (!Number.isFinite(Number(el.scale))) {
      el.scale = legacySizeToScale(el.size || "m");
      el.size = "m";
    } else {
      el.scale = Math.max(0.5, Math.min(2.5, Number(el.scale)));
    }
    if (!Number.isFinite(Number(el.rotation))) {
      el.rotation = 0;
    } else {
      el.rotation = Math.max(-180, Math.min(180, Number(el.rotation)));
    }
    if (!el.size) el.size = "m";
  }

  function ensureNormalizedAndSync() {
    const w = state.tableRect.width || 1;
    const h = state.tableRect.height || 1;
    state.elements.forEach((el) => {
      normalizeElementVisuals(el);
      if (el.nx === undefined || el.ny === undefined) {
        if (w > 0) el.nx = (el.x || 0) / w;
        if (h > 0) el.ny = (el.y || 0) / h;
      }
      el.x = (el.nx || 0.5) * w;
      el.y = (el.ny || 0.5) * h;
    });
  }

  function computeTableRect() {
    const W = state.containerRect.width || 10;
    const H = state.containerRect.height || 10;
    const rw = Number(state.options.width) || 1;
    const rh = Number(state.options.height) || 1;
    const ratio = rw / rh;
    let width = W;
    let height = W / ratio;
    if (height > H) {
      height = H;
      width = H * ratio;
    }
    state.tableRect = { width, height };
  }

  function tableVisualScale() {
    const w = Number(state.tableRect.width) || 0;
    const h = Number(state.tableRect.height) || 0;
    if (w <= 0 || h <= 0) return 1;
    const compactByViewport = window.matchMedia(COMPACT_LAYOUT_MEDIA).matches;
    const compactByTable = w < COMPACT_BASE_TABLE_WIDTH_PX || h < COMPACT_BASE_TABLE_HEIGHT_PX;
    if (!compactByViewport && !compactByTable) return 1;
    const sx = w / COMPACT_BASE_TABLE_WIDTH_PX;
    const sy = h / COMPACT_BASE_TABLE_HEIGHT_PX;
    const s = Math.min(sx, sy);
    return Math.max(0.35, Math.min(1, s));
  }

  function updateTableSize() {
    if (!tableEl || !tableEl.parentElement) return;
    const wrap = tableEl.parentElement;
    const cs = getComputedStyle(wrap);
    const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const padY = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
    const width = Math.max(0, Math.round(wrap.clientWidth - padX));
    const height = Math.max(0, Math.round(wrap.clientHeight - padY));
    state.containerRect = { width, height };
    const prev = { ...state.tableRect };
    computeTableRect();
    if (state.tableRect.width > 0 && state.tableRect.height > 0) {
      ensureNormalizedAndSync();
      if (prev.width !== state.tableRect.width || prev.height !== state.tableRect.height) {
        renderTable();
      }
      const visualScale = tableVisualScale() * LIVEVIEW_SCALE_FACTOR;
      tableEl.style.width = `${state.tableRect.width}px`;
      tableEl.style.height = `${state.tableRect.height}px`;
      tableEl.style.setProperty("--emu-table-scale", String(visualScale));
    }
  }

  function svgFor(el) {
    const color = el.color || "#60a5fa";
    const stroke = "#e5e7eb";
    const type = el.icon || el.type;
    switch (type) {
      case "flipper-left":
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44"><g transform="translate(109.3 0) scale(-1 1)"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></g></svg>`;
      case "flipper-right":
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></svg>`;
      case "launch-plunger":
        return `<svg class="emu-svg" viewBox="0 0 28 96" xmlns="http://www.w3.org/2000/svg"><path d="M6 92V12A8 8 0 0 1 14 4A8 8 0 0 1 22 12V92Z" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
      case "bumper":
        return `<svg class="emu-svg" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="16" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
      case "pop-bumper":
        return `<svg class="emu-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><circle cx="32" cy="32" r="26" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
      case "led":
        return `<svg class="emu-svg" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><circle cx="14" cy="14" r="10" fill="${color}" /></svg>`;
      case "rgb":
        return `<svg class="emu-svg" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="g"><stop offset="0%" stop-color="#fff"/><stop offset="100%" stop-color="${color}"/></radialGradient></defs><circle cx="14" cy="14" r="10" fill="url(#g)" /></svg>`;
      case "target":
        return `<svg class="emu-svg" viewBox="0 0 20 40" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="12" height="32" rx="3" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
      case "coil":
        return `<svg class="emu-svg" viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="4" width="36" height="12" rx="3" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
      default:
        return `<svg class="emu-svg" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="12" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
  }

  function renderTable() {
    const visualScale = tableVisualScale() * LIVEVIEW_SCALE_FACTOR;
    tableEl.innerHTML = "";
    tableEl.style.width = `${state.tableRect.width}px`;
    tableEl.style.height = `${state.tableRect.height}px`;
    tableEl.style.setProperty("--emu-table-scale", String(visualScale));

    state.elements.forEach((el) => {
      const node = document.createElement("div");
      node.className = "emu-el";
      node.dataset.id = el.id;
      node.dataset.type = el.icon || el.type;
      node.dataset.size = el.size || "m";
      node.style.setProperty("--emu-size-scale", String((Number(el.scale) || 1) * visualScale));
      node.style.setProperty("--emu-rotation-deg", `${Number(el.rotation) || 0}deg`);
      node.style.setProperty("--emu-glow-color", el.color || "#22c55e");
      node.style.setProperty("--emu-glow-scale", String(Math.max(0.7, Math.min(2.5, Number(el.scale) || 1))));
      node.style.left = `${el.x}px`;
      node.style.top = `${el.y}px`;
      node.innerHTML = svgFor(el);
      if (state.flipperHeldById[el.id]) {
        const heldType = String(el.icon || el.type || "").toLowerCase();
        if (heldType === "flipper-left") node.classList.add("is-flip-left-held", "is-flip-held-lowpower");
        else if (heldType === "flipper-right") node.classList.add("is-flip-right-held", "is-flip-held-lowpower");
      }
      node.addEventListener("contextmenu", (evt) => openContextMenuForElement(evt, el));
      tableEl.appendChild(node);
    });
  }

  function toCssUrl(url) {
    return String(url || "").replace(/["\\]/g, "\\$&");
  }

  function colorWithAlpha(color, alpha) {
    const c = String(color || "").trim();
    const m = c.match(/^rgba?\(([^)]+)\)$/i);
    if (!m) return `rgba(0,0,0,${alpha})`;
    const parts = m[1].split(",").map((x) => x.trim());
    const r = Number(parts[0] || 0);
    const g = Number(parts[1] || 0);
    const b = Number(parts[2] || 0);
    const rr = Number.isFinite(r) ? Math.max(0, Math.min(255, r)) : 0;
    const gg = Number.isFinite(g) ? Math.max(0, Math.min(255, g)) : 0;
    const bb = Number.isFinite(b) ? Math.max(0, Math.min(255, b)) : 0;
    return `rgba(${rr},${gg},${bb},${alpha})`;
  }

  function applyPlayfieldBackground() {
    const url = state.playfield?.url || "";
    if (!url) {
      tableEl.style.removeProperty("background-image");
      tableEl.style.removeProperty("background-size");
      tableEl.style.removeProperty("background-position");
      tableEl.style.removeProperty("background-repeat");
      return;
    }
    const opacity = Number.isFinite(Number(state.playfield?.opacity)) ? Number(state.playfield.opacity) : 1;
    const clampedOpacity = Math.max(0, Math.min(1, opacity));
    const overlayAlpha = 1 - clampedOpacity;
    const base = getComputedStyle(tableEl).backgroundColor || "rgb(0, 0, 0)";
    const overlay = colorWithAlpha(base, overlayAlpha);
    const bgImage = overlayAlpha > 0.001
      ? `linear-gradient(${overlay}, ${overlay}), url("${toCssUrl(url)}")`
      : `url("${toCssUrl(url)}")`;
    tableEl.style.setProperty("background-image", bgImage, "important");
    const fitMode = state.playfield?.fit || "cover";
    const bgSize = fitMode === "exact" ? "100% 100%" : fitMode;
    const bgPos = fitMode === "exact" ? "0% 0%" : (state.playfield?.position || "center");
    tableEl.style.setProperty("background-size", bgSize, "important");
    tableEl.style.setProperty("background-position", bgPos, "important");
    tableEl.style.setProperty("background-repeat", "no-repeat", "important");
  }

  function pulseElement(id) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.remove("is-fired");
    void node.offsetWidth;
    node.classList.add("is-fired");
    setTimeout(() => node.classList.remove("is-fired"), 200);
  }

  function pressElement(id) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.remove("is-pressed");
    void node.offsetWidth;
    node.classList.add("is-pressed");
    setTimeout(() => node.classList.remove("is-pressed"), 150);
  }

  function pulseLaunchPlunger(id) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.remove("is-launch-fired");
    void node.offsetWidth;
    node.classList.add("is-launch-fired");
    setTimeout(() => node.classList.remove("is-launch-fired"), 180);
  }

  function isLedLike(el) {
    const type = (el?.icon || el?.type || "").toLowerCase();
    return type === "led" || type === "rgb";
  }

  function outputValueIsHigh(v) {
    if (typeof v === "boolean") return v;
    const n = Number(v);
    if (!Number.isNaN(n)) return n !== 0;
    const s = String(v || "").trim().toUpperCase();
    return s === "HIGH" || s === "ON" || s === "TRUE" || s === "SET";
  }

  function outputValueIsPulse(v) {
    return String(v || "").trim().toUpperCase() === "PULSE";
  }

  function safeLevelIsHighForTarget(targetSource, targetEl) {
    const candidates = [];
    if (targetSource) candidates.push(String(targetSource));
    if (targetEl?.hardwareId) candidates.push(String(targetEl.hardwareId));
    if (targetEl?.id) candidates.push(String(targetEl.id));
    for (const key of candidates) {
      const raw = String(state.safetyById?.[key] || "").trim().toUpperCase();
      if (raw === "HIGH") return true;
      if (raw === "LOW") return false;
    }
    return false;
  }

  function setOutputIsActiveForTarget(targetSource, targetEl, actionParams) {
    if (outputValueIsPulse(actionParams?.value)) return true;
    const commandHigh = outputValueIsHigh(actionParams?.value);
    const safeHigh = safeLevelIsHighForTarget(targetSource, targetEl);
    return commandHigh !== safeHigh;
  }

  function setOutputVisual(id, isOn) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.toggle("is-output-on", !!isOn);
  }

  function inferGestureFromEventName(name) {
    const n = String(name || "").toUpperCase();
    const suffixMap = [
      ["_DOUBLE_CLICKED", "DOUBLE_CLICKED"],
      ["_HELD", "HELD"],
      ["_CLICKED", "CLICKED"],
      ["_PRESSED", "PRESSED"],
      ["_RELEASED", "RELEASED"],
    ];
    for (const [suffix, fn] of suffixMap) {
      if (n.endsWith(suffix)) return fn;
    }
    return null;
  }

  function inferFlipperDirectionHint(targetSource, hintDir) {
    if (hintDir === "left" || hintDir === "right") return hintDir;
    const raw = String(targetSource || "").toLowerCase();
    if (raw.includes("left")) return "left";
    if (raw.includes("right")) return "right";
    return null;
  }

  function flipElement(id, dir, durationMs) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-fired" : "is-flip-left-fired";
    node.classList.remove("is-flip-left-fired", "is-flip-right-fired", "is-flip-left-tohold", "is-flip-right-tohold");
    node.style.setProperty("--emu-flip-ms", `${Math.max(60, Math.min(280, durationMs || 90))}ms`);
    void node.offsetWidth;
    node.classList.add(cls);
    setTimeout(() => {
      node.classList.remove(cls);
      node.style.removeProperty("--emu-flip-ms");
    }, Math.max(90, durationMs || 90) + 20);
  }

  function setFlipperHeld(id, dir, isOn) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-held" : "is-flip-left-held";
    state.flipperHeldById[id] = !!isOn;
    node.classList.toggle(cls, !!isOn);
    node.classList.toggle("is-flip-held-lowpower", !!isOn);
  }

  function kickFlipper(id, dir) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-kick" : "is-flip-left-kick";
    node.classList.remove("is-flip-left-kick", "is-flip-right-kick");
    void node.offsetWidth;
    node.classList.add(cls);
    setTimeout(() => node.classList.remove(cls), 95);
  }

  function animateRuleTarget(targetSource, actionType, actionParams, dirHint) {
    const visualAction = String(actionType || "").trim().toLowerCase();
    if (!["set_output", "pulse", "emit_event"].includes(visualAction)) return;
    const targetEl = state.elements.find((el) => el.hardwareId === targetSource || el.id === targetSource);
    const outputActive = setOutputIsActiveForTarget(targetSource, targetEl || null, actionParams || {});
    if (!targetEl) {
      const fallbackDir = inferFlipperDirectionHint(targetSource, dirHint);
      if (!fallbackDir) return;
      const fallbackEl = state.elements.find((el) => {
        const kind = (el.icon || el.type || "").toLowerCase();
        return (fallbackDir === "left" && kind === "flipper-left") || (fallbackDir === "right" && kind === "flipper-right");
      });
      if (!fallbackEl) return;
      if (visualAction === "set_output") {
        if (outputActive) {
          kickFlipper(fallbackEl.id, fallbackDir);
          setFlipperHeld(fallbackEl.id, fallbackDir, true);
        } else {
          setFlipperHeld(fallbackEl.id, fallbackDir, false);
        }
      } else {
        flipElement(fallbackEl.id, fallbackDir, 110);
      }
      return;
    }
    const kind = (targetEl.icon || targetEl.type || "").toLowerCase();
    if (kind === "flipper-left" || kind === "flipper-right") {
      const dir = kind === "flipper-left" ? "left" : "right";
      if (visualAction === "set_output") {
        if (outputActive) {
          kickFlipper(targetEl.id, dir);
          setFlipperHeld(targetEl.id, dir, true);
        } else {
          setFlipperHeld(targetEl.id, dir, false);
        }
      } else {
        flipElement(targetEl.id, dir, 110);
      }
      return;
    }
    if (kind === "launch-plunger") {
      if (visualAction === "pulse" || (visualAction === "set_output" && outputActive)) {
        pulseLaunchPlunger(targetEl.id);
      }
      return;
    }
    if (visualAction === "set_output" && isLedLike(targetEl)) {
      setOutputVisual(targetEl.id, outputActive);
      return;
    }
    pulseElement(targetEl.id);
  }

  function triggerRuleActionAnimations(ev) {
    if (!ev) return 0;
    const source = (ev.source || "").trim();
    if (!source) return 0;
    const params = ev.params && typeof ev.params === "object" ? ev.params : {};
    const eventType = typeof params.eventType === "string" ? params.eventType.trim() : "";
    const gesture = eventType || inferGestureFromEventName(ev.name);
    const out = [];
    const seen = new Set();

    if (gesture) {
      const key = `${source}|${gesture}`;
      const hits = state.ruleActionsBySourceGesture[key] || [];
      hits.forEach((entry) => {
        const k = `${entry.target}|${entry.type}|${JSON.stringify(entry.params || {})}`;
        if (seen.has(k)) return;
        seen.add(k);
        out.push(entry);
      });
    }
    if (!gesture) {
      const byEvent = state.ruleActionsBySourceEvent[`${source}|${ev.name}`] || [];
      byEvent.forEach((entry) => {
        const k = `${entry.target}|${entry.type}|${JSON.stringify(entry.params || {})}`;
        if (seen.has(k)) return;
        seen.add(k);
        out.push(entry);
      });
    }

    out.forEach((entry) => animateRuleTarget(entry.target, entry.type, entry.params || {}, entry.dir || null));
    return out.length;
  }

  function fireEvent(name, source, params) {
    return fetch("/api/events/fire", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ name, source, params: params || {} }),
    }).catch(() => null);
  }

  function ruleBindingForSource(source, gesture) {
    const entry = state.ruleTriggersBySource[source];
    if (!entry) return null;
    return entry[gesture] || null;
  }

  function fireBoundEventById(id, gesture) {
    const el = state.elements.find((e) => String(e.id) === String(id));
    if (!el) return;
    const source = String(el.hardwareId || el.id || "");
    if (!source) return;
    const ruleBinding = ruleBindingForSource(source, String(gesture || "").toUpperCase());
    if (!ruleBinding || !ruleBinding.name) return;
    const params = Object.assign({}, ruleBinding.params || {});
    params.eventType = String(gesture || "").toUpperCase();
    pressElement(el.id);
    triggerRuleActionAnimations({ source, name: ruleBinding.name, params });
    fireEvent(ruleBinding.name, source, params);
  }

  function normalizeKeymapEntry(entry) {
    if (!entry || typeof entry !== "object") return null;
    const id = String(entry.id || "").trim();
    if (!id) return null;
    return {
      id,
      keyDownGesture: String(entry.keyDownGesture || "PRESSED").trim().toUpperCase(),
      keyUpGesture: String(entry.keyUpGesture || "").trim().toUpperCase(),
    };
  }

  function onKeyDown(evt) {
    const key = String(evt?.key || "").toLowerCase();
    if (!key || state.activeKeyPresses[key]) return;
    const entry = normalizeKeymapEntry(state.keymap[key]);
    if (!entry) return;
    state.activeKeyPresses[key] = true;
    fireBoundEventById(entry.id, entry.keyDownGesture || "PRESSED");
  }

  function onKeyUp(evt) {
    const key = String(evt?.key || "").toLowerCase();
    if (!key) return;
    const entry = normalizeKeymapEntry(state.keymap[key]);
    delete state.activeKeyPresses[key];
    if (!entry || !entry.keyUpGesture) return;
    fireBoundEventById(entry.id, entry.keyUpGesture);
  }

  function eventMatchesElement(ev, el) {
    if (!el) return false;
    if (ev.source && (ev.source === el.hardwareId || ev.source === el.id)) return true;
    return false;
  }

  function handleIncomingEvent(ev) {
    if (!ev) return;
    const applied = triggerRuleActionAnimations(ev);
    if (applied > 0) return;
    const matching = state.elements.filter((el) => eventMatchesElement(ev, el));
    matching.forEach((el) => {
      const eventType = String(ev?.params?.eventType || "").toUpperCase();
      if (eventType === "PRESSED") pressElement(el.id);
      else pulseElement(el.id);
    });
  }

  function connectEventStream() {
    if (!window.EventSource) return;
    if (state.eventSource) {
      try { state.eventSource.close(); } catch (_) {}
      state.eventSource = null;
    }
    const es = new EventSource("/api/events/stream");
    state.eventSource = es;
    es.onopen = () => setStatus("Live");
    es.onmessage = (msg) => {
      try {
        handleIncomingEvent(JSON.parse(msg.data || "{}"));
      } catch (_) {}
    };
    es.onerror = () => {
      setStatus("Reconnecting…");
      try { es.close(); } catch (_) {}
      if (state.eventSource === es) state.eventSource = null;
      if (!state.reconnectTimer) {
        state.reconnectTimer = setTimeout(() => {
          state.reconnectTimer = null;
          connectEventStream();
        }, 1500);
      }
    };
  }

  async function loadState() {
    const r = await fetch("/api/playfield/state", { credentials: "same-origin" });
    const data = await r.json();
    state.options = data.options || state.options;
    state.playfield = data.playfield || state.playfield;
    state.elements = Array.isArray(data.elements) ? data.elements : [];
    state.keymap = data.keymap || {};
    Object.entries(state.keymap).forEach(([k, v]) => {
      const norm = normalizeKeymapEntry(v);
      if (norm) state.keymap[k] = norm;
      else delete state.keymap[k];
    });
    ensureNormalizedAndSync();
    applyPlayfieldBackground();
    updateTableSize();
    renderTable();
  }

  async function loadHardwareSafety() {
    try {
      const r = await fetch("/api/playfield/hardware", { credentials: "same-origin" });
      const data = await r.json();
      state.safetyById = (data && data.safetyById && typeof data.safetyById === "object") ? data.safetyById : {};
    } catch (_) {
      state.safetyById = {};
    }
  }

  async function loadRules() {
    const r = await fetch("/api/rules/list", { credentials: "same-origin" });
    if (!r.ok) return;
    const data = await r.json();
    const rules = data && data.rules ? data.rules : [];
    const bySource = {};
    const actionByGesture = {};
    const actionByEvent = {};

    rules.forEach((rule) => {
      const triggerBindings = [];
      (rule.triggers || []).forEach((item) => {
        if (item?.type !== "hardware") return;
        const source = item.source;
        const gesture = item.fn;
        const name = item.event;
        if (!source || !gesture || !name) return;
        bySource[source] = bySource[source] || {};
        if (!bySource[source][gesture]) bySource[source][gesture] = { name, params: item.params || {} };
        triggerBindings.push({ source, fn: gesture, event: name });
      });
      const groups = rule?.triggerGroups?.groups || [];
      groups.forEach((group) => {
        (group.items || []).forEach((item) => {
          if (item?.type !== "hardware") return;
          const source = item.source;
          const gesture = item.fn;
          const name = item.event;
          if (!source || !gesture || !name) return;
          bySource[source] = bySource[source] || {};
          if (!bySource[source][gesture]) bySource[source][gesture] = { name, params: item.params || {} };
          triggerBindings.push({ source, fn: gesture, event: name });
        });
      });

      (rule.actions || []).forEach((action) => {
        const target = action.target || action.params?.device || action.params?.target;
        if (!target) return;
        triggerBindings.forEach((tb) => {
          const gk = `${tb.source}|${tb.fn}`;
          actionByGesture[gk] = actionByGesture[gk] || [];
          actionByGesture[gk].push({
            target,
            type: action.type || "",
            params: action.params || {},
          });
          const ek = `${tb.source}|${tb.event}`;
          actionByEvent[ek] = actionByEvent[ek] || [];
          actionByEvent[ek].push({
            target,
            type: action.type || "",
            params: action.params || {},
          });
        });
      });
    });

    state.ruleTriggersBySource = bySource;
    state.ruleActionsBySourceGesture = actionByGesture;
    state.ruleActionsBySourceEvent = actionByEvent;
  }

  async function loadDisplays() {
    try {
      const r = await fetch("/api/media/config", { credentials: "same-origin" });
      if (!r.ok) {
        state.displays = [];
        renderDisplays();
        return;
      }
      const data = await r.json();
      const displays = Array.isArray(data?.config?.displays) ? data.config.displays : [];
      state.displays = displays.filter((d) => isDisplayEnabled(d?.enabled));
    } catch (_) {
      state.displays = [];
    }
    renderDisplays();
  }

  function initListeners() {
    if (typeof ResizeObserver !== "undefined" && tableEl.parentElement) {
      const ro = new ResizeObserver(() => {
        updateTableSize();
        renderTable();
      });
      ro.observe(tableEl.parentElement);
    } else {
      window.addEventListener("resize", () => {
        updateTableSize();
        renderTable();
      });
    }
    window.addEventListener("keydown", onKeyDown, false);
    window.addEventListener("keyup", onKeyUp, false);
    window.addEventListener("blur", () => { state.activeKeyPresses = Object.create(null); });
    window.addEventListener("click", () => closeContextMenu(), false);
    window.addEventListener("contextmenu", (evt) => {
      if (!(evt.target instanceof Element) || !evt.target.closest(".emu-el")) closeContextMenu();
    }, false);
    window.addEventListener("resize", () => closeContextMenu(), false);
    document.addEventListener("scroll", () => closeContextMenu(), true);
    window.addEventListener("pagehide", () => {
      closeContextMenu();
      if (state.eventSource) {
        try { state.eventSource.close(); } catch (_) {}
        state.eventSource = null;
      }
      if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
      }
    });
  }

  async function init() {
    try {
      await Promise.all([loadState(), loadHardwareSafety(), loadRules(), loadDisplays()]);
      connectEventStream();
      setStatus("Live");
    } catch (e) {
      console.error(e);
      setStatus("Load failed");
    }
    initListeners();
  }

  init();
})();
