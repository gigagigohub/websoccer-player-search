import unittest

from websoccer_analysis.simulation.v4_clean_uniform import (
    UNIFORM_KEY_WEIGHT,
    UNIFORM_SLOT_WEIGHT,
    calc_team_v4_clean_uniform_index,
)


class V4CleanUniformIndexTest(unittest.TestCase):
    def setUp(self):
        self.slot_player_ids = {slot: 1000 + slot for slot in range(1, 12)}
        self.player_point_by_id = {1000 + slot: float(slot) / 2 for slot in range(1, 12)}
        self.formation_key_slots = {
            101: {
                1: 10,
                2: 9,
                3: 11,
                4: 8,
                99: 1,
            }
        }
        self.formation_power = {101: 0.2}

    def test_calculates_uniform_index_without_coach_power_by_default(self):
        result = calc_team_v4_clean_uniform_index(
            formation_id=101,
            headcoach_id=5,
            slot_player_ids=self.slot_player_ids,
            player_point_by_id=self.player_point_by_id,
            formation_key_slots=self.formation_key_slots,
            formation_power=self.formation_power,
            coach_power_by_id={5: 10.0},
        )

        starting_sum = sum(self.player_point_by_id.values())
        key_sum = (
            self.player_point_by_id[1010]
            + self.player_point_by_id[1009]
            + self.player_point_by_id[1011]
            + self.player_point_by_id[1008]
        )
        expected_total = 0.2 + UNIFORM_SLOT_WEIGHT * starting_sum + UNIFORM_KEY_WEIGHT * key_sum

        self.assertAlmostEqual(result.starting11_point_sum, starting_sum)
        self.assertAlmostEqual(result.starting11_contribution, UNIFORM_SLOT_WEIGHT * starting_sum)
        self.assertAlmostEqual(result.keyslot_point_sum, key_sum)
        self.assertAlmostEqual(result.keyslot_contribution, UNIFORM_KEY_WEIGHT * key_sum)
        self.assertAlmostEqual(result.formation_contribution, 0.2)
        self.assertAlmostEqual(result.coach_contribution, 0.0)
        self.assertAlmostEqual(result.total_index, expected_total)
        self.assertEqual(len(result.slot_breakdown), 11)
        self.assertEqual(len(result.keyslot_breakdown), 4)
        self.assertEqual({x.slot_no for x in result.slot_breakdown if x.is_keyslot}, {8, 9, 10, 11})
        self.assertTrue(all(x.weight == UNIFORM_SLOT_WEIGHT for x in result.slot_breakdown))
        self.assertTrue(all(x.weight == UNIFORM_KEY_WEIGHT for x in result.keyslot_breakdown))

    def test_optional_coach_power_is_only_added_when_enabled(self):
        result = calc_team_v4_clean_uniform_index(
            formation_id=101,
            headcoach_id=5,
            slot_player_ids=self.slot_player_ids,
            player_point_by_id=self.player_point_by_id,
            formation_key_slots=self.formation_key_slots,
            formation_power=self.formation_power,
            coach_power_by_id={5: -0.3},
            include_coach_power=True,
        )

        self.assertAlmostEqual(result.coach_contribution, -0.3)

    def test_unknown_formation_power_defaults_to_zero(self):
        result = calc_team_v4_clean_uniform_index(
            formation_id=999,
            headcoach_id=None,
            slot_player_ids=self.slot_player_ids,
            player_point_by_id=self.player_point_by_id,
            formation_key_slots=self.formation_key_slots,
            formation_power=self.formation_power,
        )

        self.assertAlmostEqual(result.formation_contribution, 0.0)
        self.assertAlmostEqual(result.keyslot_point_sum, 0.0)
        self.assertEqual(result.keyslot_breakdown, [])

    def test_missing_slot_raises_value_error(self):
        slot_player_ids = dict(self.slot_player_ids)
        del slot_player_ids[11]

        with self.assertRaisesRegex(ValueError, "missing required slots"):
            calc_team_v4_clean_uniform_index(
                formation_id=101,
                headcoach_id=None,
                slot_player_ids=slot_player_ids,
                player_point_by_id=self.player_point_by_id,
                formation_key_slots=self.formation_key_slots,
                formation_power=self.formation_power,
            )

    def test_missing_player_point_raises_value_error(self):
        player_point_by_id = dict(self.player_point_by_id)
        del player_point_by_id[1005]

        with self.assertRaisesRegex(ValueError, "missing player_id: 1005"):
            calc_team_v4_clean_uniform_index(
                formation_id=101,
                headcoach_id=None,
                slot_player_ids=self.slot_player_ids,
                player_point_by_id=player_point_by_id,
                formation_key_slots=self.formation_key_slots,
                formation_power=self.formation_power,
            )

    def test_invalid_keyslot_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "invalid slot"):
            calc_team_v4_clean_uniform_index(
                formation_id=101,
                headcoach_id=None,
                slot_player_ids=self.slot_player_ids,
                player_point_by_id=self.player_point_by_id,
                formation_key_slots={101: {1: 12}},
                formation_power=self.formation_power,
            )


if __name__ == "__main__":
    unittest.main()
