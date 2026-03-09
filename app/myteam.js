const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const LINEUP_STORAGE_KEY = "ws_starting_eleven_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const LINEUP_SIZE = 11;
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
  myteamLogoutButton: document.querySelector("#myteamLogoutButton"),
  myTeamMeta: document.querySelector("#myTeamMeta"),
  myTeamTarget: document.querySelector("#myTeamTarget"),
  myTeamSlots: document.querySelector("#myTeamSlots"),
  emptySlotModal: document.querySelector("#emptySlotModal"),
  emptySlotBackdrop: document.querySelector("#emptySlotBackdrop"),
  emptySlotClose: document.querySelector("#emptySlotClose"),
  emptySlotOk: document.querySelector("#emptySlotOk"),
  playerCardModal: document.querySelector("#playerCardModal"),
  playerCardBackdrop: document.querySelector("#playerCardBackdrop"),
  playerCardClose: document.querySelector("#playerCardClose"),
  playerCardHost: document.querySelector("#playerCardHost"),
  playerDeleteButton: document.querySelector("#playerDeleteButton"),
};

let players = [];
let lineup = Array.from({ length: LINEUP_SIZE }, () => null);
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let selectedSlotIndex = null;
let selectedPlayerId = null;
let selectedCardExpanded = false;

function metricLabel(metric) {
  return METRIC_LABELS[metric] || metric;
}

function detailMetricLabel(metric) {
  return DETAIL_METRIC_LABELS[metric] || metric;
}

function closeMenuPanel() {
  if (!els.myteamMenuPanel) return;
  els.myteamMenuPanel.hidden = true;
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function normalizeLineupArray(parsed) {
  return Array.from({ length: LINEUP_SIZE }, (_, i) => {
    const row = parsed?.[i];
    if (row == null) return null;
    if (typeof row === "number" || typeof row === "string") {
      const id = Number(row);
      return Number.isInteger(id) ? { playerId: id, season: null } : null;
    }
    if (typeof row === "object") {
      const id = Number(row.playerId);
      if (!Number.isInteger(id)) return null;
      const season = row.season == null ? null : String(row.season);
      return { playerId: id, season };
    }
    return null;
  });
}

function saveLineupLocal() {
  localStorage.setItem(LINEUP_STORAGE_KEY, JSON.stringify(lineup));
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
  if (!Array.isArray(rows) || !rows.length) return false;
  const remote = rows[0]?.lineup_json;
  if (!Array.isArray(remote)) return false;
  lineup = normalizeLineupArray(remote);
  saveLineupLocal();
  return true;
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
    return [first.metric, tie[0]];
  }

  return [first.metric, second.metric];
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
  const html = lineup.map((entry, idx) => {
    const slot = idx + 1;
    const playerId = Number(entry?.playerId);
    const player = Number.isInteger(playerId) ? players.find((x) => x.id === playerId) : null;
    const name = player ? player.name : "未登録";
    const season = player ? (entry?.season || null) : null;
    const seasonText = season ? `${season}目` : "-";
    const pos = (player?.position || "-").toUpperCase();
    const posClass = positionClass(pos);
    const typeLabel = player ? getCategory(player) : "-";
    const typeClass = player ? typeClassByPlayer(player) : "cat-na";
    const imageHtml = player
      ? `<img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${player.name}" />`
      : `<div class="lineup-empty-thumb"></div>`;
    const selectedPeriod = player ? findPeriodBySeason(player, season) : null;
    const selectedMetrics = selectedPeriod?.metrics || (player ? getPeakMetrics(player) : null);
    const coreHtml = player ? `
      <div class="lineup-core">
        ${miniCoreMetric("スピ", selectedMetrics?.["スピ"])}
        ${miniCoreMetric("テク", selectedMetrics?.["テク"])}
        ${miniCoreMetric("パワ", selectedMetrics?.["パワ"])}
      </div>
    ` : "";

    return `
      <button type="button" class="lineup-slot${player ? " has-player" : ""} myteam-slot" data-slot-index="${idx}">
        <span class="slot-no">${slot}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              <span class="badge type-badge ${typeClass}">${typeLabel}</span>
              <span class="badge lineup-season">${seasonText}</span>
            </div>
            <span class="slot-name">${name}</span>
          </div>
          ${coreHtml}
        </div>
      </button>
    `;
  }).join("");
  els.myTeamSlots.innerHTML = html;
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

  const items = segments.map((seg) => {
    const label = seg?.label || "";
    const grid = Array.isArray(seg?.grid) ? seg.grid : [];
    const outRows = grid.slice(0, 4);
    const outCells = outRows.map((row, rIdx) => {
      const rowCells = (Array.isArray(row) ? row : []).slice(0, 3).map((v, cIdx) => {
        if (v == null) return "";
        const n = Math.max(1, Math.min(7, Number(v) || 1));
        return `<div class="hm-cell hm-l${n}" style="--r:${rIdx};--c:${cIdx}">${n}</div>`;
      }).join("");
      return rowCells;
    }).join("");

    const gkVal = grid?.[4]?.[1];
    const gkCell = (isGK && gkVal != null)
      ? `<div class="gk-cell hm-l${Math.max(1, Math.min(7, Number(gkVal) || 1))}">${gkVal}</div>`
      : "";

    return `
      <div class="pos-heatmap-seg">
        <div class="pos-heatmap-label">${label}</div>
        <div class="pitch-map ${isGK ? "is-gk" : "is-fp"}">
          <div class="pitch-lines"></div>
          <div class="hm-grid">${outCells}</div>
          ${gkCell}
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

function playerCardHtml(player, season, expanded) {
  const staticImg = `./images/chara/players/static/${player.id}.gif`;
  const actionImg = `./images/chara/players/action/${player.id}.gif`;
  const selectedPeriod = findPeriodBySeason(player, season);
  const displayMetrics = selectedPeriod?.metrics || getPeakMetrics(player);
  const currentSeasonText = season ? `${season}目` : "-";
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
  const nTop = Math.max(0, Math.min(30, mind.zisei)) / 30;
  const nRight = Math.max(0, Math.min(30, mind.soshiki)) / 30;
  const nBottom = Math.max(0, Math.min(30, mind.kansei)) / 30;
  const nLeft = Math.max(0, Math.min(30, mind.kojin)) / 30;
  const pTop = `${cx},${cy - r * nTop}`;
  const pRight = `${cx + r * nRight},${cy}`;
  const pBottom = `${cx},${cy + r * nBottom}`;
  const pLeft = `${cx - r * nLeft},${cy}`;
  const areaPoints = `${pTop} ${pRight} ${pBottom} ${pLeft}`;

  const collapsedHtml = `
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
    <div class="metrics-wrap">
      <div class="metrics main-3">${mainMetrics.map(metricBox).join("")}</div>
      <div class="metric-group">
        <div class="metrics group-4">${group2.map(metricBox).join("")}</div>
      </div>
      <div class="metric-group">
        <div class="metrics group-4">${group1.map(metricBox).join("")}</div>
      </div>
    </div>
  `;

  const bodyHtml = expanded ? periodTableHtml(player, staticImg, actionImg, season) : collapsedHtml;

  return `
    <article class="card ${expanded ? "is-expanded" : "is-collapsed"}" data-player-id="${player.id}">
      <div class="card-top">
        <button type="button" class="expand-toggle" data-player-id="${player.id}" aria-label="詳細表示切替">${expanded ? "−" : "+"}</button>
        <span class="card-id">ID: ${player.id}</span>
        <div class="card-head-main">
          <h3 class="card-name">
            <span class="badge pos-badge ${posClass}">${pos}</span>
            <span class="badge type-badge ${typeClass}">${typeLabel}</span>
            <span>${player.name}</span>
            <span class="myteam-current-season">${currentSeasonText}</span>
          </h3>
          <div class="peak-periods">${peakHtml}</div>
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
  const season = lineup[selectedSlotIndex]?.season || null;
  els.playerCardHost.innerHTML = playerCardHtml(player, season, selectedCardExpanded);
}

function openPlayerCardModal(slotIndex) {
  const entry = lineup[slotIndex];
  const playerId = Number(entry?.playerId);
  if (!Number.isInteger(playerId)) return;
  selectedSlotIndex = slotIndex;
  selectedPlayerId = playerId;
  selectedCardExpanded = false;
  renderPlayerCardModal();
  if (els.playerCardModal) els.playerCardModal.hidden = false;
}

function closePlayerCardModal() {
  selectedSlotIndex = null;
  selectedPlayerId = null;
  selectedCardExpanded = false;
  if (els.playerCardModal) els.playerCardModal.hidden = true;
}

async function deleteSelectedFromTeam() {
  if (!Number.isInteger(selectedSlotIndex)) return;
  lineup[selectedSlotIndex] = null;
  saveLineupLocal();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup();
    } catch (e) {
      console.warn(e);
    }
  }
  renderLineup();
  closePlayerCardModal();
}

async function init() {
  loadCloudConfig();
  if (els.myteamMenuButton) {
    els.myteamMenuButton.addEventListener("click", () => {
      if (!els.myteamMenuPanel) return;
      els.myteamMenuPanel.hidden = !els.myteamMenuPanel.hidden;
    });
  }
  if (els.myteamDatabaseButton) {
    els.myteamDatabaseButton.addEventListener("click", () => {
      window.location.href = "./index.html";
    });
  }
  if (els.myteamLogoutButton) {
    els.myteamLogoutButton.addEventListener("click", () => {
      logoutTeamId();
      window.location.href = "./index.html";
    });
  }
  document.addEventListener("click", (e) => {
    if (!els.myteamMenuPanel || !els.myteamMenuButton) return;
    if (els.myteamMenuPanel.hidden) return;
    if (e.target.closest("#myteamMenuButton") || e.target.closest("#myteamMenuPanel")) return;
    closeMenuPanel();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeMenuPanel();
      closeEmptySlotModal();
      closePlayerCardModal();
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
  if (els.playerDeleteButton) els.playerDeleteButton.addEventListener("click", deleteSelectedFromTeam);
  if (els.playerCardHost) {
    els.playerCardHost.addEventListener("click", (e) => {
      const btn = e.target.closest(".expand-toggle");
      if (!btn) return;
      selectedCardExpanded = !selectedCardExpanded;
      renderPlayerCardModal();
    });
  }

  const dataRes = await fetch("./data.json");
  const data = await dataRes.json();
  players = data.players || [];

  if (!hasCloudConfig()) {
    if (els.myTeamTarget) els.myTeamTarget.textContent = "TeamIDが未設定です（先にLoginしてください）";
    if (els.myTeamMeta) els.myTeamMeta.textContent = "Not logged in";
    renderLineup();
    return;
  }

  if (els.myTeamMeta) els.myTeamMeta.textContent = `TeamID: ${cloudConfig.lineupKey}`;
  if (els.myTeamTarget) els.myTeamTarget.textContent = "現在のスタメン";
  try {
    await loadCloudLineup();
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
      const playerId = Number(entry?.playerId);
      if (!Number.isInteger(playerId)) {
        openEmptySlotModal();
        return;
      }
      openPlayerCardModal(idx);
    });
  }
}

init().catch((e) => {
  if (els.myTeamTarget) els.myTeamTarget.textContent = "データ読み込みに失敗しました";
  console.error(e);
});
