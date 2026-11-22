(function () {
  function formatCurrency(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "£0.00";
    return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(n);
  }

  function toNumber(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }

  function getCellText(row, idx) {
    const cell = row.cells[idx];
    if (!cell) return "";
    return String(cell.textContent || "").trim();
  }

  function buildFilterUi(table) {
    const existing = document.getElementById("component-table-controls");
    if (existing) return existing;

    const wrap = document.createElement("div");
    wrap.id = "component-table-controls";
    wrap.className = "component-table-controls";

    const label = document.createElement("label");
    label.setAttribute("for", "component-category-filter");
    label.className = "component-table-controls__label";
    label.textContent = "Filter category:";

    const select = document.createElement("select");
    select.id = "component-category-filter";
    select.className = "component-table-controls__select";

    wrap.appendChild(label);
    wrap.appendChild(select);

    const parent = table.parentNode;
    if (parent && parent.classList && parent.classList.contains("manual-table-wrap") && parent.parentNode) {
      parent.parentNode.insertBefore(wrap, parent);
    } else {
      parent.insertBefore(wrap, table);
    }
    return wrap;
  }

  function refresh() {
    const root = document.getElementById("docs-article") || document;
    const sourceTable = root.querySelector("table.js-component-cost-table")
      || root.querySelector("#component-cost-table");
    if (!sourceTable) return;

    const tbody = sourceTable.tBodies[0];
    if (!tbody) return;

    if (!sourceTable._componentRows) {
      sourceTable._componentRows = Array.from(tbody.rows);
      sourceTable._componentSort = { index: -1, dir: "asc" };
      sourceTable._componentFilter = "all";
    }

    const allRows = sourceTable._componentRows;
    const state = sourceTable._componentSort;

    const controls = buildFilterUi(sourceTable);
    const filterSelect = controls.querySelector("#component-category-filter");

    const categories = Array.from(new Set(allRows.map((row) => getCellText(row, 1)).filter(Boolean))).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base" })
    );

    if (filterSelect && !filterSelect._componentInit) {
      filterSelect.innerHTML = [
        '<option value="all">All categories</option>',
        ...categories.map((c) => `<option value="${c.replace(/"/g, "&quot;")}">${c}</option>`),
      ].join("");
      filterSelect.value = sourceTable._componentFilter || "all";
      filterSelect.addEventListener("change", () => {
        sourceTable._componentFilter = filterSelect.value || "all";
        renderRows();
      });
      filterSelect._componentInit = true;
    }

    const headers = Array.from(sourceTable.tHead ? sourceTable.tHead.rows[0].cells : []);
    headers.forEach((th, index) => {
      if (th._componentSortInit) return;
      th.style.cursor = "pointer";
      th.title = "Sort";
      th.addEventListener("click", () => {
        if (state.index === index) {
          state.dir = state.dir === "asc" ? "desc" : "asc";
        } else {
          state.index = index;
          state.dir = "asc";
        }
        renderRows();
      });
      th._componentSortInit = true;
    });

    function filteredRows() {
      const selected = sourceTable._componentFilter || "all";
      if (selected === "all") return allRows.slice();
      return allRows.filter((row) => getCellText(row, 1) === selected);
    }

    function sortedRows(rows) {
      if (state.index < 0) return rows;
      const idx = state.index;
      const dir = state.dir === "desc" ? -1 : 1;
      return rows.slice().sort((a, b) => {
        if (idx === 3) {
          const av = toNumber(a.cells[3]?.getAttribute("data-cost"));
          const bv = toNumber(b.cells[3]?.getAttribute("data-cost"));
          return (av - bv) * dir;
        }
        const at = getCellText(a, idx);
        const bt = getCellText(b, idx);
        return at.localeCompare(bt, undefined, { numeric: true, sensitivity: "base" }) * dir;
      });
    }

    function updateHeaderIndicators() {
      headers.forEach((th, idx) => {
        const base = th.textContent.replace(/\s*[▲▼]$/, "");
        if (idx === state.index) {
          th.textContent = `${base} ${state.dir === "asc" ? "▲" : "▼"}`;
        } else {
          th.textContent = base;
        }
      });
    }

    function updateSummaries(rows) {
      let totalCost = 0;
      const byCategory = new Map();

      rows.forEach((row) => {
        const category = getCellText(row, 1) || "Uncategorised";
        const cost = toNumber(row.cells[3]?.getAttribute("data-cost"));
        totalCost += cost;
        const current = byCategory.get(category) || { count: 0, total: 0 };
        current.count += 1;
        current.total += cost;
        byCategory.set(category, current);
      });

      const totalLabelEl = root.querySelector("#project-total-label");
      const totalItemsEl = root.querySelector("#project-total-items");
      const totalCostEl = root.querySelector("#project-total-cost");
      if (totalLabelEl) {
        totalLabelEl.textContent = (sourceTable._componentFilter && sourceTable._componentFilter !== "all")
          ? "Filtered Project Cost"
          : "Total Project Cost";
      }
      if (totalItemsEl) totalItemsEl.textContent = String(rows.length);
      if (totalCostEl) totalCostEl.textContent = formatCurrency(totalCost);

      const breakdownBody = root.querySelector("#project-cost-breakdown-body");
      if (!breakdownBody) return;

      const ordered = Array.from(byCategory.entries()).sort((a, b) => b[1].total - a[1].total);
      breakdownBody.innerHTML = ordered.map(([category, data]) => {
        return [
          "<tr>",
          `<td>${category}</td>`,
          `<td>${data.count}</td>`,
          `<td>${formatCurrency(data.total)}</td>`,
          "</tr>",
        ].join("");
      }).join("");
    }

    function renderRows() {
      const rows = sortedRows(filteredRows());
      tbody.innerHTML = "";
      rows.forEach((row) => tbody.appendChild(row));
      updateHeaderIndicators();
      updateSummaries(rows);
    }

    renderRows();
  }

  document.addEventListener("docs:article-rendered", refresh);
  window.addEventListener("hashchange", () => {
    window.setTimeout(refresh, 0);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, { once: true });
  } else {
    refresh();
  }
})();
