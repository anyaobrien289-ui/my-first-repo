/* eslint-disable no-console */

const path = require("path");
const http = require("http");

const express = require("express");
const { Server } = require("socket.io");

const PORT = process.env.PORT ? Number(process.env.PORT) : 3000;

const app = express();
app.disable("x-powered-by");

app.use(express.json({ limit: "1mb" }));
app.use(express.urlencoded({ extended: false }));

const publicDir = path.join(__dirname, "..", "public");
app.use(express.static(publicDir, { extensions: ["html"] }));

app.get("/", (_req, res) => res.redirect("/panel"));
app.get("/panel", (_req, res) => res.sendFile(path.join(publicDir, "panel.html")));

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, time: new Date().toISOString() });
});

function getEnv(name, fallback = "") {
  const v = process.env[name];
  if (typeof v === "string" && v.trim()) return v.trim();
  return fallback;
}

function clampString(s, maxLen) {
  if (typeof s !== "string") return "";
  const trimmed = s.trim();
  if (trimmed.length <= maxLen) return trimmed;
  return trimmed.slice(0, maxLen);
}

function safeJsonParse(maybeJsonText) {
  if (typeof maybeJsonText !== "string") return { ok: false, error: "Not a string." };
  const text = maybeJsonText.trim();
  if (!text) return { ok: false, error: "Empty." };
  try {
    return { ok: true, json: JSON.parse(text) };
  } catch (_e) {
    // Try to salvage a JSON object inside a larger string.
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start >= 0 && end > start) {
      const slice = text.slice(start, end + 1);
      try {
        return { ok: true, json: JSON.parse(slice) };
      } catch (e2) {
        return { ok: false, error: `Failed to parse JSON (salvage attempt): ${String(e2 && e2.message ? e2.message : e2)}` };
      }
    }
    return { ok: false, error: "Failed to parse JSON." };
  }
}

async function fetchJson(url, { timeoutMs = 9000, headers = {} } = {}) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        "user-agent": "live-question-panel/0.1 (+local)",
        accept: "application/json",
        ...headers,
      },
      signal: ac.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return { ok: false, status: res.status, error: text || res.statusText };
    }
    const json = await res.json();
    return { ok: true, status: res.status, json };
  } catch (err) {
    return { ok: false, status: 0, error: String(err && err.message ? err.message : err) };
  } finally {
    clearTimeout(timer);
  }
}

function uniq(arr) {
  return [...new Set(arr)];
}

function extractYearsFromText(text, { maxUnique = 25 } = {}) {
  if (!text) return [];
  const matches = text.match(/\b(1[0-9]{3}|20[0-9]{2}|2100)\b/g) || [];
  const years = uniq(matches.map((y) => Number(y)).filter((n) => Number.isFinite(n)));
  years.sort((a, b) => a - b);
  return years.slice(0, maxUnique);
}

function parseWikidataTimeValue(timeValue) {
  // timeValue example: "+1955-08-17T00:00:00Z"
  if (typeof timeValue !== "string") return null;
  const m = timeValue.match(/^([+-])(\d{4})-(\d{2})-(\d{2})T/);
  if (!m) return null;
  const sign = m[1] === "-" ? -1 : 1;
  const year = sign * Number(m[2]);
  const month = Number(m[3]);
  const day = Number(m[4]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  return { year, month, day };
}

function pickWikidataFacts(entity) {
  const claims = entity?.claims || {};

  const pickTime = (prop) => {
    const mainsnak = claims?.[prop]?.[0]?.mainsnak;
    const timeValue = mainsnak?.datavalue?.value?.time;
    const parsed = parseWikidataTimeValue(timeValue);
    if (!parsed) return null;
    return { ...parsed, raw: timeValue };
  };

  const pickQuantity = (prop) => {
    const mainsnak = claims?.[prop]?.[0]?.mainsnak;
    const value = mainsnak?.datavalue?.value;
    if (!value || typeof value.amount !== "string") return null;
    const amount = Number(value.amount);
    if (!Number.isFinite(amount)) return null;
    return { amount, unit: value.unit || null };
  };

  return {
    dateOfBirth: pickTime("P569"),
    dateOfDeath: pickTime("P570"),
    inception: pickTime("P571"),
    publicationDate: pickTime("P577"),
    population: pickQuantity("P1082"),
  };
}

function crossVerify({ wikipedia, wikidata, openalex, crossref }) {
  const bySource = {
    wikipedia: extractYearsFromText(wikipedia?.extract || ""),
    wikidata: uniq(
      [
        wikidata?.facts?.dateOfBirth?.year,
        wikidata?.facts?.dateOfDeath?.year,
        wikidata?.facts?.inception?.year,
        wikidata?.facts?.publicationDate?.year,
      ].filter((n) => Number.isFinite(n))
    ),
    openalex: uniq(
      (openalex?.works || [])
        .map((w) => w.publication_year)
        .filter((n) => Number.isFinite(n))
        .slice(0, 25)
    ),
    crossref: uniq(
      (crossref?.works || [])
        .map((w) => w.issued_year)
        .filter((n) => Number.isFinite(n))
        .slice(0, 25)
    ),
  };

  const counts = new Map();
  for (const [src, years] of Object.entries(bySource)) {
    for (const y of years) {
      const key = String(y);
      const prev = counts.get(key) || { year: y, sources: [] };
      if (!prev.sources.includes(src)) prev.sources.push(src);
      counts.set(key, prev);
    }
  }

  const all = [...counts.values()].sort((a, b) => (b.sources.length - a.sources.length) || (a.year - b.year));
  const supported = all.filter((x) => x.sources.length >= 2).slice(0, 15);
  const singleSourceOnly = all.filter((x) => x.sources.length === 1).slice(0, 15);

  // Simple consistency signal: how many years are multi-sourced among the "signal" years.
  const considered = all.slice(0, 30);
  const overlapScore = considered.length
    ? Math.round((considered.filter((x) => x.sources.length >= 2).length / considered.length) * 100)
    : 0;

  const alerts = [];
  const hasAny = Object.values(bySource).some((ys) => ys.length > 0);
  if (!hasAny) alerts.push("No time-based claims found to cross-verify for this query.");
  if (hasAny && supported.length === 0) alerts.push("No overlapping years found across sources (possible ambiguity or conflicting coverage).");
  if (overlapScore > 0 && overlapScore < 20) alerts.push("Low cross-source overlap score; treat claims as unverified until you inspect sources.");

  return {
    overlapScore,
    years: {
      supported,
      singleSourceOnly,
      bySource,
    },
    alerts,
  };
}

async function validateAcrossSources(q) {
  // Wikipedia: resolve best title via opensearch, then summary.
  const wikiSearchUrl =
    "https://en.wikipedia.org/w/api.php?action=opensearch&limit=1&namespace=0&format=json&search=" +
    encodeURIComponent(q);
  const wikiSearch = await fetchJson(wikiSearchUrl);
  let wikiTitle = q;
  if (wikiSearch.ok && Array.isArray(wikiSearch.json) && Array.isArray(wikiSearch.json[1]) && wikiSearch.json[1][0]) {
    wikiTitle = String(wikiSearch.json[1][0]);
  }
  const wikiSummaryUrl =
    "https://en.wikipedia.org/api/rest_v1/page/summary/" + encodeURIComponent(wikiTitle.replace(/\s+/g, "_"));
  const wikiSummary = await fetchJson(wikiSummaryUrl);
  const wikipedia = wikiSummary.ok
    ? {
        title: wikiSummary.json?.title || wikiTitle,
        extract: wikiSummary.json?.extract || "",
        url: wikiSummary.json?.content_urls?.desktop?.page || null,
      }
    : { error: wikiSummary.error || "Wikipedia request failed." };

  // Wikidata: find best entity id then fetch entitydata.
  const wdSearchUrl =
    "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=1&search=" +
    encodeURIComponent(q);
  const wdSearch = await fetchJson(wdSearchUrl);
  let wikidata = { error: "Wikidata request failed." };
  if (wdSearch.ok && wdSearch.json?.search?.[0]?.id) {
    const id = String(wdSearch.json.search[0].id);
    const entityUrl = `https://www.wikidata.org/wiki/Special:EntityData/${encodeURIComponent(id)}.json`;
    const entityRes = await fetchJson(entityUrl);
    if (entityRes.ok) {
      const entity = entityRes.json?.entities?.[id];
      wikidata = {
        id,
        label: entity?.labels?.en?.value || null,
        description: entity?.descriptions?.en?.value || null,
        url: `https://www.wikidata.org/wiki/${id}`,
        facts: pickWikidataFacts(entity),
      };
    } else {
      wikidata = {
        id,
        url: `https://www.wikidata.org/wiki/${id}`,
        error: entityRes.error || "Wikidata entity fetch failed.",
      };
    }
  }

  // OpenAlex: top works
  const oaUrl = "https://api.openalex.org/works?per-page=5&search=" + encodeURIComponent(q);
  const oaRes = await fetchJson(oaUrl);
  const openalex = oaRes.ok
    ? {
        url: `https://openalex.org/works?search=${encodeURIComponent(q)}`,
        works: (oaRes.json?.results || []).map((w) => ({
          id: w.id || null,
          title: w.title || null,
          publication_year: w.publication_year || null,
          doi: w.doi || null,
          url: w.id || null,
        })),
      }
    : { error: oaRes.error || "OpenAlex request failed." };

  // Crossref: top works
  const crUrl = "https://api.crossref.org/works?rows=5&query=" + encodeURIComponent(q);
  const crRes = await fetchJson(crUrl);
  const crossref = crRes.ok
    ? {
        url: `https://search.crossref.org/?q=${encodeURIComponent(q)}`,
        works: (crRes.json?.message?.items || []).map((it) => ({
          title: Array.isArray(it.title) ? it.title[0] : it.title || null,
          doi: it.DOI || null,
          url: it.URL || null,
          issued_year: it?.issued?.["date-parts"]?.[0]?.[0] || null,
          type: it.type || null,
        })),
      }
    : { error: crRes.error || "Crossref request failed." };

  const verification = crossVerify({ wikipedia, wikidata, openalex, crossref });

  return { sources: { wikipedia, wikidata, openalex, crossref }, verification };
}

app.get("/api/validate", async (req, res) => {
  const q = clampString(String(req.query.q || ""), 200);
  if (!q) return res.status(400).json({ ok: false, error: "Missing query parameter 'q'." });

  const { sources, verification } = await validateAcrossSources(q);
  res.json({ ok: true, query: q, sources, verification });
});

async function fetchJsonPost(url, body, { timeoutMs = 20000, headers = {} } = {}) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "user-agent": "live-question-panel/0.1 (+local)",
        accept: "application/json",
        "content-type": "application/json",
        ...headers,
      },
      body: JSON.stringify(body),
      signal: ac.signal,
    });
    const text = await res.text().catch(() => "");
    if (!res.ok) return { ok: false, status: res.status, error: text || res.statusText };
    try {
      return { ok: true, status: res.status, json: text ? JSON.parse(text) : {} };
    } catch (e) {
      return { ok: false, status: res.status, error: `Non-JSON response: ${String(e && e.message ? e.message : e)}` };
    }
  } catch (err) {
    return { ok: false, status: 0, error: String(err && err.message ? err.message : err) };
  } finally {
    clearTimeout(timer);
  }
}

async function callOpenAIBacking({ apiKey, model, topic }) {
  const schemaHint =
    "Return JSON exactly shaped like: {\"question\": string, \"assessment\": {\"is_deep\": boolean, \"confidence\": number, \"reasons\": string[]}}";

  const prompt = `Generate ONE deep, open-ended discussion question about the topic: "${topic}".

Goal: inquiry should not be constrained by predefined limitations; the question should invite unrestricted intellectual exploration while staying coherent and safe.

Then assess the question for depth and open-endedness. confidence must be between 0 and 1.
reasons must be 2-5 short bullets as strings.`;

  const url = "https://api.openai.com/v1/chat/completions";
  const body = {
    model,
    temperature: 0.4,
    messages: [
      {
        role: "system",
        content:
          "You are a careful assistant. Output ONLY strict JSON, no markdown, no extra text. If you cannot comply, output a JSON object with an error field.",
      },
      { role: "user", content: `${schemaHint}\n\n${prompt}` },
    ],
    response_format: { type: "json_object" },
  };

  const resp = await fetchJsonPost(url, body, {
    timeoutMs: 20000,
    headers: { authorization: `Bearer ${apiKey}` },
  });
  if (!resp.ok) return { ok: false, error: resp.error || "OpenAI request failed." };

  const text = resp.json?.choices?.[0]?.message?.content;
  const parsed = safeJsonParse(text);
  if (!parsed.ok) return { ok: false, error: parsed.error || "Failed to parse OpenAI JSON." };
  return { ok: true, model, data: parsed.json };
}

async function callGeminiBacking({ apiKey, model, topic }) {
  const schemaHint =
    "Return JSON exactly shaped like: {\"question\": string, \"assessment\": {\"is_deep\": boolean, \"confidence\": number, \"reasons\": string[]}}";
  const prompt = `Generate ONE deep, open-ended discussion question about the topic: "${topic}".

Goal: inquiry should not be constrained by predefined limitations; the question should invite unrestricted intellectual exploration while staying coherent and safe.

Then assess the question for depth and open-endedness. confidence must be between 0 and 1.
reasons must be 2-5 short bullets as strings.

Output ONLY strict JSON (no markdown).`;

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const body = {
    contents: [{ role: "user", parts: [{ text: `${schemaHint}\n\n${prompt}` }] }],
    generationConfig: { temperature: 0.4 },
  };

  const resp = await fetchJsonPost(url, body, { timeoutMs: 20000 });
  if (!resp.ok) return { ok: false, error: resp.error || "Gemini request failed." };

  const text = resp.json?.candidates?.[0]?.content?.parts?.map((p) => p.text).join("\n");
  const parsed = safeJsonParse(text);
  if (!parsed.ok) return { ok: false, error: parsed.error || "Failed to parse Gemini JSON." };
  return { ok: true, model, data: parsed.json };
}

function normalizeAssessment(obj) {
  const q = typeof obj?.question === "string" ? obj.question.trim() : "";
  const a = obj?.assessment || {};
  const is_deep = Boolean(a?.is_deep);
  const confidence = typeof a?.confidence === "number" ? a.confidence : null;
  const reasons = Array.isArray(a?.reasons) ? a.reasons.map((r) => String(r)).slice(0, 8) : [];
  return { question: q, assessment: { is_deep, confidence, reasons } };
}

app.post("/api/deep-question", async (req, res) => {
  const topic = clampString(String(req.body?.topic || ""), 200);
  if (!topic) return res.status(400).json({ ok: false, error: "Missing JSON body field 'topic'." });

  const openaiKey = getEnv("OPENAI_API_KEY");
  const geminiKey = getEnv("GEMINI_API_KEY");
  const openaiModel = getEnv("OPENAI_MODEL", "gpt-5.2");
  const geminiModel = getEnv("GEMINI_MODEL", "gemini-3");

  if (!openaiKey || !geminiKey) {
    return res.status(503).json({
      ok: false,
      error: "Deep questions require BOTH GPT-5.2 and Gemini 3 backing, but API keys are not configured.",
      detail:
        "Set env vars OPENAI_API_KEY and GEMINI_API_KEY (optionally OPENAI_MODEL and GEMINI_MODEL), then retry.",
      required_env: ["OPENAI_API_KEY", "GEMINI_API_KEY"],
    });
  }

  const [gptRes, gemRes] = await Promise.all([
    callOpenAIBacking({ apiKey: openaiKey, model: openaiModel, topic }),
    callGeminiBacking({ apiKey: geminiKey, model: geminiModel, topic }),
  ]);

  if (!gptRes.ok || !gemRes.ok) {
    return res.status(502).json({
      ok: false,
      error: "Failed to generate LLM-backed deep question from both providers.",
      detail: {
        gpt: gptRes.ok ? null : gptRes.error,
        gemini: gemRes.ok ? null : gemRes.error,
      },
    });
  }

  const gpt = normalizeAssessment(gptRes.data);
  const gemini = normalizeAssessment(gemRes.data);

  const bothAgree = gpt.assessment.is_deep === true && gemini.assessment.is_deep === true;
  const question = bothAgree ? gpt.question || gemini.question : gpt.question || gemini.question || "";

  // Also return a multi-source validation snapshot for the topic (cross-verification).
  const { sources, verification } = await validateAcrossSources(topic);

  res.json({
    ok: true,
    topic,
    question,
    backing: {
      bothAgree,
      gpt: { model: openaiModel, ...gpt },
      gemini: { model: geminiModel, ...gemini },
    },
    sources,
    verification,
  });
});

// ---------------- Live panel (Socket.IO) ----------------

const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: true, methods: ["GET", "POST"] },
});

const rooms = new Map(); // roomName -> { createdAt, messages: [{id, ts, name, text}] }
const MAX_MESSAGE_CHARS = 20000;
const MAX_MESSAGES_PER_ROOM = 500;

function getOrCreateRoom(roomName) {
  if (!rooms.has(roomName)) {
    rooms.set(roomName, { createdAt: Date.now(), messages: [] });
  }
  return rooms.get(roomName);
}

function listRooms() {
  return [...rooms.entries()]
    .map(([name, room]) => ({
      name,
      createdAt: room.createdAt,
      messageCount: room.messages.length,
    }))
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 50);
}

function makeId() {
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}

io.on("connection", (socket) => {
  socket.emit("rooms:list", { rooms: listRooms() });

  socket.on("room:create", (payload = {}) => {
    const room = clampString(String(payload.room || ""), 60).replace(/[^\w \-./]/g, "");
    if (!room) return;
    getOrCreateRoom(room);
    io.emit("rooms:list", { rooms: listRooms() });
  });

  socket.on("room:join", (payload = {}) => {
    const room = clampString(String(payload.room || ""), 60);
    const name = clampString(String(payload.name || "Anonymous"), 40) || "Anonymous";
    if (!room) return;
    getOrCreateRoom(room);
    socket.join(room);
    socket.data.room = room;
    socket.data.name = name;
    const history = rooms.get(room)?.messages || [];
    socket.emit("room:history", { room, messages: history.slice(-200) });
    socket.emit("rooms:list", { rooms: listRooms() });
  });

  socket.on("message:send", (payload = {}) => {
    const room = clampString(String(payload.room || socket.data.room || ""), 60);
    const name = clampString(String(payload.name || socket.data.name || "Anonymous"), 40) || "Anonymous";
    const text = clampString(String(payload.text || ""), MAX_MESSAGE_CHARS);
    if (!room || !text) return;
    const roomState = getOrCreateRoom(room);
    const msg = { id: makeId(), ts: Date.now(), name, text };
    roomState.messages.push(msg);
    if (roomState.messages.length > MAX_MESSAGES_PER_ROOM) {
      roomState.messages.splice(0, roomState.messages.length - MAX_MESSAGES_PER_ROOM);
    }
    io.to(room).emit("message:new", { room, message: msg });
  });

  socket.on("disconnect", () => {});
});

// Seed a default room
getOrCreateRoom("General");

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`Live panel running on http://localhost:${PORT}/panel`);
  });
}

module.exports = { app, server };

