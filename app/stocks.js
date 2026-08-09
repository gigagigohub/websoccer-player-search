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
  planSeasonBadge: document.querySelector("#planSeasonBadge"),
  stockSummary: document.querySelector("#stockSummary"),
  shortageNotice: document.querySelector("#shortageNotice"),
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

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function normalize(value) {
  return String(value ?? "").normalize("NFKC").trim().toLowerCase();
}

function formatNumber(value) {
  return new Intl.NumberFormat("ja-JP").format(Number(value || 0));
}

function formatPercent(value) {
  const percent = Number(value || 0) * 100;
  if (percent <= 0) return "–";
  return `${percent.toFixed(percent >= 10 ? 1 : 2).replace(/\.0$/, "")}%`;
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
    `<span class="meta-line">Stocks: ${escapeHtml(formatJst(payload.generatedAt))}</span>`,
    `<span class="meta-line">Game S${escapeHtml(source.gameSeason)} / Plan S${escapeHtml(source.planSeason)}</span>`,
  ].join("");
  if (els.planSeasonBadge) els.planSeasonBadge.textContent = `Plan S${source.planSeason || "–"}`;
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

  const shortages = payload.shortages || [];
  if (!els.shortageNotice) return;
  els.shortageNotice.hidden = shortages.length === 0;
  els.shortageNotice.innerHTML = shortages.length
    ? `<strong>Protected quota shortage:</strong> ${shortages.map((row) => `${escapeHtml(row.name)} ${row.currentTerm}期 ×${row.shortage}`).join(" / ")}`
    : "";
}

function buildPlayerSuggestions() {
  const byName = new Map();
  stocks.forEach((row) => {
    const key = normalize(row.name);
    if (!key) return;
    if (!byName.has(key)) {
      byName.set(key, {
        name: String(row.name),
        fullNames: new Set(),
        cards: 0,
        terms: new Set(),
      });
    }
    const item = byName.get(key);
    if (row.fullName) item.fullNames.add(String(row.fullName));
    item.cards += Number(row.count || 0);
    item.terms.add(Number(row.currentTerm || 0));
  });
  playerSuggestions = [...byName.values()].map((item) => ({
    name: item.name,
    fullNames: [...item.fullNames],
    cards: item.cards,
    termCount: item.terms.size,
  })).sort((a, b) => String(a.name).localeCompare(String(b.name), "ja"));
}

function matchingSuggestions(query) {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) return [];
  return playerSuggestions
    .filter((item) => normalize([item.name, ...item.fullNames].join(" ")).includes(normalizedQuery))
    .sort((a, b) => {
      const aStarts = normalize(a.name).startsWith(normalizedQuery) ? 0 : 1;
      const bStarts = normalize(b.name).startsWith(normalizedQuery) ? 0 : 1;
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
      <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.fullNames[0] || "")}</small></span>
      <em>${formatNumber(item.termCount)} terms · ${formatNumber(item.cards)} cards</em>
    </button>
  `).join("");
  els.stockSuggestions.hidden = false;
  els.stockQuery.setAttribute("aria-expanded", "true");
}

function selectSuggestion(name) {
  els.stockQuery.value = String(name || "");
  closeSuggestions();
  applyFilters();
  els.stockQuery.focus();
}

function applyFilters() {
  const query = normalize(els.stockQuery.value);
  filteredStocks = query
    ? stocks.filter((row) => normalize([row.name, row.fullName].join(" ")).includes(query))
      .sort((a, b) => String(a.name).localeCompare(String(b.name), "ja")
        || Number(a.currentTerm) - Number(b.currentTerm)
        || Number(a.playerId) - Number(b.playerId))
    : [];
  renderStocks();
}

function renderTemplateUses(row) {
  const uses = (row.templateUses || []).slice(0, 3);
  if (!uses.length) return '<span class="stock-template-empty">テンプレ採用なし</span>';
  return uses.map((use) => `
    <span>${escapeHtml(use.formation)} slot${escapeHtml(use.slot)} · ${formatPercent(use.usageRate)}</span>
  `).join("");
}

function renderStockCard(row) {
  const categories = row.categoryMembership?.length ? row.categoryMembership : [row.category].filter(Boolean);
  const reserveManagementNos = new Set(row.externalReserveManagementNos || []);
  return `
    <article class="stock-card">
      <div class="stock-card-main">
        <div class="stock-player-line">
          <div class="stock-player-copy">
            <div class="stock-player-name">${escapeHtml(row.name)}</div>
            <div class="stock-player-full">${escapeHtml(row.fullName)} · ID ${escapeHtml(row.playerId)}</div>
          </div>
          <div class="stock-term">${escapeHtml(row.currentTerm)}<small>期</small></div>
        </div>
        <div class="stock-badges">
          ${row.position ? `<span class="stock-badge position-${escapeHtml(row.position.toLowerCase())}">${escapeHtml(row.position)}</span>` : ""}
          ${categories.map((category) => `<span class="stock-badge">${escapeHtml(category)}</span>`).join("")}
          ${row.playType ? `<span class="stock-badge stock-type-badge">${escapeHtml(row.playType)}</span>` : ""}
          ${row.isPeak ? '<span class="stock-badge stock-peak-badge">PEAK</span>' : ""}
          ${Number(row.externalReserveCount || 0) > 0 ? `<span class="stock-badge stock-reserve-badge">RESERVE ×${formatNumber(row.externalReserveCount)}</span>` : ""}
        </div>
        <div class="stock-template-line">
          <strong>TPL ${formatPercent(row.templateUsageRate)}</strong>
          <div>${renderTemplateUses(row)}</div>
        </div>
      </div>
      <div class="stock-availability">
        <div class="stock-count-block"><strong>${formatNumber(row.count)}</strong><span>cards</span></div>
        <div class="stock-management-nos">
          ${(row.managementNos || []).map((no) => reserveManagementNos.has(no)
            ? `<span class="is-reserve" title="外部予備">R · No.${escapeHtml(no)}</span>`
            : `<span>No.${escapeHtml(no)}</span>`).join("")}
        </div>
      </div>
    </article>
  `;
}

function renderStocks() {
  const totalCards = filteredStocks.reduce((sum, row) => sum + Number(row.count || 0), 0);
  els.stockCount.textContent = `${formatNumber(filteredStocks.length)} types / ${formatNumber(totalCards)} cards`;
  els.stockList.innerHTML = filteredStocks.length
    ? filteredStocks.map(renderStockCard).join("")
    : `<div class="stock-empty">${normalize(els.stockQuery.value) ? "一致する選手在庫はありません。" : "選手名を入力してください。"}</div>`;
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
    renderSuggestions();
    applyFilters();
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
    } else if (event.key === "Enter" && highlightedSuggestion >= 0 && buttons[highlightedSuggestion]) {
      event.preventDefault();
      selectSuggestion(buttons[highlightedSuggestion].dataset.playerName);
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
    const response = await fetch("./ax_external_stock_data.json?v=20260809-search-stocks-v3", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    stocks = Array.isArray(payload.stocks) ? payload.stocks : [];
    renderMeta();
    renderSummary();
    buildPlayerSuggestions();
    applyFilters();
  } catch (error) {
    els.metaText.textContent = "Stock data unavailable";
    els.stockList.innerHTML = `<div class="stock-empty stock-error">在庫データを読み込めませんでした。${escapeHtml(error.message || error)}</div>`;
  }
}

init();
