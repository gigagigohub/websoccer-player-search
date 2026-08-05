import json
import tempfile
import unittest
from pathlib import Path


import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import formation_matchup_model as model


class FormationMatchupModelTests(unittest.TestCase):
    def test_usage_template_resolves_duplicate_into_feasible_eleven(self):
        slots = {
            slot: [
                {
                    "playerId": slot,
                    "uses": 10,
                    "usageRate": 0.8,
                    "avgPts": 3.0,
                }
            ]
            for slot in range(1, 12)
        }
        slots[2] = [
            {"playerId": 1, "uses": 9, "usageRate": 0.9, "avgPts": 3.0},
            {"playerId": 22, "uses": 7, "usageRate": 0.7, "avgPts": 3.0},
        ]
        slots[1].append(
            {"playerId": 21, "uses": 1, "usageRate": 0.1, "avgPts": 3.0}
        )
        templates, overrides = model.build_usage_templates(
            {10: slots},
            {10: [{"coachId": 3, "uses": 20, "usageRate": 0.8, "avgPts": 3.0}]},
        )

        self.assertEqual(len(set(templates[10]["players"])), 11)
        self.assertEqual(templates[10]["players"][0], 1)
        self.assertEqual(templates[10]["players"][1], 22)
        self.assertEqual(templates[10]["coachId"], 3)
        self.assertEqual(overrides[0]["slot"], 2)

    def test_secondary_template_uses_own_ten_percent_threshold(self):
        slots = {
            slot: [
                {"playerId": slot, "uses": 70, "usageRate": 0.70, "avgPts": 3.0},
                {"playerId": 100 + slot, "uses": 10, "usageRate": 0.10, "avgPts": 2.5},
                {"playerId": 200 + slot, "uses": 9, "usageRate": 0.09, "avgPts": 3.5},
            ]
            for slot in range(1, 12)
        }
        strict, _ = model.build_usage_templates(
            {10: slots},
            {10: [{"coachId": 3, "uses": 20, "usageRate": 0.8, "avgPts": 3.0}]},
        )
        candidates = model.build_usage_candidate_sets({10: slots}, strict)

        self.assertEqual(candidates[10][1], [1, 101])
        self.assertNotIn(201, candidates[10][1])

    def test_guard_loader_requires_executed_successful_cc_hide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "execute": True,
                "teams": [
                    {
                        "season": 2635,
                        "worldId": 20,
                        "desiredLineupMode": "hide_fixed",
                        "lineupModeDecision": {"reason": "same_agent_cc_preliminary_lower_rank_hides"},
                        "lineup": {"update": {"status": "updated"}},
                        "targetSlotMatches": [
                            {"prefix": "Cc", "matchId": "12345"},
                            {"prefix": "League", "matchId": "99999"},
                        ],
                    },
                    {
                        "season": 2635,
                        "worldId": 20,
                        "desiredLineupMode": "hide_fixed",
                        "lineup": {"update": {"status": "failed"}},
                        "targetSlotMatches": [{"prefix": "Cc", "matchId": "54321"}],
                    },
                ],
            }
            (root / "team_agent_match_guard_20260101_001500_000001.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            exclusions, meta = model.load_guard_exclusions(root)

        self.assertEqual(exclusions, {(2635, 20, 12345)})
        self.assertEqual(meta["evidenceRows"], 1)
        self.assertEqual(meta["uniqueMatches"], 1)

    def test_repeated_team_pair_total_weight_is_capped(self):
        matches = [
            {
                "homeTeam": 1,
                "awayTeam": 2,
                "homeFormation": 10,
                "awayFormation": 20,
                "season": season,
            }
            for season in range(10)
        ]
        weighted = model.assign_capped_weights(matches, cap=3.0)
        self.assertAlmostEqual(sum(row["weight"] for row in weighted), 3.0)
        self.assertTrue(all(row["repeatCount"] == 10 for row in weighted))

    def test_pair_effect_is_directionally_antisymmetric(self):
        scored = []
        for idx in range(18):
            scored.append(
                {
                    "homeFormation": 10 if idx % 2 == 0 else 20,
                    "awayFormation": 20 if idx % 2 == 0 else 10,
                    "homeTeam": 1000 + idx,
                    "awayTeam": 2000 + idx,
                    "season": 2600 + idx,
                    "world": 1 + idx % 8,
                    "weight": 1.0,
                    "y": 1.0 if idx % 2 == 0 else -1.0,
                    "residual": 0.65 if idx % 2 == 0 else -0.65,
                }
            )
        config = model.MatchupConfig(
            min_matches=10,
            min_effective_matches=8,
            min_unique_team_pairs=6,
            min_unique_teams_each=3,
            min_seasons=3,
            min_worlds=3,
            matchup_prior=3.0,
        )
        pairs = model._aggregate_pair_stats(scored, config)
        pair = pairs[(10, 20)]
        low = model._directional_row(pair, True, pair, pair, config)
        high = model._directional_row(pair, False, pair, pair, config)

        self.assertGreater(low["delta"], 0)
        self.assertAlmostEqual(low["delta"], -high["delta"])
        self.assertEqual(low["wins"], high["losses"])
        self.assertEqual(low["losses"], high["wins"])
        self.assertAlmostEqual(low["ciLow"], -high["ciHigh"])
        self.assertAlmostEqual(low["ciHigh"], -high["ciLow"])

    def test_group_scope_and_guard_exclusion_are_reported(self):
        match_rows = []
        team_rows = []
        for idx in range(8):
            season = 2600 + idx
            match_id = 100 + idx
            match_rows.append(
                {
                    "season": season,
                    "world_id": 1 + idx % 4,
                    "match_id": match_id,
                    "title": f"{season} チャンピオンズカップ グループステージ グループA 第1節",
                }
            )
            for side, team_id, formation_id, result in (
                ("home", 1000 + idx, 10, "W"),
                ("away", 2000 + idx, 20, "L"),
            ):
                team_rows.append(
                    {
                        "season": season,
                        "world_id": 1 + idx % 4,
                        "match_id": match_id,
                        "side": side,
                        "team_id": team_id,
                        "formation_id": formation_id,
                        "headcoach_id": 1 if side == "home" else 2,
                        "result": result,
                    }
                )
        guard = {(2600, 1, 100)}
        config = model.MatchupConfig(
            min_matches=3,
            min_effective_matches=3,
            min_unique_team_pairs=3,
            min_unique_teams_each=3,
            min_seasons=3,
            min_worlds=3,
            coordinate_iterations=5,
        )
        output = model.build_bias_aware_matchups(
            team_rows, match_rows, guard_exclusions=guard, config=config
        )

        self.assertEqual(output["meta"]["guardExcludedMatches"], 1)
        self.assertEqual(output["meta"]["primary"]["matches"], 7)
        self.assertEqual(output["meta"]["allStagesSensitivity"]["matches"], 7)

    def test_template_explorer_counts_slot_difference_coach_and_cc_upgrade(self):
        match_rows = [
            {
                "season": 2600,
                "world_id": 1,
                "match_id": 100,
                "title": "2600 チャンピオンズカップ グループステージ グループA 第1節",
            }
        ]
        team_rows = [
            {
                "season": 2600,
                "world_id": 1,
                "match_id": 100,
                "side": "home",
                "team_id": 1,
                "formation_id": 10,
                "headcoach_id": 1,
                "result": "W",
            },
            {
                "season": 2600,
                "world_id": 1,
                "match_id": 100,
                "side": "away",
                "team_id": 2,
                "formation_id": 20,
                "headcoach_id": 9,
                "result": "L",
            },
        ]
        slot_stats = {}
        coach_stats = {}
        player_rows = []
        for formation_id, base, side in ((10, 0, "home"), (20, 100, "away")):
            slot_stats[formation_id] = {}
            for slot in range(1, 12):
                template_player = base + slot
                slot_stats[formation_id][slot] = [
                    {
                        "playerId": template_player,
                        "uses": 10,
                        "usageRate": 1.0,
                        "avgPts": 3.0,
                    }
                ]
                actual_player = 999 if formation_id == 10 and slot == 1 else template_player
                player_rows.append(
                    {
                        "season": 2600,
                        "world_id": 1,
                        "match_id": 100,
                        "side": side,
                        "member_order": slot,
                        "is_starting11": 1,
                        "player_id": actual_player,
                    }
                )
            coach_stats[formation_id] = [
                {
                    "coachId": 1 if formation_id == 10 else 2,
                    "uses": 10,
                    "usageRate": 1.0,
                    "avgPts": 3.0,
                }
            ]

        output = model.build_template_matchup_explorer(
            team_rows,
            match_rows,
            player_rows,
            slot_stats,
            coach_stats,
            player_categories={1: "NR", 999: "CC"},
            config=model.MatchupConfig(coordinate_iterations=2),
        )

        self.assertEqual(output["meta"]["explorerMatches"], 1)
        row = output["matches"][0]
        self.assertEqual(row["homeDifference"], 1)
        self.assertEqual(row["awayDifference"], 0)
        self.assertEqual(row["homeSecondaryDifference"], 1)
        self.assertEqual(row["awaySecondaryDifference"], 0)
        self.assertTrue(row["homeCoachExact"])
        self.assertFalse(row["awayCoachExact"])
        self.assertEqual(row["homeCcUpgradeCount"], 1)
        self.assertEqual(row["awayCcUpgradeCount"], 0)

    def test_secondary_template_accepts_rank_two_at_ten_percent(self):
        match_rows = [{
            "season": 2600,
            "world_id": 1,
            "match_id": 100,
            "title": "2600 チャンピオンズカップ グループステージ グループA 第1節",
        }]
        team_rows = []
        slot_stats = {}
        coach_stats = {}
        player_rows = []
        for formation_id, base, side, result in (
            (10, 0, "home", "W"),
            (20, 100, "away", "L"),
        ):
            team_rows.append({
                "season": 2600,
                "world_id": 1,
                "match_id": 100,
                "side": side,
                "team_id": formation_id,
                "formation_id": formation_id,
                "headcoach_id": 1,
                "result": result,
            })
            slot_stats[formation_id] = {}
            for slot in range(1, 12):
                first = base + slot
                second = base + 1000 + slot
                slot_stats[formation_id][slot] = [
                    {"playerId": first, "uses": 70, "usageRate": 0.70, "avgPts": 3.0},
                    {"playerId": second, "uses": 10, "usageRate": 0.10, "avgPts": 2.0},
                ]
                player_rows.append({
                    "season": 2600,
                    "world_id": 1,
                    "match_id": 100,
                    "side": side,
                    "member_order": slot,
                    "is_starting11": 1,
                    "player_id": second if formation_id == 10 and slot == 1 else first,
                })
            coach_stats[formation_id] = [
                {"coachId": 1, "uses": 10, "usageRate": 1.0, "avgPts": 3.0}
            ]

        output = model.build_template_matchup_explorer(
            team_rows,
            match_rows,
            player_rows,
            slot_stats,
            coach_stats,
            config=model.MatchupConfig(coordinate_iterations=2),
        )
        row = output["matches"][0]

        self.assertEqual(row["homeDifference"], 1)
        self.assertEqual(row["homeSecondaryDifference"], 0)
        secondary_exact = next(
            count
            for count in output["meta"]["scenarioCounts"]
            if count["templateMode"] == "secondary_usage_10"
            and count["maxDifferences"] == 0
            and not count["requireCoachMatch"]
            and not count["excludeCcUpgrades"]
        )
        self.assertEqual(secondary_exact["matches"], 1)


if __name__ == "__main__":
    unittest.main()
