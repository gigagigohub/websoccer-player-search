const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";

const els = {
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  menuLoginId: document.querySelector("#menuLoginId"),
  loginButton: document.querySelector("#loginButton"),
  logoutButton: document.querySelector("#logoutButton"),
  ccSeasonSelect: document.querySelector("#ccSeasonSelect"),
  ccUpdated: document.querySelector("#ccUpdated"),
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
let activeSeason = null;

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

function isOwnTeam(team) {
  return Boolean(team?.isOwnTeam);
}

function teamNameHtml(team, { showBadge = true } = {}) {
  const key = String(team?.managedKey || "");
  const teamLabel = `<span class="cc-team-label">${escapeHtml(team?.name || "-")}</span>`;
  if (!showBadge) return teamLabel;
  const ownBadge = isOwnTeam(team)
    ? '<span class="cc-own-team-badge" title="自チーム">MY</span>'
    : "";
  const managedBadge = key
    ? `<span class="cc-managed-key" title="A-X managed team">${escapeHtml(key)}</span>`
    : "";
  const badge = ownBadge || managedBadge;
  return `<span class="cc-badge-slot"${badge ? "" : ' aria-hidden="true"'}>${badge}</span>${teamLabel}`;
}

function teamCellHtml(team) {
  const league = [team?.leagueClass, team?.leagueName].filter(Boolean).join(" / ");
  return `
    <div class="cc-team-cell${team?.managedKey ? " is-managed" : ""}${isOwnTeam(team) ? " is-own-team" : ""}">
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
      <div class="cc-match-team cc-match-home${match.home?.managedKey ? " is-managed" : ""}${isOwnTeam(match.home) ? " is-own-team" : ""}">${teamNameHtml(match.home, { showBadge: false })}</div>
      <div class="cc-match-score">${score}</div>
      <div class="cc-match-team cc-match-away${match.away?.managedKey ? " is-managed" : ""}${isOwnTeam(match.away) ? " is-own-team" : ""}">${teamNameHtml(match.away, { showBadge: false })}</div>
      <span class="cc-match-state">${match.completed ? "Final" : "Scheduled"}</span>
    </article>
  `;
}

function groupCardHtml(group) {
  const completed = (group.matches || []).filter((match) => match.completed).length;
  const standings = (group.standings || []).map((row) => `
    <tr class="${[row.team?.managedKey ? "is-managed" : "", isOwnTeam(row.team) ? "is-own-team" : ""].filter(Boolean).join(" ")}">
      <td class="cc-rank">${escapeHtml(row.rank)}</td>
      <td>${teamCellHtml(row.team)}</td>
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
          <thead><tr><th>#</th><th>Team</th><th>GD</th><th>Pts</th></tr></thead>
          <tbody>${standings || '<tr><td colspan="4">順位データはまだありません。</td></tr>'}</tbody>
        </table>
      </div>
      <div class="cc-match-list">${(group.matches || []).map(matchHtml).join("") || '<div class="cc-empty">試合データはまだありません。</div>'}</div>
    </article>
  `;
}

function renderGroups() {
  const groups = activeSeason.groups || [];
  const summary = activeSeason.summary || {};
  els.groupTabCount.textContent = formatNumber(summary.groupCount);
  const beforeKickoff = groups.length > 0 && groups.every((group) => !(group.matches || []).some((match) => match.completed));
  els.groupStageMeta.textContent = `${beforeKickoff ? "開幕前 · " : ""}${formatNumber(summary.groupCount)} groups · ${formatNumber(summary.groupMatchCount)} matches`;
  els.ccGroupGrid.innerHTML = groups.length
    ? groups.map(groupCardHtml).join("")
    : '<div class="cc-empty cc-empty-panel">グループステージのデータはまだありません。</div>';
}

function qualifierHtml(entrant) {
  const provisional = entrant.provisional !== false;
  const status = !entrant.team ? "順位未取得" : !provisional ? "順位確定"
    : entrant.beforeKickoff ? "試合前の仮順位" : "現在順位・未確定";
  return `
    <div class="cc-qualifier">
      <div class="cc-qualifier-label"><strong>${escapeHtml(entrant.group)}組 ${escapeHtml(entrant.rank)}位</strong><span>Slot ${escapeHtml(entrant.slot)}</span></div>
      <div class="cc-qualifier-team${provisional ? " is-provisional" : ""}">${entrant.team ? teamNameHtml(entrant.team) : '<span class="cc-team-label">未定</span>'}</div>
      <small>${status}${entrant.tied && provisional ? " · 同成績" : ""}</small>
    </div>
  `;
}

function tournamentPreviewHtml(preview) {
  return `
    <p class="cc-preview-note">各組の1・2位が進出します。薄いチーム名は現在順位による仮表示です。試合前・同成績の場合は取得時の順位順で、出場確定ではありません。</p>
    <div class="cc-preview-grid">${preview.map((match) => `
      <article class="cc-preview-card">
        <div class="cc-group-title"><h3>1回戦 ${escapeHtml(match.matchNumber)}</h3><span>Round of 16</span></div>
        <div class="cc-qualifier-pair">${qualifierHtml(match.home)}<span class="cc-preview-vs">vs</span>${qualifierHtml(match.away)}</div>
      </article>
    `).join("")}</div>
  `;
}

function renderTournament() {
  const rounds = activeSeason.tournamentRounds || [];
  const summary = activeSeason.summary || {};
  const preview = activeSeason.tournamentPreview || [];
  if (!rounds.length && preview.length) {
    els.tournamentTabCount.textContent = `${preview.length * 2}枠`;
    els.tournamentMeta.textContent = "進出枠と現在順位";
    els.ccTournament.innerHTML = tournamentPreviewHtml(preview);
    return;
  }
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

function seasonRows() {
  if (Array.isArray(payload?.seasons)) return payload.seasons;
  return payload ? [payload] : [];
}

function updateSeasonQuery(season) {
  const url = new URL(window.location.href);
  url.searchParams.set("season", String(season));
  window.history.replaceState({}, "", url);
}

function selectSeason(season, { updateUrl = false } = {}) {
  const rows = seasonRows();
  activeSeason = rows.find((row) => Number(row.source?.season) === Number(season)) || rows[0];
  if (!activeSeason) return;

  const selectedSeason = Number(activeSeason.source?.season || 0);
  els.ccSeasonSelect.value = String(selectedSeason);
  els.ccUpdated.textContent = formatJst(activeSeason.generatedAt);
  els.metaText.textContent = "Hawk Champions Cup Results";
  renderGroups();
  renderTournament();
  setView(Number(activeSeason.summary?.tournamentMatchCount || 0) > 0 ? "tournament" : "groups");
  if (updateUrl) updateSeasonQuery(selectedSeason);
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
  const rows = seasonRows();
  const requestedSeason = Number(new URLSearchParams(window.location.search).get("season"));
  const initial = rows.find((row) => Number(row.source?.season) === requestedSeason) || rows[0];
  els.ccSeasonSelect.innerHTML = rows.map((row) => {
    const season = Number(row.source?.season || 0);
    return `<option value="${escapeHtml(season)}">S${escapeHtml(season)}</option>`;
  }).join("");
  els.ccSeasonSelect.disabled = rows.length < 2;
  selectSeason(initial?.source?.season);
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
  els.ccSeasonSelect.addEventListener("change", () => {
    selectSeason(els.ccSeasonSelect.value, { updateUrl: true });
  });
}

async function init() {
  updateMenuState();
  bindEvents();
  try {
    const response = await fetch("./hawk_cc_data.json?v=20260906-cc-draw-v1", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    render();
  } catch (error) {
    els.metaText.textContent = "Hawk CC data unavailable";
    els.ccSeasonSelect.innerHTML = "<option>Unavailable</option>";
    els.ccSeasonSelect.disabled = true;
    els.ccUpdated.textContent = "読み込み失敗";
    els.ccGroupGrid.innerHTML = '<div class="cc-empty cc-empty-panel">時間をおいて再読み込みしてください。</div>';
    els.ccTournament.innerHTML = '<div class="cc-empty cc-empty-panel">時間をおいて再読み込みしてください。</div>';
  }
}

init();
