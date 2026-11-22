(function () {
  const badge = document.querySelector("[data-coil-safety]");
  if (!badge) return;
  const detail = document.querySelector("[data-coil-fault]");

  function render(status) {
    const fault = typeof status?.fault === "string" && status.fault !== "none" ? status.fault : "";
    let label = "Unknown";
    let style = "bg-secondary";
    if (fault) {
      label = "Fault";
      style = "bg-danger";
    } else if (status?.armed === true) {
      label = "Armed";
      style = "bg-warning text-dark";
    } else if (status?.armed === false) {
      label = "Disarmed";
    }
    badge.className = `badge ${style}`;
    badge.textContent = label;
    if (detail) detail.textContent = fault.replaceAll("_", " ");
  }

  let timer;
  let pending = false;
  async function refresh() {
    if (document.hidden || pending) return;
    pending = true;
    try {
      const response = await fetch(badge.dataset.coilSafety, {
        cache: "no-store",
        signal: AbortSignal.timeout(1500),
      });
      render(response.ok ? await response.json() : null);
    } catch {
      render(null);
    } finally {
      pending = false;
      if (!document.hidden) timer = setTimeout(refresh, 2000);
    }
  }

  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    render(null);
    if (!document.hidden) refresh();
  });
  refresh();
})();
