const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-26 20:13 JST";

const TYPE_LABELS = {
  1: "超攻撃型",
  2: "攻撃型",
  3: "バランス型",
  4: "守備型",
  5: "超守備型",
};

const els = {
  hero: document.querySelector(".hero"),
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  playersButton: document.querySelector("#playersButton"),
  coachesButton: document.querySelector("#coachesButton"),
  formationsButton: document.querySelector("#formationsButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  coachNameQuery: document.querySelector("#coachNameQuery"),
  coachNameSuggest: document.querySelector("#coachNameSuggest"),
  coachTypeFilter: document.querySelector("#coachTypeFilter"),
  coachAvailableFormationFilter: document.querySelector("#coachAvailableFormationFilter"),
  coachUnderstoodFormationFilter: document.querySelector("#coachUnderstoodFormationFilter"),
  coachCount: document.querySelector("#coachCount"),
  coachList: document.querySelector("#coachList"),

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

  seasonModal: document.querySelector("#seasonModal"),
  seasonBackdrop: document.querySelector("#seasonBackdrop"),
  seasonClose: document.querySelector("#seasonClose"),
  seasonTarget: document.querySelector("#seasonTarget"),
  seasonSelect: document.querySelector("#seasonSelect"),
  seasonCancel: document.querySelector("#seasonCancel"),
  seasonApply: document.querySelector("#seasonApply"),

  coachModal: document.querySelector("#coachModal"),
  coachBackdrop: document.querySelector("#coachBackdrop"),
  coachClose: document.querySelector("#coachClose"),
  coachTitle: document.querySelector("#coachTitle"),
  coachDetail: document.querySelector("#coachDetail"),

  formationModal: document.querySelector("#formationModal"),
  formationBackdrop: document.querySelector("#formationBackdrop"),
  formationClose: document.querySelector("#formationClose"),
  formationTitle: document.querySelector("#formationTitle"),
  formationDetail: document.querySelector("#formationDetail"),
};

let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let cloudMeta = { formationId: null, ownedFormationIds: [], coach: null };
let coaches = [];
let formations = [];
let nationNameById = new Map();
let filteredCoaches = [];
let selectedCoachIdForAdd = null;
let selectedCoachIdForDetail = null;
const coachTabModeById = new Map();
let modalScrollLockY = 0;
let modalScrollLocked = false;

function normalizeSeasonInput(input) {
  const raw = String(input || "").trim();
  if (!raw) return "";
  const n = raw.replace(/[^0-9]/g, "");
  if (n.length > 0) return `${Number(n)}期目`;
  if (raw.endsWith("期目")) return raw;
  if (raw.endsWith("期")) return `${raw}目`;
  return raw;
}

function seasonNumber(seasonText) {
  const n = Number(String(seasonText || "").replace(/[^0-9]/g, ""));
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function seasonLabel(seasonText) {
  return `${seasonNumber(seasonText)}期目`;
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
  const hasOpenModal = !!document.querySelector('[id$="Modal"]:not([hidden]), .season-modal:not([hidden]), .lineup-modal:not([hidden])');
  setModalScrollLocked(hasOpenModal);
}

function setupModalScrollLock() {
  const modals = [...document.querySelectorAll('[id$="Modal"], .season-modal, .lineup-modal')];
  const observer = new MutationObserver(() => refreshModalScrollLock());
  modals.forEach((m) => observer.observe(m, { attributes: true, attributeFilter: ["hidden"] }));
  refreshModalScrollLock();
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
  els.metaText.innerHTML = `Updated: ${APP_UPDATED_AT_JST}`;
}

function syncMenuButtonSize() {
  if (!els.menuButton) return;
  const heroEl = els.hero || els.menuButton.closest(".hero");
  const heroHeight = heroEl ? Math.round(heroEl.getBoundingClientRect().height) : 40;
  const size = Math.max(30, Math.round(heroHeight * 0.72));
  document.documentElement.style.setProperty("--menu-button-size", `${size}px`);
}

function closeMenuPanel() {
  if (!els.menuPanel) return;
  els.menuPanel.classList.remove("is-open");
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

function openSeasonModal(coachId) {
  selectedCoachIdForAdd = Number(coachId);
  if (!Number.isInteger(selectedCoachIdForAdd) || !els.seasonModal || !els.seasonSelect) return;
  const coach = coaches.find((c) => Number(c?.id) === selectedCoachIdForAdd);
  const seasons = Array.isArray(coach?.leadershipBySeason) ? coach.leadershipBySeason : [];
  const max = Math.max(1, seasons.length || 1);
  if (els.seasonTarget) {
    els.seasonTarget.textContent = coach ? `${coach.name}を監督登録します` : "監督登録";
  }
  els.seasonSelect.innerHTML = Array.from({ length: max }, (_, i) => `<option value="${i + 1}">${i + 1}期目</option>`).join("");
  els.seasonSelect.value = "1";
  els.seasonModal.hidden = false;
}

function closeSeasonModal() {
  selectedCoachIdForAdd = null;
  if (els.seasonModal) els.seasonModal.hidden = true;
}

function normalizeMeta(raw) {
  const fid = Number(raw?.formationId);
  const owned = Array.isArray(raw?.ownedFormationIds)
    ? raw.ownedFormationIds.map((x) => Number(x)).filter((x) => Number.isInteger(x) && x > 0)
    : [];
  const coachId = Number(raw?.coach?.coachId);
  const coachSeason = raw?.coach?.season == null ? null : normalizeSeasonInput(raw?.coach?.season);
  return {
    formationId: Number.isInteger(fid) && fid > 0 ? fid : null,
    ownedFormationIds: [...new Set(owned)],
    coach: Number.isInteger(coachId) && coachId > 0 ? { coachId, season: coachSeason || "1期目" } : null,
  };
}

function formationMetaId(lineupId = cloudConfig?.lineupKey) {
  const id = String(lineupId || "").trim();
  return id ? `${id}__meta` : "";
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
  const params = new URLSearchParams({ select: "lineup_id", lineup_id: `eq.${id}`, limit: "1" });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, { method: "GET" });
  return Array.isArray(rows) && rows.length > 0;
}

async function cloudCreateLineup(lineupId) {
  const id = String(lineupId || "").trim();
  if (!id) return;
  const payload = {
    lineup_id: id,
    lineup_json: Array.from({ length: 11 }, () => null),
    updated_at: new Date().toISOString(),
  };
  await supabaseRequest(`${SUPABASE_TABLE}?on_conflict=lineup_id`, {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=representation" },
    body: JSON.stringify(payload),
  });
}

async function loadCloudMeta() {
  const id = formationMetaId();
  if (!id) return false;
  const params = new URLSearchParams({ select: "lineup_json", lineup_id: `eq.${id}`, limit: "1" });
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

function getNationName(nationId) {
  const id = Number(nationId);
  if (!Number.isInteger(id)) return "-";
  return nationNameById.get(id) || `国籍ID:${id}`;
}

function typeLabel(typeNum) {
  return TYPE_LABELS[Number(typeNum)] || "-";
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

function findCoachNameSuggestions(rawQuery, limit = 3) {
  const q = toSearchNormalized(rawQuery);
  if (!q) return [];
  const seen = new Set();
  const scored = [];
  coaches.forEach((c) => {
    const name = String(c?.name || "").trim();
    if (!name || seen.has(name)) return;
    seen.add(name);
    const norm = toSearchNormalized(name);
    const idx = norm.indexOf(q);
    if (idx < 0) return;
    scored.push({ name, idx, len: norm.length });
  });
  return scored
    .sort((a, b) => a.idx - b.idx || a.len - b.len || a.name.localeCompare(b.name, "ja"))
    .slice(0, limit)
    .map((x) => x.name);
}

function renderCoachNameSuggest() {
  if (!els.coachNameSuggest || !els.coachNameQuery) return;
  const list = findCoachNameSuggestions(els.coachNameQuery.value);
  if (!list.length) {
    els.coachNameSuggest.hidden = true;
    els.coachNameSuggest.innerHTML = "";
    return;
  }
  els.coachNameSuggest.hidden = false;
  els.coachNameSuggest.innerHTML = list
    .map((name) => `<button type="button" class="name-suggest-item" data-name="${name}">${name}</button>`)
    .join("");
}

function getFormationName(fid) {
  const f = formations.find((x) => Number(x?.id) === Number(fid));
  if (!f) return `Formation ${fid}`;
  const y = formatFormationYearLabel(f.year, f.stride);
  return `${f.name}${y ? ` ${y}` : ""}`;
}

function buildCoachFormationFilters() {
  const targets = [els.coachAvailableFormationFilter, els.coachUnderstoodFormationFilter].filter(Boolean);
  if (!targets.length) return;
  const options = formations
    .slice()
    .sort((a, b) => {
      const na = getFormationName(a?.id);
      const nb = getFormationName(b?.id);
      return na.localeCompare(nb, "ja");
    })
    .map((f) => `<option value="${f.id}">${getFormationName(f.id)}</option>`)
    .join("");
  targets.forEach((sel) => {
    sel.innerHTML = `<option value="">-</option>${options}`;
  });
}

function leadershipTableHtml(leadership, currentSeason = null) {
  const rows = Array.isArray(leadership) ? leadership : [];
  if (!rows.length) return `<p class="dim">-</p>`;
  const chunks = [];
  for (let i = 0; i < rows.length; i += 8) {
    chunks.push(rows.slice(i, i + 8));
  }
  const blocks = chunks.map((chunk, idx) => {
    const start = idx * 8;
    const headers = chunk.map((_, i) => `<th>${start + i + 1}期</th>`).join("");
    const cells = chunk
      .map((v, i) => `<td class="${Number(currentSeason) === start + i + 1 ? "is-current" : ""}">${Number(v)}</td>`)
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

function coachFormationPills(list, withSeason = false) {
  const rows = Array.isArray(list) ? list : [];
  if (!rows.length) return "-";
  return rows
    .map((row) => {
      const fid = Number(withSeason ? row?.formationId : row);
      if (!Number.isInteger(fid)) return "";
      const suffix = withSeason && Number(row?.fromSeason) > 1 ? ` (${Number(row.fromSeason)}期目〜)` : "";
      const owned = cloudMeta.ownedFormationIds?.includes(fid) ? "is-owned" : "";
      return `<button type="button" class="inline-pill coach-formation-pill ${owned}" data-formation-id="${fid}">${getFormationName(fid)}${suffix}</button>`;
    })
    .join("");
}

function coachCardHtml(coach) {
  const staticImg = `./images/chara/headcoaches/static/${coach.id}@2x.gif`;
  const actionImg = `./images/chara/headcoaches/action/${coach.id}@2x.gif`;
  const nation = getNationName(coach.nationId);
  const leadership = Array.isArray(coach.leadershipBySeason) ? coach.leadershipBySeason : [];
  const currentSeason = cloudMeta?.coach && Number(cloudMeta?.coach?.coachId) === Number(coach.id)
    ? seasonNumber(cloudMeta?.coach?.season)
    : null;
  const tab = coachTabModeById.get(Number(coach.id)) || "lead";
  const tabPanelHtml =
    tab === "obtain"
      ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Available Formation</div><div class="coach-formation-list">${coachFormationPills(coach.obtainable, true)}</div></div>`
      : tab === "understood"
        ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Understood Formation</div><div class="coach-formation-list">${coachFormationPills(coach.depth4FormationIds || [], false)}</div></div>`
        : `<div class="coach-tab-panel coach-tab-scroll coach-tab-panel-lead"><div class="profile-description-title">Leadership</div>${leadershipTableHtml(leadership, currentSeason)}</div>`;

  return `
    <article class="coach-card coach-card-fixed" data-coach-id="${coach.id}">
      <div class="coach-card-top">
        <h3 class="card-name">
          <span class="badge pos-badge hc-badge">HC</span>
          <span>${coach.name}</span>
        </h3>
        <button type="button" class="lineup-toggle coach-add-btn" data-coach-id="${coach.id}" aria-label="監督登録">Add</button>
      </div>
      <div class="coach-card-body">
        <div class="coach-images-btn">
          <div class="thumbs coach-thumbs">
            <img loading="lazy" src="${staticImg}" alt="${coach.name}" onerror="this.src='${actionImg}'" />
            <img loading="lazy" src="${actionImg}" alt="${coach.name}" />
          </div>
        </div>
        <div class="profile-side coach-profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nation}</span></div>
          <div class="profile-item"><span class="k">年齢</span><span class="v">${coach.age || "-"}</span></div>
          <div class="profile-item"><span class="k">タイプ</span><span class="v">${typeLabel(coach.type)}</span></div>
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

function filterCoaches() {
  const q = toSearchNormalized(els.coachNameQuery?.value || "");
  const typeVal = Number(els.coachTypeFilter?.value || 0);
  const avlFormationId = Number(els.coachAvailableFormationFilter?.value || 0);
  const undFormationId = Number(els.coachUnderstoodFormationFilter?.value || 0);
  filteredCoaches = coaches.filter((c) => {
    if (typeVal > 0 && Number(c?.type) !== typeVal) return false;
    if (avlFormationId > 0) {
      const available = Array.isArray(c?.obtainable) ? c.obtainable : [];
      if (!available.some((row) => Number(row?.formationId) === avlFormationId)) return false;
    }
    if (undFormationId > 0) {
      const understood = Array.isArray(c?.depth4FormationIds) ? c.depth4FormationIds : [];
      if (!understood.some((fid) => Number(fid) === undFormationId)) return false;
    }
    if (!q) return true;
    return includesSearch(c?.name || "", q) || includesSearch(c?.fullName || "", q);
  });
}

function renderCoaches() {
  if (!els.coachList) return;
  filterCoaches();
  els.coachList.innerHTML = filteredCoaches.map(coachCardHtml).join("");
  if (els.coachCount) els.coachCount.textContent = `${filteredCoaches.length} results`;
  renderCoachNameSuggest();
}

function renderCoachDetail(coachId) {
  if (!els.coachDetail || !els.coachTitle) return;
  const coach = coaches.find((c) => Number(c?.id) === Number(coachId));
  if (!coach) {
    els.coachTitle.textContent = "Coach";
    els.coachDetail.innerHTML = `<p class=\"dim\">No data.</p>`;
    return;
  }
  els.coachTitle.textContent = "Coach";
  const leadership = Array.isArray(coach.leadershipBySeason) ? coach.leadershipBySeason : [];
  const currentSeason = cloudMeta?.coach && Number(cloudMeta?.coach?.coachId) === Number(coach.id)
    ? seasonNumber(cloudMeta?.coach?.season)
    : null;
  const staticImg = `./images/chara/headcoaches/static/${coach.id}@2x.gif`;
  const actionImg = `./images/chara/headcoaches/action/${coach.id}@2x.gif`;
  const nation = getNationName(coach.nationId);
  const tab = coachTabModeById.get(Number(coach.id)) || "lead";
  const tabPanelHtml =
    tab === "obtain"
      ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Available Formation</div><div class="coach-formation-list">${coachFormationPills(coach.obtainable || [], true)}</div></div>`
      : tab === "understood"
        ? `<div class="coach-tab-panel coach-tab-scroll"><div class="profile-description-title">Understood Formation</div><div class="coach-formation-list">${coachFormationPills(coach.depth4FormationIds || [], false)}</div></div>`
        : `<div class="coach-tab-panel coach-tab-scroll coach-tab-panel-lead"><div class="profile-description-title">Leadership</div>${leadershipTableHtml(leadership, currentSeason)}</div>`;

  els.coachDetail.innerHTML = `
    <article class="coach-card coach-card-fixed">
      <div class="coach-card-top">
        <h3 class="card-name">
          <span class="badge pos-badge hc-badge">HC</span>
          <span>${coach.name}</span>
        </h3>
      </div>
      <div class="coach-card-body">
        <div class="coach-images-btn">
          <div class="thumbs coach-thumbs">
            <img loading="lazy" src="${staticImg}" alt="${coach.name}" onerror="this.src='${actionImg}'" />
            <img loading="lazy" src="${actionImg}" alt="${coach.name}" />
          </div>
        </div>
        <div class="profile-side coach-profile-side">
          <div class="profile-item"><span class="k">国籍</span><span class="v">${nation}</span></div>
          <div class="profile-item"><span class="k">年齢</span><span class="v">${coach.age || "-"}</span></div>
          <div class="profile-item"><span class="k">タイプ</span><span class="v">${typeLabel(coach.type)}</span></div>
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
  selectedCoachIdForDetail = Number(coachId);
  renderCoachDetail(selectedCoachIdForDetail);
  if (els.coachModal) els.coachModal.hidden = false;
}

function closeCoachModal() {
  selectedCoachIdForDetail = null;
  if (els.coachModal) els.coachModal.hidden = true;
}

function openFormationModal(formationId) {
  if (!els.formationModal || !els.formationTitle || !els.formationDetail) return;
  const f = formations.find((x) => Number(x?.id) === Number(formationId));
  if (!f) return;
  const y = formatFormationYearLabel(f.year, f.stride);
  els.formationTitle.textContent = `${f.name}${y ? ` ${y}` : ""}`;
  els.formationDetail.innerHTML = `
    <div class="formation-block">
      <h3>System</h3>
      <p>${f.system || "-"}</p>
      <p>Usage: ${(Number(f.cc?.usageRate || 0) * 100).toFixed(2)}%</p>
      <p>Win: ${(Number(f.cc?.winRate || 0) * 100).toFixed(2)}%</p>
    </div>
    <div class="formation-block">
      <h3>Key Positions</h3>
      <div>${(f.keyPositions || []).map((k) => `<span class=\"inline-pill\">Slot ${k.slot}</span>`).join(" ") || "-"}</div>
    </div>
  `;
  els.formationModal.hidden = false;
}

function closeFormationModal() {
  if (els.formationModal) els.formationModal.hidden = true;
}

async function registerCoachFromSeason() {
  const coachId = Number(selectedCoachIdForAdd);
  if (!Number.isInteger(coachId)) return;
  const season = normalizeSeasonInput(els.seasonSelect?.value || "1");
  cloudMeta.coach = { coachId, season: season || "1期目" };
  if (isLoggedIn()) {
    try {
      await saveCloudMeta();
    } catch (e) {
      window.alert("監督登録のクラウド保存に失敗しました。");
      return;
    }
  }
  closeSeasonModal();
  window.alert("監督の登録が完了しました。");
}

async function ensureLoginAndOpenSeason(coachId) {
  if (!isLoggedIn()) {
    selectedCoachIdForAdd = Number(coachId);
    openLoginModal();
    return;
  }
  await loadCloudMeta().catch(() => {});
  openSeasonModal(coachId);
}

function bindEvents() {
  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => {
      if (!els.menuPanel) return;
      els.menuPanel.classList.toggle("is-open");
    });
  }
  if (els.playersButton) els.playersButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./index.html"; });
  if (els.formationsButton) els.formationsButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./formations.html"; });
  if (els.myTeamButton) els.myTeamButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./myteam.html"; });
  if (els.coachesButton) els.coachesButton.addEventListener("click", closeMenuPanel);

  if (els.loginButton) els.loginButton.addEventListener("click", () => { closeMenuPanel(); openLoginModal(); });
  if (els.logoutButton) els.logoutButton.addEventListener("click", () => { closeMenuPanel(); saveCloudConfig(""); cloudMeta = { formationId: null, ownedFormationIds: [], coach: null }; updateMenuState(); renderCoaches(); });

  if (els.coachNameQuery) {
    els.coachNameQuery.addEventListener("input", renderCoaches);
    els.coachNameQuery.addEventListener("blur", () => {
      setTimeout(() => {
        if (!els.coachNameSuggest) return;
        els.coachNameSuggest.hidden = true;
      }, 120);
    });
  }
  if (els.coachTypeFilter) els.coachTypeFilter.addEventListener("change", renderCoaches);
  if (els.coachAvailableFormationFilter) els.coachAvailableFormationFilter.addEventListener("change", renderCoaches);
  if (els.coachUnderstoodFormationFilter) els.coachUnderstoodFormationFilter.addEventListener("change", renderCoaches);

  if (els.coachList) {
    els.coachList.addEventListener("click", async (e) => {
      const addBtn = e.target.closest(".coach-add-btn");
      if (addBtn) {
        const coachId = Number(addBtn.dataset.coachId);
        if (Number.isInteger(coachId)) await ensureLoginAndOpenSeason(coachId);
        return;
      }
      const tabBtn = e.target.closest("[data-coach-tab][data-coach-id]");
      if (tabBtn) {
        const coachId = Number(tabBtn.dataset.coachId);
        const tab = String(tabBtn.dataset.coachTab || "");
        if (Number.isInteger(coachId) && (tab === "lead" || tab === "obtain" || tab === "understood")) {
          coachTabModeById.set(coachId, tab);
          renderCoaches();
        }
        return;
      }
      const fbtn = e.target.closest("[data-formation-id]");
      if (fbtn) {
        const fid = Number(fbtn.dataset.formationId);
        if (Number.isInteger(fid)) window.location.href = `./formations.html?openFormationId=${fid}`;
      }
    });
  }

  if (els.coachNameSuggest) {
    els.coachNameSuggest.addEventListener("click", (e) => {
      const btn = e.target.closest(".name-suggest-item");
      if (!btn || !els.coachNameQuery) return;
      els.coachNameQuery.value = btn.dataset.name || "";
      els.coachNameSuggest.hidden = true;
      renderCoaches();
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
      if (Number.isInteger(fid)) window.location.href = `./formations.html?openFormationId=${fid}`;
    });
  }

  if (els.loginBackdrop) els.loginBackdrop.addEventListener("click", closeLoginModal);
  if (els.loginClose) els.loginClose.addEventListener("click", closeLoginModal);
  if (els.signupOpen) els.signupOpen.addEventListener("click", () => { closeLoginModal(); openSignupModal(); });

  if (els.loginApply) {
    els.loginApply.addEventListener("click", async () => {
      const key = String(els.loginLineupKey?.value || "").trim();
      const prev = String(cloudConfig.lineupKey || "").trim();
      if (!key) return;
      saveCloudConfig(key);
      try {
        const exists = await cloudLineupExists(key);
        if (!exists) {
          saveCloudConfig(prev);
          updateMenuState();
          window.alert("入力されたIDの登録はありません。Create New IDを使用してください。");
          return;
        }
        await loadCloudMeta().catch(() => {});
      } catch (_) {
        saveCloudConfig(prev);
        updateMenuState();
        window.alert("Loginに失敗しました。");
        return;
      }
      updateMenuState();
      closeLoginModal();
      if (Number.isInteger(selectedCoachIdForAdd)) {
        openSeasonModal(selectedCoachIdForAdd);
      }
      renderCoaches();
    });
  }

  if (els.signupBackdrop) els.signupBackdrop.addEventListener("click", closeSignupModal);
  if (els.signupClose) els.signupClose.addEventListener("click", closeSignupModal);
  if (els.signupCancel) els.signupCancel.addEventListener("click", closeSignupModal);
  if (els.signupApply) {
    els.signupApply.addEventListener("click", async () => {
      const key = String(els.signupLineupKey?.value || "").trim();
      const prev = String(cloudConfig.lineupKey || "").trim();
      if (!key) return;
      saveCloudConfig(key);
      try {
        const exists = await cloudLineupExists(key);
        if (exists) {
          saveCloudConfig(prev);
          updateMenuState();
          window.alert("そのIDは既に使われています。別のIDを入力してください。");
          return;
        }
        await cloudCreateLineup(key);
        cloudMeta = { formationId: null, ownedFormationIds: [], coach: null };
        await saveCloudMeta();
      } catch (_) {
        saveCloudConfig(prev);
        updateMenuState();
        window.alert("Create New IDに失敗しました。");
        return;
      }
      updateMenuState();
      closeSignupModal();
      closeLoginModal();
      if (Number.isInteger(selectedCoachIdForAdd)) {
        openSeasonModal(selectedCoachIdForAdd);
      }
      renderCoaches();
    });
  }

  if (els.seasonBackdrop) els.seasonBackdrop.addEventListener("click", closeSeasonModal);
  if (els.seasonClose) els.seasonClose.addEventListener("click", closeSeasonModal);
  if (els.seasonCancel) els.seasonCancel.addEventListener("click", closeSeasonModal);
  if (els.seasonApply) els.seasonApply.addEventListener("click", registerCoachFromSeason);

  if (els.coachBackdrop) els.coachBackdrop.addEventListener("click", closeCoachModal);
  if (els.coachClose) els.coachClose.addEventListener("click", closeCoachModal);
  if (els.formationBackdrop) els.formationBackdrop.addEventListener("click", closeFormationModal);
  if (els.formationClose) els.formationClose.addEventListener("click", closeFormationModal);

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
    closeSeasonModal();
    closeCoachModal();
    closeFormationModal();
  });
}

async function init() {
  setupModalScrollLock();
  loadCloudConfig();
  syncMenuButtonSize();
  window.addEventListener("resize", syncMenuButtonSize);
  bindEvents();

  const [formationsRes, coachesRes, playersRes] = await Promise.all([
    fetch("./formations_data.json"),
    fetch("./coaches_data.json").catch(() => null),
    fetch("./data.json").catch(() => null),
  ]);

  const fData = await formationsRes.json();
  formations = Array.isArray(fData?.formations) ? fData.formations : [];
  buildCoachFormationFilters();

  let enriched = null;
  if (coachesRes && coachesRes.ok) {
    try {
      const cData = await coachesRes.json();
      enriched = Array.isArray(cData?.coaches) ? cData.coaches : null;
    } catch (e) {
      console.warn(e);
    }
  }
  const baseCoaches = Array.isArray(fData?.coaches) ? fData.coaches : [];
  const byId = new Map((enriched || []).map((c) => [Number(c?.id), c]));
  coaches = baseCoaches.map((c) => {
    const ext = byId.get(Number(c?.id));
    return {
      ...c,
      leadershipBySeason: Array.isArray(ext?.leadershipBySeason) ? ext.leadershipBySeason : [],
      obtainable: Array.isArray(ext?.obtainable) ? ext.obtainable : [],
      depth4FormationIds: Array.isArray(ext?.depth4FormationIds) ? ext.depth4FormationIds : (Array.isArray(c?.formationDepth4) ? c.formationDepth4 : []),
    };
  });

  if (playersRes && playersRes.ok) {
    try {
      const pData = await playersRes.json();
      const rows = Array.isArray(pData?.players) ? pData.players : [];
      syncProfileSideWidthFromPlayers(rows);
      rows.forEach((p) => {
        const id = Number(p?.nationId);
        if (!Number.isInteger(id) || nationNameById.has(id)) return;
        const n = String(p?.nationality || "").trim();
        if (n) nationNameById.set(id, n);
      });
    } catch (e) {
      console.warn(e);
    }
  }

  if (isLoggedIn()) {
    await loadCloudMeta().catch(() => {});
  }
  updateMenuState();
  renderCoaches();
}

init().catch((e) => {
  if (els.metaText) els.metaText.textContent = "Failed to load coaches.";
  console.error(e);
});
