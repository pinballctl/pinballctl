(() => {
  const rows = document.getElementById("liveview-rules-state-rows");
  const tab = document.getElementById("liveview-rules-state-tab");
  const scopes = {global: "Global", game: "Per game", player: "Per player"};
  const storageKey = "pinballctl.liveview.tab";
  let refresh;

  function message(text) {
    rows.replaceChildren();
    const cell = rows.insertRow().insertCell();
    cell.colSpan = 5;
    cell.textContent = text;
  }

  async function load() {
    try {
      const response = await fetch("/api/rules/runtime-state", {cache: "no-store"});
      if (!response.ok) throw new Error("Could not load Rules state.");
      const {values} = await response.json();
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
      message(error.message);
    } finally {
      if (tab.classList.contains("active")) refresh = setTimeout(load, 500);
    }
  }

  tab.addEventListener("shown.bs.tab", () => {
    localStorage.setItem(storageKey, "rules-state");
    load();
  });
  tab.addEventListener("hidden.bs.tab", () => {
    localStorage.removeItem(storageKey);
    clearTimeout(refresh);
  });
  if (localStorage.getItem(storageKey) === "rules-state") bootstrap.Tab.getOrCreateInstance(tab).show();
})();
