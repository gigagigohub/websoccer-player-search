const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const LINEUP_STORAGE_KEY = "ws_starting_eleven_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const LINEUP_SIZE = 11;
const LIFECYCLE_MODE_STORAGE_KEY = "ws_lifecycle_mode_v1";
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
  lifecycleToggle: document.querySelector("#lifecycleToggle"),
  advanceSeasonButton: document.querySelector("#advanceSeasonButton"),
  rewindSeasonButton: document.querySelector("#rewindSeasonButton"),
  emptySlotModal: document.querySelector("#emptySlotModal"),
  emptySlotBackdrop: document.querySelector("#emptySlotBackdrop"),
  emptySlotClose: document.querySelector("#emptySlotClose"),
  emptySlotOk: document.querySelector("#emptySlotOk"),
  playerCardModal: document.querySelector("#playerCardModal"),
  playerCardBackdrop: document.querySelector("#playerCardBackdrop"),
  playerCardHost: document.querySelector("#playerCardHost"),
  playerDeleteButton: document.querySelector("#playerDeleteButton"),
};

let players = [];
let lineup = Array.from({ length: LINEUP_SIZE }, () => null);
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };
let selectedSlotIndex = null;
let selectedPlayerId = null;
let selectedCardExpanded = false;
let lifecycleModeEnabled = false;

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
    els.lifecycleToggle.textContent = lifecycleModeEnabled ? "Lifecycle Mode: ON" : "Lifecycle Mode: OFF";
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
  const pos = (successorPlayer.position || "-").toUpperCase();
  const posClass = positionClass(pos);
  const typeLabel = getCategory(successorPlayer);
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

  if (!changed) return false;
  saveLineupLocal();
  if (hasCloudConfig()) {
    try {
      await saveCloudLineup();
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
    const typeLabel = player ? getCategory(player) : "-";
    const typeClass = player ? typeClassByPlayer(player) : "cat-na";
    const imageHtml = player
      ? `<img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${player.name}" />`
      : `<div class="lineup-empty-thumb"></div>`;
    const selectedPeriod = player ? findPeriodBySeason(player, season) : null;
    const selectedMetrics = selectedPeriod?.metrics || (player ? getPeakMetrics(player) : null);
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

    return `
      <button type="button" class="lineup-slot${player ? " has-player" : ""} myteam-slot" data-slot-index="${idx}">
        <span class="slot-no">${slot}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              <span class="badge type-badge ${typeClass}">${typeLabel}</span>
              ${seasonBadge}
            </div>
            <span class="slot-name">${name}</span>
          </div>
          ${rightPaneHtml}
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
  loadLifecycleMode();
  renderLifecycleControls();
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
      const ok = window.confirm("Advanceをタップすると、全選手の現在期を１期進めますがよろしいですか？（戻るボタンで戻せます）");
      if (!ok) return;
      await shiftAllLineupSeasons(1);
    });
  }
  if (els.rewindSeasonButton) {
    els.rewindSeasonButton.addEventListener("click", async () => {
      await shiftAllLineupSeasons(-1);
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
