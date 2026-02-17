// Firmware versions viewer (vanilla JS)
(function () {
  const root = document.getElementById("firmware-root");
  if (!root) return;

  const rowsEl = root.querySelector('[data-field="rows"]');
  const latestEl = root.querySelector('[data-field="latest"]');
  const countEl = root.querySelector('[data-field="count"]');
  const sourceEl = root.querySelector('[data-field="source"]');
  const sourceSelect = root.querySelector('[data-field="source-select"]');
  const remoteRow = root.querySelector('[data-field="remote-row"]');
  const remoteUrlInput = root.querySelector('[data-field="remote-url"]');
  const remoteLoadBtn = root.querySelector('[data-action="remote-load"]');
  const deleteAllBtn = root.querySelector('[data-action="delete-all"]');

  const remoteDefaultUrl = root.dataset.remoteDefault || "";
  const state = {
    local: null,
    remoteDefault: null,
    remoteCustom: null,
    source: "default",
  };

  function versionsSet(list) {
    const set = new Set();
    (list || []).forEach((v) => { if (v.version) set.add(String(v.version)); });
    return set;
  }

  function formatSize(bytes) {
    if (!bytes && bytes !== 0) return "—";
    const num = Number(bytes);
    if (Number.isNaN(num)) return "—";
    if (num < 1024) return `${num} B`;
    if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`;
    return `${(num / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return "—";
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
    if (!(day && month && year && hour && minute)) return "—";
    return `${day} ${month} ${year} ${hour}:${minute}`;
  }

  function mergedVersions() {
    const localList = state.local?.versions || [];
    const remoteList = state.remoteDefault?.versions || [];
    const customList = state.remoteCustom?.versions || [];
    let chosenRemote = remoteList;
    if (state.source === "custom") chosenRemote = customList;

    const map = new Map();
    chosenRemote.forEach((v) => {
      const key = String(v.version || v.filename || "");
      if (!key) return;
      map.set(key, { ...v, _source: "remote" });
    });
    localList.forEach((v) => {
      const key = String(v.version || v.filename || "");
      if (!key) return;
      map.set(key, { ...v, _source: "local" });
    });
    return Array.from(map.values());
  }

  function latestByDate(list) {
    if (!list || !list.length) return null;
    let latest = null;
    let latestTs = -Infinity;
    list.forEach((v) => {
      const ts = Date.parse(v.date || "") || -Infinity;
      if (ts > latestTs) {
        latestTs = ts;
        latest = v.version || v.filename || null;
      }
    });
    if (latest) return latest;
    return list[0]?.version || list[0]?.filename || null;
  }

  function sortVersions(list) {
    return [...list].sort((a, b) => {
      const ta = Date.parse(a.date || "") || 0;
      const tb = Date.parse(b.date || "") || 0;
      if (ta !== tb) return tb - ta; // newest first
      const va = String(a.version || a.filename || "");
      const vb = String(b.version || b.filename || "");
      return vb.localeCompare(va, undefined, { numeric: true, sensitivity: "base" });
    });
  }

  function render() {
    const showCustom = state.source === "custom";
    const hasCustom = !!(state.remoteCustom && (state.remoteCustom.versions || []).length);
    const versions = (showCustom && !hasCustom) ? [] : sortVersions(mergedVersions());
    const localSet = versionsSet(state.local?.versions || []);
    const hasLocal = (state.local?.versions || []).length > 0;

    rowsEl.innerHTML = "";
    if (!versions.length) {
      rowsEl.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">No firmware versions found.</td></tr>';
    } else {
      versions.forEach((v) => {
        const isLocal = localSet.has(String(v.version || ""));
        const tr = document.createElement("tr");

        const tdVer = document.createElement("td");
        tdVer.className = "fw-semibold";
        tdVer.textContent = v.version || "—";
        const tdDate = document.createElement("td"); tdDate.textContent = formatDate(v.date);
        const tdNotes = document.createElement("td"); tdNotes.textContent = v.notes || "";
        const tdSize = document.createElement("td"); tdSize.textContent = formatSize(v.size);
        const tdStatus = document.createElement("td");
        tdStatus.innerHTML = isLocal
          ? '<span class="badge bg-success-subtle text-success-emphasis">Downloaded</span>'
          : '<span class="badge bg-secondary-subtle text-secondary-emphasis">Remote</span>';
        const tdAction = document.createElement("td"); tdAction.className = "text-end";
        if (isLocal) {
          const btn = document.createElement("button");
          btn.className = "btn btn-sm btn-outline-danger d-inline-flex align-items-center gap-1";
          btn.setAttribute("data-confirm", "Remove this version?");
          btn.innerHTML = '<i class="fa fa-trash"></i><span>Remove</span>';
          btn.addEventListener("click", () => deleteVersion(v));
          tdAction.appendChild(btn);
        } else {
          const btn = document.createElement("button");
          btn.className = "btn btn-sm btn-outline-primary";
          btn.textContent = "Download";
          btn.addEventListener("click", () => downloadVersion(v));
          tdAction.appendChild(btn);
        }

        tr.appendChild(tdVer); tr.appendChild(tdDate); tr.appendChild(tdNotes);
        tr.appendChild(tdSize); tr.appendChild(tdStatus); tr.appendChild(tdAction);
        rowsEl.appendChild(tr);
      });
    }
    const active = state.source === "custom" ? state.remoteCustom : state.remoteDefault;
    const latest = latestByDate(versions);
    if (latestEl) latestEl.textContent = `Latest: ${latest || "—"}`;
    if (countEl) countEl.textContent = versions.length ? `${versions.length} version${versions.length === 1 ? "" : "s"}` : "";
    if (sourceEl) {
      if (state.source === "custom") sourceEl.textContent = active?.source || "Custom";
      else sourceEl.textContent = "Default";
    }
    if (deleteAllBtn) deleteAllBtn.disabled = !hasLocal;
  }

  function dlHref(entry) {
    if (!entry) return "";
    if (entry.download_url) return entry.download_url;
    const filename = entry.filename || "";
    if (!filename) return "";
    if (/^https?:\/\//i.test(filename)) return filename;
    return `/api/firmware/download/${encodeURIComponent(filename)}`;
  }

  async function loadLocal() {
    try {
      const res = await fetch("/api/firmware/versions", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      state.local = await res.json();
      state.local.source = "Local";
      render();
    } catch (e) {
      state.local = { versions: [] };
      if (rowsEl) rowsEl.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Failed to load local versions</td></tr>`;
      if (latestEl) latestEl.textContent = "Latest: —";
    }
  }

  async function loadRemote(url, kind = "default") {
    const target = (url || "").trim();
    if (!target) return;
    if (countEl) countEl.textContent = "Loading remote…";
    try {
      const apiUrl = target.startsWith("/api/firmware/") ? target : `/esplink/api/versions?source=remote&remote_url=${encodeURIComponent(target)}`;
      const res = await fetch(apiUrl, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (kind === "custom") state.remoteCustom = { ...data, source: target };
      else state.remoteDefault = { ...data, source: target };
      render();
    } catch (e) {
      if (kind === "custom") state.remoteCustom = null;
      else state.remoteDefault = null;
      if (rowsEl) rowsEl.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Failed to load remote manifest</td></tr>`;
    } finally {
      if (countEl) countEl.textContent = "";
    }
  }

  function entryForDownload(entry) {
    if (!entry) return null;
    const payload = { ...entry };
    if (entry.download_url) payload.filename = entry.download_url;
    else if (entry.filename && /^https?:\/\//i.test(entry.filename)) payload.filename = entry.filename;
    return payload;
  }

  async function downloadVersion(entry) {
    const payload = entryForDownload(entry);
    if (!payload || !payload.filename || !payload.version) {
      alert("Invalid entry for download");
      return;
    }
    try {
      const resp = await fetch("/esplink/api/versions/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry: payload }),
      });
      const j = await resp.json();
      if (!j.ok) throw new Error(j.error || "Download failed");
      await loadLocal();
      if (state.source !== "custom" && remoteDefaultUrl) {
        await loadRemote(remoteDefaultUrl, "default");
      }
    } catch (e) {
      alert(e.message || "Download failed");
    }
  }

  async function deleteVersion(entry) {
    if (!entry || !entry.version) return;
    try {
      const resp = await fetch("/api/firmware/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: entry.version }),
      });
      const j = await resp.json();
      if (!j.ok && j.ok !== undefined) throw new Error(j.error || "Delete failed");
      await loadLocal();
      render();
    } catch (e) {
      alert(e.message || "Delete failed");
    }
  }

  function wire() {
    sourceSelect?.addEventListener("change", () => {
      state.source = sourceSelect.value || "default";
      remoteRow?.classList.toggle("d-none", state.source !== "custom");
      if (state.source === "default" && !state.remoteDefault && remoteDefaultUrl) {
        loadRemote(remoteDefaultUrl, "default");
      }
      render();
    });
    remoteLoadBtn?.addEventListener("click", () => {
      const url = remoteUrlInput?.value || "";
      loadRemote(url, "custom");
      state.source = "custom";
      if (sourceSelect) sourceSelect.value = "custom";
      remoteRow?.classList.remove("d-none");
    });
    deleteAllBtn?.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/firmware/delete/all", { method: "POST" });
        const j = await resp.json();
        if (!j.ok && j.ok !== undefined) throw new Error(j.error || "Delete failed");
        await loadLocal();
        render();
      } catch (e) {
        alert(e.message || "Delete failed");
      }
    });
  }

  wire();
  loadLocal();
  if (remoteDefaultUrl) loadRemote(remoteDefaultUrl, "default");
})();
