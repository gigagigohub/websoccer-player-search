import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_v4_slot_adjusted_team_power as tpi  # noqa: E402


class ChampionTpiGridTest(unittest.TestCase):
    def test_top_bucket_merges_all_tpi_values_at_or_above_90(self):
        self.assertEqual(tpi.tpi_grid_label(89.999), "85〜90")
        self.assertEqual(tpi.tpi_grid_label(90.0), "90以上")
        self.assertEqual(tpi.tpi_grid_label(99.999), "90以上")
        self.assertEqual(tpi.tpi_grid_label(100.0), "90以上")

    def test_combines_holdout_champion_summaries(self):
        summary = tpi.combine_champion_tpi_summaries(
            [
                {
                    "championIndexes": [65.0, 95.0],
                    "skippedFinals": 0,
                    "pkResolvedFinals": 1,
                    "gridStats": [
                        {"label": "65〜70", "champions": 1, "totalTeams": 20},
                        {"label": "90以上", "champions": 1, "totalTeams": 2},
                    ],
                },
                {
                    "championIndexes": [70.0],
                    "skippedFinals": 1,
                    "pkResolvedFinals": 0,
                    "gridStats": [
                        {"label": "65〜70", "champions": 0, "totalTeams": 10},
                        {"label": "70〜75", "champions": 1, "totalTeams": 8},
                    ],
                },
            ]
        )

        self.assertEqual(summary["sampleCount"], 3.0)
        self.assertEqual(summary["median"], 70.0)
        self.assertEqual(summary["skippedFinals"], 1.0)
        self.assertEqual(summary["pkResolvedFinals"], 1.0)
        self.assertEqual(
            summary["gridStats"],
            [
                {"label": "65〜70", "champions": 1, "totalTeams": 30},
                {"label": "70〜75", "champions": 1, "totalTeams": 8},
                {"label": "90以上", "champions": 1, "totalTeams": 2},
            ],
        )


if __name__ == "__main__":
    unittest.main()
