const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
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
  stocksButton: document.querySelector("#stocksButton"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  stockSummary: document.querySelector("#stockSummary"),
  stockQuery: document.querySelector("#stockQuery"),
  stockSuggestions: document.querySelector("#stockSuggestions"),
  stockCount: document.querySelector("#stockCount"),
  stockList: document.querySelector("#stockList"),
};

let payload = null;
let stocks = [];
let filteredStocks = [];
let playerSuggestions = [];
let highlightedSuggestion = -1;
let committedQuery = "";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function toHiragana(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .trim()
    .toLowerCase()
    .replace(/[\u30a1-\u30f6]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0x60))
    .replace(/[・･·\.．]/g, "")
    .replace(/\s+/g, "");
}

function formatNumber(value) {
  return new Intl.NumberFormat("ja-JP").format(Number(value || 0));
}

function formatJst(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso || "");
  const parts = Object.fromEntries(new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} JST`;
}

function loadCloudConfig() {
  try {
    return JSON.parse(localStorage.getItem(CLOUD_CONFIG_STORAGE_KEY) || "{}");
  } catch (_error) {
    return {};
  }
}

function updateMenuState() {
  const config = loadCloudConfig();
  const lineupKey = String(config.lineupKey || "").trim();
  const loggedIn = Boolean(lineupKey);
  if (els.loginButton) els.loginButton.hidden = loggedIn;
  if (els.logoutButton) els.logoutButton.hidden = !loggedIn;
  if (els.menuLoginId) {
    els.menuLoginId.hidden = !loggedIn;
    els.menuLoginId.textContent = loggedIn ? `Team ID：${lineupKey}` : "";
  }
}

function closeMenuPanel() {
  if (els.menuPanel) els.menuPanel.classList.remove("is-open");
}

function renderMeta() {
  if (!payload || !els.metaText) return;
  const source = payload.source || {};
  els.metaText.innerHTML = [
    `<span class="meta-line">Inventory: ${escapeHtml(formatJst(payload.generatedAt))}</span>`,
    `<span class="meta-line">Game S${escapeHtml(source.gameSeason)}</span>`,
  ].join("");
}

function renderSummary() {
  if (!payload || !els.stockSummary) return;
  const summary = payload.summary || {};
  const items = [
    ["Outside A-X", summary.stockCards, "cards"],
    ["External reserve", summary.externalReserveCards, "cards"],
    ["Player × term", summary.stockTypes, "types"],
    ["Numbered Teams", summary.teamsWithStock, "teams"],
  ];
  els.stockSummary.innerHTML = items.map(([label, value, unit]) => `
    <div class="stock-summary-card">
      <span>${escapeHtml(label)}</span>
      <strong>${formatNumber(value)}</strong>
      <small>${escapeHtml(unit)}</small>
    </div>
  `).join("");

}

function buildPlayerSuggestions() {
  const byName = new Map();
  stocks.forEach((row) => {
    const key = toHiragana(row.name);
    if (!key) return;
    if (!byName.has(key)) {
      byName.set(key, {
        name: String(row.name),
        nameRubies: new Set(),
        cards: 0,
        terms: new Set(),
      });
    }
    const item = byName.get(key);
    if (row.nameRuby) item.nameRubies.add(String(row.nameRuby));
    item.cards += Number(row.count || 0);
    item.terms.add(Number(row.currentTerm || 0));
  });
  playerSuggestions = [...byName.values()].map((item) => ({
    name: item.name,
    nameRubies: [...item.nameRubies],
    cards: item.cards,
    termCount: item.terms.size,
  })).sort((a, b) => String(a.name).localeCompare(String(b.name), "ja"));
}

function matchingSuggestions(query) {
  const normalizedQuery = toHiragana(query);
  if (!normalizedQuery) return [];
  return playerSuggestions
    .filter((item) => toHiragana([item.name, ...item.nameRubies].join("")).includes(normalizedQuery))
    .sort((a, b) => {
      const aStarts = toHiragana(a.name).startsWith(normalizedQuery) ? 0 : 1;
      const bStarts = toHiragana(b.name).startsWith(normalizedQuery) ? 0 : 1;
      return aStarts - bStarts || String(a.name).localeCompare(String(b.name), "ja");
    })
    .slice(0, 12);
}

function closeSuggestions() {
  highlightedSuggestion = -1;
  els.stockSuggestions.hidden = true;
  els.stockSuggestions.innerHTML = "";
  els.stockQuery.setAttribute("aria-expanded", "false");
}

function updateSuggestionHighlight() {
  const buttons = [...els.stockSuggestions.querySelectorAll("button")];
  buttons.forEach((button, index) => {
    const selected = index === highlightedSuggestion;
    button.classList.toggle("is-highlighted", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
    if (selected) button.scrollIntoView({ block: "nearest" });
  });
}

function renderSuggestions() {
  const matches = matchingSuggestions(els.stockQuery.value);
  highlightedSuggestion = -1;
  if (!matches.length) {
    closeSuggestions();
    return;
  }
  els.stockSuggestions.innerHTML = matches.map((item) => `
    <button type="button" role="option" data-player-name="${escapeHtml(item.name)}" aria-selected="false">
      <strong>${escapeHtml(item.name)}</strong>
      <em>${formatNumber(item.termCount)} terms · ${formatNumber(item.cards)} cards</em>
    </button>
  `).join("");
  els.stockSuggestions.hidden = false;
  els.stockQuery.setAttribute("aria-expanded", "true");
}

function selectSuggestion(name) {
  els.stockQuery.value = String(name || "");
  closeSuggestions();
  applyExactNameFilter(name);
  els.stockQuery.focus();
}

function applyExactNameFilter(rawQuery = els.stockQuery.value) {
  const query = toHiragana(rawQuery);
  committedQuery = query;
  filteredStocks = query
    ? stocks.filter((row) => {
      const playerName = toHiragana(row.name);
      const playerNameRuby = toHiragana(row.nameRuby);
      return playerName === query || (playerNameRuby && playerNameRuby === query);
    })
      .sort((a, b) => String(a.name).localeCompare(String(b.name), "ja")
        || Number(a.currentTerm) - Number(b.currentTerm)
        || Number(a.playerId) - Number(b.playerId))
    : [];
  renderStocks();
}

function positionClass(position) {
  const normalized = String(position || "").toLowerCase();
  return ["gk", "df", "mf", "fw"].includes(normalized) ? `pos-${normalized}` : "";
}

function categoryClass(row, category) {
  if (category === "NR") {
    const rate = Number(row.rate || 0);
    if (rate === 7) return "cat-nr-r7";
    if (rate === 5 || rate === 6) return "cat-nr-r56";
    if (rate === 4) return "cat-nr-r4";
    return "cat-nr-r13";
  }
  if (category === "SS") return "cat-ss";
  if (category === "CM") return "cat-cm";
  if (category === "CM/SS") return "cat-cmss";
  if (category === "CC") return "cat-cc";
  return "cat-na";
}

function renderCategoryBadges(row) {
  const primary = String(row.category || "");
  const memberships = (row.categoryMembership || []).map(String);
  if (primary === "CM/SS") {
    return '<span class="badge type-badge cat-ss">SS</span><span class="badge type-badge cat-cm">CM</span>';
  }
  if (primary === "NR" && memberships.includes("CM")) {
    return `<span class="badge type-badge ${categoryClass(row, "NR")}">NR</span><span class="badge type-badge cat-cm">CM</span>`;
  }
  const categories = primary ? [primary] : memberships.slice(0, 1);
  return categories.map((category) => `
    <span class="badge type-badge ${categoryClass(row, category)}">${escapeHtml(category)}</span>
  `).join("");
}

function playerImageSrc(row, kind) {
  if (row.imagePending) return "./images/chara/players/pending.svg";
  const safeKind = kind === "action" ? "action" : "static";
  return `./images/chara/players/${safeKind}/${encodeURIComponent(row.playerId)}.gif`;
}

function renderMetric(metric, value) {
  const labels = { "パワ": "P", "テク": "T", "スピ": "S" };
  const fullLabels = { "パワ": "パワー", "テク": "テクニック", "スピ": "スピード" };
  const classes = { "パワ": "m-power", "テク": "m-tech", "スピ": "m-speed" };
  const numericValue = Number(value);
  const hasValue = Number.isFinite(numericValue);
  const displayValue = hasValue ? numericValue : "–";
  const bounded = hasValue ? Math.max(0, Math.min(10, Math.round(numericValue))) : 0;
  const cells = Array.from({ length: 10 }, (_, index) =>
    `<span class="gauge-cell${index < bounded ? " on" : ""}"></span>`
  ).join("");
  const label = labels[metric] || String(metric || "");
  const fullLabel = fullLabels[metric] || label;
  return `
    <div class="stock-metric ${classes[metric] || ""}" aria-label="${escapeHtml(fullLabel)} ${escapeHtml(displayValue)}">
      <span class="stock-metric-key" aria-hidden="true">${escapeHtml(label)}</span>
      <div class="stock-metric-body">
        <div class="gauge" aria-hidden="true">${cells}</div>
        <strong>${escapeHtml(displayValue)}</strong>
      </div>
    </div>
  `;
}

function renderTermStock(row) {
  const reserveManagementNos = new Set(row.externalReserveManagementNos || []);
  const metrics = row.termMetrics || {};
  return `
    <section class="stock-term-row">
      <div class="stock-term-summary">
        <div class="stock-term">${escapeHtml(row.currentTerm)}<small>期</small></div>
        <div class="stock-term-badges">
          ${row.isPeak ? '<span class="stock-state-badge stock-peak-badge">PEAK</span>' : ""}
          ${Number(row.externalReserveCount || 0) > 0 ? `<span class="stock-state-badge stock-reserve-badge">RESERVE ×${formatNumber(row.externalReserveCount)}</span>` : ""}
        </div>
      </div>
      <div class="stock-term-metrics">
        ${["スピ", "テク", "パワ"].map((metric) => renderMetric(metric, metrics[metric])).join("")}
      </div>
      <div class="stock-term-inventory">
        <div class="stock-count-block"><strong>${formatNumber(row.count)}</strong><span>cards</span></div>
        <div class="stock-management-nos">
          ${(row.managementNos || []).map((no) => reserveManagementNos.has(no)
            ? `<span class="is-reserve" title="外部予備">R · No.${escapeHtml(no)}</span>`
            : `<span>No.${escapeHtml(no)}</span>`).join("")}
        </div>
      </div>
    </section>
  `;
}

function renderPlayerStockCard(rows) {
  const orderedRows = [...rows].sort((a, b) => Number(a.currentTerm) - Number(b.currentTerm));
  const player = orderedRows[0];
  const pos = String(player.position || "–").toUpperCase();
  const totalCards = orderedRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
  return `
    <article class="stock-player-card" data-player-id="${escapeHtml(player.playerId)}">
      <div class="stock-player-card-head">
        <div class="stock-player-images">
          <img loading="lazy" src="${playerImageSrc(player, "static")}" alt="${escapeHtml(player.name)} 静止" />
          <img loading="lazy" src="${playerImageSrc(player, "action")}" alt="${escapeHtml(player.name)} アクション" />
        </div>
        <div class="stock-player-identity">
          <h3 class="stock-player-card-name">
            ${player.position ? `<span class="badge pos-badge ${positionClass(pos)}">${escapeHtml(pos)}</span>` : ""}
            ${renderCategoryBadges(player)}
            <span>${escapeHtml(player.name)}</span>
          </h3>
          <div class="stock-player-card-meta">
            <span>ID ${escapeHtml(player.playerId)}</span>
            <span>${formatNumber(orderedRows.length)} terms</span>
            <span>${formatNumber(totalCards)} cards</span>
          </div>
        </div>
      </div>
      <div class="stock-term-list">
        ${orderedRows.map(renderTermStock).join("")}
      </div>
    </article>
  `;
}

function renderStocks() {
  const totalCards = filteredStocks.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const groupedRows = new Map();
  filteredStocks.forEach((row) => {
    const key = String(row.playerId);
    if (!groupedRows.has(key)) groupedRows.set(key, []);
    groupedRows.get(key).push(row);
  });
  els.stockCount.textContent = `${formatNumber(groupedRows.size)} players / ${formatNumber(filteredStocks.length)} terms / ${formatNumber(totalCards)} cards`;
  const inputQuery = toHiragana(els.stockQuery.value);
  const emptyMessage = committedQuery
    ? "一致する選手在庫はありません。"
    : inputQuery
      ? "候補から選手を選択してください。"
      : "選手名を入力してください。";
  els.stockList.innerHTML = filteredStocks.length
    ? [...groupedRows.values()].map(renderPlayerStockCard).join("")
    : `<div class="stock-empty">${emptyMessage}</div>`;
}

function bindEvents() {
  els.menuButton.addEventListener("click", () => els.menuPanel.classList.toggle("is-open"));
  els.playersButton.addEventListener("click", () => { window.location.href = "./index.html"; });
  els.coachesButton.addEventListener("click", () => { window.location.href = "./coaches.html"; });
  els.formationsButton.addEventListener("click", () => { window.location.href = "./formations.html"; });
  els.collectionsButton.addEventListener("click", () => { window.location.href = "./collections.html"; });
  els.myTeamButton.addEventListener("click", () => { window.location.href = "./myteam.html"; });
  els.stocksButton.addEventListener("click", closeMenuPanel);
  els.loginButton.addEventListener("click", () => { window.location.href = "./index.html?openLogin=1"; });
  els.logoutButton.addEventListener("click", () => {
    const config = loadCloudConfig();
    config.lineupKey = "";
    localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(config));
    closeMenuPanel();
    updateMenuState();
  });
  document.addEventListener("click", (event) => {
    if (!els.menuPanel.contains(event.target) && event.target !== els.menuButton) closeMenuPanel();
    if (!els.stockSuggestions.contains(event.target) && event.target !== els.stockQuery) closeSuggestions();
  });
  els.stockQuery.addEventListener("input", () => {
    committedQuery = "";
    filteredStocks = [];
    renderSuggestions();
    renderStocks();
  });
  els.stockQuery.addEventListener("focus", renderSuggestions);
  els.stockQuery.addEventListener("keydown", (event) => {
    const buttons = [...els.stockSuggestions.querySelectorAll("button")];
    if (event.key === "ArrowDown" && buttons.length) {
      event.preventDefault();
      highlightedSuggestion = Math.min(highlightedSuggestion + 1, buttons.length - 1);
      updateSuggestionHighlight();
    } else if (event.key === "ArrowUp" && buttons.length) {
      event.preventDefault();
      highlightedSuggestion = Math.max(highlightedSuggestion - 1, 0);
      updateSuggestionHighlight();
    } else if (event.key === "Enter" && !event.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      if (highlightedSuggestion >= 0 && buttons[highlightedSuggestion]) {
        selectSuggestion(buttons[highlightedSuggestion].dataset.playerName);
      } else {
        closeSuggestions();
        applyExactNameFilter();
      }
    } else if (event.key === "Escape") {
      closeSuggestions();
    }
  });
  els.stockSuggestions.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-player-name]");
    if (button) selectSuggestion(button.dataset.playerName);
  });
}

async function init() {
  updateMenuState();
  bindEvents();
  try {
    const response = await fetch("./ax_external_stock_data.json?v=20260904-player-inventory-v22", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    stocks = Array.isArray(payload.stocks) ? payload.stocks : [];
    renderMeta();
    renderSummary();
    buildPlayerSuggestions();
    renderStocks();
  } catch (error) {
    els.metaText.textContent = "Stock data unavailable";
    els.stockList.innerHTML = `<div class="stock-empty stock-error">在庫データを読み込めませんでした。${escapeHtml(error.message || error)}</div>`;
  }
}

init();
