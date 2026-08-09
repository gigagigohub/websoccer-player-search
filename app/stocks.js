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
  stockPosition: document.querySelector("#stockPosition"),
  stockTerm: document.querySelector("#stockTerm"),
  stockCategory: document.querySelector("#stockCategory"),
  stockMinUsage: document.querySelector("#stockMinUsage"),
  stockSort: document.querySelector("#stockSort"),
  stockPeakOnly: document.querySelector("#stockPeakOnly"),
  stockTemplateOnly: document.querySelector("#stockTemplateOnly"),
  stockReset: document.querySelector("#stockReset"),
  stockCount: document.querySelector("#stockCount"),
  stockList: document.querySelector("#stockList"),
};

let payload = null;
let stocks = [];
let filteredStocks = [];

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

function populateFilters() {
  const terms = [...new Set(stocks.map((row) => Number(row.currentTerm || 0)).filter(Boolean))].sort((a, b) => a - b);
  const categories = [...new Set(stocks.flatMap((row) => row.categoryMembership?.length ? row.categoryMembership : [row.category]).filter(Boolean))].sort();
  els.stockTerm.insertAdjacentHTML("beforeend", terms.map((term) => `<option value="${term}">${term}期</option>`).join(""));
  els.stockCategory.insertAdjacentHTML("beforeend", categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join(""));
}

function stockHaystack(row) {
  return normalize([
    row.playerId,
    row.name,
    row.fullName,
    row.playType,
    row.position,
    row.category,
    ...(row.categoryMembership || []),
    ...(row.managementNos || []).flatMap((no) => [no, `No.${no}`]),
  ].join(" "));
}

function compareStocks(a, b) {
  const reserveOrder = Number(Number(b.externalReserveCount || 0) > 0)
    - Number(Number(a.externalReserveCount || 0) > 0);
  if (reserveOrder) return reserveOrder;
  const mode = els.stockSort.value;
  if (mode === "termAsc") {
    return Number(a.currentTerm) - Number(b.currentTerm)
      || Number(b.templateUsageRate) - Number(a.templateUsageRate)
      || String(a.name).localeCompare(String(b.name), "ja");
  }
  if (mode === "stockDesc") {
    return Number(b.count) - Number(a.count)
      || Number(b.templateUsageRate) - Number(a.templateUsageRate)
      || Number(a.currentTerm) - Number(b.currentTerm);
  }
  if (mode === "nameAsc") {
    return String(a.name).localeCompare(String(b.name), "ja")
      || Number(a.currentTerm) - Number(b.currentTerm);
  }
  return Number(b.templateUsageRate) - Number(a.templateUsageRate)
    || Number(a.currentTerm) - Number(b.currentTerm)
    || String(a.name).localeCompare(String(b.name), "ja");
}

function applyFilters() {
  const query = normalize(els.stockQuery.value);
  const position = els.stockPosition.value;
  const term = Number(els.stockTerm.value || 0);
  const category = els.stockCategory.value;
  const minUsage = Number(els.stockMinUsage.value || 0);
  const peakOnly = els.stockPeakOnly.checked;
  const templateOnly = els.stockTemplateOnly.checked;

  filteredStocks = stocks.filter((row) => {
    if (query && !stockHaystack(row).includes(query)) return false;
    if (position && row.position !== position) return false;
    if (term && Number(row.currentTerm) !== term) return false;
    const memberships = row.categoryMembership?.length ? row.categoryMembership : [row.category];
    if (category && !memberships.includes(category)) return false;
    const isExternalReserve = Number(row.externalReserveCount || 0) > 0;
    if (!isExternalReserve && peakOnly && !row.isPeak) return false;
    if (!isExternalReserve && templateOnly && Number(row.templateUsageRate || 0) <= 0) return false;
    if (!isExternalReserve && Number(row.templateUsageRate || 0) < minUsage) return false;
    return true;
  }).sort(compareStocks);
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
    : '<div class="stock-empty">条件に一致する外在庫はありません。</div>';
}

function resetFilters() {
  els.stockQuery.value = "";
  els.stockPosition.value = "";
  els.stockTerm.value = "";
  els.stockCategory.value = "";
  els.stockMinUsage.value = "0";
  els.stockSort.value = "templateDesc";
  els.stockPeakOnly.checked = false;
  els.stockTemplateOnly.checked = false;
  applyFilters();
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
  });
  [els.stockQuery, els.stockPosition, els.stockTerm, els.stockCategory, els.stockMinUsage, els.stockSort, els.stockPeakOnly, els.stockTemplateOnly]
    .forEach((element) => {
      element.addEventListener("input", () => applyFilters());
      element.addEventListener("change", () => applyFilters());
    });
  els.stockReset.addEventListener("click", resetFilters);
}

async function init() {
  updateMenuState();
  bindEvents();
  try {
    const response = await fetch("./ax_external_stock_data.json?v=20260809-search-stocks-v2", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    stocks = Array.isArray(payload.stocks) ? payload.stocks : [];
    renderMeta();
    renderSummary();
    populateFilters();
    applyFilters();
  } catch (error) {
    els.metaText.textContent = "Stock data unavailable";
    els.stockList.innerHTML = `<div class="stock-empty stock-error">在庫データを読み込めませんでした。${escapeHtml(error.message || error)}</div>`;
  }
}

init();
