const SIM_LINE_LABELS = {
  1: "FW",
  2: "MF",
  3: "DF",
  4: "GK",
};

const els = {
  metaText: document.querySelector("#metaText"),
  menuButton: document.querySelector("#menuButton"),
  menuPanel: document.querySelector("#menuPanel"),
  playersButton: document.querySelector("#playersButton"),
  coachesButton: document.querySelector("#coachesButton"),
  formationsButton: document.querySelector("#formationsButton"),
  collectionsButton: document.querySelector("#collectionsButton"),
  simulationButton: document.querySelector("#simulationButton"),
  myTeamButton: document.querySelector("#myTeamButton"),
  calibrationStatus: document.querySelector("#calibrationStatus"),
  fillExample: document.querySelector("#fillExample"),
  clearSimulation: document.querySelector("#clearSimulation"),
  homeRows: document.querySelector("#homeRows"),
  awayRows: document.querySelector("#awayRows"),
  homeCoachPts: document.querySelector("#homeCoachPts"),
  awayCoachPts: document.querySelector("#awayCoachPts"),
  homeStarterCount: document.querySelector("#homeStarterCount"),
  awayStarterCount: document.querySelector("#awayStarterCount"),
  simulationSummary: document.querySelector("#simulationSummary"),
  simulationBreakdown: document.querySelector("#simulationBreakdown"),
  scoreDistribution: document.querySelector("#scoreDistribution"),
  simulationWarnings: document.querySelector("#simulationWarnings"),
  resultSource: document.querySelector("#resultSource"),
};

let calibration = null;

function closeMenuPanel() {
  if (els.menuPanel) els.menuPanel.classList.remove("is-open");
}

function fmtNumber(value, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "-";
}

function fmtPct(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : "-";
}

function setMeta(meta) {
  if (!els.metaText) return;
  const updated = meta?.generatedAt ? new Date(meta.generatedAt) : null;
  const updatedText = Number.isNaN(updated?.getTime?.()) ? "Updated: -" : `Updated: ${updated.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })}`;
  const cc = meta?.ccData;
  const ccText = cc ? `CC Data: ${cc.seasonStart}-${cc.seasonEnd} / ${cc.games} games` : "CC Data: -";
  els.metaText.innerHTML = `<span class="meta-line">${updatedText}</span><span class="meta-line">${ccText}</span>`;
}

async function loadMeta() {
  try {
    const res = await fetch("./site_meta.json?v=20260515-simulation-v3");
    if (!res.ok) throw new Error(String(res.status));
    setMeta(await res.json());
  } catch {
    if (els.metaText) els.metaText.textContent = "Updated: -";
  }
}

async function loadCalibration() {
  try {
    const res = await fetch("./simulation_v3_calibration.json?v=20260515-simulation-v3");
    if (!res.ok) throw new Error(String(res.status));
    calibration = await res.json();
    if (els.calibrationStatus) {
      els.calibrationStatus.textContent = `Calibration: CC ${calibration.seasonStart}-${calibration.seasonEnd} / ${calibration.pairCount} games`;
    }
  } catch {
    calibration = null;
    if (els.calibrationStatus) els.calibrationStatus.textContent = "Calibration: fallback";
  }
}

function createPlayerRow(side, index) {
  const row = document.createElement("div");
  row.className = "simulation-player-row";
  row.dataset.side = side;
  row.dataset.index = String(index);
  row.innerHTML = `
    <div class="simulation-row-num">${index + 1}</div>
    <input class="simulation-player-name" type="text" placeholder="Name" autocomplete="off" />
    <input class="simulation-player-pts" type="number" step="0.1" inputmode="decimal" placeholder="pts" />
    <select class="simulation-player-pos" aria-label="line">
      <option value="4">GK</option>
      <option value="3">DF</option>
      <option value="2">MF</option>
      <option value="1">FW</option>
    </select>
  `;
  return row;
}

function createRows() {
  for (const side of ["home", "away"]) {
    const host = side === "home" ? els.homeRows : els.awayRows;
    if (!host) continue;
    host.innerHTML = "";
    for (let i = 0; i < 11; i += 1) host.appendChild(createPlayerRow(side, i));
  }
  setDefaultPositions();
}

function setDefaultPositions() {
  for (const side of ["home", "away"]) {
    const rows = document.querySelectorAll(`.simulation-player-row[data-side="${side}"]`);
    rows.forEach((row, index) => {
      const pos = row.querySelector(".simulation-player-pos");
      if (!pos) return;
      if (index === 0) pos.value = "4";
      else if (index <= 4) pos.value = "3";
      else if (index <= 8) pos.value = "2";
      else pos.value = "1";
    });
  }
}

function readTeam(side) {
  const rows = [...document.querySelectorAll(`.simulation-player-row[data-side="${side}"]`)];
  const players = rows.map((row, idx) => ({
    playerId: idx + 1,
    name: row.querySelector(".simulation-player-name")?.value?.trim() || "",
    pts: row.querySelector(".simulation-player-pts")?.value ?? "",
    posCode14: Number(row.querySelector(".simulation-player-pos")?.value),
    isStarting11: true,
  }));
  const coachEl = side === "home" ? els.homeCoachPts : els.awayCoachPts;
  return {
    players,
    headcoach: {
      pts: coachEl?.value ?? "",
    },
  };
}

function updateCounts() {
  for (const side of ["home", "away"]) {
    const rows = [...document.querySelectorAll(`.simulation-player-row[data-side="${side}"]`)];
    const filled = rows.filter((row) => row.querySelector(".simulation-player-pts")?.value !== "").length;
    const el = side === "home" ? els.homeStarterCount : els.awayStarterCount;
    if (el) el.textContent = `${filled}/11`;
  }
}

function renderStat(label, value, detail = "") {
  return `<div class="simulation-stat"><span>${label}</span><strong>${value}</strong>${detail ? `<small>${detail}</small>` : ""}</div>`;
}

function renderBreakdownSide(label, team) {
  const line = team.lineBreakdown || {};
  return `
    <div class="simulation-breakdown-card">
      <h4>${label}</h4>
      <div class="simulation-breakdown-list">
        <span>Starting XI</span><strong>${fmtNumber(team.starterPtsSum, 1)}</strong>
        <span>Head Coach</span><strong>${fmtNumber(team.headcoachPts, 1)}</strong>
        <span>FW</span><strong>${fmtNumber(line.fwPts, 1)}</strong>
        <span>MF</span><strong>${fmtNumber(line.mfPts, 1)}</strong>
        <span>DF</span><strong>${fmtNumber(line.dfPts, 1)}</strong>
        <span>GK</span><strong>${fmtNumber(line.gkPts, 1)}</strong>
      </div>
    </div>
  `;
}

function renderScoreDistribution(rows) {
  const top = (rows || []).slice(0, 10);
  if (!els.scoreDistribution) return;
  els.scoreDistribution.innerHTML = top.map((row) => `
    <div class="score-row">
      <span>${row.homeGoals}-${row.awayGoals}</span>
      <strong>${fmtPct(row.probability)}</strong>
    </div>
  `).join("");
}

function renderWarnings(warnings) {
  if (!els.simulationWarnings) return;
  const list = [...new Set(warnings || [])];
  els.simulationWarnings.hidden = list.length === 0;
  els.simulationWarnings.innerHTML = list.map((w) => `<div>${w}</div>`).join("");
}

function runSimulation() {
  updateCounts();
  if (!window.WsSimulationV3) return;
  const result = window.WsSimulationV3.simulateMatchV3(readTeam("home"), readTeam("away"), {
    model: "v3",
    useEmpiricalCalibration: true,
    binWidth: 2,
    maxGoals: 9,
    calibration,
  });

  if (els.simulationSummary) {
    els.simulationSummary.innerHTML = [
      renderStat("Home Index", fmtNumber(result.home.teamIndex, 1)),
      renderStat("Away Index", fmtNumber(result.away.teamIndex, 1)),
      renderStat("Index Diff", `${result.indexDiff >= 0 ? "+" : ""}${fmtNumber(result.indexDiff, 1)}`),
      renderStat("Home Win", fmtPct(result.probabilities.homeWin)),
      renderStat("Draw", fmtPct(result.probabilities.draw)),
      renderStat("Away Win", fmtPct(result.probabilities.awayWin)),
      renderStat("Home xPts", fmtNumber(result.expected.homePoints, 2)),
      renderStat("Away xPts", fmtNumber(result.expected.awayPoints, 2)),
      renderStat("Home xG", fmtNumber(result.expected.homeGoals, 2)),
      renderStat("Away xG", fmtNumber(result.expected.awayGoals, 2)),
    ].join("");
  }
  if (els.simulationBreakdown) {
    els.simulationBreakdown.innerHTML = renderBreakdownSide("Home", result.home) + renderBreakdownSide("Away", result.away);
  }
  renderScoreDistribution(result.scoreDistribution);
  renderWarnings(result.warnings);
  if (els.resultSource) {
    const meta = result.meta || {};
    els.resultSource.textContent = `${meta.calibration || "-"} / bucket ${meta.bucket ?? "-"} / n=${meta.sampleSize ?? 0}`;
  }
}

function fillExample() {
  const homePts = [4, 3, 3, 3, 2, 3, 3, 3, 3, 3, 3];
  const awayPts = [3, 3, 3, 2, 2, 3, 3, 2, 2, 3, 3];
  for (const side of ["home", "away"]) {
    const pts = side === "home" ? homePts : awayPts;
    const rows = [...document.querySelectorAll(`.simulation-player-row[data-side="${side}"]`)];
    rows.forEach((row, index) => {
      row.querySelector(".simulation-player-name").value = `${side === "home" ? "Home" : "Away"} ${index + 1}`;
      row.querySelector(".simulation-player-pts").value = String(pts[index]);
    });
  }
  if (els.homeCoachPts) els.homeCoachPts.value = "4";
  if (els.awayCoachPts) els.awayCoachPts.value = "2";
  runSimulation();
}

function clearSimulation() {
  document.querySelectorAll(".simulation-player-name,.simulation-player-pts,.simulation-coach-pts").forEach((el) => {
    el.value = "";
  });
  setDefaultPositions();
  runSimulation();
}

function bindEvents() {
  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => {
      if (els.menuPanel) els.menuPanel.classList.toggle("is-open");
    });
  }
  if (els.playersButton) els.playersButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./index.html"; });
  if (els.coachesButton) els.coachesButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./coaches.html"; });
  if (els.formationsButton) els.formationsButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./formations.html"; });
  if (els.collectionsButton) els.collectionsButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./collections.html"; });
  if (els.simulationButton) els.simulationButton.addEventListener("click", closeMenuPanel);
  if (els.myTeamButton) els.myTeamButton.addEventListener("click", () => { closeMenuPanel(); window.location.href = "./myteam.html"; });
  if (els.fillExample) els.fillExample.addEventListener("click", fillExample);
  if (els.clearSimulation) els.clearSimulation.addEventListener("click", clearSimulation);
  document.addEventListener("input", (event) => {
    if (event.target.closest(".simulation-page")) runSimulation();
  });
  document.addEventListener("change", (event) => {
    if (event.target.closest(".simulation-page")) runSimulation();
  });
}

async function init() {
  createRows();
  bindEvents();
  await Promise.all([loadMeta(), loadCalibration()]);
  runSimulation();
}

init();
