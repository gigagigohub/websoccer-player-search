import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const elements = new Map();
const context = vm.createContext({
  Intl, URL, URLSearchParams,
  document: {
    querySelector: (id) => {
      if (!elements.has(id)) elements.set(id, { textContent: "", innerHTML: "" });
      return elements.get(id);
    },
  },
});
const source = fs.readFileSync(new URL("../app/hawk-cc.js", import.meta.url), "utf8");
vm.runInContext(source.replace(/\ninit\(\);\s*$/, ""), context);
const payload = JSON.parse(fs.readFileSync(new URL("../app/hawk_cc_data.json", import.meta.url), "utf8"));
const current = payload.seasons.find((s) => s.tournamentPreview?.length);
const season = structuredClone(current);
season.tournamentRounds = [];
season.summary.tournamentMatchCount = 0;
for (const group of season.groups) for (const match of group.matches) {
  match.completed = false;
  match.score = null;
}
for (const match of season.tournamentPreview) for (const side of ["home", "away"]) {
  match[side].provisional = true;
  match[side].beforeKickoff = true;
}
season.tournamentPreview[0].home.team = { name: "<script>alert(1)</script>" };
vm.runInContext(`activeSeason = ${JSON.stringify(season)}; renderGroups(); renderTournament();`, context);
assert.match(elements.get("#groupStageMeta").textContent, /開幕前/);
assert.equal(elements.get("#tournamentTabCount").textContent, "16枠");
const preview = elements.get("#ccTournament").innerHTML;
assert.equal((preview.match(/class="cc-qualifier"/g) || []).length, 16);
assert.equal((preview.match(/is-provisional/g) || []).length, 16);
assert.match(preview, /A組 1位/);
assert.match(preview, /B組 2位/);
assert.match(preview, /試合前の仮順位/);
assert.ok(!preview.includes("<script>"));
assert.match(preview, /&lt;script&gt;/);
const finished = payload.seasons.find((s) => s.tournamentRounds.length === 4);
assert.ok(finished, "completed season fixture");
vm.runInContext(`activeSeason = ${JSON.stringify(finished)}; renderTournament();`, context);
assert.ok(!elements.get("#ccTournament").innerHTML.includes("is-provisional"));
assert.match(elements.get("#ccTournament").innerHTML, /Final/);
console.log("CC Result: opening fixtures, 16 provisional slots, escaping, and completed season passed.");
