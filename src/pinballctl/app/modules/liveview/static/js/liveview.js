(function () {
  document.body.classList.add("emu-page");
  const root = document.getElementById("liveview-page");
  const tableEl = document.getElementById("emu-table");
  const systemEventsEl = document.getElementById("liveview-system-events");
  const sceneTriggerEl = document.getElementById("liveview-scene-trigger");
  const stagePane = document.getElementById("liveview-stage-pane");
  const optionsScroll = document.querySelector(".liveview-options-scroll");
  const appFooter = document.querySelector("footer.footer");
  if (!root || !tableEl) return;

  const COMPACT_LAYOUT_MEDIA = "(max-width: 1200px)";
  const COMPACT_BASE_TABLE_WIDTH_PX = 560;
  const COMPACT_BASE_TABLE_HEIGHT_PX = 1120;
  const LIVEVIEW_SCALE_FACTOR = 0.94;
  const LIGHTING_PREVIEW_PAD_PX = 45;
  const LIGHTING_FRAME_MS = 500;
  const LIVEVIEW_SYSTEM_EVENTS_COLLAPSED_KEY = "pinballctl.liveview.systemEventsCollapsed.v1";
  const LIVEVIEW_SCENE_TRIGGER_COLLAPSED_KEY = "pinballctl.liveview.sceneTriggerCollapsed.v1";

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
    canonicalIdByTail: {},
    canonicalIds: new Set(),
    ruleTriggersBySource: {},
    ruleTriggersByTargetGesture: {},
    ruleActionsBySourceGesture: {},
    ruleActionsBySourceEvent: {},
    flipperHeldById: Object.create(null),
    eventSeqByKey: Object.create(null),
    mediaDisplays: [],
    mediaScenes: [],
    selectedMediaSceneId: "",
    selectedMediaRuntimeId: "",
    selectedMediaLaunchMode: "fullscreen",
    lightingFixtures: [],
    lightingCompiledScenesById: {},
    lightingScenesById: {},
    activeLightingScenes: {},
    lightingLedHardwareOnById: {},
    lightingPixelOverridesByFixtureId: {},
    lightingTickTimer: null,
    lcdTextByTarget: {},
    systemEventCategories: {},
    selectedSystemEvent: "",
    lastSystemEventStatus: "",
    lastSystemEventStatusType: "",
    systemEventsCollapsed: true,
    sceneTriggerCollapsed: false,
    sceneTriggerStatus: "",
    sceneTriggerStatusType: "",
    contextMenu: {
      root: null,
      targetId: "",
    },
  };

  function setStatus(text) {
    void text;
  }

  function loadSystemEventsCollapsedState() {
    try {
      const raw = window.localStorage.getItem(LIVEVIEW_SYSTEM_EVENTS_COLLAPSED_KEY);
      if (raw == null) {
        state.systemEventsCollapsed = true;
        return;
      }
      const normalized = String(raw).trim().toLowerCase();
      state.systemEventsCollapsed = !(normalized === "0" || normalized === "false" || normalized === "off");
    } catch (_) {
      state.systemEventsCollapsed = true;
    }
  }

  function saveSystemEventsCollapsedState() {
    try {
      window.localStorage.setItem(
        LIVEVIEW_SYSTEM_EVENTS_COLLAPSED_KEY,
        state.systemEventsCollapsed ? "1" : "0",
      );
    } catch (_) {
      // ignore storage restrictions
    }
  }

  function loadSceneTriggerCollapsedState() {
    try {
      const raw = window.localStorage.getItem(LIVEVIEW_SCENE_TRIGGER_COLLAPSED_KEY);
      if (raw == null) {
        state.sceneTriggerCollapsed = false;
        return;
      }
      const normalized = String(raw).trim().toLowerCase();
      state.sceneTriggerCollapsed = normalized === "1" || normalized === "true" || normalized === "on";
    } catch (_) {
      state.sceneTriggerCollapsed = false;
    }
  }

  function saveSceneTriggerCollapsedState() {
    try {
      window.localStorage.setItem(
        LIVEVIEW_SCENE_TRIGGER_COLLAPSED_KEY,
        state.sceneTriggerCollapsed ? "1" : "0",
      );
    } catch (_) {
      // ignore storage restrictions
    }
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
    const source = canonicalHardwareId(String(el?.hardwareId || el?.id || "").trim());
    if (!source) return [];
    const out = new Set();
    const bySource = state.ruleTriggersBySource[source];
    if (bySource && typeof bySource === "object") {
      Object.keys(bySource)
        .map((g) => String(g || "").trim().toUpperCase())
        .filter((g) => !!g && bySource[g] && bySource[g].name)
        .forEach((g) => out.add(g));
    }
    Object.keys(state.ruleTriggersByTargetGesture || {}).forEach((k) => {
      const sep = k.indexOf("|");
      if (sep < 0) return;
      const target = k.slice(0, sep);
      const gesture = k.slice(sep + 1);
      if (!gesture) return;
      if (target === source || uidTail(target) === uidTail(source)) out.add(String(gesture).toUpperCase());
    });
    return Array.from(out).sort((a, b) => gestureSortKey(a) - gestureSortKey(b));
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
    const source = canonicalHardwareId(String(el.hardwareId || el.id || "").trim());
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
      btn.addEventListener("click", async () => {
        const targetId = String(btn.getAttribute("data-target-id") || "").trim();
        const gesture = String(btn.getAttribute("data-gesture") || "").trim().toUpperCase();
        closeContextMenu();
        if (!targetId || !gesture) return;
        if (gesture === "PRESSED_AND_RELEASED") {
          fireBoundEventById(targetId, "PRESSED");
          setTimeout(() => fireBoundEventById(targetId, "RELEASED"), 110);
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

  function uidTail(uid) {
    const parts = String(uid || "").split("__");
    if (parts.length < 4) return String(uid || "").trim();
    return parts.slice(-3).join("__");
  }

  function uidTailNorm(uid) {
    return uidTail(uid).trim().toLowerCase();
  }

  function canonicalHardwareId(rawId) {
    const src = String(rawId || "").trim();
    if (!src) return "";
    if (state.canonicalIds.has(src)) return src;
    return state.canonicalIdByTail[uidTailNorm(src)] || src;
  }

  function normalizeLiveviewHardwareRefs() {
    state.elements.forEach((el) => {
      if (!el || typeof el !== "object") return;
      const hid = String(el.hardwareId || "").trim();
      if (!hid) return;
      const mapped = canonicalHardwareId(hid);
      if (mapped) el.hardwareId = mapped;
    });
  }

  function clampWithLightingPad(value, axisPx, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    const span = Math.max(1, Number(axisPx) || 1);
    const padNorm = LIGHTING_PREVIEW_PAD_PX / span;
    const min = -padNorm;
    const max = 1 + padNorm;
    if (n < min) return min;
    if (n > max) return max;
    return n;
  }

  function mediaDisplayTitle(target, index) {
    const role = String(target?.role || "").trim();
    if (role) return role;
    const name = String(target?.name || "").trim();
    if (name) return name;
    const id = String(target?.id || "").trim();
    if (id) return id;
    return `Display ${index + 1}`;
  }

  function sceneTriggerStatusClass() {
    const kind = String(state.sceneTriggerStatusType || "").trim().toLowerCase();
    if (kind === "error") return "text-danger";
    if (kind === "success") return "text-success";
    return "text-secondary";
  }

  function mediaRuntimeOptions() {
    return Array.isArray(state.mediaDisplays) ? state.mediaDisplays : [];
  }

  function mediaSceneOptions() {
    return Array.isArray(state.mediaScenes) ? state.mediaScenes : [];
  }

  function mediaSceneById(sceneId) {
    return mediaSceneOptions().find((scene) => String(scene?.id || "").trim() === String(sceneId || "").trim()) || null;
  }

  function mediaSceneStackBehavior(scene) {
    const blend = String(scene?.blendMode || "").trim().toUpperCase();
    return blend === "PAUSE_LOWER" ? "interrupt" : "replace";
  }

  function normalizeMediaLaunchMode(value) {
    return String(value || "").trim().toLowerCase() === "windowed" ? "windowed" : "fullscreen";
  }

  function ensureSceneTriggerSelections() {
    const scenes = mediaSceneOptions();
    const runtimes = mediaRuntimeOptions();
    const sceneIds = new Set(scenes.map((scene) => String(scene?.id || "").trim()).filter(Boolean));
    const runtimeIds = new Set(runtimes.map((target) => String(target?.id || target?.displayId || "").trim()).filter(Boolean));
    if (!sceneIds.has(String(state.selectedMediaSceneId || "").trim())) {
      state.selectedMediaSceneId = scenes.length ? String(scenes[0]?.id || "").trim() : "";
    }
    if (!runtimeIds.has(String(state.selectedMediaRuntimeId || "").trim())) {
      state.selectedMediaRuntimeId = runtimes.length ? String(runtimes[0]?.id || "").trim() : "";
    }
    state.selectedMediaLaunchMode = normalizeMediaLaunchMode(state.selectedMediaLaunchMode);
  }

  function renderSceneTriggerCard() {
    if (!sceneTriggerEl) return;
    ensureSceneTriggerSelections();
    const scenes = mediaSceneOptions();
    const runtimes = mediaRuntimeOptions();
    const sceneOptions = scenes.length
      ? scenes.map((scene) => {
        const sceneId = String(scene?.id || "").trim();
        const selected = sceneId && sceneId === String(state.selectedMediaSceneId || "").trim() ? " selected" : "";
        const label = String(scene?.name || sceneId || "Scene").trim();
        return `<option value="${esc(sceneId)}"${selected}>${esc(label)}</option>`;
      }).join("")
      : `<option value="">No media scenes available</option>`;
    const runtimeOptions = runtimes.length
      ? runtimes.map((target, index) => {
        const runtimeId = String(target?.id || "").trim();
        const selected = runtimeId && runtimeId === String(state.selectedMediaRuntimeId || "").trim() ? " selected" : "";
        return `<option value="${esc(runtimeId)}"${selected}>${esc(mediaDisplayTitle(target, index))}</option>`;
      }).join("")
      : `<option value="">No displays available</option>`;
    const launchMode = normalizeMediaLaunchMode(state.selectedMediaLaunchMode);
    const disabledAttr = (!scenes.length || !runtimes.length) ? " disabled" : "";
    const expanded = !state.sceneTriggerCollapsed;
    const panelClass = expanded ? "" : " d-none";
    const iconClass = expanded ? "fa-chevron-down" : "fa-chevron-right";
    sceneTriggerEl.innerHTML = `
      <div class="card emu-card liveview-scene-trigger-card">
        <div class="card-header d-flex align-items-center justify-content-between" role="button" tabindex="0" data-liveview-toggle="scene-trigger" aria-label="Toggle Scene Trigger">
          <span class="fw-semibold">Scene Trigger</span>
          <button type="button" class="btn btn-sm btn-link text-decoration-none p-0 liveview-card-collapse-toggle" data-liveview-toggle="scene-trigger" aria-label="Toggle Scene Trigger" aria-expanded="${expanded ? "true" : "false"}">
            <i class="fa ${iconClass}" data-liveview-toggle-icon="scene-trigger"></i>
          </button>
        </div>
        <div class="card-body${panelClass}" data-liveview-panel="scene-trigger">
          <div class="mb-2">
            <label class="form-label form-label-sm mb-1" for="liveview-scene-trigger-scene">Scene</label>
            <select class="form-select form-select-sm" id="liveview-scene-trigger-scene"${disabledAttr}>${sceneOptions}</select>
          </div>
          <div class="mb-2">
            <label class="form-label form-label-sm mb-1" for="liveview-scene-trigger-runtime">Display</label>
            <select class="form-select form-select-sm" id="liveview-scene-trigger-runtime"${disabledAttr}>${runtimeOptions}</select>
          </div>
          <div class="mb-2">
            <label class="form-label form-label-sm mb-1" for="liveview-scene-trigger-mode">Window mode</label>
            <select class="form-select form-select-sm" id="liveview-scene-trigger-mode"${disabledAttr}>
              <option value="windowed"${launchMode === "windowed" ? " selected" : ""}>Windowed</option>
              <option value="fullscreen"${launchMode !== "windowed" ? " selected" : ""}>Fullscreen</option>
            </select>
          </div>
          <div class="d-flex gap-2 flex-wrap">
            <button type="button" class="btn btn-outline-primary btn-sm" id="liveview-scene-trigger-play"${disabledAttr}>Play Scene</button>
            <button type="button" class="btn btn-outline-danger btn-sm" id="liveview-scene-trigger-stop"${disabledAttr}>Stop Scene</button>
          </div>
          <div class="small mt-2 ${sceneTriggerStatusClass()}" id="liveview-scene-trigger-status">${esc(state.sceneTriggerStatus || "Choose a display, mode, and scene, then launch it through the media runtime flow.")}</div>
        </div>
      </div>`;

    sceneTriggerEl.querySelectorAll("[data-liveview-toggle=\"scene-trigger\"]").forEach((el) => {
      const toggle = () => {
        state.sceneTriggerCollapsed = !state.sceneTriggerCollapsed;
        saveSceneTriggerCollapsedState();
        renderSceneTriggerCard();
      };
      el.addEventListener("click", (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
        toggle();
      });
      el.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter" || evt.key === " ") {
          evt.preventDefault();
          toggle();
        }
      });
    });

    const sceneSelectEl = document.getElementById("liveview-scene-trigger-scene");
    const runtimeSelectEl = document.getElementById("liveview-scene-trigger-runtime");
    const modeSelectEl = document.getElementById("liveview-scene-trigger-mode");
    const playBtn = document.getElementById("liveview-scene-trigger-play");
    const stopBtn = document.getElementById("liveview-scene-trigger-stop");
    sceneSelectEl?.addEventListener("change", () => {
      state.selectedMediaSceneId = String(sceneSelectEl.value || "").trim();
    });
    runtimeSelectEl?.addEventListener("change", () => {
      state.selectedMediaRuntimeId = String(runtimeSelectEl.value || "").trim();
    });
    modeSelectEl?.addEventListener("change", () => {
      state.selectedMediaLaunchMode = normalizeMediaLaunchMode(modeSelectEl.value || "fullscreen");
    });
    playBtn?.addEventListener("click", () => {
      void playEmbeddedScene();
    });
    stopBtn?.addEventListener("click", () => {
      void stopEmbeddedDisplay();
    });
  }

  async function playEmbeddedScene() {
    const sceneId = String(state.selectedMediaSceneId || "").trim();
    const runtimeId = String(state.selectedMediaRuntimeId || "").trim();
    if (!sceneId || !runtimeId) return;
    state.sceneTriggerStatus = "Launching scene…";
    state.sceneTriggerStatusType = "";
    renderSceneTriggerCard();
    try {
      const target = mediaRuntimeOptions().find((row) => String(row?.id || "") === runtimeId) || null;
      const scene = mediaSceneById(sceneId);
      const displayId = String(target?.id || runtimeId).trim();
      const launchMode = normalizeMediaLaunchMode(state.selectedMediaLaunchMode);
      const res = await fetch("/api/media/play", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          sceneId,
          displayId,
          launchMode,
          stackBehavior: mediaSceneStackBehavior(scene),
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(String(payload?.error || `HTTP ${res.status}`));
      }
      const sceneLabel = String(scene?.name || sceneId).trim();
      const runtimeLabelText = target ? mediaDisplayTitle(target, 0) : runtimeId;
      state.sceneTriggerStatus = `${sceneLabel} launched on ${runtimeLabelText} (${launchMode}).`;
      state.sceneTriggerStatusType = "success";
    } catch (err) {
      state.sceneTriggerStatus = `Play failed: ${err?.message || "unknown_error"}`;
      state.sceneTriggerStatusType = "error";
    }
    renderSceneTriggerCard();
  }

  async function stopEmbeddedDisplay() {
    const sceneId = String(state.selectedMediaSceneId || "").trim();
    const runtimeId = String(state.selectedMediaRuntimeId || "").trim();
    if (!runtimeId && !sceneId) return;
    state.sceneTriggerStatus = "Stopping scene…";
    state.sceneTriggerStatusType = "";
    renderSceneTriggerCard();
    try {
      const target = mediaRuntimeOptions().find((row) => String(row?.id || "") === runtimeId) || null;
      const launchMode = normalizeMediaLaunchMode(state.selectedMediaLaunchMode);
      const res = await fetch("/api/media/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          sceneId: sceneId || null,
          displayId: String(target?.id || runtimeId || "").trim() || null,
          launchMode,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(String(payload?.error || `HTTP ${res.status}`));
      }
      const scene = mediaSceneById(sceneId);
      const runtimeLabelText = target ? mediaDisplayTitle(target, 0) : runtimeId;
      state.sceneTriggerStatus = `${String(scene?.name || sceneId || "Scene").trim()} stopped on ${runtimeLabelText} (${launchMode}).`;
      state.sceneTriggerStatusType = "success";
    } catch (err) {
      state.sceneTriggerStatus = `Stop failed: ${err?.message || "unknown_error"}`;
      state.sceneTriggerStatusType = "error";
    }
    renderSceneTriggerCard();
  }

  function systemEventOptionsMarkup() {
    const categories = state.systemEventCategories && typeof state.systemEventCategories === "object"
      ? state.systemEventCategories
      : {};
    const keys = Object.keys(categories);
    if (!keys.length) return "";
    return keys.map((key) => {
      const cat = categories[key] && typeof categories[key] === "object" ? categories[key] : {};
      const label = String(cat.label || key).trim() || key;
      const events = Array.isArray(cat.events) ? cat.events : [];
      const items = events
        .map((ev) => String(ev || "").trim())
        .filter((ev) => !!ev)
        .map((ev) => `<option value="${esc(ev)}"${state.selectedSystemEvent === ev ? " selected" : ""}>${esc(ev)}</option>`)
        .join("");
      if (!items) return "";
      return `<optgroup label="${esc(label)}">${items}</optgroup>`;
    }).join("");
  }

  function renderSystemEventsCard() {
    if (!systemEventsEl) return;
    const options = systemEventOptionsMarkup();
    if (!options) {
      systemEventsEl.innerHTML = `
        <div class="card emu-card">
          <div class="card-header d-flex align-items-center justify-content-between">
            <span class="fw-semibold">System Events</span>
            <button type="button" class="btn btn-sm btn-link text-decoration-none p-0 liveview-card-collapse-toggle" aria-expanded="false" disabled>
              <i class="fa fa-chevron-right"></i>
            </button>
          </div>
          <div class="card-body">
            <div class="text-secondary small">No system events available from rules registry.</div>
          </div>
        </div>`;
      return;
    }
    const statusClass = state.lastSystemEventStatusType === "error" ? "text-danger"
      : state.lastSystemEventStatusType === "ok" ? "text-success"
      : "text-secondary";
    const expanded = !state.systemEventsCollapsed;
    const panelClass = expanded ? "" : " d-none";
    const iconClass = expanded ? "fa-chevron-down" : "fa-chevron-right";
    systemEventsEl.innerHTML = `
      <div class="card emu-card">
        <div class="card-header d-flex align-items-center justify-content-between" role="button" tabindex="0" data-liveview-toggle="system-events" aria-label="Toggle System Events">
          <span class="fw-semibold">System Events</span>
          <button type="button" class="btn btn-sm btn-link text-decoration-none p-0 liveview-card-collapse-toggle" data-liveview-toggle="system-events" aria-label="Toggle System Events" aria-expanded="${expanded ? "true" : "false"}">
            <i class="fa ${iconClass}" data-liveview-toggle-icon="system-events"></i>
          </button>
        </div>
        <div class="card-body${panelClass}" data-liveview-panel="system-events">
          <div class="small text-secondary mb-1">Trigger rules-defined system events manually for testing.</div>
          <div class="d-flex align-items-center gap-2 liveview-system-event-row">
            <select class="form-select form-select-sm" id="liveview-system-event-select">${options}</select>
            <button type="button" class="btn btn-outline-primary btn-sm text-nowrap" id="liveview-system-event-fire">Trigger</button>
          </div>
          <div class="liveview-system-events-status small mt-1 ${statusClass}" id="liveview-system-event-status">${esc(state.lastSystemEventStatus || "")}</div>
        </div>
      </div>`;
    systemEventsEl.querySelectorAll("[data-liveview-toggle=\"system-events\"]").forEach((el) => {
      const toggle = () => {
        state.systemEventsCollapsed = !state.systemEventsCollapsed;
        saveSystemEventsCollapsedState();
        renderSystemEventsCard();
      };
      el.addEventListener("click", (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
        toggle();
      });
      el.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter" || evt.key === " ") {
          evt.preventDefault();
          toggle();
        }
      });
    });
    const selectEl = document.getElementById("liveview-system-event-select");
    const fireBtn = document.getElementById("liveview-system-event-fire");
    if (selectEl) {
      selectEl.addEventListener("change", () => {
        state.selectedSystemEvent = String(selectEl.value || "").trim();
      });
    }
    if (fireBtn) {
      fireBtn.addEventListener("click", () => {
        void fireSelectedSystemEvent();
      });
    }
  }

  async function fireSelectedSystemEvent() {
    const eventName = String(state.selectedSystemEvent || "").trim();
    if (!eventName) return;
    try {
      const res = await fireEvent(eventName, "system", {});
      if (!res) {
        state.lastSystemEventStatusType = "error";
        state.lastSystemEventStatus = "Failed to reach events API.";
      } else if (!res.ok) {
        const err = res?.payload?.error ? String(res.payload.error) : `${res.status}`;
        state.lastSystemEventStatusType = "error";
        state.lastSystemEventStatus = `Failed to trigger ${eventName} (${err}).`;
      } else {
        const body = (res && typeof res.payload === "object" && res.payload) ? res.payload : {};
        if (body && body.ok) {
          state.lastSystemEventStatusType = "ok";
          state.lastSystemEventStatus = `Triggered ${eventName}.`;
        } else {
          const err = body && body.error ? String(body.error) : "unknown_error";
          state.lastSystemEventStatusType = "error";
          state.lastSystemEventStatus = `Failed to trigger ${eventName} (${err}).`;
        }
      }
    } catch (_) {
      state.lastSystemEventStatusType = "error";
      state.lastSystemEventStatus = "Failed to trigger event.";
    }
    renderSystemEventsCard();
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

  function tableDesignScale(widthPx, heightPx) {
    const designW = Math.max(1, Number(state.options?.width) || 700);
    const designH = Math.max(1, Number(state.options?.height) || 1400);
    const w = Math.max(1, Number(widthPx) || Number(state.tableRect?.width) || designW);
    const h = Math.max(1, Number(heightPx) || Number(state.tableRect?.height) || designH);
    const s = Math.min(w / designW, h / designH);
    return Math.max(0.2, Math.min(1, s));
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
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44"><g transform="translate(109.3 0) scale(-1 1)"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></g></svg>`;
      case "flipper-right":
        return `<svg class="emu-svg" xmlns="http://www.w3.org/2000/svg" viewBox="-12 -22 136 44"><path fill="${color}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd" d="M 0.8 -9.9679 L 101.44 -17.9423 A 18 18 0 1 1 101.44 17.9423 L 0.8 9.9679 A 10 10 0 1 1 0.8 -9.9679 Z M 106.5 0 A 6.5 6.5 0 1 0 93.5 0 A 6.5 6.5 0 1 0 106.5 0 Z"/></svg>`;
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
      case "lcd-display": {
        const lcd = lcdTextForElement(el);
        const line1 = String(lcd.line1 || "");
        const line2 = String(lcd.line2 || "");
        const maxLen = Math.max(line1.length, line2.length, 1);
        const fontSize = Math.max(5.8, Math.min(8.4, 128 / maxLen));
        const clipId = `lcdTextClip-${String(el.id || "lcd").replace(/[^A-Za-z0-9_-]/g, "_")}`;
        return `<svg class="emu-svg" viewBox="0 0 120 72" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="LCD Display">
          <rect x="6" y="6" width="108" height="60" rx="10" fill="#04070f" stroke="#ffffff" stroke-width="2"/>
          <rect x="8" y="8" width="104" height="26" rx="8" fill="rgba(255,255,255,0.08)"/>
          <rect x="16" y="16" width="88" height="40" rx="4" fill="rgba(255,255,255,0.04)"/>
          <clipPath id="${clipId}">
            <rect x="18" y="18" width="84" height="36" rx="2"/>
          </clipPath>
          <g clip-path="url(#${clipId})" font-family="SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" font-size="${fontSize}" font-weight="600" fill="#cffafe" text-anchor="start" style="letter-spacing:0.02em">
            <text x="22" y="29">${esc(line1)}</text>
            <text x="22" y="51">${esc(line2)}</text>
          </g>
        </svg>`;
      }
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

    renderLightingOverlay(visualScale);

    state.elements.forEach((el) => {
      const node = document.createElement("div");
      node.className = "emu-el";
      node.dataset.id = el.id;
      node.dataset.type = el.icon || el.type;
      node.dataset.size = el.size || "m";
      const kind = String(el.icon || el.type || "").trim().toLowerCase();
      let sizeScale = (Number(el.scale) || 1) * visualScale;
      // Keep LCD display footprint aligned with Playfield/Lighting while
      // Live View retains its global stage scale factor.
      if (kind === "lcd-display" && LIVEVIEW_SCALE_FACTOR > 0) {
        sizeScale *= 1 / LIVEVIEW_SCALE_FACTOR;
      }
      node.style.setProperty("--emu-size-scale", String(sizeScale));
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

  function fixturePixels(fixture) {
    const widthPx = Math.max(1, Number(state.tableRect?.width) || 1);
    const heightPx = Math.max(1, Number(state.tableRect?.height) || 1);
    const count = Math.max(1, toPositiveInt(fixture?.pixelCount, 1));
    const mode = String(fixture?.layoutMode || "line").trim().toLowerCase();
    if (mode === "manual" && Array.isArray(fixture?.points) && fixture.points.length) {
      const raw = fixture.points.map((p) => ({
        x: clampWithLightingPad(p?.x, widthPx, 0.5),
        y: clampWithLightingPad(p?.y, heightPx, 0.5),
      }));
      if (raw.length >= count) return raw.slice(0, count);
      const out = raw.slice();
      const fallback = fixturePixels(Object.assign({}, fixture, { layoutMode: "line" }));
      while (out.length < count) out.push(fallback[out.length] || fallback[fallback.length - 1] || { x: 0.5, y: 0.5 });
      return out;
    }
    const line = resolvedFixtureLine(fixture, widthPx, heightPx);
    const x1 = clampWithLightingPad(line.x1, widthPx, 0.4);
    const y1 = clampWithLightingPad(line.y1, heightPx, 0.5);
    const x2 = clampWithLightingPad(line.x2, widthPx, 0.6);
    const y2 = clampWithLightingPad(line.y2, heightPx, 0.5);
    const out = [];
    for (let i = 0; i < count; i += 1) {
      const t = count === 1 ? 0.5 : i / (count - 1);
      out.push({ x: x1 + ((x2 - x1) * t), y: y1 + ((y2 - y1) * t) });
    }
    return out;
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
    const stageScale = tableDesignScale(w, h);
    const half = Math.max(1, wantedLengthPx * stageScale) / 2;
    const hx = (Math.cos(theta) * half) / w;
    const hy = (Math.sin(theta) * half) / h;
    return {
      x1: clampWithLightingPad(cx - hx, w, 0.4),
      y1: clampWithLightingPad(cy - hy, h, 0.5),
      x2: clampWithLightingPad(cx + hx, w, 0.6),
      y2: clampWithLightingPad(cy + hy, h, 0.5),
    };
  }

  function fixtureMarkerColor(fixture) {
    const type = String(fixture?.type || "").trim().toLowerCase();
    if (type === "rgb_strip") return "rgba(147, 197, 253, 0.92)";
    if (type === "rgb_led") return "rgba(103, 232, 249, 0.92)";
    const fixed = String(fixture?.fixedColor || "").trim();
    if (/^#[0-9a-f]{6}$/i.test(fixed)) return fixed;
    return "rgba(250, 204, 21, 0.92)";
  }

  function fixtureMarkerSizePx(fixture, visualScale) {
    const base = Number(fixture?.markerSizePx);
    const raw = Number.isFinite(base) ? base : (String(fixture?.type || "").toLowerCase() === "rgb_strip" ? 8 : 12);
    const stageScale = tableDesignScale();
    const compactScale = Number.isFinite(Number(visualScale)) ? Math.max(0.2, Number(visualScale)) : 1;
    const scaled = raw * stageScale * compactScale;
    return Math.max(3, Math.min(22, scaled));
  }

  function normalizeHexColor(value, fallback = "#60a5fa") {
    const s = String(value || "").trim();
    return /^#[0-9a-fA-F]{6}$/.test(s) ? s.toLowerCase() : fallback;
  }

  function hexToRgba(hex, alpha) {
    const s = normalizeHexColor(hex, "#60a5fa");
    const r = parseInt(s.slice(1, 3), 16);
    const g = parseInt(s.slice(3, 5), 16);
    const b = parseInt(s.slice(5, 7), 16);
    const a = Math.max(0, Math.min(1, Number(alpha) || 0));
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  function sceneDurationMs(scene) {
    if (Number.isFinite(Number(scene?.durationMs)) && Number(scene.durationMs) > 0) {
      return Math.max(0, Math.round(Number(scene.durationMs)));
    }
    const frames = Array.isArray(scene?.frames) ? scene.frames : [];
    if (frames.length > 0) {
      // Compiled scenes may omit durationMs; estimate from frame timeline so
      // non-looping scenes still expire in Live View.
      const maxAtMs = frames.reduce((acc, row) => {
        const at = Number(row?.atMs);
        return Number.isFinite(at) && at > acc ? at : acc;
      }, 0);
      if (maxAtMs > 0) return Math.max(1, Math.round(maxAtMs + LIGHTING_FRAME_MS));
      const frameCount = Number(scene?.frameCount);
      const count = Number.isFinite(frameCount) && frameCount > 0 ? Math.round(frameCount) : frames.length;
      return Math.max(1, Math.round(count * LIGHTING_FRAME_MS));
    }
    const duration = scene && typeof scene.duration === "object" ? scene.duration : {};
    const rawUnit = String(duration?.unit || "seconds").trim().toLowerCase();
    const rawValue = Number(duration?.value);
    const value = Number.isFinite(rawValue) ? rawValue : 0;
    if (value <= 0) return 0;
    if (rawUnit === "minutes") return Math.max(0, Math.round(value * 60000));
    if (rawUnit === "frames") return Math.max(0, Math.round(value * LIGHTING_FRAME_MS));
    return Math.max(0, Math.round(value * 1000));
  }

  function sceneIsLooping(scene) {
    const mode = String(scene?.endBehavior || "stop").trim().toLowerCase();
    return mode === "repeat" || mode === "bounce";
  }

  function startLightingScene(sceneId) {
    const sid = String(sceneId || "").trim();
    if (!sid) return;
    const scene = state.lightingCompiledScenesById[sid] || state.lightingScenesById[sid];
    if (!scene) return;
    const now = Date.now();
    const durMs = sceneDurationMs(scene);
    const looping = sceneIsLooping(scene);
    state.activeLightingScenes[sid] = {
      startedAtMs: now,
      expiresAtMs: looping ? null : (durMs > 0 ? now + durMs : null),
      drivenFixtureIds: [],
    };
    ensureLightingTick();
    renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
  }

  function clearHardwareLedLatchForFixtures(fixtureIds) {
    const ids = Array.isArray(fixtureIds) ? fixtureIds : [];
    if (!ids.length) return false;
    const fixtureMap = lightingFixtureMap();
    let changed = false;
    ids.forEach((fid) => {
      const id = String(fid || "").trim();
      if (!id) return;
      const fixture = fixtureMap[id];
      if (!fixture) return;
      if (String(fixture?.type || "").trim().toLowerCase() !== "led") return;
      if (!state.lightingLedHardwareOnById[id]) return;
      state.lightingLedHardwareOnById[id] = false;
      changed = true;
    });
    return changed;
  }

  function stopLightingScene(sceneId) {
    const sid = String(sceneId || "").trim();
    let cleared = false;
    if (!sid || sid === "*") {
      Object.values(state.activeLightingScenes || {}).forEach((row) => {
        cleared = clearHardwareLedLatchForFixtures(row?.drivenFixtureIds || []) || cleared;
      });
      state.activeLightingScenes = {};
    } else {
      const row = state.activeLightingScenes[sid] || {};
      cleared = clearHardwareLedLatchForFixtures(row?.drivenFixtureIds || []) || cleared;
      delete state.activeLightingScenes[sid];
    }
    ensureLightingTick();
    renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
    if (cleared) renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
  }

  function pruneExpiredLightingScenes() {
    const now = Date.now();
    let changed = false;
    Object.keys(state.activeLightingScenes).forEach((sid) => {
      const row = state.activeLightingScenes[sid];
      const exp = Number(row?.expiresAtMs);
      if (Number.isFinite(exp) && exp > 0 && now >= exp) {
        clearHardwareLedLatchForFixtures(row?.drivenFixtureIds || []);
        delete state.activeLightingScenes[sid];
        changed = true;
      }
    });
    return changed;
  }

  function pruneExpiredLightingPixelOverrides() {
    const now = Date.now();
    let changed = false;
    Object.keys(state.lightingPixelOverridesByFixtureId || {}).forEach((fid) => {
      const fixtureRow = state.lightingPixelOverridesByFixtureId[fid];
      if (!fixtureRow || typeof fixtureRow !== "object") {
        delete state.lightingPixelOverridesByFixtureId[fid];
        changed = true;
        return;
      }
      Object.keys(fixtureRow).forEach((pxKey) => {
        const cell = fixtureRow[pxKey];
        if (!cell || typeof cell !== "object") {
          delete fixtureRow[pxKey];
          changed = true;
          return;
        }
        const expiresAt = Number(cell.expiresAtMs);
        if (Number.isFinite(expiresAt) && expiresAt > 0 && now >= expiresAt) {
          delete fixtureRow[pxKey];
          changed = true;
        }
      });
      if (Object.keys(fixtureRow).length === 0) {
        delete state.lightingPixelOverridesByFixtureId[fid];
        changed = true;
      }
    });
    return changed;
  }

  function ensureLightingTick() {
    const hasActiveScenes = Object.keys(state.activeLightingScenes).length > 0;
    const hasPixelOverrides = Object.keys(state.lightingPixelOverridesByFixtureId || {}).length > 0;
    const hasActive = hasActiveScenes || hasPixelOverrides;
    if (!hasActive) {
      if (state.lightingTickTimer) {
        clearInterval(state.lightingTickTimer);
        state.lightingTickTimer = null;
      }
      return;
    }
    if (state.lightingTickTimer) return;
    state.lightingTickTimer = setInterval(() => {
      const changed = pruneExpiredLightingScenes() || pruneExpiredLightingPixelOverrides();
      renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
      if (
        Object.keys(state.activeLightingScenes).length === 0
        && Object.keys(state.lightingPixelOverridesByFixtureId || {}).length === 0
      ) {
        clearInterval(state.lightingTickTimer);
        state.lightingTickTimer = null;
        if (changed) renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
      }
    }, 120);
  }

  function lightingFixtureMap() {
    const out = {};
    (Array.isArray(state.lightingFixtures) ? state.lightingFixtures : []).forEach((f) => {
      const id = String(f?.id || "").trim();
      if (id) out[id] = f;
    });
    return out;
  }

  function activeLightingByFixtureId() {
    const fixtureMap = lightingFixtureMap();
    const byFixture = {};
    const sceneDrivenFixtureIds = new Set();
    Object.values(fixtureMap).forEach((f) => {
      const id = String(f?.id || "").trim();
      if (!id) return;
      const pcount = Math.max(1, Number(f?.pixelCount || 1));
      const baseColor = normalizeHexColor(f?.fixedColor, "#60a5fa");
      const pixels = Array.from({ length: pcount }, () => ({ on: false, color: baseColor }));
      byFixture[id] = {
        on: false,
        color: baseColor,
        pixels,
      };
    });

    Object.keys(state.activeLightingScenes).forEach((sid) => {
      const scene = state.lightingCompiledScenesById[sid];
      if (!scene) return;
      const runtime = state.activeLightingScenes[sid] || {};
      const sceneDrivenNow = new Set();
      const startedAt = Number(runtime?.startedAtMs) || Date.now();
      const durationMs = Math.max(1, sceneDurationMs(scene));
      const frames = Array.isArray(scene?.frames) ? scene.frames : [];
      const frameCountRaw = Number(scene?.frameCount);
      const frameCount = Math.max(
        1,
        Number.isFinite(frameCountRaw) && frameCountRaw > 0
          ? Math.round(frameCountRaw)
          : frames.length || 1
      );
      const elapsed = Math.max(0, Date.now() - startedAt);
      const endBehavior = String(scene?.endBehavior || "stop").trim().toLowerCase();
      let phase = elapsed / durationMs;
      if (endBehavior === "repeat" || endBehavior === "bounce") {
        phase = phase - Math.floor(phase);
      } else {
        phase = Math.max(0, Math.min(1, phase));
      }
      let frameIdx = Math.floor(phase * frameCount);
      if (frameIdx >= frameCount) frameIdx = frameCount - 1;
      if (frameIdx < 0) frameIdx = 0;
      const frame = frames[Math.min(frameIdx, frames.length - 1)] || null;
      const changes = Array.isArray(frame?.changes) ? frame.changes : [];

      changes.forEach((row) => {
        const target = String(row?.target || "").trim() || "*";
        const pxRaw = row?.pixelIndex;
        const hasPx = Number.isFinite(Number(pxRaw));
        const px = hasPx ? Math.max(0, Math.floor(Number(pxRaw))) : null;
        const isOff = !!row?.off;
        const rowColor = normalizeHexColor(row?.color, "#60a5fa");
        const brightness = Number.isFinite(Number(row?.brightness)) ? Math.max(0, Math.min(1, Number(row.brightness))) : 1;
        const intensity = Number.isFinite(Number(row?.intensity)) ? Math.max(0, Math.min(1, Number(row.intensity))) : 1;
        const on = !isOff && (brightness * intensity) > 0.01;

        const applyToFixture = (fid) => {
          if (!byFixture[fid]) return;
          const fixture = fixtureMap[fid];
          const type = String(fixture?.type || "").trim().toLowerCase();
          const useDynamicColor = type === "rgb_strip" || type === "rgb_led";
          const color = useDynamicColor
            ? rowColor
            : normalizeHexColor(fixture?.fixedColor, "#60a5fa");
          const item = byFixture[fid];
          if (!Array.isArray(item.pixels) || !item.pixels.length) return;
          sceneDrivenFixtureIds.add(fid);
          sceneDrivenNow.add(fid);
          if (hasPx && px !== null && px < item.pixels.length) {
            item.pixels[px] = { on, color };
          } else {
            for (let i = 0; i < item.pixels.length; i += 1) item.pixels[i] = { on, color };
          }
        };

        if (target === "*") {
          Object.keys(byFixture).forEach((fid) => applyToFixture(fid));
        } else {
          applyToFixture(target);
        }
      });
      runtime.drivenFixtureIds = Array.from(sceneDrivenNow);
      state.activeLightingScenes[sid] = runtime;
    });

    Object.entries(state.lightingLedHardwareOnById || {}).forEach(([fid, isOn]) => {
      const fixture = fixtureMap[fid];
      if (!fixture) return;
      if (String(fixture?.type || "").trim().toLowerCase() !== "led") return;
      // If a playing scene currently drives this fixture, let scene animation
      // take precedence over latched hardware-on state in Live View.
      if (sceneDrivenFixtureIds.has(fid)) return;
      if (!byFixture[fid]) {
        const baseColor = normalizeHexColor(fixture?.fixedColor, "#60a5fa");
        byFixture[fid] = { on: false, color: baseColor, pixels: [{ on: false, color: baseColor }] };
      }
      if (!Array.isArray(byFixture[fid].pixels) || !byFixture[fid].pixels.length) {
        byFixture[fid].pixels = [{ on: false, color: byFixture[fid].color || normalizeHexColor(fixture?.fixedColor, "#60a5fa") }];
      }
      byFixture[fid].pixels[0] = {
        on: !!isOn,
        color: normalizeHexColor(fixture?.fixedColor, "#60a5fa"),
      };
    });

    const now = Date.now();
    Object.entries(state.lightingPixelOverridesByFixtureId || {}).forEach(([fid, fixtureOverrides]) => {
      if (!fixtureOverrides || typeof fixtureOverrides !== "object") return;
      const fixture = fixtureMap[fid];
      if (!fixture) return;
      if (!byFixture[fid]) {
        const baseColor = normalizeHexColor(fixture?.fixedColor, "#60a5fa");
        const pcount = Math.max(1, Number(fixture?.pixelCount || 1));
        byFixture[fid] = {
          on: false,
          color: baseColor,
          pixels: Array.from({ length: pcount }, () => ({ on: false, color: baseColor })),
        };
      }
      const item = byFixture[fid];
      if (!Array.isArray(item.pixels) || !item.pixels.length) return;
      Object.entries(fixtureOverrides).forEach(([pxKey, row]) => {
        const px = Number(pxKey);
        if (!Number.isFinite(px) || px < 0 || px >= item.pixels.length) return;
        if (!row || typeof row !== "object") return;
        const mode = String(row.mode || "on").trim().toLowerCase();
        let isOn = mode !== "off";
        if (mode === "blink") {
          const startedAtMs = Number(row.startedAtMs) || now;
          const blinkIntervalMs = Math.max(50, Number(row.blinkIntervalMs) || 150);
          const phase = Math.floor(Math.max(0, now - startedAtMs) / blinkIntervalMs);
          isOn = phase % 2 === 0;
        }
        item.pixels[px] = {
          on: isOn,
          color: normalizeHexColor(row.color, normalizeHexColor(fixture?.fixedColor, "#60a5fa")),
        };
      });
    });

    Object.keys(byFixture).forEach((fid) => {
      const item = byFixture[fid];
      const pixels = Array.isArray(item?.pixels) ? item.pixels : [];
      const firstOn = pixels.find((p) => !!p?.on);
      item.on = !!firstOn;
      item.color = firstOn?.color || item.color;
    });

    return byFixture;
  }

  function setHardwareLedStateFromAction(targetSource, actionParams) {
    const fixture = (Array.isArray(state.lightingFixtures) ? state.lightingFixtures : [])
      .find((f) => String(f?.id || "").trim() === String(targetSource || "").trim());
    if (!fixture) return false;
    if (String(fixture?.type || "").trim().toLowerCase() !== "led") return false;
    const isOn = setOutputIsActiveForTarget(targetSource, null, actionParams || {});
    const fid = String(fixture.id);
    const prev = !!state.lightingLedHardwareOnById[fid];
    const next = !!isOn;
    state.lightingLedHardwareOnById[fid] = next;
    return prev !== next;
  }

  function applyLightingActionRuntime(entry) {
    const type = String(entry?.type || "").trim().toLowerCase();
    if (!type) return;
    if (type === "apply_lighting_scene") {
      const sceneId = String(entry?.params?.sceneId || entry?.target || "").trim();
      if (sceneId) startLightingScene(sceneId);
      return;
    }
    if (type === "stop_lighting_scene") {
      const sceneId = String(entry?.params?.sceneId || entry?.target || "*").trim();
      stopLightingScene(sceneId || "*");
      return;
    }
    if (type === "set_output") {
      const target = String(entry?.target || "").trim();
      if (target) {
        const changed = setHardwareLedStateFromAction(target, entry?.params || {});
        if (changed) renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
      }
      return;
    }
    if (type === "set_lighting_pixels") {
      const target = String(entry?.params?.fixtureId || entry?.target || "").trim();
      if (target) {
        const changed = setLightingPixelsFromAction(target, entry?.params || {});
        if (changed) renderLightingOverlay(tableVisualScale() * LIVEVIEW_SCALE_FACTOR);
      }
    }
  }

  function setLightingPixelsFromAction(targetFixtureId, actionParams) {
    const fid = String(targetFixtureId || "").trim();
    if (!fid) return false;
    const fixture = (Array.isArray(state.lightingFixtures) ? state.lightingFixtures : [])
      .find((f) => String(f?.id || "").trim() === fid);
    if (!fixture) return false;
    const rawIndexes = actionParams?.pixelIndexes;
    const indexes = [];
    if (Array.isArray(rawIndexes)) {
      rawIndexes.forEach((value) => {
        const idx = Number(value);
        if (Number.isFinite(idx) && idx >= 0) indexes.push(Math.floor(idx));
      });
    } else if (typeof rawIndexes === "string") {
      rawIndexes.split(",").forEach((value) => {
        const idx = Number(value.trim());
        if (Number.isFinite(idx) && idx >= 0) indexes.push(Math.floor(idx));
      });
    }
    const pixelCount = Math.max(1, Number(fixture?.pixelCount || 1));
    const uniqueIndexes = Array.from(new Set(indexes)).filter((idx) => idx >= 0 && idx < pixelCount);
    if (!uniqueIndexes.length) return false;
    const mode = String(actionParams?.mode || "on").trim().toLowerCase();
    const color = normalizeHexColor(actionParams?.color, normalizeHexColor(fixture?.fixedColor, "#60a5fa"));
    const brightness = Number.isFinite(Number(actionParams?.brightness))
      ? Math.max(0, Math.min(1, Number(actionParams.brightness)))
      : 1;
    const blinkCount = Math.max(1, Math.floor(Number(actionParams?.blinkCount) || 2));
    const blinkIntervalMs = Math.max(50, Math.floor(Number(actionParams?.blinkIntervalMs) || 150));
    const startedAtMs = Date.now();
    const expiresAtMs = mode === "blink" ? startedAtMs + (blinkCount * blinkIntervalMs * 2) : null;
    const fixtureRow = state.lightingPixelOverridesByFixtureId[fid] || {};
    let changed = false;
    uniqueIndexes.forEach((idx) => {
      const prev = fixtureRow[idx];
      const next = {
        mode,
        color,
        brightness,
        startedAtMs,
        blinkIntervalMs,
        expiresAtMs,
      };
      if (JSON.stringify(prev || null) !== JSON.stringify(next)) changed = true;
      fixtureRow[idx] = next;
    });
    state.lightingPixelOverridesByFixtureId[fid] = fixtureRow;
    ensureLightingTick();
    return changed;
  }

  function renderLightingOverlay(visualScale) {
    const existing = tableEl.querySelector(".liveview-lighting-overlay");
    if (existing) existing.remove();
    const fixtures = Array.isArray(state.lightingFixtures) ? state.lightingFixtures : [];
    if (!fixtures.length) return;
    const byFixture = activeLightingByFixtureId();
    const wrap = document.createElement("div");
    wrap.className = "liveview-lighting-overlay";

    const isDarkMode = root.classList.contains("is-dark");
    fixtures.forEach((fixture) => {
      const points = fixturePixels(fixture);
      if (!points.length) return;
      const fid = String(fixture?.id || "").trim();
      const active = byFixture[fid] || { on: false, color: normalizeHexColor(fixture?.fixedColor, "#60a5fa") };
      const fallbackColor = fixtureMarkerColor(fixture);
      const sizePx = fixtureMarkerSizePx(fixture, visualScale);

      points.forEach((pt, idx) => {
        // Live View sits on the playfield preview orientation, which is the
        // opposite visual direction to the lighting authoring strip preview.
        // Reverse logical pixel order here so animated strips read correctly.
        const pixelIdx = points.length > 1 ? (points.length - 1 - idx) : idx;
        const pixel = Array.isArray(active?.pixels) ? (active.pixels[Math.min(pixelIdx, active.pixels.length - 1)] || null) : null;
        const pOn = pixel ? !!pixel.on : !!active.on;
        const pColor = pixel?.color || active.color || fallbackColor;
        const dot = document.createElement("div");
        dot.className = "liveview-lighting-dot";
        if (pOn) dot.classList.add("is-on");
        dot.title = String(fixture?.title || fixture?.id || "");
        dot.style.width = `${sizePx}px`;
        dot.style.height = `${sizePx}px`;
        dot.style.left = `${pt.x * state.tableRect.width}px`;
        dot.style.top = `${pt.y * state.tableRect.height}px`;
        dot.style.setProperty("--light-color", pColor);
        const offFill = isDarkMode ? hexToRgba(pColor, 0.18) : "rgba(0, 0, 0, 0.58)";
        const offBorder = isDarkMode ? "rgba(214, 224, 243, 0.35)" : "rgba(15, 23, 42, 0.68)";
        dot.style.setProperty("--light-fill", pOn ? hexToRgba(pColor, 0.82) : offFill);
        dot.style.setProperty("--light-border", pOn ? hexToRgba(pColor, 0.95) : offBorder);
        dot.style.setProperty("--light-glow-a", hexToRgba(pColor, 0.62));
        dot.style.setProperty("--light-glow-b", hexToRgba(pColor, 0.42));
        wrap.appendChild(dot);
      });
    });

    tableEl.appendChild(wrap);
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
    state.flipperHeldById[id] = !!isOn;
    const node = tableEl.querySelector(`.emu-el[data-id="${id}"]`);
    if (!node) return;
    const cls = dir === "right" ? "is-flip-right-held" : "is-flip-left-held";
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
    const targetEl = state.elements.find((el) => targetMatchesElement(targetSource, el));
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
    const source = canonicalHardwareId((ev.source || "").trim());
    const params = ev.params && typeof ev.params === "object" ? ev.params : {};
    const eventType = typeof params.eventType === "string" ? params.eventType.trim() : "";
    const gesture = eventType || inferGestureFromEventName(ev.name);
    const out = [];
    const seen = new Set();
    const sourceTail = uidTail(source);
    const dedupePush = (entry) => {
      const key = `${entry.target}|${entry.type}|${JSON.stringify(entry.params || {})}`;
      if (seen.has(key)) return;
      seen.add(key);
      out.push(entry);
    };
    const collectActionEntries = (map, suffix) => {
      const exact = map[`${source}|${suffix}`] || [];
      exact.forEach(dedupePush);
      if (!sourceTail) return;
      Object.entries(map).forEach(([k, list]) => {
        const sep = k.indexOf("|");
        if (sep < 0) return;
        const src = k.slice(0, sep);
        const keySuffix = k.slice(sep + 1);
        if (keySuffix !== suffix) return;
        if (uidTail(src) !== sourceTail) return;
        (list || []).forEach(dedupePush);
      });
    };

    if (gesture && source) {
      collectActionEntries(state.ruleActionsBySourceGesture, gesture);
    }
    if (!gesture && source) {
      collectActionEntries(state.ruleActionsBySourceEvent, ev.name);
    }
    out.forEach((entry) => {
      animateRuleTarget(entry.target, entry.type, entry.params || {}, entry.dir || null);
      applyLightingActionRuntime(entry);
    });
    return out.length;
  }

  function fireEvent(name, source, params) {
    const payloadParams = (params && typeof params === "object") ? { ...params } : {};
    let seq = 0;
    if (Number.isFinite(Number(payloadParams.__seq))) {
      seq = Math.max(0, Math.floor(Number(payloadParams.__seq)));
      delete payloadParams.__seq;
    }
    return fetch("/api/events/fire", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ name, source, seq: seq || undefined, params: payloadParams }),
    }).then(async (res) => {
      let payload = null;
      try {
        payload = await res.json();
      } catch (_) {
        payload = null;
      }
      return {
        ok: !!(res.ok && payload && payload.ok !== false),
        status: res.status,
        payload: payload || {},
        derived: Array.isArray(payload?.derived) ? payload.derived : [],
      };
    }).catch(() => null);
  }

  function nextEventSeq(source, eventName) {
    const key = `${String(source || "")}|${String(eventName || "")}`;
    const now = Date.now();
    const prev = Number(state.eventSeqByKey[key] || 0);
    const next = now > prev ? now : (prev + 1);
    state.eventSeqByKey[key] = next;
    return next;
  }

  function normalizeEventKey(evt) {
    const raw = String(evt?.key || "").toLowerCase();
    if (!raw) return "";
    if (raw === "left") return "arrowleft";
    if (raw === "right") return "arrowright";
    if (raw === "up") return "arrowup";
    if (raw === "down") return "arrowdown";
    if (raw === "spacebar") return " ";
    return raw;
  }

  function normalizeGestureParams(gesture, params) {
    const g = String(gesture || "").trim().toUpperCase();
    const src = params && typeof params === "object" ? params : {};
    const out = {};
    if (g === "DOUBLE_CLICKED" && src.windowMs != null) out.windowMs = src.windowMs;
    else if (g === "HELD" && src.minMs != null) out.minMs = src.minMs;
    else if (g === "REPEAT_WHILE_HELD" && src.repeatMs != null) out.repeatMs = src.repeatMs;
    out.eventType = g;
    return out;
  }

  function ruleBindingForSource(source, gesture) {
    const src = canonicalHardwareId(source);
    const entry = state.ruleTriggersBySource[src];
    if (entry && entry[gesture]) return { binding: entry[gesture], resolvedSource: src };
    const srcTail = uidTail(src);
    if (!srcTail) return null;
    for (const [key, row] of Object.entries(state.ruleTriggersBySource || {})) {
      if (uidTail(key) !== srcTail) continue;
      if (row && row[gesture]) return { binding: row[gesture], resolvedSource: key };
    }
    return null;
  }

  function ruleBindingForTarget(target, gesture) {
    const t = canonicalHardwareId(target);
    if (!t) return null;
    const g = String(gesture || "").toUpperCase();
    const exact = state.ruleTriggersByTargetGesture[`${t}|${g}`];
    if (Array.isArray(exact) && exact.length) return exact[0];
    const tTail = uidTail(t);
    if (!tTail) return null;
    for (const [key, list] of Object.entries(state.ruleTriggersByTargetGesture || {})) {
      const sep = key.indexOf("|");
      if (sep < 0) continue;
      const targetKey = key.slice(0, sep);
      const gestureKey = key.slice(sep + 1);
      if (gestureKey !== g) continue;
      if (uidTail(targetKey) !== tTail) continue;
      if (Array.isArray(list) && list.length) return list[0];
    }
    return null;
  }

  function fireBoundEventById(id, gesture) {
    const el = state.elements.find((e) => String(e.id) === String(id));
    if (!el) return;
    const source = canonicalHardwareId(String(el.hardwareId || el.id || ""));
    if (!source) return;
    const wantedGesture = String(gesture || "").toUpperCase();
    const sourceBound = ruleBindingForSource(source, wantedGesture);
    let ruleBinding = null;
    let resolvedSource = source;
    if (sourceBound && sourceBound.binding && sourceBound.binding.name) {
      ruleBinding = sourceBound.binding;
      resolvedSource = canonicalHardwareId(sourceBound.resolvedSource || source) || source;
    } else {
      const targetBound = ruleBindingForTarget(source, wantedGesture);
      if (!targetBound || !targetBound.name || !targetBound.source) return;
      ruleBinding = targetBound;
      resolvedSource = canonicalHardwareId(targetBound.source) || source;
    }
    const params = normalizeGestureParams(gesture, ruleBinding.params || {});
    params.__seq = nextEventSeq(resolvedSource, ruleBinding.name);
    void fireEvent(ruleBinding.name, resolvedSource, params).then((res) => {
      if (!res || res.ok) return;
      console.warn("Live View event fire failed", {
        status: res.status,
        name: ruleBinding.name,
        source: resolvedSource,
        gesture: params.eventType,
      });
    }).catch(() => {});
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
    const key = normalizeEventKey(evt);
    if (!key || state.activeKeyPresses[key]) return;
    const entry = normalizeKeymapEntry(state.keymap[key]);
    if (!entry) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    state.activeKeyPresses[key] = true;
    fireBoundEventById(entry.id, entry.keyDownGesture || "PRESSED");
  }

  function onKeyUp(evt) {
    const key = normalizeEventKey(evt);
    if (!key) return;
    const entry = normalizeKeymapEntry(state.keymap[key]);
    delete state.activeKeyPresses[key];
    if (!entry || !entry.keyUpGesture) return;
    if (evt && typeof evt.preventDefault === "function") evt.preventDefault();
    if (evt && typeof evt.stopPropagation === "function") evt.stopPropagation();
    fireBoundEventById(entry.id, entry.keyUpGesture);
  }

  function releaseActiveKeyGestures() {
    const keys = Object.keys(state.activeKeyPresses || {});
    keys.forEach((key) => {
      const entry = normalizeKeymapEntry(state.keymap[key]);
      if (!entry || !entry.keyUpGesture) return;
      fireBoundEventById(entry.id, entry.keyUpGesture);
    });
    state.activeKeyPresses = Object.create(null);
  }

  function eventMatchesElement(ev, el) {
    if (!el) return false;
    const evSource = canonicalHardwareId(ev.source || "");
    const elHw = canonicalHardwareId(el.hardwareId || "");
    const elId = canonicalHardwareId(el.id || "");
    if (evSource && (evSource === elHw || evSource === elId)) return true;
    if (ev.source && (uidTail(ev.source) === uidTail(el.hardwareId || el.id || ""))) return true;
    return false;
  }

  function targetMatchesElement(targetSource, el) {
    if (!el) return false;
    const tgt = canonicalHardwareId(targetSource || "");
    const elHw = canonicalHardwareId(el.hardwareId || "");
    const elId = canonicalHardwareId(el.id || "");
    if (tgt && (tgt === elHw || tgt === elId)) return true;
    const tTail = uidTailNorm(targetSource || "");
    if (tTail && (tTail === uidTailNorm(el.hardwareId || "") || tTail === uidTailNorm(el.id || ""))) return true;
    return false;
  }

  function extractHardwareIdsFromLcdTarget(targetSource) {
    const raw = String(targetSource || "").trim();
    if (!raw) return [];
    const matches = raw.match(/[A-Za-z0-9-]+__MAIN__GPIO__\d+/gi) || [];
    const out = [];
    matches.forEach((m) => {
      const id = canonicalHardwareId(m) || String(m || "").trim();
      if (id) out.push(id);
    });
    return out;
  }

  function extractGpioPinsFromText(rawText) {
    const raw = String(rawText || "").trim();
    if (!raw) return [];
    const out = [];
    const seen = new Set();
    const pushPin = (val) => {
      const n = Number.parseInt(String(val || ""), 10);
      if (!Number.isFinite(n) || n < 0) return;
      if (seen.has(n)) return;
      seen.add(n);
      out.push(n);
    };
    // Full hardware ids: ...__MAIN__GPIO__42
    const full = raw.match(/__MAIN__GPIO__(\d+)/gi) || [];
    full.forEach((token) => {
      const m = token.match(/__MAIN__GPIO__(\d+)/i);
      if (m && m[1]) pushPin(m[1]);
    });
    // Compact component ids: lcd-main-gpio-3-main-gpio-8
    const compact = raw.match(/main-gpio-(\d+)/gi) || [];
    compact.forEach((token) => {
      const m = token.match(/main-gpio-(\d+)/i);
      if (m && m[1]) pushPin(m[1]);
    });
    return out.sort((a, b) => a - b);
  }

  function lcdTargetMatchesElement(targetSource, el) {
    if (targetMatchesElement(targetSource, el)) return true;
    const raw = String(targetSource || "").trim();
    if (!raw.toUpperCase().startsWith("LCD_DISPLAY::")) return false;
    const ids = extractHardwareIdsFromLcdTarget(raw);
    if (ids.some((id) => targetMatchesElement(id, el))) return true;

    // Also support compact LCD target ids that encode just GPIO pairs.
    const targetPins = extractGpioPinsFromText(raw);
    if (!targetPins.length) return false;
    const elementPins = extractGpioPinsFromText(String(el?.hardwareId || el?.id || ""));
    if (!elementPins.length) return false;
    // Playfield LCD elements can be represented by just one of the two linked I2C pins.
    // In that case, match if the element pin is part of the target component pair.
    if (elementPins.length === 1) {
      return targetPins.includes(elementPins[0]);
    }
    if (targetPins.length !== elementPins.length) return false;
    for (let i = 0; i < targetPins.length; i += 1) {
      if (targetPins[i] !== elementPins[i]) return false;
    }
    return true;
  }

  function lcdTextForElement(el) {
    const hardwareId = canonicalHardwareId(String(el?.hardwareId || el?.id || "").trim()) || String(el?.hardwareId || el?.id || "").trim();
    if (hardwareId) {
      const direct = state.lcdTextByTarget[hardwareId];
      if (direct) return direct;
    }
    for (const [target, payload] of Object.entries(state.lcdTextByTarget || {})) {
      if (lcdTargetMatchesElement(target, el)) return payload || { line1: "", line2: "" };
    }
    return { line1: "", line2: "" };
  }

  function setLcdText(targetSource, line1, line2) {
    const target = canonicalHardwareId(String(targetSource || "").trim()) || String(targetSource || "").trim();
    if (!target) return false;
    const next = {
      line1: String(line1 == null ? "" : line1),
      line2: String(line2 == null ? "" : line2),
    };
    const prev = state.lcdTextByTarget[target];
    if (prev && prev.line1 === next.line1 && prev.line2 === next.line2) return false;
    state.lcdTextByTarget[target] = next;
    const updated = state.elements.some((el) => {
      const kind = String(el?.icon || el?.type || "").trim().toLowerCase();
      if (kind !== "lcd-display") return false;
      return lcdTargetMatchesElement(target, el);
    });
    if (updated) renderTable();
    return updated;
  }

  function handleIncomingEvent(ev) {
    if (!ev) return;
    const evName = String(ev?.name || "").trim().toUpperCase();
    if (evName === "LCD_SET") {
      const target = String(ev?.params?.target || "").trim();
      if (target) {
        setLcdText(target, ev?.params?.line1, ev?.params?.line2);
      }
    }
    if (evName === "LIGHT_SCENE_PLAY") {
      const sceneId = String(ev?.params?.sceneId || "").trim();
      if (sceneId) startLightingScene(sceneId);
    } else if (evName === "LIGHT_SCENE_STOP") {
      const sceneId = String(ev?.params?.sceneId || "*").trim() || "*";
      stopLightingScene(sceneId);
    }
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
      state.canonicalIdByTail = {};
      state.canonicalIds = new Set();
      Object.keys(state.safetyById).forEach((id) => {
        const sid = String(id || "").trim();
        if (!sid) return;
        state.canonicalIds.add(sid);
        const tail = uidTailNorm(sid);
        if (!tail) return;
        if (!state.canonicalIdByTail[tail]) state.canonicalIdByTail[tail] = sid;
      });
    } catch (_) {
      state.safetyById = {};
      state.canonicalIdByTail = {};
      state.canonicalIds = new Set();
    }
  }

  async function loadRules() {
    const r = await fetch("/api/rules/list", { credentials: "same-origin" });
    if (!r.ok) return;
    const data = await r.json();
    const rules = data && data.rules ? data.rules : [];
    const bySource = {};
    const triggerByTargetGesture = {};
    const actionByGesture = {};
    const actionByEvent = {};
    rules.forEach((rule) => {
      const triggerBindings = [];
      (rule.triggers || []).forEach((item) => {
        const name = item.event;
        if (item?.type !== "hardware") return;
        const source = canonicalHardwareId(item.source);
        const gesture = item.fn;
        if (!source || !gesture || !name) return;
        bySource[source] = bySource[source] || {};
        if (!bySource[source][gesture]) bySource[source][gesture] = { name, params: item.params || {} };
        triggerBindings.push({ source, fn: gesture, event: name });
      });
      const groups = rule?.triggerGroups?.groups || [];
      groups.forEach((group) => {
        (group.items || []).forEach((item) => {
          const name = item.event;
          if (item?.type !== "hardware") return;
          const source = canonicalHardwareId(item.source);
          const gesture = item.fn;
          if (!source || !gesture || !name) return;
          bySource[source] = bySource[source] || {};
          if (!bySource[source][gesture]) bySource[source][gesture] = { name, params: item.params || {} };
          triggerBindings.push({ source, fn: gesture, event: name });
        });
      });

      (rule.actions || []).forEach((action) => {
        const rawTarget = action.target || action.params?.device || action.params?.target;
        const target = canonicalHardwareId(rawTarget || "") || rawTarget;
        if (!target) return;
        triggerBindings.forEach((tb) => {
          const tkey = `${target}|${tb.fn}`;
          triggerByTargetGesture[tkey] = triggerByTargetGesture[tkey] || [];
          triggerByTargetGesture[tkey].push({
            name: tb.event,
            params: {},
            source: tb.source,
          });
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
    state.ruleTriggersByTargetGesture = triggerByTargetGesture;
    state.ruleActionsBySourceGesture = actionByGesture;
    state.ruleActionsBySourceEvent = actionByEvent;
  }

  async function loadMediaRuntimeData() {
    try {
      const cfgResp = await fetch("/api/media/config", { credentials: "same-origin" });
      if (!cfgResp.ok) {
        state.mediaDisplays = [];
        state.mediaScenes = [];
        renderSceneTriggerCard();
        return;
      }
      const cfgData = await cfgResp.json();
      const scenes = Array.isArray(cfgData?.config?.scenes) ? cfgData.config.scenes : [];
      const displays = Array.isArray(cfgData?.config?.displays) ? cfgData.config.displays : [];
      state.mediaDisplays = displays.filter((row) => row && typeof row === "object" && String(row.id || "").trim());
      state.mediaScenes = scenes.filter((scene) => scene && typeof scene === "object" && String(scene.id || "").trim());
    } catch (_) {
      state.mediaDisplays = [];
      state.mediaScenes = [];
    }
    renderSceneTriggerCard();
  }

  async function loadSystemEvents() {
    try {
      const r = await fetch("/api/events/registry", { credentials: "same-origin" });
      if (!r.ok) {
        state.systemEventCategories = {};
        renderSystemEventsCard();
        return;
      }
      const data = await r.json();
      const categories = data?.triggers?.system?.categories;
      state.systemEventCategories = (categories && typeof categories === "object") ? categories : {};
      if (!state.selectedSystemEvent) {
        const first = Object.values(state.systemEventCategories)
          .find((cat) => Array.isArray(cat?.events) && cat.events.length > 0);
        state.selectedSystemEvent = first && Array.isArray(first.events) ? String(first.events[0] || "").trim() : "";
      }
    } catch (_) {
      state.systemEventCategories = {};
    }
    renderSystemEventsCard();
  }

  async function loadLightingState() {
    try {
      const [stateResp, compiledResp] = await Promise.all([
        fetch("/api/lighting/state", { credentials: "same-origin" }),
        fetch("/api/lighting/compiled", { credentials: "same-origin" }),
      ]);
      if (!stateResp.ok) {
        state.lightingFixtures = [];
        state.lightingScenesById = {};
        state.lightingCompiledScenesById = {};
        return;
      }
      const data = await stateResp.json();
      const compiledData = compiledResp.ok ? await compiledResp.json() : {};
      const fixtures = Array.isArray(data?.fixtures) ? data.fixtures : [];
      const scenes = Array.isArray(data?.config?.scenes) ? data.config.scenes : [];
      const compiledScenes = Array.isArray(compiledData?.compiled?.scenes) ? compiledData.compiled.scenes : [];
      const scenesById = {};
      const compiledById = {};
      scenes.forEach((scene) => {
        const id = String(scene?.id || "").trim();
        if (id) scenesById[id] = scene;
      });
      compiledScenes.forEach((scene) => {
        const id = String(scene?.id || "").trim();
        if (id) compiledById[id] = scene;
      });
      state.lightingFixtures = fixtures;
      state.lightingScenesById = scenesById;
      state.lightingCompiledScenesById = compiledById;
      state.activeLightingScenes = {};
      state.lightingLedHardwareOnById = {};
      state.lightingPixelOverridesByFixtureId = {};
    } catch (_) {
      state.lightingFixtures = [];
      state.lightingScenesById = {};
      state.lightingCompiledScenesById = {};
      state.activeLightingScenes = {};
      state.lightingLedHardwareOnById = {};
      state.lightingPixelOverridesByFixtureId = {};
    }
  }

  function updateLiveviewViewportHeight() {
    if (stagePane && !stagePane.classList.contains("active")) return;
    const wrap = tableEl.parentElement;
    if (!wrap) return;
    if (window.matchMedia("(max-width: 1100px)").matches) {
      wrap.style.height = "50vh";
      if (optionsScroll) optionsScroll.style.removeProperty("max-height");
      return;
    }
    const previewBody = wrap.parentElement;
    if (!previewBody) return;
    const bodyStyles = getComputedStyle(previewBody);
    const bodyPadY = (parseFloat(bodyStyles.paddingTop) || 0) + (parseFloat(bodyStyles.paddingBottom) || 0);
    const available = Math.floor(previewBody.clientHeight - bodyPadY - 8);
    const nextHeight = Math.max(180, available);
    wrap.style.height = `${nextHeight}px`;
    if (optionsScroll) {
      const optionsTop = optionsScroll.getBoundingClientRect().top;
      const footerTop = appFooter ? appFooter.getBoundingClientRect().top : window.innerHeight;
      const optionsAvailable = Math.floor(footerTop - optionsTop - 8);
      const optionsMax = Math.max(220, optionsAvailable);
      optionsScroll.style.maxHeight = `${optionsMax}px`;
    }
  }

  function initListeners() {
    if (typeof ResizeObserver !== "undefined" && tableEl.parentElement) {
      const ro = new ResizeObserver(() => {
        updateLiveviewViewportHeight();
        updateTableSize();
        renderTable();
      });
      ro.observe(tableEl.parentElement);
    } else {
      window.addEventListener("resize", () => {
        updateLiveviewViewportHeight();
        updateTableSize();
        renderTable();
      });
    }
    // Capture at document level so shortcuts still work reliably across
    // nested UI content/focus shifts within the module.
    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("keyup", onKeyUp, true);
    window.addEventListener("blur", () => { releaseActiveKeyGestures(); });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") releaseActiveKeyGestures();
    });
    window.addEventListener("click", () => closeContextMenu(), false);
    window.addEventListener("contextmenu", (evt) => {
      if (!(evt.target instanceof Element) || !evt.target.closest(".emu-el")) closeContextMenu();
    }, false);
    window.addEventListener("resize", () => closeContextMenu(), false);
    document.addEventListener("scroll", () => closeContextMenu(), true);
    window.addEventListener("pagehide", () => {
      releaseActiveKeyGestures();
      closeContextMenu();
      if (state.eventSource) {
        try { state.eventSource.close(); } catch (_) {}
        state.eventSource = null;
      }
      if (state.reconnectTimer) {
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
      }
      if (state.lightingTickTimer) {
        clearInterval(state.lightingTickTimer);
        state.lightingTickTimer = null;
      }
    });
  }

  async function init() {
    applyInitialThemeWatcher();
    loadSystemEventsCollapsedState();
    loadSceneTriggerCollapsedState();
    try {
      await Promise.all([loadState(), loadHardwareSafety(), loadMediaRuntimeData(), loadLightingState(), loadSystemEvents()]);
      normalizeLiveviewHardwareRefs();
      await loadRules();
      updateLiveviewViewportHeight();
      renderTable();
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
