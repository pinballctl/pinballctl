// Vanilla hardware mapping UI.
(function () {
  const root = document.getElementById("hardware-root");
  if (!root) return;

  const tbody = root.querySelector("#hardware-body");
  const saveBtn = document.getElementById("hardware-save");
  const reloadBtn = document.getElementById("hardware-reload");
  const syncBtn = document.getElementById("hardware-sync");
  const metaEl = document.getElementById("hardware-meta");
  const toastEl = document.getElementById("hardware-toast");
  const errorEl = document.getElementById("hardware-error");
  const dirtyBadge = document.getElementById("hardware-dirty");
  const showAllToggle = document.getElementById("hardware-show-all");
  const syncModalEl = document.getElementById("hardware-sync-modal");
  const syncSpinner = document.getElementById("hardware-sync-spinner");
  const syncStatus = document.getElementById("hardware-sync-status");
  const syncDetail = document.getElementById("hardware-sync-detail");
  const driverConfigModalEl = document.getElementById("hardware-driver-config-modal");
  const driverConfigContextEl = document.getElementById("hardware-driver-config-context");
  const driverConfigFieldsEl = document.getElementById("hardware-driver-config-fields");
  const spinner = document.createElement("div");
  spinner.className = "text-center text-secondary py-3";
  spinner.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading…';

  let pins = [];
  let functions = [];
  let driversByFunction = { "*": ["Default"] };
  let functionProfiles = {};
  let functionAliases = {};
  let mapping = {};
  let dirty = false;
  let syncTimer = null;
  let syncAttempts = 0;
  let syncStartedAtSec = 0;
  let syncModal = null;
  let driverConfigModal = null;
  let showAllPins = false;
  let activeDriverConfigUid = "";
  let bypassUnloadOnce = false;
  const SHOW_ALL_KEY = "hardware.show_all_pins";

  const REPORTED_LABELS = {
    BOOT_STRAP: "BOOT_STRAP – affects boot mode",
    USB_NATIVE: "USB_NATIVE – native USB D+/D-",
    FLASH_BUS: "FLASH_BUS – SPI flash / PSRAM",
    PSRAM_BUS: "PSRAM_BUS – octal PSRAM overlap",
    JTAG_DEBUG: "JTAG_DEBUG – JTAG / debug interface",
    UART_CONSOLE: "UART_CONSOLE – UART used for console / flashing",
    GPIO_FREE: "GPIO_FREE – general-purpose, safe",
    GPIO_LIMITED: "GPIO_LIMITED – GPIO but with caveats",
    RESERVED_INTERNAL: "RESERVED_INTERNAL – not user-accessible",
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return "";
    const parts = new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(d);
    const lookup = (type) => parts.find((p) => p.type === type)?.value || "";
    const day = lookup("day");
    const month = lookup("month");
    const year = lookup("year");
    const hour = lookup("hour");
    const minute = lookup("minute");
    if (!(day && month && year && hour && minute)) return "";
    return `${day} ${month} ${year} ${hour}:${minute}`;
  }

  function setDirty(v) {
    dirty = !!v;
    if (saveBtn) {
      saveBtn.disabled = !dirty;
      saveBtn.setAttribute("aria-disabled", dirty ? "false" : "true");
    }
    if (dirty) dirtyBadge?.classList.remove("d-none");
    else dirtyBadge?.classList.add("d-none");
  }

  function setToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg || "";
    if (msg) toastEl.classList.remove("d-none");
    else toastEl.classList.add("d-none");
  }

  function setError(msg) {
    if (!errorEl) return;
    errorEl.textContent = msg || "";
    errorEl.classList.remove("hardware-error-list");
    if (msg) errorEl.classList.remove("d-none");
    else errorEl.classList.add("d-none");
  }

  function setErrorHtml(html) {
    if (!errorEl) return;
    errorEl.innerHTML = html || "";
    errorEl.classList.add("hardware-error-list");
    if (html) errorEl.classList.remove("d-none");
    else errorEl.classList.add("d-none");
  }

  function showValidationModal(title, html) {
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return false;
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return false;
    const titleEl = modalEl.querySelector(".modal-title");
    const bodyEl = modalEl.querySelector(".modal-body");
    const cancelBtn = modalEl.querySelector('[data-bs-dismiss="modal"]');
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!bodyEl || !confirmBtn) return false;
    if (titleEl) titleEl.textContent = title || "Validation";
    bodyEl.innerHTML = html || "";
    if (cancelBtn) cancelBtn.classList.add("d-none");
    confirmBtn.textContent = "Close";
    confirmBtn.className = "btn btn-primary";
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    const onHidden = () => {
      if (cancelBtn) cancelBtn.classList.remove("d-none");
      confirmBtn.textContent = "Confirm";
      confirmBtn.className = "btn btn-danger";
      confirmBtn.removeEventListener("click", onClose);
    };
    const onClose = () => modal.hide();
    modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
    confirmBtn.addEventListener("click", onClose, { once: true });
    modal.show();
    return true;
  }

  function validationMessage(field, code) {
    const f = String(field || "").trim();
    const c = String(code || "").trim();
    const map = {
      invalid_row: "Row is invalid.",
      too_long: "Friendly name is too long (max 64 chars).",
      unknown_function: "Function is not recognised.",
      invalid_value: f ? `Invalid value for ${f}.` : "Invalid value.",
      requires_pin_type: "Pin type is not valid for this driver.",
      pair_requires_two_pins: "Linked component must have exactly two pins.",
      pair_requires_roles: "Linked component roles are invalid.",
      pair_invalid_pins: "Linked pins are invalid or duplicated.",
      pair_mismatch: "Linked pair values must match on both pins.",
      driver_invalid: f ? `Invalid driver for ${f}.` : "Invalid driver.",
    };
    return map[c] || (c ? c.replaceAll("_", " ") : "Validation error.");
  }

  function issueContext(uid) {
    const key = String(uid || "").trim();
    const row = mapping && typeof mapping === "object" ? mapping[key] : null;
    if (row && typeof row === "object") {
      const friendly = String(row.friendly || "").trim();
      if (friendly) return friendly;
    }
    const pin = (pins || []).find((p) => String(p?.uid || "") === key);
    if (pin) {
      const chan = String(pin.chan || "").trim();
      if (chan) return `Pin ${chan}`;
    }
    const pair = Object.entries(mapping || {})
      .find(([, v]) => v && typeof v === "object" && String(v.componentId || "").trim() === key);
    if (pair) {
      const pRow = pair[1];
      const friendly = String(pRow.friendly || "").trim();
      if (friendly) return friendly;
    }
    return "";
  }

  function renderValidationErrors(errors) {
    const list = Array.isArray(errors) ? errors : [];
    if (!list.length) {
      setError("Validation failed.");
      return;
    }
    const lines = list.slice(0, 12).map((it) => {
      const uid = String(it?.uid || "").trim();
      const field = String(it?.field || "").trim();
      const code = String(it?.error || "").trim();
      const ctx = issueContext(uid);
      const uidLabel = uid ? `<code>${esc(uid)}</code>` : "<code>(unknown)</code>";
      const fieldLabel = field && field !== "*" ? `<code>${esc(field)}</code>` : "<code>row</code>";
      const reason = esc(validationMessage(field, code));
      const extra = ctx ? ` <span class="text-secondary">(${esc(ctx)})</span>` : "";
      return `<div>• ${uidLabel}${extra} · ${fieldLabel} · ${reason}</div>`;
    });
    const more = list.length > 12 ? `<div class="text-secondary">…and ${list.length - 12} more</div>` : "";
    const header = `<div class="fw-semibold mb-2">Validation failed (${list.length} issues)</div>`;
    const details = `${header}${lines.join("")}${more}`;
    setError("");
    if (!showValidationModal("Validation Failed", details)) {
      setErrorHtml(details);
    }
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
    syncBtn.classList.remove("btn-outline-primary", "btn-outline-secondary", "btn-warning", "btn-success", "hardware-sync-btn-muted");
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
    const fallback = () => Promise.resolve(window.confirm("You have unsaved changes. Save before syncing?"));
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

      if (body) body.textContent = "You have unsaved changes. Save before syncing?";
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
    const fallback = () => Promise.resolve(window.confirm("Sync to ESP? Pin values will be changed on the ESP."));
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

      if (body) body.textContent = "Sync to ESP? Pin values will be changed on the ESP.";
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
      const r = await fetch("/api/hardware/sync/status");
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
      if (status.blobType && status.blobType !== "hardware") {
        return;
      }
      if (!status.state) return;
      if (status.state === "done" && status.ok) {
        setSyncStatus("Sync complete", "Hardware applied on ESP.", false);
        refreshSyncWarning();
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
        setSyncStatus("Syncing", `Sending ${status.size || "blob"} bytes…`, true);
      }
    } catch (e) {
      setSyncStatus("Sync failed", "Unable to read sync status.", false);
      stopSyncPoll();
      syncBtn.disabled = false;
    }
  }

  function row(uid) {
    if (!mapping[uid]) mapping[uid] = { friendly: "", function: "", safety: "", driver: "Default" };
    if (!mapping[uid].driver) mapping[uid].driver = "Default";
    return mapping[uid];
  }

  function driverOptionsForFunction(fn) {
    const key = String(normalizeFunction(fn) || "").trim();
    const fallback = Array.isArray(driversByFunction["*"]) && driversByFunction["*"].length
      ? driversByFunction["*"]
      : ["Default"];
    const opts = Array.isArray(driversByFunction[key]) && driversByFunction[key].length
      ? driversByFunction[key]
      : fallback;
    return Array.from(new Set(opts.map((v) => String(v || "").trim()).filter(Boolean)));
  }

  function driverOptionEntriesForFunction(fn) {
    const names = driverOptionsForFunction(fn);
    const fp = functionProfile(fn);
    const drivers = Array.isArray(fp?.drivers) ? fp.drivers : [];
    return names.map((name) => {
      const match = drivers.find((d) => d && typeof d === "object" && String(d.name || "").trim() === name);
      return {
        name,
        label: String(match?.label || name).trim() || name,
      };
    });
  }

  function defaultDriverForFunction(fn) {
    const opts = driverOptionsForFunction(fn);
    return opts.length ? opts[0] : "Default";
  }

  function normalizeFunction(fn) {
    const v = String(fn || "").trim();
    if (!v) return "";
    return String(functionAliases[v] || v);
  }

  function functionProfile(fn) {
    const key = String(normalizeFunction(fn) || "").trim();
    const p = functionProfiles && typeof functionProfiles === "object" ? functionProfiles[key] : null;
    return p && typeof p === "object" ? p : null;
  }

  function driverProfile(fn, driver) {
    const fp = functionProfile(fn);
    const drivers = Array.isArray(fp?.drivers) ? fp.drivers : [];
    const selected = String(driver || "").trim();
    if (selected) {
      const match = drivers.find((d) => d && typeof d === "object" && String(d.name || "") === selected);
      if (match) return match;
    }
    return drivers[0] || null;
  }

  function linkedConfigForRow(rowObj) {
    if (!rowObj || typeof rowObj !== "object") return null;
    const dp = driverProfile(rowObj.function, rowObj.driver);
    if (!dp || typeof dp !== "object") return null;
    const link = dp.link;
    if (!link || typeof link !== "object" || link.enabled !== true) return null;
    return { functionName: normalizeFunction(rowObj.function), driverName: String(dp.name || "Default"), profile: dp, link };
  }

  function isLinkedFunction(fn, driver) {
    return !!linkedConfigForRow({ function: fn, driver: driver || defaultDriverForFunction(fn) });
  }

  function normalizeFieldValue(field, value) {
    if (!field || typeof field !== "object") return value;
    const t = String(field.type || "text").toLowerCase();
    if (t === "number") {
      let n = Number.parseInt(value, 10);
      if (!Number.isFinite(n)) n = Number.parseInt(field.default, 10);
      if (!Number.isFinite(n)) n = 0;
      if (Number.isFinite(Number(field.min))) n = Math.max(Number(field.min), n);
      if (Number.isFinite(Number(field.max))) n = Math.min(Number(field.max), n);
      return n;
    }
    if (t === "hex") {
      let n = Number.parseInt(String(value || field.default || "0x00"), 0);
      if (!Number.isFinite(n)) n = Number.parseInt(String(field.default || "0x00"), 0);
      if (!Number.isFinite(n)) n = 0;
      const min = Number.isFinite(Number(field.min)) ? Number(field.min) : 0;
      const max = Number.isFinite(Number(field.max)) ? Number(field.max) : 255;
      n = Math.max(min, Math.min(max, n));
      return `0x${n.toString(16).padStart(2, "0")}`;
    }
    if (t === "select") {
      const options = Array.isArray(field.options) ? field.options.map((v) => String(v || "").trim()).filter(Boolean) : [];
      const v = String(value || field.default || "").trim();
      if (!options.length) return v;
      return options.includes(v) ? v : options[0];
    }
    return String(value ?? field.default ?? "").trim();
  }

  function oppositeRole(linkCfg, role) {
    const roles = Array.isArray(linkCfg?.roles) ? linkCfg.roles.map((v) => String(v || "").trim().toUpperCase()).filter(Boolean) : [];
    if (roles.length < 2) return "";
    const r = String(role || "").trim().toUpperCase();
    if (r && roles[0] === r) return roles[1];
    return roles[0];
  }

  function sanitizeComponentId(raw, prefix = "comp") {
    const s = String(raw || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
    return s || `${prefix}-1`;
  }

  function deriveComponentId(linkCfg, primaryUid, secondaryUid = "") {
    const prefix = String(linkCfg?.componentIdPrefix || "comp").trim() || "comp";
    const a = sanitizeComponentId(primaryUid, prefix);
    const b = sanitizeComponentId(secondaryUid, prefix);
    if (b) {
      return `${prefix}-${a}-${b}`;
    }
    return `${prefix}-${a}`;
  }

  function pinKeyFromUid(uid) {
    const parts = String(uid || "").split("__");
    if (parts.length < 4) return String(uid || "");
    return `${parts[parts.length - 3]}__${parts[parts.length - 2]}__${parts[parts.length - 1]}`;
  }

  function pinKey(pin) {
    if (!pin || typeof pin !== "object") return "";
    if (pin.uid) return pinKeyFromUid(pin.uid);
    return `${pin.board || ""}__${pin.type || ""}__${pin.chan || ""}`;
  }

  function releaseLinkedSecondary(primaryUid, linkCfg) {
    const primary = row(primaryUid);
    const secKey = String(linkCfg?.secondaryUidField || "secondaryPinUid").trim();
    const linkedKey = String(linkCfg?.linkedPrimaryField || "linkedPrimaryUid").trim();
    const compKey = String(linkCfg?.componentIdField || "componentId").trim();
    const roleKey = String(linkCfg?.roleField || "componentRole").trim();
    const oldSecondaryUid = String(primary[secKey] || "").trim();
    if (!oldSecondaryUid) return;
    const secondary = row(oldSecondaryUid);
    if (String(secondary[linkedKey] || "").trim() === String(primaryUid)) {
      delete secondary[linkedKey];
      delete secondary[compKey];
      delete secondary[roleKey];
      const fp = functionProfile(primary.function);
      const drivers = Array.isArray(fp?.drivers) ? fp.drivers : [];
      drivers.forEach((d) => {
        const settings = Array.isArray(d?.settings) ? d.settings : [];
        settings.forEach((fld) => {
          const k = String(fld?.key || "").trim();
          if (k) delete secondary[k];
        });
      });
      if (isLinkedFunction(secondary.function, secondary.driver)) secondary.function = "";
    }
    delete primary[secKey];
  }

  function syncLinkedPair(primaryUid, secondaryUid) {
    const primary = row(primaryUid);
    primary.function = normalizeFunction(primary.function);
    const linked = linkedConfigForRow(primary);
    if (!linked) return;
    const { functionName, driverName, profile, link } = linked;
    const roles = Array.isArray(link.roles) ? link.roles.map((v) => String(v || "").trim().toUpperCase()).filter(Boolean) : [];
    const roleKey = String(link.roleField || "componentRole").trim();
    const secKey = String(link.secondaryUidField || "secondaryPinUid").trim();
    const linkedKey = String(link.linkedPrimaryField || "linkedPrimaryUid").trim();
    const compKey = String(link.componentIdField || "componentId").trim();
    const role = roles.includes(String(primary[roleKey] || "").trim().toUpperCase()) ? String(primary[roleKey]).trim().toUpperCase() : (roles[0] || "");
    primary[roleKey] = role;
    primary[compKey] = deriveComponentId(link, primaryUid, secondaryUid);
    primary.driver = driverName;
    const settings = Array.isArray(profile?.settings) ? profile.settings : [];
    settings.forEach((fld) => {
      const k = String(fld?.key || "").trim();
      if (!k) return;
      primary[k] = normalizeFieldValue(fld, primary[k]);
    });
    releaseLinkedSecondary(primaryUid, link);
    const secUid = String(secondaryUid || "").trim();
    if (!secUid || secUid === primaryUid) return;
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (uid === primaryUid || !cfg || typeof cfg !== "object") return;
      if (String(cfg[secKey] || "").trim() !== secUid) return;
      delete cfg[secKey];
      if (String(row(secUid)[linkedKey] || "").trim() === String(uid)) {
        delete row(secUid)[linkedKey];
      }
    });
    const secondary = row(secUid);
    const secondaryRole = oppositeRole(link, primary[roleKey]);
    secondary.function = functionName;
    secondary[compKey] = primary[compKey];
    secondary[roleKey] = secondaryRole;
    secondary[linkedKey] = primaryUid;
    settings.forEach((fld) => {
      const k = String(fld?.key || "").trim();
      if (!k) return;
      secondary[k] = primary[k];
    });
    secondary.driver = driverName;
    secondary.friendly = String(primary.friendly || "").trim();
    primary[secKey] = secUid;
  }

  function primaryForSecondary(uid, linkCfg) {
    const targetUid = String(uid || "").trim();
    if (!targetUid) return "";
    const secKey = String(linkCfg?.secondaryUidField || "secondaryPinUid").trim();
    const linkedKey = String(linkCfg?.linkedPrimaryField || "linkedPrimaryUid").trim();
    for (const [candidateUid, cfg] of Object.entries(mapping || {})) {
      if (!cfg || typeof cfg !== "object") continue;
      const linked = linkedConfigForRow(cfg);
      if (!linked) continue;
      if (String(cfg[linkedKey] || "").trim()) continue;
      if (String(cfg[secKey] || "").trim() !== targetUid) continue;
      return String(candidateUid);
    }
    return "";
  }

  function resolvePrimaryUidForLinked(uid) {
    const requested = String(uid || "").trim();
    if (!requested) return "";
    const cfg = row(requested);
    const linked = linkedConfigForRow(cfg);
    if (!linked) return requested;
    const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
    const linkedKey = String(linked.link.linkedPrimaryField || "linkedPrimaryUid").trim();
    const secUid = String(cfg[secKey] || "").trim();
    if (secUid) return requested;
    const linkedPrimary = String(cfg[linkedKey] || "").trim();
    if (linkedPrimary) return linkedPrimary;
    const scanned = primaryForSecondary(requested, linked.link);
    return scanned || requested;
  }

  function normalizeLinkedBindings() {
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      cfg.function = normalizeFunction(cfg.function);
      const linked = linkedConfigForRow(cfg);
      if (!linked) return;
      const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
      const linkedKey = String(linked.link.linkedPrimaryField || "linkedPrimaryUid").trim();
      const sec = String(cfg[secKey] || "").trim();
      const lp = String(cfg[linkedKey] || "").trim();
      if (sec && lp) {
        delete cfg[linkedKey];
      }
      if (sec && sec === uid) {
        delete cfg[secKey];
      }
    });

    // Break stale mutual-primary cycles deterministically (keep lexicographically smaller uid as primary).
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      const linked = linkedConfigForRow(cfg);
      if (!linked) return;
      const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
      const sec = String(cfg[secKey] || "").trim();
      if (!sec || sec === uid) return;
      const other = mapping[sec];
      if (!other || typeof other !== "object") return;
      const back = String(other[secKey] || "").trim();
      if (back !== uid) return;
      if (uid < sec) {
        delete other[secKey];
      } else {
        delete cfg[secKey];
      }
    });

    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      const linked = linkedConfigForRow(cfg);
      if (!linked) {
        return;
      }
      const { functionName, driverName, profile, link } = linked;
      const secKey = String(link.secondaryUidField || "secondaryPinUid").trim();
      const linkedKey = String(link.linkedPrimaryField || "linkedPrimaryUid").trim();
      const roleKey = String(link.roleField || "componentRole").trim();
      const compKey = String(link.componentIdField || "componentId").trim();
      const roles = Array.isArray(link.roles) ? link.roles.map((v) => String(v || "").trim().toUpperCase()).filter(Boolean) : [];
      const settings = Array.isArray(profile?.settings) ? profile.settings : [];
      const secUid = String(cfg[secKey] || "").trim();
      if (!secUid || secUid === uid) {
        delete cfg[secKey];
        return;
      }
      if (!mapping[secUid]) mapping[secUid] = { friendly: "", function: "", safety: "" };
      const primary = row(uid);
      const secondary = row(secUid);
      primary.function = functionName;
      primary.driver = driverName;
      const role = roles.includes(String(primary[roleKey] || "").trim().toUpperCase()) ? String(primary[roleKey]).trim().toUpperCase() : (roles[0] || "");
      primary[roleKey] = role;
      primary[compKey] = deriveComponentId(link, uid, secUid);
      settings.forEach((fld) => {
        const k = String(fld?.key || "").trim();
        if (!k) return;
        primary[k] = normalizeFieldValue(fld, primary[k]);
      });

      secondary.function = functionName;
      secondary[linkedKey] = uid;
      delete secondary[secKey];
      secondary[roleKey] = oppositeRole(link, role);
      secondary[compKey] = primary[compKey];
      settings.forEach((fld) => {
        const k = String(fld?.key || "").trim();
        if (!k) return;
        secondary[k] = primary[k];
      });
      secondary.driver = driverName;
      secondary.friendly = String(primary.friendly || "").trim();
    });

    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      const linked = linkedConfigForRow(cfg);
      if (!linked) return;
      const linkedKey = String(linked.link.linkedPrimaryField || "linkedPrimaryUid").trim();
      const lp = String(cfg[linkedKey] || "").trim();
      if (!lp) return;
      if (primaryForSecondary(uid, linked.link) !== lp) {
        delete cfg[linkedKey];
      }
    });
  }

  function linkedCandidates(primaryUid, linkCfg) {
    const reqPinType = String(linkCfg?.requirePinType || "").trim().toUpperCase();
    return pins
      .filter((pin) => {
        if (String(pin.uid || "") === String(primaryUid || "")) return false;
        if (reqPinType && String(pin.type || "").toUpperCase() !== reqPinType) return false;
        return true;
      })
      .map((pin) => {
        const chan = String(pin.chan || "").trim();
        const label = `${pin.uid}${chan ? ` (${chan})` : ""}`;
        return { value: String(pin.uid || ""), label };
      });
  }

  function renderDriverConfigModal(uid) {
    const key = String(uid || "").trim();
    if (!key) return;
    const pin = (pins || []).find((p) => String(p.uid || "") === key);
    const cfg = row(key);
    const linked = linkedConfigForRow(cfg);
    if (!linked || !driverConfigFieldsEl) return;
    const { profile, link } = linked;
    const roleKey = String(link.roleField || "componentRole").trim();
    const secKey = String(link.secondaryUidField || "secondaryPinUid").trim();
    const roles = Array.isArray(link.roles) ? link.roles.map((v) => String(v || "").trim().toUpperCase()).filter(Boolean) : [];
    const role = roles.includes(String(cfg[roleKey] || "").trim().toUpperCase()) ? String(cfg[roleKey]).trim().toUpperCase() : (roles[0] || "");
    const secondaryRole = oppositeRole(link, role);
    const secUid = String(cfg[secKey] || "").trim();
    const options = linkedCandidates(key, link);

    if (driverConfigContextEl) {
      const friendly = String(cfg.friendly || "").trim();
      const chan = String(pin?.chan || "").trim();
      const suffix = chan ? `GPIO ${chan}` : key;
      const primaryChan = String((pin?.chan ?? "")).trim();
      const primaryText = primaryChan ? `Primary: GPIO ${primaryChan}` : `Primary: ${key}`;
      const secondaryPin = (pins || []).find((p) => String(p?.uid || "") === secUid);
      const secondaryChan = String((secondaryPin?.chan ?? "")).trim();
      const secondaryText = secUid
        ? (secondaryChan ? `Secondary: GPIO ${secondaryChan}` : `Secondary: ${secUid}`)
        : "Secondary: not selected";
      const compId = String(cfg.componentId || "").trim();
      const compText = compId ? `Component: ${compId}` : "Component: (not set)";
      driverConfigContextEl.innerHTML = `
        <div>${esc(friendly || key)} (${esc(suffix)})</div>
        <div class="text-secondary small mt-1">${esc(primaryText)} · ${esc(secondaryText)}</div>
        <div class="text-secondary small">${esc(compText)}</div>
      `;
    }
    const settings = Array.isArray(profile?.settings) ? profile.settings : [];
    const roleRow = `
      <div class="hardware-driver-item">
        <label for="hardware-driver-link-role">This Pin Role</label>
        <div class="hardware-driver-control">
          <select class="form-select form-select-sm" id="hardware-driver-link-role">
            ${roles.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("")}
          </select>
          <small class="hardware-driver-help">Defines the role of this pin in the linked driver pair.</small>
        </div>
      </div>`;
    const secRow = `
      <div class="hardware-driver-item">
        <label for="hardware-driver-link-secondary">Secondary Pin (${esc(secondaryRole)})</label>
        <div class="hardware-driver-control">
          <select class="form-select form-select-sm" id="hardware-driver-link-secondary">
            <option value="">Select secondary pin…</option>
            ${options.map((opt) => `<option value="${esc(opt.value)}">${esc(opt.label)}</option>`).join("")}
          </select>
          <small class="hardware-driver-help">Select the partner pin for the opposite role.</small>
        </div>
      </div>`;
    const settingRows = settings.map((fld) => {
      const keyName = String(fld?.key || "").trim();
      if (!keyName) return "";
      const id = `hardware-driver-setting-${keyName}`;
      const label = String(fld.label || keyName);
      const help = String(fld.help || "");
      const val = normalizeFieldValue(fld, cfg[keyName]);
      cfg[keyName] = val;
      let control = "";
      const t = String(fld.type || "text").toLowerCase();
      if (t === "number") {
        const minAttr = Number.isFinite(Number(fld.min)) ? ` min="${Number(fld.min)}"` : "";
        const maxAttr = Number.isFinite(Number(fld.max)) ? ` max="${Number(fld.max)}"` : "";
        control = `<input class="form-control form-control-sm" id="${id}" data-setting-key="${esc(keyName)}" type="number" value="${esc(val)}"${minAttr}${maxAttr}>`;
      } else if (t === "select") {
        const optionsHtml = (Array.isArray(fld.options) ? fld.options : []).map((o) => {
          const ov = String(o || "");
          const sel = ov === String(val) ? " selected" : "";
          return `<option value="${esc(ov)}"${sel}>${esc(ov)}</option>`;
        }).join("");
        control = `<select class="form-select form-select-sm" id="${id}" data-setting-key="${esc(keyName)}">${optionsHtml}</select>`;
      } else {
        control = `<input class="form-control form-control-sm" id="${id}" data-setting-key="${esc(keyName)}" value="${esc(val)}">`;
      }
      return `<div class="hardware-driver-item"><label for="${id}">${esc(label)}</label><div class="hardware-driver-control">${control}${help ? `<small class="hardware-driver-help">${esc(help)}</small>` : ""}</div></div>`;
    }).join("");
    driverConfigFieldsEl.innerHTML = `${roleRow}${secRow}${settingRows}`;
    const roleInput = driverConfigFieldsEl.querySelector("#hardware-driver-link-role");
    const secondaryInput = driverConfigFieldsEl.querySelector("#hardware-driver-link-secondary");
    if (roleInput) roleInput.value = role;
    if (secondaryInput) secondaryInput.value = secUid;
  }

  function openDriverConfigModal(uid) {
    const requestedUid = String(uid || "").trim();
    if (!requestedUid) return;
    const resolvedUid = resolvePrimaryUidForLinked(requestedUid);
    activeDriverConfigUid = resolvedUid;
    if (!activeDriverConfigUid || !isLinkedFunction(row(activeDriverConfigUid).function, row(activeDriverConfigUid).driver)) return;
    if (!driverConfigModal && driverConfigModalEl && window.bootstrap?.Modal) {
      driverConfigModal = bootstrap.Modal.getOrCreateInstance(driverConfigModalEl);
    }
    renderDriverConfigModal(activeDriverConfigUid);
    driverConfigModal?.show();
  }

  function render() {
    normalizeLinkedBindings();
    tbody.innerHTML = "";
    if (!pins.length) {
      tbody.innerHTML = '<tr><td colspan="11" class="text-center text-secondary py-3">No pins loaded. Click Reload Pins to fetch from ESP.</td></tr>';
      return;
    }

    const visiblePins = showAllPins ? pins : pins.filter((p) => p.safe !== false);
    if (!visiblePins.length) {
      tbody.innerHTML = '<tr><td colspan="11" class="text-center text-secondary py-3">No mappable pins. Enable “Show all Pins” to view reserved pins.</td></tr>';
      return;
    }

    const frag = document.createDocumentFragment();
    visiblePins.forEach((p) => {
      const reportedKey = (p.reported || "").toUpperCase();
      const reportedLabel = REPORTED_LABELS[reportedKey] || "";
      const notes = p.notes || "";
      let noteText = notes || reportedLabel || "-";
      if (noteText.includes(" · ")) {
        noteText = noteText.split(" · ").pop() || noteText;
      }
      const tr = document.createElement("tr");
      const typeLabel = p.safe === false
        ? `Reserved <small class="text-secondary d-block">${p.type || ""}</small>`
        : (p.type || "-");
      const typeClass = reportedKey === "GPIO_FREE" ? "text-success" : "";
      const canMap = p.safe !== false;
      const isGpioPin = String(p.type || "").toUpperCase() === "GPIO";
      tr.innerHTML = `
        <td class="text-monospace small">${p.uid}</td>
        <td>${p.board || "-"}</td>
        <td class="${typeClass}">${typeLabel}</td>
        <td class="small text-secondary">${noteText}</td>
        <td class="text-center">${p.chan || "-"}</td>
        <td>${typeof p.state === "number" ? (p.state ? "High" : "Low") : "-"}</td>
        <td></td>
        <td></td>
        <td></td>
        <td></td>
        <td class="text-center"></td>
      `;

      const r = row(p.uid);
      r.function = normalizeFunction(r.function);
      const linkedMeta = linkedConfigForRow(r);
      const linkedKeyForRow = String(linkedMeta?.link?.linkedPrimaryField || "linkedPrimaryUid").trim();
      const primaryByScan = linkedMeta ? primaryForSecondary(p.uid, linkedMeta.link) : "";
      const boundPrimaryUid = String(primaryByScan || r[linkedKeyForRow] || "").trim();
      const isLinkedBoundReadonly = !!boundPrimaryUid && boundPrimaryUid !== p.uid;

      const friendlyInput = document.createElement("input");
      friendlyInput.className = "form-control form-control-sm";
      friendlyInput.value = r.friendly || "";
      const isLocked = !canMap;
      if (!isLocked && !isLinkedBoundReadonly) {
        friendlyInput.addEventListener("input", (e) => {
          row(p.uid).friendly = e.target.value;
          const linked = linkedConfigForRow(row(p.uid));
          if (linked) {
            const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
            const secUid = String(row(p.uid)[secKey] || "").trim();
            if (secUid) row(secUid).friendly = e.target.value;
          }
          setDirty(true);
        });
      }
      const safetyCell = tr.children[6];
      if (isGpioPin && !isLocked) {
        const safetySelect = document.createElement("select");
        safetySelect.className = "form-select form-select-sm";
        safetySelect.innerHTML = `
          <option value="">DEFAULT</option>
          <option value="HIGH">HIGH</option>
          <option value="LOW">LOW</option>
        `;
        safetySelect.value = row(p.uid).safety || "";
        safetySelect.addEventListener("change", (e) => {
          row(p.uid).safety = e.target.value || "";
          setDirty(true);
        });
        safetyCell.appendChild(safetySelect);
      }

      if (!isLocked) {
        const friendlyWrap = document.createElement("div");
        friendlyWrap.className = "d-flex align-items-center gap-2";
        if (isLinkedBoundReadonly) {
          friendlyInput.readOnly = true;
          friendlyInput.classList.add("bg-body-tertiary");
        }
        friendlyWrap.appendChild(friendlyInput);
        if (isLinkedBoundReadonly) {
          const lock = document.createElement("span");
          lock.className = "hardware-friendly-lock";
          lock.title = `Inherited from ${boundPrimaryUid}`;
          lock.innerHTML = '<i class="fa fa-lock" aria-hidden="true"></i>';
          tr.children[10].appendChild(lock);
        }
        tr.children[7].appendChild(friendlyWrap);
      }

      const fnSelect = document.createElement("select");
      fnSelect.className = "form-select form-select-sm";
      fnSelect.innerHTML = `<option value="">(None)</option>${functions.map(fn => `<option value="${fn}">${fn}</option>`).join("")}`;
      fnSelect.value = r.function || "";
      fnSelect.disabled = isLinkedBoundReadonly;
      const fnCell = tr.children[8];
      const driverCell = tr.children[9];
      const actionCell = tr.children[10];
      const fnWrap = document.createElement("div");
      fnWrap.className = "d-flex align-items-center gap-2";
      fnWrap.appendChild(fnSelect);
      if (!isLocked) {
        fnSelect.addEventListener("change", (e) => {
          const val = e.target.value || "";
          const r = row(p.uid);
          const oldLinked = linkedConfigForRow(r);
          if (oldLinked) {
            releaseLinkedSecondary(p.uid, oldLinked.link);
          }
          r.function = normalizeFunction(val);
          r.driver = defaultDriverForFunction(r.function);
          const nextLinked = linkedConfigForRow(r);
          if (nextLinked) {
            const roleKey = String(nextLinked.link.roleField || "componentRole").trim();
            const roles = Array.isArray(nextLinked.link.roles) ? nextLinked.link.roles.map((x) => String(x || "").trim().toUpperCase()).filter(Boolean) : [];
            if (!r[roleKey]) r[roleKey] = roles[0] || "";
            const settings = Array.isArray(nextLinked.profile?.settings) ? nextLinked.profile.settings : [];
            settings.forEach((fld) => {
              const k = String(fld?.key || "").trim();
              if (!k) return;
              r[k] = normalizeFieldValue(fld, r[k]);
            });
          } else if (activeDriverConfigUid === String(p.uid || "")) {
            activeDriverConfigUid = "";
            driverConfigModal?.hide();
          }
          setDirty(true);
          render();
        });
        fnCell.appendChild(fnWrap);
      }

      const driverSelect = document.createElement("select");
      driverSelect.className = "form-select form-select-sm";
      const driverOptions = driverOptionsForFunction(r.function);
      const driverEntries = driverOptionEntriesForFunction(r.function);
      const selectedDriver = String(r.driver || "").trim() || defaultDriverForFunction(r.function);
      driverSelect.innerHTML = driverEntries.map((d) => `<option value="${esc(d.name)}">${esc(d.label)}</option>`).join("");
      if (!driverOptions.includes(selectedDriver)) {
        driverSelect.innerHTML = `<option value="${esc(selectedDriver)}">${esc(selectedDriver)}</option>${driverSelect.innerHTML}`;
      }
      driverSelect.value = selectedDriver;
      driverSelect.disabled = isLinkedBoundReadonly || !String(r.function || "").trim();
      if (!isLocked && !isLinkedBoundReadonly) {
        driverSelect.addEventListener("change", (e) => {
          row(p.uid).driver = String(e.target.value || "Default").trim() || "Default";
          const linked = linkedConfigForRow(row(p.uid));
          if (linked) {
            const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
            const secUid = String(row(p.uid)[secKey] || "").trim();
            if (secUid) row(secUid).driver = row(p.uid).driver;
          }
          setDirty(true);
        });
      }
      if (String(r.function || "").trim() && !isLinkedBoundReadonly) {
        driverCell.appendChild(driverSelect);
      } else {
        driverCell.innerHTML = "";
      }

      const activeLinked = linkedConfigForRow(r);
      if (!isLocked && activeLinked && !isLinkedBoundReadonly) {
        const cfgBtn = document.createElement("button");
        cfgBtn.type = "button";
        cfgBtn.className = "btn btn-outline-secondary btn-sm hardware-driver-config-btn";
        cfgBtn.title = "Configure Driver";
        cfgBtn.setAttribute("aria-label", "Configure Driver");
        cfgBtn.innerHTML = '<i class="fa fa-sliders" aria-hidden="true"></i>';
        cfgBtn.addEventListener("click", () => openDriverConfigModal(p.uid));
        actionCell.appendChild(cfgBtn);
      }

      if (isLinkedBoundReadonly) {
        const linked = row(boundPrimaryUid);
        const inherited = String(linked.friendly || "").trim();
        if (inherited && r.friendly !== inherited) {
          r.friendly = inherited;
          friendlyInput.value = inherited;
        }
        const inheritedDriver = String(linked.driver || "").trim() || "Default";
        if (inheritedDriver && r.driver !== inheritedDriver) {
          r.driver = inheritedDriver;
          driverSelect.value = inheritedDriver;
        }
      }

      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  }

  async function loadMeta() {
    const r = await fetch("/api/hardware/meta");
    const j = await r.json();
    functions = j.functions || [];
    driversByFunction = (j && j.drivers && typeof j.drivers === "object") ? j.drivers : { "*": ["Default"] };
    functionProfiles = (j && j.functionProfiles && typeof j.functionProfiles === "object") ? j.functionProfiles : {};
    functionAliases = (j && j.aliases && typeof j.aliases === "object") ? j.aliases : {};
  }

  async function loadPins() {
    const r = await fetch("/api/hardware/pins");
    const j = await r.json();
    pins = j.pins || [];
    const controller = j.controller || "";
    const reloadedAt = j.reloadedAt || "";
    const source = j.source || "";
    const prettyDate = formatDate(reloadedAt);
    let sourceLabel = "";
    if (source === "esp") sourceLabel = "ESP";
    else if (source === "defaults") sourceLabel = "Defaults";
    else if (source) sourceLabel = source;
    if (metaEl) {
      const bits = [];
      if (controller) bits.push(`Controller: ${controller}`);
      if (prettyDate) bits.push(`Reloaded: ${prettyDate}`);
      if (sourceLabel) bits.push(`Source: ${sourceLabel}`);
      metaEl.textContent = bits.join(" · ");
    }
    if (j.usingDefaults) setToast("Using default pin set (no live hardware data)");
  }

  async function loadMapping() {
    const r = await fetch("/api/hardware/mapping");
    mapping = await r.json();
    normalizeLinkedBindings();
    setDirty(false);
  }

  function handleDriverConfigFieldChange(target) {
    const uid = resolvePrimaryUidForLinked(activeDriverConfigUid);
    if (!uid) return;
    const cfg = row(uid);
    const linked = linkedConfigForRow(cfg);
    if (!linked) return;
    if (!(target instanceof HTMLElement)) return;
    const roleKey = String(linked.link.roleField || "componentRole").trim();
    const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
    if (target.id === "hardware-driver-link-role") {
      cfg[roleKey] = String(target.value || "").trim().toUpperCase();
      const secUid = String(cfg[secKey] || "").trim();
      if (secUid) syncLinkedPair(uid, secUid);
    } else if (target.id === "hardware-driver-link-secondary") {
      const secUid = String(target.value || "").trim();
      syncLinkedPair(uid, secUid);
    } else {
      const settingKey = String(target.getAttribute("data-setting-key") || "").trim();
      if (!settingKey) return;
      const field = (Array.isArray(linked.profile?.settings) ? linked.profile.settings : [])
        .find((f) => String(f?.key || "").trim() === settingKey);
      cfg[settingKey] = normalizeFieldValue(field, target.value);
      const secUid = String(cfg[secKey] || "").trim();
      if (secUid) syncLinkedPair(uid, secUid);
    }
    setDirty(true);
    renderDriverConfigModal(uid);
    render();
  }

  function flushDriverConfigFormToMapping() {
    const uid = resolvePrimaryUidForLinked(activeDriverConfigUid);
    if (!uid || !driverConfigFieldsEl) return;
    const cfg = row(uid);
    const linked = linkedConfigForRow(cfg);
    if (!linked) return;
    const roleKey = String(linked.link.roleField || "componentRole").trim();
    const secKey = String(linked.link.secondaryUidField || "secondaryPinUid").trim();
    const roleEl = driverConfigFieldsEl.querySelector("#hardware-driver-link-role");
    const secEl = driverConfigFieldsEl.querySelector("#hardware-driver-link-secondary");

    if (roleEl && "value" in roleEl) {
      cfg[roleKey] = String(roleEl.value || "").trim().toUpperCase();
    }

    const secUid = secEl && "value" in secEl ? String(secEl.value || "").trim() : String(cfg[secKey] || "").trim();
    if (secUid) {
      syncLinkedPair(uid, secUid);
    }

    const settingEls = driverConfigFieldsEl.querySelectorAll("[data-setting-key]");
    settingEls.forEach((node) => {
      const settingKey = String(node.getAttribute("data-setting-key") || "").trim();
      if (!settingKey || !("value" in node)) return;
      const field = (Array.isArray(linked.profile?.settings) ? linked.profile.settings : [])
        .find((f) => String(f?.key || "").trim() === settingKey);
      cfg[settingKey] = normalizeFieldValue(field, node.value);
    });
  }

  async function save() {
    setError("");
    setToast("");
    saveBtn.disabled = true;
    try {
      // Persist any in-progress modal values even if browser change/input didn't fire.
      flushDriverConfigFormToMapping();
      // Ensure linked pair metadata is complete before persisting.
      normalizeLinkedBindings();
      const r = await fetch("/api/hardware/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mapping),
      });
      if (r.status === 422) {
        const j = await r.json();
        renderValidationErrors(j.errors);
        console.warn("Validation errors", j.errors);
        return false;
      }
      const j = await r.json();
      if (j.ok) {
        setToast(`Saved at ${j.updatedAt || "now"}`);
        setDirty(false);
        await loadSyncStatus();
        return true;
      } else {
        setError(j.error || "Save failed");
        return false;
      }
    } catch (e) {
      setError("Save failed");
      return false;
    } finally {
      if (saveBtn) {
        saveBtn.disabled = !dirty;
        saveBtn.setAttribute("aria-disabled", dirty ? "false" : "true");
      }
    }
  }

  async function syncToEsp() {
    setError("");
    setToast("");
    let skipSyncConfirm = false;
    if (dirty) {
      const proceed = await confirmSaveBeforeSync();
      if (!proceed) return;
      const saved = await save();
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
      setSyncStatus("Starting sync…", "Building mapping.pb and preparing transfer.", true);
    try {
      const r = await fetch("/api/hardware/sync", { method: "POST" });
      const j = await r.json();
      if (!j.ok) {
        if (j.error === "bridge_not_connected") {
          setSyncStatus("Bridge offline", "Connect the ESP and start the bridge, then try again.", false);
        } else if (j.error === "bridge_unresponsive" || j.error === "bridge_unreachable") {
          setSyncStatus("Bridge unresponsive", "No response from ESP. Check the USB connection and try again.", false);
        } else {
          setSyncStatus("Sync failed", j.error || "Sync failed", false);
        }
        syncBtn.disabled = false;
        return;
      }
      syncStartedAtSec = Date.now() / 1000;
      setSyncStatus("Sync running", "Sending mapping.pb to the ESP…", true);
      syncTimer = setInterval(pollSyncStatus, 1000);
      pollSyncStatus();
    } catch (e) {
      setSyncStatus("Sync failed", "Request error while starting sync.", false);
      syncBtn.disabled = false;
      syncStartedAtSec = 0;
    }
  }

  async function reloadPins() {
    setError("");
    setToast("");
    if (tbody) {
      tbody.innerHTML = "";
      tbody.appendChild(spinner.cloneNode(true));
    }
    reloadBtn.disabled = true;
    try {
      const before = new Set(pins.map((p) => p.uid));
      const r = await fetch("/api/hardware/reload?source=esp", { method: "POST" });
      const j = await r.json();
      const priorByUid = mapping || {};
      const priorByKey = {};
      Object.entries(priorByUid || {}).forEach(([uid, cfg]) => {
        const k = pinKeyFromUid(uid);
        if (!k || !cfg || typeof cfg !== "object") return;
        if (!priorByKey[k]) priorByKey[k] = cfg;
      });
      const newMap = {};
      for (const p of j.pins || []) {
        const k = pinKey(p);
        const preserved = priorByUid[p.uid] || (k ? priorByKey[k] : null);
        newMap[p.uid] = preserved || { friendly: "", function: "", safety: "" };
      }
      mapping = newMap;
      pins = j.pins || [];

      const added = Array.isArray(j.added) ? j.added.length : 0;
      const removed = Array.isArray(j.removed) ? j.removed.length : 0;
      setToast(`Reloaded ${j.count ?? pins.length} pins (+${added} / -${removed})`);
      render();
      setDirty(true);
    } catch (e) {
      setError("Reload failed");
    } finally {
      reloadBtn.disabled = false;
    }
  }

  async function init() {
    window.addEventListener("beforeunload", (e) => {
      if (!dirty) return;
      if (bypassUnloadOnce) {
        bypassUnloadOnce = false;
        return;
      }
      e.preventDefault();
      e.returnValue = "";
    });

    document.addEventListener("click", (e) => {
      const link = e.target && e.target.closest ? e.target.closest("a[href]") : null;
      if (!link) return;
      const href = String(link.getAttribute("href") || "");
      if (!href || href.startsWith("#") || link.hasAttribute("download")) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      if (String(link.getAttribute("target") || "").toLowerCase() === "_blank") return;
      if (!dirty) return;
      e.preventDefault();
      e.stopPropagation();
      confirmLeaveWithUnsaved().then((ok) => {
        if (!ok) return;
        bypassUnloadOnce = true;
        window.location.href = link.href;
      });
    }, true);

    document.addEventListener("submit", (e) => {
      if (!dirty) return;
      e.preventDefault();
      e.stopPropagation();
      confirmLeaveWithUnsaved().then((ok) => {
        if (!ok) return;
        bypassUnloadOnce = true;
        HTMLFormElement.prototype.submit.call(e.target);
      });
    }, true);

    if (showAllToggle) {
      const stored = localStorage.getItem(SHOW_ALL_KEY);
      showAllPins = stored === "true";
      showAllToggle.checked = showAllPins;
      showAllToggle.addEventListener("change", () => {
        showAllPins = showAllToggle.checked;
        localStorage.setItem(SHOW_ALL_KEY, showAllPins ? "true" : "false");
        render();
      });
    }

    if (driverConfigModalEl && window.bootstrap?.Modal) {
      driverConfigModal = bootstrap.Modal.getOrCreateInstance(driverConfigModalEl);
      driverConfigModalEl.addEventListener("hidden.bs.modal", () => {
        activeDriverConfigUid = "";
      });
    }
    driverConfigFieldsEl?.addEventListener("change", (e) => handleDriverConfigFieldChange(e.target));
    driverConfigFieldsEl?.addEventListener("input", (e) => handleDriverConfigFieldChange(e.target));

    try {
      await loadMeta();
      await loadPins();
      await loadMapping();
      render();
      await loadSyncStatus();
    } catch (e) {
      console.error(e);
      setError("Failed to load hardware data");
    }
  }

  async function loadSyncStatus() {
    try {
      const r = await fetch("/api/esplink/sync/status", { cache: "no-store" });
      const j = await r.json();
      if (j?.espConnected !== true) {
        setSyncUiState("unknown");
        return false;
      } else if (j?.hardware?.inSync === false) {
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

  saveBtn?.addEventListener("click", save);
  reloadBtn?.addEventListener("click", reloadPins);
  syncBtn?.addEventListener("click", syncToEsp);

  init();
})();
