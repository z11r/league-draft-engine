"use strict";

/* Talk to the same origin when served over http(s) (dev via the mock, or prod
   when the real backend serves these files). Fall back to the local mock only
   when the page is opened straight off disk as a file://. */
const API_BASE =
  location.protocol === "http:" || location.protocol === "https:"
    ? ""
    : "http://127.0.0.1:8000";

const SIDES = ["blue", "red"];
const ROLES = ["top", "jungle", "mid", "bot", "support"];
const SLOT_ORDER = SIDES.flatMap((s) => ROLES.map((r) => `${s}_${r}`));

const state = {
  champions: [],
  byLower: new Map(), // "ahri" -> "Ahri"
  raw: Object.fromEntries(SLOT_ORDER.map((id) => [id, ""])), // typed text per slot
  effective: Object.fromEntries(SLOT_ORDER.map((id) => [id, null])), // valid pick or null
  selected: null,
  suggestedFor: null,
  predictReq: 0,
};

const $ = (id) => document.getElementById(id);
const el = {
  datalist: $("champ-list"),
  suggestBtn: $("suggest-btn"),
  hint: $("panel-hint"),
  recs: $("recs"),
  backendTag: $("backend-tag"),
  predict: $("predict"),
  predictWaiting: $("predict-waiting"),
  predictError: $("predict-error"),
  predictValue: $("predict-value"),
  barBlue: $("predict-bar-blue"),
  barRed: $("predict-bar-red"),
};

/* ---------- API helper ---------- */
async function api(path, options) {
  const res = await fetch(API_BASE + path, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ---------- Boot ---------- */
async function boot() {
  el.backendTag.textContent = (API_BASE || location.host || "same-origin") + " · api";
  buildSlots();
  try {
    const data = await api("/champions");
    state.champions = data.champions || [];
    state.byLower = new Map(state.champions.map((c) => [c.toLowerCase(), c]));
    el.datalist.innerHTML = state.champions
      .map((c) => `<option value="${c}"></option>`)
      .join("");
    setHint("Select an empty slot, then Suggest.");
  } catch (err) {
    document
      .querySelectorAll(".slot-input")
      .forEach((i) => (i.disabled = true));
    setHint("Couldn't load champions. Is the backend running?", true);
  }
}

/* ---------- Slots ---------- */
function buildSlots() {
  for (const side of SIDES) {
    const wrap = $("slots-" + side);
    for (const role of ROLES) {
      const id = `${side}_${role}`;
      const slot = document.createElement("div");
      slot.className = "slot";
      slot.dataset.slot = id;
      slot.innerHTML = `
        <span class="slot-role">${role}</span>
        <input class="slot-input" list="champ-list" placeholder="—"
               aria-label="${side} ${role} champion" autocomplete="off" />
        <span class="slot-status" aria-hidden="true"></span>`;
      const input = slot.querySelector(".slot-input");

      slot.addEventListener("click", () => select(id));
      input.addEventListener("focus", () => select(id));
      input.addEventListener("input", () => {
        state.raw[id] = input.value;
        recompute();
      });
      input.addEventListener("change", () => {
        // Snap to canonical casing if it matches a known champion.
        const canon = state.byLower.get(input.value.trim().toLowerCase());
        if (canon) input.value = canon;
        state.raw[id] = input.value;
        recompute();
      });
      wrap.appendChild(slot);
    }
  }
  el.suggestBtn.addEventListener("click", onSuggest);
}

function select(id) {
  state.selected = id;
  document
    .querySelectorAll(".slot")
    .forEach((s) => s.classList.toggle("is-selected", s.dataset.slot === id));
  updateSuggestButton();
}

function slotEl(id) {
  return document.querySelector(`.slot[data-slot="${id}"]`);
}

/* Recompute per-slot validity, dedupe, and knock-on effects. */
function recompute() {
  const seen = new Set();
  for (const id of SLOT_ORDER) {
    const raw = state.raw[id].trim();
    const canon = state.byLower.get(raw.toLowerCase());
    const s = slotEl(id);
    s.classList.remove("is-filled", "is-dupe", "is-invalid");
    if (!raw) {
      state.effective[id] = null;
    } else if (!canon) {
      state.effective[id] = null;
      s.classList.add("is-invalid");
    } else if (seen.has(canon)) {
      state.effective[id] = null;
      s.classList.add("is-dupe");
    } else {
      state.effective[id] = canon;
      seen.add(canon);
      s.classList.add("is-filled");
    }
  }
  updateSuggestButton();
  runPredict();
}

function updateSuggestButton() {
  const id = state.selected;
  const empty = id && state.raw[id].trim() === "";
  el.suggestBtn.disabled = !empty;
  if (!id) setHint("Select an empty slot, then Suggest.");
  else if (!empty) setHint("That slot is filled — pick an empty one to get suggestions.");
  else setHint(`Suggesting for ${label(id)}.`);
}

function label(id) {
  const [side, role] = id.split("_");
  return `${side} ${role}`;
}

function setHint(text, isError) {
  el.hint.textContent = text;
  el.hint.classList.toggle("is-error", !!isError);
}

/* ---------- Team payloads ---------- */
function team(side) {
  const t = {};
  for (const role of ROLES) t[role] = state.effective[`${side}_${role}`];
  return t;
}

/* ---------- Suggest / recommend ---------- */
async function onSuggest() {
  const id = state.selected;
  if (!id || state.raw[id].trim() !== "") return;
  state.suggestedFor = id;
  el.suggestBtn.disabled = true;
  setHint(`Finding picks for ${label(id)}…`);
  el.recs.innerHTML = "";
  try {
    const data = await api("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blue: team("blue"), red: team("red"), slot: id }),
    });
    renderRecs(data.recommendations || []);
    setHint(`Top picks for ${label(id)} — click one to draft it.`);
  } catch (err) {
    el.recs.innerHTML = "";
    setHint("Suggestion request failed.", true);
  } finally {
    updateSuggestButton();
  }
}

function renderRecs(list) {
  el.recs.innerHTML = "";
  list.forEach((rec, i) => {
    const pct = Math.round(rec.win_probability * 100);
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "rec";
    btn.innerHTML = `
      <span class="rec-fill" style="width:${pct}%"></span>
      <span class="rec-rank">${i + 1}</span>
      <span class="rec-name">${rec.champion}</span>
      <span class="rec-prob">${(rec.win_probability * 100).toFixed(1)}%</span>`;
    btn.addEventListener("click", () => draft(rec.champion));
    li.appendChild(btn);
    el.recs.appendChild(li);
  });
}

/* Fill the slot we suggested for, then clear the list. */
function draft(champion) {
  const id = state.suggestedFor;
  if (!id) return;
  const input = slotEl(id).querySelector(".slot-input");
  input.value = champion;
  state.raw[id] = champion;
  el.recs.innerHTML = "";
  state.suggestedFor = null;
  recompute();
}

/* ---------- Predict ---------- */
async function runPredict() {
  const filled = SLOT_ORDER.filter((id) => state.effective[id]).length;
  if (filled !== 10) {
    el.predict.hidden = true;
    el.predictError.hidden = true;
    el.predictWaiting.hidden = false;
    return;
  }
  const reqId = ++state.predictReq;
  try {
    const data = await api("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blue: team("blue"), red: team("red") }),
    });
    if (reqId !== state.predictReq) return; // a newer request superseded this one
    const p = data.blue_win_probability;
    el.predictValue.textContent = (p * 100).toFixed(1) + "%";
    el.barBlue.style.width = p * 100 + "%";
    el.barRed.style.width = (1 - p) * 100 + "%";
    el.predictWaiting.hidden = true;
    el.predictError.hidden = true;
    el.predict.hidden = false;
  } catch (err) {
    if (reqId !== state.predictReq) return;
    el.predict.hidden = true;
    el.predictWaiting.hidden = true;
    el.predictError.hidden = false;
  }
}

boot();
