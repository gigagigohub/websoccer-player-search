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

function metricLabel(metric) {
  return METRIC_LABELS[metric] || metric;
}

const els = {
  metaText: document.querySelector("#metaText"),
  nameQuery: document.querySelector("#nameQuery"),
  logicMode: document.querySelector("#logicMode"),
  positionFilter: document.querySelector("#positionFilter"),
  cmOnly: document.querySelector("#cmOnly"),
  ssOnly: document.querySelector("#ssOnly"),
  normalOnly: document.querySelector("#normalOnly"),
  conditions: document.querySelector("#conditions"),
  addCondition: document.querySelector("#addCondition"),
  resetCondition: document.querySelector("#resetCondition"),
  resultCount: document.querySelector("#resultCount"),
  results: document.querySelector("#results"),
  conditionTemplate: document.querySelector("#conditionTemplate"),
};

let players = [];

function toHiragana(s) {
  return (s || "")
    .replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60))
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

  [metric, op, value1, value2].forEach((e) => e.addEventListener("input", render));
  op.addEventListener("change", () => {
    syncBetween();
    render();
  });
  remove.addEventListener("click", () => {
    node.remove();
    render();
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

function checkCondition(player, condition) {
  const values = player.metricValues?.[condition.metric] || [];
  if (!values.length) return false;

  switch (condition.op) {
    case "eq":
      return values.some((v) => v === condition.value1);
    case "gte":
      return values.some((v) => v >= condition.value1);
    case "lte":
      return values.some((v) => v <= condition.value1);
    case "between":
      return values.some((v) => v >= condition.value1 && v <= condition.value2);
    default:
      return false;
  }
}

function filterPlayers() {
  const query = toHiragana(els.nameQuery.value.trim().toLowerCase());
  const logicMode = els.logicMode.value;
  const positionFilter = els.positionFilter.value;
  const cmOnly = els.cmOnly.checked;
  const ssOnly = els.ssOnly.checked;
  const normalOnly = els.normalOnly.checked;
  const conditions = getConditions();

  return players.filter((player) => {
    const playerName = toHiragana((player.name || "").toLowerCase());
    if (query && !playerName.includes(query)) {
      return false;
    }
    if (positionFilter && player.position !== positionFilter) {
      return false;
    }

    const hasCM = !!player.flags?.CM;
    const hasSS = !!player.flags?.SS;
    const isNormal = !hasCM && !hasSS;
    const hasCategoryFilter = cmOnly || ssOnly || normalOnly;
    if (hasCategoryFilter) {
      const categoryMatched =
        (cmOnly && hasCM) ||
        (ssOnly && hasSS) ||
        (normalOnly && isNormal);
      if (!categoryMatched) return false;
    }

    if (!conditions.length) {
      return true;
    }

    const checks = conditions.map((c) => checkCondition(player, c));
    return logicMode === "AND" ? checks.every(Boolean) : checks.some(Boolean);
  });
}

function cardHtml(player) {
  const staticImg = `./images/chara/players/static/${player.id}.gif`;
  const actionImg = `./images/chara/players/action/${player.id}.gif`;
  const metricBox = (metric) => {
    const v = player.maxMetrics?.[metric];
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
    zisei: player.maxMetrics?.["知性"] ?? 0,
    kansei: player.maxMetrics?.["感性"] ?? 0,
    kojin: player.maxMetrics?.["個人"] ?? 0,
    soshiki: player.maxMetrics?.["組織"] ?? 0,
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
  const hasCM = !!player.flags?.CM;
  const hasSS = !!player.flags?.SS;
  const typeLabel = hasCM && hasSS ? "CM/SS" : hasCM ? "CM" : hasSS ? "SS" : "NR";
  const pos = (player.position || "-").toUpperCase();
  const posClass =
    pos === "GK" ? "pos-gk" :
    pos === "DF" ? "pos-df" :
    pos === "MF" ? "pos-mf" :
    pos === "FW" ? "pos-fw" : "";

  return `
    <article class="card">
      <div class="card-top">
        <span class="card-id">ID: ${player.id}</span>
        <div class="card-head-main">
          <h3 class="card-name">
            <span class="badge pos-badge ${posClass}">${pos}</span>
            <span class="badge type-badge">${typeLabel}</span>
            <a href="${player.url}" target="_blank" rel="noreferrer">${player.name}</a>
          </h3>
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
    </article>
  `;
}

function render() {
  const filtered = filterPlayers();
  filtered.sort((a, b) => {
    const aNR = !a.flags?.CM && !a.flags?.SS;
    const bNR = !b.flags?.CM && !b.flags?.SS;
    if (aNR !== bNR) return aNR ? -1 : 1;
    return (b.bestTotal - a.bestTotal) || a.name.localeCompare(b.name, "ja");
  });

  els.resultCount.textContent = `${filtered.length}件`;
  els.results.innerHTML = filtered.map(cardHtml).join("");
}

async function init() {
  [els.nameQuery, els.logicMode, els.positionFilter].forEach((el) => {
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  });
  [els.cmOnly, els.ssOnly, els.normalOnly].forEach((el) => {
    el.addEventListener("change", render);
  });

  els.addCondition.addEventListener("click", () => {
    addConditionRow({ metric: "スピ", op: "gte", value1: "" });
    render();
  });

  els.resetCondition.addEventListener("click", () => {
    els.conditions.innerHTML = "";
    render();
  });

  const res = await fetch("./data.json");
  const data = await res.json();
  players = data.players || [];

  els.metaText.textContent = `取得元: ${data.source} / データ作成: ${data.generatedAt} / 選手数: ${players.length}`;
  render();
}

init().catch((e) => {
  els.metaText.textContent = "データ読み込みに失敗しました";
  console.error(e);
});
