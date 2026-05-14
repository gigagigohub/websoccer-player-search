(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.WsSimulationV3 = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const DEFAULT_BIN_WIDTH = 2;
  const DEFAULT_MAX_GOALS = 9;
  const DEFAULT_ALPHA = 1;
  const DEFAULT_MIN_SAMPLE_SIZE = 30;
  const VALID_POS_CODES = new Set([1, 2, 3, 4]);

  function toNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function round(value, digits = 4) {
    const scale = 10 ** digits;
    return Math.round((Number(value) || 0) * scale) / scale;
  }

  function calculateLineBreakdown(players) {
    const breakdown = { fwPts: 0, mfPts: 0, dfPts: 0, gkPts: 0 };
    for (const player of players || []) {
      if (player && player.isStarting11 === false) continue;
      const pts = toNumber(player?.pts) ?? 0;
      const pos = Number(player?.posCode14);
      if (pos === 1) breakdown.fwPts += pts;
      else if (pos === 2) breakdown.mfPts += pts;
      else if (pos === 3) breakdown.dfPts += pts;
      else if (pos === 4) breakdown.gkPts += pts;
    }
    return {
      fwPts: round(breakdown.fwPts, 4),
      mfPts: round(breakdown.mfPts, 4),
      dfPts: round(breakdown.dfPts, 4),
      gkPts: round(breakdown.gkPts, 4),
    };
  }

  function calculateTeamIndexV3(teamInput, sideLabel = "Team") {
    const warnings = [];
    const players = Array.isArray(teamInput?.players) ? teamInput.players : [];
    const starters = players.filter((p) => p && p.isStarting11 !== false);
    if (starters.length !== 11) {
      warnings.push(`${sideLabel}: starting11 count is ${starters.length}, expected 11.`);
    }

    let starterPtsSum = 0;
    starters.forEach((player, idx) => {
      const pts = toNumber(player?.pts);
      if (pts === null) {
        warnings.push(`${sideLabel}: player ${idx + 1} pts is missing or invalid; treated as 0.`);
      } else {
        starterPtsSum += pts;
      }
      const pos = Number(player?.posCode14);
      if (!VALID_POS_CODES.has(pos)) {
        warnings.push(`${sideLabel}: player ${idx + 1} pos_code_1_4 is invalid.`);
      }
    });

    const headcoachPtsRaw = toNumber(teamInput?.headcoach?.pts);
    const headcoachPts = headcoachPtsRaw ?? 0;
    if (headcoachPtsRaw === null) {
      warnings.push(`${sideLabel}: headcoach pts is missing; treated as 0.`);
    }

    const lineBreakdown = calculateLineBreakdown(starters);
    const teamIndex = starterPtsSum + headcoachPts;
    return {
      teamIndex: round(teamIndex, 4),
      starterPtsSum: round(starterPtsSum, 4),
      headcoachPts: round(headcoachPts, 4),
      starterCount: starters.length,
      lineBreakdown,
      warnings,
    };
  }

  function calculateIndexDiff(homeIndex, awayIndex) {
    return round((Number(homeIndex) || 0) - (Number(awayIndex) || 0), 4);
  }

  function calculateExpectedGoalsFallback(indexDiff) {
    const diff = Number(indexDiff) || 0;
    const goalDiffExpected = 0.015852 + 0.178095 * diff;
    const totalGoalsExpected = 2.893821 + 0.073914 * Math.abs(diff);
    return {
      homeGoals: Math.max(0.05, (totalGoalsExpected + goalDiffExpected) / 2),
      awayGoals: Math.max(0.05, (totalGoalsExpected - goalDiffExpected) / 2),
      goalDiffExpected,
      totalGoalsExpected,
    };
  }

  function factorial(k) {
    let v = 1;
    for (let i = 2; i <= k; i += 1) v *= i;
    return v;
  }

  function poisson(lambda, k) {
    const l = Math.max(0.000001, Number(lambda) || 0);
    const n = Math.max(0, Math.floor(Number(k) || 0));
    return Math.exp(-l) * (l ** n) / factorial(n);
  }

  function buildScoreDistribution(homeExpectedGoals, awayExpectedGoals, maxGoals = DEFAULT_MAX_GOALS) {
    const limit = Math.max(1, Math.floor(Number(maxGoals) || DEFAULT_MAX_GOALS));
    const rows = [];
    let total = 0;
    for (let h = 0; h <= limit; h += 1) {
      for (let a = 0; a <= limit; a += 1) {
        const probability = poisson(homeExpectedGoals, h) * poisson(awayExpectedGoals, a);
        total += probability;
        rows.push({ homeGoals: h, awayGoals: a, probability });
      }
    }
    const norm = total > 0 ? total : 1;
    return rows
      .map((row) => ({ ...row, probability: row.probability / norm }))
      .sort((a, b) => b.probability - a.probability || a.homeGoals - b.homeGoals || a.awayGoals - b.awayGoals);
  }

  function calculateProbabilitiesFromScoreDistribution(scoreDistribution) {
    let homeWin = 0;
    let draw = 0;
    let awayWin = 0;
    for (const row of scoreDistribution || []) {
      const p = Number(row.probability) || 0;
      if (row.homeGoals > row.awayGoals) homeWin += p;
      else if (row.homeGoals === row.awayGoals) draw += p;
      else awayWin += p;
    }
    const total = homeWin + draw + awayWin;
    if (total > 0) {
      homeWin /= total;
      draw /= total;
      awayWin /= total;
    }
    return { homeWin, draw, awayWin };
  }

  function calculateExpectedPoints(probabilities) {
    const homeWin = Number(probabilities?.homeWin) || 0;
    const draw = Number(probabilities?.draw) || 0;
    const awayWin = Number(probabilities?.awayWin) || 0;
    return {
      homePoints: 3 * homeWin + draw,
      awayPoints: 3 * awayWin + draw,
    };
  }

  function bucketForDiff(indexDiff, binWidth = DEFAULT_BIN_WIDTH) {
    const width = Math.max(0.1, Number(binWidth) || DEFAULT_BIN_WIDTH);
    return Math.floor((Number(indexDiff) || 0) / width) * width;
  }

  function mergeBucketRows(rows) {
    const merged = {
      n: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      homeGoalsWeighted: 0,
      awayGoalsWeighted: 0,
      buckets: [],
    };
    for (const row of rows || []) {
      const n = Number(row.n) || 0;
      merged.n += n;
      merged.wins += Number(row.wins) || 0;
      merged.draws += Number(row.draws) || 0;
      merged.losses += Number(row.losses) || 0;
      merged.homeGoalsWeighted += (Number(row.avgHomeGoals) || 0) * n;
      merged.awayGoalsWeighted += (Number(row.avgAwayGoals) || 0) * n;
      merged.buckets.push(row.bucket);
    }
    if (merged.n > 0) {
      merged.avgHomeGoals = merged.homeGoalsWeighted / merged.n;
      merged.avgAwayGoals = merged.awayGoalsWeighted / merged.n;
    }
    return merged;
  }

  function getEmpiricalExpectation(indexDiff, calibration, options = {}) {
    if (!calibration || !Array.isArray(calibration.buckets) || !calibration.buckets.length) return null;
    const binWidth = Number(options.binWidth || calibration.binWidth || DEFAULT_BIN_WIDTH);
    const minSampleSize = Number(options.minSampleSize || calibration.minSampleSize || DEFAULT_MIN_SAMPLE_SIZE);
    const target = bucketForDiff(indexDiff, binWidth);
    const byBucket = new Map(calibration.buckets.map((row) => [Number(row.bucket), row]));
    const maxRadius = Number(options.maxMergeRadius ?? 4);
    for (let radius = 0; radius <= maxRadius; radius += 1) {
      const rows = [];
      for (let step = -radius; step <= radius; step += 1) {
        const row = byBucket.get(target + step * binWidth);
        if (row) rows.push(row);
      }
      const merged = mergeBucketRows(rows);
      if (merged.n >= minSampleSize) {
        const alpha = Number(options.alpha || calibration.alpha || DEFAULT_ALPHA);
        const denom = merged.n + 3 * alpha;
        return {
          probabilities: {
            homeWin: (merged.wins + alpha) / denom,
            draw: (merged.draws + alpha) / denom,
            awayWin: (merged.losses + alpha) / denom,
          },
          expectedGoals: {
            homeGoals: Math.max(0.05, merged.avgHomeGoals || 0),
            awayGoals: Math.max(0.05, merged.avgAwayGoals || 0),
          },
          meta: {
            calibration: radius === 0 ? "empirical" : "empirical-merged",
            binWidth,
            bucket: target,
            sampleSize: merged.n,
            mergedBuckets: merged.buckets,
          },
        };
      }
    }
    return null;
  }

  function simulateMatchV3(homeInput, awayInput, options = {}) {
    const home = calculateTeamIndexV3(homeInput, "Home");
    const away = calculateTeamIndexV3(awayInput, "Away");
    const indexDiff = calculateIndexDiff(home.teamIndex, away.teamIndex);
    const maxGoals = options.maxGoals ?? DEFAULT_MAX_GOALS;
    const calibration = options.calibration || null;
    let source = null;

    if (options.useEmpiricalCalibration !== false) {
      source = getEmpiricalExpectation(indexDiff, calibration, options);
    }

    let probabilities;
    let expectedGoals;
    let meta;
    if (source) {
      probabilities = source.probabilities;
      expectedGoals = source.expectedGoals;
      meta = source.meta;
    } else {
      expectedGoals = calculateExpectedGoalsFallback(indexDiff);
      const distribution = buildScoreDistribution(expectedGoals.homeGoals, expectedGoals.awayGoals, maxGoals);
      probabilities = calculateProbabilitiesFromScoreDistribution(distribution);
      meta = {
        calibration: "fallback",
        binWidth: options.binWidth || calibration?.binWidth || DEFAULT_BIN_WIDTH,
        bucket: bucketForDiff(indexDiff, options.binWidth || calibration?.binWidth || DEFAULT_BIN_WIDTH),
        sampleSize: 0,
      };
    }

    const scoreDistribution = buildScoreDistribution(expectedGoals.homeGoals, expectedGoals.awayGoals, maxGoals);
    const expectedPoints = calculateExpectedPoints(probabilities);
    const probabilityTotal = probabilities.homeWin + probabilities.draw + probabilities.awayWin;
    const warnings = [...home.warnings, ...away.warnings];
    if (Math.abs(probabilityTotal - 1) > 0.001) warnings.push("Probability total is not close to 1.0.");
    if (expectedPoints.homePoints < -0.001 || expectedPoints.homePoints > 3.001) warnings.push("Home expected points is out of range.");
    if (expectedPoints.awayPoints < -0.001 || expectedPoints.awayPoints > 3.001) warnings.push("Away expected points is out of range.");

    return {
      model: "v3",
      home,
      away,
      indexDiff,
      probabilities,
      expected: {
        homePoints: expectedPoints.homePoints,
        awayPoints: expectedPoints.awayPoints,
        homeGoals: expectedGoals.homeGoals,
        awayGoals: expectedGoals.awayGoals,
      },
      scoreDistribution,
      meta,
      warnings,
    };
  }

  return {
    calculateTeamIndexV3,
    calculateLineBreakdown,
    calculateIndexDiff,
    calculateExpectedGoalsFallback,
    poisson,
    buildScoreDistribution,
    calculateProbabilitiesFromScoreDistribution,
    calculateExpectedPoints,
    bucketForDiff,
    getEmpiricalExpectation,
    simulateMatchV3,
  };
});
