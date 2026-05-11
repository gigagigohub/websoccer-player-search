#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
from pathlib import Path


DEFAULT_REPO = Path("/Users/k.nishimura/work/coding/websoccer-player-search")
DEFAULT_WSM_DIR = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db")
DEFAULT_RESOURCES = Path("/Users/k.nishimura/work/coding/wsc_data/Resources/img")


def latest_wsm(wsm_dir):
    files = sorted(
        [p for p in Path(wsm_dir).glob("wsm_*.sqlite3") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError(f"No wsm_*.sqlite3 found in {wsm_dir}")
    return files[0]


def rel_app_path(path, app_dir):
    return "./" + path.relative_to(app_dir).as_posix()


def copy_if_exists(src, dst):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def build_uniforms(conn, resources_dir, app_dir):
    rows = conn.execute(
        """
        SELECT ZUNIFORM_ID, ZNAME, ZYEAR, ZCATEGORY_ID, ZRARITY, ZSTRIDE
        FROM ao__ZMOUNIFORM
        ORDER BY ZUNIFORM_ID
        """
    ).fetchall()
    uniforms = []
    for uniform_id, name, year, category_id, rarity, stride in rows:
        image_paths = {}
        for kind in ("home", "away", "series"):
            src = resources_dir / "uniforms" / kind / f"{uniform_id}@2x.gif"
            dst = app_dir / "images" / "collections" / "uniforms" / kind / f"{uniform_id}@2x.gif"
            if copy_if_exists(src, dst):
                image_paths[kind] = rel_app_path(dst, app_dir)

        title_parts = [str(name or "").strip()]
        if year:
            title_parts.append(str(year))
        title = " ".join(x for x in title_parts if x)
        uniforms.append(
            {
                "id": int(uniform_id),
                "name": title,
                "baseName": str(name or "").strip(),
                "year": int(year or 0),
                "categoryId": int(category_id or 0),
                "rarity": int(rarity or 0),
                "stride": int(stride or 0),
                "images": image_paths,
            }
        )
    return uniforms


def build_emblems(conn, resources_dir, app_dir):
    rows = conn.execute(
        """
        SELECT ZEMBLEM_ID, ZNAME, ZCATEGORY_ID, ZRARITY
        FROM ao__ZMOEMBLEM
        ORDER BY ZEMBLEM_ID
        """
    ).fetchall()
    emblems = []
    for emblem_id, name, category_id, rarity in rows:
        src = resources_dir / "emblems" / f"{emblem_id}@2x.gif"
        dst = app_dir / "images" / "collections" / "emblems" / f"{emblem_id}@2x.gif"
        image = rel_app_path(dst, app_dir) if copy_if_exists(src, dst) else ""
        emblems.append(
            {
                "id": int(emblem_id),
                "name": str(name or "").strip(),
                "categoryId": int(category_id or 0),
                "rarity": int(rarity or 0),
                "image": image,
            }
        )
    return emblems


def main():
    parser = argparse.ArgumentParser(description="Export uniform/emblem collections data for the static site.")
    parser.add_argument("--repo-dir", default=str(DEFAULT_REPO))
    parser.add_argument("--master-db", default="")
    parser.add_argument("--wsm-dir", default=str(DEFAULT_WSM_DIR))
    parser.add_argument("--resources-dir", default=str(DEFAULT_RESOURCES))
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir)
    app_dir = repo_dir / "app"
    resources_dir = Path(args.resources_dir)
    master_db = Path(args.master_db) if args.master_db else latest_wsm(args.wsm_dir)

    conn = sqlite3.connect(master_db)
    data = {
        "source": "master-db",
        "uniforms": build_uniforms(conn, resources_dir, app_dir),
        "emblems": build_emblems(conn, resources_dir, app_dir),
    }
    out = app_dir / "collections_data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}")
    print(f"uniforms={len(data['uniforms'])} emblems={len(data['emblems'])}")


if __name__ == "__main__":
    main()
