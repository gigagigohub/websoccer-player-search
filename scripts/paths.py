from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_ROOT = REPO_ROOT.parent


def wsc_data_root() -> Path:
    env = os.environ.get("WSC_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    local = CODEX_ROOT / "wsc_data"
    if local.exists():
        return local
    return Path.home() / "work" / "coding" / "wsc_data"


WSC_DATA = wsc_data_root()


def latest_wsm_file() -> Path:
    wsm_dir = WSC_DATA / "websoccer_master_db"
    files = sorted(wsm_dir.glob("wsm_*.sqlite3"), key=lambda p: (p.name, p.stat().st_mtime))
    if files:
        return files[-1]
    return wsm_dir / "websoccer_master.sqlite3"
