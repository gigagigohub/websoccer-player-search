const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-21 21:42 JST";

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
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  playersButton: document.querySelector("#playersButton"),
  loginButton: document.querySelector("#loginButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  logoutButton: document.querySelector("#logoutButton"),
  sortKey: document.querySelector("#sortKey"),
  sortDir: document.querySelector("#sortDir"),
  coachFilter: document.querySelector("#coachFilter"),
  coachModeDepth4: document.querySelector("#coachModeDepth4"),
  coachModeObtainable: document.querySelector("#coachModeObtainable"),
  formationCount: document.querySelector("#formationCount"),
  formationList: document.querySelector("#formationList"),
  loginModal: document.querySelector("#loginModal"),
  loginBackdrop: document.querySelector("#loginBackdrop"),
  loginClose: document.querySelector("#loginClose"),
  loginLineupKey: document.querySelector("#loginLineupKey"),
  loginApply: document.querySelector("#loginApply"),
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
};

let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let formations = [];
let coaches = [];
let coachMode = "depth4";
let filteredAndSorted = [];
let currentFormation = null;

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
  const login = isLoggedIn() ? ` / <span class="meta-login-badge">Login：${cloudConfig.lineupKey}</span>` : "";
  els.metaText.innerHTML = `Updated: ${APP_UPDATED_AT_JST}${login}`;
}

function updateMenuState() {
  const loggedIn = isLoggedIn();
  if (els.loginButton) els.loginButton.hidden = loggedIn;
  if (els.myTeamButton) els.myTeamButton.hidden = !loggedIn;
  if (els.logoutButton) els.logoutButton.hidden = !loggedIn;
  renderMeta();
}

function closeMenuPanel() {
  if (!els.menuPanel) return;
  els.menuPanel.hidden = true;
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

function buildSortOptions() {
  if (!els.sortKey) return;
  els.sortKey.innerHTML = SORT_OPTIONS.map((o) => `<option value="${o.key}">${o.label}</option>`).join("");
  els.sortKey.value = "cc.usageRate";
}

function buildCoachFilter() {
  if (!els.coachFilter) return;
  const options = coaches
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, "ja"))
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
  els.coachFilter.innerHTML = `<option value="">ALL</option>${options}`;
}

function updateCoachModeButtons() {
  const map = {
    depth4: els.coachModeDepth4,
    obtainable: els.coachModeObtainable,
  };
  Object.entries(map).forEach(([k, el]) => {
    if (!el) return;
    el.classList.toggle("is-on", coachMode === k);
  });
}

function applyFilterAndSort() {
  const sortKey = els.sortKey?.value || "cc.usageRate";
  const sortDir = els.sortDir?.value === "asc" ? 1 : -1;
  const coachId = Number(els.coachFilter?.value || 0);

  let rows = formations.slice();
  if (coachId > 0) {
    const coach = coaches.find((c) => Number(c.id) === coachId);
    if (coach) {
      const allowSet = new Set((coachMode === "depth4" ? coach.formationDepth4 : coach.formationObtainable).map(Number));
      rows = rows.filter((f) => allowSet.has(Number(f.id)));
    }
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
  const yearText = Number.isFinite(Number(f.year)) && Number(f.year) > 0 ? Number(f.year) : "-";
  return `
    <button type="button" class="formation-item" data-formation-id="${f.id}">
      <div class="formation-item-head">
        <div class="formation-name-wrap">
          <strong>${f.name}</strong>
          <span class="formation-year">${yearText}</span>
        </div>
        <span class="formation-system">${f.system || "-"}</span>
      </div>
      <div class="formation-item-metrics">
        <span>Usage ${pct(f.cc.usageRate)}</span>
        <span>Win ${pct(f.cc.winRate)}</span>
        <span>Speed ${f.params.spd}</span>
        <span>Tech ${f.params.tec}</span>
        <span>Power ${f.params.pwr}</span>
        <span>Total ${f.params.ttl}</span>
      </div>
    </button>
  `;
}

function renderList() {
  if (!els.formationList) return;
  applyFilterAndSort();
  els.formationList.innerHTML = filteredAndSorted.map(formationCardHtml).join("");
  if (els.formationCount) {
    els.formationCount.textContent = `${filteredAndSorted.length} formations`;
  }
}

function renderFormationPitch(positions) {
  const minX = 1;
  const maxX = 321;
  const minY = 2;
  const maxY = 337;
  return `
    <div class="formation-pitch">
      ${positions
        .map((p) => {
          const left = ((p.x - minX) / (maxX - minX)) * 100;
          const top = ((p.y - minY) / (maxY - minY)) * 100;
          return `<button type="button" class="formation-slot-point" data-slot="${p.slot}" style="left:${left.toFixed(2)}%;top:${top.toFixed(2)}%">${p.slot}</button>`;
        })
        .join("")}
    </div>
  `;
}

function renderCoachesList(list) {
  if (!Array.isArray(list) || !list.length) return "-";
  return list.map((c) => `<span class="inline-pill">${c.name}</span>`).join(" ");
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

function renderSlotTop(slotTop) {
  const slots = Array.from({ length: 11 }, (_, i) => i + 1);
  return `
    <div class="formation-slot-top-grid">
      ${slots
        .map((slot) => {
          const top = slotTop?.[String(slot)] || null;
          if (!top) {
            return `<button type="button" class="slot-top-item" data-slot="${slot}"><span>Slot ${slot}</span><span class="dim">No data</span></button>`;
          }
          return `
            <button type="button" class="slot-top-item" data-slot="${slot}">
              <span>Slot ${slot}</span>
              <strong>${top.playerName}</strong>
              <span>${pct(top.usageRate)} / ${avg(top.avgPts)}</span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function openFormationModal(formation) {
  currentFormation = formation;
  if (!els.formationModal || !els.formationTitle || !els.formationDetail) return;

  const params = Object.entries(formation.params || {})
    .map(([k, v]) => `<span>${PARAM_LABELS[k] || k}: ${v}</span>`)
    .join("");

  els.formationTitle.textContent = `${formation.name} (${formation.system || "-"})`;
  els.formationDetail.innerHTML = `
    <div class="formation-detail-grid">
      <div>
        ${renderFormationPitch(formation.positions || [])}
      </div>
      <div>
        <div class="formation-block">
          <h3>CC Stats</h3>
          <p>Usage: ${pct(formation.cc.usageRate)} (${formation.cc.uses})</p>
          <p>Win: ${pct(formation.cc.winRate)} (${formation.cc.wins}/${formation.cc.uses || 0})</p>
        </div>
        <div class="formation-block">
          <h3>Parameters</h3>
          <div class="formation-param-grid">${params}</div>
        </div>
        <div class="formation-block">
          <h3>Obtainable Coaches</h3>
          <div>${renderCoachesList(formation.coaches?.obtainable)}</div>
        </div>
        <div class="formation-block">
          <h3>Depth 4 Coaches</h3>
          <div>${renderCoachesList(formation.coaches?.depth4)}</div>
        </div>
      </div>
    </div>
    <div class="formation-block">
      <h3>Key Positions</h3>
      ${renderKeyPositions(formation.keyPositions || [])}
    </div>
    <div class="formation-block">
      <h3>CC Slot Top Player (Usage #1)</h3>
      ${renderSlotTop(formation.slotTop || {})}
    </div>
  `;
  els.formationModal.hidden = false;
}

function closeFormationModal() {
  if (!els.formationModal) return;
  els.formationModal.hidden = true;
}

function openSlotModal(slot) {
  if (!currentFormation || !els.slotModal || !els.slotTitle || !els.slotDetail) return;
  const rows = currentFormation.slotStats?.[String(slot)] || [];
  els.slotTitle.textContent = `${currentFormation.name} / Slot ${slot}`;
  if (!rows.length) {
    els.slotDetail.innerHTML = `<p class="dim">No CC slot data.</p>`;
  } else {
    els.slotDetail.innerHTML = `
      <div class="slot-table-wrap">
        <table class="slot-table">
          <thead>
            <tr><th>Rank</th><th>Player</th><th>Usage</th><th>Avg Pts</th><th>ID</th></tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (r, idx) => `
                  <tr>
                    <td>${idx + 1}</td>
                    <td>${r.playerName}</td>
                    <td>${pct(r.usageRate)} (${r.uses})</td>
                    <td>${avg(r.avgPts)}</td>
                    <td>${r.playerId}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }
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
      els.menuPanel.hidden = !els.menuPanel.hidden;
    });
  }
  if (els.playersButton) {
    els.playersButton.addEventListener("click", () => {
      closeMenuPanel();
      window.location.href = "./index.html";
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
  if (els.loginApply) {
    els.loginApply.addEventListener("click", () => {
      const key = String(els.loginLineupKey?.value || "").trim();
      saveCloudConfig(key);
      updateMenuState();
      closeLoginModal();
    });
  }

  if (els.sortKey) els.sortKey.addEventListener("change", renderList);
  if (els.sortDir) els.sortDir.addEventListener("change", renderList);
  if (els.coachFilter) els.coachFilter.addEventListener("change", renderList);

  if (els.coachModeDepth4) {
    els.coachModeDepth4.addEventListener("click", () => {
      coachMode = "depth4";
      updateCoachModeButtons();
      renderList();
    });
  }
  if (els.coachModeObtainable) {
    els.coachModeObtainable.addEventListener("click", () => {
      coachMode = "obtainable";
      updateCoachModeButtons();
      renderList();
    });
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

  if (els.formationDetail) {
    els.formationDetail.addEventListener("click", (e) => {
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

  document.addEventListener("click", (e) => {
    if (!els.menuPanel || !els.menuButton || els.menuPanel.hidden) return;
    if (e.target.closest("#menuButton") || e.target.closest("#menuPanel")) return;
    closeMenuPanel();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeMenuPanel();
    closeLoginModal();
    closeFormationModal();
    closeSlotModal();
  });
}

async function init() {
  loadCloudConfig();
  buildSortOptions();
  updateCoachModeButtons();
  bindEvents();

  const res = await fetch("./formations_data.json");
  const data = await res.json();
  formations = Array.isArray(data.formations) ? data.formations : [];
  coaches = Array.isArray(data.coaches) ? data.coaches : [];
  buildCoachFilter();
  updateMenuState();
  renderList();
}

init().catch((e) => {
  if (els.metaText) {
    els.metaText.textContent = "Failed to load formations.";
  }
  console.error(e);
});
