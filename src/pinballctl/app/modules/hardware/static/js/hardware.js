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
  const lcdConfigModalEl = document.getElementById("hardware-lcd-config-modal");
  const lcdConfigContextEl = document.getElementById("hardware-lcd-config-context");
  const lcdRoleInput = document.getElementById("hardware-lcd-role");
  const lcdSecondaryInput = document.getElementById("hardware-lcd-secondary");
  const lcdSecondaryLabel = document.getElementById("hardware-lcd-secondary-label");
  const lcdAddrInput = document.getElementById("hardware-lcd-address");
  const lcdColsInput = document.getElementById("hardware-lcd-cols");
  const lcdRowsInput = document.getElementById("hardware-lcd-rows");
  const spinner = document.createElement("div");
  spinner.className = "text-center text-secondary py-3";
  spinner.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading…';

  let pins = [];
  let functions = [];
  let mapping = {};
  let dirty = false;
  let syncTimer = null;
  let syncAttempts = 0;
  let syncStartedAtSec = 0;
  let syncModal = null;
  let lcdConfigModal = null;
  let showAllPins = false;
  let activeLcdUid = "";
  let bypassUnloadOnce = false;
  const SHOW_ALL_KEY = "hardware.show_all_pins";
  const LCD_FUNCTION = "LCD Display";

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

  function validationMessage(field, code) {
    const f = String(field || "").trim();
    const c = String(code || "").trim();
    const map = {
      invalid_row: "Row is invalid.",
      too_long: "Friendly name is too long (max 64 chars).",
      unknown_function: "Function is not recognised.",
      invalid_value: f ? `Invalid value for ${f}.` : "Invalid value.",
      lcd_requires_gpio: "LCD Display must be mapped to GPIO pins.",
      invalid_i2c_address: "I2C address must be between 0x03 and 0x77.",
      lcd_pair_requires_two_pins: "LCD component must have exactly two pins.",
      lcd_pair_requires_sda_scl: "LCD pair must include one SDA and one SCL.",
      lcd_pair_invalid_pins: "LCD pair pins are invalid or duplicated.",
      lcd_pair_mismatch: "LCD pair values must match on both pins.",
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
    const header = `<div class="fw-semibold">Validation failed (${list.length} issues)</div>`;
    setErrorHtml(`${header}${lines.join("")}${more}`);
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
    if (!mapping[uid]) mapping[uid] = { friendly: "", function: "", safety: "" };
    return mapping[uid];
  }

  function normalizeFunction(fn) {
    const v = String(fn || "").trim();
    if (!v) return "";
    if (v === "LCD1602") return LCD_FUNCTION;
    return v;
  }

  function isLcdFunction(fn) {
    return normalizeFunction(fn) === LCD_FUNCTION;
  }

  function sanitizeLcdAddress(raw) {
    const s = String(raw || "").trim() || "0x27";
    const n = Number.parseInt(s, 0);
    if (!Number.isFinite(n) || n < 0x03 || n > 0x77) return "0x27";
    return `0x${n.toString(16).padStart(2, "0")}`;
  }

  function oppositeRole(role) {
    const r = String(role || "").trim().toUpperCase();
    return r === "SCL" ? "SDA" : "SCL";
  }

  function sanitizeComponentId(raw) {
    const s = String(raw || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
    return s || "lcd-1";
  }

  function deriveLcdComponentId(primaryUid, secondaryUid = "") {
    const a = sanitizeComponentId(primaryUid);
    const b = sanitizeComponentId(secondaryUid);
    if (b) {
      const pair = [a, b].sort();
      return `lcd-${pair[0]}-${pair[1]}`;
    }
    return `lcd-${a}`;
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

  function releaseLcdSecondaryIfBound(primaryUid) {
    const primary = row(primaryUid);
    const oldSecondaryUid = String(primary.secondaryPinUid || "").trim();
    if (!oldSecondaryUid) return;
    const secondary = row(oldSecondaryUid);
    if (String(secondary.linkedPrimaryUid || "").trim() === String(primaryUid)) {
      delete secondary.linkedPrimaryUid;
      delete secondary.componentId;
      delete secondary.componentRole;
      delete secondary.i2cAddress;
      delete secondary.lcdCols;
      delete secondary.lcdRows;
      if (isLcdFunction(secondary.function)) secondary.function = "";
    }
    delete primary.secondaryPinUid;
  }

  function syncLcdPair(primaryUid, secondaryUid) {
    const primary = row(primaryUid);
    const normalizedPrimaryFn = normalizeFunction(primary.function);
    primary.function = normalizedPrimaryFn;
    if (!isLcdFunction(normalizedPrimaryFn)) return;
    const role = String(primary.componentRole || "SDA").trim().toUpperCase() === "SCL" ? "SCL" : "SDA";
    primary.componentRole = role;
    primary.componentId = deriveLcdComponentId(primaryUid, secondaryUid);
    primary.i2cAddress = sanitizeLcdAddress(primary.i2cAddress);
    primary.lcdCols = Number.parseInt(primary.lcdCols ?? "16", 10) || 16;
    primary.lcdRows = Number.parseInt(primary.lcdRows ?? "2", 10) || 2;
    releaseLcdSecondaryIfBound(primaryUid);
    const secUid = String(secondaryUid || "").trim();
    if (!secUid || secUid === primaryUid) return;
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (uid === primaryUid || !cfg || typeof cfg !== "object") return;
      if (String(cfg.secondaryPinUid || "").trim() !== secUid) return;
      delete cfg.secondaryPinUid;
      if (String(row(secUid).linkedPrimaryUid || "").trim() === String(uid)) {
        delete row(secUid).linkedPrimaryUid;
      }
    });
    const secondary = row(secUid);
    const secondaryRole = oppositeRole(primary.componentRole);
    secondary.function = LCD_FUNCTION;
    secondary.componentId = primary.componentId;
    secondary.componentRole = secondaryRole;
    secondary.linkedPrimaryUid = primaryUid;
    secondary.i2cAddress = primary.i2cAddress;
    secondary.lcdCols = primary.lcdCols;
    secondary.lcdRows = primary.lcdRows;
    secondary.friendly = String(primary.friendly || "").trim();
    primary.secondaryPinUid = secUid;
  }

  function primaryForSecondary(uid) {
    const targetUid = String(uid || "").trim();
    if (!targetUid) return "";
    for (const [candidateUid, cfg] of Object.entries(mapping || {})) {
      if (!cfg || typeof cfg !== "object") continue;
      if (!isLcdFunction(cfg.function)) continue;
      if (String(cfg.linkedPrimaryUid || "").trim()) continue;
      if (String(cfg.secondaryPinUid || "").trim() !== targetUid) continue;
      return String(candidateUid);
    }
    return "";
  }

  function normalizeLcdBindings() {
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      cfg.function = normalizeFunction(cfg.function);
      const sec = String(cfg.secondaryPinUid || "").trim();
      const linked = String(cfg.linkedPrimaryUid || "").trim();
      if (sec && linked) {
        // A row cannot be both primary and secondary at once.
        delete cfg.linkedPrimaryUid;
      }
      if (sec && sec === uid) {
        delete cfg.secondaryPinUid;
      }
    });

    // Break stale mutual-primary cycles deterministically (keep lexicographically smaller uid as primary).
    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      const sec = String(cfg.secondaryPinUid || "").trim();
      if (!sec || sec === uid) return;
      const other = mapping[sec];
      if (!other || typeof other !== "object") return;
      const back = String(other.secondaryPinUid || "").trim();
      if (back !== uid) return;
      if (uid < sec) {
        delete other.secondaryPinUid;
      } else {
        delete cfg.secondaryPinUid;
      }
    });

    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      if (!isLcdFunction(cfg.function)) {
        delete cfg.secondaryPinUid;
        delete cfg.linkedPrimaryUid;
        return;
      }
      const secUid = String(cfg.secondaryPinUid || "").trim();
      if (!secUid || secUid === uid) {
        delete cfg.secondaryPinUid;
        return;
      }
      if (!mapping[secUid]) mapping[secUid] = { friendly: "", function: "", safety: "" };
      const primary = row(uid);
      const secondary = row(secUid);
      primary.function = LCD_FUNCTION;
      primary.componentRole = String(primary.componentRole || "SDA").trim().toUpperCase() === "SCL" ? "SCL" : "SDA";
      primary.componentId = deriveLcdComponentId(uid, secUid);
      primary.i2cAddress = sanitizeLcdAddress(primary.i2cAddress);
      primary.lcdCols = Number.parseInt(primary.lcdCols ?? "16", 10) || 16;
      primary.lcdRows = Number.parseInt(primary.lcdRows ?? "2", 10) || 2;

      secondary.function = LCD_FUNCTION;
      secondary.linkedPrimaryUid = uid;
      delete secondary.secondaryPinUid;
      secondary.componentRole = oppositeRole(primary.componentRole);
      secondary.componentId = primary.componentId;
      secondary.i2cAddress = primary.i2cAddress;
      secondary.lcdCols = primary.lcdCols;
      secondary.lcdRows = primary.lcdRows;
      secondary.friendly = String(primary.friendly || "").trim();
    });

    Object.entries(mapping || {}).forEach(([uid, cfg]) => {
      if (!cfg || typeof cfg !== "object") return;
      const linked = String(cfg.linkedPrimaryUid || "").trim();
      if (!linked) return;
      if (primaryForSecondary(uid) !== linked) {
        delete cfg.linkedPrimaryUid;
      }
    });
  }

  function lcdCandidates(primaryUid) {
    return pins
      .filter((pin) => String(pin.type || "").toUpperCase() === "GPIO" && String(pin.uid || "") !== String(primaryUid || ""))
      .map((pin) => {
        const chan = String(pin.chan || "").trim();
        const label = `${pin.uid}${chan ? ` (GPIO ${chan})` : ""}`;
        return { value: String(pin.uid || ""), label };
      });
  }

  function renderLcdConfigModal(uid) {
    const key = String(uid || "").trim();
    if (!key) return;
    const pin = (pins || []).find((p) => String(p.uid || "") === key);
    const cfg = row(key);
    const role = String(cfg.componentRole || "SDA").trim().toUpperCase() === "SCL" ? "SCL" : "SDA";
    const secondaryRole = oppositeRole(role);
    const secUid = String(cfg.secondaryPinUid || "").trim();
    const options = lcdCandidates(key);

    if (lcdConfigContextEl) {
      const friendly = String(cfg.friendly || "").trim();
      const chan = String(pin?.chan || "").trim();
      const suffix = chan ? `GPIO ${chan}` : key;
      lcdConfigContextEl.textContent = `${friendly || key} (${suffix})`;
    }
    if (lcdSecondaryLabel) lcdSecondaryLabel.textContent = `Secondary Pin (${secondaryRole})`;
    if (lcdRoleInput) lcdRoleInput.value = role;
    if (lcdSecondaryInput) {
      lcdSecondaryInput.innerHTML = `<option value="">Select secondary pin…</option>${options.map((opt) => `<option value="${opt.value}">${opt.label}</option>`).join("")}`;
      lcdSecondaryInput.value = secUid;
    }
    if (lcdAddrInput) lcdAddrInput.value = sanitizeLcdAddress(cfg.i2cAddress || "0x27");
    if (lcdColsInput) lcdColsInput.value = cfg.lcdCols ?? 16;
    if (lcdRowsInput) lcdRowsInput.value = cfg.lcdRows ?? 2;
  }

  function openLcdConfigModal(uid) {
    activeLcdUid = String(uid || "").trim();
    if (!activeLcdUid || !isLcdFunction(row(activeLcdUid).function)) return;
    if (!lcdConfigModal && lcdConfigModalEl && window.bootstrap?.Modal) {
      lcdConfigModal = bootstrap.Modal.getOrCreateInstance(lcdConfigModalEl);
    }
    renderLcdConfigModal(activeLcdUid);
    lcdConfigModal?.show();
  }

  function render() {
    normalizeLcdBindings();
    tbody.innerHTML = "";
    if (!pins.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center text-secondary py-3">No pins loaded. Click Reload Pins to fetch from ESP.</td></tr>';
      return;
    }

    const visiblePins = showAllPins ? pins : pins.filter((p) => p.safe !== false);
    if (!visiblePins.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center text-secondary py-3">No mappable pins. Enable “Show all Pins” to view reserved pins.</td></tr>';
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
        <td class="text-center"></td>
      `;

      const r = row(p.uid);
      r.function = normalizeFunction(r.function);
      const boundPrimaryUid = String(primaryForSecondary(p.uid) || r.linkedPrimaryUid || "").trim();
      const isLcdBoundReadonly = !!boundPrimaryUid && boundPrimaryUid !== p.uid;

      const friendlyInput = document.createElement("input");
      friendlyInput.className = "form-control form-control-sm";
      friendlyInput.value = r.friendly || "";
      const isLocked = !canMap;
      if (!isLocked && !isLcdBoundReadonly) {
        friendlyInput.addEventListener("input", (e) => {
          row(p.uid).friendly = e.target.value;
          if (isLcdFunction(row(p.uid).function)) {
            const secUid = String(row(p.uid).secondaryPinUid || "").trim();
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
        if (isLcdBoundReadonly) {
          friendlyInput.readOnly = true;
          friendlyInput.classList.add("bg-body-tertiary");
        }
        friendlyWrap.appendChild(friendlyInput);
        if (isLcdBoundReadonly) {
          const lock = document.createElement("span");
          lock.className = "hardware-friendly-lock";
          lock.title = `Inherited from ${boundPrimaryUid}`;
          lock.innerHTML = '<i class="fa fa-lock" aria-hidden="true"></i>';
          tr.children[9].appendChild(lock);
        }
        tr.children[7].appendChild(friendlyWrap);
      }

      const fnSelect = document.createElement("select");
      fnSelect.className = "form-select form-select-sm";
      fnSelect.innerHTML = `<option value="">(None)</option>${functions.map(fn => `<option value="${fn}">${fn}</option>`).join("")}`;
      fnSelect.value = r.function || "";
      fnSelect.disabled = isLcdBoundReadonly;
      const fnCell = tr.children[8];
      const actionCell = tr.children[9];
      const fnWrap = document.createElement("div");
      fnWrap.className = "d-flex align-items-center gap-2";
      fnWrap.appendChild(fnSelect);
      if (!isLocked) {
        fnSelect.addEventListener("change", (e) => {
          const val = e.target.value || "";
          const r = row(p.uid);
          r.function = val;
          if (isLcdFunction(val)) {
            if (!r.componentId) r.componentId = deriveLcdComponentId(p.uid, String(r.secondaryPinUid || "").trim());
            if (!r.componentRole) r.componentRole = "SDA";
            if (!r.i2cAddress) r.i2cAddress = "0x27";
            if (!r.lcdCols) r.lcdCols = 16;
            if (!r.lcdRows) r.lcdRows = 2;
            r.function = LCD_FUNCTION;
          } else {
            releaseLcdSecondaryIfBound(p.uid);
            delete r.componentId;
            delete r.componentRole;
            delete r.i2cAddress;
            delete r.lcdCols;
            delete r.lcdRows;
            delete r.linkedPrimaryUid;
            delete r.secondaryPinUid;
            if (activeLcdUid === String(p.uid || "")) {
              activeLcdUid = "";
              lcdConfigModal?.hide();
            }
          }
          setDirty(true);
          render();
        });
        fnCell.appendChild(fnWrap);
      }

      if (!isLocked && isLcdFunction(r.function) && !isLcdBoundReadonly) {
        const cfgBtn = document.createElement("button");
        cfgBtn.type = "button";
        cfgBtn.className = "btn btn-outline-secondary btn-sm hardware-lcd-config-btn";
        cfgBtn.title = "Configure LCD Display";
        cfgBtn.setAttribute("aria-label", "Configure LCD Display");
        cfgBtn.innerHTML = '<i class="fa fa-sliders" aria-hidden="true"></i>';
        cfgBtn.addEventListener("click", () => openLcdConfigModal(p.uid));
        actionCell.appendChild(cfgBtn);
      }

      if (isLcdBoundReadonly) {
        const linked = row(boundPrimaryUid);
        const inherited = String(linked.friendly || "").trim();
        if (inherited && r.friendly !== inherited) {
          r.friendly = inherited;
          friendlyInput.value = inherited;
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
    normalizeLcdBindings();
    setDirty(false);
  }

  async function save() {
    setError("");
    setToast("");
    saveBtn.disabled = true;
    try {
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

    if (lcdConfigModalEl && window.bootstrap?.Modal) {
      lcdConfigModal = bootstrap.Modal.getOrCreateInstance(lcdConfigModalEl);
      lcdConfigModalEl.addEventListener("hidden.bs.modal", () => {
        activeLcdUid = "";
      });
    }
    lcdRoleInput?.addEventListener("change", (e) => {
      const uid = activeLcdUid;
      if (!uid) return;
      row(uid).componentRole = String(e.target.value || "").trim().toUpperCase();
      const secUid = String(row(uid).secondaryPinUid || "").trim();
      if (secUid) syncLcdPair(uid, secUid);
      setDirty(true);
      renderLcdConfigModal(uid);
      render();
    });
    lcdSecondaryInput?.addEventListener("change", (e) => {
      const uid = activeLcdUid;
      if (!uid) return;
      const secUid = String(e.target.value || "").trim();
      syncLcdPair(uid, secUid);
      setDirty(true);
      renderLcdConfigModal(uid);
      render();
    });
    lcdAddrInput?.addEventListener("input", (e) => {
      const uid = activeLcdUid;
      if (!uid) return;
      row(uid).i2cAddress = sanitizeLcdAddress(String(e.target.value || "").trim());
      const secUid = String(row(uid).secondaryPinUid || "").trim();
      if (secUid) syncLcdPair(uid, secUid);
      setDirty(true);
    });
    lcdColsInput?.addEventListener("input", (e) => {
      const uid = activeLcdUid;
      if (!uid) return;
      row(uid).lcdCols = String(e.target.value || "").trim();
      const secUid = String(row(uid).secondaryPinUid || "").trim();
      if (secUid) syncLcdPair(uid, secUid);
      setDirty(true);
    });
    lcdRowsInput?.addEventListener("input", (e) => {
      const uid = activeLcdUid;
      if (!uid) return;
      row(uid).lcdRows = String(e.target.value || "").trim();
      const secUid = String(row(uid).secondaryPinUid || "").trim();
      if (secUid) syncLcdPair(uid, secUid);
      setDirty(true);
    });

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
