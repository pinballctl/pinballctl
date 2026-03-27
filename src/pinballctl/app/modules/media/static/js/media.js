(() => {
  const root = document.getElementById("media-page");
  if (!root) return;

  const MEDIA_TAB_KEY = "pinballctl.media.lastTab.v1";
  const MEDIA_COLLAPSE_KEY = "pinballctl.media.collapse.v1";
  const MEDIA_SELECTED_SCENE_KEY = "pinballctl.media.selectedScene.v1";
  const MEDIA_SELECTED_OVERLAY_KEY = "pinballctl.media.selectedOverlay.v1";
  const MEDIA_FONT_STYLE_ID = "media-custom-fonts-style";

  const state = {
    config: null,
    env: null,
    runtime: null,
    selectedGodotRuntimeId: null,
    selectedSceneId: null,
    selectedOverlayId: null,
    selectedOverlayIdx: -1,
    selectedLayerIdx: -1,
    dirty: false,
    previewRatio: 16 / 9,
    previewDisplayW: 1920,
    previewDisplayH: 1080,
    previewShouldPlay: false,
    overlayPreviewShouldPlay: false,
    assetSortKey: "name",
    assetSortDir: "asc",
  };

  const $ = (sel) => root.querySelector(sel);
  const saveButtons = Array.from(root.querySelectorAll("[data-media-save]"));
  const elAssets = $("#media-assets-table");
  const elAssetCount = $("#media-asset-count-pill");
  const elAssetSortNameIndicator = $("#media-asset-sort-name-indicator");
  const elAssetSortAddedIndicator = $("#media-asset-sort-added-indicator");
  const elAssetPreviewModal = document.getElementById("media-asset-preview-modal");
  const elRuntimeWarningModal = document.getElementById("media-runtime-warning-modal");
  const elAssetPreviewStage = document.getElementById("media-asset-preview-stage");
  const elAssetPreviewTitle = document.getElementById("media-asset-preview-title");
  const elUploadDropzone = $("#media-upload-dropzone");
  const elUploadBrowse = $("#media-upload-browse");
  const elUploadFile = $("#media-upload-file");
  const elUploadProgressWrap = $("#media-upload-progress-wrap");
  const elUploadProgress = $("#media-upload-progress");
  const elUploadProgressText = $("#media-upload-progress-text");
  const elFontUploadDropzone = $("#media-font-upload-dropzone");
  const elFontUploadBrowse = $("#media-font-upload-browse");
  const elFontUploadFile = $("#media-font-upload-file");
  const elFontsTable = $("#media-fonts-table");
  const elFontFilter = $("#media-font-filter");
  const elFontSourceFilter = $("#media-font-source-filter");
  const elDetectDisplays = $("#media-detect-displays");
  const elDisplays = $("#media-displays-table");
  const elDefaultsEditor = $("#media-defaults-editor");
  const elSceneSelect = $("#media-scene-select");
  const elEditor = $("#media-scene-editor");
  const elOverlaySelect = $("#media-overlay-select");
  const elOverlayEditor = $("#media-overlay-editor");
  const elOverlayLayersEditor = $("#media-overlay-layers-editor");
  const elPreview = $("#media-preview-stage");
  const elOverlayPreview = $("#media-overlay-preview-stage");
  const elScenesPane = root.querySelector("#media-pane-scenes");
  const elScenesLayout = elScenesPane?.querySelector(".media-scenes-layout") || null;
  const elScenesPreviewCol = elScenesPane?.querySelector(".media-scenes-preview-col") || null;
  const elScenesSideCol = elScenesPane?.querySelector(".media-scenes-side-col") || null;
  const elScenesOptionsScroll = elScenesPane?.querySelector(".media-scenes-options-scroll") || null;
  const elOverlayPane = root.querySelector("#media-pane-overlays");
  const elOverlayLayout = elOverlayPane?.querySelector(".media-scenes-layout") || null;
  const elOverlayPreviewCol = elOverlayPane?.querySelector(".media-scenes-preview-col") || null;
  const elOverlaySideCol = elOverlayPane?.querySelector(".media-scenes-side-col") || null;
  const elOverlayOptionsScroll = elOverlayPane?.querySelector(".media-scenes-options-scroll") || null;
  const elPreviewPlay = $("#media-preview-play");
  const elPreviewStop = $("#media-preview-stop");
  const elPreviewScrub = $("#media-preview-scrub");
  const elPreviewTime = $("#media-preview-time");
  const elOverlayPreviewPlay = $("#media-overlay-preview-play");
  const elOverlayPreviewStop = $("#media-overlay-preview-stop");
  const elOverlayPreviewScrub = $("#media-overlay-preview-scrub");
  const elOverlayPreviewTime = $("#media-overlay-preview-time");
  const elPreviewOpenFull = $("#media-preview-open-full");
  const elPreviewOpenWindow = $("#media-preview-open-window");
  const elAddScene = $("#media-add-scene");
  const elAddOverlay = $("#media-add-overlay");
  const elRuntime = $("#media-runtime-table");
  const elRuntimeEnginePanel = $("#media-runtime-engine-panel");
  const elRuntimeGodotPanel = $("#media-runtime-godot-panel");
  const elRuntimeFooter = $("#media-runtime-footer");
  const elStopAll = $("#media-stop-all");

  let uploadInProgress = false;
  let fontUploadInProgress = false;
  let dragState = null;
  let previewVideo = null;
  let overlayPreviewVideo = null;
  let previewRenderer = null;
  let overlayPreviewRenderer = null;
  let previewResizeRaf = 0;
  let previewScrubbing = false;
  let overlayPreviewScrubbing = false;
  let previewToggleBusy = false;
  let overlayPreviewToggleBusy = false;
  let overlayDragRenderRaf = 0;
  let overlayDragPendingIdx = -1;
  let overlayDragPendingLayer = null;
  let runtimePollTimer = 0;
  let assetConversionPollTimer = 0;
  let runtimeRefreshInFlight = false;
  let assetRefreshInFlight = false;

  async function refreshRuntimeState() {
    if (runtimeRefreshInFlight) return;
    runtimeRefreshInFlight = true;
    const runtimeId = String(state.selectedGodotRuntimeId || "").trim();
    try {
      const [stateRes, envRes, statusRes] = await Promise.allSettled([
        api("/state"),
        api("/environment"),
        api(`/runtime/status${runtimeId ? `?runtimeId=${encodeURIComponent(runtimeId)}` : ""}`),
      ]);
      if (stateRes.status === "fulfilled") state.runtime = stateRes.value.state || null;
      if (envRes.status === "fulfilled") state.env = envRes.value || null;
      if (statusRes.status === "fulfilled" && state.runtime) state.runtime.godotStatus = statusRes.value || null;
      if (!state.selectedGodotRuntimeId) {
        state.selectedGodotRuntimeId = currentGodotRuntimeId();
      }
      renderRuntimeTable();
      updateGodotRuntimePanelStatus();
    } finally {
      runtimeRefreshInFlight = false;
    }
  }

  function godotRuntimeTargets() {
    const targets = state.env?.runtimeTargets || state.runtime?.godot?.targets || state.runtime?.godotStatus?.runtimeTargets || [];
    return Array.isArray(targets) ? targets : [];
  }

  function currentGodotRuntimeId() {
    const selected = String(state.selectedGodotRuntimeId || "").trim();
    if (selected) return selected;
    const defaultId = String(state.runtime?.godot?.defaultRuntimeId || state.runtime?.godotStatus?.runtimeId || godotRuntimeTargets()[0]?.id || "").trim();
    return defaultId;
  }

  function currentMediaTabTarget() {
    const activeBtn = root.querySelector('[data-bs-toggle="tab"][data-bs-target^="#media-pane-"].active');
    return String(activeBtn?.getAttribute("data-bs-target") || "").trim();
  }

  function syncRuntimePolling() {
    if (runtimePollTimer) {
      window.clearInterval(runtimePollTimer);
      runtimePollTimer = 0;
    }
    if (currentMediaTabTarget() !== "#media-pane-runtime") return;
    runtimePollTimer = window.setInterval(() => {
      if (document.visibilityState === "hidden") return;
      refreshRuntimeState().catch(() => {});
    }, 1000);
  }

  function assetConversionState(asset) {
    const row = asset && typeof asset === "object" ? asset : {};
    const conv = row.conversion && typeof row.conversion === "object" ? row.conversion : null;
    const sourceFormat = String((conv && conv.originalFormat) || row.sourceFormat || row.filename?.split(".").pop() || "").trim().toLowerCase();
    const playbackFormat = String((conv && conv.playbackFormat) || row.playbackFormat || sourceFormat || "").trim().toLowerCase();
    const progressPct = Math.max(0, Math.min(100, Number((conv && conv.progressPct) || 0) || 0));
    const status = String((conv && conv.status) || (String(row.kind || "").toLowerCase() === "video" ? "queued" : "ready")).trim().toLowerCase();
    return { status, progressPct, sourceFormat, playbackFormat };
  }

  function assetFormatLabel(asset) {
    const info = assetConversionState(asset);
    const src = info.sourceFormat ? info.sourceFormat.toUpperCase() : "UNKNOWN";
    const dst = info.playbackFormat ? info.playbackFormat.toUpperCase() : src;
    return src === dst ? src : `${src} -> ${dst}`;
  }

  function assetStatusHtml(asset) {
    const info = assetConversionState(asset);
    if (String(asset?.kind || "").toLowerCase() !== "video") {
      return '<span class="badge text-bg-success">Ready</span>';
    }
    if (info.status === "converted" || info.status === "ready") {
      return '<span class="badge text-bg-success"><i class="fa fa-check me-1"></i>Converted</span>';
    }
    if (info.status === "converting") {
      return `<span class="badge text-bg-primary"><span class="spinner-border spinner-border-sm me-1" style="width:.75rem;height:.75rem;" aria-hidden="true"></span>${esc(String(info.progressPct))}%</span>`;
    }
    if (info.status === "finalizing") {
      return '<span class="badge text-bg-info text-dark"><span class="spinner-border spinner-border-sm me-1" style="width:.75rem;height:.75rem;" aria-hidden="true"></span>Finalizing</span>';
    }
    if (info.status === "queued" || info.status === "outdated") {
      return '<span class="badge text-bg-warning text-dark"><span class="spinner-border spinner-border-sm me-1" style="width:.75rem;height:.75rem;" aria-hidden="true"></span>Queued</span>';
    }
    if (info.status === "missing") {
      return '<span class="badge text-bg-danger">Missing Source</span>';
    }
    if (info.status === "failed") {
      return '<span class="badge text-bg-danger">Failed</span>';
    }
    return `<span class="badge text-bg-secondary">${esc(info.status || "Unknown")}</span>`;
  }

  function hasActiveAssetConversions() {
    return assets().some((asset) => {
      const info = assetConversionState(asset);
      return String(asset?.kind || "").toLowerCase() === "video" && ["queued", "outdated", "converting", "finalizing"].includes(info.status);
    });
  }

  async function refreshAssetConfig() {
    const cfgRes = await api("/config");
    if (cfgRes?.config) {
      state.config = cfgRes.config;
      renderAssets();
    }
  }

  function syncAssetConversionPolling() {
    if (assetConversionPollTimer) {
      window.clearInterval(assetConversionPollTimer);
      assetConversionPollTimer = 0;
    }
    const libraryOpen = currentMediaTabTarget() === "#media-pane-library";
    if (!hasActiveAssetConversions() && !libraryOpen) return;
    assetConversionPollTimer = window.setInterval(() => {
      if (document.visibilityState === "hidden") return;
      if (!hasActiveAssetConversions() && currentMediaTabTarget() !== "#media-pane-library") return;
      if (assetRefreshInFlight) return;
      assetRefreshInFlight = true;
      refreshAssetConfig()
        .catch(() => {})
        .finally(() => {
          assetRefreshInFlight = false;
        });
    }, 2000);
  }

  function syncLayoutColumnHeight(layoutEl, sideColEl, optionsScrollEl) {
    if (!layoutEl || !sideColEl || !optionsScrollEl) return;
    if (window.matchMedia("(max-width: 991.98px)").matches) {
      layoutEl.style.removeProperty("height");
      layoutEl.style.removeProperty("max-height");
      sideColEl.style.removeProperty("height");
      sideColEl.style.removeProperty("max-height");
      optionsScrollEl.style.removeProperty("height");
      optionsScrollEl.style.removeProperty("max-height");
      return;
    }
    const layoutRect = layoutEl.getBoundingClientRect();
    const footer = document.querySelector("footer.footer");
    const footerH = Math.max(0, Math.ceil(footer?.getBoundingClientRect?.().height || 0));
    const viewportH = Math.max(0, window.innerHeight || document.documentElement.clientHeight || 0);
    let available = Math.max(220, Math.floor(viewportH - layoutRect.top - footerH - 8));
    layoutEl.style.height = `${available}px`;
    layoutEl.style.maxHeight = `${available}px`;

    const doc = document.documentElement;
    const overshoot = Math.max(0, Math.ceil((doc.scrollHeight || 0) - (doc.clientHeight || viewportH)));
    if (overshoot > 0) {
      available = Math.max(220, available - overshoot - 2);
      layoutEl.style.height = `${available}px`;
      layoutEl.style.maxHeight = `${available}px`;
    }

    if (!Number.isFinite(available) || available <= 0) return;
    sideColEl.style.height = `${available}px`;
    sideColEl.style.maxHeight = `${available}px`;
    optionsScrollEl.style.height = `${available}px`;
    optionsScrollEl.style.maxHeight = `${available}px`;
  }

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

  function activeOverlayPreviewVideo() {
    const inDom = elOverlayPreview?.querySelector("video#media-overlay-preview-video") || null;
    if (!inDom) return null;
    if (overlayPreviewVideo !== inDom) overlayPreviewVideo = inDom;
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

  function updateOverlayPreviewControlsUi() {
    const hasVideo = !!overlayPreviewVideo;
    const dur = hasVideo && Number.isFinite(overlayPreviewVideo.duration) ? Math.max(0, Number(overlayPreviewVideo.duration || 0)) : 0;
    const cur = hasVideo ? Math.max(0, Number(overlayPreviewVideo.currentTime || 0)) : 0;
    const paused = !hasVideo || !!overlayPreviewVideo.paused || !!overlayPreviewVideo.ended;

    if (elOverlayPreviewPlay) {
      elOverlayPreviewPlay.disabled = !hasVideo;
      elOverlayPreviewPlay.setAttribute("aria-disabled", hasVideo ? "false" : "true");
      elOverlayPreviewPlay.innerHTML = paused ? '<i class="fa fa-play"></i>' : '<i class="fa fa-pause"></i>';
      elOverlayPreviewPlay.title = paused ? "Play" : "Pause";
      elOverlayPreviewPlay.setAttribute("aria-label", paused ? "Play" : "Pause");
    }
    if (elOverlayPreviewStop) {
      elOverlayPreviewStop.disabled = !hasVideo;
      elOverlayPreviewStop.setAttribute("aria-disabled", hasVideo ? "false" : "true");
    }
    if (elOverlayPreviewScrub) {
      elOverlayPreviewScrub.disabled = !hasVideo;
      elOverlayPreviewScrub.setAttribute("aria-disabled", hasVideo ? "false" : "true");
      if (!overlayPreviewScrubbing) {
        const ratio = dur > 0 ? Math.max(0, Math.min(1, cur / dur)) : 0;
        elOverlayPreviewScrub.value = String(Math.round(ratio * 1000));
      }
    }
    if (elOverlayPreviewTime) {
      elOverlayPreviewTime.textContent = `${fmtTime(cur)} / ${fmtTime(dur)}`;
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

  function detachOverlayPreviewVideoHandlers() {
    if (!overlayPreviewVideo) return;
    overlayPreviewVideo.onplay = null;
    overlayPreviewVideo.onplaying = null;
    overlayPreviewVideo.onpause = null;
    overlayPreviewVideo.onended = null;
    overlayPreviewVideo.ontimeupdate = null;
    overlayPreviewVideo.onloadedmetadata = null;
    overlayPreviewVideo.onseeked = null;
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

  function attachOverlayPreviewVideoHandlers(video) {
    detachOverlayPreviewVideoHandlers();
    overlayPreviewVideo = video || null;
    if (!overlayPreviewVideo) {
      updateOverlayPreviewControlsUi();
      return;
    }
    overlayPreviewVideo.onplay = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.onplaying = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.onpause = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.onended = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.ontimeupdate = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.onloadedmetadata = () => updateOverlayPreviewControlsUi();
    overlayPreviewVideo.onseeked = () => updateOverlayPreviewControlsUi();
    updateOverlayPreviewControlsUi();
  }

  function pauseAtFirstFrame(video) {
    if (!video) return;
    const apply = () => {
      try {
        video.pause();
        const dur = Number(video.duration || 0);
        const target = Number.isFinite(dur) && dur > 0
          ? Math.min(0.05, Math.max(0.001, dur - 0.001))
          : 0.033;
        video.currentTime = target;
      } catch (_) {}
      updatePreviewControlsUi();
      updateOverlayPreviewControlsUi();
    };
    if (video.readyState >= 1) apply();
    else video.addEventListener("loadedmetadata", apply, { once: true });
  }

  function stopPreviewPlayback() {
    state.previewShouldPlay = false;
    const video = activePreviewVideo();
    if (!video) {
      updatePreviewControlsUi();
      return;
    }
    try {
      video.pause();
    } catch (_) {}
    updatePreviewControlsUi();
  }

  function stopOverlayPreviewPlayback() {
    state.overlayPreviewShouldPlay = false;
    const video = activeOverlayPreviewVideo();
    if (!video) {
      updateOverlayPreviewControlsUi();
      return;
    }
    try {
      video.pause();
    } catch (_) {}
    updateOverlayPreviewControlsUi();
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
    if (t === "frame") return "image";
    return ["text", "image"].includes(t) ? t : "";
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

  function readSelectedOverlayId() {
    try {
      return String(localStorage.getItem(MEDIA_SELECTED_OVERLAY_KEY) || "").trim();
    } catch (_) {
      return "";
    }
  }

  function writeSelectedOverlayId(overlayId) {
    try {
      const val = String(overlayId || "").trim();
      if (!val) localStorage.removeItem(MEDIA_SELECTED_OVERLAY_KEY);
      else localStorage.setItem(MEDIA_SELECTED_OVERLAY_KEY, val);
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
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 8000);
    const req = { ...(opts || {}), signal: controller.signal };
    try {
      const r = await fetch(`/api/media${path}`, req);
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.ok === false) throw new Error(j.error || `HTTP ${r.status}`);
      return j;
    } catch (err) {
      if (err?.name === "AbortError") throw new Error("request_timeout");
      throw err;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function showRuntimeWarning(message, title = "Runtime Already Playing") {
    const fallback = () => window.alert(String(message || "This scene is already running."));
    if (!elRuntimeWarningModal || typeof bootstrap === "undefined" || !bootstrap.Modal) {
      fallback();
      return;
    }
    const titleEl = elRuntimeWarningModal.querySelector(".modal-title");
    const bodyEl = elRuntimeWarningModal.querySelector(".modal-body");
    if (titleEl) titleEl.textContent = String(title || "Runtime Already Playing");
    if (bodyEl) bodyEl.textContent = String(message || "This scene is already running.");
    bootstrap.Modal.getOrCreateInstance(elRuntimeWarningModal, { backdrop: true }).show();
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

  function overlays() {
    return Array.isArray(state.config?.overlays) ? state.config.overlays : [];
  }

  function assets() {
    return Array.isArray(state.config?.assets) ? state.config.assets : [];
  }

  function assetLabel(asset) {
    return String(asset?.displayName || asset?.filename || asset?.id || "").trim();
  }

  function assetAddedTs(asset) {
    const raw = String(asset?.createdAt || "").trim();
    if (!raw) return 0;
    const ts = Date.parse(raw);
    if (Number.isFinite(ts)) return ts;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  }

  function formatAssetSize(bytes) {
    const n = Number(bytes || 0);
    if (!Number.isFinite(n) || n <= 0) return "-";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = n;
    let idx = 0;
    while (value >= 1024 && idx < units.length - 1) {
      value /= 1024;
      idx += 1;
    }
    const fixed = value >= 10 || idx === 0 ? 0 : 1;
    return `${value.toFixed(fixed)} ${units[idx]}`;
  }

  function formatAssetAdded(asset) {
    const raw = String(asset?.createdAt || "").trim();
    const ts = assetAddedTs(asset);
    if (!raw || ts <= 0) return "-";
    try {
      return new Date(ts).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return raw.replace("T", " ").replace("Z", "");
    }
  }

  function sortedAssets() {
    const rows = assets().slice();
    const key = state.assetSortKey === "added" ? "added" : "name";
    const dir = state.assetSortDir === "desc" ? -1 : 1;
    rows.sort((a, b) => {
      if (key === "added") {
        const d = (assetAddedTs(a) - assetAddedTs(b)) * dir;
        if (d !== 0) return d;
      } else {
        const d = assetLabel(a).localeCompare(assetLabel(b), undefined, { sensitivity: "base", numeric: true }) * dir;
        if (d !== 0) return d;
      }
      return String(a?.id || "").localeCompare(String(b?.id || ""), undefined, { sensitivity: "base", numeric: true });
    });
    return rows;
  }

  function renderAssetSortIndicators() {
    if (elAssetSortNameIndicator) {
      const arrow = state.assetSortKey === "name"
        ? (state.assetSortDir === "asc" ? "↑" : "↓")
        : "";
      elAssetSortNameIndicator.textContent = arrow;
      elAssetSortNameIndicator.classList.toggle("text-secondary", Boolean(arrow));
    }
    if (elAssetSortAddedIndicator) {
      const arrow = state.assetSortKey === "added"
        ? (state.assetSortDir === "asc" ? "↑" : "↓")
        : "";
      elAssetSortAddedIndicator.textContent = arrow;
      elAssetSortAddedIndicator.classList.toggle("text-secondary", Boolean(arrow));
    }
  }

  function applyAssetSort(key) {
    const normalized = key === "added" ? "added" : "name";
    if (state.assetSortKey === normalized) {
      state.assetSortDir = state.assetSortDir === "asc" ? "desc" : "asc";
    } else {
      state.assetSortKey = normalized;
      state.assetSortDir = normalized === "added" ? "desc" : "asc";
    }
    renderAssets();
  }

  function displays() {
    return Array.isArray(state.config?.displays) ? state.config.displays : [];
  }

  function sceneById(sceneId) {
    return scenes().find((s) => String(s.id || "") === String(sceneId || ""));
  }

  function displayLabelById(displayId) {
    const row = (Array.isArray(state.config?.displays) ? state.config.displays : [])
      .find((d) => String(d?.id || "") === String(displayId || ""));
    if (!row) return String(displayId || "");
    return String(row.role || row.name || row.id || displayId || "").trim();
  }

  function runtimeTargetLabel(target, fallbackId = "") {
    if (!target) return displayLabelById(fallbackId) || String(fallbackId || "");
    return String(target.role || displayLabelById(target.displayId || target.id || "") || target.name || target.id || fallbackId || "").trim();
  }

  function runtimePidLabel(row) {
    let pid = Number(row?.pid || 0);
    if (!(Number.isFinite(pid) && pid > 0)) {
      const outputs = Array.isArray(row?.outputs) ? row.outputs : [];
      const outputPids = outputs
        .map((out) => Number(out?.pid || 0))
        .filter((n) => Number.isFinite(n) && n > 0);
      if (outputPids.length) pid = outputPids[0];
    }
    if (Number.isFinite(pid) && pid > 0) return String(pid);
    const launchMode = String(row?.launchMode || "").trim().toLowerCase();
    if (launchMode === "embedded") return `Embedded (${Number.isFinite(pid) ? pid : 0})`;
    return "-";
  }

  function runtimeLaunchLabel(row) {
    const launchMode = String(row?.launchMode || "").trim().toLowerCase();
    if (launchMode === "embedded") return "Embedded";
    if (launchMode === "windowed") return "Windowed";
    if (launchMode === "fullscreen") return "Fullscreen";
    return launchMode || "-";
  }

  function runtimeStartedLabel(row) {
    const startedAtMs = Number(row?.createdAtMs || row?.startedAtMs || 0);
    if (!Number.isFinite(startedAtMs) || startedAtMs <= 0) return "-";
    try {
      return new Date(startedAtMs).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_) {
      return "-";
    }
  }

  function runtimeRows() {
    const runtimeSessions = Array.isArray(state.runtime?.runtimeSessions) ? state.runtime.runtimeSessions : [];
    if (runtimeSessions.length) return runtimeSessions.slice();
    const outputEndpoints = Array.isArray(state.runtime?.outputEndpoints) ? state.runtime.outputEndpoints : [];
    if (outputEndpoints.length) {
      const grouped = new Map();
      outputEndpoints.forEach((out) => {
        const runtimeId = String(out?.runtimeId || "").trim();
        const sceneId = String(out?.sceneId || "").trim();
        if (!runtimeId || !sceneId) return;
        const row = grouped.get(runtimeId) || {
          id: runtimeId,
          runtimeId,
          sceneId,
          state: "running",
          outputs: [],
          outputIds: [],
          createdAtMs: 0,
          updatedAtMs: 0,
        };
        row.outputs.push({
          id: String(out?.id || out?.outputId || ""),
          type: String(out?.type || "").trim().toLowerCase(),
          displayId: String(out?.displayId || out?.target?.displayId || ""),
          state: String(out?.state || "running"),
          pid: Number(out?.pid || 0),
          lastSeenMs: Number(out?.lastSeenMs || out?.lastFrameTime || 0),
          createdAtMs: Number(out?.createdAtMs || 0),
        });
        row.outputIds.push(String(out?.id || out?.outputId || ""));
        const outCreatedAtMs = Number(out?.createdAtMs || 0);
        if (Number.isFinite(outCreatedAtMs) && outCreatedAtMs > 0) {
          row.createdAtMs = row.createdAtMs > 0 ? Math.min(row.createdAtMs, outCreatedAtMs) : outCreatedAtMs;
        }
        grouped.set(runtimeId, row);
      });
      if (grouped.size) return Array.from(grouped.values());
    }
    const surfaceRows = Array.isArray(state.runtime?.surfaceSessions) ? state.runtime.surfaceSessions : [];
    const sessionRows = Array.isArray(state.runtime?.sessions) ? state.runtime.sessions : [];
    if (surfaceRows.length || sessionRows.length) {
      const rows = surfaceRows.slice();
      const seen = new Set(rows.map((row) => [
        String(row?.displayId || ""),
        String(row?.sceneId || ""),
        String(row?.launchMode || "").trim().toLowerCase(),
      ].join("|")));
      sessionRows.forEach((row) => {
        const key = [
          String(row?.displayId || ""),
          String(row?.sceneId || ""),
          String(row?.launchMode || "").trim().toLowerCase(),
        ].join("|");
        if (seen.has(key)) return;
        rows.push({ ...row, pid: Number(row?.pid || 0) });
      });
      return rows;
    }
    const activeRows = Array.isArray(state.runtime?.engine?.active) ? state.runtime.engine.active : [];
    return activeRows.slice();
  }

  function currentRendererName() {
    return String(state.env?.renderer?.name || "godot").trim().toLowerCase();
  }

  function isGodotRuntime() {
    return currentRendererName() === "godot";
  }

  function runtimeDisplayOptionsHtml(selectedValue) {
    const selected = String(selectedValue || "").trim();
    return displays().map((d) => {
      const value = String(d?.id || "").trim();
      return `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(displayLabel(d))}</option>`;
    }).join("");
  }

  function authoredSceneOptionsHtml(selectedValue) {
    const selected = String(selectedValue || "").trim();
    const options = [
      `<option value="no_scene" ${selected === "no_scene" ? "selected" : ""}>No Scene</option>`,
      ...scenes().map((scene) => {
      const value = String(scene?.id || "").trim();
      const label = String(scene?.name || scene?.id || "").trim();
      return `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(label)}</option>`;
      }),
    ];
    return options.join("");
  }

  function knownGodotScenes() {
    return Array.isArray(state.env?.dynamicScenes) ? state.env.dynamicScenes.filter(Boolean) : [];
  }

  function overlayById(overlayId) {
    return overlays().find((ov) => String(ov.id || "") === String(overlayId || ""));
  }

  function overlayLayers(overlay) {
    return Array.isArray(overlay?.layers) ? overlay.layers : [];
  }

  function selectedLayer() {
    const overlay = overlayById(state.selectedOverlayId);
    const layers = overlayLayers(overlay);
    const idx = Number(state.selectedLayerIdx);
    return Number.isFinite(idx) && idx >= 0 ? layers[idx] || null : null;
  }

  function moveOverlayLayer(overlay, fromIdx, toIdx) {
    if (!overlay) return false;
    const layers = overlayLayers(overlay);
    const from = Number(fromIdx);
    const to = Number(toIdx);
    if (!Number.isFinite(from) || !Number.isFinite(to)) return false;
    if (from < 0 || from >= layers.length || to < 0 || to >= layers.length || from === to) return false;
    const [moved] = layers.splice(from, 1);
    layers.splice(to, 0, moved);
    overlay.layers = layers;
    state.selectedLayerIdx = to;
    return true;
  }

  function setOverlayLayerOrder(overlay, fromIdx, requestedOrder) {
    const layers = overlayLayers(overlay);
    const target = Math.max(1, Math.min(layers.length, Math.round(Number(requestedOrder || 1)))) - 1;
    return moveOverlayLayer(overlay, fromIdx, target);
  }

  function displayLabel(d) {
    const role = String(d?.role || "").trim();
    const fallback = String(d?.name || d?.id || "").trim();
    const label = role || fallback || "Display";
    return `${label} (${Number(d?.width || 0)}x${Number(d?.height || 0)})`;
  }

  function sceneDisplay(scene) {
    const key = primarySceneScreen(scene);
    return displays().find((d) => String(d.id || "") === key || String(d.role || "") === key) || displays()[0] || null;
  }

  async function launchScene(sceneId, launchMode = "fullscreen") {
    const mode = String(launchMode || "").trim().toLowerCase() === "windowed" ? "windowed" : "fullscreen";
    const previewViewport = currentPreviewViewport();
    const scene = sceneById(sceneId);
    const stackBehavior = sceneStackBehavior(scene);
    const res = await api("/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneId, launchMode: mode, previewViewport, stackBehavior }),
    });
    const st = await api("/state");
    state.runtime = st.state || null;
    renderRuntime();
    if (res?.reused && (mode === "windowed" || mode === "fullscreen")) {
      const sceneName = String(scene?.name || sceneId || "Scene").trim();
      const modeLabel = mode === "windowed" ? "windowed" : "fullscreen";
      showRuntimeWarning(`${sceneName} is already playing in ${modeLabel} mode. The existing player was reused.`);
    }
  }

  function clearOverlaySelection() {
    if (state.selectedOverlayIdx === -1) return;
    state.selectedOverlayIdx = -1;
    syncEditorOverlaySelection();
    renderPreview();
  }

  function sceneOverlayRefs(scene) {
    return Array.isArray(scene?.overlayRefs) ? scene.overlayRefs : [];
  }

  function normalizedOverlayRef(ref, idx = 0) {
    return {
      overlayId: String(ref?.overlayId || ref?.id || "").trim() || `overlay_${idx + 1}`,
      active: ref?.active !== false,
    };
  }

  function resolvedSceneOverlayEntries(scene, { includeInactive = true, forEditor = false } = {}) {
    const out = [];
    sceneOverlayRefs(scene)
      .forEach((ref, idx) => {
        const normalized = normalizedOverlayRef(ref, idx);
        const overlay = overlayById(normalized.overlayId);
        if (!overlay) return;
        const layers = overlayLayers(overlay);
        layers.forEach((layer) => {
          const resolved = {
            ...layer,
            overlayId: overlay.id,
            overlayName: overlay.name,
            zIndex: out.length + 1,
          };
          if (forEditor && !normalized.active) {
            resolved.opacity = Math.max(0.1, Math.min(1, Number(layer.opacity ?? 1) * 0.3));
          }
          if (!includeInactive && !normalized.active) return;
          out.push({ ref: normalized, overlay, resolved, index: out.length, overlayIndex: idx });
        });
      });
    const total = out.length;
    out.forEach((entry, idx) => {
      entry.resolved.zIndex = total - idx;
    });
    return out;
  }

  function effectiveSceneOverlays(scene, opts) {
    return resolvedSceneOverlayEntries(scene, opts).map((entry) => entry.resolved);
  }

  function buildRenderableScene(scene, { includeInactive = false, forEditor = false } = {}) {
    if (!scene) return null;
    return {
      ...scene,
      overlays: effectiveSceneOverlays(scene, { includeInactive, forEditor }),
    };
  }

  function layerZForIndex(total, idx) {
    const n = Number(total);
    const i = Number(idx);
    if (!Number.isFinite(n) || !Number.isFinite(i)) return 1;
    return Math.max(1, 1000 + Math.round(n - i));
  }

  function previewMediaSrc(assetId) {
    const id = String(assetId || "").trim();
    return id ? `/api/media/assets/file/${encodeURIComponent(id)}` : "";
  }

  function previewOverlayText(ov) {
    const key = String(ov?.valueKey || "").trim();
    if (key) return `{{${key}}}`;
    return String(ov?.text || "");
  }

  function ensurePreviewRenderer() {
    if (!elPreview || !window.PinballctlMediaSceneRenderer) return null;
    let layersRoot = elPreview.querySelector("[data-preview-layers]");
    let overlaysRoot = elPreview.querySelector("[data-preview-overlays]");
    let emptyNode = elPreview.querySelector("[data-preview-empty]");
    if (!layersRoot || !overlaysRoot || !emptyNode) {
      elPreview.innerHTML = `
        <div class="media-preview-layers" data-preview-layers></div>
        <div class="media-preview-overlays" data-preview-overlays></div>
        <div class="media-preview-base d-flex align-items-center justify-content-center text-secondary" data-preview-empty>No base asset selected</div>
      `;
      layersRoot = elPreview.querySelector("[data-preview-layers]");
      overlaysRoot = elPreview.querySelector("[data-preview-overlays]");
      emptyNode = elPreview.querySelector("[data-preview-empty]");
      previewRenderer = null;
    }
    if (previewRenderer) return previewRenderer;
    previewRenderer = window.PinballctlMediaSceneRenderer.createSceneRenderer({
      layersRoot,
      overlayRoot: overlaysRoot,
      layerClassName: "media-preview-layer",
      overlayClassName: "media-preview-overlay",
      overlayImageLayerClassName: "media-preview-overlay-image-layer",
      overlayTextLayerClassName: "media-preview-overlay-text-layer",
      imageClassName: "media-preview-overlay-image",
      assetUrlFor(assetId) {
        return previewMediaSrc(assetId);
      },
      mediaClassNameForLayer() {
        return "media-preview-base";
      },
      videoIdForLayer(layer, layerIndex) {
        return layerIndex === 0 ? "media-preview-video" : "";
      },
      overlayTextFor(ov) {
        return previewOverlayText(ov);
      },
      overlayIdFor(ov, layer, overlayIndex) {
        return String(ov?.id || `preview_ov_${overlayIndex + 1}`);
      },
      decorateOverlayNode(node, ctx) {
        const idx = Number(ctx?.overlayIndex ?? -1);
        node.setAttribute("data-overlay-idx", String(idx));
      },
    });
    return previewRenderer;
  }

  function buildPreviewPayload(scene) {
    const selectedScene = buildRenderableScene(scene || sceneById(state.selectedSceneId), { includeInactive: false, forEditor: false });
    if (!selectedScene) return { layers: [], overlayValues: {}, fontScale: 1 };
    const asset = assets().find((a) => String(a?.id || "") === String(selectedScene.baseAssetId || "")) || null;
    return {
      layers: [{
        layerId: "preview",
        renderOrder: 1,
        state: state.previewShouldPlay ? "playing" : "paused",
        scene: selectedScene,
        asset,
      }],
      overlayValues: {},
      fontScale: Number(getComputedStyle(elPreview).getPropertyValue("--media-preview-scale") || 1) || 1,
    };
  }

  function ensureOverlayPreviewRenderer() {
    if (overlayPreviewRenderer) return overlayPreviewRenderer;
    if (!elOverlayPreview || !window.PinballctlMediaSceneRenderer || typeof window.PinballctlMediaSceneRenderer.createSceneRenderer !== "function") return null;
    let layersRoot = elOverlayPreview.querySelector("[data-preview-layers]");
    let overlaysRoot = elOverlayPreview.querySelector("[data-preview-overlays]");
    let emptyNode = elOverlayPreview.querySelector("[data-preview-empty]");
    if (!layersRoot || !overlaysRoot || !emptyNode) {
      elOverlayPreview.innerHTML = `
        <div class="media-preview-layers" data-preview-layers></div>
        <div class="media-preview-overlays" data-preview-overlays></div>
        <div class="media-preview-empty d-none" data-preview-empty>No preview asset selected.</div>
      `;
      layersRoot = elOverlayPreview.querySelector("[data-preview-layers]");
      overlaysRoot = elOverlayPreview.querySelector("[data-preview-overlays]");
      emptyNode = elOverlayPreview.querySelector("[data-preview-empty]");
    }
    overlayPreviewRenderer = window.PinballctlMediaSceneRenderer.createSceneRenderer({
      layersRoot,
      overlayRoot: overlaysRoot,
      layerClassName: "media-preview-layer",
      overlayClassName: "media-preview-overlay",
      overlayImageLayerClassName: "media-preview-overlay-image-layer",
      overlayTextLayerClassName: "media-preview-overlay-text-layer",
      imageClassName: "media-preview-overlay-image",
      assetUrlFor(assetId) {
        return previewMediaSrc(assetId);
      },
      mediaClassNameForLayer() {
        return "media-preview-base";
      },
      videoIdForLayer(layer, layerIndex) {
        return layerIndex === 0 ? "media-overlay-preview-video" : "";
      },
      overlayTextFor(ov) {
        return previewOverlayText(ov);
      },
      overlayIdFor(ov, layer, overlayIndex) {
        return String(ov?.id || `overlay_preview_${overlayIndex + 1}`);
      },
      decorateOverlayNode(node, ctx) {
        const idx = Number(ctx?.overlayIndex ?? -1);
        const editing = isOverlaysPaneActive() && idx === state.selectedLayerIdx;
        node.setAttribute("data-overlay-idx", String(idx));
        node.classList.toggle("is-selected", editing);
        if (editing) {
          node.innerHTML += '<span class="media-preview-handle media-preview-handle-resize" data-overlay-handle="resize"></span><span class="media-preview-handle media-preview-handle-rotate" data-overlay-handle="rotate"></span>';
        }
      },
    });
    return overlayPreviewRenderer;
  }

  function renderOverlayPreview() {
    if (!elOverlayPreview) return;
    const overlay = overlayById(state.selectedOverlayId);
    if (!overlay) {
      if (overlayPreviewRenderer) overlayPreviewRenderer.clear();
      elOverlayPreview.innerHTML = "";
      attachOverlayPreviewVideoHandlers(null);
      return;
    }
    const renderer = ensureOverlayPreviewRenderer();
    if (!renderer) return;
    const display = displays()[0] || { width: 1920, height: 1080 };
    const w = Math.max(64, Number(display?.width || 1920));
    const h = Math.max(64, Number(display?.height || 1080));
    elOverlayPreview.style.aspectRatio = `${w} / ${h}`;
    fitOverlayPreviewStage();
    const asset = assets().find((a) => String(a?.id || "") === String(overlay.previewAssetId || "")) || null;
    renderer.render({
      layers: [{
        layerId: `overlay-preview:${overlay.id}`,
        renderOrder: 1,
        state: state.overlayPreviewShouldPlay ? "playing" : "paused",
        scene: {
          baseAssetId: overlay.previewAssetId || "",
          loop: true,
          mute: true,
          overlays: overlayLayers(overlay).map((layer, idx, all) => ({ ...layer, zIndex: all.length - idx })),
        },
        asset,
      }],
      overlayValues: {},
      fontScale: 1,
    });
    const previewEmpty = elOverlayPreview.querySelector("[data-preview-empty]");
    if (previewEmpty) previewEmpty.classList.add("d-none");
    const baseMedia = elOverlayPreview.querySelector("video, img.media-preview-base");
    const nextVideo = elOverlayPreview.querySelector("video#media-overlay-preview-video");
    attachOverlayPreviewVideoHandlers(nextVideo);
    if (baseMedia && baseMedia.tagName === "VIDEO") {
      if (!state.overlayPreviewShouldPlay) pauseAtFirstFrame(baseMedia);
      baseMedia.classList.add("is-ready");
    } else if (baseMedia) {
      baseMedia.classList.add("is-ready");
    }
    elOverlayPreview.classList.add("is-ready");
  }

  function rerenderPreviewLayout() {
    fitPreviewStage();
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !elPreview) return;
    const renderer = ensurePreviewRenderer();
    if (!renderer) return;
    renderer.render(buildPreviewPayload(scene));
  }

  function schedulePreviewLayoutRerender() {
    if (previewResizeRaf) return;
    previewResizeRaf = window.requestAnimationFrame(() => {
      previewResizeRaf = 0;
      rerenderPreviewLayout();
      syncScenesColumnHeight();
      syncOverlaysColumnHeight();
      fitOverlayPreviewStage();
    });
  }

  function flushOverlayDragRefresh() {
    overlayDragRenderRaf = 0;
    if (!overlayDragPendingLayer || !Number.isFinite(overlayDragPendingIdx) || overlayDragPendingIdx < 0) return;
    updateOverlayPositionFields(overlayDragPendingIdx, overlayDragPendingLayer);
    renderOverlayPreview();
  }

  function scheduleOverlayDragRefresh(idx, layer) {
    overlayDragPendingIdx = Number(idx);
    overlayDragPendingLayer = layer || null;
    if (overlayDragRenderRaf) return;
    overlayDragRenderRaf = window.requestAnimationFrame(flushOverlayDragRefresh);
  }

  function syncEditorOverlaySelection() {
    if (!elEditor) return;
    const rows = elEditor.querySelectorAll("[data-overlay-idx]");
    rows.forEach((row) => {
      const idx = Number(row.getAttribute("data-overlay-idx"));
      row.classList.toggle("border-primary", Number.isFinite(idx) && idx === state.selectedOverlayIdx);
    });
  }

  function wireTabs() {
    const tabButtons = Array.from(root.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#media-pane-"]'));
    tabButtons.forEach((btn) => {
      btn.addEventListener("shown.bs.tab", (e) => {
        const target = String(e.target?.getAttribute("data-bs-target") || "");
        if (!target) return;
        stopPreviewPlayback();
        stopOverlayPreviewPlayback();
        try { localStorage.setItem(MEDIA_TAB_KEY, target); } catch (_) {}
        if (target === "#media-pane-scenes") {
          window.requestAnimationFrame(() => {
            syncScenesColumnHeight();
            renderPreview();
          });
        } else if (target === "#media-pane-overlays") {
          window.requestAnimationFrame(() => {
            syncOverlaysColumnHeight();
            fitOverlayPreviewStage();
            renderOverlayPreview();
          });
        } else if (target === "#media-pane-runtime") {
          refreshRuntimeState().catch(() => {});
        }
        syncRuntimePolling();
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
    syncLayoutColumnHeight(elScenesLayout, elScenesSideCol, elScenesOptionsScroll);
  }

  function syncOverlaysColumnHeight() {
    syncLayoutColumnHeight(elOverlayLayout, elOverlaySideCol, elOverlayOptionsScroll);
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
    // Match the runtime display scaling so preview text/layout matches
    // fullscreen and windowed playback as closely as possible.
    const refW = 1280;
    const refH = 720;
    const sx = finalW / refW;
    const sy = finalH / refH;
    const scale = Math.max(0.05, Math.min(4, Math.min(sx, sy)));
    elPreview.style.setProperty("--media-preview-scale", String(scale));
  }

  function fitOverlayPreviewStage() {
    if (!elOverlayPreview) return;
    const wrap = elOverlayPreview.closest(".media-preview-stage-wrap");
    if (!wrap) return;
    const availW = Math.max(0, Math.floor(wrap.clientWidth || 0));
    const availH = Math.max(0, Math.floor(wrap.clientHeight || 0));
    if (availW <= 0 || availH <= 0) return;
    const display = displays()[0] || { width: 1920, height: 1080 };
    const ratio = Math.max(0.1, Number(display?.width || 1920) / Math.max(1, Number(display?.height || 1080)));
    let width = availW;
    let height = Math.round(width / ratio);
    if (height > availH) {
      height = availH;
      width = Math.round(height * ratio);
    }
    const finalW = Math.max(64, width);
    const finalH = Math.max(64, height);
    elOverlayPreview.style.width = `${finalW}px`;
    elOverlayPreview.style.height = `${finalH}px`;
    const sx = finalW / 1280;
    const sy = finalH / 720;
    const scale = Math.max(0.05, Math.min(4, Math.min(sx, sy)));
    elOverlayPreview.style.setProperty("--media-preview-scale", String(scale));
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

  function uploadFontFile(file) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      form.append("file", file);
      xhr.open("POST", "/api/media/fonts/upload", true);
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

  async function uploadFontFiles(files) {
    const list = Array.from(files || []);
    if (!list.length || fontUploadInProgress) return;
    fontUploadInProgress = true;
    if (elFontUploadDropzone) elFontUploadDropzone.classList.add("is-uploading");
    try {
      for (const file of list) {
        await uploadFontFile(file);
      }
      await loadAll(false);
      setDirty(true);
    } finally {
      fontUploadInProgress = false;
      if (elFontUploadDropzone) elFontUploadDropzone.classList.remove("is-uploading");
    }
  }

  function fontCatalog() {
    const catalog = Array.isArray(state.env?.fontCatalog) ? state.env.fontCatalog : [];
    const out = [];
    const seen = new Set();
    catalog.forEach((row) => {
      const family = String(row?.family || row?.name || "").trim();
      if (!family) return;
      const key = family.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push(row);
    });
    const fallbackFonts = Array.isArray(state.env?.fonts) ? state.env.fonts : [];
    fallbackFonts.forEach((name) => {
      const family = String(name || "").trim();
      if (!family) return;
      const key = family.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push({
        id: `system:${family}`,
        name: family,
        family,
        source: "system",
        url: "",
      });
    });
    return out;
  }

  function applyFontCatalogStyles() {
    let styleEl = document.getElementById(MEDIA_FONT_STYLE_ID);
    if (!(styleEl instanceof HTMLStyleElement)) {
      styleEl = document.createElement("style");
      styleEl.id = MEDIA_FONT_STYLE_ID;
      document.head.appendChild(styleEl);
    }
    const css = fontCatalog()
      .filter((row) => String(row?.source || "") === "custom" && String(row?.family || "").trim() && String(row?.url || "").trim())
      .map((row) => (
        `@font-face{font-family:'${String(row.family).replaceAll("'", "\\'")}';src:url('${String(row.url).replaceAll("'", "%27")}') format('truetype');font-style:normal;font-weight:400;font-display:swap;}`
      ))
      .join("\n");
    styleEl.textContent = css;
  }

  function renderFonts() {
    if (!elFontsTable) return;
    const query = String(elFontFilter?.value || "").trim().toLowerCase();
    const sourceFilter = String(elFontSourceFilter?.value || "all").trim().toLowerCase();
    const rows = fontCatalog().filter((row) => {
      const rowSource = String(row?.source || "system").trim().toLowerCase();
      if (sourceFilter !== "all" && rowSource !== sourceFilter) return false;
      if (!query) return true;
      return String(row?.name || "").toLowerCase().includes(query)
        || String(row?.family || "").toLowerCase().includes(query)
        || rowSource.includes(query);
    });
    if (!rows.length) {
      elFontsTable.innerHTML = `<tr><td colspan="4" class="text-secondary text-center py-3">No fonts match the current filter.</td></tr>`;
      return;
    }
    elFontsTable.innerHTML = rows.map((row) => `
      <tr>
        <td>${esc(row.name || row.family || "")}</td>
        <td class="media-font-sample-cell"><span class="media-font-sample-text" style="font-family:${esc(row.family || "")}">Lorem ipsum dolor sit amet, consectetur adipiscing elit.</span></td>
        <td><span class="badge text-bg-secondary">${esc(String(row.source || "system").toUpperCase())}</span></td>
        <td class="text-end">
          ${String(row.source || "") === "custom"
            ? `<button type="button" class="btn btn-outline-danger btn-sm" data-media-font-delete="${esc(row.id || "")}"><i class="fa fa-trash"></i></button>`
            : ""}
        </td>
      </tr>
    `).join("");
  }

  function assetInUse(assetId) {
    const id = String(assetId || "").trim();
    if (!id) return false;
    const cfg = state.config || {};
    const sceneRows = Array.isArray(cfg.scenes) ? cfg.scenes : [];
    if (sceneRows.some((scene) => String(scene?.baseAssetId || "").trim() === id)) return true;
    const overlayRows = Array.isArray(cfg.overlays) ? cfg.overlays : [];
    return overlayRows.some((overlay) => {
      if (String(overlay?.previewAssetId || "").trim() === id) return true;
      const layers = Array.isArray(overlay?.layers) ? overlay.layers : [];
      return layers.some((layer) => String(layer?.assetId || "").trim() === id);
    });
  }

  function renderAssets() {
    const rows = sortedAssets();
    renderAssetSortIndicators();
    if (elAssetCount) elAssetCount.textContent = String(rows.length);
    if (!elAssets) return;
    if (!rows.length) {
      elAssets.innerHTML = `<tr><td colspan="8" class="text-secondary text-center py-3">No media assets uploaded yet.</td></tr>`;
      syncAssetConversionPolling();
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
        <td><span class="small">${esc(assetFormatLabel(a))}</span></td>
        <td>${assetStatusHtml(a)}</td>
        <td>
          ${assetInUse(a.id)
            ? '<span class="text-success" title="Asset is in use"><i class="fa fa-check"></i></span>'
            : '<span class="text-danger" title="Asset is not in use"><i class="fa fa-times"></i></span>'}
        </td>
        <td class="text-end">${esc(formatAssetSize(a.sizeBytes))}</td>
        <td>${esc(formatAssetAdded(a))}</td>
        <td class="text-end">
          <button type="button" class="btn btn-outline-secondary btn-sm media-icon-btn me-1" data-media-asset-preview title="Preview"><i class="fa fa-play"></i></button>
          <button type="button" class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" data-media-asset-delete aria-label="Remove asset" title="Remove asset"><i class="fa fa-trash"></i><span>Remove</span></button>
        </td>
      </tr>
    `).join("");
    syncAssetConversionPolling();
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

  function renderDefaults() {
    if (!elDefaultsEditor) return;
    const displaysList = displays();
    const scenesList = scenes();
    const defaults = defaultScenesByDisplay();
    const autoplayMap = autoplayByDisplay();
    const settings = state.config?.settings && typeof state.config.settings === "object" ? state.config.settings : {};
    const godot = settings.godot && typeof settings.godot === "object" ? settings.godot : {};
    elDefaultsEditor.innerHTML = `
      <div class="d-grid gap-3">
        <div class="border rounded p-3">
          <div class="row g-3">
            <div class="col-md-6">
              <label class="form-label">Godot Binary</label>
              <input class="form-control form-control-sm" data-settings-k="godot.binary" value="${esc(String(godot.binary || ""))}" placeholder="/Applications/Godot.app/Contents/MacOS/Godot">
            </div>
            <div class="col-md-6">
              <label class="form-label">Godot Port</label>
              <input class="form-control form-control-sm" data-settings-k="godot.port" type="number" min="1024" max="65535" value="${esc(String(godot.port || 17342))}">
            </div>
            <div class="col-12">
              <div class="form-check form-switch m-0">
                <input class="form-check-input" type="checkbox" data-settings-k="godot.autoRestart" ${godot.autoRestart !== false ? "checked" : ""}>
                <label class="form-check-label">Auto-restart Godot runtime if the process dies</label>
              </div>
            </div>
            <div class="col-12">
              <div class="form-check form-switch m-0">
                <input class="form-check-input" type="checkbox" data-settings-k="godot.debugVisible" ${godot.debugVisible !== false ? "checked" : ""}>
                <label class="form-check-label">Show Godot debug panel while testing</label>
              </div>
            </div>
          </div>
        </div>
        ${displaysList.length ? displaysList.map((d) => {
          const did = String(d.id || "").trim();
          const options = ['<option value="">None</option>'].concat(
            scenesList
              .filter((scene) => sceneTargetsDisplay(scene, d))
              .map((scene) => `<option value="${esc(scene.id)}" ${String(defaults[did] || "") === String(scene.id || "") ? "selected" : ""}>${esc(scene.name || scene.id)}</option>`)
          ).join("");
          return `
            <div class="border rounded p-3">
              <label class="form-label">${esc(displayLabel(d))}</label>
              <select class="form-select form-select-sm mb-2" data-default-display="${esc(did)}">${options}</select>
              <div class="form-check form-switch m-0">
                <input class="form-check-input" type="checkbox" data-autoplay-display="${esc(did)}" ${autoplayMap[did] ? "checked" : ""}>
                <label class="form-check-label">Auto-play on start</label>
              </div>
            </div>
          `;
        }).join("") : '<div class="text-secondary">No displays configured.</div>'}
      </div>
    `;
  }

  function renderScenes() {
    const rows = scenes();
    if (!elEditor || !elPreview) return;
    if (!rows.length) {
      writeSelectedSceneId("");
      if (elSceneSelect) {
        elSceneSelect.innerHTML = `<option value="">No scenes yet</option>`;
        elSceneSelect.disabled = true;
      }
      if (elPreviewOpenFull) elPreviewOpenFull.disabled = true;
      if (elPreviewOpenWindow) elPreviewOpenWindow.disabled = true;
      elEditor.innerHTML = `<div class="text-secondary">Create a scene to start building.</div>`;
      elPreview.innerHTML = "";
      return;
    }
    if (!sceneById(state.selectedSceneId)) state.selectedSceneId = String(rows[0].id || "");
    writeSelectedSceneId(state.selectedSceneId);
    const selected = sceneById(state.selectedSceneId);
    const ovCount = sceneOverlayRefs(selected).length;
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

    renderSceneEditor();
    renderPreview();
    syncEditorOverlaySelection();
  }

  function sceneOverlaysEditorHtml(scene) {
    if (!scene) {
      return `<div class="text-secondary">Select a scene.</div>`;
    }
    const refs = sceneOverlayRefs(scene);
    const options = ['<option value="">Select overlay…</option>']
      .concat(overlays().map((ov) => `<option value="${esc(ov.id)}">${esc(ov.name || ov.id)}</option>`))
      .join("");
    const rowsHtml = refs.length
      ? refs.map((ref, idx) => {
          const normalized = normalizedOverlayRef(ref, idx);
          const overlay = overlayById(normalized.overlayId);
          const label = overlay?.name || normalized.overlayId || `Overlay ${idx + 1}`;
          return `
            <div class="media-overlay-row ${idx === state.selectedOverlayIdx ? "border-primary" : ""}" data-overlay-idx="${idx}" draggable="true">
              <div class="media-overlay-header">
                <div class="d-flex align-items-center gap-2 min-w-0">
                  <span class="text-secondary"><i class="fa fa-grip-vertical"></i></span>
                  <div class="media-overlay-title">${esc(label)}</div>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <label class="form-check m-0">
                    <input class="form-check-input" type="checkbox" data-scene-overlay-active ${normalized.active ? "checked" : ""}>
                    <span class="form-check-label">Active</span>
                  </label>
                  <button type="button" class="btn btn-outline-danger btn-sm" data-scene-overlay-remove title="Remove overlay"><i class="fa fa-trash"></i></button>
                </div>
              </div>
            </div>
          `;
        }).join("")
      : `<div class="text-secondary">No overlays selected for this scene.</div>`;
    return `
      <div class="d-flex gap-2 align-items-center mb-3">
        <select class="form-select form-select-sm" id="media-scene-overlay-add-select">${options}</select>
        <button type="button" class="btn btn-success btn-sm text-nowrap" id="media-scene-overlay-add"><i class="fa fa-plus me-1"></i>Add Overlay</button>
      </div>
      <div id="media-scene-overlays-wrap">${rowsHtml}</div>
    `;
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
      ["credit", "Credit"],
      ["game_elapsed_time", "Game Elapsed Time"],
    ].forEach(([v, l]) => add(v, l));

    const runtimeValues = state.runtime?.overlayValues;
    if (runtimeValues && typeof runtimeValues === "object") {
      Object.keys(runtimeValues).forEach((k) => add(k, k));
    }

    overlays().forEach((ov) => {
      overlayLayers(ov).forEach((layer) => {
        const v = String(layer?.valueKey || "").trim();
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
    const seen = new Set();
    const customFonts = [];
    const systemFonts = [];
    fontCatalog().forEach((row) => {
      const family = String(row?.family || row?.name || "").trim();
      const label = String(row?.name || family).trim();
      if (!family) return;
      const key = family.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      const target = String(row?.source || "") === "custom" ? customFonts : systemFonts;
      target.push({
        value: family,
        label: String(row?.source || "") === "custom" ? `${label} (Custom)` : label,
      });
    });
    fallbackFonts.forEach((f) => {
      const name = String(f || "").trim();
      if (!name) return;
      const key = name.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      systemFonts.push({ value: name, label: name });
    });
    const fonts = [...customFonts, ...systemFonts];
    const selected = String(selectedFont || "").trim();
    const options = ['<option value="">Default</option>'];
    fonts.forEach((row) => {
      const value = String(row?.value || "").trim();
      const label = String(row?.label || value).trim();
      if (!value) return;
      options.push(`<option value="${esc(value)}" ${selected === value ? "selected" : ""}>${esc(label)}</option>`);
    });
    return options.join("");
  }

  function boolAttr(v) {
    return v ? "checked" : "";
  }

  function sceneScreenTargets(scene) {
    const screens = Array.isArray(scene?.screens) ? scene.screens : [];
    const out = [];
    screens.forEach((raw) => {
      const val = String(raw || "").trim();
      if (val && !out.includes(val)) out.push(val);
    });
    return out;
  }

  function displayMatchesSceneTarget(display, target) {
    const tgt = String(target || "").trim();
    if (!tgt) return false;
    return [
      String(display?.id || "").trim(),
      String(display?.role || "").trim(),
      String(display?.name || "").trim(),
    ].includes(tgt);
  }

  function sceneTargetsDisplay(scene, display) {
    const targets = sceneScreenTargets(scene);
    if (!targets.length) return false;
    return targets.some((target) => displayMatchesSceneTarget(display, target));
  }

  function primarySceneScreen(scene) {
    return String(sceneScreenTargets(scene)[0] || "").trim();
  }

  function defaultScenesByDisplay() {
    const settings = state.config?.settings && typeof state.config.settings === "object" ? state.config.settings : {};
    const raw = settings.defaultScenesByDisplay && typeof settings.defaultScenesByDisplay === "object" ? settings.defaultScenesByDisplay : {};
    return raw;
  }

  function autoplayByDisplay() {
    const settings = state.config?.settings && typeof state.config.settings === "object" ? state.config.settings : {};
    const raw = settings.autoplayByDisplay && typeof settings.autoplayByDisplay === "object" ? settings.autoplayByDisplay : {};
    return raw;
  }

  function sceneStackBehavior(scene) {
    const blend = String(scene?.blendMode || "").trim().toUpperCase();
    return blend === "PAUSE_LOWER" ? "interrupt" : "replace";
  }

  function renderOverlayOptions(overlay, { includeDelete = true } = {}) {
    const ov = overlay || {};
    const previewAssetOpts = ['<option value="">None</option>']
      .concat(assets().map((a) => `<option value="${esc(a.id)}" ${String(ov.previewAssetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`))
      .join("");
    return `
      <div class="row g-2">
        <div class="col-12">
          <label class="form-label">Name</label>
          <input class="form-control form-control-sm" data-k="name" value="${esc(ov.name || "")}" placeholder="Overlay name">
        </div>
        <div class="col-12">
          <label class="form-label">Preview Media</label>
          <select class="form-select form-select-sm" data-k="previewAssetId">${previewAssetOpts}</select>
          <div class="form-text">Used only while building and positioning this overlay.</div>
        </div>
        ${includeDelete ? `
          <div class="col-12">
            <button type="button" class="btn btn-outline-danger btn-sm w-100 d-inline-flex align-items-center justify-content-center gap-1" id="media-delete-overlay"><i class="fa fa-trash"></i><span>Remove</span></button>
          </div>
        ` : ""}
      </div>
    `;
  }

  function renderLayerOptions(layer) {
    const row = layer || {};
    const layerType = normalizeOverlayType(row.type);
    const textMode = String(row.valueKey || "").trim() ? "variable" : "fixed";
    const textAlign = normalizeTextAlign(row.textAlign);
    const bgMode = String(row.bgColor || "").trim().toLowerCase() === "transparent" ? "transparent" : "solid";
    const imageAssets = assets().filter((a) => String(a.kind || "").toLowerCase() !== "video");
    return `
      <div class="row g-2">
        <div class="col-12">
          <label class="form-label">Name</label>
          <input class="form-control form-control-sm" data-layer-k="name" value="${esc(row.name || "")}" placeholder="Layer name">
        </div>
        <div class="col-12">
          <label class="form-label">Type</label>
          <select class="form-select form-select-sm" data-layer-k="type">
            <option value="text" ${layerType === "text" ? "selected" : ""}>Text</option>
            <option value="image" ${layerType === "image" ? "selected" : ""}>Image</option>
          </select>
        </div>
        <div class="col-6 col-lg-3"><label class="form-label">X</label><input type="number" step="0.25" class="form-control form-control-sm" data-layer-k="xPct" value="${q025(row.xPct || 0)}"></div>
        <div class="col-6 col-lg-3"><label class="form-label">Y</label><input type="number" step="0.25" class="form-control form-control-sm" data-layer-k="yPct" value="${q025(row.yPct || 0)}"></div>
        <div class="col-6 col-lg-3"><label class="form-label">W</label><input type="number" step="0.25" class="form-control form-control-sm" data-layer-k="wPct" value="${q025(row.wPct || 20)}"></div>
        <div class="col-6 col-lg-3"><label class="form-label">H</label><input type="number" step="0.25" class="form-control form-control-sm" data-layer-k="hPct" value="${q025(row.hPct || 8)}"></div>
        ${layerType === "text" ? `
          <div class="col-12">
            <label class="form-label">Text Source</label>
            <select class="form-select form-select-sm mb-2" data-layer-k="textMode">
              <option value="fixed" ${textMode === "fixed" ? "selected" : ""}>Fixed Text</option>
              <option value="variable" ${textMode === "variable" ? "selected" : ""}>Variable</option>
            </select>
            ${textMode === "fixed"
              ? `<textarea class="form-control form-control-sm" rows="3" data-layer-k="text" placeholder="Enter text">${esc(row.text || "")}</textarea>`
              : `<select class="form-select form-select-sm" data-layer-k="valueKeyPreset">${renderVariableOptions(row.valueKey)}</select>`
            }
          </div>
        ` : `
          <div class="col-12">
            <label class="form-label">Image Asset</label>
            <select class="form-select form-select-sm" data-layer-k="assetId"><option value="">Select image…</option>${imageAssets.map((a) => `<option value="${esc(a.id)}" ${String(row.assetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`).join("")}</select>
          </div>
          <div class="col-12">
            <label class="form-label">Fit</label>
            <select class="form-select form-select-sm" data-layer-k="fit">
              <option value="cover" ${String(row.fit || "contain") === "cover" ? "selected" : ""}>Cover</option>
              <option value="contain" ${String(row.fit || "contain") === "contain" ? "selected" : ""}>Contain</option>
              <option value="fill" ${String(row.fit || "contain") === "fill" ? "selected" : ""}>Fill</option>
              <option value="none" ${String(row.fit || "contain") === "none" ? "selected" : ""}>None</option>
              <option value="scale-down" ${String(row.fit || "contain") === "scale-down" ? "selected" : ""}>Scale Down</option>
            </select>
          </div>
        `}
        ${layerType === "text" ? `
          <div class="col-12">
            <label class="form-label">Text Align</label>
            <select class="form-select form-select-sm" data-layer-k="textAlign">
              <option value="left" ${textAlign === "left" ? "selected" : ""}>Left</option>
              <option value="center" ${textAlign === "center" ? "selected" : ""}>Centre</option>
              <option value="right" ${textAlign === "right" ? "selected" : ""}>Right</option>
            </select>
          </div>
          <div class="col-12">
            <label class="form-label">Text Effects</label>
            <div>${renderTextEffectsOptions(row.textEffects)}</div>
          </div>
          <div class="col-6"><label class="form-label">Font Size</label><input type="number" class="form-control form-control-sm" data-layer-k="fontSizePx" value="${Number(row.fontSizePx || 24)}"></div>
          <div class="col-6"><label class="form-label">Font Family</label><select class="form-select form-select-sm" data-layer-k="fontFamily">${renderFontOptions(row.fontFamily)}</select></div>
          <div class="col-6"><label class="form-label">Font Color</label><input type="color" class="form-control form-control-color form-control-sm" data-layer-k="color" value="${esc(row.color || "#ffffff")}"></div>
          <div class="col-6"><label class="form-label">Background</label><select class="form-select form-select-sm mb-2" data-layer-k="bgMode"><option value="transparent" ${bgMode === "transparent" ? "selected" : ""}>Transparent</option><option value="solid" ${bgMode === "solid" ? "selected" : ""}>Color</option></select>${bgMode === "solid" ? `<input type="color" class="form-control form-control-color form-control-sm" data-layer-k="bgColor" value="${esc(row.bgColor || "#000000")}">` : ""}</div>
        ` : ""}
        <div class="col-12"><label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2"><span>Rotate</span><span class="small text-secondary" data-layer-k-label="rotateDeg">${Math.round(Number(row.rotateDeg || 0))}\u00b0</span></label><input type="range" class="form-range" min="-180" max="180" step="1" data-layer-k="rotateDeg" value="${Math.round(Number(row.rotateDeg || 0))}"></div>
        <div class="col-12"><label class="form-label d-flex align-items-center justify-content-between mb-0 mt-2"><span>Opacity</span><span class="small text-secondary" data-layer-k-label="opacity">${Number(row.opacity ?? 1).toFixed(1)}</span></label><input type="range" class="form-range" min="0" max="1" step="0.1" data-layer-k="opacity" value="${Number(row.opacity ?? 1)}"></div>
      </div>
    `;
  }

  function renderSceneEditor() {
    const scene = sceneById(state.selectedSceneId);
    if (!elEditor) return;
    if (!scene) {
      elEditor.innerHTML = `<div class="text-secondary">Select a scene.</div>`;
      return;
    }
    const targetScreens = sceneScreenTargets(scene);
    const blendMode = String(scene.blendMode || "STOP_LOWER").toUpperCase();
    const interruptPolicy = String(scene.interruptPolicy || "NO_INTERRUPT").toUpperCase();
    const duplicatePolicy = String(scene.duplicatePolicy || "DROP_IF_PLAYING").toUpperCase();
    const transition = scene.transition && typeof scene.transition === "object" ? scene.transition : {};
    const transitionType = String(transition.type || "CUT").toUpperCase();
    const transitionDurationMs = Math.max(0, Math.round(Number(transition.durationMs || 0)));
    const queue = scene.queue && typeof scene.queue === "object" ? scene.queue : {};
    const audioBehaviour = scene.audioBehaviour && typeof scene.audioBehaviour === "object" ? scene.audioBehaviour : {};
    const audioPause = Array.isArray(audioBehaviour.pause) ? audioBehaviour.pause : [];
    const audioDuck = Array.isArray(audioBehaviour.duck) ? audioBehaviour.duck : [];
    const audioTypes = ["music", "sfx", "voice", "ambient"];
    const audioChoiceFor = (kind) => {
      const key = String(kind || "").trim();
      if (audioPause.includes(key)) return "pause";
      if (audioDuck.includes(key)) return "duck";
      return "allow";
    };
    const assetOpts = ['<option value="">Select asset…</option>'].concat(assets().map((a) => `<option value="${esc(a.id)}" ${String(scene.baseAssetId || "") === String(a.id || "") ? "selected" : ""}>${esc(a.displayName || a.filename || a.id)}</option>`)).join("");
    elEditor.innerHTML = `
      <div class="row g-2 mb-3">
        <div class="col-12">
          <label class="form-label">Name</label>
          <input class="form-control form-control-sm" data-scene-k="name" value="${esc(scene.name || "")}">
        </div>

        <div class="col-12">
          <label class="form-label">Target Displays</label>
          <div class="row g-2">
            ${displays().map((d) => {
              const key = String(d.id || d.role || "").trim();
              const checked = targetScreens.includes(key) || targetScreens.includes(String(d.role || "").trim());
              return `<div class="col-12 col-lg-6">
                <label class="form-check">
                  <input class="form-check-input" type="checkbox" data-scene-screen="${esc(key)}" value="${esc(key)}" ${boolAttr(checked)}>
                  <span class="form-check-label">${esc(displayLabel(d))}</span>
                </label>
              </div>`;
            }).join("")}
          </div>
          <div class="form-text">Select one or more outputs for this scene.</div>
        </div>

        <div class="col-12">
          <label class="form-label">Base Asset</label>
          <select class="form-select form-select-sm" data-scene-k="baseAssetId">${assetOpts}</select>
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Priority</label>
          <input type="number" class="form-control form-control-sm" data-scene-k="priority" value="${Number(scene.priority || 100)}">
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Blend Mode</label>
          <select class="form-select form-select-sm" data-scene-k="blendMode">
            <option value="PLAY_OVER" ${blendMode === "PLAY_OVER" ? "selected" : ""}>Play Over</option>
            <option value="PAUSE_LOWER" ${blendMode === "PAUSE_LOWER" ? "selected" : ""}>Pause Lower</option>
            <option value="STOP_LOWER" ${blendMode === "STOP_LOWER" ? "selected" : ""}>Stop Lower</option>
          </select>
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

        <div class="col-12 col-lg-6">
          <label class="form-label">Interrupt Policy</label>
          <select class="form-select form-select-sm" data-scene-k="interruptPolicy">
            <option value="ALLOW" ${interruptPolicy === "ALLOW" ? "selected" : ""}>Allow</option>
            <option value="NO_INTERRUPT" ${interruptPolicy === "NO_INTERRUPT" ? "selected" : ""}>No Interrupt</option>
            <option value="RESTART" ${interruptPolicy === "RESTART" ? "selected" : ""}>Restart</option>
            <option value="QUEUE" ${interruptPolicy === "QUEUE" ? "selected" : ""}>Queue</option>
          </select>
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Duplicate Policy</label>
          <select class="form-select form-select-sm" data-scene-k="duplicatePolicy">
            <option value="ALLOW" ${duplicatePolicy === "ALLOW" ? "selected" : ""}>Allow</option>
            <option value="DROP_IF_PLAYING" ${duplicatePolicy === "DROP_IF_PLAYING" ? "selected" : ""}>Drop If Playing</option>
            <option value="DROP_IF_QUEUED" ${duplicatePolicy === "DROP_IF_QUEUED" ? "selected" : ""}>Drop If Queued</option>
            <option value="COALESCE" ${duplicatePolicy === "COALESCE" ? "selected" : ""}>Coalesce</option>
          </select>
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Cooldown (ms)</label>
          <input type="number" min="0" class="form-control form-control-sm" data-scene-k="cooldownMs" value="${Number(scene.cooldownMs || 0)}">
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Transition</label>
          <select class="form-select form-select-sm" data-scene-k="transitionType">
            <option value="CUT" ${transitionType === "CUT" ? "selected" : ""}>Cut</option>
            <option value="FADE" ${transitionType === "FADE" ? "selected" : ""}>Fade</option>
            <option value="DISSOLVE" ${transitionType === "DISSOLVE" ? "selected" : ""}>Dissolve</option>
            <option value="ZOOM" ${transitionType === "ZOOM" ? "selected" : ""}>Zoom</option>
          </select>
        </div>

        <div class="col-12 col-lg-6">
          <label class="form-label">Transition Duration (ms)</label>
          <input type="number" min="0" max="5000" class="form-control form-control-sm" data-scene-k="transitionDurationMs" value="${transitionDurationMs}">
        </div>

        <div class="col-12">
          <div class="card border-secondary-subtle">
            <div class="card-body py-2">
              <div class="fw-semibold small mb-2">Queue</div>
              <div class="row g-2">
                <div class="col-12 col-lg-4">
                  <div class="form-check form-switch m-0">
                    <input class="form-check-input" type="checkbox" data-scene-k="queueEnabled" ${boolAttr(!!queue.enabled)}>
                    <label class="form-check-label">Enable Queue</label>
                  </div>
                </div>
                <div class="col-12 col-lg-4">
                  <label class="form-label small mb-1">Max Length</label>
                  <input type="number" min="0" class="form-control form-control-sm" data-scene-k="queueMaxLength" value="${Number(queue.maxLength || 8)}">
                </div>
                <div class="col-12 col-lg-4">
                  <div class="form-check form-switch mt-4">
                    <input class="form-check-input" type="checkbox" data-scene-k="queueDedupe" ${boolAttr(queue.dedupe !== false)}>
                    <label class="form-check-label">Dedupe Queue</label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-12">
          <div class="card border-secondary-subtle">
            <div class="card-body py-2">
              <div class="fw-semibold small mb-2">Scene Overlays</div>
              ${sceneOverlaysEditorHtml(scene)}
            </div>
          </div>
        </div>

        <div class="col-12">
          <div class="card border-secondary-subtle">
            <div class="card-body py-2">
              <div class="fw-semibold small mb-2">Audio Behaviour</div>
              <div class="row g-3">
                ${audioTypes.map((k) => `
                  <div class="col-12">
                    <div class="small text-secondary mb-1 text-capitalize">${k}</div>
                    <div class="d-flex flex-wrap gap-3">
                      ${["pause", "duck", "allow"].map((mode) => `
                        <label class="form-check">
                          <input
                            class="form-check-input"
                            type="radio"
                            name="scene-audio-${esc(scene.id)}-${esc(k)}"
                            data-scene-audio-type="${esc(k)}"
                            value="${mode}"
                            ${audioChoiceFor(k) === mode ? "checked" : ""}
                          >
                          <span class="form-check-label text-capitalize">${mode}</span>
                        </label>
                      `).join("")}
                    </div>
                  </div>
                `).join("")}
                <div class="col-12">
                  <div class="form-check form-switch m-0">
                    <input class="form-check-input" type="checkbox" data-scene-k="resumeOnEnd" ${boolAttr(audioBehaviour.resumeOnEnd !== false)}>
                    <label class="form-check-label">Resume Audio On End</label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-12">
          <button type="button" class="btn btn-outline-danger btn-sm w-100 d-inline-flex align-items-center justify-content-center gap-1" id="media-delete-scene"><i class="fa fa-trash"></i><span>Remove</span></button>
        </div>
      </div>
    `;
  }

  function renderOverlayEditor() {
    if (!elOverlayEditor || !elOverlaySelect || !elOverlayLayersEditor) return;
    const rows = overlays();
    if (!rows.length) {
      elOverlaySelect.innerHTML = `<option value="">No overlays yet</option>`;
      elOverlaySelect.disabled = true;
       writeSelectedOverlayId("");
      elOverlayEditor.innerHTML = `<div class="text-secondary">Create an overlay to start building.</div>`;
      elOverlayLayersEditor.innerHTML = `<div class="text-secondary">Create an overlay to add layers.</div>`;
      if (elOverlayPreview) elOverlayPreview.innerHTML = "";
      return;
    }
    if (!overlayById(state.selectedOverlayId)) state.selectedOverlayId = String(rows[0].id || "");
    writeSelectedOverlayId(state.selectedOverlayId);
    elOverlaySelect.disabled = false;
    elOverlaySelect.innerHTML = rows.map((ov) => `<option value="${esc(ov.id)}">${esc(ov.name || ov.id)}</option>`).join("");
    elOverlaySelect.value = String(state.selectedOverlayId || rows[0]?.id || "");
    const overlay = overlayById(state.selectedOverlayId);
    elOverlayEditor.innerHTML = overlay ? renderOverlayOptions(overlay, { includeDelete: true }) : `<div class="text-secondary">Select an overlay.</div>`;
    renderOverlayLayersEditor();
    renderOverlayPreview();
  }

  function renderOverlayLayersEditor() {
    if (!elOverlayLayersEditor) return;
    const overlay = overlayById(state.selectedOverlayId);
    if (!overlay) {
      elOverlayLayersEditor.innerHTML = `<div class="text-secondary">Select an overlay.</div>`;
      return;
    }
    const layers = overlayLayers(overlay);
    if (!layers.length) state.selectedLayerIdx = -1;
    else if (state.selectedLayerIdx < 0 || state.selectedLayerIdx >= layers.length) state.selectedLayerIdx = 0;
    const listHtml = layers.length
      ? layers.map((layer, idx) => `
          <div class="media-overlay-row ${idx === state.selectedLayerIdx ? "border-primary" : ""}" data-layer-idx="${idx}" data-layer-card="${idx}">
            <div class="media-overlay-header">
              <div class="d-flex align-items-center gap-2 min-w-0">
                <span class="text-secondary"><i class="fa fa-layer-group"></i></span>
                <div class="media-overlay-title">${esc(layer.name || `Layer ${idx + 1}`)}</div>
              </div>
              <div class="d-flex align-items-center gap-2">
                ${idx === state.selectedLayerIdx ? '<span class="badge text-bg-primary">Editing</span>' : ""}
                <button type="button" class="btn btn-outline-secondary btn-sm" data-layer-move="up" title="Move up" ${idx <= 0 ? "disabled" : ""}><i class="fa fa-chevron-up"></i></button>
                <button type="button" class="btn btn-outline-secondary btn-sm" data-layer-move="down" title="Move down" ${idx >= layers.length - 1 ? "disabled" : ""}><i class="fa fa-chevron-down"></i></button>
                <button type="button" class="btn btn-outline-danger btn-sm" data-layer-remove title="Remove layer"><i class="fa fa-trash"></i></button>
              </div>
            </div>
            <div class="pt-2 mt-2">
              ${renderLayerOptions(layer)}
            </div>
          </div>
        `).join("")
      : `<div class="text-secondary">No layers yet.</div>`;
    elOverlayLayersEditor.innerHTML = `
      <div class="d-flex gap-2 align-items-center mb-3">
        <select class="form-select form-select-sm" id="media-overlay-layer-type">
          <option value="text">Text</option>
          <option value="image">Image</option>
        </select>
        <button type="button" class="btn btn-success btn-sm text-nowrap" id="media-add-layer"><i class="fa fa-plus me-1"></i>Add Layer</button>
      </div>
      <div id="media-overlay-layers-wrap">${listHtml}</div>
    `;
  }

  function renderPreview() {
    const scene = sceneById(state.selectedSceneId);
    if (!elPreview) return;
    if (!scene) {
      if (previewRenderer) previewRenderer.clear();
      elPreview.innerHTML = "";
      return;
    }
    const renderer = ensurePreviewRenderer();
    if (!renderer) return;
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
    fitPreviewStage();
    renderer.render(buildPreviewPayload(scene));
    const previewEmpty = elPreview.querySelector("[data-preview-empty]");
    if (previewEmpty) previewEmpty.classList.toggle("d-none", !!String(scene.baseAssetId || "").trim());
    if (!elPreview.classList.contains("is-ready")) {
      window.requestAnimationFrame(() => {
        fitPreviewStage();
        renderer.render(buildPreviewPayload(scene));
        elPreview.classList.add("is-ready");
      });
    }
    const nextVideo = elPreview.querySelector("video#media-preview-video");
    if (nextVideo) nextVideo.setAttribute("data-asset-id", String(scene.baseAssetId || ""));
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
    } else if (nextVideo) {
      nextVideo.muted = !!scene.mute;
      if (state.previewShouldPlay) {
        const start = () => { nextVideo.play().catch(() => {}); };
        if (nextVideo.readyState >= 1) start();
        else nextVideo.addEventListener("loadedmetadata", start, { once: true });
      } else {
        pauseAtFirstFrame(nextVideo);
      }
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
    const overlaysList = effectiveSceneOverlays(scene, { includeInactive: true, forEditor: true });
    if (!scene || !Array.isArray(overlaysList) || !elPreview) return false;
    if (!overlaysList[idx]) return false;
    const renderer = ensurePreviewRenderer();
    if (!renderer) return false;
    renderer.render(buildPreviewPayload(scene));
    return !!elPreview.querySelector(`.media-preview-overlay[data-overlay-idx="${idx}"]`);
  }

  function syncSceneFromEditor() {
    const scene = sceneById(state.selectedSceneId);
    if (!scene || !elEditor) return;

    scene.name = String(elEditor.querySelector('[data-scene-k="name"]')?.value || "").trim() || scene.name;
    scene.baseAssetId = String(elEditor.querySelector('[data-scene-k="baseAssetId"]')?.value || "").trim();
    scene.priority = Math.round(Number(elEditor.querySelector('[data-scene-k="priority"]')?.value || 100));
    scene.blendMode = String(elEditor.querySelector('[data-scene-k="blendMode"]')?.value || "STOP_LOWER").trim().toUpperCase();
    scene.loop = !!elEditor.querySelector('[data-scene-k="loop"]')?.checked;
    scene.mute = !elEditor.querySelector('[data-scene-k="includeAudio"]')?.checked;
    scene.interruptPolicy = String(elEditor.querySelector('[data-scene-k="interruptPolicy"]')?.value || "NO_INTERRUPT").trim().toUpperCase();
    scene.duplicatePolicy = String(elEditor.querySelector('[data-scene-k="duplicatePolicy"]')?.value || "DROP_IF_PLAYING").trim().toUpperCase();
    scene.cooldownMs = Math.max(0, Math.round(Number(elEditor.querySelector('[data-scene-k="cooldownMs"]')?.value || 0)));
    scene.transition = {
      type: String(elEditor.querySelector('[data-scene-k="transitionType"]')?.value || "CUT").trim().toUpperCase(),
      durationMs: Math.max(0, Math.min(5000, Math.round(Number(elEditor.querySelector('[data-scene-k="transitionDurationMs"]')?.value || 0)))),
    };
    if (scene.transition.type === "CUT") scene.transition.durationMs = 0;
    scene.screens = Array.from(elEditor.querySelectorAll("[data-scene-screen]:checked")).map((el) => String(el.value || "").trim()).filter(Boolean);
    if (!scene.screens.length) scene.screens = ["backbox"];
    scene.queue = {
      enabled: !!elEditor.querySelector('[data-scene-k="queueEnabled"]')?.checked,
      maxLength: Math.max(0, Math.round(Number(elEditor.querySelector('[data-scene-k="queueMaxLength"]')?.value || 8))),
      dedupe: !!elEditor.querySelector('[data-scene-k="queueDedupe"]')?.checked,
    };
    const collectAudioMode = (mode) => Array.from(elEditor.querySelectorAll('[data-scene-audio-type]:checked'))
      .filter((el) => String(el.value || "").trim() === String(mode || "").trim())
      .map((el) => String(el.getAttribute("data-scene-audio-type") || "").trim())
      .filter(Boolean);
    scene.audioBehaviour = {
      pause: collectAudioMode("pause"),
      duck: collectAudioMode("duck"),
      allow: collectAudioMode("allow"),
      resumeOnEnd: !!elEditor.querySelector('[data-scene-k="resumeOnEnd"]')?.checked,
    };
    state.config.settings = state.config.settings || {};
    state.config.settings.defaultScenesByDisplay = defaultScenesByDisplay();
    state.config.settings.autoplayByDisplay = autoplayByDisplay();
  }

  function syncOverlayFromEditor() {
    const overlay = overlayById(state.selectedOverlayId);
    if (!overlay || !elOverlayEditor) return;
    overlay.name = String(elOverlayEditor.querySelector('[data-k="name"]')?.value || "").trim() || overlay.name;
    overlay.previewAssetId = String(elOverlayEditor.querySelector('[data-k="previewAssetId"]')?.value || "").trim();
  }

  function syncLayerSizeFields(idx, layer) {
    if (!elOverlayLayersEditor || !Number.isFinite(idx) || !layer) return;
    const card = elOverlayLayersEditor.querySelector(`[data-layer-card="${idx}"]`);
    if (!card) return;
    const wInput = card.querySelector('[data-layer-k="wPct"]');
    const hInput = card.querySelector('[data-layer-k="hPct"]');
    if (wInput) wInput.value = String(Number(layer.wPct || 0).toFixed(3));
    if (hInput) hInput.value = String(Number(layer.hPct || 0).toFixed(3));
  }

  function scaleTextLayerBoxForFontSize(layer, prevFontSizePx, nextFontSizePx) {
    const prevPx = Math.max(1, Number(prevFontSizePx || 0));
    const nextPx = Math.max(1, Number(nextFontSizePx || 0));
    if (!layer || !Number.isFinite(prevPx) || !Number.isFinite(nextPx) || prevPx <= 0) return;
    if (Math.abs(nextPx - prevPx) < 0.001) return;
    const ratio = nextPx / prevPx;
    layer.wPct = q025(clamp(Number(layer.wPct || 20) * ratio, 0.25, 100));
    layer.hPct = q025(clamp(Number(layer.hPct || 8) * ratio, 0.25, 100));
  }

  function syncLayerFromEditor(layerIdx = state.selectedLayerIdx, options = {}) {
    const overlay = overlayById(state.selectedOverlayId);
    const idx = Number(layerIdx);
    const layer = overlay && Number.isFinite(idx) && idx >= 0 ? overlayLayers(overlay)[idx] || null : null;
    if (!layer || !elOverlayLayersEditor) return;
    const card = elOverlayLayersEditor.querySelector(`[data-layer-card="${idx}"]`);
    if (!card) return;
    const sourceKey = String(options?.sourceKey || "").trim();
    const textMode = String(card.querySelector('[data-layer-k="textMode"]')?.value || "").trim();
    const valueKeyPreset = String(card.querySelector('[data-layer-k="valueKeyPreset"]')?.value || "").trim();
    const existingValueKey = String(layer.valueKey || "").trim();
    const fallbackVariableKey = firstAvailableVariableKey();
    const resolvedValueKey = textMode === "variable" ? (valueKeyPreset || existingValueKey || fallbackVariableKey) : "";
    const bgMode = String(card.querySelector('[data-layer-k="bgMode"]')?.value || "").trim();
    const existingBg = String(layer.bgColor || "").trim();
    const bgInputValue = String(card.querySelector('[data-layer-k="bgColor"]')?.value || "").trim();
    layer.name = String(card.querySelector('[data-layer-k="name"]')?.value || "").trim() || layer.name;
    layer.type = normalizeOverlayType(card.querySelector('[data-layer-k="type"]')?.value);
    layer.valueKey = resolvedValueKey;
    layer.text = String(card.querySelector('[data-layer-k="text"]')?.value || "").trim();
    layer.textAlign = normalizeTextAlign(card.querySelector('[data-layer-k="textAlign"]')?.value || layer.textAlign || "center");
    layer.textEffects = selectedTextEffectsFromRow(card, layer.textEffects || []);
    layer.xPct = q025(Number(card.querySelector('[data-layer-k="xPct"]')?.value || 0));
    layer.yPct = q025(Number(card.querySelector('[data-layer-k="yPct"]')?.value || 0));
    layer.wPct = q025(Number(card.querySelector('[data-layer-k="wPct"]')?.value || 20));
    layer.hPct = q025(Number(card.querySelector('[data-layer-k="hPct"]')?.value || 8));
    layer.rotateDeg = Number(card.querySelector('[data-layer-k="rotateDeg"]')?.value || 0);
    layer.scale = Number(layer.scale || 1);
    layer.opacity = Number(card.querySelector('[data-layer-k="opacity"]')?.value || 1);
    const prevFontSizePx = Number(layer.fontSizePx || 24);
    layer.fontSizePx = Number(card.querySelector('[data-layer-k="fontSizePx"]')?.value || 24);
    layer.fontFamily = String(card.querySelector('[data-layer-k="fontFamily"]')?.value || "").trim();
    layer.color = String(card.querySelector('[data-layer-k="color"]')?.value || "#ffffff");
    layer.bgColor = bgMode === "transparent" ? "transparent" : (bgInputValue || (existingBg && existingBg.toLowerCase() !== "transparent" ? existingBg : "#000000"));
    layer.assetId = String(card.querySelector('[data-layer-k="assetId"]')?.value || "").trim();
    layer.fit = ["cover", "contain", "fill", "none", "scale-down"].includes(String(card.querySelector('[data-layer-k="fit"]')?.value || "").trim().toLowerCase())
      ? String(card.querySelector('[data-layer-k="fit"]')?.value || "").trim().toLowerCase()
      : "contain";
    if (layer.type === "text" && textMode === "fixed") layer.valueKey = "";
    if (layer.type !== "text") layer.textEffects = [];
    if (layer.type === "text" && sourceKey === "fontSizePx") {
      scaleTextLayerBoxForFontSize(layer, prevFontSizePx, layer.fontSizePx);
      syncLayerSizeFields(idx, layer);
    }
  }

  function syncAllLayersFromEditor() {
    if (!elOverlayLayersEditor) return;
    const cards = Array.from(elOverlayLayersEditor.querySelectorAll("[data-layer-card]"));
    cards.forEach((card) => {
      const idx = Number(card.getAttribute("data-layer-card"));
      if (Number.isFinite(idx) && idx >= 0) syncLayerFromEditor(idx);
    });
  }

  function beginDrag(mode, idx, evt, context = "scene") {
    const isOverlayContext = String(context || "") === "overlay";
    const scene = sceneById(state.selectedSceneId);
    const entry = isOverlayContext
      ? { overlay: overlayLayers(overlayById(state.selectedOverlayId))[idx] || null }
      : resolvedSceneOverlayEntries(scene, { includeInactive: true, forEditor: true })[idx];
    const ov = entry?.overlay || null;
    if (!ov) return;
    const targetPreview = isOverlayContext ? elOverlayPreview : elPreview;
    const rect = targetPreview?.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const centerX = rect.left + ((Number(ov.xPct || 0) + (Number(ov.wPct || 20) / 2)) / 100) * rect.width;
    const centerY = rect.top + ((Number(ov.yPct || 0) + (Number(ov.hPct || 8) / 2)) / 100) * rect.height;
    const startPointerDeg = Math.atan2(evt.clientY - centerY, evt.clientX - centerX) * (180 / Math.PI);

    dragState = {
      context: isOverlayContext ? "overlay" : "scene",
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
    if (isOverlayContext) {
      state.selectedLayerIdx = idx;
      renderOverlayLayersEditor();
      renderOverlayPreview();
    } else {
      state.selectedOverlayIdx = idx;
      renderPreview();
    }
  }

  function onDragMove(evt) {
    if (!dragState) return;
    const isOverlayContext = dragState.context === "overlay";
    const scene = sceneById(state.selectedSceneId);
    const ov = isOverlayContext
      ? (overlayLayers(overlayById(state.selectedOverlayId))[dragState.idx] || null)
      : resolvedSceneOverlayEntries(scene, { includeInactive: true, forEditor: true })[dragState.idx]?.overlay || null;
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
    if (isOverlayContext) {
      scheduleOverlayDragRefresh(dragState.idx, ov);
    } else if (!updatePreviewOverlayNode(dragState.idx)) {
      renderPreview();
    }
  }

  function onDragUp() {
    if (!dragState) return;
    const wasOverlayContext = dragState.context === "overlay";
    dragState = null;
    if (overlayDragRenderRaf) {
      window.cancelAnimationFrame(overlayDragRenderRaf);
      flushOverlayDragRefresh();
    }
    renderOverlayEditor();
    if (wasOverlayContext) {
      renderOverlayPreview();
      renderPreview();
    }
  }

  function blurArrowFocus() {
    const ae = document.activeElement;
    if (!ae || ae === document.body || ae === document.documentElement) return;
    const tag = String(ae.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (ae.isContentEditable) return;
    if (typeof ae.blur === "function") ae.blur();
    requestAnimationFrame(() => {
      const now = document.activeElement;
      if (!now || now === document.body || now === document.documentElement) return;
      const nowTag = String(now.tagName || "").toUpperCase();
      if (nowTag === "INPUT" || nowTag === "TEXTAREA" || nowTag === "SELECT") return;
      if (now.isContentEditable) return;
      if (typeof now.blur === "function") now.blur();
    });
  }

  function updateOverlayPositionFields(idx, ov) {
    if (!elOverlayLayersEditor || !Number.isFinite(idx) || !ov) return;
    const card = elOverlayLayersEditor.querySelector(`[data-layer-card="${idx}"]`);
    if (!card) return;
    const xInput = card.querySelector('[data-layer-k="xPct"]');
    const yInput = card.querySelector('[data-layer-k="yPct"]');
    if (xInput) xInput.value = String(Number(ov.xPct || 0).toFixed(3));
    if (yInput) yInput.value = String(Number(ov.yPct || 0).toFixed(3));
    syncLayerSizeFields(idx, ov);
  }

  function nudgeSelectedOverlayByPixels(dxPx, dyPx) {
    const overlayTab = isOverlaysPaneActive();
    const targetPreview = overlayTab ? elOverlayPreview : elPreview;
    if (!targetPreview) return false;
    const idx = overlayTab ? Number(state.selectedLayerIdx) : Number(state.selectedOverlayIdx);
    if (!Number.isFinite(idx) || idx < 0) return false;
    const scene = sceneById(state.selectedSceneId);
    const ov = overlayTab
      ? selectedLayer()
      : resolvedSceneOverlayEntries(scene, { includeInactive: true, forEditor: true })[idx]?.overlay || null;
    if (!ov) return false;

    const rect = targetPreview.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return false;
    const prevX = Number(ov.xPct || 0);
    const prevY = Number(ov.yPct || 0);
    const curXPx = (prevX / 100) * rect.width;
    const curYPx = (prevY / 100) * rect.height;
    const nextXPx = clamp(curXPx + Number(dxPx || 0), 0, rect.width);
    const nextYPx = clamp(curYPx + Number(dyPx || 0), 0, rect.height);
    const nextX = (nextXPx / rect.width) * 100;
    const nextY = (nextYPx / rect.height) * 100;
    if (Math.abs(nextX - prevX) < 0.0001 && Math.abs(nextY - prevY) < 0.0001) return false;

    ov.xPct = nextX;
    ov.yPct = nextY;
    setDirty(true);
    if (overlayTab) {
      scheduleOverlayDragRefresh(idx, ov);
    } else if (!updatePreviewOverlayNode(idx)) {
      renderPreview();
    }
    return true;
  }

  function isScenesPaneActive() {
    const pane = root.querySelector("#media-pane-scenes");
    return !!(pane && pane.classList.contains("active"));
  }

  function isOverlaysPaneActive() {
    const pane = root.querySelector("#media-pane-overlays");
    return !!(pane && pane.classList.contains("active"));
  }

  function renderRuntimeTable() {
    if (!elRuntime) return;
    const active = runtimeRows();
    if (elStopAll) {
      elStopAll.disabled = !active.length;
      elStopAll.setAttribute("aria-disabled", active.length ? "false" : "true");
    }
    if (elRuntimeFooter) elRuntimeFooter.classList.toggle("d-none", !isGodotRuntime());
    if (!active.length) {
      elRuntime.innerHTML = `<div class="text-secondary small">No active scenes.</div>`;
      return;
    }
    elRuntime.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm mb-0 align-middle">
          <thead><tr><th>Scene</th><th>Outputs</th><th>PID</th><th>Status</th><th>Started</th><th class="text-end">Action</th></tr></thead>
          <tbody>
            ${active.map((a) => `
              <tr>
                <td>${esc((sceneById(a.sceneId || "")?.name || "").trim() || (a.sceneId || ""))}</td>
                <td>${esc(Array.isArray(a.outputs) ? a.outputs.map((out) => {
                  const typ = runtimeLaunchLabel({ launchMode: out.type });
                  const target = displayLabelById(out.displayId || "");
                  return `${typ}${target && target !== "-" ? ` / ${target}` : ""}`;
                }).join(", ") : displayLabelById(a.displayId || ""))}</td>
                <td>${esc(runtimePidLabel(a))}</td>
                <td>${esc(String(a.state || "running"))}</td>
                <td>${esc(runtimeStartedLabel(a))}</td>
                <td class="text-end"><button type="button" class="btn btn-outline-danger btn-sm" data-runtime-stop-session="${esc(a.id || a.runtimeId || a.sessionId || "")}" data-runtime-stop-scene="${esc(a.sceneId || "")}">Stop</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderRuntime() {
    if (isGodotRuntime()) renderRuntimeEnginePanel();
    else if (elRuntimeEnginePanel) elRuntimeEnginePanel.innerHTML = "";
    if (elRuntimeGodotPanel) {
      elRuntimeGodotPanel.classList.toggle("d-none", !isGodotRuntime());
      if (isGodotRuntime()) {
        const deferGodotRender = shouldDeferGodotRuntimePanelRender();
        if (!deferGodotRender) renderGodotRuntimePanel();
      } else {
        elRuntimeGodotPanel.innerHTML = "";
      }
    }
    renderRuntimeTable();
  }

  function renderRuntimeEnginePanel() {
    if (!elRuntimeEnginePanel) return;
    const activeRows = runtimeRows();
    const envRenderer = state.env?.renderer || {};
    const tooling = state.env?.tooling || {};
    const targets = godotRuntimeTargets();
    const anyRunning = activeRows.length > 0;
    const godotFound = !!envRenderer.godotFound;
    const wsClientReady = !!tooling.websocketClientAvailable;
    const backendTone = godotFound ? "success" : "danger";
    const toolingTone = wsClientReady ? "success" : "warning";
    elRuntimeEnginePanel.innerHTML = `
      <div class="media-runtime-panel-card">
        <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
          <div>
            <h6 class="mb-1">Runtime Engine</h6>
            <div class="small text-secondary" data-godot-engine-summary>Godot launches on demand when you start a target or play a scene.</div>
          </div>
          <div class="d-flex gap-2 flex-wrap">
            <span class="badge text-bg-${anyRunning ? "success" : "secondary"}" data-godot-engine-state>${esc(anyRunning ? "active launches" : "idle")}</span>
          </div>
        </div>

        <div class="media-runtime-kv">
          <div class="text-secondary">Backend</div><div>Godot</div>
          <div class="text-secondary">Launch model</div><div>On-demand per target</div>
          <div class="text-secondary">Configured targets</div><div>${esc(String(targets.length))}</div>
          <div class="text-secondary">Active launches</div><div>${esc(String(activeRows.length))}</div>
          <div class="text-secondary">Godot binary</div><div><span class="badge text-bg-${backendTone}">${esc(godotFound ? "found" : "missing")}</span></div>
          <div class="text-secondary">WebSocket client</div><div><span class="badge text-bg-${toolingTone}">${esc(wsClientReady ? "ready" : "missing")}</span></div>
          <div class="text-secondary">Binary path</div><div><code>${esc(String(envRenderer.binary || ""))}</code></div>
        </div>
      </div>
    `;
  }

  function currentGodotRuntimePanelState() {
    if (!elRuntimeGodotPanel) return {};
    const sceneSel = elRuntimeGodotPanel.querySelector("[data-godot-scene-select]");
    const displaySel = elRuntimeGodotPanel.querySelector("[data-godot-display-select]");
    const modeSel = elRuntimeGodotPanel.querySelector("[data-godot-mode-select]");
    const tokenKeyInput = elRuntimeGodotPanel.querySelector("[data-godot-token-key]");
    const tokenValueInput = elRuntimeGodotPanel.querySelector("[data-godot-token-value]");
    return {
      runtimeId: String(displaySel?.value || currentGodotRuntimeId()).trim(),
      sceneId: String(sceneSel?.value || "").trim(),
      displayId: String(displaySel?.value || "").trim(),
      mode: String(modeSel?.value || "").trim(),
      tokenKey: String(tokenKeyInput?.value || "").trim(),
      tokenValue: String(tokenValueInput?.value || "").trim(),
    };
  }

  function shouldDeferGodotRuntimePanelRender() {
    if (!elRuntimeGodotPanel) return false;
    const activeEl = document.activeElement;
    if (!(activeEl instanceof HTMLElement)) return false;
    if (!elRuntimeGodotPanel.contains(activeEl)) return false;
    return !!activeEl.closest(
      "[data-godot-scene-select], [data-godot-display-select], [data-godot-mode-select], [data-godot-token-key], [data-godot-token-value]"
    );
  }

  function renderGodotRuntimePanel() {
    if (!elRuntimeGodotPanel) return;
    const panelState = currentGodotRuntimePanelState();
    const runtimeId = String(panelState.runtimeId || currentGodotRuntimeId()).trim();
    const targets = godotRuntimeTargets();
    const target = targets.find((row) => String(row.id || "") === runtimeId) || null;
    const overlayValues = state.runtime?.overlayValues?.[runtimeId] || {};
    const selectedSceneId = String(panelState.sceneId || state.selectedSceneId || "").trim();
    elRuntimeGodotPanel.innerHTML = `
      <div class="media-runtime-panel-card">
        <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
          <div>
            <h6 class="mb-1">Targets</h6>
            <div class="small text-secondary">Choose a display, mode, and scene, then launch an instance.</div>
            <div class="small text-secondary mt-1" data-godot-target-summary>Selected target: ${esc(runtimeTargetLabel(target, runtimeId) || runtimeId || "-")}</div>
          </div>
        </div>

        <div class="row g-3 align-items-end mb-3">
          <div class="col-lg-3">
            <label class="form-label small text-secondary mb-1">Display</label>
            <select class="form-select form-select-sm" data-godot-display-select>
              ${runtimeDisplayOptionsHtml(panelState.displayId || runtimeId || target?.displayId || target?.id || displays()[0]?.id || "")}
            </select>
          </div>
          <div class="col-lg-3">
            <label class="form-label small text-secondary mb-1">Window mode</label>
            <select class="form-select form-select-sm" data-godot-mode-select>
              <option value="windowed" ${String(panelState.mode || "").toLowerCase() === "windowed" ? "selected" : ""}>Windowed</option>
              <option value="fullscreen" ${String(panelState.mode || "").toLowerCase() !== "windowed" ? "selected" : ""}>Fullscreen</option>
            </select>
          </div>
          <div class="col-lg-4">
            <label class="form-label small text-secondary mb-1">Scene</label>
            <select class="form-select form-select-sm" data-godot-scene-select>
              ${authoredSceneOptionsHtml(selectedSceneId)}
            </select>
          </div>
          <div class="col-lg-2">
            <label class="form-label small text-secondary mb-1 d-block">&nbsp;</label>
            <button type="button" class="btn btn-success btn-sm w-100" data-godot-runtime-start><i class="fa fa-play me-1"></i>Launch / Play</button>
          </div>
        </div>

        <div class="row g-3">
          <div class="col-lg-4">
            <label class="form-label small text-secondary mb-1">Token</label>
            <input type="text" class="form-control form-control-sm" data-godot-token-key placeholder="score" value="${esc(panelState.tokenKey || "score")}">
          </div>
          <div class="col-lg-6">
            <label class="form-label small text-secondary mb-1">Value</label>
            <input type="text" class="form-control form-control-sm" data-godot-token-value placeholder="12345" value="${esc(panelState.tokenValue || String(overlayValues.score || "12345"))}">
          </div>
          <div class="col-lg-2 d-flex align-items-end">
            <button type="button" class="btn btn-outline-primary btn-sm w-100" data-godot-send-token>Update Token</button>
          </div>
        </div>

      </div>
    `;
  }

  function updateGodotRuntimePanelStatus() {
    renderRuntimeEnginePanel();
    if (!elRuntimeGodotPanel || elRuntimeGodotPanel.classList.contains("d-none")) return;
    const panelState = currentGodotRuntimePanelState();
    const runtimeId = String(panelState.runtimeId || currentGodotRuntimeId()).trim();
    const targets = godotRuntimeTargets();
    const target = targets.find((row) => String(row.id || "") === runtimeId) || null;
    const runtimeSummary = elRuntimeGodotPanel.querySelector("[data-godot-target-summary]");
    if (runtimeSummary) runtimeSummary.textContent = `Selected target: ${runtimeTargetLabel(target, runtimeId) || runtimeId || "-"}`;
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
      state.config = { settings: {}, displays: [], assets: [], overlays: [], scenes: [] };
    }

    if (envRes.status === "fulfilled") state.env = envRes.value;
    if (stateRes.status === "fulfilled") state.runtime = stateRes.value.state;
    if (!state.selectedGodotRuntimeId) {
      state.selectedGodotRuntimeId = currentGodotRuntimeId();
    }
    if (isGodotRuntime()) {
      try {
        const runtimeId = String(state.selectedGodotRuntimeId || "").trim();
        const statusRes = await api(`/runtime/status${runtimeId ? `?runtimeId=${encodeURIComponent(runtimeId)}` : ""}`);
        if (state.runtime) state.runtime.godotStatus = statusRes || null;
      } catch (_) {}
    }

    if (refreshDisplays && state.env?.displays?.length) {
      state.config.displays = state.env.displays;
      setDirty(true);
    }

    applyFontCatalogStyles();
    renderAssets();
    renderDisplays();
    renderDefaults();
    renderFonts();
    renderOverlayEditor();
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
      if (isOverlaysPaneActive()) {
        syncOverlayFromEditor();
        syncAllLayersFromEditor();
      }
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

  elFontUploadBrowse?.addEventListener("click", () => { if (!fontUploadInProgress) elFontUploadFile?.click(); });
  elFontUploadFile?.addEventListener("change", async () => {
    const files = Array.from(elFontUploadFile.files || []);
    if (!files.length) return;
    try { await uploadFontFiles(files); } catch (err) { alert(`Font upload failed: ${err.message}`); }
    elFontUploadFile.value = "";
  });

  if (elFontUploadDropzone) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach((name) => {
      elFontUploadDropzone.addEventListener(name, (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
      });
    });
    ["dragenter", "dragover"].forEach((name) => {
      elFontUploadDropzone.addEventListener(name, () => {
        if (!fontUploadInProgress) elFontUploadDropzone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((name) => {
      elFontUploadDropzone.addEventListener(name, () => {
        elFontUploadDropzone.classList.remove("is-dragover");
      });
    });
    elFontUploadDropzone.addEventListener("drop", async (evt) => {
      if (fontUploadInProgress) return;
      const files = Array.from(evt.dataTransfer?.files || []);
      if (!files.length) return;
      try { await uploadFontFiles(files); } catch (err) { alert(`Font upload failed: ${err.message}`); }
    });
    elFontUploadDropzone.addEventListener("keydown", (evt) => {
      if (fontUploadInProgress) return;
      if (evt.key === "Enter" || evt.key === " ") {
        evt.preventDefault();
        elFontUploadFile?.click();
      }
    });
    elFontUploadDropzone.addEventListener("click", (evt) => {
      if (fontUploadInProgress) return;
      if (evt.target && evt.target.closest && evt.target.closest("#media-font-upload-browse")) return;
      elFontUploadFile?.click();
    });
  }

  elFontFilter?.addEventListener("input", renderFonts);
  elFontSourceFilter?.addEventListener("change", renderFonts);
  elFontsTable?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-media-font-delete]");
    if (!btn) return;
    const fontId = String(btn.getAttribute("data-media-font-delete") || "").trim();
    if (!fontId) return;
    const ok = await askConfirm("Remove this custom font?", {
      title: "Remove Font",
      confirmLabel: "Remove",
      confirmClass: "btn-danger",
    });
    if (!ok) return;
    try {
      await api("/fonts/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fontId }),
      });
      await loadAll(false);
    } catch (err) {
      alert(`Remove font failed: ${err.message}`);
    }
  });

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

  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-media-asset-sort]");
    if (!btn) return;
    const key = String(btn.getAttribute("data-media-asset-sort") || "").trim().toLowerCase();
    if (!key) return;
    applyAssetSort(key);
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

  function syncDefaultDisplaySelection(e) {
    state.config.settings = state.config.settings || {};
    state.config.settings.godot = state.config.settings.godot && typeof state.config.settings.godot === "object"
      ? state.config.settings.godot
      : {};
    const settingField = e.target.closest("[data-settings-k]");
    if (settingField) {
      const key = String(settingField.getAttribute("data-settings-k") || "").trim();
      if (key === "godot.binary") {
        state.config.settings.godot.binary = String(settingField.value || "").trim();
      } else if (key === "godot.port") {
        state.config.settings.godot.port = Math.max(1024, Math.min(65535, Number(settingField.value || 17342) || 17342));
      } else if (key === "godot.autoRestart") {
        state.config.settings.godot.autoRestart = !!settingField.checked;
      } else if (key === "godot.debugVisible") {
        state.config.settings.godot.debugVisible = !!settingField.checked;
      }
    }
    const sel = e.target.closest("[data-default-display]");
    if (sel) {
      const mapping = { ...defaultScenesByDisplay() };
      const did = String(sel.getAttribute("data-default-display") || "").trim();
      const sceneId = String(sel.value || "").trim();
      if (!did) return;
      if (sceneId) mapping[did] = sceneId;
      else delete mapping[did];
      state.config.settings.defaultScenesByDisplay = mapping;
    }
    const toggle = e.target.closest("[data-autoplay-display]");
    if (toggle) {
      const mapping = { ...autoplayByDisplay() };
      const did = String(toggle.getAttribute("data-autoplay-display") || "").trim();
      if (!did) return;
      mapping[did] = !!toggle.checked;
      state.config.settings.autoplayByDisplay = mapping;
    }
    setDirty(true);
    renderDefaults();
  }

  elDefaultsEditor?.addEventListener("input", syncDefaultDisplaySelection);
  elDefaultsEditor?.addEventListener("change", syncDefaultDisplaySelection);
  root.querySelectorAll('[data-bs-toggle="tab"]').forEach((tabBtn) => {
    tabBtn.addEventListener("shown.bs.tab", () => {
      syncRuntimePolling();
      syncAssetConversionPolling();
    });
  });
  document.addEventListener("visibilitychange", () => {
    syncRuntimePolling();
    syncAssetConversionPolling();
  });

  elSceneSelect?.addEventListener("change", () => {
    const sceneId = String(elSceneSelect.value || "").trim();
    if (!sceneId) return;
    state.selectedSceneId = sceneId;
    writeSelectedSceneId(sceneId);
    state.previewShouldPlay = false;
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
      screens: [String(firstDisplay?.id || firstDisplay?.role || "backbox")],
      baseAssetId: String(firstAsset?.id || ""),
      priority: 100,
      blendMode: "STOP_LOWER",
      loop: true,
      mute: true,
      interruptPolicy: "NO_INTERRUPT",
      duplicatePolicy: "DROP_IF_PLAYING",
      cooldownMs: 0,
      transition: { type: "CUT", durationMs: 0 },
      queue: { enabled: false, maxLength: 8, dedupe: true },
      audioBehaviour: { pause: [], duck: [], allow: ["music", "sfx", "voice", "ambient"], resumeOnEnd: true },
      overlayRefs: [],
    };
    state.config.scenes.push(scene);
    state.selectedSceneId = scene.id;
    state.previewShouldPlay = false;
    state.selectedOverlayIdx = -1;
    setDirty(true);
    renderScenes();
  });

  elEditor?.addEventListener("input", (e) => {
    if (!e.target.closest("[data-scene-k], [data-scene-screen], [data-scene-audio-type]")) return;

    syncSceneFromEditor();
    setDirty(true);
    renderPreview();
    renderDefaults();
  });

  elEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-scene-k]")) return;
    syncSceneFromEditor();
    setDirty(true);
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
    state.config.overlays = overlays();
    const overlay = {
      id: uid("overlay"),
      name: `Overlay ${overlays().length + 1}`,
      previewAssetId: "",
      layers: [],
    };
    state.config.overlays.push(overlay);
    state.selectedOverlayId = overlay.id;
    state.selectedLayerIdx = -1;
    writeSelectedOverlayId(overlay.id);
    setDirty(true);
    renderOverlayEditor();
  });

  elOverlaySelect?.addEventListener("change", () => {
    const overlayId = String(elOverlaySelect.value || "").trim();
    stopOverlayPreviewPlayback();
    state.selectedOverlayId = overlayId || null;
    state.selectedLayerIdx = 0;
    writeSelectedOverlayId(state.selectedOverlayId);
    renderOverlayEditor();
  });

  elOverlayEditor?.addEventListener("input", (e) => {
    if (!e.target.closest("[data-k]")) return;
    syncOverlayFromEditor();
    setDirty(true);
    renderOverlayPreview();
    renderPreview();
  });

  elOverlayEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-k]")) return;
    syncOverlayFromEditor();
    setDirty(true);
    renderOverlayPreview();
    renderPreview();
  });

  elOverlayEditor?.addEventListener("click", async (e) => {
    if (!e.target.closest("#media-delete-overlay")) return;
    const overlay = overlayById(state.selectedOverlayId);
    if (!overlay) return;
    const ok = await askConfirm("Remove this overlay?", {
      title: "Remove Overlay",
      confirmLabel: "Remove",
      confirmClass: "btn-danger",
    });
    if (!ok) return;
    state.config.overlays = overlays().filter((ov) => String(ov.id || "") !== String(overlay.id || ""));
    state.config.scenes = scenes().map((scene) => ({
      ...scene,
      overlayRefs: sceneOverlayRefs(scene).filter((ref) => String(ref?.overlayId || "") !== String(overlay.id || "")),
    }));
    state.selectedOverlayId = state.config.overlays[0]?.id || null;
    state.selectedLayerIdx = 0;
    writeSelectedOverlayId(state.selectedOverlayId);
    if (state.selectedOverlayIdx >= sceneOverlayRefs(sceneById(state.selectedSceneId)).length) state.selectedOverlayIdx = -1;
    setDirty(true);
    renderOverlayEditor();
    renderScenes();
  });

  elOverlayLayersEditor?.addEventListener("input", (e) => {
    if (!e.target.closest("[data-layer-k]")) return;
    const card = e.target.closest("[data-layer-card]");
    const layerIdx = Number(card?.getAttribute("data-layer-card"));
    const sourceKey = String(e.target.getAttribute("data-layer-k") || "").trim();
    if (Number.isFinite(layerIdx) && layerIdx >= 0 && layerIdx !== state.selectedLayerIdx) {
      state.selectedLayerIdx = layerIdx;
    }
    if (e.target.matches('input[type="range"][data-layer-k="rotateDeg"]')) {
      const label = card?.querySelector('[data-layer-k-label="rotateDeg"]');
      if (label) label.textContent = `${Math.round(Number(e.target.value || 0))}\u00b0`;
    }
    if (e.target.matches('input[type="range"][data-layer-k="opacity"]')) {
      const label = card?.querySelector('[data-layer-k-label="opacity"]');
      if (label) label.textContent = Number(e.target.value || 0).toFixed(1);
    }
    syncLayerFromEditor(layerIdx, { sourceKey });
    setDirty(true);
    const structureChange = e.target.matches('[data-layer-k="type"],[data-layer-k="textMode"],[data-layer-k="bgMode"],[data-layer-k="valueKeyPreset"]');
    if (structureChange) {
      renderOverlayLayersEditor();
      renderOverlayPreview();
      renderPreview();
      return;
    }
    renderOverlayPreview();
    renderPreview();
  });

  elOverlayLayersEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-layer-k]")) return;
    const card = e.target.closest("[data-layer-card]");
    const layerIdx = Number(card?.getAttribute("data-layer-card"));
    const sourceKey = String(e.target.getAttribute("data-layer-k") || "").trim();
    if (Number.isFinite(layerIdx) && layerIdx >= 0 && layerIdx !== state.selectedLayerIdx) {
      state.selectedLayerIdx = layerIdx;
    }
    syncLayerFromEditor(layerIdx, { sourceKey });
    setDirty(true);
    if (e.target.matches('[data-layer-k="type"],[data-layer-k="textMode"],[data-layer-k="bgMode"],[data-layer-k="valueKeyPreset"]')) {
      renderOverlayLayersEditor();
    }
    renderOverlayPreview();
    renderPreview();
  });

  elOverlayLayersEditor?.addEventListener("click", async (e) => {
    const overlay = overlayById(state.selectedOverlayId);
    if (!overlay) return;
    if (e.target.closest("#media-add-layer")) {
      const type = String(elOverlayLayersEditor.querySelector("#media-overlay-layer-type")?.value || "text").trim().toLowerCase();
      overlay.layers = overlayLayers(overlay);
      overlay.layers.push({
        id: uid("layer"),
        name: `Layer ${overlay.layers.length + 1}`,
        type: type === "image" ? "image" : "text",
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
      });
      state.selectedLayerIdx = overlay.layers.length - 1;
      setDirty(true);
      renderOverlayLayersEditor();
      renderOverlayPreview();
      renderPreview();
      return;
    }
    if (e.target.closest("[data-layer-remove]")) {
      const row = e.target.closest("[data-layer-idx]");
      const idx = Number(row?.getAttribute("data-layer-idx"));
      if (!Number.isFinite(idx)) return;
      overlay.layers = overlayLayers(overlay);
      overlay.layers.splice(idx, 1);
      if (state.selectedLayerIdx >= overlay.layers.length) state.selectedLayerIdx = overlay.layers.length - 1;
      setDirty(true);
      renderOverlayLayersEditor();
      renderOverlayPreview();
      renderPreview();
      return;
    }
    const moveBtn = e.target.closest("[data-layer-move]");
    if (moveBtn) {
      const row = e.target.closest("[data-layer-idx]");
      const idx = Number(row?.getAttribute("data-layer-idx"));
      if (!Number.isFinite(idx)) return;
      const dir = String(moveBtn.getAttribute("data-layer-move") || "").trim();
      const nextIdx = dir === "up" ? idx - 1 : idx + 1;
      if (!moveOverlayLayer(overlay, idx, nextIdx)) return;
      setDirty(true);
      renderOverlayLayersEditor();
      renderOverlayPreview();
      renderPreview();
      return;
    }
    const row = e.target.closest("[data-layer-idx]");
    if (row) {
      const idx = Number(row.getAttribute("data-layer-idx"));
      if (Number.isFinite(idx) && idx !== state.selectedLayerIdx) {
        state.selectedLayerIdx = idx;
        renderOverlayLayersEditor();
        renderOverlayPreview();
        renderPreview();
      }
    }
  });

  let sceneOverlayDragIdx = -1;

  elEditor?.addEventListener("click", async (e) => {
    const scene = sceneById(state.selectedSceneId);
    if (!scene) return;
    if (e.target.closest("#media-scene-overlay-add")) {
      const select = elEditor.querySelector("#media-scene-overlay-add-select");
      const overlayId = String(select?.value || "").trim();
      if (!overlayId) return;
      scene.overlayRefs = sceneOverlayRefs(scene);
      scene.overlayRefs.push({ overlayId, active: true });
      state.selectedOverlayIdx = scene.overlayRefs.length - 1;
      setDirty(true);
      renderSceneEditor();
      renderPreview();
      return;
    }
    if (e.target.closest("[data-scene-overlay-remove]")) {
      const row = e.target.closest("[data-overlay-idx]");
      if (!row) return;
      const idx = Number(row.getAttribute("data-overlay-idx"));
      scene.overlayRefs = sceneOverlayRefs(scene);
      scene.overlayRefs.splice(idx, 1);
      if (state.selectedOverlayIdx >= scene.overlayRefs.length) state.selectedOverlayIdx = scene.overlayRefs.length - 1;
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
    } else if (e.target.closest("#media-scene-overlays-wrap")) {
      clearOverlaySelection();
    }
  });

  elEditor?.addEventListener("change", (e) => {
    if (!e.target.closest("[data-scene-overlay-active]")) return;
    const scene = sceneById(state.selectedSceneId);
    const row = e.target.closest("[data-overlay-idx]");
    const idx = Number(row?.getAttribute("data-overlay-idx"));
    if (!scene || !Number.isFinite(idx)) return;
    scene.overlayRefs = sceneOverlayRefs(scene);
    const ref = normalizedOverlayRef(scene.overlayRefs[idx], idx);
    ref.active = !!e.target.checked;
    scene.overlayRefs[idx] = ref;
    setDirty(true);
    renderPreview();
  });

  elEditor?.addEventListener("dragstart", (e) => {
    const row = e.target.closest("[data-overlay-idx]");
    if (!row) return;
    sceneOverlayDragIdx = Number(row.getAttribute("data-overlay-idx"));
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
  });

  elEditor?.addEventListener("dragover", (e) => {
    if (!e.target.closest("[data-overlay-idx]")) return;
    e.preventDefault();
  });

  elEditor?.addEventListener("drop", (e) => {
    const scene = sceneById(state.selectedSceneId);
    const row = e.target.closest("[data-overlay-idx]");
    const toIdx = Number(row?.getAttribute("data-overlay-idx"));
    const fromIdx = Number(sceneOverlayDragIdx);
    if (!scene || !Number.isFinite(fromIdx) || !Number.isFinite(toIdx) || fromIdx === toIdx) return;
    scene.overlayRefs = sceneOverlayRefs(scene);
    const [moved] = scene.overlayRefs.splice(fromIdx, 1);
    scene.overlayRefs.splice(toIdx, 0, moved);
    state.selectedOverlayIdx = toIdx;
    sceneOverlayDragIdx = -1;
    setDirty(true);
    renderSceneEditor();
    renderPreview();
  });

  elEditor?.addEventListener("dragend", () => {
    sceneOverlayDragIdx = -1;
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

  elOverlayPreviewPlay?.addEventListener("click", async (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    if (overlayPreviewToggleBusy) return;
    const v = activeOverlayPreviewVideo();
    if (!v) return;
    overlayPreviewToggleBusy = true;
    try {
      const shouldPause = !v.paused && !v.ended;
      if (shouldPause) {
        state.overlayPreviewShouldPlay = false;
        v.pause();
      } else {
        state.overlayPreviewShouldPlay = true;
        if (v.ended) v.currentTime = 0;
        await v.play().catch(() => {});
      }
    } finally {
      overlayPreviewToggleBusy = false;
      updateOverlayPreviewControlsUi();
    }
  });

  elOverlayPreviewStop?.addEventListener("click", () => {
    const v = activeOverlayPreviewVideo();
    if (!v) return;
    state.overlayPreviewShouldPlay = false;
    try {
      v.pause();
      v.currentTime = 0;
    } catch (_) {}
    updateOverlayPreviewControlsUi();
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

  elOverlayPreviewScrub?.addEventListener("pointerdown", () => {
    overlayPreviewScrubbing = true;
  });
  elOverlayPreviewScrub?.addEventListener("pointerup", () => {
    overlayPreviewScrubbing = false;
    updateOverlayPreviewControlsUi();
  });
  elOverlayPreviewScrub?.addEventListener("change", () => {
    const v = activeOverlayPreviewVideo();
    if (!v || !Number.isFinite(v.duration) || v.duration <= 0) return;
    const ratio = clamp(Number(elOverlayPreviewScrub.value || 0) / 1000, 0, 1);
    v.currentTime = ratio * Number(v.duration || 0);
    overlayPreviewScrubbing = false;
    updateOverlayPreviewControlsUi();
  });
  elOverlayPreviewScrub?.addEventListener("input", () => {
    const v = activeOverlayPreviewVideo();
    if (!v || !Number.isFinite(v.duration) || v.duration <= 0) return;
    const ratio = clamp(Number(elOverlayPreviewScrub.value || 0) / 1000, 0, 1);
    const t = ratio * Number(v.duration || 0);
    if (elOverlayPreviewTime) elOverlayPreviewTime.textContent = `${fmtTime(t)} / ${fmtTime(v.duration || 0)}`;
    if (overlayPreviewScrubbing) {
      try { v.currentTime = t; } catch (_) {}
    }
  });

  elPreview?.addEventListener("mousedown", (evt) => {
    return;
  });

  elOverlayPreview?.addEventListener("mousedown", (evt) => {
    const overlay = evt.target.closest(".media-preview-overlay");
    if (!overlay) return;
    const idx = Number(overlay.getAttribute("data-overlay-idx"));
    if (Number.isFinite(idx) && idx >= 0 && idx !== state.selectedLayerIdx) {
      state.selectedLayerIdx = idx;
      renderOverlayLayersEditor();
      renderOverlayPreview();
      return;
    }
    const ov = selectedLayer();
    const ovType = normalizeOverlayType(ov?.type);
    if (!ov) return;
    const handle = evt.target.closest("[data-overlay-handle]");
    if (handle) {
      const mode = String(handle.getAttribute("data-overlay-handle") || "");
      if (mode === "resize" || mode === "rotate") {
        evt.preventDefault();
        beginDrag(mode, idx, evt, "overlay");
      }
      return;
    }
    evt.preventDefault();
    beginDrag("move", idx, evt, "overlay");
  });

  document.addEventListener("mousemove", onDragMove);
  document.addEventListener("mouseup", onDragUp);
  document.addEventListener("keydown", (evt) => {
    const target = evt.target;
    if (target && (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable
    )) {
      return;
    }

    if (evt.key === "Escape") {
      if (isOverlaysPaneActive()) return;
      clearOverlaySelection();
      return;
    }

    if (evt.altKey || evt.ctrlKey || evt.metaKey) return;
    const isArrowKey = evt.key === "ArrowLeft" || evt.key === "ArrowRight" || evt.key === "ArrowUp" || evt.key === "ArrowDown";
    if (!isArrowKey) return;
    if (!isOverlaysPaneActive()) return;

    const dxPx = evt.key === "ArrowLeft" ? -1 : (evt.key === "ArrowRight" ? 1 : 0);
    const dyPx = evt.key === "ArrowUp" ? -1 : (evt.key === "ArrowDown" ? 1 : 0);
    if (nudgeSelectedOverlayByPixels(dxPx, dyPx)) {
      evt.preventDefault();
      return;
    }

    evt.preventDefault();
    blurArrowFocus();
  });

  elRuntime?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-runtime-stop-scene]");
    if (!btn) return;
    const sceneId = String(btn.getAttribute("data-runtime-stop-scene") || "").trim();
    const sessionId = String(btn.getAttribute("data-runtime-stop-session") || "").trim();
    if (!sceneId && !sessionId) return;
    try {
      await api("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sceneId, sessionId }),
      });
      await refreshRuntimeState();
    } catch (err) {
      alert(`Stop failed: ${err.message}`);
    }
  });

  elRuntimeGodotPanel?.addEventListener("click", async (e) => {
    const target = e.target.closest("[data-godot-runtime-start], [data-godot-send-token]");
    if (!target) return;
    const sceneSel = elRuntimeGodotPanel.querySelector("[data-godot-scene-select]");
    const displaySel = elRuntimeGodotPanel.querySelector("[data-godot-display-select]");
    const modeSel = elRuntimeGodotPanel.querySelector("[data-godot-mode-select]");
    const tokenKeyInput = elRuntimeGodotPanel.querySelector("[data-godot-token-key]");
    const tokenValueInput = elRuntimeGodotPanel.querySelector("[data-godot-token-value]");
    const runtimeId = String(displaySel?.value || currentGodotRuntimeId()).trim();
    try {
      if (target.matches("[data-godot-runtime-start]")) {
        const sceneId = String(sceneSel?.value || "").trim();
        if (sceneId === "no_scene" || !sceneId) {
          await api("/runtime/launch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              runtimeId,
              displayId: displaySel?.value || "",
              launchMode: modeSel?.value || "fullscreen",
              sceneId: "no_scene",
            }),
          });
        } else {
          await api("/play", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              sceneId,
              displayId: displaySel?.value || "",
              launchMode: modeSel?.value || "fullscreen",
            }),
          });
        }
      } else if (target.matches("[data-godot-send-token]")) {
        const tokenKey = String(tokenKeyInput?.value || "").trim();
        if (!tokenKey) throw new Error("Enter a token name first");
        await api("/runtime/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ runtimeId, cmd: "UPDATE_TEXT", text: { key: tokenKey, value: tokenValueInput?.value || "" } }),
        });
      }
      await refreshRuntimeState();
    } catch (err) {
      alert(`Godot runtime action failed: ${err.message}`);
    }
  });

  elRuntimeGodotPanel?.addEventListener("change", async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.matches("[data-godot-scene-select]")) {
      const sceneSel = elRuntimeGodotPanel.querySelector("[data-godot-scene-select]");
      const sceneId = String(sceneSel?.value || "").trim();
      state.selectedSceneId = sceneId || null;
      writeSelectedSceneId(sceneId);
      return;
    }
    if (!target.matches("[data-godot-display-select], [data-godot-mode-select]")) return;
    const displaySel = elRuntimeGodotPanel.querySelector("[data-godot-display-select]");
    const modeSel = elRuntimeGodotPanel.querySelector("[data-godot-mode-select]");
    const runtimeId = String(displaySel?.value || currentGodotRuntimeId()).trim();
    state.selectedGodotRuntimeId = runtimeId || null;
    try {
      await api("/runtime/display", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          runtimeId,
          displayId: displaySel?.value || "",
          mode: modeSel?.value || "fullscreen",
        }),
      });
      await refreshRuntimeState();
    } catch (err) {
      alert(`Display update failed: ${err.message}`);
    }
  });

  elStopAll?.addEventListener("click", async () => {
    try {
      if (isGodotRuntime()) {
        const targets = godotRuntimeTargets();
        if (targets.length) {
          await Promise.all(targets.map((row) => api("/runtime/stop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ runtimeId: String(row.id || "") }),
          })));
        }
      } else {
        await api("/stop", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
      }
      await refreshRuntimeState();
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

  syncRuntimePolling();

  window.addEventListener("resize", () => {
    schedulePreviewLayoutRerender();
  });

  const previewStageWrap = elPreview?.closest(".media-preview-stage-wrap") || null;
  if (previewStageWrap && typeof ResizeObserver !== "undefined") {
    const previewResizeObserver = new ResizeObserver(() => {
      schedulePreviewLayoutRerender();
    });
    previewResizeObserver.observe(previewStageWrap);
  }

  const overlayPreviewStageWrap = elOverlayPreview?.closest(".media-preview-stage-wrap") || null;
  if (overlayPreviewStageWrap && typeof ResizeObserver !== "undefined") {
    const overlayPreviewResizeObserver = new ResizeObserver(() => {
      syncOverlaysColumnHeight();
      fitOverlayPreviewStage();
      renderOverlayPreview();
    });
    overlayPreviewResizeObserver.observe(overlayPreviewStageWrap);
  }

  state.selectedSceneId = readSelectedSceneId() || null;
  state.selectedOverlayId = readSelectedOverlayId() || null;
  wireTabs();
  wireCardCollapses();
  // Apply scene-pane sizing immediately so first paint doesn't start "short"
  // and then jump after async load completes.
  syncScenesColumnHeight();
  syncOverlaysColumnHeight();
  loadAll(false).catch((err) => {
    console.error(err);
    alert(`Media module failed to load: ${err.message}`);
  });
})();
