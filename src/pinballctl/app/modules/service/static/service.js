// Service log module UI logic
(function () {
  const root = document.getElementById("service-root");
  if (!root) return;

  const entryList = root.querySelector('[data-field="entry-list"]');
  const entryCount = root.querySelector('[data-field="entry-count"]');
  const filterType = root.querySelector('[data-field="filter-type"]');
  const filterFrom = root.querySelector('[data-field="filter-from"]');
  const filterTo = root.querySelector('[data-field="filter-to"]');
  const btnApply = root.querySelector('[data-action="apply-filters"]');
  const btnClear = root.querySelector('[data-action="clear-filters"]');
  const btnNew = root.querySelector('[data-action="new"]');

  const detailEmpty = root.querySelector('[data-field="detail-empty"]');
  const detailView = root.querySelector('[data-field="detail-view"]');
  const detailTitle = root.querySelector('[data-field="detail-title"]');
  const detailMeta = root.querySelector('[data-field="detail-meta"]');
  const detailType = root.querySelector('[data-field="detail-type"]');
  const detailDescription = root.querySelector('[data-field="detail-description"]');
  const detailParts = root.querySelector('[data-field="detail-parts"]');
  const detailOutcome = root.querySelector('[data-field="detail-outcome"]');
  const detailFollowup = root.querySelector('[data-field="detail-followup"]');
  const detailAttachments = root.querySelector('[data-field="detail-attachments"]');
  const btnEdit = root.querySelector('[data-action="edit-entry"]');

  const modalEl = document.getElementById("service-new-modal");
  const modal = modalEl && window.bootstrap?.Modal ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
  const formEngineer = root.querySelector('[data-field="form-engineer"]');
  const formType = root.querySelector('[data-field="form-type"]');
  const formTitle = root.querySelector('[data-field="form-title"]');
  const formDescription = root.querySelector('[data-field="form-description"]');
  const formParts = root.querySelector('[data-field="form-parts"]');
  const formOutcome = root.querySelector('[data-field="form-outcome"]');
  const formFollowup = root.querySelector('[data-field="form-followup"]');
  const formExistingAttachments = root.querySelector('[data-field="form-existing-attachments"]');
  const formAttachments = root.querySelector('[data-field="form-attachments"]');
  const formError = root.querySelector('[data-field="form-error"]');
  const btnSave = root.querySelector('[data-action="save-entry"]');
  const btnAddAttachment = root.querySelector('[data-action="add-attachment"]');

  let entries = [];
  let activeEntry = null;
  let editingEntryId = null;
  let recentEntryId = null;
  const maxAttachments = 5;
  const modalTitle = modalEl?.querySelector(".modal-title");

  function addAttachmentRow() {
    if (!formAttachments) return;
    const rows = formAttachments.querySelectorAll(".service-attachment-row");
    const existingCount = formExistingAttachments
      ? formExistingAttachments.querySelectorAll("[data-filename]").length
      : 0;
    if (rows.length + existingCount >= maxAttachments) return;
    const row = document.createElement("div");
    row.className = "service-attachment-row d-flex align-items-center gap-2 mb-2";
    const input = document.createElement("input");
    input.type = "file";
    input.className = "form-control";
    input.accept = ".png,.jpg,.jpeg,.pdf,.docx";
    input.dataset.role = "attachment";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1";
    remove.innerHTML = '<i class="fa fa-trash" aria-hidden="true"></i><span>Remove</span>';
    remove.addEventListener("click", () => row.remove());
    row.appendChild(input);
    row.appendChild(remove);
    formAttachments.appendChild(row);
  }

  function showDetail(entry) {
    if (!entry) return;
    activeEntry = entry;
    detailTitle.textContent = entry.title || "Untitled entry";
    detailMeta.textContent = `${entry.engineer || "Unknown"} · ${formatDate(entry.created_at)}`;
    detailType.textContent = entry.service_type || "SERVICE";
    detailType.classList.remove("bg-secondary", "bg-info", "bg-warning", "bg-danger");
    detailType.classList.add(typeBadge(entry.service_type));
    detailDescription.textContent = entry.description || "—";
    detailParts.textContent = entry.parts_replaced || "—";
    detailOutcome.textContent = entry.outcome || "—";
    detailFollowup.textContent = entry.follow_up || "—";
    detailAttachments.innerHTML = "";
    const attachments = Array.isArray(entry.attachments) ? entry.attachments : [];
    if (!attachments.length) {
      const li = document.createElement("li");
      li.className = "text-secondary";
      li.textContent = "None";
      detailAttachments.appendChild(li);
    } else {
      attachments.forEach((item) => {
        const label = item?.original || item?.label || item?.name || "";
        const li = document.createElement("li");
        if (item?.filename) {
          const a = document.createElement("a");
          a.href = `/api/service/attachment/${encodeURIComponent(item.filename)}`;
          a.textContent = label || "Attachment";
          a.target = "_blank";
          li.appendChild(a);
        } else {
          li.textContent = label || "Attachment";
        }
        detailAttachments.appendChild(li);
      });
    }
    detailEmpty.classList.add("d-none");
    detailView.classList.remove("d-none");
    if (btnEdit) btnEdit.classList.remove("d-none");
  }

  function renderList() {
    entryList.innerHTML = "";
    if (!entries.length) {
      entryList.innerHTML = '<div class="text-secondary small py-3">No entries yet.</div>';
      entryCount.textContent = "0";
      detailEmpty.classList.remove("d-none");
      detailView.classList.add("d-none");
      if (btnEdit) btnEdit.classList.add("d-none");
      activeEntry = null;
      return;
    }
    entryCount.textContent = String(entries.length);
    entries.forEach((entry) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "list-group-item list-group-item-action";
      if (recentEntryId && String(entry.id || "") === String(recentEntryId)) {
        btn.classList.add("list-group-item-success");
      }
      const title = document.createElement("div");
      title.className = "fw-semibold";
      title.textContent = entry.title || "Untitled entry";
      const meta = document.createElement("div");
      meta.className = "d-flex align-items-center gap-2 small";
      const badge = document.createElement("span");
      badge.className = `badge ${typeBadge(entry.service_type)}`;
      badge.textContent = entry.service_type || "SERVICE";
      const date = document.createElement("span");
      date.className = "text-secondary";
      date.textContent = formatDate(entry.created_at);
      meta.appendChild(badge);
      meta.appendChild(date);
      btn.appendChild(title);
      btn.appendChild(meta);
      btn.addEventListener("click", () => showDetail(entry));
      entryList.appendChild(btn);
    });
    showDetail(entries[0]);
  }

  function formatDate(value) {
    if (!value) return "Unknown date";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
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

  function typeBadge(type) {
    if (type === "REPAIR") return "bg-warning";
    if (type === "RECALL") return "bg-danger";
    if (type === "WARRANTY") return "bg-info";
    return "bg-secondary";
  }

  async function loadEntries() {
    const params = new URLSearchParams();
    if (filterType?.value) params.append("type", filterType.value);
    if (filterFrom?.value) params.append("from", filterFrom.value);
    if (filterTo?.value) params.append("to", filterTo.value);
    const url = params.toString() ? `/api/service/log?${params}` : "/api/service/log";
    const res = await fetch(url, { cache: "no-store" });
    const data = await res.json();
    entries = Array.isArray(data.entries) ? data.entries : [];
    renderList();
  }

  function resetForm() {
    editingEntryId = null;
    if (formEngineer) formEngineer.value = "";
    if (formType) formType.value = "SERVICE";
    if (formTitle) formTitle.value = "";
    if (formDescription) formDescription.value = "";
    if (formParts) formParts.value = "";
    if (formOutcome) formOutcome.value = "";
    if (formFollowup) formFollowup.value = "";
    if (formExistingAttachments) {
      formExistingAttachments.innerHTML = "";
      formExistingAttachments.classList.add("d-none");
    }
    if (formAttachments) {
      formAttachments.innerHTML = "";
      addAttachmentRow();
    }
    if (formError) {
      formError.textContent = "";
      formError.classList.add("d-none");
    }
    if (modalTitle) modalTitle.textContent = "New Service Entry";
    if (btnSave) btnSave.textContent = "Save Entry";
  }

  function renderExistingAttachments(list) {
    if (!formExistingAttachments) return;
    formExistingAttachments.innerHTML = "";
    if (!list.length) {
      formExistingAttachments.classList.add("d-none");
      return;
    }
    formExistingAttachments.classList.remove("d-none");
    const header = document.createElement("div");
    header.className = "text-secondary small mb-1";
    header.textContent = "Existing attachments";
    formExistingAttachments.appendChild(header);
    list.forEach((item) => {
      const row = document.createElement("div");
      row.className = "d-flex align-items-center justify-content-between gap-2 mb-1";
      row.dataset.filename = item.filename || "";
      const label = document.createElement("span");
      label.className = "small";
      label.textContent = item.original || item.label || item.filename || "Attachment";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1";
      remove.innerHTML = '<i class="fa fa-trash" aria-hidden="true"></i><span>Remove</span>';
      remove.addEventListener("click", () => row.remove());
      row.appendChild(label);
      row.appendChild(remove);
      formExistingAttachments.appendChild(row);
    });
  }

  function openEdit(entry) {
    if (!entry) return;
    editingEntryId = entry.id || null;
    if (formEngineer) formEngineer.value = entry.engineer || "";
    if (formType) formType.value = entry.service_type || "SERVICE";
    if (formTitle) formTitle.value = entry.title || "";
    if (formDescription) formDescription.value = entry.description || "";
    if (formParts) formParts.value = entry.parts_replaced || "";
    if (formOutcome) formOutcome.value = entry.outcome || "";
    if (formFollowup) formFollowup.value = entry.follow_up || "";
    const existing = Array.isArray(entry.attachments) ? entry.attachments : [];
    renderExistingAttachments(existing.filter((item) => item && (item.filename || item.label)));
    if (formAttachments) {
      formAttachments.innerHTML = "";
      addAttachmentRow();
    }
    if (formError) {
      formError.textContent = "";
      formError.classList.add("d-none");
    }
    if (modalTitle) modalTitle.textContent = "Edit Service Entry";
    if (btnSave) btnSave.textContent = "Save Changes";
    modal?.show();
  }

  async function saveEntry() {
    const isNewEntry = !editingEntryId;
    const payload = new FormData();
    payload.append("engineer", formEngineer?.value || "");
    payload.append("service_type", formType?.value || "SERVICE");
    payload.append("title", formTitle?.value || "");
    payload.append("description", formDescription?.value || "");
    payload.append("parts_replaced", formParts?.value || "");
    payload.append("outcome", formOutcome?.value || "");
    payload.append("follow_up", formFollowup?.value || "");
    if (editingEntryId && formExistingAttachments) {
      payload.append("keep_attachments_present", "1");
      formExistingAttachments.querySelectorAll("[data-filename]").forEach((row) => {
        const filename = row.dataset.filename;
        if (filename) {
          payload.append("keep_attachments", filename);
        }
      });
    }
    if (formAttachments) {
      formAttachments.querySelectorAll('[data-role="attachment"]').forEach((input) => {
        if (input.files && input.files[0]) {
          payload.append("attachments", input.files[0]);
        }
      });
    }
    const url = editingEntryId ? `/api/service/log/${encodeURIComponent(editingEntryId)}` : "/api/service/log";
    const res = await fetch(url, { method: "POST", body: payload });
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      if (formError) {
        formError.textContent = data.error || "Save failed";
        formError.classList.remove("d-none");
      }
      return;
    }
    modal?.hide();
    resetForm();
    recentEntryId = isNewEntry ? (data.entry?.id || null) : null;
    await loadEntries();
    showDetail(data.entry);
  }

  btnApply?.addEventListener("click", loadEntries);
  btnClear?.addEventListener("click", () => {
    if (filterType) filterType.value = "";
    if (filterFrom) filterFrom.value = "";
    if (filterTo) filterTo.value = "";
    loadEntries();
  });
  btnNew?.addEventListener("click", () => {
    resetForm();
    modal?.show();
  });
  btnEdit?.addEventListener("click", () => openEdit(activeEntry));
  btnAddAttachment?.addEventListener("click", addAttachmentRow);
  btnSave?.addEventListener("click", saveEntry);

  addAttachmentRow();
  loadEntries();
})();
