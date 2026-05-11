const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-30 23:10 JST";
const REPO_COMMITS_API = "https://api.github.com/repos/gigagigohub/websoccer-player-search/commits/main";

const els = {
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  playersButton: document.querySelector("#playersButton"),
  coachesButton: document.querySelector("#coachesButton"),
  formationsButton: document.querySelector("#formationsButton"),
  collectionsButton: document.querySelector("#collectionsButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  uniformTab: document.querySelector("#uniformTab"),
  emblemTab: document.querySelector("#emblemTab"),
  collectionQuery: document.querySelector("#collectionQuery"),
  rarityFilter: document.querySelector("#rarityFilter"),
  collectionSort: document.querySelector("#collectionSort"),
  collectionTitle: document.querySelector("#collectionTitle"),
  collectionCount: document.querySelector("#collectionCount"),
  collectionList: document.querySelector("#collectionList"),
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
};

let appUpdatedAtJst = APP_UPDATED_AT_JST;
let ccDataMeta = null;
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let mode = "uniforms";
let uniforms = [];
let emblems = [];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[c]));
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function loadCloudConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(CLOUD_CONFIG_STORAGE_KEY) || "{}");
    cloudConfig = {
      url: normalizedSupabaseUrl(saved.url || ""),
      anonKey: String(saved.anonKey || "").trim(),
      lineupKey: String(saved.lineupKey || "").trim(),
    };
  } catch (e) {
    cloudConfig = { url: "", anonKey: "", lineupKey: "" };
  }
  if (FIXED_SUPABASE_URL) cloudConfig.url = normalizedSupabaseUrl(FIXED_SUPABASE_URL);
  if (FIXED_SUPABASE_ANON_KEY) cloudConfig.anonKey = String(FIXED_SUPABASE_ANON_KEY).trim();
}

function saveCloudConfig(lineupKey = cloudConfig.lineupKey) {
  cloudConfig.lineupKey = String(lineupKey || "").trim();
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
}

function hasCloudConfig() {
  return !!String(cloudConfig.lineupKey || "").trim();
}

function closeMenuPanel() {
  if (els.menuPanel) els.menuPanel.classList.remove("is-open");
}

function updateMenuState() {
  const loggedIn = hasCloudConfig();
  if (els.loginButton) els.loginButton.hidden = loggedIn;
  if (els.logoutButton) els.logoutButton.hidden = !loggedIn;
  if (els.menuLoginId) {
    els.menuLoginId.hidden = !loggedIn;
    els.menuLoginId.textContent = loggedIn ? `Team ID：${cloudConfig.lineupKey}` : "";
  }
}

function renderMeta() {
  if (!els.metaText) return;
  const ccLine = ccDataMeta
    ? `<span class="meta-line">CC Data: ${ccDataMeta.seasonStart}-${ccDataMeta.seasonEnd} / ${ccDataMeta.games} games</span>`
    : "";
  els.metaText.innerHTML = `<span class="meta-line">Updated: ${appUpdatedAtJst}</span>${ccLine}`;
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
    const label = formatJstFromIso(obj?.commit?.committer?.date || obj?.commit?.author?.date || "");
    if (!label) return;
    appUpdatedAtJst = label;
    renderMeta();
  } catch (e) {
    // Keep static fallback.
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
    // Metadata is optional.
  }
}

async function supabaseRequest(pathWithQuery, options = {}) {
  if (!cloudConfig.url || !cloudConfig.anonKey) throw new Error("Supabase config is missing.");
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
    const text = await res.text().catch(() => "");
    throw new Error(text || `Supabase request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loginTeamId() {
  const key = String(els.loginLineupKey?.value || "").trim();
  if (!key) return;
  saveCloudConfig(key);
  updateMenuState();
  closeLoginModal();
}

async function signupTeamId() {
  const key = String(els.signupLineupKey?.value || "").trim();
  if (!key) return;
  const prevKey = cloudConfig.lineupKey;
  try {
    saveCloudConfig(key);
    await supabaseRequest(SUPABASE_TABLE, {
      method: "POST",
      headers: { Prefer: "resolution=ignore-duplicates" },
      body: JSON.stringify({ lineup_key: key, state: {} }),
    });
    updateMenuState();
    closeSignupModal();
    closeLoginModal();
  } catch (e) {
    saveCloudConfig(prevKey);
    window.alert("Create New IDに失敗しました。");
  }
}

function openLoginModal() {
  if (!els.loginModal) return;
  els.loginModal.hidden = false;
  if (els.loginLineupKey) {
    els.loginLineupKey.value = cloudConfig.lineupKey || "";
    els.loginLineupKey.focus();
  }
}

function closeLoginModal() {
  if (els.loginModal) els.loginModal.hidden = true;
}

function openSignupModal() {
  if (!els.signupModal) return;
  els.signupModal.hidden = false;
  if (els.signupLineupKey) {
    els.signupLineupKey.value = "";
    els.signupLineupKey.focus();
  }
}

function closeSignupModal() {
  if (els.signupModal) els.signupModal.hidden = true;
}

function rarityLabel(value) {
  const n = Number(value);
  if (!Number.isInteger(n)) return "-";
  return `R${n}`;
}

function collectionSearchText(item) {
  return [
    item.id,
    item.name,
    item.baseName,
    item.year,
    item.rarity,
  ].filter((x) => x !== undefined && x !== null).join(" ").toLowerCase();
}

function currentItems() {
  return mode === "emblems" ? emblems : uniforms;
}

function populateSelectOptions(select, values, prefix = "") {
  if (!select) return;
  const current = select.value;
  select.innerHTML = '<option value="">ALL</option>';
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = String(value);
    opt.textContent = `${prefix}${value}`;
    select.appendChild(opt);
  });
  if ([...select.options].some((opt) => opt.value === current)) {
    select.value = current;
  }
}

function refreshFilterOptions() {
  const rows = currentItems();
  const rarities = [...new Set(rows.map((x) => Number(x.rarity)).filter((x) => Number.isInteger(x)))].sort((a, b) => a - b);
  populateSelectOptions(els.rarityFilter, rarities, "R");
}

function filteredItems() {
  const query = String(els.collectionQuery?.value || "").trim().toLowerCase();
  const rarity = String(els.rarityFilter?.value || "");
  const sortKey = String(els.collectionSort?.value || "idAsc");
  let rows = currentItems().filter((item) => {
    if (query && !collectionSearchText(item).includes(query)) return false;
    if (rarity && String(item.rarity) !== rarity) return false;
    return true;
  });
  rows = [...rows].sort((a, b) => {
    if (sortKey === "idDesc") return Number(b.id) - Number(a.id);
    if (sortKey === "nameAsc") return String(a.name || "").localeCompare(String(b.name || ""), "ja") || Number(a.id) - Number(b.id);
    if (sortKey === "nameDesc") return String(b.name || "").localeCompare(String(a.name || ""), "ja") || Number(a.id) - Number(b.id);
    return Number(a.id) - Number(b.id);
  });
  return rows;
}

function missingImage(label) {
  return `<div class="collection-image-missing">${escapeHtml(label)}</div>`;
}

function renderUniform(item) {
  const home = item.images?.home
    ? `<img src="${escapeHtml(item.images.home)}" alt="${escapeHtml(item.name)} home" loading="lazy">`
    : missingImage("Home");
  const away = item.images?.away
    ? `<img src="${escapeHtml(item.images.away)}" alt="${escapeHtml(item.name)} away" loading="lazy">`
    : missingImage("Away");
  return `
    <article class="collection-card collection-uniform-card">
      <div class="collection-card-head">
        <h3>${escapeHtml(item.name || `Uniform ${item.id}`)}</h3>
        <span class="collection-id">#${escapeHtml(item.id)}</span>
      </div>
      <div class="collection-uniform-images">
        <div class="collection-uniform-frame"><span>Home</span>${home}</div>
        <div class="collection-uniform-frame"><span>Away</span>${away}</div>
      </div>
      <div class="collection-meta">
        <span class="collection-chip">${escapeHtml(rarityLabel(item.rarity))}</span>
      </div>
    </article>`;
}

function renderEmblem(item) {
  const image = item.image
    ? `<img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" loading="lazy">`
    : missingImage("Emblem");
  return `
    <article class="collection-card collection-emblem-card">
      <div class="collection-card-head">
        <h3>${escapeHtml(item.name || `Emblem ${item.id}`)}</h3>
        <span class="collection-id">#${escapeHtml(item.id)}</span>
      </div>
      <div class="collection-emblem-image">${image}</div>
      <div class="collection-meta">
        <span class="collection-chip">${escapeHtml(rarityLabel(item.rarity))}</span>
      </div>
    </article>`;
}

function renderCollections() {
  const rows = filteredItems();
  if (els.collectionTitle) els.collectionTitle.textContent = mode === "emblems" ? "Emblems" : "Uniforms";
  if (els.collectionCount) els.collectionCount.textContent = `${rows.length} results`;
  if (els.collectionList) {
    els.collectionList.innerHTML = rows.map((item) => mode === "emblems" ? renderEmblem(item) : renderUniform(item)).join("");
  }
}

function setMode(nextMode) {
  mode = nextMode === "emblems" ? "emblems" : "uniforms";
  if (els.uniformTab) {
    els.uniformTab.classList.toggle("is-active", mode === "uniforms");
    els.uniformTab.setAttribute("aria-pressed", mode === "uniforms" ? "true" : "false");
  }
  if (els.emblemTab) {
    els.emblemTab.classList.toggle("is-active", mode === "emblems");
    els.emblemTab.setAttribute("aria-pressed", mode === "emblems" ? "true" : "false");
  }
  refreshFilterOptions();
  renderCollections();
}

function syncMenuButtonSize() {
  document.documentElement.style.setProperty("--menu-button-size", "60px");
}

function bindEvents() {
  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => {
      if (!els.menuPanel) return;
      els.menuPanel.classList.toggle("is-open");
    });
  }
  if (els.playersButton) els.playersButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./index.html"; });
  if (els.coachesButton) els.coachesButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./coaches.html"; });
  if (els.formationsButton) els.formationsButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./formations.html"; });
  if (els.collectionsButton) els.collectionsButton.addEventListener("click", closeMenuPanel);
  if (els.myTeamButton) els.myTeamButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./myteam.html"; });
  if (els.loginButton) els.loginButton.addEventListener("click", () => { closeMenuPanel(); openLoginModal(); });
  if (els.logoutButton) els.logoutButton.addEventListener("click", () => { closeMenuPanel(); saveCloudConfig(""); updateMenuState(); });

  if (els.uniformTab) els.uniformTab.addEventListener("click", () => setMode("uniforms"));
  if (els.emblemTab) els.emblemTab.addEventListener("click", () => setMode("emblems"));
  [els.collectionQuery, els.rarityFilter, els.collectionSort].forEach((el) => {
    if (el) el.addEventListener("input", renderCollections);
    if (el) el.addEventListener("change", renderCollections);
  });
  if (els.loginBackdrop) els.loginBackdrop.addEventListener("click", closeLoginModal);
  if (els.loginClose) els.loginClose.addEventListener("click", closeLoginModal);
  if (els.loginApply) els.loginApply.addEventListener("click", loginTeamId);
  if (els.loginLineupKey) els.loginLineupKey.addEventListener("keydown", (e) => { if (e.key === "Enter") loginTeamId(); });
  if (els.signupOpen) els.signupOpen.addEventListener("click", openSignupModal);
  if (els.signupBackdrop) els.signupBackdrop.addEventListener("click", closeSignupModal);
  if (els.signupClose) els.signupClose.addEventListener("click", closeSignupModal);
  if (els.signupCancel) els.signupCancel.addEventListener("click", closeSignupModal);
  if (els.signupApply) els.signupApply.addEventListener("click", signupTeamId);
  if (els.signupLineupKey) els.signupLineupKey.addEventListener("keydown", (e) => { if (e.key === "Enter") signupTeamId(); });
}

async function init() {
  loadCloudConfig();
  syncMenuButtonSize();
  bindEvents();
  const [collectionRes] = await Promise.all([
    fetch("./collections_data.json?v=20260511-collections"),
    loadSiteMeta(),
  ]);
  const data = await collectionRes.json();
  uniforms = Array.isArray(data?.uniforms) ? data.uniforms : [];
  emblems = Array.isArray(data?.emblems) ? data.emblems : [];
  updateMenuState();
  renderMeta();
  refreshUpdatedAtFromGitHub();
  setMode("uniforms");
}

init().catch((e) => {
  console.error(e);
  if (els.collectionList) {
    els.collectionList.innerHTML = '<p class="collection-empty">Collections data could not be loaded.</p>';
  }
});
