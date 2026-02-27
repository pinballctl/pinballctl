// Vanilla ESPLink controller.
(function () {
  const root = document.getElementById("esplink-root");
  if (!root) return;

  const selDevice = document.getElementById("esp-device");
  const dot = document.getElementById("esp-dot");
  const statusText = document.getElementById("esp-status-text");
  const firmwareEl = document.getElementById("esp-firmware");
  const refreshBtn = document.getElementById("esp-refresh");
  const rebootBtn = document.getElementById("esp-reboot");
  const syncBtn = document.getElementById("esp-sync");
  const noDevicesCard = document.getElementById("esp-no-devices");
  const grid = document.getElementById("esp-grid");

  const portEl = document.getElementById("esp-port");
  const chipEl = document.getElementById("esp-chip");
  const ipEl = document.getElementById("esp-ip");
  const rssiEl = document.getElementById("esp-rssi");

  const localList = document.getElementById("esp-local-list");
  const localWrap = document.getElementById("esp-local-wrap");
  const fwCount = document.getElementById("esp-fw-count");

  const uploadWrap = document.getElementById("esp-upload");
  const uploadLog = document.getElementById("esp-upload-log");
  const uploadClose = document.getElementById("esp-upload-close");

  const state = {
    devices: [],
    currentId: "",
    status: {},
    localManifest: { latest: null, versions: [] },
    bridge: {},
    uploadVisible: false,
    uploading: false,
    lastAppliedVersion: "",
    statusRequestId: 0,
    autoBridgeAttemptAt: 0,
    suppressAutoBridgeUntil: 0,
    refreshTimer: null,
    refreshInFlight: false,
  };

  function encId() {
    return encodeURIComponent((state.currentId || "").replace(/^\/+/, ""));
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

  function normalizeVersion(value) {
    if (!value) return "";
    const m = /v?(\d+\.\d+\.\d+)/.exec(String(value));
    return m ? m[1] : String(value).trim();
  }

  function setConnected(ok) {
    dot.classList.toggle("green", !!ok);
    statusText.textContent = ok ? "Connected" : "Not connected";
  }

  function cleanValue(v) {
    if (v === null || v === undefined) return "";
    const s = String(v).trim();
    if (!s || s === "-" || s.toLowerCase() === "n/a") return "";
    return s;
  }

  function renderStatus() {
    const st = state.status || {};
    setConnected(!!st.connected);
    firmwareEl.textContent = st.firmware || "N/A";
    if (portEl) portEl.textContent = state.currentId || "-";
    const chipText = cleanValue(st.chip) || cleanValue(state.bridge?.chip) || cleanValue(state.bridge?.chip_model);
    if (chipEl) chipEl.textContent = chipText || "-";
    if (ipEl) ipEl.textContent = st.ip || "-";
    if (rssiEl) rssiEl.textContent = (st.rssi || st.rssi === 0) ? st.rssi : "-";
    rebootBtn.disabled = !state.currentId;
    syncBtn.disabled = !state.currentId;
    if (fsStatusBtn) fsStatusBtn.disabled = !state.currentId;
    if (fsListBtn) fsListBtn.disabled = !state.currentId;
    if (rebootActionBtn) rebootActionBtn.disabled = !state.currentId;
    if (echoTestBtn) echoTestBtn.disabled = !state.currentId;
  }

  function renderDevices() {
    selDevice.innerHTML = `<option value="" disabled ${state.currentId ? "" : "selected"}>Select device…</option>`;
    (state.devices || []).forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.port ? `${d.port} — ${d.description || "ESP"}` : d.id;
      if (d.id === state.currentId) opt.selected = true;
      selDevice.appendChild(opt);
    });
    const has = state.devices && state.devices.length;
    noDevicesCard.classList.toggle("d-none", !!has);
    grid.classList.toggle("d-none", !has);
  }

  function syncCurrentDevice() {
    const ids = new Set((state.devices || []).map((d) => d.id));
    if (state.currentId && ids.has(state.currentId)) return;
    const bridgePort = state.bridge?.port;
    if (bridgePort && ids.has(bridgePort)) {
      state.currentId = bridgePort;
      return;
    }
    state.currentId = state.devices?.[0]?.id || "";
  }

  function renderManifestList() {
    localList.classList.remove("d-none");
    const mergedRaw = state.localManifest?.versions || [];
    const merged = [...mergedRaw].sort((a, b) => {
      const parse = (v) => {
        const m = /^v?(\d+)\.(\d+)\.(\d+)/.exec(v || "");
        return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : [0, 0, 0];
      };
      const [a1, a2, a3] = parse(a?.version);
      const [b1, b2, b3] = parse(b?.version);
      if (a1 !== b1) return b1 - a1;
      if (a2 !== b2) return b2 - a2;
      return b3 - a3;
    });
    const showOnlyApplied = (state.uploadVisible || state.uploading) && state.lastAppliedVersion;
    const appliedVersion = normalizeVersion(state.lastAppliedVersion);
    const filtered = showOnlyApplied
      ? merged.filter((v) => normalizeVersion(v?.version) === appliedVersion)
      : merged;
    localList.innerHTML = "";
    if (!filtered.length) {
      const div = document.createElement("div");
      div.className = "muted";
      div.textContent = showOnlyApplied ? "Applying firmware…" : "No firmware versions found.";
      localList.appendChild(div);
      if (fwCount) fwCount.textContent = "0 versions";
      return;
    }
    const latest = merged[0]?.version || state.localManifest?.latest || null;
    filtered.forEach((v) => {
      const item = document.createElement("div");
      item.className = "fw-item";
      const meta = document.createElement("div");
      meta.className = "fw-meta";
      const dateTxt = formatDate(v.date);
      const noteTxt = v.notes ? String(v.notes) : "";
      const subtitle = dateTxt && noteTxt ? `${dateTxt} — ${noteTxt}` : (dateTxt || noteTxt || "");
      const isLatest = latest && v.version === latest;
      const currentVersion = normalizeVersion(state.status?.firmware);
      const listedVersion = normalizeVersion(v.version);
      const isCurrent = currentVersion && listedVersion && currentVersion === listedVersion;
      let badges = "";
      if (isLatest) {
        badges += '<span class="badge rounded-pill" style="background-color: rgb(68, 114, 196); cursor: pointer;">Latest</span>';
      }
      if (isCurrent) {
        badges += '<span class="badge rounded-pill" style="background-color: rgb(46, 125, 50); cursor: pointer;">Current</span>';
      }
      meta.innerHTML = `<div class="fw-title d-flex align-items-center gap-2"><span>${v.version || "-"}</span>${badges}</div><div class="fw-notes">${subtitle}</div>`;
      const actions = document.createElement("div");
      actions.className = "fw-actions";
      const pill = document.createElement("span");
      pill.className = "badge bg-success-subtle text-success-emphasis";
      pill.textContent = "Downloaded";
      actions.appendChild(pill);
      const btn = document.createElement("button");
      btn.className = "btn btn-primary btn-sm";
      btn.textContent = "Apply";
      btn.disabled = !state.currentId || state.uploading;
      btn.addEventListener("click", () => applyLocal(v.version));
      actions.appendChild(btn);
      item.appendChild(meta);
      item.appendChild(actions);
      localList.appendChild(item);
    });
    if (fwCount) {
      const shownCount = filtered.length;
      const totalCount = merged.length;
      if (showOnlyApplied) {
        fwCount.textContent = `${shownCount} of ${totalCount} versions`;
      } else {
        fwCount.textContent = `${totalCount} version${totalCount === 1 ? "" : "s"}`;
      }
    }
  }

  // Bridge card
  const bridgeRunningEl = document.getElementById("bridge-running");
  const bridgePortEl = document.getElementById("bridge-port");
  const bridgeFwEl = document.getElementById("bridge-fw");
  const bridgeChipEl = document.getElementById("bridge-chip");
  const bridgeChipModelEl = document.getElementById("bridge-chip-model");
  const bridgeChipRevEl = document.getElementById("bridge-chip-rev");
  const bridgeChipCoresEl = document.getElementById("bridge-chip-cores");
  const bridgeProfileEl = document.getElementById("bridge-profile");
  const bridgeControllerEl = document.getElementById("bridge-controller");
  const bridgeStartBtn = document.getElementById("bridge-start");
  const bridgeStopBtn = document.getElementById("bridge-stop");
  const bridgeRestartBtn = document.getElementById("bridge-restart");
  const fsStatusBtn = document.getElementById("esp-fs-status");
  const fsListBtn = document.getElementById("esp-fs-list");
  const rebootActionBtn = document.getElementById("esp-reboot-action");
  const echoTestBtn = document.getElementById("esp-echo-test");
  const fsModalEl = document.getElementById("esp-fs-modal");
  const fsModalBody = document.getElementById("esp-fs-modal-body");
  const fsModal = fsModalEl ? new bootstrap.Modal(fsModalEl) : null;
  const fsListModalEl = document.getElementById("esp-fs-list-modal");
  const fsListModalBody = document.getElementById("esp-fs-list-modal-body");
  const fsListModal = fsListModalEl ? new bootstrap.Modal(fsListModalEl) : null;
  const echoModalEl = document.getElementById("esp-echo-modal");
  const echoModalBody = document.getElementById("esp-echo-modal-body");
  const echoModal = echoModalEl ? new bootstrap.Modal(echoModalEl) : null;
  const rebootModalEl = document.getElementById("esp-reboot-modal");
  const rebootModalBody = document.getElementById("esp-reboot-modal-body");
  const rebootModal = rebootModalEl ? new bootstrap.Modal(rebootModalEl) : null;

  function renderBridge() {
    const b = state.bridge || {};
    if (bridgeRunningEl) bridgeRunningEl.textContent = b.running ? "Running" : "Stopped";
    if (bridgePortEl) bridgePortEl.textContent = b.port || "-";
    if (bridgeFwEl) bridgeFwEl.textContent = b.firmware || "-";
    if (bridgeChipEl) bridgeChipEl.textContent = b.chip || "-";
    if (bridgeChipModelEl) bridgeChipModelEl.textContent = b.chip_model || "-";
    if (bridgeChipRevEl) bridgeChipRevEl.textContent = (b.chip_revision || b.chip_revision === 0) ? String(b.chip_revision) : "-";
    if (bridgeChipCoresEl) bridgeChipCoresEl.textContent = (b.chip_cores || b.chip_cores === 0) ? String(b.chip_cores) : "-";
    if (bridgeProfileEl) bridgeProfileEl.textContent = b.profile || "-";
    if (bridgeControllerEl) bridgeControllerEl.textContent = b.controller || "-";
    if (bridgeStartBtn) bridgeStartBtn.disabled = !!b.running;
    if (bridgeStopBtn) bridgeStopBtn.disabled = !b.running;
    if (bridgeRestartBtn) bridgeRestartBtn.disabled = false;
  }

  async function loadBridge() {
    try {
      const res = await fetch("/esplink/api/bridge/status", { cache: "no-store" });
      state.bridge = await res.json();
      syncCurrentDevice();
      renderBridge();
      renderStatus();
    } catch (e) {
      state.bridge = {};
      syncCurrentDevice();
      renderBridge();
      renderStatus();
    }
  }

  async function startBridge() {
    await fetch("/esplink/api/bridge/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ port: state.currentId || "auto" }) }).catch(() => {});
    await refreshBridgeAndStatus();
  }
  async function stopBridge() {
    state.suppressAutoBridgeUntil = Date.now() + 5 * 60 * 1000;
    await fetch("/esplink/api/bridge/stop", { method: "POST" }).catch(() => {});
    await loadBridge();
  }
  async function restartBridge() {
    await fetch("/esplink/api/bridge/restart", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ port: state.currentId || "auto" }) }).catch(() => {});
    await refreshBridgeAndStatus();
  }

  async function refreshBridgeAndStatus() {
    for (let i = 0; i < 8; i++) {
      await loadBridge();
      await loadStatus();
      const fw = state.status?.firmware || state.bridge?.firmware;
      const live = !!state.status?.connected || !!state.bridge?.running;
      if (fw && live) return;
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }


  function showFsModal(payload) {
    if (!fsModalBody) return;
    fsModalBody.innerHTML = payload ? renderKeyValueTable(payload) : "<div>No data</div>";
    fsModal?.show();
  }

  function showFsListModal(payload) {
    if (!fsListModalBody) return;
    fsListModalBody.innerHTML = payload || "<div>No data</div>";
    fsListModal?.show();
  }

  function showEchoModal(payload) {
    if (!echoModalBody) return;
    echoModalBody.innerHTML = payload ? renderKeyValueTable(payload) : "<div>No data</div>";
    echoModal?.show();
  }

  function showRebootModal(payload) {
    if (!rebootModalBody) return;
    rebootModalBody.innerHTML = payload ? renderKeyValueTable(payload) : "<div>No data</div>";
    rebootModal?.show();
  }

  function renderKeyValueTable(payload) {
    if (!payload || typeof payload !== "object") {
      return `<div>${String(payload || "")}</div>`;
    }
    const rows = Object.entries(payload).map(([key, value]) => {
      let display = "";
      if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        display = String(value);
      } else {
        display = JSON.stringify(value);
      }
      return `<tr><td class="text-body">${escapeHtml(key)}</td><td class="text-success">${escapeHtml(display)}</td></tr>`;
    }).join("");
    return `<table class="table table-sm table-striped mb-0"><tbody>${rows}</tbody></table>`;
  }

  function renderFsListTable(payload) {
    const files = payload?.files || [];
    if (!files.length) {
      return "<div class=\"text-secondary\">No files found.</div>";
    }
    const formatMtime = (value) => {
      const raw = Number(value);
      if (!raw || !Number.isFinite(raw)) return "-";
      const tsMs = raw > 1e12 ? raw : raw * 1000;
      const d = new Date(tsMs);
      if (Number.isNaN(d.getTime())) return "-";
      return new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(d);
    };
    const rows = files.map((file) => {
      const name = escapeHtml(file.name || "");
      const size = typeof file.size === "number" ? String(file.size) : "-";
      const uploaded = escapeHtml(formatMtime(file.uploadedAt));
      return `<tr><td>${name}</td><td>${size}</td><td>${uploaded}</td></tr>`;
    }).join("");
    return `
      <table class="table table-sm align-middle mb-0">
        <thead>
          <tr>
            <th>Name / Path</th>
            <th style="width: 140px;">Size (bytes)</th>
            <th style="width: 220px;">Uploaded</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function fetchFsStatus() {
    if (!state.currentId) return;
    try {
      const res = await fetch(`/esplink/api/devices/${encId()}/fs-status`, { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        showFsModal({ error: data.error || "Failed to fetch FS status", status: data.status || null });
        return;
      }
      showFsModal(data.status || data);
    } catch (e) {
      showFsModal({ error: "Failed to fetch FS status" });
    }
  }

  async function fetchFsList() {
    if (!state.currentId) return;
    showFsListModal("<div class=\"text-secondary\">Requesting file list…</div>");
    try {
      const res = await fetch("/esplink/api/fs/list", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "/" }),
      });
      const data = await res.json();
      if (!data.success) {
        showFsListModal(renderKeyValueTable({ error: data.error || "Failed to fetch file list" }));
        return;
      }
      showFsListModal(renderFsListTable(data));
    } catch (e) {
      showFsListModal(renderKeyValueTable({ error: "Failed to fetch file list" }));
    }
  }

  async function runEchoTest() {
    if (!state.currentId) return;
    try {
      const res = await fetch(`/esplink/api/devices/${encId()}/echo`, { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        showEchoModal({ error: data.error || "Echo failed", status: data.status || null });
        return;
      }
      showEchoModal(data.status || data);
    } catch (e) {
      showEchoModal({ error: "Echo failed" });
    }
  }

  function appendUpload(line) {
    state.uploadVisible = true;
    uploadWrap.classList.remove("d-none");
    state.uploadLog = (state.uploadLog || "");
    state.uploadLog += (state.uploadLog ? "\n" : "") + line;
    uploadLog.textContent = state.uploadLog;
    uploadLog.scrollTop = uploadLog.scrollHeight;
  }

  async function refresh() {
    try {
      const res = await fetch("/esplink/api/devices");
      state.devices = await res.json();
      syncCurrentDevice();
      renderDevices();
      await loadStatus();
    } catch (e) {
      console.error(e);
    }
  }

  async function loadStatus() {
    if (!state.currentId) {
      state.status = { connected: false };
      renderStatus();
      renderManifests();
      return;
    }
    const requestId = (state.statusRequestId += 1);
    try {
      const res = await fetch(`/esplink/api/devices/${encId()}/status`);
      const payload = await res.json();
      if (requestId !== state.statusRequestId) return;
      state.status = payload;
    } catch (e) {
      if (requestId !== state.statusRequestId) return;
      state.status = { connected: false };
    }
    renderStatus();
    renderManifests();
  }

  async function loadLocalManifest() {
    try {
      const res = await fetch("/api/firmware/versions", { cache: "no-store" });
      const j = await res.json();
      state.localManifest = (j && j.versions) ? j : { latest: null, versions: [] };
    } catch (e) {
      state.localManifest = { latest: null, versions: [] };
    }
    renderManifests();
  }

  function renderManifests() {
    if (localWrap) {
      const compact = state.uploadVisible || state.uploading;
      localWrap.classList.toggle("compact", compact);
      localWrap.classList.toggle("tall", !compact);
    }
    renderManifestList();
  }

  async function applyLocal(ver) {
    if (state.uploading) return;
    state.uploading = true;
    state.lastAppliedVersion = ver;
    renderManifests();
    startUpload({ method: "local", version: ver });
  }

  async function startUpload(payload) {
    if (!state.currentId) return;
    state.uploadLog = "";
    appendUpload("Starting upload…");
    try {
      const resp = await fetch(`/esplink/api/devices/${encId()}/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok || !resp.body) {
        appendUpload("[ERROR] failed to start");
        await loadStatus();
        return;
      }
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n"); buf = parts.pop();
        for (const chunk of parts) {
          let ev = null, data = "";
          for (const ln of chunk.split("\n")) {
            if (ln.startsWith("event:")) ev = ln.slice(6).trim();
            if (ln.startsWith("data:")) data += (data ? "\n" : "") + ln.slice(5).trim();
          }
          if (ev === "STEP") appendUpload(`STEP ${data}`);
          else if (ev === "LOG") appendUpload(data);
          else if (ev === "ERROR") appendUpload(`ERROR ${data}`);
        }
      }
    } catch (e) {
      appendUpload(`[ERROR] stream: ${e}`);
    } finally {
      state.uploading = false;
      renderManifests();
      await refreshStatusAfterUpload(state.lastAppliedVersion);
      await loadLocalManifest();
      state.lastAppliedVersion = "";
    }
  }

  async function refreshStatusAfterUpload(expectedVersion) {
    const target = normalizeVersion(expectedVersion);
    for (let i = 0; i < 12; i++) {
      await loadStatus();
      const current = normalizeVersion(state.status?.firmware);
      if (target && current && current === target) return;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  function clearUpload() {
    state.uploadLog = "";
    uploadLog.textContent = "";
    uploadWrap.classList.add("d-none");
    state.uploadVisible = false;
    renderManifests();
    loadStatus();
  }

  async function reboot() {
    if (!state.currentId) return;
    try {
      const res = await fetch(`/esplink/api/devices/${encId()}/reboot`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        showRebootModal({ error: data.error || "Reboot failed" });
        return;
      }
      showRebootModal(data);
    } catch (e) {
      showRebootModal({ error: "Reboot failed" });
    }
    await loadStatus();
  }

  async function syncTime() {
    if (!state.currentId) return;
    try {
      const r = await fetch(`/esplink/api/devices/${encId()}/sync-time`, { method: "POST" });
      const j = await r.json();
      appendUpload(`[i] time synced ${j.now_iso}`);
    } catch (e) {
      appendUpload("[ERROR] sync failed");
    } finally {
      await loadStatus();
    }
  }

  function wireEvents() {
    selDevice?.addEventListener("change", async (e) => { state.currentId = e.target.value; await loadStatus(); });
    refreshBtn?.addEventListener("click", refresh);
    rebootBtn?.addEventListener("click", reboot);
    syncBtn?.addEventListener("click", syncTime);
    uploadClose?.addEventListener("click", clearUpload);
    bridgeStartBtn?.addEventListener("click", startBridge);
    bridgeStopBtn?.addEventListener("click", stopBridge);
    bridgeRestartBtn?.addEventListener("click", restartBridge);
    fsStatusBtn?.addEventListener("click", fetchFsStatus);
    fsListBtn?.addEventListener("click", fetchFsList);
    rebootActionBtn?.addEventListener("click", reboot);
    echoTestBtn?.addEventListener("click", runEchoTest);
  }

  async function init() {
    wireEvents();
    await refresh();
    await loadLocalManifest();
    renderManifests();
    await loadBridge();
    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.refreshTimer = setInterval(async () => {
      if (state.uploading) return;
      if (state.refreshInFlight) return;
      state.refreshInFlight = true;
      try {
        await refresh();
        await loadBridge();
      } finally {
        state.refreshInFlight = false;
      }
    }, 2000);
  }

  init();
})();
