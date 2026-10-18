(function () {
  const saveBtn = document.getElementById("scoring-save");
  const baseAddBtn = document.getElementById("base-add");
  const ruleAddBtn = document.getElementById("rule-add");
  const comboAddBtn = document.getElementById("combo-add");
  const baseBody = document.querySelector("#base-table tbody");
  const rulesList = document.getElementById("rules-list");
  const comboList = document.getElementById("combo-list");

  if (!saveBtn || !baseBody || !rulesList || !comboList) return;

  const API = {
    config: "/api/scoring/config",
    sources: "/api/scoring/sources",
  };
  const TAB_KEY = "pinballctl.scoring.activeTab.v1";
  const EXPAND_KEY = "pinballctl.scoring.expand.v1";

  const state = {
    config: { settings: {}, basePoints: [], scoreRules: [], combos: [] },
    sources: [],
    expandedBaseId: null,
    expandedRuleId: null,
    expandedComboId: null,
    dirty: false,
  };
  let saving = false;
  const settingsEl = document.getElementById("scoring-settings");
  const settingsBody = document.getElementById("scoring-settings-body");
  const settingsTitle = document.getElementById("scoring-settings-title");
  const settingsSave = document.getElementById("scoring-settings-save");
  const settingsModal = bootstrap.Modal.getOrCreateInstance(settingsEl);
  let settingsKind = null;
  let returnFocus = null;

  // Move the existing form, preserving field handlers and the original data model.
  function showSettings(kind) {
    if (settingsKind !== kind) return;
    const list = kind === "base" ? baseBody : kind === "rule" ? rulesList : comboList;
    const card = list.querySelector(".is-expanded");
    const body = card?.querySelector(".scoring-rule-body");
    if (!body) { settingsModal.hide(); return; }
    const wrapper = document.createElement("div");
    wrapper.setAttribute(`data-${kind}-idx`, card.getAttribute(`data-${kind}-idx`));
    body.classList.remove("d-none");
    wrapper.appendChild(body);
    settingsBody.replaceChildren(wrapper);
    settingsTitle.textContent = card.querySelector(".fw-semibold").textContent;
    if (!settingsEl.classList.contains("show")) {
      returnFocus = document.activeElement;
      settingsModal.show();
    }
  }
  function onEditor(list, type, handler) {
    list.addEventListener(type, handler);
    settingsBody.addEventListener(type, handler);
  }
  settingsSave.addEventListener("click", () => saveBtn.click());
  new MutationObserver(() => { settingsSave.disabled = saveBtn.disabled; }).observe(saveBtn, {attributes:true, attributeFilter:["disabled"]});
  settingsEl.addEventListener("hidden.bs.modal", () => {
    const closingKind = settingsKind;
    const closingId = closingKind === "base" ? state.expandedBaseId : closingKind === "rule" ? state.expandedRuleId : state.expandedComboId;
    const rows = closingKind === "base" ? state.config.basePoints : closingKind === "rule" ? state.config.scoreRules : state.config.combos;
    const closingIndex = rows.findIndex(row => row.id === closingId);
    settingsKind = null;
    state.expandedBaseId = null;
    state.expandedRuleId = null;
    state.expandedComboId = null;
    saveExpandedState();
    settingsBody.replaceChildren();
    renderBase();
    renderRules();
    renderCombos();
    const opener = document.querySelector(`[data-${closingKind}-toggle="${closingIndex}"]`);
    (opener || (returnFocus?.isConnected ? returnFocus : closingKind === "base" ? baseAddBtn : closingKind === "combo" ? comboAddBtn : ruleAddBtn))?.focus();
  });
  const BUTTON_EVENT_OPTIONS = ["CLICKED", "PRESSED", "RELEASED", "DOUBLE_CLICKED", "HELD", "REPEAT_WHILE_HELD"];

  function loadExpandedState() {
    try {
      const raw = localStorage.getItem(EXPAND_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return;
      const rid = String(parsed.ruleId || "").trim();
      const cid = String(parsed.comboId || "").trim();
      state.expandedRuleId = rid || null;
      state.expandedComboId = cid || null;
    } catch (_) {}
  }

  function saveExpandedState() {
    try {
      localStorage.setItem(EXPAND_KEY, JSON.stringify({
        ruleId: state.expandedRuleId || "",
        comboId: state.expandedComboId || "",
      }));
    } catch (_) {}
  }

  function sanitizeExpandedState() {
    const ruleIds = new Set((state.config.scoreRules || []).map((r) => String(r?.id || "")).filter(Boolean));
    const comboIds = new Set((state.config.combos || []).map((c) => String(c?.id || "")).filter(Boolean));
    if (!ruleIds.has(String(state.expandedRuleId || ""))) state.expandedRuleId = null;
    if (!comboIds.has(String(state.expandedComboId || ""))) state.expandedComboId = null;
    saveExpandedState();
  }

  function uid() {
    return "s_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function esc(v) {
    return String(v || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function buttonSourceOptions(current) {
    const rows = ['<option value="">Select button…</option>'];
    state.sources.forEach((s) => {
      const value = String(s.id || "");
      const selected = value === String(current || "") ? " selected" : "";
      rows.push(`<option value="${esc(value)}"${selected}>${esc(s.friendly || s.id)}</option>`);
    });
    return rows.join("");
  }

  function eventTypeOptions(current) {
    const rows = ['<option value="">Select event…</option>'];
    BUTTON_EVENT_OPTIONS.forEach((v) => {
      const selected = v === String(current || "").toUpperCase() ? " selected" : "";
      rows.push(`<option value="${v}"${selected}>${v}</option>`);
    });
    return rows.join("");
  }

  function rowMode(row) {
    const mode = String(row?.mode || "").toLowerCase();
    if (mode === "event" || mode === "hardware") return mode;
    if (String(row?.source || "").trim()) return "hardware";
    if (String(row?.eventName || "").trim()) return "event";
    return "hardware";
  }

  function sourceModeOptions(current) {
    const mode = current === "event" ? "event" : "hardware";
    return `
      <option value="hardware"${mode === "hardware" ? " selected" : ""}>Hardware</option>
      <option value="event"${mode === "event" ? " selected" : ""}>Event</option>
    `;
  }

  function anySourceDisabledSelect() {
    return '<select class="form-select form-select-sm" disabled><option>Any source</option></select>';
  }

  function stepMode(step) {
    const mode = String(step?.mode || "").toLowerCase();
    if (mode === "event" || mode === "hardware") return mode;
    if (String(step?.source || "").trim()) return "hardware";
    if (String(step?.eventName || "").trim()) return "event";
    return "hardware";
  }

  function renderBase() {
    const rows = Array.isArray(state.config.basePoints) ? state.config.basePoints : [];
    baseBody.innerHTML = rows.map((row, idx) => {
      row.id = row.id || uid();
      row.mode = rowMode(row);
      const sourceControl = row.mode === "hardware"
        ? `<select class="form-select form-select-sm" data-field="source" aria-label="Source">${buttonSourceOptions(row.source)}</select>`
        : anySourceDisabledSelect();
      const triggerControl = row.mode === "hardware"
        ? `<select class="form-select form-select-sm" data-field="eventType" aria-label="Trigger">${eventTypeOptions(row.eventType)}</select>`
        : `<input class="form-control form-control-sm" data-field="eventName" aria-label="Event name" value="${esc(row.eventName || "")}" placeholder="GAME_STARTED">`;
      const source = row.mode === "hardware" ? sourceDisplayName(row.source) : "Any source (event)";
      return `
        <tr data-base-idx="${idx}" class="${state.expandedBaseId === row.id ? "is-expanded" : ""}">
          <td class="fw-semibold">${esc(source)}</td>
          <td>${esc(row.mode === "hardware" ? row.eventType || "CLICKED" : row.eventName || "(unset)")}</td>
          <td>${Number(row.points || 0)}</td><td>${esc(row.note || "")}</td>
          <td><div class="d-flex gap-2 justify-content-end text-nowrap">
            <button class="btn btn-sm btn-outline-danger" data-remove="${idx}" type="button" aria-label="Remove base points" title="Remove base points"><i class="fa fa-trash" aria-hidden="true"></i></button>
            <button class="btn btn-sm btn-outline-secondary" data-base-toggle="${idx}" type="button" aria-haspopup="dialog" aria-label="Base points settings" title="Base points settings"><i class="fa fa-sliders" aria-hidden="true"></i></button>
          </div>
          <div class="scoring-rule-body d-none">
            <div class="mb-3"><label class="form-label">Source type</label><select class="form-select" data-field="mode" aria-label="Source type">${sourceModeOptions(row.mode)}</select></div>
            <div class="mb-3"><label class="form-label">Source</label>${sourceControl}</div>
            <div class="mb-3"><label class="form-label">Trigger</label>${triggerControl}</div>
            <div class="mb-3"><label class="form-label">Points</label><input class="form-control" data-field="points" aria-label="Points" type="number" value="${Number(row.points || 0)}"></div>
            <div><label class="form-label">Notes</label><input class="form-control" data-field="note" aria-label="Notes" value="${esc(row.note || "")}" placeholder="Optional"></div>
          </div></td>
        </tr>`;
    }).join("") || '<tr><td colspan="5" class="text-secondary text-center py-3">No base points yet.</td></tr>';
    showSettings("base");
  }

  function renderRules() {
    const rows = Array.isArray(state.config.scoreRules) ? state.config.scoreRules : [];
    if (!rows.length) {
      rulesList.innerHTML = '<div class="text-secondary small">No scoring rules yet.</div>';
      return;
    }
    rulesList.innerHTML = `<table class="table table-hover align-middle mb-0" aria-label="Rules"><thead><tr><th scope="col">Rule</th><th scope="col">Source / trigger</th><th scope="col">Points</th><th scope="col">Hit requirement</th><th scope="col">Settings</th></tr></thead><tbody>` + rows.map((row, idx) => {
      row.id = row.id || uid();
      row.mode = rowMode(row);
      const expanded = state.expandedRuleId === row.id;
      const sourceControl = row.mode === "hardware"
        ? `<select class="form-select form-select-sm" data-field="source">${buttonSourceOptions(row.source)}</select>`
        : anySourceDisabledSelect();
      const triggerControl = row.mode === "hardware"
        ? `<select class="form-select form-select-sm" data-field="eventType">${eventTypeOptions(row.eventType)}</select>`
        : `<input class="form-control form-control-sm" data-field="eventName" value="${esc(row.eventName || "")}" placeholder="MODE_STARTED">`;
      const sourceSummary = row.mode === "event"
        ? `Event: ${row.eventName || "(unset)"}`
        : `Button: ${sourceDisplayName(row.source)}${row.eventType ? ` • ${row.eventType}` : ""}`;
      const scoringSummary = `${Number(row.basePoints || 0)} + ${Number(row.pointsPerHit || 0)}/hit`;
      const gateSummary = `min ${Number(row.minHits || 1)}${Number(row.minHitsWithinMs || 0) > 0 ? ` in ${Number(row.minHitsWithinMs || 0)}ms` : ""}`;
      return `
        <tr class="${expanded ? "is-expanded" : ""}" data-rule-idx="${idx}"><td class="fw-semibold">${esc(row.name || "Rule")}</td><td>${esc(sourceSummary)}</td><td>${esc(scoringSummary)}</td><td>${esc(gateSummary)}</td><td><div class="d-flex gap-2 justify-content-end text-nowrap"><button type="button" class="btn btn-sm btn-outline-danger" data-rule-remove="${idx}" aria-label="Remove" title="Remove"><i class="fa fa-trash" aria-hidden="true"></i></button><button type="button" class="btn btn-sm btn-outline-secondary" data-rule-toggle="${idx}" aria-haspopup="dialog" aria-label="Rule settings" title="Rule settings"><i class="fa fa-sliders" aria-hidden="true"></i></button></div>
          <div class="scoring-rule-body d-none">
            <div class="row g-2">
              <div class="col-12 col-md-3">
                <label class="form-label">Name</label>
                <input class="form-control form-control-sm" data-field="name" value="${esc(row.name || "Rule")}">
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Source</label>
                <div class="scoring-source-inline">
                  <select class="form-select form-select-sm" data-field="mode">${sourceModeOptions(row.mode)}</select>
                  ${sourceControl}
                </div>
              </div>
              <div class="col-12 col-md-3">
                <label class="form-label">Trigger</label>
                ${triggerControl}
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Min Hits</label>
                <input class="form-control form-control-sm" data-field="minHits" type="number" min="1" value="${Number(row.minHits || 1)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Min Window ms</label>
                <input class="form-control form-control-sm" data-field="minHitsWithinMs" type="number" min="0" value="${Number(row.minHitsWithinMs || 0)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Base</label>
                <input class="form-control form-control-sm" data-field="basePoints" type="number" value="${Number(row.basePoints || 0)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">+ / Hit</label>
                <input class="form-control form-control-sm" data-field="pointsPerHit" type="number" value="${Number(row.pointsPerHit || 0)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Max Bonus Hits</label>
                <input class="form-control form-control-sm" data-field="maxBonusHits" type="number" min="0" value="${Number(row.maxBonusHits || 0)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Cooloff ms</label>
                <input class="form-control form-control-sm" data-field="cooloffMs" type="number" min="0" value="${Number(row.cooloffMs || 0)}">
              </div>
              <div class="col-6 col-md-2">
                <label class="form-label">Cooloff Step</label>
                <input class="form-control form-control-sm" data-field="cooloffStep" type="number" min="1" value="${Number(row.cooloffStep || 1)}">
              </div>
              <div class="col-6 col-md-4">
                <label class="form-label">Emit Event</label>
                <input class="form-control form-control-sm" data-field="emitEvent" value="${esc(row.emitEvent || "")}" placeholder="EVENT">
              </div>
            </div>
          </div>
        </td></tr>
      `;
    }).join("") + "</tbody></table>";
    showSettings("rule");
  }

  function comboStepRow(step, cidx, sidx) {
    step.mode = stepMode(step);
    const sourceControl = step.mode === "hardware"
      ? `<select class="form-select form-select-sm" data-step-field="source">${buttonSourceOptions(step.source)}</select>`
      : anySourceDisabledSelect();
    const triggerControl = step.mode === "hardware"
      ? `<select class="form-select form-select-sm" data-step-field="eventType">${eventTypeOptions(step.eventType)}</select>`
      : `<input class="form-control form-control-sm" data-step-field="eventName" value="${esc(step.eventName || "")}" placeholder="BONUS_READY">`;
    return `
      <div class="scoring-step-row" data-step-idx="${sidx}">
        <div class="scoring-source-inline">
          <select class="form-select form-select-sm" data-step-field="mode">${sourceModeOptions(step.mode)}</select>
          ${sourceControl}
        </div>
        ${triggerControl}
        <button type="button" class="btn btn-sm btn-outline-danger d-inline-flex align-items-center gap-1" data-step-remove="${cidx}:${sidx}" aria-label="Remove" title="Remove"><i class="fa fa-trash" aria-hidden="true"></i></button>
      </div>
    `;
  }

  function renderCombos() {
    const combos = Array.isArray(state.config.combos) ? state.config.combos : [];
    if (!combos.length) {
      comboList.innerHTML = '<div class="text-secondary small">No combos yet.</div>';
      return;
    }
    comboList.innerHTML = `<table class="table table-hover align-middle mb-0" aria-label="Combos"><thead><tr><th scope="col">Combo</th><th scope="col">Order</th><th scope="col">Steps</th><th scope="col">Points</th><th scope="col">Multiplier</th><th scope="col">Settings</th></tr></thead><tbody>` + combos.map((combo, idx) => {
      combo.id = combo.id || uid();
      combo.steps = Array.isArray(combo.steps) ? combo.steps : [];
      const expanded = state.expandedComboId === combo.id;
      return `
        <tr class="${expanded ? "is-expanded" : ""}" data-combo-idx="${idx}"><td class="fw-semibold">${esc(combo.name || "Combo")}</td><td>${esc(String(combo.mode || "ordered"))}</td><td>${combo.steps.length}</td><td>${Number(combo.awardPoints || 0)}</td><td>${Number(combo.multiplierValue || 1)}× / ${Number(combo.multiplierDurationMs || 0)}ms</td><td><div class="d-flex gap-2 justify-content-end text-nowrap"><button type="button" class="btn btn-sm btn-outline-danger" data-combo-remove="${idx}" aria-label="Remove" title="Remove"><i class="fa fa-trash" aria-hidden="true"></i></button><button type="button" class="btn btn-sm btn-outline-secondary" data-combo-toggle="${idx}" aria-haspopup="dialog" aria-label="Combo settings" title="Combo settings"><i class="fa fa-sliders" aria-hidden="true"></i></button></div>
          <div class="scoring-rule-body d-none">
            <div class="row g-2 mb-2">
              <div class="col-12 col-md-2"><label class="form-label">Name</label><input class="form-control form-control-sm" data-field="name" value="${esc(combo.name || "Combo")}"></div>
              <div class="col-6 col-md-2"><label class="form-label">Order</label><select class="form-select form-select-sm" data-field="mode"><option value="ordered"${String(combo.mode || "ordered") === "ordered" ? " selected" : ""}>Specific</option><option value="any"${String(combo.mode || "ordered") === "any" ? " selected" : ""}>Any</option></select></div>
              <div class="col-6 col-md-2"><label class="form-label">Window ms</label><input class="form-control form-control-sm" data-field="windowMs" type="number" min="100" value="${Number(combo.windowMs || 3000)}"></div>
              <div class="col-6 col-md-2"><label class="form-label">Award points</label><input class="form-control form-control-sm" data-field="awardPoints" type="number" value="${Number(combo.awardPoints || 0)}"></div>
              <div class="col-6 col-md-2"><label class="form-label">x Multiplier</label><input class="form-control form-control-sm" data-field="multiplierValue" type="number" min="1" step="0.1" value="${Number(combo.multiplierValue || 1)}"></div>
              <div class="col-6 col-md-2"><label class="form-label">Mult ms</label><input class="form-control form-control-sm" data-field="multiplierDurationMs" type="number" min="0" value="${Number(combo.multiplierDurationMs || 0)}"></div>
            </div>
            <div class="row g-2 mb-2">
              <div class="col-12 col-md-4"><label class="form-label">Emit custom event</label><input class="form-control form-control-sm" data-field="emitEvent" value="${esc(combo.emitEvent || "")}" placeholder="BONUS_EVENT"></div>
            </div>
            <div data-steps-wrap>${combo.steps.map((step, sidx) => comboStepRow(step, idx, sidx)).join("")}</div>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-step-add="${idx}">Add step</button>
          </div>
        </td></tr>
      `;
    }).join("") + "</tbody></table>";
    showSettings("combo");
  }

  function numberFields(set) {
    return new Set(set);
  }

  const baseNums = numberFields(["points"]);
  const ruleNums = numberFields(["minHits", "minHitsWithinMs", "basePoints", "pointsPerHit", "maxBonusHits", "cooloffMs", "cooloffStep"]);
  const comboNums = numberFields(["windowMs", "awardPoints", "multiplierValue", "multiplierDurationMs"]);

  function setDirty(flag) {
    state.dirty = !!flag;
    saveBtn.disabled = saving || !state.dirty;
    saveBtn.setAttribute("aria-disabled", saveBtn.disabled ? "true" : "false");
  }

  function wireBase() {
    const onField = (e) => {
      const tr = e.target.closest("[data-base-idx]");
      if (!tr) return;
      const idx = Number(tr.getAttribute("data-base-idx"));
      const row = state.config.basePoints[idx];
      if (!row) return;
      const field = e.target.getAttribute("data-field");
      if (!field) return;
      if (field === "mode") {
        row.mode = e.target.value === "event" ? "event" : "hardware";
        if (row.mode === "event") {
          row.source = "";
          row.eventType = "";
        } else {
          row.eventName = "";
          row.source = row.source || (state.sources[0]?.id || "");
        }
        setDirty(true);
        renderBase();
        return;
      }
      row[field] = baseNums.has(field) ? Number(e.target.value || 0) : e.target.value;
      if (field === "eventType") row.eventType = String(row.eventType || "").toUpperCase();
      if (field === "eventName") row.eventName = String(row.eventName || "").toUpperCase();
      setDirty(true);
    };

    onEditor(baseBody, "input", onField);
    onEditor(baseBody, "change", onField);

    baseBody.addEventListener("click", (e) => {
      const toggle = e.target.closest("[data-base-toggle]");
      if (toggle) {
        settingsKind = "base";
        state.expandedBaseId = state.config.basePoints[Number(toggle.dataset.baseToggle)].id;
        renderBase();
        return;
      }
      const btn = e.target.closest("[data-remove]");
      if (!btn) return;
      const idx = Number(btn.getAttribute("data-remove"));
      state.config.basePoints.splice(idx, 1);
      setDirty(true);
      renderBase();
    });
  }

  function wireRules() {
    const onField = (e) => {
      const card = e.target.closest("[data-rule-idx]");
      if (!card) return;
      const idx = Number(card.getAttribute("data-rule-idx"));
      const row = state.config.scoreRules[idx];
      if (!row) return;
      const field = e.target.getAttribute("data-field");
      if (!field) return;
      if (field === "mode") {
        row.mode = e.target.value === "event" ? "event" : "hardware";
        if (row.mode === "event") {
          row.source = "";
          row.eventType = "";
        } else {
          row.eventName = "";
          row.source = row.source || (state.sources[0]?.id || "");
        }
        state.expandedRuleId = row.id;
        setDirty(true);
        renderRules();
        return;
      }
      row[field] = ruleNums.has(field) ? Number(e.target.value || 0) : e.target.value;
      if (field === "eventType") row.eventType = String(row.eventType || "").toUpperCase();
      if (field === "eventName") row.eventName = String(row.eventName || "").toUpperCase();
      setDirty(true);
    };

    onEditor(rulesList, "input", onField);
    onEditor(rulesList, "change", onField);

    onEditor(rulesList, "click", (e) => {
      const toggle = e.target.closest("[data-rule-toggle]");
      if (toggle) {
        const idx = Number(toggle.getAttribute("data-rule-toggle"));
        const row = state.config.scoreRules[idx];
        if (!row) return;
        settingsKind = "rule";
        state.expandedRuleId = row.id;
        saveExpandedState();
        renderRules();
        return;
      }
      const btn = e.target.closest("[data-rule-remove]");
      if (btn) {
        const idx = Number(btn.getAttribute("data-rule-remove"));
        const removed = state.config.scoreRules[idx];
        state.config.scoreRules.splice(idx, 1);
        if (removed && removed.id && state.expandedRuleId === removed.id) state.expandedRuleId = null;
        saveExpandedState();
        setDirty(true);
        renderRules();
      }
    });
  }

  function wireCombos() {
    onEditor(comboList, "input", (e) => {
      const card = e.target.closest("[data-combo-idx]");
      if (!card) return;
      const cidx = Number(card.getAttribute("data-combo-idx"));
      const combo = state.config.combos[cidx];
      if (!combo) return;

      const field = e.target.getAttribute("data-field");
      if (field) {
        combo[field] = comboNums.has(field) ? Number(e.target.value || 0) : e.target.value;
        setDirty(true);
        return;
      }

      const stepRow = e.target.closest(".scoring-step-row");
      if (!stepRow) return;
      const sidx = Number(stepRow.getAttribute("data-step-idx"));
      const step = combo.steps[sidx];
      if (!step) return;
      const stepField = e.target.getAttribute("data-step-field");
      if (!stepField) return;
      if (stepField === "mode") {
        step.mode = e.target.value === "event" ? "event" : "hardware";
        if (step.mode === "event") {
          step.source = "";
          step.eventType = "";
        } else {
          step.eventName = "";
          step.source = step.source || (state.sources[0]?.id || "");
          step.eventType = step.eventType || "CLICKED";
        }
        setDirty(true);
        renderCombos();
        return;
      }
      step[stepField] = e.target.value;
      if (stepField === "eventType") step.eventType = String(step.eventType || "").toUpperCase();
      if (stepField === "eventName") step.eventName = String(step.eventName || "").toUpperCase();
      setDirty(true);
    });

    onEditor(comboList, "click", (e) => {
      const comboToggle = e.target.closest("[data-combo-toggle]");
      if (comboToggle) {
        const idx = Number(comboToggle.getAttribute("data-combo-toggle"));
        const combo = state.config.combos[idx];
        if (!combo) return;
        settingsKind = "combo";
        state.expandedComboId = combo.id;
        saveExpandedState();
        renderCombos();
        return;
      }
      const comboRemove = e.target.closest("[data-combo-remove]");
      if (comboRemove) {
        const idx = Number(comboRemove.getAttribute("data-combo-remove"));
        const removed = state.config.combos[idx];
        state.config.combos.splice(idx, 1);
        if (removed && removed.id && state.expandedComboId === removed.id) state.expandedComboId = null;
        saveExpandedState();
        setDirty(true);
        renderCombos();
        return;
      }

      const stepAdd = e.target.closest("[data-step-add]");
      if (stepAdd) {
        const cidx = Number(stepAdd.getAttribute("data-step-add"));
        const combo = state.config.combos[cidx];
        if (!combo) return;
        combo.steps = Array.isArray(combo.steps) ? combo.steps : [];
        combo.steps.push({ id: uid(), mode: "hardware", source: state.sources[0]?.id || "", eventType: "CLICKED", eventName: "" });
        setDirty(true);
        renderCombos();
        return;
      }

      const stepRemove = e.target.closest("[data-step-remove]");
      if (stepRemove) {
        const [cidxStr, sidxStr] = String(stepRemove.getAttribute("data-step-remove") || "").split(":");
        const cidx = Number(cidxStr);
        const sidx = Number(sidxStr);
        const combo = state.config.combos[cidx];
        if (!combo || !Array.isArray(combo.steps)) return;
        combo.steps.splice(sidx, 1);
        setDirty(true);
        renderCombos();
      }
    });
  }

  function addBase() {
    state.config.basePoints.push({ id: uid(), mode: "hardware", source: state.sources[0]?.id || "", eventType: "CLICKED", eventName: "", points: 10, note: "" });
    settingsKind = "base";
    state.expandedBaseId = state.config.basePoints[state.config.basePoints.length - 1].id;
    setDirty(true);
    renderBase();
  }

  function addRule() {
    const next = {
      id: uid(),
      name: "Rule",
      mode: "hardware",
      source: state.sources[0]?.id || "",
      eventType: "CLICKED",
      eventName: "",
      minHits: 1,
      minHitsWithinMs: 0,
      basePoints: 10,
      pointsPerHit: 0,
      maxBonusHits: 0,
      cooloffMs: 0,
      cooloffStep: 1,
      emitEvent: "",
      note: "",
    };
    state.config.scoreRules.push(next);
    settingsKind = "rule";
    state.expandedRuleId = next.id;
    saveExpandedState();
    setDirty(true);
    renderRules();
  }

  function addCombo() {
    const next = {
      id: uid(),
      name: "Combo",
      mode: "ordered",
      windowMs: 3000,
      awardPoints: 100,
      multiplierValue: 1,
      multiplierDurationMs: 0,
      emitEvent: "",
      steps: [{ id: uid(), mode: "hardware", source: state.sources[0]?.id || "", eventType: "CLICKED", eventName: "" }],
    };
    state.config.combos.push(next);
    settingsKind = "combo";
    state.expandedComboId = next.id;
    saveExpandedState();
    setDirty(true);
    renderCombos();
  }

  function restoreActiveTab() {
    const tabsWrap = document.getElementById("scoring-tabs");
    if (!tabsWrap) return;
    let target = "";
    try {
      target = String(localStorage.getItem(TAB_KEY) || "");
    } catch (_) {}
    if (!target) return;
    const btn = tabsWrap.querySelector(`[data-bs-target="${target}"]`);
    if (!btn || typeof bootstrap === "undefined" || !bootstrap.Tab) return;
    bootstrap.Tab.getOrCreateInstance(btn).show();
  }

  function wireTabPersistence() {
    const tabsWrap = document.getElementById("scoring-tabs");
    if (!tabsWrap) return;
    tabsWrap.addEventListener("shown.bs.tab", (e) => {
      const target = e?.target?.getAttribute?.("data-bs-target");
      if (!target) return;
      try {
        localStorage.setItem(TAB_KEY, target);
      } catch (_) {}
    });
  }

  function sourceDisplayName(sourceId) {
    const id = String(sourceId || "");
    if (!id) return "(unset)";
    const found = state.sources.find((s) => String(s.id || "") === id);
    return found ? String(found.friendly || found.id || id) : id;
  }

  async function save() {
    if (saving || !state.dirty) return;
    saving = true;
    setDirty(state.dirty);
    try {
      const resp = await fetch(API.config, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: state.config }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "save_failed");
      state.config = data.config || state.config;
      (state.config.scoreRules || []).forEach((r) => { if (!r.id) r.id = uid(); });
      (state.config.combos || []).forEach((c) => { if (!c.id) c.id = uid(); });
      sanitizeExpandedState();
      renderBase();
      renderRules();
      renderCombos();
      setDirty(false);
    } catch (err) {
      window.alert(`Save failed: ${err.message || err}`);
    } finally {
      saving = false;
      setDirty(state.dirty);
    }
  }

  async function boot() {
    const [cfgResp, srcResp] = await Promise.all([fetch(API.config), fetch(API.sources)]);
    const cfgJson = await cfgResp.json();
    const srcJson = await srcResp.json();

    state.config = cfgJson.config || { settings: {}, basePoints: [], scoreRules: [], combos: [] };
    state.config.basePoints = Array.isArray(state.config.basePoints) ? state.config.basePoints : [];
    state.config.scoreRules = Array.isArray(state.config.scoreRules) ? state.config.scoreRules : [];
    state.config.combos = Array.isArray(state.config.combos) ? state.config.combos : [];
    (state.config.scoreRules || []).forEach((r) => { if (!r.id) r.id = uid(); });
    (state.config.combos || []).forEach((c) => { if (!c.id) c.id = uid(); });
    loadExpandedState();
    sanitizeExpandedState();

    state.sources = Array.isArray(srcJson.sources) ? srcJson.sources : [];
    renderBase();
    renderRules();
    renderCombos();

    wireBase();
    wireRules();
    wireCombos();

    baseAddBtn?.addEventListener("click", addBase);
    ruleAddBtn?.addEventListener("click", addRule);
    comboAddBtn?.addEventListener("click", addCombo);
    saveBtn?.addEventListener("click", save);
    wireTabPersistence();
    restoreActiveTab();
    setDirty(false);
  }

  boot();
})();
