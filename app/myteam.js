const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const LINEUP_STORAGE_KEY = "ws_starting_eleven_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-30 23:10 JST";
const REPO_COMMITS_API = "https://api.github.com/repos/gigagigohub/websoccer-player-search/commits/main";
const ROHM_SLOT_DATA_URL = "./rohm_slot_data.json?v=20260510-rohm-peak-avg";
const IS_SIMULATION_MODE = document.body?.classList?.contains("simulation-page");
const STARTING_LINEUP_SIZE = 11;
const RESERVE_LINEUP_SIZE = 5;
const LINEUP_SIZE = IS_SIMULATION_MODE ? STARTING_LINEUP_SIZE : STARTING_LINEUP_SIZE + RESERVE_LINEUP_SIZE;
const V4_CLEAN_UNIFORM_SLOT_WEIGHT = 0.57938903;
const V4_CLEAN_UNIFORM_KEY_WEIGHT = 0.03754174;
const V4_CC_DIRECT_MIN_USES = 20;
const V4_FALLBACK_PLAYER_USE_CAP = 60;
const V4_FALLBACK_PERSON_USE_CAP = 80;
const LIFECYCLE_MODE_STORAGE_KEY = "ws_lifecycle_mode_v1";
const MYTEAM_FORMATION_STORAGE_KEY = "ws_myteam_formation_v1";
const MYTEAM_COACH_STORAGE_KEY = "ws_myteam_coach_v1";
const SIMULATION_LINEUP_STORAGE_KEY = "ws_simulation_lineup_v1";
const SIMULATION_FORMATION_STORAGE_KEY = "ws_simulation_formation_v1";
const SIMULATION_COACH_STORAGE_KEY = "ws_simulation_coach_v1";
const CORE_METRICS = ["スピ", "テク", "パワ"];
const METRICS = [
  "スピ", "テク", "パワ", "スタ", "ラフ", "個性", "人気",
  "PK", "FK", "CK", "CP", "知性", "感性", "個人", "組織"
];
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
let appUpdatedAtJst = APP_UPDATED_AT_JST;
let updatedAtFetchStarted = false;
let ccDataMeta = null;
let ccRangeData = { rows: [], skippedFinals: 0 };
const FETCH_TIMEOUT_MS = 12000;

async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

const els = {
  hero: document.querySelector(".hero"),
  myteamMenuButton: document.querySelector("#myteamMenuButton"),
  myteamMenuPanel: document.querySelector("#myteamMenuPanel"),
  myteamMenuLoginId: document.querySelector("#myteamMenuLoginId"),
  myteamDatabaseButton: document.querySelector("#myteamDatabaseButton"),
  myteamCoachesButton: document.querySelector("#myteamCoachesButton"),
  myteamFormationsButton: document.querySelector("#myteamFormationsButton"),
  myteamCollectionsButton: document.querySelector("#myteamCollectionsButton"),
  myteamCurrentButton: document.querySelector("#myteamCurrentButton"),
  myteamSimulationButton: document.querySelector("#myteamSimulationButton"),
  myteamLoginButton: document.querySelector("#myteamLoginButton"),
  myteamLogoutButton: document.querySelector("#myteamLogoutButton"),
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
  myTeamMeta: document.querySelector("#myTeamMeta"),
  myTeamTarget: document.querySelector("#myTeamTarget"),
  myTeamIndexWrap: document.querySelector("#myTeamIndexWrap"),
  myTeamSlots: document.querySelector("#myTeamSlots"),
  myTeamReserveSlots: document.querySelector("#myTeamReserveSlots"),
  myTeamReserveTotals: document.querySelector("#myTeamReserveTotals"),
  myTeamCoachWrap: document.querySelector("#myTeamCoachWrap"),
  myTeamFormationWrap: document.querySelector("#myTeamFormationWrap"),
  lifecycleToggle: document.querySelector("#lifecycleToggle"),
  advanceSeasonButton: document.querySelector("#advanceSeasonButton"),
  rewindSeasonButton: document.querySelector("#rewindSeasonButton"),
  myTeamFormationEditor: document.querySelector("#myTeamFormationEditor"),
  myTeamFormationBackdrop: document.querySelector("#myTeamFormationBackdrop"),
  myTeamFormationSelect: document.querySelector("#myTeamFormationSelect"),
  myTeamFormationApply: document.querySelector("#myTeamFormationApply"),
  myTeamFormationCancel: document.querySelector("#myTeamFormationCancel"),
  emptySlotModal: document.querySelector("#emptySlotModal"),
  emptySlotBackdrop: document.querySelector("#emptySlotBackdrop"),
  emptySlotClose: document.querySelector("#emptySlotClose"),
  emptySlotOk: document.querySelector("#emptySlotOk"),
  playerCardModal: document.querySelector("#playerCardModal"),
  playerCardBackdrop: document.querySelector("#playerCardBackdrop"),
  playerCardTitle: document.querySelector("#playerCardTitle"),
  playerCardClose: document.querySelector("#playerCardClose"),
  playerCardHost: document.querySelector("#playerCardHost"),
  playerCardActions: document.querySelector("#playerCardModal .player-card-actions"),
  playerReplaceBtn: document.querySelector("#playerReplaceBtn"),
  playerRemoveSuccessorBtn: document.querySelector("#playerRemoveSuccessorBtn"),
  playerReplacePanel: document.querySelector("#playerReplacePanel"),
  playerReplaceSearch: document.querySelector("#playerReplaceSearch"),
  playerReplaceResults: document.querySelector("#playerReplaceResults"),
  playerReplaceSeason: document.querySelector("#playerReplaceSeason"),
  playerReplaceSourceWrap: document.querySelector("#playerReplaceSourceWrap"),
  playerReplaceSourceType: document.querySelector("#playerReplaceSourceType"),
  playerReplaceSourceCustomWrap: document.querySelector("#playerReplaceSourceCustomWrap"),
  playerReplaceSourceInput: document.querySelector("#playerReplaceSourceInput"),
  playerReplaceApply: document.querySelector("#playerReplaceApply"),
  playerReplaceCancel: document.querySelector("#playerReplaceCancel"),
  coachCardModal: document.querySelector("#coachCardModal"),
  coachCardBackdrop: document.querySelector("#coachCardBackdrop"),
  coachCardClose: document.querySelector("#coachCardClose"),
  coachCardTitle: document.querySelector("#coachCardTitle"),
  coachCardHost: document.querySelector("#coachCardHost"),
  coachReplaceBtn: document.querySelector("#coachReplaceBtn"),
  coachReplacePanel: document.querySelector("#coachReplacePanel"),
  coachReplaceSearch: document.querySelector("#coachReplaceSearch"),
  coachReplaceResults: document.querySelector("#coachReplaceResults"),
  coachReplaceSeason: document.querySelector("#coachReplaceSeason"),
  coachReplaceApply: document.querySelector("#coachReplaceApply"),
  coachReplaceCancel: document.querySelector("#coachReplaceCancel"),
  myteamSettingModal: document.querySelector("#myteamSettingModal"),
  myteamSettingBackdrop: document.querySelector("#myteamSettingBackdrop"),
  myteamSettingClose: document.querySelector("#myteamSettingClose"),
  myteamRenameLineupKey: document.querySelector("#myteamRenameLineupKey"),
  myteamRenameIdApply: document.querySelector("#myteamRenameIdApply"),
  myteamDeleteIdApply: document.querySelector("#myteamDeleteIdApply"),
  tpiInfoModal: document.querySelector("#tpiInfoModal"),
  tpiInfoBackdrop: document.querySelector("#tpiInfoBackdrop"),
  tpiInfoClose: document.querySelector("#tpiInfoClose"),
  simulationCopyButton: document.querySelector("#simulationCopyButton"),
};

let players = [];
let lineup = Array.from({ length: LINEUP_SIZE }, () => null);
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let selectedSlotIndex = null;
let selectedPlayerId = null;
let selectedPlayerMode = "starter";
let replacementPlayerId = null;
let replacementCoachId = null;
let lifecycleModeEnabled = false;
const cardViewModeById = new Map();
let formations = [];
let coaches = [];
let v4CleanUniformData = { meta: {}, formationPower: {}, coachPower: {}, formationSlotExpectedPts: {}, weights: {} };
let latestRenderedTeamTpi = null;
let myTeamPlayerById = new Map();
let v4PointContext = null;
let selectedFormationId = null;
let selectedCoach = null;
let isFormationEditorOpen = false;
let coachCardTabMode = "lead";
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

function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`;
}

function avg(v) {
  return Number(v || 0).toFixed(2);
}

function coachSeasonNumber(seasonText) {
  const n = Number(String(seasonText || "").replace(/[^0-9]/g, ""));
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function coachSeasonLabel(seasonText) {
  return `${coachSeasonNumber(seasonText)}期目`;
}

function coachTypeLabel(value) {
  const n = Number(value);
  if (n === 1) return "超攻撃型";
  if (n === 2) return "攻撃型";
  if (n === 3) return "バランス型";
  if (n === 4) return "守備型";
  if (n === 5) return "超守備型";
  return "-";
}

function coachLeadershipTableHtml(leadership, currentSeason = null, maxCols = null) {
  const rows = Array.isArray(leadership) ? leadership : [];
  if (!rows.length) return `<p class="dim">-</p>`;
  const cols = Number.isInteger(maxCols) && maxCols > 0 ? maxCols : rows.length;
  const season = Number(currentSeason);
  const start = Number.isInteger(season) && season > 0 && cols > 0 ? Math.max(0, season - 1) : 0;
  const view = Array.from({ length: cols }, (_, i) => rows[start + i] ?? null);
  const headers = view.map((_, i) => `<th>${start + i + 1}期</th>`).join("");
  const cells = view
    .map((v, i) => {
      const seasonNo = start + i + 1;
      const cls = seasonNo === season ? "is-current" : "";
      return `<td class="${cls}">${v == null ? "-" : Number(v)}</td>`;
    })
    .join("");
  return `
    <div class="coach-table-wrap">
      <table class="coach-lead-table">
        <thead><tr>${headers}</tr></thead>
        <tbody><tr>${cells}</tr></tbody>
      </table>
    </div>
  `;
}

function coachLeadershipBlocksHtml(leadership, currentSeason = null) {
  const rows = Array.isArray(leadership) ? leadership : [];
  if (!rows.length) return `<p class="dim">-</p>`;
  const season = Number(currentSeason);
  const chunks = [];
  for (let i = 0; i < rows.length; i += 8) {
    chunks.push(rows.slice(i, i + 8));
  }
  const blocks = chunks.map((chunk, idx) => {
    const start = idx * 8;
    const headers = chunk.map((_, i) => `<th>${start + i + 1}期</th>`).join("");
    const cells = chunk
      .map((v, i) => {
        const seasonNo = start + i + 1;
        const cls = seasonNo === season ? "is-current" : "";
        return `<td class="${cls}">${v == null ? "-" : Number(v)}</td>`;
      })
      .join("");
    return `
      <div class="coach-lead-block">
        <table class="coach-lead-table">
          <thead><tr>${headers}</tr></thead>
          <tbody><tr>${cells}</tr></tbody>
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

function nationNameFromId(nationId) {
  const id = Number(nationId);
  if (!Number.isInteger(id)) return "-";
  for (const p of players) {
    if (Number(p?.nationId) === id) {
      const n = String(p?.nationality || "").trim();
      if (n) return n;
    }
  }
  return "-";
}

function getFormationNameById(fid) {
  const id = Number(fid);
  const f = formations.find((x) => Number(x?.id) === id);
  if (!f) return `Formation ${id}`;
  const y = formatFormationYearLabel(f?.year, f?.stride);
  return `${f?.name || `Formation ${id}`}${y ? ` ${y}` : ""}`;
}

function coachFormationPills(list, withSeason = false) {
  const rows = Array.isArray(list) ? list : [];
  if (!rows.length) return "-";
  return rows
    .map((row) => {
      const fid = Number(withSeason ? row?.formationId : row);
      if (!Number.isInteger(fid)) return "";
      const suffix = withSeason && Number(row?.fromSeason) > 1 ? ` (${Number(row.fromSeason)}期目〜)` : "";
      return `<button type="button" class="inline-pill coach-formation-pill" data-formation-id="${fid}">${getFormationNameById(fid)}${suffix}</button>`;
    })
    .join("");
}

function formationMetaId(lineupId = cloudConfig?.lineupKey) {
  const id = String(lineupId || "").trim();
  return id ? `${id}__meta` : "";
}

function simulationLineupId(lineupId = cloudConfig?.lineupKey) {
  const id = String(lineupId || "").trim();
  return id ? `${id}__simulation` : "";
}

function simulationMetaId(lineupId = cloudConfig?.lineupKey) {
  const id = String(lineupId || "").trim();
  return id ? `${id}__simulation_meta` : "";
}

function cloudLineupIdForMode(mode = IS_SIMULATION_MODE ? "simulation" : "myteam", lineupId = cloudConfig?.lineupKey) {
  return mode === "simulation" ? simulationLineupId(lineupId) : String(lineupId || "").trim();
}

function cloudMetaIdForMode(mode = IS_SIMULATION_MODE ? "simulation" : "myteam", lineupId = cloudConfig?.lineupKey) {
  return mode === "simulation" ? simulationMetaId(lineupId) : formationMetaId(lineupId);
}

function scopedStorageKey(baseKey) {
  const id = String(cloudConfig?.lineupKey || "").trim();
  return id ? `${baseKey}:${id}` : baseKey;
}

function lineupStorageKeyForCurrentMode() {
  return IS_SIMULATION_MODE ? scopedStorageKey(SIMULATION_LINEUP_STORAGE_KEY) : LINEUP_STORAGE_KEY;
}

function formationStorageKeyForCurrentMode() {
  return scopedStorageKey(IS_SIMULATION_MODE ? SIMULATION_FORMATION_STORAGE_KEY : MYTEAM_FORMATION_STORAGE_KEY);
}

function coachStorageKeyForCurrentMode() {
  return scopedStorageKey(IS_SIMULATION_MODE ? SIMULATION_COACH_STORAGE_KEY : MYTEAM_COACH_STORAGE_KEY);
}

function normalizeFormationId(v) {
  const n = Number(v);
  return Number.isInteger(n) && n > 0 ? n : null;
}

function normalizeCoach(raw) {
  const id = Number(raw?.coachId);
  if (!Number.isInteger(id) || id <= 0) return null;
  const season = raw?.season == null ? "1期目" : coachSeasonLabel(raw?.season);
  return { coachId: id, season };
}

function loadSelectedFormationId() {
  const raw = String(localStorage.getItem(formationStorageKeyForCurrentMode()) || "").trim();
  selectedFormationId = normalizeFormationId(raw);
}

function saveSelectedFormationId() {
  const key = formationStorageKeyForCurrentMode();
  if (Number.isInteger(selectedFormationId) && selectedFormationId > 0) {
    localStorage.setItem(key, String(selectedFormationId));
  } else {
    localStorage.removeItem(key);
  }
}

function loadSelectedCoach() {
  try {
    selectedCoach = normalizeCoach(JSON.parse(localStorage.getItem(coachStorageKeyForCurrentMode()) || "null"));
  } catch (_) {
    selectedCoach = null;
  }
}

function saveSelectedCoach() {
  const key = coachStorageKeyForCurrentMode();
  if (selectedCoach && Number.isInteger(Number(selectedCoach.coachId))) {
    localStorage.setItem(key, JSON.stringify(selectedCoach));
  } else {
    localStorage.removeItem(key);
  }
}

function buildFormationOptions() {
  if (!els.myTeamFormationSelect) return;
  const rows = (Array.isArray(formations) ? formations : []).slice().sort((a, b) => {
    const n = String(a?.name || "").localeCompare(String(b?.name || ""), "ja");
    if (n !== 0) return n;
    return Number(a?.year || 0) - Number(b?.year || 0);
  });
  const options = rows.map((f) => {
    const id = Number(f?.id);
    if (!Number.isInteger(id)) return "";
    const year = formatFormationYearLabel(f?.year, f?.stride);
    const suffix = year ? ` ${year}` : "";
    return `<option value="${id}">${f?.name || `Formation ${id}`}${suffix}</option>`;
  }).join("");
  els.myTeamFormationSelect.innerHTML = `<option value=\"\">Not selected</option>${options}`;
  const exists = rows.some((f) => Number(f?.id) === selectedFormationId);
  els.myTeamFormationSelect.value = exists ? String(selectedFormationId) : "";
  if (!exists) {
    selectedFormationId = null;
    saveSelectedFormationId();
  }
  renderFormationCurrent();
}

function renderMyTeamFormationPitch(formation) {
  const positions = Array.isArray(formation?.positions) ? formation.positions : [];
  const formationId = Number(formation?.id || 0);
  if (!positions.length || !Number.isInteger(formationId) || formationId <= 0) {
    return `<div class="lineup-empty-thumb"></div>`;
  }
  const minX = 1;
  const maxX = 321;
  const minY = 2;
  const maxY = 337;
  const padLeft = 16;
  const padRight = 16;
  const padTop = 18;
  const padBottom = 10;
  const markerSrc = `./images/formation/${formationId}@2x.png`;
  return `
    <div class="myteam-formation-scale-wrap">
      <div class="formation-pitch myteam-formation-pitch">
      ${positions.map((p) => {
        const nx = (Number(p?.x || 0) - minX) / (maxX - minX);
        const ny = (Number(p?.y || 0) - minY) / (maxY - minY);
        const left = padLeft + nx * (100 - padLeft - padRight);
        const top = padTop + ny * (100 - padTop - padBottom);
        return `
          <span class="formation-slot-point" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%">
            <img class="formation-slot-icon" src="${markerSrc}" alt="" />
          </span>
        `;
      }).join("")}
      </div>
    </div>
  `;
}

function renderFormationCurrent() {
  if (!els.myTeamFormationWrap) return;
  if (!Number.isInteger(selectedFormationId) || selectedFormationId <= 0) {
    els.myTeamFormationWrap.innerHTML = `
      <div class="lineup-slot myteam-slot myteam-formation-slot is-empty" id="myTeamFormationSlot">
        <span class="slot-no">FM</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${renderMyTeamFormationPitch(null)}</div>
          <div class="lineup-player-meta">
            <span class="slot-name">Not selected</span>
          </div>
          <button type="button" class="formation-change-btn myteam-formation-change-btn" data-formation-change>Change</button>
        </div>
      </div>
    `;
    renderTpiInfoBenchmark();
    return;
  }
  const f = formations.find((x) => Number(x?.id) === selectedFormationId);
  if (!f) {
    selectedFormationId = null;
    saveSelectedFormationId();
    renderFormationCurrent();
    return;
  }
  const year = formatFormationYearLabel(f?.year, f?.stride);
  const name = `${f?.name || `Formation ${selectedFormationId}`}${year ? ` ${year}` : ""}`;
  const formationInfoText = `Usage ${pct(f?.cc?.usageRate)} / WinRate ${pct(f?.cc?.winRate)}`;
  els.myTeamFormationWrap.innerHTML = `
    <div class="lineup-slot myteam-slot myteam-formation-slot has-player" id="myTeamFormationSlot" data-formation-open>
      <span class="slot-no">FM</span>
      <div class="lineup-slot-main">
        <div class="lineup-thumb-wrap">${renderMyTeamFormationPitch(f)}</div>
        <div class="lineup-player-meta">
          <span class="slot-name">${name}</span>
          <span class="lineup-cc-stat">${formationInfoText}</span>
        </div>
        <button type="button" class="formation-change-btn myteam-formation-change-btn" data-formation-change>Change</button>
      </div>
    </div>
  `;
}

function openFormationEditor() {
  if (!els.myTeamFormationEditor || !els.myTeamFormationSelect) return;
  isFormationEditorOpen = true;
  els.myTeamFormationEditor.hidden = false;
  const exists = formations.some((f) => Number(f?.id) === selectedFormationId);
  els.myTeamFormationSelect.value = exists ? String(selectedFormationId) : "";
}

function closeFormationEditor() {
  if (!els.myTeamFormationEditor) return;
  isFormationEditorOpen = false;
  els.myTeamFormationEditor.hidden = true;
}

async function applyFormationFromSelect() {
  if (!els.myTeamFormationSelect) return;
  const id = Number(els.myTeamFormationSelect.value || 0);
  selectedFormationId = normalizeFormationId(id);
  saveSelectedFormationId();
  if (hasCloudConfig()) {
    try {
      await saveCloudFormationId();
    } catch (_) {
      window.alert("フォーメーションのクラウド保存に失敗しました。");
    }
  }
  renderFormationCurrent();
  renderLineup();
  closeFormationEditor();
}

function openSelectedFormationDetail() {
  if (!Number.isInteger(selectedFormationId) || selectedFormationId <= 0) return;
  const url = new URL("./formations.html", window.location.href);
  url.searchParams.set("openFormationId", String(selectedFormationId));
  url.searchParams.set("returnTo", IS_SIMULATION_MODE ? "simulation" : "myteam");
  window.location.href = url.toString();
}

function findCcSlotStat(formationId, slot, playerId) {
  const fid = Number(formationId);
  const sid = Number(slot);
  const pid = Number(playerId);
  if (!Number.isInteger(fid) || !Number.isInteger(sid) || !Number.isInteger(pid)) return { row: null, refCategory: null, byName: false };
  const formation = formations.find((f) => Number(f?.id) === fid);
  const rows = formation?.slotStats?.[String(sid)];
  if (!Array.isArray(rows)) return { row: null, refCategory: null, byName: false };
  const byId = rows.find((r) => Number(r?.playerId) === pid) || null;
  if (byId) return { row: byId, refCategory: null, byName: false };

  const basePlayer = players.find((p) => Number(p?.id) === pid);
  const baseName = String(basePlayer?.name || "").trim();
  if (!baseName) return { row: null, refCategory: null, byName: false };
  const byNameRows = rows.filter((r) => String(r?.playerName || "").trim() === baseName);
  if (!byNameRows.length) return { row: null, refCategory: null, byName: false };
  const refRow = byNameRows[0];
  const refPlayer = players.find((p) => Number(p?.id) === Number(refRow?.playerId));
  return {
    row: refRow,
    refCategory: refPlayer ? getCategory(refPlayer) : "-",
    byName: true,
  };
}

function rebuildMyTeamPlayerIndex() {
  myTeamPlayerById = new Map();
  (Array.isArray(players) ? players : []).forEach((player) => {
    const playerId = Number(player?.id || 0);
    if (Number.isInteger(playerId) && playerId > 0) myTeamPlayerById.set(playerId, player);
  });
}

function findPlayerById(playerId) {
  const pid = Number(playerId);
  if (!Number.isInteger(pid) || pid <= 0) return null;
  return myTeamPlayerById.get(pid) || players.find((p) => Number(p?.id) === pid) || null;
}

function playerPersonId(player) {
  const personId = Number(player?.personId || 0);
  if (Number.isInteger(personId) && personId > 0) return personId;
  const playerId = Number(player?.id || 0);
  return Number.isInteger(playerId) && playerId > 0 ? playerId : 0;
}

function v4PointKey(formationId, slot, tail = "") {
  return `${Number(formationId)}:${Number(slot)}${tail ? `:${tail}` : ""}`;
}

function v4TeamPowerSlotWeight() {
  const n = Number(v4CleanUniformData?.weights?.slotAdjusted);
  return Number.isFinite(n) ? n : V4_CLEAN_UNIFORM_SLOT_WEIGHT;
}

function v4TeamPowerKeyWeight() {
  const n = Number(v4CleanUniformData?.weights?.keyAdjusted);
  return Number.isFinite(n) ? n : V4_CLEAN_UNIFORM_KEY_WEIGHT;
}

function v4FormationSlotExpectedFromData(formationId, slot) {
  const fid = Number(formationId);
  const slotNo = Number(slot);
  if (!Number.isInteger(fid) || !Number.isInteger(slotNo)) return null;
  const source = v4CleanUniformData?.formationSlotExpectedPts || {};
  const flat = Number(source[v4PointKey(fid, slotNo)]);
  if (Number.isFinite(flat)) return flat;
  const nested = source[String(fid)] || source[fid];
  if (nested && typeof nested === "object") {
    const nestedValue = Number(nested[String(slotNo)] ?? nested[slotNo]);
    if (Number.isFinite(nestedValue)) return nestedValue;
  }
  return null;
}

function v4AddMapRow(map, key, row) {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(row);
}

function v4WeightedAverage(rows) {
  let sum = 0;
  let weight = 0;
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const avgPts = Number(row?.avgPts);
    const uses = Math.max(1, Number(row?.uses || 0));
    if (!Number.isFinite(avgPts)) return;
    sum += avgPts * uses;
    weight += uses;
  });
  return weight > 0 ? sum / weight : null;
}

function v4SlotExpectedValue(ctx, formationId, slot) {
  const decomposed = v4FormationSlotExpectedFromData(formationId, slot);
  if (Number.isFinite(decomposed)) return decomposed;
  return ctx?.slotAvgByFormationSlot?.get(v4PointKey(formationId, slot))
    ?? ctx?.slotAvgBySlot?.get(String(slot))
    ?? (Number.isFinite(Number(v4CleanUniformData?.globalAvg)) ? Number(v4CleanUniformData.globalAvg) : null)
    ?? (Number.isFinite(Number(ctx?.globalAvg)) ? Number(ctx.globalAvg) : null);
}

function v4DeviationFromSlotExpectation(ctx, rows, weightCap = Infinity, valueOffset = 0) {
  let sum = 0;
  let weight = 0;
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const avgPts = Number(row?.avgPts) + Number(valueOffset || 0);
    const expected = v4SlotExpectedValue(ctx, row?.formationId, row?.slot);
    if (!Number.isFinite(avgPts) || !Number.isFinite(Number(expected))) return;
    const rawWeight = Math.max(1, Number(row?.uses || 0));
    sum += (avgPts - Number(expected)) * rawWeight;
    weight += rawWeight;
  });
  return weight > 0 ? { deviation: sum / weight, weight: Math.min(weight, weightCap) } : null;
}

function v4CategoryDeviation(ctx, rows, category, options = {}) {
  const targetCategory = String(category || "");
  const filtered = (Array.isArray(rows) ? rows : []).filter((row) => {
    if (String(row?.category || "") !== targetCategory) return false;
    if (options.playerId != null && Number(row?.playerId) !== Number(options.playerId)) return false;
    if (options.excludePlayerId != null && Number(row?.playerId) === Number(options.excludePlayerId)) return false;
    if (options.excludeFormationId != null && Number(row?.formationId) === Number(options.excludeFormationId)) return false;
    return Number.isFinite(Number(row?.avgPts));
  });
  const result = v4DeviationFromSlotExpectation(
    ctx,
    filtered,
    options.weightCap ?? Infinity,
    options.valueOffset ?? 0
  );
  if (!result || Number(result.weight || 0) < Number(options.minUses ?? 1)) return null;
  return result;
}

function v4FallbackPointFromSlotExpectation(ctx, formationId, slot, exactCc, playerRows, personRows) {
  const base = v4SlotExpectedValue(ctx, formationId, slot);
  if (!Number.isFinite(Number(base))) return null;

  const deviations = [];
  if (exactCc && Number.isFinite(Number(exactCc.avgPts))) {
    const exactDeviation = v4DeviationFromSlotExpectation(ctx, [exactCc], V4_CC_DIRECT_MIN_USES);
    if (exactDeviation) deviations.push(exactDeviation);
  }

  const playerDeviation = v4DeviationFromSlotExpectation(ctx, playerRows, V4_FALLBACK_PLAYER_USE_CAP);
  if (playerDeviation) deviations.push(playerDeviation);

  const personDeviation = v4DeviationFromSlotExpectation(ctx, personRows, V4_FALLBACK_PERSON_USE_CAP);
  if (personDeviation) deviations.push(personDeviation);

  if (!deviations.length) return {
    point: Number(base),
    adjustment: 0,
    base: Number(base),
    weight: 0,
  };

  const totalWeight = deviations.reduce((sum, row) => sum + Number(row.weight || 0), 0);
  if (totalWeight <= 0) return null;
  const adjustment = deviations.reduce((sum, row) => sum + Number(row.deviation || 0) * Number(row.weight || 0), 0) / totalWeight;
  return {
    point: Number(base) + adjustment,
    adjustment,
    base: Number(base),
    weight: totalWeight,
  };
}

function v4BuildCategoryDiff(rowsByFormationSlotPerson) {
  const acc = new Map();
  rowsByFormationSlotPerson.forEach((rows) => {
    const byCategory = new Map();
    rows.forEach((row) => {
      if (Number(row?.uses || 0) < V4_CC_DIRECT_MIN_USES) return;
      const category = String(row?.category || "");
      if (!category) return;
      const current = byCategory.get(category) || { sum: 0, weight: 0 };
      const uses = Math.max(1, Number(row.uses || 0));
      current.sum += Number(row.avgPts || 0) * uses;
      current.weight += uses;
      byCategory.set(category, current);
    });
    const cats = Array.from(byCategory.entries())
      .filter(([, value]) => value.weight > 0)
      .map(([category, value]) => ({
        category,
        avg: value.sum / value.weight,
        weight: value.weight,
      }));
    cats.forEach((target) => {
      cats.forEach((ref) => {
        if (target.category === ref.category) return;
        const key = `${target.category}|${ref.category}`;
        const current = acc.get(key) || { sum: 0, weight: 0 };
        const weight = Math.min(target.weight, ref.weight);
        current.sum += (target.avg - ref.avg) * weight;
        current.weight += weight;
        acc.set(key, current);
      });
    });
  });
  const result = new Map();
  acc.forEach((value, key) => {
    if (value.weight > 0) result.set(key, value.sum / value.weight);
  });
  return result;
}

function buildV4PointContext(rohmData = {}) {
  const ctx = {
    ccRowByFormationSlotPlayer: new Map(),
    ccRowsByFormationSlotPerson: new Map(),
    ccRowsByPlayer: new Map(),
    ccRowsByPerson: new Map(),
    slotAvgByFormationSlot: new Map(),
    slotAvgBySlot: new Map(),
    globalAvg: 3.0,
    categoryDiff: new Map(),
    rohmRowByFormationSlotPlayer: new Map(),
    rohmRowsByPlayer: new Map(),
    rohmRowsByPerson: new Map(),
    rohmRowsByFormationSlotPerson: new Map(),
    rohmToCcOffset: -0.38,
  };

  const slotAccByFormationSlot = new Map();
  const slotAccBySlot = new Map();
  const globalRows = [];
  (Array.isArray(formations) ? formations : []).forEach((formation) => {
    const formationId = Number(formation?.id || 0);
    if (!Number.isInteger(formationId) || formationId <= 0) return;
    Object.entries(formation?.slotStats || {}).forEach(([slotKey, rows]) => {
      const slot = Number(slotKey);
      if (!Number.isInteger(slot) || slot < 1 || slot > STARTING_LINEUP_SIZE) return;
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        const playerId = Number(row?.playerId || 0);
        const player = findPlayerById(playerId);
        if (!player) return;
        const uses = Number(row?.uses || 0);
        const avgPts = Number(row?.avgPts);
        if (!Number.isInteger(playerId) || playerId <= 0 || !Number.isFinite(avgPts)) return;
        const personId = playerPersonId(player);
        const category = typeLabelByPlayer(player);
        const record = {
          formationId,
          slot,
          playerId,
          personId,
          category,
          uses,
          avgPts,
          source: "cc",
        };
        ctx.ccRowByFormationSlotPlayer.set(v4PointKey(formationId, slot, playerId), record);
        v4AddMapRow(ctx.ccRowsByFormationSlotPerson, v4PointKey(formationId, slot, personId), record);
        v4AddMapRow(ctx.ccRowsByPlayer, String(playerId), record);
        v4AddMapRow(ctx.ccRowsByPerson, String(personId), record);
        globalRows.push(record);
        v4AddMapRow(slotAccByFormationSlot, v4PointKey(formationId, slot), record);
        v4AddMapRow(slotAccBySlot, String(slot), record);
      });
    });
  });

  slotAccByFormationSlot.forEach((rows, key) => {
    const avgPts = v4WeightedAverage(rows);
    if (avgPts != null) ctx.slotAvgByFormationSlot.set(key, avgPts);
  });
  slotAccBySlot.forEach((rows, key) => {
    const avgPts = v4WeightedAverage(rows);
    if (avgPts != null) ctx.slotAvgBySlot.set(key, avgPts);
  });
  ctx.globalAvg = v4WeightedAverage(globalRows) ?? 3.0;
  ctx.categoryDiff = v4BuildCategoryDiff(ctx.ccRowsByFormationSlotPerson);

  let rohmCcDiffSum = 0;
  let rohmCcDiffWeight = 0;
  Object.entries(rohmData?.formations || {}).forEach(([formationKey, rohmFormation]) => {
    const formationId = Number(rohmFormation?.localFormationId || formationKey || 0);
    if (!Number.isInteger(formationId) || formationId <= 0) return;
    Object.entries(rohmFormation?.slots || {}).forEach(([slotKey, slotData]) => {
      const slot = Number(slotKey);
      if (!Number.isInteger(slot) || slot < 1 || slot > STARTING_LINEUP_SIZE) return;
      (Array.isArray(slotData?.rows) ? slotData.rows : []).forEach((row) => {
        const playerId = Number(row?.localPlayerId || 0);
        const player = findPlayerById(playerId);
        const avgPts = Number(row?.avgPts);
        if (!player || !Number.isInteger(playerId) || playerId <= 0 || !Number.isFinite(avgPts)) return;
        const personId = playerPersonId(player);
        const uses = Number(row?.uses || row?.peakGames || 0);
        const record = {
          formationId,
          slot,
          playerId,
          personId,
          category: typeLabelByPlayer(player),
          uses,
          avgPts,
          rank: Number(row?.rank || row?.rohmRank || 0),
          source: "rohm",
        };
        const playerKey = v4PointKey(formationId, slot, playerId);
        const current = ctx.rohmRowByFormationSlotPlayer.get(playerKey);
        if (
          !current
          || Number(record.uses || 0) > Number(current.uses || 0)
          || (
            Number(record.uses || 0) === Number(current.uses || 0)
            && Number(record.avgPts || 0) > Number(current.avgPts || 0)
          )
        ) {
          ctx.rohmRowByFormationSlotPlayer.set(playerKey, record);
        }
        v4AddMapRow(ctx.rohmRowsByFormationSlotPerson, v4PointKey(formationId, slot, personId), record);
        v4AddMapRow(ctx.rohmRowsByPlayer, String(playerId), record);
        v4AddMapRow(ctx.rohmRowsByPerson, String(personId), record);

        const ccRecord = ctx.ccRowByFormationSlotPlayer.get(playerKey);
        if (ccRecord && Number(ccRecord.uses || 0) >= V4_CC_DIRECT_MIN_USES) {
          const weight = Math.max(1, Math.min(Number(ccRecord.uses || 0), Number(record.uses || ccRecord.uses || 0)));
          rohmCcDiffSum += (Number(ccRecord.avgPts || 0) - Number(record.avgPts || 0)) * weight;
          rohmCcDiffWeight += weight;
        }
      });
    });
  });
  if (rohmCcDiffWeight > 0) ctx.rohmToCcOffset = rohmCcDiffSum / rohmCcDiffWeight;
  return ctx;
}

function v4EstimateNrToSsAdjustment(ctx, context = {}) {
  if (!ctx) return null;
  const targetPlayerId = Number(context.targetPlayerId || 0);
  const personId = Number(context.personId || 0);
  const formationId = Number(context.formationId || 0);
  const slot = Number(context.slot || 0);
  const sameFormationSlotCcRows = (
    Number.isInteger(formationId) && formationId > 0
    && Number.isInteger(slot) && slot >= 1 && slot <= STARTING_LINEUP_SIZE
    && Number.isInteger(personId) && personId > 0
  )
    ? (ctx.ccRowsByFormationSlotPerson.get(v4PointKey(formationId, slot, personId)) || [])
    : [];
  const sameFormationSlotRohmRows = (
    Number.isInteger(formationId) && formationId > 0
    && Number.isInteger(slot) && slot >= 1 && slot <= STARTING_LINEUP_SIZE
    && Number.isInteger(personId) && personId > 0
  )
    ? (ctx.rohmRowsByFormationSlotPerson.get(v4PointKey(formationId, slot, personId)) || [])
    : [];
  const referenceOffset = Number(context.referenceOffset || 0);
  const referenceDeviation = context.referenceRecord
    ? v4DeviationFromSlotExpectation(ctx, [context.referenceRecord], Infinity, referenceOffset)
    : null;
  const nrDeviation = referenceDeviation
    || v4CategoryDeviation(ctx, sameFormationSlotCcRows, "NR", {
      minUses: V4_CC_DIRECT_MIN_USES,
      weightCap: V4_FALLBACK_PERSON_USE_CAP,
    })
    || { deviation: 0, weight: 0 };

  const applyBaseline = (candidate, source) => candidate ? {
    value: Number(candidate.deviation || 0) - Number(nrDeviation.deviation || 0),
    source,
  } : null;

  const sameIdCc = v4CategoryDeviation(ctx, sameFormationSlotCcRows, "SS", {
    playerId: targetPlayerId,
    minUses: V4_CC_DIRECT_MIN_USES,
    weightCap: V4_FALLBACK_PLAYER_USE_CAP,
  });
  const sameIdResult = applyBaseline(sameIdCc, "CC same SS id");
  if (sameIdResult) return sameIdResult;

  const otherIdCc = v4CategoryDeviation(ctx, sameFormationSlotCcRows, "SS", {
    excludePlayerId: targetPlayerId,
    minUses: V4_CC_DIRECT_MIN_USES,
    weightCap: V4_FALLBACK_PERSON_USE_CAP,
  });
  const otherIdResult = applyBaseline(otherIdCc, "CC other SS id");
  if (otherIdResult) return otherIdResult;

  const hasQualifiedCcRows = v4HasQualifiedRows(sameFormationSlotCcRows);
  if (hasQualifiedCcRows) return null;

  const rohmValueOffset = Number(ctx.rohmToCcOffset || 0);
  const rohmNrDeviation = v4CategoryDeviation(ctx, sameFormationSlotRohmRows, "NR", {
    minUses: V4_CC_DIRECT_MIN_USES,
    weightCap: V4_FALLBACK_PERSON_USE_CAP,
    valueOffset: rohmValueOffset,
  });
  const applyRohmBaseline = (candidate, source) => {
    if (!candidate || !rohmNrDeviation) return null;
    return {
      value: Number(candidate.deviation || 0) - Number(rohmNrDeviation.deviation || 0),
      source,
    };
  };

  const otherIdRohm = v4CategoryDeviation(ctx, sameFormationSlotRohmRows, "SS", {
    excludePlayerId: targetPlayerId,
    minUses: V4_CC_DIRECT_MIN_USES,
    weightCap: V4_FALLBACK_PERSON_USE_CAP,
    valueOffset: rohmValueOffset,
  });
  const otherIdRohmResult = applyRohmBaseline(otherIdRohm, "Rohm other SS id / Rohm NR baseline");
  if (otherIdRohmResult) return otherIdRohmResult;

  return null;
}

function v4CategoryAdjustmentInfo(targetCategory, refCategory, context = {}) {
  if (!targetCategory || !refCategory || targetCategory === refCategory) return { value: 0, source: "" };
  const ctx = context.ctx || v4PointContext;
  if (targetCategory === "SS" && refCategory === "NR") {
    const nrToSs = v4EstimateNrToSsAdjustment(ctx, context);
    if (nrToSs) return nrToSs;
  }
  const value = ctx?.categoryDiff?.get(`${targetCategory}|${refCategory}`);
  return {
    value: Number.isFinite(Number(value)) ? Number(value) : 0,
    source: "CC global category addon",
  };
}

function v4CategoryAdjustment(targetCategory, refCategory, context = {}) {
  return v4CategoryAdjustmentInfo(targetCategory, refCategory, context).value;
}

function v4ReferenceCategoryPriority(row, targetCategory) {
  const refCategory = String(row?.category || "");
  if (refCategory === targetCategory) return 0;
  if (targetCategory === "SS" && refCategory === "NR") return 1;
  if (Number.isFinite(v4CategoryAdjustment(targetCategory, refCategory)) && v4CategoryAdjustment(targetCategory, refCategory) !== 0) return 2;
  return 3;
}

function v4SelectReferenceRecord(rows, targetCategory, minUses = 1) {
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => Number(row?.uses || 0) >= minUses && Number.isFinite(Number(row?.avgPts)))
    .sort((a, b) =>
      v4ReferenceCategoryPriority(a, targetCategory) - v4ReferenceCategoryPriority(b, targetCategory)
      || Number(b?.uses || 0) - Number(a?.uses || 0)
      || Number(b?.avgPts || 0) - Number(a?.avgPts || 0)
      || Number(a?.playerId || 0) - Number(b?.playerId || 0)
    )[0] || null;
}

function v4HasQualifiedRows(rows, minUses = V4_CC_DIRECT_MIN_USES) {
  return (Array.isArray(rows) ? rows : []).some((row) =>
    Number(row?.uses || 0) >= minUses && Number.isFinite(Number(row?.avgPts))
  );
}

function v4PointLabelForRecord(prefix, record, targetCategory, baseOffset = 0, adjustmentContext = {}) {
  const categoryInfo = v4CategoryAdjustmentInfo(targetCategory, record?.category, adjustmentContext);
  const categoryOffset = Number(categoryInfo.value || 0);
  const parts = [prefix];
  if (record?.category && record.category !== targetCategory) {
    const source = categoryInfo.source ? ` ${categoryInfo.source}` : "";
    parts.push(`${record.category}->${targetCategory}${source} ${categoryOffset >= 0 ? "+" : ""}${formatIndexValue(categoryOffset, 2)}`);
  }
  if (baseOffset) parts.push(`A補正 ${baseOffset >= 0 ? "+" : ""}${formatIndexValue(baseOffset, 2)}`);
  return parts.join(" / ");
}

function resolveMyTeamPlayerPoint(formationId, slot, player) {
  const ctx = v4PointContext;
  const playerId = Number(player?.id || 0);
  const personId = playerPersonId(player);
  const targetCategory = typeLabelByPlayer(player);
  if (!ctx || !Number.isInteger(playerId) || playerId <= 0 || !personId) {
    return { point: null, source: "missing", label: "評価データなし" };
  }

  const exactCc = ctx.ccRowByFormationSlotPlayer.get(v4PointKey(formationId, slot, playerId));
  if (exactCc && Number(exactCc.uses || 0) >= V4_CC_DIRECT_MIN_USES) {
    return {
      point: Number(exactCc.avgPts),
      source: "cc-exact",
      label: `CC ${Number(exactCc.uses || 0)} games`,
    };
  }

  const samePersonCc = ctx.ccRowsByFormationSlotPerson.get(v4PointKey(formationId, slot, personId)) || [];
  const ccRef = v4SelectReferenceRecord(samePersonCc, targetCategory, V4_CC_DIRECT_MIN_USES);
  if (ccRef) {
    const adjustmentContext = {
      ctx,
      targetPlayerId: playerId,
      personId,
      formationId,
      slot,
      referenceRecord: ccRef,
      referenceOffset: 0,
    };
    const offset = v4CategoryAdjustment(targetCategory, ccRef.category, adjustmentContext);
    return {
      point: Number(ccRef.avgPts || 0) + offset,
      source: "cc-person",
      label: v4PointLabelForRecord(ccRef.category === targetCategory ? "CC same person" : "CC category estimate", ccRef, targetCategory, 0, adjustmentContext),
      referencePlayerId: ccRef.playerId,
    };
  }

  const hasQualifiedFormationSlotCc =
    (exactCc && Number(exactCc.uses || 0) >= V4_CC_DIRECT_MIN_USES)
    || v4HasQualifiedRows(samePersonCc);
  if (!hasQualifiedFormationSlotCc) {
    const exactRohm = ctx.rohmRowByFormationSlotPlayer.get(v4PointKey(formationId, slot, playerId));
    if (exactRohm) {
      return {
        point: Number(exactRohm.avgPts || 0) + Number(ctx.rohmToCcOffset || 0),
        source: "rohm-exact",
        label: v4PointLabelForRecord("Rohm exact", exactRohm, targetCategory, Number(ctx.rohmToCcOffset || 0)),
        referencePlayerId: exactRohm.playerId,
      };
    }

    const samePersonRohm = ctx.rohmRowsByFormationSlotPerson.get(v4PointKey(formationId, slot, personId)) || [];
    const rohmRef = v4SelectReferenceRecord(samePersonRohm, targetCategory, 1);
    if (rohmRef) {
      const adjustmentContext = {
        ctx,
        targetPlayerId: playerId,
        personId,
        formationId,
        slot,
        referenceRecord: rohmRef,
        referenceOffset: Number(ctx.rohmToCcOffset || 0),
      };
      const point = Number(rohmRef.avgPts || 0)
        + Number(ctx.rohmToCcOffset || 0)
        + v4CategoryAdjustment(targetCategory, rohmRef.category, adjustmentContext);
      return {
        point,
        source: "rohm-person",
        label: v4PointLabelForRecord("Rohm same person", rohmRef, targetCategory, Number(ctx.rohmToCcOffset || 0), adjustmentContext),
        referencePlayerId: rohmRef.playerId,
      };
    }
  }

  const fallbackEstimate = v4FallbackPointFromSlotExpectation(
    ctx,
    formationId,
    slot,
    exactCc,
    ctx.ccRowsByPlayer.get(String(playerId)),
    ctx.ccRowsByPerson.get(String(personId))
  );
  if (fallbackEstimate) {
    const adjustment = Number(fallbackEstimate.adjustment || 0);
    return {
      point: fallbackEstimate.point,
      source: "fallback",
      label: `CC slot-base estimate ${adjustment >= 0 ? "+" : ""}${formatIndexValue(adjustment, 2)}`,
    };
  }
  return {
    point: Number(ctx.globalAvg || 3.0),
    source: "fallback-global",
    label: "global average estimate",
  };
}

function v4RequiredSlots() {
  return Array.from({ length: STARTING_LINEUP_SIZE }, (_, i) => i + 1);
}

function asFiniteNumber(value, fieldName) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    throw new Error(`${fieldName} must be numeric`);
  }
  return n;
}

function lookupFormationSlotExpected(formationSlotExpected, formationId, slotNo) {
  const flatKey = v4PointKey(formationId, slotNo);
  const flat = Number(formationSlotExpected?.[flatKey]);
  if (Number.isFinite(flat)) return flat;
  const nested = formationSlotExpected?.[String(formationId)] || formationSlotExpected?.[formationId];
  if (nested && typeof nested === "object") {
    const nestedValue = Number(nested[String(slotNo)] ?? nested[slotNo]);
    if (Number.isFinite(nestedValue)) return nestedValue;
  }
  return 0;
}

function calcTeamV4CleanUniformIndex({
  formationId,
  headcoachId,
  slotPlayerIds,
  playerPointById,
  formationKeySlots,
  formationPower,
  formationSlotExpected = {},
  coachPowerById = null,
  includeCoachPower = false,
  slotWeight = V4_CLEAN_UNIFORM_SLOT_WEIGHT,
  keyWeight = V4_CLEAN_UNIFORM_KEY_WEIGHT,
}) {
  const requiredSlots = v4RequiredSlots();
  const missingSlots = requiredSlots.filter((slotNo) => !(slotNo in slotPlayerIds));
  if (missingSlots.length) {
    throw new Error(`slotPlayerIds is missing required slots: ${missingSlots.join(", ")}`);
  }

  const rawKeySlots = formationKeySlots?.[formationId] || {};
  const validKeySlots = {};
  Object.entries(rawKeySlots).forEach(([rawKeyNo, rawSlotNo]) => {
    const keyNo = Number(rawKeyNo);
    const slotNo = Number(rawSlotNo);
    if (!Number.isInteger(keyNo) || keyNo < 1 || keyNo > 4) return;
    if (!Number.isInteger(slotNo) || slotNo < 1 || slotNo > STARTING_LINEUP_SIZE) {
      throw new Error(`formationKeySlots[${formationId}][${keyNo}] has invalid slot: ${slotNo}`);
    }
    validKeySlots[keyNo] = slotNo;
  });

  const keySlotNumbers = new Set(Object.values(validKeySlots));
  let starting11PointSum = 0;
  let starting11AdjustedSum = 0;
  const appliedSlotWeight = asFiniteNumber(slotWeight, "slotWeight");
  const appliedKeyWeight = asFiniteNumber(keyWeight, "keyWeight");
  const slotBreakdown = requiredSlots.map((slotNo) => {
    const playerId = Number(slotPlayerIds[slotNo]);
    if (!Number.isInteger(playerId)) {
      throw new Error(`slotPlayerIds[${slotNo}] has invalid player id`);
    }
    if (!(playerId in playerPointById)) {
      throw new Error(`playerPointById is missing player_id: ${playerId}`);
    }
    const playerPoint = asFiniteNumber(playerPointById[playerId], `playerPointById[${playerId}]`);
    const slotExpectedPoint = lookupFormationSlotExpected(formationSlotExpected, formationId, slotNo);
    const adjustedPoint = playerPoint - slotExpectedPoint;
    const contribution = appliedSlotWeight * adjustedPoint;
    starting11PointSum += playerPoint;
    starting11AdjustedSum += adjustedPoint;
    return {
      slotNo,
      playerId,
      playerPoint,
      slotExpectedPoint,
      adjustedPoint,
      weight: appliedSlotWeight,
      contribution,
      isKeyslot: keySlotNumbers.has(slotNo),
    };
  });
  const starting11Contribution = appliedSlotWeight * starting11AdjustedSum;

  let keyslotPointSum = 0;
  let keyslotAdjustedSum = 0;
  const keyslotBreakdown = Object.entries(validKeySlots)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([rawKeyNo, slotNo]) => {
      const keyNo = Number(rawKeyNo);
      const playerId = Number(slotPlayerIds[slotNo]);
      const playerPoint = asFiniteNumber(playerPointById[playerId], `playerPointById[${playerId}]`);
      const slotExpectedPoint = lookupFormationSlotExpected(formationSlotExpected, formationId, slotNo);
      const adjustedPoint = playerPoint - slotExpectedPoint;
      const contribution = appliedKeyWeight * adjustedPoint;
      keyslotPointSum += playerPoint;
      keyslotAdjustedSum += adjustedPoint;
      return {
        keyNo,
        slotNo,
        playerId,
        playerPoint,
        slotExpectedPoint,
        adjustedPoint,
        weight: appliedKeyWeight,
        contribution,
      };
    });
  const keyslotContribution = appliedKeyWeight * keyslotAdjustedSum;
  const formationContribution = asFiniteNumber(formationPower?.[formationId] ?? 0, `formationPower[${formationId}]`);
  const coachContribution = includeCoachPower && coachPowerById && headcoachId != null
    ? asFiniteNumber(coachPowerById?.[headcoachId] ?? 0, `coachPowerById[${headcoachId}]`)
    : 0;
  const totalIndex = formationContribution + starting11Contribution + keyslotContribution + coachContribution;
  return {
    totalIndex,
    formationContribution,
    starting11PointSum,
    starting11AdjustedSum,
    starting11Contribution,
    keyslotPointSum,
    keyslotAdjustedSum,
    keyslotContribution,
    coachContribution,
    slotBreakdown,
    keyslotBreakdown,
  };
}

function selectedFormationKeySlotLookup() {
  const fid = Number(selectedFormationId);
  if (!Number.isInteger(fid) || fid <= 0) return {};
  const formation = formations.find((f) => Number(f?.id) === fid);
  const rows = Array.isArray(formation?.keyPositions) ? formation.keyPositions : [];
  const keySlots = {};
  rows.forEach((row) => {
    const keyNo = Number(row?.rank);
    const slotNo = Number(row?.slot);
    if (Number.isInteger(keyNo) && keyNo >= 1 && keyNo <= 4 && Number.isInteger(slotNo)) {
      keySlots[keyNo] = slotNo;
    }
  });
  return { [fid]: keySlots };
}

function buildMyTeamV4CleanUniformInput() {
  const formationId = Number(selectedFormationId);
  const warnings = [];
  if (!Number.isInteger(formationId) || formationId <= 0) {
    warnings.push("Formation not selected.");
    return { input: null, warnings };
  }

  const slotPlayerIds = {};
  const playerPointById = {};
  const pointSourceBySlot = {};
  for (let slotNo = 1; slotNo <= STARTING_LINEUP_SIZE; slotNo += 1) {
    const entry = lineup[slotNo - 1];
    const playerId = Number(entry?.playerId);
    if (!Number.isInteger(playerId)) {
      warnings.push(`Slot ${slotNo}: player not registered.`);
      continue;
    }
    const player = players.find((p) => Number(p?.id) === playerId);
    if (!player) {
      warnings.push(`Slot ${slotNo}: player data not found (${playerId}).`);
      continue;
    }
    slotPlayerIds[slotNo] = playerId;
    const pointInfo = resolveMyTeamPlayerPoint(formationId, slotNo, player);
    const avgPts = Number(pointInfo?.point);
    if (!Number.isFinite(avgPts)) {
      warnings.push(`Slot ${slotNo}: point estimate not found for ${player.name}.`);
      continue;
    }
    playerPointById[playerId] = avgPts;
    pointSourceBySlot[slotNo] = {
      playerId,
      playerName: player.name,
      point: avgPts,
      source: pointInfo.source || "",
      label: pointInfo.label || "",
      referencePlayerId: pointInfo.referencePlayerId || 0,
    };
    if (pointInfo.source !== "cc-exact") {
      warnings.push(`Slot ${slotNo}: ${player.name} ${pointInfo.label || "estimated"} = ${formatIndexValue(avgPts, 2)}`);
    }
  }

  if (!v4CleanUniformData?.formationPower || !(String(formationId) in v4CleanUniformData.formationPower)) {
    warnings.push("Formation power not found. 0.00 is used.");
  }

  return {
    input: {
      formationId,
      headcoachId: selectedCoach?.coachId == null ? null : Number(selectedCoach.coachId),
      slotPlayerIds,
      playerPointById,
      formationKeySlots: selectedFormationKeySlotLookup(),
      formationPower: v4CleanUniformData?.formationPower || {},
      formationSlotExpected: v4CleanUniformData?.formationSlotExpectedPts || {},
      coachPowerById: v4CleanUniformData?.coachPower || {},
      includeCoachPower: true,
      slotWeight: v4TeamPowerSlotWeight(),
      keyWeight: v4TeamPowerKeyWeight(),
    },
    pointSourceBySlot,
    warnings,
  };
}

function formatIndexValue(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "-";
}

function renderTeamIndex() {
  if (!els.myTeamIndexWrap) return;
  const { input, pointSourceBySlot, warnings } = buildMyTeamV4CleanUniformInput();
  if (!input) {
    els.myTeamIndexWrap.innerHTML = `
      <section class="myteam-index-card is-empty">
        <div class="myteam-index-head">
          <span class="myteam-index-title"><span class="myteam-index-label">Team Power Index</span><button type="button" class="myteam-index-info" data-tpi-info aria-label="Team Power Index info">i</button></span>
          <strong class="myteam-index-value">-</strong>
        </div>
        <p class="myteam-index-note">${warnings.map(escapeHtml).join(" / ") || "No index data."}</p>
      </section>
    `;
    renderTpiInfoBenchmark();
    return;
  }

  try {
    const result = calcTeamV4CleanUniformIndex(input);
    const warningHtml = warnings.length
      ? `<div class="myteam-index-warnings">${warnings.map((w) => `<span>${escapeHtml(w)}</span>`).join("")}</div>`
      : "";
    latestRenderedTeamTpi = result.totalIndex;
    els.myTeamIndexWrap.innerHTML = `
      <section class="myteam-index-card">
        <div class="myteam-index-head">
          <span class="myteam-index-title"><span class="myteam-index-label">Team Power Index</span><button type="button" class="myteam-index-info" data-tpi-info aria-label="Team Power Index info">i</button></span>
          <strong class="myteam-index-value">${formatIndexValue(result.totalIndex, 2)}</strong>
        </div>
        <div class="myteam-index-grid">
          <span>Slots <strong>${formatIndexValue(result.starting11Contribution, 2)}</strong></span>
          <span>Key Slots <strong>${formatIndexValue(result.keyslotContribution, 2)}</strong></span>
          <span>Formation <strong>${formatIndexValue(result.formationContribution, 2)}</strong></span>
          <span>Coach <strong>${formatIndexValue(result.coachContribution, 2)}</strong></span>
        </div>
        ${warningHtml}
      </section>
    `;
    renderTpiInfoBenchmark();
    return;
  } catch (error) {
    latestRenderedTeamTpi = null;
    const allWarnings = [...warnings, error?.message || "Index calculation failed."];
    const knownSlots = Object.values(pointSourceBySlot || {}).length;
    els.myTeamIndexWrap.innerHTML = `
      <section class="myteam-index-card is-empty">
        <div class="myteam-index-head">
          <span class="myteam-index-title"><span class="myteam-index-label">Team Power Index</span><button type="button" class="myteam-index-info" data-tpi-info aria-label="Team Power Index info">i</button></span>
          <strong class="myteam-index-value">-</strong>
        </div>
        <p class="myteam-index-note">CC Avg found: ${knownSlots}/11</p>
        <div class="myteam-index-warnings">${allWarnings.map((w) => `<span>${escapeHtml(w)}</span>`).join("")}</div>
      </section>
    `;
    renderTpiInfoBenchmark();
  }
}

function getSelectedFormationKeySlots() {
  const fid = Number(selectedFormationId);
  if (!Number.isInteger(fid) || fid <= 0) return new Set();
  const formation = formations.find((f) => Number(f?.id) === fid);
  const rows = Array.isArray(formation?.keyPositions) ? formation.keyPositions : [];
  const set = new Set();
  rows.forEach((r) => {
    const slot = Number(r?.slot);
    if (Number.isInteger(slot) && slot >= 1 && slot <= STARTING_LINEUP_SIZE) set.add(slot);
  });
  return set;
}

function closeMenuPanel() {
  if (!els.myteamMenuPanel) return;
  els.myteamMenuPanel.classList.remove("is-open");
}

function syncMenuButtonSize() {
  if (!els.myteamMenuButton) return;
  document.documentElement.style.setProperty("--menu-button-size", "60px");
}

function openMyteamSettingModal() {
  if (!els.myteamSettingModal) return;
  if (els.myteamRenameLineupKey) {
    els.myteamRenameLineupKey.value = cloudConfig.lineupKey || "";
    els.myteamRenameLineupKey.focus();
  }
  els.myteamSettingModal.hidden = false;
}

function closeMyteamSettingModal() {
  if (!els.myteamSettingModal) return;
  els.myteamSettingModal.hidden = true;
}

function openTpiInfoModal() {
  if (els.tpiInfoModal) {
    els.tpiInfoModal.hidden = false;
    renderTpiInfoBenchmark();
    window.setTimeout(() => {
      els.tpiInfoModal?.querySelector(".tpi-champion-cell.is-active")?.scrollIntoView({ block: "nearest", inline: "center" });
    }, 0);
  }
}

function closeTpiInfoModal() {
  if (els.tpiInfoModal) els.tpiInfoModal.hidden = true;
}

function tpiGridLabelFromValue(value, step = 0.25) {
  const idx = Math.floor(value / step);
  const start = idx * step;
  const end = start + step;
  return `${formatIndexValue(start, 2)}〜${formatIndexValue(end, 2)}`;
}

function renderTpiInfoBenchmark() {
  const rows = Array.isArray(ccRangeData?.rows) ? ccRangeData.rows : [];
  const skippedFinals = Number(ccRangeData?.skippedFinals || 0);
  const currentTpi = Number(latestRenderedTeamTpi);
  const activeLabel = Number.isFinite(currentTpi) ? tpiGridLabelFromValue(currentTpi) : null;

  document.querySelectorAll("[data-tpi-champion-benchmark]").forEach((box) => {
    if (!rows.length) {
      const noteEl = box.querySelector("[data-tpi-champion-note]");
      const gridEl = box.querySelector("[data-tpi-champion-grid]");
      if (noteEl) noteEl.textContent = "集計データを読み込めませんでした（cc_range_data.json が未設定）";
      if (gridEl) gridEl.innerHTML = `<div class="tpi-champion-cell"><span class="tpi-champion-cell-range">N/A</span><strong>—</strong><small>—/—</small></div>`;
      box.hidden = false;
      return;
    }
    const noteEl = box.querySelector("[data-tpi-champion-note]");
    const gridEl = box.querySelector("[data-tpi-champion-grid]");
    if (noteEl) {
      const championCount = rows.reduce((acc, row) => acc + Number(row?.champions || 0), 0);
      const totalCount = rows.reduce((acc, row) => acc + Number(row?.totalTeams || 0), 0);
      const skipText = skippedFinals > 0 ? ` / PK不明の同点決勝${skippedFinals}件を除外` : "";
      noteEl.textContent = `出場${totalCount} teams / 優勝${championCount} teams${skipText}`;
    }
    if (gridEl) {
      const rowsKey = JSON.stringify(rows);
      const needsRender = gridEl.dataset.rowsKey !== rowsKey;
      if (needsRender) {
        gridEl.innerHTML = rows.map((row) => {
          const label = String(row?.label || "");
          const total = Number(row?.totalTeams || 0);
          const champions = Number(row?.champions || 0);
          const prob = total > 0 ? (champions / total) * 100 : 0;
          const isActive = activeLabel && label === activeLabel;
          return `<div class="tpi-champion-cell${isActive ? " is-active" : ""}" data-tpi-champion-label="${escapeHtml(label)}"><span class="tpi-champion-cell-range">${escapeHtml(label)}</span><strong>${prob.toFixed(1)}%</strong><small>${champions}/${total}</small></div>`;
        }).join("");
        gridEl.dataset.rowsKey = rowsKey;
      } else {
        gridEl.querySelectorAll(".tpi-champion-cell").forEach((cell) => {
          const label = cell.getAttribute("data-tpi-champion-label");
          cell.classList.toggle("is-active", Boolean(activeLabel && label === activeLabel));
        });
      }
    }
    box.hidden = false;
  });
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
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

function saveLineupLocal() {
  localStorage.setItem(lineupStorageKeyForCurrentMode(), JSON.stringify(lineup));
}

function loadLifecycleMode() {
  if (IS_SIMULATION_MODE) {
    lifecycleModeEnabled = false;
    return;
  }
  lifecycleModeEnabled = localStorage.getItem(LIFECYCLE_MODE_STORAGE_KEY) === "1";
}

function saveLifecycleMode() {
  if (IS_SIMULATION_MODE) return;
  localStorage.setItem(LIFECYCLE_MODE_STORAGE_KEY, lifecycleModeEnabled ? "1" : "0");
}

function renderLifecycleControls() {
  if (els.lifecycleToggle) {
    els.lifecycleToggle.classList.toggle("is-on", lifecycleModeEnabled);
    els.lifecycleToggle.textContent = lifecycleModeEnabled ? "Cycle Management Mode: ON" : "Cycle Management Mode: OFF";
  }
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

function logoutTeamId() {
  cloudConfig = {
    url: normalizedSupabaseUrl(FIXED_SUPABASE_URL || cloudConfig.url),
    anonKey: String(FIXED_SUPABASE_ANON_KEY || cloudConfig.anonKey).trim(),
    lineupKey: "",
  };
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
}

async function loginTeamIdFromMyTeam() {
  closeMenuPanel();
  openLoginModal();
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

async function applyLoginFromModal() {
  const nextKey = String(els.loginLineupKey?.value || "").trim();
  if (!nextKey) return;
  const prevKey = String(cloudConfig.lineupKey || "").trim();
  cloudConfig.lineupKey = nextKey;
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
  renderMyTeamMeta();
  if (els.myTeamTarget) els.myTeamTarget.textContent = "";
  try {
    const exists = await cloudLineupExists(nextKey);
    if (!exists) {
      cloudConfig.lineupKey = prevKey;
      localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
      renderMyTeamMeta();
      window.alert("入力されたIDの登録はありません。Create New IDを使用してください。");
      return;
    }
    if (IS_SIMULATION_MODE) {
      await loadSimulationStateForCurrentId();
      buildFormationOptions();
      closeFormationEditor();
      renderFormationCurrent();
      renderLineup();
      closeLoginModal();
      return;
    }
    await loadCloudLineup();
    await loadCloudFormationId();
    buildFormationOptions();
    closeFormationEditor();
    renderFormationCurrent();
    renderLineup();
    closeLoginModal();
  } catch (e) {
    cloudConfig.lineupKey = prevKey;
    localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
    renderMyTeamMeta();
    if (els.myTeamTarget) els.myTeamTarget.textContent = "クラウド読込に失敗しました";
    window.alert("Loginに失敗しました。");
  }
}

async function applySignupFromModal() {
  const nextKey = String(els.signupLineupKey?.value || "").trim();
  if (!nextKey) return;
  const prevKey = String(cloudConfig.lineupKey || "").trim();
  cloudConfig.lineupKey = nextKey;
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
  renderMyTeamMeta();
  if (els.myTeamTarget) els.myTeamTarget.textContent = "";
  try {
    const exists = await cloudLineupExists(nextKey);
    if (exists) {
      cloudConfig.lineupKey = prevKey;
      localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
      renderMyTeamMeta();
      window.alert("そのIDは既に使われています。別のIDを入力してください。");
      return;
    }
    lineup = Array.from({ length: LINEUP_SIZE }, () => null);
    saveLineupLocal();
    await saveCloudLineup();
    await saveCloudFormationId();
    buildFormationOptions();
    closeFormationEditor();
    renderFormationCurrent();
    renderLineup();
    closeSignupModal();
    closeLoginModal();
  } catch (e) {
    cloudConfig.lineupKey = prevKey;
    localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
    renderMyTeamMeta();
    window.alert("Create New IDに失敗しました。");
  }
}

function renderMyTeamMeta() {
  if (!els.myTeamMeta) return;
  const loggedIn = hasCloudConfig();
  const ccLine = ccDataMeta
    ? `<span class="meta-line">CC Data: ${ccDataMeta.seasonStart}-${ccDataMeta.seasonEnd} / ${ccDataMeta.games} games</span>`
    : "";
  els.myTeamMeta.innerHTML = `<span class="meta-line">Updated: ${appUpdatedAtJst}</span>${ccLine}`;
  if (els.myteamLoginButton) els.myteamLoginButton.hidden = loggedIn;
  if (els.myteamLogoutButton) els.myteamLogoutButton.hidden = !loggedIn;
  if (els.myteamMenuLoginId) {
    els.myteamMenuLoginId.hidden = !loggedIn;
    els.myteamMenuLoginId.textContent = loggedIn ? `Team ID：${cloudConfig.lineupKey}` : "";
  }
  refreshUpdatedAtFromGitHub();
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
  if (updatedAtFetchStarted) return;
  updatedAtFetchStarted = true;
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
    if (els.myTeamMeta) {
      const loggedIn = hasCloudConfig();
      const ccLine = ccDataMeta
        ? `<span class="meta-line">CC Data: ${ccDataMeta.seasonStart}-${ccDataMeta.seasonEnd} / ${ccDataMeta.games} games</span>`
        : "";
      els.myTeamMeta.innerHTML = `<span class="meta-line">Updated: ${appUpdatedAtJst}</span>${ccLine}`;
      if (els.myteamLoginButton) els.myteamLoginButton.hidden = loggedIn;
      if (els.myteamLogoutButton) els.myteamLogoutButton.hidden = !loggedIn;
    }
  } catch (e) {
    // fallback static label
  }
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

function hasCloudConfig() {
  return !!(cloudConfig.url && cloudConfig.anonKey && cloudConfig.lineupKey);
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
  if (!res.ok) {
    throw new Error(`supabase ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loadCloudLineup(mode = IS_SIMULATION_MODE ? "simulation" : "myteam") {
  const lineupId = cloudLineupIdForMode(mode);
  if (!lineupId) return false;
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${lineupId}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  if (!Array.isArray(rows) || !rows.length) {
    if (mode !== "simulation") {
      selectedCoach = null;
      saveSelectedCoach();
    }
    return false;
  }
  const remote = rows[0]?.lineup_json;
  if (!Array.isArray(remote)) return false;
  lineup = normalizeLineupArray(remote);
  saveLineupLocal();
  return true;
}

async function loadCloudFormationId(mode = IS_SIMULATION_MODE ? "simulation" : "myteam") {
  const metaId = cloudMetaIdForMode(mode);
  if (!metaId) return false;
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${metaId}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  if (!Array.isArray(rows) || !rows.length) return false;
  const remote = rows[0]?.lineup_json;
  selectedFormationId = normalizeFormationId(remote?.formationId);
  selectedCoach = normalizeCoach(remote?.coach);
  saveSelectedFormationId();
  saveSelectedCoach();
  return selectedFormationId != null;
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

async function saveCloudLineup(mode = IS_SIMULATION_MODE ? "simulation" : "myteam") {
  const lineupId = cloudLineupIdForMode(mode);
  if (!lineupId) return;
  const payload = {
    lineup_id: lineupId,
    lineup_json: lineup,
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

async function saveCloudFormationId(mode = IS_SIMULATION_MODE ? "simulation" : "myteam") {
  const metaId = cloudMetaIdForMode(mode);
  if (!metaId) return;
  const payload = {
    lineup_id: metaId,
    lineup_json: {
      formationId: normalizeFormationId(selectedFormationId),
      coach: selectedCoach,
    },
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

function myTeamFormationStorageKeyForCurrentId() {
  return scopedStorageKey(MYTEAM_FORMATION_STORAGE_KEY);
}

function myTeamCoachStorageKeyForCurrentId() {
  return scopedStorageKey(MYTEAM_COACH_STORAGE_KEY);
}

function stripLineupForSimulation(rows) {
  return Array.from({ length: LINEUP_SIZE }, (_, i) => {
    const row = rows?.[i];
    const playerId = Number(row?.playerId);
    return Number.isInteger(playerId) && playerId > 0
      ? { playerId, season: null, successor: null }
      : null;
  });
}

function loadLocalLineupForCurrentMode() {
  try {
    const parsed = JSON.parse(localStorage.getItem(lineupStorageKeyForCurrentMode()) || "null");
    const localLineup = normalizeLineupArray(parsed);
    if (!Array.isArray(localLineup)) return false;
    lineup = IS_SIMULATION_MODE ? stripLineupForSimulation(localLineup) : localLineup;
    return lineup.some((row) => row && Number.isInteger(Number(row.playerId)));
  } catch (_) {
    return false;
  }
}

function loadLocalSimulationState() {
  const lineupLoaded = loadLocalLineupForCurrentMode();
  loadSelectedFormationId();
  loadSelectedCoach();
  return lineupLoaded || selectedFormationId != null || selectedCoach != null;
}

async function loadSimulationStateForCurrentId() {
  if (!IS_SIMULATION_MODE) return false;
  lineup = Array.from({ length: LINEUP_SIZE }, () => null);
  selectedFormationId = null;
  selectedCoach = null;
  let loaded = false;
  if (hasCloudConfig()) {
    try {
      const lineupLoaded = await loadCloudLineup("simulation");
      const metaLoaded = await loadCloudFormationId("simulation");
      loaded = !!lineupLoaded || !!metaLoaded;
    } catch (e) {
      console.warn(e);
      loaded = false;
    }
  }
  if (!loaded) loaded = loadLocalSimulationState();
  return loaded;
}

function loadLocalMyTeamStateForSimulation() {
  let localLineup = null;
  try {
    const parsed = JSON.parse(localStorage.getItem(LINEUP_STORAGE_KEY) || "null");
    localLineup = normalizeLineupArray(parsed);
  } catch (_) {
    localLineup = null;
  }
  if (Array.isArray(localLineup)) {
    lineup = stripLineupForSimulation(localLineup);
  }

  selectedFormationId = normalizeFormationId(localStorage.getItem(myTeamFormationStorageKeyForCurrentId()));
  try {
    const coach = normalizeCoach(JSON.parse(localStorage.getItem(myTeamCoachStorageKeyForCurrentId()) || "null"));
    selectedCoach = coach ? { coachId: coach.coachId, season: null } : null;
  } catch (_) {
    selectedCoach = null;
  }

  return Array.isArray(localLineup) && localLineup.some((row) => row && Number.isInteger(Number(row.playerId)));
}

async function copyMyTeamStateToSimulation() {
  if (!IS_SIMULATION_MODE) return;
  let copied = false;
  if (hasCloudConfig()) {
    try {
      const lineupLoaded = await loadCloudLineup("myteam");
      const metaLoaded = await loadCloudFormationId("myteam");
      copied = !!lineupLoaded || !!metaLoaded;
    } catch (_) {
      copied = false;
    }
  }
  if (!copied) copied = loadLocalMyTeamStateForSimulation();
  lineup = stripLineupForSimulation(lineup);
  if (selectedCoach) selectedCoach = { coachId: Number(selectedCoach.coachId), season: null };
  if (!copied) {
    window.alert("コピーできるMyTeam登録が見つかりませんでした。");
  }
  saveLineupLocal();
  saveSelectedFormationId();
  saveSelectedCoach();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup("simulation");
      await saveCloudFormationId("simulation");
    } catch (e) {
      window.alert("Simulationのクラウド保存に失敗しました。");
    }
  }
  renderLineup();
}

async function cloudDeleteLineupById(lineupId, required = true) {
  const key = String(lineupId || "").trim();
  if (!key) return;
  const params = new URLSearchParams({
    lineup_id: `eq.${key}`,
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "DELETE",
    headers: {
      Prefer: "return=representation",
    },
  });
  const deletedCount = Array.isArray(rows) ? rows.length : 0;
  if (required && deletedCount < 1) {
    throw new Error("delete_not_applied");
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

function latestHistoryStart(player, key) {
  const rows = Array.isArray(player?.[key]) ? player[key] : [];
  let latest = "";
  rows.forEach((row) => {
    const s = String(row?.start || "");
    if (s > latest) latest = s;
  });
  return latest;
}

function badgeCategoryByRecency(player) {
  const category = getCategory(player);
  if (category !== "CM/SS") return category;
  const ssLatest = latestHistoryStart(player, "scoutHistory");
  const cmLatest = latestHistoryStart(player, "cmHistory");
  if (cmLatest && !ssLatest) return "CM";
  if (ssLatest && !cmLatest) return "SS";
  if (!cmLatest && !ssLatest) return "SS";
  return cmLatest > ssLatest ? "CM" : "SS";
}

function typeLabelByPlayer(player) {
  return badgeCategoryByRecency(player);
}

function typeClassByPlayer(player) {
  const typeLabel = typeLabelByPlayer(player);
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

function positionClass(position) {
  const pos = (position || "-").toUpperCase();
  if (pos === "GK") return "pos-gk";
  if (pos === "DF") return "pos-df";
  if (pos === "MF") return "pos-mf";
  if (pos === "FW") return "pos-fw";
  return "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function toHiragana(value) {
  return String(value || "")
    .replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60))
    .replace(/[・･·.．\s\-ー＝=]/g, "")
    .toLowerCase();
}

function normalizedReplacementSearchText(player) {
  return toHiragana(player?.name || "");
}

function replacementCategoryRank(player) {
  const label = typeLabelByPlayer(player);
  if (label === "NR") return 0;
  if (label === "CC") return 1;
  if (label === "SS") return 2;
  if (label === "CM") return 3;
  return 4;
}

function coreTotal(metrics) {
  return (metrics?.["スピ"] || 0) + (metrics?.["テク"] || 0) + (metrics?.["パワ"] || 0);
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
  const periods = Array.isArray(player.periods) ? player.periods : [];
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

function findPeriodBySeason(player, season) {
  if (!player || !season) return null;
  const periods = Array.isArray(player.periods) ? player.periods : [];
  return periods.find((p) => p?.season === season) || null;
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

function hasAnyFirstSeasonPlayers() {
  return lineup.some((entry) => {
    const playerId = Number(entry?.playerId);
    if (!Number.isInteger(playerId)) return false;
    const player = players.find((x) => x.id === playerId);
    const periods = Array.isArray(player?.periods) ? player.periods : [];
    const seasons = periods.map((p) => p?.season).filter(Boolean);
    if (!seasons.length) return false;
    const currentSeason = entry?.season || null;
    const idx = seasons.findIndex((s) => s === currentSeason);
    return idx <= 0;
  });
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

function getSuccessorDisplaySeason(entry) {
  const successor = normalizeSuccessor(entry?.successor);
  if (!successor) return null;
  const successorPlayer = players.find((x) => x.id === successor.playerId);
  if (!successorPlayer) return successor.season || null;

  const currentPlayerId = Number(entry?.playerId);
  const currentPlayer = Number.isInteger(currentPlayerId) ? players.find((x) => x.id === currentPlayerId) : null;
  const currentSeason = entry?.season || null;
  const currentRemaining = currentPlayer ? getRemainingPeakPeriods(currentPlayer, currentSeason) : 0;
  return shiftSeasonForEntry(successorPlayer, successor.season || null, Math.max(0, currentRemaining));
}

function successorSummaryHtml(entry, currentRemaining) {
  const successor = entry?.successor;
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

  const baseSeason = successor?.season || null;
  const evalSeason = shiftSeasonForEntry(successorPlayer, baseSeason, Math.max(0, currentRemaining));
  const remain = getRemainingPeakPeriods(successorPlayer, evalSeason);
  const sourceText = successor?.source ? `<span class="lineup-successor-source">${successor.source}</span>` : "";
  const pos = (successorPlayer.position || "-").toUpperCase();
  const posClass = positionClass(pos);
  const typeLabel = typeLabelByPlayer(successorPlayer);
  const typeClass = typeClassByPlayer(successorPlayer);

  return `
    <div class="lineup-successor">
      <div class="lineup-successor-arrow" aria-hidden="true">▶</div>
      <div class="lineup-thumb-wrap">
        <img loading="lazy" src="./images/chara/players/static/${successorPlayer.id}.gif" alt="${successorPlayer.name}" />
      </div>
      <div class="lineup-successor-meta">
        <div class="lineup-badges">
          <span class="badge pos-badge ${posClass}">${pos}</span>
          <span class="badge type-badge ${typeClass}">${typeLabel}</span>
          ${remainingBadgeHtml(remain)}
        </div>
        <span class="slot-name">${successorPlayer.name}</span>
        ${sourceText}
      </div>
    </div>
  `;
}

async function shiftAllLineupSeasons(delta) {
  if (!Number.isInteger(delta) || delta === 0) return false;
  let changed = false;
  lineup = lineup.map((entry) => {
    if (!entry || !Number.isInteger(Number(entry.playerId))) return entry;
    const player = players.find((x) => x.id === Number(entry.playerId));
    if (!player) return entry;
    const nextSeason = shiftSeasonForEntry(player, entry.season || null, delta);
    const successor = normalizeSuccessor(entry.successor);
    let nextSuccessor = successor;
    if (successor) {
      const successorPlayer = players.find((x) => x.id === successor.playerId);
      if (successorPlayer) {
        nextSuccessor = {
          ...successor,
          season: shiftSeasonForEntry(successorPlayer, successor.season || null, delta),
        };
      }
    }
    if (nextSeason !== (entry.season || null)) changed = true;
    if ((nextSuccessor?.season || null) !== (entry.successor?.season || null)) changed = true;
    return { ...entry, season: nextSeason, successor: nextSuccessor };
  });

  if (selectedCoach && Number.isInteger(Number(selectedCoach.coachId))) {
    const coach = (Array.isArray(coaches) ? coaches : []).find((c) => Number(c?.id) === Number(selectedCoach.coachId));
    const max = Math.max(1, Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason.length : 1);
    const cur = coachSeasonNumber(selectedCoach.season || "1期目");
    const next = Math.max(1, Math.min(max, cur + delta));
    if (next !== cur) {
      selectedCoach = { ...selectedCoach, season: `${next}期目` };
      changed = true;
    }
  }

  if (!changed) return false;
  saveLineupLocal();
  saveSelectedCoach();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup();
      await saveCloudFormationId();
    } catch (e) {
      console.warn(e);
    }
  }
  renderLineup();
  if (els.playerCardModal && !els.playerCardModal.hidden && Number.isInteger(selectedSlotIndex)) {
    renderPlayerCardModal();
  }
  return true;
}

function miniCoreMetric(metric, value) {
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
}

function myTeamSlotLabelByIndex(idx) {
  if (idx < STARTING_LINEUP_SIZE) return String(idx + 1);
  return `R${idx - STARTING_LINEUP_SIZE + 1}`;
}

function renderReserveTotals() {
  if (!els.myTeamReserveTotals) return;
  if (IS_SIMULATION_MODE) {
    els.myTeamReserveTotals.innerHTML = "";
    return;
  }
  let individualityTotal = 0;
  let popularityTotal = 0;
  lineup.forEach((entry) => {
    const playerId = Number(entry?.playerId);
    if (!Number.isInteger(playerId)) return;
    const player = players.find((x) => x.id === playerId);
    if (!player) return;
    const selectedPeriod = findPeriodBySeason(player, entry?.season || null);
    const metrics = selectedPeriod?.metrics || getPeakMetrics(player);
    individualityTotal += Number(metrics?.["個性"] || 0);
    popularityTotal += Number(metrics?.["人気"] || 0);
  });
  let coachLeadershipNow = "-";
  if (selectedCoach && Number.isInteger(Number(selectedCoach.coachId))) {
    const coach = (Array.isArray(coaches) ? coaches : []).find((c) => Number(c?.id) === Number(selectedCoach.coachId));
    const leadership = Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason : [];
    const seasonNum = coachSeasonNumber(selectedCoach?.season || "1期目");
    const leadValue = leadership[seasonNum - 1];
    if (Number.isFinite(Number(leadValue))) coachLeadershipNow = Number(leadValue);
  }
  els.myTeamReserveTotals.innerHTML = `
    <span class="reserve-total-item">個性 <span class="reserve-total-value">${individualityTotal}</span>/${coachLeadershipNow}</span>
    <span class="reserve-total-item">人気 <span class="reserve-total-value">${popularityTotal}</span></span>
  `;
}

function renderLineup() {
  if (!els.myTeamSlots) return;
  const keySlots = getSelectedFormationKeySlots();
  const renderSlotRange = (start, end) => lineup.slice(start, end).map((entry, localIdx) => {
    const idx = start + localIdx;
    const slot = idx + 1;
    const slotLabel = myTeamSlotLabelByIndex(idx);
    const playerId = Number(entry?.playerId);
    const player = Number.isInteger(playerId) ? players.find((x) => x.id === playerId) : null;
    const name = player ? player.name : "未登録";
    const season = player ? (entry?.season || null) : null;
    const seasonText = season ? `${season}目` : "-";
    const remaining = player ? getRemainingPeakPeriods(player, season) : 0;
    const seasonBadge = IS_SIMULATION_MODE
      ? ""
      : lifecycleModeEnabled
      ? remainingBadgeHtml(remaining)
      : `<span class="badge lineup-season">${seasonText}</span>`;
    const pos = (player?.position || "-").toUpperCase();
    const posClass = positionClass(pos);
    const typeLabel = player ? typeLabelByPlayer(player) : "-";
    const typeClass = player ? typeClassByPlayer(player) : "cat-na";
    const imageHtml = player
      ? `<img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${player.name}" />`
      : `<div class="lineup-empty-thumb"></div>`;
    const selectedPeriod = player ? findPeriodBySeason(player, season) : null;
    const selectedMetrics = selectedPeriod?.metrics || (player ? getPeakMetrics(player) : null);
    const v4PointInfo = (player && Number.isInteger(selectedFormationId) && idx < STARTING_LINEUP_SIZE)
      ? resolveMyTeamPlayerPoint(selectedFormationId, slot, player)
      : null;
    const v4Point = Number(v4PointInfo?.point);
    const pointEstimated = !!v4PointInfo && v4PointInfo.source !== "cc-exact";
    const ccStatText = player && Number.isInteger(selectedFormationId) && idx < STARTING_LINEUP_SIZE
      ? `Pts ${formatIndexValue(v4Point, 2)}`
      : "";
    const ccStatClass = `lineup-cc-stat${pointEstimated ? " is-estimated" : ""}`;
    const rightPaneHtml = player
      ? (lifecycleModeEnabled
        ? successorSummaryHtml(entry, remaining)
        : `
          <div class="lineup-core">
            ${miniCoreMetric("スピ", selectedMetrics?.["スピ"])}
            ${miniCoreMetric("テク", selectedMetrics?.["テク"])}
            ${miniCoreMetric("パワ", selectedMetrics?.["パワ"])}
          </div>
        `)
      : "";

    const keyStar = keySlots.has(slot)
      ? `<span class="slot-key-star" aria-label="Key Position" title="Key Position">★</span>`
      : "";
    return `
      <button type="button" class="lineup-slot${player ? " has-player" : ""} myteam-slot" data-slot-index="${idx}">
        <span class="slot-no">${slotLabel}${keyStar}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              <span class="badge type-badge ${typeClass}">${typeLabel}</span>
              ${seasonBadge}
            </div>
            <span class="slot-name">${name}</span>
            ${ccStatText ? `<span class="${ccStatClass}">${ccStatText}</span>` : ""}
          </div>
          ${rightPaneHtml}
        </div>
      </button>
    `;
  }).join("");
  els.myTeamSlots.innerHTML = renderSlotRange(0, STARTING_LINEUP_SIZE);
  if (els.myTeamReserveSlots) {
    els.myTeamReserveSlots.innerHTML = IS_SIMULATION_MODE ? "" : renderSlotRange(STARTING_LINEUP_SIZE, LINEUP_SIZE);
  }
  renderReserveTotals();
  renderCoachSection();
  renderFormationCurrent();
  renderTeamIndex();
}

function handleMyTeamSlotClick(e) {
  const slot = e.target.closest(".myteam-slot");
  if (!slot) return;
  const idx = Number(slot.dataset.slotIndex);
  if (!Number.isInteger(idx)) return;
  const entry = lineup[idx];
  const clickedSuccessor = lifecycleModeEnabled && !!e.target.closest(".lineup-successor");
  if (clickedSuccessor) {
    const successorId = Number(entry?.successor?.playerId);
    if (!Number.isInteger(successorId)) {
      openEmptyPlayerSlotModal(idx, "successor");
      return;
    }
    openPlayerCardModal(idx, "successor");
    return;
  }
  const playerId = Number(entry?.playerId);
  if (!Number.isInteger(playerId)) {
    openEmptyPlayerSlotModal(idx);
    return;
  }
  openPlayerCardModal(idx);
}

function renderCoachSection() {
  if (!els.myTeamCoachWrap) return;
  if (!selectedCoach || !Number.isInteger(Number(selectedCoach.coachId))) {
    els.myTeamCoachWrap.innerHTML = `
      <button type="button" class="lineup-slot myteam-slot myteam-coach-slot is-empty" id="myTeamCoachSlot">
        <span class="slot-no">HC</span>
        <div class="lineup-slot-main">
          <div class="lineup-empty-thumb"></div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge hc-badge">HC</span>
            </div>
            <span class="slot-name">未登録</span>
          </div>
        </div>
      </button>
    `;
    return;
  }
  const coachId = Number(selectedCoach.coachId);
  const coach = (Array.isArray(coaches) ? coaches : []).find((c) => Number(c?.id) === coachId);
  const name = coach?.name || `Coach ${coachId}`;
  const typeLabel = coachTypeLabel(coach?.type);
  const season = coachSeasonLabel(selectedCoach?.season || "1期目");
  const seasonNum = coachSeasonNumber(season);
  const leadership = Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason : [];
  const img = `./images/chara/headcoaches/static/${coachId}@2x.gif`;
  const formation = Number.isInteger(selectedFormationId)
    ? formations.find((x) => Number(x?.id) === Number(selectedFormationId))
    : null;
  const coachStats = Array.isArray(formation?.coachStats) ? formation.coachStats : [];
  const coachStat = coachStats.find((r) => Number(r?.coachId) === coachId) || null;
  const coachInfoText = `${typeLabel} / ${coachStat ? pct(coachStat.usageRate) : "-"} / ${coachStat ? avg(coachStat.avgPts) : "-"}`;
  const seasonBadgeHtml = IS_SIMULATION_MODE ? "" : `<span class="badge lineup-season coach-season-badge">${season}</span>`;
  const leadershipHtml = IS_SIMULATION_MODE
    ? ""
    : `<div class="lineup-coach-lead-wrap">${coachLeadershipTableHtml(leadership, seasonNum, 5)}</div>`;
  els.myTeamCoachWrap.innerHTML = `
    <button type="button" class="lineup-slot myteam-slot myteam-coach-slot has-player" id="myTeamCoachSlot">
      <span class="slot-no">HC</span>
      <div class="lineup-slot-main">
        <div class="lineup-thumb-wrap"><img loading="lazy" src="${img}" alt="${name}" /></div>
        <div class="lineup-player-meta">
          <div class="lineup-badges">
            <span class="badge pos-badge hc-badge">HC</span>
            ${seasonBadgeHtml}
          </div>
          <span class="slot-name">${name}</span>
          <span class="lineup-cc-stat">${coachInfoText}</span>
        </div>
      </div>
      ${leadershipHtml}
    </button>
  `;
}

function handleMyTeamCoachClick() {
  if (!selectedCoach || !Number.isInteger(Number(selectedCoach.coachId))) {
    openEmptyCoachCardModal();
    return;
  }
  openCoachCardModal();
}

function openEmptySlotModal() {
  if (els.emptySlotModal) els.emptySlotModal.hidden = false;
}

function closeEmptySlotModal() {
  if (els.emptySlotModal) els.emptySlotModal.hidden = true;
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

function periodTableHtml(player, staticImg, actionImg, currentSeason) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  const header = METRICS.map((m) => `<th>${detailMetricLabel(m)}</th>`).join("");
  const tiers = new Map(getPeakTimeline(player).map((x) => [x.season, x.tier]));
  const rows = periods.map((period) => {
    const metrics = period?.metrics || {};
    const values = METRICS.map((m) => `<td>${metrics[m] ?? "-"}</td>`).join("");
    const season = period?.season || "-";
    const tierClass = tiers.get(season) || "peak-none";
    const currentClass = currentSeason && season === currentSeason ? " current-season-row" : "";
    return `<tr class="${currentClass.trim()}"><th class="season-cell ${tierClass}">${season}</th>${values}</tr>`;
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
          <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
          <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
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
    { mode: 0, label: "STAT" },
    { mode: 1, label: "SZN" },
    { mode: 2, label: "INFO" },
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

function playerCardHtml(player, season) {
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
  const nTop = Math.max(0, Math.min(30, mind.zisei)) / 30;
  const nRight = Math.max(0, Math.min(30, mind.soshiki)) / 30;
  const nBottom = Math.max(0, Math.min(30, mind.kansei)) / 30;
  const nLeft = Math.max(0, Math.min(30, mind.kojin)) / 30;
  const pTop = `${cx},${cy - r * nTop}`;
  const pRight = `${cx + r * nRight},${cy}`;
  const pBottom = `${cx},${cy + r * nBottom}`;
  const pLeft = `${cx - r * nLeft},${cy}`;
  const areaPoints = `${pTop} ${pRight} ${pBottom} ${pLeft}`;
  const peakBlock = viewMode === 0 ? `<div class="peak-periods peak-in-body">${peakHtml}</div>` : "";
  const normalViewHtml = `
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
  const detailViewHtml = periodTableHtml(player, staticImg, actionImg, season);
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
  const player = players.find((p) => p.id === selectedPlayerId);
  if (!player) return;
  const entry = lineup[selectedSlotIndex];
  const season = selectedPlayerMode === "successor"
    ? getSuccessorDisplaySeason(entry)
    : (entry?.season || null);
  if (els.playerCardTitle) els.playerCardTitle.textContent = "Player";
  els.playerCardHost.innerHTML = playerCardHtml(player, season);
  if (els.playerReplaceBtn) {
    els.playerReplaceBtn.textContent = selectedPlayerMode === "successor" ? "Replace Successor" : "Replace Player";
    els.playerReplaceBtn.hidden = false;
  }
  syncPlayerReplaceLayout();
  if (els.playerRemoveSuccessorBtn) {
    els.playerRemoveSuccessorBtn.hidden = IS_SIMULATION_MODE || selectedPlayerMode !== "successor";
  }
}

function openPlayerCardModal(slotIndex, mode = "starter") {
  const entry = lineup[slotIndex];
  const playerId = mode === "successor"
    ? Number(entry?.successor?.playerId)
    : Number(entry?.playerId);
  if (!Number.isInteger(playerId)) return;
  selectedSlotIndex = slotIndex;
  selectedPlayerId = playerId;
  selectedPlayerMode = mode === "successor" ? "successor" : "starter";
  renderPlayerCardModal();
  if (els.playerCardModal) els.playerCardModal.hidden = false;
}

function openEmptyPlayerSlotModal(slotIndex, mode = "starter") {
  if (!Number.isInteger(slotIndex) || !els.playerCardModal || !els.playerCardHost) return;
  selectedSlotIndex = slotIndex;
  selectedPlayerId = null;
  selectedPlayerMode = mode === "successor" ? "successor" : "starter";
  const isSuccessor = selectedPlayerMode === "successor";
  if (els.playerCardTitle) els.playerCardTitle.textContent = isSuccessor ? "Add Successor" : "Add Player";
  els.playerCardHost.innerHTML = `
    <div class="player-replace-empty-slot">
      <div class="lineup-empty-thumb"></div>
      <div>
        <div class="player-replace-empty-title">未登録</div>
        <div class="player-replace-empty-text">${IS_SIMULATION_MODE ? "検索して選手を選択してください。" : `検索して${isSuccessor ? "後継選手" : "選手"}と期を選択してください。`}</div>
      </div>
    </div>
  `;
  if (els.playerReplaceBtn) els.playerReplaceBtn.hidden = true;
  els.playerCardModal.hidden = false;
  openPlayerReplacePanel();
}

function closePlayerCardModal() {
  selectedSlotIndex = null;
  selectedPlayerId = null;
  selectedPlayerMode = "starter";
  closePlayerReplacePanel();
  if (els.playerCardModal) els.playerCardModal.hidden = true;
  if (els.playerReplaceBtn) els.playerReplaceBtn.hidden = true;
  if (els.playerRemoveSuccessorBtn) els.playerRemoveSuccessorBtn.hidden = true;
}

function closePlayerReplacePanel() {
  replacementPlayerId = null;
  if (els.playerReplacePanel) els.playerReplacePanel.hidden = true;
  if (els.playerReplaceSearch) els.playerReplaceSearch.value = "";
  if (els.playerReplaceResults) els.playerReplaceResults.innerHTML = "";
  if (els.playerReplaceSeason) els.playerReplaceSeason.innerHTML = "";
  if (els.playerReplaceSourceWrap) els.playerReplaceSourceWrap.hidden = true;
  if (els.playerReplaceSourceType) els.playerReplaceSourceType.value = "self";
  if (els.playerReplaceSourceInput) els.playerReplaceSourceInput.value = "";
  syncPlayerReplaceSourceInput();
  if (els.playerReplaceApply) els.playerReplaceApply.disabled = true;
  syncPlayerReplaceLayout();
}

function syncPlayerReplaceSourceInput() {
  if (!els.playerReplaceSourceType || !els.playerReplaceSourceCustomWrap) return;
  els.playerReplaceSourceCustomWrap.hidden = els.playerReplaceSourceType.value !== "custom";
}


function syncPlayerReplaceLayout() {
  const isReplaceOpen = !!els.playerReplacePanel && !els.playerReplacePanel.hidden;
  if (els.playerCardModal) {
    els.playerCardModal.dataset.view = isReplaceOpen ? "replace" : "detail";
  }
  if (els.playerCardTitle) {
    if (isReplaceOpen) {
      els.playerCardTitle.textContent = selectedPlayerMode === "successor" ? "Replace Successor" : "Replace Player";
    } else if (Number.isInteger(selectedPlayerId)) {
      els.playerCardTitle.textContent = "Player";
    } else {
      els.playerCardTitle.textContent = selectedPlayerMode === "successor" ? "Add Successor" : "Add Player";
    }
  }
  if (els.playerCardHost) els.playerCardHost.hidden = isReplaceOpen;
  if (els.playerCardActions) els.playerCardActions.hidden = isReplaceOpen;
  if (els.playerReplaceBtn) els.playerReplaceBtn.hidden = isReplaceOpen;
}

function playerReplacementScore(player, rawQuery, query) {
  const idText = String(player?.id || "");
  const name = toHiragana(player?.name || "");
  if (idText === rawQuery) return 0;
  if (name === query) return 1;
  if (idText.startsWith(rawQuery)) return 2;
  if (name.startsWith(query)) return 3;
  if (name.includes(query)) return 4;
  return 9;
}

function replacementCandidates(rawQuery) {
  const raw = String(rawQuery || "").trim();
  const query = toHiragana(raw);
  if (!raw || !query) return [];
  return players
    .filter((player) => {
      if (!player || player.retired) return false;
      const score = playerReplacementScore(player, raw, query);
      return score < 9;
    })
    .sort((a, b) => {
      const sa = playerReplacementScore(a, raw, query);
      const sb = playerReplacementScore(b, raw, query);
      if (sa !== sb) return sa - sb;
      const nameA = normalizedReplacementSearchText(a);
      const nameB = normalizedReplacementSearchText(b);
      if (nameA === nameB) {
        const ca = replacementCategoryRank(a);
        const cb = replacementCategoryRank(b);
        if (ca !== cb) return ca - cb;
      }
      return Number(b.id || 0) - Number(a.id || 0);
    })
    .slice(0, 12);
}

function renderPlayerReplaceResults() {
  if (!els.playerReplaceResults) return;
  replacementPlayerId = null;
  if (els.playerReplaceSeason) els.playerReplaceSeason.innerHTML = "";
  if (els.playerReplaceApply) els.playerReplaceApply.disabled = true;
  const list = replacementCandidates(els.playerReplaceSearch?.value || "");
  if (!list.length) {
    els.playerReplaceResults.innerHTML = `<div class="player-replace-empty">No candidates</div>`;
    return;
  }
  els.playerReplaceResults.innerHTML = list.map((player) => {
    const pos = (player.position || "-").toUpperCase();
    const posClass = positionClass(pos);
    const typeLabel = typeLabelByPlayer(player);
    const typeClass = typeClassByPlayer(player);
    return `
      <button type="button" class="player-replace-option" data-player-id="${player.id}">
        <span class="player-replace-thumb">
          <img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${escapeHtml(player.name)}" />
        </span>
        <span class="player-replace-meta">
          <span class="player-replace-name">${escapeHtml(player.name)}</span>
          <span class="player-replace-sub">
            <span class="badge pos-badge ${posClass}">${escapeHtml(pos)}</span>
            <span class="badge type-badge ${typeClass}">${escapeHtml(typeLabel)}</span>
            ID: ${player.id}
          </span>
        </span>
      </button>
    `;
  }).join("");
}

function selectReplacementPlayer(playerId) {
  const id = Number(playerId);
  const player = players.find((p) => Number(p?.id) === id);
  if (!player || !els.playerReplaceSeason) return;
  replacementPlayerId = id;
  if (IS_SIMULATION_MODE) {
    els.playerReplaceSeason.innerHTML = `<option value="">Peak</option>`;
    if (els.playerReplaceResults) {
      els.playerReplaceResults.querySelectorAll(".player-replace-option").forEach((btn) => {
        btn.classList.toggle("is-selected", Number(btn.dataset.playerId) === id);
      });
    }
    if (els.playerReplaceApply) els.playerReplaceApply.disabled = false;
    return;
  }
  const seasons = (Array.isArray(player.periods) ? player.periods : [])
    .map((p) => p?.season)
    .filter((s) => typeof s === "string" && s.length > 0);
  els.playerReplaceSeason.innerHTML = seasons
    .map((season) => `<option value="${escapeHtml(season)}">${escapeHtml(season)}</option>`)
    .join("");
  if (els.playerReplaceResults) {
    els.playerReplaceResults.querySelectorAll(".player-replace-option").forEach((btn) => {
      btn.classList.toggle("is-selected", Number(btn.dataset.playerId) === id);
    });
  }
  if (els.playerReplaceApply) els.playerReplaceApply.disabled = !seasons.length;
}

function openPlayerReplacePanel() {
  if (!Number.isInteger(selectedSlotIndex) || !els.playerReplacePanel) return;
  replacementPlayerId = null;
  els.playerReplacePanel.hidden = false;
  const isSuccessor = selectedPlayerMode === "successor";
  if (els.playerReplaceSourceWrap) els.playerReplaceSourceWrap.hidden = !isSuccessor;
  if (els.playerReplaceSourceType) els.playerReplaceSourceType.value = "self";
  if (els.playerReplaceSourceInput) els.playerReplaceSourceInput.value = "";
  syncPlayerReplaceSourceInput();
  if (els.playerReplaceApply) els.playerReplaceApply.disabled = true;
  if (els.playerReplaceSearch) {
    els.playerReplaceSearch.value = "";
    els.playerReplaceSearch.focus({ preventScroll: true });
  }
  if (els.playerReplaceResults) {
    els.playerReplaceResults.innerHTML = `<div class="player-replace-empty">Search player name or ID</div>`;
  }
  if (els.playerReplaceSeason) els.playerReplaceSeason.innerHTML = "";
  syncPlayerReplaceLayout();
}

async function applySelectedPlayerReplacement() {
  if (!Number.isInteger(selectedSlotIndex)) return;
  const idx = selectedSlotIndex;
  const entry = lineup[idx];
  const playerId = Number(replacementPlayerId);
  const season = IS_SIMULATION_MODE ? null : String(els.playerReplaceSeason?.value || "").trim();
  if (!Number.isInteger(playerId) || (!IS_SIMULATION_MODE && !season)) return;

  if (selectedPlayerMode === "successor") {
    if (!entry) return;
    const sourceType = els.playerReplaceSourceType?.value === "custom" ? "custom" : "self";
    const source = sourceType === "custom"
      ? String(els.playerReplaceSourceInput?.value || "").trim()
      : "自チーム";
    if (!source) return;
    lineup[idx] = {
      ...entry,
      successor: { playerId, season, source },
    };
  } else {
    const currentSuccessor = normalizeSuccessor(entry?.successor);
    lineup[idx] = { playerId, season, successor: IS_SIMULATION_MODE ? null : currentSuccessor };
  }

  saveLineupLocal();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup();
    } catch (e) {
      window.alert("クラウド保存に失敗しました。");
    }
  }
  renderLineup();
  selectedPlayerId = playerId;
  closePlayerReplacePanel();
  renderPlayerCardModal();
}

async function removeSelectedSuccessorFromTeam() {
  if (!Number.isInteger(selectedSlotIndex)) return;
  const idx = selectedSlotIndex;
  const entry = lineup[idx];
  if (!entry || !entry.successor) return;
  lineup[idx] = { ...entry, successor: null };
  saveLineupLocal();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup();
    } catch (e) {
      window.alert("クラウド保存に失敗しました。");
    }
  }
  renderLineup();
  closePlayerCardModal();
}

function coachReplacementScore(coach, rawQuery, query) {
  const idText = String(coach?.id || "");
  const name = toHiragana(coach?.name || "");
  if (idText === rawQuery) return 0;
  if (name === query) return 1;
  if (idText.startsWith(rawQuery)) return 2;
  if (name.startsWith(query)) return 3;
  if (name.includes(query)) return 4;
  return 9;
}

function coachReplacementCandidates(rawQuery) {
  const raw = String(rawQuery || "").trim();
  const query = toHiragana(raw);
  if (!raw || !query) return [];
  return (Array.isArray(coaches) ? coaches : [])
    .filter((coach) => {
      if (!coach) return false;
      const score = coachReplacementScore(coach, raw, query);
      return score < 9;
    })
    .sort((a, b) => {
      const sa = coachReplacementScore(a, raw, query);
      const sb = coachReplacementScore(b, raw, query);
      if (sa !== sb) return sa - sb;
      const nameOrder = String(a?.name || "").localeCompare(String(b?.name || ""), "ja");
      if (nameOrder !== 0) return nameOrder;
      return Number(a?.id || 0) - Number(b?.id || 0);
    })
    .slice(0, 12);
}

function coachSeasonOptions(coach) {
  const count = Math.max(1, Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason.length : 1);
  return Array.from({ length: count }, (_, i) => `${i + 1}期目`);
}

function renderCoachReplaceResults() {
  if (!els.coachReplaceResults) return;
  replacementCoachId = null;
  if (els.coachReplaceSeason) els.coachReplaceSeason.innerHTML = "";
  if (els.coachReplaceApply) els.coachReplaceApply.disabled = true;
  const list = coachReplacementCandidates(els.coachReplaceSearch?.value || "");
  if (!list.length) {
    els.coachReplaceResults.innerHTML = `<div class="player-replace-empty">No candidates</div>`;
    return;
  }
  els.coachReplaceResults.innerHTML = list.map((coach) => {
    const coachId = Number(coach?.id || 0);
    const typeLabel = coachTypeLabel(coach?.type);
    return `
      <button type="button" class="player-replace-option coach-replace-option" data-coach-id="${coachId}">
        <span class="player-replace-thumb coach-replace-thumb">
          <img loading="lazy" src="./images/chara/headcoaches/static/${coachId}@2x.gif" alt="${escapeHtml(coach?.name || `Coach ${coachId}`)}" />
        </span>
        <span class="player-replace-meta">
          <span class="player-replace-name">${escapeHtml(coach?.name || `Coach ${coachId}`)}</span>
          <span class="player-replace-sub">
            <span class="badge pos-badge hc-badge">HC</span>
            ${escapeHtml(typeLabel)} / ID: ${coachId}
          </span>
        </span>
      </button>
    `;
  }).join("");
}

function selectReplacementCoach(coachId) {
  const id = Number(coachId);
  const coach = (Array.isArray(coaches) ? coaches : []).find((c) => Number(c?.id) === id);
  if (!coach || !els.coachReplaceSeason) return;
  replacementCoachId = id;
  if (IS_SIMULATION_MODE) {
    els.coachReplaceSeason.innerHTML = `<option value="">Peak</option>`;
    if (els.coachReplaceResults) {
      els.coachReplaceResults.querySelectorAll(".coach-replace-option").forEach((btn) => {
        btn.classList.toggle("is-selected", Number(btn.dataset.coachId) === id);
      });
    }
    if (els.coachReplaceApply) els.coachReplaceApply.disabled = false;
    return;
  }
  const currentSeason = selectedCoach && Number(selectedCoach.coachId) === id
    ? coachSeasonLabel(selectedCoach.season || "1期目")
    : "1期目";
  const seasons = coachSeasonOptions(coach);
  els.coachReplaceSeason.innerHTML = seasons
    .map((season) => `<option value="${escapeHtml(season)}"${season === currentSeason ? " selected" : ""}>${escapeHtml(season)}</option>`)
    .join("");
  if (els.coachReplaceResults) {
    els.coachReplaceResults.querySelectorAll(".coach-replace-option").forEach((btn) => {
      btn.classList.toggle("is-selected", Number(btn.dataset.coachId) === id);
    });
  }
  if (els.coachReplaceApply) els.coachReplaceApply.disabled = !seasons.length;
}

function openCoachReplacePanel(mode = "replace") {
  if (!els.coachReplacePanel) return;
  replacementCoachId = null;
  els.coachReplacePanel.hidden = false;
  if (els.coachReplaceApply) {
    els.coachReplaceApply.textContent = mode === "add" ? "Add" : "Replace";
    els.coachReplaceApply.disabled = true;
  }
  if (els.coachReplaceSearch) {
    els.coachReplaceSearch.value = "";
    els.coachReplaceSearch.focus();
  }
  if (els.coachReplaceResults) {
    els.coachReplaceResults.innerHTML = `<div class="player-replace-empty">Search coach name or ID</div>`;
  }
  if (els.coachReplaceSeason) els.coachReplaceSeason.innerHTML = "";
}

function closeCoachReplacePanel() {
  replacementCoachId = null;
  if (els.coachReplacePanel) els.coachReplacePanel.hidden = true;
  if (els.coachReplaceSearch) els.coachReplaceSearch.value = "";
  if (els.coachReplaceResults) els.coachReplaceResults.innerHTML = "";
  if (els.coachReplaceSeason) els.coachReplaceSeason.innerHTML = "";
  if (els.coachReplaceApply) els.coachReplaceApply.disabled = true;
}

async function applySelectedCoachReplacement() {
  const coachId = Number(replacementCoachId);
  const season = IS_SIMULATION_MODE ? null : coachSeasonLabel(els.coachReplaceSeason?.value || "1期目");
  if (!Number.isInteger(coachId) || coachId <= 0) return;
  selectedCoach = { coachId, season };
  saveSelectedCoach();
  if (hasCloudConfig()) {
    try {
      await saveCloudFormationId();
    } catch (e) {
      window.alert("監督情報のクラウド保存に失敗しました。");
    }
  }
  renderCoachSection();
  renderLineup();
  closeCoachReplacePanel();
  renderCoachCardModal();
}

function renderCoachCardModal() {
  if (!els.coachCardHost) return;
  if (els.coachCardTitle) els.coachCardTitle.textContent = "Coach";
  if (els.coachReplaceBtn) {
    els.coachReplaceBtn.textContent = "Replace Coach";
    els.coachReplaceBtn.hidden = false;
  }
  if (!selectedCoach || !Number.isInteger(Number(selectedCoach.coachId))) {
    els.coachCardHost.innerHTML = `<p class="dim">Coach not registered.</p>`;
    return;
  }
  const coachId = Number(selectedCoach.coachId);
  const coach = (Array.isArray(coaches) ? coaches : []).find((c) => Number(c?.id) === coachId);
  if (!coach) {
    els.coachCardHost.innerHTML = `<p class="dim">Coach data not found.</p>`;
    return;
  }
  const staticImg = `./images/chara/headcoaches/static/${coachId}@2x.gif`;
  const actionImg = `./images/chara/headcoaches/action/${coachId}@2x.gif`;
  const typeLabel = coachTypeLabel(coach?.type);
  const season = coachSeasonLabel(selectedCoach?.season || "1期目");
  const seasonNum = coachSeasonNumber(season);
  const leadership = Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason : [];
  const obtainable = Array.isArray(coach?.obtainable) ? coach.obtainable : [];
  const depth4 = Array.isArray(coach?.depth4FormationIds) ? coach.depth4FormationIds : (Array.isArray(coach?.formationDepth4) ? coach.formationDepth4 : []);
  const nationText = String(coach?.nationality || "").trim() || nationNameFromId(coach?.nationId);
  const tab = coachCardTabMode;
  const tabPanelHtml =
    tab === "obtain"
      ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Available Formation</div><div class="coach-formation-list">${coachFormationPills(obtainable, true)}</div></div>`
      : tab === "understood"
        ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Understood Formation</div><div class="coach-formation-list">${coachFormationPills(depth4, false)}</div></div>`
        : `<div class="coach-tab-panel coach-tab-scroll coach-tab-panel-lead"><div class="profile-description-title">Leadership</div>${coachLeadershipBlocksHtml(leadership, seasonNum)}</div>`;
  els.coachCardHost.innerHTML = `
    <article class="coach-card coach-card-fixed coach-card-myteam-modal" data-coach-id="${coachId}">
      <div class="coach-card-top">
        <h3 class="card-name"><span class="badge pos-badge hc-badge">HC</span><span>${coach?.name || `Coach ${coachId}`}</span></h3>
      </div>
      <div class="coach-card-body">
        <div class="thumbs coach-thumbs">
          <img loading="lazy" src="${staticImg}" alt="${coach?.name || `Coach ${coachId}`}" onerror="this.src='${actionImg}'" />
          <img loading="lazy" src="${actionImg}" alt="${coach?.name || `Coach ${coachId}`}" onerror="this.src='${staticImg}'" />
        </div>
        <div class="profile-side coach-profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nationText}</span></div>
          <div class="profile-item"><span class="k">年齢</span><span class="v">${coach?.age || "-"}</span></div>
          <div class="profile-item"><span class="k">タイプ</span><span class="v">${typeLabel}</span></div>
        </div>
      </div>
      ${tabPanelHtml}
      <div class="card-tabs">
        <button type="button" class="card-tab ${tab === "lead" ? "is-active" : ""}" data-coach-tab="lead">LEAD</button>
        <button type="button" class="card-tab ${tab === "obtain" ? "is-active" : ""}" data-coach-tab="obtain">AVL</button>
        <button type="button" class="card-tab ${tab === "understood" ? "is-active" : ""}" data-coach-tab="understood">UND</button>
      </div>
    </article>
  `;
}

function openCoachCardModal() {
  coachCardTabMode = "lead";
  renderCoachCardModal();
  if (els.coachCardModal) els.coachCardModal.hidden = false;
}

function openEmptyCoachCardModal() {
  if (!els.coachCardModal || !els.coachCardHost) return;
  coachCardTabMode = "lead";
  if (els.coachCardTitle) els.coachCardTitle.textContent = "Add Coach";
  els.coachCardHost.innerHTML = `
    <div class="player-replace-empty-slot">
      <div class="lineup-empty-thumb"></div>
      <div>
        <div class="player-replace-empty-title">未登録</div>
        <div class="player-replace-empty-text">${IS_SIMULATION_MODE ? "検索して監督を選択してください。" : "検索して監督と期を選択してください。"}</div>
      </div>
    </div>
  `;
  if (els.coachReplaceBtn) els.coachReplaceBtn.hidden = true;
  els.coachCardModal.hidden = false;
  openCoachReplacePanel("add");
}

function closeCoachCardModal() {
  closeCoachReplacePanel();
  if (els.coachCardModal) els.coachCardModal.hidden = true;
  if (els.coachReplaceBtn) els.coachReplaceBtn.hidden = false;
}

async function init() {
  setupModalScrollLock();
  loadCloudConfig();
  syncMenuButtonSize();
  window.addEventListener("resize", syncMenuButtonSize);
  loadLifecycleMode();
  loadSelectedFormationId();
  loadSelectedCoach();
  renderLifecycleControls();
  if (els.myteamMenuButton) {
    els.myteamMenuButton.addEventListener("click", () => {
      if (!els.myteamMenuPanel) return;
      els.myteamMenuPanel.classList.toggle("is-open");
    });
  }
  if (els.myteamDatabaseButton) {
    els.myteamDatabaseButton.addEventListener("click", () => {
      window.location.href = "./index.html";
    });
  }
  if (els.myteamCoachesButton) {
    els.myteamCoachesButton.addEventListener("click", () => {
      window.location.href = "./coaches.html";
    });
  }
  if (els.myteamFormationsButton) {
    els.myteamFormationsButton.addEventListener("click", () => {
      window.location.href = "./formations.html";
    });
  }
  if (els.myteamCollectionsButton) {
    els.myteamCollectionsButton.addEventListener("click", () => {
      window.location.href = "./collections.html";
    });
  }
  if (els.myteamCurrentButton) {
    els.myteamCurrentButton.addEventListener("click", () => {
      if (!IS_SIMULATION_MODE) {
        closeMenuPanel();
        return;
      }
      window.location.href = "./myteam.html";
    });
  }
  if (els.myteamSimulationButton) {
    els.myteamSimulationButton.addEventListener("click", () => {
      window.location.href = "./simulation.html";
    });
  }
  if (els.myteamLoginButton) {
    els.myteamLoginButton.addEventListener("click", async () => {
      await loginTeamIdFromMyTeam();
    });
  }
  if (els.myteamLogoutButton) {
    els.myteamLogoutButton.addEventListener("click", () => {
      logoutTeamId();
      window.location.href = "./index.html";
    });
  }
  if (els.lifecycleToggle) {
    els.lifecycleToggle.addEventListener("click", () => {
      lifecycleModeEnabled = !lifecycleModeEnabled;
      saveLifecycleMode();
      renderLifecycleControls();
      renderLineup();
    });
  }
  if (els.advanceSeasonButton) {
    els.advanceSeasonButton.addEventListener("click", async () => {
      const ok = window.confirm("全選手の現在期を1期進めます。よろしいですか？\n（-1ボタンで1期戻せます）");
      if (!ok) return;
      await shiftAllLineupSeasons(1);
    });
  }
  if (els.rewindSeasonButton) {
    els.rewindSeasonButton.addEventListener("click", async () => {
      const confirmText = hasAnyFirstSeasonPlayers()
        ? "1期目の選手が登録されています。\n1期目以外の選手のみ変更が反映されますが、よろしいですか？"
        : "全選手の現在期を1期戻します。よろしいですか？";
      const ok = window.confirm(confirmText);
      if (!ok) return;
      await shiftAllLineupSeasons(-1);
    });
  }
  if (els.myTeamFormationSelect) {
    els.myTeamFormationSelect.addEventListener("change", () => {
      // Keep this for keyboard users. Final apply is via Apply button.
      if (!isFormationEditorOpen) return;
      renderFormationCurrent();
    });
  }
  if (els.myTeamFormationApply) {
    els.myTeamFormationApply.addEventListener("click", async () => {
      await applyFormationFromSelect();
    });
  }
  if (els.myTeamFormationCancel) {
    els.myTeamFormationCancel.addEventListener("click", () => {
      closeFormationEditor();
    });
  }
  if (els.myTeamFormationBackdrop) {
    els.myTeamFormationBackdrop.addEventListener("click", () => {
      closeFormationEditor();
    });
  }
  if (els.myTeamFormationWrap) {
    els.myTeamFormationWrap.addEventListener("click", (e) => {
      if (e.target.closest("[data-formation-change]")) {
        openFormationEditor();
        return;
      }
      if (e.target.closest("[data-formation-open]")) {
        openSelectedFormationDetail();
      }
    });
  }
  if (els.myTeamCoachWrap) {
    els.myTeamCoachWrap.addEventListener("click", handleMyTeamCoachClick);
  }
  if (els.myTeamIndexWrap) {
    els.myTeamIndexWrap.addEventListener("click", (e) => {
      if (!e.target.closest("[data-tpi-info]")) return;
      openTpiInfoModal();
    });
  }
  document.addEventListener("click", (e) => {
    if (!els.myteamMenuPanel || !els.myteamMenuButton) return;
    if (!els.myteamMenuPanel.classList.contains("is-open")) return;
    if (e.target.closest("#myteamMenuButton") || e.target.closest("#myteamMenuPanel")) return;
    closeMenuPanel();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeMenuPanel();
      closeLoginModal();
      closeSignupModal();
      closeFormationEditor();
      closeEmptySlotModal();
      closePlayerCardModal();
      closeCoachCardModal();
      closeMyteamSettingModal();
      closeTpiInfoModal();
    }
  });

  if (els.emptySlotBackdrop) els.emptySlotBackdrop.addEventListener("click", closeEmptySlotModal);
  if (els.emptySlotClose) els.emptySlotClose.addEventListener("click", closeEmptySlotModal);
  if (els.emptySlotOk) {
    els.emptySlotOk.addEventListener("click", () => {
      window.location.href = "./index.html";
    });
  }

  if (els.playerCardBackdrop) els.playerCardBackdrop.addEventListener("click", closePlayerCardModal);
  if (els.playerCardClose) els.playerCardClose.addEventListener("click", closePlayerCardModal);
  if (els.playerReplaceBtn) {
    els.playerReplaceBtn.addEventListener("click", (e) => {
      e.preventDefault();
      openPlayerReplacePanel();
    });
  }
  if (els.playerRemoveSuccessorBtn) {
    els.playerRemoveSuccessorBtn.addEventListener("click", async () => {
      const ok = window.confirm("この後継選手を解除します。よろしいですか？");
      if (!ok) return;
      await removeSelectedSuccessorFromTeam();
    });
  }
  if (els.playerReplaceSearch) {
    els.playerReplaceSearch.addEventListener("input", renderPlayerReplaceResults);
    els.playerReplaceSearch.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const first = els.playerReplaceResults?.querySelector(".player-replace-option");
      if (!first) return;
      e.preventDefault();
      selectReplacementPlayer(first.dataset.playerId);
    });
  }
  if (els.playerReplaceSourceType) {
    els.playerReplaceSourceType.addEventListener("change", syncPlayerReplaceSourceInput);
  }
  if (els.playerReplaceResults) {
    els.playerReplaceResults.addEventListener("click", (e) => {
      const btn = e.target.closest(".player-replace-option");
      if (!btn) return;
      selectReplacementPlayer(btn.dataset.playerId);
    });
  }
  if (els.playerReplaceCancel) {
    els.playerReplaceCancel.addEventListener("click", closePlayerReplacePanel);
  }
  if (els.playerReplaceApply) {
    els.playerReplaceApply.addEventListener("click", applySelectedPlayerReplacement);
  }
  if (els.playerCardHost) {
    els.playerCardHost.addEventListener("click", (e) => {
      const tabBtn = e.target.closest(".card-tab");
      if (!tabBtn) return;
      const id = Number(tabBtn.dataset.playerId);
      const mode = Number(tabBtn.dataset.mode);
      if (!Number.isInteger(id)) return;
      if (!Number.isInteger(mode) || mode < 0 || mode > 2) return;
      cardViewModeById.set(id, mode);
      renderPlayerCardModal();
    });
  }
  if (els.coachCardBackdrop) els.coachCardBackdrop.addEventListener("click", closeCoachCardModal);
  if (els.coachCardClose) els.coachCardClose.addEventListener("click", closeCoachCardModal);
  if (els.coachReplaceBtn) {
    els.coachReplaceBtn.addEventListener("click", () => {
      openCoachReplacePanel();
    });
  }
  if (els.coachReplaceSearch) {
    els.coachReplaceSearch.addEventListener("input", renderCoachReplaceResults);
    els.coachReplaceSearch.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const first = els.coachReplaceResults?.querySelector(".coach-replace-option");
      if (!first) return;
      e.preventDefault();
      selectReplacementCoach(first.dataset.coachId);
    });
  }
  if (els.coachReplaceResults) {
    els.coachReplaceResults.addEventListener("click", (e) => {
      const btn = e.target.closest(".coach-replace-option");
      if (!btn) return;
      selectReplacementCoach(btn.dataset.coachId);
    });
  }
  if (els.coachReplaceCancel) {
    els.coachReplaceCancel.addEventListener("click", closeCoachReplacePanel);
  }
  if (els.coachReplaceApply) {
    els.coachReplaceApply.addEventListener("click", applySelectedCoachReplacement);
  }
  if (els.coachCardHost) {
    els.coachCardHost.addEventListener("click", (e) => {
      const tabBtn = e.target.closest("[data-coach-tab]");
      if (tabBtn) {
        const tab = String(tabBtn.dataset.coachTab || "");
        if (tab === "lead" || tab === "obtain" || tab === "understood") {
          coachCardTabMode = tab;
          renderCoachCardModal();
        }
        return;
      }
      const formationBtn = e.target.closest("[data-formation-id]");
      if (!formationBtn) return;
      const fid = Number(formationBtn.dataset.formationId);
      if (!Number.isInteger(fid) || fid <= 0) return;
      const url = new URL("./formations.html", window.location.href);
      url.searchParams.set("openFormationId", String(fid));
      url.searchParams.set("returnTo", IS_SIMULATION_MODE ? "simulation" : "myteam");
      window.location.href = url.toString();
    });
  }

  if (els.loginBackdrop) els.loginBackdrop.addEventListener("click", closeLoginModal);
  if (els.loginClose) els.loginClose.addEventListener("click", closeLoginModal);
  if (els.loginApply) {
    els.loginApply.addEventListener("click", async () => {
      await applyLoginFromModal();
    });
  }
  if (els.signupOpen) {
    els.signupOpen.addEventListener("click", () => {
      closeLoginModal();
      openSignupModal();
    });
  }
  if (els.signupBackdrop) els.signupBackdrop.addEventListener("click", closeSignupModal);
  if (els.signupClose) els.signupClose.addEventListener("click", closeSignupModal);
  if (els.signupCancel) els.signupCancel.addEventListener("click", closeSignupModal);
  if (els.signupApply) {
    els.signupApply.addEventListener("click", async () => {
      await applySignupFromModal();
    });
  }

  if (els.myteamSettingBackdrop) {
    els.myteamSettingBackdrop.addEventListener("click", closeMyteamSettingModal);
  }
  if (els.myteamSettingClose) {
    els.myteamSettingClose.addEventListener("click", closeMyteamSettingModal);
  }
  if (els.tpiInfoBackdrop) {
    els.tpiInfoBackdrop.addEventListener("click", closeTpiInfoModal);
  }
  if (els.tpiInfoClose) {
    els.tpiInfoClose.addEventListener("click", closeTpiInfoModal);
  }
  if (els.simulationCopyButton) {
    els.simulationCopyButton.addEventListener("click", copyMyTeamStateToSimulation);
  }
  if (els.myteamRenameIdApply) {
    els.myteamRenameIdApply.addEventListener("click", async () => {
      const oldKey = String(cloudConfig.lineupKey || "").trim();
      const newKey = String(els.myteamRenameLineupKey?.value || "").trim();
      if (!oldKey || !newKey) return;
      if (oldKey === newKey) {
        closeMyteamSettingModal();
        return;
      }
      cloudConfig.lineupKey = newKey;
      localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
      try {
        const exists = await cloudLineupExists(newKey);
        if (exists) {
          window.alert("そのIDは既に使われています。別のIDを入力してください。");
          cloudConfig.lineupKey = oldKey;
          localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
          renderMyTeamMeta();
          return;
        }
        lineup = normalizeLineupArray(lineup);
        await saveCloudLineup();
        await saveCloudFormationId();
        await cloudDeleteLineupById(oldKey);
        await cloudDeleteLineupById(formationMetaId(oldKey), false);
        saveLineupLocal();
        renderMyTeamMeta();
        closeMyteamSettingModal();
      } catch (e) {
        cloudConfig.lineupKey = oldKey;
        localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
        renderMyTeamMeta();
        const msg = e?.message === "delete_not_applied"
          ? "ID名の変更後に旧ID削除ができませんでした。SupabaseのDelete権限を確認してください。"
          : "ID名の変更に失敗しました。";
        window.alert(msg);
      }
    });
  }
  if (els.myteamDeleteIdApply) {
    els.myteamDeleteIdApply.addEventListener("click", async () => {
      const key = String(cloudConfig.lineupKey || "").trim();
      if (!key) return;
      const ok = window.confirm("このIDを削除します。よろしいですか？");
      if (!ok) return;
      try {
        await cloudDeleteLineupById(key);
        await cloudDeleteLineupById(formationMetaId(key), false);
        lineup = Array.from({ length: LINEUP_SIZE }, () => null);
        saveLineupLocal();
        logoutTeamId();
        renderMyTeamMeta();
        closeMyteamSettingModal();
        window.location.href = "./index.html";
      } catch (e) {
        const msg = e?.message === "delete_not_applied"
          ? "IDの削除に失敗しました。SupabaseのDelete権限を確認してください。"
          : "IDの削除に失敗しました。";
        window.alert(msg);
      }
    });
  }

  loadSiteMeta();
  const [dataRes, formationsRes, coachesMetaRes, v4CleanUniformRes, rohmRes, ccRangeRes] = await Promise.all([
    fetchWithTimeout("./data.json?v=20260517-cc2625"),
    fetchWithTimeout("./formations_data.json?v=20260517-cc2625").catch(() => null),
    fetchWithTimeout("./coaches_data.json?v=20260517-cc2625").catch(() => null),
    fetchWithTimeout("./v4_clean_uniform_data.json?v=20260517-cc2625").catch(() => null),
    fetchWithTimeout(ROHM_SLOT_DATA_URL).catch(() => null),
    fetchWithTimeout("./cc_range_data.json?v=20260517-cc2625").catch(() => null),
  ]);
  const data = await dataRes.json();
  players = data.players || [];
  rebuildMyTeamPlayerIndex();
  syncProfileSideWidthFromPlayers(players);
  if (formationsRes && formationsRes.ok) {
    const formationsData = await formationsRes.json();
    formations = Array.isArray(formationsData?.formations) ? formationsData.formations : [];
    const baseCoaches = Array.isArray(formationsData?.coaches) ? formationsData.coaches : [];
    let enriched = [];
    if (coachesMetaRes && coachesMetaRes.ok) {
      try {
        const raw = await coachesMetaRes.json();
        enriched = Array.isArray(raw?.coaches) ? raw.coaches : [];
      } catch (_) {
        enriched = [];
      }
    }
    const byId = new Map(enriched.map((c) => [Number(c?.id), c]));
    coaches = baseCoaches.map((c) => {
      const ext = byId.get(Number(c?.id));
      return {
        ...c,
        name: String(ext?.name || c?.name || "").trim() || c?.name || "",
        nationality: String(ext?.nationality || "").trim(),
        age: ext?.age != null ? ext.age : c?.age,
        type: ext?.type != null ? ext.type : c?.type,
        leadershipBySeason: Array.isArray(ext?.leadershipBySeason) ? ext.leadershipBySeason : [],
        obtainable: Array.isArray(ext?.obtainable) ? ext.obtainable : [],
        depth4FormationIds: Array.isArray(ext?.depth4FormationIds) ? ext.depth4FormationIds : (Array.isArray(c?.formationDepth4) ? c.formationDepth4 : []),
      };
    });
  } else {
    formations = [];
    coaches = [];
  }
  if (v4CleanUniformRes && v4CleanUniformRes.ok) {
    try {
      const raw = await v4CleanUniformRes.json();
      v4CleanUniformData = {
        meta: raw?.meta || {},
        formationPower: raw?.formationPower || {},
        coachPower: raw?.coachPower || {},
        formationSlotExpectedPts: raw?.formationSlotExpectedPts || {},
        globalAvg: raw?.globalAvg,
        weights: raw?.weights || {},
        metrics: raw?.metrics || {},
        diagnostics: raw?.diagnostics || {},
      };
    } catch (_) {
      v4CleanUniformData = { meta: {}, formationPower: {}, coachPower: {}, formationSlotExpectedPts: {}, weights: {} };
    }
  }
  if (ccRangeRes && ccRangeRes.ok) {
    try {
      const raw = await ccRangeRes.json();
      ccRangeData = {
        rows: Array.isArray(raw?.rows) ? raw.rows : [],
        skippedFinals: Number(raw?.skippedFinals || 0),
      };
    } catch (_) {
      ccRangeData = { rows: [], skippedFinals: 0 };
    }
  }
  renderTpiInfoBenchmark();
  const rohmData = rohmRes && rohmRes.ok ? await rohmRes.json().catch(() => ({})) : {};
  v4PointContext = buildV4PointContext(rohmData);
  buildFormationOptions();
  closeFormationEditor();
  renderFormationCurrent();

  if (IS_SIMULATION_MODE) {
    await loadSimulationStateForCurrentId();
    buildFormationOptions();
    closeFormationEditor();
    renderFormationCurrent();
    renderMyTeamMeta();
    if (els.myTeamTarget) els.myTeamTarget.textContent = "Simulation";
    renderLineup();
    if (els.myTeamSlots) {
      els.myTeamSlots.addEventListener("click", handleMyTeamSlotClick);
    }
    if (els.myTeamReserveSlots) {
      els.myTeamReserveSlots.addEventListener("click", handleMyTeamSlotClick);
    }
    return;
  }

  if (!hasCloudConfig()) {
    if (els.myTeamTarget) els.myTeamTarget.textContent = "TeamIDが未設定です（先にLoginしてください）";
    renderMyTeamMeta();
    renderLineup();
    return;
  }

  renderMyTeamMeta();
  if (els.myTeamTarget) els.myTeamTarget.textContent = "";
  try {
    await loadCloudLineup();
    await loadCloudFormationId();
  } catch (e) {
    if (els.myTeamTarget) els.myTeamTarget.textContent = "クラウド読込に失敗しました";
  }
  renderLineup();

  if (els.myTeamSlots) {
    els.myTeamSlots.addEventListener("click", handleMyTeamSlotClick);
  }
  if (els.myTeamReserveSlots) {
    els.myTeamReserveSlots.addEventListener("click", handleMyTeamSlotClick);
  }
}

init().catch((e) => {
  if (els.myTeamTarget) els.myTeamTarget.textContent = "データ読み込みに失敗しました";
  console.error(e);
});
