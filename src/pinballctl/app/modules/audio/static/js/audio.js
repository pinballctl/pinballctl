(() => {
  const root = document.getElementById("audio-page");
  if (!root) return;

  const state = {
    config: null,
    devices: [],
    runtime: null,
    outputEnv: null,
    rulesUsageMaps: [],
    assetSort: { key: "name", dir: "asc" },
  };

  const $ = (sel) => root.querySelector(sel);
  const elAssets = $("#audio-assets-table");
  const elCues = $("#audio-cues-table");
  const elMaps = $("#audio-maps-table");
  const elDevices = $("#audio-devices");
  const elRuntime = $("#audio-runtime");
  const elOutputEnv = $("#audio-output-env");
  const elAssetCountPill = $("#audio-asset-count-pill");
  const saveButtons = Array.from(root.querySelectorAll("[data-audio-save]"));
  const elUploadDropzone = $("#audio-upload-dropzone");
  const elUploadBrowse = $("#audio-upload-browse");
  const elUploadFile = $("#audio-upload-file");
  const elUploadProgressWrap = $("#audio-upload-progress-wrap");
  const elUploadProgress = $("#audio-upload-progress");
  const elUploadProgressText = $("#audio-upload-progress-text");
  let runtimePollTimer = null;
  let cueUiTimer = null;
  let uploadInProgress = false;
  const AUDIO_TAB_KEY = "pinballctl.audio.lastTab.v1";
  let dirty = false;
  const cuePausedMs = new Map();
  const cueScrubDragging = new Set();
  const cueActionBusy = new Set();
  const cuePendingSeekUnits = new Map();

  async function api(path, opts) {
    const res = await fetch(`/api/audio${path}`, opts || {});
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  }

  function uid(prefix) {
    return `${prefix}_${Math.random().toString(16).slice(2, 10)}`;
  }

  function escHtml(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;");
  }

  function wireTabPersistence() {
    const tabButtons = Array.from(root.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#audio-pane-"]'));
    if (!tabButtons.length) return;

    tabButtons.forEach((btn) => {
      btn.addEventListener("show.bs.tab", (e) => {
        const target = e.target?.getAttribute("data-bs-target") || "";
        const current = e.relatedTarget?.getAttribute("data-bs-target") || "";
        if (!dirty || !target || target === current) return;
        if (btn.getAttribute("data-audio-unsaved-ok") === "1") return;
        e.preventDefault();
        askConfirm("You have unsaved changes. Leave this tab without saving?", {
          title: "Unsaved Changes",
          label: "Leave Tab",
          confirmClass: "btn-warning",
        }).then((ok) => {
          if (!ok) return;
          btn.setAttribute("data-audio-unsaved-ok", "1");
          if (window.bootstrap?.Tab) {
            window.bootstrap.Tab.getOrCreateInstance(btn).show();
          } else {
            btn.click();
          }
        });
      });
      btn.addEventListener("shown.bs.tab", (e) => {
        e.target?.removeAttribute?.("data-audio-unsaved-ok");
        const target = e.target?.getAttribute("data-bs-target") || "";
        if (!target) return;
        try { localStorage.setItem(AUDIO_TAB_KEY, target); } catch (_) {}
      });
    });

    let last = "";
    try { last = localStorage.getItem(AUDIO_TAB_KEY) || ""; } catch (_) { last = ""; }
    if (!last) return;
    const btn = root.querySelector(`[data-bs-toggle="tab"][data-bs-target="${last}"]`);
    if (!btn) return;
    if (window.bootstrap && window.bootstrap.Tab) {
      window.bootstrap.Tab.getOrCreateInstance(btn).show();
    }
  }

  function setDirty(flag) {
    dirty = !!flag;
    saveButtons.forEach((btn) => {
      btn.disabled = !dirty;
      btn.setAttribute("aria-disabled", dirty ? "false" : "true");
    });
  }

  function askConfirm(message, opts = {}) {
    const fallback = () => Promise.resolve(window.confirm(message));
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) return fallback();

    const body = modalEl.querySelector(".modal-body");
    const titleEl = modalEl.querySelector(".modal-title");
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!confirmBtn) return fallback();

    const title = opts.title || "Confirm";
    const label = opts.label || "Delete";
    const btnClass = opts.confirmClass || "btn-danger";
    if (body) body.textContent = message;
    if (titleEl) titleEl.textContent = title;
    confirmBtn.textContent = label;
    confirmBtn.className = `btn ${btnClass}`;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" });
    return new Promise((resolve) => {
      const cleanup = () => {
        confirmBtn.removeEventListener("click", onConfirm);
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
      };
      const onConfirm = () => {
        cleanup();
        resolve(true);
        modal.hide();
      };
      const onHidden = () => {
        cleanup();
        resolve(false);
      };
      confirmBtn.addEventListener("click", onConfirm, { once: true });
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      modal.show();
    });
  }

  function setUploadProgress(percent, text) {
    const p = Math.max(0, Math.min(100, Math.floor(percent || 0)));
    if (elUploadProgressWrap) {
      elUploadProgressWrap.classList.remove("d-none");
      elUploadProgressWrap.setAttribute("aria-valuenow", String(p));
    }
    if (elUploadProgress) {
      elUploadProgress.style.width = `${p}%`;
      elUploadProgress.textContent = `${p}%`;
    }
    if (elUploadProgressText) {
      elUploadProgressText.classList.remove("d-none");
      elUploadProgressText.textContent = text || "";
    }
  }

  function resetUploadProgress() {
    if (elUploadProgressWrap) {
      elUploadProgressWrap.classList.add("d-none");
      elUploadProgressWrap.setAttribute("aria-valuenow", "0");
    }
    if (elUploadProgress) {
      elUploadProgress.style.width = "0%";
      elUploadProgress.textContent = "0%";
    }
    if (elUploadProgressText) {
      elUploadProgressText.classList.add("d-none");
      elUploadProgressText.textContent = "";
    }
  }

  function uploadFileWithProgress(file, progressCb) {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/audio/assets/upload", true);
      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        progressCb(evt.loaded, evt.total);
      };
      xhr.onload = () => {
        let data = {};
        try {
          data = JSON.parse(xhr.responseText || "{}");
        } catch (_) {
          data = {};
        }
        if (xhr.status >= 200 && xhr.status < 300 && data.ok !== false) {
          resolve(data);
          return;
        }
        reject(new Error(data.error || `HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error("network_error"));
      xhr.send(form);
    });
  }

  async function uploadFiles(files) {
    const list = Array.from(files || []);
    if (!list.length || uploadInProgress) return;
    uploadInProgress = true;
    const totalBytes = list.reduce((sum, f) => sum + (Number(f.size) || 0), 0) || 1;
    let doneBytes = 0;
    let okCount = 0;
    const failures = [];
    setUploadProgress(0, `Uploading 0/${list.length} files`);
    try {
      for (let i = 0; i < list.length; i += 1) {
        const file = list[i];
        try {
          await uploadFileWithProgress(file, (loaded, total) => {
            const overall = ((doneBytes + loaded) / totalBytes) * 100;
            setUploadProgress(overall, `Uploading ${i + 1}/${list.length}: ${file.name}`);
          });
          doneBytes += Number(file.size) || 0;
          okCount += 1;
          const pct = (doneBytes / totalBytes) * 100;
          setUploadProgress(pct, `Uploaded ${okCount}/${list.length}: ${file.name}`);
        } catch (err) {
          doneBytes += Number(file.size) || 0;
          failures.push(`${file.name}: ${err.message}`);
          const pct = (doneBytes / totalBytes) * 100;
          setUploadProgress(pct, `Failed ${i + 1}/${list.length}: ${file.name}`);
        }
      }
      if (elUploadFile) elUploadFile.value = "";
      await loadAll(false);
      if (failures.length) {
        alert(`Uploaded ${okCount}/${list.length} files.\n\nFailures:\n${failures.join("\n")}`);
      }
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      uploadInProgress = false;
      resetUploadProgress();
      if (elUploadDropzone) elUploadDropzone.classList.remove("is-uploading");
    }
  }

  function fmtMs(ms) {
    const rawMs = Math.max(0, Number(ms) || 0);
    if (rawMs > 0 && rawMs < 1000) {
      return `${(rawMs / 1000).toFixed(2)}s`;
    }
    const total = Math.floor(rawMs / 1000);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function fmtUploaded(ts) {
    const raw = String(ts || "").trim();
    if (!raw) return "-";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return "-";
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  }

  function busLabel(value) {
    const v = String(value || "").trim().toLowerCase();
    if (v === "music") return "Music";
    if (v === "sfx") return "SFX";
    if (v === "voice") return "Voice";
    if (v === "ambient") return "Ambient";
    if (v === "orphan") return "Orphan";
    return v || "n/a";
  }

  function getDefaultAssetSortDir(key) {
    if (key === "name") return "asc";
    if (key === "createdAt") return "desc";
    if (key === "durationMs") return "desc";
    return "asc";
  }

  function assetSortValue(asset, key) {
    if (key === "name") return String(asset.displayName || "").trim().toLowerCase();
    if (key === "durationMs") return Number(asset.durationMs || 0);
    if (key === "createdAt") {
      const t = new Date(String(asset.createdAt || "")).getTime();
      return Number.isNaN(t) ? 0 : t;
    }
    return "";
  }

  function sortedAssets() {
    const assets = Array.isArray(state.config?.assets) ? [...state.config.assets] : [];
    const { key, dir } = state.assetSort || { key: "createdAt", dir: "desc" };
    assets.sort((a, b) => {
      const av = assetSortValue(a, key);
      const bv = assetSortValue(b, key);
      let cmp = 0;
      if (typeof av === "string" && typeof bv === "string") cmp = av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" });
      else cmp = Number(av) - Number(bv);
      if (cmp === 0) {
        const an = String(a.displayName || "").trim().toLowerCase();
        const bn = String(b.displayName || "").trim().toLowerCase();
        cmp = an.localeCompare(bn, undefined, { numeric: true, sensitivity: "base" });
      }
      return dir === "desc" ? -cmp : cmp;
    });
    return assets;
  }

  function updateAssetSortButtons() {
    root.querySelectorAll(".audio-sort-btn").forEach((btn) => {
      const key = btn.getAttribute("data-audio-sort-key") || "";
      const label = btn.getAttribute("data-audio-sort-label") || btn.textContent.trim();
      if (!btn.getAttribute("data-audio-sort-label")) btn.setAttribute("data-audio-sort-label", label);
      if (key !== state.assetSort.key) {
        btn.innerHTML = label;
        btn.classList.remove("fw-semibold");
        return;
      }
      const arrow = state.assetSort.dir === "asc" ? "↑" : "↓";
      btn.innerHTML = `${label} <span class="text-secondary">${arrow}</span>`;
      btn.classList.add("fw-semibold");
    });
  }

  function cueOptions(value) {
    const cues = (state.config?.cues || []).map((c) => `<option value="${c.id}" ${c.id === value ? "selected" : ""}>${c.name}</option>`).join("");
    return `<option value="">(none)</option>${cues}`;
  }

  function assetOptions(value) {
    const assets = (state.config?.assets || []).map((a) => `<option value="${a.id}" ${a.id === value ? "selected" : ""}>${a.displayName}</option>`).join("");
    return `<option value="">(none)</option>${assets}`;
  }

  function deviceOptions(value) {
    const selected = String(value || "default");
    const seen = new Set(["default"]);
    const isDefaultLike = (d) => {
      const id = String(d?.id || "").trim().toLowerCase();
      const name = String(d?.name || "").trim().toLowerCase();
      return id === "default" || name === "default" || name === "default output";
    };
    const devices = (state.devices || [])
      .filter((d) => {
        const id = String(d?.id || "").trim();
        if (!id || seen.has(id)) return false;
        if (isDefaultLike(d)) return false;
        seen.add(id);
        return true;
      })
      .map((d) => `<option value="${d.id}" ${String(d.id) === selected ? "selected" : ""}>${d.name}</option>`)
      .join("");
    return `<option value="default" ${selected === "default" ? "selected" : ""}>Default</option>${devices}`;
  }

  function cuePreviewPayloadFromRow(row) {
    const cueId = String(row?.dataset?.cueId || "").trim();
    return {
      id: cueId || uid("cue"),
      name: String(row?.querySelector('[data-k="name"]')?.value || "").trim() || "Cue",
      enabled: true,
      assetId: String(row?.querySelector('[data-k="assetId"]')?.value || "").trim(),
      bus: String(row?.querySelector('[data-k="bus"]')?.value || "sfx").trim() || "sfx",
      volume: Number(row?.querySelector('[data-k="volume"]')?.value || 1),
      loop: !!row?.querySelector('[data-k="loop"]')?.checked,
      repeatCount: Number(row?.querySelector('[data-k="repeatCount"]')?.value || 1),
      maxConcurrent: Number(row?.querySelector('[data-k="maxConcurrent"]')?.value || 3),
      cooldownMs: Number(row?.querySelector('[data-k="cooldownMs"]')?.value || 0),
      restartPolicy: "restart",
      targetOutput: String(row?.querySelector('[data-k="targetOutput"]')?.value || "default").trim() || "default",
      notes: "temporary cue preview",
    };
  }

  function activeCueHandleById() {
    const out = new Map();
    const rows = Array.isArray(state.runtime?.engine?.active) ? state.runtime.engine.active : [];
    rows.forEach((r) => {
      if (!r || String(r?.cueId || "").startsWith("preview_asset_")) return;
      const cueId = String(r.cueId || "").trim();
      if (!cueId) return;
      const at = Number(r.startedAtMs || 0);
      const prev = out.get(cueId);
      if (!prev || at >= Number(prev.startedAtMs || 0)) out.set(cueId, r);
    });
    return out;
  }

  function formatTimeSeconds(totalSec) {
    const secs = Math.max(0, Number(totalSec) || 0);
    if (secs > 0 && secs < 1) {
      return `${secs.toFixed(2)}s`;
    }
    const s = Math.floor(secs);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${String(rem).padStart(2, "0")}`;
  }

  function setCueBarToScrubPosition(scrub, bar, units) {
    if (!scrub || !bar) return;
    const u = Math.max(0, Math.min(1000, Number(units || 0)));
    const ratio = u / 1000;
    const scrubRect = scrub.getBoundingClientRect();
    const progressRect = (bar.parentElement || bar).getBoundingClientRect();
    const trackW = Math.max(0, Number(scrubRect.width || 0));
    const laneW = Math.max(0, Number(progressRect.width || 0));
    const rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize || "16") || 16;
    // Keep in sync with CSS thumb width: 0.72rem.
    const thumbW = 0.72 * rootPx;
    if (trackW <= 0 || laneW <= 0) {
      bar.style.width = `${u / 10}%`;
      return;
    }
    const centerXAbs = trackW > thumbW
      ? scrubRect.left + (ratio * (trackW - thumbW)) + (thumbW / 2)
      : scrubRect.left + (ratio * trackW);
    const widthPx = Math.max(0, Math.min(laneW, centerXAbs - progressRect.left));
    bar.style.width = `${widthPx}px`;
  }

  function renderSharedPlayer({ kind, id, audioSrc = "", totalMs = 0, stateText = "Stopped", cycleText = "" }) {
    const k = String(kind || "asset").trim().toLowerCase() === "cue" ? "cue" : "asset";
    const safeId = escHtml(id || "");
    const safeSrc = escHtml(audioSrc || "");
    const safeState = escHtml(stateText || "Stopped");
    const safeCycle = escHtml(cycleText || "");
    const total = Math.max(0, Number(totalMs || 0));
    const totalText = total > 0 ? formatTimeSeconds(total / 1000) : "--:--";
    return `<div class="audio-cue-controls audio-simple-player" data-audio-player data-audio-player-kind="${k}" data-audio-player-id="${safeId}">
      <button type="button" class="btn btn-outline-success btn-sm audio-icon-btn" data-audio-player-toggle data-audio-${k}-toggle aria-label="Play preview" title="Play preview">
        <i class="fa fa-play audio-play-icon" data-audio-player-toggle-icon data-audio-${k}-toggle-icon aria-hidden="true"></i>
      </button>
      <div class="audio-cue-meter">
        <div class="audio-cue-meter-header">
          <span class="audio-cue-state" data-audio-player-state data-audio-${k}-state>${safeState}</span>
          <span class="audio-cue-cycle" data-audio-player-cycle data-audio-${k}-cycle>${safeCycle}</span>
        </div>
        <div class="audio-cue-scrub-wrap">
          <div class="audio-cue-track">
            <div class="progress audio-cue-progress">
              <div class="progress-bar audio-cue-progressbar" data-audio-player-progressbar data-audio-${k}-progressbar role="progressbar" style="width:0%"></div>
            </div>
            <input type="range" min="0" max="1000" step="1" value="0" class="form-range audio-cue-scrub" data-audio-player-scrub data-audio-${k}-scrub aria-label="Scrub position">
          </div>
          <div class="audio-cue-time">
            <span data-audio-player-elapsed data-audio-${k}-elapsed>0:00</span>
            <span>/</span>
            <span data-audio-player-total data-audio-${k}-total>${totalText}</span>
          </div>
        </div>
      </div>
      ${safeSrc ? `<audio class="d-none" data-audio-asset-audio preload="metadata" src="${safeSrc}"></audio>` : ""}
    </div>`;
  }

  function setSharedPlayerUi(playerEl, { units = 0, elapsedMs = 0, totalMs = 0, isPlaying = false, stateText = "", cycleText = "" }) {
    if (!playerEl) return;
    const scrub = playerEl.querySelector("[data-audio-player-scrub]");
    const bar = playerEl.querySelector("[data-audio-player-progressbar]");
    const elapsedEl = playerEl.querySelector("[data-audio-player-elapsed]");
    const totalEl = playerEl.querySelector("[data-audio-player-total]");
    const stateEl = playerEl.querySelector("[data-audio-player-state]");
    const cycleEl = playerEl.querySelector("[data-audio-player-cycle]");
    const toggleBtn = playerEl.querySelector("[data-audio-player-toggle]");
    const toggleIcon = playerEl.querySelector("[data-audio-player-toggle-icon]");
    const u = Math.max(0, Math.min(1000, Number(units || 0)));

    if (scrub) scrub.value = String(u);
    if (bar && scrub) {
      setCueBarToScrubPosition(scrub, bar, u);
      bar.classList.toggle("audio-cue-progressbar-active", !!isPlaying || Number(elapsedMs || 0) > 0);
    }
    if (elapsedEl) elapsedEl.textContent = formatTimeSeconds(Math.max(0, Number(elapsedMs || 0)) / 1000);
    if (totalEl) totalEl.textContent = Number(totalMs || 0) > 0 ? formatTimeSeconds(Number(totalMs || 0) / 1000) : "--:--";
    if (stateEl && stateText) stateEl.textContent = stateText;
    if (cycleEl) cycleEl.textContent = String(cycleText || "");
    if (toggleBtn) {
      toggleBtn.classList.toggle("btn-outline-success", !isPlaying);
      toggleBtn.classList.toggle("btn-outline-warning", isPlaying);
      toggleBtn.setAttribute("title", isPlaying ? "Pause preview" : "Play preview");
      toggleBtn.setAttribute("aria-label", isPlaying ? "Pause preview" : "Play preview");
    }
    if (toggleIcon) {
      toggleIcon.classList.toggle("fa-play", !isPlaying);
      toggleIcon.classList.toggle("fa-pause", isPlaying);
      toggleIcon.classList.toggle("audio-play-icon", !isPlaying);
      toggleIcon.classList.toggle("audio-pause-icon", isPlaying);
    }
  }

  function cueRowTiming(row) {
    const assetId = String(row?.querySelector('[data-k="assetId"]')?.value || "").trim();
    const loop = !!row?.querySelector('[data-k="loop"]')?.checked;
    const repeatCount = Math.max(1, Number(row?.querySelector('[data-k="repeatCount"]')?.value || 1));
    const asset = (state.config?.assets || []).find((a) => String(a?.id || "") === assetId);
    const assetDurationMs = Math.max(0, Number(asset?.durationMs || 0));
    const totalMs = assetDurationMs;
    return { loop, repeatCount, assetDurationMs, totalMs };
  }

  function cueProgressAtMs(row, handle, nowMs) {
    const timing = cueRowTiming(row);
    const startedMs = Number(handle?.startedAtMs || nowMs);
    const elapsedMs = Math.max(0, nowMs - startedMs);
    let shownElapsedMs = elapsedMs;
    let shownTotalMs = timing.totalMs;
    let progress = 0;
    let cycleText = "";
    let stateText = "Playing";

    if (timing.loop) {
      stateText = "Playing (Loop)";
      if (timing.assetDurationMs > 0) {
        shownElapsedMs = elapsedMs % timing.assetDurationMs;
        shownTotalMs = timing.assetDurationMs;
        progress = shownElapsedMs / timing.assetDurationMs;
        cycleText = `Loop ${Math.floor(elapsedMs / timing.assetDurationMs) + 1}`;
      } else {
        shownTotalMs = null;
      }
    } else if (timing.assetDurationMs > 0) {
      const passIdx = Math.min(timing.repeatCount - 1, Math.floor(elapsedMs / timing.assetDurationMs));
      const totalForAllPasses = timing.repeatCount * timing.assetDurationMs;
      shownElapsedMs = elapsedMs >= totalForAllPasses ? timing.assetDurationMs : (elapsedMs % timing.assetDurationMs);
      shownTotalMs = timing.assetDurationMs;
      progress = Math.max(0, Math.min(1, shownElapsedMs / timing.assetDurationMs));
      cycleText = `Pass ${Math.min(timing.repeatCount, passIdx + 1)}/${timing.repeatCount}`;
    }

    return { timing, shownElapsedMs, shownTotalMs, progress, cycleText, stateText };
  }

  function backendSupportsSeek() {
    return String(state.runtime?.engine?.backend || "").trim().toLowerCase() === "ffplay";
  }

  function updateCueProgressFromRuntime() {
    const nowMs = Date.now();
    const handlesByCue = activeCueHandleById();
    elCues.querySelectorAll("tr[data-cue-id]").forEach((row) => {
      const cueId = String(row.dataset.cueId || "");
      const bar = row.querySelector("[data-audio-cue-progressbar]");
      const scrub = row.querySelector("[data-audio-cue-scrub]");
      const elapsedEl = row.querySelector("[data-audio-cue-elapsed]");
      const totalEl = row.querySelector("[data-audio-cue-total]");
      const stateEl = row.querySelector("[data-audio-cue-state]");
      const cycleEl = row.querySelector("[data-audio-cue-cycle]");
      if (!bar || !scrub || !elapsedEl || !totalEl || !stateEl || !cycleEl) return;

      const timing = cueRowTiming(row);
      const handle = handlesByCue.get(cueId);
      const pendingUnits = cuePendingSeekUnits.has(cueId)
        ? Math.max(0, Math.min(1000, Number(cuePendingSeekUnits.get(cueId) || 0)))
        : null;
      if (pendingUnits !== null) {
        const totalMs = timing.totalMs && timing.totalMs > 0 ? timing.totalMs : timing.assetDurationMs;
        const pendingMs = totalMs > 0 ? Math.floor((pendingUnits / 1000) * totalMs) : 0;
        setCueBarToScrubPosition(scrub, bar, pendingUnits);
        scrub.value = String(pendingUnits);
        elapsedEl.textContent = formatTimeSeconds(pendingMs / 1000);
        if (timing.totalMs && timing.totalMs > 0) totalEl.textContent = formatTimeSeconds(timing.totalMs / 1000);
        else if (timing.assetDurationMs > 0) totalEl.textContent = formatTimeSeconds(timing.assetDurationMs / 1000);
        else totalEl.textContent = "--:--";
        stateEl.textContent = handle ? "Seeking..." : "Paused";
        bar.classList.add("audio-cue-progressbar-active");
        cycleEl.textContent = "";
        return;
      }
      if (!handle) {
        const pausedMs = Math.max(0, Number(cuePausedMs.get(cueId) || 0));
        const pausedTotalMs = timing.totalMs && timing.totalMs > 0 ? timing.totalMs : timing.assetDurationMs;
        const pausedProgress = pausedTotalMs > 0 ? Math.max(0, Math.min(1, pausedMs / pausedTotalMs)) : 0;
        const pausedUnits = Math.max(0, Math.min(1000, Math.floor(pausedProgress * 1000)));
        setCueBarToScrubPosition(scrub, bar, pausedUnits);
        bar.classList.toggle("audio-cue-progressbar-active", pausedMs > 0);
        elapsedEl.textContent = formatTimeSeconds(pausedMs / 1000);
        if (timing.totalMs && timing.totalMs > 0) totalEl.textContent = formatTimeSeconds(timing.totalMs / 1000);
        else if (timing.assetDurationMs > 0) totalEl.textContent = formatTimeSeconds(timing.assetDurationMs / 1000);
        else totalEl.textContent = "--:--";
        stateEl.textContent = pausedMs > 0 ? "Paused" : "Stopped";
        if (!cueScrubDragging.has(cueId)) scrub.value = String(pausedUnits);
        cycleEl.textContent = "";
        return;
      }

      const calc = cueProgressAtMs(row, handle, nowMs);
      const { shownElapsedMs, shownTotalMs, progress, cycleText, stateText } = calc;
      elapsedEl.textContent = formatTimeSeconds(shownElapsedMs / 1000);
      totalEl.textContent = shownTotalMs && shownTotalMs > 0 ? formatTimeSeconds(shownTotalMs / 1000) : "--:--";
      stateEl.textContent = stateText;
      const dragging = cueScrubDragging.has(cueId);
      const units = dragging
        ? Math.max(0, Math.min(1000, Number(scrub.value || 0)))
        : Math.max(0, Math.min(1000, Math.floor(Math.max(0, Math.min(1, progress)) * 1000)));
      bar.classList.add("audio-cue-progressbar-active");
      if (!dragging) scrub.value = String(units);
      const uiUnits = Math.max(0, Math.min(1000, Number(scrub.value || units)));
      setCueBarToScrubPosition(scrub, bar, uiUnits);
      cycleEl.textContent = cycleText;
    });
  }

  function applyCuePlaybackState() {
    const activeCueIds = new Set(activeCueHandleById().keys());
    elCues.querySelectorAll("tr[data-cue-id]").forEach((row) => {
      const cueId = String(row.dataset.cueId || "");
      const toggleBtn = row.querySelector("[data-audio-cue-toggle]");
      const toggleIcon = row.querySelector("[data-audio-cue-toggle-icon]");
      const scrub = row.querySelector("[data-audio-cue-scrub]");
      const hasAsset = !!String(row.querySelector('[data-k="assetId"]')?.value || "").trim();
      const isActive = activeCueIds.has(cueId);
      if (toggleBtn) {
        toggleBtn.disabled = !hasAsset;
        toggleBtn.classList.toggle("btn-outline-success", !isActive);
        toggleBtn.classList.toggle("btn-outline-warning", isActive);
        toggleBtn.setAttribute("title", isActive ? "Pause cue preview" : "Play cue preview");
        toggleBtn.setAttribute("aria-label", isActive ? "Pause cue preview" : "Play cue preview");
      }
      if (toggleIcon) {
        toggleIcon.classList.toggle("fa-play", !isActive);
        toggleIcon.classList.toggle("fa-pause", isActive);
        toggleIcon.classList.toggle("audio-play-icon", !isActive);
        toggleIcon.classList.toggle("audio-pause-icon", isActive);
      }
      if (scrub) scrub.disabled = !hasAsset || !backendSupportsSeek();
      row.classList.toggle("audio-cue-playing", isActive);
    });
    updateCueProgressFromRuntime();
  }

  function renderDevices() {
    const devices = state.devices || [];
    elDevices.innerHTML = devices.length
      ? devices
      .map((d) => `<div class="d-flex align-items-center justify-content-between py-1 border-bottom border-opacity-25"><span>${d.name}</span><span class="badge text-bg-secondary">${d.backend || "n/a"}</span></div>`)
      .join("")
      : `<div class="text-secondary small">No outputs detected.</div>`;
  }

  function renderOutputEnvironment() {
    if (!elOutputEnv) return;
    const env = state.outputEnv || {};
    const tooling = env.tooling || {};
    const tools = Array.isArray(tooling.tools) ? tooling.tools : [];
    const missingRequired = Array.isArray(tooling.missingRequired) ? tooling.missingRequired : [];
    const notes = Array.isArray(tooling.notes) ? tooling.notes : [];

    const statusClass = missingRequired.length ? "alert-warning" : "alert-success";
    const statusText = missingRequired.length
      ? `Targeted speaker routing not ready. Missing: ${missingRequired.join(", ")}`
      : "Targeted speaker routing ready on this host.";
    const toolsHtml = tools.length
      ? `<div class="table-responsive mt-2">
          <table class="table table-sm mb-0 align-middle">
            <thead>
              <tr>
                <th>Tool</th>
                <th>Status</th>
                <th>Purpose</th>
                <th>Install Hint</th>
              </tr>
            </thead>
            <tbody>
              ${tools
                .map(
                  (t) => `<tr>
                    <td><code>${t.name}</code></td>
                    <td>${t.installed ? '<span class="badge text-bg-success">Installed</span>' : '<span class="badge text-bg-warning">Missing</span>'}${t.required ? ' <span class="badge text-bg-secondary">Required</span>' : ""}</td>
                    <td class="text-wrap">${t.purpose || ""}</td>
                    <td class="text-wrap"><code>${t.installCommand || ""}</code></td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>`
      : "";
    const notesHtml = notes.length
      ? `<div class="small text-secondary mt-2">${notes.map((n) => `<div>${n}</div>`).join("")}</div>`
      : "";

    elOutputEnv.innerHTML = `
      <div class="alert ${statusClass} py-2 px-3 mt-3 mb-0">${statusText}</div>
      ${toolsHtml}
      ${notesHtml}
    `;
  }

  function renderAssets() {
    const assets = sortedAssets();
    const cues = Array.isArray(state.config?.cues) ? state.config.cues : [];
    const usageByAsset = new Map();
    cues.forEach((c) => {
      const aid = String(c?.assetId || "").trim();
      if (!aid) return;
      if (!usageByAsset.has(aid)) usageByAsset.set(aid, []);
      usageByAsset.get(aid).push({
        id: String(c?.id || ""),
        name: String(c?.name || "Cue").trim() || "Cue",
        bus: busLabel(c?.bus || "sfx"),
      });
    });
    usageByAsset.forEach((rows) => rows.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base", numeric: true })));
    updateAssetSortButtons();
    if (elAssetCountPill) elAssetCountPill.textContent = String(assets.length);
    if (!assets.length) {
      elAssets.innerHTML = `<tr><td colspan="7" class="text-secondary text-center py-3">No assets uploaded yet.</td></tr>`;
      return;
    }
    elAssets.innerHTML = assets
      .map(
        (a) => {
          const usage = usageByAsset.get(String(a.id || "")) || [];
          const usageLabel = usage.length ? String(usage.length) : "0";
          const usagePopover = usage.length
            ? usage
              .map(
                (u) => `<button type="button" class="audio-usage-link" data-audio-jump-cue="${u.id}" title="Open cue">
                    <span class="audio-usage-link-name">${u.name}</span>
                    <span class="audio-usage-link-bus">${u.bus}</span>
                  </button>`
              )
              .join("")
            : `<div class="audio-usage-empty">Not used by any cue</div>`;
          return `<tr data-asset-id="${a.id}">
          <td>
            <div class="audio-asset-name-wrap" data-audio-asset-name-wrap>
              <span class="audio-asset-name-text" data-audio-asset-name-text>${a.displayName}</span>
              <button type="button" class="btn btn-outline-secondary btn-sm audio-icon-btn audio-asset-name-edit" data-audio-asset-name-edit aria-label="Edit name" title="Edit name">
                <i class="fa fa-pen" aria-hidden="true"></i>
              </button>
            </div>
          </td>
          <td>${(a.format || "").toUpperCase()}</td>
          <td>${fmtUploaded(a.createdAt)}</td>
          <td>${fmtMs(a.durationMs)}</td>
          <td>
            <div class="audio-usage-wrap">
              <span class="audio-usage-chip ${usage.length ? "is-used" : "is-unused"}">${usageLabel}</span>
              <div class="audio-usage-popover">
                <div class="audio-usage-popover-title">Cue Usage</div>
                ${usagePopover}
              </div>
            </div>
          </td>
          <td>
            ${renderSharedPlayer({
              kind: "asset",
              id: a.id,
              audioSrc: `/api/audio/assets/file/${encodeURIComponent(a.id)}`,
              totalMs: Number(a.durationMs || 0),
              stateText: "Stopped",
            })}
          </td>
          <td class="text-end">
            <button type="button" class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" data-audio-asset-delete aria-label="Remove asset" title="Remove asset">
              <i class="fa fa-trash" aria-hidden="true"></i><span>Remove</span>
            </button>
          </td>
        </tr>`;
        }
      )
      .join("");
  }

  async function saveAssetDisplayName(assetId, displayName) {
    const cfg = state.config;
    if (!cfg) return;
    const assets = cfg.assets || [];
    const row = assets.find((a) => String(a.id || "") === String(assetId || ""));
    if (!row) return;
    row.displayName = String(displayName || "").trim() || row.displayName || "Audio";
    await api("/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: cfg }),
    });
    const fresh = await api("/config");
    state.config = fresh.config;
    renderAssets();
  }

  function startAssetNameEdit(assetId) {
    const row = elAssets.querySelector(`tr[data-asset-id="${assetId}"]`);
    if (!row) return;
    const wrap = row.querySelector("[data-audio-asset-name-wrap]");
    if (!wrap) return;
    if (wrap.querySelector("input[data-audio-asset-name-input]")) return;
    const textEl = wrap.querySelector("[data-audio-asset-name-text]");
    const current = String(textEl?.textContent || "").trim();
    wrap.innerHTML = `<input type="text" class="form-control form-control-sm audio-asset-name-input" data-audio-asset-name-input value="${current.replace(/\"/g, "&quot;")}">`;
    const input = wrap.querySelector("[data-audio-asset-name-input]");
    if (!input) return;
    const finish = async (commit) => {
      const next = String(input.value || "").trim() || current || "Audio";
      if (!commit || next === current) {
        renderAssets();
        return;
      }
      try {
        await saveAssetDisplayName(assetId, next);
      } catch (err) {
        alert(`Rename failed: ${err.message}`);
        renderAssets();
      }
    };
    input.addEventListener("blur", () => { finish(true); }, { once: true });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        input.blur();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        finish(false);
      }
    });
    input.focus();
    input.select();
  }

  function renderCues() {
    const cues = state.config?.cues || [];
    if (!cues.length) {
      elCues.innerHTML = `<tr><td colspan="11" class="text-secondary text-center py-3">No cues configured.</td></tr>`;
      return;
    }
    const assetIds = new Set((state.config?.assets || []).map((a) => String(a?.id || "")));
    elCues.innerHTML = cues
      .map(
        (c) => {
          const assetId = String(c.assetId || "");
          const hasAsset = assetIds.has(assetId);
          const playerHtml = hasAsset
            ? renderSharedPlayer({ kind: "cue", id: c.id, totalMs: Number((state.config?.assets || []).find((a) => String(a?.id || "") === assetId)?.durationMs || 0) })
            : `<span class="text-secondary small">No asset</span>`;
          return `<tr data-cue-id="${c.id}">
          <td><input class="form-control form-control-sm audio-input-md" data-k="name" value="${c.name || ""}"></td>
          <td><select class="form-select form-select-sm audio-input-md" data-k="assetId">${assetOptions(c.assetId)}</select></td>
          <td>
            <select class="form-select form-select-sm audio-input-sm" data-k="bus">
              <option value="music" ${c.bus === "music" ? "selected" : ""}>Music</option>
              <option value="sfx" ${c.bus === "sfx" ? "selected" : ""}>SFX</option>
              <option value="voice" ${c.bus === "voice" ? "selected" : ""}>Voice</option>
              <option value="ambient" ${c.bus === "ambient" ? "selected" : ""}>Ambient</option>
            </select>
          </td>
          <td>
            <div class="audio-volume-wrap">
              <input type="range" step="0.05" min="0" max="2" class="form-range audio-volume-slider" data-k="volume" value="${Number(c.volume || 1).toFixed(2)}">
              <span class="audio-volume-value" data-audio-volume-value>${Number(c.volume || 1).toFixed(2)}</span>
            </div>
          </td>
          <td>
            <div class="form-check form-switch d-inline-block m-0">
              <input class="form-check-input" type="checkbox" role="switch" data-k="loop" ${c.loop ? "checked" : ""}>
            </div>
          </td>
          <td><input type="number" min="1" max="10000" class="form-control form-control-sm audio-input-xs" data-k="repeatCount" value="${c.repeatCount || 1}"></td>
          <td><input type="number" min="1" max="64" class="form-control form-control-sm audio-input-xs" data-k="maxConcurrent" value="${c.maxConcurrent || 3}"></td>
          <td><input type="number" min="0" max="3600000" class="form-control form-control-sm audio-input-xs" data-k="cooldownMs" value="${c.cooldownMs || 0}"></td>
          <td><select class="form-select form-select-sm audio-input-md" data-k="targetOutput">${deviceOptions(c.targetOutput || "default")}</select></td>
          <td>
            ${playerHtml}
          </td>
          <td class="text-end">
            <button type="button" class="btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1" data-audio-cue-delete aria-label="Remove cue" title="Remove cue">
              <i class="fa fa-trash" aria-hidden="true"></i><span>Remove</span>
            </button>
          </td>
        </tr>`;
        }
      )
      .join("");
    applyCuePlaybackState();
  }

  function renderMaps() {
    const cfgMaps = Array.isArray(state.config?.mappings) ? state.config.mappings : [];
    const maps = cfgMaps.length ? cfgMaps : (Array.isArray(state.rulesUsageMaps) ? state.rulesUsageMaps : []);
    if (!maps.length) {
      elMaps.innerHTML = `<tr><td colspan="6" class="text-secondary text-center py-3">No audio rule usage found.</td></tr>`;
      return;
    }
    elMaps.innerHTML = maps
      .map(
        (m) => `<tr data-map-id="${m.id}">
          <td><code>${escHtml(m.eventName || "")}</code></td>
          <td><span class="badge text-bg-secondary">${escHtml(m.matchMode || "exact")}</span></td>
          <td>${escHtml(m.eventSource || "any")}</td>
          <td><span class="badge text-bg-info">${escHtml(m.action || "play")}</span></td>
          <td>${escHtml(
            String(m.cueId || "") === "__all__"
              ? "All Cues"
              : ((state.config?.cues || []).find((c) => String(c.id || "") === String(m.cueId || ""))?.name || m.cueId || "(none)")
          )}</td>
          <td>${Number(m.priority || 100)}</td>
        </tr>`
      )
      .join("");
  }

  function buildUsageMapsFromRules(rules) {
    const out = [];
    if (!Array.isArray(rules)) return out;
    rules.forEach((rule, rIdx) => {
      if (!rule || typeof rule !== "object") return;
      if (rule.enabled === false) return;
      const actions = Array.isArray(rule.actions) ? rule.actions : [];
      if (!actions.length) return;
      const triggerGroups = Array.isArray(rule?.triggerGroups?.groups) ? rule.triggerGroups.groups : [];
      const fallbackTriggers = Array.isArray(rule?.triggers) ? rule.triggers : [];
      const groups = triggerGroups.length
        ? triggerGroups
        : [{ logic: String(rule?.logic || "ALL").toUpperCase(), items: fallbackTriggers }];
      actions.forEach((a, aIdx) => {
        const actionType = String(a?.type || "").trim().toLowerCase();
        if (actionType !== "play_audio_cue" && actionType !== "stop_audio_cue" && actionType !== "toggle_audio_cue") return;
        const cueId = String(a?.params?.cueId || a?.target || "").trim();
        const actionLabel = actionType === "stop_audio_cue" ? "stop" : (actionType === "toggle_audio_cue" ? "toggle" : "play");
        const groupLogic = String(rule?.triggerGroups?.logic || rule?.logic || "ALL").trim().toLowerCase();
        groups.forEach((group, gIdx) => {
          const items = Array.isArray(group?.items) ? group.items : [];
          if (!items.length) {
            out.push({
              id: `rules_${rIdx}_${aIdx}_${gIdx}_none`,
              eventName: String(rule?.name || "RULE_TRIGGER").trim() || "RULE_TRIGGER",
              matchMode: groupLogic || "all",
              eventSource: "any",
              action: actionLabel,
              cueId: cueId || "__all__",
              priority: Number(rule?.priority || 100),
            });
            return;
          }
          items.forEach((t, tIdx) => {
            const ev = String(t?.event || t?.key || t?.name || t?.fn || "").trim();
            const eventName = ev || (String(rule?.name || "RULE_TRIGGER").trim() || "RULE_TRIGGER");
            const src = String(t?.source || "").trim() || "any";
            out.push({
              id: `rules_${rIdx}_${aIdx}_${gIdx}_${tIdx}`,
              eventName,
              matchMode: String(group?.logic || groupLogic || "all").trim().toLowerCase() || "all",
              eventSource: src,
              action: actionLabel,
              cueId: cueId || "__all__",
              priority: Number(rule?.priority || 100),
            });
          });
        });
      });
    });
    return out;
  }

  function renderRuntime() {
    const active = state.runtime?.engine?.active || [];
    if (!active.length) {
      elRuntime.innerHTML = `<div class="text-secondary small">No active playback.</div>`;
      return;
    }
    const cues = state.config?.cues || [];
    const assets = state.config?.assets || [];
    const cueById = new Map(cues.map((c) => [String(c.id || ""), c]));
    const assetById = new Map(assets.map((a) => [String(a.id || ""), a]));

    const cueLabel = (cueId) => {
      const id = String(cueId || "");
      const cue = cueById.get(id);
      if (cue) return cue.name || id;
      if (id.startsWith("preview_asset_")) {
        const aid = id.slice("preview_asset_".length);
        const asset = assetById.get(aid);
        return asset ? `Preview: ${asset.displayName || aid}` : `Preview: ${aid}`;
      }
      if (id.startsWith("orphan:")) return `Orphan ${id.split(":", 2)[1] || ""}`.trim();
      return id;
    };

    elRuntime.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm mb-0 align-middle">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Bus</th>
              <th>Source</th>
              <th>Output</th>
              <th>PID</th>
              <th class="text-end">Action</th>
            </tr>
          </thead>
          <tbody>
            ${active
              .map(
                (r) => `<tr>
                  <td>${escHtml(cueLabel(r.cueId || r.playbackId || ""))}${r.orphan ? ` <span class="badge text-bg-warning ms-1">orphan</span>` : ""}</td>
                  <td>${r.orphan ? '<span class="badge text-bg-warning">Orphan</span>' : '<span class="badge text-bg-success">Playing</span>'}</td>
                  <td><span class="badge text-bg-secondary">${busLabel(r.bus)}</span></td>
                  <td>${escHtml(r.source || "n/a")}</td>
                  <td>${escHtml(r.targetOutput || "default")}</td>
                  <td>${Number(r.pid || 0) > 0 ? Number(r.pid) : "-"}</td>
                  <td class="text-end">
                    <button type="button" class="btn btn-outline-danger btn-sm" data-audio-runtime-stop data-playback-id="${escHtml(r.playbackId || "")}" data-pid="${Number(r.pid || 0) > 0 ? Number(r.pid) : ""}">Stop</button>
                  </td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
    applyCuePlaybackState();
  }

  function readTablesBackIntoConfig() {
    const cfg = state.config;
    if (!cfg) return;

    cfg.cues = Array.from(elCues.querySelectorAll("tr[data-cue-id]")).map((tr) => ({
      id: tr.dataset.cueId,
      name: tr.querySelector('[data-k="name"]').value.trim(),
      assetId: tr.querySelector('[data-k="assetId"]').value,
      bus: tr.querySelector('[data-k="bus"]').value,
      volume: Number(tr.querySelector('[data-k="volume"]').value || 1),
      loop: !!tr.querySelector('[data-k="loop"]').checked,
      repeatCount: Number(tr.querySelector('[data-k="repeatCount"]').value || 1),
      maxConcurrent: Number(tr.querySelector('[data-k="maxConcurrent"]').value || 3),
      cooldownMs: Number(tr.querySelector('[data-k="cooldownMs"]').value || 0),
      restartPolicy: "layer",
      targetOutput: tr.querySelector('[data-k="targetOutput"]').value || "default",
      enabled: true,
      notes: "",
    }));

    const mapRows = Array.from(elMaps.querySelectorAll("tr[data-map-id]"));
    const hasEditableMaps = mapRows.some((tr) => !!tr.querySelector('[data-k="eventName"]'));
    if (hasEditableMaps) {
      cfg.mappings = mapRows.map((tr) => ({
        id: tr.dataset.mapId,
        enabled: true,
        eventName: tr.querySelector('[data-k="eventName"]').value.trim().toUpperCase(),
        matchMode: tr.querySelector('[data-k="matchMode"]').value,
        eventSource: tr.querySelector('[data-k="eventSource"]').value.trim(),
        sourceMatchMode: "exact",
        action: tr.querySelector('[data-k="action"]').value,
        cueId: tr.querySelector('[data-k="cueId"]').value,
        priority: Number(tr.querySelector('[data-k="priority"]').value || 100),
      }));
    }
  }

  async function loadAll(refreshDevices = false) {
    const [cfgRes, devRes, runtimeRes, rulesRes] = await Promise.allSettled([
      api("/config"),
      api(`/devices${refreshDevices ? "?refresh=1" : ""}`),
      api("/state"),
      fetch("/api/rules/list", { cache: "no-store" }).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))),
    ]);

    if (cfgRes.status === "fulfilled" && cfgRes.value?.config) {
      state.config = cfgRes.value.config;
    } else if (!state.config) {
      state.config = { assets: [], cues: [], mappings: [] };
    }

    if (devRes.status === "fulfilled") {
      state.devices = devRes.value?.devices || [];
      state.outputEnv = devRes.value || null;
    } else {
      state.devices = [];
      state.outputEnv = null;
    }

    if (runtimeRes.status === "fulfilled") {
      state.runtime = runtimeRes.value?.state || null;
    } else {
      state.runtime = null;
    }

    if (rulesRes.status === "fulfilled") {
      const rules = Array.isArray(rulesRes.value?.rules) ? rulesRes.value.rules : [];
      state.rulesUsageMaps = buildUsageMapsFromRules(rules);
    } else {
      state.rulesUsageMaps = [];
    }

    renderDevices();
    renderOutputEnvironment();
    renderAssets();
    renderCues();
    renderMaps();
    renderRuntime();
    setDirty(false);
  }

  async function refreshRuntimeOnly() {
    try {
      const runtime = await api("/state");
      state.runtime = runtime.state || null;
      renderRuntime();
    } catch (_) {
      // Keep polling resilient; avoid disrupting current editing flow.
    }
  }

  function startRuntimePolling() {
    if (runtimePollTimer) return;
    runtimePollTimer = window.setInterval(refreshRuntimeOnly, 1000);
  }

  function startCueUiTicker() {
    if (cueUiTimer) return;
    cueUiTimer = window.setInterval(updateCueProgressFromRuntime, 250);
  }

  async function waitForCueRuntimeState(cueId, shouldBeActive, timeoutMs = 700) {
    const deadline = Date.now() + Math.max(100, Number(timeoutMs) || 700);
    while (Date.now() < deadline) {
      await refreshRuntimeOnly();
      const isActive = activeCueHandleById().has(String(cueId || ""));
      if (isActive === !!shouldBeActive) return;
      await new Promise((resolve) => window.setTimeout(resolve, 80));
    }
  }

  root.querySelectorAll("[data-audio-refresh]").forEach((btn) => {
    btn.addEventListener("click", () => loadAll(false));
  });
  root.querySelectorAll(".audio-sort-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-audio-sort-key") || "";
      if (!key) return;
      if (state.assetSort.key === key) {
        state.assetSort.dir = state.assetSort.dir === "asc" ? "desc" : "asc";
      } else {
        state.assetSort.key = key;
        state.assetSort.dir = getDefaultAssetSortDir(key);
      }
      renderAssets();
    });
  });
  $("#audio-refresh-devices").addEventListener("click", () => loadAll(true));

  $("#audio-add-cue").addEventListener("click", () => {
    const cfg = state.config;
    cfg.cues.push({
      id: uid("cue"),
      name: "New Cue",
      enabled: true,
      assetId: "",
      bus: "sfx",
      volume: 1,
      loop: false,
      repeatCount: 1,
      maxConcurrent: 3,
      cooldownMs: 0,
      restartPolicy: "layer",
      targetOutput: "default",
      notes: "",
    });
    renderCues();
    setDirty(true);
  });

  const addMapBtn = $("#audio-add-map");
  if (addMapBtn) {
    addMapBtn.addEventListener("click", () => {
      const cfg = state.config;
      cfg.mappings.push({
        id: uid("map"),
        enabled: true,
        eventName: "",
        matchMode: "exact",
        eventSource: "",
        sourceMatchMode: "exact",
        action: "play",
        cueId: "",
        priority: 100,
      });
      renderMaps();
      setDirty(true);
    });
  }

  root.querySelectorAll("[data-audio-save]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        readTablesBackIntoConfig();
        await api("/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ config: state.config }),
        });
        await loadAll(false);
      } catch (err) {
        alert(`Save failed: ${err.message}`);
      }
    });
  });

  const markDirtyFromEvent = (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.closest("tr[data-cue-id]") && !target.closest("tr[data-map-id]")) return;
    if (!target.closest("[data-k]")) return;
    setDirty(true);
  };
  elCues.addEventListener("input", markDirtyFromEvent);
  elCues.addEventListener("change", markDirtyFromEvent);
  elMaps.addEventListener("input", markDirtyFromEvent);
  elMaps.addEventListener("change", markDirtyFromEvent);
  elCues.addEventListener("input", (e) => {
    const input = e.target;
    if (!(input instanceof HTMLInputElement)) return;
    if (input.getAttribute("data-k") !== "volume") return;
    const row = input.closest("tr[data-cue-id]");
    const label = row ? row.querySelector("[data-audio-volume-value]") : null;
    if (!label) return;
    const v = Number(input.value || 0);
    label.textContent = Number.isFinite(v) ? v.toFixed(2) : "0.00";
  });

  if (elUploadBrowse && elUploadFile) {
    elUploadBrowse.addEventListener("click", (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      if (uploadInProgress) return;
      elUploadFile.click();
    });
  }

  if (elUploadFile) {
    elUploadFile.addEventListener("change", async () => {
      const files = elUploadFile.files || [];
      if (!files.length) return;
      if (elUploadDropzone) elUploadDropzone.classList.add("is-uploading");
      await uploadFiles(files);
    });
  }

  if (elUploadDropzone) {
    const stopDefaults = (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
    };

    ["dragenter", "dragover", "dragleave", "drop"].forEach((name) => {
      elUploadDropzone.addEventListener(name, stopDefaults);
    });

    ["dragenter", "dragover"].forEach((name) => {
      elUploadDropzone.addEventListener(name, () => {
        if (!uploadInProgress) elUploadDropzone.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach((name) => {
      elUploadDropzone.addEventListener(name, () => {
        elUploadDropzone.classList.remove("is-dragover");
      });
    });

    elUploadDropzone.addEventListener("drop", async (evt) => {
      if (uploadInProgress) return;
      const files = evt.dataTransfer?.files || [];
      if (!files.length) return;
      elUploadDropzone.classList.add("is-uploading");
      await uploadFiles(files);
    });

    elUploadDropzone.addEventListener("click", () => {
      if (uploadInProgress) return;
      if (elUploadFile) elUploadFile.click();
    });

    elUploadDropzone.addEventListener("keydown", (evt) => {
      if (uploadInProgress) return;
      if (evt.key === "Enter" || evt.key === " ") {
        evt.preventDefault();
        if (elUploadFile) elUploadFile.click();
      }
    });
  }

  function assetPlayerForRow(row) {
    return row?.querySelector('[data-audio-player-kind="asset"]') || null;
  }

  function assetAudioForPlayer(playerEl) {
    return playerEl?.querySelector("[data-audio-asset-audio]") || null;
  }

  function assetTotalMs(playerEl, audioEl = null) {
    const fromData = Number(playerEl?.getAttribute("data-audio-player-total-ms") || 0);
    if (fromData > 0) return fromData;
    const a = audioEl || assetAudioForPlayer(playerEl);
    if (!a) return 0;
    const d = Number(a.duration || 0);
    return d > 0 ? Math.floor(d * 1000) : 0;
  }

  function syncAssetPlayerFromAudio(playerEl) {
    const audioEl = assetAudioForPlayer(playerEl);
    if (!audioEl) return;
    const totalMs = assetTotalMs(playerEl, audioEl);
    const elapsedMs = Math.max(0, Math.floor((Number(audioEl.currentTime || 0)) * 1000));
    const units = totalMs > 0 ? Math.floor(Math.max(0, Math.min(1, elapsedMs / totalMs)) * 1000) : 0;
    setSharedPlayerUi(playerEl, {
      units,
      elapsedMs,
      totalMs,
      isPlaying: !audioEl.paused && !audioEl.ended,
      stateText: !audioEl.paused && !audioEl.ended ? "Playing" : (elapsedMs > 0 ? "Paused" : "Stopped"),
      cycleText: "",
    });
  }

  function pauseOtherAssetPlayers(exceptPlayerEl) {
    elAssets.querySelectorAll('[data-audio-player-kind="asset"]').forEach((playerEl) => {
      if (playerEl === exceptPlayerEl) return;
      const audioEl = assetAudioForPlayer(playerEl);
      if (!audioEl) return;
      try { audioEl.pause(); } catch (_) {}
      syncAssetPlayerFromAudio(playerEl);
    });
  }

  elAssets.addEventListener("click", async (e) => {
    const row = e.target.closest("tr[data-asset-id]");
    if (!row) return;
    const assetId = row.dataset.assetId;
    const playerEl = assetPlayerForRow(row);
    const toggleBtn = e.target.closest("[data-audio-asset-toggle]");
    const jumpCueBtn = e.target.closest("[data-audio-jump-cue]");
    const nameText = e.target.closest("[data-audio-asset-name-text]");
    const nameEditBtn = e.target.closest("[data-audio-asset-name-edit]");
    const deleteBtn = e.target.closest("[data-audio-asset-delete]");

    if (toggleBtn && playerEl) {
      const audioEl = assetAudioForPlayer(playerEl);
      if (!audioEl) return;
      if (!audioEl.paused && !audioEl.ended) {
        try { audioEl.pause(); } catch (_) {}
        syncAssetPlayerFromAudio(playerEl);
        return;
      }
      pauseOtherAssetPlayers(playerEl);
      try {
        const p = audioEl.play();
        if (p && typeof p.catch === "function") {
          p.catch(() => { syncAssetPlayerFromAudio(playerEl); });
        }
      } catch (_) {}
      syncAssetPlayerFromAudio(playerEl);
      return;
    }

    if (jumpCueBtn) {
      const cueId = String(jumpCueBtn.getAttribute("data-audio-jump-cue") || "").trim();
      if (!cueId) return;
      const cueTabBtn = document.getElementById("audio-tab-cues");
      if (cueTabBtn && window.bootstrap?.Tab) {
        window.bootstrap.Tab.getOrCreateInstance(cueTabBtn).show();
      }
      window.setTimeout(() => {
        const cueRow = elCues.querySelector(`tr[data-cue-id="${cueId}"]`);
        if (!cueRow) return;
        cueRow.classList.remove("audio-row-flash");
        cueRow.scrollIntoView({ behavior: "smooth", block: "center" });
        // force reflow so animation can replay when clicking the same cue repeatedly
        void cueRow.offsetWidth;
        cueRow.classList.add("audio-row-flash");
      }, 80);
      return;
    }

    if (nameText || nameEditBtn) {
      startAssetNameEdit(assetId);
      return;
    }

    if (deleteBtn) {
      const ok = await askConfirm("Remove this asset?", {
        title: "Remove Asset",
        label: "Remove",
        confirmClass: "btn-danger",
      });
      if (!ok) return;
      try {
        await api("/assets/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ assetId }),
        });
        await loadAll(false);
      } catch (err) {
        alert(`Remove failed: ${err.message}`);
      }
    }
  });

  elAssets.addEventListener("loadedmetadata", (e) => {
    const audioEl = e.target;
    if (!(audioEl instanceof HTMLAudioElement) || !audioEl.matches("[data-audio-asset-audio]")) return;
    const playerEl = audioEl.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    const totalMs = Math.max(0, Math.floor(Number(audioEl.duration || 0) * 1000));
    if (totalMs > 0) playerEl.setAttribute("data-audio-player-total-ms", String(totalMs));
    syncAssetPlayerFromAudio(playerEl);
  }, true);

  elAssets.addEventListener("timeupdate", (e) => {
    const audioEl = e.target;
    if (!(audioEl instanceof HTMLAudioElement) || !audioEl.matches("[data-audio-asset-audio]")) return;
    const playerEl = audioEl.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    syncAssetPlayerFromAudio(playerEl);
  }, true);

  elAssets.addEventListener("play", (e) => {
    const audioEl = e.target;
    if (!(audioEl instanceof HTMLAudioElement) || !audioEl.matches("[data-audio-asset-audio]")) return;
    const playerEl = audioEl.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    pauseOtherAssetPlayers(playerEl);
    syncAssetPlayerFromAudio(playerEl);
  }, true);

  elAssets.addEventListener("pause", (e) => {
    const audioEl = e.target;
    if (!(audioEl instanceof HTMLAudioElement) || !audioEl.matches("[data-audio-asset-audio]")) return;
    const playerEl = audioEl.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    syncAssetPlayerFromAudio(playerEl);
  }, true);

  elAssets.addEventListener("ended", (e) => {
    const audioEl = e.target;
    if (!(audioEl instanceof HTMLAudioElement) || !audioEl.matches("[data-audio-asset-audio]")) return;
    const playerEl = audioEl.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    try { audioEl.currentTime = 0; } catch (_) {}
    setSharedPlayerUi(playerEl, { units: 0, elapsedMs: 0, totalMs: assetTotalMs(playerEl, audioEl), isPlaying: false, stateText: "Stopped" });
  }, true);

  elAssets.addEventListener("input", (e) => {
    const scrub = e.target.closest("[data-audio-asset-scrub]");
    if (!scrub) return;
    const playerEl = scrub.closest('[data-audio-player-kind="asset"]');
    if (!playerEl) return;
    const audioEl = assetAudioForPlayer(playerEl);
    if (!audioEl) return;
    const totalMs = assetTotalMs(playerEl, audioEl);
    if (totalMs <= 0) return;
    const units = Math.max(0, Math.min(1000, Number(scrub.value || 0)));
    const seekMs = Math.floor((units / 1000) * totalMs);
    try { audioEl.currentTime = seekMs / 1000; } catch (_) {}
    setSharedPlayerUi(playerEl, {
      units,
      elapsedMs: seekMs,
      totalMs,
      isPlaying: !audioEl.paused && !audioEl.ended,
      stateText: !audioEl.paused && !audioEl.ended ? "Playing" : "Paused",
      cycleText: "",
    });
  });

  elCues.addEventListener("click", async (e) => {
    const row = e.target.closest("tr[data-cue-id]");
    if (!row) return;
    const cueId = row.dataset.cueId;
    const cueToggleBtn = e.target.closest("[data-audio-cue-toggle]");
    const cueDeleteBtn = e.target.closest("[data-audio-cue-delete]");

    if (cueToggleBtn) {
      if (cueActionBusy.has(cueId)) return;
      const cue = cuePreviewPayloadFromRow(row);
      if (!cue.assetId) {
        alert("Select an asset for this cue before preview.");
        return;
      }
      cueActionBusy.add(cueId);
      cueToggleBtn.disabled = true;
      try {
        await refreshRuntimeOnly();
        const isActive = activeCueHandleById().has(cueId);
        if (isActive) {
          const handle = activeCueHandleById().get(cueId);
          const nowMs = Date.now();
          const calc = cueProgressAtMs(row, handle, nowMs);
          cuePausedMs.set(cueId, Math.max(0, Math.floor(calc.shownElapsedMs)));
          await api("/stop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cueId }),
          });
          await waitForCueRuntimeState(cueId, false, 900);
        } else {
          const seekMs = Math.max(0, Math.floor(Number(cuePausedMs.get(cueId) || 0)));
          await api("/stop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ previewOnly: true }),
          });
          await api("/cues/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cue, seekMs }),
          });
          await waitForCueRuntimeState(cueId, true, 900);
        }
        await refreshRuntimeOnly();
      } catch (err) {
        alert(`Playback failed: ${err.message}`);
      } finally {
        cueActionBusy.delete(cueId);
        applyCuePlaybackState();
      }
      return;
    }

    if (cueDeleteBtn) {
      const cfg = state.config;
      cfg.cues = (cfg.cues || []).filter((c) => c.id !== cueId);
      cfg.mappings = (cfg.mappings || []).map((m) => (m.cueId === cueId ? { ...m, cueId: "" } : m));
      renderCues();
      renderMaps();
      setDirty(true);
      return;
    }
  });

  elCues.addEventListener("pointerdown", (e) => {
    const scrub = e.target.closest("[data-audio-cue-scrub]");
    if (!scrub) return;
    const row = scrub.closest("tr[data-cue-id]");
    if (!row) return;
    cueScrubDragging.add(String(row.dataset.cueId || ""));
  });

  const applyCueScrub = async (row, slider) => {
    if (!row || !slider) return;
    const cueId = String(row.dataset.cueId || "");
    if (cueActionBusy.has(cueId)) return;
    const cue = cuePreviewPayloadFromRow(row);
    if (!cue.assetId) return;
    const timing = cueRowTiming(row);
    const baseTotalMs = timing.assetDurationMs;
    if (!baseTotalMs || baseTotalMs <= 0) return;
    const ratio = Math.max(0, Math.min(1, Number(slider.value || 0) / 1000));
    const seekUnits = Math.floor(ratio * 1000);
    const seekMs = Math.floor(baseTotalMs * ratio);
    cuePendingSeekUnits.set(cueId, seekUnits);
    cuePausedMs.set(cueId, seekMs);
    const bar = row.querySelector("[data-audio-cue-progressbar]");
    if (bar) setCueBarToScrubPosition(slider, bar, seekUnits);
    const isActive = activeCueHandleById().has(cueId);
    if (!isActive) {
      cuePendingSeekUnits.delete(cueId);
      updateCueProgressFromRuntime();
      return;
    }
    cueActionBusy.add(cueId);
    try {
      await api("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cueId }),
      });
      await waitForCueRuntimeState(cueId, false, 900);
      await api("/cues/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cue, seekMs }),
      });
      await waitForCueRuntimeState(cueId, true, 900);
      await refreshRuntimeOnly();
    } catch (err) {
      alert(`Seek failed: ${err.message}`);
    } finally {
      cuePendingSeekUnits.delete(cueId);
      cueActionBusy.delete(cueId);
    }
  };

  elCues.addEventListener("input", (e) => {
    const scrub = e.target.closest("[data-audio-cue-scrub]");
    if (!scrub) return;
    const row = scrub.closest("tr[data-cue-id]");
    if (!row) return;
    const cueId = String(row.dataset.cueId || "");
    cueScrubDragging.add(cueId);
    const timing = cueRowTiming(row);
    const baseTotalMs = timing.assetDurationMs;
    if (!baseTotalMs || baseTotalMs <= 0) return;
    const ratio = Math.max(0, Math.min(1, Number(scrub.value || 0) / 1000));
    const seekUnits = Math.floor(ratio * 1000);
    const seekMs = Math.floor(baseTotalMs * ratio);
    cuePendingSeekUnits.set(cueId, seekUnits);
    cuePausedMs.set(cueId, seekMs);
    const bar = row.querySelector("[data-audio-cue-progressbar]");
    if (bar) setCueBarToScrubPosition(scrub, bar, seekUnits);
    const elapsedEl = row.querySelector("[data-audio-cue-elapsed]");
    const stateEl = row.querySelector("[data-audio-cue-state]");
    if (elapsedEl) elapsedEl.textContent = formatTimeSeconds(seekMs / 1000);
    if (stateEl && !activeCueHandleById().has(cueId)) stateEl.textContent = "Paused";
  });

  elCues.addEventListener("change", async (e) => {
    const scrub = e.target.closest("[data-audio-cue-scrub]");
    if (!scrub) return;
    const row = scrub.closest("tr[data-cue-id]");
    if (!row) return;
    await applyCueScrub(row, scrub);
    cueScrubDragging.delete(String(row.dataset.cueId || ""));
  });

  elCues.addEventListener("pointerup", (e) => {
    const scrub = e.target.closest("[data-audio-cue-scrub]");
    if (!scrub) return;
    const row = scrub.closest("tr[data-cue-id]");
    if (!row) return;
    cueScrubDragging.delete(String(row.dataset.cueId || ""));
  });

  elMaps.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-map-id]");
    if (!row) return;
    if (e.target.matches("[data-audio-map-delete]")) {
      const mapId = row.dataset.mapId;
      state.config.mappings = (state.config.mappings || []).filter((m) => m.id !== mapId);
      renderMaps();
      setDirty(true);
    }
  });

  elRuntime.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-audio-runtime-stop]");
    if (!btn) return;
    const playbackId = String(btn.getAttribute("data-playback-id") || "").trim();
    const pidRaw = String(btn.getAttribute("data-pid") || "").trim();
    const pid = pidRaw ? Number(pidRaw) : null;
    btn.disabled = true;
    try {
      await api("/runtime/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playbackId, pid }),
      });
      await refreshRuntimeOnly();
    } catch (err) {
      alert(`Runtime stop failed: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = "";
  });

  setDirty(false);

  loadAll(false).catch((err) => {
    console.error(err);
    alert(`Audio module failed to load: ${err.message}`);
  });
  wireTabPersistence();
  startRuntimePolling();
  startCueUiTicker();
})();
