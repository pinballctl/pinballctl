(() => {
  const get = name => document.getElementById(`rules-state-${name}`);
  const drawer = get("drawer");
  const form = get("form");
  const kind = get("kind"), key = get("name"), scope = get("scope");
  const clock = get("clock"), duration = get("duration"), message = get("message");
  const scopes = {global: "Global", game: "Per game", player: "Per player"};

  function refreshFields() {
    const timer = kind.value === "timer";
    get("timer").hidden = !timer;
    duration.required = timer;
    duration.disabled = clock.disabled = !timer;
    for (const option of clock.options) {
      option.disabled = scope.value === "player" && option.value === "wall";
    }
    if (clock.selectedOptions[0]?.disabled) clock.value = scope.value === "player" ? "play" : "wall";
  }

  function edit(type, name, config) {
    kind.value = type;
    key.value = name;
    kind.disabled = key.readOnly = true;
    scope.value = config.scope;
    clock.value = config.clock || "wall";
    duration.value = config.durationMs || 30000;
    get("form-title").textContent = `Edit ${name}`;
    message.textContent = "";
    refreshFields();
    scope.focus();
  }

  async function load() {
    const response = await fetch("/api/rules/state-definitions", {cache: "no-store"});
    if (!response.ok) throw new Error("Could not load Rules state definitions.");
    const {definitions} = await response.json();
    const rows = get("rows");
    rows.replaceChildren();
    for (const [type, names] of Object.entries(definitions)) {
      for (const [name, config] of Object.entries(names).sort(([a], [b]) => a.localeCompare(b))) {
        const row = rows.insertRow();
        for (const value of [name, type, scopes[config.scope]]) row.insertCell().textContent = value;
        const cell = row.insertCell();
        cell.className = "text-end";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-sm btn-outline-secondary";
        button.title = `Edit ${name}`;
        button.setAttribute("aria-label", button.title);
        button.innerHTML = '<i class="fa fa-pen" aria-hidden="true"></i>';
        button.addEventListener("click", () => edit(type, name, config));
        cell.append(button);
      }
    }
    if (!rows.rows.length) {
      const cell = rows.insertRow().insertCell();
      cell.colSpan = 4;
      cell.textContent = "No named state yet.";
    }
  }

  kind.addEventListener("change", refreshFields);
  scope.addEventListener("change", refreshFields);
  key.addEventListener("input", () => { key.value = key.value.toUpperCase(); });
  drawer.addEventListener("show.bs.offcanvas", () => load().catch(error => { message.textContent = error.message; }));
  form.addEventListener("reset", () => {
    kind.disabled = key.readOnly = false;
    get("form-title").textContent = "Add state or timer";
    message.textContent = "";
    queueMicrotask(refreshFields);
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    const data = {scope: scope.value};
    if (kind.value === "timer") Object.assign(data, {durationMs: duration.valueAsNumber, clock: clock.value});
    try {
      const response = await fetch(`/api/rules/state-definitions/${kind.value}/${encodeURIComponent(key.value)}`, {
        method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save the definition.");
      await load();
      document.dispatchEvent(new Event("rules-definitions-updated"));
      message.textContent = "Definition saved.";
    } catch (error) {
      message.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });
  refreshFields();
})();
