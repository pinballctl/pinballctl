(() => {
  const root = document.getElementById("accelerometer-page");
  if (!root) return;

  const elRows = root.querySelector("[data-accel-rows]");
  const elNudge = root.querySelector("[data-accel-nudge-count]");
  const elLift = root.querySelector("[data-accel-lift-count]");
  const elLevelText = root.querySelector("[data-accel-level-text]");
  const elPitch = root.querySelector("[data-accel-pitch]");
  const elRoll = root.querySelector("[data-accel-roll]");
  const elLevelStatus = root.querySelector("[data-accel-level-status]");
  const elPitchBubble = root.querySelector("[data-accel-pitch-bubble]");
  const elRollBubble = root.querySelector("[data-accel-roll-bubble]");
  const btnSave = root.querySelector("[data-accel-save]");
  const indNudge = root.querySelector('[data-indicator="nudge"]');
  const indLift = root.querySelector('[data-indicator="lift"]');

  const state = {
    pollTimer: null,
    prevBySource: new Map(),
    smoothedPitch: 0,
    smoothedRoll: 0,
    smoothingReady: false,
  };

  function esc(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function api(path, opts) {
    const res = await fetch(`/api/accelerometer${path}`, opts || {});
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function getConfirmModalParts() {
    const modalEl = document.getElementById("generic-confirm-modal");
    if (!modalEl || typeof bootstrap === "undefined" || !bootstrap.Modal) return null;
    const titleEl = modalEl.querySelector(".modal-title");
    const bodyEl = modalEl.querySelector(".modal-body");
    const cancelBtn = modalEl.querySelector('[data-bs-dismiss="modal"]');
    const confirmBtn = modalEl.querySelector("[data-confirm-accept]");
    if (!titleEl || !bodyEl || !cancelBtn || !confirmBtn) return null;
    return { modalEl, titleEl, bodyEl, cancelBtn, confirmBtn, modal: bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: "static" }) };
  }

  function askConfirm(message, opts = {}) {
    const parts = getConfirmModalParts();
    if (!parts) return Promise.resolve(window.confirm(message));
    const { modalEl, titleEl, bodyEl, cancelBtn, confirmBtn, modal } = parts;
    titleEl.textContent = opts.title || "Confirm";
    bodyEl.textContent = message;
    cancelBtn.classList.remove("d-none");
    cancelBtn.textContent = opts.cancelLabel || "Cancel";
    confirmBtn.className = `btn ${opts.confirmClass || "btn-danger"}`;
    confirmBtn.textContent = opts.confirmLabel || "Confirm";
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

  function showMessage(message, opts = {}) {
    const parts = getConfirmModalParts();
    if (!parts) {
      window.alert(message);
      return Promise.resolve();
    }
    const { modalEl, titleEl, bodyEl, cancelBtn, confirmBtn, modal } = parts;
    titleEl.textContent = opts.title || "Accelerometer";
    bodyEl.textContent = message;
    cancelBtn.classList.add("d-none");
    confirmBtn.className = `btn ${opts.confirmClass || "btn-primary"}`;
    confirmBtn.textContent = opts.confirmLabel || "OK";
    return new Promise((resolve) => {
      const cleanup = () => {
        confirmBtn.removeEventListener("click", onConfirm);
        modalEl.removeEventListener("hidden.bs.modal", onHidden);
      };
      const onConfirm = () => {
        cleanup();
        resolve();
        modal.hide();
      };
      const onHidden = () => {
        cleanup();
        resolve();
      };
      confirmBtn.addEventListener("click", onConfirm, { once: true });
      modalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
      modal.show();
    });
  }

  function pulse(el) {
    if (!el) return;
    el.classList.add("flash");
    window.setTimeout(() => el.classList.remove("flash"), 220);
  }

  function fmtNum(v, p = 3) {
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(p) : "0.000";
  }

  function bubbleLeftPercent(deg) {
    const maxDeg = 6.0;
    const clamped = Math.max(-maxDeg, Math.min(maxDeg, Number(deg) || 0));
    return 50 + ((clamped / maxDeg) * 44);
  }

  function adaptiveSmooth(prev, next, lowAlpha, highAlpha, triggerDeg) {
    const delta = Math.abs((Number(next) || 0) - (Number(prev) || 0));
    const alpha = delta >= triggerDeg ? highAlpha : lowAlpha;
    return (prev * (1 - alpha)) + (next * alpha);
  }

  function quantiseDeg(value, step = 0.1) {
    const n = Number(value) || 0;
    const q = Math.round(n / step) * step;
    return Object.is(q, -0) ? 0 : q;
  }

  function render(runtime) {
    const bridge = runtime?.bridge || {};
    const connected = !!bridge.connected;
    const derived = runtime?.derived || {};
    const summary = derived.summary || {};
    const sensors = Array.isArray(derived.sensors) ? derived.sensors : [];
    const nudgeCount = Number(summary.tiltCount || 0);
    const liftCount = Number(summary.liftCount || 0);
    if (elNudge) elNudge.textContent = String(nudgeCount);
    if (elLift) elLift.textContent = String(liftCount);

    let avgPitch = 0;
    let avgRoll = 0;
    if (sensors.length) {
      avgPitch = sensors.reduce((a, s) => a + Number(s.levelPitchDeg || 0), 0) / sensors.length;
      avgRoll = sensors.reduce((a, s) => a + Number(s.levelRollDeg || 0), 0) / sensors.length;
    }
    if (!state.smoothingReady) {
      state.smoothedPitch = avgPitch;
      state.smoothedRoll = avgRoll;
      state.smoothingReady = true;
    } else {
      state.smoothedPitch = adaptiveSmooth(state.smoothedPitch, avgPitch, 0.28, 0.62, 0.35);
      state.smoothedRoll = adaptiveSmooth(state.smoothedRoll, avgRoll, 0.22, 0.56, 0.35);
    }
    const pitchDeadbandDeg = 0.08;
    const rollDeadbandDeg = 0.14;
    const shownPitchRaw = Math.abs(state.smoothedPitch) < pitchDeadbandDeg ? 0 : state.smoothedPitch;
    const shownRollRaw = Math.abs(state.smoothedRoll) < rollDeadbandDeg ? 0 : state.smoothedRoll;
    const shownPitch = quantiseDeg(shownPitchRaw, 1.0);
    const shownRoll = quantiseDeg(shownRollRaw, 1.0);

    if (elPitch) elPitch.textContent = `${shownPitch.toFixed(0)}°`;
    if (elRoll) elRoll.textContent = `${shownRoll.toFixed(0)}°`;
    const levelWarning = !!summary.levelWarning;
    if (elLevelStatus) {
      elLevelStatus.textContent = levelWarning ? "Not level" : "Level";
      elLevelStatus.dataset.accelLevelStatus = levelWarning ? "warn" : "ok";
    }
    if (elLevelText) {
      elLevelText.textContent = connected
        ? (levelWarning ? "Table appears out of level calibration tolerance." : "Table is level within tolerance.")
        : "ESP is offline. Connect ESP to read live metrics.";
    }
    if (elPitchBubble) elPitchBubble.style.left = `${bubbleLeftPercent(shownPitch).toFixed(2)}%`;
    if (elRollBubble) elRollBubble.style.left = `${bubbleLeftPercent(shownRoll).toFixed(2)}%`;

    const newBySource = new Map();
    sensors.forEach((s) => {
      const source = String(s.source || "");
      newBySource.set(source, {
        tiltCount: Number(s.tiltCount || 0),
        liftCount: Number(s.liftCount || 0),
      });
      const prev = state.prevBySource.get(source);
      if (prev) {
        if (Number(s.tiltCount || 0) > prev.tiltCount) pulse(indNudge);
        if (Number(s.liftCount || 0) > prev.liftCount) pulse(indLift);
      }
    });
    state.prevBySource = newBySource;

    if (!elRows) return;
    if (!sensors.length) {
      elRows.innerHTML = '<tr><td colspan="11" class="text-secondary">No accelerometer sensors configured.</td></tr>';
      return;
    }
    elRows.innerHTML = sensors.map((s) => `
      <tr>
        <td>${esc(s.source || "")}</td>
        <td>${esc(s.componentId || "—")}</td>
        <td>${fmtNum(s.ax, 3)}</td>
        <td>${fmtNum(s.ay, 3)}</td>
        <td>${fmtNum(s.az, 3)}</td>
        <td>${fmtNum(s.angleDeg, 2)}°</td>
        <td>${fmtNum(s.lastJoltG, 3)}g</td>
        <td>${s.lifted ? "Yes" : "No"}</td>
        <td>${Number(s.tiltCount || 0)}</td>
        <td>${Number(s.liftCount || 0)}</td>
        <td>${s.online ? "Yes" : "No"}</td>
      </tr>
    `).join("");
  }

  async function refresh() {
    try {
      const data = await api("/runtime");
      render(data);
      if (data.error && elLevelText) {
        elLevelText.textContent = `Runtime query issue: ${data.error}`;
      }
    } catch (err) {
      if (elLevelText) {
        elLevelText.textContent = `Accelerometer runtime unavailable: ${err.message}`;
      }
    }
  }

  async function saveCalibration() {
    const ok = await askConfirm(
      "Save current accelerometer readings as baseline and send updated config to the ESP?",
      {
        title: "Save Baseline",
        confirmLabel: "Save Baseline",
        confirmClass: "btn-success",
      }
    );
    if (!ok) return;
    if (btnSave) btnSave.disabled = true;
    try {
      const res = await api("/calibrate/save", { method: "POST" });
      await showMessage(
        `Saved ${res.saved || 0} baseline profile(s) and synced ${res.configCount || 0} config(s).`,
        { title: "Baseline Saved", confirmLabel: "Close", confirmClass: "btn-success" }
      );
      await refresh();
    } catch (err) {
      await showMessage(`Save baseline failed: ${err.message}`, {
        title: "Save Failed",
        confirmLabel: "Close",
        confirmClass: "btn-danger",
      });
    } finally {
      if (btnSave) btnSave.disabled = false;
    }
  }

  function start() {
    if (state.pollTimer) window.clearInterval(state.pollTimer);
    refresh();
    state.pollTimer = window.setInterval(refresh, 1000);
  }

  function stop() {
    if (state.pollTimer) window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  btnSave?.addEventListener("click", saveCalibration);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });
  start();
})();
