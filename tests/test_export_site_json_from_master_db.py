import sys
import sqlite3
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from export_site_json_from_master_db import build_players, build_scouts  # noqa: E402


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _query):
        return _Cursor(self._rows)


def scout_row(**overrides):
    row = {
        "event_id": 207,
        "name": "",
        "start": "2026-07-29 22:00:00",
        "end": "2026-08-19 19:00:00",
        "type": 50,
        "version": 330,
        "notes": "",
        "name_raw": "",
        "name_source": "",
        "player_count": 2,
        "player_ids_json": "[3260, 3261]",
    }
    row.update(overrides)
    return row


class BuildScoutsTest(unittest.TestCase):
    def test_preserves_existing_manual_name_when_master_db_name_is_blank(self):
        fallback = {
            207: {
                "name": "World2",
                "nameRaw": "ワールドスカウトその2",
                "nameSource": "manual_from_shop_button",
            }
        }

        scouts = build_scouts(_Connection([scout_row()]), {207}, fallback)

        self.assertEqual(scouts[0]["name"], "World2")
        self.assertEqual(scouts[0]["nameRaw"], "ワールドスカウトその2")
        self.assertEqual(scouts[0]["nameSource"], "manual_from_shop_button")
        self.assertEqual(scouts[0]["shopButtonImage"], "./images/Shop/btn/ss_btn_207.png")

    def test_master_db_name_takes_precedence_over_fallback(self):
        fallback = {
            207: {
                "name": "World2",
                "nameRaw": "ワールドスカウトその2",
                "nameSource": "manual_from_shop_button",
            }
        }
        row = scout_row(name="Database Name", name_raw="DB Raw", name_source="original")

        scouts = build_scouts(_Connection([row]), set(), fallback)

        self.assertEqual(scouts[0]["name"], "Database Name")
        self.assertEqual(scouts[0]["nameRaw"], "DB Raw")
        self.assertEqual(scouts[0]["nameSource"], "original")


class PlayerImageAvailabilityTest(unittest.TestCase):
    def test_nr_player_waits_for_image_then_recovers_when_asset_arrives(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.executescript("""
            CREATE TABLE ao__ZMONATION (ZNATION_ID INTEGER, ZNAME TEXT);
            CREATE TABLE ao__ZMOPLAYERSINFO
                (Z_PK INTEGER, ZPLAY_TYPE TEXT, ZDESCRIPTION_TEXT TEXT);
            CREATE TABLE ao__ZMOPLAYER (ZPLAYER_ID INTEGER, ZNAME TEXT);
            CREATE TABLE player_person_identity
                (player_id INTEGER, raw_person_id INTEGER,
                 canonical_person_id INTEGER, is_override INTEGER);
            CREATE TABLE ao__ZMOPLAYERSPARAM (ZPLAYER_ID INTEGER);
            CREATE TABLE manual_player_category
                (player_id INTEGER, category TEXT, category_membership_json TEXT);
            INSERT INTO ao__ZMOPLAYER VALUES (3314, 'サリバウィ');
            INSERT INTO player_person_identity VALUES (3314, 3314, 3314, 0);
            INSERT INTO manual_player_category VALUES (3314, 'NR', '["NR"]');
        """)
        before = build_players(conn, {}, set())[0]
        self.assertEqual(before["category"], "NR")
        self.assertFalse(before["categoryPending"])
        self.assertTrue(before["imagePending"])
        after = build_players(conn, {}, {3314})[0]
        self.assertFalse(after["imagePending"])


if __name__ == "__main__":
    unittest.main()
