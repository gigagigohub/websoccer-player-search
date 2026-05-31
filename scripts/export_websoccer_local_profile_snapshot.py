#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export a safe summary of a local WebSoccer Mac profile.")
    p.add_argument("--profile-data", required=True, help="Profile Data directory, or a backup directory containing Documents/Model/Model.sqlite.")
    p.add_argument("--out-dir", default="", help="Output directory. Default: <profile-data>/profile_snapshot.")
    return p.parse_args()


def dict_rows(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, params)]


def main() -> int:
    args = parse_args()
    profile = Path(args.profile_data).expanduser().resolve()
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found: {db}")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else profile / "profile_snapshot"
    out_dir.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    team_rows = dict_rows(
        con,
        """
        select
          t.ZTEAM_ID as teamId,
          t.ZNAME as teamName,
          t.ZOWNER_NAME as ownerName,
          t.ZSZN as season,
          t.ZWORLD_ID as worldId,
          t.ZLEAGUE as leagueField,
          w.ZNAME as worldName,
          l.ZGROUP_NAME as leagueGroupName,
          l.ZID as leagueId
        from ZMOTEAMDATA t
        left join ZMOWORLD w on w.ZID = t.ZWORLD_ID
        left join ZMOLEAGUE l on l.Z_PK = t.ZLEAGUE
        limit 1
        """,
    )
    team = team_rows[0] if team_rows else {}

    players = dict_rows(
        con,
        """
        select
          tp.ZPLAYER_NO as rosterNo,
          tp.ZPOS_NO as posNo,
          tp.ZGET_SEASON as acquiredSeason,
          p.ZPLAYER_ID as playerId,
          p.ZPERSON_ID as personId,
          p.ZNAME as name,
          p.ZFULLNAME as fullName,
          p.ZRARITY as rarity,
          p.ZPOS_TYPE as posType,
          p.ZPOS_ROLE as posRole,
          pp.ZSZN_NO as paramSeasonNo,
          pp.ZPWR as power,
          pp.ZTEC as technique,
          pp.ZSPD as speed,
          pp.ZSTM as stamina,
          pp.ZTMP as temperament
        from ZMOTEAMSPLAYER tp
        left join ZMOPLAYER p on p.Z_PK = tp.ZPLAYER
        left join ZMOPLAYERSPARAM pp on pp.Z_PK = tp.ZPLAYER_PARAM
        order by tp.ZPLAYER_NO
        """,
    )
    for player in players:
        season_no = player.get("paramSeasonNo")
        player["termNo"] = int(season_no) + 1 if isinstance(season_no, int) else None
    coach_rows = dict_rows(
        con,
        """
        select
          th.ZGET_SEASON as acquiredSeason,
          th.ZRATING as rating,
          h.ZHEADCOACH_ID as headcoachId,
          h.ZNAME as name,
          h.ZFULLNAME as fullName,
          h.ZRARITY as rarity
        from ZMOTEAMSHEADCOACH th
        left join ZMOHEADCOACH h on h.Z_PK = th.ZHEADCOACH
        order by th.Z_PK
        """,
    )
    funds_rows = dict_rows(con, "select ZBONUS as bonus, ZGOLD as gold, ZPOINT as point, ZTICKET as ticket from ZMOTEAMFUNDS")
    player_get_seasons = dict_rows(con, "select ZGET_SEASON as season, count(*) as players from ZMOTEAMSPLAYER group by ZGET_SEASON order by ZGET_SEASON")

    summary = {
        "profileData": str(profile),
        "team": team,
        "coach": coach_rows[0] if coach_rows else None,
        "funds": funds_rows[0] if funds_rows else None,
        "playerCount": len(players),
        "playerAcquiredSeasons": player_get_seasons,
        "players": players,
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "players.csv").open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "rosterNo",
            "posNo",
            "acquiredSeason",
            "playerId",
            "personId",
            "name",
            "fullName",
            "rarity",
            "posType",
            "posRole",
            "paramSeasonNo",
            "termNo",
            "power",
            "technique",
            "speed",
            "stamina",
            "temperament",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(players)
    con.close()

    print(f"[DONE] wrote {out_dir / 'summary.json'}")
    print(f"[DONE] wrote {out_dir / 'players.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
