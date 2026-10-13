#!/usr/bin/env python3
"""Check that every link in the blog posts is live.

    python3 blog/tools/check_links.py blog/*.md          # check the posts
    python3 blog/tools/check_links.py --list urls.txt    # check a plain list, one URL per line

Each URL is requested with a browser-like User-Agent; HEAD first, GET on refusal.
A link is "ok" when the final response is 2xx (3xx are followed) and the page title
is printed so a link that lands on the wrong page is visible too. A link is "WALL"
when the site answers a script with a bot challenge (401, 403, 429, 999, or a 202/203
challenge page); publishers, .gov and .mil sites do this, and the link still works in
a browser, so it is reported but not counted as dead. A link is "DEAD" on 404, 410,
5xx or a connection failure. Exit status is 1 when any link is dead, so this can gate
a build. Standard library only.
"""
from __future__ import annotations

import argparse
import html
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# Sites that answer scripts with a fake 404 ("Profile Not Found") while serving the
# page to a browser. Their status codes mean nothing; report them as walled.
LIARS = ("linkedin.com",)
LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)|<(https?://[^>\s]+)>|(?<![(\[<\w])(https?://[^\s<>()\[\]\"']+)")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TIMEOUT = 25


def extract(paths: list[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in paths:
        text = open(path, encoding="utf-8").read()
        in_code = False
        for line in text.splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code
            for m in LINK_RE.finditer(line):
                url = next(g for g in m.groups() if g)
                url = url.rstrip(".,;:")
                found.setdefault(url, set()).add(path)
    return found


def fetch(url: str, method: str):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": "text/html,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
        body = b""
        if method == "GET" and "html" in (r.headers.get("Content-Type") or ""):
            body = r.read(200_000)
        return r.status, r.geturl(), r.headers.get("Content-Type", ""), body


def check(url: str) -> tuple[str, int | str, str, str]:
    last: tuple[int | str, str, str] = ("?", "", "")
    for method in ("HEAD", "GET"):
        try:
            status, final, ctype, body = fetch(url, method)
            title = ""
            if body:
                m = TITLE_RE.search(body.decode("utf-8", "replace"))
                if m:
                    title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:90]
            if method == "HEAD" and 200 <= status < 300 and "html" in ctype:
                continue  # go round again with GET to read the title
            return url, status, final, title or ctype.split(";")[0]
        except urllib.error.HTTPError as e:
            last = (e.code, e.geturl() or url, "")
            if method == "HEAD" and e.code in (403, 405, 404, 500, 501):
                continue
            return url, e.code, last[1], ""
        except Exception as e:  # noqa: BLE001
            last = (type(e).__name__, url, str(e)[:60])
            continue
    return url, last[0], last[1], last[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="markdown files to scan")
    ap.add_argument("--list", help="file with one URL per line")
    args = ap.parse_args()

    urls: dict[str, set[str]] = extract(args.paths) if args.paths else {}
    if args.list:
        for line in open(args.list, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                urls.setdefault(line, set()).add(args.list)
    if not urls:
        print("no URLs found", file=sys.stderr)
        return 2

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(check, sorted(urls)))

    dead = walled = 0
    for url, status, final, title in results:
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        if host.endswith(LIARS):
            flag = "WALL"
            walled += 1
            title = "site answers scripts with a fake status; check in a browser"
        elif isinstance(status, int) and 200 <= status < 300 and status not in (202, 203):
            flag = "ok  "
        elif status in (202, 203, 401, 403, 429, 999) or "CERTIFICATE" in str(title):
            flag = "WALL"
            walled += 1
        else:
            flag = "DEAD"
            dead += 1
        extra = f" -> {final}" if final and final.rstrip("/") != url.rstrip("/") else ""
        print(f"{flag} {status:<4} {url}{extra}\n         {title}")
    print(f"\n{len(results)} links: {len(results) - dead - walled} ok, {walled} behind a bot wall, {dead} dead")
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
