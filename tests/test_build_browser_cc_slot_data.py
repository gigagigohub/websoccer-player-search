import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_browser_cc_slot_data.py"
SPEC = importlib.util.spec_from_file_location("build_browser_cc_slot_data", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBrowserCcSlotDataTests(unittest.TestCase):
    def test_build_payload_maps_supported_formation_and_keeps_unimplemented_player(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "browser.sqlite3"
            formations_path = root / "formations.json"
            players_path = root / "players.json"
            formations_path.write_text(
                json.dumps(
                    {
                        "formations": [
                            {"id": 1, "name": "バルセロナ", "year": 1999, "stride": 1}
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            players_path.write_text(
                json.dumps({"players": [{"id": 10, "name": "リンク済"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE browser_cc_matches (
                  platform TEXT, season INTEGER, world_id INTEGER, match_id INTEGER
                );
                CREATE TABLE browser_cc_teams (
                  platform TEXT, season INTEGER, world_id INTEGER, match_id INTEGER,
                  side TEXT, formation_id INTEGER, formation_name TEXT
                );
                CREATE TABLE browser_cc_players (
                  platform TEXT, formation_id INTEGER, member_order INTEGER,
                  player_id INTEGER, player_name TEXT, player_fullname TEXT,
                  is_starting11 INTEGER, pts REAL, goals INTEGER
                );
                CREATE TABLE browser_player_identity (
                  legacy_player_id INTEGER, smartphone_player_id INTEGER,
                  canonical_person_id INTEGER, link_level TEXT, match_method TEXT
                );
                CREATE TABLE browser_player_catalog (
                  legacy_player_id INTEGER, player_name TEXT, player_fullname TEXT,
                  rohm_category TEXT
                );
                """
            )
            conn.executemany(
                "INSERT INTO browser_cc_matches VALUES (?,?,?,?)",
                [("ymbga", 2814, 1, 1), ("mixi", 2814, 1, 2)],
            )
            conn.executemany(
                "INSERT INTO browser_cc_teams VALUES (?,?,?,?,?,?,?)",
                [
                    ("ymbga", 2814, 1, 1, "home", 101, "バルセロナ 1999-00"),
                    ("mixi", 2814, 1, 2, "home", 202, "スマホ未実装 2020-21"),
                ],
            )
            conn.executemany(
                "INSERT INTO browser_cc_players VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    ("ymbga", 101, 1, 1001, "リンク済", "リンク済選手", 1, 4, 1),
                    ("ymbga", 101, 1, 1002, "旧選手", "旧選手フル", 1, 2, 0),
                    ("mixi", 202, 1, 1001, "除外選手", "除外選手", 1, 5, 0),
                ],
            )
            conn.executemany(
                "INSERT INTO browser_player_identity VALUES (?,?,?,?,?)",
                [
                    (1001, 10, 10, "card_exact", "image"),
                    (1002, None, 20, "person", "fullname"),
                ],
            )
            conn.executemany(
                "INSERT INTO browser_player_catalog VALUES (?,?,?,?)",
                [
                    (1001, "リンク済", "リンク済選手", "無"),
                    (1002, "旧選手 (引退(銅))", "旧選手フル", "retire"),
                ],
            )
            conn.commit()
            conn.close()

            payload = MODULE.build_payload(db_path, formations_path, players_path)
            self.assertEqual(payload["formationMapping"]["mappedBrowserFormations"], 1)
            self.assertEqual(len(payload["formationMapping"]["missing"]), 1)
            self.assertNotIn("202", payload["formations"])
            slot = payload["formations"]["1"]["platforms"]["ymbga"]["slots"]["1"]
            self.assertEqual(slot["totalUses"], 2)
            self.assertEqual(slot["rows"][0]["localPlayerId"], 10)
            unimplemented = next(row for row in slot["rows"] if row["legacyPlayerId"] == 1002)
            self.assertIsNone(unimplemented["localPlayerId"])
            self.assertEqual(unimplemented["rohmCategory"], "引退(銅)")

    def test_duplicate_local_formation_label_is_ambiguous(self):
        mapped, missing, ambiguous = MODULE.build_formation_map(
            [
                {"id": 1, "name": "フランス", "year": 1982, "stride": 0},
                {"id": 2, "name": "フランス", "year": 1982, "stride": 0},
            ],
            [
                {
                    "browserFormationId": 28,
                    "browserFormationName": "フランス 1982",
                    "teamRows": 22,
                }
            ],
        )
        self.assertEqual(mapped, {})
        self.assertEqual(missing, [])
        self.assertEqual(ambiguous[0]["candidateLocalFormationIds"], [1, 2])


if __name__ == "__main__":
    unittest.main()
