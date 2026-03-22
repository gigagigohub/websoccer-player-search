const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const APP_UPDATED_AT_JST = "2026-03-22 20:39 JST";
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
  playerCardModal: document.querySelector("#playerCardModal"),
  playerCardBackdrop: document.querySelector("#playerCardBackdrop"),
  playerCardClose: document.querySelector("#playerCardClose"),
  playerCardHost: document.querySelector("#playerCardHost"),
};

let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let formations = [];
let coaches = [];
let playerCategoryById = new Map();
let playerRateById = new Map();
let playersById = new Map();
let filteredAndSorted = [];
let currentFormation = null;
let slotTopSortMode = "usage";
let selectedPlayerId = null;
const cardViewModeById = new Map();

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

function metricLabel(metric) {
  return METRIC_LABELS[metric] || metric;
}

function detailMetricLabel(metric) {
  return DETAIL_METRIC_LABELS[metric] || metric;
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

function getCategory(player) {
  if (player?.category) return String(player.category);
  return getCcCategoryLabelByPlayerId(player?.id);
}

function typeClassByPlayer(player) {
  const typeLabel = normalizeCategory(getCategory(player));
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
                <span>Usage ${pct(c.usageRate)} / Avg ${avg(c.avgPts)}</span>
              </div>
            </div>
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
  const playType = player.playType || "-";
  const height = Number(player.height);
  const weight = Number(player.weight);
  const hwText = `${Number.isFinite(height) && height > 0 ? height : "-"}cm / ${Number.isFinite(weight) && weight > 0 ? weight : "-"}kg`;
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
  const typeLabel = getCategory(player);
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
  const params = new URLSearchParams(window.location.search || "");
  if (params.get("returnTo") === "myteam") {
    window.location.href = "./myteam.html";
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
                  <tr class="slot-player-row" data-player-id="${r.playerId}">
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
  if (els.playerCardBackdrop) els.playerCardBackdrop.addEventListener("click", closePlayerCardModal);
  if (els.playerCardClose) els.playerCardClose.addEventListener("click", closePlayerCardModal);

  if (els.slotDetail) {
    els.slotDetail.addEventListener("click", (e) => {
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
    closePlayerCardModal();
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
      playersById = new Map(
        rows
          .map((p) => [Number(p?.id), p])
          .filter(([id]) => Number.isInteger(id))
      );
    } catch (e) {
      console.warn(e);
    }
  }
  buildCoachFilter();
  updateMenuState();
  renderList();
  tryOpenFormationFromQuery();
}

init().catch((e) => {
  if (els.metaText) {
    els.metaText.textContent = "Failed to load formations.";
  }
  console.error(e);
});
