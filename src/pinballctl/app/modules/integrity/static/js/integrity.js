(function () {
  const runBtn = document.getElementById("integrity-run");
  const cleanupBtn = document.getElementById("integrity-cleanup");
  const body = document.getElementById("integrity-body");
  const changesEl = document.getElementById("integrity-changes");
  const tabsEl = document.getElementById("integrity-tabs");
  const kindFilterEl = document.getElementById("integrity-kind-filter");
  const keywordFilterEl = document.getElementById("integrity-keyword-filter");

  if (!runBtn || !cleanupBtn || !body) return;

  const state = {
    report: null,
    statusFilter: "all",
    kindFilter: "all",
    keyword: "",
    canCleanup: false,
  };
  const LAST_TAB_KEY = "pinballctl.integrity.lastTab.v1";

  const KIND_LABELS = {
    audio_asset: "Audio Asset",
    audio_cue: "Audio Cue",
    hardware_component: "Hardware Component",
    hardware_reference: "Hardware Reference",
    cue_reference: "Cue Reference",
  };

  function statusIcon(status) {
    const s = String(status || "").toLowerCase();
    if (s === "ok") return '<span class="integrity-status ok" title="OK"><i class="fa fa-check fa-fw"></i></span>';
    if (s === "warning") return '<span class="integrity-status warning" title="Warning"><i class="fa fa-triangle-exclamation fa-fw"></i></span>';
    return '<span class="integrity-status error" title="Error"><i class="fa fa-xmark fa-fw"></i></span>';
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setSelectOptions(selectEl, values, current, labelPrefix) {
    if (!selectEl) return;
    const opts = [`<option value="all">${esc(labelPrefix)}</option>`];
    values.forEach((v) => {
      const label = selectEl === kindFilterEl ? friendlyKind(v) : v;
      opts.push(`<option value="${esc(v)}"${v === current ? " selected" : ""}>${esc(label)}</option>`);
    });
    selectEl.innerHTML = opts.join("");
  }

  function camelCaseLabel(value) {
    const chunks = String(value || "").split(/[^a-zA-Z0-9]+/).filter(Boolean);
    return chunks.map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase()).join("");
  }

  function friendlyKind(kind) {
    const token = String(kind || "").trim();
    if (!token) return "";
    if (KIND_LABELS[token]) return KIND_LABELS[token];
    return token
      .split(/[_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function moduleClass(moduleName) {
    const token = String(moduleName || "").trim().toLowerCase();
    if (!token) return "";
    return `integrity-use-module-${token.replace(/[^a-z0-9]+/g, "-")}`;
  }

  function titleCaseToken(value) {
    return String(value || "")
      .split(/[_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function formatChangeRows(change) {
    const rows = [];
    Object.entries(change || {}).forEach(([key, val]) => {
      if (key === "file" || key === "change") return;
      if (typeof val === "number" && val === 0) return;
      if (val === null || val === undefined || val === "") return;
      rows.push(
        `<div><span class="text-secondary">${esc(titleCaseToken(key))}:</span> <strong>${esc(String(val))}</strong></div>`
      );
    });
    return rows.length ? rows.join("") : '<div class="text-secondary">No effective changes.</div>';
  }

  function renderChanges(changes) {
    if (!changesEl) return;
    if (!changes.length) {
      changesEl.textContent = "";
      return;
    }
    changesEl.innerHTML = `<strong>Applied changes</strong>
      <div class="mt-2 d-flex flex-column gap-2">
        ${changes.map((change) => `
          <div class="border rounded p-2">
            <div><span class="text-secondary">Change:</span> <strong>${esc(titleCaseToken(change.change || ""))}</strong></div>
            <div><span class="text-secondary">File:</span> <code>${esc(change.file || "")}</code></div>
            ${formatChangeRows(change)}
          </div>
        `).join("")}
      </div>`;
  }

  function syncFilterOptions(items) {
    const kinds = [...new Set(items.map((x) => String(x.kind || "").trim()).filter(Boolean))].sort();

    if (state.kindFilter !== "all" && !kinds.includes(state.kindFilter)) state.kindFilter = "all";

    setSelectOptions(kindFilterEl, kinds, state.kindFilter, "All kinds");
  }

  function filteredItems(items) {
    const q = state.keyword.toLowerCase();
    return items.filter((row) => {
      const status = String(row.status || "").toLowerCase();
      if (state.statusFilter === "unused") {
        const uses = Array.isArray(row.uses) ? row.uses : [];
        if (uses.length !== 0) return false;
      } else if (state.statusFilter !== "all" && status !== state.statusFilter) {
        return false;
      }
      if (state.kindFilter !== "all" && String(row.kind || "") !== state.kindFilter) return false;
      if (!q) return true;
      const haystack = [
        row.name,
        row.id,
        row.kind,
        row.details,
        ...(Array.isArray(row.tags) ? row.tags : []),
        ...(Array.isArray(row.uses) ? row.uses.map((u) => `${u.module || ""} ${u.detail || ""}`) : []),
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    });
  }

  function renderRows(items) {
    if (!items.length) {
      body.innerHTML = '<tr><td colspan="5" class="text-secondary text-center py-4">No items match current filters.</td></tr>';
      return;
    }

    body.innerHTML = items.map((row) => {
      const uses = Array.isArray(row.uses) ? row.uses : [];
      const usesHtml = uses.length
        ? `<div class="integrity-uses">${
            uses.map((u) =>
              `<div class="integrity-use"><span class="badge integrity-use-module ${moduleClass(u.module)}">${esc(camelCaseLabel(u.module || ""))}</span> ${esc(u.detail || "")}</div>`
            ).join("")
          }</div>`
        : '<div class="text-secondary">No references</div>';
      const tagsHtml = "";
      const canResolve = row.fixable && String(row.status || "").toLowerCase() !== "ok";
      const resolveBtn = canResolve
        ? `<button class="btn btn-sm btn-outline-danger integrity-cleanup-item" type="button" data-issue-key="${esc(row.issueKey || "")}" data-kind="${esc(row.kind || "")}" data-id="${esc(row.id || "")}">Resolve</button>`
        : '<span class="text-secondary small">N/A</span>';

      return `
        <tr>
          <td>${statusIcon(row.status)}</td>
          <td>${esc(friendlyKind(row.kind || ""))}</td>
          <td>${esc(row.name || row.id || "")}</td>
          <td class="integrity-details">
            <div class="integrity-details-main">${esc(row.details || "")}</div>
            ${usesHtml}
            ${tagsHtml}
          </td>
          <td class="integrity-actions">${resolveBtn}</td>
        </tr>
      `;
    }).join("");
  }

  function renderTabsCounts(items) {
    if (!tabsEl) return;
    const counts = { all: items.length, ok: 0, error: 0, unused: 0 };
    items.forEach((row) => {
      const s = String(row.status || "").toLowerCase();
      if (Object.hasOwn(counts, s)) counts[s] += 1;
      const uses = Array.isArray(row.uses) ? row.uses : [];
      if (uses.length === 0) counts.unused += 1;
    });
    tabsEl.querySelectorAll("[data-status]").forEach((btn) => {
      const status = String(btn.dataset.status || "all");
      const count = counts[status] || 0;
      const base = status === "all" ? "All" : (status === "ok" ? "OK" : (status === "unused" ? "Unused" : "Errors"));
      btn.textContent = `${base} (${count})`;
      btn.classList.toggle("active", status === state.statusFilter);
    });
  }

  function loadLastTab() {
    try {
      const saved = String(window.localStorage.getItem(LAST_TAB_KEY) || "").trim().toLowerCase();
      if (saved === "all" || saved === "ok" || saved === "error" || saved === "unused") {
        state.statusFilter = saved;
      }
    } catch (_) {}
  }

  function saveLastTab() {
    try {
      window.localStorage.setItem(LAST_TAB_KEY, String(state.statusFilter || "all"));
    } catch (_) {}
  }

  function render(report) {
    state.report = report || { items: [], stats: {} };
    const items = (report && Array.isArray(report.items)) ? report.items : [];
    state.canCleanup = items.some((row) => row && row.fixable && String(row.status || "").toLowerCase() !== "ok");
    cleanupBtn.disabled = !state.canCleanup;
    syncFilterOptions(items);
    renderTabsCounts(items);
    renderRows(filteredItems(items));

    const changes = (report && Array.isArray(report.changes)) ? report.changes : [];
    renderChanges(changes);
  }

  function setBusy(isBusy) {
    runBtn.disabled = isBusy;
    cleanupBtn.disabled = isBusy || !state.canCleanup;
    body.querySelectorAll(".integrity-cleanup-item").forEach((btn) => {
      btn.disabled = isBusy;
    });
  }

  function setInlineError(message) {
    if (!changesEl) return;
    changesEl.innerHTML = `<span class="text-danger">${esc(message || "Request failed.")}</span>`;
  }

  function confirmAction(title, message, confirmText) {
    const fallback = () => Promise.resolve(window.confirm(String(message || "")));
    if (typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl) return fallback();
    const bodyEl = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!confirmBtn) return fallback();
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });

    return new Promise((resolve) => {
      let accepted = false;
      const onConfirm = () => {
        accepted = true;
        teardown();
        modal.hide();
        resolve(true);
      };
      const onHidden = () => {
        teardown();
        if (!accepted) resolve(false);
      };
      const teardown = () => {
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
        confirmBtn.removeEventListener("click", onConfirm);
      };

      if (titleEl) titleEl.textContent = title || "Confirm";
      if (bodyEl) bodyEl.textContent = message || "";
      confirmBtn.textContent = confirmText || "Confirm";
      confirmBtn.className = "btn btn-danger";
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      confirmBtn.addEventListener("click", onConfirm, { once: true });
      modal.show();
    });
  }

  async function parseApiResponse(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (!response.ok || payload.ok === false) {
      const msg = payload.error || payload.message || `HTTP ${response.status}`;
      throw new Error(msg);
    }
    return payload;
  }

  async function runCheck() {
    setBusy(true);
    try {
      const r = await fetch("/api/integrity/report");
      const j = await parseApiResponse(r);
      render(j);
    } catch (e) {
      setInlineError(`Failed to run integrity check: ${e && e.message ? e.message : e}`);
    } finally { setBusy(false); }
  }

  async function cleanup() {
    const ok = await confirmAction(
      "Confirm Cleanup",
      "Cleanup orphaned references across modules? This will modify config files.",
      "Cleanup"
    );
    if (!ok) return;
    setBusy(true);
    try {
      const r = await fetch("/api/integrity/cleanup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apply: true }),
      });
      const j = await parseApiResponse(r);
      render(j);
    } catch (e) {
      setInlineError(`Cleanup failed: ${e && e.message ? e.message : e}`);
    } finally { setBusy(false); }
  }

  async function cleanupItem(kind, id, issueKey) {
    if (!issueKey && (!kind || !id)) return;
    const label = issueKey || `${kind}:${id}`;
    const ok = await confirmAction("Confirm Resolve", `Resolve this issue only?\n${label}`, "Resolve");
    if (!ok) return;
    setBusy(true);
    try {
      const r = await fetch("/api/integrity/cleanup-item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, id, issueKey }),
      });
      const j = await parseApiResponse(r);
      render(j);
    } catch (e) {
      setInlineError(`Item cleanup failed: ${e && e.message ? e.message : e}`);
    } finally { setBusy(false); }
  }

  if (tabsEl) {
    tabsEl.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-status]");
      if (!btn) return;
      state.statusFilter = String(btn.dataset.status || "all");
      saveLastTab();
      render(state.report || { items: [], stats: {} });
    });
  }

  if (kindFilterEl) {
    kindFilterEl.addEventListener("change", () => {
      state.kindFilter = kindFilterEl.value || "all";
      render(state.report || { items: [], stats: {} });
    });
  }

  if (keywordFilterEl) {
    keywordFilterEl.addEventListener("input", () => {
      state.keyword = keywordFilterEl.value || "";
      render(state.report || { items: [], stats: {} });
    });
  }

  body.addEventListener("click", (event) => {
    const btn = event.target.closest(".integrity-cleanup-item");
    if (!btn) return;
    cleanupItem(btn.dataset.kind || "", btn.dataset.id || "", btn.dataset.issueKey || "");
  });

  runBtn.addEventListener("click", runCheck);
  cleanupBtn.addEventListener("click", cleanup);
  loadLastTab();
  runCheck();
})();
