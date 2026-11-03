// Sentinel dashboard client. Talks only to the same-origin proxy in server.py.
"use strict";

const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const recordsEl = document.getElementById("records");
const refreshBtn = document.getElementById("refresh-btn");
const clearBtn = document.getElementById("clear-btn");

function setStatus(msg, kind) {
  statusEl.textContent = msg;
  statusEl.className = "status" + (kind ? " " + kind : "");
}

function toBase64(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function uploadFile(file) {
  const buf = await file.arrayBuffer();
  const payload = { filename: file.name, content_b64: toBase64(buf) };
  const res = await fetch("/api/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `upload failed (${res.status})`);
  }
  return res.json();
}

async function waitForScanned(fileId, timeoutMs = 25000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`/api/files/${fileId}`);
    if (res.ok) {
      const rec = await res.json();
      if (rec.scan_state === "SCANNED") return rec;
    }
    await new Promise((r) => setTimeout(r, 1200));
  }
  return null;
}

function badge(verdict) {
  const v = (verdict || "pending").toLowerCase();
  const label = (verdict || "PENDING").toUpperCase();
  return `<span class="badge ${v}">${label}</span>`;
}

function renderRecords(files) {
  if (!files || files.length === 0) {
    recordsEl.innerHTML = '<p class="empty">No files scanned yet. Submit one above.</p>';
    return;
  }
  recordsEl.innerHTML = files
    .map((f) => {
      const verdict = f.verdict || f.scan_state || "pending";
      const cls = (f.verdict || "").toLowerCase();
      const reasons = (f.reasons || [])
        .map((r) => `<span class="reason">${escapeHtml(r)}</span>`)
        .join("");
      const size = f.size_bytes != null ? `${f.size_bytes} B` : "";
      const cache = f.cache_hit ? " · cache hit" : "";
      return `
        <div class="record ${cls}">
          <div class="identity">
            <span class="fname">${escapeHtml(f.filename || "(unnamed)")}</span>
            <span class="meta">${escapeHtml(f.file_id || "")}</span>
            <span class="meta">${size}${cache}</span>
          </div>
          <div class="terms">
            ${badge(verdict)}
            <span class="score">score ${f.risk_score != null ? f.risk_score : "—"}</span>
          </div>
          <div class="reasons">${reasons || '<span class="reason">—</span>'}</div>
        </div>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function refresh() {
  try {
    const res = await fetch("/api/files");
    const data = await res.json();
    renderRecords(data.files);
  } catch (e) {
    setStatus("Could not load records: " + e.message, "err");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = Array.from(fileInput.files);
  if (files.length === 0) return;
  submitBtn.disabled = true;

  const pending = [];
  try {
    // Upload all selected files first, then wait for their verdicts.
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setStatus(`Uploading ${i + 1}/${files.length}: ${file.name}…`);
      try {
        const { file_id } = await uploadFile(file);
        pending.push({ name: file.name, id: file_id });
      } catch (err) {
        setStatus(`Failed to upload ${file.name}: ${err.message}`, "err");
      }
    }
    await refresh();

    // Collect verdicts.
    let clean = 0, flagged = 0, stuck = 0;
    for (let i = 0; i < pending.length; i++) {
      const p = pending[i];
      setStatus(`Scanning ${i + 1}/${pending.length}: ${p.name}…`);
      const rec = await waitForScanned(p.id);
      if (!rec) { stuck++; }
      else if (rec.verdict === "clean") { clean++; }
      else { flagged++; }
      await refresh();
    }

    const bits = [`${pending.length} file(s)`, `${clean} clean`, `${flagged} flagged`];
    if (stuck) bits.push(`${stuck} still scanning / dead-lettered`);
    setStatus(bits.join(" · "), flagged > 0 || stuck > 0 ? "err" : "ok");
    form.reset();
  } finally {
    submitBtn.disabled = false;
  }
});

clearBtn.addEventListener("click", async () => {
  if (!window.confirm("Clear all verdict records and stored files? This cannot be undone.")) {
    return;
  }
  clearBtn.disabled = true;
  setStatus("Clearing records…");
  try {
    const res = await fetch("/api/clear", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `clear failed (${res.status})`);
    setStatus(`Cleared ${data.cleared} record(s).`, "ok");
    await refresh();
  } catch (e) {
    setStatus("Could not clear: " + e.message, "err");
  } finally {
    clearBtn.disabled = false;
  }
});

refreshBtn.addEventListener("click", refresh);
refresh();
