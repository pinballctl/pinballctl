(() => {
  const tab = document.getElementById("hardware-test-tab");
  const pane = document.getElementById("hardware-test-pane");
  const mappingTab = document.getElementById("hardware-mapping-tab");
  if (!tab || !pane || !mappingTab) return;

  const testTabPreference = "pinballctl.hardware.test-tab";

  const tbody = document.getElementById("hardware-test-devices");
  const status = document.getElementById("hardware-test-status");
  const liveStatus = "Monitoring live. Rules and lighting playback on the ESP are paused during the test.";
  const labels = {on: "On", off: "Off", hold: "Hold", flash: "Flash", pulse: "Pulse", text: "Show text"};
  const messages = {
    game_active: "Hardware testing is available when the game is idle.",
    mapping_required: "Sync the hardware mapping to the ESP first.",
    mapping_too_large: "The applied mapping is too large to load for testing.",
    test_unavailable: "ESP unavailable.",
    test_no_response: "ESP connected, but Hardware Test received no reply. Check that the ESP is running firmware with Hardware Test support.",
    controller_busy: "The ESP is busy.",
    test_in_use: "Another Hardware Test session is active.",
    test_ended: "The test session ended.",
    action_blocked: "The driver blocked this test. Check the device mapping and coil safety status.",
  };
  const retryable = new Set(["test_unavailable", "test_no_response", "test_ended", "test_in_use", "controller_busy", "game_active", "mapping_required"]);
  let current = null;
  let reconnectTimer;
  let displayedDevices = [];

  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function showStatus(message) {
    if (status.textContent !== message) status.textContent = message;
  }

  async function command(session, op, params = {}) {
    const result = await fetch(pane.dataset.testUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session: session.id, op, ...params}),
    });
    return result.json();
  }

  function stop() {
    clearTimeout(reconnectTimer);
    const session = current;
    if (!session) return;
    current = null;
    clearTimeout(session.timer);
    showDevices(session, displayedDevices, false);
    if (!session.live) return;
    const body = new Blob([JSON.stringify({session: session.id, op: "stop"})], {type: "application/json"});
    if (!navigator.sendBeacon?.(pane.dataset.testUrl, body)) {
      void fetch(pane.dataset.testUrl, {method: "POST", body, keepalive: true}).catch(() => {});
    }
  }

  function updateRow(row, state) {
    let label = "Unknown";
    if (typeof state.high === "boolean") {
      if (row.dot.dataset.high !== String(state.high)) row.dot.dataset.high = String(state.high);
      label = state.high ? "High" : "Low";
    } else {
      if ("high" in row.dot.dataset) delete row.dot.dataset.high;
      if ("online" in state) {
        label = state.online ? [state.x, state.y, state.z].map(value => Number(value).toFixed(2)).join(", ") + " g" : "Offline";
      } else if ("testing" in state) {
        label = state.testing ? "Testing" : "Idle";
      }
    }
    if (row.label.textContent !== label) row.label.textContent = label;
    if (row.activity !== null && state.activity > row.activity) {
      row.dot.classList.add("hardware-test-hit");
      clearTimeout(row.flash);
      row.flash = setTimeout(() => row.dot.classList.remove("hardware-test-hit"), 250);
    }
    if (row.activity !== state.activity) {
      row.activity = state.activity;
      if (row.showCount) row.count.textContent = `${state.activity} ${state.activity === 1 ? "hit" : "hits"}`;
    }
  }

  function sendAction(session, target, action) {
    session.pending = session.pending.then(async () => {
      if (current !== session) return;
      try {
        const result = await command(session, "action", {target, action});
        if (current !== session) return;
        if (["test_unavailable", "test_no_response", "test_ended"].includes(result.error)) return fail(session, result.error);
        showStatus(result.ok ? liveStatus : messages[result.error] || "The test action failed.");
      } catch (_) {
        fail(session, "test_unavailable");
      }
    });
  }

  function bindHold(button, session, target) {
    function begin() {
      if (current !== session || session.held) return;
      session.held = target;
      sendAction(session, target, "hold");
    }
    function end() {
      if (session.held !== target) return;
      session.held = "";
      sendAction(session, target, "release");
    }
    button.classList.add("hardware-test-hold");
    button.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      button.setPointerCapture(event.pointerId);
      begin();
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture", "blur"]) {
      button.addEventListener(event, end);
    }
    const isHoldKey = event => event.key === " " || event.key === "Enter";
    button.addEventListener("keydown", event => {
      if (!isHoldKey(event)) return;
      event.preventDefault();
      if (!event.repeat) begin();
    });
    button.addEventListener("keyup", event => {
      if (!isHoldKey(event)) return;
      event.preventDefault();
      end();
    });
  }

  function renderDevice(session, device, live) {
    const tr = document.createElement("tr");
    const stateCell = element("td", "hardware-test-state");
    const line = element("div", "d-flex align-items-center gap-1 gap-md-2");
    const dot = element("span", "hardware-test-dot");
    dot.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    line.append(dot, label);
    const count = element("div", "small text-secondary");
    stateCell.append(line, count);
    const name = element("th", "", device.name);
    name.scope = "row";
    if (Number.isInteger(device.pin)) name.append(element("div", "small text-secondary fw-normal", `GPIO ${device.pin}`));
    name.append(element("div", "small text-secondary fw-normal d-md-none", `${device.function} · ${device.driver || "Default"}`));
    const driver = element("td", "d-none d-md-table-cell", device.function);
    driver.append(element("div", "small text-secondary", device.driver || "Default"));
    const controls = document.createElement("td");
    const buttons = element("div", "d-flex flex-wrap gap-2");
    for (const action of device.actions) {
      if (!labels[action]) continue;
      const button = element("button", "btn btn-sm btn-outline-secondary", labels[action]);
      button.type = "button";
      button.disabled = !live;
      button.setAttribute("aria-label", `${labels[action]} ${device.name}`);
      if (live && action === "hold") bindHold(button, session, device.id);
      if (live && action !== "hold") button.addEventListener("click", () => sendAction(session, device.id, action));
      buttons.append(button);
    }
    if (!buttons.childElementCount) {
      buttons.append(element("span", "text-secondary small",
        ["Button", "Switch"].includes(device.function) ? "Operate the switch" :
        device.function === "Accelerometer" ? "Move or tap the sensor" : "Unavailable"));
    }
    controls.append(buttons);
    tr.append(stateCell, name, driver, controls);
    tbody.append(tr);
    const row = {dot, label, count, activity: null, showCount: ["Button", "Switch"].includes(device.function)};
    if (live) updateRow(row, device);
    else row.label.textContent = "Unavailable";
    return row;
  }

  function showDevices(session, devices, live) {
    tbody.replaceChildren();
    displayedDevices = devices;
    session.rows = devices.map(device => renderDevice(session, device, live));
  }

  function fail(session, code, devices) {
    if (current !== session) return;
    if (devices?.length) displayedDevices = devices;
    stop();
    const message = messages[code] || "The hardware test request failed.";
    const willRetry = retryable.has(code);
    showStatus(willRetry ? `${message} Retrying automatically…` : message);
    if (willRetry) reconnectTimer = setTimeout(start, 2000);
  }

  function poll(session) {
    session.timer = setTimeout(() => {
      session.pending = session.pending.then(async () => {
        if (current !== session) return;
        try {
          const result = await command(session, "poll", {held: session.held});
          if (current !== session) return;
          if (!result.ok) return fail(session, result.error);
          result.state.forEach((state, index) => updateRow(session.rows[index], state));
          poll(session);
        } catch (_) {
          fail(session, "test_unavailable");
        }
      });
    }, 200);
  }

  async function start() {
    if (current || document.hidden || !tab.classList.contains("active")) return;
    const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, "0")).join("");
    clearTimeout(reconnectTimer);
    const session = {id, held: "", pending: Promise.resolve(), rows: [], live: false};
    current = session;
    if (!status.textContent || status.textContent === liveStatus) showStatus("Connecting to the ESP…");
    try {
      const result = await command(session, "start");
      if (current !== session) {
        if (result.ok) void command(session, "stop").catch(() => {});
        return;
      }
      if (!result.ok) return fail(session, result.error, result.devices);
      session.live = true;
      showDevices(session, result.devices, true);
      showStatus(liveStatus);
      poll(session);
    } catch (_) {
      fail(session, "test_unavailable");
    }
  }

  tab.addEventListener("shown.bs.tab", () => {
    try { sessionStorage.setItem(testTabPreference, "selected"); } catch (_) {}
    start();
  });
  mappingTab.addEventListener("shown.bs.tab", () => {
    try { sessionStorage.removeItem(testTabPreference); } catch (_) {}
  });
  tab.addEventListener("hide.bs.tab", stop);
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", start);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });
  let restoreTestTab = false;
  try { restoreTestTab = sessionStorage.getItem(testTabPreference) === "selected"; } catch (_) {}
  if (restoreTestTab) window.bootstrap?.Tab.getOrCreateInstance(tab).show();
})();
