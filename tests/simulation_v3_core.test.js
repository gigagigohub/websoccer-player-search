const test = require("node:test");
const assert = require("node:assert/strict");

const sim = require("../app/simulation_v3_core.js");

function playersFromPts(pts, pos = []) {
  return pts.map((value, index) => ({
    playerId: index + 1,
    pts: value,
    posCode14: pos[index] || 2,
    isStarting11: true,
  }));
}

test("calculates V3 team index and diff", () => {
  const home = sim.calculateTeamIndexV3({ players: playersFromPts([3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]), headcoach: { pts: 4 } }, "Home");
  const away = sim.calculateTeamIndexV3({ players: playersFromPts([3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2]), headcoach: { pts: 2 } }, "Away");
  assert.equal(home.starterPtsSum, 33);
  assert.equal(home.teamIndex, 37);
  assert.equal(away.starterPtsSum, 29);
  assert.equal(away.teamIndex, 31);
  assert.equal(sim.calculateIndexDiff(home.teamIndex, away.teamIndex), 6);
});

test("calculates line breakdown by pos_code_1_4", () => {
  const players = playersFromPts(
    [4, 3, 3, 3, 2, 3, 3, 3, 3, 2, 2],
    [4, 3, 3, 3, 3, 2, 2, 2, 2, 1, 1]
  );
  assert.deepEqual(sim.calculateLineBreakdown(players), {
    gkPts: 4,
    dfPts: 11,
    mfPts: 12,
    fwPts: 4,
  });
});

test("calculates expected points", () => {
  const result = sim.calculateExpectedPoints({ homeWin: 0.7, draw: 0.2, awayWin: 0.1 });
  assert.equal(result.homePoints, 2.3);
  assert.equal(result.awayPoints, 0.5);
});

test("normalizes poisson score distribution", () => {
  const rows = sim.buildScoreDistribution(2.2, 1.1, 9);
  const total = rows.reduce((sum, row) => sum + row.probability, 0);
  assert.ok(Math.abs(total - 1) < 1e-6);
  const probs = sim.calculateProbabilitiesFromScoreDistribution(rows);
  assert.ok(Math.abs((probs.homeWin + probs.draw + probs.awayWin) - 1) < 1e-6);
});

test("validates starter count and missing values", () => {
  const ten = sim.calculateTeamIndexV3({ players: playersFromPts(Array(10).fill(3)), headcoach: { pts: 1 } }, "Home");
  assert.ok(ten.warnings.some((w) => w.includes("starting11 count is 10")));

  const twelve = sim.calculateTeamIndexV3({ players: playersFromPts(Array(12).fill(3)), headcoach: { pts: 1 } }, "Away");
  assert.ok(twelve.warnings.some((w) => w.includes("starting11 count is 12")));

  const missing = sim.calculateTeamIndexV3({ players: playersFromPts([null, ...Array(10).fill(3)]), headcoach: {} }, "Home");
  assert.ok(missing.warnings.some((w) => w.includes("pts is missing")));
  assert.ok(missing.warnings.some((w) => w.includes("headcoach pts is missing")));
});

test("simulateMatchV3 returns bounded probabilities and expected points", () => {
  const result = sim.simulateMatchV3(
    { players: playersFromPts(Array(11).fill(3)), headcoach: { pts: 4 } },
    { players: playersFromPts([3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2]), headcoach: { pts: 2 } },
    { useEmpiricalCalibration: false, maxGoals: 9 }
  );
  const total = result.probabilities.homeWin + result.probabilities.draw + result.probabilities.awayWin;
  assert.ok(Math.abs(total - 1) < 1e-6);
  assert.ok(result.expected.homePoints >= 0 && result.expected.homePoints <= 3);
  assert.ok(result.expected.awayPoints >= 0 && result.expected.awayPoints <= 3);
});
