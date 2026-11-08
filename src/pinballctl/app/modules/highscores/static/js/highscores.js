(() => {
  const $ = id => document.getElementById(`highscores-${id}`);
  const tabs = [...document.querySelectorAll("[data-board]")];
  const settingsForm = $("settings-form");
  const editForm = $("edit-form");
  let category = localStorage.getItem("highscores-board");
  if (!tabs.some(tab => tab.dataset.board === category)) category = "all-time";
  let page = 1;
  let loadId = 0;
  let editedEntry;

  async function request(path, method = "GET", body) {
    const response = await fetch(`/api/highscores/${path}`, {
      method,
      headers: body ? {"Content-Type": "application/json"} : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "High Scores could not be updated.");
    return result;
  }

  function showError(element, message = "") {
    element.textContent = message;
    element.hidden = !message;
  }

  function action(label, icon, handler, confirm) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn btn-sm ${confirm ? "btn-outline-danger" : "btn-outline-secondary"}`;
    button.title = label;
    button.setAttribute("aria-label", label);
    if (confirm) {
      button.dataset.confirm = confirm;
      button.dataset.confirmLabel = "Remove entry";
    }
    const symbol = document.createElement("i");
    symbol.className = `fa fa-${icon}`;
    symbol.setAttribute("aria-hidden", "true");
    button.append(symbol);
    button.addEventListener("click", handler);
    return button;
  }

  function draw(scores) {
    $("rows").replaceChildren();
    if (!scores.length) {
      const cell = $("rows").insertRow().insertCell();
      cell.colSpan = 6;
      cell.className = "text-secondary";
      cell.textContent = "No scores for this period.";
      return;
    }
    for (const entry of scores) {
      const row = $("rows").insertRow();
      for (const value of [entry.rank, entry.initials, entry.name, entry.score.toLocaleString(), new Date(entry.endedAtMs).toLocaleString()]) {
        row.insertCell().textContent = value;
      }
      row.cells[3].className = "text-end";
      const cell = row.insertCell();
      cell.className = "text-end text-nowrap";
      const edit = action("Edit entry", "pen", () => {
        editedEntry = entry;
        $("initials").value = entry.initials === "---" ? "" : entry.initials;
        $("name").value = entry.name;
        $("score").value = entry.score;
        showError(editForm.querySelector("[data-form-error]"));
        bootstrap.Offcanvas.getOrCreateInstance($("edit")).show();
      });
      edit.classList.add("me-2");
      cell.append(edit, action("Remove entry", "trash", () => mutate("entry", "DELETE", {
        gameId: entry.gameId, playerId: entry.playerId,
      }), "Remove this score from every leaderboard?"));
    }
  }

  async function load() {
    const id = ++loadId;
    for (const tab of tabs) {
      const selected = tab.dataset.board === category;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-pressed", selected);
    }
    try {
      const result = await request(`?category=${category}&page=${page}`);
      if (id !== loadId) return;
      if (!result.scores.length && page > 1) {
        page--;
        return load();
      }
      draw(result.scores);
      $("page").textContent = `Page ${page}`;
      $("previous").disabled = page === 1;
      $("next").disabled = !result.more;
      $("display-rows").value = result.displayRows;
    } catch (error) {
      if (id === loadId) showError($("message"), error.message);
    }
  }

  async function mutate(path, method, body, form) {
    const errorBox = form?.querySelector("[data-form-error]") || $("message");
    showError(errorBox);
    const submit = form?.querySelector("button[type=submit]");
    if (submit) submit.disabled = true;
    try {
      await request(path, method, body);
      if (form) bootstrap.Offcanvas.getInstance(form.closest(".offcanvas")).hide();
      if (path === "reset") page = 1;
      await load();
    } catch (error) {
      showError(errorBox, error.message);
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  for (const tab of tabs) tab.addEventListener("click", () => {
    category = tab.dataset.board;
    localStorage.setItem("highscores-board", category);
    page = 1;
    showError($("message"));
    load();
  });
  $("previous").addEventListener("click", () => { page--; load(); });
  $("next").addEventListener("click", () => { page++; load(); });
  $("reset").addEventListener("click", () => mutate("reset", "POST", {confirm: true}));
  settingsForm.addEventListener("submit", event => {
    event.preventDefault();
    mutate("settings", "PUT", {displayRows: $("display-rows").valueAsNumber}, settingsForm);
  });
  editForm.addEventListener("submit", event => {
    event.preventDefault();
    mutate("entry", "PATCH", {
      gameId: editedEntry.gameId, playerId: editedEntry.playerId, name: $("name").value,
      initials: $("initials").value, score: $("score").valueAsNumber,
    }, editForm);
  });
  load();
})();
