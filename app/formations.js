const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-22 02:59 JST";

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
let playerCategoryById = new Map();
let playerRateById = new Map();
let filteredAndSorted = [];
let currentFormation = null;
let slotTopSortMode = "usage";

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

function normalizeCategory(value) {
  const c = String(value || "").trim().toUpperCase();
  return c || "-";
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
  const category = getCcCategoryLabelByPlayerId(id);
  const rate = Number(playerRateById.get(id));
  const c = normalizeCategory(category);
  return `<span class="badge type-badge ${categoryBadgeClass(c, rate)}">${c}</span>`;
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

function applyFilterAndSort() {
  const sortKey = els.sortKey?.value || "cc.usageRate";
  const sortDir = els.sortDir?.value === "asc" ? 1 : -1;
  const coachId = Number(els.coachFilter?.value || 0);

  let rows = formations.slice();
  if (coachId > 0) {
    rows = rows.filter((f) => {
      const list = f.coaches?.depth4 || [];
      return list.some((c) => Number(c?.id) === coachId || Number(c?.coachId) === coachId);
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
    els.formationCount.textContent = `${filteredAndSorted.length} formations`;
  }
}

function renderFormationPitch(positions, formationId) {
  const minX = 1;
  const maxX = 321;
  const minY = 2;
  const maxY = 337;
  const padLeft = 10;
  const padRight = 10;
  const padTop = 14;
  const padBottom = 8;
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

function renderSlotTop(slotStats, mode = "usage") {
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
                <strong class="slot-top-name">${top.playerName}</strong>
                <span class="slot-top-statline">
                  ${categoryBadgeHtmlByPlayerId(top.playerId)}
                  <span>Usage ${pct(top.usageRate)} / Avg ${avg(top.avgPts)}</span>
                </span>
              </div>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderCoachRanking(coachStats) {
  const rows = Array.isArray(coachStats) ? coachStats : [];
  if (!rows.length) {
    return `<p class="dim">No coach usage data.</p>`;
  }
  return `
    <div class="formation-slot-top-list">
      ${rows
        .map((c, idx) => {
          const imgSrc = `./images/chara/headcoaches/static/${c.coachId}@2x.gif`;
          return `
            <div class="slot-top-row coach-top-row">
              <span class="slot-top-slotno">#${idx + 1}</span>
              <div class="slot-top-thumb">
                <img loading="lazy" src="${imgSrc}" alt="${c.coachName}" />
              </div>
              <div class="slot-top-meta">
                <strong class="slot-top-name">${c.coachName}</strong>
                <span>${pct(c.usageRate)} / ${avg(c.avgPts)} / ID ${c.coachId}</span>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
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

function openFormationModal(formation) {
  currentFormation = formation;
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
        </div>
      </div>
    </div>
    <div class="formation-detail-stack">
        <div class="formation-block">
          <h3>Formation Data</h3>
          ${renderFormationParamGrid(formation.params)}
        </div>
        <div class="formation-block">
          <h3>Depth 4 Coaches</h3>
          <div>${renderCoachesList(formation.coaches?.depth4)}</div>
        </div>
    </div>
    <div class="formation-block">
      <h3>Key Positions</h3>
      ${renderKeyPositions(formation.keyPositions || [])}
    </div>
    <div class="formation-block">
      <div class="slot-top-toolbar">
        <h3>CC Slot Top Player (#1)</h3>
        <div class="slot-top-sort-switch" role="group" aria-label="CC Slot Top sort mode">
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "usage" ? " is-on" : ""}" data-slot-top-sort="usage">Usage</button>
          <button type="button" class="slot-top-sort-btn${slotTopSortMode === "avg" ? " is-on" : ""}" data-slot-top-sort="avg">Avg</button>
        </div>
      </div>
      ${renderSlotTop(formation.slotStats || {}, slotTopSortMode)}
    </div>
    <div class="formation-block">
      <h3>CC Coach Ranking</h3>
      ${renderCoachRanking(formation.coachStats)}
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
  const allRows = currentFormation.slotStats?.[String(slot)] || [];
  const rows = sortSlotRows(allRows, slotTopSortMode).slice(0, 20);
  els.slotTitle.textContent = `${currentFormation.name} / Slot ${slot}`;
  if (!rows.length) {
    els.slotDetail.innerHTML = `<p class="dim">No CC slot data.</p>`;
  } else {
    els.slotDetail.innerHTML = `
      <div class="slot-table-wrap">
        <table class="slot-table">
          <thead>
            <tr><th>#</th><th>Player</th><th>Cat</th><th>Usage</th><th>Avg</th></tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (r, idx) => `
                  <tr>
                    <td>${idx + 1}</td>
                    <td>${r.playerName}</td>
                    <td>${categoryBadgeHtmlByPlayerId(r.playerId)}</td>
                    <td>${pct(r.usageRate)} (${r.uses})</td>
                    <td>${avg(r.avgPts)}</td>
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
  if (els.coachFilter) {
    els.coachFilter.addEventListener("change", renderList);
    els.coachFilter.addEventListener("input", renderList);
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
      const sortBtn = e.target.closest("[data-slot-top-sort]");
      if (sortBtn) {
        const mode = String(sortBtn.dataset.slotTopSort || "");
        if (mode === "usage" || mode === "avg") {
          slotTopSortMode = mode;
          if (currentFormation) openFormationModal(currentFormation);
        }
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
  bindEvents();

  const [formationsRes, playersRes] = await Promise.all([
    fetch("./formations_data.json"),
    fetch("./data.json").catch(() => null),
  ]);
  const formationData = await formationsRes.json();
  formations = Array.isArray(formationData.formations) ? formationData.formations : [];
  coaches = Array.isArray(formationData.coaches) ? formationData.coaches : [];
  if (playersRes && playersRes.ok) {
    try {
      const playersData = await playersRes.json();
      const rows = Array.isArray(playersData?.players) ? playersData.players : [];
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
    } catch (e) {
      console.warn(e);
    }
  }
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
