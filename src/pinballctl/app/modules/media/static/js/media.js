(() => {
  const root = document.getElementById("media-page");
  if (!root) return;

  const MEDIA_TAB_KEY = "pinballctl.media.lastTab.v1";
  const MEDIA_COLLAPSE_KEY = "pinballctl.media.collapse.v1";
  const MEDIA_OVERLAY_COLLAPSE_KEY = "pinballctl.media.overlayCollapse.v1";
  const MEDIA_SELECTED_SCENE_KEY = "pinballctl.media.selectedScene.v1";

  const state = {
    config: null,
    env: null,
    runtime: null,
    selectedSceneId: null,
    selectedOverlayIdx: -1,
    overlayCollapsed: {},
    dirty: false,
    previewRatio: 16 / 9,
    previewDisplayW: 1920,
    previewDisplayH: 1080,
    previewShouldPlay: true,
  };

  const $ = (sel) => root.querySelector(sel);
  const saveButtons = Array.from(root.querySelectorAll("[data-media-save]"));
  const elAssets = $("#media-assets-table");
  const elAssetCount = $("#media-asset-count-pill");
  const elAssetPreviewModal = document.getElementById("media-asset-preview-modal");
  const elAssetPreviewStage = document.getElementById("media-asset-preview-stage");
  const elAssetPreviewTitle = document.getElementById("media-asset-preview-title");
  const elUploadDropzone = $("#media-upload-dropzone");
  const elUploadBrowse = $("#media-upload-browse");
  const elUploadFile = $("#media-upload-file");
  const elUploadProgressWrap = $("#media-upload-progress-wrap");
  const elUploadProgress = $("#media-upload-progress");
  const elUploadProgressText = $("#media-upload-progress-text");
  const elDetectDisplays = $("#media-detect-displays");
  const elOutputEnv = $("#media-output-env");
  const elDisplays = $("#media-displays-table");
  const elSceneSelect = $("#media-scene-select");
  const elEditor = $("#media-scene-editor");
  const elOverlaysEditor = $("#media-overlays-editor");
  const elPreview = $("#media-preview-stage");
  const elScenesLayout = root.querySelector(".media-scenes-layout");
  const elScenesPreviewCol = root.querySelector(".media-scenes-preview-col");
  const elScenesSideCol = root.querySelector(".media-scenes-side-col");
  const elScenesOptionsScroll = root.querySelector(".media-scenes-options-scroll");
  const elPreviewPlay = $("#media-preview-play");
  const elPreviewStop = $("#media-preview-stop");
  const elPreviewScrub = $("#media-preview-scrub");
  const elPreviewTime = $("#media-preview-time");
  const elPreviewOpenFull = $("#media-preview-open-full");
  const elPreviewOpenWindow = $("#media-preview-open-window");
  const elAddScene = $("#media-add-scene");
  const elAddOverlay = $("#media-add-overlay");
  const elRuntime = $("#media-runtime-table");
  const elRuntimeRefresh = $("#media-runtime-refresh");
  const elStopAll = $("#media-stop-all");

  let uploadInProgress = false;
  let dragState = null;
  let previewVideo = null;
  let previewScrubbing = false;
  let previewToggleBusy = false;

  function esc(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function uid(prefix) {
    return `${prefix}_${Math.random().toString(16).slice(2, 10)}`;
  }

  function clamp(v, lo, hi) {
    const n = Number(v);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, n));
  }

  function fmtTime(sec) {
    const s = Math.max(0, Math.floor(Number(sec || 0)));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  function currentPreviewViewport() {
    if (!elPreview) return null;
    const w = Math.max(1, Math.round(Number(elPreview.clientWidth || 0)));
    const h = Math.max(1, Math.round(Number(elPreview.clientHeight || 0)));
    if (w <= 1 || h <= 1) return null;
    return { width: w, height: h };
  }

  function previewHasVideo() {
    return !!(previewVideo && Number.isFinite(previewVideo.duration));
  }

  function activePreviewVideo() {
    const inDom = elPreview?.querySelector("video#media-preview-video") || null;
    if (!inDom) return null;
    if (previewVideo !== inDom) previewVideo = inDom;
    return inDom;
  }

  function updatePreviewControlsUi() {
    const hasVideo = !!previewVideo;
    const dur = hasVideo && Number.isFinite(previewVideo.duration) ? Math.max(0, Number(previewVideo.duration || 0)) : 0;
    const cur = hasVideo ? Math.max(0, Number(previewVideo.currentTime || 0)) : 0;
    const paused = !hasVideo || !!previewVideo.paused || !!previewVideo.ended;

    if (elPreviewPlay) {
      elPreviewPlay.disabled = !hasVideo;
      elPreviewPlay.setAttribute("aria-disabled", hasVideo ? "false" : "true");
      elPreviewPlay.innerHTML = paused ? '<i class="fa fa-play"></i>' : '<i class="fa fa-pause"></i>';
      elPreviewPlay.title = paused ? "Play" : "Pause";
      elPreviewPlay.setAttribute("aria-label", paused ? "Play" : "Pause");
    }
    if (elPreviewStop) {
      elPreviewStop.disabled = !hasVideo;
      elPreviewStop.setAttribute("aria-disabled", hasVideo ? "false" : "true");
    }
    if (elPreviewScrub) {
      elPreviewScrub.disabled = !hasVideo;
      elPreviewScrub.setAttribute("aria-disabled", hasVideo ? "false" : "true");
      if (!previewScrubbing) {
        const ratio = dur > 0 ? Math.max(0, Math.min(1, cur / dur)) : 0;
        elPreviewScrub.value = String(Math.round(ratio * 1000));
      }
    }
    if (elPreviewTime) {
      elPreviewTime.textContent = `${fmtTime(cur)} / ${fmtTime(dur)}`;
    }
  }

  function detachPreviewVideoHandlers() {
    if (!previewVideo) return;
    previewVideo.onplay = null;
    previewVideo.onplaying = null;
    previewVideo.onpause = null;
    previewVideo.onended = null;
    previewVideo.ontimeupdate = null;
    previewVideo.onloadedmetadata = null;
    previewVideo.onseeked = null;
  }

  function attachPreviewVideoHandlers(video) {
    detachPreviewVideoHandlers();
    previewVideo = video || null;
    if (!previewVideo) {
      updatePreviewControlsUi();
      return;
    }
    previewVideo.onplay = () => updatePreviewControlsUi();
    previewVideo.onplaying = () => updatePreviewControlsUi();
    previewVideo.onpause = () => updatePreviewControlsUi();
    previewVideo.onended = () => updatePreviewControlsUi();
    previewVideo.ontimeupdate = () => updatePreviewControlsUi();
    previewVideo.onloadedmetadata = () => updatePreviewControlsUi();
    previewVideo.onseeked = () => updatePreviewControlsUi();
    updatePreviewControlsUi();
  }

  function q025(v) {
    const n = Number(v || 0);
    return Math.round(n * 4) / 4;
  }

  function qPxPercent(pct, totalPx) {
    const px = Math.round((Number(pct || 0) / 100) * Math.max(1, Number(totalPx || 1)));
    return (px / Math.max(1, Number(totalPx || 1))) * 100;
  }

  function normalizeOverlayType(raw) {
    const t = String(raw || "").trim().toLowerCase();
    if (t === "badge") return "text";
    return ["text", "image", "frame"].includes(t) ? t : "";
  }

  function normalizeTextAlign(raw) {
    const t = String(raw || "").trim().toLowerCase();
    return ["left", "center", "right"].includes(t) ? t : "center";
  }

  function normalizeTextEffects(raw) {
    const allowed = new Set(["shadow", "outline", "underline", "strike", "bold", "italic", "uppercase", "tracking", "glow"]);
    const out = [];
    const list = Array.isArray(raw) ? raw : [];
    list.forEach((item) => {
      const key = String(item || "").trim().toLowerCase();
      if (!allowed.has(key)) return;
      if (out.includes(key)) return;
      out.push(key);
    });
    return out;
  }

  function parseColorRgb(rawColor) {
    const s = String(rawColor || "").trim().toLowerCase();
    if (!s) return null;
    if (s.startsWith("#")) {
      const hex = s.slice(1);
      if (hex.length === 3 || hex.length === 4) {
        const r = parseInt(hex[0] + hex[0], 16);
        const g = parseInt(hex[1] + hex[1], 16);
        const b = parseInt(hex[2] + hex[2], 16);
        if ([r, g, b].every((n) => Number.isFinite(n))) return { r, g, b };
      } else if (hex.length === 6 || hex.length === 8) {
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        if ([r, g, b].every((n) => Number.isFinite(n))) return { r, g, b };
      }
      return null;
    }
    const m = s.match(/^rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)(?:\s*,\s*[0-9.]+\s*)?\)$/);
    if (!m) return null;
    const r = clamp(Number(m[1]), 0, 255);
    const g = clamp(Number(m[2]), 0, 255);
    const b = clamp(Number(m[3]), 0, 255);
    return { r: Math.round(r), g: Math.round(g), b: Math.round(b) };
  }

  function srgbToLinear(v) {
    const n = clamp(Number(v) / 255, 0, 1);
    if (n <= 0.04045) return n / 12.92;
    return ((n + 0.055) / 1.055) ** 2.4;
  }

  function relativeLuminance(rgb) {
    if (!rgb) return null;
    const r = srgbToLinear(rgb.r);
    const g = srgbToLinear(rgb.g);
    const b = srgbToLinear(rgb.b);
    return (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
  }

  function effectRgbFromTextColor(rawColor) {
    const rgb = parseColorRgb(rawColor);
    const lum = relativeLuminance(rgb);
    if (!Number.isFinite(lum)) return { r: 0, g: 0, b: 0 };
    return lum >= 0.56 ? { r: 0, g: 0, b: 0 } : { r: 255, g: 255, b: 255 };
  }

  function rgba(rgb, alpha) {
    return `rgba(${rgb.r},${rgb.g},${rgb.b},${alpha})`;
  }

  function textEffectStyles(ovType, rawEffects, textColor) {
    if (String(ovType || "") !== "text") {
      return {
        fontWeight: "400",
        fontStyle: "normal",
        textTransform: "none",
        letterSpacing: "normal",
        textDecoration: "none",
        textShadow: "none",
      };
    }
    const fx = new Set(normalizeTextEffects(rawEffects));
    const fxRgb = effectRgbFromTextColor(textColor);
    const decorations = [];
    if (fx.has("underline")) decorations.push("underline");
    if (fx.has("strike")) decorations.push("line-through");
    const shadows = [];
    if (fx.has("outline")) {
      shadows.push(`-1px 0 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`1px 0 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`0 -1px 0 ${rgba(fxRgb, 0.92)}`);
      shadows.push(`0 1px 0 ${rgba(fxRgb, 0.92)}`);
    }
    if (fx.has("shadow")) shadows.push(`0 2px 6px ${rgba(fxRgb, 0.78)}`);
    if (fx.has("glow")) shadows.push(`0 0 6px ${rgba(fxRgb, 0.42)}, 0 0 14px ${rgba(fxRgb, 0.24)}`);
    return {
      fontWeight: fx.has("bold") ? "700" : "400",
      fontStyle: fx.has("italic") ? "italic" : "normal",
      textTransform: fx.has("uppercase") ? "uppercase" : "none",
      letterSpacing: fx.has("tracking") ? "0.06em" : "normal",
      textDecoration: decorations.length ? decorations.join(" ") : "none",
      textShadow: shadows.length ? shadows.join(", ") : "none",
    };
  }

  function renderTextEffectsOptions(selectedEffects) {
    const selected = new Set(normalizeTextEffects(selectedEffects));
    const options = [
      ["shadow", "Shadow"],
      ["outline", "Outline"],
      ["glow", "Glow"],
      ["underline", "Underline"],
      ["strike", "Strike Thru"],
      ["bold", "Bold"],
      ["italic", "Italic"],
      ["uppercase", "Uppercase"],
      ["tracking", "Tracking"],
    ];
    return `
      <select class="form-select form-select-sm" data-k="textEffect" multiple size="6" aria-label="Text effects">
        ${options.map(([value, label]) => `<option value="${value}" ${selected.has(value) ? "selected" : ""}>${label}</option>`).join("")}
      </select>
      <div class="form-text mt-1">Hold Cmd/Ctrl to select multiple effects.</div>
    `;
  }

  function selectedTextEffectsFromRow(row, fallback) {
    const sel = row?.querySelector('[data-k="textEffect"]');
    if (!sel) return normalizeTextEffects(fallback);
    const picked = Array.from(sel.selectedOptions || []).map((n) => n.value);
    return normalizeTextEffects(picked);
  }

  function normalizeAngleDelta(deltaDeg) {
    let d = Number(deltaDeg || 0);
    while (d > 180) d -= 360;
    while (d < -180) d += 360;
    return d;
  }

  function readJsonLs(key, fallback = {}) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || "");
      return parsed && typeof parsed === "object" ? parsed : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function writeJsonLs(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value || {})); } catch (_) {}
  }

  function readSelectedSceneId() {
    try {
      return String(localStorage.getItem(MEDIA_SELECTED_SCENE_KEY) || "").trim();
    } catch (_) {
      return "";
    }
  }

  function writeSelectedSceneId(sceneId) {
    try {
      const val = String(sceneId || "").trim();
      if (!val) localStorage.removeItem(MEDIA_SELECTED_SCENE_KEY);
      else localStorage.setItem(MEDIA_SELECTED_SCENE_KEY, val);
    } catch (_) {}
  }

  function askConfirm(message, opts = {}) {
    const fallback = () => Promise.resolve(window.confirm(message));
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!body || !confirmBtn) return fallback();

    body.textContent = String(message || "Are you sure?");
    if (titleEl) titleEl.textContent = String(opts.title || "Confirm");
    confirmBtn.textContent = String(opts.confirmLabel || "Confirm");
    confirmBtn.className = `btn ${opts.confirmClass || "btn-danger"}`;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        confirmBtn.removeEventListener("click", onConfirm);
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        resolve(!!ok);
      };
      const onConfirm = () => {
        finish(true);
        modal.hide();
      };
      const onHidden = () => finish(false);
      confirmBtn.addEventListener("click", onConfirm);
      modalEl.addEventListener("hidden.bs.modal", onHidden);
      modal.show();
    });
  }

  async function api(path, opts) {
    const r = await fetch(`/api/media${path}`, opts || {});
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.ok === false) throw new Error(j.error || `HTTP ${r.status}`);
    return j;
  }

  function setDirty(flag) {
    state.dirty = !!flag;
    saveButtons.forEach((btn) => {
      btn.disabled = !state.dirty;
      btn.setAttribute("aria-disabled", state.dirty ? "false" : "true");
    });
  }

  function scenes() {
    return Array.isArray(state.config?.scenes) ? state.config.scenes : [];
  }

  function assets() {
    return Array.isArray(state.config?.assets) ? state.config.assets : [];
  }

  function displays() {
    return Array.isArray(state.config?.displays) ? state.config.displays : [];
  }

  function sceneById(sceneId) {
    return scenes().find((s) => String(s.id || "") === String(sceneId || ""));
  }

  function displayLabel(d) {
    return `${d.name || d.id} (${Number(d.width || 0)}x${Number(d.height || 0)})`;
  }

  function sceneDisplay(scene) {
    const key = String(scene?.targetDisplay || "");
    return displays().find((d) => String(d.id || "") === key || String(d.role || "") === key) || displays()[0] || null;
  }

  async function launchScene(sceneId, launchMode = "fullscreen") {
    const mode = String(launchMode || "").trim().toLowerCase() === "windowed" ? "windowed" : "fullscreen";
    const previewViewport = currentPreviewViewport();
    await api("/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneId, launchMode: mode, previewViewport }),
    });
    const st = await api("/state");
    state.runtime = st.state || null;
    renderRuntime();
  }

  function clearOverlaySelection() {
    if (state.selectedOverlayIdx === -1) return;
    state.selectedOverlayIdx = -1;
    syncEditorOverlaySelection();
    renderPreview();
  }

  function syncEditorOverlaySelection() {
    if (!elOverlaysEditor) return;
    const rows = elOverlaysEditor.querySelectorAll("[data-overlay-idx]");
    rows.forEach((row) => {
      const idx = Number(row.getAttribute("data-overlay-idx"));
      row.classList.toggle("border-primary", Number.isFinite(idx) && idx === state.selectedOverlayIdx);
    });
  }

  function selectFrameOverlayOrClear() {
    const scene = sceneById(state.selectedSceneId);
    const overlays = Array.isArray(scene?.overlays) ? scene.overlays : [];
    let frameIdx = -1;
    let frameZ = -Infinity;
    overlays.forEach((ov, idx) => {
      if (normalizeOverlayType(ov?.type) !== "frame") return;
      const z = Number(ov?.zIndex || idx + 1);
      if (z >= frameZ) {
        frameZ = z;
        frameIdx = idx;
      }
    });
    if (frameIdx >= 0) {
      if (state.selectedOverlayIdx !== frameIdx) {
        state.selectedOverlayIdx = frameIdx;
        syncEditorOverlaySelection();
        renderPreview();
      }
      return;
    }
    clearOverlaySelection();
  }

  function wireTabs() {
    const tabButtons = Array.from(root.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#media-pane-"]'));
    tabButtons.forEach((btn) => {
      btn.addEventListener("shown.bs.tab", (e) => {
        const target = String(e.target?.getAttribute("data-bs-target") || "");
        if (!target) return;
        try { localStorage.setItem(MEDIA_TAB_KEY, target); } catch (_) {}
        if (target === "#media-pane-scenes") {
          window.requestAnimationFrame(() => {
            syncScenesColumnHeight();
          });
        }
      });
    });

    let last = "";
    try { last = localStorage.getItem(MEDIA_TAB_KEY) || ""; } catch (_) { last = ""; }
    if (!last) return;
    const btn = root.querySelector(`[data-bs-toggle="tab"][data-bs-target="${last}"]`);
    if (btn && typeof bootstrap !== "undefined" && bootstrap.Tab) {
      bootstrap.Tab.getOrCreateInstance(btn).show();
    }
  }

  function wireCardCollapses() {
    const prefs = readJsonLs(MEDIA_COLLAPSE_KEY, {});
    const collapses = Array.from(root.querySelectorAll('.collapse[id^="media-"]'));
    collapses.forEach((el) => {
      const id = String(el.id || "");
      if (!id) return;
      const toggleButtons = Array.from(root.querySelectorAll(`[data-bs-target="#${id}"]`));
      const desired = prefs[id];
      if (typeof desired === "boolean") {
        // Apply startup state without animation to avoid open->close flicker on load.
        el.classList.remove("collapsing");
        el.classList.toggle("show", desired);
      }
      const syncStoredState = () => {
        const isOpen = el.classList.contains("show");
        prefs[id] = isOpen;
        toggleButtons.forEach((btn) => btn.setAttribute("aria-expanded", isOpen ? "true" : "false"));
        writeJsonLs(MEDIA_COLLAPSE_KEY, prefs);
      };
      if (typeof desired === "boolean") {
        toggleButtons.forEach((btn) => btn.setAttribute("aria-expanded", desired ? "true" : "false"));
      }
      el.addEventListener("shown.bs.collapse", () => {
        syncStoredState();
      });
      el.addEventListener("hidden.bs.collapse", () => {
        syncStoredState();
      });
      toggleButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          window.requestAnimationFrame(syncStoredState);
        });
      });
    });

    const headers = Array.from(root.querySelectorAll(".card-header"));
    headers.forEach((header) => {
      const toggleBtn = header.querySelector(".media-card-collapse-toggle");
      if (!toggleBtn) return;
      header.classList.add("media-card-header-collapsible");
      header.addEventListener("click", (evt) => {
        const target = evt.target;
        if (target && target.closest && target.closest("button,a,input,select,textarea,label,[role='button']")) return;
        toggleBtn.click();
      });
    });

    root.classList.remove("media-collapse-pending");
  }

  function syncScenesColumnHeight() {
    if (!elScenesLayout || !elScenesPreviewCol || !elScenesSideCol || !elScenesOptionsScroll) return;
    if (window.matchMedia("(max-width: 991.98px)").matches) {
      elScenesLayout.style.removeProperty("height");
      elScenesLayout.style.removeProperty("max-height");
      elScenesSideCol.style.removeProperty("height");
      elScenesSideCol.style.removeProperty("max-height");
      elScenesOptionsScroll.style.removeProperty("max-height");
      return;
    }
    const layoutRect = elScenesLayout.getBoundingClientRect();
    const footer = document.querySelector("footer.footer");
    const footerH = Math.max(0, Math.ceil(footer?.getBoundingClientRect?.().height || 0));
    const viewportH = Math.max(0, window.innerHeight || document.documentElement.clientHeight || 0);
    let available = Math.max(220, Math.floor(viewportH - layoutRect.top - footerH - 8));
    elScenesLayout.style.height = `${available}px`;
    elScenesLayout.style.maxHeight = `${available}px`;

    // If page still overflows slightly, trim the layout by the exact overshoot.
    const doc = document.documentElement;
    const overshoot = Math.max(0, Math.ceil((doc.scrollHeight || 0) - (doc.clientHeight || viewportH)));
    if (overshoot > 0) {
      available = Math.max(220, available - overshoot - 2);
      elScenesLayout.style.height = `${available}px`;
      elScenesLayout.style.maxHeight = `${available}px`;
    }

    const h = available;
    if (!Number.isFinite(h) || h <= 0) return;
    elScenesSideCol.style.height = `${h}px`;
    elScenesSideCol.style.maxHeight = `${h}px`;
    elScenesOptionsScroll.style.maxHeight = `${h}px`;
  }

  function fitPreviewStage() {
    if (!elPreview) return;
    const wrap = elPreview.closest(".media-preview-stage-wrap");
    if (!wrap) return;
    const availW = Math.max(0, Math.floor(wrap.clientWidth || 0));
    const availH = Math.max(0, Math.floor(wrap.clientHeight || 0));
    if (availW <= 0 || availH <= 0) return;
    const ratio = Number(state.previewRatio || (16 / 9));
    const safeRatio = Number.isFinite(ratio) && ratio > 0 ? ratio : (16 / 9);
    let width = availW;
    let height = Math.round(width / safeRatio);
    if (height > availH) {
      height = availH;
      width = Math.round(height * safeRatio);
    }
    const finalW = Math.max(64, width);
    const finalH = Math.max(64, height);
    elPreview.style.width = `${finalW}px`;
    elPreview.style.height = `${finalH}px`;
    const referenceW = Math.max(1, Math.min(960, Number(state.previewDisplayW || 1920)));
    const referenceH = Math.max(1, Math.round(referenceW / safeRatio));
    const scale = Math.min(1, finalW / referenceW, finalH / referenceH);
    elPreview.style.setProperty("--media-preview-scale", String(scale));
  }

  function setUploadProgress(percent, text) {
    const p = Math.max(0, Math.min(100, Number(percent || 0)));
    if (elUploadProgressWrap) {
      elUploadProgressWrap.classList.remove("d-none");
      elUploadProgressWrap.setAttribute("aria-valuenow", String(Math.round(p)));
    }
    if (elUploadProgress) {
      elUploadProgress.style.width = `${Math.round(p)}%`;
      elUploadProgress.textContent = `${Math.round(p)}%`;
    }
    if (elUploadProgressText) {
      if (text) {
        elUploadProgressText.classList.remove("d-none");
        elUploadProgressText.textContent = String(text);
      } else {
        elUploadProgressText.classList.add("d-none");
        elUploadProgressText.textContent = "";
      }
    }
  }

  function resetUploadProgress() {
    if (elUploadProgressWrap) elUploadProgressWrap.classList.add("d-none");
    if (elUploadProgress) {
      elUploadProgress.style.width = "0%";
      elUploadProgress.textContent = "0%";
    }
    if (elUploadProgressText) {
      elUploadProgressText.classList.add("d-none");
      elUploadProgressText.textContent = "";
    }
  }

  function uploadFileWithProgress(file, progressCb) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      form.append("file", file);
      xhr.open("POST", "/api/media/assets/upload", true);
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && progressCb) progressCb(evt.loaded, evt.total);
      };
      xhr.onload = () => {
        let json = {};
        try { json = JSON.parse(xhr.responseText || "{}"); } catch (_) {}
        if (xhr.status >= 200 && xhr.status < 300 && json.ok !== false) resolve(json);
        else reject(new Error(json.error || `HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error("network_error"));
      xhr.send(form);
    });
  }

  async function uploadFiles(files) {
    const list = Array.from(files || []);
    if (!list.length || uploadInProgress) return;
    uploadInProgress = true;
    if (elUploadDropzone) elUploadDropzone.classList.add("is-uploading");
    try {
      const total = list.length;
      for (let i = 0; i < total; i += 1) {
        const file = list[i];
        setUploadProgress((i / total) * 100, `Uploading ${i + 1} of ${total}: ${file.name}`);
        await uploadFileWithProgress(file, (loaded, size) => {
          const per = size > 0 ? loaded / size : 0;
          const overall = ((i + per) / total) * 100;
          setUploadProgress(overall, `Uploading ${i + 1} of ${total}: ${file.name}`);
        });
      }
      setUploadProgress(100, `Uploaded ${total} file${total === 1 ? "" : "s"}.`);
      await loadAll(false);
      setDirty(true);
    } finally {
      uploadInProgress = false;
      if (elUploadDropzone) elUploadDropzone.classList.remove("is-uploading");
      window.setTimeout(resetUploadProgress, 400);
    }
  }

  function renderOutputEnvironment() {
    if (!elOutputEnv) return;
    const env = state.env || {};
    const tooling = env.tooling || {};
    const renderer = env.renderer || {};
    const tools = Array.isArray(tooling.tools) ? tooling.tools : [];
    const missingRequired = Array.isArray(tooling.missingRequired) ? tooling.missingRequired : [];
    const notes = Array.isArray(tooling.notes) ? tooling.notes : [];
    const fonts = Array.isArray(env.fonts) ? env.fonts : [];

    const statusClass = missingRequired.length ? "alert-warning" : "alert-success";
    const statusText = missingRequired.length
      ? `Runtime renderer not ready. Missing: ${missingRequired.join(", ")}`
      : `Runtime renderer ready on this host (${renderer.binary || renderer.name || "chromium"}).`;

    const rows = tools.map((t) => `
      <tr>
        <td><code>${esc(t.name || "")}</code></td>
        <td>${t.installed ? '<span class="badge text-bg-success">Installed</span>' : '<span class="badge text-bg-warning">Missing</span>'}${t.required ? ' <span class="badge text-bg-secondary">Required</span>' : ""}</td>
        <td class="text-wrap">${esc(t.purpose || "")}</td>
        <td class="text-wrap"><code>${esc(t.installCommand || "")}</code></td>
      </tr>
    `).join("");

    elOutputEnv.innerHTML = `
      <div class="alert ${statusClass} py-2 px-3 mt-3 mb-2">${esc(statusText)}</div>
      <div class="small text-secondary mb-2">Detected renderer binary: <code>${esc(renderer.binary || "")}</code></div>
      <div class="small text-secondary mb-2">Detected fonts for text overlays: <span class="badge text-bg-secondary">${fonts.length}</span></div>
      <div class="table-responsive">
        <table class="table table-sm mb-0 align-middle">
          <thead><tr><th>Tool</th><th>Status</th><th>Purpose</th><th>Install Hint</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="small text-secondary mt-2">${notes.map((n) => `<div>${esc(n)}</div>`).join("")}</div>
    `;
  }

  function renderAssets() {
    const rows = assets();
    if (elAssetCount) elAssetCount.textContent = String(rows.length);
    if (!elAssets) return;
    if (!rows.length) {
      elAssets.innerHTML = `<tr><td colspan="4" class="text-secondary text-center py-3">No media assets uploaded yet.</td></tr>`;
      return;
    }
    elAssets.innerHTML = rows.map((a) => `
      <tr data-asset-id="${esc(a.id)}">
        <td>
          <div class="media-asset-name-wrap" data-media-asset-name-wrap>
            <span class="media-asset-name-text" data-media-asset-name-text>${esc(a.displayName || a.filename || a.id)}</span>
            <button type="button" class="btn btn-outline-secondary btn-sm media-icon-btn media-asset-name-edit" data-media-asset-name-edit aria-label="Edit name" title="Edit name"><i class="fa fa-pen"></i></button>
          </div>
        </td>
        <td><span class="badge text-bg-secondary">${esc(String(a.kind || "media").toUpperCase())}</span></td>
        <td>${esc(a.createdAt || "-")}</td>
        <td class="text-end">
          <button type="button" class="btn btn-outline-secondary btn-sm media-icon-btn me-1" data-media-asset-preview title="Preview"><i class="fa fa-play"></i></button>
          <button type="button" class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" data-media-asset-delete aria-label="Remove asset" title="Remove asset"><i class="fa fa-trash"></i><span>Remove</span></button>
        </td>
      </tr>
    `).join("");
  }

  async function saveAssetDisplayName(assetId, displayName) {
    const cfg = state.config;
    if (!cfg) return;
    const row = (cfg.assets || []).find((a) => String(a?.id || "") === String(assetId || ""));
    if (!row) return;
    row.displayName = String(displayName || "").trim() || row.displayName || row.filename || row.id;
    await api("/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: cfg }),
    });
    const fresh = await api("/config");
    state.config = fresh.config || cfg;
    renderAssets();
  }

  function startAssetNameEdit(assetId) {
    const row = elAssets?.querySelector(`tr[data-asset-id="${assetId}"]`);
    if (!row) return;
    const wrap = row.querySelector("[data-media-asset-name-wrap]");
    if (!wrap) return;
    if (wrap.querySelector("input[data-media-asset-name-input]")) return;
    const current = String(wrap.querySelector("[data-media-asset-name-text]")?.textContent || "").trim();
    wrap.innerHTML = `<input type="text" class="form-control form-control-sm media-asset-name-input" data-media-asset-name-input value="${esc(current)}">`;
    const input = wrap.querySelector("[data-media-asset-name-input]");
    if (!input) return;

    const finish = async (commit) => {
      const next = String(input.value || "").trim() || current;
      if (!commit || next === current) {
        renderAssets();
        return;
      }
      try {
        await saveAssetDisplayName(assetId, next);
      } catch (err) {
        alert(`Rename failed: ${err.message}`);
        renderAssets();
      }
    };

    input.addEventListener("blur", () => { finish(true); }, { once: true });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        input.blur();
      }
      if (e.key === "Escape") {
        e.preventDefault();
        finish(false);
      }
    });
    input.focus();
    input.select();
  }

  function showAssetPreview(assetId) {
    const asset = assets().find((a) => String(a?.id || "") === String(assetId || ""));
    if (!asset || !elAssetPreviewModal || !elAssetPreviewStage) return;
    const src = `/api/media/assets/file/${encodeURIComponent(String(asset.id || ""))}`;
    const label = String(asset.displayName || asset.filename || asset.id || "Asset");
    if (elAssetPreviewTitle) elAssetPreviewTitle.textContent = `Preview: ${label}`;
    if (String(asset.kind || "").toLowerCase() === "video") {
      elAssetPreviewStage.innerHTML = `<video src="${src}" autoplay controls playsinline style="width:100%;height:100%;object-fit:contain"></video>`;
    } else {
      elAssetPreviewStage.innerHTML = `<img src="${src}" alt="${esc(label)}" style="width:100%;height:100%;object-fit:contain">`;
    }
    if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
      bootstrap.Modal.getOrCreateInstance(elAssetPreviewModal, { backdrop: true }).show();
    }
  }

  function renderDisplays() {
    const rows = displays();
    if (!elDisplays) return;
    if (!rows.length) {
      elDisplays.innerHTML = `<tr><td colspan="5" class="text-secondary text-center py-3">No displays configured.</td></tr>`;
      return;
    }
    elDisplays.innerHTML = rows.map((d, i) => `
      <tr data-display-idx="${i}">
        <td>${esc(d.name || d.id)}</td>
        <td><input class="form-control form-control-sm media-display-role" data-k="role" value="${esc(d.role || "")}"></td>
        <td>${Number(d.width || 0)}x${Number(d.height || 0)}</td>
        <td><input type="number" min="1" class="form-control form-control-sm" style="max-width:90px" data-k="screenIndex" value="${Number(d.screenIndex || i + 1)}"></td>
        <td><input type="checkbox" class="form-check-input" data-k="enabled" ${d.enabled ? "checked" : ""}></td>
      </tr>
    `).join("");
  }

  function renderScenes() {
    const rows = scenes();
    if (!elEditor || !elOverlaysEditor || !elPreview) return;
    if (!rows.length) {
      writeSelectedSceneId("");
      if (elSceneSelect) {
        elSceneSelect.innerHTML = `<option value="">No scenes yet</option>`;
        elSceneSelect.disabled = true;
      }
      if (elPreviewOpenFull) elPreviewOpenFull.disabled = true;
      if (elPreviewOpenWindow) elPreviewOpenWindow.disabled = true;
      if (elAddOverlay) elAddOverlay.disabled = true;
      elEditor.innerHTML = `<div class="text-secondary">Create a scene to start building.</div>`;
      elOverlaysEditor.innerHTML = `<div class="text-secondary">Create a scene to add overlays.</div>`;
      elPreview.innerHTML = "";
      return;
    }
    if (!sceneById(state.selectedSceneId)) state.selectedSceneId = String(rows[0].id || "");
    writeSelectedSceneId(state.selectedSceneId);
    const selected = sceneById(state.selectedSceneId);
    const ovCount = Array.isArray(selected?.overlays) ? selected.overlays.length : 0;
    if (state.selectedOverlayIdx >= ovCount) state.selectedOverlayIdx = -1;
    if (elSceneSelect) {
      elSceneSelect.disabled = false;
      elSceneSelect.innerHTML = rows.map((s) => `
        <option value="${esc(s.id)}">${esc(s.name || s.id)}</option>
      `).join("");
      elSceneSelect.value = String(state.selectedSceneId || rows[0]?.id || "");
    }
    if (elPreviewOpenFull) elPreviewOpenFull.disabled = false;
    if (elPreviewOpenWindow) elPreviewOpenWindow.disabled = false;
    if (elAddOverlay) elAddOverlay.disabled = false;

    renderSceneEditor();
    renderPreview();
    syncEditorOverlaySelection();
  }

  function collectVariableOptionsMap(extraKeys = []) {
    const map = new Map();
    const add = (value, label) => {
      const v = String(value || "").trim();
      if (!v) return;
      if (map.has(v)) return;
      map.set(v, String(label || v));
    };

    [
      ["score", "Score"],
      ["ball", "Ball"],
      ["player", "Player"],
    ].forEach(([v, l]) => add(v, l));

    const runtimeValues = state.runtime?.overlayValues;
    if (runtimeValues && typeof runtimeValues === "object") {
      Object.keys(runtimeValues).forEach((k) => add(k, k));
    }

    scenes().forEach((s) => {
      const ovs = Array.isArray(s?.overlays) ? s.overlays : [];
      ovs.forEach((ov) => {
        const v = String(ov?.valueKey || "").trim();
        if (v) add(v, v);
      });
    });

    (Array.isArray(extraKeys) ? extraKeys : []).forEach((k) => add(k, k));
    return map;
  }

  function firstAvailableVariableKey() {
    const map = collectVariableOptionsMap();
    const entries = Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
    return String(entries[0]?.[0] || "").trim();
  }

  function renderVariableOptions(selectedKey) {
    const key = String(selectedKey || "").trim();
    const map = collectVariableOptionsMap(key ? [key] : []);

    const options = Array.from(map.entries())
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([value, label]) => `<option value="${esc(value)}" ${key === value ? "selected" : ""}>${esc(label)}</option>`);
    return options.join("");
  }

  function renderFontOptions(selectedFont) {
    const fallbackFonts = [
      "Arial",
      "Helvetica",
      "Verdana",
      "Trebuchet MS",
      "Tahoma",
      "Times New Roman",
      "Georgia",
      "Courier New",
      "Monaco",
      "Menlo",
      "Noto Sans",
      "Noto Serif",
      "Roboto",
      "Ubuntu",
      "sans-serif",
      "serif",
      "monospace",
    ];
    const detected = Array.isArray(state.env?.fonts) ? state.env.fonts : [];
    const seen = new Set();
    const fonts = [];
    [...detected, ...fallbackFonts].forEach((f) => {
      const name = String(f || "").trim();
      if (!name) return;
      const key = name.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      fonts.push(name);
    });
    const selected = String(selectedFont || "").trim();
    const options = ['<option value="">Default</option>'];
    fonts.forEach((f) => {
      const name = String(f || "").trim();
      if (!name) return;
      options.push(`<option value="${esc(name)}" ${selected === name ? "selected" : ""}>${esc(name)}</option>`);
    });
    return options.join("");
  }

  function renderSceneEditor() {
    const scene = sceneById(state.selectedSceneId);
    if (!elEditor || !elOverlaysEditor) return;
    if (!scene) {
      elEditor.innerHTML = `<div class="text-secondary">Select a scene.</div>`;
      elOverlaysEditor.innerHTML = `<div class="text-secondary">Select a scene.</div>`;
      return;
    }

    const displayOpts = displays().map((d) => `<option value="${esc(d.id)}" ${String(scene.targetDisplay || "") === String(d.id || "") ? "selected" : ""}>${esc(displayLabel(d))}</option>`).join("");
    const assetOpts = ['<option value="">Select asset…</option>'].concat(assets().map((a) => `<option value="${esc(a.id)}" ${String(scene.baseAssetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`)).join("");
    const imageAssets = assets().filter((a) => String(a.kind || "").toLowerCase() !== "video");
    const overlays = Array.isArray(scene.overlays) ? scene.overlays : [];

    const overlaysHtml = overlays.map((ov, idx) => {
      const ovId = String(ov.id || `overlay_${idx + 1}`);
      const ovType = normalizeOverlayType(ov.type);
      const hasType = !!ovType;
      const isText = ovType === "text";
      const isFrame = ovType === "frame";
      const isImage = ovType === "image";
      const textMode = String(ov.valueKey || "").trim() ? "variable" : "fixed";
      const textAlign = normalizeTextAlign(ov.textAlign);
      const bgMode = String(ov.bgColor || "").trim().toLowerCase() === "transparent" ? "transparent" : "solid";
      const collapsed = !!state.overlayCollapsed[ovId];

      return `
      <div class="media-overlay-row ${idx === state.selectedOverlayIdx ? "border-primary" : ""} ${collapsed ? "is-collapsed" : ""}" data-overlay-idx="${idx}">
        <div class="media-overlay-header">
          <div class="media-overlay-title">${esc(ov.name || `Overlay ${idx + 1}`)}</div>
          <div class="d-flex align-items-center gap-1">
            <button type="button" class="btn btn-outline-secondary btn-sm" data-overlay-move="up" ${idx === 0 ? "disabled" : ""} title="Move up"><i class="fa fa-chevron-up"></i></button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-overlay-move="down" ${idx === overlays.length - 1 ? "disabled" : ""} title="Move down"><i class="fa fa-chevron-down"></i></button>
            <button type="button" class="btn btn-sm media-overlay-toggle-btn" data-overlay-toggle title="Expand/collapse"><i class="fa ${collapsed ? "fa-chevron-right" : "fa-chevron-down"}"></i></button>
          </div>
        </div>

        <div class="row g-2 ${collapsed ? "d-none" : ""}">
          <div class="col-12">
            <div class="row g-2 align-items-center">
              <div class="col-12 col-lg-3"><label class="form-label mb-0">Name</label></div>
              <div class="col-12 col-lg-9">
                <input class="form-control form-control-sm" data-k="name" value="${esc(ov.name || `Overlay ${idx + 1}`)}" placeholder="Layer name">
              </div>
            </div>
          </div>
          <div class="col-12">
            <div class="row g-2 align-items-center">
              <div class="col-12 col-lg-3"><label class="form-label mb-0">Type</label></div>
              <div class="col-12 col-lg-9">
                <select class="form-select form-select-sm" data-k="type">
                  <option value="" ${hasType ? "" : "selected"}>Select type...</option>
                  <option value="text" ${ovType === "text" ? "selected" : ""}>Text</option>
                  <option value="image" ${isImage ? "selected" : ""}>Image</option>
                  <option value="frame" ${isFrame ? "selected" : ""}>Frame</option>
                </select>
              </div>
            </div>
          </div>

          ${!hasType ? "" : isText ? `
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Text Source</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="textMode">
                    <option value="fixed" ${textMode === "fixed" ? "selected" : ""}>Fixed Text</option>
                    <option value="variable" ${textMode === "variable" ? "selected" : ""}>Variable</option>
                  </select>
                  <div class="mt-2">
                    ${textMode === "fixed"
                      ? `<input class="form-control form-control-sm" data-k="text" value="${esc(ov.text || "")}" placeholder="Enter text">`
                      : `<select class="form-select form-select-sm" data-k="valueKeyPreset">${renderVariableOptions(ov.valueKey)}</select>`
                    }
                  </div>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Position</label></div>
                <div class="col-12 col-lg-9">
                  <div class="row g-2">
                    <div class="col-12 col-lg-4"><div class="input-group input-group-sm"><span class="input-group-text">X</span><input type="number" step="0.25" class="form-control" data-k="xPct" value="${q025(ov.xPct || 0)}"></div></div>
                    <div class="col-12 col-lg-4"><div class="input-group input-group-sm"><span class="input-group-text">Y</span><input type="number" step="0.25" class="form-control" data-k="yPct" value="${q025(ov.yPct || 0)}"></div></div>
                    <div class="col-12 col-lg-4"><div class="input-group input-group-sm"><span class="input-group-text">Z</span><input type="number" step="0.25" class="form-control" data-k="zIndex" value="${q025(ov.zIndex || (idx + 1))}"></div></div>
                  </div>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Text Align</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="textAlign">
                    <option value="left" ${textAlign === "left" ? "selected" : ""}>Left</option>
                    <option value="center" ${textAlign === "center" ? "selected" : ""}>Centre</option>
                    <option value="right" ${textAlign === "right" ? "selected" : ""}>Right</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Text Effects</label></div>
                <div class="col-12 col-lg-9">
                  <div class="w-100">
                    ${renderTextEffectsOptions(ov.textEffects)}
                  </div>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Size</label></div>
                <div class="col-12 col-lg-9">
                  <div class="row g-2">
                    <div class="col-12 col-lg-6"><div class="input-group input-group-sm"><span class="input-group-text">W</span><input type="number" step="0.25" class="form-control" data-k="wPct" value="${q025(ov.wPct || 20)}"></div></div>
                    <div class="col-12 col-lg-6"><div class="input-group input-group-sm"><span class="input-group-text">H</span><input type="number" step="0.25" class="form-control" data-k="hPct" value="${q025(ov.hPct || 8)}"></div></div>
                  </div>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Rotate</label></div>
                <div class="col-12 col-lg-9">
                  <label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2">
                    <span class="small text-secondary">Angle</span>
                    <span class="small text-secondary" data-k-label="rotateDeg">${Math.round(Number(ov.rotateDeg || 0))}\u00b0</span>
                  </label>
                  <input type="range" class="form-range" min="-180" max="180" step="1" data-k="rotateDeg" value="${Math.round(Number(ov.rotateDeg || 0))}">
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Opacity</label></div>
                <div class="col-12 col-lg-9">
                  <label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2">
                    <span class="small text-secondary">Level</span>
                    <span class="small text-secondary" data-k-label="opacity">${Number(ov.opacity ?? 1).toFixed(1)}</span>
                  </label>
                  <input type="range" class="form-range" min="0" max="1" step="0.1" data-k="opacity" value="${Number(ov.opacity ?? 1)}">
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Background</label></div>
                <div class="col-12 col-lg-9">
                  <div class="row g-2">
                    <div class="col-12 col-lg-6">
                      <select class="form-select form-select-sm" data-k="bgMode">
                        <option value="transparent" ${bgMode === "transparent" ? "selected" : ""}>Transparent</option>
                        <option value="solid" ${bgMode === "solid" ? "selected" : ""}>Color</option>
                      </select>
                    </div>
                    <div class="col-12 col-lg-6">${bgMode === "solid" ? `<input type="color" class="form-control form-control-color form-control-sm" data-k="bgColor" value="${esc(ov.bgColor || "#000000")}">` : ""}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Font Family</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="fontFamily">${renderFontOptions(ov.fontFamily)}</select>
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Font Size</label></div>
                <div class="col-12 col-lg-9">
                  <input type="number" class="form-control form-control-sm" data-k="fontSizePx" value="${Number(ov.fontSizePx || 24)}">
                </div>
              </div>
            </div>

            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Font Color</label></div>
                <div class="col-12 col-lg-9">
                  <input type="color" class="form-control form-control-color form-control-sm" data-k="color" value="${esc(ov.color || "#ffffff")}">
                </div>
              </div>
            </div>
          ` : isFrame ? `
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Overlay Image</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="assetId"><option value="">Select image…</option>${imageAssets.map((a) => `<option value="${esc(a.id)}" ${String(ov.assetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`).join("")}</select>
                </div>
              </div>
            </div>
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Fit</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="fit">
                    <option value="cover" ${String(ov.fit || "contain") === "cover" ? "selected" : ""}>Cover</option>
                    <option value="contain" ${String(ov.fit || "contain") === "contain" ? "selected" : ""}>Contain</option>
                    <option value="fill" ${String(ov.fit || "contain") === "fill" ? "selected" : ""}>Fill</option>
                    <option value="none" ${String(ov.fit || "contain") === "none" ? "selected" : ""}>None</option>
                    <option value="scale-down" ${String(ov.fit || "contain") === "scale-down" ? "selected" : ""}>Scale Down</option>
                  </select>
                </div>
              </div>
            </div>
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Opacity</label></div>
                <div class="col-12 col-lg-9 d-flex align-items-center gap-2">
                  <input type="range" class="form-range m-0 flex-grow-1" min="0" max="1" step="0.1" data-k="opacity" value="${Number(ov.opacity ?? 1)}">
                  <span class="small text-secondary text-nowrap" data-k-label="opacity">${Number(ov.opacity ?? 1).toFixed(1)}</span>
                </div>
              </div>
            </div>
          ` : `
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Overlay Image</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="assetId"><option value="">Select image…</option>${imageAssets.map((a) => `<option value="${esc(a.id)}" ${String(ov.assetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`).join("")}</select>
                </div>
              </div>
            </div>
            <div class="col-12">
              <div class="row g-2 align-items-center">
                <div class="col-12 col-lg-3"><label class="form-label mb-0">Fit</label></div>
                <div class="col-12 col-lg-9">
                  <select class="form-select form-select-sm" data-k="fit">
                    <option value="cover" ${String(ov.fit || "contain") === "cover" ? "selected" : ""}>Cover</option>
                    <option value="contain" ${String(ov.fit || "contain") === "contain" ? "selected" : ""}>Contain</option>
                    <option value="fill" ${String(ov.fit || "contain") === "fill" ? "selected" : ""}>Fill</option>
                    <option value="none" ${String(ov.fit || "contain") === "none" ? "selected" : ""}>None</option>
                    <option value="scale-down" ${String(ov.fit || "contain") === "scale-down" ? "selected" : ""}>Scale Down</option>
                  </select>
                </div>
              </div>
            </div>
            <div class="col-6 col-lg-3"><label class="form-label">X</label><input type="number" step="0.25" class="form-control form-control-sm" data-k="xPct" value="${q025(ov.xPct || 0)}"></div>
            <div class="col-6 col-lg-3"><label class="form-label">Y</label><input type="number" step="0.25" class="form-control form-control-sm" data-k="yPct" value="${q025(ov.yPct || 0)}"></div>
            <div class="col-6 col-lg-3"><label class="form-label">W</label><input type="number" step="0.25" class="form-control form-control-sm" data-k="wPct" value="${q025(ov.wPct || 20)}"></div>
            <div class="col-6 col-lg-3"><label class="form-label">H</label><input type="number" step="0.25" class="form-control form-control-sm" data-k="hPct" value="${q025(ov.hPct || 8)}"></div>
            <div class="col-12 col-lg-3"><label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2"><span>Rotate</span><span class="small text-secondary" data-k-label="rotateDeg">${Math.round(Number(ov.rotateDeg || 0))}\u00b0</span></label><input type="range" class="form-range" min="-180" max="180" step="1" data-k="rotateDeg" value="${Math.round(Number(ov.rotateDeg || 0))}"></div>
            <div class="col-12 col-lg-3"><label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2"><span>Opacity</span><span class="small text-secondary" data-k-label="opacity">${Number(ov.opacity ?? 1).toFixed(1)}</span></label><input type="range" class="form-range" min="0" max="1" step="0.1" data-k="opacity" value="${Number(ov.opacity ?? 1)}"></div>
          `}
          <div class="col-12 d-flex justify-content-end mt-2">
            <button type="button" class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" data-overlay-delete title="Remove overlay"><i class="fa fa-trash"></i><span>Remove</span></button>
          </div>
        </div>
      </div>
      `;
    }).join("");

    elEditor.innerHTML = `
      <div class="row g-2 mb-3">
        <div class="col-12">
          <label class="form-label">Name</label>
          <input class="form-control form-control-sm" data-scene-k="name" value="${esc(scene.name || "")}">
        </div>

        <div class="col-12">
          <label class="form-label">Target Display</label>
          <select class="form-select form-select-sm" data-scene-k="targetDisplay">${displayOpts}</select>
        </div>

        <div class="col-12">
          <label class="form-label">Base Asset</label>
          <select class="form-select form-select-sm" data-scene-k="baseAssetId">${assetOpts}</select>
        </div>

        <div class="col-12">
          <div class="form-check form-switch m-0">
            <input class="form-check-input" type="checkbox" data-scene-k="loop" ${scene.loop ? "checked" : ""}>
            <label class="form-check-label">Loop</label>
          </div>
        </div>

        <div class="col-12">
          <div class="form-check form-switch m-0">
            <input class="form-check-input" type="checkbox" data-scene-k="includeAudio" ${scene.mute ? "" : "checked"}>
            <label class="form-check-label">Include Audio</label>
          </div>
        </div>

        <div class="col-12">
          <button type="button" class="btn btn-outline-danger btn-sm w-100 d-inline-flex align-items-center justify-content-center gap-1" id="media-delete-scene"><i class="fa fa-trash"></i><span>Remove</span></button>
        </div>
      </div>
    `;
    elOverlaysEditor.innerHTML = `<div id="media-overlays-wrap">${overlaysHtml}</div>`;
  }

  function renderPreview() {
    const scene = sceneById(state.selectedSceneId);
    if (!elPreview) return;
    if (!scene) {
      elPreview.innerHTML = "";
      return;
    }
    const prevVideo = elPreview.querySelector("video#media-preview-video");
    const prevVideoState = prevVideo ? {
      assetId: String(prevVideo.getAttribute("data-asset-id") || "").trim(),
      currentTime: Number(prevVideo.currentTime || 0),
      paused: !!prevVideo.paused,
      ended: !!prevVideo.ended,
      muted: !!prevVideo.muted,
      playbackRate: Number(prevVideo.playbackRate || 1),
    } : null;

    const display = sceneDisplay(scene);
    const w = Math.max(64, Number(display?.width || 1920));
    const h = Math.max(64, Number(display?.height || 1080));
    state.previewRatio = w / h;
    state.previewDisplayW = w;
    state.previewDisplayH = h;
    elPreview.style.aspectRatio = `${w} / ${h}`;

    const asset = assets().find((a) => String(a.id || "") === String(scene.baseAssetId || ""));
    const assetSrc = asset ? `/api/media/assets/file/${encodeURIComponent(asset.id)}` : "";
    const base = asset
      ? (String(asset.kind || "").toLowerCase() === "video"
          ? `<video class="media-preview-base" id="media-preview-video" data-asset-id="${esc(asset.id || "")}" src="${assetSrc}" ${scene.loop ? "loop" : ""} ${scene.mute ? "muted" : ""} playsinline></video>`
          : `<img class="media-preview-base" src="${assetSrc}" alt="">`)
      : `<div class="media-preview-base d-flex align-items-center justify-content-center text-secondary">No base asset selected</div>`;

    const overlays = Array.isArray(scene.overlays) ? scene.overlays : [];
    const ovHtml = overlays.map((ov, idx) => {
      const ovType = normalizeOverlayType(ov.type);
      if (!ovType) return "";
      const stackZ = Math.max(1, overlays.length - idx);
      const text = String(ov.valueKey || "").trim() ? `{{${ov.valueKey}}}` : String(ov.text || "");
      const textAlign = normalizeTextAlign(ov.textAlign);
      const justify = textAlign === "left" ? "flex-start" : (textAlign === "right" ? "flex-end" : "center");
      const fx = textEffectStyles(ovType, ov.textEffects, ov.color);
      const bg = String(ov.bgColor || "").trim() || "transparent";
      const selected = idx === state.selectedOverlayIdx ? " is-selected" : "";
      const imageSrc = ov.assetId ? `/api/media/assets/file/${encodeURIComponent(String(ov.assetId))}` : "";
      const fit = ["cover", "contain", "fill", "none", "scale-down"].includes(String(ov.fit || "").toLowerCase())
        ? String(ov.fit).toLowerCase()
        : "contain";

      const inner = ovType === "frame"
        ? (imageSrc ? `<img class="media-preview-frame-image" src="${imageSrc}" style="object-fit:${fit};" alt="">` : "")
        : (ovType === "image"
            ? (imageSrc ? `<img class="media-preview-overlay-image" src="${imageSrc}" style="object-fit:${fit};" alt="">` : "")
            : esc(text));

      const handles = selected && ovType !== "frame"
        ? `<span class="media-preview-handle media-preview-handle-resize" data-overlay-handle="resize"></span>
           <span class="media-preview-handle media-preview-handle-rotate" data-overlay-handle="rotate"></span>`
        : "";

      const frameClass = ovType === "frame" ? " media-preview-overlay-frame" : "";
      const imageClass = ovType === "image" ? " media-preview-overlay-image-layer" : "";
      const textClass = ovType === "text" ? " media-preview-overlay-text-layer" : "";
      const resolvedBg = ovType === "frame" || ovType === "image" ? "transparent" : bg;
      return `<div class="media-preview-overlay${frameClass}${imageClass}${textClass}${selected}" data-overlay-idx="${idx}" style="
        left:${ovType === "frame" ? 0 : Number(ov.xPct || 0)}%;
        top:${ovType === "frame" ? 0 : Number(ov.yPct || 0)}%;
        width:${ovType === "frame" ? 100 : Number(ov.wPct || 20)}%;
        height:${ovType === "frame" ? 100 : Number(ov.hPct || 8)}%;
        transform:rotate(${ovType === "frame" ? 0 : Number(ov.rotateDeg || 0)}deg) scale(${ovType === "frame" ? 1 : Number(ov.scale || 1)});
        opacity:${Number(ov.opacity ?? 1)};
        color:${esc(ovType === "frame" ? "#fff" : (ov.color || "#fff"))};
        background:${esc(resolvedBg)};
        text-align:${textAlign};
        justify-content:${justify};
        font-weight:${fx.fontWeight};
        font-style:${fx.fontStyle};
        text-transform:${fx.textTransform};
        letter-spacing:${fx.letterSpacing};
        text-decoration:${fx.textDecoration};
        text-shadow:${fx.textShadow};
        font-size:calc(${Number(ovType === "frame" ? 24 : (ov.fontSizePx || 24))}px * var(--media-preview-scale, 1));
        font-family:${esc(ovType === "frame" ? "inherit" : (String(ov.fontFamily || "").replaceAll(";", "") || "inherit"))};
        z-index:${stackZ};
      ">${inner}${handles}</div>`;
    }).join("");

    elPreview.innerHTML = `${base}${ovHtml}`;
    fitPreviewStage();
    if (!elPreview.classList.contains("is-ready")) {
      window.requestAnimationFrame(() => {
        fitPreviewStage();
        elPreview.classList.add("is-ready");
      });
    }
    const nextVideo = elPreview.querySelector("video#media-preview-video");
    attachPreviewVideoHandlers(nextVideo);
    if (nextVideo && prevVideoState && prevVideoState.assetId && prevVideoState.assetId === String(scene.baseAssetId || "")) {
      const restore = () => {
        try {
          const dur = Number(nextVideo.duration || 0);
          let t = Number(prevVideoState.currentTime || 0);
          if (Number.isFinite(dur) && dur > 0) t = clamp(t, 0, Math.max(0, dur - 0.05));
          if (Number.isFinite(t) && t >= 0) nextVideo.currentTime = t;
          if (Number.isFinite(prevVideoState.playbackRate) && prevVideoState.playbackRate > 0) {
            nextVideo.playbackRate = prevVideoState.playbackRate;
          }
          nextVideo.muted = prevVideoState.muted;
          if (state.previewShouldPlay && !prevVideoState.ended) nextVideo.play().catch(() => {});
          else nextVideo.pause();
        } catch (_) {}
      };
      if (nextVideo.readyState >= 1) restore();
      else nextVideo.addEventListener("loadedmetadata", restore, { once: true });
    }
    const baseMedia = elPreview.querySelector("video#media-preview-video, img.media-preview-base");
    if (baseMedia) {
      const markReady = () => {
        baseMedia.classList.add("is-ready");
      };
      if (baseMedia.tagName === "VIDEO") {
        const v = /** @type {HTMLVideoElement} */ (baseMedia);
        if (v.readyState >= 1) markReady();
        else v.addEventListener("loadedmetadata", markReady, { once: true });
      } else {
        const img = /** @type {HTMLImageElement} */ (baseMedia);
        if (img.complete) markReady();
        else img.addEventListener("load", markReady, { once: true });
      }
    }
  }

  function updatePreviewOverlayNode(idx) {
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !Array.isArray(scene.overlays) || !elPreview) return false;
    const ov = scene.overlays[idx];
    if (!ov) return false;
    const node = elPreview.querySelector(`.media-preview-overlay[data-overlay-idx="${idx}"]`);
    if (!node) return false;
    const ovType = normalizeOverlayType(ov.type);
    if (!ovType) return false;
    const selected = idx === state.selectedOverlayIdx;
    const textAlign = normalizeTextAlign(ov.textAlign);
    const justify = textAlign === "left" ? "flex-start" : (textAlign === "right" ? "flex-end" : "center");
    const fx = textEffectStyles(ovType, ov.textEffects, ov.color);
    const imageSrc = ov.assetId ? `/api/media/assets/file/${encodeURIComponent(String(ov.assetId))}` : "";
    const fit = ["cover", "contain", "fill", "none", "scale-down"].includes(String(ov.fit || "").toLowerCase())
      ? String(ov.fit).toLowerCase()
      : "contain";
    const resolvedBg = ovType === "frame" || ovType === "image" ? "transparent" : (String(ov.bgColor || "").trim() || "transparent");

    node.classList.toggle("media-preview-overlay-frame", ovType === "frame");
    node.classList.toggle("media-preview-overlay-image-layer", ovType === "image");
    node.classList.toggle("media-preview-overlay-text-layer", ovType === "text");
    node.classList.toggle("is-selected", selected);
    node.style.left = `${ovType === "frame" ? 0 : Number(ov.xPct || 0)}%`;
    node.style.top = `${ovType === "frame" ? 0 : Number(ov.yPct || 0)}%`;
    node.style.width = `${ovType === "frame" ? 100 : Number(ov.wPct || 20)}%`;
    node.style.height = `${ovType === "frame" ? 100 : Number(ov.hPct || 8)}%`;
    node.style.transform = `rotate(${ovType === "frame" ? 0 : Number(ov.rotateDeg || 0)}deg) scale(${ovType === "frame" ? 1 : Number(ov.scale || 1)})`;
    node.style.opacity = `${Number(ov.opacity ?? 1)}`;
    node.style.background = resolvedBg;
    node.style.color = `${ovType === "frame" ? "#fff" : (ov.color || "#fff")}`;
    node.style.textAlign = textAlign;
    node.style.justifyContent = justify;
    node.style.fontWeight = fx.fontWeight;
    node.style.fontStyle = fx.fontStyle;
    node.style.textTransform = fx.textTransform;
    node.style.letterSpacing = fx.letterSpacing;
    node.style.textDecoration = fx.textDecoration;
    node.style.textShadow = fx.textShadow;
    node.style.fontSize = `calc(${Number(ovType === "frame" ? 24 : (ov.fontSizePx || 24))}px * var(--media-preview-scale, 1))`;
    node.style.fontFamily = `${ovType === "frame" ? "inherit" : (String(ov.fontFamily || "").replaceAll(";", "") || "inherit")}`;
    node.style.zIndex = `${Math.max(1, scene.overlays.length - idx)}`;

    const handles = selected && ovType !== "frame"
      ? '<span class="media-preview-handle media-preview-handle-resize" data-overlay-handle="resize"></span><span class="media-preview-handle media-preview-handle-rotate" data-overlay-handle="rotate"></span>'
      : "";
    if (ovType === "frame") {
      node.innerHTML = imageSrc ? `<img class="media-preview-frame-image" src="${imageSrc}" style="object-fit:${fit};" alt="">` : "";
      return true;
    }
    if (ovType === "image") {
      node.innerHTML = (imageSrc ? `<img class="media-preview-overlay-image" src="${imageSrc}" style="object-fit:${fit};" alt="">` : "") + handles;
      return true;
    }
    const text = String(ov.valueKey || "").trim() ? `{{${ov.valueKey}}}` : String(ov.text || "");
    node.innerHTML = `${esc(text)}${handles}`;
    return true;
  }

  function syncSceneFromEditor() {
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !elEditor || !elOverlaysEditor) return;

    scene.name = String(elEditor.querySelector('[data-scene-k="name"]')?.value || "").trim() || scene.name;
    scene.targetDisplay = String(elEditor.querySelector('[data-scene-k="targetDisplay"]')?.value || "").trim();
    scene.baseAssetId = String(elEditor.querySelector('[data-scene-k="baseAssetId"]')?.value || "").trim();
    scene.loop = !!elEditor.querySelector('[data-scene-k="loop"]')?.checked;
    scene.mute = !elEditor.querySelector('[data-scene-k="includeAudio"]')?.checked;

    const overlays = [];
    elOverlaysEditor.querySelectorAll("[data-overlay-idx]").forEach((row, i) => {
      const idx = Number(row.getAttribute("data-overlay-idx") || i);
      const existing = Array.isArray(scene.overlays) ? scene.overlays[idx] : null;
      const textMode = String(row.querySelector('[data-k="textMode"]')?.value || "").trim();
      const valueKeyPreset = String(row.querySelector('[data-k="valueKeyPreset"]')?.value || "").trim();
      const existingValueKey = String(existing?.valueKey || "").trim();
      const fallbackVariableKey = firstAvailableVariableKey();
      const resolvedValueKey = textMode === "variable" ? (valueKeyPreset || existingValueKey || fallbackVariableKey) : "";
      const bgMode = String(row.querySelector('[data-k="bgMode"]')?.value || "").trim();
      const existingBg = String(existing?.bgColor || "").trim();
      const bgInputValue = String(row.querySelector('[data-k="bgColor"]')?.value || "").trim();

      const ov = {
        id: String(existing?.id || uid("overlay")).trim(),
        name: String(row.querySelector('[data-k="name"]')?.value || "").trim() || `Overlay ${i + 1}`,
        type: normalizeOverlayType(row.querySelector('[data-k="type"]')?.value),
        valueKey: resolvedValueKey,
        text: String(row.querySelector('[data-k="text"]')?.value || "").trim(),
        textAlign: normalizeTextAlign(row.querySelector('[data-k="textAlign"]')?.value || existing?.textAlign || "center"),
        textEffects: selectedTextEffectsFromRow(row, existing?.textEffects || []),
        xPct: q025(Number(row.querySelector('[data-k="xPct"]')?.value || 0)),
        yPct: q025(Number(row.querySelector('[data-k="yPct"]')?.value || 0)),
        wPct: q025(Number(row.querySelector('[data-k="wPct"]')?.value || 20)),
        hPct: q025(Number(row.querySelector('[data-k="hPct"]')?.value || 8)),
        rotateDeg: Number(row.querySelector('[data-k="rotateDeg"]')?.value || 0),
        scale: Number(existing?.scale || 1),
        opacity: Number(row.querySelector('[data-k="opacity"]')?.value || 1),
        fontSizePx: Number(row.querySelector('[data-k="fontSizePx"]')?.value || 24),
        fontFamily: String(row.querySelector('[data-k="fontFamily"]')?.value || "").trim(),
        color: String(row.querySelector('[data-k="color"]')?.value || "#ffffff"),
        bgColor: bgMode === "transparent" ? "transparent" : (bgInputValue || (existingBg && existingBg.toLowerCase() !== "transparent" ? existingBg : "#000000")),
        assetId: String(row.querySelector('[data-k="assetId"]')?.value || "").trim(),
        fit: ["cover", "contain", "fill", "none", "scale-down"].includes(String(row.querySelector('[data-k="fit"]')?.value || "").trim().toLowerCase())
          ? String(row.querySelector('[data-k="fit"]')?.value || "").trim().toLowerCase()
          : "contain",
        zIndex: q025(Number(row.querySelector('[data-k="zIndex"]')?.value || (i + 1))),
      };

      if (ov.type === "frame") {
        ov.valueKey = "";
        ov.text = "";
        ov.textAlign = "center";
        ov.xPct = 0;
        ov.yPct = 0;
        ov.wPct = 100;
        ov.hPct = 100;
        ov.rotateDeg = 0;
        ov.scale = 1;
        ov.color = "#ffffff";
        ov.bgColor = "transparent";
        ov.fontSizePx = 24;
        ov.fontFamily = "";
        ov.textEffects = [];
      }
      if (ov.type === "text" && textMode === "fixed") {
        ov.valueKey = "";
      }
      if (ov.type !== "text") {
        ov.textEffects = [];
      }

      overlays.push(ov);
    });

    scene.overlays = overlays;
  }

  function beginDrag(mode, idx, evt) {
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !Array.isArray(scene.overlays)) return;
    const ov = scene.overlays[idx];
    if (!ov) return;
    const rect = elPreview.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const centerX = rect.left + ((Number(ov.xPct || 0) + (Number(ov.wPct || 20) / 2)) / 100) * rect.width;
    const centerY = rect.top + ((Number(ov.yPct || 0) + (Number(ov.hPct || 8) / 2)) / 100) * rect.height;
    const startPointerDeg = Math.atan2(evt.clientY - centerY, evt.clientX - centerX) * (180 / Math.PI);

    dragState = {
      mode,
      idx,
      rect,
      startX: evt.clientX,
      startY: evt.clientY,
      centerX,
      centerY,
      startPointerDeg,
      start: {
        xPct: Number(ov.xPct || 0),
        yPct: Number(ov.yPct || 0),
        wPct: Number(ov.wPct || 20),
        hPct: Number(ov.hPct || 8),
        rotateDeg: Number(ov.rotateDeg || 0),
      },
    };
    state.selectedOverlayIdx = idx;
    renderPreview();
  }

  function onDragMove(evt) {
    if (!dragState) return;
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !Array.isArray(scene.overlays)) return;
    const ov = scene.overlays[dragState.idx];
    if (!ov) return;

    const dxPct = ((evt.clientX - dragState.startX) / dragState.rect.width) * 100;
    const dyPct = ((evt.clientY - dragState.startY) / dragState.rect.height) * 100;

    if (dragState.mode === "move") {
      const x = clamp(dragState.start.xPct + dxPct, 0, 100);
      const y = clamp(dragState.start.yPct + dyPct, 0, 100);
      ov.xPct = q025(qPxPercent(x, dragState.rect.width));
      ov.yPct = q025(qPxPercent(y, dragState.rect.height));
    } else if (dragState.mode === "resize") {
      const nextWPct = q025(clamp(dragState.start.wPct + dxPct, 0.25, 100));
      const nextHPct = q025(clamp(dragState.start.hPct + dyPct, 0.25, 100));
      ov.wPct = nextWPct;
      ov.hPct = nextHPct;
    } else if (dragState.mode === "rotate") {
      const curPointerDeg = Math.atan2(evt.clientY - dragState.centerY, evt.clientX - dragState.centerX) * (180 / Math.PI);
      const deltaDeg = normalizeAngleDelta(curPointerDeg - dragState.startPointerDeg);
      ov.rotateDeg = dragState.start.rotateDeg + deltaDeg;
    }

    setDirty(true);
    if (!updatePreviewOverlayNode(dragState.idx)) renderPreview();
  }

  function onDragUp() {
    if (!dragState) return;
    dragState = null;
    renderSceneEditor();
  }

  function renderRuntime() {
    if (!elRuntime) return;
    const active = Array.isArray(state.runtime?.engine?.active) ? state.runtime.engine.active : [];
    if (!active.length) {
      elRuntime.innerHTML = `<div class="text-secondary small">No active scenes.</div>`;
      return;
    }
    elRuntime.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm mb-0 align-middle">
          <thead><tr><th>Scene</th><th>Display</th><th>PID</th><th class="text-end">Action</th></tr></thead>
          <tbody>
            ${active.map((a) => `
              <tr>
                <td>${esc(a.sceneId || "")}</td>
                <td>${esc(a.displayId || "")}</td>
                <td>${Number(a.pid || 0) || "-"}</td>
                <td class="text-end"><button type="button" class="btn btn-outline-danger btn-sm" data-runtime-stop-scene="${esc(a.sceneId || "")}">Stop</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function loadAll(refreshDisplays = false) {
    const [cfgRes, envRes, stateRes] = await Promise.allSettled([
      api("/config"),
      api("/environment"),
      api("/state"),
    ]);

    if (cfgRes.status === "fulfilled" && cfgRes.value?.config) {
      state.config = cfgRes.value.config;
    } else if (!state.config) {
      state.config = { settings: {}, displays: [], assets: [], scenes: [] };
    }

    if (envRes.status === "fulfilled") state.env = envRes.value;
    if (stateRes.status === "fulfilled") state.runtime = stateRes.value.state;

    if (refreshDisplays && state.env?.displays?.length) {
      state.config.displays = state.env.displays;
      setDirty(true);
    }

    renderAssets();
    renderDisplays();
    renderOutputEnvironment();
    renderScenes();
    renderRuntime();
    fitPreviewStage();
    syncScenesColumnHeight();
    if (!refreshDisplays) setDirty(false);
  }

  async function saveConfig() {
    try {
      // Ensure the current editor state (including focused fields/selects) is flushed to config.
      syncSceneFromEditor();
      await api("/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: state.config }),
      });
      await loadAll(false);
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    }
  }

  saveButtons.forEach((btn) => btn.addEventListener("click", saveConfig));

  elUploadBrowse?.addEventListener("click", () => { if (!uploadInProgress) elUploadFile?.click(); });
  elUploadFile?.addEventListener("change", async () => {
    const files = Array.from(elUploadFile.files || []);
    if (!files.length) return;
    try { await uploadFiles(files); } catch (err) { alert(`Upload failed: ${err.message}`); }
    elUploadFile.value = "";
  });

  if (elUploadDropzone) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach((name) => {
      elUploadDropzone.addEventListener(name, (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
      });
    });
    ["dragenter", "dragover"].forEach((name) => {
      elUploadDropzone.addEventListener(name, () => {
        if (!uploadInProgress) elUploadDropzone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((name) => {
      elUploadDropzone.addEventListener(name, () => {
        elUploadDropzone.classList.remove("is-dragover");
      });
    });
    elUploadDropzone.addEventListener("drop", async (evt) => {
      if (uploadInProgress) return;
      const files = Array.from(evt.dataTransfer?.files || []);
      if (!files.length) return;
      try { await uploadFiles(files); } catch (err) { alert(`Upload failed: ${err.message}`); }
    });
    elUploadDropzone.addEventListener("keydown", (evt) => {
      if (uploadInProgress) return;
      if (evt.key === "Enter" || evt.key === " ") {
        evt.preventDefault();
        elUploadFile?.click();
      }
    });
    elUploadDropzone.addEventListener("click", (evt) => {
      if (uploadInProgress) return;
      if (evt.target && evt.target.closest && evt.target.closest("#media-upload-browse")) return;
      elUploadFile?.click();
    });
  }

  elAssets?.addEventListener("click", async (e) => {
    const row = e.target.closest("tr[data-asset-id]");
    if (!row) return;
    const assetId = String(row.getAttribute("data-asset-id") || "");
    if (!assetId) return;

    if (e.target.closest("[data-media-asset-preview]")) {
      showAssetPreview(assetId);
      return;
    }
    if (e.target.closest("[data-media-asset-name-text]") || e.target.closest("[data-media-asset-name-edit]")) {
      startAssetNameEdit(assetId);
      return;
    }
    if (!e.target.closest("[data-media-asset-delete]")) return;

    const ok = await askConfirm("Remove this asset?", {
      title: "Remove Asset",
      confirmLabel: "Remove",
      confirmClass: "btn-danger",
    });
    if (!ok) return;

    try {
      await api("/assets/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assetId }),
      });
      await loadAll(false);
      setDirty(true);
    } catch (err) {
      alert(`Remove failed: ${err.message}`);
    }
  });

  elAssetPreviewModal?.addEventListener("hidden.bs.modal", () => {
    if (!elAssetPreviewStage) return;
    const video = elAssetPreviewStage.querySelector("video");
    if (video) {
      try {
        video.pause();
        video.removeAttribute("src");
        video.load();
      } catch (_) {}
    }
    elAssetPreviewStage.innerHTML = "";
  });

  elDetectDisplays?.addEventListener("click", async () => {
    await loadAll(true);
  });

  elDisplays?.addEventListener("input", (e) => {
    const row = e.target.closest("tr[data-display-idx]");
    if (!row) return;
    const idx = Number(row.getAttribute("data-display-idx"));
    const d = displays()[idx];
    if (!d) return;
    const key = e.target.getAttribute("data-k");
    if (!key) return;
    if (key === "enabled") d.enabled = !!e.target.checked;
    else if (key === "screenIndex") d.screenIndex = Math.max(1, Number(e.target.value || 1));
    else d[key] = e.target.value;
    setDirty(true);
    renderPreview();
  });

  elSceneSelect?.addEventListener("change", () => {
    const sceneId = String(elSceneSelect.value || "").trim();
    if (!sceneId) return;
    state.selectedSceneId = sceneId;
    writeSelectedSceneId(sceneId);
    state.previewShouldPlay = true;
    state.selectedOverlayIdx = -1;
    renderScenes();
  });

  elPreviewOpenFull?.addEventListener("click", async () => {
    const sceneId = String(state.selectedSceneId || "").trim();
    if (!sceneId) return;
    try {
      await launchScene(sceneId, "fullscreen");
    } catch (err) {
      alert(`Open fullscreen failed: ${err.message}`);
    }
  });

  elPreviewOpenWindow?.addEventListener("click", async () => {
    const sceneId = String(state.selectedSceneId || "").trim();
    if (!sceneId) return;
    try {
      await launchScene(sceneId, "windowed");
    } catch (err) {
      alert(`Open window failed: ${err.message}`);
    }
  });

  elAddScene?.addEventListener("click", () => {
    state.config.scenes = scenes();
    const firstDisplay = displays()[0];
    const firstAsset = assets()[0];
    const scene = {
      id: uid("scene"),
      name: `Scene ${scenes().length + 1}`,
      targetDisplay: String(firstDisplay?.id || firstDisplay?.role || "backbox"),
      baseAssetId: String(firstAsset?.id || ""),
      loop: true,
      mute: true,
      overlays: [],
    };
    state.config.scenes.push(scene);
    state.selectedSceneId = scene.id;
    state.previewShouldPlay = true;
    state.selectedOverlayIdx = -1;
    setDirty(true);
    renderScenes();
  });

  elEditor?.addEventListener("input", (e) => {
    if (!e.target.closest("[data-scene-k]")) return;

    syncSceneFromEditor();
    setDirty(true);
    renderPreview();
  });

  elOverlaysEditor?.addEventListener("input", (e) => {
    if (!e.target.closest("[data-overlay-idx]")) return;
    const row = e.target.closest("[data-overlay-idx]");
    const idx = Number(row?.getAttribute("data-overlay-idx"));
    if (e.target.matches('input[type="range"][data-k="rotateDeg"]')) {
      const label = row?.querySelector('[data-k-label="rotateDeg"]');
      if (label) label.textContent = `${Math.round(Number(e.target.value || 0))}\u00b0`;
    }
    if (e.target.matches('input[type="range"][data-k="opacity"]')) {
      const label = row?.querySelector('[data-k-label="opacity"]');
      if (label) label.textContent = Number(e.target.value || 0).toFixed(1);
    }
    syncSceneFromEditor();
    setDirty(true);
    const structureChange = e.target.matches('[data-k="type"],[data-k="textMode"],[data-k="bgMode"],[data-k="valueKeyPreset"]');
    if (structureChange) {
      renderSceneEditor();
      renderPreview();
      return;
    }
    if (!(Number.isFinite(idx) && updatePreviewOverlayNode(idx))) renderPreview();
  });

  elEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-scene-k]")) return;
    syncSceneFromEditor();
    setDirty(true);
    renderPreview();
  });

  elOverlaysEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-overlay-idx]")) return;
    syncSceneFromEditor();
    setDirty(true);
    if (e.target.matches('[data-k="type"],[data-k="textMode"],[data-k="bgMode"],[data-k="valueKeyPreset"]')) renderSceneEditor();
    renderPreview();
  });

  elEditor?.addEventListener("click", async (e) => {
    const scene = sceneById(state.selectedSceneId);
    if (!scene) return;

    if (e.target.closest("#media-delete-scene")) {
      const ok = await askConfirm("Remove this scene?", {
        title: "Remove Scene",
        confirmLabel: "Remove",
        confirmClass: "btn-danger",
      });
      if (!ok) return;
      state.config.scenes = scenes().filter((s) => String(s.id || "") !== String(scene.id || ""));
      state.selectedSceneId = state.config.scenes[0]?.id || null;
      setDirty(true);
      renderScenes();
    }
  });

  elAddOverlay?.addEventListener("click", () => {
    const scene = sceneById(state.selectedSceneId);
    if (!scene) return;
    scene.overlays = Array.isArray(scene.overlays) ? scene.overlays : [];
    scene.overlays.push({
      id: uid("overlay"),
      name: `Overlay ${scene.overlays.length + 1}`,
      type: "",
      text: "Score",
      valueKey: "",
      textAlign: "center",
      textEffects: [],
      xPct: 5,
      yPct: 5,
      wPct: 25,
      hPct: 10,
      rotateDeg: 0,
      scale: 1,
      opacity: 1,
      color: "#ffffff",
      bgColor: "#000000",
      fontSizePx: 28,
      fontFamily: "",
      assetId: "",
      fit: "contain",
      zIndex: scene.overlays.length + 1,
    });
    state.selectedOverlayIdx = scene.overlays.length - 1;
    setDirty(true);
    renderSceneEditor();
    renderPreview();
  });

  elOverlaysEditor?.addEventListener("click", async (e) => {
    const scene = sceneById(state.selectedSceneId);
    if (!scene) return;

    const toggleOverlayRow = (row) => {
      if (!row) return false;
      syncSceneFromEditor();
      const idx = Number(row.getAttribute("data-overlay-idx"));
      const ov = Array.isArray(scene.overlays) ? scene.overlays[idx] : null;
      const ovId = String(ov?.id || "");
      if (!ovId) return false;
      state.overlayCollapsed[ovId] = !state.overlayCollapsed[ovId];
      writeJsonLs(MEDIA_OVERLAY_COLLAPSE_KEY, state.overlayCollapsed);
      renderSceneEditor();
      return true;
    };

    if (e.target.closest("[data-overlay-toggle]")) {
      const row = e.target.closest("[data-overlay-idx]");
      if (toggleOverlayRow(row)) return;
    }

    const header = e.target.closest(".media-overlay-header");
    if (header && !e.target.closest("button,a,input,select,textarea,label,[role='button']")) {
      const row = header.closest("[data-overlay-idx]");
      if (toggleOverlayRow(row)) return;
    }

    if (e.target.closest("[data-overlay-move]")) {
      syncSceneFromEditor();
      const row = e.target.closest("[data-overlay-idx]");
      if (!row) return;
      const idx = Number(row.getAttribute("data-overlay-idx"));
      const direction = String(e.target.closest("[data-overlay-move]")?.getAttribute("data-overlay-move") || "");
      const next = direction === "up" ? idx - 1 : idx + 1;
      if (!Array.isArray(scene.overlays) || idx < 0 || next < 0 || next >= scene.overlays.length) return;
      const [moved] = scene.overlays.splice(idx, 1);
      scene.overlays.splice(next, 0, moved);
      scene.overlays.forEach((ov, i) => { ov.zIndex = i + 1; });
      state.selectedOverlayIdx = next;
      setDirty(true);
      renderSceneEditor();
      renderPreview();
      return;
    }

    if (e.target.closest("[data-overlay-delete]")) {
      const ok = await askConfirm("Remove this overlay?", {
        title: "Remove Overlay",
        confirmLabel: "Remove",
        confirmClass: "btn-danger",
      });
      if (!ok) return;
      scene.overlays = Array.isArray(scene.overlays) ? scene.overlays : [];
      syncSceneFromEditor();
      const row = e.target.closest("[data-overlay-idx]");
      if (!row) return;
      const idx = Number(row.getAttribute("data-overlay-idx"));
      scene.overlays.splice(idx, 1);
      if (state.selectedOverlayIdx >= scene.overlays.length) state.selectedOverlayIdx = scene.overlays.length - 1;
      setDirty(true);
      renderSceneEditor();
      renderPreview();
      return;
    }

    const row = e.target.closest("[data-overlay-idx]");
      if (row) {
      const idx = Number(row.getAttribute("data-overlay-idx"));
      if (Number.isFinite(idx) && idx !== state.selectedOverlayIdx) {
        state.selectedOverlayIdx = idx;
        syncEditorOverlaySelection();
        renderPreview();
      }
    } else if (e.target.closest("#media-overlays-wrap")) {
      clearOverlaySelection();
    }
  });

  elPreviewPlay?.addEventListener("click", async (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    if (previewToggleBusy) return;
    const v = activePreviewVideo();
    if (!v) return;
    previewToggleBusy = true;
    try {
      const scene = sceneById(state.selectedSceneId);
      v.muted = !!scene?.mute;
      const shouldPause = !v.paused && !v.ended;
      if (shouldPause) {
        state.previewShouldPlay = false;
        v.pause();
      } else {
        state.previewShouldPlay = true;
        if (v.ended) v.currentTime = 0;
        await v.play().catch(() => {});
      }
    } finally {
      previewToggleBusy = false;
      updatePreviewControlsUi();
    }
  });

  elPreviewStop?.addEventListener("click", () => {
    const v = activePreviewVideo();
    if (!v) return;
    state.previewShouldPlay = false;
    try {
      v.pause();
      v.currentTime = 0;
    } catch (_) {}
    updatePreviewControlsUi();
  });

  elPreviewScrub?.addEventListener("pointerdown", () => {
    previewScrubbing = true;
  });
  elPreviewScrub?.addEventListener("pointerup", () => {
    previewScrubbing = false;
    updatePreviewControlsUi();
  });
  elPreviewScrub?.addEventListener("change", () => {
    const v = activePreviewVideo();
    if (!v || !Number.isFinite(v.duration) || v.duration <= 0) return;
    const ratio = clamp(Number(elPreviewScrub.value || 0) / 1000, 0, 1);
    v.currentTime = ratio * Number(v.duration || 0);
    previewScrubbing = false;
    updatePreviewControlsUi();
  });
  elPreviewScrub?.addEventListener("input", () => {
    const v = activePreviewVideo();
    if (!v || !Number.isFinite(v.duration) || v.duration <= 0) return;
    const ratio = clamp(Number(elPreviewScrub.value || 0) / 1000, 0, 1);
    const t = ratio * Number(v.duration || 0);
    if (elPreviewTime) elPreviewTime.textContent = `${fmtTime(t)} / ${fmtTime(v.duration || 0)}`;
    if (previewScrubbing) {
      try { v.currentTime = t; } catch (_) {}
    }
  });

  elPreview?.addEventListener("mousedown", (evt) => {
    const overlay = evt.target.closest(".media-preview-overlay");
    if (!overlay) {
      selectFrameOverlayOrClear();
      return;
    }
    const idx = Number(overlay.getAttribute("data-overlay-idx"));
    if (!Number.isFinite(idx)) return;
    const scene = sceneById(state.selectedSceneId);
    const ov = Array.isArray(scene?.overlays) ? scene.overlays[idx] : null;
    const ovType = normalizeOverlayType(ov?.type);

    if (ovType === "frame") {
      if (state.selectedOverlayIdx !== idx) {
        state.selectedOverlayIdx = idx;
        syncEditorOverlaySelection();
        renderPreview();
      }
      return;
    }

    const handle = evt.target.closest("[data-overlay-handle]");
    if (handle) {
      const mode = String(handle.getAttribute("data-overlay-handle") || "");
      if (mode === "resize" || mode === "rotate") {
        evt.preventDefault();
        beginDrag(mode, idx, evt);
      }
      return;
    }

    evt.preventDefault();
    beginDrag("move", idx, evt);
  });

  document.addEventListener("mousemove", onDragMove);
  document.addEventListener("mouseup", onDragUp);
  document.addEventListener("keydown", (evt) => {
    if (evt.key !== "Escape") return;
    clearOverlaySelection();
  });

  elRuntimeRefresh?.addEventListener("click", async () => {
    try {
      const res = await api("/state");
      state.runtime = res.state || null;
      renderRuntime();
    } catch (err) {
      alert(`Refresh failed: ${err.message}`);
    }
  });

  elRuntime?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-runtime-stop-scene]");
    if (!btn) return;
    const sceneId = String(btn.getAttribute("data-runtime-stop-scene") || "").trim();
    if (!sceneId) return;
    try {
      await api("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sceneId }),
      });
      const st = await api("/state");
      state.runtime = st.state || null;
      renderRuntime();
    } catch (err) {
      alert(`Stop failed: ${err.message}`);
    }
  });

  elStopAll?.addEventListener("click", async () => {
    try {
      await api("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const st = await api("/state");
      state.runtime = st.state || null;
      renderRuntime();
    } catch (err) {
      alert(`Stop all failed: ${err.message}`);
    }
  });

  root.addEventListener("dblclick", async (e) => {
    const sceneBtn = e.target.closest("[data-scene-id]");
    if (!sceneBtn) return;
    const sceneId = String(sceneBtn.getAttribute("data-scene-id") || "").trim();
    if (!sceneId) return;
    try {
      await launchScene(sceneId, "fullscreen");
    } catch (err) {
      alert(`Play failed: ${err.message}`);
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (!state.dirty) return;
    e.preventDefault();
    e.returnValue = "";
  });

  window.addEventListener("resize", () => {
    fitPreviewStage();
    syncScenesColumnHeight();
  });

  state.overlayCollapsed = readJsonLs(MEDIA_OVERLAY_COLLAPSE_KEY, {});
  state.selectedSceneId = readSelectedSceneId() || null;
  wireTabs();
  wireCardCollapses();
  // Apply scene-pane sizing immediately so first paint doesn't start "short"
  // and then jump after async load completes.
  syncScenesColumnHeight();
  loadAll(false).catch((err) => {
    console.error(err);
    alert(`Media module failed to load: ${err.message}`);
  });
})();
