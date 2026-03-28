const METRICS = [
  "スピ", "テク", "パワ", "スタ", "ラフ", "個性", "人気",
  "PK", "FK", "CK", "CP", "知性", "感性", "個人", "組織"
];
const CONDITION_METRICS = ["ID", ...METRICS];
const METRIC_LABELS = {
  "ID": "ID",
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
const LINEUP_SIZE = 11;
const LINEUP_STORAGE_KEY = "ws_starting_eleven_v1";
const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const RENDER_BATCH_SIZE = 200;
const RENDER_CARDS_PER_FRAME = 24;
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_ISO = "2026-03-26T21:53:00+09:00";
const APP_UPDATED_AT_JST = "2026-03-28 18:26 JST";
let appUpdatedAtJst = APP_UPDATED_AT_JST;

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

const els = {
  hero: document.querySelector(".hero"),
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  playersButton: document.querySelector("#playersButton"),
  coachesButton: document.querySelector("#coachesButton"),
  loginButton: document.querySelector("#loginButton"),
  formationsButton: document.querySelector("#formationsButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  logoutButton: document.querySelector("#logoutButton"),
  nameQuery: document.querySelector("#nameQuery"),
  nameSuggest: document.querySelector("#nameSuggest"),
  positionFilter: document.querySelector("#positionFilter"),
  aptitudePositionFilter: document.querySelector("#aptitudePositionFilter"),
  aptitudeIncludeSix: document.querySelector("#aptitudeIncludeSix"),
  aptitudeAreaLabel: document.querySelector("#aptitudeAreaLabel"),
  cmOnly: document.querySelector("#cmOnly"),
  ssOnly: document.querySelector("#ssOnly"),
  nrWhiteOnly: document.querySelector("#nrWhiteOnly"),
  nrBronzeOnly: document.querySelector("#nrBronzeOnly"),
  nrSilverOnly: document.querySelector("#nrSilverOnly"),
  nrGoldOnly: document.querySelector("#nrGoldOnly"),
  nrAllOnly: document.querySelector("#nrAllOnly"),
  ccOnly: document.querySelector("#ccOnly"),
  scoutFilterWrap: document.querySelector("#scoutFilterWrap"),
  scoutEventFilter: document.querySelector("#scoutEventFilter"),
  cmFilterWrap: document.querySelector("#cmFilterWrap"),
  cmEventFilter: document.querySelector("#cmEventFilter"),
  applySearch: document.querySelector("#applySearch"),
  conditions: document.querySelector("#conditions"),
  addCondition: document.querySelector("#addCondition"),
  resetCondition: document.querySelector("#resetCondition"),
  resultCount: document.querySelector("#resultCount"),
  results: document.querySelector("#results"),
  loadMoreResults: document.querySelector("#loadMoreResults"),
  conditionTemplate: document.querySelector("#conditionTemplate"),
  lineupModal: document.querySelector("#lineupModal"),
  lineupBackdrop: document.querySelector("#lineupBackdrop"),
  lineupClose: document.querySelector("#lineupClose"),
  lineupTitle: document.querySelector("#lineupTitle"),
  lineupStarterMode: document.querySelector("#lineupStarterMode"),
  lineupSuccessorMode: document.querySelector("#lineupSuccessorMode"),
  lineupTarget: document.querySelector("#lineupTarget"),
  lineupSlots: document.querySelector("#lineupSlots"),
  seasonModal: document.querySelector("#seasonModal"),
  seasonBackdrop: document.querySelector("#seasonBackdrop"),
  seasonClose: document.querySelector("#seasonClose"),
  seasonTarget: document.querySelector("#seasonTarget"),
  seasonSelect: document.querySelector("#seasonSelect"),
  seasonCancel: document.querySelector("#seasonCancel"),
  seasonApply: document.querySelector("#seasonApply"),
  loginModal: document.querySelector("#loginModal"),
  loginBackdrop: document.querySelector("#loginBackdrop"),
  loginClose: document.querySelector("#loginClose"),
  loginLineupKey: document.querySelector("#loginLineupKey"),
  signupOpen: document.querySelector("#signupOpen"),
  loginApply: document.querySelector("#loginApply"),
  signupModal: document.querySelector("#signupModal"),
  signupBackdrop: document.querySelector("#signupBackdrop"),
  signupClose: document.querySelector("#signupClose"),
  signupLineupKey: document.querySelector("#signupLineupKey"),
  signupCancel: document.querySelector("#signupCancel"),
  signupApply: document.querySelector("#signupApply"),
  settingModal: document.querySelector("#settingModal"),
  settingBackdrop: document.querySelector("#settingBackdrop"),
  settingClose: document.querySelector("#settingClose"),
  renameLineupKey: document.querySelector("#renameLineupKey"),
  renameIdApply: document.querySelector("#renameIdApply"),
  deleteIdApply: document.querySelector("#deleteIdApply"),
  scoutListModal: document.querySelector("#scoutListModal"),
  scoutListBackdrop: document.querySelector("#scoutListBackdrop"),
  scoutListClose: document.querySelector("#scoutListClose"),
  scoutListTarget: document.querySelector("#scoutListTarget"),
  scoutListItems: document.querySelector("#scoutListItems"),
  successorSourceModal: document.querySelector("#successorSourceModal"),
  successorSourceBackdrop: document.querySelector("#successorSourceBackdrop"),
  successorSourceClose: document.querySelector("#successorSourceClose"),
  successorSourceTarget: document.querySelector("#successorSourceTarget"),
  successorSourceType: document.querySelector("#successorSourceType"),
  successorSourceCustomWrap: document.querySelector("#successorSourceCustomWrap"),
  successorSourceInput: document.querySelector("#successorSourceInput"),
  successorSourceCancel: document.querySelector("#successorSourceCancel"),
  successorSourceApply: document.querySelector("#successorSourceApply"),
  cloudLoadLineup: document.querySelector("#cloudLoadLineup"),
  cloudSaveLineup: document.querySelector("#cloudSaveLineup"),
  cloudStatus: document.querySelector("#cloudStatus"),
};

let players = [];
let scouts = [];
const scoutsByEventId = new Map();
let cmEvents = [];
const cmEventsByEventId = new Map();
const cardViewModeById = new Map();
let currentFilteredPlayers = [];
let renderedCount = 0;
let pendingLineupPlayerId = null;
let pendingLineupSlotIndex = null;
let pendingLineupMode = "starter";
let pendingSuccessorRegistration = null;
let pendingLoginForAddPlayerId = null;
let startingLineup = Array.from({ length: LINEUP_SIZE }, () => null);
let lineupSlotsLocked = false;
let lineupRegisterMode = "starter";
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let renderJobToken = 0;
let modalScrollLockY = 0;
let modalScrollLocked = false;

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

function normalizeSeasonInput(input) {
  const raw = String(input || "").trim();
  if (!raw) return "";
  const n = raw.replace(/[^0-9]/g, "");
  if (n.length > 0) {
    return `${Number(n)}期`;
  }
  if (raw.endsWith("期")) return raw;
  return raw;
}

function findPeriodBySeason(player, season) {
  if (!player || !season) return null;
  const periods = Array.isArray(player.periods) ? player.periods : [];
  return periods.find((p) => p?.season === season) || null;
}

function normalizeSuccessor(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = Number(raw.playerId);
  if (!Number.isInteger(id)) return null;
  const season = raw.season == null ? null : String(raw.season);
  const source = raw.source == null ? null : String(raw.source);
  return { playerId: id, season, source };
}

function normalizeLineupArray(parsed) {
  return Array.from({ length: LINEUP_SIZE }, (_, i) => {
    const row = parsed?.[i];
    if (row == null) return null;
    if (typeof row === "number" || typeof row === "string") {
      const id = Number(row);
      return Number.isInteger(id) ? { playerId: id, season: null, successor: null } : null;
    }
    if (typeof row === "object") {
      const id = Number(row.playerId);
      if (!Number.isInteger(id)) return null;
      const season = row.season == null ? null : String(row.season);
      const successor = normalizeSuccessor(row.successor);
      return { playerId: id, season, successor };
    }
    return null;
  });
}

function setCloudStatus(message, isError = false) {
  renderHeaderMeta();
}

function closeMenuPanel() {
  if (!els.menuPanel) return;
  els.menuPanel.classList.remove("is-open");
}

function isLoggedIn() {
  return !!String(cloudConfig.lineupKey || "").trim();
}

function renderHeaderMeta() {
  if (!els.metaText) return;
  els.metaText.innerHTML = `Updated: ${appUpdatedAtJst}`;
}

function syncMenuButtonSize() {
  if (!els.menuButton) return;
  const heroEl = els.hero || els.menuButton.closest(".hero");
  const heroHeight = heroEl ? Math.round(heroEl.getBoundingClientRect().height) : 40;
  const size = Math.max(30, Math.round(heroHeight * 0.72));
  document.documentElement.style.setProperty("--menu-button-size", `${size}px`);
}

function syncAptitudeAreaLabel() {
  if (!els.aptitudeAreaLabel) return;
  const includeSix = !!els.aptitudeIncludeSix?.checked;
  els.aptitudeAreaLabel.textContent = includeSix ? "Position Area (>=6)" : "Position Area (=7)";
}

function updateMenuState() {
  const loggedIn = isLoggedIn();
  if (els.loginButton) els.loginButton.hidden = loggedIn;
  if (els.logoutButton) els.logoutButton.hidden = !loggedIn;
  if (els.menuLoginId) {
    els.menuLoginId.hidden = !loggedIn;
    els.menuLoginId.textContent = loggedIn ? `Team ID：${cloudConfig.lineupKey}` : "";
  }
  renderHeaderMeta();
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

function consumePostLoginReturnPath() {
  const params = new URLSearchParams(window.location.search);
  const returnTo = String(params.get("returnTo") || "").trim().toLowerCase();
  const target = returnTo === "myteam" ? "./myteam.html" : "";
  params.delete("openLogin");
  params.delete("returnTo");
  const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash || ""}`;
  window.history.replaceState({}, "", next);
  return target;
}

function openSettingModal() {
  if (!els.settingModal) return;
  if (els.renameLineupKey) {
    els.renameLineupKey.value = cloudConfig.lineupKey || "";
    els.renameLineupKey.focus();
  }
  els.settingModal.hidden = false;
}

function closeSettingModal() {
  if (!els.settingModal) return;
  els.settingModal.hidden = true;
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function hasCloudConfig() {
  return !!(cloudConfig.url && cloudConfig.anonKey && cloudConfig.lineupKey);
}

function loadCloudConfig() {
  try {
    const raw = localStorage.getItem(CLOUD_CONFIG_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    cloudConfig = {
      url: normalizedSupabaseUrl(parsed?.url || ""),
      anonKey: String(parsed?.anonKey || "").trim(),
      lineupKey: String(parsed?.lineupKey || "").trim(),
    };
  } catch (e) {
    console.warn("failed to load cloud config", e);
  }
  if (FIXED_SUPABASE_URL) cloudConfig.url = normalizedSupabaseUrl(FIXED_SUPABASE_URL);
  if (FIXED_SUPABASE_ANON_KEY) cloudConfig.anonKey = String(FIXED_SUPABASE_ANON_KEY).trim();
  if (els.loginLineupKey) els.loginLineupKey.value = cloudConfig.lineupKey;
}

function saveCloudConfig(lineupKeyInput = null) {
  const lineupKey = String(lineupKeyInput ?? cloudConfig.lineupKey ?? "").trim();
  cloudConfig = {
    url: normalizedSupabaseUrl(FIXED_SUPABASE_URL || cloudConfig.url),
    anonKey: String(FIXED_SUPABASE_ANON_KEY || cloudConfig.anonKey).trim(),
    lineupKey,
  };
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
  if (!hasCloudConfig()) {
    setCloudStatus("Cloud: base config missing", true);
    return false;
  }
  setCloudStatus("Cloud: key ready");
  return true;
}

async function supabaseRequest(pathWithQuery, options = {}) {
  if (!hasCloudConfig()) {
    throw new Error("cloud config missing");
  }
  const res = await fetch(`${cloudConfig.url}/rest/v1/${pathWithQuery}`, {
    ...options,
    headers: {
      apikey: cloudConfig.anonKey,
      Authorization: `Bearer ${cloudConfig.anonKey}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`supabase ${res.status}: ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function cloudSaveLineup() {
  const payload = {
    lineup_id: cloudConfig.lineupKey,
    lineup_json: startingLineup,
    updated_at: new Date().toISOString(),
  };
  await supabaseRequest(`${SUPABASE_TABLE}?on_conflict=lineup_id`, {
    method: "POST",
    headers: {
      Prefer: "resolution=merge-duplicates,return=representation",
    },
    body: JSON.stringify(payload),
  });
}

async function cloudLoadLineup() {
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${cloudConfig.lineupKey}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  if (!Array.isArray(rows) || !rows.length) return false;
  const remote = rows[0]?.lineup_json;
  if (!Array.isArray(remote)) return false;
  startingLineup = normalizeLineupArray(remote);
  saveStartingLineup();
  return true;
}

async function cloudLineupExists(lineupId) {
  const id = String(lineupId || "").trim();
  if (!id) return false;
  const params = new URLSearchParams({
    select: "lineup_id",
    lineup_id: `eq.${id}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  return Array.isArray(rows) && rows.length > 0;
}

async function cloudDeleteLineupById(lineupId) {
  const id = String(lineupId || "").trim();
  if (!id) return;
  const params = new URLSearchParams({
    lineup_id: `eq.${id}`,
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "DELETE",
    headers: {
      Prefer: "return=representation",
    },
  });
  const deletedCount = Array.isArray(rows) ? rows.length : 0;
  if (deletedCount < 1) {
    throw new Error("delete_not_applied");
  }
}

function loadStartingLineup() {
  try {
    const raw = localStorage.getItem(LINEUP_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return;
    startingLineup = normalizeLineupArray(parsed);
  } catch (e) {
    console.warn("failed to load lineup", e);
  }
}

function saveStartingLineup() {
  localStorage.setItem(LINEUP_STORAGE_KEY, JSON.stringify(startingLineup));
}

function closeLineupModal() {
  pendingLineupPlayerId = null;
  pendingLineupMode = "starter";
  lineupSlotsLocked = false;
  lineupRegisterMode = "starter";
  if (!els.lineupModal) return;
  els.lineupModal.hidden = true;
}

function setLineupModalTitle(show, text = "スタメン登録") {
  if (!els.lineupTitle) return;
  els.lineupTitle.hidden = !show;
  if (show) els.lineupTitle.textContent = text;
}

function logoutLineupKey() {
  cloudConfig = {
    url: normalizedSupabaseUrl(FIXED_SUPABASE_URL || cloudConfig.url),
    anonKey: String(FIXED_SUPABASE_ANON_KEY || cloudConfig.anonKey).trim(),
    lineupKey: "",
  };
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
  setCloudStatus("Cloud: logged out");
  updateMenuState();
}

function closeSeasonModal() {
  pendingLineupSlotIndex = null;
  if (!els.seasonModal) return;
  els.seasonModal.hidden = true;
}

function syncSuccessorSourceInput() {
  if (!els.successorSourceType || !els.successorSourceCustomWrap) return;
  els.successorSourceCustomWrap.hidden = els.successorSourceType.value !== "custom";
}

function closeSuccessorSourceModal() {
  pendingSuccessorRegistration = null;
  if (els.successorSourceModal) els.successorSourceModal.hidden = true;
}

function openSuccessorSourceModal(player, slotIndex, season) {
  if (!els.successorSourceModal) return;
  pendingSuccessorRegistration = { playerId: player.id, slotIndex, season };
  if (els.successorSourceTarget) {
    els.successorSourceTarget.textContent = `${player.name} の所属チームを入力してください`;
  }
  if (els.successorSourceType) els.successorSourceType.value = "self";
  if (els.successorSourceInput) els.successorSourceInput.value = "";
  syncSuccessorSourceInput();
  els.successorSourceModal.hidden = false;
}

function getPlayerNameById(playerId) {
  const p = players.find((x) => x.id === playerId);
  return p?.name || `ID:${playerId}`;
}

function lineupPlayerFromEntry(entry) {
  const playerId = Number(entry?.playerId);
  if (!Number.isInteger(playerId)) return null;
  return players.find((x) => x.id === playerId) || null;
}

function getRemainingPeakPeriods(player, season) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  if (!periods.length) return 0;
  const seasons = periods.map((p) => p?.season).filter(Boolean);
  if (!seasons.length) return 0;
  let curIdx = seasons.findIndex((s) => s === season);
  if (curIdx < 0) curIdx = 0;

  const tiers = new Map(getPeakTimeline(player).map((x) => [x.season, x.tier]));
  const isPeakMain = (idx) => tiers.get(seasons[idx]) === "peak-main";

  if (isPeakMain(curIdx)) {
    let end = curIdx;
    while (end + 1 < seasons.length && isPeakMain(end + 1)) end += 1;
    return end - curIdx + 1;
  }

  let next = -1;
  for (let i = curIdx; i < seasons.length; i += 1) {
    if (isPeakMain(i)) {
      next = i;
      break;
    }
  }
  if (next < 0) return 0;
  let end = next;
  while (end + 1 < seasons.length && isPeakMain(end + 1)) end += 1;
  return end - curIdx + 1;
}

function shiftSeasonForEntry(player, currentSeason, delta) {
  const periods = Array.isArray(player?.periods) ? player.periods : [];
  if (!periods.length) return currentSeason || null;
  const seasons = periods.map((p) => p?.season).filter(Boolean);
  if (!seasons.length) return currentSeason || null;
  let idx = seasons.findIndex((s) => s === currentSeason);
  if (idx < 0) idx = 0;
  const nextIdx = Math.max(0, Math.min(seasons.length - 1, idx + delta));
  return seasons[nextIdx];
}

function remainingBadgeClass(remain) {
  if (remain <= 0) return "remain-0";
  if (remain === 1) return "remain-1";
  if (remain === 2) return "remain-2";
  if (remain === 3) return "remain-3";
  if (remain === 4) return "remain-4";
  return "remain-5p";
}

function remainingBadgeHtml(remain) {
  return `<span class="badge lineup-season remain-badge ${remainingBadgeClass(remain)}">残${remain}期</span>`;
}

function successorSummaryHtml(entry, currentRemaining) {
  const successor = normalizeSuccessor(entry?.successor);
  const successorId = Number(successor?.playerId);
  const successorPlayer = Number.isInteger(successorId) ? players.find((x) => x.id === successorId) : null;
  if (!successorPlayer) {
    return `
      <div class="lineup-successor is-empty">
        <div class="lineup-successor-arrow" aria-hidden="true">▶</div>
        <div class="lineup-empty-thumb"></div>
        <div class="lineup-successor-meta">
          <span class="slot-name">未登録</span>
        </div>
      </div>
    `;
  }

  const evalSeason = shiftSeasonForEntry(successorPlayer, successor?.season || null, Math.max(0, currentRemaining));
  const remain = getRemainingPeakPeriods(successorPlayer, evalSeason);
  const pos = (successorPlayer.position || "-").toUpperCase();
  const posClass = positionClass(pos);
  const typeBadges = categoryBadgesHtmlByPlayer(successorPlayer);
  return `
    <div class="lineup-successor">
      <div class="lineup-successor-arrow" aria-hidden="true">▶</div>
      <div class="lineup-thumb-wrap">
        <img loading="lazy" src="./images/chara/players/static/${successorPlayer.id}.gif" alt="${successorPlayer.name}" />
      </div>
      <div class="lineup-successor-meta">
        <div class="lineup-badges">
          <span class="badge pos-badge ${posClass}">${pos}</span>
          ${typeBadges}
          ${remainingBadgeHtml(remain)}
        </div>
        <span class="slot-name">${successorPlayer.name}</span>
      </div>
    </div>
  `;
}

function allowedSlotIndexesForPendingName() {
  const pendingId = Number(pendingLineupPlayerId);
  if (!Number.isInteger(pendingId)) return null;
  const pending = players.find((p) => p.id === pendingId);
  if (!pending) return null;

  const sameNameIndexes = startingLineup
    .map((entry, idx) => ({ player: lineupPlayerFromEntry(entry), idx }))
    .filter((row) => row.player && row.player.name === pending.name)
    .map((row) => row.idx);

  if (!sameNameIndexes.length) return null;
  return new Set(sameNameIndexes);
}

function renderLineupSlots() {
  if (!els.lineupSlots) return;
  const allowedIndexes = allowedSlotIndexesForPendingName();
  const miniCoreMetric = (metric, value) => {
    const bounded = Math.max(0, Math.min(10, Math.round(value || 0)));
    const keyClass =
      metric === "スピ" ? "m-speed" :
      metric === "テク" ? "m-tech" :
      "m-power";
    const cells = Array.from({ length: 10 }, (_, i) =>
      `<span class="gauge-cell${i < bounded ? " on" : ""}"></span>`
    ).join("");
    return `
      <div class="lineup-core-item ${keyClass}">
        <span class="lineup-core-key">${metricLabel(metric)}</span>
        <div class="lineup-core-body">
          <div class="gauge">${cells}</div>
          <span class="lineup-core-num">${value ?? "-"}</span>
        </div>
      </div>
    `;
  };

  const html = startingLineup.map((entry, idx) => {
    const slot = idx + 1;
    const playerId = Number(entry?.playerId);
    const player = lineupPlayerFromEntry(entry);
    const name = player ? player.name : "未登録";
    const hasPlayer = Number.isInteger(playerId) && !!player;
    const season = hasPlayer ? (entry?.season || null) : null;
    const seasonText = season ? `${season}目` : "-";
    const currentRemaining = hasPlayer ? getRemainingPeakPeriods(player, season) : 0;
    const disabledByNameRule = !!allowedIndexes && !allowedIndexes.has(idx);
    const disabledByLock = lineupSlotsLocked;
    const disabledByModeRule = lineupRegisterMode === "successor" && !hasPlayer;
    const pos = (player?.position || "-").toUpperCase();
    const posClass = positionClass(pos);
    const typeBadges = player
      ? categoryBadgesHtmlByPlayer(player)
      : `<span class="badge type-badge cat-na">-</span>`;
    const imageHtml = player
      ? `<img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${player.name}" />`
      : `<div class="lineup-empty-thumb"></div>`;
    const selectedPeriod = hasPlayer ? findPeriodBySeason(player, season) : null;
    const selectedMetrics = selectedPeriod?.metrics || (player ? getPeakMetrics(player) : null);
    const rightPaneHtml = player
      ? `
        ${lineupRegisterMode === "successor"
          ? successorSummaryHtml(entry, currentRemaining)
          : `
            <div class="lineup-core">
              ${miniCoreMetric("スピ", selectedMetrics?.["スピ"])}
              ${miniCoreMetric("テク", selectedMetrics?.["テク"])}
              ${miniCoreMetric("パワ", selectedMetrics?.["パワ"])}
            </div>
          `
        }
      `
      : "";
    const disabled = disabledByNameRule || disabledByLock || disabledByModeRule;
    return `
      <button type="button" class="lineup-slot${hasPlayer ? " has-player" : ""}${disabled ? " is-disabled" : ""}" data-slot-index="${idx}" ${disabled ? "disabled" : ""}>
        <span class="slot-no">${slot}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              ${typeBadges}
              <span class="badge lineup-season">${seasonText}</span>
            </div>
            <span class="slot-name">${name}</span>
          </div>
          ${rightPaneHtml}
        </div>
      </button>
    `;
  }).join("");
  els.lineupSlots.innerHTML = html;
}

function renderLineupModeSwitch() {
  if (els.lineupStarterMode) {
    els.lineupStarterMode.classList.toggle("is-active", lineupRegisterMode === "starter");
  }
  if (els.lineupSuccessorMode) {
    els.lineupSuccessorMode.classList.toggle("is-active", lineupRegisterMode === "successor");
  }
}

function openLineupModal(playerId) {
  pendingLineupPlayerId = playerId;
  pendingLineupMode = lineupRegisterMode;
  lineupSlotsLocked = false;
  setLineupModalTitle(true, lineupRegisterMode === "successor" ? "後継選手登録" : "スタメン登録");
  const player = players.find((p) => p.id === playerId);
  const allowedIndexes = allowedSlotIndexesForPendingName();
  if (els.lineupTarget) {
    const targetLabel = lineupRegisterMode === "successor" ? "後継選手として" : "";
    const slotLabel = lineupRegisterMode === "successor" ? "どのスタメン枠に登録しますか？" : "どのスタメン枠に登録しますか？";
    const base = player
      ? `${player.name} を${targetLabel}${slotLabel}`
      : `ID:${playerId} を${targetLabel}${slotLabel}`;
    els.lineupTarget.textContent = allowedIndexes
      ? `${base}（同名登録済みのため、同名枠への入れ替えのみ可能）`
      : base;
  }
  renderLineupModeSwitch();
  renderLineupSlots();
  if (els.lineupModal) {
    els.lineupModal.hidden = false;
  }
}

function openSeasonModal(player, slotIndex, mode = "starter") {
  if (!player || !els.seasonModal || !els.seasonSelect) return;
  const seasons = (player.periods || [])
    .map((p) => p?.season)
    .filter((s) => typeof s === "string" && s.length > 0);
  if (!seasons.length) return;

  pendingLineupPlayerId = player.id;
  pendingLineupSlotIndex = slotIndex;
  pendingLineupMode = mode;
  els.seasonSelect.innerHTML = seasons
    .map((season) => `<option value="${season}">${season}</option>`)
    .join("");
  if (els.seasonTarget) {
    els.seasonTarget.textContent = mode === "successor"
      ? `${player.name} を後継選手として何期目で登録しますか？`
      : `${player.name} を何期目で登録しますか？`;
  }
  els.seasonModal.hidden = false;
}

function toHiragana(s) {
  return (s || "")
    .replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60))
    .replace(/[・･·\.．]/g, "")
    .replace(/\s+/g, "");
}

function normalizedPlayerSearchName(player) {
  const base = String(player?.name || "");
  const ruby = String(player?.nameRuby || "");
  return toHiragana(`${base}${ruby}`.toLowerCase());
}

function hideNameSuggest() {
  if (!els.nameSuggest) return;
  els.nameSuggest.hidden = true;
  els.nameSuggest.innerHTML = "";
}

function getNameSuggestions(rawQuery, limit = 3) {
  const query = toHiragana(String(rawQuery || "").toLowerCase().trim());
  if (!query) return [];
  const seenName = new Set();
  const seenType = new Set();
  const nameHits = [];
  const typeHits = [];
  for (const player of players) {
    const name = String(player?.name || "");
    const type = String(player?.playType || "");
    if (!name) continue;
    const norm = normalizedPlayerSearchName(player);
    const typeNorm = toHiragana(type.toLowerCase());
    const nameIdx = norm.indexOf(query);
    const typeIdx = typeNorm.indexOf(query);
    if (nameIdx >= 0 && !seenName.has(name)) {
      seenName.add(name);
      const score = nameIdx === 0 ? 0 : (nameIdx + 1);
      nameHits.push({ value: name, score, len: name.length });
    }
    if (type && typeIdx >= 0 && !seenType.has(type)) {
      seenType.add(type);
      const score = typeIdx === 0 ? 0 : (typeIdx + 1);
      typeHits.push({ value: type, score, len: type.length });
    }
  }
  const sorter = (a, b) => a.score - b.score || a.len - b.len || a.value.localeCompare(b.value, "ja");
  nameHits.sort(sorter);
  typeHits.sort(sorter);
  if (typeHits.length > 0) return typeHits.slice(0, limit).map((x) => x.value);
  return nameHits.slice(0, limit).map((x) => x.value);
}

function updateNameSuggest() {
  if (!els.nameSuggest || !els.nameQuery) return;
  const list = getNameSuggestions(els.nameQuery.value, 3);
  if (!list.length) {
    hideNameSuggest();
    return;
  }
  els.nameSuggest.innerHTML = list
    .map((name) => `<button type="button" class="name-suggest-item" data-name="${name}">${name}</button>`)
    .join("");
  els.nameSuggest.hidden = false;
}

function addConditionRow(defaults = {}) {
  const node = els.conditionTemplate.content.firstElementChild.cloneNode(true);
  const metric = node.querySelector(".metric");
  const op = node.querySelector(".op");
  const value1 = node.querySelector(".value1");
  const value2 = node.querySelector(".value2");
  const remove = node.querySelector(".remove");

  CONDITION_METRICS.forEach((m) => {
    const option = document.createElement("option");
    option.value = m;
    option.textContent = metricLabel(m);
    metric.appendChild(option);
  });

  metric.value = defaults.metric || "スピ";
  op.value = defaults.op || "gte";
  value1.value = defaults.value1 ?? "";
  value2.value = defaults.value2 ?? "";

  const syncBetween = () => {
    node.classList.toggle("between", op.value === "between");
  };

  op.addEventListener("change", () => {
    syncBetween();
  });
  remove.addEventListener("click", () => {
    node.remove();
  });

  syncBetween();
  els.conditions.appendChild(node);
}

function getConditions() {
  return [...els.conditions.querySelectorAll(".condition-row")]
    .map((row) => {
      const metric = row.querySelector(".metric").value;
      const op = row.querySelector(".op").value;
      const v1 = Number(row.querySelector(".value1").value);
      const v2 = Number(row.querySelector(".value2").value);

      if (!metric || Number.isNaN(v1)) {
        return null;
      }

      if (op === "between") {
        if (Number.isNaN(v2)) return null;
        return { metric, op, value1: Math.min(v1, v2), value2: Math.max(v1, v2) };
      }

      return { metric, op, value1: v1 };
    })
    .filter(Boolean);
}

function checkValueCondition(value, condition) {
  if (typeof value !== "number" || Number.isNaN(value)) return false;
  switch (condition.op) {
    case "eq":
      return value === condition.value1;
    case "gte":
      return value >= condition.value1;
    case "lte":
      return value <= condition.value1;
    case "between":
      return value >= condition.value1 && value <= condition.value2;
    default:
      return false;
  }
}

function getCategory(player) {
  if (player.category) return player.category;
  const hasCM = !!player.flags?.CM;
  const hasSS = !!player.flags?.SS;
  if (hasCM && hasSS) return "CM/SS";
  if (hasCM) return "CM";
  if (hasSS) return "SS";
  return "NR";
}

function typeClassByPlayer(player) {
  const typeLabel = getCategory(player);
  if (typeLabel === "NR") {
    const rate = Number(player?.rate);
    if (rate === 7) return "cat-nr-r7";
    if (rate === 5 || rate === 6) return "cat-nr-r56";
    if (rate === 4) return "cat-nr-r4";
    return "cat-nr-r13";
  }
  if (typeLabel === "SS") return "cat-ss";
  if (typeLabel === "CM") return "cat-cm";
  if (typeLabel === "CM/SS") return "cat-cmss";
  if (typeLabel === "CC") return "cat-cc";
  return "cat-na";
}

function categoryBadgesHtmlByPlayer(player) {
  const typeLabel = getCategory(player);
  if (typeLabel === "CM/SS") {
    return `<span class="badge type-badge cat-ss">SS</span><span class="badge type-badge cat-cm">CM</span>`;
  }
  const typeClass = typeClassByPlayer(player);
  return `<span class="badge type-badge ${typeClass}">${typeLabel}</span>`;
}

function formatEventPeriod(start, end) {
  const normalize = (s) => {
    const raw = String(s || "").trim();
    if (!raw) return "";
    return raw.slice(0, 10);
  };
  const s = normalize(start);
  const e = normalize(end);
  if (s && e) return `${s} - ${e}`;
  if (s) return s;
  if (e) return e;
  return "-";
}

function closeScoutListModal() {
  if (!els.scoutListModal) return;
  els.scoutListModal.hidden = true;
}

function renderListResultsByEvent(eventId, source) {
  const isCM = source === "cm";
  const eventMap = isCM ? cmEventsByEventId : scoutsByEventId;
  if (!eventMap.has(eventId)) return;

  // Reset all filters, then keep only the selected SS/CM event filter active.
  els.conditions.innerHTML = "";
  els.nameQuery.value = "";
  hideNameSuggest();
  if (els.positionFilter) els.positionFilter.value = "";
  if (els.aptitudePositionFilter) els.aptitudePositionFilter.value = "";
  if (els.aptitudeIncludeSix) els.aptitudeIncludeSix.checked = false;
  syncAptitudeAreaLabel();

  [
    els.nrWhiteOnly, els.nrBronzeOnly, els.nrSilverOnly, els.nrGoldOnly, els.nrAllOnly,
    els.ssOnly, els.cmOnly, els.ccOnly,
  ].forEach((el) => setCategoryChipActive(el, false));
  setCategoryChipActive(isCM ? els.cmOnly : els.ssOnly, true);

  updateScoutFilterVisibility();
  updateCMFilterVisibility();

  if (els.scoutEventFilter) els.scoutEventFilter.value = isCM ? "" : String(eventId);
  if (els.cmEventFilter) els.cmEventFilter.value = isCM ? String(eventId) : "";

  render();

  // Move viewport to the top of result section.
  // Run once immediately and once after modal-close scroll restoration.
  const scrollToResultsTop = () => {
    const resultHead = document.querySelector(".result-head");
    if (resultHead) {
      resultHead.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  scrollToResultsTop();
  setTimeout(scrollToResultsTop, 120);
}

function openScoutListModal(playerId) {
  if (!els.scoutListModal || !els.scoutListItems) return;
  const player = players.find((p) => p.id === playerId);
  if (!player) return;
  const scoutHistory = Array.isArray(player.scoutHistory)
    ? player.scoutHistory.map((h) => ({ ...h, source: "scout" }))
    : [];
  const cmHistory = Array.isArray(player.cmHistory)
    ? player.cmHistory.map((h) => ({ ...h, source: "cm" }))
    : [];
  const history = [...scoutHistory, ...cmHistory];
  history.sort((a, b) => {
    const as = String(a?.start || "");
    const bs = String(b?.start || "");
    if (as !== bs) return bs.localeCompare(as);
    return Number(b?.eventId || 0) - Number(a?.eventId || 0);
  });
  if (els.scoutListTarget) {
    els.scoutListTarget.textContent = `${player.name} の履歴`;
  }
  if (!history.length) {
    els.scoutListItems.innerHTML = `<div class="scout-list-empty">履歴がありません</div>`;
  } else {
    els.scoutListItems.innerHTML = history.map((h) => {
      const eventId = Number(h?.eventId || 0);
      const source = String(h?.source || "scout");
      const typeLabel = source === "cm" ? "CM" : "SS";
      const fallback = source === "cm" ? `CM ${eventId}` : `Scout ${eventId}`;
      const name = String(h?.name || fallback);
      const period = formatEventPeriod(h?.start, h?.end);
      return `
        <button type="button" class="scout-list-item" data-event-id="${eventId}" data-source="${source}">
          <span class="scout-list-meta">${typeLabel}</span>
          <span class="scout-list-name">${name}</span>
          <span class="scout-list-period">${period}</span>
        </button>
      `;
    }).join("");
  }
  els.scoutListModal.hidden = false;
}

function positionClass(position) {
  const pos = (position || "-").toUpperCase();
  if (pos === "GK") return "pos-gk";
  if (pos === "DF") return "pos-df";
  if (pos === "MF") return "pos-mf";
  if (pos === "FW") return "pos-fw";
  return "";
}

function getMatchingPeriods(player, conditions) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  if (!conditions.length) return periods;

  return periods.filter((period) => {
    const metrics = period?.metrics || {};
    const checks = conditions.map((c) => {
      const targetValue = c.metric === "ID" ? Number(player?.id) : metrics[c.metric];
      return checkValueCondition(targetValue, c);
    });
    return checks.every(Boolean);
  });
}

const CORE_METRICS = ["スピ", "テク", "パワ"];

function coreTotal(metrics, selected = CORE_METRICS) {
  return selected.reduce((sum, metric) => sum + (metrics?.[metric] || 0), 0);
}

function getStrengthMetrics(player) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
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

  if (first.value === second.value && second.value === third.value) {
    return [...CORE_METRICS];
  }

  if (second.value === third.value && first.value > second.value) {
    const tie = [second.metric, third.metric].sort((a, b) => {
      if (totalByMetric[b] !== totalByMetric[a]) return totalByMetric[b] - totalByMetric[a];
      return CORE_METRICS.indexOf(a) - CORE_METRICS.indexOf(b);
    });
    const picked = [first.metric, tie[0]];
    const maxByMetric = CORE_METRICS.reduce((acc, metric) => {
      acc[metric] = Math.max(...periods.map((p) => (p?.metrics || {})[metric] || 0));
      return acc;
    }, {});
    const hasAnyEightPlus = CORE_METRICS.some((metric) => (maxByMetric[metric] || 0) >= 8);
    if (hasAnyEightPlus) {
      const filtered = picked.filter((metric) => (maxByMetric[metric] || 0) >= 8);
      if (filtered.length === 1) return filtered;
      if (filtered.length === 2) return filtered;
    }
    return picked;
  }

  const picked = [first.metric, second.metric];
  const maxByMetric = CORE_METRICS.reduce((acc, metric) => {
    acc[metric] = Math.max(...periods.map((p) => (p?.metrics || {})[metric] || 0));
    return acc;
  }, {});
  const hasAnyEightPlus = CORE_METRICS.some((metric) => (maxByMetric[metric] || 0) >= 8);
  if (hasAnyEightPlus) {
    const filtered = picked.filter((metric) => (maxByMetric[metric] || 0) >= 8);
    if (filtered.length === 1) return filtered;
    if (filtered.length === 2) return filtered;
  }
  return picked;
}

function getPeakMetrics(player) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  if (!periods.length) return player.maxMetrics || {};
  const strengthMetrics = getStrengthMetrics(player);

  let best = periods[0]?.metrics || {};
  let bestScore = coreTotal(best, strengthMetrics);

  for (let i = 1; i < periods.length; i += 1) {
    const m = periods[i]?.metrics || {};
    const score = coreTotal(m, strengthMetrics);
    if (score > bestScore) {
      best = m;
      bestScore = score;
    }
  }

  return best;
}

function getPeakTimeline(player) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  if (!periods.length) return [];
  const strengthMetrics = getStrengthMetrics(player);

  const scored = periods.map((p) => {
    const m = p?.metrics || {};
    const score = coreTotal(m, strengthMetrics);
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

function getGridPosCellValue(grid, code) {
  const m = {
    GK: [4, 1],
    RSB: [3, 2], CB: [3, 1], LSB: [3, 0],
    RDM: [2, 2], CDM: [2, 1], LDM: [2, 0],
    RMF: [1, 2], OMF: [1, 1], LMF: [1, 0],
    RWG: [0, 2], CF: [0, 1], LWG: [0, 0],
  };
  const key = String(code || "").toUpperCase();
  const rc = m[key];
  if (!rc) return null;
  const [r, c] = rc;
  const row = grid?.[r];
  if (!Array.isArray(row)) return null;
  const v = row[c];
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function hasAptitudeAtLeast(player, code, threshold = 6) {
  if (!code) return true;
  const segments = Array.isArray(player?.positionHeatmaps) ? player.positionHeatmaps : [];
  return segments.some((seg) => {
    const grid = Array.isArray(seg?.grid) ? seg.grid : [];
    const v = getGridPosCellValue(grid, code);
    return typeof v === "number" && v >= threshold;
  });
}

function isNRWhiteByRate(player) {
  const rate = Number(player?.rate);
  return rate !== 4 && rate !== 5 && rate !== 6 && rate !== 7;
}

function isCategoryChipActive(el) {
  return !!el?.classList.contains("is-active");
}

function setCategoryChipActive(el, active) {
  if (!el) return;
  el.classList.toggle("is-active", !!active);
  el.setAttribute("aria-pressed", active ? "true" : "false");
}

function syncNRAllChip() {
  if (!els.nrAllOnly || !els.nrWhiteOnly || !els.nrBronzeOnly || !els.nrSilverOnly || !els.nrGoldOnly) return;
  const allActive =
    isCategoryChipActive(els.nrWhiteOnly) &&
    isCategoryChipActive(els.nrBronzeOnly) &&
    isCategoryChipActive(els.nrSilverOnly) &&
    isCategoryChipActive(els.nrGoldOnly);
  setCategoryChipActive(els.nrAllOnly, allActive);
}

function renderScoutEventFilterOptions() {
  if (!els.scoutEventFilter) return;
  const current = String(els.scoutEventFilter.value || "");
  const sorted = [...scouts].sort((a, b) => {
    const as = String(a?.start || "");
    const bs = String(b?.start || "");
    if (as !== bs) return bs.localeCompare(as);
    return Number(b?.eventId || 0) - Number(a?.eventId || 0);
  });
  const options = ['<option value="">ALL</option>'];
  sorted.forEach((s) => {
    const eventId = Number(s?.eventId || 0);
    if (!Number.isInteger(eventId) || eventId <= 0) return;
    const name = String(s?.name || `Scout ${eventId}`);
    const period = formatEventPeriod(s?.start, s?.end);
    options.push(`<option value="${eventId}">${name} (${period})</option>`);
  });
  els.scoutEventFilter.innerHTML = options.join("");
  if (current) els.scoutEventFilter.value = current;
}

function renderCMEventFilterOptions() {
  if (!els.cmEventFilter) return;
  const current = String(els.cmEventFilter.value || "");
  const sorted = [...cmEvents].sort((a, b) => {
    const as = String(a?.start || "");
    const bs = String(b?.start || "");
    if (as !== bs) return bs.localeCompare(as);
    return Number(b?.eventId || 0) - Number(a?.eventId || 0);
  });
  const options = ['<option value="">ALL</option>'];
  sorted.forEach((s) => {
    const eventId = Number(s?.eventId || 0);
    if (!Number.isInteger(eventId) || eventId <= 0) return;
    const name = String(s?.name || `CM ${eventId}`);
    const period = formatEventPeriod(s?.start, s?.end);
    options.push(`<option value="${eventId}">${name} (${period})</option>`);
  });
  els.cmEventFilter.innerHTML = options.join("");
  if (current) els.cmEventFilter.value = current;
}

function updateScoutFilterVisibility() {
  if (!els.scoutFilterWrap || !els.scoutEventFilter) return;
  const show = isCategoryChipActive(els.ssOnly);
  els.scoutFilterWrap.hidden = !show;
  if (!show) {
    els.scoutEventFilter.value = "";
    return;
  }
  renderScoutEventFilterOptions();
}

function updateCMFilterVisibility() {
  if (!els.cmFilterWrap || !els.cmEventFilter) return;
  const show = isCategoryChipActive(els.cmOnly);
  els.cmFilterWrap.hidden = !show;
  if (!show) {
    els.cmEventFilter.value = "";
    return;
  }
  renderCMEventFilterOptions();
}

function filterPlayers(conditions = getConditions()) {
  const query = toHiragana(els.nameQuery.value.trim().toLowerCase());
  const positionFilter = els.positionFilter.value;
  const aptitudePosFilter = (els.aptitudePositionFilter?.value || "").toUpperCase();
  const aptitudeThreshold = els.aptitudeIncludeSix?.checked ? 6 : 7;
  const cmOnly = isCategoryChipActive(els.cmOnly);
  const ssOnly = isCategoryChipActive(els.ssOnly);
  const nrWhiteOnly = isCategoryChipActive(els.nrWhiteOnly);
  const nrBronzeOnly = isCategoryChipActive(els.nrBronzeOnly);
  const nrSilverOnly = isCategoryChipActive(els.nrSilverOnly);
  const nrGoldOnly = isCategoryChipActive(els.nrGoldOnly);
  const nrAllOnly = isCategoryChipActive(els.nrAllOnly);
  const ccOnly = isCategoryChipActive(els.ccOnly);
  const scoutEventFilter = Number(els.scoutEventFilter?.value || 0);
  const cmEventFilter = Number(els.cmEventFilter?.value || 0);

  return players.filter((player) => {
    const category = getCategory(player);
    const playerName = normalizedPlayerSearchName(player);
    const playerType = toHiragana((player.playType || "").toLowerCase());
    if (query && !playerName.includes(query) && !playerType.includes(query)) {
      return false;
    }
    if (positionFilter && player.position !== positionFilter) {
      return false;
    }
    if (aptitudePosFilter && !hasAptitudeAtLeast(player, aptitudePosFilter, aptitudeThreshold)) {
      return false;
    }

    const hasCategoryFilter =
      cmOnly || ssOnly || nrWhiteOnly || nrBronzeOnly || nrSilverOnly || nrGoldOnly || nrAllOnly || ccOnly;
    if (hasCategoryFilter) {
      const rate = Number(player?.rate);
      const isNR = category === "NR";
      const nrMatched =
        (nrAllOnly && isNR) ||
        (nrWhiteOnly && isNR && isNRWhiteByRate(player)) ||
        (nrBronzeOnly && isNR && rate === 4) ||
        (nrSilverOnly && isNR && (rate === 5 || rate === 6)) ||
        (nrGoldOnly && isNR && rate === 7);
      const categoryMatched =
        nrMatched ||
        (ssOnly && (category === "SS" || category === "CM/SS")) ||
        (cmOnly && (category === "CM" || category === "CM/SS")) ||
        (ccOnly && category === "CC");
      if (!categoryMatched) return false;
    }

    if (scoutEventFilter > 0) {
      const scoutHistory = Array.isArray(player.scoutHistory) ? player.scoutHistory : [];
      if (!scoutHistory.some((x) => Number(x?.eventId || 0) === scoutEventFilter)) {
        return false;
      }
    }
    if (cmEventFilter > 0) {
      const cmHistory = Array.isArray(player.cmHistory) ? player.cmHistory : [];
      if (!cmHistory.some((x) => Number(x?.eventId || 0) === cmEventFilter)) {
        return false;
      }
    }

    if (!conditions.length) {
      return true;
    }

    return getMatchingPeriods(player, conditions).length > 0;
  });
}

function periodTableHtml(player, staticImg, actionImg) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
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
          <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
        </div>
        ${positionHeatmapsHtml(player)}
      </div>
      <div class="periods-scroll">
        <table class="periods-table">
          <thead>
            <tr><th>期</th>${header}</tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function positionHeatmapsHtml(player) {
  const segments = Array.isArray(player.positionHeatmaps) ? player.positionHeatmaps : [];
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
      <div class="pos-heatmaps-track">
        ${items}
      </div>
    </div>
  `;
}

function profileViewHtml(player, staticImg, actionImg) {
  const nationality = player.nationality || (player.nationId != null ? `国籍ID:${player.nationId}` : "-");
  const playType = player.playType || "-";
  const height = Number(player.height);
  const weight = Number(player.weight);
  const hwText = `${Number.isFinite(height) && height > 0 ? height : "-"}cm / ${Number.isFinite(weight) && weight > 0 ? weight : "-"}kg`;
  const description = (player.description || "").trim() || "説明なし";

  return `
    <div class="profile-view">
      <div class="media-row">
        <div class="thumbs">
          <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
        </div>
        <div class="profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nationality}</span></div>
          <div class="profile-item"><span class="k">身長体重</span><span class="v">${hwText}</span></div>
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
        <button
          type="button"
          class="card-tab${viewMode === t.mode ? " is-active" : ""}"
          data-player-id="${playerId}"
          data-mode="${t.mode}"
          role="tab"
          aria-selected="${viewMode === t.mode ? "true" : "false"}"
        >${t.label}</button>
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

function cardHtml(player) {
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
    const max = 10;
    const bounded = Math.max(0, Math.min(max, Math.round(value)));
    const metricClass =
      metric === "スピ" ? "m-speed" :
      metric === "テク" ? "m-tech" :
      metric === "パワ" ? "m-power" :
      metric === "個性" ? "m-unique" : "";
    const cells = Array.from({ length: 10 }, (_, i) =>
      `<span class="gauge-cell${i < bounded ? " on" : ""}"></span>`
    ).join("");
    return `
      <div class="metric-box ${metricClass}">
        <span class="metric-key">${metricLabel(metric)}</span>
        <div class="metric-body">
          <div class="gauge">
            ${cells}
          </div>
          <span class="metric-num">${v == null ? "-" : v}</span>
        </div>
      </div>
    `;
  };

  const mainMetrics = ["スピ", "テク", "パワ", "個性"];
  const group1 = ["スタ", "ラフ", "人気"];
  const group2 = ["PK", "FK", "CK", "CP"];
  const typeLabel = getCategory(player);
  const typeBadges = categoryBadgesHtmlByPlayer(player);
  const hasScoutHistory = Array.isArray(player.scoutHistory) && player.scoutHistory.length > 0;
  const hasCMHistory = Array.isArray(player.cmHistory) && player.cmHistory.length > 0;
  const hasAnyListHistory = hasScoutHistory || hasCMHistory;
  const showScoutButton = typeLabel === "SS" || typeLabel === "CM" || typeLabel === "CM/SS";
  const pos = (player.position || "-").toUpperCase();
  const posClass = positionClass(pos);
  const peakBlock = `<div class="peak-periods peak-in-body">${peakHtml}</div>`;
  let normalViewHtml = `<div class="param-view deferred-pane"></div>`;
  if (viewMode === 0) {
    const mind = {
      zisei: displayMetrics?.["知性"] ?? 0,
      kansei: displayMetrics?.["感性"] ?? 0,
      kojin: displayMetrics?.["個人"] ?? 0,
      soshiki: displayMetrics?.["組織"] ?? 0,
    };

    const cx = 70;
    const cy = 70;
    const r = 54;
    const nTop = Math.max(0, Math.min(30, mind.zisei)) / 30;
    const nRight = Math.max(0, Math.min(30, mind.soshiki)) / 30;
    const nBottom = Math.max(0, Math.min(30, mind.kansei)) / 30;
    const nLeft = Math.max(0, Math.min(30, mind.kojin)) / 30;
    const pTop = `${cx},${cy - r * nTop}`;
    const pRight = `${cx + r * nRight},${cy}`;
    const pBottom = `${cx},${cy + r * nBottom}`;
    const pLeft = `${cx - r * nLeft},${cy}`;
    const areaPoints = `${pTop} ${pRight} ${pBottom} ${pLeft}`;
    normalViewHtml = `
      <div class="param-view">
          <div class="media-row">
            <div class="thumbs">
              <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
              <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
            </div>
            <div class="mind-chart" aria-label="知性感性個人組織チャート">
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
        <div class="metric-group">
          <div class="metrics group-4">${group2.map(metricBox).join("")}</div>
        </div>
        <div class="metric-group">
          <div class="metrics group-4">${group1.map(metricBox).join("")}</div>
        </div>
      </div>
      </div>
    `;
  }
  const detailViewHtml = viewMode === 1
    ? periodTableHtml(player, staticImg, actionImg)
    : `<div class="expanded-view deferred-pane"></div>`;
  const thirdViewHtml = viewMode === 2
    ? profileViewHtml(player, staticImg, actionImg)
    : `<div class="profile-view deferred-pane"></div>`;
  const bodyHtml = swipeDeckHtml(viewMode, normalViewHtml, detailViewHtml, thirdViewHtml);
  const cardStateClass = viewMode === 1 ? "is-expanded" : "is-collapsed";

  return `
    <article class="card ${cardStateClass} mode-${viewMode}" data-player-id="${player.id}">
      <div class="card-top">
        ${cardTabsHtml(player.id, viewMode)}
        ${showScoutButton ? `<button type="button" class="scout-list-toggle" data-player-id="${player.id}" aria-label="履歴" ${hasAnyListHistory ? "" : "disabled"}>List</button>` : ""}
        <button type="button" class="lineup-toggle" data-player-id="${player.id}" aria-label="スタメン登録">Add</button>
        <span class="card-id">ID: ${player.id}</span>
        <div class="card-head-main">
          <h3 class="card-name">
            <span class="badge pos-badge ${posClass}">${pos}</span>
            ${typeBadges}
            <span>${player.name}</span>
          </h3>
        </div>
      </div>
      <div class="card-body">
        ${bodyHtml}
      </div>
    </article>
  `;
}

function rerenderSingleCard(playerId) {
  const target = els.results.querySelector(`.card[data-player-id="${playerId}"]`);
  if (!target) {
    render();
    return;
  }
  const player = players.find((p) => p.id === playerId);
  if (!player) return;

  const host = document.createElement("div");
  host.innerHTML = cardHtml(player).trim();
  const next = host.firstElementChild;
  if (!next) return;
  target.replaceWith(next);
}

function render() {
  renderJobToken += 1;
  const conditions = getConditions();
  const filtered = filterPlayers(conditions);
  const hasIdCondition = conditions.some((c) => c?.metric === "ID");
  const scoutEventFilter = Number(els.scoutEventFilter?.value || 0);
  const cmEventFilter = Number(els.cmEventFilter?.value || 0);
  const categoryRank = {
    "NR": 0,
    "CC": 1,
    "SS": 2,
    "CM": 3,
    "CM/SS": 3,
    "NA": 4,
    "RT": 99,
  };
  if (hasIdCondition) {
    filtered.sort((a, b) => Number(a.id || 0) - Number(b.id || 0));
  } else if (cmEventFilter > 0) {
    const event = cmEventsByEventId.get(cmEventFilter);
    const orderMap = new Map(
      (Array.isArray(event?.playerIds) ? event.playerIds : [])
        .map((id, idx) => [Number(id), idx]),
    );
    filtered.sort((a, b) => {
      const ai = orderMap.has(a.id) ? orderMap.get(a.id) : Number.MAX_SAFE_INTEGER;
      const bi = orderMap.has(b.id) ? orderMap.get(b.id) : Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
      const ar = categoryRank[getCategory(a)] ?? 50;
      const br = categoryRank[getCategory(b)] ?? 50;
      if (ar !== br) return ar - br;
      return (b.bestTotal - a.bestTotal) || a.name.localeCompare(b.name, "ja");
    });
  } else if (scoutEventFilter > 0) {
    const scout = scoutsByEventId.get(scoutEventFilter);
    const orderMap = new Map(
      (Array.isArray(scout?.playerIds) ? scout.playerIds : [])
        .map((id, idx) => [Number(id), idx]),
    );
    filtered.sort((a, b) => {
      const ai = orderMap.has(a.id) ? orderMap.get(a.id) : Number.MAX_SAFE_INTEGER;
      const bi = orderMap.has(b.id) ? orderMap.get(b.id) : Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
      const ar = categoryRank[getCategory(a)] ?? 50;
      const br = categoryRank[getCategory(b)] ?? 50;
      if (ar !== br) return ar - br;
      return (b.bestTotal - a.bestTotal) || a.name.localeCompare(b.name, "ja");
    });
  } else {
    filtered.sort((a, b) => {
      const ar = categoryRank[getCategory(a)] ?? 50;
      const br = categoryRank[getCategory(b)] ?? 50;
      if (ar !== br) return ar - br;
      return (b.bestTotal - a.bestTotal) || a.name.localeCompare(b.name, "ja");
    });
  }
  currentFilteredPlayers = filtered;
  renderedCount = 0;
  els.results.innerHTML = "";
  renderNextBatch(true);
}

function updateResultSummary() {
  const total = currentFilteredPlayers.length;
  if (total > renderedCount) {
    els.resultCount.textContent = `${total} results (showing ${renderedCount})`;
  } else {
    els.resultCount.textContent = `${total} results`;
  }
  if (els.loadMoreResults) {
    els.loadMoreResults.hidden = renderedCount >= total;
  }
}

function renderNextBatch(reset = false) {
  const jobToken = ++renderJobToken;
  if (reset) {
    renderedCount = 0;
    els.results.innerHTML = "";
  }
  const total = currentFilteredPlayers.length;
  if (renderedCount >= total) {
    updateResultSummary();
    return;
  }
  const nextCount = Math.min(total, renderedCount + RENDER_BATCH_SIZE);
  const appendStep = () => {
    if (jobToken !== renderJobToken) return;
    if (renderedCount >= nextCount) {
      updateResultSummary();
      return;
    }
    const frameCount = Math.min(RENDER_CARDS_PER_FRAME, nextCount - renderedCount);
    const chunk = currentFilteredPlayers.slice(renderedCount, renderedCount + frameCount);
    els.results.insertAdjacentHTML("beforeend", chunk.map((p) => cardHtml(p)).join(""));
    renderedCount += frameCount;
    updateResultSummary();
    if (renderedCount < nextCount) {
      requestAnimationFrame(appendStep);
    }
  };
  requestAnimationFrame(appendStep);
}

async function init() {
  setupModalScrollLock();
  loadStartingLineup();
  loadCloudConfig();
  setCloudStatus(hasCloudConfig() ? "Cloud: ready" : "Cloud: not configured");
  updateMenuState();
  syncMenuButtonSize();
  window.addEventListener("resize", syncMenuButtonSize);

  els.addCondition.addEventListener("click", () => {
    addConditionRow({ metric: "スピ", op: "gte", value1: "" });
  });

  els.resetCondition.addEventListener("click", () => {
    els.conditions.innerHTML = "";
    els.nameQuery.value = "";
    hideNameSuggest();
    [
      els.nrWhiteOnly, els.nrBronzeOnly, els.nrSilverOnly, els.nrGoldOnly, els.nrAllOnly,
      els.ssOnly, els.cmOnly, els.ccOnly,
    ].forEach((el) => setCategoryChipActive(el, false));
    els.positionFilter.value = "";
    if (els.aptitudePositionFilter) els.aptitudePositionFilter.value = "";
    if (els.aptitudeIncludeSix) els.aptitudeIncludeSix.checked = false;
    if (els.scoutEventFilter) els.scoutEventFilter.value = "";
    if (els.cmEventFilter) els.cmEventFilter.value = "";
    syncAptitudeAreaLabel();
    updateScoutFilterVisibility();
    updateCMFilterVisibility();
  });
  if (els.aptitudeIncludeSix) {
    els.aptitudeIncludeSix.addEventListener("change", syncAptitudeAreaLabel);
  }
  if (els.nrAllOnly) {
    els.nrAllOnly.addEventListener("click", () => {
      const next = !isCategoryChipActive(els.nrAllOnly);
      [els.nrAllOnly, els.nrWhiteOnly, els.nrBronzeOnly, els.nrSilverOnly, els.nrGoldOnly]
        .forEach((el) => setCategoryChipActive(el, next));
      updateScoutFilterVisibility();
      updateCMFilterVisibility();
    });
  }
  [els.nrWhiteOnly, els.nrBronzeOnly, els.nrSilverOnly, els.nrGoldOnly].forEach((el) => {
    if (!el) return;
    el.addEventListener("click", () => {
      setCategoryChipActive(el, !isCategoryChipActive(el));
      syncNRAllChip();
      updateScoutFilterVisibility();
      updateCMFilterVisibility();
    });
  });
  [els.ccOnly, els.ssOnly, els.cmOnly].forEach((el) => {
    if (!el) return;
    el.addEventListener("click", () => {
      setCategoryChipActive(el, !isCategoryChipActive(el));
      updateScoutFilterVisibility();
      updateCMFilterVisibility();
    });
  });

  els.applySearch.addEventListener("click", render);
  if (els.nameQuery) {
    els.nameQuery.addEventListener("input", updateNameSuggest);
    els.nameQuery.addEventListener("focus", updateNameSuggest);
  }
  if (els.nameSuggest) {
    els.nameSuggest.addEventListener("click", (e) => {
      const btn = e.target.closest(".name-suggest-item");
      if (!btn || !els.nameQuery) return;
      const name = String(btn.dataset.name || "");
      els.nameQuery.value = name;
      hideNameSuggest();
      els.nameQuery.focus();
    });
  }
  if (els.loadMoreResults) {
    els.loadMoreResults.addEventListener("click", () => renderNextBatch(false));
  }
  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => {
      if (!els.menuPanel) return;
      els.menuPanel.classList.toggle("is-open");
    });
  }
  if (els.playersButton) {
    els.playersButton.addEventListener("click", () => {
      closeMenuPanel();
    });
  }
  if (els.myTeamButton) {
    els.myTeamButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./myteam.html";
    });
  }
  if (els.formationsButton) {
    els.formationsButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./formations.html";
    });
  }
  if (els.coachesButton) {
    els.coachesButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./coaches.html";
    });
  }
  if (els.loginButton) {
    els.loginButton.addEventListener("click", () => {
      closeMenuPanel();
      openLoginModal();
    });
  }
  const pageParams = new URLSearchParams(window.location.search);
  if (pageParams.get("openLogin") === "1") {
    openLoginModal();
    pageParams.delete("openLogin");
    const next = `${window.location.pathname}${pageParams.toString() ? `?${pageParams.toString()}` : ""}${window.location.hash || ""}`;
    window.history.replaceState({}, "", next);
  }
  if (els.logoutButton) {
    els.logoutButton.addEventListener("click", () => {
      closeMenuPanel();
      logoutLineupKey();
    });
  }
  document.addEventListener("click", (e) => {
    if (!els.menuPanel || !els.menuButton) return;
    if (!els.menuPanel.classList.contains("is-open")) return;
    if (e.target.closest("#menuButton") || e.target.closest("#menuPanel")) return;
    closeMenuPanel();
  });
  document.addEventListener("click", (e) => {
    if (!els.nameSuggest || !els.nameQuery || els.nameSuggest.hidden) return;
    if (e.target.closest("#nameQuery") || e.target.closest("#nameSuggest")) return;
    hideNameSuggest();
  });
  els.results.addEventListener("click", (e) => {
    const scoutBtn = e.target.closest(".scout-list-toggle");
    if (scoutBtn) {
      const scoutId = Number(scoutBtn.dataset.playerId);
      if (Number.isInteger(scoutId)) {
        openScoutListModal(scoutId);
      }
      return;
    }
    const lineupBtn = e.target.closest(".lineup-toggle");
    if (lineupBtn) {
      const lineupId = Number(lineupBtn.dataset.playerId);
      if (Number.isInteger(lineupId)) {
        if (!isLoggedIn()) {
          pendingLoginForAddPlayerId = lineupId;
          openLoginModal();
        } else {
          openLineupModal(lineupId);
        }
      }
      return;
    }
    const tabBtn = e.target.closest(".card-tab");
    if (!tabBtn) return;
    const id = Number(tabBtn.dataset.playerId);
    const mode = Number(tabBtn.dataset.mode);
    if (!Number.isInteger(id)) return;
    if (!Number.isInteger(mode) || mode < 0 || mode > 2) return;
    cardViewModeById.set(id, mode);
    rerenderSingleCard(id);
  });

  if (els.lineupBackdrop) {
    els.lineupBackdrop.addEventListener("click", closeLineupModal);
  }
  if (els.lineupClose) {
    els.lineupClose.addEventListener("click", closeLineupModal);
  }
  if (els.lineupStarterMode) {
    els.lineupStarterMode.addEventListener("click", () => {
      if (!Number.isInteger(Number(pendingLineupPlayerId))) return;
      lineupRegisterMode = "starter";
      setLineupModalTitle(true, "スタメン登録");
      renderLineupModeSwitch();
      openLineupModal(Number(pendingLineupPlayerId));
    });
  }
  if (els.lineupSuccessorMode) {
    els.lineupSuccessorMode.addEventListener("click", () => {
      if (!Number.isInteger(Number(pendingLineupPlayerId))) return;
      lineupRegisterMode = "successor";
      setLineupModalTitle(true, "後継選手登録");
      renderLineupModeSwitch();
      openLineupModal(Number(pendingLineupPlayerId));
    });
  }
  if (els.lineupSlots) {
    els.lineupSlots.addEventListener("click", (e) => {
      const slotBtn = e.target.closest(".lineup-slot");
      if (!slotBtn || pendingLineupPlayerId == null) return;
      const slotIndex = Number(slotBtn.dataset.slotIndex);
      if (!Number.isInteger(slotIndex) || slotIndex < 0 || slotIndex >= LINEUP_SIZE) return;
      const player = players.find((p) => p.id === pendingLineupPlayerId);
      if (!player) return;
      openSeasonModal(player, slotIndex, lineupRegisterMode);
    });
  }
  if (els.seasonBackdrop) {
    els.seasonBackdrop.addEventListener("click", closeSeasonModal);
  }
  if (els.seasonClose) {
    els.seasonClose.addEventListener("click", closeSeasonModal);
  }
  if (els.seasonCancel) {
    els.seasonCancel.addEventListener("click", closeSeasonModal);
  }
  if (els.seasonApply) {
    els.seasonApply.addEventListener("click", async () => {
      const playerId = Number(pendingLineupPlayerId);
      const slotIndex = Number(pendingLineupSlotIndex);
      const selectedSeason = normalizeSeasonInput(els.seasonSelect?.value || "");
      const mode = pendingLineupMode === "successor" ? "successor" : "starter";
      if (!Number.isInteger(playerId)) return;
      if (!Number.isInteger(slotIndex) || slotIndex < 0 || slotIndex >= LINEUP_SIZE) return;
      if (!selectedSeason) return;
      if (mode === "successor") {
        const player = players.find((p) => p.id === playerId);
        if (!player) return;
        openSuccessorSourceModal(player, slotIndex, selectedSeason);
        closeSeasonModal();
        return;
      } else {
        const currentEntry = startingLineup[slotIndex];
        const currentSuccessor = normalizeSuccessor(currentEntry?.successor);
        startingLineup[slotIndex] = { playerId, season: selectedSeason, successor: currentSuccessor };
      }
      saveStartingLineup();
      const player = players.find((p) => p.id === playerId);
      if (els.lineupTarget) {
        els.lineupTarget.textContent = mode === "successor"
          ? (player ? `${player.name}選手の後継選手登録が完了しました` : "後継選手の登録が完了しました")
          : (player ? `${player.name}選手の登録が完了しました` : "選手の登録が完了しました");
      }
      lineupSlotsLocked = true;
      renderLineupSlots();
      if (hasCloudConfig()) {
        try {
          await cloudSaveLineup();
          setCloudStatus("Cloud: saved");
        } catch (e) {
          setCloudStatus(`Cloud save failed: ${e.message}`, true);
        }
      }
      closeSeasonModal();
    });
  }
  if (els.loginBackdrop) {
    els.loginBackdrop.addEventListener("click", closeLoginModal);
  }
  if (els.loginClose) {
    els.loginClose.addEventListener("click", closeLoginModal);
  }
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
      if (!saveCloudConfig(key)) return;
      updateMenuState();
      try {
        const ok = await cloudLoadLineup();
        if (!ok) {
          const create = window.confirm("入力されたIDの登録はありません。IDを新規作成しますか？");
          if (!create) {
            saveCloudConfig(prevKey);
            updateMenuState();
            return;
          }
          startingLineup = Array.from({ length: LINEUP_SIZE }, () => null);
          saveStartingLineup();
          await cloudSaveLineup();
          setCloudStatus("Cloud: key created");
        } else {
          setCloudStatus("Cloud: loaded");
        }
      } catch (e) {
        saveCloudConfig(prevKey);
        updateMenuState();
        setCloudStatus(`Cloud load failed: ${e.message}`, true);
        return;
      }
      closeLoginModal();
      if (Number.isInteger(pendingLoginForAddPlayerId)) {
        const id = pendingLoginForAddPlayerId;
        pendingLoginForAddPlayerId = null;
        openLineupModal(id);
      } else {
        const returnPath = consumePostLoginReturnPath();
        if (returnPath) {
          window.location.href = returnPath;
          return;
        }
      }
    });
  }
  if (els.signupBackdrop) {
    els.signupBackdrop.addEventListener("click", closeSignupModal);
  }
  if (els.signupClose) {
    els.signupClose.addEventListener("click", closeSignupModal);
  }
  if (els.signupCancel) {
    els.signupCancel.addEventListener("click", closeSignupModal);
  }
  if (els.signupApply) {
    els.signupApply.addEventListener("click", async () => {
      const key = String(els.signupLineupKey?.value || "").trim();
      if (!saveCloudConfig(key)) return;
      updateMenuState();
      try {
        startingLineup = Array.from({ length: LINEUP_SIZE }, () => null);
        saveStartingLineup();
        await cloudSaveLineup();
        setCloudStatus("Cloud: key created");
      } catch (e) {
        setCloudStatus(`Cloud create failed: ${e.message}`, true);
      }
      closeSignupModal();
      if (Number.isInteger(pendingLoginForAddPlayerId)) {
        const id = pendingLoginForAddPlayerId;
        pendingLoginForAddPlayerId = null;
        openLineupModal(id);
      } else {
        const returnPath = consumePostLoginReturnPath();
        if (returnPath) {
          window.location.href = returnPath;
          return;
        }
      }
    });
  }
  if (els.settingBackdrop) {
    els.settingBackdrop.addEventListener("click", closeSettingModal);
  }
  if (els.settingClose) {
    els.settingClose.addEventListener("click", closeSettingModal);
  }
  if (els.scoutListBackdrop) {
    els.scoutListBackdrop.addEventListener("click", closeScoutListModal);
  }
  if (els.scoutListClose) {
    els.scoutListClose.addEventListener("click", closeScoutListModal);
  }
  if (els.scoutListItems) {
    els.scoutListItems.addEventListener("click", (e) => {
      const btn = e.target.closest(".scout-list-item");
      if (!btn) return;
      const eventId = Number(btn.dataset.eventId);
      const source = String(btn.dataset.source || "scout");
      if (!Number.isInteger(eventId)) return;
      closeScoutListModal();
      renderListResultsByEvent(eventId, source);
    });
  }
  if (els.renameIdApply) {
    els.renameIdApply.addEventListener("click", async () => {
      const oldKey = String(cloudConfig.lineupKey || "").trim();
      const newKey = String(els.renameLineupKey?.value || "").trim();
      if (!oldKey || !newKey) return;
      if (oldKey === newKey) {
        closeSettingModal();
        return;
      }
      try {
        const prevKey = oldKey;
        if (!saveCloudConfig(newKey)) return;
        const exists = await cloudLineupExists(newKey);
        if (exists) {
          window.alert("そのIDは既に使われています。別のIDを入力してください。");
          saveCloudConfig(prevKey);
          updateMenuState();
          return;
        }
        startingLineup = normalizeLineupArray(startingLineup);
        await cloudSaveLineup();
        await cloudDeleteLineupById(prevKey);
        saveStartingLineup();
        updateMenuState();
        closeSettingModal();
      } catch (e) {
        setCloudStatus(`Cloud rename failed: ${e.message}`, true);
        const msg = e?.message === "delete_not_applied"
          ? "Rename後の旧ID削除に失敗しました。SupabaseのDelete権限を確認してください。"
          : "Rename IDに失敗しました。";
        window.alert(msg);
      }
    });
  }
  if (els.deleteIdApply) {
    els.deleteIdApply.addEventListener("click", async () => {
      const key = String(cloudConfig.lineupKey || "").trim();
      if (!key) {
        window.alert("TeamIDが未設定です。");
        return;
      }
      const ok = window.confirm("このIDを削除します。よろしいですか？");
      if (!ok) return;
      try {
        await cloudDeleteLineupById(key);
        startingLineup = Array.from({ length: LINEUP_SIZE }, () => null);
        saveStartingLineup();
        logoutLineupKey();
        closeSettingModal();
      } catch (e) {
        setCloudStatus(`Cloud delete failed: ${e.message}`, true);
        const msg = e?.message === "delete_not_applied"
          ? "Delete IDに失敗しました。SupabaseのDelete権限を確認してください。"
          : "Delete IDに失敗しました。";
        window.alert(msg);
      }
    });
  }
  if (els.successorSourceBackdrop) {
    els.successorSourceBackdrop.addEventListener("click", closeSuccessorSourceModal);
  }
  if (els.successorSourceClose) {
    els.successorSourceClose.addEventListener("click", closeSuccessorSourceModal);
  }
  if (els.successorSourceCancel) {
    els.successorSourceCancel.addEventListener("click", closeSuccessorSourceModal);
  }
  if (els.successorSourceType) {
    els.successorSourceType.addEventListener("change", syncSuccessorSourceInput);
  }
  if (els.successorSourceApply) {
    els.successorSourceApply.addEventListener("click", async () => {
      const draft = pendingSuccessorRegistration;
      if (!draft) return;
      const sourceType = els.successorSourceType?.value === "custom" ? "custom" : "self";
      const source = sourceType === "custom"
        ? String(els.successorSourceInput?.value || "").trim()
        : "自チーム";
      if (!source) return;

      const slotIndex = Number(draft.slotIndex);
      const playerId = Number(draft.playerId);
      const season = normalizeSeasonInput(draft.season || "");
      if (!Number.isInteger(slotIndex) || slotIndex < 0 || slotIndex >= LINEUP_SIZE) return;
      if (!Number.isInteger(playerId) || !season) return;

      const currentEntry = startingLineup[slotIndex];
      const currentMainId = Number(currentEntry?.playerId);
      if (!Number.isInteger(currentMainId)) return;
      startingLineup[slotIndex] = {
        ...currentEntry,
        successor: { playerId, season, source },
      };
      saveStartingLineup();
      const player = players.find((p) => p.id === playerId);
      if (els.lineupTarget) {
        els.lineupTarget.textContent = player
          ? `${player.name}選手の後継選手登録が完了しました`
          : "後継選手の登録が完了しました";
      }
      lineupSlotsLocked = true;
      renderLineupSlots();
      if (hasCloudConfig()) {
        try {
          await cloudSaveLineup();
          setCloudStatus("Cloud: saved");
        } catch (e) {
          setCloudStatus(`Cloud save failed: ${e.message}`, true);
        }
      }
      closeSuccessorSourceModal();
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && els.lineupModal && !els.lineupModal.hidden) {
      closeLineupModal();
      return;
    }
    if (e.key === "Escape" && els.seasonModal && !els.seasonModal.hidden) {
      closeSeasonModal();
      return;
    }
    if (e.key === "Escape" && els.loginModal && !els.loginModal.hidden) {
      closeLoginModal();
      closeMenuPanel();
      return;
    }
    if (e.key === "Escape" && els.signupModal && !els.signupModal.hidden) {
      closeSignupModal();
      closeMenuPanel();
      return;
    }
    if (e.key === "Escape" && els.successorSourceModal && !els.successorSourceModal.hidden) {
      closeSuccessorSourceModal();
      return;
    }
    if (e.key === "Escape" && els.settingModal && !els.settingModal.hidden) {
      closeSettingModal();
      return;
    }
    if (e.key === "Escape" && els.scoutListModal && !els.scoutListModal.hidden) {
      closeScoutListModal();
      return;
    }
    if (e.key === "Escape" && els.nameSuggest && !els.nameSuggest.hidden) {
      hideNameSuggest();
    }
  });

  const res = await fetch("./data.json");
  const data = await res.json();
  players = data.players || [];
  syncProfileSideWidthFromPlayers(players);
  scouts = Array.isArray(data.scouts) ? data.scouts : [];
  cmEvents = Array.isArray(data.cmEvents) ? data.cmEvents : [];
  scoutsByEventId.clear();
  scouts.forEach((s) => {
    const eventId = Number(s?.eventId || 0);
    if (Number.isInteger(eventId)) scoutsByEventId.set(eventId, s);
  });
  cmEventsByEventId.clear();
  cmEvents.forEach((s) => {
    const eventId = Number(s?.eventId || 0);
    if (Number.isInteger(eventId)) cmEventsByEventId.set(eventId, s);
  });
  appUpdatedAtJst = APP_UPDATED_AT_JST;
  syncAptitudeAreaLabel();
  syncNRAllChip();
  renderScoutEventFilterOptions();
  renderCMEventFilterOptions();
  updateScoutFilterVisibility();
  updateCMFilterVisibility();
  renderHeaderMeta();
  els.resultCount.textContent = "0 results";
  els.results.innerHTML = "";
  if (els.loadMoreResults) els.loadMoreResults.hidden = true;
}

init().catch((e) => {
  els.metaText.textContent = "Failed to load data.";
  console.error(e);
});
