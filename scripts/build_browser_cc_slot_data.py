#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path(
    "/Users/gigagigo/Codex/websoccer/wsc_data/browser_cc_archive/browser_cc_archive.sqlite3"
)
FORMATION_ALIASES = {
    "ロンドンT 2018-19": "トッテナム 2018-19",
}
PLATFORMS = ("ymbga", "mixi")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a static Yahoo!/mixi CC slot aggregate without mixing Rohm League-A stats."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--app-dir", type=Path, default=Path.cwd() / "app")
    parser.add_argument("--formations", type=Path)
    parser.add_argument("--players", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().replace("ヴァ", "バ")
    return re.sub(r"[\s・･\.\-‐‑‒–—―ー]", "", text)


def formation_year_label(year: Any, stride: Any) -> str:
    value = int(year or 0)
    if value <= 0:
        return ""
    if int(stride or 0) == 1:
        return f"{value}-{str((value + 1) % 100).zfill(2)}"
    return str(value)


def local_formation_label(formation: dict[str, Any]) -> str:
    year = formation_year_label(formation.get("year"), formation.get("stride"))
    return f"{formation.get('name') or ''} {year}".strip()


def build_formation_map(
    formations: list[dict[str, Any]],
    browser_formations: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    local_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for formation in formations:
        local_by_label[normalize(local_formation_label(formation))].append(formation)

    for browser_label, local_label in FORMATION_ALIASES.items():
        local_by_label[normalize(browser_label)] = [
            formation
            for formation in formations
            if local_formation_label(formation) == local_label
        ]

    mapped: dict[int, dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for browser in browser_formations:
        browser_id = int(browser.get("browserFormationId") or 0)
        browser_name = str(browser.get("browserFormationName") or "").strip()
        candidates = local_by_label.get(normalize(browser_name), [])
        record = {
            "browserFormationId": browser_id,
            "browserFormationName": browser_name,
            "teamRows": int(browser.get("teamRows") or 0),
        }
        if len(candidates) == 1:
            local = candidates[0]
            mapped[browser_id] = {
                **record,
                "localFormationId": int(local.get("id") or 0),
                "localFormationLabel": local_formation_label(local),
            }
        elif len(candidates) > 1:
            ambiguous.append(
                {
                    **record,
                    "candidateLocalFormationIds": [int(row.get("id") or 0) for row in candidates],
                }
            )
        else:
            missing.append(record)
    return mapped, missing, ambiguous


def browser_formation_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT formation_id, formation_name, COUNT(*) AS team_rows
        FROM browser_cc_teams
        WHERE formation_id IS NOT NULL AND formation_id > 0
        GROUP BY formation_id, formation_name
        ORDER BY formation_id, team_rows DESC
        """
    ).fetchall()
    # A browser formation ID is stable. Prefer its most frequently observed display name.
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        browser_id = int(row[0])
        team_rows = int(row[2] or 0)
        if browser_id not in by_id:
            by_id[browser_id] = {
                "browserFormationId": browser_id,
                "browserFormationName": str(row[1] or "").strip(),
                "teamRows": 0,
                "_preferredNameRows": -1,
            }
        record = by_id[browser_id]
        record["teamRows"] += team_rows
        if team_rows > int(record["_preferredNameRows"]):
            record["browserFormationName"] = str(row[1] or "").strip()
            record["_preferredNameRows"] = team_rows
    for record in by_id.values():
        record.pop("_preferredNameRows", None)
    return list(by_id.values())


def retired_category(player_name: str) -> str:
    match = re.search(r"\(引退\(([^)]+)\)\)\s*$", player_name)
    return f"引退({match.group(1)})" if match else "引退"


def display_rohm_category(category: Any, player_name: Any) -> str:
    value = str(category or "").strip()
    if value == "retire":
        return retired_category(str(player_name or ""))
    return value or "-"


def load_player_links(
    conn: sqlite3.Connection,
    smartphone_player_ids: set[int],
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          i.legacy_player_id,
          i.smartphone_player_id,
          i.canonical_person_id,
          i.link_level,
          i.match_method,
          c.player_name,
          c.player_fullname,
          c.rohm_category
        FROM browser_player_identity i
        LEFT JOIN browser_player_catalog c
          ON c.legacy_player_id = i.legacy_player_id
        """
    ).fetchall()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        legacy_id = int(row[0])
        candidate_player_id = int(row[1] or 0)
        local_player_id = (
            candidate_player_id if candidate_player_id in smartphone_player_ids else None
        )
        result[legacy_id] = {
            "localPlayerId": local_player_id,
            "canonicalPersonId": int(row[2] or 0) or None,
            "linkLevel": str(row[3] or "unlinked"),
            "matchMethod": str(row[4] or ""),
            "catalogPlayerName": str(row[5] or ""),
            "catalogPlayerFullName": str(row[6] or ""),
            "rohmCategory": display_rohm_category(row[7], row[5]),
        }
    return result


def aggregate_rows(
    conn: sqlite3.Connection,
    formation_map: dict[int, dict[str, Any]],
    player_links: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    rows = conn.execute(
        """
        SELECT
          platform,
          formation_id,
          member_order,
          player_id,
          MAX(player_name) AS player_name,
          MAX(player_fullname) AS player_fullname,
          COUNT(*) AS uses,
          SUM(COALESCE(pts, 0)) AS pts_sum,
          SUM(COALESCE(goals, 0)) AS goals
        FROM browser_cc_players
        WHERE is_starting11 = 1
          AND platform IN ('ymbga', 'mixi')
          AND member_order BETWEEN 1 AND 11
          AND formation_id IS NOT NULL
          AND player_id IS NOT NULL
          AND player_id > 0
        GROUP BY platform, formation_id, member_order, player_id
        ORDER BY platform, formation_id, member_order, uses DESC, player_id
        """
    )
    slot_totals: dict[tuple[int, str, int], int] = defaultdict(int)
    buckets: dict[tuple[int, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        platform = str(row[0])
        browser_formation_id = int(row[1] or 0)
        mapping = formation_map.get(browser_formation_id)
        if mapping is None:
            continue
        local_formation_id = int(mapping["localFormationId"])
        slot = int(row[2] or 0)
        legacy_player_id = int(row[3] or 0)
        uses = int(row[6] or 0)
        pts_sum = float(row[7] or 0)
        goals = int(row[8] or 0)
        link = player_links.get(
            legacy_player_id,
            {
                "localPlayerId": None,
                "canonicalPersonId": None,
                "linkLevel": "unlinked",
                "matchMethod": "",
                "catalogPlayerName": "",
                "catalogPlayerFullName": "",
                "rohmCategory": "-",
            },
        )
        player_name = str(row[4] or link.get("catalogPlayerName") or legacy_player_id)
        player_fullname = str(row[5] or link.get("catalogPlayerFullName") or player_name)
        key = (local_formation_id, platform, slot)
        slot_totals[key] += uses
        buckets[key].append(
            {
                "legacyPlayerId": legacy_player_id,
                "localPlayerId": link.get("localPlayerId"),
                "canonicalPersonId": link.get("canonicalPersonId"),
                "linkLevel": link.get("linkLevel") or "unlinked",
                "playerName": player_name,
                "playerFullName": player_fullname,
                "rohmCategory": link.get("rohmCategory") or "-",
                "uses": uses,
                "ptsSum": round(pts_sum, 4),
                "avgPts": round(pts_sum / uses, 4) if uses else 0.0,
                "goals": goals,
                "goalsPer7": round(goals / uses * 7, 4) if uses else 0.0,
            }
        )

    local_mapping_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for mapping in formation_map.values():
        local_mapping_rows[int(mapping["localFormationId"])].append(mapping)

    for (local_formation_id, platform, slot), items in buckets.items():
        total_uses = slot_totals[(local_formation_id, platform, slot)]
        items.sort(key=lambda item: (-int(item["uses"]), int(item["legacyPlayerId"])))
        for item in items:
            item["usageRate"] = round(int(item["uses"]) / total_uses, 6) if total_uses else 0.0
        formation = result.setdefault(
            str(local_formation_id),
            {
                "localFormationId": local_formation_id,
                "browserFormations": sorted(
                    local_mapping_rows[local_formation_id],
                    key=lambda item: int(item["browserFormationId"]),
                ),
                "platforms": {},
            },
        )
        platform_data = formation["platforms"].setdefault(platform, {"slots": {}})
        platform_data["slots"][str(slot)] = {
            "totalUses": total_uses,
            "rows": items,
        }
    return result


def build_payload(
    db_path: Path,
    formations_path: Path,
    players_path: Path,
) -> dict[str, Any]:
    formations_data = json.loads(formations_path.read_text(encoding="utf-8"))
    players_data = json.loads(players_path.read_text(encoding="utf-8"))
    formations = formations_data.get("formations") or []
    smartphone_player_ids = {
        int(player.get("id") or 0)
        for player in players_data.get("players") or []
        if int(player.get("id") or 0) > 0
    }

    conn = sqlite3.connect(str(db_path))
    try:
        browser_formations = browser_formation_rows(conn)
        formation_map, missing, ambiguous = build_formation_map(formations, browser_formations)
        player_links = load_player_links(conn, smartphone_player_ids)
        formation_data = aggregate_rows(conn, formation_map, player_links)
        platform_counts = {
            row[0]: {"matches": int(row[1]), "teamRows": int(row[2])}
            for row in conn.execute(
                """
                SELECT m.platform, COUNT(DISTINCT m.match_id), COUNT(t.side)
                FROM browser_cc_matches m
                LEFT JOIN browser_cc_teams t
                  ON t.platform=m.platform AND t.season=m.season
                 AND t.world_id=m.world_id AND t.match_id=m.match_id
                GROUP BY m.platform
                """
            )
        }
        seasons = {
            row[0]: sorted(int(value) for value in str(row[1] or "").split(",") if value)
            for row in conn.execute(
                """
                SELECT platform, GROUP_CONCAT(DISTINCT season)
                FROM browser_cc_matches
                GROUP BY platform
                """
            )
        }
    finally:
        conn.close()

    mapped_team_rows = sum(int(row.get("teamRows") or 0) for row in formation_map.values())
    excluded_team_rows = sum(int(row.get("teamRows") or 0) for row in missing + ambiguous)
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": "browser_cc_archive.sqlite3",
        "platforms": platform_counts,
        "seasons": seasons,
        "formationMapping": {
            "mappedBrowserFormations": len(formation_map),
            "mappedLocalFormations": len(formation_data),
            "mappedTeamRows": mapped_team_rows,
            "excludedTeamRows": excluded_team_rows,
            "missing": missing,
            "ambiguous": ambiguous,
        },
        "formations": formation_data,
    }


def main() -> int:
    args = parse_args()
    app_dir = args.app_dir.expanduser().resolve()
    formations_path = (args.formations or app_dir / "formations_data.json").expanduser().resolve()
    players_path = (args.players or app_dir / "data.json").expanduser().resolve()
    out_path = (args.out or app_dir / "browser_cc_slot_data.json").expanduser().resolve()
    payload = build_payload(args.db.expanduser().resolve(), formations_path, players_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    mapping = payload["formationMapping"]
    print(
        f"wrote {out_path} with {mapping['mappedBrowserFormations']} mapped browser formations "
        f"and {mapping['mappedLocalFormations']} local formation pages"
    )
    print(
        f"excluded {len(mapping['missing'])} missing and {len(mapping['ambiguous'])} ambiguous formations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
