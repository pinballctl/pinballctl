(function () {
  const sceneSelect = document.getElementById("lighting-scene-select");
  const fixturesWrap = document.getElementById("lighting-fixtures");
  const editorWrap = document.getElementById("lighting-editor");
  const editorTitle = document.getElementById("lighting-editor-title");
  const editorCard = document.getElementById("lighting-editor-card");
  const pixelCard = document.getElementById("lighting-pixel-card");
  const pixelInfo = document.getElementById("lighting-pixel-info");
  const previewWrap = document.getElementById("lighting-preview-wrap");
  const previewTable = document.getElementById("lighting-preview-table");
  const customTimelineWrap = document.getElementById("lighting-custom-timeline");
  const optionsScroll = document.querySelector(".lighting-options-scroll");
  const gridLayout = document.querySelector(".lighting-grid-layout");
  const stagePane = document.getElementById("lighting-tab-stage-pane");
  const runtimePane = document.getElementById("lighting-tab-runtime-pane");
  const appFooter = document.querySelector("footer.footer");
  const pageRoot = document.getElementById("lighting-page");
  const addSceneBtn = document.getElementById("lighting-add-scene");
  const saveBtn = document.getElementById("lighting-save");
  const syncBtn = document.getElementById("lighting-sync");
  const allToggleBtn = document.getElementById("lighting-preview-all-toggle");
  const playToggleBtn = document.getElementById("lighting-preview-toggle");
  const espRunBtn = document.getElementById("lighting-preview-esp-run");
  const syncModalEl = document.getElementById("lighting-sync-modal");
  const markerModalEl = document.getElementById("lighting-marker-modal");
  const castModalEl = document.getElementById("lighting-cast-modal");
  const syncSpinner = document.getElementById("lighting-sync-spinner");
  const syncStatus = document.getElementById("lighting-sync-status");
  const syncDetail = document.getElementById("lighting-sync-detail");
  const syncProgressBar = document.getElementById("lighting-sync-progress-bar");
  const syncProgressMeta = document.getElementById("lighting-sync-progress-meta");
  if (!sceneSelect || !fixturesWrap || !editorWrap || !previewWrap || !previewTable) return;

  const API = {
    state: "/api/lighting/state",
    patterns: "/api/lighting/patterns",
    save: "/api/lighting/save",
    compile: "/api/lighting/compile",
    previewFrames: "/api/lighting/preview/frames",
    sync: "/api/lighting/sync",
    syncStatus: "/api/lighting/sync/status",
    previewPlay: "/api/lighting/preview/play",
    previewStop: "/api/lighting/preview/stop",
    previewEspState: "/api/lighting/preview/esp-state",
    fixturesLayout: "/api/lighting/fixtures/layout",
  };

  const state = {
    config: { fixtures: {}, scenes: [] },
    fixtures: [],
    selectedSceneId: null,
    dirty: false,
    drag: null,
    dragPending: null,
    playfield: {
      width: 700,
      height: 1400,
      ratio: 0.5,
      playfieldImageUrl: null,
      playfieldFit: "cover",
      playfieldPosition: "center",
      playfieldOpacity: 1,
    },
    previewRect: { width: 320, height: 640 },
    playback: null,
    selectedPixel: null,
    suppressClick: false,
    syncTimer: null,
    syncAttempts: 0,
    syncLastStatus: null,
    syncStartedAtSec: 0,
    syncLastProgressAtMs: 0,
    syncLastAcked: 0,
    syncMaxAttempts: 720,
    espPollTimer: 0,
    runtimeStatus: null,
    espPollInFlight: false,
    syncModal: null,
    markerModal: null,
    markerModalCtx: null,
    castModal: null,
    castModalCtx: null,
    castFilter: "all",
    castSearch: "",
    customSceneId: null,
    customFrameMs: 100,
    customFrameCount: 2,
    customFrameIndex: 0,
    customSelection: new Set(),
    boxSelect: null,
    layoutRaf: 0,
    layoutBusy: false,
    layoutElements: [],
    showLayoutGuides: true,
    patterns: [],
    patternMap: {},
    previewCompiled: null,
    previewCompileTimer: 0,
    previewCompileReq: 0,
    previewAllOn: false,
    espScenePlaying: false,
    espSceneId: "",
    espConnected: true,
    headlessMode: false,
    espActionPending: false,
    espActionTargetPlaying: null,
    espActionTimeout: 0,
    espVisibilityHandlerBound: false,
  };
  const ESP_POLL_MS_IDLE = 7000;
  const ESP_POLL_MS_PLAYING = 800;
  const ESP_POLL_MS_PENDING = 300;
  const PREVIEW_PAD_PX = 45;
  const DRAG_START_DELAY_MS = 120;
  const DRAG_START_DISTANCE_PX = 6;
  const DURATION_FRAME_MS = 500;
  const BASE_PREVIEW_WIDTH_PX = 320;
  const BASE_PREVIEW_HEIGHT_PX = 640;
  const COMPACT_LAYOUT_MEDIA = "(max-width: 1200px)";
  const COMPACT_BASE_TABLE_WIDTH_PX = 560;
  const COMPACT_BASE_TABLE_HEIGHT_PX = 1120;
  const MOBILE_PREVIEW_MEDIA = "(max-width: 1100px)";
  const PANEL_STATE_KEY = "pinballctl.lighting.panelState.v1";
  const SCENE_SELECTION_KEY = "pinballctl.lighting.selectedSceneId.v1";
  const MARKER_SHAPES = [
    "circle",
    "square",
    "triangle",
    "hexagon",
    "star",
    "arrow",
    "rectangle",
    "pill",
  ];

  const panelState = {
    fixtures: false,
    scenes: true,
    editor: true,
    pixel: true,
  };

  function loadPanelState() {
    try {
      const raw = window.localStorage.getItem(PANEL_STATE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (!data || typeof data !== "object") return;
      Object.keys(panelState).forEach((k) => {
        if (typeof data[k] === "boolean") panelState[k] = data[k];
      });
    } catch (e) {
      // ignore storage parse issues
    }
  }

  function savePanelState() {
    try {
      window.localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(panelState));
    } catch (e) {
      // ignore storage quota/privacy issues
    }
  }

  function loadSelectedScene() {
    try {
      const raw = window.localStorage.getItem(SCENE_SELECTION_KEY);
      if (!raw) return;
      const value = String(raw).trim();
      if (value) state.selectedSceneId = value;
    } catch (e) {
      // ignore storage/privacy issues
    }
  }

  function saveSelectedScene() {
    try {
      if (state.selectedSceneId) {
        window.localStorage.setItem(SCENE_SELECTION_KEY, String(state.selectedSceneId));
      } else {
        window.localStorage.removeItem(SCENE_SELECTION_KEY);
      }
    } catch (e) {
      // ignore storage/privacy issues
    }
  }

  function setSelectedScene(sceneId) {
    const value = String(sceneId || "").trim();
    state.selectedSceneId = value || null;
    saveSelectedScene();
    clearCompiledPreview();
    if (state.selectedSceneId) scheduleCompiledPreview(20);
  }

  function iconForExpanded(icon, expanded) {
    if (!icon) return;
    icon.classList.remove("fa-chevron-right", "fa-chevron-down", "fa-plus");
    icon.classList.add(expanded ? "fa-chevron-down" : "fa-chevron-right");
  }

  function setPanelOpen(name, open) {
    const panel = document.querySelector(`[data-lighting-panel="${name}"]`);
    const icon = document.querySelector(`[data-lighting-toggle-icon="${name}"]`);
    const headerToggle = document.querySelector(`[data-lighting-toggle="${name}"]`);
    const iconToggleBtn = icon?.closest(".lighting-card-collapse-toggle");
    if (!panel) return;
    panel.classList.toggle("d-none", !open);
    if (headerToggle) headerToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (iconToggleBtn) iconToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    iconForExpanded(icon, open);
  }

  function initPanelToggles() {
    document.querySelectorAll("[data-lighting-toggle]").forEach((btn) => {
      const name = btn.getAttribute("data-lighting-toggle");
      if (!name) return;
      const toggle = () => {
        panelState[name] = !panelState[name];
        setPanelOpen(name, panelState[name]);
        savePanelState();
      };
      btn.addEventListener("click", toggle);
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      });
    });
    Object.keys(panelState).forEach((name) => setPanelOpen(name, panelState[name]));
  }

  function readPlayfield(playfield) {
    const width = Number(playfield?.width);
    const height = Number(playfield?.height);
    const safeWidth = Number.isFinite(width) && width > 0 ? width : 700;
    const safeHeight = Number.isFinite(height) && height > 0 ? height : 1400;
    const playfieldImageUrl = String(playfield?.playfieldImageUrl || "").trim();
    const fitRaw = String(playfield?.playfieldFit || "").trim().toLowerCase();
    const posRaw = String(playfield?.playfieldPosition || "").trim().toLowerCase();
    let opacity = Number(playfield?.playfieldOpacity);
    if (!Number.isFinite(opacity)) opacity = 1;
    if (opacity < 0) opacity = 0;
    if (opacity > 1) opacity = 1;
    const fit = fitRaw === "contain" ? "contain" : (fitRaw === "exact" ? "exact" : "cover");
    const validPositions = new Set([
      "center", "top", "bottom", "left", "right",
      "top left", "top right", "bottom left", "bottom right",
    ]);
    const position = validPositions.has(posRaw) ? posRaw : "center";
    return {
      width: safeWidth,
      height: safeHeight,
      ratio: safeWidth / safeHeight,
      playfieldImageUrl: playfieldImageUrl || null,
      playfieldFit: fit,
      playfieldPosition: position,
      playfieldOpacity: opacity,
    };
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

  function applyPreviewPlayfieldBackground() {
    const url = String(state.playfield?.playfieldImageUrl || "").trim();
    if (!url) {
      previewTable.style.removeProperty("background-image");
      previewTable.style.removeProperty("background-size");
      previewTable.style.removeProperty("background-position");
      previewTable.style.removeProperty("background-repeat");
      return;
    }
    const safeUrl = url.replace(/["\\]/g, "\\$&");
    const opacity = Number.isFinite(Number(state.playfield?.playfieldOpacity))
      ? Number(state.playfield.playfieldOpacity)
      : 1;
    const clampedOpacity = Math.max(0, Math.min(1, opacity));
    const overlayAlpha = 1 - clampedOpacity;
    const base = getComputedStyle(previewTable).backgroundColor || "rgb(0, 0, 0)";
    const overlay = colorWithAlpha(base, overlayAlpha);
    const bgImage = overlayAlpha > 0.001
      ? `linear-gradient(${overlay}, ${overlay}), url("${safeUrl}")`
      : `url("${safeUrl}")`;
    previewTable.style.setProperty("background-image", bgImage, "important");
    const fitMode = state.playfield?.playfieldFit || "cover";
    const bgSize = fitMode === "exact" ? "100% 100%" : fitMode;
    const bgPos = fitMode === "exact" ? "0% 0%" : (state.playfield?.playfieldPosition || "center");
    previewTable.style.setProperty("background-size", bgSize, "important");
    previewTable.style.setProperty("background-position", bgPos, "important");
    previewTable.style.setProperty("background-repeat", "no-repeat", "important");
  }

  function updatePreviewSize() {
    if (!previewWrap || previewWrap.offsetParent === null) return;
    const cs = getComputedStyle(previewWrap);
    const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
    const padY = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
    const maxW = Math.max(120, Math.round(previewWrap.clientWidth - padX));
    const maxH = Math.max(220, Math.round(previewWrap.clientHeight - padY));
    const ratio = Number(state.playfield.ratio) > 0 ? Number(state.playfield.ratio) : 0.5;
    let width = maxW;
    let height = width / ratio;
    if (height > maxH) {
      height = maxH;
      width = height * ratio;
    }
    const next = {
      width: Math.max(60, Math.round(width)),
      height: Math.max(120, Math.round(height)),
    };
    state.previewRect = next;
    previewTable.style.width = `${next.width}px`;
    previewTable.style.height = `${next.height}px`;
  }

  function updatePreviewViewportHeight() {
    if (stagePane && !stagePane.classList.contains("active")) return;
    if (!previewWrap) return;
    if (window.matchMedia(MOBILE_PREVIEW_MEDIA).matches) {
      previewWrap.style.height = "50vh";
      if (optionsScroll) {
        optionsScroll.style.removeProperty("max-height");
      }
      return;
    }
    const previewBody = previewWrap.parentElement;
    if (!previewBody) return;
    const bodyStyles = getComputedStyle(previewBody);
    const bodyPadY = (parseFloat(bodyStyles.paddingTop) || 0) + (parseFloat(bodyStyles.paddingBottom) || 0);
    const timelineVisible = customTimelineWrap && !customTimelineWrap.classList.contains("d-none");
    const timelineHeight = timelineVisible ? customTimelineWrap.offsetHeight + 14 : 0;
    const available = Math.floor(previewBody.clientHeight - bodyPadY - timelineHeight - 8);
    const minHeight = 160;
    const nextHeight = Math.max(minHeight, available);
    if (Number.isFinite(nextHeight) && nextHeight > 0) {
      const current = parseFloat(previewWrap.style.height || "0");
      if (!Number.isFinite(current) || Math.abs(current - nextHeight) > 1) {
        previewWrap.style.height = `${nextHeight}px`;
      }
    }
    if (optionsScroll) {
      const optionsTop = optionsScroll.getBoundingClientRect().top;
      const footerTop = appFooter ? appFooter.getBoundingClientRect().top : window.innerHeight;
      const optionsAvailable = Math.floor(footerTop - optionsTop - 8);
      const optionsMax = Math.max(220, optionsAvailable);
      const current = parseFloat(optionsScroll.style.maxHeight || "0");
      if (!Number.isFinite(current) || Math.abs(current - optionsMax) > 1) {
        optionsScroll.style.maxHeight = `${optionsMax}px`;
      }
    }
  }

  function updateLayoutViewportHeight() {
    if (stagePane && !stagePane.classList.contains("active")) return;
    if (window.matchMedia(MOBILE_PREVIEW_MEDIA).matches) {
      if (pageRoot) pageRoot.style.removeProperty("height");
      if (gridLayout) gridLayout.style.removeProperty("height");
      return;
    }
    const footerHeight = appFooter ? Math.max(0, Math.round(appFooter.getBoundingClientRect().height)) : 0;
    if (pageRoot) {
      const pageTop = pageRoot.getBoundingClientRect().top;
      const pageAvail = Math.floor(window.innerHeight - pageTop - footerHeight - 16);
      if (Number.isFinite(pageAvail) && pageAvail > 0) {
        const nextPage = Math.max(320, pageAvail);
        const currPage = parseFloat(pageRoot.style.height || "0");
        if (!Number.isFinite(currPage) || Math.abs(currPage - nextPage) > 1) {
          pageRoot.style.height = `${nextPage}px`;
        }
      }
    }
    if (gridLayout) {
      const gridTop = gridLayout.getBoundingClientRect().top;
      const available = Math.floor(window.innerHeight - gridTop - footerHeight - 16);
      if (Number.isFinite(available) && available > 0) {
        const next = Math.max(240, available);
        const current = parseFloat(gridLayout.style.height || "0");
        if (!Number.isFinite(current) || Math.abs(current - next) > 1) {
          gridLayout.style.height = `${next}px`;
        }
      }
    }
  }

  function scheduleLayoutPass() {
    if (state.layoutRaf) return;
    state.layoutRaf = requestAnimationFrame(() => {
      state.layoutRaf = 0;
      if (state.layoutBusy) return;
      state.layoutBusy = true;
      try {
        updateLayoutViewportHeight();
        updatePreviewViewportHeight();
        updatePreviewSize();
        renderPreview();
      } finally {
        state.layoutBusy = false;
      }
    });
  }

  function previewSize() {
    return {
      width: state.previewRect.width || state.playfield.width || 700,
      height: state.previewRect.height || state.playfield.height || 1400,
    };
  }

  function previewVisualScale() {
    const size = previewSize();
    const sx = Number(size.width || 0) / BASE_PREVIEW_WIDTH_PX;
    const sy = Number(size.height || 0) / BASE_PREVIEW_HEIGHT_PX;
    const s = Math.min(sx || 1, sy || 1);
    return Math.max(0.45, Math.min(1, s));
  }

  function previewDesignScale(widthPx, heightPx) {
    const designW = Math.max(1, Number(state.playfield?.width) || 700);
    const designH = Math.max(1, Number(state.playfield?.height) || 1400);
    const w = Math.max(1, Number(widthPx) || Number(previewSize().width) || designW);
    const h = Math.max(1, Number(heightPx) || Number(previewSize().height) || designH);
    const s = Math.min(w / designW, h / designH);
    return Math.max(0.2, Math.min(1, s));
  }

  function layoutGuideVisualScale() {
    const size = previewSize();
    const w = Number(size.width || 0);
    const h = Number(size.height || 0);
    if (w <= 0 || h <= 0) return 1;
    const compactByViewport = window.matchMedia(COMPACT_LAYOUT_MEDIA).matches;
    const compactByTable = w < COMPACT_BASE_TABLE_WIDTH_PX || h < COMPACT_BASE_TABLE_HEIGHT_PX;
    if (!compactByViewport && !compactByTable) return 1;
    const sx = w / COMPACT_BASE_TABLE_WIDTH_PX;
    const sy = h / COMPACT_BASE_TABLE_HEIGHT_PX;
    const s = Math.min(sx, sy);
    return Math.max(0.35, Math.min(1, s));
  }

  function uuid() {
    return `scene_${Math.random().toString(36).slice(2, 10)}`;
  }

  function currentScene() {
    return state.config.scenes.find((s) => s.id === state.selectedSceneId) || null;
  }

  function normalizeSceneBlendMode(scene) {
    const v = String(scene?.blendMode || "overlay").toLowerCase();
    if (v === "pause_lower") return "pause_lower";
    if (v === "stop_lower") return "stop_lower";
    return "overlay";
  }

  function normalizeSceneCastMask(scene) {
    const v = String(scene?.castMask || "cast").toLowerCase();
    return v === "all" ? "all" : "cast";
  }

  function normalizeScenePriority(scene) {
    const raw = Number(scene?.priority);
    const n = Number.isFinite(raw) ? Math.round(raw) : 0;
    return Math.max(-100, Math.min(100, n));
  }

  function sceneAffectsFixture(scene, fixtureId) {
    if (!scene || !fixtureId) return false;
    if (normalizeSceneCastMask(scene) === "all") return true;
    const cast = new Set(Array.isArray(scene.cast) ? scene.cast : []);
    return cast.has(String(fixtureId));
  }

  function sceneVisibleFixtures(scene) {
    if (!scene) return [];
    if (normalizeSceneCastMask(scene) === "all") return state.fixtures.slice();
    const cast = new Set(Array.isArray(scene.cast) ? scene.cast : []);
    return cast.size ? state.fixtures.filter((f) => cast.has(f.id)) : [];
  }

  function fixtureSupportsDynamicColor(fixture) {
    const type = String(fixture?.type || "").trim().toLowerCase();
    if (type === "rgb_strip" || type === "rgb_led") return true;
    const fn = String(fixture?.function || "").trim().toLowerCase();
    return fn.includes("rgb");
  }

  function normalizeMarkerShape(value) {
    const s = String(value || "circle").trim().toLowerCase();
    return MARKER_SHAPES.includes(s) ? s : "circle";
  }

  function defaultMarkerSizePx(fixture) {
    return fixture?.type === "rgb_strip" ? 8 : 14;
  }

  function normalizeMarkerSizePx(value, fixture) {
    let n = Number(value);
    if (!Number.isFinite(n)) n = defaultMarkerSizePx(fixture);
    n = Math.max(4, Math.min(200, n));
    return n;
  }

  function normalizeMarkerRotationDeg(value) {
    let n = Number(value);
    if (!Number.isFinite(n)) n = 0;
    n = Math.max(-180, Math.min(180, n));
    return n;
  }

  function ensureFixtureVisualConfig(fixture) {
    if (!fixture) return;
    fixture.markerShape = normalizeMarkerShape(fixture.markerShape);
    fixture.markerSizePx = normalizeMarkerSizePx(fixture.markerSizePx, fixture);
    fixture.markerRotationDeg = normalizeMarkerRotationDeg(fixture.markerRotationDeg);
    if (!Array.isArray(fixture.pointVisuals)) fixture.pointVisuals = [];
    fixture.pointVisuals = fixture.pointVisuals.map((row) => {
      if (!row || typeof row !== "object") return {};
      return {
        shape: normalizeMarkerShape(row.shape),
        sizePx: normalizeMarkerSizePx(row.sizePx, fixture),
        rotationDeg: normalizeMarkerRotationDeg(row.rotationDeg),
      };
    });
  }

  function fixtureUsesPerPixelVisuals(fixture) {
    if (!fixture) return false;
    return fixture.type === "rgb_strip" && String(fixture.layoutMode || "line") === "manual";
  }

  function ensurePointVisualAt(fixture, pixelIndex) {
    ensureFixtureVisualConfig(fixture);
    const idx = Math.max(0, Math.floor(Number(pixelIndex) || 0));
    while (fixture.pointVisuals.length <= idx) fixture.pointVisuals.push({});
    const row = fixture.pointVisuals[idx] || {};
    fixture.pointVisuals[idx] = {
      shape: normalizeMarkerShape(row.shape || fixture.markerShape),
      sizePx: normalizeMarkerSizePx(row.sizePx, fixture),
      rotationDeg: normalizeMarkerRotationDeg(row.rotationDeg),
    };
    return fixture.pointVisuals[idx];
  }

  function visualConfigForDot(fixture, pixelIndex) {
    ensureFixtureVisualConfig(fixture);
    if (fixtureUsesPerPixelVisuals(fixture)) {
      const row = ensurePointVisualAt(fixture, pixelIndex);
      return {
        shape: normalizeMarkerShape(row.shape),
        sizePx: normalizeMarkerSizePx(row.sizePx, fixture),
        rotationDeg: normalizeMarkerRotationDeg(row.rotationDeg),
      };
    }
    return {
      shape: normalizeMarkerShape(fixture.markerShape),
      sizePx: normalizeMarkerSizePx(fixture.markerSizePx, fixture),
      rotationDeg: normalizeMarkerRotationDeg(fixture.markerRotationDeg),
    };
  }

  function isCustomScene(scene) {
    return String(scene?.pattern || "").toLowerCase() === "custom";
  }

  function patternSpec(patternId) {
    const key = String(patternId || "").trim().toLowerCase();
    return state.patternMap[key] || state.patternMap.solid || null;
  }

  function camelLabel(value, fallback = "Value") {
    const raw = String(value || "").trim();
    if (!raw) return fallback;
    const spaced = raw
      .replace(/[_\-\s]+/g, " ")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/[^A-Za-z0-9 ]+/g, " ");
    const parts = spaced.split(/\s+/).filter(Boolean);
    if (!parts.length) return fallback;
    return parts
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join("");
  }

  function titleLabel(value, fallback = "Value") {
    const raw = String(value || "").trim();
    if (!raw) return fallback;
    const aliases = {
      theater_chase: "Theatre Chase",
      theaterchase: "Theatre Chase",
      "theater chase": "Theatre Chase",
    };
    const alias = aliases[raw.toLowerCase()];
    if (alias) return alias;
    const spaced = raw
      .replace(/[_\-\s]+/g, " ")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/[^A-Za-z0-9 ]+/g, " ");
    const parts = spaced.split(/\s+/).filter(Boolean);
    if (!parts.length) return fallback;
    return parts
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function patternDefaultParams(patternId) {
    const spec = patternSpec(patternId);
    const out = {};
    if (!spec || !Array.isArray(spec.params)) return out;
    spec.params.forEach((row) => {
      if (!row || !row.key) return;
      out[row.key] = row.default;
    });
    return out;
  }

  function normalizePatternId(patternId) {
    const key = String(patternId || "").trim().toLowerCase();
    if (state.patternMap[key]) return key;
    if (key === "colour_wheel" || key === "color_wheel") return "rainbow";
    return state.patternMap.solid ? "solid" : key;
  }

  function ensureScenePatternDefaults(scene) {
    if (!scene || typeof scene !== "object") return;
    scene.pattern = normalizePatternId(scene.pattern || "solid");
    if (!scene.params || typeof scene.params !== "object") scene.params = {};
    const defs = patternDefaultParams(scene.pattern);
    Object.keys(defs).forEach((k) => {
      if (scene.params[k] === undefined) scene.params[k] = defs[k];
    });
  }

  function clampStepIntensity(raw, fallback = 1.0) {
    let v = Number(raw);
    if (!Number.isFinite(v)) v = Number(fallback);
    if (!Number.isFinite(v)) v = 1.0;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    return v;
  }

  function parseStepSequenceSteps(raw) {
    const text = String(raw || "").trim();
    const src = text || "#ff0000:250:1.00;#000000:250:1.00";
    const tokens = src
      .replace(/\r/g, "")
      .replace(/\n/g, ";")
      .replace(/,/g, ";")
      .split(";")
      .map((t) => t.trim())
      .filter(Boolean);
    const out = [];
    tokens.forEach((token) => {
      let parts = [];
      if (token.includes(":")) parts = token.split(":");
      else if (token.includes("@")) parts = token.split("@");
      const colour = normalizeHexColor(parts[0] || token, "#ffffff");
      let durationMs = Math.round(Number(parts[1]));
      if (!Number.isFinite(durationMs)) durationMs = 250;
      durationMs = Math.max(20, Math.min(10000, durationMs));
      const intensity = clampStepIntensity(parts[2], 1.0);
      out.push({ colour, durationMs, intensity });
    });
    if (!out.length) out.push({ colour: "#ff0000", durationMs: 250, intensity: 1.0 });
    return out;
  }

  function serializeStepSequenceSteps(steps) {
    return (Array.isArray(steps) ? steps : [])
      .map((row) => {
        const colour = normalizeHexColor(row?.colour, "#ffffff");
        const durationMs = Math.max(20, Math.min(10000, Math.round(Number(row?.durationMs) || 250)));
        const intensity = clampStepIntensity(row?.intensity, 1.0);
        return `${colour}:${durationMs}:${intensity.toFixed(2)}`;
      })
      .join(";");
  }

  function parseDriftPalette(raw) {
    const text = String(raw || "").trim();
    const src = text || "#ff0040,#ffb000,#00d1ff,#7cff00";
    const out = src
      .replace(/\r/g, "")
      .replace(/\n/g, ",")
      .replace(/;/g, ",")
      .split(",")
      .map((t) => normalizeHexColor(t.trim(), ""))
      .filter(Boolean)
      .map((c) => normalizeHexColor(c, "#ffffff"));
    if (out.length < 2) return ["#ff0040", "#00d1ff"];
    return out.slice(0, 12);
  }

  function serializeDriftPalette(colours) {
    const out = (Array.isArray(colours) ? colours : [])
      .map((c) => normalizeHexColor(c, ""))
      .filter(Boolean)
      .map((c) => normalizeHexColor(c, "#ffffff"));
    if (out.length < 2) return "#ff0040,#00d1ff";
    return out.slice(0, 12).join(",");
  }

  async function loadPatterns() {
    const r = await fetch(API.patterns, { cache: "no-store" });
    const j = await r.json();
    if (!r.ok || !j?.ok || !Array.isArray(j.patterns)) throw new Error("Failed to load patterns");
    state.patterns = j.patterns
      .map((row) => ({
        id: String(row?.id || "").trim().toLowerCase(),
        label: String(row?.label || row?.id || "").trim(),
        params: Array.isArray(row?.params) ? row.params : [],
      }))
      .filter((row) => !!row.id);
    state.patternMap = {};
    state.patterns.forEach((row) => {
      state.patternMap[row.id] = row;
    });
    if (!state.patternMap.solid) {
      state.patterns.unshift({ id: "solid", label: "solid", params: [{ key: "color", label: "Colour", type: "color", default: "#ffffff" }, { key: "brightness", label: "Brightness", type: "number", default: 1, min: 0, max: 1, step: 0.05 }] });
      state.patternMap.solid = state.patterns[0];
    }
    state.patterns.sort((a, b) => {
      const al = titleLabel(a?.label || a?.id || "", "Value").toLowerCase();
      const bl = titleLabel(b?.label || b?.id || "", "Value").toLowerCase();
      if (al < bl) return -1;
      if (al > bl) return 1;
      const ai = String(a?.id || "").toLowerCase();
      const bi = String(b?.id || "").toLowerCase();
      if (ai < bi) return -1;
      if (ai > bi) return 1;
      return 0;
    });
  }

  function clearCompiledPreview() {
    state.previewCompiled = null;
  }

  async function refreshCompiledPreviewNow() {
    const scene = currentScene();
    if (!scene?.id) {
      clearCompiledPreview();
      return;
    }
    const reqId = ++state.previewCompileReq;
    const r = await fetch(API.previewFrames, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneId: scene.id, config: state.config }),
    });
    const j = await r.json();
    if (reqId !== state.previewCompileReq) return;
    if (!r.ok || !j?.ok || !j?.preview?.scene) {
      clearCompiledPreview();
      return;
    }
    state.previewCompiled = j.preview;
    if (!state.playback) renderPreview();
  }

  function scheduleCompiledPreview(delayMs = 120) {
    if (state.previewCompileTimer) clearTimeout(state.previewCompileTimer);
    state.previewCompileTimer = setTimeout(() => {
      state.previewCompileTimer = 0;
      refreshCompiledPreviewNow().catch(() => {});
    }, delayMs);
  }

  function markDirty(v = true) {
    state.dirty = !!v;
    if (saveBtn) {
      saveBtn.disabled = !state.dirty;
      saveBtn.setAttribute("aria-disabled", state.dirty ? "false" : "true");
    }
    if (v) {
      scheduleCompiledPreview();
    }
  }

  function stopSyncPoll() {
    if (state.syncTimer) {
      clearInterval(state.syncTimer);
      state.syncTimer = null;
    }
    state.syncAttempts = 0;
    state.syncLastStatus = null;
    state.syncLastProgressAtMs = 0;
    state.syncLastAcked = 0;
    state.syncMaxAttempts = 720;
  }

  function setSyncStatus(text, detail, busy) {
    if (syncStatus) syncStatus.textContent = text || "";
    if (syncDetail) syncDetail.textContent = detail || "";
    if (syncSpinner) syncSpinner.classList.toggle("d-none", !busy);
  }

  function setSyncProgress(percent, meta, busy) {
    const p = Math.max(0, Math.min(100, Number(percent) || 0));
    if (syncProgressBar) {
      syncProgressBar.style.width = `${p}%`;
      syncProgressBar.textContent = "";
      syncProgressBar.classList.toggle("progress-bar-animated", !!busy);
      syncProgressBar.classList.toggle("progress-bar-striped", !!busy);
    }
    if (syncProgressMeta) syncProgressMeta.textContent = meta || "";
  }

  function bytesToMbText(bytes) {
    const n = Number(bytes || 0);
    if (!Number.isFinite(n) || n <= 0) return "0.00 MB";
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  }

  function updateRuntimeUi() {
    const data = state.runtimeStatus && typeof state.runtimeStatus === "object" ? state.runtimeStatus : null;
    const scenes = Array.isArray(data?.scene?.activeScenes) ? data.scene.activeScenes : [];
    const scenePlaying = !!data?.scene?.playing;
    const sceneId = String(data?.scene?.sceneId || "").trim();
    const hasDerivedScene = scenePlaying && !!sceneId && scenes.length === 0;
    const activeCountRaw = Number(data?.scene?.activeSceneCount);
    const activeCount = Number.isFinite(activeCountRaw)
      ? Math.max(0, Math.round(activeCountRaw))
      : (scenes.length || (hasDerivedScene ? 1 : 0));
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = String(value);
    };
    const blendLabel = (raw) => {
      const key = String(raw || "").trim().toLowerCase();
      if (key === "stop_lower") return "Stop Lower";
      if (key === "pause_lower") return "Pause Lower";
      if (key === "overlay") return "Play Over";
      return key || "-";
    };
    const sceneMetaById = new Map(
      (Array.isArray(state?.config?.scenes) ? state.config.scenes : [])
        .filter((s) => s && typeof s === "object" && String(s.id || "").trim())
        .map((s) => [String(s.id || "").trim(), s]),
    );
    const resolveSceneName = (sid) => {
      const key = String(sid || "").trim();
      if (!key) return "";
      const meta = sceneMetaById.get(key);
      const title = String(meta?.title || "").trim();
      return title || key;
    };
    setText("lighting-runtime-esp-connected", data?.espConnected === true ? "Yes" : "No");
    setText(
      "lighting-runtime-headless",
      data?.headless === true ? "Yes" : (data?.headless === false ? "No" : "Unknown"),
    );
    setText("lighting-runtime-active-count", activeCount);
    setText("lighting-runtime-overrides", Number(data?.scene?.overridesActive || 0));
    setText(
      "lighting-runtime-status-text",
      data?.scene?.reason
        ? String(data.scene.reason)
        : (scenePlaying ? `Playing: ${sceneId || "(unknown)"}` : "Idle"),
    );
    setText("lighting-runtime-last-updated", new Date().toLocaleTimeString());

    const body = document.getElementById("lighting-runtime-scenes-body");
    if (!body) return;
    if (!scenes.length && !hasDerivedScene) {
      body.innerHTML = '<tr><td colspan="5" class="text-secondary small">No active scenes.</td></tr>';
      return;
    }
    const tableRows = scenes.length
      ? scenes
      : [{ id: sceneId, priority: null, blendMode: "overlay", paused: false, order: 0, __derived: true }];
    body.innerHTML = tableRows.map((row) => {
      const rawSceneId = String(row?.id || "");
      const sceneMeta = sceneMetaById.get(rawSceneId);
      const sid = escapeHtml(rawSceneId);
      const sceneName = escapeHtml(resolveSceneName(rawSceneId));
      const derived = !!row?.__derived;
      const configuredPriority = Number(sceneMeta?.priority);
      const runtimePriority = Number(row?.priority);
      const chosenPriority = Number.isFinite(configuredPriority)
        ? Math.round(configuredPriority)
        : (Number.isFinite(runtimePriority) ? Math.round(runtimePriority) : null);
      const priority = chosenPriority === null ? "-" : String(chosenPriority);
      const configuredBlend = String(sceneMeta?.blendMode || "").trim().toLowerCase();
      const runtimeBlend = String(row?.blendMode || "").trim().toLowerCase();
      const chosenBlend = configuredBlend || runtimeBlend || (derived ? "overlay" : "overlay");
      const blend = escapeHtml(blendLabel(chosenBlend));
      const paused = derived ? "No" : (row?.paused ? "Yes" : "No");
      const order = Number.isFinite(Number(row?.order)) ? Math.round(Number(row.order)) : 0;
      const sceneCell = sceneName && sceneName !== sid
        ? `${sceneName}<div class="small text-secondary">${sid}</div>`
        : sid;
      return `<tr><td>${sceneCell}</td><td>${priority}</td><td>${blend}</td><td>${paused}</td><td>${order}</td></tr>`;
    }).join("");
  }

  function setSyncUiState(mode) {
    if (!syncBtn) return;
    syncBtn.classList.remove("btn-outline-primary", "btn-outline-secondary", "btn-warning", "btn-success", "lighting-sync-btn-muted");
    if (mode === "out") {
      syncBtn.classList.add("btn-warning");
      return;
    }
    if (mode === "in") {
      syncBtn.classList.add("btn-outline-secondary");
      return;
    }
    syncBtn.classList.add("btn-outline-primary");
  }

  function confirmSaveBeforeSync() {
    const fallback = () => Promise.resolve(window.confirm("You have unsaved changes. Save before syncing lighting?"));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
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
      if (body) body.textContent = "You have unsaved changes. Save before syncing lighting?";
      if (titleEl) titleEl.textContent = "Save Before Sync";
      if (confirmBtn) {
        confirmBtn.textContent = "Save & Sync";
        confirmBtn.className = "btn btn-primary";
      }
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  function confirmSyncAction() {
    const fallback = () => Promise.resolve(window.confirm("Sync lighting to ESP? This will overwrite lighting.pd on the ESP."));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
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
      if (body) body.textContent = "Sync lighting to ESP? This will overwrite lighting.pd on the ESP.";
      if (titleEl) titleEl.textContent = "Confirm Sync";
      if (confirmBtn) {
        confirmBtn.textContent = "Sync";
        confirmBtn.className = "btn btn-primary";
      }
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  function confirmClearAllFramesAction() {
    const fallback = () => Promise.resolve(window.confirm("Clear all custom timeline frames in this scene? This cannot be undone."));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
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
      if (body) body.textContent = "Clear all custom timeline frames in this scene? This cannot be undone.";
      if (titleEl) titleEl.textContent = "Clear All Frames";
      if (confirmBtn) {
        confirmBtn.textContent = "Clear Frames";
        confirmBtn.className = "btn btn-danger";
      }
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  function confirmDeleteSceneAction(sceneTitle) {
    const label = String(sceneTitle || "").trim();
    const msg = label
      ? `Remove scene "${label}"? This cannot be undone.`
      : "Remove this scene? This cannot be undone.";
    const fallback = () => Promise.resolve(window.confirm(msg));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
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
      if (body) body.textContent = msg;
      if (titleEl) titleEl.textContent = "Remove Scene";
      if (confirmBtn) {
        confirmBtn.textContent = "Remove";
        confirmBtn.className = "btn btn-danger";
      }
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  async function loadSyncStatus() {
    let timer = null;
    try {
      const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      timer = controller ? setTimeout(() => controller.abort(), 1500) : null;
      const r = await fetch("/api/esplink/sync/status", {
        cache: "no-store",
        signal: controller ? controller.signal : undefined,
      });
      const j = await r.json();
      if (j?.espConnected !== true) {
        setSyncUiState("unknown");
        return false;
      } else if (j?.lighting?.inSync === false) {
        setSyncUiState("out");
        return true;
      } else {
        setSyncUiState("in");
        return false;
      }
    } catch (e) {
      setSyncUiState("unknown");
      return false;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function refreshSyncWarning(attempts = 4, delayMs = 600) {
    loadSyncStatus().then((outOfSync) => {
      if (outOfSync && attempts > 0) {
        setTimeout(() => refreshSyncWarning(attempts - 1, Math.min(delayMs * 1.5, 1500)), delayMs);
      }
    });
  }

  function promptSyncRequiredForEspPlay() {
    const fallback = () => Promise.resolve(window.confirm("Lighting is out of sync with the ESP. Sync now before playing scenes?"));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      let resolved = false;
      let syncAccepted = false;
      const prevTitle = titleEl?.textContent || "";
      const prevBody = body?.textContent || "";
      const prevConfirm = confirmBtn?.textContent || "Confirm";
      const prevConfirmClass = confirmBtn?.className || "";
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
        if (titleEl) titleEl.textContent = prevTitle;
        if (body) body.textContent = prevBody;
        if (confirmBtn) {
          confirmBtn.textContent = prevConfirm;
          if (prevConfirmClass) confirmBtn.className = prevConfirmClass;
        }
      };
      const onConfirm = async () => {
        syncAccepted = true;
        modal.hide();
      };
      const onHidden = () => {
        if (resolved) return;
        resolved = true;
        cleanup();
        resolve(!!syncAccepted);
      };
      if (titleEl) titleEl.textContent = "ESP Lighting Out Of Sync";
      if (body) {
        body.textContent = "Lighting on the ESP is not in sync. Some scenes may not play correctly or at all. Sync now to continue.";
      }
      if (confirmBtn) {
        confirmBtn.textContent = "Sync Now";
        confirmBtn.className = "btn btn-warning";
      }
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      modal.show();
    });
  }

  function showInfoModal(title, message, detail = "") {
    const fallback = () => {
      const text = detail ? `${message}\n\n${detail}` : message;
      window.alert(text);
      return Promise.resolve();
    };
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const cancelBtn = modalEl.querySelector('[data-bs-dismiss="modal"]');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      const prevTitle = titleEl?.textContent || "";
      const prevBody = body?.innerHTML || "";
      const prevConfirmText = confirmBtn?.textContent || "Confirm";
      const prevConfirmClass = confirmBtn?.className || "";
      const prevCancelText = cancelBtn?.textContent || "Cancel";
      const prevCancelClass = cancelBtn?.className || "";
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
        if (titleEl) titleEl.textContent = prevTitle;
        if (body) body.innerHTML = prevBody;
        if (confirmBtn) {
          confirmBtn.textContent = prevConfirmText;
          if (prevConfirmClass) confirmBtn.className = prevConfirmClass;
          confirmBtn.classList.remove("d-none");
        }
        if (cancelBtn) {
          cancelBtn.textContent = prevCancelText;
          if (prevCancelClass) cancelBtn.className = prevCancelClass;
        }
      };
      const onConfirm = () => modal.hide();
      const onHidden = () => {
        cleanup();
        resolve();
      };
      if (titleEl) titleEl.textContent = String(title || "Info");
      if (body) {
        body.innerHTML = detail
          ? `<div>${escapeHtml(String(message || ""))}</div><div class="small text-secondary mt-2">${escapeHtml(String(detail || ""))}</div>`
          : `<div>${escapeHtml(String(message || ""))}</div>`;
      }
      if (confirmBtn) {
        confirmBtn.textContent = "OK";
        confirmBtn.className = "btn btn-primary";
      }
      if (cancelBtn) {
        cancelBtn.textContent = "Close";
        cancelBtn.className = "btn btn-outline-secondary d-none";
      }
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      modal.show();
    });
  }

  function describePlayEspError(reasonRaw) {
    const reason = String(reasonRaw || "").trim().toLowerCase();
    if (reason === "sync_in_progress") {
      return {
        title: "Sync In Progress",
        message: "Lighting data is still syncing to the ESP.",
        detail: "Wait for sync to finish, then try Play on ESP again.",
      };
    }
    if (reason === "runtime_not_loaded") {
      return {
        title: "Lighting Runtime Not Loaded",
        message: "The ESP could not load the lighting runtime from the uploaded blob.",
        detail: "This is not caused by unplugged LEDs. Check bridge logs for LIGHTING_APPLY/LIGHTING_BOOT reason details.",
      };
    }
    if (reason === "runtime_guarded") {
      return {
        title: "Lighting Runtime Guarded",
        message: "The ESP has disabled automatic lighting boot after repeated load failures.",
        detail: "This is firmware-side (not LED strip wiring). Repeated sync uploads will not clear it until the underlying load failure is fixed.",
      };
    }
    if (reason === "no_response") {
      return {
        title: "ESP Did Not Reply",
        message: "Play command was sent, but no response came back from the ESP in time.",
        detail: "This is usually a bridge/firmware reply timeout, not LED wiring. Scenes should still play even if LED strips are unplugged.",
      };
    }
    if (reason === "bridge_offline") {
      return {
        title: "ESP Not Connected",
        message: "Play on ESP is unavailable because the bridge reports the ESP is offline.",
        detail: "Reconnect the ESP and try again.",
      };
    }
    if (reason === "rpc_error") {
      return {
        title: "Bridge Communication Error",
        message: "The bridge could not complete the play request.",
        detail: "Try again; if it persists, restart the bridge service.",
      };
    }
    if (reason === "not_loaded_sync_queued") {
      return {
        title: "Lighting Runtime Not Loaded",
        message: "Lighting data was not loaded on the ESP, so sync was queued automatically.",
        detail: "Wait for sync to complete, then try Play on ESP again.",
      };
    }
    if (reason === "not_loaded" || reason === "missing_scene" || reason === "scene_not_found") {
      return {
        title: "Scene Not Ready On ESP",
        message: "The selected scene could not be started on the ESP runtime.",
        detail: `Reason: ${reason}. Re-sync lighting and try again.`,
      };
    }
    if (reason === "unknown_scene") {
      return {
        title: "Unknown Scene",
        message: "The selected scene does not exist in the current lighting configuration.",
        detail: "Save lighting, sync, and retry.",
      };
    }
    return {
      title: "Play On ESP Failed",
      message: "The scene could not be started on the ESP.",
      detail: reason ? `Reason: ${reason}` : "",
    };
  }

  async function pollSyncStatus() {
    state.syncAttempts += 1;
    if (state.syncAttempts > state.syncMaxAttempts) {
      stopSyncPoll();
      if (syncBtn) syncBtn.disabled = false;
      const last = state.syncLastStatus && typeof state.syncLastStatus === "object" ? state.syncLastStatus : {};
      const st = String(last.state || "").trim();
      const detail = st
        ? `Sync did not complete (state=${st}${last.error ? `, error=${last.error}` : ""}).`
        : "No sync status update from bridge.";
      setSyncStatus("Timed out", detail, false);
      return;
    }
    try {
      const r = await fetch(API.syncStatus, { cache: "no-store" });
      const j = await r.json();
      if (j.bridge && j.bridge.connected === false) {
        stopSyncPoll();
        if (syncBtn) syncBtn.disabled = false;
        setSyncStatus("Bridge offline", "Bridge is not connected to the ESP.", false);
        return;
      }
      const status = j.blob_status || {};
      const blobAt = Number(j.blob_at || 0);
      // Ignore clearly stale status, but allow a few seconds for client/server clock skew.
      if (state.syncStartedAtSec > 0 && blobAt > 0 && blobAt + 5 < state.syncStartedAtSec) {
        return;
      }
      state.syncLastStatus = status;
      if (!status.state) return;
      if (status.state === "done" && status.ok && status.blobType === "lighting") {
        stopSyncPoll();
        if (syncBtn) syncBtn.disabled = false;
        setSyncStatus("Sync complete", "", false);
        setSyncProgress(100, "", false);
        refreshSyncWarning();
        return;
      }
      if (status.state === "error" && status.blobType === "lighting") {
        stopSyncPoll();
        if (syncBtn) syncBtn.disabled = false;
        setSyncStatus("Sync failed", status.error || "unknown", false);
        const progress = j.progress || {};
        const p = Number.isFinite(Number(progress.ackPercent)) ? Number(progress.ackPercent) : 0;
        setSyncProgress(p, status.error || "Sync failed.", false);
        return;
      }
      if (status.state === "begin" && status.blobType === "lighting") {
        const progress = j.progress || {};
        const ack = Number(progress.ackPercent || 0);
        const size = Number(progress.size || status.size || 0);
        const acked = Number(progress.acked || status.acked || 0);
        const nowMs = Date.now();
        if (size > 0) {
          // Larger uploads naturally take longer; scale timeout window with size.
          // Base: ~3 minutes, +45s per extra MB (capped to 10 minutes total).
          const sizeMb = size / (1024 * 1024);
          const maxSec = Math.min(600, Math.max(180, Math.round(180 + Math.max(0, sizeMb - 1) * 45)));
          state.syncMaxAttempts = Math.max(720, Math.ceil((maxSec * 1000) / 250));
        }
        if (acked > state.syncLastAcked) {
          state.syncLastAcked = acked;
          state.syncLastProgressAtMs = nowMs;
        } else if (!state.syncLastProgressAtMs) {
          state.syncLastProgressAtMs = nowMs;
        }
        // If progress stalls for too long, fail early with clearer reason.
        if (state.syncLastProgressAtMs && (nowMs - state.syncLastProgressAtMs) > 90000) {
          stopSyncPoll();
          if (syncBtn) syncBtn.disabled = false;
          setSyncStatus("Sync stalled", "Upload progress has not advanced for 90s.", false);
          setSyncProgress(ack, "No progress update from bridge.", false);
          return;
        }
        const meta = size > 0
          ? `${bytesToMbText(acked)} / ${bytesToMbText(size)}`
          : "Transferring…";
        setSyncStatus("Uploading to ESP…", "", true);
        setSyncProgress(ack, meta, true);
      }
    } catch (e) {
      stopSyncPoll();
      if (syncBtn) syncBtn.disabled = false;
      setSyncStatus("Sync failed", "Unable to read lighting sync status.", false);
      setSyncProgress(0, "No response from sync status API.", false);
    }
  }

  function fixtureById(id) {
    return state.fixtures.find((f) => f.id === id) || null;
  }

  function sceneDurationMs(scene) {
    if (!scene || !scene.duration) return 1000;
    const v = Number(scene.duration.value || 0);
    if (!Number.isFinite(v) || v < 0) return 0;
    if (scene.duration.unit === "frames") return Math.max(0, Math.round(v)) * DURATION_FRAME_MS;
    return scene.duration.unit === "minutes" ? Math.round(v * 60_000) : Math.round(v * 1_000);
  }

  function renderScenes() {
    const rows = Array.isArray(state.config.scenes) ? state.config.scenes : [];
    if (!rows.length) {
      sceneSelect.innerHTML = '<option value="">No scenes</option>';
      sceneSelect.disabled = true;
      return;
    }
    sceneSelect.disabled = false;
    sceneSelect.innerHTML = rows.map((scene) => {
      const dur = scene.duration || { value: 0, unit: "seconds" };
      const durUnitLabel = camelLabel(dur.unit || "seconds", "Seconds");
      const label = `${scene.title || scene.id} · ${titleLabel(scene.pattern || "solid", "Solid")} · ${dur.value || 0} ${durUnitLabel}`;
      return `<option value="${escapeHtml(scene.id)}">${escapeHtml(label)}</option>`;
    }).join("");
    sceneSelect.value = String(state.selectedSceneId || rows[0]?.id || "");
  }

  function renderFixturesSidebar() {
    fixturesWrap.innerHTML = "";
    const list = document.createElement("div");
    list.className = "d-flex flex-column gap-2";
    state.fixtures.forEach((f) => {
      const row = document.createElement("div");
      row.className = "d-flex align-items-center justify-content-between border rounded p-2";
      const meta = f.type === "rgb_strip" ? `${f.pixelCount} px` : "single";
      row.innerHTML = `<div class="w-100"><div class="d-flex align-items-center justify-content-between"><div><div class="fw-semibold">${f.title}</div><div class="small text-secondary">${f.id}</div></div><span class="badge text-bg-secondary">${meta}</span></div></div>`;
      if (f.type === "rgb_strip") {
        const controls = document.createElement("div");
        controls.className = "d-flex align-items-center gap-2 mt-2 flex-wrap";
        const size = previewSize();
        const px = document.createElement("input");
        px.type = "number";
        px.min = "1";
        px.className = "form-control form-control-sm";
        px.style.maxWidth = "120px";
        px.value = Number(f.pixelCount || 1);
        px.title = "Pixel count";
        const applyPixelCount = () => {
          const v = Number(px.value || 1);
          f.pixelCount = Number.isFinite(v) && v > 0 ? Math.round(v) : 1;
          px.value = String(f.pixelCount);
          if ((f.layoutMode || "line") === "line") {
            fitStripLengthForPixelCount(f, size.width, size.height);
          } else {
            normalizeManualPointsForCount(f, size.width, size.height);
          }
          markDirty();
          renderFixturesSidebar();
          renderPreview();
        };
        px.addEventListener("change", applyPixelCount);
        px.addEventListener("blur", applyPixelCount);
        px.addEventListener("keydown", (e) => {
          if (e.key !== "Enter") return;
          e.preventDefault();
          applyPixelCount();
          px.blur();
        });
        const mode = document.createElement("select");
        mode.className = "form-select form-select-sm";
        mode.style.maxWidth = "140px";
        mode.innerHTML = `
          <option value="line">${escapeHtml(camelLabel("line", "Line"))}</option>
          <option value="manual">${escapeHtml(camelLabel("manual", "Manual"))}</option>
        `;
        mode.value = f.layoutMode || "line";
        mode.addEventListener("change", () => {
          f.layoutMode = mode.value;
          if (f.layoutMode === "manual" && (!Array.isArray(f.points) || !f.points.length)) {
            const size = previewSize();
            f.points = fixturePixels(f, size.width, size.height);
            normalizeManualPointsForCount(f, size.width, size.height);
          } else if (f.layoutMode === "line") {
            fitStripLengthForPixelCount(f, size.width, size.height);
          }
          markDirty();
          renderFixturesSidebar();
          renderPreview();
        });
        controls.appendChild(labelSpan("Pixels"));
        controls.appendChild(px);
        controls.appendChild(labelSpan("Layout"));
        controls.appendChild(mode);
        row.querySelector("div.w-100")?.appendChild(controls);
      } else {
        const controls = document.createElement("div");
        controls.className = "d-flex align-items-center gap-2 mt-2";
        const color = document.createElement("input");
        color.type = "color";
        color.className = "form-control form-control-sm form-control-color";
        color.value = normalizeHexColor(f.fixedColor, "#60a5fa");
        color.title = "Fixed LED colour";
        color.addEventListener("input", () => {
          f.fixedColor = normalizeHexColor(color.value, "#60a5fa");
          markDirty();
          renderPreview();
        });
        controls.appendChild(labelSpan("Colour"));
        controls.appendChild(color);
        row.querySelector("div.w-100")?.appendChild(controls);
      }
      list.appendChild(row);
    });
    fixturesWrap.appendChild(list);
  }

  function lineGeometry(fixture, widthPx, heightPx) {
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    const line = resolvedFixtureLine(fixture, w, h);
    const x1 = Number(line.x1);
    const y1 = Number(line.y1);
    const x2 = Number(line.x2);
    const y2 = Number(line.y2);
    const dxPx = (x2 - x1) * w;
    const dyPx = (y2 - y1) * h;
    const lengthPx = Math.max(1, Math.hypot(dxPx, dyPx));
    const angleDeg = (Math.atan2(dyPx, dxPx) * 180) / Math.PI;
    return { lengthPx, angleDeg, cx: (x1 + x2) / 2, cy: (y1 + y2) / 2 };
  }

  function resolvedFixtureLine(fixture, widthPx, heightPx) {
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    const base = fixture?.line || { x1: 0.4, y1: 0.5, x2: 0.6, y2: 0.5 };
    const x1 = Number.isFinite(Number(base.x1)) ? Number(base.x1) : 0.4;
    const y1 = Number.isFinite(Number(base.y1)) ? Number(base.y1) : 0.5;
    const x2 = Number.isFinite(Number(base.x2)) ? Number(base.x2) : 0.6;
    const y2 = Number.isFinite(Number(base.y2)) ? Number(base.y2) : 0.5;
    const wantedLengthPx = Number(fixture?.lengthPx);
    if (!Number.isFinite(wantedLengthPx) || wantedLengthPx <= 0) {
      return { x1, y1, x2, y2 };
    }
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    const dxPx = (x2 - x1) * w;
    const dyPx = (y2 - y1) * h;
    const theta = (Math.abs(dxPx) < 1e-6 && Math.abs(dyPx) < 1e-6) ? 0 : Math.atan2(dyPx, dxPx);
    const stageScale = previewDesignScale(w, h);
    const half = Math.max(1, wantedLengthPx * stageScale) / 2;
    const hx = (Math.cos(theta) * half) / w;
    const hy = (Math.sin(theta) * half) / h;
    return {
      x1: clampWithPad(cx - hx, w),
      y1: clampWithPad(cy - hy, h),
      x2: clampWithPad(cx + hx, w),
      y2: clampWithPad(cy + hy, h),
    };
  }

  function setLineFromCenterAngleLength(fixture, widthPx, heightPx, cx, cy, angleDeg, lengthPx) {
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    const theta = (Number(angleDeg) * Math.PI) / 180;
    const halfLen = Math.max(1, Number(lengthPx) || 1) / 2;
    const hx = (Math.cos(theta) * halfLen) / w;
    const hy = (Math.sin(theta) * halfLen) / h;
    const x1 = clampWithPad(Number(cx) - hx, w);
    const y1 = clampWithPad(Number(cy) - hy, h);
    const x2 = clampWithPad(Number(cx) + hx, w);
    const y2 = clampWithPad(Number(cy) + hy, h);
    fixture.line = { x1, y1, x2, y2 };
    fixture.lengthPx = Math.max(1, Number(lengthPx) || 1);
  }

  function setLineLengthPx(fixture, widthPx, heightPx, lengthPx) {
    const g = lineGeometry(fixture, widthPx, heightPx);
    setLineFromCenterAngleLength(fixture, widthPx, heightPx, g.cx, g.cy, g.angleDeg, Math.max(1, Number(lengthPx) || 1));
  }

  function setLineAngleDeg(fixture, widthPx, heightPx, angleDeg) {
    const g = lineGeometry(fixture, widthPx, heightPx);
    const targetLength = Math.max(1, Number(fixture?.lengthPx) || g.lengthPx);
    setLineFromCenterAngleLength(fixture, widthPx, heightPx, g.cx, g.cy, Number(angleDeg) || 0, targetLength);
  }

  function fitStripLengthForPixelCount(fixture, widthPx, heightPx) {
    const count = Math.max(1, Number(fixture?.pixelCount || 1));
    const targetSpacingPx = 16;
    const targetLen = Math.max(1, (count - 1) * targetSpacingPx);
    setLineLengthPx(fixture, widthPx, heightPx, targetLen);
  }

  function manualOverflowMetrics(fixture, widthPx, heightPx) {
    const w = Math.max(120, Number(widthPx) || Number(state.previewRect?.width) || 700);
    const h = Math.max(220, Number(heightPx) || Number(state.previewRect?.height) || 1400);
    const padX = PREVIEW_PAD_PX / w;
    const cfg = visualConfigForDot(fixture, 0);
    const shape = String(cfg?.shape || "circle");
    const isWide = shape === "rectangle" || shape === "pill";
    const baseDotDiameterPx = Math.max(8, Number(isWide ? cfg.sizePx * 1.65 : cfg.sizePx) || 8);
    const visualScale = Math.max(0.35, Number(previewVisualScale()) || 1);
    const renderedDotDiameterPx = Math.max(6, Math.min(24, baseDotDiameterPx * visualScale));
    const rowStepPx = renderedDotDiameterPx + 5; // requested vertical gap target
    const colStepPx = renderedDotDiameterPx + 8;
    const rowStep = rowStepPx / h;
    const colStep = colStepPx / w;
    const startY = 0.06;
    const baseX = 1 + (padX * 0.35);
    return { w, h, rowStep, colStep, startY, baseX, rows: 25 };
  }

  function manualOverflowPoint(fixture, extraIndex, widthPx, heightPx) {
    const m = manualOverflowMetrics(fixture, widthPx, heightPx);
    const idx = Math.max(0, Math.floor(Number(extraIndex) || 0));
    const row = idx % m.rows;
    const col = Math.floor(idx / m.rows);
    return {
      x: clampWithPad(m.baseX + (col * m.colStep), m.w),
      y: clampWithPad(m.startY + (row * m.rowStep), m.h),
    };
  }

  function normalizeManualPointsForCount(fixture, widthPx, heightPx) {
    if (!fixture || fixture.type !== "rgb_strip") return;
    const w = Math.max(120, Number(widthPx) || Number(state.previewRect?.width) || 700);
    const h = Math.max(220, Number(heightPx) || Number(state.previewRect?.height) || 1400);
    const m = manualOverflowMetrics(fixture, w, h);
    const count = Math.max(1, Number(fixture.pixelCount || 1));
    const existing = Array.isArray(fixture.points) ? fixture.points : [];
    const lineFallback = fixturePixels({ ...fixture, layoutMode: "line" }, w, h);
    const out = [];
    const takenSlots = new Set();

    const slotForPoint = (pt) => {
      const x = Number(pt?.x);
      const y = Number(pt?.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      const rowF = (y - m.startY) / (m.rowStep || 1e-6);
      const colF = (x - m.baseX) / (m.colStep || 1e-6);
      const row = Math.round(rowF);
      const col = Math.round(colF);
      if (row < 0 || row >= m.rows || col < 0) return null;
      const xExpected = m.baseX + (col * m.colStep);
      const yExpected = m.startY + (row * m.rowStep);
      const xErr = Math.abs(x - xExpected);
      const yErr = Math.abs(y - yExpected);
      if (xErr > (m.colStep * 0.6) || yErr > (m.rowStep * 0.6)) return null;
      return (col * m.rows) + row;
    };

    let nextSlot = 0;
    const allocNextSlot = () => {
      while (takenSlots.has(nextSlot)) nextSlot += 1;
      const slot = nextSlot;
      takenSlots.add(slot);
      nextSlot += 1;
      return slot;
    };

    for (let i = 0; i < count; i += 1) {
      let src = existing[i] || null;
      if (src) {
        src = {
          x: Number.isFinite(Number(src.x)) ? Number(src.x) : 0.5,
          y: Number.isFinite(Number(src.y)) ? Number(src.y) : 0.5,
        };
        const slot = slotForPoint(src);
        if (slot !== null) takenSlots.add(slot);
      }
      if (!src && existing.length === 0) {
        src = lineFallback[i] || lineFallback[lineFallback.length - 1] || null;
      }
      if (!src) {
        // Only newly added/missing points get overflow auto-placement.
        src = manualOverflowPoint(fixture, allocNextSlot(), w, h);
      }
      out.push({
        x: Number(src.x),
        y: Number(src.y),
      });
    }
    fixture.points = out;
  }

  function labelSpan(text) {
    const n = document.createElement("span");
    n.className = "small text-secondary";
    n.textContent = text;
    return n;
  }

  function sceneCastIds(scene) {
    const all = new Set(state.fixtures.map((f) => f.id));
    return Array.isArray(scene?.cast) ? scene.cast.filter((id) => all.has(id)) : [];
  }

  function setSceneCastIds(scene, ids) {
    if (!scene) return;
    const uniq = [];
    const seen = new Set();
    const all = new Set(state.fixtures.map((f) => f.id));
    (ids || []).forEach((id) => {
      const v = String(id || "");
      if (!v || seen.has(v) || !all.has(v)) return;
      seen.add(v);
      uniq.push(v);
    });
    scene.cast = uniq;
  }

  function selectedCastFixtures(scene) {
    const set = new Set(sceneCastIds(scene));
    return state.fixtures.filter((f) => set.has(f.id));
  }

  function updateSceneCastSummary(scene) {
    const summaryEl = document.getElementById("lighting-scene-cast-summary");
    const chipsEl = document.getElementById("lighting-scene-cast-chips");
    if (!summaryEl || !chipsEl || !scene) return;
    const allMode = normalizeSceneCastMask(scene) === "all";
    const selected = allMode ? state.fixtures.slice() : selectedCastFixtures(scene);
    const count = selected.length;
    if (allMode) {
      summaryEl.textContent = count ? `All fixtures (${count})` : "All fixtures (none available)";
    } else {
      summaryEl.textContent = count === 0 ? "No fixtures selected." : `${count} fixture${count === 1 ? "" : "s"} selected.`;
    }
    chipsEl.innerHTML = "";
    if (!count) return;
    const maxChips = 4;
    selected.slice(0, maxChips).forEach((f) => {
      const chip = document.createElement("span");
      chip.className = "lighting-scene-cast-chip";
      chip.textContent = f.title || f.id;
      chipsEl.appendChild(chip);
    });
    if (count > maxChips) {
      const extra = document.createElement("span");
      extra.className = "lighting-scene-cast-chip";
      extra.textContent = `+${count - maxChips}`;
      chipsEl.appendChild(extra);
    }
  }

  function currentCastModalScene() {
    const sceneId = String(state.castModalCtx?.sceneId || "");
    return state.config.scenes.find((s) => String(s?.id || "") === sceneId) || null;
  }

  function castFilterMatch(fixture, filter) {
    if (filter === "strips") return String(fixture?.type || "") === "rgb_strip";
    if (filter === "singles") return String(fixture?.type || "") !== "rgb_strip";
    return true;
  }

  function renderCastModalList() {
    const scene = currentCastModalScene();
    if (!scene || !castModalEl) return;
    const listEl = castModalEl.querySelector("#lighting-cast-list");
    const countEl = castModalEl.querySelector("#lighting-cast-count");
    if (!listEl || !countEl) return;
    const selectedSet = new Set(sceneCastIds(scene));
    const q = String(state.castSearch || "").trim().toLowerCase();
    const filtered = state.fixtures.filter((f) => {
      if (!castFilterMatch(f, state.castFilter)) return false;
      if (!q) return true;
      const hay = `${f.title || ""} ${f.id || ""}`.toLowerCase();
      return hay.includes(q);
    });
    countEl.textContent = `${selectedSet.size} selected`;
    listEl.innerHTML = "";
    filtered.forEach((f) => {
      const id = `cast_modal_${String(f.id).replace(/[^A-Za-z0-9_]/g, "_")}`;
      const row = document.createElement("label");
      row.className = "form-check lighting-cast-modal-row";
      row.innerHTML = `
        <input class="form-check-input" type="checkbox" id="${id}" ${selectedSet.has(f.id) ? "checked" : ""}>
        <span class="form-check-label">${escapeHtml(f.title || f.id)} <span class="text-secondary">(${escapeHtml(f.id)})</span></span>
      `;
      row.querySelector("input")?.addEventListener("change", (e) => {
        const set = new Set(sceneCastIds(scene));
        if (e.target.checked) set.add(f.id);
        else set.delete(f.id);
        setSceneCastIds(scene, Array.from(set));
        markDirty();
        updateSceneCastSummary(scene);
        renderPreview();
        renderCastModalList();
      });
      listEl.appendChild(row);
    });
  }

  function setCastFilter(nextFilter) {
    state.castFilter = nextFilter;
    castModalEl?.querySelector("#lighting-cast-filter-all")?.classList.toggle("active", nextFilter === "all");
    castModalEl?.querySelector("#lighting-cast-filter-strips")?.classList.toggle("active", nextFilter === "strips");
    castModalEl?.querySelector("#lighting-cast-filter-singles")?.classList.toggle("active", nextFilter === "singles");
    renderCastModalList();
  }

  function openCastModal(scene) {
    if (!scene || !castModalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) return;
    state.castModalCtx = { sceneId: String(scene.id || "") };
    if (!state.castModal) {
      state.castModal = bootstrap.Modal.getOrCreateInstance(castModalEl, { backdrop: "static" });
    }
    const searchEl = castModalEl.querySelector("#lighting-cast-search");
    if (searchEl) searchEl.value = state.castSearch || "";
    setCastFilter(state.castFilter || "all");
    renderCastModalList();
    state.castModal.show();
    setTimeout(() => searchEl?.focus(), 20);
  }

  function updateSceneEditorTitle(scene) {
    if (!editorTitle) return;
    const name = String(scene?.title || scene?.id || "").trim();
    editorTitle.textContent = name ? `Scene Editor - ${name}` : "Scene Editor";
  }

  function renderSceneEditor() {
    const scene = currentScene();
    if (!scene) {
      if (editorCard) editorCard.classList.add("d-none");
      editorWrap.innerHTML = "";
      updateSceneEditorTitle(null);
      return;
    }
    if (editorCard) editorCard.classList.remove("d-none");
    ensureScenePatternDefaults(scene);
    scene.priority = normalizeScenePriority(scene);
    scene.blendMode = normalizeSceneBlendMode(scene);
    scene.castMask = normalizeSceneCastMask(scene);
    updateSceneEditorTitle(scene);
    const pattern = scene.pattern || "solid";
    const custom = pattern === "custom";
    const markers = sceneMarkers(scene)
      .slice()
      .sort((a, b) => Number(a?.atMs || 0) - Number(b?.atMs || 0));
    const tagsHtml = markers.length
      ? markers.map((m) => {
          const atMs = Math.max(0, Math.round(Number(m?.atMs || 0)));
          const label = String(m?.tag || "");
          return `<button class="lighting-scene-tag-pill" type="button" data-scene-marker-at="${atMs}" title="Jump to ${escapeHtml(label)}">${escapeHtml(label)}</button>`;
        }).join("")
      : '<span class="small text-secondary">No tags</span>';
    editorWrap.innerHTML = `
      <div class="lighting-grid">
        <label>Title</label>
        <input class="form-control form-control-sm" id="lighting-scene-title" value="${escapeHtml(scene.title || "")}">
      </div>
      <div class="lighting-grid">
        <label>Cast</label>
        <div class="lighting-cast-summary">
          <div class="small text-secondary" id="lighting-scene-cast-summary"></div>
          <div class="lighting-scene-cast-chips" id="lighting-scene-cast-chips"></div>
          <button class="btn btn-outline-secondary btn-sm" type="button" id="lighting-scene-edit-cast">Edit Cast</button>
        </div>
      </div>
      <div class="lighting-grid">
        <label>Priority</label>
        <input class="form-control form-control-sm" type="number" min="-100" max="100" step="1" id="lighting-scene-priority" value="${scene.priority}">
      </div>
      <div class="lighting-grid">
        <label>Blend mode</label>
        <select class="form-select form-select-sm" id="lighting-scene-blend">
          <option value="overlay"${scene.blendMode === "overlay" ? " selected" : ""}>Play Over</option>
          <option value="pause_lower"${scene.blendMode === "pause_lower" ? " selected" : ""}>Pause Lower</option>
          <option value="stop_lower"${scene.blendMode === "stop_lower" ? " selected" : ""}>Stop Lower</option>
        </select>
      </div>
      <div class="lighting-grid">
        <label>Cast mask</label>
        <select class="form-select form-select-sm" id="lighting-scene-cast-mask">
          <option value="cast"${scene.castMask === "cast" ? " selected" : ""}>Cast Only</option>
          <option value="all"${scene.castMask === "all" ? " selected" : ""}>All Fixtures</option>
        </select>
      </div>
      <div class="lighting-grid">
        <label>Duration</label>
        <div class="d-flex gap-2">
          <input class="form-control form-control-sm" type="number" min="0" step="${scene.duration?.unit === "frames" ? "1" : "0.1"}" id="lighting-scene-duration-value" value="${Number(scene.duration?.value || 0)}">
          <select class="form-select form-select-sm" id="lighting-scene-duration-unit">
            <option value="seconds"${scene.duration?.unit === "seconds" ? " selected" : ""}>${escapeHtml(camelLabel("seconds", "Seconds"))}</option>
            <option value="minutes"${scene.duration?.unit === "minutes" ? " selected" : ""}>${escapeHtml(camelLabel("minutes", "Minutes"))}</option>
            <option value="frames"${scene.duration?.unit === "frames" ? " selected" : ""}>${escapeHtml(camelLabel("frames", "Frames"))}</option>
          </select>
        </div>
      </div>
      <div class="lighting-grid">
        <label>End behavior</label>
        <select class="form-select form-select-sm" id="lighting-scene-end">
          <option value="stop"${scene.endBehavior === "stop" ? " selected" : ""}>${escapeHtml(camelLabel("stop", "Stop"))}</option>
          <option value="repeat"${scene.endBehavior === "repeat" ? " selected" : ""}>${escapeHtml(camelLabel("repeat", "Repeat"))}</option>
          <option value="bounce"${scene.endBehavior === "bounce" ? " selected" : ""}>${escapeHtml(camelLabel("bounce", "Bounce"))}</option>
        </select>
      </div>
      <div class="lighting-grid">
        <label>Pattern</label>
        <select class="form-select form-select-sm" id="lighting-scene-pattern">
          ${state.patterns.map((p) => `<option value="${escapeHtml(p.id)}"${pattern === p.id ? " selected" : ""}>${escapeHtml(titleLabel(p.label || p.id, "Solid"))}</option>`).join("")}
        </select>
      </div>
      <div class="lighting-grid">
        <label>Playfield</label>
        <div class="form-check m-0">
          <input class="form-check-input" type="checkbox" id="lighting-show-layout-guides"${state.showLayoutGuides ? " checked" : ""}>
          <label class="form-check-label" for="lighting-show-layout-guides">Show playfield components</label>
        </div>
      </div>
      <div class="lighting-grid">
        <label>Pattern params</label>
        <div class="lighting-params-grid" id="lighting-scene-params"></div>
      </div>
      ${custom ? `
      <div class="lighting-grid">
        <label>Tags</label>
        <div class="lighting-scene-tags" id="lighting-scene-tags">${tagsHtml}</div>
      </div>
      ` : ""}
      <div class="d-flex justify-content-end gap-2 lighting-scene-actions">
        ${custom ? `<button class="btn btn-outline-danger btn-sm me-auto" type="button" id="lighting-custom-clear-all-frames">Clear All Frames</button>` : ""}
        <button class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" type="button" id="lighting-delete-scene"><i class="fa fa-trash"></i><span>Remove</span></button>
      </div>
    `;

    updateSceneCastSummary(scene);
    document.getElementById("lighting-scene-edit-cast")?.addEventListener("click", () => openCastModal(scene));

    const paramsWrap = document.getElementById("lighting-scene-params");
    const params = scene.params || (scene.params = {});
    const addParam = (label, key, type, fallback, opts = {}) => {
      const wrap = document.createElement("div");
      wrap.className = "lighting-param-row";
      const l = document.createElement("label");
      l.className = "lighting-param-label";
      l.textContent = camelLabel(label, "Param");
      const input = document.createElement("input");
      input.className = "form-control form-control-sm";
      input.type = type;
      if (type === "number") {
        if (opts.min !== undefined) input.min = String(opts.min);
        if (opts.max !== undefined) input.max = String(opts.max);
        if (opts.step !== undefined) input.step = String(opts.step);
      }
      const normalizeNumeric = (raw) => {
        let n = Number(raw);
        if (!Number.isFinite(n)) n = Number(fallback);
        if (!Number.isFinite(n)) n = 0;
        if (opts.min !== undefined) n = Math.max(Number(opts.min), n);
        if (opts.max !== undefined) n = Math.min(Number(opts.max), n);
        if (opts.integer) n = Math.round(n);
        return n;
      };
      const parseEditingNumeric = (raw) => {
        const text = String(raw ?? "").trim();
        if (!text || text === "-" || text === "." || text === "-.") return null;
        const n = Number(text);
        if (!Number.isFinite(n)) return null;
        return opts.integer ? Math.round(n) : n;
      };
      if (params[key] === undefined) params[key] = fallback;
      if (type === "number") params[key] = normalizeNumeric(params[key]);
      input.value = params[key];
      const onInputValue = () => {
        if (type === "number") {
          const n = parseEditingNumeric(input.value);
          if (n === null) return;
          params[key] = n;
        } else {
          params[key] = input.value;
        }
        markDirty();
        renderPreview();
      };
      const onCommitValue = () => {
        if (type === "number") {
          const n = normalizeNumeric(input.value);
          params[key] = n;
          input.value = String(n);
        } else {
          params[key] = input.value;
        }
        markDirty();
        renderPreview();
      };
      input.addEventListener("input", onInputValue);
      input.addEventListener("change", onCommitValue);
      input.addEventListener("blur", onCommitValue);
      wrap.appendChild(l);
      wrap.appendChild(input);
      paramsWrap.appendChild(wrap);
      return { wrap, control: input };
    };
    const addSelectParam = (label, key, options, fallback) => {
      const wrap = document.createElement("div");
      wrap.className = "lighting-param-row";
      const l = document.createElement("label");
      l.className = "lighting-param-label";
      l.textContent = camelLabel(label, "Param");
      const select = document.createElement("select");
      select.className = "form-select form-select-sm";
      if (params[key] === undefined) params[key] = fallback;
      const value = String(params[key]);
      select.innerHTML = options.map((o) => `<option value="${escapeHtml(o.value)}">${escapeHtml(camelLabel(o.label, String(o.value || "")))}</option>`).join("");
      select.value = value;
      const onSelect = () => {
        params[key] = select.value;
        markDirty();
        renderPreview();
      };
      select.addEventListener("change", onSelect);
      select.addEventListener("input", onSelect);
      wrap.appendChild(l);
      wrap.appendChild(select);
      paramsWrap.appendChild(wrap);
      return { wrap, control: select };
    };
    const addStepSequenceEditor = (label, key) => {
      if (params[key] === undefined) params[key] = "#ff0000:250:1.00;#000000:250:1.00";
      let steps = parseStepSequenceSteps(params[key]);
      const wrap = document.createElement("div");
      wrap.className = "lighting-param-row";
      wrap.classList.add("lighting-param-row-steps");
      const l = document.createElement("label");
      l.className = "lighting-param-label";
      l.textContent = camelLabel(label, "Steps");
      const body = document.createElement("div");
      body.className = "lighting-step-sequence-editor";
      wrap.appendChild(l);
      wrap.appendChild(body);
      paramsWrap.appendChild(wrap);

      const commit = () => {
        params[key] = serializeStepSequenceSteps(steps);
        markDirty();
        renderPreview();
      };

      const renderRows = () => {
        body.innerHTML = "";
        const header = document.createElement("div");
        header.className = "lighting-step-row lighting-step-row-header";
        header.innerHTML = `
          <span>Colour</span>
          <span>Ms</span>
          <span>Intensity</span>
          <span></span>
        `;
        body.appendChild(header);

        steps.forEach((row, idx) => {
          const r = document.createElement("div");
          r.className = "lighting-step-row";

          const colour = document.createElement("input");
          colour.type = "color";
          colour.className = "form-control form-control-sm form-control-color";
          colour.value = normalizeHexColor(row.colour, "#ffffff");
          colour.addEventListener("input", () => {
            steps[idx].colour = normalizeHexColor(colour.value, "#ffffff");
            commit();
          });

          const dur = document.createElement("input");
          dur.type = "number";
          dur.className = "form-control form-control-sm";
          dur.min = "20";
          dur.max = "10000";
          dur.step = "10";
          dur.value = String(Math.max(20, Math.min(10000, Math.round(Number(row.durationMs) || 250))));
          const onDur = () => {
            let v = Math.round(Number(dur.value) || 250);
            v = Math.max(20, Math.min(10000, v));
            dur.value = String(v);
            steps[idx].durationMs = v;
            commit();
          };
          dur.addEventListener("input", onDur);
          dur.addEventListener("change", onDur);

          const intensity = document.createElement("input");
          intensity.type = "number";
          intensity.className = "form-control form-control-sm";
          intensity.min = "0";
          intensity.max = "1";
          intensity.step = "0.05";
          intensity.value = clampStepIntensity(row.intensity, 1.0).toFixed(2);
          const onIntensity = () => {
            const v = clampStepIntensity(intensity.value, 1.0);
            intensity.value = v.toFixed(2);
            steps[idx].intensity = v;
            commit();
          };
          intensity.addEventListener("input", onIntensity);
          intensity.addEventListener("change", onIntensity);

          const actions = document.createElement("div");
          actions.className = "lighting-step-actions";
          const addBtn = document.createElement("button");
          addBtn.type = "button";
          addBtn.className = "btn btn-outline-success btn-sm";
          addBtn.textContent = "+";
          addBtn.title = "Add step";
          addBtn.addEventListener("click", () => {
            const clone = {
              colour: normalizeHexColor(steps[idx]?.colour, "#ffffff"),
              durationMs: Math.max(20, Math.min(10000, Math.round(Number(steps[idx]?.durationMs) || 250))),
              intensity: clampStepIntensity(steps[idx]?.intensity, 1.0),
            };
            steps.splice(idx + 1, 0, clone);
            commit();
            renderRows();
          });
          const removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.className = "btn btn-outline-danger btn-sm";
          removeBtn.textContent = "-";
          removeBtn.title = "Remove step";
          removeBtn.disabled = steps.length <= 1;
          removeBtn.addEventListener("click", () => {
            if (steps.length <= 1) return;
            steps.splice(idx, 1);
            commit();
            renderRows();
          });
          actions.appendChild(addBtn);
          actions.appendChild(removeBtn);

          r.appendChild(colour);
          r.appendChild(dur);
          r.appendChild(intensity);
          r.appendChild(actions);
          body.appendChild(r);
        });
      };

      renderRows();
    };
    const addDriftPaletteEditor = (label, key) => {
      if (params[key] === undefined) params[key] = "#ff0040,#ffb000,#00d1ff,#7cff00";
      let colours = parseDriftPalette(params[key]);
      const wrap = document.createElement("div");
      wrap.className = "lighting-param-row";
      wrap.classList.add("lighting-param-row-steps");
      const l = document.createElement("label");
      l.className = "lighting-param-label";
      l.textContent = camelLabel(label, "Palette");
      const body = document.createElement("div");
      body.className = "lighting-step-sequence-editor";
      wrap.appendChild(l);
      wrap.appendChild(body);
      paramsWrap.appendChild(wrap);

      const commit = () => {
        params[key] = serializeDriftPalette(colours);
        markDirty();
        renderPreview();
      };

      const renderRows = () => {
        body.innerHTML = "";
        const header = document.createElement("div");
        header.className = "lighting-step-row lighting-step-row-header";
        header.innerHTML = `
          <span>Colour</span>
          <span></span>
          <span></span>
          <span></span>
        `;
        body.appendChild(header);

        colours.forEach((colourValue, idx) => {
          const r = document.createElement("div");
          r.className = "lighting-step-row lighting-palette-row";

          const colour = document.createElement("input");
          colour.type = "color";
          colour.className = "form-control form-control-sm form-control-color";
          colour.value = normalizeHexColor(colourValue, "#ffffff");
          colour.addEventListener("input", () => {
            colours[idx] = normalizeHexColor(colour.value, "#ffffff");
            commit();
          });

          const spacer1 = document.createElement("div");
          const spacer2 = document.createElement("div");
          spacer1.className = "lighting-palette-spacer";
          spacer2.className = "lighting-palette-spacer";

          const actions = document.createElement("div");
          actions.className = "lighting-step-actions";
          const addBtn = document.createElement("button");
          addBtn.type = "button";
          addBtn.className = "btn btn-outline-success btn-sm";
          addBtn.textContent = "+";
          addBtn.title = "Add colour";
          addBtn.disabled = colours.length >= 12;
          addBtn.addEventListener("click", () => {
            if (colours.length >= 12) return;
            const clone = normalizeHexColor(colours[idx], "#ffffff");
            colours.splice(idx + 1, 0, clone);
            commit();
            renderRows();
          });
          const removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.className = "btn btn-outline-danger btn-sm";
          removeBtn.textContent = "-";
          removeBtn.title = "Remove colour";
          removeBtn.disabled = colours.length <= 2;
          removeBtn.addEventListener("click", () => {
            if (colours.length <= 2) return;
            colours.splice(idx, 1);
            commit();
            renderRows();
          });
          actions.appendChild(addBtn);
          actions.appendChild(removeBtn);

          r.appendChild(colour);
          r.appendChild(spacer1);
          r.appendChild(spacer2);
          r.appendChild(actions);
          body.appendChild(r);
        });
      };

      renderRows();
    };
    const spec = patternSpec(pattern);
    if (spec && Array.isArray(spec.params)) {
      spec.params.forEach((row) => {
        if (!row || !row.key) return;
        const key = String(row.key);
        const label = String(row.label || key);
        const type = String(row.type || "text").toLowerCase();
        const fallback = row.default;
        if (type === "select") {
          const options = Array.isArray(row.options) ? row.options.map((o) => ({ value: String(o?.value ?? ""), label: String(o?.label ?? o?.value ?? "") })) : [];
          addSelectParam(label, key, options, fallback);
          return;
        }
        if (type === "bool") {
          addSelectParam(
            label,
            key,
            [
              { value: "true", label: "on" },
              { value: "false", label: "off" },
            ],
            fallback ? "true" : "false"
          );
          return;
        }
        if (type === "number") {
          addParam(label, key, "number", fallback, {
            min: row.min,
            max: row.max,
            step: row.step,
            integer: !!row.integer,
          });
          return;
        }
        if (type === "color") {
          addParam(label, key, "color", fallback || "#ffffff");
          return;
        }
        if (pattern === "step_sequence" && key === "steps") {
          addStepSequenceEditor(label, key);
          return;
        }
        if (pattern === "drift_palette" && key === "palette") {
          addDriftPaletteEditor(label, key);
          return;
        }
        addParam(label, key, "text", fallback ?? "");
      });
    }

    const bind = (id, fn) => {
      const n = document.getElementById(id);
      if (!n) return;
      n.addEventListener("input", fn);
      n.addEventListener("change", fn);
    };
    bind("lighting-scene-title", (e) => {
      scene.title = e.target.value;
      updateSceneEditorTitle(scene);
      markDirty();
      renderScenes();
    });
    bind("lighting-scene-duration-value", (e) => {
      scene.duration = scene.duration || { value: 5, unit: "seconds" };
      const raw = Number(e.target.value || 0);
      scene.duration.value = scene.duration.unit === "frames" ? Math.max(1, Math.round(raw)) : raw;
      if (scene.duration.unit === "frames") e.target.value = String(scene.duration.value);
      markDirty();
      if (isCustomScene(scene)) {
        ensureCustomTimelineState(scene);
        renderCustomTimelinePanel();
      }
    });
    bind("lighting-scene-duration-unit", (e) => {
      scene.duration = scene.duration || { value: 5, unit: "seconds" };
      scene.duration.unit = e.target.value;
      const durInput = document.getElementById("lighting-scene-duration-value");
      if (scene.duration.unit === "frames") {
        scene.duration.value = Math.max(1, Math.round(Number(scene.duration.value || 1)));
        if (durInput) {
          durInput.step = "1";
          durInput.value = String(scene.duration.value);
        }
      } else if (durInput) {
        durInput.step = "0.1";
      }
      markDirty();
      if (isCustomScene(scene)) {
        ensureCustomTimelineState(scene);
        renderCustomTimelinePanel();
      }
    });
    bind("lighting-scene-end", (e) => {
      scene.endBehavior = e.target.value;
      markDirty();
      if (state.playback && state.playback.sceneId === scene.id) {
        state.playback.endBehavior = scene.endBehavior || "stop";
        const elapsed = Math.max(0, performance.now() - state.playback.startedAtMs);
        if (state.playback.endBehavior === "stop" && state.playback.durationMs > 0 && elapsed >= state.playback.durationMs) {
          stopLocalPreview();
          return;
        }
      }
      renderPreview();
    });
    bind("lighting-scene-priority", (e) => {
      scene.priority = Math.max(-100, Math.min(100, Math.round(Number(e.target.value || 0))));
      e.target.value = String(scene.priority);
      markDirty();
    });
    bind("lighting-scene-blend", (e) => {
      const v = String(e.target.value || "overlay");
      scene.blendMode = (v === "pause_lower" || v === "stop_lower") ? v : "overlay";
      markDirty();
    });
    bind("lighting-scene-cast-mask", (e) => {
      scene.castMask = e.target.value === "all" ? "all" : "cast";
      markDirty();
      renderPreview();
    });
    bind("lighting-scene-pattern", (e) => {
      scene.pattern = normalizePatternId(e.target.value);
      scene.params = patternDefaultParams(scene.pattern);
      markDirty();
      renderSceneEditor();
    });
    bind("lighting-show-layout-guides", (e) => {
      state.showLayoutGuides = !!e.target.checked;
      if (!state.config.ui || typeof state.config.ui !== "object") state.config.ui = {};
      state.config.ui.showLayoutGuides = state.showLayoutGuides;
      markDirty();
      renderPreview();
    });

    const delBtn = document.getElementById("lighting-delete-scene");
    if (delBtn) {
      delBtn.addEventListener("click", async () => {
        const ok = await confirmDeleteSceneAction(scene.title || scene.id);
        if (!ok) return;
        const idx = state.config.scenes.findIndex((s) => s.id === scene.id);
        if (idx >= 0) state.config.scenes.splice(idx, 1);
        setSelectedScene(state.config.scenes[0]?.id || null);
        markDirty();
        render();
      });
    }
    const clearAllBtn = document.getElementById("lighting-custom-clear-all-frames");
    if (clearAllBtn && custom) {
      clearAllBtn.addEventListener("click", async () => {
        const ok = await confirmClearAllFramesAction();
        if (!ok) return;
        scene.timeline = [];
        markDirty();
        renderCustomTimelinePanel();
        renderPixelInspector();
        renderPreview();
      });
    }

    if (custom) ensureCustomTimelineState(scene);
    if (custom) {
      editorWrap.querySelectorAll("[data-scene-marker-at]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const atMs = Number(btn.getAttribute("data-scene-marker-at") || 0);
          const idx = frameIndexForMs(scene, atMs);
          setCustomFrameIndex(idx);
        });
      });
    }
    renderCustomTimelinePanel();
  }

  function fixturePixels(fixture, widthPx, heightPx) {
    const w = widthPx || 700;
    const h = heightPx || 1400;
    const count = Math.max(1, Number(fixture.pixelCount || 1));
    const mode = fixture.layoutMode || "line";
    if (mode === "manual" && Array.isArray(fixture.points) && fixture.points.length) {
      const raw = fixture.points.map((p) => ({ x: clampWithPad(Number(p.x), w), y: clampWithPad(Number(p.y), h) }));
      const count = Math.max(1, Number(fixture.pixelCount || 1));
      if (raw.length >= count) return raw.slice(0, count);
      const out = raw.slice();
      while (out.length < count) {
        const next = manualOverflowPoint(fixture, out.length - raw.length, w, h);
        out.push({ x: next.x, y: next.y });
      }
      return out;
    }
    const line = resolvedFixtureLine(fixture, w, h);
    const out = [];
    for (let i = 0; i < count; i += 1) {
      const t = count === 1 ? 0.5 : i / (count - 1);
      out.push({
        x: clampWithPad(line.x1 + (line.x2 - line.x1) * t, w),
        y: clampWithPad(line.y1 + (line.y2 - line.y1) * t, h),
      });
    }
    return out;
  }

  const GUIDE_SIZE_MULT = { s: 0.5, m: 1, l: 1.5, xl: 2 };
  const GUIDE_BASE_SIZE = {
    default: [64, 24],
    led: [22, 22],
    rgb: [22, 22],
    button: [28, 28],
    bumper: [34, 34],
    "pop-bumper": [46, 46],
    target: [18, 34],
    coil: [36, 18],
    "lcd-display": [72, 43],
    "launch-plunger": [28, 84],
  };
  const GUIDE_EXPLICIT_SIZE = {
    "flipper-left": { s: [36, 14], m: [72, 28], l: [108, 42], xl: [144, 56] },
    "flipper-right": { s: [36, 14], m: [72, 28], l: [108, 42], xl: [144, 56] },
    "launch-plunger": { s: [18, 54], m: [28, 84], l: [42, 126], xl: [56, 168] },
    "pop-bumper": { s: [48, 48], m: [68, 68], l: [110, 110], xl: [138, 138] },
  };

  function layoutGuideType(el) {
    return String(el?.icon || el?.type || "").trim().toLowerCase();
  }

  function layoutGuideSizeKey(el) {
    const raw = String(el?.size || "m").trim().toLowerCase();
    return raw === "s" || raw === "m" || raw === "l" || raw === "xl" ? raw : "m";
  }

  function layoutGuideDimensions(el) {
    const type = layoutGuideType(el);
    const sizeKey = layoutGuideSizeKey(el);
    let scale = Number(el?.scale);
    if (!Number.isFinite(scale) || scale <= 0) scale = 1;
    const explicit = GUIDE_EXPLICIT_SIZE[type];
    let width = 0;
    let height = 0;
    if (explicit && Array.isArray(explicit[sizeKey])) {
      width = Number(explicit[sizeKey][0]) || 0;
      height = Number(explicit[sizeKey][1]) || 0;
    } else {
      const base = GUIDE_BASE_SIZE[type] || GUIDE_BASE_SIZE.default;
      const mult = GUIDE_SIZE_MULT[sizeKey] || 1;
      width = (Number(base[0]) || 20) * mult;
      height = (Number(base[1]) || 20) * mult;
    }
    const vs = layoutGuideVisualScale();
    return {
      width: Math.max(4, width * scale * vs),
      height: Math.max(4, height * scale * vs),
    };
  }

  function layoutGuideBaseDimensions(el) {
    const type = layoutGuideType(el);
    const sizeKey = layoutGuideSizeKey(el);
    const explicit = GUIDE_EXPLICIT_SIZE[type];
    if (explicit && Array.isArray(explicit[sizeKey])) {
      return {
        width: Number(explicit[sizeKey][0]) || 20,
        height: Number(explicit[sizeKey][1]) || 20,
      };
    }
    const base = GUIDE_BASE_SIZE[type] || GUIDE_BASE_SIZE.default;
    const mult = GUIDE_SIZE_MULT[sizeKey] || 1;
    return {
      width: (Number(base[0]) || 20) * mult,
      height: (Number(base[1]) || 20) * mult,
    };
  }

  function layoutGuideBorderRadius(type) {
    const t = String(type || "").toLowerCase();
    if (t === "flipper-left" || t === "flipper-right") return "999px";
    if (t === "launch-plunger") return "10px 10px 0 0";
    if (t === "coil") return "6px";
    if (t === "target") return "8px";
    if (t === "led" || t === "rgb" || t === "button" || t === "bumper" || t === "pop-bumper") return "50%";
    return "10px";
  }

  function layoutGuideSvgFor(el, color) {
    const c = normalizeHexColor(color, "#60a5fa");
    const stroke = "#e5e7eb";
    const type = String(el?.icon || el?.type || "").trim().toLowerCase();
    const safeId = String(el?.id || "guide").replace(/[^A-Za-z0-9_-]/g, "_");
    if (type === "flipper-left") {
      return `<svg class="emu-svg lighting-layout-guide-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44" role="img" aria-label="Flipper"><g transform="translate(109.3 0) scale(-1 1)"><path fill="${c}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></g></svg>`;
    }
    if (type === "flipper-right") {
      return `<svg class="emu-svg lighting-layout-guide-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44" role="img" aria-label="Flipper"><path fill="${c}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></svg>`;
    }
    if (type === "launch-plunger") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 28 96" xmlns="http://www.w3.org/2000/svg"><path d="M6 92V12A8 8 0 0 1 14 4A8 8 0 0 1 22 12V92Z" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
    if (type === "bumper") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="16" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
    if (type === "pop-bumper") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><circle cx="32" cy="32" r="26" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
    if (type === "led") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><circle cx="14" cy="14" r="10" fill="${c}" /></svg>`;
    }
    if (type === "rgb") {
      const gid = `lighting_guide_g_${safeId}`;
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="${gid}"><stop offset="0%" stop-color="#fff"/><stop offset="100%" stop-color="${c}"/></radialGradient></defs><circle cx="14" cy="14" r="10" fill="url(#${gid})" /></svg>`;
    }
    if (type === "target") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 20 40" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="12" height="32" rx="3" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
    if (type === "coil") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="4" width="36" height="12" rx="3" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
    }
    if (type === "lcd-display") {
      return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 120 72" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="LCD Display"><rect x="6" y="6" width="108" height="60" rx="10" fill="#04070f" stroke="#ffffff" stroke-width="2"/><rect x="8" y="8" width="104" height="26" rx="8" fill="rgba(255,255,255,0.08)"/><rect x="16" y="16" width="88" height="40" rx="4" fill="rgba(255,255,255,0.04)"/></svg>`;
    }
    return `<svg class="emu-svg lighting-layout-guide-svg" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="12" fill="${c}" stroke="${stroke}" stroke-width="2"/></svg>`;
  }

  function renderLayoutGuides(widthPx, heightPx) {
    if (!state.showLayoutGuides) return;
    const items = Array.isArray(state.layoutElements) ? state.layoutElements : [];
    if (!items.length) return;
    const layoutW = Number(state.playfield?.width) > 0 ? Number(state.playfield.width) : 700;
    const layoutH = Number(state.playfield?.height) > 0 ? Number(state.playfield.height) : 1400;
    const layer = document.createElement("div");
    layer.className = "lighting-layout-guides";
    items.forEach((el) => {
      if (!el || typeof el !== "object") return;
      let nx = Number(el.nx);
      let ny = Number(el.ny);
      if (!Number.isFinite(nx) && Number.isFinite(Number(el.x)) && layoutW > 0) nx = Number(el.x) / layoutW;
      if (!Number.isFinite(ny) && Number.isFinite(Number(el.y)) && layoutH > 0) ny = Number(el.y) / layoutH;
      if (!Number.isFinite(nx)) nx = 0.5;
      if (!Number.isFinite(ny)) ny = 0.5;
      const type = layoutGuideType(el);
      const guide = document.createElement("div");
      guide.className = "lighting-layout-guide lighting-layout-guide-emu";
      guide.dataset.type = type || "unknown";
      guide.dataset.size = layoutGuideSizeKey(el);
      const guideColor = normalizeHexColor(el.color, "#60a5fa");
      guide.style.left = `${nx * widthPx}px`;
      guide.style.top = `${ny * heightPx}px`;
      guide.style.setProperty("--emu-size-scale", String((Number(el.scale) || 1) * layoutGuideVisualScale()));
      guide.style.borderRadius = layoutGuideBorderRadius(type);
      guide.style.setProperty("--lighting-guide-bg", hexToRgba(guideColor, 0.35));
      guide.style.setProperty("--lighting-guide-border", hexToRgba(guideColor, 0.75));
      guide.style.setProperty("--lighting-guide-highlight", hexToRgba(guideColor, 0.22));
      guide.style.transform = `translate(-50%, -50%) rotate(${Number(el.rotation) || 0}deg)`;
      guide.classList.add("has-svg");
      guide.innerHTML = layoutGuideSvgFor(el, guideColor);
      layer.appendChild(guide);
    });
    previewTable.appendChild(layer);
  }

  function isHexColor(value) {
    return /^#[0-9a-fA-F]{6}$/.test(String(value || "").trim());
  }

  async function hydrateLayoutGuideColors() {
    const current = Array.isArray(state.layoutElements) ? state.layoutElements : [];
    if (!current.length) return;
    const needsColor = current.some((el) => !isHexColor(el?.color));
    if (!needsColor) return;
    try {
      const r = await fetch("/api/playfield/state", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok || !j) return;
      const source = Array.isArray(j.elements) ? j.elements : [];
      if (!source.length) return;
      const byId = new Map();
      source.forEach((el) => {
        const id = String(el?.id || "").trim();
        if (!id) return;
        byId.set(id, el);
      });
      let changed = false;
      state.layoutElements = current.map((el) => {
        const id = String(el?.id || "").trim();
        const src = id ? byId.get(id) : null;
        const fallbackColor = src?.color;
        const color = isHexColor(el?.color) ? String(el.color) : (isHexColor(fallbackColor) ? String(fallbackColor) : "");
        if (color && color !== el.color) changed = true;
        return { ...el, color: color || el.color };
      });
      if (changed) renderPreview();
    } catch (e) {
      // best effort only
    }
  }

  function renderPreview() {
    applyPreviewPlayfieldBackground();
    previewTable.innerHTML = "";
    const size = previewSize();
    const w = size.width;
    const h = size.height;
    const vs = previewVisualScale();
    previewTable.style.setProperty("--lighting-preview-scale", String(vs));
    renderLayoutGuides(w, h);
    const scene = currentScene();
    const visibleFixtures = sceneVisibleFixtures(scene);
    visibleFixtures.forEach((f) => {
      const pixels = fixturePixels(f, w, h);
      const node = document.createElement("div");
      node.className = "lighting-fixture";
      node.dataset.id = f.id;
      node.style.left = `${pixels[0].x * w}px`;
      node.style.top = `${pixels[0].y * h}px`;
      if (f.type === "rgb_strip") {
        const box = document.createElement("div");
        box.className = "lighting-fixture-strip";
        pixels.forEach((p, idx) => {
          const d = document.createElement("span");
          d.className = "lighting-fixture-strip-dot";
          d.dataset.pixelIndex = String(idx);
          d.title = `${f.title} [${idx}]`;
          d.style.left = `${(p.x - pixels[0].x) * w}px`;
          d.style.top = `${(p.y - pixels[0].y) * h}px`;
          applyDotGeometry(d, f, idx);
          box.appendChild(d);
          if ((f.layoutMode || "line") === "manual") {
            d.classList.add("is-manual");
            d.addEventListener("pointerdown", (e) => {
              e.preventDefault();
              e.stopPropagation();
              state.drag = null;
              state.dragPending = {
                id: f.id,
                pixelIndex: idx,
                mode: "pixel",
                startX: e.clientX,
                startY: e.clientY,
                startedAt: Date.now(),
              };
            });
          }
          const targetKey = pixelTargetKey(f.id, idx);
          if (state.customSelection.has(targetKey)) d.classList.add("is-selected");

          const label = document.createElement("span");
          label.className = "lighting-fixture-strip-index";
          const prev = pixels[Math.max(0, idx - 1)] || p;
          const next = pixels[Math.min(pixels.length - 1, idx + 1)] || p;
          const dirX = ((next.x - prev.x) * w) || 0;
          const dirY = ((next.y - prev.y) * h) || 0;
          label.dataset.pos = stripLabelPosition(dirX, dirY);
          label.textContent = String(idx);
          label.style.left = `${(p.x - pixels[0].x) * w}px`;
          label.style.top = `${(p.y - pixels[0].y) * h}px`;
          box.appendChild(label);
        });
        if (pixels.length >= 2) {
          const dx = (pixels[1].x - pixels[0].x) * w;
          const dy = (pixels[1].y - pixels[0].y) * h;
          const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
          const len = Math.hypot(dx, dy) || 1;
          const ux = dx / len;
          const uy = dy / len;
          const arrow = document.createElement("span");
          arrow.className = "lighting-fixture-strip-arrow";
          arrow.title = "Pixel direction (index increases this way)";
          arrow.style.left = `${-ux * 20}px`;
          arrow.style.top = `${-uy * 20}px`;
          arrow.style.setProperty("--strip-dir-angle", `${angle}deg`);
          box.appendChild(arrow);
        }
        node.appendChild(box);
      } else {
        const dot = document.createElement("span");
        dot.className = "lighting-fixture-dot";
        applyDotGeometry(dot, f);
        if (state.customSelection.has(pixelTargetKey(f.id, 0))) dot.classList.add("is-selected");
        node.appendChild(dot);
      }
      const sel = state.selectedPixel;
      if (sel && sel.fixtureId === f.id) {
        if (f.type === "rgb_strip") {
          if (String(f.layoutMode || "line") === "line") {
            node.querySelectorAll(".lighting-fixture-strip-dot").forEach((dot) => dot.classList.add("is-selected"));
          } else {
            const sd = node.querySelector(`.lighting-fixture-strip-dot[data-pixel-index="${sel.pixelIndex}"]`);
            if (sd) sd.classList.add("is-selected");
          }
        } else {
          node.querySelector(".lighting-fixture-dot")?.classList.add("is-selected");
        }
      }
      setFixtureVisual(node, f, applyPreviewAllOverrideFx(f, { on: false, scale: 1 }));
      node.addEventListener("pointerdown", (e) => {
        const sceneNow = currentScene();
        if (isCustomScene(sceneNow)) return;
        e.preventDefault();
        e.stopPropagation();
        state.drag = null;
        state.dragPending = { id: f.id, mode: "fixture", startX: e.clientX, startY: e.clientY, startedAt: Date.now() };
      });
      previewTable.appendChild(node);
    });
    if (!state.playback) {
      const scene = currentScene();
      if (isCustomScene(scene)) applyCustomFrameVisual(scene);
      return;
    }
    applyPlaybackVisual(performance.now());
  }

  function patternPeriodMs(scene) {
    const p = scene?.params || {};
    const pattern = String(scene?.pattern || "solid").toLowerCase();
    if (pattern === "strobe") {
      const hz = Number(p.rateHz);
      if (Number.isFinite(hz) && hz > 0) return Math.max(16, Math.round(1000 / hz));
    }
    const period = Number(p.periodMs);
    if (Number.isFinite(period) && period > 0) return Math.max(80, period);
    const speedRaw = Number(p.speed);
    const speed = Number.isFinite(speedRaw) ? Math.max(1, speedRaw) : 80;
    // Wider response curve: low speed is clearly slower, high speed clearly faster.
    const clamped = Math.max(1, Math.min(100, speed));
    const mapped = 9000 - (clamped - 1) * 85;
    return Math.max(500, Math.min(9000, mapped));
  }

  function phaseFromElapsed(elapsedMs, periodMs, endBehavior = "repeat") {
    const period = Math.max(1, Number(periodMs) || 1);
    const elapsed = Math.max(0, Number(elapsedMs) || 0);
    const mode = String(endBehavior || "repeat").toLowerCase();
    if (mode === "bounce") {
      const cycle = period * 2;
      const inCycle = elapsed % cycle;
      const t = inCycle <= period ? inCycle : (cycle - inCycle);
      return Math.max(0, Math.min(1, t / period));
    }
    return Math.max(0, Math.min(1, (elapsed % period) / period));
  }

  function phaseForPlayback(elapsedMs, periodMs, endBehavior, durationMs) {
    const mode = String(endBehavior || "repeat").toLowerCase();
    const elapsed = Math.max(0, Number(elapsedMs) || 0);
    const duration = Math.max(0, Number(durationMs) || 0);
    // For stop mode, play a single forward pass across scene duration.
    if (mode === "stop" && duration > 0) {
      return Math.max(0, Math.min(1, elapsed / duration));
    }
    return phaseFromElapsed(elapsed, periodMs, mode);
  }

  function sceneBrightness(scene) {
    const b = Number(scene?.params?.brightness);
    if (!Number.isFinite(b)) return 1;
    return Math.max(0, Math.min(1, b));
  }

  function previewFrameIndex(elapsedMs, durationMs, frameCount, endBehavior, scene) {
    const count = Math.max(1, Number(frameCount) || 1);
    const duration = Math.max(1, Number(durationMs) || 1);
    const elapsed = Math.max(0, Number(elapsedMs) || 0);
    const mode = String(endBehavior || "repeat").toLowerCase();
    const pattern = normalizePatternId(scene?.pattern || "solid");
    if (mode === "stop") {
      const p = Math.max(0, Math.min(1, elapsed / duration));
      return Math.max(0, Math.min(count - 1, Math.floor(p * count)));
    }
    // Match legacy preview semantics for looping modes without over-speeding:
    // derive a cycle-sized frame window from (period / frame_ms).
    const period = Math.max(1, Number(patternPeriodMs(scene)) || 1);
    const frameMs = Math.max(1, duration / count);
    let cycleFrames = Math.max(2, Math.min(count, Math.round(period / frameMs)));
    // Radar/ripple generators complete a full spatial sweep over ~100 frames.
    // If we clamp too low, edges never receive light.
    if (pattern === "radar" || pattern === "ripple") {
      cycleFrames = Math.max(2, Math.min(count, 100));
    }
    if (mode === "bounce") {
      const p = phaseFromElapsed(elapsed, period, "bounce");
      return Math.max(0, Math.min(cycleFrames - 1, Math.floor(p * cycleFrames)));
    }
    const p = phaseFromElapsed(elapsed, period, "repeat");
    return Math.max(0, Math.min(cycleFrames - 1, Math.floor(p * cycleFrames)));
  }

  function customTimelineFx(scene, fixture, elapsedMs) {
    if (!scene || !fixture) return null;
    const fixtureId = String(fixture.id || "");
    const count = Math.max(1, Number(fixture.pixelCount || 1));
    const dynamic = fixtureSupportsDynamicColor(fixture);
    const baseColor = dynamic ? "#ffffff" : normalizeHexColor(fixture.fixedColor, "#60a5fa");
    const pixelState = Array.from({ length: count }, () => ({ on: false, color: baseColor, intensity: 0, brightness: 1 }));
    const timeline = Array.isArray(scene.timeline) ? scene.timeline : [];
    const elapsed = Math.max(0, Math.round(Number(elapsedMs) || 0));

    const applyRowToPixel = (row, px) => {
      if (px < 0 || px >= count) return;
      const cur = pixelState[px];
      const intensityRaw = Number(row?.intensity);
      const brightnessRaw = Number(row?.brightness);
      const intensity = Number.isFinite(intensityRaw) ? Math.max(0, Math.min(1, intensityRaw)) : cur.intensity;
      const brightness = Number.isFinite(brightnessRaw) ? Math.max(0, Math.min(1, brightnessRaw)) : cur.brightness;
      const color = dynamic ? normalizeHexColor(row?.color, cur.color || baseColor) : baseColor;
      pixelState[px] = { on: intensity > 0.01, color, intensity, brightness };
    };

    const grouped = new Map();
    for (let i = 0; i < timeline.length; i += 1) {
      const row = timeline[i];
      if (!row || typeof row !== "object") continue;
      const atMs = Number(row.atMs || 0);
      if (!Number.isFinite(atMs) || atMs > elapsed) continue;
      const target = String(row.fixtureId || "");
      if (target && target !== "*" && target !== fixtureId) continue;
      if (!grouped.has(atMs)) grouped.set(atMs, []);
      grouped.get(atMs).push(row);
    }
    const times = Array.from(grouped.keys()).sort((a, b) => a - b);
    for (let ti = 0; ti < times.length; ti += 1) {
      const rows = grouped.get(times[ti]) || [];
      // At each timestamp: apply fixture-wide first...
      for (let ri = 0; ri < rows.length; ri += 1) {
        const row = rows[ri];
        const rowPx = Number.isFinite(Number(row.pixelIndex)) ? Math.floor(Number(row.pixelIndex)) : null;
        if (rowPx !== null) continue;
        for (let px = 0; px < count; px += 1) applyRowToPixel(row, px);
      }
      // ...then pixel-specific so they override at the same timestamp.
      for (let ri = 0; ri < rows.length; ri += 1) {
        const row = rows[ri];
        const rowPx = Number.isFinite(Number(row.pixelIndex)) ? Math.floor(Number(row.pixelIndex)) : null;
        if (rowPx === null) continue;
        applyRowToPixel(row, rowPx);
      }
    }

    if (fixture.type === "rgb_strip" && count > 1) {
      const dotOn = pixelState.map((p) => !!p.on);
      const dotColors = pixelState.map((p) => p.color);
      const dotIntensity = pixelState.map((p) => Math.max(0, Math.min(1, p.intensity)) * Math.max(0, Math.min(1, p.brightness)));
      const peak = dotIntensity.reduce((m, v) => Math.max(m, v), 0);
      return { on: dotOn.some(Boolean), scale: 1.0 + peak * 0.04, dotOn, dotColors, dotIntensity, color: dotColors[0] || baseColor, brightness: sceneBrightness(scene) };
    }
    const p0 = pixelState[0] || { on: false, color: baseColor, intensity: 0, brightness: 1 };
    return {
      on: !!p0.on,
      scale: 1.0 + Math.max(0, Math.min(1, p0.intensity * p0.brightness)) * 0.05,
      color: p0.color,
      intensity: Math.max(0, Math.min(1, p0.intensity * p0.brightness)),
      brightness: sceneBrightness(scene),
    };
  }

  function compiledFrameFx(scene, fixture, elapsedMs, endBehavior, durationMs) {
    if (isCustomScene(scene)) {
      return customTimelineFx(scene, fixture, elapsedMs);
    }
    const preview = state.previewCompiled;
    const compiledScene = preview?.scene;
    if (!scene || !fixture || !compiledScene || String(compiledScene.id || "") !== String(scene.id || "")) return null;
    const frames = Array.isArray(compiledScene.frames) ? compiledScene.frames : [];
    const frameCount = Math.max(1, Number(compiledScene.frameCount || frames.length || 1));
    if (!frames.length) return null;
    const idx = previewFrameIndex(elapsedMs, durationMs || compiledScene.durationMs || 1, frameCount, endBehavior, scene);
    const fixtureId = String(fixture.id || "");
    const count = Math.max(1, Number(fixture.pixelCount || 1));
    const pixelState = Array.from({ length: count }, () => ({ on: false, color: "#ffffff", intensity: 0, brightness: 1 }));
    let fixtureDirectTouched = false;

    for (let i = 0; i <= idx && i < frames.length; i += 1) {
      const frame = frames[i];
      const changes = Array.isArray(frame?.changes) ? frame.changes : [];
      changes.forEach((c) => {
        const target = String(c?.target || "");
        if (target === "*" && c?.off) {
          for (let px = 0; px < count; px += 1) pixelState[px] = { on: false, color: "#ffffff", intensity: 0, brightness: 1 };
          return;
        }
        const applyToPixel = (px) => {
          const row = pixelState[px];
          if (c?.off) {
            pixelState[px] = { ...row, on: false, intensity: 0 };
            if (target === fixtureId) fixtureDirectTouched = true;
            return;
          }
          const color = normalizeHexColor(c?.color, row.color || "#ffffff");
          const intensityRaw = Number(c?.intensity);
          const brightRaw = Number(c?.brightness);
          const intensity = Number.isFinite(intensityRaw) ? Math.max(0, Math.min(1, intensityRaw)) : row.intensity;
          const brightness = Number.isFinite(brightRaw) ? Math.max(0, Math.min(1, brightRaw)) : row.brightness;
          pixelState[px] = { on: intensity > 0.01, color, intensity, brightness };
          if (target === fixtureId) fixtureDirectTouched = true;
        };
        const px = Number(c?.pixelIndex);
        if (target === "*") {
          if (Number.isFinite(px) && px >= 0 && px < count) {
            applyToPixel(Math.floor(px));
          } else {
            for (let p = 0; p < count; p += 1) applyToPixel(p);
          }
          return;
        }
        if (target !== fixtureId) return;
        if (Number.isFinite(px) && px >= 0 && px < count) {
          applyToPixel(Math.floor(px));
        } else {
          for (let p = 0; p < count; p += 1) applyToPixel(p);
        }
      });
    }

    // Some compiled patterns may omit single fixtures entirely.
    // If this fixture is untouched by compiled changes, default it to ON.
    // Use fixedColor when available so fixed-color singles always participate.
    if (!fixtureDirectTouched && (count === 1 || fixture.type !== "rgb_strip")) {
      const fixed = normalizeHexColor(
        fixture.fixedColor,
        fixtureSupportsDynamicColor(fixture) ? "#ffffff" : "#60a5fa"
      );
      const b = sceneBrightness(scene);
      return {
        on: true,
        scale: 1,
        color: fixed,
        intensity: 1,
        brightness: b,
      };
    }

    if (fixture.type === "rgb_strip" && count > 1) {
      const dotOn = pixelState.map((p) => !!p.on);
      const dotColors = pixelState.map((p) => p.color);
      const dotIntensity = pixelState.map((p) => Math.max(0, Math.min(1, p.intensity)) * Math.max(0, Math.min(1, p.brightness)));
      const peak = dotIntensity.reduce((m, v) => Math.max(m, v), 0);
      return { on: dotOn.some(Boolean), scale: 1.0 + peak * 0.04, dotOn, dotColors, dotIntensity, color: dotColors[0] || "#ffffff", brightness: sceneBrightness(scene) };
    }
    const p0 = pixelState[0] || { on: false, color: "#ffffff", intensity: 0, brightness: 1 };
    return {
      on: !!p0.on,
      scale: 1.0 + Math.max(0, Math.min(1, p0.intensity * p0.brightness)) * 0.05,
      color: p0.color,
      intensity: Math.max(0, Math.min(1, p0.intensity * p0.brightness)),
      brightness: sceneBrightness(scene),
    };
  }

  function stopLocalPreview() {
    if (!state.playback) return;
    if (state.playback.rafId) cancelAnimationFrame(state.playback.rafId);
    state.playback = null;
    updatePlayToggleUI();
    updateCustomTimelineNavButtons(state.customFrameIndex, state.customFrameCount);
    renderPreview();
  }

  function applyPlaybackVisual(nowMs) {
    const pb = state.playback;
    if (!pb) return;
    if (pb.untilMs && nowMs >= pb.untilMs && pb.endBehavior === "stop") {
      stopLocalPreview();
      return;
    }
    const scene = currentScene();
    if (!scene || scene.id !== pb.sceneId) return;
    const visible = sceneVisibleFixtures(scene);
    if (!visible.length) return;
    const elapsed = Math.max(0, nowMs - pb.startedAtMs);
    if (isCustomScene(scene)) syncCustomTimelinePlayback(scene, elapsed);
    previewTable.querySelectorAll(".lighting-fixture").forEach((node) => {
      const id = node.dataset.id || "";
      if (!sceneAffectsFixture(scene, id)) return;
      const fixture = fixtureById(id);
      if (!fixture) return;
      let fx = compiledFrameFx(scene, fixture, elapsed, pb.endBehavior, pb.durationMs || 0);
      if (!fx) fx = { on: false, scale: 1, brightness: sceneBrightness(scene) };
      if (!Number.isFinite(Number(fx?.brightness))) fx.brightness = sceneBrightness(scene);
      setFixtureVisual(node, fixture, applyPreviewAllOverrideFx(fixture, fx));
    });
    pb.rafId = requestAnimationFrame(applyPlaybackVisual);
  }

  function applyCustomFrameVisual(scene) {
    const elapsed = currentCustomTimeMs(scene);
    const durationMs = sceneDurationMs(scene);
    const visible = sceneVisibleFixtures(scene);
    if (!visible.length) return;
    previewTable.querySelectorAll(".lighting-fixture").forEach((node) => {
      const id = node.dataset.id || "";
      if (!sceneAffectsFixture(scene, id)) return;
      const fixture = fixtureById(id);
      if (!fixture) return;
      let fx = compiledFrameFx(scene, fixture, elapsed, scene.endBehavior || "stop", durationMs);
      if (!fx) fx = { on: false, scale: 1, brightness: sceneBrightness(scene) };
      if (!Number.isFinite(Number(fx?.brightness))) fx.brightness = sceneBrightness(scene);
      setFixtureVisual(node, fixture, applyPreviewAllOverrideFx(fixture, fx));
    });
  }

  function startLocalPreview(scene) {
    stopLocalPreview();
    if (!scene) return;
    scheduleCompiledPreview(0);
    const durMs = sceneDurationMs(scene);
    const now = performance.now();
    const startOffsetMs = isCustomScene(scene) ? currentCustomTimeMs(scene) : 0;
    const startedAtMs = now - Math.max(0, startOffsetMs);
    const endBehavior = scene.endBehavior || "stop";
    const remainingMs = Math.max(0, durMs - Math.max(0, startOffsetMs));
    state.playback = {
      sceneId: scene.id,
      startedAtMs,
      untilMs: (endBehavior === "stop" && remainingMs > 0) ? (now + remainingMs) : 0,
      durationMs: durMs,
      endBehavior,
      periodMs: patternPeriodMs(scene),
      rafId: 0,
    };
    updatePlayToggleUI();
    applyPlaybackVisual(now);
  }

  function onMouseMove(e) {
    if (state.boxSelect?.active) {
      const rect = previewTable.getBoundingClientRect();
      const x = Math.max(0, Math.min(rect.width, (e.clientX || 0) - rect.left));
      const y = Math.max(0, Math.min(rect.height, (e.clientY || 0) - rect.top));
      state.boxSelect.endX = x;
      state.boxSelect.endY = y;
      const dx = x - state.boxSelect.startX;
      const dy = y - state.boxSelect.startY;
      if (Math.hypot(dx, dy) > 4) state.boxSelect.moved = true;
      const box = previewTable.querySelector(".lighting-selection-box");
      if (box) {
        const left = Math.min(state.boxSelect.startX, state.boxSelect.endX);
        const top = Math.min(state.boxSelect.startY, state.boxSelect.endY);
        const width = Math.abs(state.boxSelect.endX - state.boxSelect.startX);
        const height = Math.abs(state.boxSelect.endY - state.boxSelect.startY);
        box.style.left = `${left}px`;
        box.style.top = `${top}px`;
        box.style.width = `${width}px`;
        box.style.height = `${height}px`;
      }
      return;
    }
    if (!state.drag && state.dragPending) {
      const dx0 = (e.clientX || 0) - state.dragPending.startX;
      const dy0 = (e.clientY || 0) - state.dragPending.startY;
      const dist = Math.hypot(dx0, dy0);
      const heldMs = Date.now() - state.dragPending.startedAt;
      if (dist < DRAG_START_DISTANCE_PX && heldMs < DRAG_START_DELAY_MS) return;
      state.drag = {
        id: state.dragPending.id,
        mode: state.dragPending.mode || "fixture",
        pixelIndex: Number(state.dragPending.pixelIndex),
        x: e.clientX,
        y: e.clientY,
      };
      state.dragPending = null;
    }
    if (!state.drag) return;
    state.suppressClick = true;
    const fixture = fixtureById(state.drag.id);
    if (!fixture) return;
    const rect = previewTable.getBoundingClientRect();
    const dx = (e.clientX - state.drag.x) / (rect.width || 1);
    const dy = (e.clientY - state.drag.y) / (rect.height || 1);
    state.drag.x = e.clientX;
    state.drag.y = e.clientY;
    if (state.drag.mode === "pixel" && (fixture.layoutMode || "line") === "manual") {
      moveManualPixelByDelta(fixture, state.drag.pixelIndex, dx, dy, rect.width || 1, rect.height || 1);
    } else {
      moveFixtureByDelta(fixture, dx, dy, rect.width || 1, rect.height || 1);
    }
    markDirty();
    renderPreview();
  }

  function onMouseUp() {
    if (state.boxSelect?.active) {
      const box = previewTable.querySelector(".lighting-selection-box");
      if (box) box.remove();
      if (state.boxSelect.moved) {
        const rect = previewTable.getBoundingClientRect();
        const left = Math.min(state.boxSelect.startX, state.boxSelect.endX);
        const right = Math.max(state.boxSelect.startX, state.boxSelect.endX);
        const top = Math.min(state.boxSelect.startY, state.boxSelect.endY);
        const bottom = Math.max(state.boxSelect.startY, state.boxSelect.endY);
        const hitKeys = [];
        previewTable.querySelectorAll(".lighting-fixture-strip-dot, .lighting-fixture-dot").forEach((dot) => {
          const fr = dot.closest(".lighting-fixture");
          const fixtureId = fr?.dataset?.id || "";
          if (!fixtureId) return;
          const pixelIndex = dot.classList.contains("lighting-fixture-strip-dot")
            ? Number(dot.getAttribute("data-pixel-index") || 0)
            : 0;
          const dr = dot.getBoundingClientRect();
          const cx = (dr.left + dr.right) * 0.5 - rect.left;
          const cy = (dr.top + dr.bottom) * 0.5 - rect.top;
          if (cx >= left && cx <= right && cy >= top && cy <= bottom) {
            hitKeys.push(pixelTargetKey(fixtureId, pixelIndex));
          }
        });
        const next = new Set(state.customSelection);
        if (state.boxSelect.mode === "replace") next.clear();
        hitKeys.forEach((k) => {
          if (state.boxSelect.mode === "remove") next.delete(k);
          else next.add(k);
        });
        state.customSelection = next;
        syncCustomSelectionFocus();
        if (isCustomScene(currentScene())) renderCustomTimelinePanel();
        renderPixelInspector();
        renderPreview();
      }
      const didDragSelect = !!state.boxSelect.moved;
      state.boxSelect = null;
      if (didDragSelect) {
        state.suppressClick = true;
        setTimeout(() => {
          state.suppressClick = false;
        }, 0);
      }
      return;
    }
    if (state.drag || state.dragPending) {
      setTimeout(() => {
        state.suppressClick = false;
      }, 0);
    }
    state.drag = null;
    state.dragPending = null;
  }

  function pixelTargetKey(fixtureId, pixelIndex) {
    return `${String(fixtureId || "")}::${Math.max(0, Number(pixelIndex) || 0)}`;
  }

  function syncCustomSelectionFocus() {
    if (!state.customSelection.size) {
      clearSelectedPixel();
      return;
    }
    const first = Array.from(state.customSelection)
      .map(parsePixelTargetKey)
      .find(Boolean);
    if (!first) {
      clearSelectedPixel();
      return;
    }
    selectPixel(first.fixtureId, first.pixelIndex);
  }

  function boxSelectModeFromEvent(e) {
    if (e.altKey) return "remove";
    return "add";
  }

  function onPreviewMouseDown(e) {
    if (e.button !== 0) return;
    if (!previewTable) return;
    const rect = previewTable.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, (e.clientX || 0) - rect.left));
    const y = Math.max(0, Math.min(rect.height, (e.clientY || 0) - rect.top));
    state.drag = null;
    state.dragPending = null;
    state.boxSelect = {
      active: true,
      startX: x,
      startY: y,
      endX: x,
      endY: y,
      moved: false,
      mode: boxSelectModeFromEvent(e),
    };
    const box = document.createElement("div");
    box.className = "lighting-selection-box";
    box.style.left = `${x}px`;
    box.style.top = `${y}px`;
    box.style.width = "0px";
    box.style.height = "0px";
    previewTable.appendChild(box);
    e.preventDefault();
  }

  function parsePixelTargetKey(key) {
    const s = String(key || "");
    const i = s.lastIndexOf("::");
    if (i < 0) return null;
    const fixtureId = s.slice(0, i);
    const pixelIndex = Number(s.slice(i + 2));
    if (!fixtureId) return null;
    if (!Number.isFinite(pixelIndex) || pixelIndex < 0) return null;
    return { fixtureId, pixelIndex: Math.floor(pixelIndex) };
  }

  function ensureCustomTimelineState(scene) {
    if (!scene) return;
    const sceneId = String(scene.id || "");
    if (state.customSceneId !== sceneId) {
      state.customSceneId = sceneId;
      state.customFrameIndex = 0;
      state.customSelection = new Set();
    }
    if (scene.duration?.unit === "frames") {
      const frameCount = Math.max(1, Math.round(Number(scene.duration?.value || 1)));
      state.customFrameCount = frameCount;
      state.customFrameMs = DURATION_FRAME_MS;
      state.customFrameIndex = Math.max(0, Math.min(frameCount - 1, state.customFrameIndex));
      return;
    }
    const durationMs = Math.max(100, sceneDurationMs(scene));
    const targetFrames = 120;
    const frameMsRaw = Math.max(50, Math.round(durationMs / Math.max(1, targetFrames - 1)));
    const frameMs = Math.max(50, Math.round(frameMsRaw / 10) * 10);
    const frameCount = Math.max(2, Math.floor(durationMs / frameMs) + 1);
    state.customFrameMs = frameMs;
    state.customFrameCount = frameCount;
    state.customFrameIndex = Math.max(0, Math.min(frameCount - 1, Math.round(Number(state.customFrameIndex) || 0)));
  }

  function currentCustomTimeMs(scene) {
    if (!scene) return 0;
    ensureCustomTimelineState(scene);
    const t = state.customFrameIndex * state.customFrameMs;
    return Math.max(0, Math.min(sceneDurationMs(scene), t));
  }

  function sceneMarkers(scene) {
    if (!scene || !Array.isArray(scene.markers)) {
      if (scene) scene.markers = [];
      return [];
    }
    return scene.markers;
  }

  function markerAtMs(scene, atMs) {
    const t = snapMsToFrame(scene, atMs);
    return sceneMarkers(scene).find((m) => Number(m?.atMs || 0) === t) || null;
  }

  function markerAtFrame(scene, frameIndex) {
    const idx = Math.max(0, Math.round(Number(frameIndex) || 0));
    return sceneMarkers(scene).find((m) => frameIndexForMs(scene, Number(m?.atMs || 0)) === idx) || null;
  }

  function normalizeMarkerTag(raw) {
    return String(raw || "").trim().toLowerCase();
  }

  function validMarkerTag(tag) {
    return /^[a-z0-9][a-z0-9_-]{0,63}$/.test(String(tag || ""));
  }

  function upsertSceneMarker(scene, atMs, tagRaw) {
    const t = snapMsToFrame(scene, atMs);
    const tag = normalizeMarkerTag(tagRaw);
    if (!validMarkerTag(tag)) {
      return { ok: false, error: "Tag must match: lowercase letters/numbers, _ or -, max 64 chars." };
    }
    const markers = sceneMarkers(scene);
    const tagInUse = markers.find((m) => String(m?.tag || "") === tag && Number(m?.atMs || 0) !== t);
    if (tagInUse) {
      return { ok: false, error: `Tag "${tag}" already exists in this scene.` };
    }
    const byTime = markers.find((m) => Number(m?.atMs || 0) === t);
    if (byTime) {
      byTime.tag = tag;
    } else {
      markers.push({ atMs: t, tag });
    }
    markers.sort((a, b) => Number(a?.atMs || 0) - Number(b?.atMs || 0));
    return { ok: true };
  }

  function removeSceneMarker(scene, atMs) {
    const t = snapMsToFrame(scene, atMs);
    scene.markers = sceneMarkers(scene).filter((m) => Number(m?.atMs || 0) !== t);
  }

  function frameIndexForMs(scene, atMs) {
    if (!scene) return 0;
    ensureCustomTimelineState(scene);
    const ms = Math.max(0, Math.round(Number(atMs) || 0));
    const idx = Math.round(ms / Math.max(1, state.customFrameMs));
    return Math.max(0, Math.min(state.customFrameCount - 1, idx));
  }

  function snapMsToFrame(scene, atMs) {
    if (!scene) return Math.max(0, Math.round(Number(atMs) || 0));
    const idx = frameIndexForMs(scene, atMs);
    const snapped = idx * Math.max(1, state.customFrameMs);
    return Math.max(0, Math.min(sceneDurationMs(scene), Math.round(snapped)));
  }

  function openMarkerModal(scene, atMs) {
    if (!scene) return;
    const t = snapMsToFrame(scene, atMs);
    const marker = markerAtMs(scene, t);
    if (!markerModalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) {
      const initial = marker ? marker.tag : "";
      const next = window.prompt("Tag name (lowercase, a-z0-9, _ or -):", initial);
      if (next === null) return;
      if (!next.trim()) {
        removeSceneMarker(scene, t);
        markDirty();
        refreshMarkerUiLive();
        return;
      }
      const result = upsertSceneMarker(scene, t, next);
      if (!result.ok) {
        alert(result.error || "Invalid tag");
        return;
      }
      markDirty();
      refreshMarkerUiLive();
      return;
    }
    const frameText = markerModalEl.querySelector("#lighting-marker-modal-frame");
    const input = markerModalEl.querySelector("#lighting-marker-modal-input");
    const removeBtn = markerModalEl.querySelector("#lighting-marker-modal-remove");
    if (frameText) {
      frameText.textContent = `Frame ${frameIndexForMs(scene, t) + 1} · ${t} ms`;
    }
    if (input) input.value = marker ? marker.tag : "";
    if (removeBtn) removeBtn.disabled = !marker;
    state.markerModalCtx = { sceneId: String(scene.id || ""), atMs: t };
    if (!state.markerModal) {
      state.markerModal = bootstrap.Modal.getOrCreateInstance(markerModalEl, { backdrop: "static" });
    }
    state.markerModal.show();
    setTimeout(() => input?.focus(), 20);
  }

  function commitMarkerModal(saveMode) {
    const ctx = state.markerModalCtx;
    if (!ctx) return;
    const scene = currentScene();
    if (!scene || String(scene.id || "") !== String(ctx.sceneId || "")) return;
    if (!saveMode) {
      removeSceneMarker(scene, ctx.atMs);
      markDirty();
      refreshMarkerUiLive();
      state.markerModal?.hide();
      return;
    }
    const input = markerModalEl?.querySelector("#lighting-marker-modal-input");
    const raw = input?.value || "";
    const result = upsertSceneMarker(scene, ctx.atMs, raw);
    if (!result.ok) {
      alert(result.error || "Invalid tag");
      return;
    }
    markDirty();
    refreshMarkerUiLive();
    state.markerModal?.hide();
  }

  function refreshMarkerUiLive() {
    // Keep editor tag pills and timeline markers in sync after marker edits.
    renderSceneEditor();
    renderPixelInspector();
    renderPreview();
  }

  function customTimelineMetaText(frame, tMs, selectedCount, scene) {
    const marker = markerAtFrame(scene, frame);
    const base = `Frame ${frame + 1}/${state.customFrameCount} · ${Math.round(tMs)} ms · Selected LEDs: ${selectedCount}`;
    if (!marker) return escapeHtml(base);
    return `${escapeHtml(base)} <span class="lighting-tag-pill">${escapeHtml(marker.tag)}</span>`;
  }

  function updateCustomTimelineNavButtons(frameIndex, frameCount) {
    const prevBtn = document.getElementById("lighting-custom-prev");
    const nextBtn = document.getElementById("lighting-custom-next");
    if (!prevBtn && !nextBtn) return;
    const safeCount = Math.max(1, Number(frameCount) || 1);
    const safeIndex = Math.max(0, Math.min(safeCount - 1, Math.round(Number(frameIndex) || 0)));
    const atFirst = safeIndex <= 0;
    const atLast = safeIndex >= (safeCount - 1);
    if (prevBtn) {
      prevBtn.disabled = atFirst;
      prevBtn.classList.toggle("disabled", atFirst);
      prevBtn.setAttribute("aria-disabled", atFirst ? "true" : "false");
    }
    if (nextBtn) {
      nextBtn.disabled = atLast;
      nextBtn.classList.toggle("disabled", atLast);
      nextBtn.setAttribute("aria-disabled", atLast ? "true" : "false");
    }
  }

  function syncCustomTimelinePlayback(scene, elapsedMs) {
    if (!scene || !isCustomScene(scene)) return;
    ensureCustomTimelineState(scene);
    const durationMs = Math.max(1, sceneDurationMs(scene));
    const running = state.playback && state.playback.sceneId === scene.id;
    const endBehavior = running ? String(state.playback.endBehavior || "stop").toLowerCase() : "stop";
    const elapsed = Math.max(0, elapsedMs);
    let tMs = Math.max(0, Math.min(durationMs, elapsed));
    if (endBehavior === "repeat") {
      tMs = elapsed % durationMs;
    } else if (endBehavior === "bounce") {
      const cycle = durationMs * 2;
      const inCycle = elapsed % cycle;
      tMs = inCycle <= durationMs ? inCycle : (cycle - inCycle);
    }
    const frameFloat = Math.max(
      0,
      Math.min(
        state.customFrameCount - 1,
        tMs / Math.max(1, state.customFrameMs)
      )
    );
    const next = Math.max(
      0,
      Math.min(
        state.customFrameCount - 1,
        Math.floor(frameFloat + 1e-6)
      )
    );
    const frameChanged = next !== state.customFrameIndex;
    state.customFrameIndex = next;
    const scrub = document.getElementById("lighting-custom-scrub");
    if (scrub) scrub.value = String(frameFloat);
    updateCustomTimelineNavButtons(next, state.customFrameCount);
    const meta = document.getElementById("lighting-custom-frame-meta");
    if (meta) meta.innerHTML = customTimelineMetaText(next, tMs, state.customSelection.size, scene);
    if (frameChanged && state.customSelection.size) renderPixelInspector();
  }

  function setCustomFrameIndex(idx) {
    const scene = currentScene();
    if (!isCustomScene(scene)) return;
    ensureCustomTimelineState(scene);
    const next = Math.max(0, Math.min(state.customFrameCount - 1, Math.round(Number(idx) || 0)));
    state.customFrameIndex = next;
    const tMs = currentCustomTimeMs(scene);
    const pb = state.playback;
    if (pb && String(pb.sceneId || "") === String(scene.id || "")) {
      const now = performance.now();
      pb.startedAtMs = now - tMs;
      if (String(pb.endBehavior || "stop").toLowerCase() === "stop") {
        const total = Math.max(0, Number(pb.durationMs) || 0);
        const remaining = Math.max(0, total - tMs);
        pb.untilMs = remaining > 0 ? (now + remaining) : now;
      }
    }
    const scrub = document.getElementById("lighting-custom-scrub");
    if (scrub && String(scrub.value) !== String(next)) scrub.value = String(next);
    updateCustomTimelineNavButtons(next, state.customFrameCount);
    const meta = document.getElementById("lighting-custom-frame-meta");
    if (meta) meta.innerHTML = customTimelineMetaText(next, tMs, state.customSelection.size, scene);
    renderPixelInspector();
    renderPreview();
  }

  function clearCustomFrame(scene) {
    if (!scene || !isCustomScene(scene)) return;
    const t = currentCustomTimeMs(scene);
    scene.timeline = (scene.timeline || []).filter((fr) => Number(fr.atMs || 0) !== t);
    const resetEntries = [];
    sceneVisibleFixtures(scene).forEach((fixture) => {
      if (!fixture || !fixture.id) return;
      const fixtureId = String(fixture.id);
      if (!fixture) return;
      const baseColor = fixtureSupportsDynamicColor(fixture)
        ? "#ffffff"
        : normalizeHexColor(fixture.fixedColor, "#60a5fa");
      if (fixture.type === "rgb_strip" && Number(fixture.pixelCount || 1) > 1) {
        resetEntries.push({
          atMs: t,
          fixtureId,
          color: baseColor,
          intensity: 0,
          brightness: 0,
        });
      } else {
        resetEntries.push({
          atMs: t,
          fixtureId,
          pixelIndex: 0,
          color: baseColor,
          intensity: 0,
          brightness: 0,
        });
      }
    });
    scene.timeline.push(...resetEntries);
    scene.timeline.sort((a, b) => Number(a.atMs || 0) - Number(b.atMs || 0));
    markDirty();
    renderCustomTimelinePanel();
    renderPixelInspector();
    renderPreview();
  }

  function applyCustomToSelection(scene, on, color, brightness = 1, options = {}) {
    if (!scene || !isCustomScene(scene)) return;
    if (!state.customSelection.size) return;
    const refreshInspector = options?.refreshInspector !== false;
    const t = currentCustomTimeMs(scene);
    scene.timeline = Array.isArray(scene.timeline) ? scene.timeline : [];
    const selected = Array.from(state.customSelection)
      .map(parsePixelTargetKey)
      .filter(Boolean);
    selected.forEach((target) => {
      scene.timeline = scene.timeline.filter((fr) => {
        if (Number(fr.atMs || 0) !== t) return true;
        if (String(fr.fixtureId || "") !== target.fixtureId) return true;
        const frPx = fr.pixelIndex;
        const frIdx = Number.isFinite(Number(frPx)) ? Number(frPx) : 0;
        return frIdx !== target.pixelIndex;
      });
      const fixture = fixtureById(target.fixtureId);
      const outColor = fixtureSupportsDynamicColor(fixture)
        ? normalizeHexColor(color, "#ffffff")
        : normalizeHexColor(fixture?.fixedColor, "#60a5fa");
      scene.timeline.push({
        atMs: t,
        fixtureId: target.fixtureId,
        pixelIndex: target.pixelIndex,
        color: outColor,
        intensity: on ? 1 : 0,
        brightness: on ? Math.max(0, Math.min(1, Number(brightness) || 0)) : 0,
      });
    });
    scene.timeline.sort((a, b) => Number(a.atMs || 0) - Number(b.atMs || 0));
    markDirty();
    scheduleCompiledPreview(0);
    renderCustomTimelinePanel();
    if (refreshInspector) renderPixelInspector();
    renderPreview();
  }

  function renderCustomTimelinePanel() {
    if (!customTimelineWrap) return;
    const scene = currentScene();
    if (!isCustomScene(scene)) {
      customTimelineWrap.classList.add("d-none");
      customTimelineWrap.innerHTML = "";
      scheduleLayoutPass();
      return;
    }
    ensureCustomTimelineState(scene);
    const frame = state.customFrameIndex;
    const prevDisabled = frame <= 0;
    const nextDisabled = frame >= (state.customFrameCount - 1);
    const tMs = currentCustomTimeMs(scene);
    const selectedCount = state.customSelection.size;
    const markers = sceneMarkers(scene);
    const frameDen = Math.max(1, state.customFrameCount - 1);
    const markerPins = markers.map((m) => {
      const atMs = Math.max(0, Math.round(Number(m?.atMs || 0)));
      const markerIdx = frameIndexForMs(scene, atMs);
      const leftPct = Math.max(0, Math.min(100, (markerIdx / frameDen) * 100));
      return `<button class="lighting-marker-pin" type="button" data-marker-at="${atMs}" style="left:${leftPct}%;" title="${escapeHtml(m.tag)}"><i class="fa fa-tag"></i></button>`;
    }).join("");
    customTimelineWrap.classList.remove("d-none");
    customTimelineWrap.innerHTML = `
      <div class="card border-secondary-subtle">
        <div class="card-body py-2">
          <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
            <div class="fw-semibold">Custom Timeline</div>
            <div class="small text-secondary" id="lighting-custom-frame-meta">${customTimelineMetaText(frame, tMs, selectedCount, scene)}</div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <button class="btn btn-outline-secondary btn-sm${prevDisabled ? " disabled" : ""}" type="button" id="lighting-custom-prev"${prevDisabled ? " disabled aria-disabled=\"true\"" : ""}><i class="fa fa-chevron-right" style="display:inline-block;transform:rotate(180deg);"></i></button>
            <button class="btn btn-outline-secondary btn-sm${nextDisabled ? " disabled" : ""}" type="button" id="lighting-custom-next"${nextDisabled ? " disabled aria-disabled=\"true\"" : ""}><i class="fa fa-chevron-right"></i></button>
            <div class="lighting-scrub-wrap flex-grow-1">
              <input class="form-range m-0" id="lighting-custom-scrub" type="range" min="0" max="${state.customFrameCount - 1}" step="any" value="${frame}">
              <div class="lighting-marker-track" id="lighting-custom-marker-track">${markerPins}</div>
            </div>
            <button class="btn btn-outline-secondary btn-sm" type="button" id="lighting-custom-tag-btn" title="Tag current frame"><i class="fa fa-tag"></i></button>
            <button class="btn btn-outline-danger btn-sm ms-auto text-nowrap" type="button" id="lighting-custom-clear-frame">Clear Frame</button>
          </div>
          <div class="small text-secondary">Use Pixel Inspector to apply ON/OFF and colour to selected LEDs.</div>
        </div>
      </div>
    `;
    const scrub = document.getElementById("lighting-custom-scrub");
    scrub?.addEventListener("input", (e) => setCustomFrameIndex(Number(e.target.value)));
    scrub?.addEventListener("change", (e) => setCustomFrameIndex(Number(e.target.value)));
    document.getElementById("lighting-custom-prev")?.addEventListener("click", () => setCustomFrameIndex(state.customFrameIndex - 1));
    document.getElementById("lighting-custom-next")?.addEventListener("click", () => setCustomFrameIndex(state.customFrameIndex + 1));
    document.getElementById("lighting-custom-tag-btn")?.addEventListener("click", () => {
      openMarkerModal(scene, currentCustomTimeMs(scene));
    });
    document.getElementById("lighting-custom-clear-frame")?.addEventListener("click", () => clearCustomFrame(scene));
    customTimelineWrap.querySelectorAll(".lighting-marker-pin").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const atMs = Number(e.currentTarget?.getAttribute("data-marker-at") || 0);
        const idx = frameIndexForMs(scene, atMs);
        setCustomFrameIndex(idx);
        openMarkerModal(scene, atMs);
      });
    });
    scheduleLayoutPass();
  }

  function onGlobalTimelineKeydown(e) {
    const blurArrowFocus = () => {
      const ae = document.activeElement;
      if (!ae || ae === document.body || ae === document.documentElement) return;
      const tag = String(ae.tagName || "").toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (ae.isContentEditable) return;
      if (typeof ae.blur === "function") ae.blur();
      // Some focus targets (notably tab panes) re-paint focus after keydown;
      // blur again on next frame to fully clear the ring.
      requestAnimationFrame(() => {
        const now = document.activeElement;
        if (!now || now === document.body || now === document.documentElement) return;
        const nowTag = String(now.tagName || "").toUpperCase();
        if (nowTag === "INPUT" || nowTag === "TEXTAREA" || nowTag === "SELECT") return;
        if (now.isContentEditable) return;
        if (typeof now.blur === "function") now.blur();
      });
    };
    const target = e.target;
    if (target && (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable
    )) {
      return;
    }
    const isArrowKey = e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "ArrowUp" || e.key === "ArrowDown";
    if (isArrowKey) {
      const rect = previewTable?.getBoundingClientRect?.();
      if (rect && rect.width > 0 && rect.height > 0) {
        const dxPx = e.key === "ArrowLeft" ? -1 : (e.key === "ArrowRight" ? 1 : 0);
        const dyPx = e.key === "ArrowUp" ? -1 : (e.key === "ArrowDown" ? 1 : 0);
        const dx = dxPx / rect.width;
        const dy = dyPx / rect.height;
        const moved = new Set();
        let changed = false;
        if (state.customSelection && state.customSelection.size) {
          Array.from(state.customSelection)
            .map(parsePixelTargetKey)
            .filter(Boolean)
            .forEach((sel) => {
              const key = `${sel.fixtureId}::${sel.pixelIndex}`;
              if (moved.has(key)) return;
              moved.add(key);
              const fixture = fixtureById(sel.fixtureId);
              if (!fixture) return;
              if (fixture.type === "rgb_strip" && String(fixture.layoutMode || "line") === "manual") {
                moveManualPixelByDelta(fixture, sel.pixelIndex, dx, dy, rect.width, rect.height);
              } else {
                moveFixtureByDelta(fixture, dx, dy, rect.width, rect.height);
              }
              changed = true;
            });
        } else if (state.selectedPixel?.fixtureId) {
          const fixture = fixtureById(state.selectedPixel.fixtureId);
          if (fixture) {
            if (fixture.type === "rgb_strip" && String(fixture.layoutMode || "line") === "manual") {
              moveManualPixelByDelta(fixture, state.selectedPixel.pixelIndex, dx, dy, rect.width, rect.height);
            } else {
              moveFixtureByDelta(fixture, dx, dy, rect.width, rect.height);
            }
            changed = true;
          }
        }
        if (changed) {
          e.preventDefault();
          markDirty();
          renderPreview();
          renderPixelInspector();
          return;
        }
      }
    }

    const scene = currentScene();
    if (!isCustomScene(scene)) {
      if (isArrowKey) {
        e.preventDefault();
        blurArrowFocus();
      }
      return;
    }
    if (!customTimelineWrap || customTimelineWrap.classList.contains("d-none")) {
      if (isArrowKey) {
        e.preventDefault();
        blurArrowFocus();
      }
      return;
    }
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      setCustomFrameIndex(state.customFrameIndex - 1);
      return;
    }
    if (e.key === "ArrowRight") {
      e.preventDefault();
      setCustomFrameIndex(state.customFrameIndex + 1);
      return;
    }
    if (isArrowKey) {
      e.preventDefault();
      blurArrowFocus();
    }
  }

  function clampWithPad(v, axisPx) {
    if (!Number.isFinite(v)) return 0.5;
    const span = Math.max(1, Number(axisPx) || 1);
    const padNorm = PREVIEW_PAD_PX / span;
    const min = -padNorm;
    const max = 1 + padNorm;
    if (v < min) return min;
    if (v > max) return max;
    return v;
  }

  function clamp(v, min, max) {
    if (v < min) return min;
    if (v > max) return max;
    return v;
  }

  function fixturePointRadiusPx(fixture) {
    ensureFixtureVisualConfig(fixture);
    const count = Math.max(1, Number(fixture?.pixelCount || 1));
    let maxWidth = 0;
    for (let i = 0; i < count; i += 1) {
      const cfg = visualConfigForDot(fixture, i);
      const isWide = cfg.shape === "rectangle" || cfg.shape === "pill";
      const width = isWide ? cfg.sizePx * 1.65 : cfg.sizePx;
      if (width > maxWidth) maxWidth = width;
    }
    return Math.max(2, maxWidth / 2);
  }

  function fixtureBoundsNorm(fixture, widthPx, heightPx) {
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    const pts = fixturePixels(fixture, w, h);
    if (!pts.length) return { minX: 0.5, maxX: 0.5, minY: 0.5, maxY: 0.5 };
    const rpx = fixturePointRadiusPx(fixture);
    const rx = rpx / w;
    const ry = rpx / h;
    let minX = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    pts.forEach((p) => {
      const x = Number(p.x);
      const y = Number(p.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      minX = Math.min(minX, x - rx);
      maxX = Math.max(maxX, x + rx);
      minY = Math.min(minY, y - ry);
      maxY = Math.max(maxY, y + ry);
    });
    if (!Number.isFinite(minX)) return { minX: 0.5, maxX: 0.5, minY: 0.5, maxY: 0.5 };
    return { minX, maxX, minY, maxY };
  }

  function moveFixtureByDelta(fixture, dx, dy, widthPx, heightPx) {
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    const padX = PREVIEW_PAD_PX / w;
    const padY = PREVIEW_PAD_PX / h;
    const bounds = fixtureBoundsNorm(fixture, w, h);
    const minDx = -padX - bounds.minX;
    const maxDx = (1 + padX) - bounds.maxX;
    const minDy = -padY - bounds.minY;
    const maxDy = (1 + padY) - bounds.maxY;
    const shiftX = clamp(dx, minDx, maxDx);
    const shiftY = clamp(dy, minDy, maxDy);

    if (fixture.layoutMode === "manual" && Array.isArray(fixture.points) && fixture.points.length) {
      fixture.points = fixture.points.map((p) => ({
        x: Number(p.x) + shiftX,
        y: Number(p.y) + shiftY,
      }));
      return;
    }
    const line = fixture.line || { x1: 0.4, y1: 0.5, x2: 0.6, y2: 0.5 };
    fixture.line = {
      x1: Number(line.x1) + shiftX,
      y1: Number(line.y1) + shiftY,
      x2: Number(line.x2) + shiftX,
      y2: Number(line.y2) + shiftY,
    };
  }

  function moveManualPixelByDelta(fixture, pixelIndex, dx, dy, widthPx, heightPx) {
    if (!fixture || fixture.type !== "rgb_strip") return;
    const idx = Number(pixelIndex);
    if (!Number.isFinite(idx) || idx < 0) return;
    const w = Math.max(1, Number(widthPx) || 1);
    const h = Math.max(1, Number(heightPx) || 1);
    normalizeManualPointsForCount(fixture, w, h);
    if (!Array.isArray(fixture.points) || !fixture.points[idx]) return;
    const p = fixture.points[idx];
    fixture.points[idx] = {
      x: clampWithPad(Number(p.x) + dx, w),
      y: clampWithPad(Number(p.y) + dy, h),
    };
  }

  async function save() {
    const sceneBeforeSave = currentScene();
    const customSceneIdBeforeSave = isCustomScene(sceneBeforeSave) ? String(sceneBeforeSave?.id || "") : "";
    const customFrameBeforeSave = state.customFrameIndex;
    state.fixtures.forEach((f) => {
      ensureFixtureVisualConfig(f);
      if (fixtureUsesPerPixelVisuals(f)) {
        const count = Math.max(1, Number(f.pixelCount || 1));
        for (let i = 0; i < count; i += 1) ensurePointVisualAt(f, i);
      }
    });
    state.config.fixtures = Object.fromEntries(
      state.fixtures.map((f) => [
        f.id,
        {
          pixelCount: Number(f.pixelCount || 1),
          fixedColor: normalizeHexColor(f.fixedColor, "#60a5fa"),
          layoutMode: f.layoutMode || "line",
          markerShape: normalizeMarkerShape(f.markerShape),
          markerSizePx: normalizeMarkerSizePx(f.markerSizePx, f),
          markerRotationDeg: normalizeMarkerRotationDeg(f.markerRotationDeg),
          lengthPx: Number.isFinite(Number(f.lengthPx)) ? Math.max(1, Number(f.lengthPx)) : null,
          line: f.line || null,
          points: Array.isArray(f.points) ? f.points : [],
          pointVisuals: Array.isArray(f.pointVisuals) ? f.pointVisuals.map((row) => ({
            shape: normalizeMarkerShape(row?.shape),
            sizePx: normalizeMarkerSizePx(row?.sizePx, f),
            rotationDeg: normalizeMarkerRotationDeg(row?.rotationDeg),
          })) : [],
        },
      ])
    );
    const r = await fetch(API.save, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.config),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      alert(`Save failed: ${j.error || r.status}`);
      return;
    }
    markDirty(false);
    await loadState();
    const sceneAfterSave = currentScene();
    if (
      customSceneIdBeforeSave &&
      isCustomScene(sceneAfterSave) &&
      String(sceneAfterSave?.id || "") === customSceneIdBeforeSave
    ) {
      setCustomFrameIndex(customFrameBeforeSave);
    }
    // Saving local lighting config means controller sync is now stale until user syncs.
    // Defer status refresh to avoid a brief race where backend status is still catching up.
    setSyncUiState("out");
    setTimeout(() => {
      loadSyncStatus().catch(() => {});
    }, 1200);
  }

  async function syncLighting(opts = {}) {
    const skipConfirm = opts && opts.skipConfirm === true;
    let skipSyncConfirm = false;
    if (state.dirty) {
      const proceed = await confirmSaveBeforeSync();
      if (!proceed) return;
      const before = state.dirty;
      await save();
      if (state.dirty || before === state.dirty) {
        // save() failed or no-op with errors shown to user.
        return;
      }
      skipSyncConfirm = true;
    }
    if (!skipSyncConfirm && !skipConfirm) {
      const confirmed = await confirmSyncAction();
      if (!confirmed) return;
    }
    if (syncBtn) syncBtn.disabled = true;
    if (!state.syncModal && syncModalEl && window.bootstrap?.Modal) {
      state.syncModal = bootstrap.Modal.getOrCreateInstance(syncModalEl);
    }
    if (state.syncModal) state.syncModal.show();
    state.syncStartedAtSec = Math.floor(Date.now() / 1000);
    setSyncStatus("Starting sync…", "", true);
    setSyncProgress(0, "Waiting for bridge upload start…", true);
    stopSyncPoll();
    const r = await fetch(API.sync, { method: "POST" });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      if (syncBtn) syncBtn.disabled = false;
      setSyncStatus("Sync failed", "", false);
      setSyncProgress(0, j.error || "Failed to queue sync.", false);
      return;
    }
    setSyncStatus("Sync running", "", true);
    state.syncTimer = setInterval(pollSyncStatus, 250);
    pollSyncStatus();
    return true;
  }

  async function waitForLightingInSync(timeoutMs = 12000) {
    const deadline = Date.now() + Math.max(500, Number(timeoutMs) || 12000);
    while (Date.now() < deadline) {
      try {
        const outOfSync = await loadSyncStatus();
        if (!outOfSync) return true;
      } catch (_) {
        // best effort
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    return false;
  }

  async function playSelected() {
    const scene = currentScene();
    if (!scene) return;
    try {
      await refreshCompiledPreviewNow();
    } catch (e) {
      // Best effort: fallback renderer can still run.
    }
    startLocalPreview(scene);
    await runSelectedOnEsp();
  }

  async function runSelectedOnEsp() {
    const scene = currentScene();
    if (!scene) return { ok: false, error: "scene_required", sceneId: "" };
    const r = await fetch(API.previewPlay, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneId: scene.id }),
    });
    let ok = false;
    let error = "";
    let sceneId = String(scene.id || "");
    try {
      const j = await r.json();
      ok = !!(r.ok && j && j.ok !== false);
      error = String((j && (j.error || j.reason)) || "");
      sceneId = String((j && j.sceneId) || scene.id || "");
    } catch (_) {
      ok = !!r.ok;
      if (!ok) error = "play_failed";
    }
    if (ok) {
      state.espScenePlaying = true;
      state.espSceneId = String(scene.id || "");
      updateEspRunButtonUI();
      maybeResolveEspActionPending();
    }
    return { ok, error, sceneId };
  }

  async function stopPreview() {
    const scene = currentScene();
    stopLocalPreview();
    await fetch(API.previewStop, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneId: scene ? scene.id : "" }),
    });
  }

  async function stopOnEsp() {
    let ok = false;
    try {
      const r = await fetch(API.previewStop, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sceneId: "*" }),
      });
      try {
        const j = await r.json();
        ok = !!(r.ok && j && j.ok !== false);
      } catch (_) {
        ok = !!r.ok;
      }
    } catch (_) {
      ok = false;
    }
    if (ok) {
      state.espScenePlaying = false;
      state.espSceneId = "";
      updateEspRunButtonUI();
      maybeResolveEspActionPending();
    }
    return ok;
  }

  function clearEspActionPending() {
    state.espActionPending = false;
    state.espActionTargetPlaying = null;
    if (state.espActionTimeout) {
      window.clearTimeout(state.espActionTimeout);
      state.espActionTimeout = 0;
    }
    if (espRunBtn) {
      espRunBtn.disabled = false;
      espRunBtn.classList.remove("is-pending");
    }
    updateEspRunButtonUI();
  }

  function beginEspActionPending(targetPlaying) {
    clearEspActionPending();
    state.espActionPending = true;
    state.espActionTargetPlaying = !!targetPlaying;
    if (espRunBtn) {
      espRunBtn.disabled = true;
      espRunBtn.classList.add("is-pending");
    }
    updateEspRunButtonUI();
    scheduleEspScenePoll(120);
    state.espActionTimeout = window.setTimeout(() => {
      clearEspActionPending();
      pollEspSceneState();
    }, 5000);
  }

  function maybeResolveEspActionPending() {
    if (!state.espActionPending) return;
    if (state.espActionTargetPlaying === null) return;
    if (!!state.espScenePlaying === !!state.espActionTargetPlaying) {
      clearEspActionPending();
    }
  }

  function espUiWantsPlaying() {
    if (state.espActionPending && state.espActionTargetPlaying !== null) {
      return !!state.espActionTargetPlaying;
    }
    return !!state.espScenePlaying;
  }

  function currentEspPollMs() {
    if (state.espActionPending) return ESP_POLL_MS_PENDING;
    if (espUiWantsPlaying()) return ESP_POLL_MS_PLAYING;
    return ESP_POLL_MS_IDLE;
  }

  function scheduleEspScenePoll(delayMs) {
    if (state.espPollTimer) {
      window.clearTimeout(state.espPollTimer);
      state.espPollTimer = 0;
    }
    const wait = Number.isFinite(Number(delayMs))
      ? Math.max(80, Math.round(Number(delayMs)))
      : currentEspPollMs();
    state.espPollTimer = window.setTimeout(async () => {
      state.espPollTimer = 0;
      if (shouldPollEspSceneState()) {
        await pollEspSceneState();
      }
      scheduleEspScenePoll(currentEspPollMs());
    }, wait);
  }

  function updateEspRunButtonUI() {
    if (!espRunBtn) return;
    const isPlaying = espUiWantsPlaying();
    const pending = !!state.espActionPending;
    const blocked = !isPlaying && state.headlessMode && state.espConnected !== true;
    espRunBtn.classList.toggle("btn-outline-info", !isPlaying && !pending);
    espRunBtn.classList.toggle("btn-danger", isPlaying || pending);
    const icon = espRunBtn.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-play", !isPlaying);
      icon.classList.toggle("fa-stop", isPlaying);
      icon.classList.toggle("fa-microchip", false);
    }
    const label = pending
      ? (isPlaying ? "Starting scene on ESP..." : "Stopping scene on ESP...")
      : (blocked
        ? "Run unavailable: headless mode with ESP disconnected"
        : (isPlaying ? "Stop scene on ESP" : "Run selected scene on ESP"));
    const disabled = pending || blocked;
    espRunBtn.disabled = disabled;
    espRunBtn.setAttribute("aria-disabled", disabled ? "true" : "false");
    espRunBtn.title = label;
    espRunBtn.setAttribute("aria-label", label);
  }

  async function pollEspSceneState() {
    if (state.espPollInFlight) return;
    state.espPollInFlight = true;
    try {
      const r = await fetch(API.previewEspState, { method: "GET" });
      const j = await r.json();
      if (!r.ok || !j) return;
      state.espConnected = j.espConnected === true;
      state.headlessMode = j.headless === true;
      state.espScenePlaying = !!j.playing;
      state.espSceneId = String(j.sceneId || "");
      const prev = state.runtimeStatus && typeof state.runtimeStatus === "object" ? state.runtimeStatus : {};
      state.runtimeStatus = {
        ...prev,
        espConnected: state.espConnected,
        headless: state.headlessMode,
        scene: {
          ...(prev.scene || {}),
          activeScenes: Array.isArray(j.activeScenes) ? j.activeScenes : [],
          activeSceneCount: Number.isFinite(Number(j.activeSceneCount))
            ? Number(j.activeSceneCount)
            : (Array.isArray(j.activeScenes) ? j.activeScenes.length : 0),
          overridesActive: Number.isFinite(Number(j.overridesActive)) ? Number(j.overridesActive) : 0,
          playing: !!j.playing,
          sceneId: String(j.sceneId || ""),
          reason: String(j.reason || ""),
        },
      };
      updateRuntimeUi();
      updateEspRunButtonUI();
      updatePlayToggleUI();
      maybeResolveEspActionPending();
      scheduleEspScenePoll(currentEspPollMs());
    } catch (_) {
      // keep local UI state
    } finally {
      state.espPollInFlight = false;
    }
  }

  function runtimeTabActive() {
    return !!(runtimePane && runtimePane.classList.contains("active"));
  }

  function stageTabActive() {
    return !!(stagePane && stagePane.classList.contains("active"));
  }

  function shouldPollEspSceneState() {
    if (document.visibilityState !== "visible") return false;
    return stageTabActive() || runtimeTabActive();
  }

  function startEspScenePolling() {
    if (state.espPollTimer) return;
    scheduleEspScenePoll(150);
    if (!state.espVisibilityHandlerBound) {
      document.addEventListener("visibilitychange", () => {
        if (shouldPollEspSceneState()) {
          pollEspSceneState();
          scheduleEspScenePoll(150);
        }
      });
      state.espVisibilityHandlerBound = true;
    }
  }

  function updatePlayToggleUI() {
    if (!playToggleBtn) return;
    const isPlaying = !!state.playback;
    playToggleBtn.classList.add("btn-outline-light", "btn-sm", "media-icon-btn");
    const icon = playToggleBtn.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-play", !isPlaying);
      icon.classList.toggle("fa-stop", isPlaying);
    }
    const label = isPlaying ? "Stop" : "Play";
    playToggleBtn.title = label;
    playToggleBtn.setAttribute("aria-label", label);
  }

  function updateAllToggleUI() {
    if (!allToggleBtn) return;
    const icon = allToggleBtn.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-sun", !state.previewAllOn);
      icon.classList.toggle("fa-xmark", state.previewAllOn);
    }
    allToggleBtn.classList.toggle("btn-warning", !!state.previewAllOn);
    allToggleBtn.classList.toggle("btn-outline-light", !state.previewAllOn);
    const label = state.previewAllOn ? "Turn all lights off" : "Turn all lights on";
    allToggleBtn.title = label;
    allToggleBtn.setAttribute("aria-label", label);
  }

  function applyPreviewAllOverrideFx(fixture, fx) {
    if (!state.previewAllOn) return fx;
    if (!fixture) return { on: true, intensity: 1, brightness: 1, color: "#ffffff", scale: 1 };
    const fallbackColor = fixtureSupportsDynamicColor(fixture)
      ? "#ffffff"
      : normalizeHexColor(fixture.fixedColor, "#60a5fa");
    const keepColor = normalizeHexColor(fx?.color, fallbackColor);
    if (fixture.type === "rgb_strip") {
      const count = Math.max(1, Number(fixture.pixelCount || 1));
      const dotColors = Array.isArray(fx?.dotColors) && fx.dotColors.length
        ? Array.from({ length: count }, (_, i) => normalizeHexColor(fx.dotColors[i], keepColor))
        : Array.from({ length: count }, () => keepColor);
      return {
        on: true,
        scale: 1,
        color: keepColor,
        brightness: 1,
        dotOn: Array.from({ length: count }, () => true),
        dotColors,
        dotIntensity: Array.from({ length: count }, () => 1),
      };
    }
    return {
      ...(fx || {}),
      on: true,
      scale: 1,
      color: keepColor,
      intensity: 1,
      brightness: 1,
    };
  }

  async function onPreviewToggle() {
    if (state.playback) {
      await stopPreview();
      return;
    }
    await playSelected();
  }

  async function onEspRunClick() {
    if (state.espActionPending) return;
    if (!state.espScenePlaying && state.headlessMode && state.espConnected !== true) {
      await showInfoModal(
        "ESP Unavailable",
        "Run on ESP is unavailable while headless mode is active and the ESP is disconnected."
      );
      return;
    }
    if (state.espScenePlaying) {
      beginEspActionPending(false);
      await stopOnEsp();
      await pollEspSceneState();
      return;
    }
    let outOfSync = false;
    try {
      outOfSync = await loadSyncStatus();
    } catch (_) {
      outOfSync = false;
    }
    if (outOfSync) {
      await showInfoModal(
        "Lighting Out Of Sync",
        "Play on ESP is blocked while lighting is out of sync.",
        "Please use Sync Lighting first, then try Play on ESP again."
      );
      return;
    }
    beginEspActionPending(true);
    const play = await runSelectedOnEsp();
    if (!play.ok) {
      clearEspActionPending();
      const msg = describePlayEspError(play.error || "play_failed");
      await showInfoModal(msg.title, msg.message, msg.detail);
    }
    await pollEspSceneState();
  }

  function onPreviewAllToggle() {
    state.previewAllOn = !state.previewAllOn;
    updateAllToggleUI();
    renderPreview();
  }

  function addScene() {
    stopLocalPreview();
    const id = uuid();
    state.config.scenes.push({
      id,
      title: `Scene ${state.config.scenes.length + 1}`,
      duration: { value: 5, unit: "seconds" },
      endBehavior: "stop",
      priority: 0,
      blendMode: "overlay",
      castMask: "cast",
      pattern: "solid",
      cast: [],
      params: patternDefaultParams("solid"),
      timeline: [],
      markers: [],
    });
    setSelectedScene(id);
    panelState.editor = true;
    setPanelOpen("editor", true);
    savePanelState();
    markDirty();
    render();
  }

  function onSceneSelectChange() {
    const sceneId = String(sceneSelect?.value || "").trim();
    if (!sceneId || sceneId === String(state.selectedSceneId || "")) return;
    stopLocalPreview();
    setSelectedScene(sceneId);
    panelState.editor = true;
    setPanelOpen("editor", true);
    savePanelState();
    render();
  }

  async function loadState() {
    if (!state.patterns.length) await loadPatterns();
    const r = await fetch(API.state);
    const j = await r.json();
    if (!r.ok || !j.ok) {
      alert("Failed to load lighting state.");
      return;
    }
    state.config = j.config || { fixtures: {}, scenes: [] };
    if (!Array.isArray(state.config.scenes)) state.config.scenes = [];
    state.config.scenes.forEach((scene) => ensureScenePatternDefaults(scene));
    if (!state.config.ui || typeof state.config.ui !== "object") state.config.ui = {};
    state.showLayoutGuides = state.config.ui.showLayoutGuides !== false;
    state.config.ui.showLayoutGuides = state.showLayoutGuides;
    state.fixtures = j.fixtures || [];
    state.fixtures.forEach((f) => ensureFixtureVisualConfig(f));
    state.playfield = readPlayfield(j.playfield);
    state.layoutElements = Array.isArray(j.layoutElements) ? j.layoutElements : [];
    hydrateLayoutGuideColors();
    await pollEspSceneState();
    applyPreviewPlayfieldBackground();
    // Recompute previewRect now so overflow spacing math uses real stage size.
    updateLayoutViewportHeight();
    updatePreviewViewportHeight();
    updatePreviewSize();
    const size = previewSize();
    state.fixtures.forEach((f) => {
      if (f?.type === "rgb_strip" && String(f.layoutMode || "line") === "manual") {
        normalizeManualPointsForCount(f, size.width, size.height);
      }
    });
    stopLocalPreview();
    state.selectedPixel = null;
    state.customSelection = new Set();
    state.customSceneId = null;
    renderPixelInspector();
    scheduleLayoutPass();
    if (!state.selectedSceneId) setSelectedScene(state.config.scenes?.[0]?.id || null);
    if (state.selectedSceneId && !state.config.scenes.some((s) => s.id === state.selectedSceneId)) {
      setSelectedScene(state.config.scenes?.[0]?.id || null);
    }
    markDirty(false);
    render();
    scheduleCompiledPreview(20);
    loadSyncStatus().catch(() => {});
  }

  function render() {
    renderScenes();
    renderFixturesSidebar();
    renderSceneEditor();
    renderCustomTimelinePanel();
    renderPreview();
    renderPixelInspector();
  }

  function clearSelectedPixel() {
    if (!state.selectedPixel) return;
    state.selectedPixel = null;
    renderPixelInspector();
    renderPreview();
  }

  function selectPixel(fixtureId, pixelIndex) {
    const fixture = fixtureById(fixtureId);
    if (!fixture) return;
    const idx = Number(pixelIndex);
    const safeIndex = Number.isFinite(idx) && idx >= 0 ? Math.floor(idx) : 0;
    state.selectedPixel = { fixtureId, pixelIndex: safeIndex };
    renderPixelInspector();
    renderPreview();
  }

  function visualTargetsKey(target) {
    if (!target || !target.fixture) return "";
    if (target.scope === "pixel") return `${target.fixture.id}::${target.pixelIndex}`;
    return `${target.fixture.id}::all`;
  }

  function expandVisualTargets(rawTargets) {
    const out = [];
    const seen = new Set();
    (rawTargets || []).forEach((row) => {
      const fixture = row?.fixture || fixtureById(row?.fixtureId);
      if (!fixture) return;
      ensureFixtureVisualConfig(fixture);
      const wantsPixel = row?.scope === "pixel" || (Number.isFinite(Number(row?.pixelIndex)) && fixtureUsesPerPixelVisuals(fixture));
      const target = wantsPixel
        ? { fixture, scope: "pixel", pixelIndex: Math.max(0, Math.floor(Number(row.pixelIndex) || 0)) }
        : { fixture, scope: "fixture", pixelIndex: 0 };
      const key = visualTargetsKey(target);
      if (!key || seen.has(key)) return;
      seen.add(key);
      out.push(target);
    });
    return out;
  }

  function readTargetVisual(target) {
    if (!target || !target.fixture) return { shape: "circle", sizePx: 14, rotationDeg: 0 };
    if (target.scope === "pixel") {
      return visualConfigForDot(target.fixture, target.pixelIndex);
    }
    ensureFixtureVisualConfig(target.fixture);
    return {
      shape: normalizeMarkerShape(target.fixture.markerShape),
      sizePx: normalizeMarkerSizePx(target.fixture.markerSizePx, target.fixture),
      rotationDeg: normalizeMarkerRotationDeg(target.fixture.markerRotationDeg),
    };
  }

  function fixtureVisualSummary(targets) {
    const list = expandVisualTargets(targets);
    if (!list.length) {
      return { shape: "circle", sizePx: 14, rotationDeg: 0, shapeMixed: false, sizeMixed: false, rotationMixed: false, targets: [] };
    }
    const first = readTargetVisual(list[0]);
    let shapeMixed = false;
    let sizeMixed = false;
    let rotationMixed = false;
    for (let i = 1; i < list.length; i += 1) {
      const v = readTargetVisual(list[i]);
      if (v.shape !== first.shape) shapeMixed = true;
      if (Math.abs(Number(v.sizePx) - Number(first.sizePx)) > 0.01) sizeMixed = true;
      if (Math.abs(Number(v.rotationDeg) - Number(first.rotationDeg)) > 0.01) rotationMixed = true;
    }
    return {
      shape: first.shape,
      sizePx: first.sizePx,
      rotationDeg: first.rotationDeg,
      shapeMixed,
      sizeMixed,
      rotationMixed,
      targets: list,
    };
  }

  function renderPixelVisualControls(targets, opts = {}) {
    const summary = fixtureVisualSummary(targets);
    const mixedHint = opts.mixedHint ? `<div class="small text-secondary">${escapeHtml(opts.mixedHint)}</div>` : "";
    return `
      <div class="small text-secondary mt-2">Visual</div>
      ${mixedHint}
      <div class="lighting-grid mt-1 mb-0">
        <label>Shape</label>
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <select class="form-select form-select-sm" id="lighting-pixel-shape" style="max-width: 200px;">
            ${MARKER_SHAPES.map((shape) => `<option value="${shape}"${shape === summary.shape ? " selected" : ""}>${escapeHtml(camelLabel(shape, "Shape"))}</option>`).join("")}
          </select>
          ${summary.shapeMixed ? '<span class="small text-secondary">mixed</span>' : ""}
        </div>
      </div>
      <div class="lighting-grid mt-1 mb-0">
        <label>Size</label>
        <div class="d-flex align-items-center gap-2">
          <input class="form-range m-0" id="lighting-pixel-size" type="range" min="4" max="200" step="1" value="${Math.round(summary.sizePx)}">
          <span class="small text-secondary" id="lighting-pixel-size-value">${Math.round(summary.sizePx)} px</span>
          ${summary.sizeMixed ? '<span class="small text-secondary">mixed</span>' : ""}
        </div>
      </div>
      <div class="lighting-grid mt-1 mb-0">
        <label>Rotation</label>
        <div class="d-flex align-items-center gap-2">
          <input class="form-range m-0" id="lighting-pixel-rotation" type="range" min="-180" max="180" step="1" value="${Math.round(summary.rotationDeg)}">
          <span class="small text-secondary" id="lighting-pixel-rotation-value">${Math.round(summary.rotationDeg)}°</span>
          ${summary.rotationMixed ? '<span class="small text-secondary">mixed</span>' : ""}
        </div>
      </div>
    `;
  }

  function bindPixelVisualControls(targets) {
    const list = expandVisualTargets(targets);
    if (!list.length) return;
    const applyToAll = (fn) => {
      list.forEach((target) => {
        const fixture = target.fixture;
        ensureFixtureVisualConfig(fixture);
        if (target.scope === "pixel") {
          const row = ensurePointVisualAt(fixture, target.pixelIndex);
          fn(row, fixture, target);
          row.shape = normalizeMarkerShape(row.shape);
          row.sizePx = normalizeMarkerSizePx(row.sizePx, fixture);
          row.rotationDeg = normalizeMarkerRotationDeg(row.rotationDeg);
        } else {
          fn(fixture, fixture, target);
          fixture.markerShape = normalizeMarkerShape(fixture.markerShape);
          fixture.markerSizePx = normalizeMarkerSizePx(fixture.markerSizePx, fixture);
          fixture.markerRotationDeg = normalizeMarkerRotationDeg(fixture.markerRotationDeg);
        }
      });
      markDirty();
      renderPreview();
    };
    const shapeInput = pixelInfo.querySelector("#lighting-pixel-shape");
    const sizeInput = pixelInfo.querySelector("#lighting-pixel-size");
    const sizeValue = pixelInfo.querySelector("#lighting-pixel-size-value");
    const rotInput = pixelInfo.querySelector("#lighting-pixel-rotation");
    const rotValue = pixelInfo.querySelector("#lighting-pixel-rotation-value");

    shapeInput?.addEventListener("change", () => {
      const shape = normalizeMarkerShape(shapeInput.value);
      const isComplex = shape === "triangle" || shape === "hexagon" || shape === "star" || shape === "arrow";
      applyToAll((cfg, fixture) => {
        cfg.shape = shape;
        cfg.markerShape = shape;
        if (isComplex) {
          const nextSize = Math.max(18, normalizeMarkerSizePx(cfg.sizePx ?? cfg.markerSizePx, fixture));
          cfg.sizePx = nextSize;
          cfg.markerSizePx = nextSize;
        }
      });
      if (isComplex) {
        const sizeNow = Number(sizeInput?.value || 18);
        if (sizeInput && sizeNow < 18) sizeInput.value = "18";
        if (sizeValue) sizeValue.textContent = `${Math.max(18, sizeNow)} px`;
      }
    });
    const applySize = () => {
      const sizePx = normalizeMarkerSizePx(sizeInput.value, list[0]?.fixture);
      if (sizeValue) sizeValue.textContent = `${Math.round(sizePx)} px`;
      applyToAll((cfg) => { cfg.sizePx = sizePx; cfg.markerSizePx = sizePx; });
    };
    sizeInput?.addEventListener("input", applySize);
    sizeInput?.addEventListener("change", applySize);
    const applyRotation = () => {
      const deg = normalizeMarkerRotationDeg(rotInput.value);
      if (rotValue) rotValue.textContent = `${Math.round(deg)}°`;
      applyToAll((cfg) => { cfg.rotationDeg = deg; cfg.markerRotationDeg = deg; });
    };
    rotInput?.addEventListener("input", applyRotation);
    rotInput?.addEventListener("change", applyRotation);
  }

  function renderLineLayoutControls(fixture) {
    if (!fixture || fixture.type !== "rgb_strip" || String(fixture.layoutMode || "line") !== "line") return "";
    const size = previewSize();
    const geom = lineGeometry(fixture, size.width, size.height);
    const lengthPx = Math.max(1, Math.round(Number(fixture.lengthPx) || geom.lengthPx));
    const angleDeg = Math.round(geom.angleDeg);
    return `
      <div class="small text-secondary mt-2">Line Layout</div>
      <div class="lighting-grid mt-1 mb-0">
        <label>Length</label>
        <div class="d-flex align-items-center gap-2">
          <input class="form-control form-control-sm" id="lighting-line-length" type="number" min="1" step="1" value="${lengthPx}" style="max-width: 130px;">
          <span class="small text-secondary">px</span>
        </div>
      </div>
      <div class="lighting-grid mt-1 mb-0">
        <label>Angle</label>
        <div class="d-flex align-items-center gap-2">
          <input class="form-range m-0" id="lighting-line-angle" type="range" min="-180" max="180" step="1" value="${angleDeg}">
          <span class="small text-secondary" id="lighting-line-angle-value">${angleDeg}°</span>
        </div>
      </div>
    `;
  }

  function bindLineLayoutControls(fixture) {
    if (!fixture || fixture.type !== "rgb_strip" || String(fixture.layoutMode || "line") !== "line") return;
    const lenInput = pixelInfo.querySelector("#lighting-line-length");
    const angleInput = pixelInfo.querySelector("#lighting-line-angle");
    const angleValue = pixelInfo.querySelector("#lighting-line-angle-value");
    const applyLength = () => {
      const size = previewSize();
      const next = Number(lenInput?.value || 1);
      if (!Number.isFinite(next) || next < 1) return;
      setLineLengthPx(fixture, size.width, size.height, next);
      markDirty();
      renderPreview();
    };
    lenInput?.addEventListener("input", applyLength);
    lenInput?.addEventListener("change", applyLength);
    const applyAngle = () => {
      const size = previewSize();
      const deg = Number(angleInput?.value || 0);
      if (!Number.isFinite(deg)) return;
      if (angleValue) angleValue.textContent = `${Math.round(deg)}°`;
      setLineAngleDeg(fixture, size.width, size.height, deg);
      markDirty();
      renderPreview();
    };
    angleInput?.addEventListener("input", applyAngle);
    angleInput?.addEventListener("change", applyAngle);
  }

  function renderPixelInspector() {
    if (!pixelCard || !pixelInfo) return;
    const scene = currentScene();
    if (isCustomScene(scene) && state.customSelection.size) {
      const tMs = currentCustomTimeMs(scene);
      const durationMs = sceneDurationMs(scene);
      const targets = Array.from(state.customSelection)
        .map(parsePixelTargetKey)
        .filter(Boolean)
        .map((t) => ({ ...t, fixture: fixtureById(t.fixtureId) }))
        .filter((t) => !!t.fixture);
      if (!targets.length) {
        pixelCard.classList.add("d-none");
        pixelInfo.innerHTML = "";
        return;
      }
      const states = targets.map((target) => {
        const fixture = target.fixture;
        const fallback = fixtureSupportsDynamicColor(fixture)
          ? "#ffffff"
          : normalizeHexColor(fixture.fixedColor, "#60a5fa");
        const fx = compiledFrameFx(scene, fixture, tMs, scene.endBehavior || "stop", durationMs);
        if (!fx) return { on: false, color: fallback, brightness: 1 };
        if (fixture.type === "rgb_strip") {
          const idx = Math.max(0, Math.floor(Number(target.pixelIndex) || 0));
          const on = Array.isArray(fx.dotOn) ? !!fx.dotOn[idx] : !!fx.on;
          const color = fixtureSupportsDynamicColor(fixture)
            ? (Array.isArray(fx.dotColors) ? normalizeHexColor(fx.dotColors[idx], fallback) : normalizeHexColor(fx.color, fallback))
            : normalizeHexColor(fixture.fixedColor, "#60a5fa");
          const bRaw = Array.isArray(fx.dotIntensity) ? Number(fx.dotIntensity[idx]) : Number(fx.intensity);
          const b = Number.isFinite(bRaw) ? Math.max(0, Math.min(1, bRaw)) : (on ? 1 : 0);
          return { on, color, brightness: b };
        }
        const on = !!fx.on;
        const color = fixtureSupportsDynamicColor(fixture)
          ? normalizeHexColor(fx.color, fallback)
          : normalizeHexColor(fixture.fixedColor, "#60a5fa");
        const bRaw = Number(fx.intensity);
        const b = Number.isFinite(bRaw) ? Math.max(0, Math.min(1, bRaw)) : (on ? 1 : 0);
        return { on, color, brightness: b };
      });
      const selectedCount = targets.length;
      const visualTargets = expandVisualTargets(
        targets.map((t) => ({
          fixture: t.fixture,
          pixelIndex: t.pixelIndex,
          scope: fixtureUsesPerPixelVisuals(t.fixture) ? "pixel" : "fixture",
        }))
      );
      const onCount = states.filter((s) => s.on).length;
      const stateLabel = onCount === 0 ? "OFF" : (onCount === selectedCount ? "ON" : "Mixed");
      const onColors = states.filter((s) => s.on).map((s) => normalizeHexColor(s.color, "#ffffff"));
      const firstColor = onColors[0] || "#ffffff";
      const colorMixed = onColors.some((c) => c !== firstColor);
      const onBrightness = states.filter((s) => s.on).map((s) => Number(s.brightness ?? 1));
      const firstBrightness = onBrightness.length ? Math.max(0, Math.min(1, onBrightness[0])) : 1;
      const brightnessMixed = onBrightness.some((b) => Math.abs(Number(b) - firstBrightness) > 0.001);
      pixelCard.classList.remove("d-none");
      pixelInfo.innerHTML = `
        <div class="d-flex align-items-center justify-content-between gap-2">
          <div class="fw-semibold">${selectedCount} pixel${selectedCount === 1 ? "" : "s"} selected</div>
          <div class="small text-secondary">${Math.round(tMs)} ms</div>
        </div>
        <div class="small text-secondary mt-2">Current</div>
        <div class="fw-semibold">${stateLabel}${colorMixed ? " · Mixed colours" : ` · ${firstColor}`}${brightnessMixed ? " · Mixed brightness" : ` · ${Math.round(firstBrightness * 100)}%`}</div>
        <div class="d-flex align-items-center gap-2 mt-2">
          <label class="small text-secondary m-0">Brightness</label>
          <input class="form-range m-0" id="lighting-pixel-brightness" type="range" min="0" max="1" step="0.05" value="${firstBrightness}">
          <span class="small text-secondary" id="lighting-pixel-brightness-value">${Math.round(firstBrightness * 100)}%</span>
        </div>
        <div class="d-flex align-items-center gap-2 mt-3 flex-wrap">
          <input class="form-control form-control-color form-control-sm" id="lighting-pixel-custom-color" type="color" value="${escapeHtml(firstColor)}" title="Apply colour">
          <button class="btn btn-success btn-sm" type="button" id="lighting-pixel-apply-on">Apply ON</button>
          <button class="btn btn-outline-secondary btn-sm" type="button" id="lighting-pixel-apply-off">Apply OFF</button>
        </div>
        ${renderPixelVisualControls(visualTargets, { mixedHint: "Manual layout: selected pixel(s). Line layout: whole strip." })}
      `;
      const brightnessInput = pixelInfo.querySelector("#lighting-pixel-brightness");
      const brightnessValue = pixelInfo.querySelector("#lighting-pixel-brightness-value");
      brightnessInput?.addEventListener("input", () => {
        const b = Math.max(0, Math.min(1, Number(brightnessInput.value || 0)));
        if (brightnessValue) brightnessValue.textContent = `${Math.round(b * 100)}%`;
        const color = pixelInfo.querySelector("#lighting-pixel-custom-color")?.value || firstColor;
        const liveOn = onCount > 0;
        applyCustomToSelection(scene, liveOn, color, b, { refreshInspector: false });
      });
      pixelInfo.querySelector("#lighting-pixel-apply-on")?.addEventListener("click", () => {
        const color = pixelInfo.querySelector("#lighting-pixel-custom-color")?.value || firstColor;
        const b = Number(pixelInfo.querySelector("#lighting-pixel-brightness")?.value || firstBrightness);
        applyCustomToSelection(scene, true, color, b);
      });
      pixelInfo.querySelector("#lighting-pixel-apply-off")?.addEventListener("click", () => {
        const color = pixelInfo.querySelector("#lighting-pixel-custom-color")?.value || firstColor;
        applyCustomToSelection(scene, false, color, 0);
      });
      const colorInput = pixelInfo.querySelector("#lighting-pixel-custom-color");
      colorInput?.addEventListener("change", () => {
        const color = colorInput.value || firstColor;
        const b = Number(pixelInfo.querySelector("#lighting-pixel-brightness")?.value || firstBrightness);
        applyCustomToSelection(scene, true, color, b);
      });
      bindPixelVisualControls(visualTargets);
      return;
    }
    if (isCustomScene(scene)) {
      pixelCard.classList.add("d-none");
      pixelInfo.innerHTML = "";
      return;
    }
    if (state.customSelection.size) {
      const targets = Array.from(state.customSelection)
        .map(parsePixelTargetKey)
        .filter(Boolean)
        .map((t) => ({ ...t, fixture: fixtureById(t.fixtureId) }))
        .filter((t) => !!t.fixture);
      if (!targets.length) {
        pixelCard.classList.add("d-none");
        pixelInfo.innerHTML = "";
        return;
      }
      const visualTargets = expandVisualTargets(
        targets.map((t) => ({
          fixture: t.fixture,
          pixelIndex: t.pixelIndex,
          scope: fixtureUsesPerPixelVisuals(t.fixture) ? "pixel" : "fixture",
        }))
      );
      const selectedCount = targets.length;
      pixelCard.classList.remove("d-none");
      pixelInfo.innerHTML = `
        <div class="d-flex align-items-center justify-content-between gap-2">
          <div class="fw-semibold">${selectedCount} pixel${selectedCount === 1 ? "" : "s"} selected</div>
        </div>
        ${renderPixelVisualControls(visualTargets, { mixedHint: "Batch edit for selected items." })}
      `;
      bindPixelVisualControls(visualTargets);
      return;
    }
    const sel = state.selectedPixel;
    if (!sel) {
      pixelCard.classList.add("d-none");
      pixelInfo.innerHTML = "";
      return;
    }
    const fixture = fixtureById(sel.fixtureId);
    if (!fixture) {
      pixelCard.classList.add("d-none");
      pixelInfo.innerHTML = "";
      return;
    }
    pixelCard.classList.remove("d-none");
    const idx = fixture.type === "rgb_strip" ? sel.pixelIndex : 0;
    const singleTarget = fixtureUsesPerPixelVisuals(fixture)
      ? [{ fixture, pixelIndex: idx, scope: "pixel" }]
      : [{ fixture, scope: "fixture" }];
    pixelInfo.innerHTML = `
      <div class="small text-secondary mb-1">Fixture</div>
      <div class="fw-semibold">${escapeHtml(fixture.title || fixture.id)}</div>
      <div class="small text-secondary mb-1 mt-2">Index</div>
      <div class="fw-semibold">${idx}</div>
      <div class="small text-secondary mt-2">${escapeHtml(fixture.id)}</div>
      ${renderPixelVisualControls(singleTarget, { mixedHint: fixtureUsesPerPixelVisuals(fixture) ? "Manual layout: this pixel only." : "Line layout: applies to whole strip." })}
      ${renderLineLayoutControls(fixture)}
    `;
    bindPixelVisualControls(singleTarget);
    bindLineLayoutControls(fixture);
  }

  function onPreviewClick(e) {
    e.stopPropagation();
    if (state.suppressClick) return;
    const isShift = !!e.shiftKey;
    const scene = currentScene();
    if (isCustomScene(scene)) {
      const stripDot = e.target.closest(".lighting-fixture-strip-dot");
      if (stripDot) {
        const fixtureNode = stripDot.closest(".lighting-fixture");
        const fixtureId = fixtureNode?.dataset.id;
        if (!fixtureId) return;
        const idx = Number(stripDot.dataset.pixelIndex || 0);
        const key = pixelTargetKey(fixtureId, idx);
        if (state.customSelection.has(key)) state.customSelection.delete(key);
        else state.customSelection.add(key);
        syncCustomSelectionFocus();
        renderCustomTimelinePanel();
        renderPixelInspector();
        renderPreview();
        return;
      }
      const singleDot = e.target.closest(".lighting-fixture-dot");
      if (singleDot) {
        const fixtureNode = singleDot.closest(".lighting-fixture");
        const fixtureId = fixtureNode?.dataset.id;
        if (!fixtureId) return;
        const key = pixelTargetKey(fixtureId, 0);
        if (state.customSelection.has(key)) state.customSelection.delete(key);
        else state.customSelection.add(key);
        syncCustomSelectionFocus();
        renderCustomTimelinePanel();
        renderPixelInspector();
        renderPreview();
        return;
      }
      state.customSelection.clear();
      clearSelectedPixel();
      renderCustomTimelinePanel();
      renderPixelInspector();
      renderPreview();
      return;
    }
    const stripDot = e.target.closest(".lighting-fixture-strip-dot");
    if (stripDot) {
      const fixtureNode = stripDot.closest(".lighting-fixture");
      const fixtureId = fixtureNode?.dataset.id;
      if (!fixtureId) return;
      const idx = Number(stripDot.dataset.pixelIndex || 0);
      if (isShift) {
        const key = pixelTargetKey(fixtureId, idx);
        if (state.customSelection.has(key)) state.customSelection.delete(key);
        else state.customSelection.add(key);
        syncCustomSelectionFocus();
        renderPixelInspector();
        renderPreview();
        return;
      }
      state.customSelection.clear();
      selectPixel(fixtureId, idx);
      return;
    }
    const singleDot = e.target.closest(".lighting-fixture-dot");
    if (singleDot) {
      const fixtureNode = singleDot.closest(".lighting-fixture");
      const fixtureId = fixtureNode?.dataset.id;
      if (!fixtureId) return;
      if (isShift) {
        const key = pixelTargetKey(fixtureId, 0);
        if (state.customSelection.has(key)) state.customSelection.delete(key);
        else state.customSelection.add(key);
        syncCustomSelectionFocus();
        renderPixelInspector();
        renderPreview();
        return;
      }
      state.customSelection.clear();
      selectPixel(fixtureId, 0);
      return;
    }
    state.customSelection.clear();
    clearSelectedPixel();
  }

  function onPreviewWrapClick(e) {
    if (state.suppressClick) return;
    const tableEl = previewTable;
    if (!tableEl) return;
    if (e.target && tableEl.contains(e.target)) return;
    const scene = currentScene();
    const hadMulti = state.customSelection.size > 0;
    state.customSelection.clear();
    clearSelectedPixel();
    if (isCustomScene(scene) && hadMulti) {
      renderCustomTimelinePanel();
    }
    renderPixelInspector();
    renderPreview();
  }

  function escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeHexColor(input, fallback = "#60a5fa") {
    const raw = String(input || "").trim();
    if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
    return fallback;
  }

  function hexToRgba(hex, alpha) {
    const c = normalizeHexColor(hex, "#60a5fa");
    const r = parseInt(c.slice(1, 3), 16);
    const g = parseInt(c.slice(3, 5), 16);
    const b = parseInt(c.slice(5, 7), 16);
    const a = Number.isFinite(alpha) ? Math.max(0, Math.min(1, alpha)) : 1;
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  function resolvedOffBorderColor() {
    const root = pageRoot || document.getElementById("lighting-page") || document.documentElement;
    const value = getComputedStyle(root).getPropertyValue("--lighting-dot-off-border").trim();
    return value || "#64748b";
  }

  function ensureDotShapeNode(dot, shape) {
    if (!dot) return null;
    const s = normalizeMarkerShape(shape);
    let svg = dot.querySelector(".lighting-shape-svg");
    if (!svg) {
      svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 100 100");
      svg.setAttribute("aria-hidden", "true");
      svg.classList.add("lighting-shape-svg");
      dot.appendChild(svg);
    }
    const wantedTag = (s === "triangle" || s === "hexagon" || s === "star" || s === "arrow") ? "polygon"
      : (s === "circle" ? "circle" : "rect");
    let node = svg.querySelector(".lighting-shape-node");
    if (!node || node.tagName.toLowerCase() !== wantedTag) {
      svg.innerHTML = "";
      node = document.createElementNS("http://www.w3.org/2000/svg", wantedTag);
      node.classList.add("lighting-shape-node");
      svg.appendChild(node);
    }
    if (wantedTag === "circle") {
      node.setAttribute("cx", "50");
      node.setAttribute("cy", "50");
      node.setAttribute("r", "42");
    } else if (wantedTag === "rect") {
      if (s === "rectangle") {
        node.setAttribute("x", "8");
        node.setAttribute("y", "27");
        node.setAttribute("width", "84");
        node.setAttribute("height", "46");
        node.setAttribute("rx", "3");
      } else if (s === "pill") {
        node.setAttribute("x", "8");
        node.setAttribute("y", "27");
        node.setAttribute("width", "84");
        node.setAttribute("height", "46");
        node.setAttribute("rx", "23");
      } else { // square
        node.setAttribute("x", "12");
        node.setAttribute("y", "12");
        node.setAttribute("width", "76");
        node.setAttribute("height", "76");
        node.setAttribute("rx", "3");
      }
    } else {
      if (s === "triangle") node.setAttribute("points", "50,6 8,92 92,92");
      else if (s === "hexagon") node.setAttribute("points", "25,8 75,8 96,50 75,92 25,92 4,50");
      else if (s === "star") node.setAttribute("points", "50,4 61,35 95,35 68,54 79,88 50,68 21,88 32,54 5,35 39,35");
      else node.setAttribute("points", "6,33 58,33 58,14 96,50 58,86 58,67 6,67"); // arrow
    }
    node.setAttribute("vector-effect", "non-scaling-stroke");
    return node;
  }

  function applyDotGeometry(dot, fixture, pixelIndex = 0) {
    if (!dot || !fixture) return;
    const preview = previewSize();
    const vs = previewDesignScale(preview.width, preview.height);
    const cfg = visualConfigForDot(fixture, pixelIndex);
    const shape = cfg.shape;
    dot.dataset.markerShape = shape;
    const isComplex = shape === "triangle" || shape === "hexagon" || shape === "star" || shape === "arrow";
    const size = Math.max(cfg.sizePx * vs, (isComplex ? 18 : 4) * vs);
    const rotation = cfg.rotationDeg;
    const isStrip = dot.classList.contains("lighting-fixture-strip-dot");
    const isWide = shape === "rectangle" || shape === "pill";
    const width = isWide ? Math.round(size * 1.65) : size;
    const height = isWide ? Math.round(size * 0.72) : size;
    dot.style.width = `${Math.max(2, width)}px`;
    dot.style.height = `${Math.max(2, height)}px`;
    dot.classList.toggle("is-complex-shape", isComplex);
    if (isComplex) {
      dot.style.borderRadius = "0";
      ensureDotShapeNode(dot, shape);
    } else {
      dot.style.borderRadius = shape === "circle" || shape === "pill" ? "999px" : "2px";
      const svg = dot.querySelector(".lighting-shape-svg");
      if (svg) svg.remove();
    }
    dot.style.setProperty("clip-path", "none");
    dot.style.setProperty("-webkit-clip-path", "none");
    dot.style.transform = isStrip ? `translate(-50%, -50%) rotate(${rotation}deg)` : `rotate(${rotation}deg)`;
  }

  function setFixtureVisual(node, fixture, fx) {
    if (!node || !fixture) return;
    const isPlaying = !!state.playback;
    const isOn = !!fx?.on;
    const brightnessRaw = Number(fx?.brightness);
    const brightness = Number.isFinite(brightnessRaw) ? Math.max(0, Math.min(1, brightnessRaw)) : 1;
    const intensityRaw = Number(fx?.intensity);
    const intensityBase = Number.isFinite(intensityRaw) ? Math.max(0, Math.min(1, intensityRaw)) : (isOn ? 1 : 0);
    const intensity = intensityBase * brightness;
    let scale = Number.isFinite(fx?.scale) ? fx.scale : 1;
    if (fixture.type === "rgb_strip") scale = 1;
    if (fixture.layoutMode === "manual") scale = 1;
    node.style.transform = `translate(-50%, -50%) scale(${scale})`;
    node.style.opacity = String(0.6 + intensity * 0.4);
    if (fixture.type === "rgb_strip") {
      const dots = Array.from(node.querySelectorAll(".lighting-fixture-strip-dot"));
      const baseColor = normalizeHexColor(fx?.color || "#f59e0b", "#f59e0b");
      dots.forEach((dot, idx) => {
        applyDotGeometry(dot, fixture, idx);
        const active = Array.isArray(fx?.dotOn) ? !!fx.dotOn[idx] : isOn;
        const color = Array.isArray(fx?.dotColors) ? normalizeHexColor(fx.dotColors[idx], baseColor) : baseColor;
        const dotIraw = Array.isArray(fx?.dotIntensity) ? Number(fx.dotIntensity[idx]) : intensityBase;
        const dotIbase = Number.isFinite(dotIraw) ? Math.max(0, Math.min(1, dotIraw)) : (active ? 1 : 0);
        const dotIntensity = dotIbase * brightness;
        const isComplex = dot.classList.contains("is-complex-shape");
        if (isComplex) {
          dot.style.backgroundColor = "transparent";
          dot.style.borderColor = "transparent";
          dot.style.boxShadow = "none";
          const shapeNode = dot.querySelector(".lighting-shape-node");
          if (shapeNode) {
            const fillAlpha = active ? (0.22 + dotIntensity * 0.78) : 0.26;
            shapeNode.style.fill = hexToRgba(color, fillAlpha);
            if (isPlaying) {
              shapeNode.style.stroke = "transparent";
            } else {
              const strokeAlpha = active ? (0.38 + dotIntensity * 0.62) : 0.34;
              shapeNode.style.stroke = `rgba(255,255,255,${strokeAlpha.toFixed(3)})`;
            }
          }
          const svg = dot.querySelector(".lighting-shape-svg");
          if (svg) {
            svg.style.filter = active
              ? `drop-shadow(0 0 ${Math.round(3 + dotIntensity * 8)}px ${hexToRgba(color, 0.45 + dotIntensity * 0.45)})`
              : "none";
          }
        } else {
          dot.style.backgroundColor = active ? hexToRgba(color, 0.22 + dotIntensity * 0.78) : hexToRgba(color, 0.26);
          dot.style.borderColor = isPlaying
            ? "transparent"
            : (active ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.50)");
          dot.style.boxShadow = active
            ? `0 0 ${Math.round(4 + dotIntensity * 10)}px ${hexToRgba(color, 0.5 + dotIntensity * 0.45)}`
            : "none";
        }
      });
      return;
    }
    const dot = node.querySelector(".lighting-fixture-dot");
    if (!dot) return;
    applyDotGeometry(dot, fixture, 0);
    const color = fixtureSupportsDynamicColor(fixture)
      ? normalizeHexColor(fx?.color || fixture.fixedColor, "#ffffff")
      : normalizeHexColor(fixture.fixedColor, "#60a5fa");
    const isComplex = dot.classList.contains("is-complex-shape");
    if (isComplex) {
      dot.style.backgroundColor = "transparent";
      dot.style.borderColor = "transparent";
      dot.style.boxShadow = "none";
      const shapeNode = dot.querySelector(".lighting-shape-node");
      if (shapeNode) {
        const fillAlpha = isOn ? (0.22 + intensity * 0.78) : 0.26;
        shapeNode.style.fill = hexToRgba(color, fillAlpha);
        if (isPlaying) {
          shapeNode.style.stroke = "transparent";
        } else {
          const strokeAlpha = isOn ? (0.38 + intensity * 0.62) : 0.34;
          shapeNode.style.stroke = `rgba(255,255,255,${strokeAlpha.toFixed(3)})`;
        }
      }
      const svg = dot.querySelector(".lighting-shape-svg");
      if (svg) {
        svg.style.filter = isOn
          ? `drop-shadow(0 0 ${Math.round(3 + intensity * 8)}px ${hexToRgba(color, 0.45 + intensity * 0.45)})`
          : "none";
      }
    } else {
      dot.style.backgroundColor = isOn ? hexToRgba(color, 0.22 + intensity * 0.78) : hexToRgba(color, 0.26);
      dot.style.borderColor = isPlaying
        ? "transparent"
        : (isOn ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.50)");
      dot.style.boxShadow = isOn
        ? `0 0 ${Math.round(4 + intensity * 10)}px ${hexToRgba(color, 0.5 + intensity * 0.45)}`
        : "none";
    }
  }

  function stripLabelPosition(dx, dy) {
    const ax = Math.abs(Number(dx) || 0);
    const ay = Math.abs(Number(dy) || 0);
    if (ax >= ay * 1.2) return "top";
    return "left";
  }

  addSceneBtn?.addEventListener("click", addScene);
  sceneSelect?.addEventListener("change", onSceneSelectChange);
  saveBtn?.addEventListener("click", save);
  syncBtn?.addEventListener("click", syncLighting);
  allToggleBtn?.addEventListener("click", onPreviewAllToggle);
  playToggleBtn?.addEventListener("click", onPreviewToggle);
  espRunBtn?.addEventListener("click", onEspRunClick);
  markerModalEl?.querySelector("#lighting-marker-modal-save")?.addEventListener("click", () => commitMarkerModal(true));
  markerModalEl?.querySelector("#lighting-marker-modal-remove")?.addEventListener("click", () => commitMarkerModal(false));
  markerModalEl?.querySelector("#lighting-marker-modal-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitMarkerModal(true);
    }
  });
  markerModalEl?.addEventListener("hidden.bs.modal", () => {
    state.markerModalCtx = null;
  });
  castModalEl?.querySelector("#lighting-cast-search")?.addEventListener("input", (e) => {
    state.castSearch = e.target.value || "";
    renderCastModalList();
  });
  castModalEl?.querySelector("#lighting-cast-filter-all")?.addEventListener("click", () => setCastFilter("all"));
  castModalEl?.querySelector("#lighting-cast-filter-strips")?.addEventListener("click", () => setCastFilter("strips"));
  castModalEl?.querySelector("#lighting-cast-filter-singles")?.addEventListener("click", () => setCastFilter("singles"));
  castModalEl?.querySelector("#lighting-cast-select-all")?.addEventListener("click", () => {
    const scene = currentCastModalScene();
    if (!scene) return;
    setSceneCastIds(scene, state.fixtures.map((f) => f.id));
    markDirty();
    updateSceneCastSummary(scene);
    renderPreview();
    renderCastModalList();
  });
  castModalEl?.querySelector("#lighting-cast-clear-all")?.addEventListener("click", () => {
    const scene = currentCastModalScene();
    if (!scene) return;
    setSceneCastIds(scene, []);
    markDirty();
    updateSceneCastSummary(scene);
    renderPreview();
    renderCastModalList();
  });

  document.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#lighting-tab-"]').forEach((btn) => {
    btn.addEventListener("shown.bs.tab", () => {
      scheduleLayoutPass();
      if (stageTabActive() || runtimeTabActive()) {
        pollEspSceneState();
      }
    });
  });
  castModalEl?.addEventListener("hidden.bs.modal", () => {
    state.castModalCtx = null;
  });
  document.addEventListener("keydown", onGlobalTimelineKeydown);
  previewTable.addEventListener("pointerdown", onPreviewMouseDown);
  previewTable.addEventListener("click", onPreviewClick);
  previewWrap.addEventListener("click", onPreviewWrapClick);
  window.addEventListener("pointermove", onMouseMove);
  window.addEventListener("pointerup", onMouseUp);
  window.addEventListener("resize", () => {
    scheduleLayoutPass();
  });
  loadPanelState();
  loadSelectedScene();
  scheduleLayoutPass();
  initPanelToggles();
  updatePlayToggleUI();
  updateAllToggleUI();
  updateEspRunButtonUI();
  startEspScenePolling();
  updateRuntimeUi();

  loadState().catch((err) => {
    console.error(err);
  });
})();
