const METRICS = [
  "スピ", "テク", "パワ", "スタ", "ラフ", "個性", "人気",
  "PK", "FK", "CK", "CP", "知性", "感性", "個人", "組織"
];

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
    option.textContent = m;
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
  const query = els.nameQuery.value.trim().toLowerCase();
  const logicMode = els.logicMode.value;
  const positionFilter = els.positionFilter.value;
  const cmOnly = els.cmOnly.checked;
  const ssOnly = els.ssOnly.checked;
  const normalOnly = els.normalOnly.checked;
  const conditions = getConditions();

  return players.filter((player) => {
    if (query && !player.name.toLowerCase().includes(query)) {
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
    const max = ["知性", "感性", "個人", "組織"].includes(metric) ? 30 : 10;
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    const metricClass =
      metric === "スピ" ? "m-speed" :
      metric === "テク" ? "m-tech" :
      metric === "パワ" ? "m-power" : "";
    return `
      <div class="metric-box ${metricClass}">
        <span class="metric-key">${metric}</span>
        <span class="metric-val">${v == null ? "-" : v}<small>/${max}</small></span>
        <div class="gauge">
          <span class="gauge-fill" style="width:${pct}%"></span>
        </div>
      </div>
    `;
  };

  const mainMetrics = ["スピ", "テク", "パワ"];
  const group1 = ["スタ", "ラフ", "個性", "人気"];
  const group2 = ["PK", "FK", "CK", "CP"];
  const group3 = ["知性", "感性", "個人", "組織"];
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
          <div class="thumbs">
            <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
            <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
          </div>
        </div>
      </div>
      <div class="metrics-wrap">
        <div class="metrics main-3">${mainMetrics.map(metricBox).join("")}</div>
        <div class="metric-group">
          <div class="metrics group-4">${group1.map(metricBox).join("")}</div>
        </div>
        <div class="metric-group">
          <div class="metrics group-4">${group2.map(metricBox).join("")}</div>
        </div>
        <div class="metric-group">
          <div class="metrics group-4">${group3.map(metricBox).join("")}</div>
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
  addConditionRow({ metric: "スピ", op: "gte", value1: 10 });

  [els.nameQuery, els.logicMode, els.positionFilter].forEach((el) => {
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  });
  [els.cmOnly, els.ssOnly, els.normalOnly].forEach((el) => {
    el.addEventListener("change", render);
  });

  els.addCondition.addEventListener("click", () => {
    addConditionRow({ metric: "テク", op: "gte", value1: "" });
    render();
  });

  els.resetCondition.addEventListener("click", () => {
    els.conditions.innerHTML = "";
    addConditionRow({ metric: "スピ", op: "gte", value1: 10 });
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
