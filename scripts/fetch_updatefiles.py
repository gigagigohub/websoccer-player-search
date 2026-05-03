#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_BASE_URL = "https://resources-ios.app.websoccer.jp"
DEFAULT_USER_AGENT = "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"


@dataclass
class Result:
    version: int
    url: str
    status: str
    http_code: int | None
    size: int
    sha256: str
    saved_path: str
    note: str


def parse_versions(spec: str) -> list[int]:
    vals: set[int] = set()
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            start, end = int(a), int(b)
            if end < start:
                start, end = end, start
            vals.update(range(start, end + 1))
        else:
            vals.add(int(chunk))
    return sorted(vals)


def parse_span(path: Path) -> tuple[int, int] | None:
    m = re.fullmatch(r"UpdateFile_p(\d+)_(\d+)", path.name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def iter_local_versions(update_dir: Path) -> Iterable[int]:
    for p in update_dir.glob("p*.zip"):
        m = re.fullmatch(r"p(\d+)\.zip", p.name)
        if m and p.stat().st_size > 0:
            yield int(m.group(1))


def default_update_dir() -> Path:
    root = Path.home() / "work" / "coding" / "wsc_data"
    cands = []
    for path in root.glob("UpdateFile_p*_*"):
        span = parse_span(path)
        if path.is_dir() and span:
            cands.append((span[1], span[0], path))
    if cands:
        cands.sort(reverse=True)
        return cands[0][2]
    return root / "UpdateFile_p40_322"


def default_versions(update_dir: Path) -> list[int]:
    versions = sorted(iter_local_versions(update_dir))
    if versions:
        return [versions[-1] + 1]
    span = parse_span(update_dir)
    if span:
        return [span[1] + 1]
    return []


def fetch_bytes(url: str, timeout: float, verify_tls: bool) -> tuple[int, str, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
            "Cache-Control": "no-cache",
        },
    )
    ctx = None if verify_tls else ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as res:
        return getattr(res, "status", 200), res.headers.get("Content-Type", ""), res.read()


def validate_zip(payload: bytes) -> tuple[bool, str]:
    if not payload.startswith(b"PK\x03\x04"):
        return False, "not-zip-signature"
    try:
        import io

        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            bad = zf.testzip()
            if bad:
                return False, f"bad-zip-entry:{bad}"
            entries = len(zf.infolist())
    except Exception as exc:
        return False, f"zip-validation-error:{type(exc).__name__}"
    return True, f"zip entries={entries}"


def fetch_one(version: int, base_url: str, update_dir: Path, timeout: float, verify_tls: bool, dry_run: bool) -> Result:
    url = f"{base_url.rstrip('/')}/UpdateFile/p{version}.zip"
    out = update_dir / f"p{version}.zip"
    if out.exists() and out.stat().st_size > 0:
        payload = out.read_bytes()
        ok, note = validate_zip(payload)
        return Result(
            version=version,
            url=url,
            status="exists_ok" if ok else "exists_invalid",
            http_code=None,
            size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            saved_path=str(out),
            note=note,
        )

    try:
        code, content_type, payload = fetch_bytes(url, timeout=timeout, verify_tls=verify_tls)
    except urllib.error.HTTPError as exc:
        return Result(version, url, "missing", exc.code, 0, "", "", f"HTTPError {exc.code}")
    except Exception as exc:
        return Result(version, url, "failed", None, 0, "", "", f"{type(exc).__name__}: {exc}")

    ok, note = validate_zip(payload)
    if not ok:
        return Result(version, url, "invalid", code, len(payload), hashlib.sha256(payload).hexdigest(), "", note)

    saved_path = ""
    if not dry_run:
        update_dir.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)
        saved_path = str(out)
    return Result(
        version=version,
        url=url,
        status="available" if dry_run else "downloaded",
        http_code=code,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        saved_path=saved_path,
        note=f"{note} ct={content_type}",
    )


def maybe_rename_update_dir(update_dir: Path, results: list[Result]) -> Path:
    span = parse_span(update_dir)
    if not span:
        return update_dir
    versions = sorted(set(iter_local_versions(update_dir)))
    if not versions:
        return update_dir
    target = update_dir.with_name(f"UpdateFile_p{versions[0]}_{versions[-1]}")
    if target == update_dir:
        return update_dir
    if target.exists():
        raise FileExistsError(f"target update dir already exists: {target}")
    update_dir.rename(target)
    for result in results:
        if result.saved_path:
            result.saved_path = str(target / Path(result.saved_path).name)
    return target


def write_report(out_dir: Path, results: list[Result]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"updatefile_fetch_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["version", "url", "status", "http_code", "size", "sha256", "saved_path", "note"])
        for r in results:
            writer.writerow([r.version, r.url, r.status, r.http_code or "", r.size, r.sha256, r.saved_path, r.note])
    json_path = out_dir / f"updatefile_fetch_{stamp}.json"
    json_path.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[REPORT] {csv_path}")
    print(f"[REPORT] {json_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check/download WebSoccer UpdateFile pXXX.zip archives from the canonical resources-ios host."
    )
    parser.add_argument("--versions", default="", help="versions to check, e.g. 323 or 321-323. Defaults to latest local + 1.")
    parser.add_argument("--update-dir", default=str(default_update_dir()), help="local UpdateFile_pX_Y directory")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true", help="check availability without saving new zip files")
    parser.add_argument("--no-rename-dir", action="store_true", help="do not rename UpdateFile_pX_Y after downloading new versions")
    parser.add_argument("--report-dir", default="", help="optional directory for CSV/JSON run report")
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="enable TLS certificate validation. Disabled by default because the app asset host can fail Python CA verification.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    update_dir = Path(args.update_dir).expanduser().resolve()
    versions = parse_versions(args.versions) if args.versions else default_versions(update_dir)
    if not versions:
        raise SystemExit("No versions specified and no local version could be inferred.")

    results = [
        fetch_one(
            version=v,
            base_url=args.base_url,
            update_dir=update_dir,
            timeout=args.timeout,
            verify_tls=args.verify_tls,
            dry_run=args.dry_run,
        )
        for v in versions
    ]

    if not args.dry_run and not args.no_rename_dir:
        update_dir = maybe_rename_update_dir(update_dir, results)

    for r in results:
        code = f" http={r.http_code}" if r.http_code else ""
        size = f" size={r.size}" if r.size else ""
        path = f" path={r.saved_path}" if r.saved_path else ""
        print(f"p{r.version}: {r.status}{code}{size}{path} {r.note}")

    if args.report_dir:
        write_report(Path(args.report_dir).expanduser().resolve(), results)

    failed = [r for r in results if r.status in {"failed", "invalid", "exists_invalid"}]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
