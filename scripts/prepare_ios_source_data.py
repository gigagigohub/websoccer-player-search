#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import zipfile
from collections import defaultdict
from typing import Dict, List, Tuple


def strip_z(name: str) -> str:
    if name.startswith("Z_"):
        return name[2:]
    if name.startswith("Z"):
        return name[1:]
    return name


def row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    out = {}
    for k in row.keys():
        out[strip_z(k)] = row[k]
    return out


def image_size_from_bytes(data: bytes) -> Tuple[int, int]:
    # GIF: width/height at [6:10] little-endian
    if len(data) >= 10 and (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")):
        return (int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little"))
    # PNG: signature + IHDR width/height at [16:24] big-endian
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return (int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))
    return (0, 0)


def image_size_from_file(path: str) -> Tuple[int, int]:
    with open(path, "rb") as f:
        b = f.read(32)
    return image_size_from_bytes(b)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare normalized data from iOS Product.sqlite + resources zip")
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--resources-zip", required=True)
    parser.add_argument("--repo-static-dir", required=True)
    parser.add_argument("--repo-action-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.sqlite)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM ZMOPLAYER")
    players_rows = [row_to_dict(cur, r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM ZMOPLAYERSINFO")
    info_rows = [row_to_dict(cur, r) for r in cur.fetchall()]
    info_by_pk = {r["PK"]: r for r in info_rows}

    cur.execute("SELECT * FROM ZMOPLAYERSPARAM ORDER BY ZPLAYER_ID ASC, ZSZN_NO ASC")
    params_rows = [row_to_dict(cur, r) for r in cur.fetchall()]
    params_by_player: Dict[int, List[dict]] = defaultdict(list)
    for r in params_rows:
        params_by_player[r["PLAYER_ID"]].append(r)

    players_by_id = {p["PLAYER_ID"]: p for p in players_rows}
    all_player_ids = set(players_by_id.keys())

    zip_static: Dict[int, str] = {}
    zip_action: Dict[int, str] = {}
    re_path = re.compile(r"Resources/img/chara/players/(static|action)/(\d+)@2x\.gif$")
    with zipfile.ZipFile(args.resources_zip, "r") as zf:
        for n in zf.namelist():
            m = re_path.search(n)
            if not m:
                continue
            kind, sid = m.group(1), int(m.group(2))
            if kind == "static":
                zip_static[sid] = n
            else:
                zip_action[sid] = n

        sample_ids = [35, 646, 1852]
        samples = []
        for sid in sample_ids:
            one = {"id": sid}
            for kind, zip_map, repo_dir in [
                ("static", zip_static, args.repo_static_dir),
                ("action", zip_action, args.repo_action_dir),
            ]:
                zp = zip_map.get(sid)
                rp = os.path.join(repo_dir, f"{sid}.gif")
                item = {
                    "zipPath": zp,
                    "repoPath": rp if os.path.exists(rp) else None,
                }
                if zp:
                    zb = zf.read(zp)
                    item["zipSizeBytes"] = len(zb)
                    item["zipImageSize"] = image_size_from_bytes(zb)
                    item["zipSha256"] = sha256_bytes(zb)
                if os.path.exists(rp):
                    item["repoSizeBytes"] = os.path.getsize(rp)
                    item["repoImageSize"] = image_size_from_file(rp)
                    item["repoSha256"] = sha256_file(rp)
                if zp and os.path.exists(rp):
                    item["sha256Equal"] = item["zipSha256"] == item["repoSha256"]
                one[kind] = item
            samples.append(one)

    repo_static_ids = {
        int(os.path.splitext(fn)[0])
        for fn in os.listdir(args.repo_static_dir)
        if fn.endswith(".gif") and os.path.splitext(fn)[0].isdigit()
    }
    repo_action_ids = {
        int(os.path.splitext(fn)[0])
        for fn in os.listdir(args.repo_action_dir)
        if fn.endswith(".gif") and os.path.splitext(fn)[0].isdigit()
    }

    output_players = []
    for pid in sorted(all_player_ids):
        p = players_by_id[pid]
        info = info_by_pk.get(p.get("INFO"))
        params = params_by_player.get(pid, [])
        output_players.append(
            {
                "playerId": pid,
                "player": p,
                "info": info,
                "params": params,
                "images": {
                    "static": {
                        "id": pid,
                        "zipPath": zip_static.get(pid),
                        "repoPath": f"images/chara/players/static/{pid}.gif" if pid in repo_static_ids else None,
                    },
                    "action": {
                        "id": pid,
                        "zipPath": zip_action.get(pid),
                        "repoPath": f"images/chara/players/action/{pid}.gif" if pid in repo_action_ids else None,
                    },
                },
            }
        )

    generated_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    output_obj = {
        "source": {
            "sqlite": args.sqlite,
            "resourcesZip": args.resources_zip,
            "note": "Column names are normalized by removing the leading 'Z'.",
        },
        "generatedAt": generated_at,
        "counts": {
            "players": len(players_rows),
            "playersInfo": len(info_rows),
            "playerParamsRows": len(params_rows),
            "playersWithParams": sum(1 for _pid, rows in params_by_player.items() if rows),
            "zipStaticImages": len(zip_static),
            "zipActionImages": len(zip_action),
            "repoStaticImages": len(repo_static_ids),
            "repoActionImages": len(repo_action_ids),
        },
        "players": output_players,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_obj, f, ensure_ascii=False)

    report = {
        "generatedAt": generated_at,
        "coverage": {
            "playerIdsInSqlite": len(all_player_ids),
            "zipStaticMatchedToSqlite": len(all_player_ids & set(zip_static.keys())),
            "zipActionMatchedToSqlite": len(all_player_ids & set(zip_action.keys())),
            "repoStaticMatchedToSqlite": len(all_player_ids & repo_static_ids),
            "repoActionMatchedToSqlite": len(all_player_ids & repo_action_ids),
            "sqliteMissingInZipStatic": sorted(all_player_ids - set(zip_static.keys()))[:50],
            "sqliteMissingInZipAction": sorted(all_player_ids - set(zip_action.keys()))[:50],
            "zipStaticMissingInSqlite": sorted(set(zip_static.keys()) - all_player_ids)[:50],
            "zipActionMissingInSqlite": sorted(set(zip_action.keys()) - all_player_ids)[:50],
        },
        "sampleChecks": samples,
        "interpretation": {
            "summary": "ZIP and repo images are both ID-based. Hashes are expected to differ in many cases due to @2x assets, but ID correspondence and dimensions can be compared.",
        },
    }

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
