(() => {
  const rows = document.getElementById("liveview-rules-state-rows");
  const tab = document.getElementById("liveview-rules-state-tab");
  const scopes = {global: "Global", game: "Per game", player: "Per player"};
  let refresh;
  let polling;

  function message(text) {
    rows.replaceChildren();
    const cell = rows.insertRow().insertCell();
    cell.colSpan = 5;
    cell.textContent = text;
  }

  async function load(signal) {
    try {
      const response = await fetch("/api/rules/runtime-state", {cache: "no-store", signal});
      if (!response.ok) throw new Error("Could not load Rules state.");
      const {values} = await response.json();
      if (signal.aborted) return;
      if (!values.length) return message("No Rules values to show.");
      rows.replaceChildren();
      for (const item of values) {
        const row = rows.insertRow();
        const value = item.value === null ? "Unavailable" :
          item.kind === "timer" ? `${(item.value.remainingMs / 1000).toFixed(1)} s · ${item.value.status}` :
            String(item.value);
        for (const cell of [item.key, item.kind, scopes[item.scope], item.player || "—", value]) {
          row.insertCell().textContent = cell;
        }
      }
    } catch (error) {
      if (!signal.aborted) message(error.message);
    } finally {
      if (!signal.aborted) refresh = setTimeout(() => load(signal), 500);
    }
  }

  function start() {
    if (polling) return;
    polling = new AbortController();
    load(polling.signal);
  }

  function stop() {
    polling?.abort();
    polling = null;
    clearTimeout(refresh);
  }

  tab.addEventListener("shown.bs.tab", start);
  tab.addEventListener("hide.bs.tab", stop);
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", (evt) => {
    if (evt.persisted && tab.classList.contains("active")) start();
  });
  if (tab.classList.contains("active")) start();
})();
