// Vanilla rules builder (triggers, conditions, actions).
(function () {
  const rulesList = document.getElementById("rules-list");
  const editor = document.getElementById("rules-editor");
  const metaCol = document.getElementById("rules-meta");
  const triggersCol = document.getElementById("rules-triggers");
  const conditionsCol = document.getElementById("rules-conditions");
  const actionsCol = document.getElementById("rules-actions");
  const summaryCol = document.getElementById("rules-summary-content");
  const logicCol = document.getElementById("rules-logic");
  const addBtn = document.getElementById("rules-add");
  const saveBtn = document.getElementById("rules-save");
  const syncBtn = document.getElementById("rules-sync");
  const syncModalEl = document.getElementById("rules-sync-modal");
  const syncSpinner = document.getElementById("rules-sync-spinner");
  const syncStatus = document.getElementById("rules-sync-status");
  const syncDetail = document.getElementById("rules-sync-detail");
  const dirtyBadge = document.getElementById("rules-dirty");
  const tagFilter = document.getElementById("rules-tag-filter");
  const tagFilterClear = document.getElementById("rules-filter-clear");
  const keywordFilter = document.getElementById("rules-keyword-filter");
  const rulesCountPill = document.getElementById("rules-count-pill");

  if (!rulesList || !editor) return;

  const API = {
    list: (window.RULES_API && window.RULES_API.list) || "/api/rules/list",
    save: (window.RULES_API && window.RULES_API.save) || "/api/rules/save",
    catalog: (window.RULES_API && window.RULES_API.catalog) || "/api/rules/catalog",
    hardware: (window.RULES_API && window.RULES_API.hardware) || "/api/rules/hardware",
  };
  const EXPANDED_RULE_KEY = "pinballctl.rules.expandedRuleId.v1";
  const EDITOR_TAB_KEY = "pinballctl.rules.editorTab.v1";

  const state = {
    rules: [],
    registry: {},
    tagPalette: [],
    lightingScenes: [],
    lightingFixtures: [],
    audioCues: [],
    mediaScenes: [],
    hardware: [],
    hardwareIndex: {},
    filterTag: "",
    filterKeyword: "",
    expandedId: null,
    activeEditorTab: "metadata",
    dirty: false,
    saving: false,
    savedFingerprint: "",
  };
  let syncTimer = null;
  let syncAttempts = 0;
  let syncStartedAtSec = 0;
  let syncModal = null;
  let bypassUnloadOnce = false;

  const COUNTER_RE = /^[A-Z0-9_]{1,32}$/;
  const PLANNED_ACTIONS = new Set(["led_pattern", "delay"]);

  function uuid() {
    return "r_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function rulesFingerprint(rules) {
    const list = Array.isArray(rules) ? rules : [];
    try {
      return JSON.stringify(list, (key, value) => {
        if (key === "updatedAt" || key === "updatedAtMs" || key === "createdAt") return undefined;
        return value;
      });
    } catch (_) {
      return "";
    }
  }

  function refreshDirtyFromSnapshot() {
    const current = rulesFingerprint(state.rules || []);
    state.dirty = !!state.savedFingerprint && current !== state.savedFingerprint;
    if (saveBtn) saveBtn.disabled = !state.dirty;
  }

  function updateSavedSnapshot() {
    state.savedFingerprint = rulesFingerprint(state.rules || []);
  }

  function markDirty(flag = true) {
    if (!flag) {
      state.dirty = false;
      if (saveBtn) saveBtn.disabled = true;
    } else {
      refreshDirtyFromSnapshot();
    }
    if (state.expandedId) {
      const rule = state.rules.find(r => r.id === state.expandedId);
      if (rule) {
        const errs = computeErrors(rule);
        updateTabBadges(errs);
        renderSummary(rule);
      }
    }
  }

  function markDirtyFromUserEdit() {
    markDirty();
    if (!state.dirty) {
      state.dirty = true;
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  function loadExpandedRuleId() {
    try {
      const raw = window.localStorage.getItem(EXPANDED_RULE_KEY);
      const value = String(raw || "").trim();
      if (value) state.expandedId = value;
    } catch (_) {}
  }

  function saveExpandedRuleId() {
    try {
      const value = String(state.expandedId || "").trim();
      if (!value) window.localStorage.removeItem(EXPANDED_RULE_KEY);
      else window.localStorage.setItem(EXPANDED_RULE_KEY, value);
    } catch (_) {}
  }

  function normalizeEditorTabKey(raw) {
    const key = String(raw || "").trim().toLowerCase();
    if (key === "meta") return "metadata";
    if (key === "metadata" || key === "triggers" || key === "conditions" || key === "actions" || key === "summary") {
      return key;
    }
    return "metadata";
  }

  function loadEditorTabKey() {
    try {
      state.activeEditorTab = normalizeEditorTabKey(window.localStorage.getItem(EDITOR_TAB_KEY));
    } catch (_) {
      state.activeEditorTab = "metadata";
    }
  }

  function saveEditorTabKey(tabKey) {
    const value = normalizeEditorTabKey(tabKey);
    state.activeEditorTab = value;
    try {
      window.localStorage.setItem(EDITOR_TAB_KEY, value);
    } catch (_) {}
  }

  function sanitizeExpandedRuleId() {
    if (!state.expandedId) return;
    const exists = (state.rules || []).some((r) => String(r?.id || "") === String(state.expandedId || ""));
    if (!exists) state.expandedId = null;
    saveExpandedRuleId();
  }

  function setSyncStatus(text, detail, busy) {
    if (syncStatus) syncStatus.textContent = text || "";
    if (syncDetail) syncDetail.textContent = detail || "";
    if (syncSpinner) {
      if (busy) syncSpinner.classList.remove("d-none");
      else syncSpinner.classList.add("d-none");
    }
  }

  function setSyncUiState(mode) {
    if (!syncBtn) return;
    syncBtn.classList.remove("btn-outline-primary", "btn-outline-secondary", "btn-warning", "btn-success", "rules-sync-btn-muted");
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
    const fallback = () => Promise.resolve(window.confirm("You have unsaved changes. Save before syncing rules?"));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });

    return new Promise((resolve) => {
      let resolved = false;
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
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
      };

      if (body) body.textContent = "You have unsaved changes. Save before syncing rules?";
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
    const fallback = () => Promise.resolve(window.confirm("Sync rules to ESP? This will overwrite rules.pd on the ESP."));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });

    return new Promise((resolve) => {
      let resolved = false;
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
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
      };

      if (body) body.textContent = "Sync rules to ESP? This will overwrite rules.pd on the ESP.";
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

  function confirmLeaveWithUnsaved() {
    const fallback = () => Promise.resolve(window.confirm("You have unsaved changes. Leave this page?"));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });

    return new Promise((resolve) => {
      let resolved = false;
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
      const cleanup = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn?.removeEventListener("click", onConfirm);
      };

      if (body) body.textContent = "You have unsaved changes. Leave this page?";
      if (titleEl) titleEl.textContent = "Unsaved Changes";
      if (confirmBtn) {
        confirmBtn.textContent = "Leave";
        confirmBtn.className = "btn btn-warning";
      }
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn?.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  function stopSyncPoll() {
    if (syncTimer) {
      clearInterval(syncTimer);
      syncTimer = null;
    }
    syncAttempts = 0;
    syncStartedAtSec = 0;
  }

  async function pollSyncStatus() {
    syncAttempts += 1;
    if (syncAttempts > 30) {
      setSyncStatus("Timed out", "No response from the bridge. Check that it is running.", false);
      syncBtn.disabled = false;
      stopSyncPoll();
      return;
    }
    try {
      const r = await fetch("/api/rules/sync/status");
      const j = await r.json();
      if (j.bridge && j.bridge.connected === false) {
        setSyncStatus("Bridge offline", "Bridge is not connected to the ESP.", false);
        stopSyncPoll();
        syncBtn.disabled = false;
        return;
      }
      const status = j.blob_status || {};
      const blobAt = Number(j.blob_at || 0) || 0;
      if (syncStartedAtSec > 0 && blobAt > 0 && blobAt < (syncStartedAtSec - 0.25)) {
        return;
      }
      if (status.blobType && status.blobType !== "rules") {
        return;
      }
      if (!status.state) return;
      if (status.state === "done" && status.ok) {
        setSyncStatus("Verifying…", "Checking upload result…", true);
        setTimeout(() => {
          setSyncStatus("Sync complete", "Rules uploaded to the ESP.", false);
          refreshSyncWarning();
        }, 300);
        stopSyncPoll();
        syncBtn.disabled = false;
        return;
      }
      if (status.state === "error") {
        setSyncStatus("Sync failed", status.error || "unknown", false);
        stopSyncPoll();
        syncBtn.disabled = false;
        return;
      }
      if (status.state === "begin") {
        setSyncStatus("Uploading to ESP…", `Sending ${status.size || "blob"} bytes…`, true);
      }
    } catch (e) {
      setSyncStatus("Sync failed", "Unable to read sync status.", false);
      stopSyncPoll();
      syncBtn.disabled = false;
    }
  }

  function canonicalTagName(name) {
    return String(name || "").trim().toLowerCase();
  }

  function isHexColor(v) {
    return /^#[0-9a-f]{6}$/i.test(String(v || "").trim());
  }

  function generatedTagColor(idx) {
    // Deterministic fallback colors once palette is exhausted.
    const hue = (idx * 137.508) % 360;
    return `hsl(${hue.toFixed(1)} 65% 46%)`;
  }

  function buildTagColorMap() {
    const pal = Array.isArray(state.tagPalette) ? state.tagPalette : [];
    const keysInOrder = [];
    const seenKeys = new Set();
    (state.rules || []).forEach((r) => {
      (r.tags || []).forEach((t) => {
        const key = canonicalTagName(t.name);
        if (!key || seenKeys.has(key)) return;
        seenKeys.add(key);
        keysInOrder.push(key);
      });
    });

    const map = {};
    const used = new Set();

    // First pass: keep existing explicit colors where they are unique.
    (state.rules || []).forEach((r) => {
      (r.tags || []).forEach((t) => {
        const key = canonicalTagName(t.name);
        const c = String(t.color || "").trim();
        if (!key || map[key] || !isHexColor(c) || used.has(c.toLowerCase())) return;
        map[key] = c;
        used.add(c.toLowerCase());
      });
    });

    // Second pass: consume unused palette colors.
    keysInOrder.forEach((key) => {
      if (map[key]) return;
      const pick = pal.find((c) => isHexColor(c) && !used.has(String(c).toLowerCase()));
      if (pick) {
        map[key] = pick;
        used.add(String(pick).toLowerCase());
      }
    });

    // Third pass: synthesize unique deterministic colors.
    let gen = 0;
    keysInOrder.forEach((key) => {
      if (map[key]) return;
      let c = generatedTagColor(gen++);
      while (used.has(String(c).toLowerCase())) c = generatedTagColor(gen++);
      map[key] = c;
      used.add(String(c).toLowerCase());
    });

    return map;
  }

  function colorForTag(name) {
    const key = canonicalTagName(name);
    if (!key) return "#a5a5a5";
    const map = buildTagColorMap();
    return map[key] || "#a5a5a5";
  }

  function normalizeRule(rule) {
    if (!rule.id) rule.id = uuid();
    rule.tags = rule.tags || [];
    rule.logic = rule.logic || "ALL";
    rule.conditionLogic = rule.conditionLogic || "ALL";
    rule.triggers = rule.triggers || [];
    rule.conditions = rule.conditions || [];
    rule.actions = rule.actions || [];
    if (!rule.triggerGroups || typeof rule.triggerGroups !== "object") {
      rule.triggerGroups = { logic: rule.logic || "ALL", groups: [] };
    }
    rule.triggerGroups.logic = rule.triggerGroups.logic || rule.logic || "ALL";
    rule.triggerGroups.groups = Array.isArray(rule.triggerGroups.groups) ? rule.triggerGroups.groups : [];
    if (!rule.triggerGroups.groups.length && rule.triggers.length) {
      rule.triggerGroups.groups.push({ logic: rule.logic || "ALL", windowMs: 750, items: rule.triggers });
    }
    rule.triggerGroups.groups.forEach((g) => {
      g.logic = g.logic || "ALL";
      g.windowMs = Number.isFinite(Number(g.windowMs)) ? Number(g.windowMs) : 750;
      g.items = Array.isArray(g.items) ? g.items : [];
    });

    if (!rule.conditionGroups || typeof rule.conditionGroups !== "object") {
      rule.conditionGroups = { logic: rule.conditionLogic || "ALL", groups: [] };
    }
    rule.conditionGroups.logic = rule.conditionGroups.logic || rule.conditionLogic || "ALL";
    rule.conditionGroups.groups = Array.isArray(rule.conditionGroups.groups) ? rule.conditionGroups.groups : [];
    if (!rule.conditionGroups.groups.length && rule.conditions.length) {
      rule.conditionGroups.groups.push({ logic: rule.conditionLogic || "ALL", items: rule.conditions });
    }
    rule.conditionGroups.groups.forEach((g) => {
      g.logic = g.logic || "ALL";
      g.items = Array.isArray(g.items) ? g.items : [];
    });

    rule.enabled = rule.enabled !== false;
    rule.notes = rule.notes || "";
    rule.actions = (rule.actions || []).map(actionToEditorShape);
    (rule.actions || []).forEach((a) => applyActionFieldDefaults(a, a?.type));
    (rule.tags || []).forEach((t) => {
      t.color = colorForTag(t.name || "");
    });
    (rule.triggers || []).forEach((t) => {
      if (t.type === "game" || t.type === "gameplay") t.type = "system";
    });
  }

  function normalizeEventName(raw) {
    return (raw || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  const BUTTON_GESTURE_FNS = new Set([
    "PRESSED",
    "RELEASED",
    "CLICKED",
    "DOUBLE_CLICKED",
    "HELD",
    "REPEAT_WHILE_HELD",
  ]);

  function canonicalHardwareTriggerEvent(device, fn, priorEvent) {
    const fnKey = String(fn || "").trim().toUpperCase();
    const prev = normalizeEventName(priorEvent || "");
    let base = prev
      .replace(/_N_DOUBLE_CLICKED$/, "")
      .replace(/_DOUBLE_CLICKED$/, "")
      .replace(/_REPEAT_WHILE_HELD$/, "")
      .replace(/_CLICKED$/, "")
      .replace(/_RELEASED$/, "")
      .replace(/_HELD$/, "")
      .replace(/_PRESSED$/, "");
    if (base.endsWith("_N")) base = base.slice(0, -2);

    if (!base) {
      const devBase = normalizeEventName(device?.eventBase || device?.friendly || device?.id || "");
      base = devBase.endsWith("_N") ? devBase.slice(0, -2) : devBase;
    }

    if (!base) return "";
    if (BUTTON_GESTURE_FNS.has(fnKey)) return `${base}_PRESSED`;
    return normalizeEventName(priorEvent || `${base}_${fnKey}`);
  }

  function normalizeCounterName(raw) {
    return (raw || "")
      .toUpperCase()
      .replace(/[\s-]+/g, "_")
      .replace(/[^A-Z0-9_]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function actionToEditorShape(action) {
    if (!action || typeof action !== "object") return action;
    if (action.type === "set_lighting_pixels") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      const fixtureId = String(action.target || params.fixtureId || "").trim();
      const rawIndexes = params.pixelIndexes;
      const parsedIndexes = Array.isArray(rawIndexes)
        ? rawIndexes.map((v) => Number(v)).filter((v) => Number.isInteger(v) && v >= 0)
        : String(rawIndexes || "")
            .split(",")
            .map((v) => v.trim())
            .filter((v) => v !== "")
            .map((v) => Number(v))
            .filter((v) => Number.isInteger(v) && v >= 0);
      const pixelIndexes = parsedIndexes.join(",");
      return {
        ...action,
        target: fixtureId,
        params: {
          ...params,
          fixtureId,
          pixelIndexes,
          color: String(params.color || "#ffffff"),
          brightness: Number.isFinite(Number(params.brightness)) ? Number(params.brightness) : 1,
        },
      };
    }
    if (action.type === "set_lcd_text") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      const device = String(action.target || params.device || params.lcdId || "").trim();
      return {
        ...action,
        target: device,
        params: {
          ...params,
          device,
          lcdId: device,
          line1: String(params.line1 || ""),
          line2: String(params.line2 || ""),
          clearFirst: !!params.clearFirst,
        },
      };
    }
    if (action.type === "set_output") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      if (String(params.value || "").toUpperCase() === "PULSE") {
        const pulseMsRaw = params.pulseMs ?? params.ms ?? params.durationMs ?? "";
        return {
          ...action,
          type: "pulse",
          params: {
            durationMs: pulseMsRaw,
          },
        };
      }
      return action;
    }
    if (action.type !== "pulse") return action;
    const params = action.params && typeof action.params === "object" ? action.params : {};
    const pulseMsRaw = params.durationMs ?? params.pulseMs ?? params.ms ?? "";
    return {
      ...action,
      type: "pulse",
      params: {
        durationMs: pulseMsRaw,
      },
    };
  }

  function actionToSavedShape(action) {
    if (!action || typeof action !== "object") return action;
    if (action.type === "set_lighting_pixels") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      const fixtureId = String(action.target || params.fixtureId || "").trim();
      const rawIndexes = params.pixelIndexes;
      const parsedIndexes = Array.isArray(rawIndexes)
        ? rawIndexes.map((v) => Number(v)).filter((v) => Number.isInteger(v) && v >= 0)
        : String(rawIndexes || "")
            .split(",")
            .map((v) => v.trim())
            .filter((v) => v !== "")
            .map((v) => Number(v))
            .filter((v) => Number.isInteger(v) && v >= 0);
      const pixelIndexes = parsedIndexes.join(",");
      const brightnessRaw = Number(params.brightness);
      const brightness = Number.isFinite(brightnessRaw) ? Math.max(0, Math.min(1, brightnessRaw)) : 1;
      return {
        ...action,
        target: fixtureId,
        params: {
          ...params,
          fixtureId,
          pixelIndexes,
          color: String(params.color || "#ffffff"),
          brightness,
        },
      };
    }
    if (action.type === "set_lcd_text") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      const device = String(action.target || params.device || params.lcdId || "").trim();
      return {
        ...action,
        target: device,
        params: {
          ...params,
          device,
          lcdId: device,
          line1: String(params.line1 || ""),
          line2: String(params.line2 || ""),
          clearFirst: !!params.clearFirst,
        },
      };
    }
    if (action.type === "pulse") {
      const params = action.params && typeof action.params === "object" ? action.params : {};
      const pulseMsRaw = params.durationMs ?? params.pulseMs ?? params.ms ?? "";
      const nextParams = { ...params };
      delete nextParams.ms;
      delete nextParams.pulseMs;
      return {
        ...action,
        type: "pulse",
        params: {
          ...nextParams,
          durationMs: pulseMsRaw,
        },
      };
    }
    if (action.type !== "set_output") return action;
    const params = action.params && typeof action.params === "object" ? action.params : {};
    if (String(params.value || "").toUpperCase() !== "PULSE") return action;
    const pulseMsRaw = params.pulseMs ?? params.ms ?? params.durationMs ?? "";
    return {
      ...action,
      type: "pulse",
      params: {
        durationMs: pulseMsRaw,
      },
    };
  }

  function isValidCounterName(name) {
    return COUNTER_RE.test(name || "");
  }

  function knownCounters() {
    const out = new Set();
    (state.rules || []).forEach((rule) => {
      (rule.conditions || []).forEach((c) => {
        if (c?.type === "counter" && c.key && isValidCounterName(c.key)) out.add(c.key);
      });
      (rule.actions || []).forEach((a) => {
        if ((a?.type === "set_counter" || a?.type === "inc_counter") && a.target && isValidCounterName(a.target)) out.add(a.target);
      });
      const cgroups = rule.conditionGroups?.groups || [];
      cgroups.forEach((g) => (g.items || []).forEach((c) => {
        if (c?.type === "counter" && c.key && isValidCounterName(c.key)) out.add(c.key);
      }));
      (rule.actions || []).forEach((a) => {
        if ((a?.type === "set_counter" || a?.type === "inc_counter") && a.target && isValidCounterName(a.target)) out.add(a.target);
      });
    });
    return Array.from(out).sort((a, b) => a.localeCompare(b));
  }

  function actionTypeOptions(includePlanned) {
    const actions = actionTypes();
    return Object.entries(actions).filter(([key, meta]) => {
      if (includePlanned) return true;
      if (meta?.planned) return false;
      if (PLANNED_ACTIONS.has(key)) return false;
      return true;
    }).map(([key, meta]) => ({ value: key, label: meta.label || key }));
  }

  function hardwareInputs() {
    return (state.hardware || []).filter(d => d.direction === "input");
  }

  function hardwareOutputs() {
    return (state.hardware || []).filter(d => d.direction === "output");
  }

  function hardwareLcds() {
    return (state.hardware || []).filter(d => d.deviceClass === "lcd" || d.direction === "display");
  }

  function hardwareById(id) {
    return state.hardwareIndex[id] || null;
  }

  function hardwareEventsForClass(cls) {
    const hw = state.registry?.triggers?.hardware?.deviceClasses || {};
    const meta = hw[cls];
    return (meta && meta.events) || [];
  }

  function systemCategories() {
    return state.registry?.triggers?.system?.categories || {};
  }

  function systemEvents(category) {
    const cats = systemCategories();
    const entry = cats[category];
    return entry ? entry.events || [] : [];
  }

  function conditionTypes() {
    return state.registry?.conditions || {};
  }

  function actionTypes() {
    return state.registry?.actions || {};
  }

  function actionMeta(actionType) {
    const key = String(actionType || "").trim();
    if (!key) return null;
    const actions = actionTypes();
    return actions[key] || null;
  }

  function actionUi(actionType) {
    return actionMeta(actionType)?.ui || null;
  }

  function actionTypeForPathKey(pathKey) {
    const key = String(pathKey || "").trim();
    if (!key) return "";
    const actions = actionTypes();
    for (const [type, meta] of Object.entries(actions)) {
      if (String(meta?.ui?.pathKey || "").trim() === key) return type;
    }
    return "";
  }

  function actionFieldVisible(act, field) {
    const cond = field?.visibleWhen;
    if (!cond || typeof cond !== "object") return true;
    const bind = String(cond.bind || "").trim();
    if (!bind) return true;
    const expected = cond.equals;
    const actual = readActionBind(act, bind);
    return String(actual ?? "") === String(expected ?? "");
  }

  function readActionBind(act, bind) {
    const key = String(bind || "").trim();
    if (!key) return undefined;
    if (key === "target") return act.target;
    if (key === "type") return act.type;
    if (key.startsWith("params.")) {
      const p = key.slice(7);
      return act.params?.[p];
    }
    return act[key];
  }

  function writeActionBind(act, bind, value) {
    const key = String(bind || "").trim();
    if (!key) return;
    if (key === "target") {
      act.target = value;
      return;
    }
    if (key === "type") {
      act.type = value;
      return;
    }
    if (key.startsWith("params.")) {
      const p = key.slice(7);
      act.params = act.params || {};
      act.params[p] = value;
      return;
    }
    act[key] = value;
  }

  function actionFieldOptions(field, act) {
    const source = String(field?.source || "").trim();
    if (source === "hardware.outputs") return hardwareOutputs().map((d) => ({ value: d.id, label: d.friendly }));
    if (source === "hardware.lcds") return hardwareLcds().map((d) => ({ value: d.id, label: d.friendly }));
    if (source === "lighting.scenes") return lightingSceneOptions();
    if (source === "lighting.fixtures") return lightingFixtureOptions();
    if (source === "lighting.fixture_pixels") {
      const fixtureBind = String(field?.fixtureBind || "target");
      const fixtureId = String(readActionBind(act, fixtureBind) || "").trim();
      const fixture = lightingFixtureById(fixtureId);
      const count = Math.max(0, Number(fixture?.pixelCount || 0));
      const out = [];
      for (let i = 0; i < count; i += 1) out.push({ value: String(i), label: String(i) });
      return out;
    }
    if (source === "lighting.tags") {
      const sceneBind = String(field?.sceneBind || "target");
      const sceneId = String(readActionBind(act, sceneBind) || "").trim();
      const scene = lightingSceneById(sceneId);
      const tags = Array.isArray(scene?.tags) ? scene.tags : [];
      return tags.map((t) => ({ value: t.tag, label: `${t.tag} (frame ${t.frame})` }));
    }
    if (source === "audio.cues") return audioCueOptions();
    if (source === "media.scenes") return mediaSceneOptions();
    if (source === "system.categories") {
      return Object.entries(systemCategories()).map(([key, meta]) => ({ value: key, label: meta?.label || key }));
    }
    if (source === "system.events") {
      const categoryBind = String(field?.categoryBind || "params.source");
      const category = String(readActionBind(act, categoryBind) || "").trim();
      return systemEvents(category).map((ev) => ({ value: ev, label: ev }));
    }
    if (source === "conditions.flags") {
      const flags = conditionTypes()?.flag?.flags || [];
      return (Array.isArray(flags) ? flags : []).map((f) => ({ value: String(f), label: String(f) }));
    }
    if (source === "conditions.counters") {
      const counters = new Set((conditionTypes()?.counter?.counters || []).map((c) => String(c)));
      knownCounters().forEach((c) => counters.add(String(c)));
      return Array.from(counters).sort((a, b) => a.localeCompare(b)).map((c) => ({ value: c, label: c }));
    }
    const base = Array.isArray(field?.options) ? field.options : [];
    return base.map((opt) => {
      if (opt && typeof opt === "object") return { value: String(opt.value ?? ""), label: String(opt.label ?? opt.value ?? "") };
      return { value: String(opt ?? ""), label: String(opt ?? "") };
    });
  }

  function coerceActionFieldValue(field, raw) {
    const valueType = String(field?.valueType || "string").trim().toLowerCase();
    if (valueType === "boolean") {
      if (raw === true || raw === "true" || raw === 1 || raw === "1") return true;
      return false;
    }
    if (valueType === "number") {
      const text = String(raw ?? "").trim();
      if (!text) return "";
      const n = Number(text);
      return Number.isFinite(n) ? n : text;
    }
    if (valueType === "integer") {
      const text = String(raw ?? "").trim();
      if (!text) return "";
      const n = Number(text);
      return Number.isFinite(n) ? Math.round(n) : text;
    }
    return String(raw ?? "");
  }

  function applyActionFieldDefaults(act, actionType) {
    const ui = actionUi(actionType);
    const fields = Array.isArray(ui?.fields) ? ui.fields : [];
    fields.forEach((field) => {
      if (!field || typeof field !== "object") return;
      const bind = String(field.bind || "").trim();
      if (!bind) return;
      const existing = readActionBind(act, bind);
      if (existing !== undefined && existing !== null && String(existing).trim() !== "") return;
      if (field.default !== undefined) {
        const value = coerceActionFieldValue(field, field.default);
        writeActionBind(act, bind, value);
        const sync = Array.isArray(field.sync) ? field.sync : [];
        sync.forEach((syncBind) => writeActionBind(act, String(syncBind || ""), value));
        return;
      }
      if (field.autoSelectFirst && String(field.kind || "").toLowerCase() === "select") {
        const opts = actionFieldOptions(field, act);
        if (!opts.length) return;
        const value = coerceActionFieldValue(field, opts[0].value);
        writeActionBind(act, bind, value);
        const sync = Array.isArray(field.sync) ? field.sync : [];
        sync.forEach((syncBind) => writeActionBind(act, String(syncBind || ""), value));
      }
    });
  }

  function renderActionFieldsFromRegistry(act, card) {
    const ui = actionUi(act?.type);
    const fields = Array.isArray(ui?.fields) ? ui.fields : [];
    if (!fields.length) return false;
    const fieldHasDependents = (changedBind) => {
      const bind = String(changedBind || "").trim();
      if (!bind) return false;
      return fields.some((f) => {
        if (!f || typeof f !== "object") return false;
        const visibleBind = String(f?.visibleWhen?.bind || "").trim();
        const sceneBind = String(f?.sceneBind || "").trim();
        const categoryBind = String(f?.categoryBind || "").trim();
        const fixtureBind = String(f?.fixtureBind || "").trim();
        return visibleBind === bind || sceneBind === bind || categoryBind === bind || fixtureBind === bind;
      });
    };
    const row = el("div", "row g-2");
    let rendered = false;
    fields.forEach((field) => {
      if (!actionFieldVisible(act, field)) return;
      const kind = String(field?.kind || "text").trim().toLowerCase();
      if (kind === "help_tokens") {
        const helpCol = el("div", String(field.col || "col-12"));
        const heading = String(field.label || "Placeholders");
        helpCol.appendChild(el("div", "small text-secondary mt-1", `${heading}:`));
        const tokenRow = el("div", "d-flex flex-wrap gap-2 mt-1");
        const tokens = Array.isArray(field.tokens) ? field.tokens : [];
        tokens.forEach((tokenEntry) => {
          const token = String(tokenEntry?.token || "").trim();
          if (!token) return;
          const summary = String(tokenEntry?.summary || "").trim();
          const item = el("span", "d-inline-flex align-items-center gap-1");
          item.appendChild(el("code", "", token));
          if (summary) item.appendChild(el("span", "", summary));
          tokenRow.appendChild(item);
        });
        helpCol.appendChild(tokenRow);
        row.appendChild(helpCol);
        rendered = true;
        return;
      }
      const bind = String(field?.bind || "").trim();
      if (!bind) return;
      const col = el("div", String(field.col || "col-12 col-lg-4"));
      const labelText = String(field?.label || bind);
      if (kind !== "checkbox") col.appendChild(el("label", "form-label", labelText));
      const current = readActionBind(act, bind);
      if (kind === "select") {
        const options = actionFieldOptions(field, act);
        const includeBlank = String(field?.placeholder || "").trim();
        const select = buildSelect(options, String(current ?? ""), includeBlank || null);
        select.dataset.actionBind = bind;
        if (field?.valueType) select.dataset.valueType = String(field.valueType);
        select.addEventListener("input", (e) => {
          const next = coerceActionFieldValue(field, e.target.value);
          writeActionBind(act, bind, next);
          const sync = Array.isArray(field.sync) ? field.sync : [];
          sync.forEach((syncBind) => writeActionBind(act, String(syncBind || ""), next));
          markDirtyFromUserEdit();
        });
        select.addEventListener("change", (e) => {
          const next = coerceActionFieldValue(field, e.target.value);
          writeActionBind(act, bind, next);
          const sync = Array.isArray(field.sync) ? field.sync : [];
          sync.forEach((syncBind) => writeActionBind(act, String(syncBind || ""), next));
          markDirtyFromUserEdit();
          if (fieldHasDependents(bind)) renderEditor();
          renderTable();
        });
        col.appendChild(select);
      } else if (kind === "color") {
        const input = el("input", "form-control form-control-sm");
        input.type = "color";
        input.value = String(current || field.default || "#ffffff");
        input.dataset.actionBind = bind;
        if (field?.valueType) input.dataset.valueType = String(field.valueType);
        input.addEventListener("input", (e) => {
          writeActionBind(act, bind, String(e.target.value || "#ffffff"));
          markDirtyFromUserEdit();
        });
        input.addEventListener("change", (e) => {
          writeActionBind(act, bind, String(e.target.value || "#ffffff"));
          markDirtyFromUserEdit();
          renderTable();
        });
        col.appendChild(input);
      } else if (kind === "range") {
        const wrap = el("div", "d-flex align-items-center gap-2");
        const input = el("input", "form-range");
        input.type = "range";
        if (field.min !== undefined) input.min = String(field.min);
        if (field.max !== undefined) input.max = String(field.max);
        if (field.step !== undefined) input.step = String(field.step);
        input.dataset.actionBind = bind;
        if (field?.valueType) input.dataset.valueType = String(field.valueType);
        const valueNum = Number(current ?? field.default ?? 0);
        input.value = Number.isFinite(valueNum) ? String(valueNum) : "0";
        const valueLbl = el("small", "text-secondary", "");
        const syncLabel = () => {
          const raw = Number(input.value || "0");
          const pct = Math.round(Math.max(0, Math.min(1, raw)) * 100);
          valueLbl.textContent = `${pct}%`;
        };
        syncLabel();
        input.addEventListener("input", () => {
          writeActionBind(act, bind, coerceActionFieldValue(field, input.value));
          syncLabel();
          markDirtyFromUserEdit();
        });
        input.addEventListener("change", () => {
          writeActionBind(act, bind, coerceActionFieldValue(field, input.value));
          syncLabel();
          markDirtyFromUserEdit();
          renderTable();
        });
        wrap.appendChild(input);
        wrap.appendChild(valueLbl);
        col.appendChild(wrap);
      } else if (kind === "number") {
        const input = el("input", "form-control form-control-sm");
        input.type = "number";
        if (field.min !== undefined) input.min = String(field.min);
        if (field.max !== undefined) input.max = String(field.max);
        if (field.step !== undefined) input.step = String(field.step);
        input.dataset.actionBind = bind;
        if (field?.valueType) input.dataset.valueType = String(field.valueType);
        input.value = current ?? "";
        input.placeholder = String(field.placeholder || "");
        input.addEventListener("input", (e) => {
          writeActionBind(act, bind, coerceActionFieldValue(field, e.target.value));
          markDirtyFromUserEdit();
        });
        input.addEventListener("change", () => renderTable());
        col.appendChild(input);
      } else if (kind === "checkbox") {
        const wrap = el("div", "form-check mt-1");
        const input = el("input", "form-check-input");
        input.type = "checkbox";
        input.dataset.actionBind = bind;
        if (field?.valueType) input.dataset.valueType = String(field.valueType);
        const fieldId = `rule-action-field-${Math.random().toString(36).slice(2, 10)}`;
        input.id = fieldId;
        input.checked = !!current;
        const cbLabel = el("label", "form-check-label", labelText);
        cbLabel.setAttribute("for", fieldId);
        input.addEventListener("change", (e) => {
          writeActionBind(act, bind, !!e.target.checked);
          markDirtyFromUserEdit();
          renderTable();
        });
        wrap.appendChild(input);
        wrap.appendChild(cbLabel);
        col.appendChild(wrap);
      } else {
        const input = el("input", "form-control form-control-sm");
        input.type = "text";
        if (field.maxLength !== undefined) input.maxLength = Number(field.maxLength);
        input.placeholder = String(field.placeholder || "");
        input.dataset.actionBind = bind;
        if (field?.valueType) input.dataset.valueType = String(field.valueType);
        input.value = String(current ?? "");
        input.addEventListener("input", (e) => {
          let next = String(e.target.value ?? "");
          if (kind === "event_name") next = normalizeEventName(next);
          writeActionBind(act, bind, next);
          markDirtyFromUserEdit();
        });
        input.addEventListener("change", () => renderTable());
        col.appendChild(input);
      }
      if (field.help) col.appendChild(el("small", "text-secondary d-block mt-1", String(field.help)));
      row.appendChild(col);
      rendered = true;
    });
    if (rendered) card.appendChild(row);
    return rendered;
  }

  function validateActionFromRegistry(act) {
    const ui = actionUi(act?.type);
    const fields = Array.isArray(ui?.fields) ? ui.fields : [];
    for (const field of fields) {
      if (!actionFieldVisible(act, field)) continue;
      const bind = String(field?.bind || "").trim();
      if (!bind) continue;
      const value = readActionBind(act, bind);
      if (field?.required) {
        const missing = Array.isArray(value)
          ? value.length === 0
          : value === undefined || value === null || String(value).trim() === "";
        if (missing) {
          const label = String(field?.label || bind || "value");
          return String(field?.requiredMessage || `Provide ${label}.`);
        }
      }
      if (field?.min !== undefined && String(value ?? "").trim() !== "") {
        const n = Number(value);
        if (Number.isFinite(n) && n < Number(field.min)) {
          const label = String(field?.label || bind || "value");
          return `${label} must be at least ${field.min}.`;
        }
      }
      if (field?.max !== undefined && String(value ?? "").trim() !== "") {
        const n = Number(value);
        if (Number.isFinite(n) && n > Number(field.max)) {
          const label = String(field?.label || bind || "value");
          return `${label} must be at most ${field.max}.`;
        }
      }
      if (field?.pattern && String(value ?? "").trim() !== "") {
        let re = null;
        try {
          re = new RegExp(String(field.pattern));
        } catch (_) {
          re = null;
        }
        if (re && !re.test(String(value))) {
          const label = String(field?.label || bind || "value");
          return String(field?.patternMessage || `${label} is invalid.`);
        }
      }
    }
    return "";
  }

  function moduleLabel(moduleKey) {
    const raw = String(moduleKey || "").trim();
    if (!raw) return "System";
    return raw.charAt(0).toUpperCase() + raw.slice(1);
  }

  function actionPathCatalog() {
    const out = {};
    const seen = new Set();
    Object.entries(actionTypes()).forEach(([type, meta]) => {
      if (meta?.planned || PLANNED_ACTIONS.has(type)) return;
      const moduleKey = String(meta?.ui?.module || "").trim().toLowerCase();
      const pathKey = String(meta?.ui?.pathKey || "").trim();
      if (!moduleKey || !pathKey) return;
      const dedupe = `${moduleKey}::${pathKey}`;
      if (seen.has(dedupe)) return;
      seen.add(dedupe);
      if (!out[moduleKey]) out[moduleKey] = [];
      out[moduleKey].push({
        key: pathKey,
        label: String(meta?.ui?.actionLabel || meta?.label || type),
      });
    });
    return out;
  }

  function actionPathForAction(act) {
    const type = String(act?.type || "").trim();
    const meta = actionMeta(type);
    const uiModule = String(meta?.ui?.module || "").trim().toLowerCase();
    const uiPath = String(meta?.ui?.pathKey || "").trim();
    if (uiPath) return { module: uiModule || "system", key: uiPath };
    const catalog = actionPathCatalog();
    const firstModule = Object.keys(catalog)[0] || "system";
    const firstPath = catalog[firstModule]?.[0]?.key || "";
    return { module: firstModule, key: firstPath };
  }

  function applyActionPath(act, pathKey) {
    if (!act || typeof act !== "object") return;
    const mappedType = actionTypeForPathKey(pathKey);
    if (!mappedType) return;
    if (String(act.type || "") !== mappedType) {
      act.target = "";
      act.params = {};
    }
    act.type = mappedType;
    act.params = (act.params && typeof act.params === "object") ? act.params : {};
    applyActionFieldDefaults(act, mappedType);
  }

  function triggerSummary(rule) {
    const groups = rule.triggerGroups?.groups || [];
    if (!groups.length) return "(no triggers)";
    const joiner = (rule.triggerGroups?.logic === "ANY") ? " OR " : " AND ";
    return groups.map((g) => {
      const inner = (g.items || []).map((t) => {
        if (t.type === "hardware") {
          const hw = hardwareById(t.source || "");
          const label = hw?.friendly || t.source || "Device";
          return `${label} ${t.fn || ""}`.trim();
        }
        if (t.type === "system") return t.event || "System Event";
        if (t.type === "custom") return t.event || "Custom Event";
        return t.event || "Trigger";
      }).join(g.logic === "ANY" ? " OR " : " AND ");
      return `(${inner || "..."})`;
    }).join(joiner);
  }

  function conditionSummary(rule) {
    const groups = rule.conditionGroups?.groups || [];
    if (!groups.length) return "(no conditions)";
    const joiner = (rule.conditionGroups?.logic === "ANY") ? " OR " : " AND ";
    return groups.map((g) => {
      const inner = (g.items || []).map((c) => {
        if (!c) return "Condition";
        if (c.type === "flag") return `${c.key || "Flag"} ${c.value ? "is true" : "is false"}`;
        if (c.type === "counter") return `${c.key || "Counter"} ${c.op || "=="} ${c.value ?? ""}`.trim();
        if (c.type === "time_since_event") return `Time since ${c.key || "event"} ${c.op || ">="} ${c.value ?? ""}ms`;
        if (c.type === "device_state") return `${c.key || "Device"} ${c.value || ""}`.trim();
        return c.key || "Condition";
      }).join(g.logic === "ANY" ? " OR " : " AND ");
      return `(${inner || "..."})`;
    }).join(joiner);
  }

  function actionSummary(rule) {
    if (!rule.actions || !rule.actions.length) return ["(no actions)"];
    return rule.actions.map((a) => {
      const meta = actionTypes()[a.type];
      const label = meta?.label || a.type || "Action";
      if (a.type === "apply_lighting_scene") {
        const sceneId = String(a.target || a.params?.sceneId || "").trim();
        const scene = lightingSceneById(sceneId);
        const sceneName = scene?.title || sceneId || "scene";
        const startMode = String(a.params?.startMode || "play").toLowerCase() === "paused" ? "paused" : "play";
        const startAt = String(a.params?.startAt || "start").toLowerCase();
        let atText = "from start";
        if (startAt === "frame") {
          const n = Number(a.params?.startFrame || 0);
          if (Number.isFinite(n) && n > 0) atText = `from frame ${Math.round(n)}`;
        } else if (startAt === "tag") {
          const tag = String(a.params?.startTag || "").trim();
          if (tag) atText = `from tag ${tag}`;
        }
        return `${label} → ${sceneName} (${atText}, ${startMode})`;
      }
      if (a.type === "play_audio_cue") {
        const cueId = String(a.target || a.params?.cueId || "").trim();
        const cue = audioCueById(cueId);
        const cueName = cue?.name || cueId || "cue";
        const playMode = String(a.params?.playMode || "layer").toLowerCase();
        return `${label} → ${cueName} (${playMode})`;
      }
      if (a.type === "stop_audio_cue") {
        const cueId = String(a.target || a.params?.cueId || "").trim();
        if (!cueId) return `${label} → all cues`;
        const cue = audioCueById(cueId);
        const cueName = cue?.name || cueId;
        return `${label} → ${cueName}`;
      }
      if (a.type === "media_play_scene" || a.type === "media_stop_scene") {
        const sceneId = String(a.target || a.params?.sceneId || "").trim();
        const scene = mediaSceneById(sceneId);
        const sceneName = scene?.name || sceneId || "scene";
        return `${label} → ${sceneName}`;
      }
      if (a.type === "media_stop_all") return `${label} → all scenes`;
      if (a.type === "toggle_audio_cue") {
        const cueId = String(a.target || a.params?.cueId || "").trim();
        const cue = audioCueById(cueId);
        const cueName = cue?.name || cueId || "cue";
        const playMode = String(a.params?.playMode || "layer").toLowerCase();
        return `${label} → ${cueName} (${playMode})`;
      }
      if (a.type === "inc_counter") {
        const target = String(a.target || "").trim() || "counter";
        const deltaRaw = String(a.params?.delta ?? "").trim();
        const deltaNum = Number(deltaRaw);
        if (deltaRaw && Number.isFinite(deltaNum) && deltaNum < 0) {
          return `Decrease Counter → ${target} (${Math.abs(deltaNum)})`;
        }
        return `${label} → ${target} (${deltaRaw || "1"})`;
      }
      if (a.type === "emit_event") return `${label} ${a.target || ""}`.trim();
      if (a.type === "set_lcd_text") {
        const target = String(a.target || a.params?.device || a.params?.lcdId || "").trim();
        const lcd = hardwareById(target);
        const lcdName = lcd?.friendly || target || "LCD";
        const line1 = String(a.params?.line1 || "").trim();
        const line2 = String(a.params?.line2 || "").trim();
        const text = [line1, line2].filter(Boolean).join(" | ");
        return `${label} → ${lcdName}${text ? ` (${text})` : ""}`;
      }
      if (a.type === "set_lighting_pixels") {
        const fixtureId = String(a.target || a.params?.fixtureId || "").trim();
        const fixture = lightingFixtureById(fixtureId);
        const fixtureName = fixture?.title || fixtureId || "fixture";
        const indexes = Array.isArray(a.params?.pixelIndexes)
          ? a.params.pixelIndexes
          : String(a.params?.pixelIndexes || "")
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean);
        const color = String(a.params?.color || "#ffffff").trim();
        const brightness = Number(a.params?.brightness);
        const btxt = Number.isFinite(brightness) ? ` @ ${(brightness * 100).toFixed(0)}%` : "";
        return `${label} → ${fixtureName} [${indexes.join(", ")}] ${color}${btxt}`.trim();
      }
      if (a.target) {
        const hw = hardwareById(a.target);
        const friendly = hw?.friendly || a.target;
        return `${label} → ${friendly}`;
      }
      return label;
    });
  }

  function renderTagOptions() {
    const all = {};
    state.rules.forEach(r => (r.tags || []).forEach(t => {
      if (!t.name) return;
      if (!all[t.name]) all[t.name] = { tag: t, count: 0 };
      all[t.name].count += 1;
    }));
    tagFilter.innerHTML = '<option value="">All Tags</option>';
    Object.values(all)
      .sort((a, b) => a.tag.name.localeCompare(b.tag.name))
      .forEach(({ tag, count }) => {
      const opt = document.createElement("option");
      opt.value = tag.name;
      opt.textContent = `${tag.name} (${count})`;
      tagFilter.appendChild(opt);
    });
    tagFilter.value = state.filterTag || "";
    updateFilterClear();
  }

  function updateFilterClear() {
    const active = !!(state.filterTag || state.filterKeyword);
    tagFilterClear?.classList.toggle("d-none", !active);
  }

  function filteredRules() {
    const keyword = (state.filterKeyword || "").trim().toLowerCase();
    return (state.rules || []).filter((r) => {
      if (state.filterTag && !(r.tags || []).some(t => t.name === state.filterTag)) return false;
      if (keyword) {
        const hay = `${r.name || ""} ${r.notes || ""}`.toLowerCase();
        if (!hay.includes(keyword)) return false;
      }
      return true;
    });
  }

  function renderTable() {
    rulesList.innerHTML = "";
    if (editor && editor.parentElement) editor.parentElement.removeChild(editor);
    editor.classList.add("d-none");
    const list = filteredRules();
    if (rulesCountPill) rulesCountPill.textContent = `Rules: ${(state.rules || []).length}`;
    list.forEach((rule) => {
      normalizeRule(rule);
      const isOpen = state.expandedId === rule.id;
      const card = el("div", `rules-rule-card${isOpen ? " is-expanded" : ""}`);
      card.dataset.ruleId = rule.id;

      const head = el("div", "rules-rule-head");
      const expBtn = document.createElement("button");
      expBtn.type = "button";
      expBtn.className = "btn btn-sm btn-outline-secondary rules-rule-toggle";
      expBtn.innerHTML = `<i class="fa ${isOpen ? "fa-chevron-down" : "fa-chevron-right"}"></i>`;
      expBtn.setAttribute("aria-label", isOpen ? "Collapse" : "Expand");
      expBtn.addEventListener("click", (e) => { e.stopPropagation(); toggleRow(rule.id); });
      head.appendChild(expBtn);

      const summary = el("div", "rules-rule-summary");
      const titleRow = el("div", "rules-rule-title-row");
      const dot = document.createElement("span");
      dot.className = `rules-enabled-dot ${rule.enabled ? "on" : "off"}`;
      dot.setAttribute("title", rule.enabled ? "Enabled" : "Disabled");
      const nameTxt = document.createElement("div");
      nameTxt.textContent = rule.name || "Untitled Rule";
      nameTxt.className = `fw-semibold ${rule.enabled ? "" : "text-secondary"}`.trim();
      titleRow.appendChild(dot);
      titleRow.appendChild(nameTxt);
      summary.appendChild(titleRow);

      const pillsLine = el("div", "rules-rule-pills-line");
      const counts = el("div", "rules-rule-counts");
      const trigCount = (rule.triggerGroups?.groups || []).reduce((sum, g) => sum + (g.items || []).length, 0);
      const condCount = (rule.conditionGroups?.groups || []).reduce((sum, g) => sum + (g.items || []).length, 0);
      const actCount = (rule.actions || []).length;
      const makeCountPill = (label, count, tabKey) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "badge rounded-pill rules-count-pill rules-count-pill-btn";
        btn.innerHTML = `<span class="rules-count-label">${label}</span><span class="rules-count-num">${count}</span>`;
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          openRuleWithTab(rule.id, tabKey);
        });
        return btn;
      };
      counts.appendChild(makeCountPill("Triggers", trigCount, "triggers"));
      counts.appendChild(makeCountPill("Conditions", condCount, "conditions"));
      counts.appendChild(makeCountPill("Actions", actCount, "actions"));
      pillsLine.appendChild(counts);

      const tagsWrap = document.createElement("div");
      tagsWrap.className = "rules-rule-tags";
      (rule.tags || []).forEach((t) => {
        const chip = document.createElement("span");
        chip.className = "badge rounded-pill";
        chip.style.backgroundColor = t.color || "#a5a5a5";
        chip.textContent = t.name;
        tagsWrap.appendChild(chip);
      });
      pillsLine.appendChild(tagsWrap);
      summary.appendChild(pillsLine);
      head.appendChild(summary);

      const actions = el("div", "rules-rule-actions");
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1";
      delBtn.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
      delBtn.setAttribute("aria-label", "Remove rule");
      delBtn.setAttribute("title", "Remove");
      delBtn.setAttribute("data-confirm", "Are you sure?");
      delBtn.addEventListener("click", (e) => { e.stopPropagation(); removeRule(rule.id); });
      actions.appendChild(delBtn);
      head.appendChild(actions);
      head.addEventListener("click", () => toggleRow(rule.id));
      card.appendChild(head);

      if (isOpen) {
        const detail = el("div", "rules-rule-body");
        editor.classList.remove("d-none");
        detail.appendChild(editor);
        card.appendChild(detail);
      }
      rulesList.appendChild(card);
    });
    if (list.length === 0) {
      const empty = el("div", "text-center text-secondary py-3", "No rules yet.");
      rulesList.appendChild(empty);
    }
  }

  function toggleRow(id) {
    state.expandedId = (state.expandedId === id ? null : id);
    saveExpandedRuleId();
    renderTable();
    renderEditor();
  }

  function switchEditorTab(tabKey) {
    const idByKey = {
      metadata: "rules-tab-meta",
      triggers: "rules-tab-triggers",
      conditions: "rules-tab-conditions",
      actions: "rules-tab-actions",
      summary: "rules-tab-summary",
    };
    const activeKey = normalizeEditorTabKey(tabKey);
    const tabId = idByKey[activeKey] || "rules-tab-meta";
    const btn = document.getElementById(tabId);
    if (!btn) return;
    saveEditorTabKey(activeKey);
    if (window.bootstrap?.Tab) {
      window.bootstrap.Tab.getOrCreateInstance(btn).show();
      return;
    }
    btn.click();
  }

  function openRuleWithTab(ruleId, tabKey) {
    if (state.expandedId !== ruleId) {
      state.expandedId = ruleId;
      saveExpandedRuleId();
      renderTable();
      renderEditor();
    }
    switchEditorTab(tabKey);
  }

  function removeRule(id) {
    const idx = (state.rules || []).findIndex(r => r.id === id);
    if (idx >= 0) {
      state.rules.splice(idx, 1);
      if (state.expandedId === id) state.expandedId = null;
      saveExpandedRuleId();
      markDirty();
      renderTable();
      renderEditor();
      renderTagOptions();
    }
  }

  function addValidation(parent, message) {
    if (!message) return;
    const warn = document.createElement("div");
    warn.className = "text-danger small mt-2";
    warn.textContent = message;
    parent.appendChild(warn);
  }

  function buildSelect(options, value, placeholder) {
    const sel = document.createElement("select");
    sel.className = "form-select form-select-sm";
    if (placeholder) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      sel.appendChild(opt);
    }
    options.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = String(o.value ?? "");
      opt.textContent = o.label;
      sel.appendChild(opt);
    });
    if (value !== undefined) sel.value = String(value ?? "");
    return sel;
  }

  function renderEditor() {
    if (!state.expandedId) {
      editor.classList.add("d-none");
      metaCol.innerHTML = "";
      triggersCol.innerHTML = "";
      conditionsCol.innerHTML = "";
      actionsCol.innerHTML = "";
      if (summaryCol) summaryCol.innerHTML = "";
      if (logicCol) logicCol.innerHTML = "";
      updateTabBadges({ triggers: false, conditions: false, actions: false });
      return;
    }
    editor.classList.remove("d-none");
    const rule = state.rules.find(r => r.id === state.expandedId);
    if (!rule) return;
    normalizeRule(rule);

    renderMeta(rule);
    const err = { triggers: false, conditions: false, actions: false };
    err.triggers = renderTriggers(rule);
    err.conditions = renderConditions(rule);
    err.actions = renderActions(rule);
    renderLogic(rule);
    renderSummary(rule);
    updateTabBadges(err);
  }

  function renderMeta(rule) {
    metaCol.innerHTML = "";

    const grid = el("div", "rules-meta-grid");

    const nameInput = el("input", "form-control form-control-sm");
    nameInput.value = rule.name || "";
    nameInput.addEventListener("input", (e) => { rule.name = e.target.value; markDirty(); });
    nameInput.addEventListener("blur", () => { renderTable(); });
    const nameValue = el("div", "");
    nameValue.appendChild(nameInput);
    if (!(rule.name || "").trim()) {
      const warn = el("div", "text-danger small mt-1", "Name is required.");
      nameValue.appendChild(warn);
      nameInput.classList.add("is-invalid");
    } else {
      nameInput.classList.remove("is-invalid");
    }
    grid.appendChild(buildMetaRow("Name", nameValue));

    const enabledWrap = el("div", "form-check mt-1");
    const enabledInput = el("input", "form-check-input");
    enabledInput.type = "checkbox";
    enabledInput.checked = !!rule.enabled;
    enabledInput.addEventListener("change", (e) => { rule.enabled = e.target.checked; markDirty(); renderTable(); });
    const enabledLbl = el("label", "form-check-label", "Rule is active");
    enabledWrap.appendChild(enabledInput);
    enabledWrap.appendChild(enabledLbl);
    grid.appendChild(buildMetaRow("Enabled", enabledWrap));

    const tagsValue = el("div", "");
    const tagsWrap = el("div", "d-flex flex-wrap gap-1 align-items-center rules-tags-inline-chips");
    (rule.tags || []).forEach((t, idx) => {
      const chip = el("span", "badge rounded-pill d-inline-flex align-items-center gap-1 rules-tag-chip");
      chip.style.backgroundColor = t.color || colorForTag(t.name || "");
      const chipText = el("span", "", t.name);
      const removeBtn = el("button", "rules-tag-remove");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", `Remove tag ${t.name}`);
      removeBtn.innerHTML = "&times;";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        (rule.tags || []).splice(idx, 1);
        markDirty();
        renderTable();
        renderMeta(rule);
        renderTagOptions();
      });
      chip.appendChild(chipText);
      chip.appendChild(removeBtn);
      tagsWrap.appendChild(chip);
    });
    const addTagInput = el("input", "form-control form-control-sm");
    addTagInput.placeholder = "Add tag…";
    addTagInput.style.maxWidth = "140px";
    const addTag = () => {
      const val = (addTagInput.value || "").trim();
      if (!val || (rule.tags || []).some(t => t.name.toLowerCase() === val.toLowerCase())) return;
      rule.tags = rule.tags || [];
      rule.tags.push({ name: val, color: colorForTag(val) });
      addTagInput.value = "";
      markDirty();
      renderTable();
      renderMeta(rule);
      renderTagOptions();
    };
    addTagInput.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") addTag();
    });
    const addGroup = el("div", "input-group input-group-sm", "");
    addGroup.style.maxWidth = "160px";
    addGroup.appendChild(addTagInput);
    const addTagBtn = el("button", "btn btn-outline-secondary");
    addTagBtn.type = "button";
    addTagBtn.innerHTML = '<i class="fa fa-plus"></i>';
    addTagBtn.addEventListener("click", (e) => { e.stopPropagation(); addTag(); });
    addGroup.appendChild(addTagBtn);
    const tagsInline = el("div", "rules-tags-inline");
    tagsInline.appendChild(addGroup);
    tagsInline.appendChild(tagsWrap);
    tagsValue.appendChild(tagsInline);
    grid.appendChild(buildMetaRow("Tags", tagsValue));

    const notesArea = el("textarea", "form-control form-control-sm");
    notesArea.rows = 2;
    notesArea.placeholder = "Optional notes about this rule…";
    notesArea.value = rule.notes || "";
    notesArea.addEventListener("input", (e) => { rule.notes = e.target.value; markDirty(); });
    const notesValue = el("div", "");
    notesValue.appendChild(notesArea);
    grid.appendChild(buildMetaRow("Notes", notesValue));

    metaCol.appendChild(grid);
  }

  function buildMetaRow(name, valueNode) {
    const row = el("div", "row g-2 align-items-start rules-meta-row");
    const nameCol = el("div", "col-12 col-md-2 rules-meta-label-col");
    const valueCol = el("div", "col-12 col-md-10 rules-meta-value");
    nameCol.appendChild(el("div", "rules-meta-name", name));
    if (valueNode) valueCol.appendChild(valueNode);
    row.appendChild(nameCol);
    row.appendChild(valueCol);
    return row;
  }

  function updateInlineError(parent, message) {
    if (!parent) return;
    let node = parent.querySelector(".rules-inline-error");
    if (message) {
      if (!node) {
        node = el("div", "text-danger small mt-1 rules-inline-error");
        parent.appendChild(node);
      }
      node.textContent = message;
    } else if (node) {
      node.remove();
    }
  }

  function updateTabBadges(errors) {
    ["triggers", "actions"].forEach((key) => {
      const badge = document.querySelector(`[data-rules-tab-badge="${key}"]`);
      if (!badge) return;
      badge.classList.toggle("d-none", !errors[key]);
    });
  }

  function renderSummary(rule) {
    if (!summaryCol) return;
    summaryCol.innerHTML = "";
    const wrap = el("div", "alert alert-secondary py-2 mt-3 rules-summary", "");
    const title = el("h6", "", "Summary");
    wrap.appendChild(title);

    const trigLine = el("div", "rules-summary-section", "");
    const trigLogic = (rule.triggerGroups?.logic === "ANY") ? "OR" : "ALL";
    const trigLabel = el("span", "rules-summary-label", "Triggers");
    const trigBadge = el("span", "badge rounded-pill bg-primary-subtle text-primary-emphasis ms-2", trigLogic);
    trigLine.appendChild(trigLabel);
    trigLine.appendChild(trigBadge);
    wrap.appendChild(trigLine);
    const trigList = el("div", "rules-summary-group small");
    const tgroups = rule.triggerGroups?.groups || [];
    if (!tgroups.length) {
      trigList.textContent = "— None";
    } else {
      trigList.innerHTML = "";
      tgroups.forEach((g, idx) => {
        const inner = (g.items || []).map((t) => {
          if (t.type === "hardware") {
            const hw = hardwareById(t.source || "");
            const label = hw?.friendly || t.source || "Device";
            return `${label} ${t.fn || ""}`.trim();
          }
          if (t.type === "system") return t.event || "System Event";
          if (t.type === "custom") return t.event || "Custom Event";
          return t.event || "Trigger";
        }).join(g.logic === "ANY" ? " OR " : " AND ");
        const line = el("div", "", "");
        const gBadge = el("span", "badge bg-secondary-subtle text-secondary-emphasis me-2", `Group ${idx + 1}`);
        const gMeta = el("span", "text-secondary", `${g.logic || "ALL"} within, window ${g.windowMs ?? 750}ms`);
        const gText = el("div", "rules-summary-item", inner || "—");
        line.appendChild(gBadge);
        line.appendChild(gMeta);
        line.appendChild(gText);
        trigList.appendChild(line);
      });
    }
    wrap.appendChild(trigList);

    const condLine = el("div", "rules-summary-section", "");
    const condLogic = (rule.conditionGroups?.logic === "ANY") ? "OR" : "ALL";
    const condLabel = el("span", "rules-summary-label", "Conditions");
    const condBadge = el("span", "badge rounded-pill bg-primary-subtle text-primary-emphasis ms-2", condLogic);
    condLine.appendChild(condLabel);
    condLine.appendChild(condBadge);
    wrap.appendChild(condLine);
    const cgroups = rule.conditionGroups?.groups || [];
    const condList = el("div", "rules-summary-group small");
    if (!cgroups.length) {
      condList.textContent = "— None";
    } else {
      cgroups.forEach((g, idx) => {
        const inner = (g.items || []).map((c) => {
          if (!c) return "Condition";
          if (c.type === "flag") return `${c.key || "Flag"} ${c.value ? "is true" : "is false"}`;
          if (c.type === "counter") return `${c.key || "Counter"} ${c.op || "=="} ${c.value ?? ""}`.trim();
          if (c.type === "time_since_event") return `Time since ${c.key || "event"} ${c.op || ">="} ${c.value ?? ""}ms`;
          if (c.type === "device_state") return `${c.key || "Device"} ${c.value || ""}`.trim();
          return c.key || "Condition";
        }).join(g.logic === "ANY" ? " OR " : " AND ");
        const line = el("div", "", "");
        const gBadge = el("span", "badge bg-secondary-subtle text-secondary-emphasis me-2", `Group ${idx + 1}`);
        const gMeta = el("span", "text-secondary", `${g.logic || "ALL"} within`);
        const gText = el("div", "rules-summary-item", inner || "—");
        line.appendChild(gBadge);
        line.appendChild(gMeta);
        line.appendChild(gText);
        condList.appendChild(line);
      });
    }
    wrap.appendChild(condList);

    const actLine = el("div", "rules-summary-section", "");
    const actLabel = el("span", "rules-summary-label", "Actions");
    actLine.appendChild(actLabel);
    wrap.appendChild(actLine);
    const actList = el("div", "rules-summary-group small");
    const acts = actionSummary(rule);
    actList.innerHTML = "";
    acts.forEach((text) => {
      const line = el("div", "rules-summary-item", text);
      actList.appendChild(line);
    });
    wrap.appendChild(actList);

    summaryCol.appendChild(wrap);
  }

  function computeErrors(rule) {
    normalizeRule(rule);
    let triggers = false;
    let actions = false;
    const trigGroups = rule.triggerGroups?.groups || [];
    if (!trigGroups.length) triggers = true;
    trigGroups.forEach((g) => {
      if (!g.items || g.items.length === 0) triggers = true;
      (g.items || []).forEach((t) => {
        if (t.type === "hardware" && (!t.source || !t.fn)) triggers = true;
        if (t.type === "system" && !t.event) triggers = true;
        if (t.type === "custom" && !t.event) triggers = true;
      });
    });
    const acts = rule.actions || [];
    if (!acts.length) actions = true;
    acts.forEach((a) => {
      if (!a.type) actions = true;
      if (validateActionFromRegistry(a)) actions = true;
    });
    return { triggers, actions, conditions: false };
  }

  function renderTriggers(rule) {
    triggersCol.innerHTML = "";
    const title = el("div", "rules-section-title", "Triggers");
    const sub = el("div", "rules-section-sub", "One or more events that fire this rule.");
    triggersCol.appendChild(title);
    triggersCol.appendChild(sub);

    let hasError = false;
    if (!rule.triggerGroups || !rule.triggerGroups.groups || rule.triggerGroups.groups.length === 0) {
      const warn = el("div", "text-warning small mb-2", "No triggers set.");
      triggersCol.appendChild(warn);
    }

    const groups = rule.triggerGroups?.groups || [];
    if (!groups.length) hasError = true;
    groups.forEach((group, gi) => {
      const groupCard = el("div", "border rounded p-2 mb-3 rules-group-card rules-nested-group-card");
      groupCard.appendChild(el("div", "rules-group-title mb-1", `Group ${gi + 1}`));

      const header = el("div", "rules-group-header");
      const titleWrap = el("div", "d-flex align-items-center gap-2");
      titleWrap.appendChild(el("span", "small text-secondary text-nowrap", "Match within group"));
      const logicSel = buildSelect(
        [{ value: "ALL", label: "ALL" }, { value: "ANY", label: "ANY" }],
        group.logic || "ALL"
      );
      logicSel.addEventListener("change", (e) => { group.logic = e.target.value; markDirty(); renderTable(); });
      titleWrap.appendChild(logicSel);
      const windowInput = el("input", "form-control form-control-sm");
      windowInput.type = "number";
      windowInput.placeholder = "Window ms";
      windowInput.style.maxWidth = "140px";
      windowInput.value = group.windowMs ?? 750;
      windowInput.addEventListener("input", (e) => {
        group.windowMs = Number(e.target.value || 0) || 750;
        markDirty();
      });
      titleWrap.appendChild(windowInput);
      header.appendChild(titleWrap);
      const groupRemove = el("button", "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1");
      groupRemove.type = "button";
      groupRemove.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
      groupRemove.addEventListener("click", () => {
        groups.splice(gi, 1);
        markDirty();
        renderEditor();
        renderTable();
      });
      header.appendChild(groupRemove);
      groupCard.appendChild(header);

      if (!group.items || group.items.length === 0) hasError = true;
      (group.items || []).forEach((tg, ti) => {
        const card = el("div", "border rounded p-2 mb-2 rules-nested-item-card rules-trigger-item-card");
        const row1 = el("div", "row g-2 mb-2 align-items-end");
        const typeCol = el("div", "col-6");
        typeCol.appendChild(el("label", "form-label", "Type"));
        const typeSel = buildSelect([
          { value: "hardware", label: "Hardware" },
          { value: "system", label: "System" },
          { value: "custom", label: "Custom" },
        ], tg.type || "hardware");
        typeSel.addEventListener("change", (e) => {
          tg.type = e.target.value;
          tg.source = "";
          tg.fn = "";
          tg.event = "";
          tg.params = {};
          markDirty();
          renderEditor();
          renderTable();
        });
        typeCol.appendChild(typeSel);
        const removeCol = el("div", "col text-end");
        const remBtn = el("button", "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1");
        remBtn.type = "button";
        remBtn.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
        remBtn.addEventListener("click", () => {
          (group.items || []).splice(ti, 1);
          markDirty();
          renderEditor();
          renderTable();
        });
        removeCol.appendChild(remBtn);
        row1.appendChild(typeCol);
        row1.appendChild(removeCol);
        card.appendChild(row1);

        if (tg.type === "hardware") {
          const hwRow = el("div", "row g-2 mb-2");
          const deviceCol = el("div", "col-12 col-lg-6");
          deviceCol.appendChild(el("label", "form-label", "Hardware device"));
          const deviceSel = buildSelect(
            hardwareInputs().map((d) => ({ value: d.id, label: `${d.friendly} (${d.function})` })),
            tg.source || "",
            "Select input…"
          );
          deviceSel.addEventListener("change", (e) => {
            tg.source = e.target.value;
            tg.params = {};
            tg.fn = "";
            tg.event = "";
            markDirty();
            renderEditor();
            renderTable();
          });
          deviceCol.appendChild(deviceSel);

          const eventCol = el("div", "col-12 col-lg-6");
          const eventLabelRow = el("div", "d-flex align-items-center gap-2");
          const eventLabel = el("label", "form-label", "Hardware event");
          const eventHelpBtn = el("button", "btn btn-link p-0 d-inline-flex align-items-center text-decoration-none");
          eventHelpBtn.type = "button";
          eventHelpBtn.setAttribute("data-bs-toggle", "modal");
          eventHelpBtn.setAttribute("data-bs-target", "#rules-hardware-event-modal");
          eventHelpBtn.innerHTML = '<i class="fa fa-circle-question"></i>';
          eventLabelRow.appendChild(eventLabel);
          eventLabelRow.appendChild(eventHelpBtn);
          eventCol.appendChild(eventLabelRow);
          const device = hardwareById(tg.source || "");
          const events = hardwareEventsForClass(device?.deviceClass || "");
          const eventSel = buildSelect(
            events.map((ev) => ({ value: ev.key, label: ev.label || ev.key })),
            tg.fn || "",
            "Select event…"
          );
          eventSel.addEventListener("change", (e) => {
            tg.fn = e.target.value;
            tg.event = canonicalHardwareTriggerEvent(device, tg.fn, tg.event);
            tg.params = tg.params || {};
            markDirty();
            renderEditor();
            renderTable();
          });
          eventCol.appendChild(eventSel);

          hwRow.appendChild(deviceCol);
          hwRow.appendChild(eventCol);
          card.appendChild(hwRow);

          const eventMeta = events.find(ev => ev.key === tg.fn);
          if (eventMeta && Array.isArray(eventMeta.params) && eventMeta.params.length) {
            const paramsRow = el("div", "row g-2");
            eventMeta.params.forEach((paramKey) => {
              const col = el("div", "col-12 col-lg-4");
              col.appendChild(el("label", "form-label", paramKey));
              const input = el("input", "form-control form-control-sm");
              input.type = "number";
              input.placeholder = "ms";
              input.value = tg.params?.[paramKey] ?? "";
              input.addEventListener("input", (e) => {
                tg.params = tg.params || {};
                tg.params[paramKey] = e.target.value;
                markDirty();
              });
              col.appendChild(input);
              paramsRow.appendChild(col);
            });
            card.appendChild(paramsRow);
          }
        } else if (tg.type === "system") {
          const sysRow = el("div", "row g-2 mb-2");
          const catCol = el("div", "col-12 col-lg-4");
          catCol.appendChild(el("label", "form-label", "Category"));
          const cats = systemCategories();
          const catSel = buildSelect(
            Object.entries(cats).map(([key, meta]) => ({ value: key, label: meta.label || key })),
            tg.source || "",
            "Select category…"
          );
          catSel.addEventListener("change", (e) => {
            tg.source = e.target.value;
            tg.event = "";
            markDirty();
            renderEditor();
            renderTable();
          });
          catCol.appendChild(catSel);
          const evCol = el("div", "col-12 col-lg-8");
          evCol.appendChild(el("label", "form-label", "Event"));
          const evSel = buildSelect(
            systemEvents(tg.source || "").map((ev) => ({ value: ev, label: ev })),
            tg.event || "",
            "Select event…"
          );
          evSel.addEventListener("change", (e) => {
            tg.event = e.target.value;
            markDirty();
            renderTable();
          });
          evCol.appendChild(evSel);
          sysRow.appendChild(catCol);
          sysRow.appendChild(evCol);
          card.appendChild(sysRow);
        } else {
          const row = el("div", "row g-2 mb-2");
          const evCol = el("div", "col-12");
          evCol.appendChild(el("label", "form-label", "Event name"));
          const evInput = el("input", "form-control form-control-sm");
          evInput.placeholder = "START_GAME_REQUESTED";
          evInput.value = tg.event || "";
          evInput.addEventListener("input", (e) => {
            tg.event = normalizeEventName(e.target.value);
            markDirty();
          });
          evCol.appendChild(evInput);
          row.appendChild(evCol);
          card.appendChild(row);
        }

        let err = "";
        if (tg.type === "hardware" && (!tg.source || !tg.fn)) err = "Select a hardware device and event.";
        if (tg.type === "system" && !tg.event) err = "Select a system event.";
        if (tg.type === "custom" && !tg.event) err = "Enter a custom event name.";
        if (err) hasError = true;
        addValidation(card, err);
        groupCard.appendChild(card);
      });

      const addTrig = el("button", "btn btn-outline-primary btn-sm", "Add Trigger");
      addTrig.type = "button";
      addTrig.addEventListener("click", () => {
        group.items = group.items || [];
        group.items.push({ type: "hardware", source: "", fn: "", event: "", params: {} });
        markDirty();
        renderEditor();
        renderTable();
      });
      groupCard.appendChild(addTrig);
      triggersCol.appendChild(groupCard);
    });

    const addGroup = el("button", "btn btn-outline-primary btn-sm", "Add Trigger Group");
    addGroup.type = "button";
    addGroup.addEventListener("click", () => {
      rule.triggerGroups = rule.triggerGroups || { logic: "ALL", groups: [] };
      rule.triggerGroups.groups = rule.triggerGroups.groups || [];
      rule.triggerGroups.groups.push({ logic: "ALL", windowMs: 750, items: [] });
      markDirty();
      renderEditor();
      renderTable();
    });
    triggersCol.appendChild(addGroup);

    const groupLogicRow = el("div", "mt-3");
    groupLogicRow.appendChild(el("label", "form-label", "Between trigger groups"));
    const groupLogicSel = buildSelect(
      [{ value: "ALL", label: "ALL" }, { value: "ANY", label: "ANY" }],
      rule.triggerGroups?.logic || "ALL"
    );
    groupLogicSel.addEventListener("change", (e) => {
      rule.triggerGroups.logic = e.target.value;
      markDirty();
      renderTable();
    });
    groupLogicRow.appendChild(groupLogicSel);
    triggersCol.appendChild(groupLogicRow);
    return hasError;
  }

  function renderConditions(rule) {
    conditionsCol.innerHTML = "";
    const title = el("div", "rules-section-title", "Conditions");
    const sub = el("div", "rules-section-sub", "Optional checks that must pass before actions run.");
    conditionsCol.appendChild(title);
    conditionsCol.appendChild(sub);

    let hasError = false;
    if (!rule.actions || rule.actions.length === 0) hasError = true;
    const groups = rule.conditionGroups?.groups || [];
    if (!groups.length) hasError = true;
    groups.forEach((group, gi) => {
      const groupCard = el("div", "border rounded p-2 mb-3 rules-group-card rules-nested-group-card");
      groupCard.appendChild(el("div", "rules-group-title mb-1", `Group ${gi + 1}`));

      const header = el("div", "rules-group-header");
      const titleWrap = el("div", "d-flex align-items-center gap-2");
      titleWrap.appendChild(el("span", "small text-secondary text-nowrap", "Match within group"));
      const logicSel = buildSelect(
        [{ value: "ALL", label: "ALL" }, { value: "ANY", label: "ANY" }],
        group.logic || "ALL"
      );
      logicSel.addEventListener("change", (e) => { group.logic = e.target.value; markDirty(); renderTable(); });
      titleWrap.appendChild(logicSel);
      header.appendChild(titleWrap);
      const groupRemove = el("button", "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1");
      groupRemove.type = "button";
      groupRemove.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
      groupRemove.addEventListener("click", () => {
        groups.splice(gi, 1);
        markDirty();
        renderEditor();
        renderTable();
      });
      header.appendChild(groupRemove);
      groupCard.appendChild(header);

      (group.items || []).forEach((cond, ci) => {
        const card = el("div", "border rounded p-2 mb-2 rules-nested-item-card rules-condition-item-card");
        const row1 = el("div", "row g-2 mb-2 align-items-end");
        const typeCol = el("div", "col-6");
        typeCol.appendChild(el("label", "form-label", "Condition Type"));
        const typeSel = buildSelect(
          Object.entries(conditionTypes()).map(([key, meta]) => ({ value: key, label: meta.label || key })),
          cond.type || "",
          "Select type…"
        );
        typeSel.addEventListener("change", (e) => {
          cond.type = e.target.value;
          cond.key = "";
          cond.op = "";
          cond.value = "";
          cond.params = {};
          markDirty();
          renderEditor();
        });
        typeCol.appendChild(typeSel);
        const removeCol = el("div", "col text-end");
        const remBtn = el("button", "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1");
        remBtn.type = "button";
        remBtn.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
        remBtn.addEventListener("click", () => {
          (group.items || []).splice(ci, 1);
          markDirty();
          renderEditor();
          renderTable();
        });
        removeCol.appendChild(remBtn);
        row1.appendChild(typeCol);
        row1.appendChild(removeCol);
        card.appendChild(row1);

        if (cond.type === "flag") {
          const meta = conditionTypes().flag || {};
          const row = el("div", "row g-2");
          const keyCol = el("div", "col-12 col-lg-5");
          keyCol.appendChild(el("label", "form-label", "Flag"));
          const flags = (meta.flags || []).map(f => ({ value: f, label: f }));
          flags.push({ value: "__custom__", label: "Custom…" });
          const keySel = buildSelect(flags, cond.key || "", "Select flag…");
          keySel.addEventListener("change", (e) => {
            cond.key = e.target.value === "__custom__" ? "" : e.target.value;
            cond.params = cond.params || {};
            cond.params.customKey = e.target.value === "__custom__";
            markDirty();
            renderEditor();
          });
          keyCol.appendChild(keySel);
          if (cond.params?.customKey) {
            const customInput = el("input", "form-control form-control-sm mt-2");
            customInput.placeholder = "CUSTOM_FLAG";
            customInput.value = cond.key || "";
            customInput.addEventListener("input", (e) => { cond.key = normalizeEventName(e.target.value); markDirty(); });
            keyCol.appendChild(customInput);
          }

          const opCol = el("div", "col-6 col-lg-3");
          opCol.appendChild(el("label", "form-label", "Operator"));
          const opSel = buildSelect((meta.operators || ["=="]).map(o => ({ value: o, label: o })), cond.op || "==");
          opSel.addEventListener("change", (e) => { cond.op = e.target.value; markDirty(); });
          opCol.appendChild(opSel);

          const valCol = el("div", "col-6 col-lg-4");
          valCol.appendChild(el("label", "form-label", "Value"));
          const valSel = buildSelect([{ value: "true", label: "True" }, { value: "false", label: "False" }], String(cond.value ?? "false"));
          valSel.addEventListener("change", (e) => { cond.value = e.target.value === "true"; markDirty(); });
          valCol.appendChild(valSel);

          row.appendChild(keyCol);
          row.appendChild(opCol);
          row.appendChild(valCol);
          card.appendChild(row);
        } else if (cond.type === "counter") {
          const meta = conditionTypes().counter || {};
          const row = el("div", "row g-2");
          const keyCol = el("div", "col-12 col-lg-5");
          keyCol.appendChild(el("label", "form-label", "Counter"));
          const counters = (meta.counters || []).map(c => ({ value: c, label: c }));
          counters.push({ value: "__custom__", label: "Custom…" });
        const known = knownCounters();
        known.forEach((c) => { if (!counters.find(o => o.value === c)) counters.push({ value: c, label: c }); });
        const keySel = buildSelect(counters, cond.key || "", "Select counter…");
        keySel.addEventListener("change", (e) => {
          cond.key = e.target.value === "__custom__" ? "" : e.target.value;
          cond.params = cond.params || {};
          cond.params.customKey = e.target.value === "__custom__";
          markDirty();
          renderEditor();
        });
        keyCol.appendChild(keySel);
        if (cond.params?.customKey) {
          const customInput = el("input", "form-control form-control-sm mt-2");
          customInput.placeholder = "CUSTOM_COUNTER";
          customInput.value = cond.key || "";
          customInput.addEventListener("input", (e) => {
            cond.key = normalizeCounterName(e.target.value);
            const valid = !cond.key || isValidCounterName(cond.key);
            customInput.classList.toggle("is-invalid", !valid);
            updateInlineError(keyCol, valid ? "" : "Counter name must be A-Z, 0-9, underscore (1-32).");
            markDirty();
          });
          keyCol.appendChild(customInput);
          if (cond.key && !isValidCounterName(cond.key)) {
            customInput.classList.add("is-invalid");
            updateInlineError(keyCol, "Counter name must be A-Z, 0-9, underscore (1-32).");
          }
        }
        if (known.length) {
          const hint = el("div", "text-secondary small mt-1", `Known counters: ${known.join(", ")}`);
          keyCol.appendChild(hint);
        }

          const opCol = el("div", "col-6 col-lg-3");
          opCol.appendChild(el("label", "form-label", "Operator"));
          const opSel = buildSelect((meta.operators || []).map(o => ({ value: o, label: o })), cond.op || ">=");
          opSel.addEventListener("change", (e) => { cond.op = e.target.value; markDirty(); });
          opCol.appendChild(opSel);

          const valCol = el("div", "col-6 col-lg-4");
          valCol.appendChild(el("label", "form-label", "Value"));
        const valInput = el("input", "form-control form-control-sm");
        valInput.type = "number";
        valInput.value = cond.value ?? "";
        valInput.addEventListener("input", (e) => { cond.value = e.target.value; markDirty(); });
        valCol.appendChild(valInput);

          row.appendChild(keyCol);
          row.appendChild(opCol);
          row.appendChild(valCol);
          card.appendChild(row);
        } else if (cond.type === "time_since_event") {
          const row = el("div", "row g-2");
          const typeCol = el("div", "col-12 col-lg-4");
          typeCol.appendChild(el("label", "form-label", "Event Type"));
          const typeSel = buildSelect([
            { value: "system", label: "System" },
            { value: "hardware", label: "Hardware" },
            { value: "custom", label: "Custom" },
          ], cond.params?.eventType || "system");
          typeSel.addEventListener("change", (e) => {
            cond.params = cond.params || {};
            cond.params.eventType = e.target.value;
            cond.key = "";
            cond.params.source = "";
            cond.params.fn = "";
            markDirty();
            renderEditor();
          });
          typeCol.appendChild(typeSel);

          const eventCol = el("div", "col-12 col-lg-8");
          eventCol.appendChild(el("label", "form-label", "Event"));
          if ((cond.params?.eventType || "system") === "hardware") {
            const wrap = el("div", "d-flex gap-2");
            const deviceSel = buildSelect(
              hardwareInputs().map((d) => ({ value: d.id, label: d.friendly })),
              cond.params?.source || "",
              "Device…"
            );
            deviceSel.addEventListener("change", (e) => {
              cond.params = cond.params || {};
              cond.params.source = e.target.value;
              cond.params.fn = "";
              cond.key = "";
              markDirty();
              renderEditor();
            });
            const device = hardwareById(cond.params?.source || "");
            const events = hardwareEventsForClass(device?.deviceClass || "");
            const eventSel = buildSelect(
              events.map(ev => ({ value: ev.key, label: ev.label || ev.key })),
              cond.params?.fn || "",
              "Event…"
            );
            eventSel.addEventListener("change", (e) => {
              cond.params = cond.params || {};
              cond.params.fn = e.target.value;
              cond.key = canonicalHardwareTriggerEvent(device, cond.params.fn, cond.key);
              markDirty();
              renderEditor();
            });
            wrap.appendChild(deviceSel);
            wrap.appendChild(eventSel);
            eventCol.appendChild(wrap);
          } else if ((cond.params?.eventType || "system") === "custom") {
            const input = el("input", "form-control form-control-sm");
            input.placeholder = "CUSTOM_EVENT";
            input.value = cond.key || "";
            input.addEventListener("input", (e) => { cond.key = normalizeEventName(e.target.value); markDirty(); });
            eventCol.appendChild(input);
          } else {
            const cats = systemCategories();
            const wrap = el("div", "d-flex gap-2");
            const catSel = buildSelect(
              Object.entries(cats).map(([key, meta]) => ({ value: key, label: meta.label || key })),
              cond.params?.source || "",
              "Category…"
            );
            catSel.addEventListener("change", (e) => {
              cond.params = cond.params || {};
              cond.params.source = e.target.value;
              cond.key = "";
              markDirty();
              renderEditor();
            });
            const evSel = buildSelect(
              systemEvents(cond.params?.source || "").map(ev => ({ value: ev, label: ev })),
              cond.key || "",
              "Event…"
            );
            evSel.addEventListener("change", (e) => { cond.key = e.target.value; markDirty(); });
            wrap.appendChild(catSel);
            wrap.appendChild(evSel);
            eventCol.appendChild(wrap);
          }

          const opCol = el("div", "col-6 col-lg-2");
          opCol.appendChild(el("label", "form-label", "Operator"));
          const opSel = buildSelect([{ value: ">", label: ">" }, { value: ">=", label: ">=" }, { value: "<", label: "<" }, { value: "<=", label: "<=" }], cond.op || ">=");
          opSel.addEventListener("change", (e) => { cond.op = e.target.value; markDirty(); });
          opCol.appendChild(opSel);

          const valCol = el("div", "col-6 col-lg-2");
          valCol.appendChild(el("label", "form-label", "ms"));
          const valInput = el("input", "form-control form-control-sm");
          valInput.type = "number";
          valInput.value = cond.value ?? "";
          valInput.addEventListener("input", (e) => { cond.value = e.target.value; markDirty(); });
          valCol.appendChild(valInput);

          row.appendChild(typeCol);
          row.appendChild(eventCol);
          row.appendChild(opCol);
          row.appendChild(valCol);
          card.appendChild(row);
        } else if (cond.type === "device_state") {
          const meta = conditionTypes().device_state || {};
          const row = el("div", "row g-2");
          const deviceCol = el("div", "col-12 col-lg-6");
          deviceCol.appendChild(el("label", "form-label", "Device"));
          const deviceSel = buildSelect(
            hardwareOutputs().map(d => ({ value: d.id, label: `${d.friendly} (${d.function})` })),
            cond.key || "",
            "Select device…"
          );
          deviceSel.addEventListener("change", (e) => {
            cond.key = e.target.value;
            cond.value = "";
            markDirty();
            renderEditor();
          });
          deviceCol.appendChild(deviceSel);

          const stateCol = el("div", "col-12 col-lg-6");
          stateCol.appendChild(el("label", "form-label", "State"));
          const device = hardwareById(cond.key || "");
          const states = meta.states?.[device?.deviceClass || ""] || [];
          const stateSel = buildSelect(states.map(s => ({ value: s, label: s })), cond.value || "", "Select state…");
          stateSel.addEventListener("change", (e) => { cond.value = e.target.value; markDirty(); });
          stateCol.appendChild(stateSel);

          row.appendChild(deviceCol);
          row.appendChild(stateCol);
          card.appendChild(row);
        }

        let err = "";
        if (!cond.type) err = "Select a condition type.";
        if (cond.type === "flag" && !cond.key) err = "Select a flag.";
        if (cond.type === "counter" && !cond.key) err = "Select a counter.";
        if (cond.type === "time_since_event" && !cond.key) err = "Select an event.";
        if (cond.type === "device_state" && (!cond.key || !cond.value)) err = "Select a device and state.";
        if (err) hasError = true;
        addValidation(card, err);
        groupCard.appendChild(card);
      });

      const addCond = el("button", "btn btn-outline-primary btn-sm", "Add Condition");
      addCond.type = "button";
      addCond.addEventListener("click", () => {
        group.items = group.items || [];
        group.items.push({ type: "flag", key: "", op: "==", value: false, params: {} });
        markDirty();
        renderEditor();
      });
      groupCard.appendChild(addCond);
      conditionsCol.appendChild(groupCard);
    });

    const addGroup = el("button", "btn btn-outline-primary btn-sm", "Add Condition Group");
    addGroup.type = "button";
    addGroup.addEventListener("click", () => {
      rule.conditionGroups = rule.conditionGroups || { logic: "ALL", groups: [] };
      rule.conditionGroups.groups = rule.conditionGroups.groups || [];
      rule.conditionGroups.groups.push({ logic: "ALL", items: [] });
      markDirty();
      renderEditor();
    });
    conditionsCol.appendChild(addGroup);

    const groupLogicRow = el("div", "mt-3");
    groupLogicRow.appendChild(el("label", "form-label", "Between condition groups"));
    const groupLogicSel = buildSelect(
      [{ value: "ALL", label: "ALL" }, { value: "ANY", label: "ANY" }],
      rule.conditionGroups?.logic || "ALL"
    );
    groupLogicSel.addEventListener("change", (e) => {
      rule.conditionGroups.logic = e.target.value;
      markDirty();
      renderTable();
    });
    groupLogicRow.appendChild(groupLogicSel);
    conditionsCol.appendChild(groupLogicRow);
    return hasError;
  }

  function renderActions(rule) {
    actionsCol.innerHTML = "";
    const title = el("div", "rules-section-title", "Actions");
    const sub = el("div", "rules-section-sub", "What should happen when triggers and conditions match.");
    actionsCol.appendChild(title);
    actionsCol.appendChild(sub);

    let hasError = false;
    if (!rule.actions || rule.actions.length === 0) hasError = true;
    (rule.actions || []).forEach((act, ai) => {
      const card = el("div", "border rounded p-2 mb-3 rules-nested-item-card rules-action-item-card");
      const row1 = el("div", "row g-2 mb-2 align-items-end");
      const currentPath = actionPathForAction(act);
      const catalog = actionPathCatalog();
      const moduleKeys = Object.keys(catalog);
      const safeModule = moduleKeys.includes(currentPath.module) ? currentPath.module : (moduleKeys[0] || "system");

      const moduleCol = el("div", "col-12 col-lg-3");
      moduleCol.appendChild(el("label", "form-label", "Module"));
      const moduleSel = buildSelect(
        moduleKeys.map((key) => ({ value: key, label: moduleLabel(key) })),
        safeModule,
        null
      );
      moduleCol.appendChild(moduleSel);

      const actionCol = el("div", "col-12 col-lg-7");
      actionCol.appendChild(el("label", "form-label", "Action"));
      const actionOptions = (catalog[safeModule] || []).filter((item) => !item.disabled);
      const actionSel = buildSelect(
        actionOptions.map((item) => ({ value: item.key, label: item.label })),
        currentPath.key || actionOptions[0]?.key || "",
        "Select action…"
      );
      actionSel.addEventListener("change", (e) => {
        applyActionPath(act, e.target.value);
        markDirty();
        renderEditor();
        renderTable();
      });
      actionCol.appendChild(actionSel);

      moduleSel.addEventListener("change", (e) => {
        const moduleKey = e.target.value;
        const options = (catalog[moduleKey] || []).filter((item) => !item.disabled);
        if (!options.length) return;
        applyActionPath(act, options[0].key);
        markDirty();
        renderEditor();
        renderTable();
      });

      const removeCol = el("div", "col-12 col-lg-2 text-lg-end");
      const remBtn = el("button", "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1");
      remBtn.type = "button";
      remBtn.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
      remBtn.addEventListener("click", () => {
        (rule.actions || []).splice(ai, 1);
        markDirty();
        renderEditor();
        renderTable();
      });
      removeCol.appendChild(remBtn);
      row1.appendChild(moduleCol);
      row1.appendChild(actionCol);
      row1.appendChild(removeCol);
      card.appendChild(row1);

      const handledByRegistry = renderActionFieldsFromRegistry(act, card);
      const paramsForType = Array.isArray(actionMeta(act.type)?.params) ? actionMeta(act.type).params : [];
      if (!handledByRegistry && paramsForType.length) {
        addValidation(card, `No registry editor defined for action type "${act.type || "unknown"}".`);
      }

      let err = validateActionFromRegistry(act);
      if (!act.type) err = "Select an action type.";
      if (err) hasError = true;
      addValidation(card, err);
      actionsCol.appendChild(card);
    });

    const addAct = el("button", "btn btn-outline-primary btn-sm", "Add Action");
    addAct.type = "button";
    addAct.addEventListener("click", () => {
      rule.actions = rule.actions || [];
      const catalog = actionPathCatalog();
      const moduleKey = Object.keys(catalog)[0];
      const pathKey = moduleKey ? catalog[moduleKey]?.[0]?.key : "";
      const act = { type: "", target: "", params: {} };
      if (pathKey) applyActionPath(act, pathKey);
      if (!act.type) act.type = "emit_event";
      rule.actions.push(act);
      markDirty();
      renderEditor();
      renderTable();
    });
    actionsCol.appendChild(addAct);
    return hasError;
  }

  function renderLogic(rule) {
    if (!logicCol) return;
    logicCol.innerHTML = "";
    const title = el("div", "rules-section-title", "Combination logic");
    const sub = el("div", "rules-section-sub", "Group logic is configured in the Triggers and Conditions tabs.");
    logicCol.appendChild(title);
    logicCol.appendChild(sub);
  }

  async function fetchCatalog() {
    const r = await fetch(API.catalog);
    const j = await r.json();
    if (j.ok) {
      state.registry = j.registry || {};
      state.tagPalette = j.tagPalette || [];
      state.lightingScenes = Array.isArray(j.lightingScenes) ? j.lightingScenes : [];
      state.lightingFixtures = Array.isArray(j.lightingFixtures) ? j.lightingFixtures : [];
      state.audioCues = Array.isArray(j.audioCues) ? j.audioCues : [];
      state.mediaScenes = Array.isArray(j.mediaScenes) ? j.mediaScenes : [];
    }
  }

  function lightingSceneCatalog() {
    const out = [];
    (state.lightingScenes || []).forEach((entry) => {
      if (typeof entry === "string") {
        const [id, title] = entry.split("|");
        if (!id) return;
        out.push({ id, title: title || id, frameCount: 1, tags: [] });
        return;
      }
      if (!entry || typeof entry !== "object") return;
      const id = String(entry.id || "").trim();
      if (!id) return;
      const title = String(entry.title || id).trim() || id;
      const frameCountRaw = Number(entry.frameCount);
      const frameCount = Number.isFinite(frameCountRaw) ? Math.max(1, Math.round(frameCountRaw)) : 1;
      const tags = Array.isArray(entry.tags)
        ? entry.tags
            .map((t) => ({
              tag: String(t?.tag || "").trim(),
              frame: Math.max(1, Math.round(Number(t?.frame || 1) || 1)),
            }))
            .filter((t) => !!t.tag)
        : [];
      out.push({ id, title, frameCount, tags });
    });
    return out;
  }

  function lightingSceneById(sceneId) {
    const id = String(sceneId || "").trim();
    if (!id) return null;
    return lightingSceneCatalog().find((s) => s.id === id) || null;
  }

  function lightingSceneOptions() {
    return lightingSceneCatalog().map((s) => ({ value: s.id, label: s.title || s.id }));
  }

  function lightingFixtureCatalog() {
    const out = [];
    (state.lightingFixtures || []).forEach((entry) => {
      if (!entry || typeof entry !== "object") return;
      const id = String(entry.id || "").trim();
      if (!id) return;
      const title = String(entry.title || id).trim() || id;
      const pixelCount = Math.max(1, Math.round(Number(entry.pixelCount || 1) || 1));
      out.push({ id, title, pixelCount });
    });
    return out;
  }

  function lightingFixtureById(fixtureId) {
    const id = String(fixtureId || "").trim();
    if (!id) return null;
    return lightingFixtureCatalog().find((f) => f.id === id) || null;
  }

  function lightingFixtureOptions() {
    return lightingFixtureCatalog().map((f) => ({
      value: f.id,
      label: `${f.title} (${f.pixelCount} px)`,
    }));
  }

  function audioCueCatalog() {
    const out = [];
    (state.audioCues || []).forEach((entry) => {
      if (!entry || typeof entry !== "object") return;
      const id = String(entry.id || "").trim();
      if (!id) return;
      const name = String(entry.name || id).trim() || id;
      const bus = String(entry.bus || "sfx").trim().toUpperCase() || "SFX";
      const enabled = entry.enabled !== false;
      out.push({ id, name, bus, enabled });
    });
    out.sort((a, b) => a.name.localeCompare(b.name));
    return out;
  }

  function audioCueById(cueId) {
    const id = String(cueId || "").trim();
    if (!id) return null;
    return audioCueCatalog().find((c) => c.id === id) || null;
  }

  function audioCueOptions() {
    return audioCueCatalog().map((c) => ({
      value: c.id,
      label: `${c.name}${c.enabled ? "" : " (Disabled)"} · ${c.bus}`,
    }));
  }

  function mediaSceneCatalog() {
    const out = [];
    (state.mediaScenes || []).forEach((entry) => {
      if (typeof entry === "string") {
        const [id, name] = entry.split("|");
        const sceneId = String(id || "").trim();
        if (!sceneId) return;
        out.push({ id: sceneId, name: String(name || sceneId).trim() || sceneId });
        return;
      }
      if (!entry || typeof entry !== "object") return;
      const id = String(entry.id || "").trim();
      if (!id) return;
      const name = String(entry.name || entry.title || id).trim() || id;
      out.push({ id, name });
    });
    out.sort((a, b) => a.name.localeCompare(b.name));
    return out;
  }

  function mediaSceneById(sceneId) {
    const id = String(sceneId || "").trim();
    if (!id) return null;
    return mediaSceneCatalog().find((s) => s.id === id) || null;
  }

  function mediaSceneOptions() {
    return mediaSceneCatalog().map((s) => ({ value: s.id, label: s.name }));
  }

  async function fetchHardware() {
    try {
      const r = await fetch(API.hardware);
      const j = await r.json();
      if (j.ok) {
        state.hardware = j.devices || [];
        state.hardwareIndex = {};
        state.hardware.forEach((d) => { state.hardwareIndex[d.id] = d; });
      }
    } catch (_) {}
  }

  async function fetchRules() {
    const r = await fetch(API.list, { cache: "no-store" });
    const j = await r.json();
    if (j.ok) state.rules = j.rules || [];
  }

  async function saveRules() {
    if (state.saving) return false;
    state.saving = true;
    if (saveBtn) saveBtn.disabled = true;
    let ok = false;
    try {
      // Commit any in-flight editor values (especially select/color controls)
      // before shape transforms and payload serialization.
      commitExpandedActionInputs();
      const invalid = (state.rules || []).some((rule) => {
        normalizeRule(rule);
        if (!(rule.name || "").trim()) return true;
        const counters = [];
        (rule.conditions || []).forEach((c) => { if (c?.type === "counter" && c.key) counters.push(c.key); });
        (rule.conditionGroups?.groups || []).forEach((g) => (g.items || []).forEach((c) => {
          if (c?.type === "counter" && c.key) counters.push(c.key);
        }));
        (rule.actions || []).forEach((a) => {
          if ((a?.type === "set_counter" || a?.type === "inc_counter") && a.target) counters.push(a.target);
        });
        return counters.some((c) => !isValidCounterName(c));
      });
      if (invalid) {
        alert("Fix invalid counter names before saving.");
        state.saving = false;
        if (saveBtn) saveBtn.disabled = !state.dirty;
        return false;
      }
      (state.rules || []).forEach((rule) => {
        normalizeRule(rule);
        rule.triggers = [];
        (rule.triggerGroups?.groups || []).forEach((g) => {
          (g.items || []).forEach((t) => { rule.triggers.push(t); });
        });
        rule.conditions = [];
        (rule.conditionGroups?.groups || []).forEach((g) => {
          (g.items || []).forEach((c) => { rule.conditions.push(c); });
        });
        rule.logic = rule.triggerGroups?.logic || rule.logic || "ALL";
        rule.conditionLogic = rule.conditionGroups?.logic || rule.conditionLogic || "ALL";
      });
      const payloadRules = JSON.parse(JSON.stringify(state.rules || []));
      payloadRules.forEach((rule) => {
        rule.actions = (rule.actions || []).map(actionToSavedShape);
      });
      let j = null;
      try {
        const r = await fetch(API.save, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rules: payloadRules }),
        });
        const raw = await r.text();
        try {
          j = JSON.parse(raw);
        } catch (_) {
          j = { ok: false, error: `save_http_${r.status}`, detail: raw?.slice(0, 400) || "" };
        }
      } catch (err) {
        j = { ok: false, error: "save_request_failed", detail: String(err || "") };
      }
      if (!j.ok) {
        const detail = String(j.detail || "").trim();
        alert(detail ? `${j.error || "Failed to save"}: ${detail}` : (j.error || "Failed to save"));
      } else {
        const prevExpandedId = state.expandedId;
        try {
          await fetchRules();
          (state.rules || []).forEach(normalizeRule);
          if (prevExpandedId && !(state.rules || []).some((rule) => rule.id === prevExpandedId)) {
            state.expandedId = null;
          }
          saveExpandedRuleId();
          renderTagOptions();
          renderTable();
          renderEditor();
          updateSavedSnapshot();
        } catch (_) {
          // Keep local state if refresh fails; the save already succeeded.
          updateSavedSnapshot();
        }
        markDirty(false);
        await loadSyncStatus();
        ok = true;
      }
    } finally {
      state.saving = false;
      if (saveBtn) saveBtn.disabled = !state.dirty;
    }
    return ok;
  }

  function commitExpandedActionInputs() {
    if (!state.expandedId || !actionsCol) return;
    const rule = (state.rules || []).find((r) => r.id === state.expandedId);
    if (!rule || !Array.isArray(rule.actions)) return;
    const cards = actionsCol.querySelectorAll(".rules-action-item-card");
    cards.forEach((card, idx) => {
      const act = rule.actions[idx];
      if (!act || typeof act !== "object") return;
      const fields = card.querySelectorAll("[data-action-bind]");
      fields.forEach((node) => {
        const bind = String(node.dataset.actionBind || "").trim();
        if (!bind) return;
        const valueType = String(node.dataset.valueType || "").trim().toLowerCase();
        let raw = "";
        if (node.type === "checkbox") raw = node.checked;
        else raw = node.value;
        const next = coerceActionFieldValue({ valueType }, raw);
        writeActionBind(act, bind, next);
      });
    });
  }

  async function syncRules() {
    let skipSyncConfirm = false;
    if (state.dirty) {
      const proceed = await confirmSaveBeforeSync();
      if (!proceed) return;
      const saved = await saveRules();
      if (!saved) {
        setSyncStatus("Save failed", "Fix validation errors, then sync again.", false);
        return;
      }
      skipSyncConfirm = true;
    }
    if (!skipSyncConfirm) {
      const confirmed = await confirmSyncAction();
      if (!confirmed) return;
    }

    syncBtn.disabled = true;
    stopSyncPoll();
    if (!syncModal && syncModalEl && window.bootstrap?.Modal) {
      syncModal = bootstrap.Modal.getOrCreateInstance(syncModalEl);
    }
    if (syncModal) syncModal.show();
    setSyncStatus("Compiling rules…", "Saving locally…", true);
    try {
      const r = await fetch("/api/rules/sync", { method: "POST" });
      const j = await r.json();
      if (!j.ok) {
        if (j.error === "bridge_not_connected") {
          setSyncStatus("Bridge offline", "Connect the ESP and start the bridge, then try again.", false);
        } else if (j.error === "bridge_unresponsive") {
          setSyncStatus("Bridge unresponsive", "No response from ESP. Check the USB connection and try again.", false);
        } else if (j.error === "missing_rules") {
          setSyncStatus("No rules to sync", "Save rules before syncing.", false);
        } else {
          setSyncStatus("Sync failed", j.error || "Sync failed", false);
        }
        syncBtn.disabled = false;
        return;
      }
      syncStartedAtSec = Date.now() / 1000;
        setSyncStatus("Uploading to ESP…", "Sending rules.pd to the ESP…", true);
      syncTimer = setInterval(pollSyncStatus, 1000);
      pollSyncStatus();
    } catch (e) {
      setSyncStatus("Sync failed", "Request error while starting sync.", false);
      syncBtn.disabled = false;
      syncStartedAtSec = 0;
    }
  }

  function initControls() {
    addBtn?.addEventListener("click", () => {
      const tags = state.filterTag ? [{ name: state.filterTag, color: colorForTag(state.filterTag) }] : [];
      const newRule = {
        id: uuid(),
        name: "New Rule",
        tags,
        logic: "ALL",
        conditionLogic: "ALL",
        triggers: [],
        conditions: [],
        actions: [],
        enabled: true,
        notes: "",
      };
      state.rules = (state.rules || []).concat([newRule]);
      state.expandedId = newRule.id;
      saveExpandedRuleId();
      markDirty();
      renderTable();
      renderEditor();
      renderTagOptions();
    });
    saveBtn?.addEventListener("click", saveRules);
    syncBtn?.addEventListener("click", syncRules);
    tagFilter?.addEventListener("change", (e) => {
      state.filterTag = e.target.value;
      updateFilterClear();
      state.expandedId = null;
      saveExpandedRuleId();
      renderTable();
      renderEditor();
    });
    keywordFilter?.addEventListener("input", (e) => {
      state.filterKeyword = e.target.value;
      updateFilterClear();
      state.expandedId = null;
      saveExpandedRuleId();
      renderTable();
      renderEditor();
    });
    tagFilterClear?.addEventListener("click", () => {
      state.filterTag = "";
      tagFilter.value = "";
      state.filterKeyword = "";
      if (keywordFilter) keywordFilter.value = "";
      updateFilterClear();
      saveExpandedRuleId();
      renderTable();
      renderEditor();
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
      if (!state.dirty) return;
      if (bypassUnloadOnce) {
        bypassUnloadOnce = false;
        return;
      }
      e.preventDefault();
      e.returnValue = "";
    });

    const rulesTabs = document.getElementById("rules-tabs");
    rulesTabs?.querySelectorAll("[data-bs-toggle='tab']").forEach((btn) => {
      btn.addEventListener("shown.bs.tab", (e) => {
        const id = String(e.target?.id || "").trim();
        const keyById = {
          "rules-tab-meta": "metadata",
          "rules-tab-triggers": "triggers",
          "rules-tab-conditions": "conditions",
          "rules-tab-actions": "actions",
          "rules-tab-summary": "summary",
        };
        saveEditorTabKey(keyById[id] || "metadata");
      });
    });
  }

  async function init() {
    await Promise.all([fetchCatalog(), fetchHardware(), fetchRules()]);
    (state.rules || []).forEach(normalizeRule);
    loadExpandedRuleId();
    loadEditorTabKey();
    sanitizeExpandedRuleId();
    renderTagOptions();
    renderTable();
    renderEditor();
    switchEditorTab(state.activeEditorTab);
    initControls();
    await loadSyncStatus();
    updateSavedSnapshot();
    markDirty(false);
  }

  async function loadSyncStatus() {
    try {
      const r = await fetch("/api/esplink/sync/status", { cache: "no-store" });
      const j = await r.json();
      if (j?.espConnected !== true) {
        setSyncUiState("unknown");
        return false;
      } else if (j?.rules?.inSync === false) {
        setSyncUiState("out");
        return true;
      } else {
        setSyncUiState("in");
        return false;
      }
    } catch (e) {
      setSyncUiState("unknown");
      return false;
    }
  }

  function refreshSyncWarning(attempts = 4, delayMs = 600) {
    loadSyncStatus().then((outOfSync) => {
      if (outOfSync && attempts > 0) {
        setTimeout(() => refreshSyncWarning(attempts - 1, Math.min(delayMs * 1.5, 1500)), delayMs);
      }
    });
  }

  init();
})();
