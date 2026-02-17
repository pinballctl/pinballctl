// Vanilla Wi-Fi status + save form.
(function () {
  const root = document.getElementById("wifi-root");
  if (!root) return;

  const alerts = {
    loading: root.querySelector('[data-state="loading"]'),
    error: root.querySelector('[data-state="error"]'),
  };
  const fields = {
    ssid: root.querySelector('[data-field="ssid"]'),
    ip: root.querySelector('[data-field="ip"]'),
    state: root.querySelector('[data-field="state"]'),
    connected: root.querySelector('[data-field="connected"]'),
  };
  const form = root.querySelector("[data-form]");
  const saveBtn = root.querySelector("[data-save]");
  const savingSpinner = root.querySelector("[data-saving-spinner]");
  const okMsg = root.querySelector("[data-okmsg]");

  let saving = false;
  let baseline = { ssid: "", psk: "" };

  function show(el) { if (el) el.classList.remove("d-none"); }
  function hide(el) { if (el) el.classList.add("d-none"); }

  function setError(msg) {
    if (!alerts.error) return;
    alerts.error.textContent = msg || "";
    if (msg) show(alerts.error); else hide(alerts.error);
  }

  function applyStatus(status) {
    if (fields.ssid) {
      const ssid = status?.ssid;
      fields.ssid.textContent = ssid === "Unsupported" ? "Unknown" : (ssid ?? "—");
    }
    if (fields.ip) fields.ip.textContent = status?.ip ?? "—";
    if (fields.state) fields.state.textContent = status?.state ?? "—";

    const connected = (() => {
      const st = (status?.state || "").toLowerCase();
      if (st === "connected" || st === "wifi_connected") return true;
      return !!status?.ip;
    })();

    if (fields.connected) {
      fields.connected.textContent = connected ? "Yes" : "No";
      fields.connected.classList.remove("bg-success", "bg-danger", "bg-secondary");
      fields.connected.classList.add(connected ? "bg-success" : "bg-danger");
    }
  }

  function formState() {
    if (!form) return { ssid: "", psk: "" };
    const data = new FormData(form);
    return {
      ssid: String(data.get("ssid") || ""),
      psk: String(data.get("psk") || ""),
    };
  }

  function updateSaveState() {
    if (!saveBtn) return;
    const now = formState();
    const dirty = now.ssid !== baseline.ssid || now.psk !== baseline.psk;
    saveBtn.disabled = saving || !dirty;
    saveBtn.setAttribute("aria-disabled", saveBtn.disabled ? "true" : "false");
  }

  async function fetchStatus() {
    hide(okMsg);
    if (alerts.loading) show(alerts.loading);
    try {
      const r = await fetch("/api/wifi/status", { cache: "no-store" });
      const data = await r.json();
      setError("");
      applyStatus(data);
    } catch (e) {
      setError("Failed to load status");
    } finally {
      hide(alerts.loading);
    }
  }

  async function save(ssid, psk) {
    if (saving) return;
    saving = true;
    updateSaveState();
    hide(okMsg);
    setError("");
    show(savingSpinner);
    try {
      const r = await fetch("/api/wifi/save", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ ssid, psk }),
      });
      const j = await r.json();
      if (j.ok) {
        okMsg.textContent = j.message || "Saved";
        show(okMsg);
        const pskInput = form?.querySelector('input[name="psk"]');
        if (pskInput) pskInput.value = "";
        baseline = formState();
        setTimeout(fetchStatus, 600);
      } else {
        setError(j.message || "Save failed");
      }
    } catch (e) {
      setError("Save failed");
    } finally {
      saving = false;
      updateSaveState();
      hide(savingSpinner);
    }
  }

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      save(fd.get("ssid") || "", fd.get("psk") || "");
    });
    form.addEventListener("input", updateSaveState);
    form.addEventListener("change", updateSaveState);
  }

  baseline = formState();
  updateSaveState();
  fetchStatus();
  setInterval(fetchStatus, 5000);
})();
