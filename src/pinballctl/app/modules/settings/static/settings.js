// Settings page logic (project name + import/export)
(function () {
  const root = document.getElementById("settings-root");
  if (!root) return;
  const SETTINGS_TAB_KEY = "pinballctl.settings.lastTab.v1";

  const nameInput = root.querySelector('[data-field="name"]');
  const exportStatus = root.querySelector('[data-field="export-status"]');
  const importStatus = root.querySelector('[data-field="import-status"]');
  const btnSave = root.querySelector('[data-action="save"]');
  const btnExport = root.querySelector('[data-action="export"]');
  const btnImport = root.querySelector('[data-action="import"]');
  const fileInput = root.querySelector('[data-field="import-file"]');
  const adminUserInput = root.querySelector('[data-field="admin-user"]');
  const adminPassInput = root.querySelector('[data-field="admin-pass"]');
  const remoteUrlInput = root.querySelector('[data-field="remote-url"]');
  const logLevelSelect = root.querySelector('[data-field="log-level"]');
  const currencySelect = root.querySelector('[data-field="currency"]');
  const startDisplaysInput = root.querySelector('[data-field="start-displays"]');
  let baseline = null;
  let saving = false;
  let exporting = false;

  function wireTabPersistence() {
    const tabButtons = Array.from(root.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#settings-pane-"]'));
    if (!tabButtons.length) return;

    tabButtons.forEach((btn) => {
      btn.addEventListener("shown.bs.tab", (e) => {
        const target = String(e.target?.getAttribute("data-bs-target") || "").trim();
        if (!target) return;
        try { localStorage.setItem(SETTINGS_TAB_KEY, target); } catch (_) {}
      });
    });

    let last = "";
    try { last = localStorage.getItem(SETTINGS_TAB_KEY) || ""; } catch (_) { last = ""; }
    if (!last) return;
    const btn = root.querySelector(`[data-bs-toggle="tab"][data-bs-target="${last}"]`);
    if (!btn || !window.bootstrap?.Tab) return;
    window.bootstrap.Tab.getOrCreateInstance(btn).show();
  }

  function setExportStatus(kind, message, showSpinner = false) {
    if (!exportStatus) return;
    exportStatus.classList.remove("d-none", "is-working", "is-success", "is-error");
    if (kind === "working") exportStatus.classList.add("is-working");
    if (kind === "success") exportStatus.classList.add("is-success");
    if (kind === "error") exportStatus.classList.add("is-error");
    const spinner = showSpinner
      ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'
      : "";
    exportStatus.innerHTML = `${spinner}<span>${String(message || "")}</span>`;
  }

  function setExportBusy(isBusy) {
    exporting = !!isBusy;
    if (btnExport) {
      btnExport.disabled = exporting;
      btnExport.setAttribute("aria-disabled", exporting ? "true" : "false");
    }
  }

  function currentState() {
    return {
      name: nameInput?.value || "",
      AUTH_USER: adminUserInput?.value || "",
      REMOTE_FIRMWARE_URL: remoteUrlInput?.value || "",
      LOG_LEVEL: logLevelSelect?.value || "INFO",
      CURRENCY: currencySelect?.value || "GBP",
      START_DISPLAYS: !!startDisplaysInput?.checked,
      AUTH_PASSWORD: adminPassInput?.value || "",
    };
  }

  function updateSaveState() {
    if (!btnSave) return;
    const now = currentState();
    const passDirty = (now.AUTH_PASSWORD || "").trim().length > 0;
    const dirty = !baseline
      || now.name !== baseline.name
      || now.AUTH_USER !== baseline.AUTH_USER
      || now.REMOTE_FIRMWARE_URL !== baseline.REMOTE_FIRMWARE_URL
      || now.LOG_LEVEL !== baseline.LOG_LEVEL
      || now.CURRENCY !== baseline.CURRENCY
      || now.START_DISPLAYS !== baseline.START_DISPLAYS
      || passDirty;
    btnSave.disabled = saving || !dirty;
    btnSave.setAttribute("aria-disabled", btnSave.disabled ? "true" : "false");
  }

  async function loadSettings() {
    try {
      const res = await fetch("/api/settings/data", { cache: "no-store" });
      const data = await res.json();
      if (nameInput) nameInput.value = data.name || "";
      if (adminUserInput) adminUserInput.value = data.AUTH_USER || "";
      if (adminPassInput) adminPassInput.value = "";
      if (remoteUrlInput) remoteUrlInput.value = data.REMOTE_FIRMWARE_URL || "";
      if (logLevelSelect) logLevelSelect.value = data.LOG_LEVEL || "INFO";
      if (currencySelect) currencySelect.value = data.CURRENCY || "GBP";
      if (startDisplaysInput) startDisplaysInput.checked = !!data.START_DISPLAYS;
      baseline = currentState();
      baseline.AUTH_PASSWORD = "";
      updateSaveState();
    } catch (e) {
      console.error(e);
    }
  }

  async function saveSettings() {
    if (saving) return;
    const name = nameInput?.value || "";
    const adminUser = adminUserInput?.value || "";
    const adminPass = adminPassInput?.value || "";
    const remoteUrl = remoteUrlInput?.value || "";
    const logLevel = logLevelSelect?.value || "INFO";
    const currency = currencySelect?.value || "GBP";
    const startDisplays = !!startDisplaysInput?.checked;
    const payload = {
      name,
      AUTH_USER: adminUser,
      REMOTE_FIRMWARE_URL: remoteUrl,
      START_DISPLAYS: startDisplays,
    };
    if (logLevel) payload.LOG_LEVEL = logLevel;
    if (currency) payload.CURRENCY = currency;
    if (adminPass && adminPass.trim().length > 0) {
      payload.AUTH_PASSWORD = adminPass;
    }
    saving = true;
    updateSaveState();
    try {
      const res = await fetch("/api/settings/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        alert("Failed to save settings");
        return;
      }
      if (adminPassInput) adminPassInput.value = "";
      baseline = currentState();
      baseline.AUTH_PASSWORD = "";
    } finally {
      saving = false;
      updateSaveState();
    }
  }

  async function exportProject() {
    if (exporting) return;
    setExportBusy(true);
    setExportStatus("working", "Preparing export…", true);
    try {
      const res = await fetch("/api/settings/export");
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename = match ? match[1] : "project.zip";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportStatus("success", "Export ready");
    } catch (e) {
      alert(e.message || "Export failed");
      setExportStatus("error", "Export failed");
    } finally {
      setExportBusy(false);
    }
  }

  async function importProject() {
    const file = fileInput?.files?.[0];
    if (!file) {
      alert("Choose a zip file to import");
      return;
    }
    if (importStatus) importStatus.textContent = "Uploading…";
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const res = await fetch("/api/settings/import", {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || "Import failed");
      if (importStatus) importStatus.textContent = "Import complete";
    } catch (e) {
      alert(e.message || "Import failed");
      if (importStatus) importStatus.textContent = "Import failed";
    }
  }

  btnSave?.addEventListener("click", saveSettings);
  btnExport?.addEventListener("click", exportProject);
  btnImport?.addEventListener("click", importProject);
  root.addEventListener("input", updateSaveState);
  root.addEventListener("change", updateSaveState);

  wireTabPersistence();
  loadSettings();
})();
