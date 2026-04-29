#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
import sqlite3
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from bs4 import BeautifulSoup

PARAM_KEYS = [
    ("spd", "ZSPD"),
    ("tec", "ZTEC"),
    ("pwr", "ZPWR"),
    ("off", "ZOFF"),
    ("def", "ZDEF"),
    ("mid", "ZMID"),
    ("ttl", "ZTTL"),
    ("stm", "ZSTM"),
    ("dif", "ZDIF"),
]

DEFAULT_MODEL_SLOT_CSV = Path(
    "/Users/k.nishimura/work/coding/wsc_data/model_slot_mapping_probe/model_slot_ocr_candidates_strict.csv"
)
DEFAULT_MODEL_PAGE_DIR = Path(
    "/Users/k.nishimura/work/coding/wsc_data/model_slot_mapping_probe/pages"
)
DEFAULT_MODEL_OCR_DIR = Path(
    "/Users/k.nishimura/work/coding/wsc_data/model_slot_mapping_probe/ocr"
)
DEFAULT_MODEL_SLOT_OVERRIDES_CSV = Path(__file__).resolve().parents[1] / "data" / "formation_model_slot_overrides.csv"
MODEL_BODY_LINK_THRESHOLD = 0.66
MODEL_EXTRA_ALIASES = {
    "ダヴィド・アラバ": ["アルバ"],
    "フレドリック・ユングベリ": ["リュングベリ", "リュンゲベリ", "リュンゲヘリ"],
    "ロベール・ピレス": ["ピレス", "ヒビレス", "ヒビレース"],
}


def to_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def points_from_row(row):
    res = str(row.get("result") or "").strip().upper()
    if res == "W":
        return 3.0
    if res == "D":
        return 1.0
    if res == "L":
        return 0.0
    gf = to_float(row.get("goals_for"), None)
    ga = to_float(row.get("goals_against"), None)
    if gf is None or ga is None:
        return None
    if gf > ga:
        return 3.0
    if gf == ga:
        return 1.0
    return 0.0


def cc_round_rank(title):
    s = str(title or "")
    if "決勝" in s and "準決勝" not in s and "準々決勝" not in s:
        return 5
    if "準決勝" in s:
        return 4
    if "準々決勝" in s or "ベスト8" in s:
        return 3
    if "ベスト16" in s:
        return 2
    if "グループ" in s:
        return 1
    return 0


def finish_label_from_rank(rank, final_result=None, final_side=None, final_pk_winner_side=None):
    if rank >= 5:
        if str(final_result or "").strip().upper() == "W" or (
            final_pk_winner_side and str(final_pk_winner_side).strip().lower() == str(final_side or "").strip().lower()
        ):
            return "Champion"
        return "Runner-up"
    if rank == 4:
        return "Best 4"
    if rank == 3:
        return "Best 8"
    if rank == 2:
        return "Best 16"
    return "GL Exit"


def team_instance_key(row):
    return (
        to_int(row.get("season")),
        to_int(row.get("world_id")),
        to_int(row.get("match_id")),
        str(row.get("side") or "").strip().lower(),
        to_int(row.get("team_id")),
    )


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_json_list(text):
    if not text:
        return []
    try:
        value = json.loads(text)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def normalize_match_text(value):
    s = unicodedata.normalize("NFKC", str(value or "")).lower()
    s = re.sub(r"[\u3041-\u3096]", lambda m: chr(ord(m.group(0)) + 0x60), s)
    s = s.replace("ヴ", "ブ").replace("ヂ", "ジ").replace("ヅ", "ズ")
    s = re.sub(r"[・･·\s　/／._\\-ー〜~'\"“”‘’（）()［］\\[\\]{}<>＜＞:：;；,，、。!！?？]", "", s)
    return s


def source_name_aliases(value):
    raw = str(value or "").strip()
    variants = {raw}
    variants.add(re.sub(r"^[A-Za-zＡ-Ｚａ-ｚ一-龥ぁ-んァ-ヴー]{1,2}\s*[・･·]\s*", "", raw))
    variants.add(re.sub(r"[^A-Za-zＡ-Ｚａ-ｚ一-龥ぁ-んァ-ヴー]+", "", raw))
    return {normalize_match_text(v) for v in variants if normalize_match_text(v)}


def model_name_aliases(model_name, include_all_parts=False):
    raw = str(model_name or "").strip()
    if not raw:
        return set()
    parts = [p for p in re.split(r"[・･·\s　/／]+", raw) if p]
    aliases = {raw, "".join(parts)}
    if parts:
        aliases.add(parts[-1])
    if include_all_parts or ("・" not in raw and "･" not in raw and "·" not in raw):
        aliases.update(p for p in parts if len(normalize_match_text(p)) >= 2)
    aliases.update(MODEL_EXTRA_ALIASES.get(raw, []))
    return {normalize_match_text(a) for a in aliases if normalize_match_text(a)}


def read_html_text(path):
    data = Path(path).read_bytes()
    for enc in ("utf-8", "cp932", "shift_jis"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_model_page_text(page_dir, slug):
    page_path = Path(page_dir).expanduser() / f"{slug}.html"
    if not slug or not page_path.exists():
        return ""
    soup = BeautifulSoup(read_html_text(page_path), "html.parser")
    content = soup.find("table", attrs={"width": "900"}) or soup.body or soup
    headings = content.find_all("h2")
    for heading in headings:
        if "モデル" not in heading.get_text(" ", strip=True):
            continue
        chunks = []
        for node in heading.next_siblings:
            name = getattr(node, "name", "")
            if name == "h2":
                break
            text = node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node).strip()
            if text:
                chunks.append(text)
        if chunks:
            return " ".join(chunks)
    return content.get_text(" ", strip=True)


def extract_page_model_terms(page_text):
    terms = set()
    for term in re.findall(r"[ァ-ヴー・･]{2,}", page_text or ""):
        variants = [term]
        variants.extend(re.split(r"[・･]+", term))
        for variant in variants:
            normalized = normalize_match_text(variant)
            if len(normalized) >= 3:
                terms.add(normalized)
    return terms


def alias_term_score(alias, term):
    if not alias or not term:
        return 0.0
    if alias == term:
        return 1.0
    shorter = min(len(alias), len(term))
    longer = max(len(alias), len(term))
    if len(alias) >= 3 and alias in term and (alias == term or len(alias) >= 4):
        return min(0.98, 0.72 + (shorter / longer) * 0.24)
    if len(term) >= 4 and term in alias:
        return min(0.98, 0.72 + (shorter / longer) * 0.24)
    if shorter <= 3:
        return 0.0
    if abs(len(alias) - len(term)) > 3:
        return 0.0
    if alias[0] != term[0] and alias[-1] != term[-1]:
        return 0.0
    if len(set(alias) & set(term)) < min(3, max(1, min(len(alias), len(term)) - 1)):
        return 0.0
    return SequenceMatcher(None, alias, term).ratio()


def build_model_alias_index(model_entries):
    exact = defaultdict(list)
    by_first_len = defaultdict(list)
    by_last_len = defaultdict(list)
    for entry in model_entries:
        aliases = {alias for alias in (entry.get("aliases") or set()) if len(alias) >= 3}
        for alias in aliases:
            item = (alias, entry)
            exact[alias].append(entry)
            by_first_len[(alias[0], len(alias))].append(item)
            by_last_len[(alias[-1], len(alias))].append(item)
    return {"exact": exact, "byFirstLen": by_first_len, "byLastLen": by_last_len}


def build_model_ocr_alias_index(model_entries):
    exact = defaultdict(list)
    by_first_len = defaultdict(list)
    by_last_len = defaultdict(list)
    for entry in model_entries:
        aliases = {alias for alias in (entry.get("ocrAliases") or entry.get("aliases") or set()) if len(alias) >= 2}
        for alias in aliases:
            item = (alias, entry)
            exact[alias].append(item)
            if len(alias) >= 3:
                by_first_len[(alias[0], len(alias))].append(item)
                by_last_len[(alias[-1], len(alias))].append(item)
    return {"exact": exact, "byFirstLen": by_first_len, "byLastLen": by_last_len}


def model_ocr_candidates_for_source(source_aliases, model_ocr_alias_index):
    candidates = {}
    for source in source_aliases:
        for alias, entry in model_ocr_alias_index["exact"].get(source, []):
            candidates[(alias, entry["personId"])] = (alias, entry)
        if len(source) < 3:
            continue
        for length in range(max(3, len(source) - 3), len(source) + 4):
            for alias, entry in model_ocr_alias_index["byFirstLen"].get((source[0], length), []):
                candidates[(alias, entry["personId"])] = (alias, entry)
            for alias, entry in model_ocr_alias_index["byLastLen"].get((source[-1], length), []):
                candidates[(alias, entry["personId"])] = (alias, entry)
    return list(candidates.values())


def load_model_entries(master_db_path):
    db_path = Path(master_db_path).expanduser() if master_db_path else None
    if not db_path or not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              m.person_id,
              m.model_name,
              i.player_id,
              p.ZNAME AS player_name,
              p.ZFULLNAME AS player_fullname,
              COALESCE(n.ZNAME, '') AS nation,
              COALESCE(info.ZPLAY_TYPE, '') AS play_type,
              COALESCE(c.category, '') AS category,
              COALESCE(c.retired, 0) AS retired
            FROM manual_player_model m
            JOIN player_person_identity i ON i.canonical_person_id = m.person_id
            JOIN ao__ZMOPLAYER p ON p.ZPLAYER_ID = i.player_id
            LEFT JOIN ao__ZMONATION n ON n.ZNATION_ID = p.ZNATION_ID
            LEFT JOIN ao__ZMOPLAYERSINFO info ON info.Z_PK = p.ZINFO
            LEFT JOIN manual_player_category c ON c.player_id = i.player_id
            WHERE COALESCE(m.model_name, '') <> ''
            ORDER BY m.person_id, COALESCE(c.retired, 0), i.player_id
            """
        ).fetchall()
    finally:
        conn.close()

    by_person = {}
    for row in rows:
        person_id = to_int(row["person_id"])
        if person_id in by_person:
            continue
        model_name = row["model_name"] or ""
        by_person[person_id] = {
            "personId": person_id,
            "modelName": model_name,
            "aliases": model_name_aliases(model_name),
            "ocrAliases": model_name_aliases(model_name, include_all_parts=True),
            "playerId": to_int(row["player_id"]),
            "playerName": row["player_name"] or "",
            "playerFullName": row["player_fullname"] or "",
            "nation": row["nation"] or "",
            "category": row["category"] or "",
            "playType": row["play_type"] or "",
        }
    return list(by_person.values())


def load_formation_slot_positions(master_db_path):
    db_path = Path(master_db_path).expanduser() if master_db_path else None
    if not db_path or not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ZFORMATION_ID, ZPOS, ZX, ZY
            FROM ao__ZMOFORMATIONSPOSITION
            ORDER BY ZFORMATION_ID, ZPOS
            """
        ).fetchall()
    finally:
        conn.close()
    positions = defaultdict(dict)
    for row in rows:
        positions[to_int(row["ZFORMATION_ID"])][to_int(row["ZPOS"])] = {
            "x": to_float(row["ZX"]),
            "y": to_float(row["ZY"]),
        }
    return positions


def read_ocr_chunks(ocr_dir, slug):
    path = Path(ocr_dir).expanduser() / f"{slug}.tsv"
    if not slug or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    lines = defaultdict(list)
    for row in rows:
        if str(row.get("level")) != "5":
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        key = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
        lines[key].append(row)

    chunks = []
    for words in lines.values():
        words.sort(key=lambda r: to_int(r.get("left")))
        groups = []
        current = []
        last_right = None
        for word in words:
            text = str(word.get("text") or "").strip()
            left = to_float(word.get("left")) / 3.0
            right = (to_float(word.get("left")) + to_float(word.get("width"))) / 3.0
            gap = 999.0 if last_right is None else left - last_right
            starts_name = bool(re.match(r"^[A-Za-zＡ-Ｚ]\s*[・･]", text))
            if current and (gap > 42 or starts_name):
                groups.append(current)
                current = []
            current.append(word)
            last_right = right
        if current:
            groups.append(current)

        for group in groups:
            text = "".join(str(w.get("text") or "").strip() for w in group).strip()
            if not text or normalize_match_text(text) in {"", "o", "oo"}:
                continue
            left = min(to_float(w.get("left")) for w in group) / 3.0
            top = min(to_float(w.get("top")) for w in group) / 3.0
            right = max(to_float(w.get("left")) + to_float(w.get("width")) for w in group) / 3.0
            bottom = max(to_float(w.get("top")) + to_float(w.get("height")) for w in group) / 3.0
            conf_values = [to_float(w.get("conf"), -1) for w in group if to_float(w.get("conf"), -1) >= 0]
            chunks.append({
                "sourceName": text,
                "x": round((left + right) / 2.0, 1),
                "y": round((top + bottom) / 2.0, 1),
                "ocrConfidence": round(sum(conf_values) / len(conf_values), 1) if conf_values else 0.0,
            })
    return chunks


def expected_source_xy(pos):
    # Source formation images are 386x420. These constants align the game's
    # 0..321 / 0..337 slot coordinates to the label centers in those images.
    return 65.0 + 0.78 * pos["x"], 52.0 + 0.91 * pos["y"]


def nearest_slot_for_chunk(fid, chunk, formation_positions):
    positions = formation_positions.get(fid) or {}
    best = None
    for slot, pos in positions.items():
        expected_x, expected_y = expected_source_xy(pos)
        dist = ((chunk["x"] - expected_x) / 65.0) ** 2 + ((chunk["y"] - expected_y) / 55.0) ** 2
        if best is None or dist < best[0]:
            best = (dist, slot)
    if not best:
        return 0, 0.0
    return best[1], best[0]


def slot_role(slot, positions):
    pos = positions.get(slot)
    if not pos:
        return ""
    ys = sorted({round(p["y"], 1) for p in positions.values()})
    max_y = max(ys) if ys else pos["y"]
    if abs(pos["y"] - max_y) < 18:
        return "gk"
    attack_rank = sum(1 for y in ys if y < pos["y"] - 18)
    defend_rank = sum(1 for y in ys if y > pos["y"] + 18)
    wide = pos["x"] < 70 or pos["x"] > 250
    central = 95 <= pos["x"] <= 230
    if attack_rank == 0:
        return "fw"
    if attack_rank <= 1 and wide:
        return "wing"
    if defend_rank <= 1 and wide:
        return "sb"
    if defend_rank <= 1 and central:
        return "cb"
    if attack_rank <= 2 and central:
        return "am"
    return "cm"


def player_role_from_text(value):
    text = str(value or "")
    if re.search(r"GK|ＧＫ|キーパー|ゴッドハンド|守護神", text):
        return "gk"
    if re.search(r"サイドバック|ウイングバック|ウィングバック", text):
        return "sb"
    if re.search(r"センターバック|ディフェンス|ストッパー|スイーパー|リベロ", text):
        return "cb"
    if re.search(r"ウイング|ウィング|サイド", text):
        return "wing"
    if re.search(r"ストライカー|フォワード|FW|ＦＷ|点取り|ポスト", text):
        return "fw"
    if re.search(r"ファンタジスタ|トップ下|司令塔|チャンスメイカー|ドリブラー", text):
        return "am"
    if re.search(r"ボランチ|セントラル|レジスタ|中盤|MF|ＭＦ|ユーティリティ", text):
        return "cm"
    return ""


INITIAL_KANA_GROUPS = {
    "a": "アイウエオァィゥェォ",
    "b": "バビブベボ",
    "c": "カキクケコキャキュキョコ",
    "d": "ダヂヅデドディデュ",
    "e": "エ",
    "f": "ファフィフフェフォ",
    "g": "ガギグゲゴジジェジョジャンジュ",
    "h": "ハヒフヘホ",
    "i": "イ",
    "j": "ジジェジョジャジュジャン",
    "k": "カキクケコ",
    "l": "ラリルレロ",
    "m": "マミムメモ",
    "n": "ナニヌネノ",
    "o": "オ",
    "p": "パピプペポ",
    "r": "ラリルレロ",
    "s": "サシスセソシャシュショ",
    "t": "タチツテトティトゥ",
    "u": "ウ",
    "v": "ヴバビブベボ",
    "w": "ワウ",
    "y": "ヤユヨ",
    "z": "ザジズゼゾ",
}


def source_initial(value):
    m = re.match(r"\s*([A-Za-zＡ-Ｚａ-ｚ]{1,2})\s*[・･]", unicodedata.normalize("NFKC", str(value or "")))
    return m.group(1).lower()[0] if m else ""


def initial_compatibility(source_text, model_name):
    initial = source_initial(source_text)
    if not initial:
        return 0.0
    first_part = re.split(r"[・･·\s　/／]+", str(model_name or "").strip())[0]
    if not first_part:
        return 0.0
    first_char = unicodedata.normalize("NFKC", first_part)[0]
    if first_char in INITIAL_KANA_GROUPS.get(initial, ""):
        return 0.18
    return -0.08


def role_compatibility(slot_role_name, entry):
    player_role = player_role_from_text(" ".join([
        entry.get("playType") or "",
        entry.get("playerFullName") or "",
        entry.get("playerName") or "",
    ]))
    if not slot_role_name or not player_role:
        return 0.0
    if slot_role_name == player_role:
        return 0.16
    compatible = {
        ("fw", "am"),
        ("am", "fw"),
        ("am", "cm"),
        ("cm", "am"),
        ("cm", "sb"),
        ("wing", "fw"),
        ("wing", "am"),
        ("sb", "cb"),
        ("cb", "sb"),
    }
    if (slot_role_name, player_role) in compatible:
        return 0.05
    incompatible = {
        ("gk", "fw"),
        ("gk", "am"),
        ("gk", "cm"),
        ("gk", "cb"),
        ("gk", "sb"),
        ("fw", "gk"),
        ("fw", "cb"),
        ("fw", "sb"),
        ("cb", "fw"),
        ("cb", "am"),
        ("cb", "cm"),
        ("sb", "fw"),
    }
    if (slot_role_name, player_role) in incompatible:
        return -0.16
    return 0.0


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[。！？])\s*", str(text or "")) if s.strip()]


def sentence_role(sentence):
    if re.search(r"GK|ＧＫ|キーパー|最後の砦|ゴールを守", sentence):
        return "gk"
    if re.search(r"スイーパー|リベロ|センターバック|ＣＢ|CB|ストッパー|ディフェンスライン|守備陣|[３3４4５5]バック", sentence):
        return "cb"
    if re.search(r"サイドバック|ウイングバック|ウィングバック|ＳＢ|SB", sentence):
        return "sb"
    if re.search(r"ウイング|ウィング|サイドハーフ|サイドアタッカー|ＲＷＨ|LWH|RWH", sentence):
        return "wing"
    if re.search(r"トップ下|セカンドトップ|１．５列目|1\\.5列目|司令塔|攻撃の中心", sentence):
        return "am"
    if re.search(r"ボランチ|アンカー|センターハーフ|ＣＨ|CH|ＤＨ|DH|中盤|ゲームメイカー", sentence):
        return "cm"
    if re.search(r"１トップ|1トップ|２トップ|2トップ|ＦＷ|FW|ストライカー|センターフォワード|前線", sentence):
        return "fw"
    return ""


def sentence_role_for_alias(sentence, alias):
    normalized_sentence = normalize_match_text(sentence)
    pos = normalized_sentence.find(alias)
    if pos < 0:
        return sentence_role(sentence)
    before = normalized_sentence[max(0, pos - 28):pos]
    around = normalized_sentence[max(0, pos - 18):pos + len(alias) + 18]
    if "スイーパー" in before or "リベロ" in before:
        return "cb"
    if re.search(r"センターバック|cb|ｃｂ|ストッパー", before):
        return "cb"
    if re.search(r"サイドバック|ウイングバック|ウィングバック|sb|ｓｂ", before):
        return "sb"
    if re.search(r"gk|ｇｋ|キーパー|最後の砦", before + around):
        return "gk"
    if re.search(r"トップ下|セカンドトップ|15列目|司令塔|攻撃の中心", before + around):
        return "am"
    if re.search(r"ボランチ|アンカー|センターハーフ|ch|ｃｈ|dh|ｄｈ|中盤|ゲームメイカー", before + around):
        return "cm"
    if re.search(r"ウイング|ウィング|サイドハーフ|サイドアタッカー|rwh|lwh", before + around):
        return "wing"
    if re.search(r"1トップ|１トップ|2トップ|２トップ|fw|ｆｗ|ストライカー|センターフォワード|前線", before + around):
        return "fw"
    return sentence_role(sentence)


def sentence_side(sentence, alias):
    normalized_sentence = normalize_match_text(sentence)
    pos = normalized_sentence.find(alias)
    if pos < 0:
        return ""
    before = normalized_sentence[max(0, pos - 16):pos]
    after = normalized_sentence[pos:pos + 16]
    left_pos = max(before.rfind("左"), after.find("左") if "左" in after[:6] else -1)
    right_pos = max(before.rfind("右"), after.find("右") if "右" in after[:6] else -1)
    if left_pos >= 0 and right_pos < 0:
        return "left"
    if right_pos >= 0 and left_pos < 0:
        return "right"
    if left_pos >= 0 and right_pos >= 0:
        return "left" if left_pos > right_pos else "right"
    return ""


def role_mentions_from_text(page_text, page_entries):
    positive_context = re.compile(r"左図|スターティング|先発|決勝|最終的|レギュラー|固定|布陣|中心|大黒柱|想定")
    alternate_context = re.compile(r"控え|他の試合|なお|当初|怪我|外され|退団|代役|候補|など|ことも|入ること|使われ|よく使われ|多かった|予選|途中|相棒")
    mentions = []
    for sentence in split_sentences(page_text):
        normalized_sentence = normalize_match_text(sentence)
        for entry in page_entries:
            aliases = sorted((entry.get("aliases") or set()) | (entry.get("ocrAliases") or set()), key=len, reverse=True)
            matched_alias = next((alias for alias in aliases if len(alias) >= 3 and alias in normalized_sentence), "")
            if not matched_alias:
                continue
            role = sentence_role_for_alias(sentence, matched_alias)
            if not role:
                continue
            score = 0.62
            if positive_context.search(sentence):
                score += 0.12
            if alternate_context.search(sentence) and not re.search(r"決勝|最終的|レギュラー|左図|先発|想定", sentence):
                score -= 0.22
            side = sentence_side(sentence, matched_alias)
            if side:
                score += 0.08
            if "スイーパー" in sentence and matched_alias in normalize_match_text(sentence.split("スイーパー", 1)[1][:18]):
                score += 0.16
            mentions.append({
                "entry": entry,
                "role": role,
                "side": side,
                "score": score,
                "sentence": sentence,
            })
    mentions.sort(key=lambda x: x["score"], reverse=True)
    return mentions


def slot_side(slot, positions):
    pos = positions.get(slot)
    if not pos:
        return ""
    if pos["x"] < 115:
        return "left"
    if pos["x"] > 205:
        return "right"
    return "center"


def role_to_slot_compatibility(mention_role, slot_role_name):
    if not mention_role or not slot_role_name:
        return 0.0
    if mention_role == slot_role_name:
        return 0.28
    compatible = {
        ("fw", "am"),
        ("am", "fw"),
        ("am", "cm"),
        ("cm", "am"),
        ("cm", "wing"),
        ("wing", "am"),
        ("wing", "fw"),
        ("sb", "wing"),
        ("sb", "cb"),
        ("cb", "sb"),
    }
    return 0.12 if (mention_role, slot_role_name) in compatible else -0.16


def best_role_match_for_slot(slot, positions, mentions, used_person_ids):
    slot_role_name = slot_role(slot, positions)
    side = slot_side(slot, positions)
    best = None
    best_score = 0.0
    for mention in mentions:
        entry = mention["entry"]
        if entry.get("personId") in used_person_ids:
            continue
        if mention["role"] not in {"gk", "fw", "cb", "sb"}:
            continue
        role_slot_score = role_to_slot_compatibility(mention["role"], slot_role_name)
        player_slot_score = role_compatibility(slot_role_name, entry)
        if role_slot_score < 0.12 or player_slot_score < 0:
            continue
        score = mention["score"] + role_slot_score + player_slot_score
        if mention.get("side"):
            score += 0.14 if mention["side"] == side else -0.18
        if score > best_score:
            best = mention
            best_score = score
    if best and best_score >= 0.82:
        return best, best_score
    return None, best_score


def best_ocr_chunk_match(chunk_text, model_ocr_alias_index, page_entries, slot_role_name, extra_entries=None):
    source_aliases = source_name_aliases(chunk_text)
    if not source_aliases:
        return None, 0.0
    page_person_ids = {entry.get("personId") for entry in page_entries}
    candidate_items = model_ocr_candidates_for_source(source_aliases, model_ocr_alias_index)
    for entry in page_entries + (extra_entries or []):
        for alias in (entry.get("ocrAliases") or entry.get("aliases") or set()):
            if len(alias) >= 2:
                candidate_items.append((alias, entry))
    best = None
    best_rank = 0.0
    best_text_score = 0.0
    seen = set()
    for alias, entry in candidate_items:
        key = (alias, entry.get("personId"))
        if key in seen:
            continue
        seen.add(key)
        text_score = max(SequenceMatcher(None, source, alias).ratio() for source in source_aliases)
        if text_score < 0.56:
            continue
        rank = text_score
        if entry.get("personId") in page_person_ids:
            rank += 0.14
        rank += initial_compatibility(chunk_text, entry.get("modelName"))
        rank += role_compatibility(slot_role_name, entry)
        if rank > best_rank:
            best = entry
            best_rank = rank
            best_text_score = text_score
    if best and (best_text_score >= 0.72 or best_rank >= 0.78):
        return best, best_text_score
    return None, best_text_score


def body_mentioned_model_entries(page_text, model_alias_index):
    terms = extract_page_model_terms(page_text)
    by_person = {}

    def remember(entry, score):
        person_id = entry.get("personId")
        if not person_id:
            return
        previous = by_person.get(person_id)
        if previous and previous.get("bodyMentionScore", 0) >= score:
            return
        item = dict(entry)
        item["bodyMentionScore"] = score
        by_person[person_id] = item

    for term in terms:
        for entry in model_alias_index["exact"].get(term, []):
            remember(entry, 1.0)

        candidates = {}
        for length in range(max(3, len(term) - 3), len(term) + 4):
            for alias, entry in model_alias_index["byFirstLen"].get((term[0], length), []):
                candidates[(alias, entry["personId"])] = (alias, entry)
            for alias, entry in model_alias_index["byLastLen"].get((term[-1], length), []):
                candidates[(alias, entry["personId"])] = (alias, entry)

        for alias, entry in candidates.values():
            score = alias_term_score(alias, term)
            if score >= 0.84:
                remember(entry, score)

    return list(by_person.values())


def best_body_model_match(row, page_entries):
    source_aliases = source_name_aliases(row.get("ocr_cleaned") or row.get("ocr_raw") or "")
    if not source_aliases or not page_entries:
        return None, 0.0
    best = None
    best_score = 0.0
    for entry in page_entries:
        aliases = entry.get("aliases") or set()
        if not aliases:
            continue
        score = max(
            SequenceMatcher(None, source, alias).ratio()
            for source in source_aliases
            for alias in aliases
        )
        if score > best_score:
            best = entry
            best_score = score
    if best and best_score >= MODEL_BODY_LINK_THRESHOLD:
        return best, best_score
    return None, best_score


def best_body_candidate_match(candidates, page_entries):
    if not candidates or not page_entries:
        return None, 0.0
    entry_by_model = {normalize_match_text(entry.get("modelName")): entry for entry in page_entries}
    best = None
    best_score = 0.0
    for candidate in candidates:
        score = to_float(candidate.get("score"), 0.0)
        if score < 55:
            continue
        entry = entry_by_model.get(normalize_match_text(candidate.get("model_name")))
        if entry and score > best_score:
            best = entry
            best_score = score
    return best, best_score


def load_model_slots(path, page_dir=None, master_db_path=None, ocr_dir=None, overrides_path=None):
    model_path = Path(path).expanduser()
    if not model_path.exists():
        return []
    model_entries = load_model_entries(master_db_path)
    model_alias_index = build_model_alias_index(model_entries) if model_entries else None
    model_ocr_alias_index = build_model_ocr_alias_index(model_entries) if model_entries else None
    model_entry_by_name = {normalize_match_text(entry.get("modelName")): entry for entry in model_entries}
    formation_positions = load_formation_slot_positions(master_db_path) if ocr_dir else {}
    page_entries_by_slug = {}
    source_rows = read_csv(model_path)
    candidate_entries_by_source = defaultdict(list)
    for row in source_rows:
        slug = row.get("slug") or ""
        source_key = normalize_match_text(row.get("ocr_cleaned") or row.get("ocr_raw") or "")
        if not slug or not source_key:
            continue
        seen_candidate_person_ids = set()
        candidate_names = [row.get("best_model_name") or ""]
        candidate_names.extend(str(c.get("model_name") or "") for c in parse_json_list(row.get("candidate_json")))
        for model_name in candidate_names:
            entry = model_entry_by_name.get(normalize_match_text(model_name))
            if not entry or entry["personId"] in seen_candidate_person_ids:
                continue
            seen_candidate_person_ids.add(entry["personId"])
            candidate_entries_by_source[(slug, source_key)].append(entry)
    metadata_by_group = {}
    rows = []
    for row in source_rows:
        fid = to_int(row.get("formation_id"))
        slot = to_int(row.get("slot"))
        player_id = to_int(row.get("best_player_id"))
        source_name = row.get("ocr_cleaned") or row.get("ocr_raw") or ""
        if not fid or not slot or not source_name:
            continue
        slug = row.get("slug") or ""
        metadata_by_group[(fid, slug)] = row
        candidates = parse_json_list(row.get("candidate_json"))
        confidence = round(to_float(row.get("best_score")), 1)
        is_linked = player_id > 0 and confidence >= 85
        body_match_score = 0.0
        body_entry = None
        if not is_linked and page_dir and model_alias_index:
            if slug not in page_entries_by_slug:
                page_text = extract_model_page_text(page_dir, slug)
                page_entries_by_slug[slug] = body_mentioned_model_entries(page_text, model_alias_index)
            page_entries = page_entries_by_slug.get(slug, [])
            body_entry, body_match_score = best_body_candidate_match(candidates, page_entries)
            link_source = "bodyCandidate" if body_entry else ""
            if not body_entry:
                body_entry, body_match_score = best_body_model_match(row, page_entries)
                link_source = "body" if body_entry else ""
            if body_entry:
                player_id = body_entry["playerId"]
                is_linked = True
        rows.append({
            "formationId": fid,
            "slot": slot,
            "sourceName": source_name,
            "modelName": (body_entry["modelName"] if body_entry else row.get("best_model_name")) if is_linked else "",
            "playerId": player_id if is_linked else 0,
            "isLinked": is_linked,
            "linkSource": link_source if body_entry else ("ocr" if is_linked else ""),
            "playerName": (body_entry["playerName"] if body_entry else row.get("best_game_name")) if is_linked else "",
            "playerFullName": (body_entry["playerFullName"] if body_entry else row.get("best_fullname")) if is_linked else "",
            "nation": (body_entry["nation"] if body_entry else row.get("best_nation")) if is_linked else "",
            "category": (body_entry["category"] if body_entry else row.get("best_category")) if is_linked else "",
            "playType": (body_entry["playType"] if body_entry else row.get("best_play_type")) if is_linked else "",
            "sourceTitle": row.get("source_title") or "",
            "sourceUrl": row.get("source_url") or "",
            "confidence": confidence,
            "ocrConfidence": round(to_float(row.get("ocr_conf")), 1),
            "slotDistance": round(to_float(row.get("slot_dist")), 3),
            "candidateCount": len(candidates),
            "candidatePlayerId": player_id if player_id > 0 and not is_linked else 0,
            "candidateModelName": row.get("best_model_name") if player_id > 0 and not is_linked else "",
            "bodyMatchScore": round(body_match_score, 3) if body_match_score else 0,
        })

    rows_by_key = {}

    def row_quality(row):
        source_rank = {
            "ocrSlot": 5,
            "ocr": 4,
            "bodyRole": 3,
            "bodyCandidate": 3,
            "body": 2,
            "manual": 9,
            "": 0,
        }.get(row.get("linkSource") or "", 1)
        return (
            1 if row.get("isLinked") else 0,
            source_rank,
            to_float(row.get("confidence")),
            to_float(row.get("bodyMatchScore")),
        )

    for row in rows:
        key = (row["formationId"], row["slot"])
        if key not in rows_by_key or row_quality(row) > row_quality(rows_by_key[key]):
            rows_by_key[key] = row

    if ocr_dir and model_ocr_alias_index and formation_positions:
        for (fid, slug), meta in metadata_by_group.items():
            positions = formation_positions.get(fid) or {}
            if not positions:
                continue
            if slug not in page_entries_by_slug:
                page_text = extract_model_page_text(page_dir, slug) if page_dir and model_alias_index else ""
                page_entries_by_slug[slug] = body_mentioned_model_entries(page_text, model_alias_index) if page_text and model_alias_index else []
            page_entries = page_entries_by_slug.get(slug, [])
            slot_candidates = {}
            for chunk in read_ocr_chunks(ocr_dir, slug):
                slot, distance = nearest_slot_for_chunk(fid, chunk, formation_positions)
                if not slot or distance > 0.75:
                    continue
                role_name = slot_role(slot, positions)
                extra_entries = candidate_entries_by_source.get((slug, normalize_match_text(chunk["sourceName"])), [])
                entry, text_score = best_ocr_chunk_match(
                    chunk["sourceName"], model_ocr_alias_index, page_entries, role_name, extra_entries
                )
                if not entry:
                    continue
                quality = (text_score + role_compatibility(role_name, entry), -distance, chunk.get("ocrConfidence", 0))
                previous = slot_candidates.get(slot)
                if previous and previous[0] >= quality:
                    continue
                slot_candidates[slot] = (quality, {
                    "formationId": fid,
                    "slot": slot,
                    "sourceName": chunk["sourceName"],
                    "modelName": entry["modelName"],
                    "playerId": entry["playerId"],
                    "isLinked": True,
                    "linkSource": "ocrSlot",
                    "playerName": entry["playerName"],
                    "playerFullName": entry["playerFullName"],
                    "nation": entry["nation"],
                    "category": entry["category"],
                    "playType": entry["playType"],
                    "sourceTitle": meta.get("source_title") or "",
                    "sourceUrl": meta.get("source_url") or "",
                    "confidence": round(text_score * 100, 1),
                    "ocrConfidence": chunk.get("ocrConfidence", 0),
                    "slotDistance": round(distance, 3),
                    "candidateCount": 0,
                    "candidatePlayerId": 0,
                    "candidateModelName": "",
                    "bodyMatchScore": 0,
                })
            for slot, (_, candidate_row) in slot_candidates.items():
                key = (fid, slot)
                existing = rows_by_key.get(key)
                if not existing or row_quality(candidate_row) >= row_quality(existing):
                    rows_by_key[key] = candidate_row

            page_text = extract_model_page_text(page_dir, slug) if page_dir else ""
            role_mentions = role_mentions_from_text(page_text, page_entries)
            used_person_ids = {
                row.get("playerId")
                for (row_fid, _), row in rows_by_key.items()
                if row_fid == fid and row.get("isLinked") and row.get("playerId")
            }
            for slot in sorted(positions):
                key = (fid, slot)
                existing = rows_by_key.get(key)
                if existing and existing.get("isLinked"):
                    continue
                mention, role_score = best_role_match_for_slot(slot, positions, role_mentions, used_person_ids)
                if not mention:
                    continue
                entry = mention["entry"]
                candidate_row = {
                    "formationId": fid,
                    "slot": slot,
                    "sourceName": mention["sentence"][:48],
                    "modelName": entry["modelName"],
                    "playerId": entry["playerId"],
                    "isLinked": True,
                    "linkSource": "bodyRole",
                    "playerName": entry["playerName"],
                    "playerFullName": entry["playerFullName"],
                    "nation": entry["nation"],
                    "category": entry["category"],
                    "playType": entry["playType"],
                    "sourceTitle": meta.get("source_title") or "",
                    "sourceUrl": meta.get("source_url") or "",
                    "confidence": round(role_score * 100, 1),
                    "ocrConfidence": 0,
                    "slotDistance": 0,
                    "candidateCount": 0,
                    "candidatePlayerId": 0,
                    "candidateModelName": "",
                    "bodyMatchScore": round(role_score, 3),
                }
                rows_by_key[key] = candidate_row
                used_person_ids.add(entry["playerId"])

    overrides_file = Path(overrides_path).expanduser() if overrides_path else None
    if overrides_file and overrides_file.exists():
        for override in read_csv(overrides_file):
            fid = to_int(override.get("formation_id"))
            slot = to_int(override.get("slot"))
            model_name = str(override.get("model_name") or "").strip()
            if not fid or not slot or not model_name:
                continue
            slug = str(override.get("slug") or "").strip()
            meta = metadata_by_group.get((fid, slug), {})
            entry = model_entry_by_name.get(normalize_match_text(model_name))
            rows_by_key[(fid, slot)] = {
                "formationId": fid,
                "slot": slot,
                "sourceName": str(override.get("source_name") or model_name).strip(),
                "modelName": entry["modelName"] if entry else model_name,
                "playerId": entry["playerId"] if entry else 0,
                "isLinked": bool(entry),
                "linkSource": "manual",
                "playerName": entry["playerName"] if entry else "",
                "playerFullName": entry["playerFullName"] if entry else "",
                "nation": entry["nation"] if entry else "",
                "category": entry["category"] if entry else "",
                "playType": entry["playType"] if entry else "",
                "sourceTitle": meta.get("source_title") or "",
                "sourceUrl": meta.get("source_url") or "",
                "confidence": 100.0,
                "ocrConfidence": 0,
                "slotDistance": 0,
                "candidateCount": 0,
                "candidatePlayerId": 0,
                "candidateModelName": "",
                "bodyMatchScore": 0,
            }

    linked_by_formation_player = defaultdict(list)
    for key, row in rows_by_key.items():
        if row.get("isLinked") and row.get("playerId"):
            linked_by_formation_player[(row["formationId"], row["playerId"])].append((key, row))
    for items in linked_by_formation_player.values():
        if len(items) <= 1:
            continue
        keep_key, _ = max(
            items,
            key=lambda item: (
                row_quality(item[1]),
                -to_float(item[1].get("slotDistance"), 99),
            ),
        )
        for key, row in items:
            if key == keep_key:
                continue
            row["isLinked"] = False
            row["playerId"] = 0
            row["modelName"] = ""
            row["playerName"] = ""
            row["playerFullName"] = ""
            row["nation"] = ""
            row["category"] = ""
            row["playType"] = ""
            row["linkSource"] = ""
            row["candidatePlayerId"] = 0
            row["candidateModelName"] = ""

    rows = list(rows_by_key.values())
    rows.sort(key=lambda x: (x["formationId"], x["slot"], -x["confidence"], x["playerId"]))
    return rows


def load_sources(base_csv_dir, cc_dir):
    sqlite_dir = base_csv_dir / "csv" / "sqlite_tables"
    return {
        "formation": read_csv(sqlite_dir / "ZMOFORMATION.csv"),
        "formation_info": read_csv(sqlite_dir / "ZMOFORMATIONSINFO.csv"),
        "formation_key": read_csv(sqlite_dir / "ZMOFORMATIONSKEYPOSITION.csv"),
        "formation_pos": read_csv(sqlite_dir / "ZMOFORMATIONSPOSITION.csv"),
        "coach": read_csv(sqlite_dir / "ZMOHEADCOACH.csv"),
        "coach_understanding": read_csv(sqlite_dir / "ZMOHEADCOACHESUNDERSTANDING.csv"),
        "match_level": read_csv(cc_dir / "normalized" / "match_level.csv"),
        "team_level": read_csv(cc_dir / "normalized" / "team_level.csv"),
        "player_level": read_csv(cc_dir / "normalized" / "player_level.csv"),
    }


def load_sources_from_master_db(master_db_path):
    conn = sqlite3.connect(str(master_db_path))
    conn.row_factory = sqlite3.Row
    try:
        src = {
            "formation": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZNAME,
                      ZSYSTEM,
                      ZSTRIDE,
                      ZYEAR
                    FROM ao__ZMOFORMATION
                    """
                ).fetchall()
            ],
            "formation_info": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZSPD,
                      ZTEC,
                      ZPWR,
                      ZOFF,
                      ZDEF,
                      ZMID,
                      ZTTL,
                      ZSTM,
                      ZDIF,
                      ZDESCRIPTION_TEXT,
                      ZSUBTITLE
                    FROM ao__ZMOFORMATIONSINFO
                    """
                ).fetchall()
            ],
            "formation_key": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZKEYPOS,
                      ZPOS,
                      ZSUBTITLE,
                      ZDESCRIPTION_TEXT
                    FROM ao__ZMOFORMATIONSKEYPOSITION
                    """
                ).fetchall()
            ],
            "formation_pos": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZPOS,
                      ZX,
                      ZY
                    FROM ao__ZMOFORMATIONSPOSITION
                    """
                ).fetchall()
            ],
            "coach": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZHEADCOACH_ID,
                      ZNAME,
                      ZFULLNAME,
                      ZHEADCOACH_TYPE,
                      ZNATION_ID,
                      ZAGE,
                      ZACT_SZN,
                      ZRARITY
                    FROM ao__ZMOHEADCOACH
                    """
                ).fetchall()
            ],
            "coach_understanding": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZHEADCOACH_ID,
                      ZFORMATION_ID,
                      ZDEPTH
                    FROM ao__ZMOHEADCOACHESUNDERSTANDING
                    """
                ).fetchall()
            ],
            "team_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      side,
                      team_id,
                      team_name,
                      formation_id,
                      formation_name,
                      headcoach_id,
                      headcoach_name,
                      headcoach_pts,
                      goals_for,
                      goals_against,
                      result
                    FROM cc_teams
                    """
                ).fetchall()
            ],
            "match_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      title,
                      pk_winner_side
                    FROM cc_matches
                    """
                ).fetchall()
            ],
            "player_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      side,
                      team_id,
                      team_name,
                      formation_id,
                      formation_name,
                      member_order,
                      is_starting11,
                      player_id,
                      player_fullname,
                      player_name,
                      pos_code_1_4,
                      pts
                    FROM cc_players
                    """
                ).fetchall()
            ],
        }
        return src
    finally:
        conn.close()


def load_cc_from_db(cc_db_path):
    conn = sqlite3.connect(str(cc_db_path))
    conn.row_factory = sqlite3.Row
    try:
        team_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  side,
                  team_id,
                  team_name,
                  formation_id,
                  formation_name,
                  headcoach_id,
                  headcoach_name,
                  headcoach_pts,
                  goals_for,
                  goals_against,
                  result
                FROM teams
                """
            ).fetchall()
        ]
        match_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  title,
                  pk_winner_side
                FROM matches
                """
            ).fetchall()
        ]
        player_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  side,
                  team_id,
                  team_name,
                  formation_id,
                  formation_name,
                  member_order,
                  is_starting11,
                  player_id,
                  player_fullname,
                  player_name,
                  pos_code_1_4,
                  pts
                FROM players
                """
            ).fetchall()
        ]
        return {"match_level": match_rows, "team_level": team_rows, "player_level": player_rows}
    finally:
        conn.close()


def build_data(src):
    formation_rows = src["formation"]
    formation_info_rows = src["formation_info"]
    key_rows = src["formation_key"]
    pos_rows = src["formation_pos"]
    coach_rows = src["coach"]
    understanding_rows = src["coach_understanding"]
    match_rows = src.get("match_level", [])
    team_rows = src["team_level"]
    player_rows = src["player_level"]
    model_slot_rows = src.get("model_slots", [])

    formation_by_id = {}
    for row in formation_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        formation_by_id[fid] = {
            "id": fid,
            "name": row.get("ZNAME") or f"Formation {fid}",
            "system": row.get("ZSYSTEM") or "",
            "stride": to_int(row.get("ZSTRIDE")),
            "year": to_int(row.get("ZYEAR")),
            "params": {k: 0 for k, _ in PARAM_KEYS},
            "description": "",
            "subtitle": "",
            "positions": [],
            "keyPositions": [],
        }

    for row in formation_info_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        for out_key, col in PARAM_KEYS:
            f["params"][out_key] = to_int(row.get(col))
        f["description"] = row.get("ZDESCRIPTION_TEXT") or ""
        f["subtitle"] = row.get("ZSUBTITLE") or ""

    for row in pos_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        f["positions"].append({
            "slot": to_int(row.get("ZPOS")),
            "x": to_float(row.get("ZX")),
            "y": to_float(row.get("ZY")),
        })

    for f in formation_by_id.values():
        f["positions"].sort(key=lambda p: p["slot"])

    for row in key_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        f["keyPositions"].append({
            "rank": to_int(row.get("ZKEYPOS")),
            "slot": to_int(row.get("ZPOS")),
            "subtitle": row.get("ZSUBTITLE") or "",
            "description": row.get("ZDESCRIPTION_TEXT") or "",
        })

    for f in formation_by_id.values():
        f["keyPositions"].sort(key=lambda p: (p["rank"], p["slot"]))

    model_slots_by_formation = defaultdict(list)
    for row in model_slot_rows:
        fid = to_int(row.get("formationId"))
        slot = to_int(row.get("slot"))
        if not fid or not slot:
            continue
        model_slots_by_formation[fid].append(row)

    for rows in model_slots_by_formation.values():
        rows.sort(key=lambda x: (to_int(x.get("slot")), -to_float(x.get("confidence")), to_int(x.get("playerId"))))

    coach_by_id = {}
    for row in coach_rows:
        cid = to_int(row.get("ZHEADCOACH_ID"))
        coach_by_id[cid] = {
            "id": cid,
            "name": row.get("ZNAME") or "",
            "fullName": row.get("ZFULLNAME") or "",
            "type": to_int(row.get("ZHEADCOACH_TYPE")),
            "nationId": to_int(row.get("ZNATION_ID")),
            "age": to_int(row.get("ZAGE")),
            "actSzn": to_int(row.get("ZACT_SZN")),
            "rarity": to_int(row.get("ZRARITY")),
        }

    coach_to_formations = defaultdict(list)
    coach_to_formations_depth4 = defaultdict(list)
    formation_to_coaches_all = defaultdict(list)
    formation_to_coaches_depth4 = defaultdict(list)

    for row in understanding_rows:
        cid = to_int(row.get("ZHEADCOACH_ID"))
        fid = to_int(row.get("ZFORMATION_ID"))
        depth = to_int(row.get("ZDEPTH"))
        if cid not in coach_by_id or fid not in formation_by_id:
            continue

        # Obtainable: keep original understanding-linked set (all depth rows).
        coach_to_formations[cid].append({"formationId": fid, "depth": depth})
        formation_to_coaches_all[fid].append({"coachId": cid, "depth": depth})

        # Depth4: use raw understanding depth as-is.
        if depth == 4:
            coach_to_formations_depth4[cid].append({"formationId": fid, "depth": depth})
            formation_to_coaches_depth4[fid].append({"coachId": cid, "depth": depth})

    for cid in coach_to_formations:
        coach_to_formations[cid].sort(key=lambda x: x["formationId"])
    for cid in coach_to_formations_depth4:
        coach_to_formations_depth4[cid].sort(key=lambda x: x["formationId"])

    # Team-level aggregate for usage/win rate and coach usage.
    formation_team_counts = defaultdict(int)
    formation_win_counts = defaultdict(int)
    formation_goal_diff_sum = defaultdict(float)
    formation_goal_diff_sq_sum = defaultdict(float)
    formation_goal_diff_n = defaultdict(int)
    total_team_rows = 0
    coach_use_count = defaultdict(int)  # (formation, coach) -> use count
    coach_pts_sum = defaultdict(float)  # (formation, coach) -> sum pts
    coach_name_by_id = {}
    match_rows_by_key = defaultdict(list)
    team_row_by_instance = {}
    team_season_match_count = defaultdict(int)
    match_info_by_key = {}
    team_season_finish = {}

    for row in match_rows:
        mkey = (to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")))
        match_info_by_key[mkey] = {
            "title": row.get("title") or "",
            "roundRank": cc_round_rank(row.get("title")),
            "pkWinnerSide": row.get("pk_winner_side") or "",
        }

    for row in team_rows:
        fid = to_int(row.get("formation_id"))
        if fid not in formation_by_id:
            continue
        total_team_rows += 1
        formation_team_counts[fid] += 1
        if (row.get("result") or "").strip().upper() == "W":
            formation_win_counts[fid] += 1
        gf = to_float(row.get("goals_for"), None)
        ga = to_float(row.get("goals_against"), None)
        if gf is not None and ga is not None:
            gd = gf - ga
            formation_goal_diff_sum[fid] += gd
            formation_goal_diff_sq_sum[fid] += gd * gd
            formation_goal_diff_n[fid] += 1
        cid = to_int(row.get("headcoach_id"))
        if cid > 0:
            key = (fid, cid)
            coach_use_count[key] += 1
            pts = to_float(row.get("headcoach_pts"), None)
            if pts is not None:
                coach_pts_sum[key] += pts
            coach_name_by_id[cid] = row.get("headcoach_name") or coach_by_id.get(cid, {}).get("name") or str(cid)
        mkey = (to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")))
        match_rows_by_key[mkey].append(row)
        team_row_by_instance[team_instance_key(row)] = row
        team_season_match_count[(to_int(row.get("season")), to_int(row.get("team_id")))] += 1
        finish_key = (to_int(row.get("season")), to_int(row.get("team_id")))
        match_info = match_info_by_key.get(mkey, {})
        round_rank = int(match_info.get("roundRank") or 0)
        prev = team_season_finish.get(finish_key)
        if not prev or round_rank > int(prev.get("roundRank") or 0):
            team_season_finish[finish_key] = {
                "roundRank": round_rank,
                "label": finish_label_from_rank(
                    round_rank,
                    row.get("result"),
                    row.get("side"),
                    match_info.get("pkWinnerSide"),
                ),
            }

    # Slot usage and pts by (formation, slot, player)
    formation_slot_total = defaultdict(int)
    slot_player_count = defaultdict(int)
    slot_player_pts_sum = defaultdict(float)
    slot_player_name = {}
    slot_player_fullname = {}
    starting_members_by_instance = defaultdict(list)

    for row in player_rows:
        if str(row.get("is_starting11") or "") != "1":
            continue
        fid = to_int(row.get("formation_id"))
        slot = to_int(row.get("member_order"))
        pid = to_int(row.get("player_id"))
        if fid not in formation_by_id or slot < 1 or slot > 11 or pid <= 0:
            continue
        key = (fid, slot, pid)
        formation_slot_total[(fid, slot)] += 1
        slot_player_count[key] += 1
        pts = to_float(row.get("pts"), None)
        if pts is not None:
            slot_player_pts_sum[key] += pts
        slot_player_name[pid] = row.get("player_name") or row.get("player_fullname") or str(pid)
        slot_player_fullname[pid] = row.get("player_fullname") or row.get("player_name") or str(pid)
        starting_members_by_instance[team_instance_key(row)].append({
            "slot": slot,
            "playerId": pid,
            "playerName": row.get("player_name") or row.get("player_fullname") or str(pid),
            "playerFullName": row.get("player_fullname") or row.get("player_name") or str(pid),
            "pos": to_int(row.get("pos_code_1_4")),
            "ptsSum": to_float(row.get("pts"), 0.0),
        })

    slot_stats = defaultdict(lambda: defaultdict(list))
    slot_top = defaultdict(dict)

    for (fid, slot, pid), count in slot_player_count.items():
        denom = formation_slot_total[(fid, slot)] or 1
        rate = count / denom
        pts_avg = slot_player_pts_sum[(fid, slot, pid)] / count if count else 0.0
        pts_sum = slot_player_pts_sum[(fid, slot, pid)]
        item = {
            "playerId": pid,
            "playerName": slot_player_name.get(pid, str(pid)),
            "playerFullName": slot_player_fullname.get(pid, slot_player_name.get(pid, str(pid))),
            "uses": count,
            "usageRate": round(rate, 6),
            "ptsSum": round(pts_sum, 4),
            "avgPts": round(pts_avg, 4),
        }
        slot_stats[fid][slot].append(item)

    for fid, slots in slot_stats.items():
        for slot, items in slots.items():
            items.sort(key=lambda x: (-x["usageRate"], -x["uses"], -x["avgPts"], x["playerId"]))
            slot_top[fid][slot] = items[0]

    coach_stats = defaultdict(list)
    for (fid, cid), count in coach_use_count.items():
        denom = formation_team_counts[fid] or 1
        usage = count / denom
        avg_pts = coach_pts_sum[(fid, cid)] / count if count else 0.0
        coach_stats[fid].append({
            "coachId": cid,
            "coachName": coach_name_by_id.get(cid, str(cid)),
            "uses": count,
            "usageRate": round(usage, 6),
            "ptsSum": round(coach_pts_sum[(fid, cid)], 4),
            "avgPts": round(avg_pts, 4),
        })
    for fid in coach_stats:
        coach_stats[fid].sort(key=lambda x: (-x["usageRate"], -x["uses"], -x["avgPts"], x["coachId"]))

    best_team_groups = {}
    for instance_key, members in starting_members_by_instance.items():
        team = team_row_by_instance.get(instance_key)
        if not team:
            continue
        fid = to_int(team.get("formation_id"))
        cid = to_int(team.get("headcoach_id"))
        season = to_int(team.get("season"))
        team_id = to_int(team.get("team_id"))
        if fid not in formation_by_id or cid <= 0 or season <= 0 or team_id <= 0:
            continue
        lineup = sorted(members, key=lambda x: x["slot"])
        if len(lineup) != 11 or len({m["slot"] for m in lineup}) != 11:
            continue
        lineup_signature = tuple((int(m["slot"]), int(m["playerId"])) for m in lineup)
        group_key = (season, team_id, fid, cid, lineup_signature)
        if group_key not in best_team_groups:
            team_season_matches = team_season_match_count[(season, team_id)]
            best_team_groups[group_key] = {
                "formationId": fid,
                "season": season,
                "teamId": team_id,
                "teamName": team.get("team_name") or "",
                "teamSeasonMatches": team_season_matches,
                "coach": {
                    "id": cid,
                    "name": team.get("headcoach_name") or coach_name_by_id.get(cid, str(cid)),
                    "ptsSum": 0.0,
                },
                "matches": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0.0,
                "goalsFor": 0,
                "goalsAgainst": 0,
                "goalDiff": 0,
                "playerPtsSum": 0.0,
                "membersBySlot": {int(m["slot"]): {**m} for m in lineup},
            }
        group = best_team_groups[group_key]
        group["matches"] += 1
        result = str(team.get("result") or "").strip().upper()
        if result == "W":
            group["wins"] += 1
        elif result == "D":
            group["draws"] += 1
        elif result == "L":
            group["losses"] += 1
        points = points_from_row(team) or 0.0
        gf = to_int(team.get("goals_for"))
        ga = to_int(team.get("goals_against"))
        group["points"] += points
        group["goalsFor"] += gf
        group["goalsAgainst"] += ga
        group["goalDiff"] += gf - ga
        coach_pts = to_float(team.get("headcoach_pts"), 0.0)
        group["coach"]["ptsSum"] += coach_pts
        for member in lineup:
            slot = int(member["slot"])
            pts = float(member.get("ptsSum") or 0.0)
            group["playerPtsSum"] += pts
            group["membersBySlot"][slot]["ptsSum"] = float(group["membersBySlot"][slot].get("ptsSum") or 0.0) + pts

    best_teams = defaultdict(list)
    for group in best_team_groups.values():
        matches = int(group["matches"] or 0)
        if matches <= 0:
            continue
        team_season_matches = int(group.get("teamSeasonMatches") or 0)
        if team_season_matches > 0 and matches != team_season_matches:
            continue
        members = []
        for slot in sorted(group["membersBySlot"]):
            member = group["membersBySlot"][slot]
            pts_sum = float(member.get("ptsSum") or 0.0)
            player_id = int(member.get("playerId") or 0)
            slot_usage_rate = 0
            for row in slot_stats[group["formationId"]].get(slot, []):
                if int(row.get("playerId") or 0) == player_id:
                    slot_usage_rate = row.get("usageRate", 0)
                    break
            members.append({
                "slot": slot,
                "playerId": player_id,
                "playerName": member.get("playerName") or "",
                "playerFullName": member.get("playerFullName") or member.get("playerName") or "",
                "pos": int(member.get("pos") or 0),
                "usageRate": slot_usage_rate,
                "ptsSum": round(pts_sum, 4),
                "avgPts": round(pts_sum / matches, 4),
            })
        coach_pts_sum = float(group["coach"].get("ptsSum") or 0.0)
        item = {
            "method": "season_team_same_coach_formation_lineup",
            "season": group["season"],
            "teamId": group["teamId"],
            "teamName": group["teamName"],
            "finish": team_season_finish.get((group["season"], group["teamId"]), {}).get("label", "GL Exit"),
            "matches": matches,
            "teamSeasonMatches": team_season_matches,
            "wins": int(group["wins"] or 0),
            "draws": int(group["draws"] or 0),
            "losses": int(group["losses"] or 0),
            "points": round(float(group["points"] or 0.0), 4),
            "goalsFor": int(group["goalsFor"] or 0),
            "goalsAgainst": int(group["goalsAgainst"] or 0),
            "goalDiff": int(group["goalDiff"] or 0),
            "score": int(group["wins"] or 0),
            "playerPtsSum": round(float(group["playerPtsSum"] or 0.0), 4),
            "avgPlayerPts": round(float(group["playerPtsSum"] or 0.0) / (matches * 11), 4),
            "coach": {
                "id": group["coach"]["id"],
                "name": group["coach"]["name"],
                "ptsSum": round(coach_pts_sum, 4),
                "avgPts": round(coach_pts_sum / matches, 4),
            },
            "members": members,
        }
        best_teams[group["formationId"]].append(item)

    for fid in best_teams:
        best_teams[fid].sort(
            key=lambda x: (
                -int(x.get("wins") or 0),
                -int(x.get("goalDiff") or 0),
                -int(x.get("goalsFor") or 0),
                -float(x.get("points") or 0.0),
                -int(x.get("matches") or 0),
                -int(x.get("season") or 0),
                str(x.get("teamName") or ""),
                int(x.get("teamId") or 0),
            )
        )
        for idx, team in enumerate(best_teams[fid][:5], start=1):
            team["rank"] = idx

    # Formation vs formation matchup stats (with significance filter).
    # Primary metric: strength-adjusted expected-points residual.
    # Why this metric:
    # - Handles draw-heavy formations better than pure win-rate.
    # - Avoids over-penalizing strong-but-low-margin styles from GD-only view.
    # - Controls for baseline formation strength on both sides.
    #
    # Points model:
    #   observedPts = 3/1/0 (W/D/L)
    #   expectedPts(fid vs opp) ~= global_mu + rating(fid) - rating(opp)
    # where rating(*) is fitted from all team-level rows by simple regularized
    # gradient updates.
    formation_mu_pts = {}
    formation_pts_sum = defaultdict(float)
    formation_pts_n = defaultdict(int)
    obs_rows = []
    total_pts = 0.0
    total_n = 0
    for rows in match_rows_by_key.values():
        if len(rows) != 2:
            continue
        a, b = rows[0], rows[1]
        fa = to_int(a.get("formation_id"))
        fb = to_int(b.get("formation_id"))
        if fa <= 0 or fb <= 0:
            continue
        pa = points_from_row(a)
        pb = points_from_row(b)
        if pa is None or pb is None:
            continue
        obs_rows.append((fa, fb, pa))
        obs_rows.append((fb, fa, pb))
        formation_pts_sum[fa] += pa
        formation_pts_sum[fb] += pb
        formation_pts_n[fa] += 1
        formation_pts_n[fb] += 1
        total_pts += pa + pb
        total_n += 2

    for fid, n in formation_pts_n.items():
        if n > 0:
            formation_mu_pts[fid] = formation_pts_sum[fid] / n

    global_mu_pts = (total_pts / total_n) if total_n else 1.0
    ratings = {fid: 0.0 for fid in formation_pts_n.keys()}
    if obs_rows:
        lr = 0.01
        l2 = 0.001
        for _ in range(120):
            for fa, fb, p_obs in obs_rows:
                ra = ratings.get(fa, 0.0)
                rb = ratings.get(fb, 0.0)
                pred = global_mu_pts + ra - rb
                err = p_obs - pred
                ratings[fa] = ra + lr * (err - l2 * ra)
                ratings[fb] = rb - lr * (err + l2 * rb)
            if ratings:
                mean_r = sum(ratings.values()) / len(ratings)
                for fid in ratings:
                    ratings[fid] -= mean_r

    matchup_raw = defaultdict(
        lambda: defaultdict(
            lambda: {
                "matches": 0,
                "goalDiffSum": 0.0,
                "pointsSum": 0.0,
                "expectedPointsSum": 0.0,
                "residualSum": 0.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
            }
        )
    )
    formation_residual_sum = defaultdict(float)
    formation_residual_sq_sum = defaultdict(float)
    formation_residual_n = defaultdict(int)
    for rows in match_rows_by_key.values():
        if len(rows) != 2:
            continue
        a, b = rows[0], rows[1]
        fa = to_int(a.get("formation_id"))
        fb = to_int(b.get("formation_id"))
        if fa <= 0 or fb <= 0:
            continue
        gfa = to_float(a.get("goals_for"), None)
        gaa = to_float(a.get("goals_against"), None)
        gfb = to_float(b.get("goals_for"), None)
        gab = to_float(b.get("goals_against"), None)
        if gfa is None or gaa is None or gfb is None or gab is None:
            continue

        gd_a = gfa - gaa
        gd_b = gfb - gab
        p_a = points_from_row(a)
        p_b = points_from_row(b)
        if p_a is None or p_b is None:
            continue

        exp_a = global_mu_pts + ratings.get(fa, 0.0) - ratings.get(fb, 0.0)
        exp_b = global_mu_pts + ratings.get(fb, 0.0) - ratings.get(fa, 0.0)
        res_a = p_a - exp_a
        res_b = p_b - exp_b

        matchup_raw[fa][fb]["matches"] += 1
        matchup_raw[fb][fa]["matches"] += 1
        matchup_raw[fa][fb]["goalDiffSum"] += gd_a
        matchup_raw[fb][fa]["goalDiffSum"] += gd_b
        matchup_raw[fa][fb]["pointsSum"] += p_a
        matchup_raw[fb][fa]["pointsSum"] += p_b
        matchup_raw[fa][fb]["expectedPointsSum"] += exp_a
        matchup_raw[fb][fa]["expectedPointsSum"] += exp_b
        matchup_raw[fa][fb]["residualSum"] += res_a
        matchup_raw[fb][fa]["residualSum"] += res_b
        if p_a >= 2.5:
            matchup_raw[fa][fb]["wins"] += 1
            matchup_raw[fb][fa]["losses"] += 1
        elif p_a >= 0.5:
            matchup_raw[fa][fb]["draws"] += 1
            matchup_raw[fb][fa]["draws"] += 1
        else:
            matchup_raw[fa][fb]["losses"] += 1
            matchup_raw[fb][fa]["wins"] += 1

        formation_residual_sum[fa] += res_a
        formation_residual_sum[fb] += res_b
        formation_residual_sq_sum[fa] += res_a * res_a
        formation_residual_sq_sum[fb] += res_b * res_b
        formation_residual_n[fa] += 1
        formation_residual_n[fb] += 1

    # Matchup ranking tuned for practical comparison:
    # - primary metric: strength-adjusted points residual (AdjPts)
    # - guardrail: minimum sample, then show the strongest/weakest ranked deltas.
    min_matchups = 15
    matchup_stats = defaultdict(lambda: {"strongAgainst": [], "weakAgainst": []})

    for fid, opp_map in matchup_raw.items():
        rn = formation_residual_n[fid]
        if rn <= 0:
            continue
        var0 = (formation_residual_sq_sum[fid] / rn) - ((formation_residual_sum[fid] / rn) ** 2)
        if var0 <= 1e-9:
            continue
        strong = []
        weak = []
        for opp_id, stat in opp_map.items():
            if int(opp_id) == int(fid):
                continue
            n = int(stat["matches"] or 0)
            if n < min_matchups:
                continue
            gd_sum = float(stat["goalDiffSum"] or 0.0)
            pts_sum = float(stat["pointsSum"] or 0.0)
            exp_pts_sum = float(stat["expectedPointsSum"] or 0.0)
            residual_sum = float(stat["residualSum"] or 0.0)
            mu_hat = gd_sum / n if n else 0.0
            pts_hat = pts_sum / n if n else 0.0
            exp_pts_hat = exp_pts_sum / n if n else 0.0
            delta = residual_sum / n if n else 0.0
            z = delta / math.sqrt(var0 / n)
            row = {
                "formationId": int(opp_id),
                "matches": n,
                "wins": int(stat["wins"] or 0),
                "draws": int(stat["draws"] or 0),
                "losses": int(stat["losses"] or 0),
                "goalDiffSum": round(gd_sum, 4),
                "goalDiffPerMatch": round(mu_hat, 6),
                "pointsPerMatch": round(pts_hat, 6),
                "expectedPointsPerMatch": round(exp_pts_hat, 6),
                "overallPointsPerMatch": round(formation_mu_pts.get(fid, global_mu_pts), 6),
                "residualPointsPerMatch": round(delta, 6),
                "delta": round(delta, 6),
                "zScore": round(z, 4),
            }
            if n >= 40:
                row["confidence"] = "High"
            elif n >= 25:
                row["confidence"] = "Mid"
            else:
                row["confidence"] = "Low"
            if delta > 0:
                strong.append(row)
            elif delta < 0:
                weak.append(row)

        strong.sort(key=lambda x: (-x["delta"], -x["matches"], x["formationId"]))
        weak.sort(key=lambda x: (x["delta"], -x["matches"], x["formationId"]))
        matchup_stats[fid] = {
            "strongAgainst": strong[:5],
            "weakAgainst": weak[:5],
            "criteria": {
                "minMatches": min_matchups,
                "method": "ranked_strength_adjusted_points_residual",
                "ranking": "top_bottom_delta_adj_pts",
                "confidenceBands": {
                    "low": [15, 24],
                    "mid": [25, 39],
                    "high": [40, None],
                },
            },
        }

    formations = []
    for fid in sorted(formation_by_id):
        f = formation_by_id[fid]
        uses = formation_team_counts[fid]
        wins = formation_win_counts[fid]
        usage_rate = (uses / total_team_rows) if total_team_rows else 0.0
        win_rate = (wins / uses) if uses else 0.0

        obtainables = sorted(formation_to_coaches_all[fid], key=lambda x: (-x["depth"], x["coachId"]))
        depth4 = sorted(formation_to_coaches_depth4[fid], key=lambda x: x["coachId"])

        f_item = {
            **f,
            "cc": {
                "uses": uses,
                "wins": wins,
                "usageRate": round(usage_rate, 6),
                "winRate": round(win_rate, 6),
            },
            "coaches": {
                "obtainable": [
                    {
                        "id": row["coachId"],
                        "name": coach_by_id[row["coachId"]]["name"],
                        "depth": row["depth"],
                    }
                    for row in obtainables
                ],
                "depth4": [
                    {
                        "id": row["coachId"],
                        "name": coach_by_id[row["coachId"]]["name"],
                        "depth": row["depth"],
                    }
                    for row in depth4
                ],
            },
            "slotTop": {
                str(slot): slot_top[fid][slot]
                for slot in sorted(slot_top[fid])
            },
            "slotStats": {
                str(slot): slot_stats[fid][slot]
                for slot in sorted(slot_stats[fid])
            },
            "coachStats": coach_stats[fid],
            "matchups": matchup_stats[fid],
            "bestTeams": best_teams[fid][:5],
            "modelSlots": model_slots_by_formation.get(fid, []),
        }
        formations.append(f_item)

    coaches = []
    for cid in sorted(coach_by_id):
        c = coach_by_id[cid]
        rel = coach_to_formations[cid]
        rel4 = coach_to_formations_depth4[cid]
        coaches.append({
            **c,
            "formationDepth4": [x["formationId"] for x in rel4],
            "formationObtainable": [x["formationId"] for x in rel],
        })

    return {
        "meta": {
            "generatedFrom": {
                "ccTeamRows": len(team_rows),
                "ccPlayerRows": len(player_rows),
                "formationCount": len(formations),
                "coachCount": len(coaches),
                "totalTeamRowsForUsage": total_team_rows,
            }
        },
        "formations": formations,
        "coaches": coaches,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-csv-dir", default="/Users/k.nishimura/Desktop/csv data")
    parser.add_argument("--cc-dir", default="/Users/k.nishimura/Desktop/CC_match_result_csv")
    parser.add_argument(
        "--cc-db",
        default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"),
        help="SQLite DB path for CC match data (if exists, this is used instead of --cc-dir CSV)",
    )
    parser.add_argument(
        "--master-db",
        default="",
        help="Unified master SQLite DB path (if set and exists, this is used as full source)",
    )
    parser.add_argument(
        "--model-slot-csv",
        default=str(DEFAULT_MODEL_SLOT_CSV),
        help="CSV path for validated formation model-player mappings",
    )
    parser.add_argument(
        "--model-page-dir",
        default=str(DEFAULT_MODEL_PAGE_DIR),
        help="Directory containing source formation HTML pages for body-text model matching",
    )
    parser.add_argument(
        "--model-ocr-dir",
        default=str(DEFAULT_MODEL_OCR_DIR),
        help="Directory containing source formation OCR TSV files for slot-aware model matching",
    )
    parser.add_argument(
        "--model-slot-overrides-csv",
        default=str(DEFAULT_MODEL_SLOT_OVERRIDES_CSV),
        help="CSV path for manually confirmed formation model slot overrides",
    )
    parser.add_argument("--out", default="/Users/k.nishimura/work/coding/websoccer-player-search/app/formations_data.json")
    args = parser.parse_args()

    master_db_path = Path(args.master_db).expanduser().resolve() if args.master_db else None
    if master_db_path and master_db_path.exists():
        src = load_sources_from_master_db(master_db_path)
        print(f"using master db: {master_db_path}")
    else:
        src = load_sources(Path(args.base_csv_dir), Path(args.cc_dir))
        cc_db_path = Path(args.cc_db).expanduser().resolve()
        if cc_db_path.exists():
            src.update(load_cc_from_db(cc_db_path))
            print(f"using cc db: {cc_db_path}")
        else:
            print(f"cc db not found, fallback csv: {Path(args.cc_dir).expanduser().resolve()}")
    model_slots = load_model_slots(
        args.model_slot_csv,
        args.model_page_dir,
        master_db_path,
        args.model_ocr_dir,
        args.model_slot_overrides_csv,
    )
    src["model_slots"] = model_slots
    if model_slots:
        print(f"using model slot csv: {Path(args.model_slot_csv).expanduser().resolve()} ({len(model_slots)} rows)")
    else:
        print(f"model slot csv not found or empty: {Path(args.model_slot_csv).expanduser().resolve()}")
    out = build_data(src)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"formations={len(out['formations'])} coaches={len(out['coaches'])}")


if __name__ == "__main__":
    main()
