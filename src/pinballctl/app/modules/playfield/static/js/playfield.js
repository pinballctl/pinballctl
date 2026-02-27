// Vanilla playfield layout editor.
(function () {
  document.body.classList.add("emu-page");
  const root = document.getElementById("emu-root");
  if (!root) return;

  const tableEl = document.getElementById("emu-table");
  const widthInput = document.getElementById("emu-width");
  const heightInput = document.getElementById("emu-height");
  const ratioEl = document.getElementById("emu-ratio");
  const playfieldFileInput = document.getElementById("emu-playfield-file");
  const playfieldUploadBtn = document.getElementById("emu-playfield-upload");
  const playfieldRemoveBtn = document.getElementById("emu-playfield-remove");
  const playfieldStatus = document.getElementById("emu-playfield-status");
  const playfieldPreviewWrap = document.getElementById("emu-playfield-preview-wrap");
  const playfieldPreviewImg = document.getElementById("emu-playfield-preview-img");
  const playfieldFitSel = document.getElementById("emu-playfield-fit");
  const playfieldPositionSel = document.getElementById("emu-playfield-position");
  const playfieldOpacityInput = document.getElementById("emu-playfield-opacity");
  const playfieldOpacityValue = document.getElementById("emu-playfield-opacity-value");
  const centerBtn = document.getElementById("emu-center");
  const clearBtn = document.getElementById("emu-clear");
  const saveBtn = document.getElementById("emu-save");

  const hwStatus = document.getElementById("emu-hw-status");
  const buttonsWrap = document.getElementById("emu-buttons");
  const ledsWrap = document.getElementById("emu-leds");
  const solenoidsWrap = document.getElementById("emu-solenoids");
  const otherWrap = document.getElementById("emu-other");

  const noSel = document.getElementById("emu-no-selection");
  const settings = document.getElementById("emu-settings");
  const selectedLabel = document.getElementById("emu-selected-label");
  const appearanceSel = document.getElementById("emu-appearance");
  const colorInput = document.getElementById("emu-color");
  const sizeScaleInput = document.getElementById("emu-size-scale");
  const sizeScaleValue = document.getElementById("emu-size-scale-value");
  const rotationInput = document.getElementById("emu-rotation");
  const rotationValue = document.getElementById("emu-rotation-value");
  const linkRow = document.getElementById("emu-link-row");
  const linkInfo = document.getElementById("emu-link-info");
  const unlinkBtn = document.getElementById("emu-unlink");
  const eventsTitle = document.getElementById("emu-events-title");
  const captureBtn = document.getElementById("emu-capture");
  const bindRow = document.getElementById("emu-bind-row");
  const boundWrap = document.getElementById("emu-bound-wrap");
  const boundKeys = document.getElementById("emu-bound-keys");
  const removeBtn = document.getElementById("emu-remove");
  const eventsWrap = document.getElementById("emu-events");

  const PAD = 45;
  const DRAG_START_DISTANCE_PX = 6;
  const DEBUG_EVENTS = false;
  const COMPACT_LAYOUT_MEDIA = "(max-width: 1200px)";
  const COMPACT_BASE_TABLE_WIDTH_PX = 560;
  const COMPACT_BASE_TABLE_HEIGHT_PX = 1120;
  const PANEL_STATE_KEY = "pinballctl.playfield.panelState.v1";
  const panelState = {};

  function dbg(...args) {
    if (!DEBUG_EVENTS) return;
    console.log("[EMU_EVT]", ...args);
  }

  function loadPanelState() {
    try {
      const raw = window.localStorage.getItem(PANEL_STATE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object") return;
      Object.keys(data).forEach((k) => {
        if (typeof data[k] === "boolean") panelState[k] = data[k];
      });
    } catch (_) {}
  }

  function savePanelState() {
    try {
      window.localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(panelState));
    } catch (_) {}
  }
  const state = {
    options: { width: 700, height: 1400 },
    playfield: { name: "", updatedAt: "", url: "", fit: "cover", position: "center", opacity: 1 },
    elements: [],
    keymap: {},
    selectedId: null,
    components: { buttons: [], leds: [], solenoids: [], other: [] },
    hardwareLoaded: false,
    containerRect: { width: 0, height: 0 },
    tableRect: { width: 0, height: 0 },
    dragging: null,
    dragPending: null,
    _elNodeCache: Object.create(null),
    waitingForKey: false,
    _capBtnList: null,
    defaultSizeForType: {
      led: "s", rgb: "s", button: "m", target: "m", coil: "m",
      "flipper-left": "m", "flipper-right": "m", "launch-plunger": "m", bumper: "l", "pop-bumper": "xl"
    },
    dirty: false,
    registry: {
      systemEvents: [],
      customPattern: null,
      hardwareEvents: {},
    },
    ruleTriggersBySource: {},
    ruleTargetsBySource: {},
    ruleTargetInfoBySource: {},
    ruleActionsBySourceGesture: {},
    ruleActionsBySourceEvent: {},
    ruleLinkedPairs: [],
    contextMenu: null,
    recentEvents: [],
    pendingLocalBySig: Object.create(null),
    recentAppliedBySigAt: Object.create(null),
    flipperHeldById: Object.create(null),
    pendingHoldTimers: Object.create(null),
    activeKeyPresses: Object.create(null),
    captureKeyListener: null,
    eventSource: null,
    safetyById: {},
  };
  let bypassUnloadOnce = false;

  function markDirty(flag = true) {
    state.dirty = !!flag;
    if (saveBtn) {
      saveBtn.disabled = !state.dirty;
      saveBtn.setAttribute("aria-disabled", state.dirty ? "false" : "true");
    }
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
  }

  function renderScaleValue(scale) {
    if (sizeScaleValue) sizeScaleValue.textContent = `${Math.round((Number(scale) || 1) * 100)}%`;
  }

  function renderRotationValue(deg) {
    if (rotationValue) rotationValue.textContent = `${Math.round(Number(deg) || 0)}°`;
  }

  function applyInitialThemeWatcher() {
    const updateDark = () => {
      const mode = (document.documentElement.getAttribute("data-theme") || "dark");
      root.classList.toggle("is-dark", mode === "dark");
    };
    updateDark();
    const mo = new MutationObserver(updateDark);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
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
      if (!el.size) {
        const t = el.icon || el.type;
        el.size = state.defaultSizeForType[t] || "m";
      }
    });
  }

  function resyncPixelFromNorm() {
    const w = state.tableRect.width || 1;
    const h = state.tableRect.height || 1;
    state.elements.forEach((el) => {
      el.x = (el.nx || 0.5) * w;
      el.y = (el.ny || 0.5) * h;
    });
    renderTable();
  }

  function ratioText() {
    const w = Number(state.options.width) || 1;
    const h = Number(state.options.height) || 1;
    const r = (w / h).toFixed(3);
    return `${w}×${h} (${r}:1)`;
  }

  function computeTableRect() {
    const W = state.containerRect.width || 10;
    const H = state.containerRect.height || 10;
    const rw = Number(state.options.width) || 1;
    const rh = Number(state.options.height) || 1;
    const ratio = rw / rh;
    let width = W;
    let height = W / ratio;
    if (height > H) { height = H; width = H * ratio; }
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
        resyncPixelFromNorm();
      }
      tableEl.style.width = `${state.tableRect.width}px`;
      tableEl.style.height = `${state.tableRect.height}px`;
      tableEl.style.setProperty("--emu-table-scale", String(tableVisualScale()));
    }
  }

  function svgFor(el) {
    if (!el) return "";
    const color = el.color || "#60a5fa";
    const stroke = "#e5e7eb";
    const type = el.icon || el.type;
    switch (type) {
      case "flipper-left":
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44" role="img" aria-label="Flipper"><g transform="translate(109.3 0) scale(-1 1)"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></g></svg>`;
      case "flipper-right":
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44" role="img" aria-label="Flipper"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></svg>`;
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
      case "button":
      default:
        return `<svg class="emu-svg" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="12" fill="${color}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
  }

  function renderTable() {
    if (!tableEl) return;
    const visualScale = tableVisualScale();
    tableEl.innerHTML = "";
    tableEl.style.width = `${state.tableRect.width}px`;
    tableEl.style.height = `${state.tableRect.height}px`;
    tableEl.style.setProperty("--emu-table-scale", String(visualScale));

    state.elements.forEach((el) => {
      const node = document.createElement("div");
      node.className = "emu-el";
      if (el.id === state.selectedId) node.classList.add("is-selected");
      node.dataset.id = el.id;
      node.dataset.type = el.icon || el.type;
      node.dataset.size = el.size || "m";
      node.style.setProperty("--emu-size-scale", String((Number(el.scale) || 1) * visualScale));
      node.style.setProperty("--emu-rotation-deg", `${Number(el.rotation) || 0}deg`);
      node.style.setProperty("--emu-glow-color", el.color || "#22c55e");
      node.style.setProperty("--emu-glow-scale", String(Math.max(0.7, Math.min(2.5, Number(el.scale) || 1))));
      node.style.left = `${el.x}px`;
      node.style.top = `${el.y}px`;
      node.innerHTML = `<span class="sr-only">${el.label}</span>${svgFor(el)}`;
      if (state.flipperHeldById[el.id]) {
        const heldType = String(el.icon || el.type || "").toLowerCase();
        if (heldType === "flipper-left") {
          node.classList.add("is-flip-left-held", "is-flip-held-lowpower");
        } else if (heldType === "flipper-right") {
          node.classList.add("is-flip-right-held", "is-flip-held-lowpower");
        }
      }
      node.addEventListener("mousedown", (evt) => startDrag(evt, el));
      node.addEventListener("contextmenu", (evt) => {
        evt.preventDefault();
        showContextMenu(el, evt.clientX, evt.clientY);
      });
      node.addEventListener("click", (evt) => {
        evt.stopPropagation();
        select(el);
      });
      node.addEventListener("dblclick", (evt) => { evt.stopPropagation(); blink(el.id); });
      tableEl.appendChild(node);
      applySelectionBounds(node, el);
    });
  }

  function applySelectionBounds(node, el) {
    if (!node) return;
    const svg = node.querySelector(".emu-svg");
    if (!svg || !tableEl) return;
    const svgRect = svg.getBoundingClientRect();
    if (!svgRect || !svgRect.width || !svgRect.height) return;
    const pad = Math.max(6, Math.round(10 * tableVisualScale())); // +5px each side at base scale
    node.style.setProperty("--emu-select-w", `${Math.ceil(svgRect.width + pad)}px`);
    node.style.setProperty("--emu-select-h", `${Math.ceil(svgRect.height + pad)}px`);
    const type = String(el?.icon || el?.type || "").toLowerCase();
    const roundTypes = new Set(["led", "rgb", "button", "bumper", "pop-bumper"]);
    let radius = "10px";
    if (roundTypes.has(type)) radius = "50%";
    else if (type === "coil") radius = "6px";
    else if (type === "target") radius = "8px";
    node.style.setProperty("--emu-select-radius", radius);
    node.style.setProperty("--emu-select-offset-x", "0px");
  }

  function renderOptions() {
    if (widthInput) widthInput.value = state.options.width;
    if (heightInput) heightInput.value = state.options.height;
    if (ratioEl) ratioEl.textContent = ratioText();
  }

  function toCssUrl(url) {
    return String(url || "").replace(/["\\]/g, "\\$&");
  }

  function normalizePlayfield(raw) {
    if (!raw || typeof raw !== "object") {
      return { name: "", updatedAt: "", url: "", fit: "cover", position: "center", opacity: 1 };
    }
    const name = String(raw.name || "").trim();
    const updatedAt = String(raw.updatedAt || "").trim();
    const url = String(raw.url || "").trim();
    const fitRaw = String(raw.fit || "").trim().toLowerCase();
    const fit = fitRaw === "contain" ? "contain" : (fitRaw === "exact" ? "exact" : "cover");
    const positionAllowed = new Set([
      "center", "top", "bottom", "left", "right",
      "top left", "top right", "bottom left", "bottom right",
    ]);
    const posRaw = String(raw.position || "").trim().toLowerCase();
    const position = positionAllowed.has(posRaw) ? posRaw : "center";
    let opacity = Number(raw.opacity);
    if (!Number.isFinite(opacity)) opacity = 1;
    if (opacity < 0) opacity = 0;
    if (opacity > 1) opacity = 1;
    return { name, updatedAt, url, fit, position, opacity };
  }

  function colorWithAlpha(color, alpha) {
    const c = String(color || "").trim();
    const m = c.match(/^rgba?\(([^)]+)\)$/i);
    if (!m) {
      return `rgba(0,0,0,${alpha})`;
    }
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
    if (!tableEl) return;
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

  function renderPlayfieldUi() {
    const hasPlayfieldUrl = !!(state.playfield && state.playfield.url);
    if (playfieldStatus) {
      if (state.playfield?.name) {
        playfieldStatus.textContent = `Using: ${state.playfield.name}`;
      } else {
        playfieldStatus.textContent = "No playfield image uploaded.";
      }
    }
    if (playfieldPreviewWrap && playfieldPreviewImg) {
      if (hasPlayfieldUrl) {
        playfieldPreviewImg.src = state.playfield.url;
        playfieldPreviewImg.alt = state.playfield?.name
          ? `Playfield image preview: ${state.playfield.name}`
          : "Playfield image preview";
        playfieldPreviewWrap.classList.remove("d-none");
      } else {
        playfieldPreviewImg.removeAttribute("src");
        playfieldPreviewImg.alt = "Playfield image preview";
        playfieldPreviewWrap.classList.add("d-none");
      }
    }
    if (playfieldFitSel) playfieldFitSel.value = state.playfield?.fit || "cover";
    if (playfieldPositionSel) playfieldPositionSel.value = state.playfield?.position || "center";
    if (playfieldOpacityInput) playfieldOpacityInput.value = String(state.playfield?.opacity ?? 1);
    if (playfieldOpacityValue) {
      const pct = Math.round((Number(state.playfield?.opacity ?? 1) || 0) * 100);
      playfieldOpacityValue.textContent = `${pct}%`;
    }
    if (playfieldRemoveBtn) {
      playfieldRemoveBtn.disabled = !hasPlayfieldUrl;
    }
  }

  function setPlayfield(raw) {
    state.playfield = normalizePlayfield(raw);
    applyPlayfieldBackground();
    renderPlayfieldUi();
  }

  function describeApiError(resp, body, fallback) {
    const code = String(body?.error || "").trim().toLowerCase();
    if (resp?.status === 401) return "Session expired. Please sign in again.";
    if (code === "file_required") return "Choose an image file first.";
    if (code === "unsupported_type") return "Unsupported image type. Use PNG, JPG, WEBP, GIF, or AVIF.";
    if (code === "empty_file") return "The selected image is empty.";
    if (code === "file_too_large") return "Image is too large (max 12MB).";
    if (code === "playfield_not_found") return "No uploaded playfield image found.";
    return fallback;
  }

  function askConfirm(message, opts = {}) {
    const fallback = () => Promise.resolve(window.confirm(message));
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();

    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!confirmBtn) return fallback();

    const title = opts.title || "Confirm";
    const label = opts.label || "Confirm";
    const btnClass = opts.confirmClass || "btn-primary";
    if (body) body.textContent = message;
    if (titleEl) titleEl.textContent = title;
    confirmBtn.textContent = label;
    confirmBtn.className = `btn ${btnClass}`;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        confirmBtn.removeEventListener("click", onConfirm);
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
      };
      const onConfirm = () => {
        resolved = true;
        cleanup();
        resolve(true);
        modal.hide();
      };
      const onHidden = () => {
        if (resolved) return;
        cleanup();
        resolve(false);
      };
      confirmBtn.addEventListener("click", onConfirm, { once: true });
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      modal.show();
    });
  }

  function confirmLeaveWithUnsaved() {
    return askConfirm("You have unsaved changes. Leave this page?", {
      title: "Unsaved Changes",
      label: "Leave",
      confirmClass: "btn-warning",
    });
  }

  async function savePlayfieldOptions() {
    const rawFit = String(playfieldFitSel?.value || "").trim().toLowerCase();
    const fit = rawFit === "contain" ? "contain" : (rawFit === "exact" ? "exact" : "cover");
    const position = String(playfieldPositionSel?.value || "center").trim().toLowerCase();
    let opacity = Number(playfieldOpacityInput?.value ?? state.playfield?.opacity ?? 1);
    if (!Number.isFinite(opacity)) opacity = 1;
    opacity = Math.max(0, Math.min(1, opacity));
    state.playfield.fit = fit;
    state.playfield.position = position || "center";
    state.playfield.opacity = opacity;
    applyPlayfieldBackground();
    renderPlayfieldUi();
    if (!state.playfield?.url) return true;
    if (playfieldFitSel) playfieldFitSel.disabled = true;
    if (playfieldPositionSel) playfieldPositionSel.disabled = true;
    try {
      const r = await fetch("/api/playfield/image/options", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ fit, position, opacity }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(describeApiError(r, j, "Failed to save playfield image settings."));
      setPlayfield(j.playfield);
      return true;
    } catch (e) {
      console.error(e);
      alert(e?.message || "Failed to save playfield image settings.");
      return false;
    } finally {
      if (playfieldFitSel) playfieldFitSel.disabled = false;
      if (playfieldPositionSel) playfieldPositionSel.disabled = false;
    }
  }

  async function uploadPlayfield() {
    const file = playfieldFileInput?.files?.[0];
    if (!file) {
      alert("Choose an image file first.");
      return;
    }
    if (playfieldUploadBtn) playfieldUploadBtn.disabled = true;
    if (playfieldRemoveBtn) playfieldRemoveBtn.disabled = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch("/api/playfield/image", {
        method: "POST",
        credentials: "same-origin",
        body: form,
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(describeApiError(r, j, "Playfield upload failed."));
      setPlayfield(j.playfield);
      await savePlayfieldOptions();
      if (playfieldFileInput) playfieldFileInput.value = "";
    } catch (e) {
      console.error(e);
      alert(e?.message || "Playfield upload failed.");
    } finally {
      if (playfieldUploadBtn) playfieldUploadBtn.disabled = false;
      renderPlayfieldUi();
    }
  }

  async function removePlayfield() {
    if (!state.playfield?.url) return;
    const ok = await askConfirm("Remove playfield image?", {
      title: "Remove Playfield",
      label: "Remove",
      confirmClass: "btn-danger",
    });
    if (!ok) return;
    if (playfieldUploadBtn) playfieldUploadBtn.disabled = true;
    if (playfieldRemoveBtn) playfieldRemoveBtn.disabled = true;
    try {
      const r = await fetch("/api/playfield/image", { method: "DELETE", credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(describeApiError(r, j, "Failed to remove playfield image."));
      setPlayfield(null);
      if (playfieldFileInput) playfieldFileInput.value = "";
    } catch (e) {
      console.error(e);
      alert(e?.message || "Failed to remove playfield image.");
    } finally {
      if (playfieldUploadBtn) playfieldUploadBtn.disabled = false;
      renderPlayfieldUi();
    }
  }

  function renderComponents() {
    const linkPalette = ["#22c55e", "#f59e0b", "#06b6d4", "#a78bfa", "#f43f5e", "#84cc16", "#fb7185", "#38bdf8"];
    const linkedByHardware = {};
    const byId = Object.create(null);
    allHardwareComponents().forEach((c) => {
      if (c && c.id) byId[c.id] = c;
    });
    const pairs = Array.isArray(state.ruleLinkedPairs) ? state.ruleLinkedPairs : [];
    const normPairs = pairs
      .filter((p) => p && p.a && p.b)
      .map((p) => [String(p.a), String(p.b)].sort())
      .sort((x, y) => (x[0] + "|" + x[1]).localeCompare(y[0] + "|" + y[1]));
    normPairs.forEach((pair, idx) => {
      const a = byId[pair[0]];
      const b = byId[pair[1]];
      const aClass = String((a && a.deviceClass) || "").toLowerCase();
      const bClass = String((b && b.deviceClass) || "").toLowerCase();
      const isGroupable =
        (aClass === "button" && (bClass === "coil" || bClass === "solenoid")) ||
        (bClass === "button" && (aClass === "coil" || aClass === "solenoid"));
      if (!isGroupable) return;
      const color = linkPalette[idx % linkPalette.length];
      const gid = `${pair[0]}|${pair[1]}`;
      linkedByHardware[pair[0]] = { gid, color };
      linkedByHardware[pair[1]] = { gid, color };
    });

    const sections = [
      { wrap: buttonsWrap, list: state.components.buttons, type: "button", empty: "None", selectable: true, hideWhenEmpty: false },
      { wrap: ledsWrap, list: state.components.leds, type: "led", empty: "", selectable: false, hideWhenEmpty: true },
      { wrap: solenoidsWrap, list: state.components.solenoids, type: "other", empty: "None", selectable: true, hideWhenEmpty: false },
      { wrap: otherWrap, list: state.components.other, type: "other", empty: "", selectable: true, hideWhenEmpty: true },
    ];
    sections.forEach(({ wrap, list, type, empty, selectable, hideWhenEmpty }) => {
      if (!wrap) return;
      const heading = wrap.previousElementSibling;
      wrap.classList.remove("d-none");
      heading?.classList.remove("d-none");
      wrap.innerHTML = "";
      if (!list || list.length === 0) {
        if (hideWhenEmpty) {
          wrap.classList.add("d-none");
          heading?.classList.add("d-none");
          return;
        }
        if (empty) {
          const m = document.createElement("div");
          m.className = "emu-muted";
          m.textContent = empty;
          wrap.appendChild(m);
        }
        return;
      }
      list.forEach((c) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "emu-chip";
        if (!selectable) {
          btn.disabled = true;
          btn.classList.add("is-faded");
          btn.title = "LED hardware is managed in Lighting";
        }
        if (isHardwareInUse(c)) btn.classList.add("is-faded");
        const linked = c && c.id ? linkedByHardware[c.id] : null;
        if (linked) {
          btn.classList.add("is-linked");
          btn.style.setProperty("--emu-link-color", linked.color);
        }
        const label = document.createElement("span");
        label.className = "emu-chip-label";
        label.textContent = c.friendly || c.id;
        btn.appendChild(label);
        if (linked) {
          const link = document.createElement("span");
          link.className = "emu-chip-link";
          link.title = "Linked component group";
          link.setAttribute("aria-label", "Linked component group");
          link.innerHTML = '<i class="fa fa-link" aria-hidden="true"></i>';
          btn.appendChild(link);
        }
        if (selectable) btn.addEventListener("click", () => addFromHardware(c, type));
        wrap.appendChild(btn);
      });
    });
    if (hwStatus) {
      hwStatus.textContent = state.hardwareLoaded ? "" : "Loading hardware…";
      hwStatus.classList.toggle("emu-muted", !!hwStatus.textContent);
    }
  }

  function renderSelection() {
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el) {
      noSel.classList.remove("d-none");
      settings.classList.add("d-none");
      if (selectedLabel) selectedLabel.textContent = "Component Inspector";
      boundWrap.classList.add("d-none");
      if (eventsWrap) eventsWrap.innerHTML = "";
      if (eventsTitle) eventsTitle.classList.add("d-none");
      renderTable();
      return;
    }
    noSel.classList.add("d-none");
    settings.classList.remove("d-none");
    setAccordionExpanded("keys", true);
    selectedLabel.textContent = el.label || el.id;
    const appearance = String(el.icon || el.type || "button");
    if ([...appearanceSel.options].some((o) => o.value === appearance)) {
      appearanceSel.value = appearance;
    } else {
      appearanceSel.value = "button";
    }
    colorInput.value = el.color || "#60a5fa";
    if (sizeScaleInput) sizeScaleInput.value = String(Number(el.scale) || 1);
    renderScaleValue(el.scale);
    if (rotationInput) rotationInput.value = String(Math.round(Number(el.rotation) || 0));
    renderRotationValue(el.rotation);
    renderLinkedInfo(el);
    const keyBindable = canBindKeys(el);
    if (bindRow) bindRow.classList.toggle("d-none", !keyBindable);
    if (captureBtn) captureBtn.classList.toggle("d-none", !keyBindable);
    if (!keyBindable) endKeyCapture();
    const bound = boundKeysForSelected();
    boundWrap.classList.toggle("d-none", !keyBindable);
    boundKeys.innerHTML = "";
    bound.forEach((k) => {
      const row = document.createElement("div");
      row.className = "emu-key-row";
      const chip = document.createElement("span");
      chip.className = "emu-chip is-static";
      chip.innerHTML = `<span class="emu-chip-label">${k}</span>`;
      const x = document.createElement("button");
      x.className = "emu-chip-x";
      x.type = "button";
      x.textContent = "×";
      x.title = "Unbind";
      x.addEventListener("click", () => { unbind(k); renderSelection(); });
      chip.appendChild(x);

      const selectDown = document.createElement("select");
      selectDown.className = "form-select form-select-sm";
      selectDown.title = "Key down gesture";
      const selectUp = document.createElement("select");
      selectUp.className = "form-select form-select-sm";
      selectUp.title = "Key up gesture";
      const gestureList = gesturesForElement(el);
      const noneDown = document.createElement("option");
      noneDown.value = "";
      noneDown.textContent = "None";
      selectDown.appendChild(noneDown);
      const noneUp = document.createElement("option");
      noneUp.value = "";
      noneUp.textContent = "None";
      selectUp.appendChild(noneUp);
      gestureList.forEach((meta) => {
        const optDown = document.createElement("option");
        optDown.value = meta.key;
        optDown.textContent = meta.key;
        selectDown.appendChild(optDown);
        const optUp = document.createElement("option");
        optUp.value = meta.key;
        optUp.textContent = meta.key;
        selectUp.appendChild(optUp);
      });
      const existing = normalizeKeymapEntry(state.keymap[k]) || {};
      const down = existing.keyDownGesture || "";
      const up = existing.keyUpGesture || "";
      selectDown.value = gestureList.some((m) => m.key === down) ? down : "";
      selectUp.value = gestureList.some((m) => m.key === up) ? up : "";
      const updateBinding = () => {
        state.keymap[k] = {
          id: el.id,
          keyDownGesture: selectDown.value || "",
          keyUpGesture: selectUp.value || "",
        };
        markDirty();
      };
      selectDown.addEventListener("change", updateBinding);
      selectUp.addEventListener("change", updateBinding);

      const keyLine = document.createElement("div");
      keyLine.className = "emu-key-line";
      const keyLabel = document.createElement("span");
      keyLabel.className = "emu-key-line-label";
      keyLabel.textContent = "Keyboard Shortcut";
      const keyValue = document.createElement("div");
      keyValue.className = "emu-key-line-value";
      keyValue.appendChild(chip);
      keyLine.appendChild(keyLabel);
      keyLine.appendChild(keyValue);
      row.appendChild(keyLine);

      const downLine = document.createElement("div");
      downLine.className = "emu-key-line";
      const downLabel = document.createElement("span");
      downLabel.className = "emu-key-line-label";
      downLabel.textContent = "Down";
      const downValue = document.createElement("div");
      downValue.className = "emu-key-line-value";
      downValue.appendChild(selectDown);
      downLine.appendChild(downLabel);
      downLine.appendChild(downValue);
      row.appendChild(downLine);

      const upLine = document.createElement("div");
      upLine.className = "emu-key-line";
      const upLabel = document.createElement("span");
      upLabel.className = "emu-key-line-label";
      upLabel.textContent = "Up";
      const upValue = document.createElement("div");
      upValue.className = "emu-key-line-value";
      upValue.appendChild(selectUp);
      upLine.appendChild(upLabel);
      upLine.appendChild(upValue);
      row.appendChild(upLine);
      boundKeys.appendChild(row);
    });
    renderEventsSection(el);
    renderTable();
  }

  function renderLinkedInfo(el) {
    if (!linkRow || !linkInfo) return;
    if (!el || !el.linkGroup) {
      linkRow.classList.add("d-none");
      linkInfo.textContent = "-";
      unlinkBtn?.classList.add("d-none");
      return;
    }
    const peers = state.elements.filter((p) => p && p.id !== el.id && p.linkGroup === el.linkGroup);
    if (!peers.length) {
      linkRow.classList.add("d-none");
      linkInfo.textContent = "-";
      unlinkBtn?.classList.add("d-none");
      return;
    }
    linkInfo.innerHTML = "";
    peers.forEach((p, idx) => {
      if (idx > 0) {
        const sep = document.createElement("span");
        sep.textContent = ", ";
        linkInfo.appendChild(sep);
      }
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "emu-link-jump";
      jump.textContent = p.label || p.hardwareId || p.id;
      jump.title = "Select linked component";
      jump.addEventListener("click", () => {
        select(p);
        blink(p.id);
      });
      linkInfo.appendChild(jump);
    });
    unlinkBtn?.classList.remove("d-none");
    linkRow.classList.remove("d-none");
  }

  function isPairManuallyBroken(srcId, dstId) {
    if (!srcId || !dstId) return false;
    const isSrc = (el) => (el.hardwareId === srcId || el.id === srcId);
    const isDst = (el) => (el.hardwareId === dstId || el.id === dstId);
    const srcEl = state.elements.find((el) => el && isSrc(el));
    const dstEl = state.elements.find((el) => el && isDst(el));
    return !!(srcEl?.linkManualBreak || dstEl?.linkManualBreak);
  }

  function unlinkSelectedGroup() {
    const selected = state.elements.find((e) => e.id === state.selectedId);
    if (!selected || !selected.linkGroup) return;
    const group = String(selected.linkGroup || "");
    state.elements.forEach((el) => {
      if (!el || String(el.linkGroup || "") !== group) return;
      el.linkManualBreak = true;
      delete el.linkAuto;
      delete el.linkGroup;
      delete el.linkRole;
      delete el.linkMove;
    });
    markDirty();
    renderSelection();
    renderTable();
    renderComponents();
  }

  function boundKeysForSelected() {
    const out = [];
    Object.entries(state.keymap || {}).forEach(([k, v]) => {
      const entry = normalizeKeymapEntry(v);
      if (entry && entry.id === state.selectedId) out.push(k);
    });
    return out;
  }

  function normalizeKeymapEntry(v) {
    if (!v) return null;
    if (typeof v === "string") {
      return { id: v, keyDownGesture: "PRESSED", keyUpGesture: "RELEASED" };
    }
    if (typeof v !== "object") return null;
    const id = v.id || "";
    if (!id) return null;
    if (v.keyDownGesture !== undefined || v.keyUpGesture !== undefined) {
      return {
        id,
        keyDownGesture: v.keyDownGesture || "",
        keyUpGesture: v.keyUpGesture || "",
      };
    }
    if (v.gesture) {
      if (v.gesture === "RELEASED") return { id, keyDownGesture: "", keyUpGesture: "RELEASED" };
      if (v.gesture === "PRESSED") return { id, keyDownGesture: "PRESSED", keyUpGesture: "RELEASED" };
      return { id, keyDownGesture: v.gesture, keyUpGesture: "" };
    }
    return { id, keyDownGesture: "PRESSED", keyUpGesture: "RELEASED" };
  }

  function isHardwareInUse(c) {
    if (!c || !c.id) return false;
    const id = c.id;
    return state.elements.some((e) => {
      if (e.hardwareId) return e.hardwareId === id;
      if (e.id === id) return true;
      return e.id && id && e.id.indexOf(id + "-") === 0;
    });
  }

  function hardwareById(id) {
    if (!id) return null;
    const all = allHardwareComponents();
    return all.find((c) => c.id === id) || null;
  }

  function allHardwareComponents() {
    return state.components.buttons
      .concat(state.components.leds)
      .concat(state.components.solenoids || [])
      .concat(state.components.other);
  }

  function classifyHardwareType(c) {
    const dclass = String((c && c.deviceClass) || "").toLowerCase();
    if (dclass === "button") return "button";
    if (dclass === "led" || dclass === "rgb") return "other";
    return "other";
  }

  function linkedPartnerHardwareId(hardwareId) {
    if (!hardwareId) return "";
    const pairs = Array.isArray(state.ruleLinkedPairs) ? state.ruleLinkedPairs : [];
    for (const pair of pairs) {
      if (!pair) continue;
      if (pair.a === hardwareId) return pair.b || "";
      if (pair.b === hardwareId) return pair.a || "";
    }
    return "";
  }

  function makeElementFromHardware(c, type, opts) {
    const seed = c && c.id ? c.id : Math.random().toString(36).slice(2);
    const base = {
      id: seed,
      type: type,
      hardwareId: c && c.id ? c.id : null,
      label: c && (c.friendly || c.id) ? (c.friendly || c.id) : seed,
      deviceClass: c && c.deviceClass ? c.deviceClass : null,
      nx: (opts && Number.isFinite(opts.nx)) ? opts.nx : 0.5,
      ny: (opts && Number.isFinite(opts.ny)) ? opts.ny : 0.5,
      x: (opts && Number.isFinite(opts.x)) ? opts.x : state.tableRect.width / 2,
      y: (opts && Number.isFinite(opts.y)) ? opts.y : state.tableRect.height / 2,
      icon: type || "button",
      color: "#60a5fa",
      size: "m",
      scale: 1,
      rotation: 0,
    };
    const cClass = String((c && c.deviceClass) || "").toLowerCase();
    if (cClass === "coil" || cClass === "solenoid") {
      base.icon = "coil";
    } else if (cClass === "led") {
      base.icon = "led";
    } else if (cClass === "rgb") {
      base.icon = "rgb";
    } else if (cClass === "button") {
      base.icon = "button";
    }
    if (
      c &&
      c.friendly &&
      String(c.friendly).toLowerCase().includes("pop bumper") &&
      (cClass === "coil" || cClass === "solenoid")
    ) {
      base.icon = "pop-bumper";
      base.size = "m";
    }
    let uniqueId = seed;
    let i = 2;
    while (state.elements.some((e) => e.id === uniqueId)) uniqueId = `${seed}-${i++}`;
    base.id = uniqueId;
    return base;
  }

  function getLinkedElements(el) {
    if (!el || !el.linkGroup || el.linkMove === false) return [];
    return state.elements.filter((e) => e && e.id !== el.id && e.linkGroup === el.linkGroup && e.linkMove !== false);
  }

  function clampElementPosition(el, x, y) {
    const w = state.tableRect.width;
    const h = state.tableRect.height;
    let nx = x;
    let ny = y;
    const node = tableEl?.querySelector(`.emu-el[data-id="${el.id}"]`);
    const svg = node?.querySelector(".emu-svg");
    const rect = svg?.getBoundingClientRect();
    const elW = rect?.width || 0;
    const elH = rect?.height || 0;
    const minX = -PAD + elW / 2;
    const minY = -PAD + elH / 2;
    const maxX = w + PAD - elW / 2;
    const maxY = h + PAD - elH / 2;
    if (nx < minX) nx = minX;
    if (ny < minY) ny = minY;
    if (nx > maxX) nx = maxX;
    if (ny > maxY) ny = maxY;
    return { x: nx, y: ny };
  }

  function addFromHardware(c, type) {
    if (type === "led" || type === "rgb") return;
    if (isHardwareInUse(c)) {
      const existing = state.elements.find((e) => (e.hardwareId === c.id) || e.id === c.id || (c.id && e.id && e.id.indexOf(c.id + "-") === 0));
      if (existing) {
        select(existing);
        blink(existing.id);
      }
      return;
    }
    const centerX = state.tableRect.width / 2;
    const centerY = state.tableRect.height / 2;
    const base = makeElementFromHardware(c, type, { x: centerX, y: centerY, nx: 0.5, ny: 0.5 });

    // If rules link this hardware to a partner (eg pop-bumper button+coil),
    // auto-place both together so they stay attached from first add.
    const partnerId = linkedPartnerHardwareId(c && c.id);
    const partnerHw = hardwareById(partnerId);
    const partnerMissing = partnerHw && !isHardwareInUse(partnerHw);
    if (partnerMissing) {
      const partnerType = classifyHardwareType(partnerHw);
      const partner = makeElementFromHardware(partnerHw, partnerType, { x: centerX, y: centerY, nx: 0.5, ny: 0.5 });
      const baseClass = String((c && c.deviceClass) || "").toLowerCase();
      const partnerClass = String((partnerHw && partnerHw.deviceClass) || "").toLowerCase();
      const baseIsTrigger = baseClass === "button";
      const partnerIsTrigger = partnerClass === "button";
      if (baseIsTrigger && !partnerIsTrigger) {
        state.elements.push(partner);
        state.elements.push(base);
      } else if (!baseIsTrigger && partnerIsTrigger) {
        state.elements.push(base);
        state.elements.push(partner);
      } else {
        state.elements.push(base);
        state.elements.push(partner);
      }
    } else {
      state.elements.push(base);
    }
    applyRuleLinkGroups();
    select(base);
    markDirty();
    renderTable();
    if (state.selectedId) renderSelection();
    renderComponents();
  }

  function select(el) {
    state.selectedId = el && el.id ? el.id : null;
    if (el) {
      appearanceSel.value = el.icon || el.type || "button";
      colorInput.value = el.color || "#60a5fa";
    }
    renderSelection();
  }

  function clearSelection() {
    state.selectedId = null;
    endKeyCapture();
    renderSelection();
  }

  function startDrag(evt, el) {
    if (!evt || evt.button !== 0) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    const node = tableEl.querySelector(`.emu-el[data-id="${el.id}"]`);
    const svg = node ? node.querySelector(".emu-svg") : null;
    const box = (svg && svg.getBoundingClientRect) ? svg.getBoundingClientRect()
      : (node && node.getBoundingClientRect ? node.getBoundingClientRect() : { width: 0, height: 0 });
    const rect = tableEl.getBoundingClientRect();
    const cs = getComputedStyle(tableEl);
    const bl = parseFloat(cs.borderLeftWidth) || 0;
    const bt = parseFloat(cs.borderTopWidth) || 0;
    const x = evt.clientX - rect.left - bl;
    const y = evt.clientY - rect.top - bt;
    // Select immediately on pointer-down so simple clicks feel responsive.
    select(el);
    state.dragging = null;
    state.dragPending = {
      el,
      linked: getLinkedElements(el),
      startX: evt.clientX,
      startY: evt.clientY,
      startedAt: Date.now(),
      offsetX: x - el.x,
      offsetY: y - el.y,
      elW: box.width || 0,
      elH: box.height || 0,
    };
  }

  function onMouseMove(evt) {
    if (!state.dragging && state.dragPending) {
      const dx = (evt.clientX || 0) - state.dragPending.startX;
      const dy = (evt.clientY || 0) - state.dragPending.startY;
      const dist = Math.hypot(dx, dy);
      if (dist < DRAG_START_DISTANCE_PX) return;
      state.dragging = state.dragPending;
      state.dragPending = null;
    }
    if (!state.dragging) return;
    const rect = tableEl.getBoundingClientRect();
    const cs = getComputedStyle(tableEl);
    const bl = parseFloat(cs.borderLeftWidth) || 0;
    const bt = parseFloat(cs.borderTopWidth) || 0;
    const w = state.tableRect.width;
    const h = state.tableRect.height;
    let x = evt.clientX - rect.left - bl - state.dragging.offsetX;
    let y = evt.clientY - rect.top - bt - state.dragging.offsetY;
    const elW = state.dragging.elW;
    const elH = state.dragging.elH;
    const minX = -PAD + elW / 2;
    const minY = -PAD + elH / 2;
    const maxX = w + PAD - elW / 2;
    const maxY = h + PAD - elH / 2;
    if (x < minX) x = minX;
    if (y < minY) y = minY;
    if (x > maxX) x = maxX;
    if (y > maxY) y = maxY;
    const snapVal = (v) => {
      const dpr = window.devicePixelRatio || 1;
      return Math.round(v * dpr) / dpr;
    };
    x = snapVal(x);
    y = snapVal(y);
    const primary = state.dragging.el;
    const prevX = primary.x;
    const prevY = primary.y;
    const p = clampElementPosition(primary, x, y);
    primary.x = p.x;
    primary.y = p.y;
    if (w > 0) primary.nx = primary.x / w;
    if (h > 0) primary.ny = primary.y / h;
    const dx = primary.x - prevX;
    const dy = primary.y - prevY;
    if (dx !== 0 || dy !== 0) {
      (state.dragging.linked || []).forEach((peer) => {
        const n = clampElementPosition(peer, (peer.x || 0) + dx, (peer.y || 0) + dy);
        peer.x = n.x;
        peer.y = n.y;
        if (w > 0) peer.nx = peer.x / w;
        if (h > 0) peer.ny = peer.y / h;
      });
    }
    markDirty();
    renderTable();
  }

  function onMouseUp() {
    state.dragPending = null;
    state.dragging = null;
  }

  function onKeyDown(evt) {
    if (shouldIgnoreKeyEvent(evt)) return;
    const key = normalizeKey(evt && evt.key);
    if (state.waitingForKey) {
      if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
      if (key === "escape") {
        endKeyCapture();
        return;
      }
      bindCapturedKey(key);
      return;
    }
    if (isArrowNudgeKey(key) && state.selectedId) {
      if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
      if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
      delete state.activeKeyPresses[key];
      nudgeSelectedByArrowKey(key);
      return;
    }
    const entry = normalizeKeymapEntry(state.keymap[key]);
    if (!entry) return;
    const id = entry.id;
    const downGesture = entry.keyDownGesture || "";
    const upGesture = entry.keyUpGesture || "";
    const el = state.elements.find((e) => e.id === id);
    if (!el) return;
    if (!canBindKeys(el)) return;
    if (!downGesture && !upGesture) return;
    if (state.activeKeyPresses[key]) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    state.activeKeyPresses[key] = true;
    dbg("KEY_DOWN", { key, id, downGesture, upGesture });
    if (downGesture) {
      fireBoundEvent(el, downGesture);
    }
  }

  function onKeyUp(evt) {
    if (shouldIgnoreKeyEvent(evt)) return;
    const key = normalizeKey(evt && evt.key);
    if (isArrowNudgeKey(key) && state.selectedId) {
      if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
      if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
      delete state.activeKeyPresses[key];
      return;
    }
    const entry = normalizeKeymapEntry(state.keymap[key]);
    if (!entry) return;
    const id = entry.id;
    const upGesture = entry.keyUpGesture || "";
    const el = state.elements.find((e) => e.id === id);
    if (!el) return;
    if (!canBindKeys(el)) return;
    const hadPress = !!state.activeKeyPresses[key];
    delete state.activeKeyPresses[key];
    if (!hadPress) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    dbg("KEY_UP", { key, id, upGesture });
    if (upGesture) {
      fireBoundEvent(el, upGesture);
    }
  }

  function shouldIgnoreKeyEvent(evt) {
    const ae = (evt && evt.target) || document.activeElement;
    if (!ae || !ae.tagName) return false;
    const tag = String(ae.tagName).toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    if (ae.isContentEditable) return true;
    return false;
  }

  function isArrowNudgeKey(key) {
    return key === "arrowup" || key === "arrowdown" || key === "arrowleft" || key === "arrowright";
  }

  function nudgeSelectedByArrowKey(key) {
    if (!state.selectedId) return false;
    const selected = state.elements.find((e) => e && e.id === state.selectedId);
    if (!selected) return false;
    let dx = 0;
    let dy = 0;
    if (key === "arrowleft") dx = -1;
    else if (key === "arrowright") dx = 1;
    else if (key === "arrowup") dy = -1;
    else if (key === "arrowdown") dy = 1;
    else return false;

    const w = state.tableRect.width || 1;
    const h = state.tableRect.height || 1;
    const prevX = Number(selected.x || 0);
    const prevY = Number(selected.y || 0);
    const next = clampElementPosition(selected, prevX + dx, prevY + dy);
    selected.x = next.x;
    selected.y = next.y;
    if (w > 0) selected.nx = selected.x / w;
    if (h > 0) selected.ny = selected.y / h;
    const movedX = selected.x - prevX;
    const movedY = selected.y - prevY;

    if (movedX !== 0 || movedY !== 0) {
      const peers = getLinkedElements(selected);
      peers.forEach((peer) => {
        const px = Number(peer.x || 0);
        const py = Number(peer.y || 0);
        const pn = clampElementPosition(peer, px + movedX, py + movedY);
        peer.x = pn.x;
        peer.y = pn.y;
        if (w > 0) peer.nx = peer.x / w;
        if (h > 0) peer.ny = peer.y / h;
      });
      markDirty();
      renderTable();
    }
    return true;
  }

  function normalizeKey(k) {
    if (!k) return "";
    k = String(k).toLowerCase();
    if (k === " " || k === "spacebar") return " ";
    if (["arrowup", "arrowdown", "arrowleft", "arrowright"].includes(k)) return k;
    return k;
  }

  function captureKey(evt) {
    if (!state.selectedId) return;
    const selected = state.elements.find((e) => e.id === state.selectedId);
    if (!selected || !canBindKeys(selected)) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    state.waitingForKey = true;
    if (state.captureKeyListener) {
      document.removeEventListener("keydown", state.captureKeyListener, true);
    }
    state.captureKeyListener = (e) => {
      if (!state.waitingForKey) return;
      const key = normalizeKey(e && e.key);
      if (!key) return;
      if (typeof e.preventDefault === "function") e.preventDefault();
      if (typeof e.stopPropagation === "function") e.stopPropagation();
      if (key === "escape") {
        endKeyCapture();
        return;
      }
      bindCapturedKey(key);
    };
    document.addEventListener("keydown", state.captureKeyListener, true);
    const btns = [];
    if (evt && evt.target && evt.target.closest) {
      const hit = evt.target.closest("[data-capture]");
      if (hit) btns.push(hit);
    }
    const fallbacks = document.querySelectorAll("[data-capture]");
    fallbacks.forEach((b) => { if (!btns.includes(b)) btns.push(b); });
    startCaptureAnim(btns);
  }

  function startCaptureAnim(list) {
    stopCaptureAnim();
    if (!list || !list.length) return;
    state._capBtnList = list;
    list.forEach((b) => {
      if (!b.dataset.captureLabel) {
        b.dataset.captureLabel = b.textContent || "";
      }
      b.textContent = "Press key...";
      b.classList.add("emu-capture-pulse");
      b.setAttribute("aria-busy", "true");
    });
  }
  function stopCaptureAnim() {
    if (!state._capBtnList) return;
    state._capBtnList.forEach((b) => {
      if (b.dataset.captureLabel !== undefined) {
        b.textContent = b.dataset.captureLabel;
      }
      b.classList.remove("emu-capture-pulse");
      b.removeAttribute("aria-busy");
    });
    state._capBtnList = null;
  }

  function endKeyCapture() {
    state.waitingForKey = false;
    if (state.captureKeyListener) {
      document.removeEventListener("keydown", state.captureKeyListener, true);
      state.captureKeyListener = null;
    }
    stopCaptureAnim();
  }

  function bindCapturedKey(key) {
    if (!state.selectedId) {
      endKeyCapture();
      return;
    }
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el || !canBindKeys(el)) {
      endKeyCapture();
      return;
    }
    const gestureList = el ? gesturesForElement(el) : [];
    const gestureKeys = gestureList.map((g) => g.key);
    const down = gestureKeys.includes("PRESSED") ? "PRESSED" : (gestureKeys[0] || "");
    const up = gestureKeys.includes("RELEASED") ? "RELEASED" : "";
    state.keymap[key] = { id: state.selectedId, keyDownGesture: down, keyUpGesture: up };
    markDirty();
    blink(state.selectedId);
    endKeyCapture();
    renderSelection();
  }

  function unbind(k) {
    if (k && (k in state.keymap)) { delete state.keymap[k]; markDirty(); }
  }

  function blink(id) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.add("blink");
    setTimeout(() => node.classList.remove("blink"), 180);
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

  function pulsePopBumper(id) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    node.classList.remove("is-pop-bumper-fired");
    void node.offsetWidth;
    node.classList.add("is-pop-bumper-fired");
    setTimeout(() => node.classList.remove("is-pop-bumper-fired"), 280);
  }

  function isLedLike(el) {
    const type = (el?.icon || el?.type || "").toLowerCase();
    return type === "led" || type === "rgb";
  }

  function isPopBumperElement(el) {
    if (!el) return false;
    const kind = String(el.icon || el.type || "").toLowerCase();
    if (kind === "pop-bumper") return true;
    if (kind === "button") return false;
    const label = String(el.label || "").toLowerCase();
    const dclass = String(el.deviceClass || "").toLowerCase();
    if (dclass && dclass !== "coil" && dclass !== "solenoid") return false;
    if (label.includes("pop bumper") || label.includes("bumper")) return true;
    return false;
  }

  function normalizeSpecialElementAppearance(el) {
    if (!el) return;
    if (!isPopBumperElement(el)) return;
    el.icon = "pop-bumper";
    if (!el.size) {
      el.size = state.defaultSizeForType["pop-bumper"] || "xl";
    }
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
      ["_REPEAT_WHILE_HELD", "REPEAT_WHILE_HELD"],
      ["_HELD", "HELD"],
      ["_CLICKED", "CLICKED"],
      ["_PRESSED", "PRESSED"],
      ["_RELEASED", "RELEASED"],
      ["_CLOSED", "CLOSED"],
      ["_OPENED", "OPENED"],
      ["_CHANGED", "CHANGED"],
    ];
    for (const [suffix, fn] of suffixMap) {
      if (n.endsWith(suffix)) return fn;
    }
    return null;
  }

  function triggerRuleActionAnimations(ev) {
    if (!ev) return;
    const source = (ev.source || "").trim();
    if (!source) return;
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
    // Only use source+event fallback matching when no explicit gesture is present.
    // Otherwise PRESSED/RELEASED rules sharing the same event name can cross-fire.
    if (!gesture) {
      const byEvent = state.ruleActionsBySourceEvent[`${source}|${ev.name}`] || [];
      byEvent.forEach((entry) => {
        const k = `${entry.target}|${entry.type}|${JSON.stringify(entry.params || {})}`;
        if (seen.has(k)) return;
        seen.add(k);
        out.push(entry);
      });
    }

    // When a flipper event includes both pulse and set_output(HIGH) on the
    // same target, treat it as one intent: flip then hold. Do not run a second
    // pulse animation for the same event.
    const holdTargets = new Set();
    const holdFlipperDirs = new Set();
    out.forEach((entry) => {
      if (entry.type !== "set_output") return;
      if (!entry.target) return;
      if (!setOutputIsActiveForTarget(entry.target, null, entry.params || {})) return;
      holdTargets.add(String(entry.target));
      const holdDir = inferFlipperDirectionHint(entry.target, entry.dir || null);
      if (holdDir === "left" || holdDir === "right") holdFlipperDirs.add(holdDir);
    });

    const filtered = out.filter((entry) => {
      if (entry.type !== "pulse") return true;
      if (!entry.target) return true;
      if (holdTargets.has(String(entry.target))) return false;
      const pulseDir = inferFlipperDirectionHint(entry.target, entry.dir || null);
      if ((pulseDir === "left" || pulseDir === "right") && holdFlipperDirs.has(pulseDir)) {
        return false;
      }
      return true;
    });

    dbg("ANIM_MATCH", {
      source,
      name: ev.name,
      gesture: gesture || null,
      actionsMatched: out.map((e) => `${e.type}:${e.target || ""}`),
      actionsApplied: filtered.map((e) => `${e.type}:${e.target || ""}`),
    });

    filtered.forEach((entry) => animateRuleTarget(entry.target, entry.type, entry.params || {}, entry.dir || null));
    return filtered.length;
  }

  function inferFlipperDirectionHint(targetSource, hintDir) {
    if (hintDir === "left" || hintDir === "right") return hintDir;
    const raw = String(targetSource || "").toLowerCase();
    if (raw.includes("left")) return "left";
    if (raw.includes("right")) return "right";
    return null;
  }

  function animateRuleTarget(targetSource, actionType, actionParams, dirHint) {
    dbg("ANIM_APPLY", { targetSource, actionType, params: actionParams || {}, dirHint: dirHint || null });
    const visualAction = String(actionType || "").trim().toLowerCase();
    if (!["set_output", "pulse", "emit_event"].includes(visualAction)) {
      return;
    }
    const targetEl = state.elements.find((el) => el.hardwareId === targetSource || el.id === targetSource);
    const outputActive = setOutputIsActiveForTarget(targetSource, targetEl || null, actionParams || {});
    if (!targetEl) {
      const fallbackDir = inferFlipperDirectionHint(targetSource, dirHint);
      if (!fallbackDir) return;
      if (visualAction === "set_output") {
        if (outputActive) {
          kickFlipperByDirection(fallbackDir);
          setFlipperHeldByDirection(fallbackDir, true);
        } else {
          setFlipperHeldByDirection(fallbackDir, false);
        }
        return;
      }
      const fallbackEl = state.elements.find((el) => {
        const kind = (el.icon || el.type || "").toLowerCase();
        return (fallbackDir === "left" && kind === "flipper-left")
          || (fallbackDir === "right" && kind === "flipper-right");
      });
      if (!fallbackEl) return;
      flipElement(fallbackEl.id, fallbackDir, 100);
      return;
    }
    const kind = (targetEl.icon || targetEl.type || "").toLowerCase();
    if (kind === "flipper-left" || kind === "flipper-right") {
      if (visualAction === "set_output") {
        const dir = kind === "flipper-left" ? "left" : "right";
        if (outputActive) {
          kickFlipper(targetEl.id, dir);
          setFlipperHeld(targetEl.id, dir, true);
        } else {
          setFlipperHeld(targetEl.id, dir, false);
        }
        return;
      }
      // Playfield visual speed should be consistent on both flippers and not tied
      // to coil pulse timing values in rules.
      const durationMs = 110;
      flipElement(targetEl.id, kind === "flipper-left" ? "left" : "right", durationMs);
      return;
    }
    if (kind === "launch-plunger") {
      if (visualAction === "pulse") {
        pulseLaunchPlunger(targetEl.id);
        return;
      }
      if (visualAction === "set_output" && outputActive) {
        pulseLaunchPlunger(targetEl.id);
        return;
      }
    }
    if (isPopBumperElement(targetEl) || kind === "bumper") {
      if (visualAction === "pulse") {
        pulsePopBumper(targetEl.id);
        return;
      }
      if (visualAction === "set_output" && (outputActive || outputValueIsPulse(actionParams?.value))) {
        pulsePopBumper(targetEl.id);
        return;
      }
    }
    if (visualAction === "set_output" && isLedLike(targetEl)) {
      const isOn = outputActive;
      setOutputVisual(targetEl.id, isOn);
      return;
    }
    if (visualAction === "pulse" || visualAction === "set_output" || visualAction === "emit_event") {
      pulseElement(targetEl.id);
    }
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

  function flipToHoldElement(id, dir, durationMs) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-tohold" : "is-flip-left-tohold";
    node.classList.remove("is-flip-left-fired", "is-flip-right-fired", "is-flip-left-tohold", "is-flip-right-tohold");
    node.style.setProperty("--emu-flip-ms", `${Math.max(50, Math.min(220, durationMs || 95))}ms`);
    void node.offsetWidth;
    node.classList.add(cls);
    setTimeout(() => {
      node.classList.remove(cls);
      node.style.removeProperty("--emu-flip-ms");
    }, Math.max(70, durationMs || 95) + 20);
  }

  function setFlipperHeld(id, dir, isOn) {
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-held" : "is-flip-left-held";
    state.flipperHeldById[id] = !!isOn;
    node.classList.toggle(cls, !!isOn);
    node.classList.toggle("is-flip-held-lowpower", !!isOn);
  }

  function setFlipperHeldByDirection(dir, isOn) {
    if (dir !== "left" && dir !== "right") return;
    const selector = dir === "right"
      ? '.emu-el[data-type="flipper-right"]'
      : '.emu-el[data-type="flipper-left"]';
    const cls = dir === "right" ? "is-flip-right-held" : "is-flip-left-held";
    tableEl.querySelectorAll(selector).forEach((node) => {
      const nodeId = String(node?.dataset?.id || "");
      if (nodeId) state.flipperHeldById[nodeId] = !!isOn;
      node.classList.toggle(cls, !!isOn);
      node.classList.toggle("is-flip-held-lowpower", !!isOn);
    });
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

  function kickFlipperByDirection(dir) {
    if (dir !== "left" && dir !== "right") return;
    const selector = dir === "right"
      ? '.emu-el[data-type="flipper-right"]'
      : '.emu-el[data-type="flipper-left"]';
    const cls = dir === "right" ? "is-flip-right-kick" : "is-flip-left-kick";
    tableEl.querySelectorAll(selector).forEach((node) => {
      node.classList.remove("is-flip-left-kick", "is-flip-right-kick");
      void node.offsetWidth;
      node.classList.add(cls);
      setTimeout(() => node.classList.remove(cls), 95);
    });
  }

  function isButtonLike(el) {
    const type = (el.icon || el.type || "").toLowerCase();
    return ["button", "flipper-left", "flipper-right", "target"].includes(type);
  }

  function triggerElementEvent(el) {
    if (!el || !isButtonLike(el)) return;
    const bindings = (el.eventBindings || {});
    const pressed = bindings.PRESSED?.name || "";
    const released = bindings.RELEASED?.name || "";
    const clicked = bindings.CLICKED?.name || "";
    if (pressed) {
      fireBoundEvent(el, "PRESSED");
      if (released) {
        setTimeout(() => fireBoundEvent(el, "RELEASED"), 120);
      }
      return;
    }
    if (clicked) {
      fireBoundEvent(el, "CLICKED");
    }
  }

  function rememberEvent(id) {
    if (!id) return;
    const now = Date.now();
    state.recentEvents = state.recentEvents.filter((item) => now - item.at < 10000);
    state.recentEvents.push({ id, at: now });
  }

  function eventSignature(ev) {
    if (!ev) return "";
    const source = String(ev.source || "");
    const name = String(ev.name || "");
    const et = String(ev.params?.eventType || "");
    if (!source && !name) return "";
    return `${source}|${name}|${et}`;
  }

  function rememberAppliedSignature(sig, atMs) {
    if (!sig) return;
    const now = Number(atMs) || Date.now();
    state.recentAppliedBySigAt[sig] = now;
    const cutoff = now - 3000;
    Object.keys(state.recentAppliedBySigAt).forEach((k) => {
      if (Number(state.recentAppliedBySigAt[k] || 0) < cutoff) delete state.recentAppliedBySigAt[k];
    });
  }

  function isNearDuplicateSignature(sig, atMs) {
    if (!sig) return false;
    const now = Number(atMs) || Date.now();
    const prev = Number(state.recentAppliedBySigAt[sig] || 0);
    if (!prev) return false;
    // Ignore immediate echo duplicates to avoid double flipper flicker.
    return (now - prev) >= 0 && (now - prev) < 80;
  }

  function clearPendingHoldTimer(key) {
    if (!key) return;
    const timer = state.pendingHoldTimers[key];
    if (!timer) return;
    clearTimeout(timer);
    delete state.pendingHoldTimers[key];
  }

  function schedulePendingHoldTimer(key, fn, delayMs) {
    clearPendingHoldTimer(key);
    state.pendingHoldTimers[key] = setTimeout(() => {
      delete state.pendingHoldTimers[key];
      fn();
    }, delayMs);
  }

  function seenEvent(id) {
    if (!id) return false;
    const now = Date.now();
    state.recentEvents = state.recentEvents.filter((item) => now - item.at < 10000);
    return state.recentEvents.some((item) => item.id === id);
  }

  async function fireEvent(name, source, params) {
    try {
      const res = await fetch("/api/events/fire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, source, params: params || {} }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.event && data.event.id) {
        rememberEvent(data.event.id);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function elementForEvent(ev) {
    if (!ev) return null;
    const source = ev.source || "";
    if (!source) return null;
    return state.elements.find((el) => el.hardwareId === source || el.id === source) || null;
  }

  function connectEventStream() {
    if (!window.EventSource) return;
    if (state.eventSource) {
      try { state.eventSource.close(); } catch (_) {}
      state.eventSource = null;
    }
    const es = new EventSource("/api/events/stream");
    state.eventSource = es;
    es.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data || "{}");
        handleIncomingEvent(ev);
      } catch (e) {
        console.error(e);
      }
    };
    es.onerror = () => {
      es.close();
      if (state.eventSource === es) state.eventSource = null;
      setTimeout(connectEventStream, 1500);
    };
  }

  function closeEventStream() {
    if (!state.eventSource) return;
    try { state.eventSource.close(); } catch (_) {}
    state.eventSource = null;
  }

  function handleIncomingEvent(ev) {
    if (!ev) return;
    if (ev.id && seenEvent(ev.id)) {
      dbg("INCOMING_SKIP_SEEN_ID", { id: ev.id, name: ev.name, source: ev.source, eventType: ev.params?.eventType || null });
      return;
    }
    rememberEvent(ev.id);
    const sig = eventSignature(ev);
    if (sig && isNearDuplicateSignature(sig, Date.now())) {
      dbg("INCOMING_SKIP_SIG_WINDOW", { sig, id: ev.id, name: ev.name, source: ev.source, eventType: ev.params?.eventType || null });
      return;
    }
    if (sig) {
      const pending = Number(state.pendingLocalBySig[sig] || 0);
      if (pending > 0) {
        state.pendingLocalBySig[sig] = pending - 1;
        if (state.pendingLocalBySig[sig] <= 0) delete state.pendingLocalBySig[sig];
        dbg("INCOMING_SKIP_ECHO_SUPPRESS", { sig, pendingBefore: pending, id: ev.id, name: ev.name, source: ev.source, eventType: ev.params?.eventType || null });
        return;
      }
    }
    dbg("INCOMING_APPLY", { id: ev.id || null, name: ev.name, source: ev.source, eventType: ev.params?.eventType || null });
    if (sig) rememberAppliedSignature(sig, Date.now());
    const appliedCount = triggerRuleActionAnimations(ev);
    if (appliedCount === 0) {
      const matching = state.elements.filter((el) => eventMatchesElement(ev, el));
      matching.forEach((el) => pulseElement(el.id));
    }
  }

  function eventMatchesElement(ev, el) {
    if (!el) return false;
    if (ev.source && (ev.source === el.hardwareId || ev.source === el.id)) return true;
    const bindings = el.eventBindings || {};
    const bindingNames = Object.values(bindings).map((b) => b?.name).filter(Boolean);
    if (bindingNames.includes(ev.name)) return true;
    const reacts = Array.isArray(el.reactEvents) ? el.reactEvents : [];
    return reacts.includes(ev.name);
  }

  function renderEventsSection(el) {
    if (!eventsWrap) return;
    eventsWrap.innerHTML = "";
    if (eventsTitle) eventsTitle.classList.add("d-none");
    ensureEventBindings(el);
    const gestureList = gesturesForElement(el);
    const hasAvailableEventsOrActions = gestureList.length > 0 || isActionTarget(el);

    if (!gestureList.length) {
      if (isActionTarget(el)) {
        renderActionTargetSection(el);
        if (eventsTitle) eventsTitle.classList.remove("d-none");
        return;
      }
      const muted = document.createElement("div");
      muted.className = "emu-muted";
      muted.textContent = state.registry.systemEvents.length
        ? "No rules triggers available for this component."
        : "Loading registry…";
      eventsWrap.appendChild(muted);
      if (eventsTitle) eventsTitle.classList.add("d-none");
      return;
    }

    gestureList.forEach((meta) => {
      const row = document.createElement("div");
      row.className = "emu-event-row";
      const label = document.createElement("label");
      label.textContent = meta.key;
      const ruleBinding = ruleBindingFor(el, meta.key);
      const fireBtn = document.createElement("button");
      fireBtn.type = "button";
      fireBtn.className = "btn btn-outline-secondary btn-sm";
      fireBtn.textContent = "Fire";
      fireBtn.disabled = !ruleBinding || !isValidEventName(ruleBinding.name || "");
      fireBtn.addEventListener("click", () => fireBoundEvent(el, meta.key));

      row.appendChild(label);
      row.appendChild(document.createElement("span"));
      row.appendChild(fireBtn);
      eventsWrap.appendChild(row);
    });

    if (canFirePressRelease(el)) {
      const row = document.createElement("div");
      row.className = "emu-event-row";
      const label = document.createElement("label");
      label.textContent = "PRESSED+RELEASED";
      const fireBtn = document.createElement("button");
      fireBtn.type = "button";
      fireBtn.className = "btn btn-outline-secondary btn-sm";
      fireBtn.textContent = "Fire";
      fireBtn.addEventListener("click", () => firePressRelease(el));
      row.appendChild(label);
      row.appendChild(document.createElement("span"));
      row.appendChild(fireBtn);
      eventsWrap.appendChild(row);
    }

    if (isActionTarget(el)) {
      renderActionTargetSection(el);
    }
    if (eventsTitle) {
      eventsTitle.classList.toggle("d-none", !hasAvailableEventsOrActions);
    }
  }

  function ensureEventBindings(el) {
    if (!el.eventBindings) el.eventBindings = {};
    if (!el.reactEvents) el.reactEvents = [];
  }

  function gesturesForElement(el) {
    return ruleGesturesFor(el);
  }

  function canBindKeys(el) {
    if (!el) return false;
    if (isLedLike(el)) return false;
    return gesturesForElement(el).length > 0;
  }

  function fallbackDeviceClassForType(el) {
    const type = (el.icon || el.type || "").toLowerCase();
    if (["button", "flipper-left", "flipper-right", "target", "bumper"].includes(type)) {
      return "button";
    }
    return null;
  }

  function deviceClassForElement(el) {
    if (el.deviceClass) return el.deviceClass;
    const match = allHardwareComponents()
      .find((c) => c.id === el.hardwareId);
    return match ? match.deviceClass : fallbackDeviceClassForType(el);
  }

  function resolveSourceForElement(el) {
    if (!el) return "";
    if (el.hardwareId) return el.hardwareId;
    const label = (el.label || "").trim();
    if (label) {
      const match = allHardwareComponents()
        .find((c) => c.id === label || c.friendly === label);
      if (match) return match.id;
    }
    return el.id || "";
  }

  function sourceDeviceClass(sourceId) {
    if (!sourceId) return "";
    const all = allHardwareComponents();
    const hw = all.find((c) => c.id === sourceId);
    if (hw && hw.deviceClass) return String(hw.deviceClass).toLowerCase();
    const el = state.elements.find((x) => x.hardwareId === sourceId || x.id === sourceId);
    if (el && el.deviceClass) return String(el.deviceClass).toLowerCase();
    return "";
  }

  function applyRuleLinkGroups() {
    state.elements.forEach((el) => {
      if (!el || !el.linkAuto) return;
      delete el.linkAuto;
      delete el.linkGroup;
      delete el.linkRole;
      delete el.linkMove;
    });
    const pairs = Array.isArray(state.ruleLinkedPairs) ? state.ruleLinkedPairs : [];
    pairs.forEach((pair) => {
      const srcId = pair.a;
      const dstId = pair.b;
      if (!srcId || !dstId) return;
      if (isPairManuallyBroken(srcId, dstId)) return;
      const groupId = `lg_${srcId.replace(/[^A-Za-z0-9]+/g, "_")}__${dstId.replace(/[^A-Za-z0-9]+/g, "_")}`;
      const sourceElems = state.elements.filter((el) => el.hardwareId === srcId || el.id === srcId);
      const targetElems = state.elements.filter((el) => el.hardwareId === dstId || el.id === dstId);
      sourceElems.forEach((el) => {
        el.linkAuto = true;
        el.linkGroup = groupId;
        el.linkRole = "trigger";
        el.linkMove = true;
      });
      targetElems.forEach((el) => {
        el.linkAuto = true;
        el.linkGroup = groupId;
        el.linkRole = "actuator";
        el.linkMove = true;
      });
    });
  }

  function syncElementHardwareBindings() {
    const hardware = allHardwareComponents();
    state.elements.forEach((el) => {
      if (el.hardwareId) {
        if (!el.deviceClass) {
          const match = hardware.find((c) => c.id === el.hardwareId);
          if (match) el.deviceClass = match.deviceClass || el.deviceClass || null;
        }
        normalizeSpecialElementAppearance(el);
        return;
      }
      const label = (el.label || "").trim();
      const match = hardware.find((c) => c.id === el.id || c.id === label || c.friendly === label);
      if (match) {
        el.hardwareId = match.id;
        el.deviceClass = match.deviceClass || el.deviceClass || null;
      }
      normalizeSpecialElementAppearance(el);
    });
    applyRuleLinkGroups();
  }

  function isValidEventName(name) {
    if (!name) return false;
    if (state.registry.systemEvents.includes(name)) return true;
    const re = state.registry.customPattern;
    if (re && re.test(name)) return true;
    return false;
  }

  function ruleBindingFor(el, gesture) {
    const source = resolveSourceForElement(el);
    if (!source) return null;
    const entry = state.ruleTriggersBySource[source];
    if (!entry) return null;
    return entry[gesture] || null;
  }

  function canFirePressRelease(el) {
    if (!el) return false;
    if (!isButtonLike(el)) return false;
    return !!(ruleBindingFor(el, "PRESSED") && ruleBindingFor(el, "RELEASED"));
  }

  function firePressRelease(el) {
    if (!canFirePressRelease(el)) return;
    fireBoundEvent(el, "PRESSED");
    setTimeout(() => fireBoundEvent(el, "RELEASED"), 120);
  }

  function ruleGesturesFor(el) {
    const source = resolveSourceForElement(el);
    if (!source) return [];
    const entry = state.ruleTriggersBySource[source] || {};
    const keys = Object.keys(entry);
    if (!keys.length) return [];
    const registryEvents = state.registry.hardwareEvents || {};
    const metaByKey = {};
    Object.values(registryEvents).forEach((list) => {
      (list || []).forEach((meta) => {
        if (meta && meta.key && !metaByKey[meta.key]) metaByKey[meta.key] = meta;
      });
    });
    return keys.map((key) => metaByKey[key] || { key, label: key, params: [] });
  }

  function isActionTarget(el) {
    const source = resolveSourceForElement(el);
    const targets = state.ruleTargetsBySource[source];
    return Array.isArray(targets) && targets.length > 0;
  }

  function renderActionTargetSection(el) {
    const reactWrap = document.createElement("div");
    reactWrap.className = "mt-2";

    const targetSource = resolveSourceForElement(el);
    const info = state.ruleTargetInfoBySource[targetSource];
    if (info && Array.isArray(info.actions) && info.actions.length) {
      info.actions.forEach((entry) => {
        const row = document.createElement("div");
        row.className = "emu-muted";
        const typeLabel = prettyActionType(entry.type || "action");
        const triggers = (entry.triggers || [])
          .map((t) => {
            if (!t || !t.source) return "";
            const srcLabel = friendlySourceLabel(t.source);
            const fn = t.fn ? ` ${t.fn}` : "";
            return `${srcLabel}${fn}`;
          })
          .filter(Boolean);
        const fromText = triggers.length ? ` <- ${triggers.join(", ")}` : "";
        const ruleText = entry.ruleName ? ` (${entry.ruleName})` : "";
        row.textContent = `${typeLabel}${fromText}${ruleText}`;
        reactWrap.appendChild(row);
      });
    }

    if (info && info.rules.length) {
      const meta = document.createElement("div");
      meta.className = "emu-muted";
      meta.textContent = `Rule: ${info.rules.join(", ")}`;
      reactWrap.appendChild(meta);
    }
    eventsWrap.appendChild(reactWrap);
  }

  function fireBoundEvent(el, gesture) {
    const binding = el.eventBindings?.[gesture];
    const ruleBinding = ruleBindingFor(el, gesture);
    const name = ruleBinding?.name || binding?.name;
    if (!name) return;
    const source = resolveSourceForElement(el);
    if (!source) return;
    const params = Object.assign({}, (binding && binding.params) || {});
    params.eventType = gesture;
    Object.keys(params).forEach((key) => {
      if (key === "eventType") return;
      const raw = params[key];
      if (raw === "") delete params[key];
      const num = Number(raw);
      if (!Number.isNaN(num) && raw !== "" && typeof raw !== "boolean") {
        params[key] = num;
      }
    });
    const localEv = { name, source, params };
    if (isButtonLike(el)) {
      pressElement(el.id);
    }
    dbg("LOCAL_FIRE", { name, source, gesture, params });
    const sig = eventSignature(localEv);
    if (sig) rememberAppliedSignature(sig, Date.now());
    triggerRuleActionAnimations(localEv);
    if (sig) {
      state.pendingLocalBySig[sig] = Number(state.pendingLocalBySig[sig] || 0) + 1;
      dbg("LOCAL_SUPPRESS_SET", { sig, pending: state.pendingLocalBySig[sig] });
    }
    fireEvent(name, source, params);
  }

  function friendlySourceLabel(source) {
    if (!source) return "";
    const all = allHardwareComponents();
    const match = all.find((c) => c.id === source);
    if (!match) return source;
    return (match.friendly || match.id || source);
  }

  function prettyActionType(type) {
    if (!type) return "";
    return String(type)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function initContextMenu() {
    const menu = document.createElement("div");
    menu.className = "emu-context";
    menu.style.display = "none";
    document.body.appendChild(menu);
    document.addEventListener("click", () => hideContextMenu());
    window.addEventListener("resize", hideContextMenu);
    state.contextMenu = menu;
  }

  function showContextMenu(el, x, y) {
    if (!state.contextMenu) return;
    const menu = state.contextMenu;
    menu.innerHTML = "";
    ensureEventBindings(el);
    const gestureList = gesturesForElement(el);
    if (!gestureList.length) {
      const muted = document.createElement("div");
      muted.className = "emu-context-muted";
      muted.textContent = "No rules triggers";
      menu.appendChild(muted);
    } else {
      gestureList.forEach((meta) => {
        const binding = el.eventBindings?.[meta.key];
        const name = binding?.name || "";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = meta.key;
        btn.disabled = !isValidEventName(name) && !ruleBindingFor(el, meta.key);
        btn.addEventListener("click", () => {
          fireBoundEvent(el, meta.key);
          hideContextMenu();
        });
        menu.appendChild(btn);
      });
      if (canFirePressRelease(el)) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "PRESSED+RELEASED";
        btn.addEventListener("click", () => {
          firePressRelease(el);
          hideContextMenu();
        });
        menu.appendChild(btn);
      }
    }
    menu.style.display = "block";
    const rect = menu.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width - 8;
    const maxY = window.innerHeight - rect.height - 8;
    menu.style.left = `${Math.min(x, maxX)}px`;
    menu.style.top = `${Math.min(y, maxY)}px`;
  }

  function hideContextMenu() {
    if (!state.contextMenu) return;
    state.contextMenu.style.display = "none";
  }

  function setAppearance(v) {
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el) return;
    if (v === "led" || v === "rgb") return;
    el.icon = v;
    markDirty();
    renderTable();
  }

  function setColor(v) {
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el) return;
    el.color = v;
    markDirty();
    renderTable();
  }

  function setScale(v) {
    if (!state.selectedId) return;
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el) return;
    let scale = Number(v);
    if (!Number.isFinite(scale)) scale = 1;
    scale = Math.max(0.5, Math.min(2.5, scale));
    el.scale = scale;
    markDirty();
    renderScaleValue(scale);
    renderTable();
  }

  function setRotation(v) {
    if (!state.selectedId) return;
    const el = state.elements.find((e) => e.id === state.selectedId);
    if (!el) return;
    let rotation = Number(v);
    if (!Number.isFinite(rotation)) rotation = 0;
    rotation = Math.max(-180, Math.min(180, rotation));
    el.rotation = rotation;
    markDirty();
    renderRotationValue(rotation);
    renderTable();
  }

  function centerAll() {
    const cx = state.tableRect.width / 2;
    const cy = state.tableRect.height / 2;
    let angle = 0;
    const step = (2 * Math.PI) / Math.max(1, state.elements.length);
    state.elements.forEach((el) => {
      el.x = cx + Math.cos(angle) * (state.tableRect.width * 0.3);
      el.y = cy + Math.sin(angle) * (state.tableRect.height * 0.3);
      if (state.tableRect.width > 0) el.nx = el.x / state.tableRect.width;
      if (state.tableRect.height > 0) el.ny = el.y / state.tableRect.height;
      angle += step;
    });
    markDirty();
    renderTable();
  }

  function clearLayout() {
    state.elements = [];
    state.keymap = {};
    state.selectedId = null;
    markDirty();
    renderSelection();
    renderTable();
    renderComponents();
  }

  async function save() {
    try {
      const playfieldOk = await savePlayfieldOptions();
      if (!playfieldOk) throw new Error("Save failed");
      const body = JSON.stringify({ options: state.options, elements: state.elements, keymap: state.keymap });
      const r = await fetch("/api/playfield/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (!r.ok) throw new Error("Save failed");
      markDirty(false);
    } catch (e) {
      console.error(e);
      alert("Save failed");
    }
  }

  function iconForExpanded(icon, expanded) {
    if (!icon) return;
    icon.classList.remove("fa-chevron-right", "fa-chevron-down", "fa-plus");
    icon.classList.add(expanded ? "fa-chevron-down" : "fa-chevron-right");
  }

  function setAccordionExpanded(key, expanded, persist = true) {
    const panel = document.querySelector(`[data-emu-panel="${key}"]`);
    const icon = document.querySelector(`[data-emu-toggle-icon="${key}"]`);
    if (!panel) return;
    panel.classList.toggle("d-none", !expanded);
    iconForExpanded(icon, expanded);
    if (persist) {
      panelState[key] = !!expanded;
      savePanelState();
    }
  }

  function wireAccordions() {
    document.querySelectorAll("[data-emu-toggle]").forEach((btn) => {
      const onToggle = () => {
        const key = btn.getAttribute("data-emu-toggle");
        const panel = document.querySelector(`[data-emu-panel="${key}"]`);
        if (!panel) return;
        const shouldExpand = panel.classList.contains("d-none");
        setAccordionExpanded(key, shouldExpand);
      };

      btn.addEventListener("click", (e) => {
        if (e && typeof e.stopPropagation === "function") e.stopPropagation();
        onToggle();
      });

      const header = btn.closest(".card-header");
      if (!header) return;
      header.setAttribute("role", "button");
      header.setAttribute("tabindex", "0");
      header.addEventListener("click", onToggle);
      header.addEventListener("keydown", (e) => {
        const key = String(e?.key || "").toLowerCase();
        if (key !== "enter" && key !== " " && key !== "spacebar") return;
        if (e && typeof e.preventDefault === "function") e.preventDefault();
        onToggle();
      });

      const key = btn.getAttribute("data-emu-toggle");
      const panel = key ? document.querySelector(`[data-emu-panel="${key}"]`) : null;
      const defaultOpen = panel ? !panel.classList.contains("d-none") : false;
      const isOpen = Object.prototype.hasOwnProperty.call(panelState, key)
        ? !!panelState[key]
        : defaultOpen;
      setAccordionExpanded(key, isOpen, false);
    });
  }

  async function loadState() {
    try {
      const r = await fetch("/api/playfield/state");
      const data = await r.json();
      state.options = data.options || state.options;
      state.playfield = normalizePlayfield(data.playfield);
      state.elements = data.elements || [];
      state.keymap = data.keymap || {};
      Object.entries(state.keymap).forEach(([k, v]) => {
        const norm = normalizeKeymapEntry(v);
        if (norm) state.keymap[k] = norm;
      });
      state.elements.forEach((el) => {
        normalizeSpecialElementAppearance(el);
        if (!el.size) {
          const t = el.icon || el.type;
          el.size = state.defaultSizeForType[t] || "m";
        }
      });
      ensureNormalizedAndSync();
      markDirty(false);
      renderOptions();
      renderPlayfieldUi();
      updateTableSize();
      applyPlayfieldBackground();
      renderTable();
      renderSelection();
      renderComponents();
    } catch (e) {
      console.error(e);
    }
  }

  async function loadHardware() {
    try {
      const r = await fetch("/api/playfield/hardware");
      const data = await r.json();
      if (data && data.components) {
        state.components = Object.assign(
          { buttons: [], leds: [], solenoids: [], other: [] },
          data.components
        );
        state.safetyById = (data && data.safetyById && typeof data.safetyById === "object")
          ? data.safetyById
          : {};
        const isLightingManaged = (c) => {
          const dclass = String(c?.deviceClass || "").trim().toLowerCase();
          if (dclass === "led" || dclass === "rgb") return true;
          const fn = String(c?.function || "").trim().toLowerCase();
          return fn === "led" || fn === "rgb strip" || fn === "rgb led" || fn === "rgb";
        };
        state.components.leds = (state.components.leds || []).filter((c) => !isLightingManaged(c));
        state.components.other = (state.components.other || []).filter((c) => !isLightingManaged(c));
      }
      if (!(data && data.components)) {
        state.safetyById = (data && data.safetyById && typeof data.safetyById === "object")
          ? data.safetyById
          : {};
      }
      state.hardwareLoaded = true;
      syncElementHardwareBindings();
      renderComponents();
      if (state.selectedId) renderSelection();
    } catch (e) {
      state.hardwareLoaded = true;
      renderComponents();
    }
  }

  async function loadRegistry() {
    try {
      const fetchTriggers = async () => {
        const r = await fetch("/api/events/registry");
        if (!r.ok) throw new Error("events registry fetch failed");
        const data = await r.json();
        if (data && data.triggers) return data.triggers;
        throw new Error("events registry missing triggers");
      };
      let triggers;
      try {
        triggers = await fetchTriggers();
      } catch (err) {
        const fallback = await fetch("/api/rules/catalog");
        if (!fallback.ok) throw err;
        const data = await fallback.json();
        triggers = data?.registry?.triggers || {};
      }

      const systemEvents = [];
      const systemCats = triggers.system?.categories || {};
      Object.values(systemCats).forEach((meta) => {
        (meta.events || []).forEach((ev) => systemEvents.push(ev));
      });
      const hardwareEvents = {};
      const classes = triggers.hardware?.deviceClasses || {};
      Object.entries(classes).forEach(([key, meta]) => {
        const list = (meta.events || []).map((ev) => {
          if (typeof ev === "string") return { key: ev, label: ev, params: [] };
          return { key: ev.key, label: ev.label || ev.key, params: ev.params || [] };
        });
        hardwareEvents[key] = list;
      });
      const customPattern = triggers.custom?.validation ? new RegExp(triggers.custom.validation) : null;
      state.registry.systemEvents = systemEvents;
      state.registry.hardwareEvents = hardwareEvents;
      state.registry.customPattern = customPattern;
      updateEventDatalist();
      if (state.selectedId) renderSelection();
    } catch (e) {
      console.error(e);
    }
  }

  async function loadRules() {
    try {
      const r = await fetch("/api/rules/list");
      if (!r.ok) throw new Error("rules fetch failed");
      const data = await r.json();
      const rules = data && data.rules ? data.rules : [];
      const bySource = {};
      const targets = {};
      const targetInfo = {};
      const actionByGesture = {};
      const actionByEvent = {};
      const linkedPairKeys = new Set();
      rules.forEach((rule) => {
        const ruleName = rule?.name || "";
        const triggerEvents = [];
        const triggerBindings = [];
        const groups = rule?.triggerGroups?.groups || [];
        groups.forEach((group) => {
          (group.items || []).forEach((item) => {
            if (item?.type !== "hardware") return;
            const source = item.source;
            const gesture = item.fn;
            const name = item.event;
            if (!source || !gesture || !name) return;
            bySource[source] = bySource[source] || {};
            if (!bySource[source][gesture]) {
              bySource[source][gesture] = { name, params: item.params || {} };
            }
            triggerEvents.push(name);
            triggerBindings.push({ source, fn: gesture, event: name });
          });
        });
        (rule.triggers || []).forEach((item) => {
          if (item?.type !== "hardware") return;
          const source = item.source;
          const gesture = item.fn;
          const name = item.event;
          if (!source || !gesture || !name) return;
          bySource[source] = bySource[source] || {};
          if (!bySource[source][gesture]) {
            bySource[source][gesture] = { name, params: item.params || {} };
          }
          triggerEvents.push(name);
          triggerBindings.push({ source, fn: gesture, event: name });
        });

        (rule.actions || []).forEach((action) => {
          if (!action || typeof action !== "object") return;
          const target = action.target || action.params?.device || action.params?.target;
          if (!target) return;
          targets[target] = targets[target] || [];
          if (!targets[target].includes(action.type)) targets[target].push(action.type);
          targetInfo[target] = targetInfo[target] || { rules: [], events: [], actions: [] };
          if (ruleName && !targetInfo[target].rules.includes(ruleName)) {
            targetInfo[target].rules.push(ruleName);
          }
          triggerEvents.forEach((evt) => {
            if (evt && !targetInfo[target].events.includes(evt)) {
              targetInfo[target].events.push(evt);
            }
          });
          const seenBindings = new Set();
          const compactBindings = triggerBindings.filter((tb) => {
            const key = `${tb.source}|${tb.fn}|${tb.event}`;
            if (seenBindings.has(key)) return false;
            seenBindings.add(key);
            return true;
          });
          compactBindings.forEach((tb) => {
            const ruleDir = (() => {
              const r = String(ruleName || "").toLowerCase();
              if (r.includes("left")) return "left";
              if (r.includes("right")) return "right";
              return null;
            })();
            const gestureKey = `${tb.source}|${tb.fn}`;
            actionByGesture[gestureKey] = actionByGesture[gestureKey] || [];
            actionByGesture[gestureKey].push({
              target,
              type: action.type || "",
              params: action.params || {},
              dir: ruleDir,
            });
            const eventKey = `${tb.source}|${tb.event}`;
            actionByEvent[eventKey] = actionByEvent[eventKey] || [];
            actionByEvent[eventKey].push({
              target,
              type: action.type || "",
              params: action.params || {},
              dir: ruleDir,
            });
            const actionType = String(action.type || "");
            if (
              tb.source &&
              target &&
              tb.source !== target &&
              (actionType === "pulse" || actionType === "set_output")
            ) {
              linkedPairKeys.add([tb.source, target].sort().join("|"));
            }
          });
          targetInfo[target].actions.push({
            type: action.type || "",
            ruleName,
            triggers: compactBindings,
          });
        });
      });
      state.ruleTriggersBySource = bySource;
      state.ruleTargetsBySource = targets;
      state.ruleTargetInfoBySource = targetInfo;
      state.ruleActionsBySourceGesture = actionByGesture;
      state.ruleActionsBySourceEvent = actionByEvent;
      state.ruleLinkedPairs = Array.from(linkedPairKeys).map((k) => {
        const [a, b] = k.split("|");
        return { a, b };
      });
      applyRuleLinkGroups();
      renderComponents();
      renderTable();
      if (state.selectedId) renderSelection();
    } catch (e) {
      console.error(e);
    }
  }

  function updateEventDatalist() {
    let dl = document.getElementById("emu-event-keys");
    if (!dl) {
      dl = document.createElement("datalist");
      dl.id = "emu-event-keys";
      document.body.appendChild(dl);
    }
    dl.innerHTML = "";
    state.registry.systemEvents.forEach((ev) => {
      const opt = document.createElement("option");
      opt.value = ev;
      dl.appendChild(opt);
    });
  }

  function initInputs() {
    widthInput?.addEventListener("change", () => {
      state.options.width = Number(widthInput.value) || state.options.width;
      markDirty();
      renderOptions();
      updateTableSize();
      renderTable();
    });
    heightInput?.addEventListener("change", () => {
      state.options.height = Number(heightInput.value) || state.options.height;
      markDirty();
      renderOptions();
      updateTableSize();
      renderTable();
    });
    centerBtn?.addEventListener("click", centerAll);
    clearBtn?.addEventListener("click", clearLayout);
    saveBtn?.addEventListener("click", save);
    playfieldUploadBtn?.addEventListener("click", uploadPlayfield);
    playfieldRemoveBtn?.addEventListener("click", removePlayfield);
    playfieldFitSel?.addEventListener("change", () => {
      savePlayfieldOptions();
      markDirty();
    });
    playfieldPositionSel?.addEventListener("change", () => {
      savePlayfieldOptions();
      markDirty();
    });
    playfieldOpacityInput?.addEventListener("input", () => {
      let opacity = Number(playfieldOpacityInput.value);
      if (!Number.isFinite(opacity)) opacity = 1;
      opacity = Math.max(0, Math.min(1, opacity));
      state.playfield.opacity = opacity;
      applyPlayfieldBackground();
      if (playfieldOpacityValue) playfieldOpacityValue.textContent = `${Math.round(opacity * 100)}%`;
      markDirty();
    });
    playfieldOpacityInput?.addEventListener("change", savePlayfieldOptions);
    unlinkBtn?.addEventListener("click", unlinkSelectedGroup);
    appearanceSel?.addEventListener("change", (e) => setAppearance(e.target.value));
    colorInput?.addEventListener("change", (e) => setColor(e.target.value));
    sizeScaleInput?.addEventListener("input", (e) => setScale(e.target.value));
    rotationInput?.addEventListener("input", (e) => setRotation(e.target.value));
    captureBtn?.addEventListener("click", captureKey);
    removeBtn?.addEventListener("click", () => { removeSelected(); renderSelection(); renderTable(); });
    tableEl?.addEventListener("click", (e) => { if (e.target === tableEl) clearSelection(); });
  }

  function removeSelected() {
    if (!state.selectedId) return;
    const selected = state.elements.find((e) => e.id === state.selectedId);
    if (!selected) return;
    const removeIds = new Set([selected.id]);
    // Linked hardware pairs should be removed together so the table cannot
    // contain a half-pair.
    if (selected.linkGroup) {
      state.elements.forEach((el) => {
        if (el && el.linkGroup === selected.linkGroup) removeIds.add(el.id);
      });
    }
    const before = state.elements.length;
    state.elements = state.elements.filter((e) => !removeIds.has(e.id));
    if (state.elements.length === before) return;
    Object.keys(state.keymap).forEach((k) => {
      const entry = normalizeKeymapEntry(state.keymap[k]);
      if (entry && removeIds.has(entry.id)) delete state.keymap[k];
    });
    state.selectedId = null;
    markDirty();
    renderComponents();
  }

  function initGlobalListeners() {
    const stageTabBtn = document.getElementById("emu-stage-tab");
    stageTabBtn?.addEventListener("shown.bs.tab", () => {
      updateTableSize();
      renderTable();
    });
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("keydown", onKeyDown, false);
    window.addEventListener("keyup", onKeyUp, false);
    window.addEventListener("blur", () => {
      state.activeKeyPresses = Object.create(null);
    });
    document.addEventListener("click", (e) => {
      if (!(e.target && e.target.closest)) return;
      if (!e.target.closest(".emu-table-col")) return;
      if (e.target.closest(".emu-el")) return;
      clearSelection();
    });
    document.addEventListener("click", (e) => {
      const link = e.target && e.target.closest ? e.target.closest("a[href]") : null;
      if (!link) return;
      const href = String(link.getAttribute("href") || "");
      if (!href || href.startsWith("#") || link.hasAttribute("download")) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      if (String(link.getAttribute("target") || "").toLowerCase() === "_blank") return;
      if (!state.dirty) return;
      e.preventDefault();
      e.stopPropagation();
      confirmLeaveWithUnsaved().then((ok) => {
        if (!ok) return;
        bypassUnloadOnce = true;
        window.location.href = link.href;
      });
    }, true);
    document.addEventListener("submit", (e) => {
      if (!state.dirty) return;
      e.preventDefault();
      e.stopPropagation();
      confirmLeaveWithUnsaved().then((ok) => {
        if (!ok) return;
        bypassUnloadOnce = true;
        HTMLFormElement.prototype.submit.call(e.target);
      });
    }, true);
    window.addEventListener("beforeunload", (e) => {
      closeEventStream();
      if (!state.dirty) return;
      if (bypassUnloadOnce) {
        bypassUnloadOnce = false;
        return;
      }
      e.preventDefault();
      e.returnValue = "";
    });
    window.addEventListener("pagehide", () => {
      closeEventStream();
    });
    const wrap = tableEl?.parentElement;
    if (wrap && typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(updateTableSize);
      ro.observe(wrap);
    } else {
      window.addEventListener("resize", updateTableSize);
    }
  }

  function init() {
    applyInitialThemeWatcher();
    loadPanelState();
    wireAccordions();
    initInputs();
    initGlobalListeners();
    initContextMenu();
    markDirty(false);
    renderOptions();
    updateTableSize();
    loadState();
    loadHardware();
    loadRegistry();
    loadRules();
    connectEventStream();
  }

  init();
})();
