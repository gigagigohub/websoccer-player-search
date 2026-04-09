#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import plistlib
import re
import shutil
import sqlite3
import zipfile
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest p321/event202 + new players from Untitled.chlz into master DB")
    p.add_argument("--master-db-dir", default=str(Path.home() / "Desktop" / "websoccer_master_db"))
    p.add_argument("--chlz", default=str(Path.home() / "Desktop" / "Untitled.chlz"))
    p.add_argument("--p321-zip", default=str(Path.home() / "Desktop" / "UpdateFile_p40_321" / "p321.zip"))
    p.add_argument("--event-id", type=int, default=202)
    p.add_argument("--event-name", default="Armada")
    p.add_argument("--site-root", default=str(Path.home() / "work" / "coding" / "websoccer-player-search"))
    return p.parse_args()


def latest_master_db(db_dir: Path) -> Path:
    cands = [p for p in db_dir.glob("wsm_*.sqlite3") if p.is_file() and p.stat().st_size > 0]
    if not cands:
        raise FileNotFoundError(f"no wsm_*.sqlite3 found in {db_dir}")
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0]


def new_db_path(db_dir: Path) -> Path:
    ts = dt.datetime.now(JST).strftime("%y%m%d%H%M")
    return db_dir / f"wsm_{ts}.sqlite3"


def parse_update_core_from_chlz(chlz: Path) -> tuple[list[dict], list[dict]]:
    with zipfile.ZipFile(chlz, "r") as zf:
        names = set(zf.namelist())
        player_idx = None
        param_idx = None
        for n in names:
            m = re.match(r"(\d+)-meta\.json$", Path(n).name)
            if not m:
                continue
            idx = m.group(1)
            meta = json.loads(zf.read(n).decode("utf-8"))
            path = str(meta.get("path") or "")
            if "/update_core_data/player/" in path:
                player_idx = idx
            if "/update_core_data/players_param/" in path:
                param_idx = idx

        if player_idx is None or param_idx is None:
            raise RuntimeError("failed to locate update_core_data player/players_param in chlz")

        pres_name = f"{player_idx}-res.json"
        prm_name = f"{param_idx}-res.json"
        if pres_name not in names or prm_name not in names:
            raise RuntimeError("missing res.json payload(s) for update_core_data")

        players = json.loads(zf.read(pres_name).decode("utf-8")).get("players") or []
        params = json.loads(zf.read(prm_name).decode("utf-8")).get("players_param") or []
        if not players or not params:
            raise RuntimeError("update_core_data payload empty")
        return players, params


def parse_ss_event(p321_zip: Path, event_id: int) -> dict:
    with zipfile.ZipFile(p321_zip, "r") as zf:
        plist_name = next((n for n in zf.namelist() if n.endswith("/Resources/PropertyList/ss.plist")), None)
        if not plist_name:
            raise RuntimeError("ss.plist not found in p321.zip")
        plist_obj = plistlib.loads(zf.read(plist_name))

    rows = plist_obj if isinstance(plist_obj, list) else []
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        if int(row[0]) != int(event_id):
            continue
        player_ids = [int(x) for x in str(row[6]).split(",") if str(x).strip().isdigit()]
        return {
            "event_id": int(row[0]),
            "type": int(row[1]),
            "start": row[2].strftime("%Y-%m-%d %H:%M:%S") if isinstance(row[2], dt.datetime) else str(row[2]),
            "end": row[3].strftime("%Y-%m-%d %H:%M:%S") if isinstance(row[3], dt.datetime) else str(row[3]),
            "notes": str(row[4] or ""),
            "name_raw": str(row[5] or ""),
            "player_ids": player_ids,
        }
    raise RuntimeError(f"event {event_id} not found in ss.plist")


def copy_new_player_images(p321_zip: Path, ids: list[int], site_root: Path) -> None:
    app_root = site_root / "app"
    docs_root = site_root / "docs"
    with zipfile.ZipFile(p321_zip, "r") as zf:
        zset = set(zf.namelist())
        for pid in ids:
            for kind in ("static", "action"):
                src = f"p321/Resources/img/chara/players/{kind}/{pid}@2x.gif"
                if src not in zset:
                    continue
                data = zf.read(src)
                for root in (app_root, docs_root):
                    out = root / "images" / "chara" / "players" / kind / f"{pid}.gif"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(data)


def main() -> int:
    args = parse_args()
    db_dir = Path(args.master_db_dir).expanduser().resolve()
    chlz = Path(args.chlz).expanduser().resolve()
    p321_zip = Path(args.p321_zip).expanduser().resolve()
    site_root = Path(args.site_root).expanduser().resolve()

    if not chlz.exists():
        raise FileNotFoundError(chlz)
    if not p321_zip.exists():
        raise FileNotFoundError(p321_zip)

    src_db = latest_master_db(db_dir)
    out_db = new_db_path(db_dir)
    shutil.copy2(src_db, out_db)

    players, params = parse_update_core_from_chlz(chlz)
    event = parse_ss_event(p321_zip, args.event_id)

    new_ids = sorted({int(p["player_id"]) for p in players})
    pmap = {int(p["player_id"]): p for p in players}

    conn = sqlite3.connect(str(out_db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")

        qmarks = ",".join(["?"] * len(new_ids))
        cur.execute(f"DELETE FROM ao__ZMOPLAYERSPARAM WHERE ZPLAYER_ID IN ({qmarks})", new_ids)
        cur.execute(f"DELETE FROM ao__ZMOPLAYER WHERE ZPLAYER_ID IN ({qmarks})", new_ids)
        cur.execute(f"DELETE FROM ao__ZMOPLAYERSINFO WHERE Z_PK IN ({qmarks})", new_ids)

        # INFO rows
        for pid in new_ids:
            p = pmap[pid]
            cur.execute(
                """
                INSERT INTO ao__ZMOPLAYERSINFO (Z_PK, Z_ENT, Z_OPT, ZDESCRIPTION_TEXT, ZPLAY_TYPE, ZSUBTITLE)
                VALUES (?, 0, 0, ?, ?, ?)
                """,
                (pid, p.get("description") or "", p.get("type") or "", p.get("subtitle") or ""),
            )

        # PLAYER core rows
        for pid in new_ids:
            p = pmap[pid]
            cur.execute(
                """
                INSERT INTO ao__ZMOPLAYER (
                  Z_PK,Z_ENT,Z_OPT,ZACT_SZN,ZAGE,ZBASE_LINE,ZBASE_POS,ZFLG_LISTUP,ZNATION_ID,ZPERSON_ID,
                  ZPLAYER_ID,ZPOS_ROLE,ZPOS_TYPE,ZRARITY,ZSTATUS,ZTALL,ZWEIGHT,ZINFO,ZPARAM,ZFULLNAME,ZNAME,ZNAMERUBY
                ) VALUES (
                  ?,0,0,0,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    pid,
                    int(p.get("age") or 0),
                    0,
                    0,
                    0,
                    int(p.get("nation_id") or 0),
                    int(p.get("person_id") or 0),
                    pid,
                    0,
                    int(p.get("pos_type") or 0),
                    int(p.get("rarity") or 0),
                    0,
                    int(p.get("tall") or 0),
                    int(p.get("weight") or 0),
                    pid,
                    pid,
                    p.get("fullname") or p.get("name") or "",
                    p.get("name") or p.get("fullname") or "",
                    p.get("nameruby") or "",
                ),
            )

        # PARAM rows
        max_pk = cur.execute("SELECT COALESCE(MAX(Z_PK), 0) FROM ao__ZMOPLAYERSPARAM").fetchone()[0]
        for row in sorted(params, key=lambda r: (int(r.get("player_id", 0)), int(r.get("szn_no", 0)))):
            pid = int(row.get("player_id") or 0)
            if pid not in pmap:
                continue
            max_pk += 1
            vals = (
                max_pk,
                0,
                0,
                int(row.get("cap") or 0),
                int(row.get("ck") or 0),
                int(row.get("cst") or 0),
                int(row.get("fk") or 0),
                int(row.get("inte") or 0),
                int(row.get("pk") or 0),
                pid,
                int(row.get("pop") or 0),
                int(row.get("pwr") or 0),
                int(row.get("r1") or 0),
                int(row.get("r10") or 0),
                int(row.get("r11") or 0),
                int(row.get("r12") or 0),
                int(row.get("r13") or 0),
                int(row.get("r14") or 0),
                int(row.get("r15") or 0),
                int(row.get("r16") or 0),
                int(row.get("r17") or 0),
                int(row.get("r18") or 0),
                int(row.get("r2") or 0),
                int(row.get("r3") or 0),
                int(row.get("r4") or 0),
                int(row.get("r5") or 0),
                int(row.get("r6") or 0),
                int(row.get("r7") or 0),
                int(row.get("r8") or 0),
                int(row.get("r9") or 0),
                int(row.get("rgh") or 0),
                int(row.get("sen") or 0),
                int(row.get("spd") or 0),
                int(row.get("stdp") or 0),
                int(row.get("stm") or 0),
                int(row.get("szn_no") or 0),
                int(row.get("tec") or 0),
                int(row.get("tmp") or 0),
            )
            cur.execute(
                """
                INSERT INTO ao__ZMOPLAYERSPARAM (
                  Z_PK,Z_ENT,Z_OPT,ZCAP,ZCK,ZCST,ZFK,ZINTE,ZPK,ZPLAYER_ID,ZPOP,ZPWR,
                  ZR1,ZR10,ZR11,ZR12,ZR13,ZR14,ZR15,ZR16,ZR17,ZR18,ZR2,ZR3,ZR4,ZR5,ZR6,ZR7,ZR8,ZR9,
                  ZRGH,ZSEN,ZSPD,ZSTDP,ZSTM,ZSZN_NO,ZTEC,ZTMP
                ) VALUES (
                  ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                vals,
            )

        # Manual scout event 202
        cur.execute(
            """
            INSERT INTO manual_scout_event (
              event_id,name,start,end,type,version,notes,name_raw,name_source,player_count,player_ids_json,is_manual,source_file
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO UPDATE SET
              name=excluded.name,
              start=excluded.start,
              end=excluded.end,
              type=excluded.type,
              version=excluded.version,
              notes=excluded.notes,
              name_raw=excluded.name_raw,
              name_source=excluded.name_source,
              player_count=excluded.player_count,
              player_ids_json=excluded.player_ids_json,
              is_manual=excluded.is_manual,
              source_file=excluded.source_file
            """,
            (
                int(args.event_id),
                args.event_name,
                event["start"],
                event["end"],
                int(event["type"]),
                321,
                event["notes"],
                event["name_raw"],
                "manual_override",
                len(event["player_ids"]),
                json.dumps(event["player_ids"], ensure_ascii=False),
                1,
                str(site_root / "app" / "data.json"),
            ),
        )

        # Categories for new players
        in_202 = set(event["player_ids"])
        for pid in new_ids:
            cat = "SS" if pid in in_202 else "NR"
            mem = [cat]
            cur.execute(
                """
                INSERT INTO manual_player_category (
                  player_id,category,category_membership_json,is_manual,source_file,source_note
                ) VALUES (?,?,?,?,?,?)
                ON CONFLICT(player_id) DO UPDATE SET
                  category=excluded.category,
                  category_membership_json=excluded.category_membership_json,
                  is_manual=excluded.is_manual,
                  source_file=excluded.source_file,
                  source_note=excluded.source_note
                """,
                (
                    pid,
                    cat,
                    json.dumps(mem, ensure_ascii=False),
                    1,
                    str(site_root / "app" / "data.json"),
                    "manual category update for p321/event202",
                ),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    copy_new_player_images(p321_zip, new_ids, site_root)

    print(f"[DONE] source_db={src_db}")
    print(f"[DONE] out_db={out_db}")
    print(f"[DONE] players_ingested={new_ids}")
    print(f"[DONE] event{args.event_id} name={args.event_name} players={len(event['player_ids'])}")
    print(f"[DONE] new players outside event{args.event_id} (NR): {[pid for pid in new_ids if pid not in set(event['player_ids'])]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
