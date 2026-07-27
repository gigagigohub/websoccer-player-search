import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from export_site_json_from_master_db import build_scouts  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
