const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const LINEUP_STORAGE_KEY = "ws_starting_eleven_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-26 00:30 JST";
const LINEUP_SIZE = 11;
const LIFECYCLE_MODE_STORAGE_KEY = "ws_lifecycle_mode_v1";
const MYTEAM_FORMATION_STORAGE_KEY = "ws_myteam_formation_v1";
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

const els = {
  myteamMenuButton: document.querySelector("#myteamMenuButton"),
  myteamMenuPanel: document.querySelector("#myteamMenuPanel"),
  myteamDatabaseButton: document.querySelector("#myteamDatabaseButton"),
  myteamCoachesButton: document.querySelector("#myteamCoachesButton"),
  myteamFormationsButton: document.querySelector("#myteamFormationsButton"),
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
  myTeamSlots: document.querySelector("#myTeamSlots"),
  myTeamCoachWrap: document.querySelector("#myTeamCoachWrap"),
  lifecycleToggle: document.querySelector("#lifecycleToggle"),
  advanceSeasonButton: document.querySelector("#advanceSeasonButton"),
  rewindSeasonButton: document.querySelector("#rewindSeasonButton"),
  myTeamFormationCurrent: document.querySelector("#myTeamFormationCurrent"),
  myTeamFormationChangeButton: document.querySelector("#myTeamFormationChangeButton"),
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
  playerCardClose: document.querySelector("#playerCardClose"),
  playerCardHost: document.querySelector("#playerCardHost"),
  playerDeleteBtn: document.querySelector("#playerDeleteBtn"),
  coachCardModal: document.querySelector("#coachCardModal"),
  coachCardBackdrop: document.querySelector("#coachCardBackdrop"),
  coachCardClose: document.querySelector("#coachCardClose"),
  coachCardHost: document.querySelector("#coachCardHost"),
  coachDeleteBtn: document.querySelector("#coachDeleteBtn"),
  myteamSettingModal: document.querySelector("#myteamSettingModal"),
  myteamSettingBackdrop: document.querySelector("#myteamSettingBackdrop"),
  myteamSettingClose: document.querySelector("#myteamSettingClose"),
  myteamRenameLineupKey: document.querySelector("#myteamRenameLineupKey"),
  myteamRenameIdApply: document.querySelector("#myteamRenameIdApply"),
  myteamDeleteIdApply: document.querySelector("#myteamDeleteIdApply"),
};

let players = [];
let lineup = Array.from({ length: LINEUP_SIZE }, () => null);
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let selectedSlotIndex = null;
let selectedPlayerId = null;
let selectedPlayerMode = "starter";
let lifecycleModeEnabled = false;
const cardViewModeById = new Map();
let formations = [];
let coaches = [];
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
  const key = cloudConfig?.lineupKey ? `${MYTEAM_FORMATION_STORAGE_KEY}:${cloudConfig.lineupKey}` : MYTEAM_FORMATION_STORAGE_KEY;
  const raw = String(localStorage.getItem(key) || "").trim();
  selectedFormationId = normalizeFormationId(raw);
}

function saveSelectedFormationId() {
  const key = cloudConfig?.lineupKey ? `${MYTEAM_FORMATION_STORAGE_KEY}:${cloudConfig.lineupKey}` : MYTEAM_FORMATION_STORAGE_KEY;
  if (Number.isInteger(selectedFormationId) && selectedFormationId > 0) {
    localStorage.setItem(key, String(selectedFormationId));
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

function renderFormationCurrent() {
  if (!els.myTeamFormationCurrent) return;
  if (!Number.isInteger(selectedFormationId) || selectedFormationId <= 0) {
    els.myTeamFormationCurrent.textContent = "Not selected";
    return;
  }
  const f = formations.find((x) => Number(x?.id) === selectedFormationId);
  if (!f) {
    els.myTeamFormationCurrent.textContent = "Not selected";
    return;
  }
  const year = formatFormationYearLabel(f?.year, f?.stride);
  els.myTeamFormationCurrent.textContent = `${f?.name || `Formation ${selectedFormationId}`}${year ? ` ${year}` : ""}`;
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
  url.searchParams.set("returnTo", "myteam");
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

function getSelectedFormationKeySlots() {
  const fid = Number(selectedFormationId);
  if (!Number.isInteger(fid) || fid <= 0) return new Set();
  const formation = formations.find((f) => Number(f?.id) === fid);
  const rows = Array.isArray(formation?.keyPositions) ? formation.keyPositions : [];
  const set = new Set();
  rows.forEach((r) => {
    const slot = Number(r?.slot);
    if (Number.isInteger(slot) && slot >= 1 && slot <= LINEUP_SIZE) set.add(slot);
  });
  return set;
}

function closeMenuPanel() {
  if (!els.myteamMenuPanel) return;
  els.myteamMenuPanel.classList.remove("is-open");
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
  localStorage.setItem(LINEUP_STORAGE_KEY, JSON.stringify(lineup));
}

function loadLifecycleMode() {
  lifecycleModeEnabled = localStorage.getItem(LIFECYCLE_MODE_STORAGE_KEY) === "1";
}

function saveLifecycleMode() {
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
  const login = hasCloudConfig()
    ? ` / <span class="meta-login-badge">Login：${cloudConfig.lineupKey}</span>`
    : "";
  els.myTeamMeta.innerHTML = `Updated: ${APP_UPDATED_AT_JST}${login}`;
  if (els.myteamLoginButton) els.myteamLoginButton.hidden = hasCloudConfig();
  if (els.myteamLogoutButton) els.myteamLogoutButton.hidden = !hasCloudConfig();
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

async function loadCloudLineup() {
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${cloudConfig.lineupKey}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  if (!Array.isArray(rows) || !rows.length) {
    selectedCoach = null;
    return false;
  }
  const remote = rows[0]?.lineup_json;
  if (!Array.isArray(remote)) return false;
  lineup = normalizeLineupArray(remote);
  saveLineupLocal();
  return true;
}

async function loadCloudFormationId() {
  const metaId = formationMetaId();
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

async function saveCloudLineup() {
  const payload = {
    lineup_id: cloudConfig.lineupKey,
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

async function saveCloudFormationId() {
  const metaId = formationMetaId();
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

function renderLineup() {
  if (!els.myTeamSlots) return;
  const keySlots = getSelectedFormationKeySlots();
  const html = lineup.map((entry, idx) => {
    const slot = idx + 1;
    const playerId = Number(entry?.playerId);
    const player = Number.isInteger(playerId) ? players.find((x) => x.id === playerId) : null;
    const name = player ? player.name : "未登録";
    const season = player ? (entry?.season || null) : null;
    const seasonText = season ? `${season}目` : "-";
    const remaining = player ? getRemainingPeakPeriods(player, season) : 0;
    const seasonBadge = lifecycleModeEnabled
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
    const ccStatInfo = (player && Number.isInteger(selectedFormationId))
      ? findCcSlotStat(selectedFormationId, slot, player.id)
      : null;
    const ccStatText = Number.isInteger(selectedFormationId)
      ? (ccStatInfo?.row
        ? `${ccStatInfo.byName ? `(${ccStatInfo.refCategory || "-"}) ` : ""}${pct(ccStatInfo.row.usageRate)} / ${avg(ccStatInfo.row.avgPts)}`
        : "- / -")
      : "";
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
        <span class="slot-no">${slot}${keyStar}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              <span class="badge type-badge ${typeClass}">${typeLabel}</span>
              ${seasonBadge}
            </div>
            <span class="slot-name">${name}</span>
            ${ccStatText ? `<span class="lineup-cc-stat">${ccStatText}</span>` : ""}
          </div>
          ${rightPaneHtml}
        </div>
      </button>
    `;
  }).join("");
  els.myTeamSlots.innerHTML = html;
  renderCoachSection();
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
  els.myTeamCoachWrap.innerHTML = `
    <button type="button" class="lineup-slot myteam-slot myteam-coach-slot has-player" id="myTeamCoachSlot">
      <span class="slot-no">HC</span>
      <div class="lineup-slot-main">
        <div class="lineup-thumb-wrap"><img loading="lazy" src="${img}" alt="${name}" /></div>
        <div class="lineup-player-meta">
          <div class="lineup-badges">
            <span class="badge pos-badge hc-badge">HC</span>
            <span class="badge lineup-season coach-season-badge">${season}</span>
          </div>
          <span class="slot-name">${name}</span>
          <span class="lineup-cc-stat">${typeLabel}</span>
        </div>
      </div>
      <div class="lineup-coach-lead-wrap">
        ${coachLeadershipTableHtml(leadership, seasonNum, 5)}
      </div>
    </button>
  `;
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
  els.playerCardHost.innerHTML = playerCardHtml(player, season);
  if (els.playerDeleteBtn) {
    els.playerDeleteBtn.textContent = selectedPlayerMode === "successor" ? "Remove Successor" : "Delete from Team";
    els.playerDeleteBtn.hidden = false;
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

function closePlayerCardModal() {
  selectedSlotIndex = null;
  selectedPlayerId = null;
  selectedPlayerMode = "starter";
  if (els.playerCardModal) els.playerCardModal.hidden = true;
  if (els.playerDeleteBtn) els.playerDeleteBtn.hidden = true;
}

async function removeSelectedPlayerFromTeam() {
  if (!Number.isInteger(selectedSlotIndex)) return;
  const idx = selectedSlotIndex;
  const entry = lineup[idx];
  if (!entry) return;

  if (selectedPlayerMode === "successor") {
    lineup[idx] = { ...entry, successor: null };
  } else {
    lineup[idx] = null;
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
  closePlayerCardModal();
}

function renderCoachCardModal() {
  if (!els.coachCardHost) return;
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

function closeCoachCardModal() {
  if (els.coachCardModal) els.coachCardModal.hidden = true;
}

async function removeCoachFromTeam() {
  selectedCoach = null;
  if (hasCloudConfig()) {
    try {
      await saveCloudFormationId();
    } catch (e) {
      window.alert("監督情報のクラウド保存に失敗しました。");
      return;
    }
  }
  renderCoachSection();
  closeCoachCardModal();
}

async function init() {
  setupModalScrollLock();
  loadCloudConfig();
  loadLifecycleMode();
  loadSelectedFormationId();
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
  if (els.myTeamFormationChangeButton) {
    els.myTeamFormationChangeButton.addEventListener("click", () => {
      openFormationEditor();
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
  if (els.myTeamFormationCurrent) {
    els.myTeamFormationCurrent.addEventListener("click", () => {
      openSelectedFormationDetail();
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
  if (els.playerDeleteBtn) {
    els.playerDeleteBtn.addEventListener("click", async () => {
      const msg = selectedPlayerMode === "successor"
        ? "この後継選手を解除します。よろしいですか？"
        : "この選手をチームから外します。よろしいですか？";
      const ok = window.confirm(msg);
      if (!ok) return;
      await removeSelectedPlayerFromTeam();
    });
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
  if (els.coachDeleteBtn) {
    els.coachDeleteBtn.addEventListener("click", async () => {
      const ok = window.confirm("この監督をチームから外します。よろしいですか？");
      if (!ok) return;
      await removeCoachFromTeam();
    });
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
      url.searchParams.set("returnTo", "myteam");
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

  const [dataRes, formationsRes, coachesMetaRes] = await Promise.all([
    fetch("./data.json"),
    fetch("./formations_data.json").catch(() => null),
    fetch("./coaches_data.json").catch(() => null),
  ]);
  const data = await dataRes.json();
  players = data.players || [];
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
  buildFormationOptions();
  closeFormationEditor();
  renderFormationCurrent();

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
    els.myTeamSlots.addEventListener("click", (e) => {
      const slot = e.target.closest(".myteam-slot");
      if (!slot) return;
      const idx = Number(slot.dataset.slotIndex);
      if (!Number.isInteger(idx)) return;
      const entry = lineup[idx];
      const clickedSuccessor = lifecycleModeEnabled && !!e.target.closest(".lineup-successor");
      if (clickedSuccessor) {
        const successorId = Number(entry?.successor?.playerId);
        if (!Number.isInteger(successorId)) {
          openEmptySlotModal();
          return;
        }
        openPlayerCardModal(idx, "successor");
        return;
      }
      const playerId = Number(entry?.playerId);
      if (!Number.isInteger(playerId)) {
        openEmptySlotModal();
        return;
      }
      openPlayerCardModal(idx);
    });
  }
  if (els.myTeamCoachWrap) {
    els.myTeamCoachWrap.addEventListener("click", () => {
      if (!selectedCoach || !Number.isInteger(Number(selectedCoach.coachId))) {
        window.alert("CoachesからAddボタンで監督を登録してください。");
        window.location.href = "./coaches.html";
        return;
      }
      openCoachCardModal();
    });
  }
}

init().catch((e) => {
  if (els.myTeamTarget) els.myTeamTarget.textContent = "データ読み込みに失敗しました";
  console.error(e);
});
