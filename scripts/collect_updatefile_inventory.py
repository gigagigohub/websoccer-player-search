#!/usr/bin/env python3
"""
Collect downloadable UpdateFile assets by combining:
1) URL extraction from Charles exports (.chlsj/.chls/.chlz or any text/binary log)
2) Optional brute-force p-range probing (/UpdateFile/p{n}.zip)
3) Recursive URL discovery from downloaded zip contents (plist/json/txt)

Outputs:
- <out>/inventory.csv            per-attempt result
- <out>/candidates.txt           normalized candidate URLs (path/query)
- <out>/summary.json             aggregate stats
- <out>/downloads/*              downloaded files
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

UPDATEFILE_PATH_RE = re.compile(
    rb"(?:https?://[^\s\"'<>]+)?(/UpdateFile/[A-Za-z0-9_./%-]+\.(?:zip|plist|json)(?:\?[^\s\"'<>]*)?)",
    re.IGNORECASE,
)
ABS_URL_RE = re.compile(
    rb"(https?://[^\s\"'<>]*/UpdateFile/[A-Za-z0-9_./%-]+\.(?:zip|plist|json)(?:\?[^\s\"'<>]*)?)",
    re.IGNORECASE,
)

DEFAULT_BASE_URLS = [
    "https://api.app.websoccer.jp",
    "https://app.websoccer.jp",
]
DEFAULT_USER_AGENT = "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"


@dataclass
class Attempt:
    candidate: str
    url: str
    status: str
    http_code: Optional[int]
    content_type: str
    size: int
    sha256: str
    saved_path: str
    note: str


def parse_range(spec: str) -> List[int]:
    spec = spec.strip()
    if not spec:
        return []
    vals: Set[int] = set()
    for chunk in spec.split(","):
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


def normalize_candidate(candidate: str) -> str:
    c = candidate.strip()
    if not c:
        return c
    # Keep query but normalize leading host -> path if possible
    parsed = urllib.parse.urlsplit(c)
    if parsed.scheme and parsed.netloc:
        return parsed.path + (("?" + parsed.query) if parsed.query else "")
    if not c.startswith("/"):
        c = "/" + c
    return c


def load_bytes(path: Path) -> bytes:
    return path.read_bytes()


def extract_candidates_from_bytes(payload: bytes) -> Set[str]:
    out: Set[str] = set()
    for m in ABS_URL_RE.finditer(payload):
        try:
            out.add(normalize_candidate(m.group(1).decode("utf-8", errors="ignore")))
        except Exception:
            pass
    for m in UPDATEFILE_PATH_RE.finditer(payload):
        try:
            out.add(normalize_candidate(m.group(1).decode("utf-8", errors="ignore")))
        except Exception:
            pass
    return {x for x in out if x and "/UpdateFile/" in x}


def iter_source_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            for q in p.rglob("*"):
                if q.is_file() and q.suffix.lower() in {".chlsj", ".chls", ".chlz", ".txt", ".json", ".log"}:
                    yield q


def guess_filename_from_candidate(candidate: str) -> str:
    c = candidate
    if "?" in c:
        path, query = c.split("?", 1)
    else:
        path, query = c, ""
    name = Path(path).name or "download.bin"
    if query:
        digest = hashlib.sha1(query.encode("utf-8", errors="ignore")).hexdigest()[:10]
        stem = Path(name).stem
        suf = Path(name).suffix
        name = f"{stem}__q{digest}{suf}"
    return name


def is_likely_valid(candidate: str, body: bytes, content_type: str) -> Tuple[bool, str]:
    lower = candidate.lower()
    if lower.endswith(".zip"):
        if body.startswith(b"PK\x03\x04"):
            return True, "zip"
        return False, "not-zip-signature"
    if lower.endswith(".json"):
        b = body.lstrip()
        if b.startswith(b"{") or b.startswith(b"["):
            return True, "json"
        return False, "not-json-signature"
    if lower.endswith(".plist"):
        b = body.lstrip()
        if b.startswith(b"<?xml") or b.startswith(b"bplist"):
            return True, "plist"
        return False, "not-plist-signature"
    # fallback
    return bool(body), "raw"


def http_get(url: str, timeout: float, user_agent: str, insecure: bool = False) -> Tuple[int, str, bytes]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": user_agent, "Accept": "*/*"})
    if insecure:
        import ssl
        ctx = ssl._create_unverified_context()
    else:
        ctx = None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        code = getattr(r, "status", 200)
        ctype = r.headers.get("Content-Type", "")
        data = r.read()
    return code, ctype, data


def attempt_download(
    candidate: str,
    base_urls: List[str],
    out_dir: Path,
    timeout: float,
    user_agent: str,
    sleep_sec: float,
    insecure: bool,
) -> Attempt:
    # If candidate is absolute already, try only that
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme and parsed.netloc:
        urls = [candidate]
    else:
        urls = [b.rstrip("/") + candidate for b in base_urls]

    # Reuse existing file if already downloaded for this candidate
    out_dir.mkdir(parents=True, exist_ok=True)
    name = guess_filename_from_candidate(candidate)
    save_path = out_dir / name
    if save_path.exists() and save_path.stat().st_size > 0:
        body = save_path.read_bytes()
        sha = hashlib.sha256(body).hexdigest()
        return Attempt(
            candidate=candidate,
            url="",
            status="skipped_exists",
            http_code=None,
            content_type="",
            size=len(body),
            sha256=sha,
            saved_path=str(save_path),
            note="already-downloaded",
        )

    last_note = ""
    for idx, url in enumerate(urls):
        try:
            code, ctype, body = http_get(url, timeout=timeout, user_agent=user_agent, insecure=insecure)
            ok, kind = is_likely_valid(candidate, body, ctype)
            sha = hashlib.sha256(body).hexdigest() if body else ""
            if ok:
                save_path.write_bytes(body)
                return Attempt(
                    candidate=candidate,
                    url=url,
                    status="ok",
                    http_code=code,
                    content_type=ctype,
                    size=len(body),
                    sha256=sha,
                    saved_path=str(save_path),
                    note=kind,
                )
            last_note = f"{kind} ct={ctype} size={len(body)}"
        except urllib.error.HTTPError as e:
            last_note = f"HTTPError {e.code}"
        except Exception as e:
            last_note = f"{type(e).__name__}: {e}"

        if idx < len(urls) - 1 and sleep_sec > 0:
            time.sleep(sleep_sec)

    return Attempt(
        candidate=candidate,
        url=urls[0] if urls else "",
        status="failed",
        http_code=None,
        content_type="",
        size=0,
        sha256="",
        saved_path="",
        note=last_note,
    )


def discover_from_zip_bytes(payload: bytes) -> Set[str]:
    discovered: Set[str] = set()
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            for zinfo in zf.infolist():
                if zinfo.is_dir():
                    continue
                name = zinfo.filename.lower()
                if not any(name.endswith(ext) for ext in (".plist", ".json", ".txt", ".csv")):
                    continue
                if zinfo.file_size > 8 * 1024 * 1024:
                    continue
                try:
                    data = zf.read(zinfo.filename)
                except Exception:
                    continue
                discovered.update(extract_candidates_from_bytes(data))
    except Exception:
        pass
    return discovered


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect UpdateFile assets from logs + probing")
    ap.add_argument("--source", action="append", default=[], help="source file/dir (repeatable)")
    ap.add_argument("--out", default="/Users/k.nishimura/Desktop/UpdateFile_inventory_auto", help="output directory")
    ap.add_argument("--base-url", action="append", default=[], help="base url for path candidates (repeatable)")
    ap.add_argument("--probe-p", default="", help="optional p-range, e.g. 1-400 or 40-320")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--sleep", type=float, default=0.05)
    ap.add_argument("--max-rounds", type=int, default=3, help="zip re-discovery rounds")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    ap.add_argument("--insecure", action="store_true", help="skip TLS certificate validation")
    args = ap.parse_args()

    out = Path(args.out)
    downloads = out / "downloads"
    out.mkdir(parents=True, exist_ok=True)

    source_inputs = [Path(s) for s in args.source] if args.source else [Path("/Users/k.nishimura/Desktop")]
    source_files = sorted(set(iter_source_files(source_inputs)))

    print(f"[INFO] source files: {len(source_files)}")
    candidates: Set[str] = set()
    for p in source_files:
        try:
            data = load_bytes(p)
        except Exception:
            continue
        found = extract_candidates_from_bytes(data)
        if found:
            candidates.update(found)

    probe_vals = parse_range(args.probe_p)
    if probe_vals:
        for n in probe_vals:
            candidates.add(f"/UpdateFile/p{n}.zip")

    candidates = {normalize_candidate(c) for c in candidates if c}
    candidates = {c for c in candidates if "/UpdateFile/" in c}

    print(f"[INFO] initial candidates: {len(candidates)}")

    base_urls = args.base_url if args.base_url else list(DEFAULT_BASE_URLS)

    attempts: List[Attempt] = []
    seen_attempted: Set[str] = set()

    rounds = max(1, args.max_rounds)
    for round_idx in range(1, rounds + 1):
        pending = sorted([c for c in candidates if c not in seen_attempted])
        if not pending:
            print(f"[INFO] round {round_idx}: no pending, stop")
            break
        print(f"[ROUND {round_idx}] pending={len(pending)}")

        new_discovered: Set[str] = set()
        for i, c in enumerate(pending, start=1):
            seen_attempted.add(c)
            if args.skip_download:
                attempts.append(Attempt(c, "", "skipped", None, "", 0, "", "", "skip-download"))
                continue
            a = attempt_download(
                candidate=c,
                base_urls=base_urls,
                out_dir=downloads,
                timeout=args.timeout,
                user_agent=args.user_agent,
                sleep_sec=args.sleep,
                insecure=args.insecure,
            )
            attempts.append(a)

            if a.status == "ok" and c.lower().endswith(".zip"):
                try:
                    payload = Path(a.saved_path).read_bytes()
                    d = discover_from_zip_bytes(payload)
                    if d:
                        new_discovered.update(d)
                except Exception:
                    pass

            if i % 20 == 0 or i == len(pending):
                ok = sum(1 for x in attempts if x.status == "ok")
                fail = sum(1 for x in attempts if x.status == "failed")
                print(f"  progress {i}/{len(pending)}  ok={ok} failed={fail}")

        before = len(candidates)
        candidates.update(new_discovered)
        added = len(candidates) - before
        print(f"[ROUND {round_idx}] discovered from zips: +{added}")
        if added == 0:
            break

    # write outputs
    (out / "candidates.txt").write_text("\n".join(sorted(candidates)) + "\n", encoding="utf-8")

    inv_path = out / "inventory.csv"
    with inv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate", "url", "status", "http_code", "content_type", "size", "sha256", "saved_path", "note"])
        for a in attempts:
            w.writerow([a.candidate, a.url, a.status, a.http_code or "", a.content_type, a.size, a.sha256, a.saved_path, a.note])

    ok = [a for a in attempts if a.status == "ok"]
    failed = [a for a in attempts if a.status == "failed"]
    summary = {
        "sourceFiles": len(source_files),
        "candidatesTotal": len(candidates),
        "attempted": len(attempts),
        "ok": len(ok),
        "failed": len(failed),
        "outputDir": str(out),
        "inventoryCsv": str(inv_path),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[DONE]", json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
