#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import unicodedata
from collections import OrderedDict, defaultdict
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))

METRIC_MAP = OrderedDict(
    [
        ("スピ", "ZSPD"),
        ("テク", "ZTEC"),
        ("パワ", "ZPWR"),
        ("スタ", "ZSTM"),
        ("ラフ", "ZRGH"),
        ("個性", "ZCST"),
        ("人気", "ZPOP"),
        ("PK", "ZPK"),
        ("FK", "ZFK"),
        ("CK", "ZCK"),
        ("CP", "ZCAP"),
        ("知性", "ZINTE"),
        ("感性", "ZSEN"),
        ("個人", "ZSTDP"),
        ("組織", "ZTMP"),
    ]
)

POS_TYPE_MAP = {
    1: "FW",
    2: "MF",
    3: "DF",
    4: "GK",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export site JSON files from unified master DB.")
    p.add_argument(
        "--master-db",
        default=str(Path.home() / "Desktop" / "websoccer_master_db" / "websoccer_master.sqlite3"),
    )
    p.add_argument(
        "--fallback-data-json",
        default=str(Path.cwd() / "app" / "data.json"),
        help="Fallback data.json for IDs not present in app-original tables.",
    )
    p.add_argument(
        "--fallback-coaches-json",
        default=str(Path.cwd() / "app" / "coaches_data.json"),
        help="Fallback coaches_data.json for rare missing rows.",
    )
    p.add_argument(
        "--out-app-dir",
        default=str(Path.cwd() / "app"),
    )
    p.add_argument(
        "--out-docs-dir",
        default=str(Path.cwd() / "docs"),
    )
    p.add_argument(
        "--rohm-cache-json",
        default=str(Path.cwd() / "app" / "prepared" / "rohm_player_pages_cache.json"),
        help="Rohm player page cache. Used for name-based model mapping on mixed personId rows.",
    )
    return p.parse_args()


def now_jst_iso() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")


def season_label(raw_szn_no: int) -> str:
    return f"{raw_szn_no + 1}期"


def to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def parse_json_list(text):
    if not text:
        return []
    try:
        value = json.loads(text)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def normalize_name(text: str) -> str:
    s = str(text or "").strip().lower()
    s = s.replace("・", "").replace("･", "").replace("·", "")
    s = s.replace(" ", "")
    s = re.sub(r"[\u30a1-\u30f6]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    s = unicodedata.normalize("NFKC", s)
    return s


def normalize_model_name(text: str) -> str:
    s = str(text or "").replace("･", "・").replace("·", "・")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"%[0-9A-Fa-f]{2}", "", s)
    s = re.sub(r"\s+\([^)]*\)$", "", s)
    s = re.sub(r"\s+（[^）]*）$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -_")
    return s


JP_CHAR_CLASS = r"\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\u3005\u30fc"


def normalize_japanese_name_spacing(text: str) -> str:
    """
    Unify surname/given-name separator for Japanese names:
    half-width space between Japanese characters -> full-width space.
    """
    s = str(text or "")
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    # Temporarily convert full-width spaces to ASCII to normalize mixed spacing,
    # then convert JP-JP boundaries back to full-width separator.
    s = s.replace("\u3000", " ")
    s = re.sub(r"[ ]{2,}", " ", s).strip()
    s = re.sub(rf"([{JP_CHAR_CLASS}]) +([{JP_CHAR_CLASS}])", r"\1　\2", s)
    return s


def compact_model_token(text: str) -> str:
    s = normalize_name(text or "")
    s = unicodedata.normalize("NFKC", s)
    return s


def dedupe_model_name(text: str) -> str:
    """
    Collapse accidental duplicated patterns like:
    - "ロイス マルコロイス" -> "マルコロイス"
    - "中田 英寿 中田英寿" -> "中田 英寿"
    while preserving legitimate multi-word names.
    """
    base = normalize_model_name(text)
    if not base:
        return ""
    tokens = [t for t in base.split(" ") if t]
    if len(tokens) <= 1:
        return base

    token_norms = [compact_model_token(t) for t in tokens]

    # Pattern: first N tokens concatenation == last token (spaced + unspaced duplicate)
    if len(tokens) >= 3:
        last_n = token_norms[-1]
        joined_prev_n = compact_model_token("".join(tokens[:-1]))
        if last_n and joined_prev_n and last_n == joined_prev_n:
            return " ".join(tokens[:-1])

    # Remove tokens that are fully contained in another token.
    keep = [True] * len(tokens)
    for i in range(len(tokens)):
        ni = token_norms[i]
        if not ni:
            continue
        for j in range(len(tokens)):
            if i == j:
                continue
            nj = token_norms[j]
            if not nj:
                continue
            if ni != nj and ni in nj:
                keep[i] = False
                break

    reduced = [tokens[i] for i, k in enumerate(keep) if k]
    if not reduced:
        return base
    if len(reduced) == 1:
        return reduced[0]
    return " ".join(reduced)


def load_rohm_name_model_map(cache_path: Path) -> dict[str, dict]:
    """
    Return normalized-name -> model info only for unique mappings.
    """
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    grouped = defaultdict(list)
    for rec in payload.get("records", []):
        name = normalize_name(rec.get("name") or "")
        model = normalize_model_name(rec.get("modelName") or "")
        if not name or not model:
            continue
        grouped[name].append(
            {
                "model": model,
                "url": str(rec.get("url") or "").strip(),
            }
        )
    out = {}
    for name, rows in grouped.items():
        unique_models = sorted({r["model"] for r in rows if r["model"]})
        if len(unique_models) != 1:
            continue
        first = next((r for r in rows if r["model"] == unique_models[0]), rows[0])
        out[name] = {"model": unique_models[0], "url": first.get("url") or ""}
    return out


def to_grid(param: dict, is_gk: bool):
    r = lambda n: to_int(param.get(f"ZR{n}", 0))
    gk_left = r(13) if is_gk else None
    gk_right = r(15) if is_gk else None
    return [
        [r(1), r(2), r(3)],
        [r(4), r(5), r(6)],
        [r(7), r(8), r(9)],
        [r(10), r(11), r(12)],
        [gk_left, r(14), gk_right],
    ]


def make_periods(params: list[dict]):
    rows = sorted(params, key=lambda x: to_int(x.get("ZSZN_NO", 0)))
    periods = []
    for row in rows:
        metrics = {jp: to_int(row.get(en, 0)) for jp, en in METRIC_MAP.items()}
        periods.append(
            {
                "season": season_label(to_int(row.get("ZSZN_NO", 0))),
                "metrics": metrics,
            }
        )
    return periods


def pick_peak_metrics(periods: list[dict]):
    if not periods:
        return {k: 0 for k in METRIC_MAP.keys()}, 0

    def total(m):
        return to_int(m.get("スピ", 0)) + to_int(m.get("テク", 0)) + to_int(m.get("パワ", 0))

    best_total = max(total(p["metrics"]) for p in periods)
    peak = next((p for p in periods if total(p["metrics"]) == best_total), periods[0])
    return dict(peak["metrics"]), best_total


def min_max_metrics(periods: list[dict]):
    if not periods:
        z = {k: 0 for k in METRIC_MAP.keys()}
        return z, z
    max_m = {}
    min_m = {}
    for k in METRIC_MAP.keys():
        vals = [to_int(p["metrics"].get(k, 0)) for p in periods]
        max_m[k] = max(vals)
        min_m[k] = min(vals)
    return max_m, min_m


def make_heatmaps(params: list[dict], pos_type: int):
    rows = sorted(params, key=lambda x: to_int(x.get("ZSZN_NO", 0)))
    is_gk = int(pos_type) == 4

    by_season = OrderedDict()
    segment_list = []
    prev_grid = None
    for row in rows:
        raw = to_int(row.get("ZSZN_NO", 0))
        label = season_label(raw)
        grid = to_grid(row, is_gk)
        hidden_r = {
            "R13": to_int(row.get("ZR13", 0)),
            "R14": to_int(row.get("ZR14", 0)),
            "R15": to_int(row.get("ZR15", 0)),
            "R16": to_int(row.get("ZR16", 0)),
            "R17": to_int(row.get("ZR17", 0)),
            "R18": to_int(row.get("ZR18", 0)),
        }
        by_season[label] = grid
        if prev_grid is None or grid != prev_grid:
            segment_list.append(
                {
                    "label": f"{raw + 1}期〜",
                    "start": raw + 1,
                    "grid": grid,
                    "hiddenR": hidden_r,
                }
            )
            prev_grid = grid

    return segment_list, by_season


def load_fallback_players(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for p in obj.get("players", []):
        pid = to_int(p.get("id"), -1)
        if pid > 0:
            result[pid] = p
    return result


def load_fallback_coaches(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for c in obj.get("coaches", []):
        cid = to_int(c.get("id"), -1)
        if cid > 0:
            result[cid] = c
    return result


def build_players(
    conn: sqlite3.Connection,
    fallback_players: dict[int, dict],
    rohm_name_model_map: dict[str, dict],
) -> list[dict]:
    conn.row_factory = sqlite3.Row
    nations = {
        to_int(r["ZNATION_ID"]): (r["ZNAME"] or "")
        for r in conn.execute("SELECT ZNATION_ID, ZNAME FROM ao__ZMONATION").fetchall()
    }

    infos = {
        to_int(r["Z_PK"]): {"playType": r["ZPLAY_TYPE"] or "", "description": r["ZDESCRIPTION_TEXT"] or ""}
        for r in conn.execute("SELECT Z_PK, ZPLAY_TYPE, ZDESCRIPTION_TEXT FROM ao__ZMOPLAYERSINFO").fetchall()
    }

    players = {
        to_int(r["ZPLAYER_ID"]): dict(r)
        for r in conn.execute("SELECT * FROM ao__ZMOPLAYER").fetchall()
    }
    mixed_person_ids = {
        to_int(r["pid"])
        for r in conn.execute(
            """
            SELECT ZPERSON_ID AS pid
            FROM ao__ZMOPLAYER
            WHERE ZPERSON_ID > 0
            GROUP BY ZPERSON_ID
            HAVING COUNT(DISTINCT ZNAME) > 1
            """
        ).fetchall()
        if to_int(r["pid"], 0) > 0
    }

    model_map = {}
    try:
        model_rows = conn.execute(
            "SELECT person_id, model_name, source_method, is_manual, notes FROM manual_player_model"
        ).fetchall()
        for row in model_rows:
            person_id = to_int(row["person_id"], 0)
            if person_id <= 0:
                continue
            model_map[person_id] = {
                "name": row["model_name"] or "",
                "sourceMethod": row["source_method"] or "",
                "isManual": bool(to_int(row["is_manual"], 0)),
                "notes": row["notes"] or "",
            }
    except sqlite3.OperationalError:
        # Compatibility for older DB snapshots without manual_player_model.
        model_map = {}

    params_by_player = defaultdict(list)
    for row in conn.execute("SELECT * FROM ao__ZMOPLAYERSPARAM").fetchall():
        pid = to_int(row["ZPLAYER_ID"])
        if pid > 0:
            params_by_player[pid].append(dict(row))

    cat_map = {}
    for row in conn.execute(
        "SELECT player_id, category, category_membership_json FROM manual_player_category"
    ).fetchall():
        pid = to_int(row["player_id"])
        cat_map[pid] = {
            "category": row["category"] or "NR",
            "membership": parse_json_list(row["category_membership_json"]) or [row["category"] or "NR"],
        }

    all_ids = sorted(set(players.keys()) | set(cat_map.keys()))
    out = []
    for pid in all_ids:
        core = players.get(pid)
        manual = cat_map.get(pid)

        if core:
            period_rows = params_by_player.get(pid, [])
            periods = make_periods(period_rows)
            metric_values, best_total = pick_peak_metrics(periods)
            max_metrics, min_metrics = min_max_metrics(periods)
            pos_type = to_int(core.get("ZPOS_TYPE", 0))
            segments, by_season = make_heatmaps(period_rows, pos_type)

            nation_id = to_int(core.get("ZNATION_ID", 0))
            nation_name = nations.get(nation_id) or f"国籍ID:{nation_id}"
            info = infos.get(to_int(core.get("ZINFO", 0)), {"playType": "", "description": ""})
            person_id = to_int(core.get("ZPERSON_ID", 0))
            model_info = model_map.get(person_id, {})

            # For personId groups with mixed player names, prefer strict name-based
            # mapping from rohm cache when available and unique.
            player_name_norm = normalize_name(core.get("ZNAME") or core.get("ZFULLNAME") or "")
            name_based = rohm_name_model_map.get(player_name_norm)
            if person_id in mixed_person_ids and name_based and name_based.get("model"):
                model_info = {
                    "name": name_based.get("model") or "",
                    "sourceMethod": "name_exact_on_mixed_person",
                    "isManual": True,
                    "notes": "mixed_personid_name_based_from_rohm_cache",
                }

            if manual:
                category = manual["category"]
                category_membership = manual["membership"]
            else:
                fb = fallback_players.get(pid, {})
                category = fb.get("category", "NR")
                category_membership = fb.get("categoryMembership", [category])

            flags = {
                "CM": "CM" in category_membership,
                "SS": "SS" in category_membership,
            }

            display_name = normalize_japanese_name_spacing(core.get("ZNAME") or core.get("ZFULLNAME") or f"ID{pid}")
            display_full_name = normalize_japanese_name_spacing(core.get("ZFULLNAME") or core.get("ZNAME") or "")
            display_model = normalize_japanese_name_spacing(dedupe_model_name(model_info.get("name", "")))

            out.append(
                {
                    "id": pid,
                    "name": display_name,
                    "url": f"https://caselli.websoccer.info/players/{pid}",
                    "periods": periods,
                    "metricValues": metric_values,
                    "maxMetrics": max_metrics,
                    "minMetrics": min_metrics,
                    "bestTotal": best_total,
                    "flags": flags,
                    "position": POS_TYPE_MAP.get(pos_type, "MF"),
                    "category": category,
                    "categoryMembership": category_membership,
                    "rate": to_int(core.get("ZRARITY", 0)),
                    "positionHeatmaps": segments,
                    "positionHeatmapBySeason": by_season,
                    "fullName": display_full_name,
                    "nationality": nation_name,
                    "nationId": nation_id,
                    "playType": info.get("playType") or "",
                    "height": to_int(core.get("ZTALL", 0)),
                    "weight": to_int(core.get("ZWEIGHT", 0)),
                    "description": info.get("description") or "",
                    "nameRuby": core.get("ZNAMERUBY") or "",
                    "personId": person_id,
                    "modelPlayer": display_model,
                    "modelPlayerManual": bool(model_info.get("isManual", False)),
                    "modelPlayerSourceMethod": model_info.get("sourceMethod", ""),
                    "modelPlayerSourceNote": model_info.get("notes", ""),
                }
            )
        else:
            fb = dict(fallback_players.get(pid, {}))
            if not fb:
                continue
            if manual:
                fb["category"] = manual["category"]
                fb["categoryMembership"] = manual["membership"]
            fb["name"] = normalize_japanese_name_spacing(fb.get("name", ""))
            fb["fullName"] = normalize_japanese_name_spacing(fb.get("fullName", ""))
            fb["modelPlayer"] = normalize_japanese_name_spacing(dedupe_model_name(fb.get("modelPlayer", "")))
            membership = fb.get("categoryMembership") or [fb.get("category", "NR")]
            fb["flags"] = {"CM": "CM" in membership, "SS": "SS" in membership}
            fb.setdefault("nameRuby", "")
            fb.setdefault("personId", 0)
            fb.setdefault("modelPlayer", "")
            fb.setdefault("modelPlayerManual", False)
            fb.setdefault("modelPlayerSourceMethod", "")
            fb.setdefault("modelPlayerSourceNote", "")
            out.append(fb)

    out.sort(key=lambda x: to_int(x.get("id"), 0))
    return out


def build_scouts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
          event_id, name, start, end, type, version, notes,
          name_raw, name_source, player_count, player_ids_json
        FROM manual_scout_event
        ORDER BY event_id DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        ids = [to_int(x) for x in parse_json_list(r["player_ids_json"])]
        out.append(
            {
                "eventId": to_int(r["event_id"]),
                "name": r["name"] or "",
                "start": r["start"] or "",
                "end": r["end"] or "",
                "type": to_int(r["type"], 0),
                "version": to_int(r["version"], 0),
                "notes": r["notes"] or "",
                "nameRaw": r["name_raw"] or "",
                "nameSource": r["name_source"] or "",
                "playerCount": to_int(r["player_count"], len(ids)),
                "playerIds": ids,
            }
        )
    return out


def build_cm_events(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT event_id, name, start, end, mode, version, player_count, player_ids_json
        FROM manual_cm_event
        ORDER BY event_id DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        ids = [to_int(x) for x in parse_json_list(r["player_ids_json"])]
        out.append(
            {
                "eventId": to_int(r["event_id"]),
                "name": r["name"] or "",
                "start": r["start"] or "",
                "end": r["end"] or "",
                "mode": r["mode"] or "",
                "version": to_int(r["version"], 0),
                "playerCount": to_int(r["player_count"], len(ids)),
                "playerIds": ids,
            }
        )
    return out


def build_coaches(conn: sqlite3.Connection, fallback_coaches: dict[int, dict]) -> list[dict]:
    conn.row_factory = sqlite3.Row
    coaches = {to_int(r["ZHEADCOACH_ID"]): dict(r) for r in conn.execute("SELECT * FROM ao__ZMOHEADCOACH").fetchall()}

    leadership = defaultdict(list)
    for row in conn.execute("SELECT ZHEADCOACH_ID, ZSZN_NO, ZLEADERSHIP FROM ao__ZMOHEADCOACHESPARAM").fetchall():
        cid = to_int(row["ZHEADCOACH_ID"])
        leadership[cid].append((to_int(row["ZSZN_NO"]), to_int(row["ZLEADERSHIP"])))
    for cid in leadership:
        leadership[cid].sort(key=lambda x: x[0])

    depth4 = defaultdict(set)
    for row in conn.execute(
        "SELECT ZHEADCOACH_ID, ZFORMATION_ID, ZDEPTH FROM ao__ZMOHEADCOACHESUNDERSTANDING"
    ).fetchall():
        cid = to_int(row["ZHEADCOACH_ID"])
        fid = to_int(row["ZFORMATION_ID"])
        if to_int(row["ZDEPTH"]) == 4 and cid > 0 and fid > 0:
            depth4[cid].add(fid)

    obtainable = defaultdict(list)
    for row in conn.execute(
        """
        SELECT coach_id, formation_id, from_season
        FROM manual_coach_obtainable
        ORDER BY coach_id ASC, from_season ASC, formation_id ASC
        """
    ).fetchall():
        cid = to_int(row["coach_id"])
        fid = to_int(row["formation_id"])
        fs = to_int(row["from_season"], 1)
        obtainable[cid].append({"formationId": fid, "fromSeason": max(1, fs)})

    all_ids = sorted(set(coaches.keys()) | set(fallback_coaches.keys()))
    out = []
    for cid in all_ids:
        core = coaches.get(cid)
        if core:
            item = {
                "id": cid,
                "name": core.get("ZNAME") or "",
                "fullName": core.get("ZFULLNAME") or core.get("ZNAME") or "",
                "type": to_int(core.get("ZHEADCOACH_TYPE"), 0),
                "nationId": to_int(core.get("ZNATION_ID"), 0),
                "age": to_int(core.get("ZAGE"), 0),
                "rarity": to_int(core.get("ZRARITY"), 0),
                "leadershipBySeason": [v for _, v in leadership.get(cid, [])],
                "obtainable": obtainable.get(cid, []),
                "depth4FormationIds": sorted(depth4.get(cid, set())),
            }
        else:
            item = dict(fallback_coaches[cid])
            item["obtainable"] = obtainable.get(cid, item.get("obtainable", []))
            item["depth4FormationIds"] = sorted(depth4.get(cid, set(item.get("depth4FormationIds", []))))
            item["leadershipBySeason"] = item.get("leadershipBySeason", [])
            item["rarity"] = to_int(item.get("rarity", 0))

        if "formationObtainableIds" not in item or not item.get("formationObtainableIds"):
            item["formationObtainableIds"] = sorted({to_int(x.get("formationId")) for x in item.get("obtainable", [])})

        out.append(item)

    out.sort(key=lambda x: to_int(x.get("id"), 0))
    return out


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    master_db = Path(args.master_db).expanduser().resolve()
    if not master_db.exists():
        raise FileNotFoundError(f"master db not found: {master_db}")

    fallback_data = load_fallback_players(Path(args.fallback_data_json).expanduser().resolve())
    fallback_coaches = load_fallback_coaches(Path(args.fallback_coaches_json).expanduser().resolve())

    rohm_name_model_map = load_rohm_name_model_map(Path(args.rohm_cache_json).expanduser().resolve())

    conn = sqlite3.connect(str(master_db))
    conn.row_factory = sqlite3.Row
    try:
        generated_at = now_jst_iso()
        players = build_players(conn, fallback_data, rohm_name_model_map)
        scouts = build_scouts(conn)
        cm_events = build_cm_events(conn)
        coaches = build_coaches(conn, fallback_coaches)
    finally:
        conn.close()

    data_obj = {
        "source": "master-db",
        "generatedAt": generated_at,
        "metrics": list(METRIC_MAP.keys()),
        "players": players,
        "scouts": scouts,
        "cmEvents": cm_events,
    }
    coaches_obj = {
        "meta": {
            "source": "master-db",
            "generatedAt": generated_at,
        },
        "coaches": coaches,
    }

    out_app_dir = Path(args.out_app_dir).expanduser().resolve()
    out_docs_dir = Path(args.out_docs_dir).expanduser().resolve()

    app_data = out_app_dir / "data.json"
    docs_data = out_docs_dir / "data.json"
    app_coaches = out_app_dir / "coaches_data.json"
    docs_coaches = out_docs_dir / "coaches_data.json"

    write_json(app_data, data_obj)
    write_json(docs_data, data_obj)
    write_json(app_coaches, coaches_obj)
    write_json(docs_coaches, coaches_obj)

    print(f"wrote {app_data}")
    print(f"wrote {docs_data}")
    print(f"wrote {app_coaches}")
    print(f"wrote {docs_coaches}")
    print(
        f"players={len(players)} scouts={len(scouts)} cmEvents={len(cm_events)} coaches={len(coaches)} generatedAt={generated_at}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
