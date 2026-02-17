// Vanilla dashboard poller for live status cards.
(function () {
  const root = document.getElementById("dashboard-root");
  if (!root) return;

  const fields = {
    wifiIface: root.querySelector('[data-field="wifi-iface"]'),
    wifiConnected: root.querySelector('[data-field="wifi-connected-label"]'),
    wifiSsid: root.querySelector('[data-field="wifi-ssid"]'),
    wifiIp: root.querySelector('[data-field="wifi-ip"]'),
    wifiSignal: root.querySelector('[data-field="wifi-signal"]'),
    bridgeStatus: root.querySelector('[data-field="bridge-status"]'),
    bridgeVia: root.querySelector('[data-field="bridge-via"]'),
    bridgePid: root.querySelector('[data-field="bridge-pid"]'),
    uptimeSince: root.querySelector('[data-field="uptime-since"]'),
    uptimeHuman: root.querySelector('[data-field="uptime-human"]'),
    uptimeSeconds: root.querySelector('[data-field="uptime-seconds"]'),
    depsList: root.querySelector('[data-field="deps-list"]'),
    espFw: root.querySelector('[data-field="esp-fw"]'),
    espChip: root.querySelector('[data-field="esp-chip"]'),
    espTime: root.querySelector('[data-field="esp-time"]'),
    espTimeSync: root.querySelector('[data-field="esp-time-sync"]'),
    espConnected: root.querySelector('[data-field="esp-connected"]'),
    syncRules: root.querySelector('[data-field="sync-rules-status"]'),
    syncRulesAt: root.querySelector('[data-field="sync-rules-at"]'),
    syncHardware: root.querySelector('[data-field="sync-hardware-status"]'),
    syncHardwareAt: root.querySelector('[data-field="sync-hardware-at"]'),
    syncLighting: root.querySelector('[data-field="sync-lighting-status"]'),
    syncLightingAt: root.querySelector('[data-field="sync-lighting-at"]'),
    syncRulesRows: root.querySelectorAll('[data-row="sync-rules"]'),
    syncHardwareRows: root.querySelectorAll('[data-row="sync-hardware"]'),
    syncLightingRows: root.querySelectorAll('[data-row="sync-lighting"]'),
    perfEps: root.querySelector('[data-field="perf-eps"]'),
    perfDrainRate: root.querySelector('[data-field="perf-drain-rate"]'),
    perfPendingTotal: root.querySelector('[data-field="perf-pending-total"]'),
    perfGaugeNeedle: root.querySelector('[data-field="perf-gauge-needle"]'),
    perfAutoRefresh: root.querySelector('[data-field="perf-auto-refresh"]'),
  };

  let timer = null;
  let inflight = false;
  let quickRetry = false;
  let spinnerTimer = null;
  let dashletRelativeTimer = null;
  let lastEspConnected = null;
  let perfTimer = null;
  let perfInflight = false;
  let perfPrevSubmitted = null;
  let perfPrevCompleted = null;
  let perfPrevAtMs = null;
  let perfEpsSmoothed = 0;
  let perfDrainSmoothed = 0;
  const perfEpsHistory = [];
  const perfDrainHistory = [];
  const pollDelay = 10000;
  const perfGaugeMax = 600;
  const currencySymbols = {
    GBP: "£",
    USD: "$",
    EUR: "€",
    JPY: "¥",
  };
  const dashletUpdatedAtMs = new Map();
  const dashletUpdatedEls = new Map();

  function setLoading(flag) {
    root.classList.toggle("loading", flag);
    if (!flag) {
      root.classList.remove("show-spinners");
      if (spinnerTimer) {
        clearTimeout(spinnerTimer);
        spinnerTimer = null;
      }
      return;
    }
    if (spinnerTimer) return;
    spinnerTimer = setTimeout(() => {
      root.classList.add("show-spinners");
    }, 500);
  }

  async function loadCurrency() {
    try {
      const res = await fetch("/api/settings/data", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const symbol = currencySymbols[data.CURRENCY] || "£";
      root.querySelectorAll('[data-field="currency-symbol"]').forEach((el) => {
        el.textContent = symbol;
      });
    } catch (err) {
      console.warn("[dashboard] currency fetch error", err);
    }
  }

  setLoading(true);

  function dashletFriendlyAge(msAgo) {
    const ms = Math.max(0, Number(msAgo) || 0);
    if (ms < 10000) return "Just now";
    const sec = Math.floor(ms / 1000);
    const secBucket = Math.floor(sec / 10) * 10;
    if (secBucket < 60) return `${secBucket} seconds ago`;
    const min = Math.floor(secBucket / 60);
    if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
    const day = Math.floor(hr / 24);
    return `${day} day${day === 1 ? "" : "s"} ago`;
  }

  function renderDashletUpdatedLabels() {
    const now = Date.now();
    dashletUpdatedEls.forEach((el, dashletId) => {
      if (!el) return;
      const at = dashletUpdatedAtMs.get(dashletId);
      if (!Number.isFinite(at)) {
        el.textContent = "Never";
        return;
      }
      el.textContent = dashletFriendlyAge(now - at);
    });
  }

  function touchDashletUpdated(dashletId, atMs) {
    const id = String(dashletId || "").trim();
    if (!id || !dashletUpdatedEls.has(id)) return;
    const ts = Number.isFinite(Number(atMs)) ? Number(atMs) : Date.now();
    dashletUpdatedAtMs.set(id, ts);
    renderDashletUpdatedLabels();
  }

  function touchDashletsUpdated(ids, atMs) {
    if (!Array.isArray(ids)) return;
    ids.forEach((id) => touchDashletUpdated(id, atMs));
  }

  function initDashletUpdatedUi() {
    const cards = Array.from(root.querySelectorAll(".card[data-dashlet]"));
    cards.forEach((card) => {
      const dashletId = String(card.getAttribute("data-dashlet") || "").trim();
      if (!dashletId) return;
      const title = card.querySelector(".card-title");
      if (!title) return;
      let actions = title.querySelector(".dashlet-title-actions");
      if (!actions) {
        actions = document.createElement("span");
        actions.className = "dashlet-title-actions ms-auto";
        title.appendChild(actions);
      }
      let updated = actions.querySelector("[data-dashlet-updated]");
      if (!updated) {
        updated = document.createElement("span");
        updated.className = "dashlet-updated text-secondary";
        updated.setAttribute("data-dashlet-updated", dashletId);
        actions.appendChild(updated);
      }
      dashletUpdatedEls.set(dashletId, updated);
      updated.textContent = "Never";
      if (card.getAttribute("data-dashlet-static") === "true") {
        dashletUpdatedAtMs.set(dashletId, Date.now());
      }

      const spinner = title.querySelector(".dashlet-spinner");
      if (spinner) {
        spinner.classList.remove("ms-auto");
        if (!actions.contains(spinner)) actions.appendChild(spinner);
      }
    });
    renderDashletUpdatedLabels();
    if (dashletRelativeTimer) clearInterval(dashletRelativeTimer);
    dashletRelativeTimer = setInterval(renderDashletUpdatedLabels, 10000);
  }

  function setBadge(el, ok, text) {
    if (!el) return;
    el.textContent = text;
    el.classList.remove("bg-success", "bg-danger", "bg-secondary");
    if (ok === true) el.classList.add("bg-success");
    else if (ok === false) el.classList.add("bg-danger");
    else el.classList.add("bg-secondary");
  }

  function setSyncBadge(el, ok, text) {
    if (!el) return;
    el.textContent = text;
    el.classList.remove("bg-success", "bg-warning", "bg-secondary");
    if (ok === true) el.classList.add("bg-success");
    else if (ok === false) el.classList.add("bg-warning");
    else el.classList.add("bg-secondary");
  }

  function setSyncNotConnected() {
    setSyncBadge(fields.syncRules, null, "Not Connected");
    setSyncBadge(fields.syncHardware, null, "Not Connected");
    setSyncBadge(fields.syncLighting, null, "Not Connected");
    if (fields.syncRulesAt) fields.syncRulesAt.textContent = "";
    if (fields.syncHardwareAt) fields.syncHardwareAt.textContent = "";
    if (fields.syncLightingAt) fields.syncLightingAt.textContent = "";
  }

  setSyncNotConnected();

  function normalizeTimestamp(value) {
    if (!value) return null;
    if (typeof value === "number") {
      return value < 1e12 ? value * 1000 : value;
    }
    if (typeof value === "string") {
      if (/^\d+$/.test(value)) {
        const numeric = Number(value);
        return numeric < 1e12 ? numeric * 1000 : numeric;
      }
      return value;
    }
    return value;
  }

  function formatSyncedAt(value) {
    const normalized = normalizeTimestamp(value);
    if (!normalized) return "";
    const d = new Date(normalized);
    if (Number.isNaN(d.getTime())) return "";
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }).format(d).replace(",", "");
  }

  function setValue(el, value) {
    if (!el) return;
    el.textContent = value === 0 || value ? String(value) : "—";
  }

  function setPerfGauge(value) {
    const clamped = Math.max(0, Math.min(perfGaugeMax, Number(value) || 0));
    const angle = -90 + ((clamped / perfGaugeMax) * 180);
    if (fields.perfGaugeNeedle) {
      fields.perfGaugeNeedle.setAttribute("transform", `rotate(${angle.toFixed(2)} 110 120)`);
    }
  }

  function avg(values) {
    if (!values.length) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  function renderPerf(data) {
    const perf = data?.postFire || {};
    const nowMs = Date.now();
    const submitted = Number(perf?.submitted ?? 0) || 0;
    const completed = Number(perf?.completed ?? 0) || 0;
    const pending = Number(perf?.pendingTotal ?? 0) || 0;
    const outstanding = Math.max(0, pending);
    setValue(fields.perfPendingTotal, outstanding);

    let epsRaw = 0; // ingest rate (submitted delta)
    let drainRaw = 0; // processing rate (completed delta)
    if (perfPrevSubmitted !== null && perfPrevCompleted !== null && perfPrevAtMs !== null) {
      const submitDelta = submitted - perfPrevSubmitted;
      const completeDelta = completed - perfPrevCompleted;
      const dtMs = Math.max(250, nowMs - perfPrevAtMs);
      if (submitDelta >= 0) {
        epsRaw = (submitDelta * 1000) / dtMs;
      } else {
        epsRaw = perfEpsSmoothed;
      }
      if (completeDelta >= 0) {
        drainRaw = (completeDelta * 1000) / dtMs;
      } else {
        // Ignore occasional counter regression.
        drainRaw = perfDrainSmoothed;
      }
    }
    perfPrevSubmitted = submitted;
    perfPrevCompleted = completed;
    perfPrevAtMs = nowMs;

    // Keep a short rolling window and use trimmed mean for spike resistance.
    perfEpsHistory.push(Math.max(0, epsRaw));
    while (perfEpsHistory.length > 6) perfEpsHistory.shift();
    perfDrainHistory.push(Math.max(0, drainRaw));
    while (perfDrainHistory.length > 6) perfDrainHistory.shift();
    let epsStable = epsRaw;
    let drainStable = drainRaw;
    if (perfEpsHistory.length >= 5) {
      const sorted = [...perfEpsHistory].sort((a, b) => a - b);
      epsStable = avg(sorted.slice(1, -1));
    } else if (perfEpsHistory.length > 1) {
      epsStable = avg(perfEpsHistory);
    }
    if (perfDrainHistory.length >= 5) {
      const sorted = [...perfDrainHistory].sort((a, b) => a - b);
      drainStable = avg(sorted.slice(1, -1));
    } else if (perfDrainHistory.length > 1) {
      drainStable = avg(perfDrainHistory);
    }

    // Damp very large transient spikes.
    if (perfEpsSmoothed > 0 && epsStable > (perfEpsSmoothed * 1.7 + 90)) {
      epsStable = (perfEpsSmoothed * 1.7) + 90;
    }
    if (perfDrainSmoothed > 0 && drainStable > (perfDrainSmoothed * 1.7 + 90)) {
      drainStable = (perfDrainSmoothed * 1.7) + 90;
    }
    if (outstanding === 0 && epsStable < 1) {
      // Fast decay to zero once the queue is idle.
      perfEpsSmoothed *= 0.3;
      if (perfEpsSmoothed < 0.2) perfEpsSmoothed = 0;
    } else {
      const blended = perfEpsSmoothed > 0 ? ((perfEpsSmoothed * 0.55) + (epsStable * 0.45)) : epsStable;
      // Limit per-tick movement to keep gauge readable.
      const stepMax = 70;
      if (perfEpsSmoothed > 0) {
        const delta = blended - perfEpsSmoothed;
        if (delta > stepMax) {
          perfEpsSmoothed += stepMax;
        } else if (delta < -stepMax) {
          perfEpsSmoothed -= stepMax;
        } else {
          perfEpsSmoothed = blended;
        }
      } else {
        perfEpsSmoothed = blended;
      }
    }
    if (outstanding === 0 && drainStable < 1) {
      perfDrainSmoothed *= 0.45;
      if (perfDrainSmoothed < 0.2) perfDrainSmoothed = 0;
    } else {
      perfDrainSmoothed = perfDrainSmoothed > 0
        ? ((perfDrainSmoothed * 0.65) + (drainStable * 0.35))
        : drainStable;
    }
    const epsDisplay = Number.isFinite(perfEpsSmoothed) ? perfEpsSmoothed : 0;
    const drainDisplay = Number.isFinite(perfDrainSmoothed) ? perfDrainSmoothed : 0;
    if (fields.perfEps) fields.perfEps.textContent = epsDisplay.toFixed(1);
    if (fields.perfDrainRate) fields.perfDrainRate.textContent = drainDisplay.toFixed(1);
    setPerfGauge(epsDisplay);
  }

  async function fetchPerf() {
    if (perfInflight || document.visibilityState === "hidden") return;
    perfInflight = true;
    try {
      const res = await fetch("/api/events/perf", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      renderPerf(data);
      touchDashletUpdated("perf");
    } catch (err) {
      console.warn("[dashboard] events perf fetch error", err);
    } finally {
      perfInflight = false;
    }
  }

  function stopPerfAutoRefresh() {
    if (!perfTimer) return;
    clearInterval(perfTimer);
    perfTimer = null;
  }

  function updatePerfAutoRefresh() {
    stopPerfAutoRefresh();
    if (!fields.perfAutoRefresh?.checked) return;
    perfTimer = setInterval(fetchPerf, 1000);
  }

  async function fetchSyncStatus() {
    if (lastEspConnected !== true) {
      setSyncNotConnected();
      touchDashletUpdated("esp");
      return;
    }
    try {
      const res = await fetch("/api/esplink/sync/status", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const rules = data?.rules || {};
      const hardware = data?.hardware || {};
      const lighting = data?.lighting || {};
      setSyncBadge(fields.syncRules, rules.inSync === true, rules.inSync ? "In Sync" : "Out of Sync");
      setSyncBadge(fields.syncHardware, hardware.inSync === true, hardware.inSync ? "In Sync" : "Out of Sync");
      setSyncBadge(fields.syncLighting, lighting.inSync === true, lighting.inSync ? "In Sync" : "Out of Sync");
      if (fields.syncRulesAt) {
        const rulesStamp = rules.lastSyncedAt || rules.esp?.uploadedAt;
        fields.syncRulesAt.textContent = rulesStamp ? `Last: ${formatSyncedAt(rulesStamp)}` : "";
      }
      if (fields.syncHardwareAt) {
        const hwStamp = hardware.lastSyncedAt || hardware.esp?.uploadedAt;
        fields.syncHardwareAt.textContent = hwStamp ? `Last: ${formatSyncedAt(hwStamp)}` : "";
      }
      if (fields.syncLightingAt) {
        const lightingStamp = lighting.lastSyncedAt || lighting.esp?.uploadedAt;
        fields.syncLightingAt.textContent = lightingStamp ? `Last: ${formatSyncedAt(lightingStamp)}` : "";
      }
      touchDashletUpdated("esp");
    } catch (e) {
      setSyncNotConnected();
      touchDashletUpdated("esp");
    }
  }

  function render(status) {
    const wifi = status?.wifi || {};
    const bridge = status?.bridge || {};
    const esp = status?.esp || {};
    const uptime = status?.uptime || {};
    const deps = status?.deps || [];

    if (fields.wifiIface) fields.wifiIface.textContent = wifi.interface || "—";
    if (fields.wifiSsid) fields.wifiSsid.textContent = wifi.ssid || "—";
    if (fields.wifiIp) fields.wifiIp.textContent = wifi.ip || "—";
    if (fields.wifiSignal) fields.wifiSignal.textContent = (wifi.signal_dbm || wifi.signal_dbm === 0) ? `${wifi.signal_dbm} dBm` : "—";
    setBadge(fields.wifiConnected, wifi.connected === true, wifi.connected ? "Yes" : "No");

    setBadge(fields.bridgeStatus, bridge.running === true, bridge.running ? "Running" : "Stopped");
    if (fields.bridgeVia) fields.bridgeVia.textContent = bridge.via || "—";
    if (fields.bridgePid) fields.bridgePid.textContent = bridge.pid || "—";

    if (fields.uptimeSince) {
      let formatted = uptime.since_pretty || "—";
      if (!uptime.since_pretty && uptime.since) {
        const d = new Date(uptime.since);
        if (!Number.isNaN(d.getTime())) {
          formatted = new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
            timeZone: "UTC",
          }).format(d).replace(",", "");
        } else {
          formatted = uptime.since;
        }
      }
      fields.uptimeSince.textContent = formatted;
    }
    if (fields.uptimeHuman) fields.uptimeHuman.textContent = uptime.human || "—";
    if (fields.uptimeSeconds) fields.uptimeSeconds.textContent = (uptime.seconds || uptime.seconds === 0) ? uptime.seconds : "—";

    const espConnected = esp.connected === true;
    lastEspConnected = espConnected;
    if (fields.espFw) fields.espFw.textContent = esp.firmware || "—";
    if (fields.espChip) fields.espChip.textContent = esp.chip || "—";
    if (fields.espTime) {
      let formatted = "—";
      if (esp.time) {
        const d = new Date(esp.time);
        if (!Number.isNaN(d.getTime())) {
          formatted = new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
            timeZone: "UTC",
          }).format(d).replace(",", "");
        } else {
          formatted = esp.time;
        }
      }
      fields.espTime.textContent = formatted;
    }
    if (fields.espTimeSync) setBadge(fields.espTimeSync, esp.time_in_sync === true, esp.time_in_sync ? "OK" : "No");
    if (fields.espConnected) setBadge(fields.espConnected, esp.connected === true, esp.connected ? "Yes" : "No");

    if (fields.depsList) {
      fields.depsList.innerHTML = "";
      if (!deps.length) {
        const li = document.createElement("li");
        li.className = "text-secondary";
        li.textContent = "No data";
        fields.depsList.appendChild(li);
      } else {
        deps.forEach((d) => {
          const li = document.createElement("li");
          li.className = "d-flex align-items-center justify-content-between py-1 border-bottom border-secondary-subtle";
          const left = document.createElement("div");
          left.textContent = d.name || "dependency";
          const right = document.createElement("div");
          right.className = "d-flex align-items-center gap-2";
          if (d.version) {
            const v = document.createElement("span");
            v.className = "text-secondary small";
            v.textContent = shortenVersion(d.version);
            v.title = d.version;
            right.appendChild(v);
          }
          const badge = document.createElement("span");
          badge.className = "badge";
          badge.classList.add(d.ok ? "bg-success" : "bg-danger");
          badge.textContent = d.ok ? "OK" : "Missing";
          right.appendChild(badge);
          li.appendChild(left);
          li.appendChild(right);
          fields.depsList.appendChild(li);
        });
      }
    }
  }

  function shortenVersion(value) {
    const raw = String(value || "").trim();
    if (!raw) return raw;
    const single = raw.split(/\s+/).slice(0, 5).join(" ");
    if (single.length <= 28) return single;
    return `${single.slice(0, 27)}...`;
  }

  async function fetchStatus() {
    if (inflight || document.visibilityState === "hidden") return scheduleNext();
    inflight = true;
    let nextDelay = pollDelay;
    try {
      const res = await fetch("/api/dashboard/status", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      render(data);
      touchDashletsUpdated(["wifi", "bridge", "uptime", "esp", "deps"]);
      fetchSyncStatus();
      fetchPerf();
      setLoading(false);
      if (data?.bridge?.running === true && data?.esp?.connected !== true) {
        if (!quickRetry) {
          quickRetry = true;
          nextDelay = 1000;
        }
      } else {
        quickRetry = false;
      }
    } catch (err) {
      console.warn("[dashboard] fetch error", err);
    } finally {
      inflight = false;
      scheduleNext(nextDelay);
    }
  }

  function scheduleNext(delay = pollDelay) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(fetchStatus, delay);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "hidden") {
      scheduleNext(0);
      fetchPerf();
      updatePerfAutoRefresh();
      return;
    }
    stopPerfAutoRefresh();
  });

  if (fields.perfAutoRefresh) {
    fields.perfAutoRefresh.checked = false;
    fields.perfAutoRefresh.addEventListener("change", () => {
      if (fields.perfAutoRefresh.checked) fetchPerf();
      updatePerfAutoRefresh();
    });
  }

  // kick off after load
  initDashletUpdatedUi();
  if (document.readyState === "complete") {
    loadCurrency();
    fetchPerf();
    fetchStatus();
  } else {
    window.addEventListener("load", () => {
      loadCurrency();
      fetchPerf();
      fetchStatus();
    }, { once: true });
  }
})();
