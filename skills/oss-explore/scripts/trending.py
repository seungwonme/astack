#!/usr/bin/env python3
"""oss-explore :: trending fetcher
github.com/trending 페이지를 파싱해 레포 목록 JSON을 stdout으로 출력.
관심사/언어를 하드코딩하지 않는다 — 전부 인자로 받는다. 의존성 0(표준 라이브러리).
"""
import argparse
import urllib.request
import re
import html
import json
import sys


def fetch(language, since):
    path = f"/trending/{language}" if language else "/trending"
    url = f"https://github.com{path}?since={since}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (oss-explore)"})
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")


def parse(doc, limit):
    out = []
    for row in re.findall(r'<article class="Box-row">(.*?)</article>', doc, re.S):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', row)
        if not m:
            continue
        repo = re.sub(r"\s+", "", m.group(1))
        dm = re.search(r'<p[^>]*class="col-9[^"]*"[^>]*>(.*?)</p>', row, re.S)
        desc = html.unescape(re.sub(r"<[^>]+>", "", dm.group(1))).strip() if dm else ""
        lm = re.search(r'<span itemprop="programmingLanguage">([^<]+)</span>', row)
        lang = lm.group(1).strip() if lm else ""
        sm = re.search(r"([\d,]+)\s*stars\s*(?:today|this week|this month)", row)
        period = int(sm.group(1).replace(",", "")) if sm else 0
        tm = re.search(r'href="/[^"]+/stargazers"[^>]*>(?:\s*<svg.*?</svg>)?\s*([\d,]+)', row, re.S)
        total = int(tm.group(1).replace(",", "")) if tm else 0
        out.append({
            "repo": repo, "period_stars": period, "total_stars": total,
            "language": lang, "description": desc,
        })
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("language", nargs="?", default="", help="trending 언어 (생략 시 전체)")
    ap.add_argument("--since", default="daily", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()
    try:
        repos = parse(fetch(a.language, a.since), a.limit)
    except Exception as e:
        print(f'{{"type":"trending","error":{json.dumps(str(e))},"repos":[]}}')
        sys.exit(1)
    print(json.dumps(
        {"type": "trending", "language": a.language, "since": a.since, "repos": repos},
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
