const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";

const els = {
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  ccStatus: document.querySelector("#ccStatus"),
  ccSummary: document.querySelector("#ccSummary"),
  groupTabCount: document.querySelector("#groupTabCount"),
  tournamentTabCount: document.querySelector("#tournamentTabCount"),
  groupStageMeta: document.querySelector("#groupStageMeta"),
  tournamentMeta: document.querySelector("#tournamentMeta"),
  ccGroupGrid: document.querySelector("#ccGroupGrid"),
  ccTournament: document.querySelector("#ccTournament"),
  groupsPanel: document.querySelector("#groupsPanel"),
  tournamentPanel: document.querySelector("#tournamentPanel"),
};

let payload = null;

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
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} JST`;
}

function formatKickoff(value, { compact = false } = {}) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!match) return String(value || "-");
  return compact ? `${Number(match[2])}/${Number(match[3])} ${match[4]}:${match[5]}` : `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
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

function teamNameHtml(team) {
  const key = String(team?.managedKey || "");
  return `${key ? `<span class="cc-managed-key" title="A-X managed team">${escapeHtml(key)}</span>` : ""}<span>${escapeHtml(team?.name || "-")}</span>`;
}

function teamCellHtml(team) {
  const league = [team?.leagueClass, team?.leagueName].filter(Boolean).join(" / ");
  return `
    <div class="cc-team-cell${team?.managedKey ? " is-managed" : ""}">
      <div class="cc-team-name">${teamNameHtml(team)}</div>
      ${league ? `<small>${escapeHtml(league)}</small>` : ""}
    </div>
  `;
}

function matchHtml(match) {
  const score = Array.isArray(match.score)
    ? `<strong>${escapeHtml(match.score[0])}<span>–</span>${escapeHtml(match.score[1])}</strong>`
    : "<em>vs</em>";
  return `
    <article class="cc-match-row${match.completed ? " is-completed" : " is-scheduled"}">
      <time datetime="${escapeHtml(match.kickoff)}">${escapeHtml(formatKickoff(match.kickoff, { compact: true }))}</time>
      <div class="cc-match-team cc-match-home">${teamNameHtml(match.home)}</div>
      <div class="cc-match-score">${score}</div>
      <div class="cc-match-team cc-match-away">${teamNameHtml(match.away)}</div>
      <span class="cc-match-state">${match.completed ? "Final" : "Scheduled"}</span>
    </article>
  `;
}

function groupCardHtml(group) {
  const completed = (group.matches || []).filter((match) => match.completed).length;
  const standings = (group.standings || []).map((row) => `
    <tr class="${row.team?.managedKey ? "is-managed" : ""}">
      <td class="cc-rank">${escapeHtml(row.rank)}</td>
      <td>${teamCellHtml(row.team)}</td>
      <td>${escapeHtml(row.wins)}-${escapeHtml(row.draws)}-${escapeHtml(row.losses)}</td>
      <td>${escapeHtml(row.goalsFor)}-${escapeHtml(row.goalsAgainst)}</td>
      <td>${Number(row.goalDifference) > 0 ? "+" : ""}${escapeHtml(row.goalDifference)}</td>
      <td class="cc-points">${escapeHtml(row.points)}</td>
    </tr>
  `).join("");
  return `
    <article class="cc-group-card">
      <div class="cc-group-title">
        <h3>Group ${escapeHtml(group.label)}</h3>
        <span>${formatNumber(completed)} / ${formatNumber((group.matches || []).length)} completed</span>
      </div>
      <div class="cc-table-scroll">
        <table class="cc-standings-table">
          <thead><tr><th>#</th><th>Team</th><th>W-D-L</th><th>GF-GA</th><th>GD</th><th>Pts</th></tr></thead>
          <tbody>${standings || '<tr><td colspan="6">順位データはまだありません。</td></tr>'}</tbody>
        </table>
      </div>
      <div class="cc-match-list">${(group.matches || []).map(matchHtml).join("") || '<div class="cc-empty">試合データはまだありません。</div>'}</div>
    </article>
  `;
}

function renderGroups() {
  const groups = payload.groups || [];
  const summary = payload.summary || {};
  els.groupTabCount.textContent = formatNumber(summary.groupCount);
  els.groupStageMeta.textContent = `${formatNumber(summary.groupCount)} groups · ${formatNumber(summary.groupMatchCount)} matches`;
  els.ccGroupGrid.innerHTML = groups.length
    ? groups.map(groupCardHtml).join("")
    : '<div class="cc-empty cc-empty-panel">グループステージのデータはまだありません。</div>';
}

function renderTournament() {
  const rounds = payload.tournamentRounds || [];
  const summary = payload.summary || {};
  els.tournamentTabCount.textContent = formatNumber(summary.tournamentMatchCount);
  els.tournamentMeta.textContent = `${formatNumber(summary.tournamentRoundCount)} rounds · ${formatNumber(summary.tournamentMatchCount)} matches`;
  els.ccTournament.innerHTML = rounds.length
    ? rounds.map((round) => `
      <section class="cc-round-card">
        <div class="cc-group-title">
          <h3>${escapeHtml(round.label)}</h3>
          <span>${formatNumber((round.matches || []).filter((match) => match.completed).length)} / ${formatNumber((round.matches || []).length)} completed</span>
        </div>
        <div class="cc-match-list cc-tournament-match-list">${(round.matches || []).map(matchHtml).join("")}</div>
      </section>
    `).join("")
    : '<div class="cc-empty cc-empty-panel">決勝トーナメントはまだ始まっていません。</div>';
}

function nextScheduledMatch() {
  const matches = [
    ...(payload.groups || []).flatMap((group) => group.matches || []),
    ...(payload.tournamentRounds || []).flatMap((round) => round.matches || []),
  ].filter((match) => !match.completed && match.kickoff);
  matches.sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
  return matches[0] || null;
}

function renderOverview() {
  const source = payload.source || {};
  const summary = payload.summary || {};
  const status = payload.status || {};
  const nextMatch = nextScheduledMatch();
  els.metaText.innerHTML = [
    `<span class="meta-line">Hawk CC: ${escapeHtml(formatJst(payload.generatedAt))}</span>`,
    `<span class="meta-line">Season ${escapeHtml(source.season || "-")}</span>`,
  ].join("");
  els.ccStatus.className = `cc-status ${status.code === "ok" ? "is-ok" : "is-partial"}`;
  els.ccStatus.textContent = status.message || "取得状況不明";
  els.ccSummary.innerHTML = [
    ["Season", source.season ? `S${source.season}` : "-", source.worldName || "ホーク"],
    ["Updated", formatKickoff(payload.generatedAt), "01:30 cache"],
    ["Completed", `${formatNumber(summary.completedMatchCount)} / ${formatNumber(summary.allMatchCount)}`, "matches"],
    ["Next", nextMatch ? formatKickoff(nextMatch.kickoff, { compact: true }) : "-", nextMatch ? `${nextMatch.home?.name || "-"} vs ${nextMatch.away?.name || "-"}` : "schedule complete"],
  ].map(([label, value, note]) => `
    <div class="cc-summary-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note)}</small>
    </div>
  `).join("");
}

function setView(view) {
  const tournament = view === "tournament";
  els.groupsPanel.hidden = tournament;
  els.tournamentPanel.hidden = !tournament;
  document.querySelectorAll("[data-cc-view]").forEach((button) => {
    const active = button.dataset.ccView === view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function render() {
  renderOverview();
  renderGroups();
  renderTournament();
  if (Number(payload.summary?.tournamentMatchCount || 0) > 0) setView("tournament");
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
  document.querySelectorAll("[data-cc-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.ccView));
  });
}

async function init() {
  updateMenuState();
  bindEvents();
  try {
    const response = await fetch("./hawk_cc_data.json?v=20260831-hawk-cc-v1", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    render();
  } catch (error) {
    els.metaText.textContent = "Hawk CC data unavailable";
    els.ccStatus.className = "cc-status is-partial";
    els.ccStatus.textContent = "読み込み失敗";
    els.ccSummary.innerHTML = `<div class="cc-empty cc-empty-panel">Hawk CCデータを読み込めませんでした。${escapeHtml(error.message || error)}</div>`;
    els.ccGroupGrid.innerHTML = '<div class="cc-empty cc-empty-panel">時間をおいて再読み込みしてください。</div>';
    els.ccTournament.innerHTML = '<div class="cc-empty cc-empty-panel">時間をおいて再読み込みしてください。</div>';
  }
}

init();
