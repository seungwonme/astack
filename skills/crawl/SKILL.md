---
argument-hint: "[url]"
name: crawl
description: 웹 페이지/문서 사이트를 무료·완전 로컬로 크롤링하여 마크다운으로 변환 — 자체 헤드리스 브라우저로 돌며 API 키·계정·크레딧·쿼터가 전혀 필요 없다(Tavily 같은 API 기반 크롤러와 달리). Use when user says "크롤링", "crawl", "웹페이지 읽어", "사이트 긁어", "문서 크롤링", needs to fetch web content as markdown, or wants free/offline/local crawling and saving pages to local files without any API. Also use when given a URL to read/analyze (blog posts, documentation, articles).
---

# Crawl

공식 `crwl` CLI(crawl4ai, `~/.local/bin/crwl`) + 이 스킬의 `scripts/`로 웹페이지·문서를 마크다운으로 변환.
**권위 소스: `crwl crawl --help`, `crwl examples`, 각 스크립트 `--help`.** 여기엔 모드 선택과 비자명한 함정만 둔다.

## 모드 선택

⚠ `crwl crawl`의 기본 출력은 마크다운이 **아니다** — `-o`를 빼면 stdout이든 `-O` 파일이든 html 포함 JSON 덤프가 나온다(`.md` 확장자도 무시됨). `-O`는 경로만 정하고 포맷은 `-o`가 정한다. 마크다운은 항상 `-o md`(본문만은 `-o md-fit`)로 명시한다. (`crawl-mirror.py`는 포맷을 자체 처리하므로 예외.)

- **한 페이지**: `crwl crawl <url> -o md` → stdout. 파일 저장은 `-O f.md` 추가.
- **섹션 → 한 파일**: `crwl crawl <url> -o md -C cfg.json` (`scripts/gen-deep-config.py`로 cfg 생성). 페이지가 `# <URL>` 구분선으로 이어 붙는다. 빠르게 한 덩어리로 읽거나 grep할 때.
- **섹션 → URL 경로 미러링(페이지별 파일)**: `scripts/crawl-mirror.py`. AI에게 먹일 깔끔한 문서 아카이브용. ⬇ 주력.

## 문서 사이트 → URL 경로 미러링 (주력)

```bash
scripts/crawl-mirror.py <seed-url> --pattern "*<host>/<path>*" --lang en --out .
# → <out>/<host>/<path>/<page>.md  (URL 경로 = 파일 경로) · 본문만 · 페이지당 1파일 · source 주석 포함
```

`https://host/a/b` → `host/a/b.md`. 디렉토리이자 페이지인 경로는 `a.md` 파일과 `a/` 폴더가 공존한다.

## 문서 사이트 함정 (crawl-mirror.py 기본값에 반영됨)

모르고 `crwl -C`로 통째 긁으면 수천 페이지·잡음 범벅이 된다. 직접 크롤 스크립트를 짤 때도 이 4가지를 챙긴다:

- **로케일 폭발**: devsite/구글 문서는 footer에 `?hl=<언어>` 변형 링크가 있어 deep-crawl이 ~20배로 불어난다(실측: 문서 198개 → 2913페이지). → `*hl=*` 링크를 안 따라가고 언어는 Accept-Language(`--lang`)로 고정한다. bare URL은 브라우저 로케일을 따르므로 영어 원문은 `--lang en`.
- **보일러플레이트**: full markdown은 쿠키 배너·사이드바 nav·footer가 페이지마다 반복되고, `md-fit`(PruningContentFilter)은 사이트마다 결과가 들쭉날쭉(본문을 날리거나 크롬을 남긴다). → 사이트의 본문 컨테이너를 **CSS 셀렉터**로 뽑는 게 가장 깔끔. devsite는 `.devsite-article-body`.
- **다른 템플릿**: 소수 페이지엔 주 셀렉터가 없다. → 폴백 셀렉터(`article`)로 2차 시도해 복구.
- **끊긴/오타 링크(404)**: deep-crawl에 스퓨리어스 URL이 섞인다(예 `.../articl`, 존재하지 않는 별칭). → 추출 본문 길이 게이트(`--min-len`)로 버린다.

## CLI deep-crawl 범위 제한 (`-C` 라우트)

`crwl` 플래그로는 deep-crawl을 URL 프리픽스로 못 막는다. 인라인 `--deep-crawl`은 빈 FilterChain + `max_depth=3` 고정이라 도메인 전역으로 샌다(`-c`는 스칼라만, `-f`는 본문 필터). 범위 제한은 `FilterChain(URLPatternFilter)`를 담은 `-C` config로만 되고, `scripts/gen-deep-config.py`가 그 config를 만든다.

## 그 외

- 출력이 길면 stdout 대신 `-o md -O f.md`로 저장 후 Read (폭주 방지).
- 봇/JS 차단·로그인: `-b headless=...` 조정, 인증은 프로필(`crwl profiles`로 생성 후 `-p`).
