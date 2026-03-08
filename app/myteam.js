const CLOUD_CONFIG_STORAGE_KEY = "ws_cloud_config_v1";
const SUPABASE_TABLE = "lineup_states";
const FIXED_SUPABASE_URL = "https://trbuptnlpmcetwprirxn.supabase.co";
const FIXED_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyYnVwdG5scG1jZXR3cHJpcnhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5Nzg5MzIsImV4cCI6MjA4ODU1NDkzMn0.mPzL3tfKfWsCh17om16OGKYiayAhrhn3Cy74DXKGwI0";
const LINEUP_SIZE = 11;

const els = {
  myteamMenuButton: document.querySelector("#myteamMenuButton"),
  myteamMenuPanel: document.querySelector("#myteamMenuPanel"),
  myteamDatabaseButton: document.querySelector("#myteamDatabaseButton"),
  myteamLogoutButton: document.querySelector("#myteamLogoutButton"),
  myTeamMeta: document.querySelector("#myTeamMeta"),
  myTeamTarget: document.querySelector("#myTeamTarget"),
  myTeamSlots: document.querySelector("#myTeamSlots"),
};

let players = [];
let lineup = Array.from({ length: LINEUP_SIZE }, () => null);
let cloudConfig = { url: "", anonKey: "", lineupKey: "" };

function closeMenuPanel() {
  if (!els.myteamMenuPanel) return;
  els.myteamMenuPanel.hidden = true;
}

function normalizedSupabaseUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

function normalizeLineupArray(parsed) {
  return Array.from({ length: LINEUP_SIZE }, (_, i) => {
    const row = parsed?.[i];
    if (row == null) return null;
    if (typeof row === "number" || typeof row === "string") {
      const id = Number(row);
      return Number.isInteger(id) ? { playerId: id, season: null } : null;
    }
    if (typeof row === "object") {
      const id = Number(row.playerId);
      if (!Number.isInteger(id)) return null;
      const season = row.season == null ? null : String(row.season);
      return { playerId: id, season };
    }
    return null;
  });
}

function loadCloudConfig() {
  try {
    const raw = localStorage.getItem(CLOUD_CONFIG_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      cloudConfig = {
        url: normalizedSupabaseUrl(parsed?.url || ""),
        anonKey: String(parsed?.anonKey || "").trim(),
        lineupKey: String(parsed?.lineupKey || "").trim(),
      };
    }
  } catch (e) {
    console.warn(e);
  }
  if (FIXED_SUPABASE_URL) cloudConfig.url = normalizedSupabaseUrl(FIXED_SUPABASE_URL);
  if (FIXED_SUPABASE_ANON_KEY) cloudConfig.anonKey = String(FIXED_SUPABASE_ANON_KEY).trim();
}

function logoutLineupKey() {
  cloudConfig = {
    url: normalizedSupabaseUrl(FIXED_SUPABASE_URL || cloudConfig.url),
    anonKey: String(FIXED_SUPABASE_ANON_KEY || cloudConfig.anonKey).trim(),
    lineupKey: "",
  };
  localStorage.setItem(CLOUD_CONFIG_STORAGE_KEY, JSON.stringify(cloudConfig));
}

function hasCloudConfig() {
  return !!(cloudConfig.url && cloudConfig.anonKey && cloudConfig.lineupKey);
}

async function supabaseRequest(pathWithQuery, options = {}) {
  const res = await fetch(`${cloudConfig.url}/rest/v1/${pathWithQuery}`, {
    ...options,
    headers: {
      apikey: cloudConfig.anonKey,
      Authorization: `Bearer ${cloudConfig.anonKey}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`supabase ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loadCloudLineup() {
  const params = new URLSearchParams({
    select: "lineup_json",
    lineup_id: `eq.${cloudConfig.lineupKey}`,
    limit: "1",
  });
  const rows = await supabaseRequest(`${SUPABASE_TABLE}?${params.toString()}`, {
    method: "GET",
  });
  if (!Array.isArray(rows) || !rows.length) return false;
  const remote = rows[0]?.lineup_json;
  if (!Array.isArray(remote)) return false;
  lineup = normalizeLineupArray(remote);
  return true;
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

function typeClassByPlayer(player) {
  const typeLabel = getCategory(player);
  if (typeLabel === "NR") {
    const rate = Number(player?.rate);
    if (rate === 7) return "cat-nr-r7";
    if (rate === 5 || rate === 6) return "cat-nr-r56";
    if (rate === 4) return "cat-nr-r4";
    return "cat-nr-r13";
  }
  if (typeLabel === "SS") return "cat-ss";
  if (typeLabel === "CM") return "cat-cm";
  if (typeLabel === "CM/SS") return "cat-cmss";
  if (typeLabel === "CC") return "cat-cc";
  return "cat-na";
}

function positionClass(position) {
  const pos = (position || "-").toUpperCase();
  if (pos === "GK") return "pos-gk";
  if (pos === "DF") return "pos-df";
  if (pos === "MF") return "pos-mf";
  if (pos === "FW") return "pos-fw";
  return "";
}

function coreTotal(metrics) {
  return (metrics?.["スピ"] || 0) + (metrics?.["テク"] || 0) + (metrics?.["パワ"] || 0);
}

function getPeakMetrics(player) {
  const periods = Array.isArray(player.periods) ? player.periods : [];
  if (!periods.length) return player.maxMetrics || {};
  let best = periods[0]?.metrics || {};
  let bestScore = coreTotal(best);
  for (let i = 1; i < periods.length; i += 1) {
    const m = periods[i]?.metrics || {};
    const score = coreTotal(m);
    if (score > bestScore) {
      best = m;
      bestScore = score;
    }
  }
  return best;
}

function findPeriodBySeason(player, season) {
  if (!player || !season) return null;
  const periods = Array.isArray(player.periods) ? player.periods : [];
  return periods.find((p) => p?.season === season) || null;
}

function metricLabel(metric) {
  if (metric === "スピ") return "スピード";
  if (metric === "テク") return "テクニック";
  if (metric === "パワ") return "パワー";
  return metric;
}

function miniCoreMetric(metric, value) {
  const bounded = Math.max(0, Math.min(10, Math.round(value || 0)));
  const keyClass =
    metric === "スピ" ? "m-speed" :
    metric === "テク" ? "m-tech" :
    "m-power";
  const cells = Array.from({ length: 10 }, (_, i) =>
    `<span class="gauge-cell${i < bounded ? " on" : ""}"></span>`
  ).join("");
  return `
    <div class="lineup-core-item ${keyClass}">
      <span class="lineup-core-key">${metricLabel(metric)}</span>
      <div class="lineup-core-body">
        <div class="gauge">${cells}</div>
        <span class="lineup-core-num">${value ?? "-"}</span>
      </div>
    </div>
  `;
}

function renderLineup() {
  if (!els.myTeamSlots) return;
  const html = lineup.map((entry, idx) => {
    const slot = idx + 1;
    const playerId = Number(entry?.playerId);
    const player = Number.isInteger(playerId) ? players.find((x) => x.id === playerId) : null;
    const name = player ? player.name : "未登録";
    const season = player ? (entry?.season || null) : null;
    const seasonText = season ? `${season}目` : "-";
    const pos = (player?.position || "-").toUpperCase();
    const posClass = positionClass(pos);
    const typeLabel = player ? getCategory(player) : "-";
    const typeClass = player ? typeClassByPlayer(player) : "cat-na";
    const imageHtml = player
      ? `<img loading="lazy" src="./images/chara/players/static/${player.id}.gif" alt="${player.name}" />`
      : `<div class="lineup-empty-thumb"></div>`;
    const selectedPeriod = player ? findPeriodBySeason(player, season) : null;
    const selectedMetrics = selectedPeriod?.metrics || (player ? getPeakMetrics(player) : null);
    const coreHtml = player ? `
      <div class="lineup-core">
        ${miniCoreMetric("スピ", selectedMetrics?.["スピ"])}
        ${miniCoreMetric("テク", selectedMetrics?.["テク"])}
        ${miniCoreMetric("パワ", selectedMetrics?.["パワ"])}
      </div>
    ` : "";

    return `
      <div class="lineup-slot has-player is-disabled">
        <span class="slot-no">${slot}</span>
        <div class="lineup-slot-main">
          <div class="lineup-thumb-wrap">${imageHtml}</div>
          <div class="lineup-player-meta">
            <div class="lineup-badges">
              <span class="badge pos-badge ${posClass}">${pos}</span>
              <span class="badge type-badge ${typeClass}">${typeLabel}</span>
              <span class="badge lineup-season">${seasonText}</span>
            </div>
            <span class="slot-name">${name}</span>
          </div>
          ${coreHtml}
        </div>
      </div>
    `;
  }).join("");
  els.myTeamSlots.innerHTML = html;
}

async function init() {
  loadCloudConfig();
  if (els.myteamMenuButton) {
    els.myteamMenuButton.addEventListener("click", () => {
      if (!els.myteamMenuPanel) return;
      els.myteamMenuPanel.hidden = !els.myteamMenuPanel.hidden;
    });
  }
  if (els.myteamDatabaseButton) {
    els.myteamDatabaseButton.addEventListener("click", () => {
      window.location.href = "./index.html";
    });
  }
  if (els.myteamLogoutButton) {
    els.myteamLogoutButton.addEventListener("click", () => {
      logoutLineupKey();
      window.location.href = "./index.html";
    });
  }
  document.addEventListener("click", (e) => {
    if (!els.myteamMenuPanel || !els.myteamMenuButton) return;
    if (els.myteamMenuPanel.hidden) return;
    if (e.target.closest("#myteamMenuButton") || e.target.closest("#myteamMenuPanel")) return;
    closeMenuPanel();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenuPanel();
  });

  const dataRes = await fetch("./data.json");
  const data = await dataRes.json();
  players = data.players || [];

  if (!hasCloudConfig()) {
    if (els.myTeamTarget) els.myTeamTarget.textContent = "TeamIDが未設定です（先にLoginしてください）";
    if (els.myTeamMeta) els.myTeamMeta.textContent = "Not logged in";
    renderLineup();
    return;
  }

  if (els.myTeamMeta) els.myTeamMeta.textContent = `TeamID: ${cloudConfig.lineupKey}`;
  if (els.myTeamTarget) els.myTeamTarget.textContent = "現在のスタメン";
  try {
    await loadCloudLineup();
  } catch (e) {
    if (els.myTeamTarget) els.myTeamTarget.textContent = "クラウド読込に失敗しました";
  }
  renderLineup();
}

init().catch((e) => {
  if (els.myTeamTarget) els.myTeamTarget.textContent = "データ読み込みに失敗しました";
  console.error(e);
});
