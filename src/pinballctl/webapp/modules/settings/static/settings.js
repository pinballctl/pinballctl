// Installation settings. Backup / Restore has its own module.
(function () {
  const root = document.getElementById("settings-root");
  if (!root) return;
  const SETTINGS_TAB_KEY = "pinballctl.settings.lastTab.v1";

  const nameInput = root.querySelector('[data-field="name"]');
  const btnSave = root.querySelector('[data-action="save"]');
  const adminUserInput = root.querySelector('[data-field="admin-user"]');
  const adminPassInput = root.querySelector('[data-field="admin-pass"]');
  const remoteUrlInput = root.querySelector('[data-field="remote-url"]');
  const logLevelSelect = root.querySelector('[data-field="log-level"]');
  const currencySelect = root.querySelector('[data-field="currency"]');
  let baseline = null;
  let saving = false;

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

  function currentState() {
    return {
      name: nameInput?.value || "",
      AUTH_USER: adminUserInput?.value || "",
      REMOTE_FIRMWARE_URL: remoteUrlInput?.value || "",
      LOG_LEVEL: logLevelSelect?.value || "INFO",
      CURRENCY: currencySelect?.value || "GBP",
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
    const payload = {
      name,
      AUTH_USER: adminUser,
      REMOTE_FIRMWARE_URL: remoteUrl,
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

  btnSave?.addEventListener("click", saveSettings);
  root.addEventListener("input", updateSaveState);
  root.addEventListener("change", updateSaveState);

  wireTabPersistence();
  loadSettings();
})();
