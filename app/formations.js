const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const SUPABASE_TABLE = "lineup_states";
const LINEUP_SIZE = 11;
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-30 23:10 JST";
const REPO_COMMITS_API = "https://api.github.com/repos/gigagigohub/websoccer-player-search/commits/main";
let appUpdatedAtJst = APP_UPDATED_AT_JST;
let ccDataMeta = null;
const METRICS = [
  "スピ", "テク", "パワ", "スタ", "ラフ", "個性", "人気",
  "PK", "FK", "CK", "CP", "知性", "感性", "個人", "組織",
];
const CORE_METRICS = ["スピ", "テク", "パワ"];
const METRIC_LABELS = {
  "スピ": "スピード",
  "テク": "テクニック",
  "パワ": "パワー",
  "スタ": "スタミナ",
  "CP": "Cap.",
};
const DETAIL_METRIC_LABELS = {
  "スピ": "スピ",
  "テク": "テク",
  "パワ": "パワ",
  "スタ": "スタ",
  "ラフ": "ラフ",
  "PK": "ＰＫ",
  "FK": "ＦＫ",
  "CK": "ＣＫ",
  "CP": "ＣＰ",
};

const PARAM_LABELS = {
  spd: "Speed",
  tec: "Technique",
  pwr: "Power",
  off: "Attack",
  def: "Defense",
  mid: "Midfield",
  ttl: "Total",
  stm: "Stamina",
  dif: "Difficulty",
};

const SORT_OPTIONS = [
  { key: "cc.usageRate", label: "CC Usage Rate" },
  { key: "cc.winRate", label: "CC Win Rate" },
  { key: "params.spd", label: "Speed" },
  { key: "params.tec", label: "Technique" },
  { key: "params.pwr", label: "Power" },
  { key: "params.off", label: "Attack" },
  { key: "params.def", label: "Defense" },
  { key: "params.mid", label: "Midfield" },
  { key: "params.ttl", label: "Total" },
  { key: "params.stm", label: "Stamina" },
  { key: "params.dif", label: "Difficulty" },
];

const els = {
  hero: document.querySelector(".hero"),
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  playersButton: document.querySelector("#playersButton"),
  coachesButton: document.querySelector("#coachesButton"),
  formationsButton: document.querySelector("#formationsButton"),
  loginButton: document.querySelector("#loginButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  logoutButton: document.querySelector("#logoutButton"),
  formationNameQuery: document.querySelector("#formationNameQuery"),
  formationNameSuggest: document.querySelector("#formationNameSuggest"),
  sortKey: document.querySelector("#sortKey"),
  sortDir: document.querySelector("#sortDir"),
  undCoachFilter: document.querySelector("#undCoachFilter"),
  avlCoachFilter: document.querySelector("#avlCoachFilter"),
  formationCount: document.querySelector("#formationCount"),
  formationList: document.querySelector("#formationList"),
  loginModal: document.querySelector("#loginModal"),
  loginBackdrop: document.querySelector("#loginBackdrop"),
  loginClose: document.querySelector("#loginClose"),
  loginLineupKey: document.querySelector("#loginLineupKey"),
  loginApply: document.querySelector("#loginApply"),
  signupOpen: document.querySelector("#signupOpen"),
  signupModal: document.querySelector("#signupModal"),
  signupBackdrop: document.querySelector("#signupBackdrop"),
  signupClose: document.querySelector("#signupClose"),
  signupLineupKey: document.querySelector("#signupLineupKey"),
  signupCancel: document.querySelector("#signupCancel"),
  signupApply: document.querySelector("#signupApply"),
  formationModal: document.querySelector("#formationModal"),
  formationBackdrop: document.querySelector("#formationBackdrop"),
  formationClose: document.querySelector("#formationClose"),
  formationTitle: document.querySelector("#formationTitle"),
  formationDetail: document.querySelector("#formationDetail"),
  slotModal: document.querySelector("#slotModal"),
  slotBackdrop: document.querySelector("#slotBackdrop"),
  slotClose: document.querySelector("#slotClose"),
  slotTitle: document.querySelector("#slotTitle"),
  slotDetail: document.querySelector("#slotDetail"),
  coachModal: document.querySelector("#coachModal"),
  coachBackdrop: document.querySelector("#coachBackdrop"),
  coachClose: document.querySelector("#coachClose"),
  coachTitle: document.querySelector("#coachTitle"),
  coachDetail: document.querySelector("#coachDetail"),
  matchupModal: document.querySelector("#matchupModal"),
  matchupBackdrop: document.querySelector("#matchupBackdrop"),
  matchupClose: document.querySelector("#matchupClose"),
  matchupTitle: document.querySelector("#matchupTitle"),
  matchupDetail: document.querySelector("#matchupDetail"),
  playerCardModal: document.querySelector("#playerCardModal"),
  playerCardBackdrop: document.querySelector("#playerCardBackdrop"),
  playerCardClose: document.querySelector("#playerCardClose"),
  playerCardHost: document.querySelector("#playerCardHost"),
};

let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let formations = [];
let coaches = [];
let coachesMeta = [];
let playerCategoryById = new Map();
let playerRateById = new Map();
let playersById = new Map();
let cloudMeta = { formationId: null, ownedFormationIds: [], coach: null };
let filteredAndSorted = [];
let currentFormation = null;
let slotTopSortMode = "usage";
let slotDetailSourceMode = "cc";
let currentSlotDetailSlot = null;
let coachRankingMode = "usage";
const bestTeamIndexByFormation = new Map();
let selectedPlayerId = null;
let rohmSlotData = null;
let rohmSlotDataPromise = null;
let rohmSlotDataError = "";
const coachTabModeById = new Map();
const cardViewModeById = new Map();
let modalScrollLockY = 0;
let modalScrollLocked = false;

function rebuildFormationAvailableCoachesFromMeta() {
  if (!Array.isArray(formations) || !formations.length) return;
  if (!Array.isArray(coachesMeta) || !coachesMeta.length) return;
  const coachNameById = new Map();
  (Array.isArray(coaches) ? coaches : []).forEach((c) => {
    const id = Number(c?.id);
    if (Number.isInteger(id) && id > 0) {
      const name = String(c?.name || "").trim();
      if (name) coachNameById.set(id, name);
    }
  });
  coachesMeta.forEach((c) => {
    const id = Number(c?.id);
    if (!Number.isInteger(id) || id <= 0) return;
    const name = String(c?.name || coachNameById.get(id) || "").trim();
    if (name) coachNameById.set(id, name);
  });

  const formationToCoachMap = new Map();
  coachesMeta.forEach((coach) => {
    const cid = Number(coach?.id);
    if (!Number.isInteger(cid) || cid <= 0) return;
    const cname = coachNameById.get(cid) || `Coach ${cid}`;
    const rows = Array.isArray(coach?.obtainable) ? coach.obtainable : [];
    rows.forEach((row) => {
      const fid = Number(row?.formationId);
      if (!Number.isInteger(fid) || fid <= 0) return;
      const fromSeasonRaw = Number(row?.fromSeason);
      const fromSeason = Number.isFinite(fromSeasonRaw) && fromSeasonRaw > 0 ? fromSeasonRaw : 1;
      if (!formationToCoachMap.has(fid)) formationToCoachMap.set(fid, new Map());
      const map = formationToCoachMap.get(fid);
      const prev = map.get(cid);
      if (!prev || fromSeason < prev.fromSeason) {
        map.set(cid, { id: cid, name: cname, fromSeason });
      }
    });
  });

  formations.forEach((formation) => {
    const fid = Number(formation?.id);
    if (!Number.isInteger(fid) || fid <= 0) return;
    const map = formationToCoachMap.get(fid);
    const rows = map
      ? Array.from(map.values()).sort((a, b) =>
          a.fromSeason - b.fromSeason
          || a.name.localeCompare(b.name, "ja")
          || a.id - b.id
        )
      : [];
    if (!formation.coaches || typeof formation.coaches !== "object") formation.coaches = {};
    formation.coaches.obtainable = rows.map((r) => ({ id: r.id, name: r.name, fromSeason: r.fromSeason }));
  });
}

function setModalScrollLocked(locked) {
  const root = document.documentElement;
  const body = document.body;
  if (!root || !body) return;
  if (locked) {
    if (modalScrollLocked) return;
    modalScrollLockY = window.scrollY || window.pageYOffset || 0;
    body.style.top = `-${modalScrollLockY}px`;
    root.classList.add("modal-scroll-lock");
    body.classList.add("modal-scroll-lock");
    modalScrollLocked = true;
    return;
  }
  if (!modalScrollLocked) return;
  root.classList.remove("modal-scroll-lock");
  body.classList.remove("modal-scroll-lock");
  body.style.top = "";
  window.scrollTo(0, modalScrollLockY);
  modalScrollLocked = false;
}

function refreshModalScrollLock() {
  const hasOpenModal = !!document.querySelector(
    '[id$="Modal"]:not([hidden]), .season-modal:not([hidden]), .lineup-modal:not([hidden])'
  );
  setModalScrollLocked(hasOpenModal);
}

function setupModalScrollLock() {
  const modals = [...document.querySelectorAll('[id$="Modal"], .season-modal, .lineup-modal')];
  const observer = new MutationObserver(() => refreshModalScrollLock());
  modals.forEach((m) => observer.observe(m, { attributes: true, attributeFilter: ["hidden"] }));
  refreshModalScrollLock();
}

function sortSlotRows(rows, mode) {
  const list = Array.isArray(rows) ? rows.slice() : [];
  if (mode === "avg") {
    list.sort((a, b) =>
      Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
      || Number(b?.usageRate || 0) - Number(a?.usageRate || 0)
      || Number(b?.uses || 0) - Number(a?.uses || 0)
      || Number(a?.playerId || 0) - Number(b?.playerId || 0)
    );
    return list;
  }
  list.sort((a, b) =>
    Number(b?.usageRate || 0) - Number(a?.usageRate || 0)
    || Number(b?.uses || 0) - Number(a?.uses || 0)
    || Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
    || Number(a?.playerId || 0) - Number(b?.playerId || 0)
  );
  return list;
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function saveCloudConfig(lineupKeyInput) {
  const lineupKey = String(lineupKeyInput ?? cloudConfig.lineupKey ?? "").trim();
  cloudConfig = {
    url: normalizedSupabaseUrl(FIXED_SUPABASE_URL || cloudConfig.url),
    anonKey: String(FIXED_SUPABASE_ANON_KEY || cloudConfig.anonKey).trim(),
    lineupKey,
  };
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
}

function loadCloudConfig() {
  try {
    const raw = localStorage.getItem(CLOUD_CONFIG_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      cloudConfig = {
        url: normalizedSupabaseUrl(parsed?.url || ""),
        anonKey: String(parsed?.anonKey || "").trim(),
        lineupKey: String(parsed?.lineupKey || "").trim(),
      };
    }
  } catch (e) {
    console.warn(e);
  }
  if (FIXED_SUPABASE_URL) cloudConfig.url = normalizedSupabaseUrl(FIXED_SUPABASE_URL);
  if (FIXED_SUPABASE_ANON_KEY) cloudConfig.anonKey = String(FIXED_SUPABASE_ANON_KEY).trim();
}

function isLoggedIn() {
  return !!String(cloudConfig.lineupKey || "").trim();
}

function renderMeta() {
  if (!els.metaText) return;
  const ccLine = ccDataMeta
    ? `<span class="meta-line">CC Data: ${ccDataMeta.seasonStart}-${ccDataMeta.seasonEnd} / ${ccDataMeta.games} games</span>`
    : "";
  els.metaText.innerHTML = `<span class="meta-line">Updated: ${appUpdatedAtJst}</span>${ccLine}`;
}

async function loadSiteMeta() {
  try {
    const res = await fetch("./site_meta.json");
    if (!res.ok) return;
    const meta = await res.json();
    const cc = meta?.ccData || {};
    const seasonStart = Number(cc.seasonStart);
    const seasonEnd = Number(cc.seasonEnd);
    const games = Number(cc.games);
    if (Number.isInteger(seasonStart) && Number.isInteger(seasonEnd) && Number.isInteger(games)) {
      ccDataMeta = { seasonStart, seasonEnd, games };
    }
  } catch (e) {
    // fallback static header
  }
}

function formatJstFromIso(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const f = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = Object.fromEntries(f.formatToParts(d).map((x) => [x.type, x.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} JST`;
}

async function refreshUpdatedAtFromGitHub() {
  try {
    const res = await fetch(REPO_COMMITS_API, { cache: "no-store" });
    if (!res.ok) return;
    const obj = await res.json();
    const iso =
      obj?.commit?.committer?.date ||
      obj?.commit?.author?.date ||
      "";
    const label = formatJstFromIso(iso);
    if (!label) return;
    appUpdatedAtJst = label;
    renderMeta();
  } catch (e) {
    // fallback static label
  }
}

function syncMenuButtonSize() {
  if (!els.menuButton) return;
  const heroEl = els.hero || els.menuButton.closest(".hero");
  const heroHeight = heroEl ? Math.round(heroEl.getBoundingClientRect().height) : 40;
  const size = Math.max(30, Math.round(heroHeight * 0.72));
  document.documentElement.style.setProperty("--menu-button-size", `${size}px`);
}

function updateMenuState() {
  const loggedIn = isLoggedIn();
  if (els.loginButton) els.loginButton.hidden = loggedIn;
  if (els.logoutButton) els.logoutButton.hidden = !loggedIn;
  if (els.menuLoginId) {
    els.menuLoginId.hidden = !loggedIn;
    els.menuLoginId.textContent = loggedIn ? `Team ID：${cloudConfig.lineupKey}` : "";
  }
  renderMeta();
}

function closeMenuPanel() {
  if (!els.menuPanel) return;
  els.menuPanel.classList.remove("is-open");
}

function openLoginModal() {
  if (!els.loginModal) return;
  if (els.loginLineupKey) {
    els.loginLineupKey.value = cloudConfig.lineupKey || "";
    els.loginLineupKey.focus();
  }
  els.loginModal.hidden = false;
}

function closeLoginModal() {
  if (!els.loginModal) return;
  els.loginModal.hidden = true;
}

function openSignupModal() {
  if (!els.signupModal) return;
  if (els.signupLineupKey) {
    els.signupLineupKey.value = "";
    els.signupLineupKey.focus();
  }
  els.signupModal.hidden = false;
}

function closeSignupModal() {
  if (!els.signupModal) return;
  els.signupModal.hidden = true;
}

async function supabaseRequest(pathWithQuery, options = {}) {
  const res = await fetch(`${cloudConfig.url}/rest/v1/${pathWithQuery}`, {
    ...options,
    headers: {
      apikey: cloudConfig.anonKey,
      Authorization: `Bearer ${cloudConfig.anonKey}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`supabase ${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

async function cloudLineupExists(lineupId) {
  const id = String(lineupId || "").trim();
  if (!id) return false;
  const params = new URLSearchParams({
    select: "lineup_id",
    lineup_id: `eq.${id}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, { method: "GET" });
  return Array.isArray(rows) && rows.length > 0;
}

async function cloudCreateLineup(lineupId) {
  const id = String(lineupId || "").trim();
  if (!id) return;
  const payload = {
    lineup_id: id,
    lineup_json: Array.from({ length: LINEUP_SIZE }, () => null),
    updated_at: new Date().toISOString(),
  };
  await supabaseRequest(`${SUPABASE_TABLE}?on_conflict=lineup_id`, {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=representation" },
    body: JSON.stringify(payload),
  });
}

function formationMetaId(lineupId = cloudConfig?.lineupKey) {
  const id = String(lineupId || "").trim();
  return id ? `${id}__meta` : "";
}

function normalizeMeta(raw) {
  const fid = Number(raw?.formationId);
  const owned = Array.isArray(raw?.ownedFormationIds)
    ? raw.ownedFormationIds.map((x) => Number(x)).filter((x) => Number.isInteger(x) && x > 0)
    : [];
  const coachId = Number(raw?.coach?.coachId);
  const season = raw?.coach?.season == null ? null : String(raw?.coach?.season);
  return {
    formationId: Number.isInteger(fid) && fid > 0 ? fid : null,
    ownedFormationIds: [...new Set(owned)],
    coach: Number.isInteger(coachId) && coachId > 0 ? { coachId, season: season || "1期目" } : null,
  };
}

async function loadCloudMeta() {
  const id = formationMetaId();
  if (!id) return false;
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${id}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, { method: "GET" });
  if (!Array.isArray(rows) || !rows.length) {
    cloudMeta = { formationId: null, ownedFormationIds: [], coach: null };
    return false;
  }
  cloudMeta = normalizeMeta(rows[0]?.lineup_json || {});
  return true;
}

async function saveCloudMeta() {
  const id = formationMetaId();
  if (!id) return;
  const payload = {
    lineup_id: id,
    lineup_json: {
      formationId: Number.isInteger(cloudMeta.formationId) ? cloudMeta.formationId : null,
      ownedFormationIds: Array.isArray(cloudMeta.ownedFormationIds) ? cloudMeta.ownedFormationIds : [],
      coach: cloudMeta.coach || null,
    },
    updated_at: new Date().toISOString(),
  };
  await supabaseRequest(`${SUPABASE_TABLE}?on_conflict=lineup_id`, {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=representation" },
    body: JSON.stringify(payload),
  });
}

function logout() {
  saveCloudConfig("");
  updateMenuState();
}

function getByPath(obj, path) {
  return path.split(".").reduce((acc, k) => (acc == null ? undefined : acc[k]), obj);
}

function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`;
}

function avg(v) {
  return Number(v || 0).toFixed(2);
}

function goalsPer7(v) {
  return Number(v || 0).toFixed(2);
}

function goalsCount(v) {
  const n = Number(v || 0);
  return Number.isFinite(n) ? String(Math.trunc(n)) : "-";
}

function metricLabel(metric) {
  return METRIC_LABELS[metric] || metric;
}

function detailMetricLabel(metric) {
  return DETAIL_METRIC_LABELS[metric] || metric;
}

function syncProfileSideWidthFromPlayers(rows) {
  const list = Array.isArray(rows) ? rows : [];
  if (!list.length) return;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const base = parseFloat(getComputedStyle(document.documentElement).fontSize || "16");
  const fontPx = Math.max(10, base * 0.68);
  ctx.font = `400 ${fontPx}px -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif`;
  const maxValueWidth = list.reduce((m, p) => {
    const v = String(p?.playType || "-");
    return Math.max(m, ctx.measureText(v).width);
  }, 0);
  const sideWidth = Math.min(144, Math.max(124, Math.ceil(maxValueWidth + 14)));
  document.documentElement.style.setProperty("--profile-side-width", `${sideWidth}px`);
}

function normalizeCategory(value) {
  const c = String(value || "").trim().toUpperCase();
  return c || "-";
}

function latestHistoryStart(player, key) {
  const rows = Array.isArray(player?.[key]) ? player[key] : [];
  let latest = "";
  rows.forEach((row) => {
    const s = String(row?.start || "");
    if (s > latest) latest = s;
  });
  return latest;
}

function badgeCategoryByRecency(player, fallbackCategory) {
  const category = normalizeCategory(fallbackCategory);
  if (category !== "CM/SS") return category;
  const ssLatest = latestHistoryStart(player, "scoutHistory");
  const cmLatest = latestHistoryStart(player, "cmHistory");
  if (cmLatest && !ssLatest) return "CM";
  if (ssLatest && !cmLatest) return "SS";
  if (!cmLatest && !ssLatest) return "SS";
  return cmLatest > ssLatest ? "CM" : "SS";
}

function getCcCategoryLabelByPlayerId(playerId) {
  const id = Number(playerId);
  if (!Number.isInteger(id)) return "-";
  return normalizeCategory(playerCategoryById.get(id));
}

function categoryBadgeClass(category, rate = null) {
  const c = normalizeCategory(category);
  if (c === "CC") return "cat-cc";
  if (c === "SS") return "cat-ss";
  if (c === "CM") return "cat-cm";
  if (c === "CM/SS") return "cat-cmss";
  if (c === "NR") {
    const r = Number(rate);
    if (r === 7) return "cat-nr-r7";
    if (r === 5 || r === 6) return "cat-nr-r56";
    if (r === 4) return "cat-nr-r4";
    return "cat-nr-r13";
  }
  return "cat-na";
}

function categoryBadgeHtmlByPlayerId(playerId) {
  const id = Number(playerId);
  const rawCategory = getCcCategoryLabelByPlayerId(id);
  const player = playersById.get(id);
  const category = player ? badgeCategoryByRecency(player, rawCategory) : rawCategory;
  const rate = player ? Number(playerRateById.get(id)) : 0;
  const c = normalizeCategory(category);
  return `<span class="badge type-badge ${categoryBadgeClass(c, rate)}">${c}</span>`;
}

function categoryBadgeHtml(category, playerId = null) {
  const id = Number(playerId);
  const player = playersById.get(id);
  const rawCategory = normalizeCategory(category || getCcCategoryLabelByPlayerId(id));
  const badgeCategory = player ? badgeCategoryByRecency(player, rawCategory) : rawCategory;
  const rate = player ? Number(playerRateById.get(id)) : 0;
  const c = normalizeCategory(badgeCategory);
  return `<span class="badge type-badge ${categoryBadgeClass(c, rate)}">${c}</span>`;
}

function getCategory(player) {
  if (player?.category) return String(player.category);
  return getCcCategoryLabelByPlayerId(player?.id);
}

function typeLabelByPlayer(player) {
  return badgeCategoryByRecency(player, getCategory(player));
}

function typeClassByPlayer(player) {
  const typeLabel = normalizeCategory(typeLabelByPlayer(player));
  if (typeLabel === "NR") {
    const rate = Number(player?.rate);
    return categoryBadgeClass(typeLabel, rate);
  }
  return categoryBadgeClass(typeLabel);
}

function positionClass(position) {
  const pos = String(position || "").toUpperCase();
  if (pos === "GK") return "pos-gk";
  if (pos === "DF") return "pos-df";
  if (pos === "MF") return "pos-mf";
  if (pos === "FW") return "pos-fw";
  return "";
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[ch]));
}

function formatFormationYearLabel(year, stride) {
  const y = Number(year);
  const s = Number(stride);
  if (!Number.isFinite(y) || y <= 0) return "";
  if (s === 1) {
    const next = String((y + 1) % 100).padStart(2, "0");
    return `${y}-${next}`;
  }
  return String(y);
}

function toSearchNormalized(value) {
  const base = String(value || "").toLowerCase().normalize("NFKC");
  const hira = base.replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60));
  return hira.replace(/[・･\.\-‐‑‒–—―ー\s]/g, "");
}

function includesSearch(haystack, needle) {
  if (!needle) return true;
  return toSearchNormalized(haystack).includes(needle);
}

function formationFullName(f) {
  const yearLabel = formatFormationYearLabel(f?.year, f?.stride);
  return `${String(f?.name || "")}${yearLabel ? ` ${yearLabel}` : ""}`.trim();
}

function findFormationNameSuggestions(rawQuery, limit = 3) {
  const q = toSearchNormalized(rawQuery);
  if (!q) return [];
  const seen = new Set();
  const scored = [];
  formations.forEach((f) => {
    const label = formationFullName(f);
    if (!label || seen.has(label)) return;
    seen.add(label);
    const norm = toSearchNormalized(label);
    const idx = norm.indexOf(q);
    if (idx < 0) return;
    scored.push({ label, idx, len: norm.length });
  });
  return scored
    .sort((a, b) => a.idx - b.idx || a.len - b.len || a.label.localeCompare(b.label, "ja"))
    .slice(0, limit)
    .map((x) => x.label);
}

function renderFormationNameSuggest() {
  if (!els.formationNameSuggest || !els.formationNameQuery) return;
  const list = findFormationNameSuggestions(els.formationNameQuery.value);
  if (!list.length) {
    els.formationNameSuggest.hidden = true;
    els.formationNameSuggest.innerHTML = "";
    return;
  }
  els.formationNameSuggest.hidden = false;
  els.formationNameSuggest.innerHTML = list
    .map((label) => `<button type="button" class="name-suggest-item" data-name="${label}">${label}</button>`)
    .join("");
}

function nationNameFromId(nationId) {
  const id = Number(nationId);
  if (!Number.isInteger(id)) return "-";
  for (const p of playersById.values()) {
    if (Number(p?.nationId) === id) {
      const n = String(p?.nationality || "").trim();
      if (n) return n;
    }
  }
  return "-";
}

function buildSortOptions() {
  if (!els.sortKey) return;
  els.sortKey.innerHTML = SORT_OPTIONS.map((o) => `<option value="${o.key}">${o.label}</option>`).join("");
  els.sortKey.value = "cc.usageRate";
}

function buildCoachFilters() {
  if (!els.undCoachFilter || !els.avlCoachFilter) return;
  const options = coaches
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, "ja"))
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
  const html = `<option value="">-</option>${options}`;
  els.undCoachFilter.innerHTML = html;
  els.avlCoachFilter.innerHTML = html;
}

function applyFilterAndSort() {
  const sortKey = els.sortKey?.value || "cc.usageRate";
  const sortDir = els.sortDir?.value === "asc" ? 1 : -1;
  const undCoachId = Number(els.undCoachFilter?.value || 0);
  const avlCoachId = Number(els.avlCoachFilter?.value || 0);
  const nameQuery = toSearchNormalized(els.formationNameQuery?.value || "");

  let rows = formations.slice();
  if (nameQuery) {
    rows = rows.filter((f) => {
      const label = formationFullName(f);
      return includesSearch(label, nameQuery);
    });
  }
  if (undCoachId > 0) {
    rows = rows.filter((f) => {
      const list = f.coaches?.depth4 || [];
      return list.some((c) => Number(c?.id) === undCoachId || Number(c?.coachId) === undCoachId);
    });
  }
  if (avlCoachId > 0) {
    rows = rows.filter((f) => {
      const list = f.coaches?.obtainable || [];
      return list.some((c) => Number(c?.id) === avlCoachId || Number(c?.coachId) === avlCoachId);
    });
  }

  rows.sort((a, b) => {
    const va = getByPath(a, sortKey);
    const vb = getByPath(b, sortKey);
    const na = Number(va);
    const nb = Number(vb);
    if (Number.isFinite(na) && Number.isFinite(nb)) {
      if (na !== nb) return (na - nb) * sortDir;
      return a.name.localeCompare(b.name, "ja");
    }
    const sa = String(va || "");
    const sb = String(vb || "");
    const cmp = sa.localeCompare(sb, "ja");
    if (cmp !== 0) return cmp * sortDir;
    return a.name.localeCompare(b.name, "ja");
  });

  filteredAndSorted = rows;
}

function formationCardHtml(f) {
  const yearText = formatFormationYearLabel(f.year, f.stride);
  return `
    <button type="button" class="formation-item" data-formation-id="${f.id}">
      <div class="formation-item-head">
        <div class="formation-name-wrap">
          <strong>${f.name}</strong>
          ${yearText ? `<span class="formation-year">${yearText}</span>` : ""}
        </div>
        <span class="formation-system">${f.system || "-"}</span>
      </div>
      <div class="formation-item-metrics">
        <div class="formation-item-metrics-row formation-item-metrics-main">
          <span>Usage ${pct(f.cc.usageRate)}</span>
          <span>Win ${pct(f.cc.winRate)}</span>
        </div>
        <div class="formation-item-metrics-row formation-item-metrics-params">
          <span>SPD ${f.params.spd}</span>
          <span>TEC ${f.params.tec}</span>
          <span>PWR ${f.params.pwr}</span>
          <span>OFF ${f.params.off}</span>
          <span>DEF ${f.params.def}</span>
          <span>MID ${f.params.mid}</span>
          <span>TTL ${f.params.ttl}</span>
          <span>STM ${f.params.stm}</span>
          <span>DIF ${f.params.dif}</span>
        </div>
      </div>
    </button>
  `;
}

function renderList() {
  if (!els.formationList) return;
  applyFilterAndSort();
  els.formationList.innerHTML = filteredAndSorted.map(formationCardHtml).join("");
  if (els.formationCount) {
    els.formationCount.textContent = `${filteredAndSorted.length} results`;
  }
  renderFormationNameSuggest();
}

function renderFormationPitch(positions, formationId) {
  const minX = 1;
  const maxX = 321;
  const minY = 2;
  const maxY = 337;
  const padLeft = 16;
  const padRight = 16;
  const padTop = 18;
  const padBottom = 10;
  const markerSrc = `./images/formation/${formationId}@2x.png`;
  const keySlots = new Set(
    (currentFormation?.keyPositions || [])
      .map((k) => Number(k?.slot))
      .filter((n) => Number.isInteger(n) && n > 0)
  );
  return `
    <div class="formation-pitch">
      ${positions
        .map((p) => {
          const nx = (p.x - minX) / (maxX - minX);
          const ny = (p.y - minY) / (maxY - minY);
          const left = padLeft + nx * (100 - padLeft - padRight);
          const top = padTop + ny * (100 - padTop - padBottom);
          return `
            <button type="button" class="formation-slot-point" data-slot="${p.slot}" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%">
              <img class="formation-slot-icon" src="${markerSrc}" alt="" />
              ${keySlots.has(Number(p.slot)) ? `<span class="formation-key-star" aria-hidden="true">★</span>` : ""}
              <span class="formation-slot-label">${p.slot}</span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderCoachesList(list) {
  if (!Array.isArray(list) || !list.length) return "-";
  return list
    .map((c) => `<button type="button" class="inline-pill coach-link-pill" data-coach-id="${Number(c?.id || c?.coachId || 0)}">${c.name}</button>`)
    .join(" ");
}

function renderKeyPositions(keyPositions) {
  if (!Array.isArray(keyPositions) || !keyPositions.length) return "<p class=\"dim\">No key position data.</p>";
  return `
    <div class="formation-kp-list">
      ${keyPositions
        .map(
          (k) => `
            <div class="formation-kp-item">
              <div class="formation-kp-title">Key ${k.rank} / Slot ${k.slot} ${k.subtitle ? `(${k.subtitle})` : ""}</div>
              <div class="formation-kp-desc">${k.description || "-"}</div>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderFormationDescription(formation) {
  const description = String(formation?.description || "").trim();
  if (!description) return `<p class="dim">No description data.</p>`;
  return `<div class="formation-description">${escapeHtml(description)}</div>`;
}

function renderSlotTop(slotStats, mode = "usage") {
  if (mode === "best") {
    return renderBestTeam(currentFormation);
  }
  if (mode === "model") {
    return renderModelSlots(currentFormation);
  }
  if (mode === "team") {
    return renderRepresentativeTeam(currentFormation);
  }
  const slots = Array.from({ length: 11 }, (_, i) => i + 1);
  const keySlots = new Set(
    (currentFormation?.keyPositions || [])
      .map((k) => Number(k?.slot))
      .filter((n) => Number.isInteger(n) && n > 0)
  );
  return `
    <div class="formation-slot-top-list">
      ${slots
        .map((slot) => {
          const rows = sortSlotRows(slotStats?.[String(slot)] || [], mode);
          const top = rows[0] || null;
          const slotLabel = `Slot ${slot}${keySlots.has(slot) ? ` <span class="slot-top-key-star" aria-hidden="true">★</span>` : ""}`;
          if (!top) {
            return `
              <button type="button" class="slot-top-row" data-slot="${slot}">
                <span class="slot-top-slotno">${slotLabel}</span>
                <div class="slot-top-thumb slot-top-thumb-empty"></div>
                <div class="slot-top-meta">
                  <strong class="slot-top-name">No data</strong>
                  <span class="dim">-</span>
                </div>
              </button>
            `;
          }
          const imgSrc = `./images/chara/players/static/${top.playerId}.gif`;
          return `
            <button type="button" class="slot-top-row" data-slot="${slot}">
              <span class="slot-top-slotno">${slotLabel}</span>
              <div class="slot-top-thumb">
                <img loading="lazy" src="${imgSrc}" alt="${top.playerName}" />
              </div>
              <div class="slot-top-meta">
                <span class="slot-top-titleline">
                  <strong class="slot-top-name">${top.playerName}</strong>
                  ${categoryBadgeHtmlByPlayerId(top.playerId)}
                </span>
                <span class="slot-top-statline with-goals">
                  <span class="slot-top-stat-text">Usage ${pct(top.usageRate)} / Avg ${avg(top.avgPts)} / Goals ${goalsPer7(top.goalsPer7)}</span>
                </span>
              </div>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function rohmCategoryClass(category) {
  const c = String(category || "");
  if (c === "無") return "cat-rohm-none";
  if (c === "銅" || c === "引退(銅)" || c === "CP銅") return "cat-rohm-bronze";
  if (c === "銀" || c === "引退(銀)" || c === "CP銀") return "cat-rohm-silver";
  if (c === "金" || c === "引退(金)" || c === "CP金") return "cat-rohm-gold";
  if (c === "PS") return "cat-ss";
  if (c === "CM") return "cat-cm";
  if (c === "CC") return "cat-cc";
  return "cat-rohm-other";
}

function rohmCategoryBadgeHtml(row) {
  const playerId = Number(row?.localPlayerId || 0);
  if (Number.isInteger(playerId) && playerId > 0) {
    return categoryBadgeHtmlByPlayerId(playerId);
  }
  const category = String(row?.rohmCategory || "-");
  return `<span class="badge type-badge rohm-category-badge ${rohmCategoryClass(category)}">${escapeHtml(category)}</span>`;
}

function getRohmSlotData(formation, slot) {
  const fid = String(Number(formation?.id || 0));
  const sid = String(Number(slot || 0));
  return rohmSlotData?.formations?.[fid]?.slots?.[sid] || null;
}

function loadRohmSlotData() {
  if (rohmSlotData) return Promise.resolve(rohmSlotData);
  if (rohmSlotDataPromise) return rohmSlotDataPromise;
  rohmSlotDataError = "";
  rohmSlotDataPromise = fetch("./rohm_slot_data.json")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      rohmSlotData = data;
      return data;
    })
    .catch((err) => {
      rohmSlotDataError = err?.message || "failed";
      throw err;
    })
    .finally(() => {
      rohmSlotDataPromise = null;
    });
  return rohmSlotDataPromise;
}

function renderModelSlots(formation) {
  const slots = Array.from({ length: 11 }, (_, i) => i + 1);
  const keySlots = new Set(
    (formation?.keyPositions || [])
      .map((k) => Number(k?.slot))
      .filter((n) => Number.isInteger(n) && n > 0)
  );
  const rowsBySlot = new Map(
    (Array.isArray(formation?.modelSlots) ? formation.modelSlots : [])
      .map((row) => [Number(row?.slot), row])
  );
  return `
    <div class="formation-slot-top-list">
      ${slots.map((slot) => {
        const row = rowsBySlot.get(slot);
        const slotLabel = `Slot ${slot}${keySlots.has(slot) ? ` <span class="slot-top-key-star" aria-hidden="true">★</span>` : ""}`;
        if (!row) {
          return `
            <div class="slot-top-row model-slot-row is-empty">
              <span class="slot-top-slotno">${slotLabel}</span>
              <div class="slot-top-thumb slot-top-thumb-empty"></div>
              <div class="slot-top-meta">
                <strong class="slot-top-name">No model data</strong>
                <span class="dim">-</span>
              </div>
            </div>
          `;
        }
        const playerId = Number(row?.playerId || 0);
        const player = playersById.get(playerId);
        const isLinked = playerId > 0 && player;
        const modelName = row?.modelName || player?.modelPlayer || row?.sourceName || "-";
        const playerName = player?.name || row?.playerName || row?.playerFullName || (playerId ? `Player ${playerId}` : "");
        const linkedBody = isLinked
          ? `
            <button type="button" class="slot-top-row model-slot-row" data-player-id="${playerId}">
              <span class="slot-top-slotno">${slotLabel}</span>
              <div class="slot-top-thumb">
                <img loading="lazy" src="./images/chara/players/static/${playerId}.gif" alt="${playerName}" />
              </div>
              <div class="slot-top-meta">
                <span class="slot-top-titleline">
                  <strong class="slot-top-name">${playerName}</strong>
                  ${categoryBadgeHtml(player?.category || row?.category, playerId)}
                </span>
                <span class="slot-top-statline model-slot-statline">
                  <span class="slot-top-stat-text">${modelName}</span>
                </span>
              </div>
            </button>
          `
          : `
            <div class="slot-top-row model-slot-row is-empty">
              <span class="slot-top-slotno">${slotLabel}</span>
              <div class="slot-top-thumb slot-top-thumb-empty"></div>
              <div class="slot-top-meta">
                <span class="slot-top-titleline">
                  <strong class="slot-top-name">No linked player</strong>
                </span>
                <span class="slot-top-statline model-slot-statline">
                  <span class="slot-top-stat-text">${modelName}</span>
                </span>
              </div>
            </div>
          `;
        return linkedBody;
      }).join("")}
    </div>
  `;
}

function renderBestTeam(formation) {
  const teams = Array.isArray(formation?.bestTeams) ? formation.bestTeams : [];
  if (!teams.length) {
    return `<p class="dim">No best team data.</p>`;
  }
  const fid = Number(formation?.id);
  const savedIndex = bestTeamIndexByFormation.get(fid) || 0;
  const index = Math.max(0, Math.min(teams.length - 1, savedIndex));
  const team = teams[index] || teams[0];
  const members = Array.isArray(team?.members)
    ? team.members.slice().sort((a, b) => Number(a?.slot || 0) - Number(b?.slot || 0)).slice(0, 11)
    : [];
  const wins = Number(team?.wins || 0);
  const draws = Number(team?.draws || 0);
  const losses = Number(team?.losses || 0);
  const goalDiff = Number(team?.goalDiff || 0);
  const goalsFor = Number(team?.goalsFor || 0);
  const goalsAgainst = Number(team?.goalsAgainst || 0);
  const finish = String(team?.finish || "-");
  const finishDisplay = finish === "1" ? "Champion" : finish;
  const coach = team?.coach || {};
  const keySlots = new Set(
    (formation?.keyPositions || [])
      .map((k) => Number(k?.slot))
      .filter((n) => Number.isInteger(n) && n > 0)
  );
  const rankTabs = teams.length > 1
    ? `<div class="best-team-rank-switch" role="group" aria-label="Top Teams rank">
        ${teams.map((row, idx) => `
          <button type="button" class="slot-top-sort-btn${idx === index ? " is-on" : ""}" data-best-team-index="${idx}">
            #${Number(row?.rank || idx + 1)}
          </button>
        `).join("")}
      </div>`
    : "";
  return `
    <div class="best-team-summary">
      <div class="best-team-title-row">
        <div>
          <strong>${team?.teamName || "-"}</strong>
          <span class="dim">Season ${Number(team?.season || 0)}</span>
        </div>
        ${rankTabs}
      </div>
      <div class="best-team-score-grid">
        <span><strong>${finishDisplay}</strong></span>
        <span>Record <strong>${wins}-${draws}-${losses}</strong></span>
        <span>Avg Pts <strong>${avg(team?.avgPlayerPts)}</strong></span>
        <span>Goals For <strong>${Number.isFinite(goalsFor) ? goalsFor : "-"}</strong></span>
        <span>Goals Against <strong>${Number.isFinite(goalsAgainst) ? goalsAgainst : "-"}</strong></span>
        <span>Goal Diff <strong>${Number.isFinite(goalDiff) ? (goalDiff >= 0 ? `+${goalDiff}` : goalDiff) : "-"}</strong></span>
      </div>
      ${Number(coach?.id || 0) > 0 ? `
        <button type="button" class="best-team-coach" data-coach-id="${Number(coach.id)}">
          Coach: ${coach.name || "-"} / Avg ${avg(coach.avgPts)} / Total ${Number(coach.ptsSum || 0).toFixed(0)}
        </button>
      ` : `<p class="dim">No coach data.</p>`}
    </div>
    <div class="formation-slot-top-list">
      ${members.map((member) => {
        const playerId = Number(member?.playerId || 0);
        const slot = Number(member?.slot || 0);
        const slotLabel = `Slot ${slot}${keySlots.has(slot) ? ` <span class="slot-top-key-star" aria-hidden="true">★</span>` : ""}`;
        const imgSrc = `./images/chara/players/static/${playerId}.gif`;
        return `
          <button type="button" class="slot-top-row best-team-player-row" data-player-id="${playerId}">
            <span class="slot-top-slotno">${slotLabel}</span>
            <div class="slot-top-thumb">
              <img loading="lazy" src="${imgSrc}" alt="${member?.playerName || ""}" />
            </div>
            <div class="slot-top-meta">
              <span class="slot-top-titleline">
                <strong class="slot-top-name">${member?.playerName || "-"}</strong>
                ${categoryBadgeHtmlByPlayerId(playerId)}
              </span>
              <span class="slot-top-statline with-goals">
                <span class="slot-top-stat-text">Usage ${pct(member?.usageRate)} / Avg ${avg(member?.avgPts)} / Goals ${goalsCount(member?.goals)}</span>
              </span>
            </div>
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function renderRepresentativeTeam(formation) {
  if (!formation || typeof formation !== "object") {
    return `<p class="dim">No representative team data.</p>`;
  }
  const cc = formation.cc || {};
  const coach = Array.isArray(formation.coachStats) && formation.coachStats.length
    ? formation.coachStats.slice().sort((a, b) =>
        Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
        || Number(b?.uses || 0) - Number(a?.uses || 0)
        || String(a?.coachName || "").localeCompare(String(b?.coachName || ""), "ja")
      )[0]
    : null;
  const topPlayers = Object.keys(formation.slotTop || {})
    .map((slot) => ({ slot: Number(slot), ...(formation.slotTop?.[slot] || {}) }))
    .filter((row) => Number.isInteger(row.slot))
    .sort((a, b) => a.slot - b.slot);
  if (!topPlayers.length) {
    return `<p class="dim">No representative lineup available.</p>`;
  }
  return `
    <div class="formation-team-summary">
      <p class="dim">CC usage ${pct(cc.usageRate)} / wins ${Number(cc.wins || 0)} / win rate ${pct(cc.winRate)}</p>
      ${coach ? `<p><strong>Representative Coach:</strong> ${coach.coachName} (${pct(coach.usageRate)} uses, avg ${avg(coach.avgPts)})</p>` : `<p class="dim">No coach ranking available.</p>`}
    </div>
    <div class="formation-slot-top-list">
      ${topPlayers
        .map((top) => {
          const slotLabel = `Slot ${top.slot}`;
          const imgSrc = `./images/chara/players/static/${top.playerId}.gif`;
          return `
            <button type="button" class="slot-top-row coach-top-row" disabled>
              <span class="slot-top-slotno">${slotLabel}</span>
              <div class="slot-top-thumb">
                <img loading="lazy" src="${imgSrc}" alt="${top.playerName}" />
              </div>
              <div class="slot-top-meta">
                <strong class="slot-top-name">${top.playerName}</strong>
                <span class="slot-top-statline">
                  ${categoryBadgeHtmlByPlayerId(top.playerId)}
                  <span>${pct(top.usageRate)} / Avg ${avg(top.avgPts)}</span>
                </span>
              </div>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function sortCoachRankingRows(coachStats, mode = "usage") {
  const rows = Array.isArray(coachStats) ? coachStats : [];
  const sorters = {
    usage: (a, b) =>
      Number(b?.usageRate || 0) - Number(a?.usageRate || 0)
      || Number(b?.uses || 0) - Number(a?.uses || 0)
      || Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
      || String(a?.coachName || "").localeCompare(String(b?.coachName || ""), "ja"),
    avg: (a, b) =>
      Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
      || Number(b?.uses || 0) - Number(a?.uses || 0)
      || Number(b?.usageRate || 0) - Number(a?.usageRate || 0)
      || String(a?.coachName || "").localeCompare(String(b?.coachName || ""), "ja"),
    stats: (a, b) =>
      Number(b?.winRate || 0) - Number(a?.winRate || 0)
      || Number(b?.uses || 0) - Number(a?.uses || 0)
      || (Number(b?.avgGoalsFor || 0) - Number(b?.avgGoalsAgainst || 0))
        - (Number(a?.avgGoalsFor || 0) - Number(a?.avgGoalsAgainst || 0))
      || Number(b?.avgGoalsFor || 0) - Number(a?.avgGoalsFor || 0)
      || String(a?.coachName || "").localeCompare(String(b?.coachName || ""), "ja"),
  };
  const sorter = sorters[mode] || sorters.usage;
  return rows.slice().sort(sorter);
}

function coachRankingStatLine(coach, mode = "usage") {
  if (mode === "avg") {
    return `Avg ${avg(coach?.avgPts)}`;
  }
  if (mode === "stats") {
    return `Win ${pct(coach?.winRate)} / Goals ${avg(coach?.avgGoalsFor)} / Against ${avg(coach?.avgGoalsAgainst)}`;
  }
  return `Usage ${pct(coach?.usageRate)} (${Number(coach?.uses || 0)} matches)`;
}

function renderCoachRanking(coachStats, mode = "usage") {
  const rows = sortCoachRankingRows(coachStats, mode);
  if (!rows.length) {
    return `<p class="dim">No coach usage data.</p>`;
  }
  return `
    <div class="formation-slot-top-list">
      ${rows
        .map((c, idx) => {
          const imgSrc = `./images/chara/headcoaches/static/${c.coachId}@2x.gif`;
          return `
            <button type="button" class="slot-top-row coach-top-row" data-coach-id="${Number(c.coachId)}">
              <span class="slot-top-slotno">#${idx + 1}</span>
              <div class="slot-top-thumb">
                <img loading="lazy" src="${imgSrc}" alt="${c.coachName}" />
              </div>
              <div class="slot-top-meta">
                <strong class="slot-top-name">${c.coachName}</strong>
                <span>${coachRankingStatLine(c, mode)}</span>
              </div>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function coreTotal(metrics) {
  return (metrics?.["スピ"] || 0) + (metrics?.["テク"] || 0) + (metrics?.["パワ"] || 0);
}

function getStrengthMetrics(player) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  if (!periods.length) return ["スピ", "テク"];
  const totalByMetric = { スピ: 0, テク: 0, パワ: 0 };
  periods.forEach((period) => {
    const metrics = period?.metrics || {};
    CORE_METRICS.forEach((metric) => {
      totalByMetric[metric] += metrics[metric] || 0;
    });
  });
  const maxOverall = Math.max(...periods.map((p) => coreTotal(p?.metrics || {})));
  const reference = periods.find((p) => coreTotal(p?.metrics || {}) === maxOverall) || periods[0];
  const refMetrics = reference?.metrics || {};
  const refRank = CORE_METRICS
    .map((metric) => ({ metric, value: refMetrics[metric] || 0 }))
    .sort((a, b) => {
      if (b.value !== a.value) return b.value - a.value;
      return CORE_METRICS.indexOf(a.metric) - CORE_METRICS.indexOf(b.metric);
    });
  const first = refRank[0];
  const second = refRank[1];
  const third = refRank[2];
  if (first.value === second.value && second.value === third.value) return [...CORE_METRICS];
  if (second.value === third.value && first.value > second.value) {
    const tie = [second.metric, third.metric].sort((a, b) => {
      if (totalByMetric[b] !== totalByMetric[a]) return totalByMetric[b] - totalByMetric[a];
      return CORE_METRICS.indexOf(a) - CORE_METRICS.indexOf(b);
    });
    return [first.metric, tie[0]];
  }
  return [first.metric, second.metric];
}

function getPeakMetrics(player) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  if (!periods.length) return player?.maxMetrics || {};
  const strengthMetrics = getStrengthMetrics(player);
  let best = periods[0]?.metrics || {};
  let bestScore = strengthMetrics.reduce((s, m) => s + (best?.[m] || 0), 0);
  for (let i = 1; i < periods.length; i += 1) {
    const m = periods[i]?.metrics || {};
    const score = strengthMetrics.reduce((s, k) => s + (m?.[k] || 0), 0);
    if (score > bestScore) {
      best = m;
      bestScore = score;
    }
  }
  return best;
}

function getPeakTimeline(player) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  if (!periods.length) return [];
  const strengthMetrics = getStrengthMetrics(player);
  const scored = periods.map((p) => {
    const m = p?.metrics || {};
    const score = strengthMetrics.reduce((s, k) => s + (m?.[k] || 0), 0);
    return { season: p?.season, score };
  });
  const maxScore = Math.max(...scored.map((x) => x.score));
  return scored
    .map((x) => {
      if (!x.season) return null;
      if (x.score === maxScore) return { season: x.season, tier: "peak-main" };
      if (x.score === maxScore - 1) return { season: x.season, tier: "peak-sub" };
      if (x.score === maxScore - 2) return { season: x.season, tier: "peak-near" };
      return null;
    })
    .filter(Boolean);
}

function positionHeatmapsHtml(player) {
  const segments = Array.isArray(player?.positionHeatmaps) ? player.positionHeatmaps : [];
  if (!segments.length) return "";
  const isGK = (player.position || "").toUpperCase() === "GK";
  const singleClass = segments.length === 1 ? "single" : "multi";
  const passiveCodes = new Set([13, 15, 16, 17, 18]);
  const hiddenVal = (seg, key, fallback = null) => {
    const v = seg?.hiddenR?.[key];
    if (v == null) return fallback;
    const n = Number(v);
    return Number.isFinite(n) ? Math.round(n) : fallback;
  };
  const codeVal = (seg, grid, code) => {
    if (code <= 12) {
      const r = Math.floor((code - 1) / 3);
      const c = (code - 1) % 3;
      return grid?.[r]?.[c] ?? null;
    }
    if (code <= 15) return hiddenVal(seg, `R${code}`, grid?.[4]?.[code - 13] ?? null);
    return hiddenVal(seg, `R${code}`, null);
  };
  const items = segments.map((seg) => {
    const label = seg?.label || "";
    const grid = Array.isArray(seg?.grid) ? seg.grid : [];
    const cells = [];
    for (let r = 0; r < 6; r += 1) {
      for (let c = 0; c < 3; c += 1) {
        const code = r * 3 + c + 1;
        const raw = codeVal(seg, grid, code);
        const hasVal = raw != null;
        const n = Math.max(1, Math.min(7, Number(raw) || 1));
        const classes = ["hm-cell"];
        classes.push(`hm-code-${code}`);
        if (passiveCodes.has(code)) {
          classes.push("hm-dim");
        } else if (hasVal) {
          classes.push(`hm-l${n}`);
        }
        cells.push(`<div class="${classes.join(" ")}" style="--r:${r};--c:${c}">${hasVal ? Math.round(Number(raw)) : "-"}</div>`);
      }
    }
    return `
      <div class="pos-heatmap-seg">
        <div class="pos-heatmap-label">${label}</div>
        <div class="pitch-map ${isGK ? "is-gk" : "is-fp"}">
          <div class="pitch-lines"></div>
          <div class="hm-grid">${cells.join("")}</div>
        </div>
      </div>
    `;
  }).join("");
  return `
    <div class="pos-heatmaps-scroll ${singleClass}">
      <div class="pos-heatmaps-track">${items}</div>
    </div>
  `;
}

function periodTableHtml(player, staticImg, actionImg) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  const header = METRICS.map((m) => `<th>${detailMetricLabel(m)}</th>`).join("");
  const tiers = new Map(getPeakTimeline(player).map((x) => [x.season, x.tier]));
  const rows = periods.map((period) => {
    const metrics = period?.metrics || {};
    const values = METRICS.map((m) => `<td>${metrics[m] ?? "-"}</td>`).join("");
    const season = period?.season || "-";
    const tierClass = tiers.get(season) || "peak-none";
    return `<tr><th class="season-cell ${tierClass}">${season}</th>${values}</tr>`;
  }).join("");
  return `
    <div class="expanded-view">
      <div class="expanded-media">
        <div class="thumbs">
          <img loading="lazy" src="${staticImg}" alt="${player.name} static" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} action" />
        </div>
        ${positionHeatmapsHtml(player)}
      </div>
      <div class="periods-scroll">
        <table class="periods-table">
          <thead><tr><th>期</th>${header}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function profileViewHtml(player, staticImg, actionImg) {
  const nationality = player.nationality || (player.nationId != null ? `国籍ID:${player.nationId}` : "-");
  const modelPlayer = player.modelPlayer || "-";
  const modelClass = modelPlayer !== "-"
    ? (modelPlayer.length >= 18 ? " model-xsmall" : modelPlayer.length >= 13 ? " model-small" : "")
    : "";
  const playType = player.playType || "-";
  const description = (player.description || "").trim() || "説明なし";
  return `
    <div class="profile-view">
      <div class="media-row">
        <div class="thumbs">
          <img loading="lazy" src="${staticImg}" alt="${player.name} static" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} action" />
        </div>
        <div class="profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nationality}</span></div>
          <div class="profile-item"><span class="k">モデル</span><span class="v${modelClass}">${modelPlayer}</span></div>
          <div class="profile-item"><span class="k">タイプ</span><span class="v">${playType}</span></div>
        </div>
      </div>
      <div class="profile-description-wrap">
        <div class="profile-description-title">PLAYER DETAIL</div>
        <div class="profile-description">${description}</div>
      </div>
    </div>
  `;
}

function getCardViewMode(playerId) {
  return cardViewModeById.get(playerId) || 0;
}

function cardTabsHtml(playerId, viewMode) {
  const tabs = [
    { mode: 0, label: "PRM" },
    { mode: 1, label: "DTL" },
    { mode: 2, label: "SCR" },
  ];
  return `
    <div class="card-tabs" role="tablist" aria-label="Card View Tabs">
      ${tabs.map((t) => `
        <button type="button" class="card-tab${viewMode === t.mode ? " is-active" : ""}" data-player-id="${playerId}" data-mode="${t.mode}" role="tab" aria-selected="${viewMode === t.mode ? "true" : "false"}">${t.label}</button>
      `).join("")}
    </div>
  `;
}

function swipeDeckHtml(viewMode, normalViewHtml, detailViewHtml, thirdViewHtml) {
  return `
    <div class="swipe-deck" style="--mode:${viewMode}">
      <div class="swipe-track">
        <section class="swipe-pane">${normalViewHtml}</section>
        <section class="swipe-pane">${detailViewHtml}</section>
        <section class="swipe-pane">${thirdViewHtml}</section>
      </div>
    </div>
  `;
}

function playerCardHtml(player) {
  const staticImg = `./images/chara/players/static/${player.id}.gif`;
  const actionImg = `./images/chara/players/action/${player.id}.gif`;
  const displayMetrics = getPeakMetrics(player);
  const viewMode = getCardViewMode(player.id);
  const peakTimeline = getPeakTimeline(player);
  const peakHtml = peakTimeline.length
    ? peakTimeline.map((x) => `<span class="peak-chip ${x.tier}">${x.season}</span>`).join("")
    : `<span class="peak-chip peak-near">-</span>`;
  const metricBox = (metric) => {
    const v = displayMetrics?.[metric];
    const value = v == null ? 0 : v;
    const bounded = Math.max(0, Math.min(10, Math.round(value)));
    const metricClass =
      metric === "スピ" ? "m-speed" :
      metric === "テク" ? "m-tech" :
      metric === "パワ" ? "m-power" :
      metric === "個性" ? "m-unique" : "";
    const cells = Array.from({ length: 10 }, (_, i) => `<span class="gauge-cell${i < bounded ? " on" : ""}"></span>`).join("");
    return `
      <div class="metric-box ${metricClass}">
        <span class="metric-key">${metricLabel(metric)}</span>
        <div class="metric-body">
          <div class="gauge">${cells}</div>
          <span class="metric-num">${v == null ? "-" : v}</span>
        </div>
      </div>
    `;
  };
  const typeLabel = typeLabelByPlayer(player);
  const typeClass = typeClassByPlayer(player);
  const pos = (player.position || "-").toUpperCase();
  const posClass = positionClass(pos);
  const mainMetrics = ["スピ", "テク", "パワ", "個性"];
  const group1 = ["スタ", "ラフ", "人気"];
  const group2 = ["PK", "FK", "CK", "CP"];
  const mind = {
    zisei: displayMetrics?.["知性"] ?? 0,
    kansei: displayMetrics?.["感性"] ?? 0,
    kojin: displayMetrics?.["個人"] ?? 0,
    soshiki: displayMetrics?.["組織"] ?? 0,
  };
  const cx = 70;
  const cy = 70;
  const r = 54;
  const pTop = `${cx},${cy - r * (Math.max(0, Math.min(30, mind.zisei)) / 30)}`;
  const pRight = `${cx + r * (Math.max(0, Math.min(30, mind.soshiki)) / 30)},${cy}`;
  const pBottom = `${cx},${cy + r * (Math.max(0, Math.min(30, mind.kansei)) / 30)}`;
  const pLeft = `${cx - r * (Math.max(0, Math.min(30, mind.kojin)) / 30)},${cy}`;
  const areaPoints = `${pTop} ${pRight} ${pBottom} ${pLeft}`;
  const peakBlock = viewMode === 0 ? `<div class="peak-periods peak-in-body">${peakHtml}</div>` : "";
  const normalViewHtml = `
    <div class="param-view">
      <div class="media-row">
        <div class="thumbs">
          <img loading="lazy" src="${staticImg}" alt="${player.name} static" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} action" />
        </div>
        <div class="mind-chart" aria-label="mind chart">
          <svg viewBox="0 0 140 140" role="img">
            <polygon class="grid" points="70,16 124,70 70,124 16,70"></polygon>
            <polygon class="grid" points="70,34 106,70 70,106 34,70"></polygon>
            <polygon class="grid" points="70,52 88,70 70,88 52,70"></polygon>
            <line class="axis" x1="70" y1="16" x2="70" y2="124"></line>
            <line class="axis" x1="16" y1="70" x2="124" y2="70"></line>
            <polygon class="area" points="${areaPoints}"></polygon>
          </svg>
          <div class="mind-label top">知性 ${mind.zisei}</div>
          <div class="mind-label right">組織 ${mind.soshiki}</div>
          <div class="mind-label bottom">感性 ${mind.kansei}</div>
          <div class="mind-label left">個人 ${mind.kojin}</div>
        </div>
      </div>
      ${peakBlock}
      <div class="metrics-wrap">
        <div class="metrics main-3">${mainMetrics.map(metricBox).join("")}</div>
        <div class="metric-group"><div class="metrics group-4">${group2.map(metricBox).join("")}</div></div>
        <div class="metric-group"><div class="metrics group-4">${group1.map(metricBox).join("")}</div></div>
      </div>
    </div>
  `;
  const detailViewHtml = periodTableHtml(player, staticImg, actionImg);
  const thirdViewHtml = profileViewHtml(player, staticImg, actionImg);
  const bodyHtml = swipeDeckHtml(viewMode, normalViewHtml, detailViewHtml, thirdViewHtml);
  const cardStateClass = viewMode === 1 ? "is-expanded" : "is-collapsed";
  return `
    <article class="card ${cardStateClass} mode-${viewMode}" data-player-id="${player.id}">
      <div class="card-top">
        ${cardTabsHtml(player.id, viewMode)}
        <span class="card-id">ID: ${player.id}</span>
        <div class="card-head-main">
          <h3 class="card-name">
            <span class="badge pos-badge ${posClass}">${pos}</span>
            <span class="badge type-badge ${typeClass}">${typeLabel}</span>
            <span>${player.name}</span>
          </h3>
        </div>
      </div>
      <div class="card-body">${bodyHtml}</div>
    </article>
  `;
}

function renderPlayerCardModal() {
  if (!els.playerCardHost || !Number.isInteger(selectedPlayerId)) return;
  const player = playersById.get(selectedPlayerId);
  if (!player) {
    els.playerCardHost.innerHTML = `<p class="dim">Player not found.</p>`;
    return;
  }
  els.playerCardHost.innerHTML = playerCardHtml(player);
}

function openPlayerCardModal(playerId) {
  const id = Number(playerId);
  if (!Number.isInteger(id)) return;
  selectedPlayerId = id;
  renderPlayerCardModal();
  if (els.playerCardModal) els.playerCardModal.hidden = false;
}

function closePlayerCardModal() {
  selectedPlayerId = null;
  if (els.playerCardModal) els.playerCardModal.hidden = true;
}

function formationGaugeBox(label, value, className = "") {
  const max = 10;
  const num = Number(value || 0);
  const bounded = Math.max(0, Math.min(max, Math.round(num)));
  const cells = Array.from({ length: 10 }, (_, i) =>
    `<span class="gauge-cell${i < bounded ? " on" : ""}"></span>`
  ).join("");
  return `
    <div class="formation-param-box ${className}">
      <span class="formation-param-key">${label}</span>
      <div class="formation-param-body">
        <div class="gauge">${cells}</div>
        <span class="formation-param-num">${Number.isFinite(num) ? Math.round(num) : "-"}</span>
      </div>
    </div>
  `;
}

function renderFormationParamGrid(params) {
  const p = params || {};
  return `
    <div class="formation-param-matrix">
      ${formationGaugeBox("スピード", p.spd, "m-speed")}
      ${formationGaugeBox("攻撃力", p.off, "m-sub")}
      ${formationGaugeBox("総合力", p.ttl, "m-sub")}

      ${formationGaugeBox("テクニック", p.tec, "m-tech")}
      ${formationGaugeBox("守備力", p.def, "m-sub")}
      ${formationGaugeBox("難易度", p.dif, "m-sub")}

      ${formationGaugeBox("パワー", p.pwr, "m-power")}
      ${formationGaugeBox("中盤構成力", p.mid, "m-sub")}
      ${formationGaugeBox("スタミナ", p.stm, "m-sub")}
    </div>
  `;
}

function getCoachById(coachId) {
  const id = Number(coachId);
  if (!Number.isInteger(id)) return null;
  return coaches.find((c) => Number(c?.id) === id) || null;
}

function coachTypeLabel(value) {
  const n = Number(value);
  if (n === 1) return "超攻撃型";
  if (n === 2) return "攻撃型";
  if (n === 3) return "バランス型";
  if (n === 4) return "守備型";
  if (n === 5) return "超守備型";
  return String(value || "-");
}

function coachLeadershipTableHtml(leadership) {
  const rows = Array.isArray(leadership) ? leadership : [];
  if (!rows.length) return "-";
  const chunks = [];
  for (let i = 0; i < rows.length; i += 8) {
    chunks.push(rows.slice(i, i + 8));
  }
  const blocks = chunks.map((chunk, idx) => {
    const start = idx * 8;
    const th = chunk.map((_, i) => `<th>${start + i + 1}期</th>`).join("");
    const td = chunk.map((v) => `<td>${Number(v)}</td>`).join("");
    return `
      <div class="coach-lead-block">
        <table class="coach-lead-table">
          <thead><tr>${th}</tr></thead>
          <tbody><tr>${td}</tr></tbody>
        </table>
      </div>
    `;
  }).join("");
  return `
    <div class="coach-table-wrap">
      <div class="coach-lead-blocks">${blocks}</div>
    </div>
  `;
}

function getFormationName(fid) {
  const f = formations.find((x) => Number(x?.id) === Number(fid));
  if (!f) return `Formation ${fid}`;
  const y = formatFormationYearLabel(f.year, f.stride);
  return `${f.name}${y ? ` ${y}` : ""}`;
}

function renderCoachDetail(coachId) {
  if (!els.coachDetail || !els.coachTitle) return;
  const coach = getCoachById(coachId);
  if (!coach) {
    els.coachTitle.textContent = "Coach";
    els.coachDetail.innerHTML = `<p class="dim">No data.</p>`;
    return;
  }
  const ext = coachesMeta.find((c) => Number(c?.id) === Number(coach.id)) || null;
  const leadership = Array.isArray(ext?.leadershipBySeason) ? ext.leadershipBySeason : [];
  const leadTable = coachLeadershipTableHtml(leadership);
  const obtainable = Array.isArray(ext?.obtainable) ? ext.obtainable : [];
  const depth4 = Array.isArray(ext?.depth4FormationIds) ? ext.depth4FormationIds : (coach.formationDepth4 || []);
  const tab = coachTabModeById.get(Number(coach.id)) || "lead";
  const obtainHtml = obtainable.map((row) => {
    const suffix = Number(row.fromSeason) > 1 ? ` (${row.fromSeason}期目〜)` : "";
    return `<button type="button" class="inline-pill coach-formation-pill" data-formation-id="${row.formationId}">${getFormationName(row.formationId)}${suffix}</button>`;
  }).join(" ");
  const depth4Html = depth4.map((fid) => {
    return `<button type="button" class="inline-pill coach-formation-pill" data-formation-id="${fid}">${getFormationName(fid)}</button>`;
  }).join(" ");

  const staticImg = `./images/chara/headcoaches/static/${coach.id}@2x.gif`;
  const actionImg = `./images/chara/headcoaches/action/${coach.id}@2x.gif`;
  const nationText = String(coach?.nationality || "").trim() || nationNameFromId(coach?.nationId);
  const tabPanelHtml =
    tab === "obtain"
      ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Available Formation</div><div class="coach-formation-list">${obtainHtml || "-"}</div></div>`
      : tab === "understood"
        ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Understood Formation</div><div class="coach-formation-list">${depth4Html || "-"}</div></div>`
        : `<div class="coach-tab-panel coach-tab-scroll coach-tab-panel-lead"><div class="profile-description-title">Leadership</div>${leadTable || "-"}</div>`;
  els.coachTitle.textContent = "Coach";
  els.coachDetail.innerHTML = `
    <article class="coach-card coach-card-fixed">
      <div class="coach-card-top">
        <h3 class="card-name"><span class="badge pos-badge hc-badge">HC</span><span>${coach.name}</span></h3>
      </div>
      <div class="coach-card-body">
        <div class="thumbs coach-thumbs">
          <img loading="lazy" src="${staticImg}" alt="${coach.name}" onerror="this.src='${actionImg}'" />
          <img loading="lazy" src="${actionImg}" alt="${coach.name}" />
        </div>
        <div class="profile-side coach-profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nationText}</span></div>
          <div class="profile-item"><span class="k">年齢</span><span class="v">${coach.age || "-"}</span></div>
          <div class="profile-item"><span class="k">タイプ</span><span class="v">${coachTypeLabel(coach.type)}</span></div>
        </div>
      </div>
      ${tabPanelHtml}
      <div class="card-tabs">
        <button type="button" class="card-tab ${tab === "lead" ? "is-active" : ""}" data-coach-tab="lead" data-coach-id="${coach.id}">LEAD</button>
        <button type="button" class="card-tab ${tab === "obtain" ? "is-active" : ""}" data-coach-tab="obtain" data-coach-id="${coach.id}">AVL</button>
        <button type="button" class="card-tab ${tab === "understood" ? "is-active" : ""}" data-coach-tab="understood" data-coach-id="${coach.id}">UND</button>
      </div>
    </article>
  `;
}

function openCoachModal(coachId) {
  if (!els.coachModal) return;
  renderCoachDetail(coachId);
  els.coachModal.hidden = false;
}

function closeCoachModal() {
  if (!els.coachModal) return;
  els.coachModal.hidden = true;
}

function openFormationModal(formation, options = {}) {
  currentFormation = formation;
  if (!options.preserveSlotTopMode) {
    slotTopSortMode = "usage";
    coachRankingMode = "usage";
  }
  if (!els.formationModal || !els.formationTitle || !els.formationDetail) return;

  const yearLabel = formatFormationYearLabel(formation.year, formation.stride);
  els.formationTitle.textContent = `${formation.name}${yearLabel ? ` ${yearLabel}` : ""} (${formation.system || "-"})`;
  els.formationDetail.innerHTML = `
    <div class="formation-detail-grid">
      <div class="formation-field-col">
        ${renderFormationPitch(formation.positions || [], formation.id)}
      </div>
      <div class="formation-cc-col">
        <div class="formation-block formation-cc-block">
          <h3>CC Stats</h3>
          <p>Usage: ${pct(formation.cc.usageRate)} (${formation.cc.uses})</p>
          <p>Win: ${pct(formation.cc.winRate)} (${formation.cc.wins}/${formation.cc.uses || 0})</p>
          <button type="button" class="formation-matchups-btn" data-open-matchups="${formation.id}">View Formation Matchups</button>
        </div>
      </div>
    </div>
    <div class="formation-block formation-description-block">
      <h3>Description</h3>
      ${renderFormationDescription(formation)}
    </div>
    <div class="formation-detail-stack">
        <div class="formation-block">
          <h3>Formation Data</h3>
          ${renderFormationParamGrid(formation.params)}
        </div>
        <div class="formation-block">
          <h3>Available Coaches</h3>
          <div class="coach-formation-list">${renderCoachesList(formation.coaches?.obtainable)}</div>
        </div>
        <div class="formation-block">
          <h3>Understood Coaches</h3>
          <div class="coach-formation-list">${renderCoachesList(formation.coaches?.depth4)}</div>
        </div>
    </div>
    <div class="formation-block">
      <h3>Key Positions</h3>
      ${renderKeyPositions(formation.keyPositions || [])}
    </div>
    <div class="formation-block">
      <div class="slot-top-toolbar">
        <h3>${slotTopSortMode === "model" ? "Model Players" : slotTopSortMode === "best" ? "Top Teams" : "CC Slot Top Player (#1)"}</h3>
        <div class="slot-top-sort-switch" role="group" aria-label="CC Slot Top sort mode">
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "usage" ? " is-on" : ""}" data-slot-top-sort="usage">Usage</button>
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "avg" ? " is-on" : ""}" data-slot-top-sort="avg">Avg</button>
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "model" ? " is-on" : ""}" data-slot-top-sort="model">Model</button>
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "best" ? " is-on" : ""}" data-slot-top-sort="best">Top Teams</button>
        </div>
      </div>
      ${renderSlotTop(formation.slotStats || {}, slotTopSortMode)}
    </div>
    <div class="formation-block">
      <div class="slot-top-toolbar">
        <h3>CC Coach Ranking</h3>
        <div class="slot-top-sort-switch coach-ranking-switch" role="group" aria-label="CC Coach Ranking mode">
          <button type="button" class="slot-top-sort-btn${coachRankingMode === "usage" ? " is-on" : ""}" data-coach-rank-mode="usage">Usage</button>
          <button type="button" class="slot-top-sort-btn${coachRankingMode === "avg" ? " is-on" : ""}" data-coach-rank-mode="avg">Avg</button>
          <button type="button" class="slot-top-sort-btn${coachRankingMode === "stats" ? " is-on" : ""}" data-coach-rank-mode="stats">Stats</button>
        </div>
      </div>
      ${renderCoachRanking(formation.coachStats, coachRankingMode)}
    </div>
  `;
  els.formationModal.hidden = false;
}

function matchupRowsHtml(rows = []) {
  if (!Array.isArray(rows) || !rows.length) return `<p class="dim">No statistically significant matchup yet.</p>`;
  const nameColWidthCh = (() => {
    let maxLen = 12;
    for (const f of formations || []) {
      const y = formatFormationYearLabel(f?.year, f?.stride);
      const label = f ? `${f.name}${y ? ` ${y}` : ""}` : "";
      maxLen = Math.max(maxLen, String(label || "").length);
    }
    return Math.min(64, Math.max(22, maxLen + 6));
  })();
  return `
    <div class="matchup-table-wrap">
      <table class="matchup-table" style="--matchup-name-col-width:${nameColWidthCh}ch;">
        <colgroup>
          <col style="width:${nameColWidthCh}ch; min-width:${nameColWidthCh}ch; max-width:${nameColWidthCh}ch;" />
          <col />
          <col />
          <col />
          <col />
        </colgroup>
        <thead>
          <tr><th>Formation</th><th>W-D-L</th><th>Pts</th><th>ΔAdjPts</th><th>N</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => {
            const f = formations.find((x) => Number(x?.id) === Number(row?.formationId));
            const y = formatFormationYearLabel(f?.year, f?.stride);
            const name = f ? `${f.name}${y ? ` ${y}` : ""}` : `Formation ${row?.formationId}`;
            const delta = Number(row?.delta || 0);
            const pts = Number(row?.pointsPerMatch || 0);
            const expPts = Number(row?.expectedPointsPerMatch || 0);
            const w = Number(row?.wins || 0);
            const d = Number(row?.draws || 0);
            const l = Number(row?.losses || 0);
            const confidence = String(row?.confidence || "").trim();
            return `
              <tr>
                <td><button type="button" class="inline-pill matchup-formation-link" data-formation-id="${row?.formationId}">${name}</button></td>
                <td>${w}-${d}-${l}</td>
                <td>${pts.toFixed(2)} <span class="dim">(Exp ${expPts.toFixed(2)})</span></td>
                <td class="${delta >= 0 ? "matchup-pos" : "matchup-neg"}">${delta >= 0 ? "+" : ""}${delta.toFixed(2)}</td>
                <td>${row?.matches}${confidence ? ` <span class="dim">(${confidence})</span>` : ""}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function openMatchupModal(formation) {
  if (!formation || !els.matchupModal || !els.matchupTitle || !els.matchupDetail) return;
  const y = formatFormationYearLabel(formation.year, formation.stride);
  els.matchupTitle.textContent = `${formation.name}${y ? ` ${y}` : ""} Matchups`;
  const m = formation.matchups || {};
  const criteria = m.criteria || {};
  els.matchupDetail.innerHTML = `
    <div class="formation-block">
      <h3>Best Matchups</h3>
      ${matchupRowsHtml(m.strongAgainst)}
    </div>
    <div class="formation-block">
      <h3>Worst Matchups</h3>
      ${matchupRowsHtml(m.weakAgainst)}
    </div>
    <p class="dim matchup-criteria">
      Minimum N: ${Number(criteria.minMatches || 0)} / ranked by adjusted points difference (Low: 15-24, Mid: 25-39, High: 40+)
    </p>
  `;
  els.matchupModal.hidden = false;
}

function closeMatchupModal() {
  if (!els.matchupModal) return;
  els.matchupModal.hidden = true;
}

function closeFormationModal() {
  if (!els.formationModal) return;
  els.formationModal.hidden = true;
  const params = new URLSearchParams(window.location.search || "");
  if (params.get("returnTo") === "myteam") {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = "./myteam.html";
    }
  }
}

function tryOpenFormationFromQuery() {
  const params = new URLSearchParams(window.location.search || "");
  const targetId = Number(params.get("openFormationId") || 0);
  if (!Number.isInteger(targetId) || targetId <= 0) return;
  const f = formations.find((x) => Number(x?.id) === targetId);
  if (!f) return;
  openFormationModal(f);
}

function renderSlotDetailSourceSwitch() {
  return `
    <div class="slot-detail-source-switch slot-top-sort-switch" role="group" aria-label="Slot detail source">
      <button type="button" class="slot-top-sort-btn${slotDetailSourceMode === "cc" ? " is-on" : ""}" data-slot-detail-source="cc">CC</button>
      <button type="button" class="slot-top-sort-btn${slotDetailSourceMode === "rohm" ? " is-on" : ""}" data-slot-detail-source="rohm">Rohm</button>
    </div>
  `;
}

function renderCcSlotDetail(slot) {
  const allRows = currentFormation.slotStats?.[String(slot)] || [];
  const rows = sortSlotRows(allRows, slotTopSortMode).slice(0, 20);
  if (!rows.length) {
    return `<p class="dim">No CC slot data.</p>`;
  }
  return `
    <div class="slot-table-wrap">
      <table class="slot-table">
        <thead>
          <tr><th>#</th><th>Player</th><th>Cat</th><th>Usage</th><th>Avg</th><th>Goals</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r, idx) => `
                <tr class="slot-player-row" data-player-id="${r.playerId}">
                  <td>${idx + 1}</td>
                  <td>${r.playerName}</td>
                  <td>${categoryBadgeHtmlByPlayerId(r.playerId)}</td>
                  <td>${pct(r.usageRate)} (${r.uses})</td>
                  <td>${avg(r.avgPts)}</td>
                  <td>${goalsPer7(r.goalsPer7)}</td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderRohmSlotDetail(slot) {
  if (!rohmSlotData) {
    if (rohmSlotDataError) {
      return `<p class="dim">No Rohm slot data. (${escapeHtml(rohmSlotDataError)})</p>`;
    }
    return `<p class="dim">Loading Rohm data...</p>`;
  }
  const rohm = getRohmSlotData(currentFormation, slot);
  const rows = (rohm?.rows || []).slice(0, 20);
  if (!rows.length) {
    return `<p class="dim">No Rohm slot data.</p>`;
  }
  const sourceLine = `
    <p class="slot-detail-source-note">
      Rohm: ${escapeHtml(rohm?.title || "")}
      ${rohm?.updatedAt ? `<span>Updated ${escapeHtml(rohm.updatedAt)}</span>` : ""}
      ${rohm?.url ? `<a href="${rohm.url}" target="_blank" rel="noopener">Source</a>` : ""}
    </p>
  `;
  return `
    ${sourceLine}
    <div class="slot-table-wrap">
      <table class="slot-table rohm-slot-table">
        <thead>
          <tr><th>#</th><th>Player</th><th>Cat</th><th>Games</th><th>Avg</th><th>Dev</th><th>Goals</th><th>Ast</th></tr>
        </thead>
        <tbody>
          ${rows
            .map((r, idx) => {
              const playerId = Number(r?.localPlayerId || 0);
              const isLinked = Number.isInteger(playerId) && playerId > 0;
              const playerName = isLinked ? (playersById.get(playerId)?.name || r.playerName) : r.playerName;
              const note = isLinked ? "" : `<span class="rohm-unlinked-note">${escapeHtml(r.matchStatus || "unlinked")}</span>`;
              return `
                <tr class="${isLinked ? "slot-player-row" : "rohm-unlinked-row"}" ${isLinked ? `data-player-id="${playerId}"` : ""}>
                  <td>${Number(r?.rank || idx + 1)}</td>
                  <td>${escapeHtml(playerName)}${note}</td>
                  <td>${rohmCategoryBadgeHtml(r)}</td>
                  <td>${Number(r?.uses || 0).toLocaleString()}</td>
                  <td>${avg(r?.avgPts)}</td>
                  <td>${r?.deviation == null ? "-" : Number(r.deviation).toFixed(2)}</td>
                  <td>${r?.goals == null ? "-" : Number(r.goals).toFixed(2)}</td>
                  <td>${r?.assists == null ? "-" : Number(r.assists).toFixed(2)}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderSlotModalContent(slot) {
  if (!els.slotDetail) return;
  els.slotDetail.innerHTML = `
    ${renderSlotDetailSourceSwitch()}
    ${slotDetailSourceMode === "rohm" ? renderRohmSlotDetail(slot) : renderCcSlotDetail(slot)}
  `;
}

function openSlotModal(slot) {
  if (!currentFormation || !els.slotModal || !els.slotTitle || !els.slotDetail) return;
  currentSlotDetailSlot = slot;
  slotDetailSourceMode = "cc";
  const yearLabel = formatFormationYearLabel(currentFormation.year, currentFormation.stride);
  els.slotTitle.textContent = `${currentFormation.name}${yearLabel ? ` ${yearLabel}` : ""} / Slot ${slot}`;
  renderSlotModalContent(slot);
  els.slotModal.hidden = false;
}

function closeSlotModal() {
  if (!els.slotModal) return;
  els.slotModal.hidden = true;
}

function bindEvents() {
  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => {
      if (!els.menuPanel) return;
      els.menuPanel.classList.toggle("is-open");
    });
  }
  if (els.playersButton) {
    els.playersButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./index.html";
    });
  }
  if (els.coachesButton) {
    els.coachesButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./coaches.html";
    });
  }
  if (els.formationsButton) {
    els.formationsButton.addEventListener("click", () => {
      closeMenuPanel();
    });
  }
  if (els.loginButton) {
    els.loginButton.addEventListener("click", () => {
      closeMenuPanel();
      openLoginModal();
    });
  }
  if (els.myTeamButton) {
    els.myTeamButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./myteam.html";
    });
  }
  if (els.logoutButton) {
    els.logoutButton.addEventListener("click", () => {
      closeMenuPanel();
      logout();
    });
  }
  if (els.loginBackdrop) els.loginBackdrop.addEventListener("click", closeLoginModal);
  if (els.loginClose) els.loginClose.addEventListener("click", closeLoginModal);
  if (els.signupOpen) {
    els.signupOpen.addEventListener("click", () => {
      closeLoginModal();
      openSignupModal();
    });
  }
  if (els.loginApply) {
    els.loginApply.addEventListener("click", async () => {
      const key = String(els.loginLineupKey?.value || "").trim();
      const prevKey = String(cloudConfig.lineupKey || "").trim();
      if (!key) return;
      saveCloudConfig(key);
      try {
        const exists = await cloudLineupExists(key);
        if (!exists) {
          saveCloudConfig(prevKey);
          updateMenuState();
          window.alert("入力されたIDの登録はありません。Create New IDを使用してください。");
          return;
        }
      } catch (_) {
        saveCloudConfig(prevKey);
        updateMenuState();
        window.alert("Loginに失敗しました。");
        return;
      }
      updateMenuState();
      await loadCloudMeta().catch(() => {});
      closeLoginModal();
      renderList();
    });
  }
  if (els.signupBackdrop) els.signupBackdrop.addEventListener("click", closeSignupModal);
  if (els.signupClose) els.signupClose.addEventListener("click", closeSignupModal);
  if (els.signupCancel) els.signupCancel.addEventListener("click", closeSignupModal);
  if (els.signupApply) {
    els.signupApply.addEventListener("click", async () => {
      const key = String(els.signupLineupKey?.value || "").trim();
      const prevKey = String(cloudConfig.lineupKey || "").trim();
      if (!key) return;
      saveCloudConfig(key);
      try {
        const exists = await cloudLineupExists(key);
        if (exists) {
          saveCloudConfig(prevKey);
          updateMenuState();
          window.alert("そのIDは既に使われています。別のIDを入力してください。");
          return;
        }
        await cloudCreateLineup(key);
      } catch (_) {
        saveCloudConfig(prevKey);
        updateMenuState();
        window.alert("Create New IDに失敗しました。");
        return;
      }
      updateMenuState();
      await loadCloudMeta().catch(() => {});
      closeSignupModal();
      closeLoginModal();
      renderList();
    });
  }

  if (els.sortKey) els.sortKey.addEventListener("change", renderList);
  if (els.formationNameQuery) {
    els.formationNameQuery.addEventListener("input", renderList);
    els.formationNameQuery.addEventListener("blur", () => {
      setTimeout(() => {
        if (!els.formationNameSuggest) return;
        els.formationNameSuggest.hidden = true;
      }, 120);
    });
  }
  if (els.undCoachFilter) {
    els.undCoachFilter.addEventListener("change", renderList);
  }
  if (els.avlCoachFilter) {
    els.avlCoachFilter.addEventListener("change", renderList);
  }

  if (els.formationList) {
    els.formationList.addEventListener("click", (e) => {
      const item = e.target.closest(".formation-item");
      if (!item) return;
      const id = Number(item.dataset.formationId);
      if (!Number.isInteger(id)) return;
      const f = formations.find((x) => Number(x.id) === id);
      if (!f) return;
      openFormationModal(f);
    });
  }

  if (els.formationNameSuggest) {
    els.formationNameSuggest.addEventListener("click", (e) => {
      const btn = e.target.closest(".name-suggest-item");
      if (!btn || !els.formationNameQuery) return;
      els.formationNameQuery.value = btn.dataset.name || "";
      els.formationNameSuggest.hidden = true;
      renderList();
    });
  }

  if (els.formationDetail) {
    els.formationDetail.addEventListener("click", (e) => {
      const coachBtn = e.target.closest("[data-coach-id]");
      if (coachBtn) {
        const cid = Number(coachBtn.dataset.coachId);
        if (Number.isInteger(cid)) openCoachModal(cid);
        return;
      }
      const bestTeamBtn = e.target.closest("[data-best-team-index]");
      if (bestTeamBtn) {
        const index = Number(bestTeamBtn.dataset.bestTeamIndex);
        if (currentFormation && Number.isInteger(index)) {
          bestTeamIndexByFormation.set(Number(currentFormation.id), index);
          openFormationModal(currentFormation, { preserveSlotTopMode: true });
        }
        return;
      }
      const coachRankBtn = e.target.closest("[data-coach-rank-mode]");
      if (coachRankBtn) {
        const mode = String(coachRankBtn.dataset.coachRankMode || "");
        if (mode === "usage" || mode === "avg" || mode === "stats") {
          coachRankingMode = mode;
          if (currentFormation) openFormationModal(currentFormation, { preserveSlotTopMode: true });
        }
        return;
      }
      const sortBtn = e.target.closest("[data-slot-top-sort]");
      if (sortBtn) {
        const mode = String(sortBtn.dataset.slotTopSort || "");
        if (mode === "usage" || mode === "avg" || mode === "team" || mode === "best" || mode === "model") {
          slotTopSortMode = mode;
          if (currentFormation) openFormationModal(currentFormation, { preserveSlotTopMode: true });
        }
        return;
      }
      const matchupBtn = e.target.closest("[data-open-matchups]");
      if (matchupBtn) {
        const fid = Number(matchupBtn.dataset.openMatchups);
        const f = formations.find((x) => Number(x?.id) === fid);
        if (f) openMatchupModal(f);
        return;
      }
      const playerBtn = e.target.closest("[data-player-id]");
      if (playerBtn) {
        const playerId = Number(playerBtn.dataset.playerId);
        if (Number.isInteger(playerId) && playerId > 0) openPlayerCardModal(playerId);
        return;
      }
      const slotBtn = e.target.closest("[data-slot]");
      if (!slotBtn) return;
      const slot = Number(slotBtn.dataset.slot);
      if (!Number.isInteger(slot)) return;
      openSlotModal(slot);
    });
  }

  if (els.formationBackdrop) els.formationBackdrop.addEventListener("click", closeFormationModal);
  if (els.formationClose) els.formationClose.addEventListener("click", closeFormationModal);
  if (els.slotBackdrop) els.slotBackdrop.addEventListener("click", closeSlotModal);
  if (els.slotClose) els.slotClose.addEventListener("click", closeSlotModal);
  if (els.coachBackdrop) els.coachBackdrop.addEventListener("click", closeCoachModal);
  if (els.coachClose) els.coachClose.addEventListener("click", closeCoachModal);
  if (els.matchupBackdrop) els.matchupBackdrop.addEventListener("click", closeMatchupModal);
  if (els.matchupClose) els.matchupClose.addEventListener("click", closeMatchupModal);
  if (els.playerCardBackdrop) els.playerCardBackdrop.addEventListener("click", closePlayerCardModal);
  if (els.playerCardClose) els.playerCardClose.addEventListener("click", closePlayerCardModal);

  if (els.slotDetail) {
    els.slotDetail.addEventListener("click", (e) => {
      const sourceBtn = e.target.closest("[data-slot-detail-source]");
      if (sourceBtn) {
        const mode = String(sourceBtn.dataset.slotDetailSource || "");
        if ((mode === "cc" || mode === "rohm") && currentSlotDetailSlot != null) {
          slotDetailSourceMode = mode;
          renderSlotModalContent(currentSlotDetailSlot);
          if (mode === "rohm" && !rohmSlotData && !rohmSlotDataPromise) {
            loadRohmSlotData()
              .then(() => {
                if (slotDetailSourceMode === "rohm" && currentSlotDetailSlot != null) {
                  renderSlotModalContent(currentSlotDetailSlot);
                }
              })
              .catch(() => {
                if (slotDetailSourceMode === "rohm" && currentSlotDetailSlot != null) {
                  renderSlotModalContent(currentSlotDetailSlot);
                }
              });
          }
        }
        return;
      }
      const row = e.target.closest("tr[data-player-id]");
      if (!row) return;
      const id = Number(row.dataset.playerId);
      if (!Number.isInteger(id)) return;
      openPlayerCardModal(id);
    });
  }

  if (els.playerCardHost) {
    els.playerCardHost.addEventListener("click", (e) => {
      const tabBtn = e.target.closest(".card-tab");
      if (!tabBtn) return;
      const id = Number(tabBtn.dataset.playerId);
      const mode = Number(tabBtn.dataset.mode);
      if (!Number.isInteger(id) || !Number.isInteger(mode)) return;
      cardViewModeById.set(id, mode);
      renderPlayerCardModal();
    });
  }
  if (els.coachDetail) {
    els.coachDetail.addEventListener("click", (e) => {
      const tabBtn = e.target.closest("[data-coach-tab][data-coach-id]");
      if (tabBtn) {
        const coachId = Number(tabBtn.dataset.coachId);
        const tab = String(tabBtn.dataset.coachTab || "");
        if (Number.isInteger(coachId) && (tab === "lead" || tab === "obtain" || tab === "understood")) {
          coachTabModeById.set(coachId, tab);
          renderCoachDetail(coachId);
        }
        return;
      }
      const fbtn = e.target.closest("[data-formation-id]");
      if (!fbtn) return;
      const fid = Number(fbtn.dataset.formationId);
      if (!Number.isInteger(fid)) return;
      const f = formations.find((x) => Number(x?.id) === fid);
      if (f) openFormationModal(f);
    });
  }

  document.addEventListener("click", (e) => {
    if (!els.menuPanel || !els.menuButton || !els.menuPanel.classList.contains("is-open")) return;
    if (e.target.closest("#menuButton") || e.target.closest("#menuPanel")) return;
    closeMenuPanel();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeMenuPanel();
    closeLoginModal();
    closeSignupModal();
    closeFormationModal();
    closeCoachModal();
    closeMatchupModal();
    closeSlotModal();
    closePlayerCardModal();
  });

  if (els.matchupDetail) {
    els.matchupDetail.addEventListener("click", (e) => {
      const fbtn = e.target.closest("[data-formation-id]");
      if (!fbtn) return;
      const fid = Number(fbtn.dataset.formationId);
      if (!Number.isInteger(fid)) return;
      const f = formations.find((x) => Number(x?.id) === fid);
      if (!f) return;
      closeMatchupModal();
      openFormationModal(f);
    });
  }
}

async function init() {
  setupModalScrollLock();
  loadCloudConfig();
  syncMenuButtonSize();
  window.addEventListener("resize", syncMenuButtonSize);
  buildSortOptions();
  bindEvents();

  const [formationsRes, playersRes, coachesMetaRes] = await Promise.all([
    fetch("./formations_data.json"),
    fetch("./data.json").catch(() => null),
    fetch("./coaches_data.json").catch(() => null),
    loadSiteMeta(),
  ]);
  const formationData = await formationsRes.json();
  formations = Array.isArray(formationData.formations) ? formationData.formations : [];
  coaches = Array.isArray(formationData.coaches) ? formationData.coaches : [];
  if (coachesMetaRes && coachesMetaRes.ok) {
    try {
      const raw = await coachesMetaRes.json();
      coachesMeta = Array.isArray(raw?.coaches) ? raw.coaches : [];
    } catch (e) {
      console.warn(e);
    }
  }
  rebuildFormationAvailableCoachesFromMeta();
  if (playersRes && playersRes.ok) {
    try {
      const playersData = await playersRes.json();
      const rows = Array.isArray(playersData?.players) ? playersData.players : [];
      syncProfileSideWidthFromPlayers(rows);
      playerCategoryById = new Map(
        rows
          .map((p) => [Number(p?.id), normalizeCategory(p?.category)])
          .filter(([id]) => Number.isInteger(id))
      );
      playerRateById = new Map(
        rows
          .map((p) => [Number(p?.id), Number(p?.rate)])
          .filter(([id]) => Number.isInteger(id))
      );
      playersById = new Map(
        rows
          .map((p) => [Number(p?.id), p])
          .filter(([id]) => Number.isInteger(id))
      );
    } catch (e) {
      console.warn(e);
    }
  }
  buildCoachFilters();
  if (isLoggedIn()) {
    await loadCloudMeta().catch(() => {});
  }
  updateMenuState();
  renderList();
  refreshUpdatedAtFromGitHub();
  tryOpenFormationFromQuery();
}

init().catch((e) => {
  if (els.metaText) {
    els.metaText.textContent = "Failed to load formations.";
  }
  console.error(e);
});
