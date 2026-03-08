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
  "CP": "CP",
};
const APP_UPDATED_AT_JST = "2026-03-08 20:26 JST";

function metricLabel(metric) {
  return METRIC_LABELS[metric] || metric;
}

function detailMetricLabel(metric) {
  return DETAIL_METRIC_LABELS[metric] || metric;
}

const els = {
  metaText: document.querySelector("#metaText"),
  nameQuery: document.querySelector("#nameQuery"),
  logicMode: document.querySelector("#logicMode"),
  positionFilter: document.querySelector("#positionFilter"),
  cmOnly: document.querySelector("#cmOnly"),
  ssOnly: document.querySelector("#ssOnly"),
  normalOnly: document.querySelector("#normalOnly"),
  naOnly: document.querySelector("#naOnly"),
  ccOnly: document.querySelector("#ccOnly"),
  applySearch: document.querySelector("#applySearch"),
  conditions: document.querySelector("#conditions"),
  addCondition: document.querySelector("#addCondition"),
  resetCondition: document.querySelector("#resetCondition"),
  resultCount: document.querySelector("#resultCount"),
  results: document.querySelector("#results"),
  conditionTemplate: document.querySelector("#conditionTemplate"),
};

let players = [];
const expandedPlayerIds = new Set();

function toHiragana(s) {
  return (s || "")
    .replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60))
    .replace(/[・･·\.．]/g, "")
    .replace(/\s+/g, "");
}

function addConditionRow(defaults = {}) {
  const node = els.conditionTemplate.content.firstElementChild.cloneNode(true);
  const metric = node.querySelector(".metric");
  const op = node.querySelector(".op");
  const value1 = node.querySelector(".value1");
  const value2 = node.querySelector(".value2");
  const remove = node.querySelector(".remove");

  METRICS.forEach((m) => {
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

function getMatchingPeriods(player, conditions, logicMode) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  if (!conditions.length) return periods;

  return periods.filter((period) => {
    const metrics = period?.metrics || {};
    const checks = conditions.map((c) => checkValueCondition(metrics[c.metric], c));
    return logicMode === "AND" ? checks.every(Boolean) : checks.some(Boolean);
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
    return [first.metric, tie[0]];
  }

  return [first.metric, second.metric];
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

function filterPlayers(conditions = getConditions(), logicMode = els.logicMode.value) {
  const query = toHiragana(els.nameQuery.value.trim().toLowerCase());
  const positionFilter = els.positionFilter.value;
  const cmOnly = els.cmOnly.checked;
  const ssOnly = els.ssOnly.checked;
  const normalOnly = els.normalOnly.checked;
  const naOnly = els.naOnly.checked;
  const ccOnly = els.ccOnly.checked;

  return players.filter((player) => {
    const category = getCategory(player);
    if (category === "RT") {
      return false;
    }
    const playerName = toHiragana((player.name || "").toLowerCase());
    if (query && !playerName.includes(query)) {
      return false;
    }
    if (positionFilter && player.position !== positionFilter) {
      return false;
    }

    const hasCategoryFilter = cmOnly || ssOnly || normalOnly || naOnly || ccOnly;
    if (hasCategoryFilter) {
      const categoryMatched =
        (normalOnly && category === "NR") ||
        (ssOnly && (category === "SS" || category === "CM/SS")) ||
        (cmOnly && (category === "CM" || category === "CM/SS")) ||
        (naOnly && category === "NA") ||
        (ccOnly && category === "CC");
      if (!categoryMatched) return false;
    }

    if (!conditions.length) {
      return true;
    }

    return getMatchingPeriods(player, conditions, logicMode).length > 0;
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

function cardHtml(player) {
  const staticImg = `./images/chara/players/static/${player.id}.gif`;
  const actionImg = `./images/chara/players/action/${player.id}.gif`;
  const displayMetrics = getPeakMetrics(player);
  const isExpanded = expandedPlayerIds.has(player.id);
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
  const typeLabel = getCategory(player);
  const typeClass =
    typeLabel === "NR" ? "cat-nr" :
    typeLabel === "SS" ? "cat-ss" :
    typeLabel === "CM" ? "cat-cm" :
    typeLabel === "CM/SS" ? "cat-cmss" :
    typeLabel === "CC" ? "cat-cc" :
    typeLabel === "NA" ? "cat-na" : "cat-na";
  const pos = (player.position || "-").toUpperCase();
  const posClass =
    pos === "GK" ? "pos-gk" :
    pos === "DF" ? "pos-df" :
    pos === "MF" ? "pos-mf" :
    pos === "FW" ? "pos-fw" : "";
  const normalViewHtml = `
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
  const detailViewHtml = periodTableHtml(player, staticImg, actionImg);
  const bodyHtml = isExpanded ? detailViewHtml : normalViewHtml;

  return `
    <article class="card ${isExpanded ? "is-expanded" : "is-collapsed"}" data-player-id="${player.id}">
      <div class="card-top">
        <button type="button" class="expand-toggle" data-player-id="${player.id}" aria-label="詳細表示切替">${isExpanded ? "−" : "+"}</button>
        <span class="card-id">ID: ${player.id}</span>
        <div class="card-head-main">
          <h3 class="card-name">
            <span class="badge pos-badge ${posClass}">${pos}</span>
            <span class="badge type-badge ${typeClass}">${typeLabel}</span>
            <span>${player.name}</span>
          </h3>
          <div class="peak-periods">${peakHtml}</div>
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
  const conditions = getConditions();
  const logicMode = els.logicMode.value;
  const filtered = filterPlayers(conditions, logicMode);
  const categoryRank = {
    "NR": 0,
    "CC": 1,
    "SS": 2,
    "CM": 3,
    "CM/SS": 3,
    "NA": 4,
    "RT": 99,
  };
  filtered.sort((a, b) => {
    const ar = categoryRank[getCategory(a)] ?? 50;
    const br = categoryRank[getCategory(b)] ?? 50;
    if (ar !== br) return ar - br;
    return (b.bestTotal - a.bestTotal) || a.name.localeCompare(b.name, "ja");
  });

  els.resultCount.textContent = `${filtered.length} results`;
  els.results.innerHTML = filtered.map((p) => cardHtml(p)).join("");
}

async function init() {
  els.addCondition.addEventListener("click", () => {
    addConditionRow({ metric: "スピ", op: "gte", value1: "" });
  });

  els.resetCondition.addEventListener("click", () => {
    els.conditions.innerHTML = "";
    els.normalOnly.checked = false;
    els.ssOnly.checked = false;
    els.cmOnly.checked = false;
    els.ccOnly.checked = false;
    els.naOnly.checked = false;
    els.positionFilter.value = "";
  });

  els.applySearch.addEventListener("click", render);
  els.results.addEventListener("click", (e) => {
    const btn = e.target.closest(".expand-toggle");
    if (!btn) return;
    const id = Number(btn.dataset.playerId);
    if (!Number.isInteger(id)) return;
    if (expandedPlayerIds.has(id)) {
      expandedPlayerIds.delete(id);
    } else {
      expandedPlayerIds.add(id);
    }
    rerenderSingleCard(id);
  });

  const res = await fetch("./data.json");
  const data = await res.json();
  players = data.players || [];

  els.metaText.textContent = `Updated: ${APP_UPDATED_AT_JST} / Players: ${players.length}`;
  els.resultCount.textContent = "0 results";
  els.results.innerHTML = "";
}

init().catch((e) => {
  els.metaText.textContent = "Failed to load data.";
  console.error(e);
});
