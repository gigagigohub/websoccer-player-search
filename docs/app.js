const METRICS = [
  "スピ", "テク", "パワ", "スタ", "ラフ", "個性", "人気",
  "PK", "FK", "CK", "CP", "知性", "感性", "個人", "組織"
];

const els = {
  metaText: document.querySelector("#metaText"),
  nameQuery: document.querySelector("#nameQuery"),
  logicMode: document.querySelector("#logicMode"),
  sortKey: document.querySelector("#sortKey"),
  conditions: document.querySelector("#conditions"),
  addCondition: document.querySelector("#addCondition"),
  resetCondition: document.querySelector("#resetCondition"),
  resultCount: document.querySelector("#resultCount"),
  results: document.querySelector("#results"),
  conditionTemplate: document.querySelector("#conditionTemplate"),
};

let players = [];

function createSortOptions() {
  const options = [
    ["bestTotal:desc", "総合値(スピ+テク+パワ) 高い順"],
    ["bestTotal:asc", "総合値(スピ+テク+パワ) 低い順"],
    ["name:asc", "名前順(昇順)"],
    ["name:desc", "名前順(降順)"],
  ];
  METRICS.forEach((m) => {
    options.push([`metric:${m}:desc`, `${m} 高い順`]);
    options.push([`metric:${m}:asc`, `${m} 低い順`]);
  });

  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    els.sortKey.appendChild(option);
  }

  els.sortKey.value = "bestTotal:desc";
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
  const conditions = getConditions();

  return players.filter((player) => {
    if (query && !player.name.toLowerCase().includes(query)) {
      return false;
    }

    if (!conditions.length) {
      return true;
    }

    const checks = conditions.map((c) => checkCondition(player, c));
    return logicMode === "AND" ? checks.every(Boolean) : checks.some(Boolean);
  });
}

function compareBySortKey(a, b, sortKey) {
  if (sortKey.startsWith("bestTotal:")) {
    const dir = sortKey.endsWith(":asc") ? 1 : -1;
    return (a.bestTotal - b.bestTotal) * dir || a.name.localeCompare(b.name, "ja");
  }

  if (sortKey.startsWith("name:")) {
    const dir = sortKey.endsWith(":asc") ? 1 : -1;
    return a.name.localeCompare(b.name, "ja") * dir;
  }

  if (sortKey.startsWith("metric:")) {
    const [, metric, direction] = sortKey.split(":");
    const dir = direction === "asc" ? 1 : -1;
    const av = a.maxMetrics?.[metric] ?? Number.NEGATIVE_INFINITY;
    const bv = b.maxMetrics?.[metric] ?? Number.NEGATIVE_INFINITY;
    return (av - bv) * dir || a.name.localeCompare(b.name, "ja");
  }

  return 0;
}

function cardHtml(player) {
  const staticImg = `https://caselli.websoccer.info/images/chara/players/static/${player.id}.gif`;
  const actionImg = `https://caselli.websoccer.info/images/chara/players/action/${player.id}.gif`;
  const metricBlocks = METRICS.map((metric) => {
    const v = player.maxMetrics?.[metric];
    return `
      <div class="metric-box">
        <span class="metric-key">${metric}</span>
        <span class="metric-val">${v == null ? "-" : v}</span>
      </div>
    `;
  }).join("");

  return `
    <article class="card">
      <div class="card-top">
        <div class="card-head-left">
          <div class="thumbs">
            <img loading="lazy" src="${staticImg}" alt="${player.name} 静止" />
            <img loading="lazy" src="${actionImg}" alt="${player.name} アクション" />
          </div>
          <h3 class="card-name"><a href="${player.url}" target="_blank" rel="noreferrer">${player.name}</a></h3>
        </div>
        <div class="card-head-right">
          <span class="badge">ID: ${player.id}</span>
          <span class="badge">総合値: ${player.bestTotal}</span>
        </div>
      </div>
      <div class="metrics">${metricBlocks}</div>
    </article>
  `;
}

function render() {
  const filtered = filterPlayers();
  const sortKey = els.sortKey.value;
  filtered.sort((a, b) => compareBySortKey(a, b, sortKey));

  els.resultCount.textContent = `${filtered.length}件`;
  els.results.innerHTML = filtered.map(cardHtml).join("");
}

async function init() {
  createSortOptions();
  addConditionRow({ metric: "スピ", op: "gte", value1: 10 });

  [els.nameQuery, els.logicMode, els.sortKey].forEach((el) => {
    el.addEventListener("input", render);
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
