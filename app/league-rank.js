const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";

const els = {
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  rankStatus: document.querySelector("#rankStatus"),
  rankSeason: document.querySelector("#rankSeason"),
  rankLeagueCount: document.querySelector("#rankLeagueCount"),
  rankManagedCount: document.querySelector("#rankManagedCount"),
  rankUpdated: document.querySelector("#rankUpdated"),
  leagueRankGrid: document.querySelector("#leagueRankGrid"),
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function formatNumber(value) {
  return new Intl.NumberFormat("ja-JP").format(Number(value || 0));
}

function formatJst(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || "-");
  const parts = Object.fromEntries(new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
}

function signed(value) {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${formatNumber(number)}`;
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
  els.loginButton.hidden = loggedIn;
  els.logoutButton.hidden = !loggedIn;
  els.menuLoginId.hidden = !loggedIn;
  els.menuLoginId.textContent = loggedIn ? `Team ID：${lineupKey}` : "";
}

function closeMenu() {
  els.menuPanel.classList.remove("is-open");
  els.menuButton.setAttribute("aria-expanded", "false");
}

function bindEvents() {
  els.menuButton.addEventListener("click", () => {
    const open = !els.menuPanel.classList.contains("is-open");
    els.menuPanel.classList.toggle("is-open", open);
    els.menuButton.setAttribute("aria-expanded", open ? "true" : "false");
  });
  els.loginButton.addEventListener("click", () => { window.location.href = "./index.html?openLogin=1"; });
  els.logoutButton.addEventListener("click", () => {
    const config = loadCloudConfig();
    config.lineupKey = "";
    localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(config));
    updateMenuState();
    closeMenu();
  });
  document.addEventListener("click", (event) => {
    if (!els.menuPanel.contains(event.target) && event.target !== els.menuButton) closeMenu();
  });
}

function rankChangeHtml(row) {
  const change = Number(row.rankChange || 0);
  if (!change) return '<span class="league-rank-change is-flat" aria-label="順位変動なし">–</span>';
  const direction = change > 0 ? "up" : "down";
  const arrow = change > 0 ? "▲" : "▼";
  return `<span class="league-rank-change is-${direction}" aria-label="${Math.abs(change)}順位${change > 0 ? "上昇" : "下降"}">${arrow}${Math.abs(change)}</span>`;
}

function managedBadges(keys) {
  return (keys || []).map((key) => `<span class="league-rank-key">${escapeHtml(key)}</span>`).join("");
}

function leagueCardHtml(league) {
  const rows = (league.rows || []).map((row) => `
    <tr class="${row.managedKey ? "is-managed" : ""}">
      <td class="league-rank-position"><strong>${escapeHtml(row.rank)}</strong>${league.resultAdjusted ? rankChangeHtml(row) : ""}</td>
      <td class="league-rank-team"><span class="league-rank-row-key">${row.managedKey ? escapeHtml(row.managedKey) : ""}</span><span>${escapeHtml(row.teamName || "-")}</span></td>
      <td>${formatNumber(row.wins)}-${formatNumber(row.draws)}-${formatNumber(row.losses)}</td>
      <td>${formatNumber(row.goalsFor)}-${formatNumber(row.goalsAgainst)}</td>
      <td class="${Number(row.goalDifference) > 0 ? "is-positive" : Number(row.goalDifference) < 0 ? "is-negative" : ""}">${signed(row.goalDifference)}</td>
      <td class="league-rank-points">${formatNumber(row.points)}</td>
    </tr>
  `).join("");
  const matchday = league.targetMatchday ? `MD ${formatNumber(league.targetMatchday)}` : "Official";
  return `
    <article class="league-rank-card">
      <header class="league-rank-card-head">
        <div class="league-rank-card-title">
          <span class="league-rank-card-keys">${managedBadges(league.managedKeys)}</span>
          <h3>${escapeHtml(league.leagueName || "-")}</h3>
        </div>
        <span>${escapeHtml(matchday)}</span>
      </header>
      <div class="league-rank-table-wrap">
        <table class="league-rank-table">
          <thead><tr><th>#</th><th>Team</th><th>W-D-L</th><th>GF-GA</th><th>GD</th><th>Pts</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6">順位データはまだありません。</td></tr>'}</tbody>
        </table>
      </div>
    </article>
  `;
}

function render(payload) {
  const leagues = Array.isArray(payload.leagues) ? payload.leagues : [];
  const summary = payload.summary || {};
  const status = payload.status || {};
  els.metaText.textContent = "A–X League Standings";
  els.rankSeason.textContent = `S${formatNumber(payload.source?.season)}`;
  els.rankLeagueCount.textContent = formatNumber(summary.leagueCount);
  els.rankManagedCount.textContent = formatNumber(summary.managedTeamCount);
  els.rankUpdated.textContent = formatJst(payload.generatedAt);
  els.rankStatus.textContent = status.message || "順位表";
  els.rankStatus.className = `league-rank-status is-${escapeHtml(status.code || "official")}`;
  els.leagueRankGrid.innerHTML = leagues.length
    ? leagues.map(leagueCardHtml).join("")
    : '<div class="league-rank-empty">表示できる順位表がありません。</div>';
}

async function init() {
  updateMenuState();
  bindEvents();
  try {
    const response = await fetch("./league_rank_data.json?v=20260903-league-rank-v1", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (_error) {
    els.metaText.textContent = "League Rank data unavailable";
    els.rankStatus.textContent = "読み込み失敗";
    els.rankStatus.className = "league-rank-status is-error";
    els.leagueRankGrid.innerHTML = '<div class="league-rank-empty">時間をおいて再読み込みしてください。</div>';
  }
}

init();
