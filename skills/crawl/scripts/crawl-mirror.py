#!/usr/bin/env -S uv run --with crawl4ai --quiet python
"""문서 섹션을 deep-crawl해 각 페이지를 URL 경로에 대응하는 .md 파일로 저장.

URL `https://host/a/b` → `<out>/host/a/b.md` (URL 경로 = 파일 경로).
crwl CLI(`crwl -O`)는 전체를 한 파일에 `# <URL>` 구분선으로 이어 붙이지만, 이 스크립트는
페이지별 파일로 미러링한다. 문서 사이트(특히 Google devsite)에서 겪은 함정을 기본값에 박아둠:

- 로케일 폭발: devsite 페이지는 footer에 `?hl=<lang>` 링크가 있어 deep-crawl이 ~20배로 불어난다.
  → 기본으로 `*hl=*` 링크를 따라가지 않고(--block), 언어는 Accept-Language(--lang)로 고정한다.
- 보일러플레이트: full markdown은 쿠키/nav/footer가 페이지마다 반복되고 md-fit은 사이트마다 들쭉날쭉.
  → 본문 컨테이너를 CSS 셀렉터로 추출(--selector, 폴백 체인). devsite 기본은 `.devsite-article-body`.
- 끊긴/오타 링크(404): deep-crawl에 스퓨리어스 URL이 섞인다. → 본문 길이 게이트(--min-len)로 버린다.
- 다른 템플릿: 소수 페이지는 주 셀렉터가 없다(예 `.devsite-article-body` 부재). → 폴백 셀렉터로 복구.

사용:
  crawl-mirror.py https://developers.google.com/search/docs \
      --pattern "*developers.google.com/search/docs*" --lang en --out .
전체 옵션: --help
"""
import argparse
import asyncio
import os
from urllib.parse import urlsplit

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter


def dest(out, url):
    sp = urlsplit(url)
    rel = f"{sp.netloc}/{sp.path.strip('/')}" if sp.path.strip("/") else sp.netloc
    return os.path.join(out, rel + ".md"), f"{sp.scheme}://{sp.netloc}{sp.path}"


def save(out, url, md):
    fp, clean = dest(out, url)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"<!-- source: {clean} -->\n\n{md.strip()}\n")


async def main(a):
    filters = [URLPatternFilter(patterns=a.pattern)]
    if a.block:
        filters.append(URLPatternFilter(patterns=a.block, reverse=True))
    strat = BFSDeepCrawlStrategy(
        max_depth=a.max_depth, max_pages=a.max_pages, filter_chain=FilterChain(filters)
    )
    headers = {"Accept-Language": f"{a.lang},{a.lang};q=0.9"} if a.lang else {}
    bc = BrowserConfig(headless=True, headers=headers)

    written, gated = set(), []
    async with AsyncWebCrawler(config=bc) as c:
        # Phase 1: 주 셀렉터로 발견 + 본문 추출
        deep = CrawlerRunConfig(
            deep_crawl_strategy=strat, css_selector=a.selector[0], cache_mode=CacheMode.BYPASS
        )
        for r in await c.arun(a.seed, config=deep):
            if not r.success:
                continue
            key = urlsplit(r.url).path
            md = (r.markdown.raw_markdown or "").strip()
            if len(md) >= a.min_len and key not in written:
                save(a.out, r.url, md)
                written.add(key)
            elif len(md) < a.min_len:
                gated.append(r.url)

        # Phase 2: 게이트된 페이지를 폴백 셀렉터로 복구 (다른 템플릿)
        recovered, spurious = [], []
        for url in gated:
            if urlsplit(url).path in written:
                continue
            md = ""
            for sel in a.selector[1:]:
                r = await c.arun(url, config=CrawlerRunConfig(css_selector=sel, cache_mode=CacheMode.BYPASS))
                md = (r.markdown.raw_markdown or "").strip() if r.success else ""
                if len(md) >= a.min_len:
                    break
            if len(md) >= a.min_len:
                save(a.out, url, md)
                written.add(urlsplit(url).path)
                recovered.append(url)
            else:
                spurious.append(url)

    print(f"written   : {len(written)}")
    print(f"recovered : {len(recovered)} (fallback selector)")
    print(f"spurious  : {len(spurious)} (404/empty, skipped)")
    for u in spurious:
        print("  skip:", u)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="URL 경로 미러링 문서 크롤러")
    p.add_argument("seed", help="시작 URL")
    p.add_argument("--pattern", action="append", required=True, help="따라갈 URL glob(반복). 예: '*host/docs*'")
    p.add_argument("--out", default=".", help="출력 루트 (기본 현재 디렉토리)")
    p.add_argument("--lang", default=None, help="Accept-Language로 로케일 고정 (예: en, ko)")
    p.add_argument("--selector", action="append", help="본문 CSS 셀렉터(반복=폴백 체인). 기본: .devsite-article-body, article")
    p.add_argument("--block", action="append", default=None, help="따라가지 않을 URL glob(반복). 기본: *hl=* (로케일 폭발 방지)")
    p.add_argument("--max-pages", type=int, default=500)
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--min-len", type=int, default=400, help="본문이 이보다 짧으면 스퓨리어스로 제외")
    a = p.parse_args()
    a.selector = a.selector or [".devsite-article-body", "article"]
    a.block = a.block if a.block is not None else ["*hl=*"]
    asyncio.run(main(a))
