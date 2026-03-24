#!/usr/bin/env python3
import argparse
import csv
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Set, Tuple

URL_RE = re.compile(rb"https?://[^\s\"'<>]+", re.IGNORECASE)


def iter_files(srcs: List[Path]):
    for s in srcs:
        if s.is_file():
            yield s
        elif s.is_dir():
            for p in s.rglob('*'):
                if p.is_file():
                    yield p


def extract_urls_from_bytes(blob: bytes) -> Set[str]:
    out = set()
    for m in URL_RE.finditer(blob):
        u = m.group(0).decode('utf-8', errors='ignore')
        if u:
            out.add(u)
    return out


def extract_urls_from_chlsj_json(blob: bytes) -> Set[str]:
    out: Set[str] = set()
    try:
        data = json.loads(blob.decode("utf-8", errors="ignore"))
    except Exception:
        return out
    if not isinstance(data, list):
        return out
    for item in data:
        if not isinstance(item, dict):
            continue
        scheme = str(item.get("scheme") or "").strip()
        host = str(item.get("host") or "").strip()
        path = item.get("path")
        query = item.get("query")
        if not scheme or not host or not path:
            continue
        p = str(path)
        if not p.startswith("/"):
            p = "/" + p
        q = str(query) if query else ""
        if q:
            out.add(f"{scheme}://{host}{p}?{q}")
        else:
            out.add(f"{scheme}://{host}{p}")
    return out


def normalize(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    # strip fragments only
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def matches_target(u: str, host: str, exts: Tuple[str, ...]) -> bool:
    p = urllib.parse.urlsplit(u)
    if not p.netloc:
        return False
    if p.netloc.lower() != host.lower():
        return False
    path = p.path.lower()
    return path.endswith(exts)


def request_url(url: str, timeout: float, ua: str, insecure: bool) -> Tuple[str, int, str, int, str]:
    headers = {"User-Agent": ua, "Accept": "*/*"}
    req = urllib.request.Request(url, method='GET', headers=headers)
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            code = getattr(r, 'status', 200)
            ctype = r.headers.get('Content-Type', '')
            data = r.read()
            return ('ok', code, ctype, len(data), '')
    except urllib.error.HTTPError as e:
        return ('http_error', e.code, '', 0, str(e))
    except Exception as e:
        return ('error', 0, '', 0, f'{type(e).__name__}: {e}')


def main():
    ap = argparse.ArgumentParser(description='Probe non-UpdateFile app.websoccer.jp assets from logs')
    ap.add_argument('--source', nargs='+', required=True, help='source files/dirs (.chlsj/.chls/.chlz etc)')
    ap.add_argument('--host', default='app.websoccer.jp')
    ap.add_argument('--exts', default='zip,plist,json', help='comma separated extensions')
    ap.add_argument('--exclude-updatefile', action='store_true')
    ap.add_argument('--timeout', type=float, default=12.0)
    ap.add_argument('--user-agent', default='WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0')
    ap.add_argument('--insecure', action='store_true')
    ap.add_argument('--out', required=True, help='output directory')
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    exts = tuple('.' + e.strip().lower().lstrip('.') for e in args.exts.split(',') if e.strip())

    raw_urls: Set[str] = set()
    src_paths = [Path(s) for s in args.source]
    scanned_files = 0
    for f in iter_files(src_paths):
        scanned_files += 1
        try:
            blob = f.read_bytes()
        except Exception:
            continue
        raw_urls |= extract_urls_from_bytes(blob)
        if f.suffix.lower() == ".chlsj":
            raw_urls |= extract_urls_from_chlsj_json(blob)

    candidates: List[str] = []
    for u in raw_urls:
        u = normalize(u)
        if not matches_target(u, args.host, exts):
            continue
        if args.exclude_updatefile and '/UpdateFile/' in u:
            continue
        candidates.append(u)

    candidates = sorted(set(candidates))

    # probe
    rows = []
    for i, url in enumerate(candidates, 1):
        status, code, ctype, size, note = request_url(url, args.timeout, args.user_agent, args.insecure)
        rows.append({
            'idx': i,
            'url': url,
            'status': status,
            'http_code': code,
            'content_type': ctype,
            'size': size,
            'note': note,
        })
        print(f'[{i}/{len(candidates)}] {status} {code} {url}')

    with (out_dir / 'candidates.txt').open('w', encoding='utf-8') as wf:
        for u in candidates:
            wf.write(u + '\n')

    with (out_dir / 'probe_results.csv').open('w', encoding='utf-8', newline='') as wf:
        w = csv.DictWriter(wf, fieldnames=['idx', 'url', 'status', 'http_code', 'content_type', 'size', 'note'])
        w.writeheader()
        w.writerows(rows)

    summary = {
        'scanned_files': scanned_files,
        'raw_url_count': len(raw_urls),
        'candidate_count': len(candidates),
        'ok_count': sum(1 for r in rows if r['status'] == 'ok'),
        'http_error_count': sum(1 for r in rows if r['status'] == 'http_error'),
        'error_count': sum(1 for r in rows if r['status'] == 'error'),
        'host': args.host,
        'extensions': list(exts),
        'exclude_updatefile': args.exclude_updatefile,
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
