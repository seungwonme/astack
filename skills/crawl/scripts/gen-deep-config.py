#!/usr/bin/env -S uv run --with crawl4ai --quiet python
"""crwl용 deep-crawl 크롤러 config(JSON) 생성기.

URL 프리픽스/패턴으로 범위를 제한하는 BFS deep-crawl 설정을 만들어
`crwl crawl <url> -C <config.json>` 에 넘긴다. crwl CLI에는 프리픽스 필터
플래그가 없어서 이 config로 FilterChain(URLPatternFilter)을 주입한다.

사용:
  gen-deep-config.py --pattern "*developers.google.com/search/docs*" \
      --max-pages 300 --max-depth 5 -o /tmp/cfg.json
  crwl crawl https://developers.google.com/search/docs -C /tmp/cfg.json \
      --deep-crawl bfs -o markdown -O out.md
"""
import argparse
import json
import sys

from crawl4ai import CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter


def main() -> None:
    ap = argparse.ArgumentParser(description="crwl deep-crawl config 생성기")
    ap.add_argument(
        "--pattern",
        action="append",
        required=True,
        help="허용할 URL glob 패턴(반복 가능). 예: '*example.com/docs*'",
    )
    ap.add_argument("--max-pages", type=int, default=200, help="최대 페이지 수 (기본 200)")
    ap.add_argument("--max-depth", type=int, default=5, help="최대 깊이 (기본 5)")
    ap.add_argument(
        "-o", "--output", default="-", help="출력 파일 경로 (기본 stdout)"
    )
    args = ap.parse_args()

    cfg = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            filter_chain=FilterChain([URLPatternFilter(patterns=args.pattern)]),
        )
    )
    payload = json.dumps(cfg.dump(), ensure_ascii=False, indent=2)

    if args.output == "-":
        sys.stdout.write(payload + "\n")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
