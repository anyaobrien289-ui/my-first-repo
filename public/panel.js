/* global io */

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(ts) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function renderMessage(msg) {
  const name = escapeHtml(msg.name || "Anonymous");
  const time = formatTime(msg.ts || Date.now());
  const text = escapeHtml(msg.text || "");
  return `
    <div class="msg">
      <div class="msg-meta">
        <span class="msg-name">${name}</span>
        <span>${time}</span>
      </div>
      <div class="msg-text">${text}</div>
    </div>
  `;
}

function setLoading(el, loading, label) {
  if (!el) return;
  el.disabled = loading;
  el.dataset._label = el.dataset._label || el.textContent;
  el.textContent = loading ? label : el.dataset._label;
}

function pill(kind, text) {
  return `<span class="pill ${kind}">${escapeHtml(text)}</span>`;
}

function renderValidation(data) {
  const v = data?.verification;
  const sources = data?.sources || {};

  const score = Number(v?.overlapScore || 0);
  const scoreKind = score >= 55 ? "good" : score >= 25 ? "warn" : "bad";

  const wikiUrl = sources?.wikipedia?.url;
  const wdUrl = sources?.wikidata?.url;
  const oaUrl = sources?.openalex?.url;
  const crUrl = sources?.crossref?.url;

  const supported = v?.years?.supported || [];
  const singles = v?.years?.singleSourceOnly || [];

  const alerts = Array.isArray(v?.alerts) ? v.alerts : [];

  const sourcesBlock = `
    <div class="section">
      <div class="section-title">Sources</div>
      <div class="list">
        <div class="item">
          <div class="item-title">Wikipedia</div>
          <div class="item-sub">${wikiUrl ? `<a href="${escapeHtml(wikiUrl)}" target="_blank" rel="noreferrer">${escapeHtml(wikiUrl)}</a>` : escapeHtml(sources?.wikipedia?.error || "No data")}</div>
        </div>
        <div class="item">
          <div class="item-title">Wikidata</div>
          <div class="item-sub">${wdUrl ? `<a href="${escapeHtml(wdUrl)}" target="_blank" rel="noreferrer">${escapeHtml(wdUrl)}</a>` : escapeHtml(sources?.wikidata?.error || "No data")}</div>
        </div>
        <div class="item">
          <div class="item-title">OpenAlex</div>
          <div class="item-sub">${oaUrl ? `<a href="${escapeHtml(oaUrl)}" target="_blank" rel="noreferrer">${escapeHtml(oaUrl)}</a>` : escapeHtml(sources?.openalex?.error || "No data")}</div>
        </div>
        <div class="item">
          <div class="item-title">Crossref</div>
          <div class="item-sub">${crUrl ? `<a href="${escapeHtml(crUrl)}" target="_blank" rel="noreferrer">${escapeHtml(crUrl)}</a>` : escapeHtml(sources?.crossref?.error || "No data")}</div>
        </div>
      </div>
    </div>
  `;

  const supportedBlock = `
    <div class="section">
      <div class="section-title">Cross-verified overlaps (time signals)</div>
      <div class="list">
        ${
          supported.length
            ? supported
                .map((x) => `<div class="item"><div class="item-title">${escapeHtml(String(x.year))}</div><div class="item-sub">Supported by: ${escapeHtml(x.sources.join(", "))}</div></div>`)
                .join("")
            : `<div class="empty">No overlapping year signals across sources for this query.</div>`
        }
      </div>
    </div>
  `;

  const singlesBlock = `
    <div class="section">
      <div class="section-title">Single-source signals (inspect carefully)</div>
      <div class="list">
        ${
          singles.length
            ? singles
                .map((x) => `<div class="item"><div class="item-title">${escapeHtml(String(x.year))}</div><div class="item-sub">Only: ${escapeHtml(x.sources.join(", "))}</div></div>`)
                .join("")
            : `<div class="empty">None.</div>`
        }
      </div>
    </div>
  `;

  const alertBlock = alerts.length
    ? `
      <div class="section">
        <div class="section-title">Alerts</div>
        <div class="list">
          ${alerts.map((a) => `<div class="item"><div class="item-sub">${escapeHtml(a)}</div></div>`).join("")}
        </div>
      </div>
    `
    : "";

  return `
    <div class="kpi-row">
      <div class="kpi">
        <div class="k">Overlap score</div>
        <div class="v">${pill(scoreKind, `${score}%`)}</div>
      </div>
      <div class="kpi">
        <div class="k">Query</div>
        <div class="v">${escapeHtml(data?.query || "")}</div>
      </div>
    </div>
    ${alertBlock}
    ${sourcesBlock}
    ${supportedBlock}
    ${singlesBlock}
  `;
}

function renderDeepQuestion(resp) {
  const ok = !!resp?.ok;
  if (!ok) {
    const err = resp?.error || "Request failed.";
    const detail = resp?.detail || null;
    return `
      <div class="kpi-row">
        <div class="kpi"><div class="k">Status</div><div class="v">${pill("bad", "Not backed")}</div></div>
      </div>
      <div class="section">
        <div class="section-title">Error</div>
        <div class="item"><div class="item-sub">${escapeHtml(String(err))}</div></div>
        ${detail ? `<div class="micro">${escapeHtml(String(detail))}</div>` : ""}
      </div>
    `;
  }

  const backed = resp?.backing?.bothAgree === true;
  const statusPill = backed ? pill("good", "Backed by both") : pill("warn", "Disagreement / partial backing");

  const q = resp?.question || "";
  const gpt = resp?.backing?.gpt || {};
  const gem = resp?.backing?.gemini || {};

  const renderModel = (m) => {
    const name = m?.model || "unknown";
    const depth = m?.assessment?.is_deep;
    const conf = m?.assessment?.confidence;
    const reasons = Array.isArray(m?.assessment?.reasons) ? m.assessment.reasons : [];
    const kind = depth ? "good" : "warn";
    return `
      <div class="item">
        <div class="item-title">${escapeHtml(name)}</div>
        <div class="item-sub">
          ${pill(kind, depth ? "Marks as deep" : "Does not mark as deep")}
          ${typeof conf === "number" ? `&nbsp;${pill("pill", `confidence ${Math.round(conf * 100)}%`)}` : ""}
        </div>
        ${reasons.length ? `<div class="micro">${escapeHtml(reasons.join(" • "))}</div>` : ""}
      </div>
    `;
  };

  return `
    <div class="kpi-row">
      <div class="kpi"><div class="k">Status</div><div class="v">${statusPill}</div></div>
      <div class="kpi"><div class="k">Topic</div><div class="v">${escapeHtml(resp?.topic || "")}</div></div>
    </div>
    <div class="section">
      <div class="section-title">Deep question</div>
      <div class="item"><div class="item-sub">${escapeHtml(q)}</div></div>
    </div>
    <div class="section">
      <div class="section-title">Model backing</div>
      <div class="list">
        ${renderModel(gpt)}
        ${renderModel(gem)}
      </div>
    </div>
  `;
}

// ---------------- Live chat ----------------

const socket = io();

const nameEl = $("name");
const roomEl = $("room");
const createRoomBtn = $("createRoom");
const joinRoomBtn = $("joinRoom");
const messagesEl = $("messages");
const sendForm = $("sendForm");
const messageEl = $("message");

let currentRoom = null;

function appendMessage(msg) {
  messagesEl.insertAdjacentHTML("beforeend", renderMessage(msg));
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setRooms(rooms) {
  const prev = roomEl.value;
  roomEl.innerHTML = "";
  const list = Array.isArray(rooms) ? rooms : [];
  for (const r of list) {
    const opt = document.createElement("option");
    opt.value = r.name;
    opt.textContent = `${r.name} (${r.messageCount})`;
    roomEl.appendChild(opt);
  }
  if (prev && [...roomEl.options].some((o) => o.value === prev)) {
    roomEl.value = prev;
  }
  if (!roomEl.value && roomEl.options.length) roomEl.value = roomEl.options[0].value;
}

socket.on("rooms:list", (payload) => setRooms(payload?.rooms));
socket.on("room:history", (payload) => {
  if (!payload?.room) return;
  currentRoom = payload.room;
  messagesEl.innerHTML = "";
  for (const msg of payload?.messages || []) appendMessage(msg);
  appendMessage({ name: "system", ts: Date.now(), text: `Joined room "${currentRoom}".` });
});
socket.on("message:new", (payload) => {
  if (payload?.room !== currentRoom) return;
  appendMessage(payload?.message);
});

createRoomBtn.addEventListener("click", () => {
  const room = window.prompt("Room name (e.g. Philosophy / Science / 'Project-X'):");
  if (!room) return;
  socket.emit("room:create", { room });
});

joinRoomBtn.addEventListener("click", () => {
  const name = (nameEl.value || "Anonymous").trim().slice(0, 40);
  const room = (roomEl.value || "General").trim().slice(0, 60);
  socket.emit("room:join", { room, name });
});

sendForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (messageEl.value || "").trim();
  if (!text) return;
  const name = (nameEl.value || "Anonymous").trim().slice(0, 40);
  const room = currentRoom || (roomEl.value || "General");
  socket.emit("message:send", { room, name, text });
  messageEl.value = "";
});

messageEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendForm.requestSubmit();
  }
});

// Auto-join default
setTimeout(() => {
  nameEl.value = localStorage.getItem("panel:name") || "";
  const name = (nameEl.value || "Anonymous").trim().slice(0, 40);
  const room = (roomEl.value || "General").trim().slice(0, 60);
  socket.emit("room:join", { room, name });
}, 400);

nameEl.addEventListener("change", () => localStorage.setItem("panel:name", (nameEl.value || "").trim().slice(0, 40)));

// ---------------- Validation + deep question ----------------

const topicEl = $("topic");
const validateBtn = $("validate");
const resultsEl = $("results");

const deepTopicEl = $("deepTopic");
const generateDeepBtn = $("generateDeep");
const deepResultsEl = $("deepResults");

validateBtn.addEventListener("click", async () => {
  const q = (topicEl.value || "").trim();
  if (!q) return;
  setLoading(validateBtn, true, "Validating…");
  resultsEl.innerHTML = `<div class="empty">Fetching sources and cross-verifying…</div>`;
  try {
    const res = await fetch(`/api/validate?q=${encodeURIComponent(q)}`);
    const json = await res.json();
    resultsEl.innerHTML = renderValidation(json);
  } catch (err) {
    resultsEl.innerHTML = `<div class="empty">Error: ${escapeHtml(String(err && err.message ? err.message : err))}</div>`;
  } finally {
    setLoading(validateBtn, false, "");
  }
});

generateDeepBtn.addEventListener("click", async () => {
  const topic = (deepTopicEl.value || "").trim();
  if (!topic) return;
  setLoading(generateDeepBtn, true, "Generating…");
  deepResultsEl.innerHTML = `<div class="empty">Requesting both models and checking agreement…</div>`;
  try {
    const res = await fetch(`/api/deep-question`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ topic }),
    });
    const json = await res.json();
    deepResultsEl.innerHTML = renderDeepQuestion(json);
  } catch (err) {
    deepResultsEl.innerHTML = `<div class="empty">Error: ${escapeHtml(String(err && err.message ? err.message : err))}</div>`;
  } finally {
    setLoading(generateDeepBtn, false, "");
  }
});

