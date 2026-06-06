---
argument-hint: "[username|owner/repo]"
name: oss-contrib
description: GitHub CLI(gh) 기반 오픈소스 기여자 툴킷. (1) 내가/특정 유저가 기여한 외부 레포를 "소속 조직(팀 프로젝트)" vs "순수 외부 OSS"로 분류해 star 순으로 정리, (2) good first issue·help wanted 이슈로 기여할 곳 발굴(star 하한 필터), (3) github.com/trending 탐색, (4) fork→clone→브랜치 기여 워크플로 부트스트랩, (5) 머지율·언어별·연도별 기여 통계. 터미널 표 또는 다크/라이트 HTML 리포트로 출력. 언어·키워드·기간·star 하한은 전부 사용자 인자(특정 분야 하드코딩 없음). Use when user says "내 오픈소스 기여", "기여한 레포 찾아", "컨트리뷰션 정리", "기여할 곳 찾아", "good first issue", "트렌딩", "trending", "기여 통계", "오픈소스 포트폴리오", "oss-contrib", "where to contribute", "contribution inventory", or wants to inventory/visualize GitHub contributions, browse trending repos, or find issues to contribute to. gh 인증(gh auth) 필요.
---

# oss-contrib

## Overview

`gh` CLI 위에 "기여자 관점" 워크플로를 얹은 범용 툴킷. **머지된 PR을 기여의 단일 기준**으로 삼는다(커밋 검색은 `gh search commits`가 `repository`를 `null`로 반환해 신뢰 불가). 언어·키워드·기간·star 하한은 **전부 사용자 인자**이며 특정 분야/조직을 하드코딩하지 않는다 — 누구나 그대로 쓸 수 있다.

스크립트는 모두 `scripts/`에 있고, 터미널 출력이 기본이며 `--json`(원시)·`--html`(리포트) 옵션을 가진다.
스크립트 경로 기준: `SC=~/.claude/skills/oss-contrib/scripts` (또는 `~/.agents/skills/shared/oss-contrib/scripts`).

## 5가지 모드

### 1. 기여 내역 정리 — `contributions.sh [username] [--json|--html|--emit-markdown]`
머지 PR을 "본인 소유가 아닌" 레포별로 집계 → **소속 조직 vs 순수 외부 OSS**로 분류 → 외부는 star 내림차순. username 생략/`@me`면 현재 로그인.
```bash
"$SC/contributions.sh"                 # 내 기여
"$SC/contributions.sh" octocat         # 특정 유저
"$SC/contributions.sh" --html          # HTML 리포트 생성 후 open
"$SC/contributions.sh" --emit-markdown # 프로필 README/이력서용 shields.io 배지 테이블(외부 OSS만)
```

### 2. 기여할 곳 발굴 — `discover.sh [--language L] [--label L].. [--topic KW] [--min-stars N] [--curated] [--top N] [--hot] [--summary] [--max-age D] [--stale-ok] [--include-linked] [--sort recent|comments-asc] [--json]`
비기너 친화 라벨 동의어 **~10종**(good first issue / help wanted / first-timers-only / easy / low-hanging-fruit / beginner / starter ...)을 OR로 검색. **기여자 관점 기본값**: 이미 PR이 연결된 이슈 제외(`--include-linked`로 포함), 1년 넘거나 blocked/wontfix/stale 제외(`--max-age`/`--stale-ok`), 상위 20건만(`--top`). 결과에 💬 댓글수(🆕0=아직 아무도 안 집은 이슈). `--min-stars`는 양산/이벤트성 레포 제거 + star순. **`--curated`**는 awesome-for-beginners 검증 레포(레포별 등재 라벨)만 발굴해 노이즈를 더 줄인다. `--sort comments-asc`로 미선점 이슈 우선. **`--hot`**은 이슈 대신 "good first issue ≥5개인 활성 레포"를 star순으로(핫스팟), **`--summary`**는 발굴 결과를 언어별(레포/이슈수)로 집계한다.
```bash
"$SC/discover.sh" --language python                 # 비기너 라벨 전체·PR미연결·최근 1년
"$SC/discover.sh" --language go --min-stars 500     # 검증된 레포만
"$SC/discover.sh" --curated --language python       # 사람이 검증한 레포만(노이즈 최소)
"$SC/discover.sh" --topic cli --sort comments-asc   # 아직 아무도 안 집은 이슈 우선
```

### 3. 트렌딩 탐색 — `trending.sh [language] [--since daily|weekly|monthly] [--limit N] [--highlight a,b] [--issues] [--json]`
github.com/trending 파싱. `--highlight`로 관심 키워드 강조(🔖), `--issues`로 각 레포의 good first issue/help wanted 수를 병렬 조회해 "트렌딩 ∩ 기여 가능" 교집합 확인.
```bash
"$SC/trending.sh" rust --since weekly
"$SC/trending.sh" --since weekly --highlight "cli,parser"   # 전체 언어, 키워드 강조
"$SC/trending.sh" typescript --issues                       # 기여 가능성 컬럼
```

### 4. 기여 워크플로 부트스트랩 — `bootstrap.sh <owner/repo> [branch] [--dir D] [--dry]`
fork → clone → 기여 브랜치 생성(upstream remote는 gh가 자동 설정). `--dry`로 명령만 미리보기.
```bash
"$SC/bootstrap.sh" owner/repo --dry      # 먼저 확인
"$SC/bootstrap.sh" owner/repo fix/typo   # 실제 실행
```
PR 생성은 자동화하지 않는다(레포별 규약이 다름). 부트스트랩 후: `git push -u origin <branch>` → `gh pr create --web`. 커밋/브랜치 규약은 `dev` 스킬의 git-convention 참고.

### 5. 기여 통계 — `stats.sh [username] [--json|--html]`
전체 PR 대비 머지율, **연도별·월별·요일별** 추이, 언어별 분포(머지 PR이 닿은 레포의 주 언어). HTML은 막대 차트. 레포별 언어 조회로 다소 느릴 수 있다.

## 핵심 함정 (스크립트에 이미 반영)

- 머지 PR 검색은 `gh search prs --author=U --merged` — `--state=merged`는 잘못된 플래그(jq parse error 유발)
- **본인 vs 타인 조직 분류**: 조회 대상이 현재 로그인이면 `user/orgs`(비공개 멤버십 포함), 다른 사람이면 `users/<u>/orgs`(공개 멤버십만). 그래서 **타인 조회 시 비공개 조직이 "순수 외부"로 잘못 분류될 수 있다** — GitHub API의 한계
- 본인 username을 명시해도 본인이면 `user/orgs`를 써야 한다(흔한 함정)
- 병렬 보강은 `xargs -P 10 -n 1 sh -c '... "$1" ...' _` 패턴 — macOS BSD `xargs -I {}`는 구성 명령 255바이트 제한이 있어 긴 스크립트에서 깨진다
- 트렌딩은 공식 API가 없어 HTML 파싱(`trending.py`). 페이지 구조가 바뀌면 정규식 갱신 필요
- `gh search issues`는 query가 `-`로 시작하면 플래그로 오인(`-linked:pr` 단독 → "unknown flag"). discover는 `created:>=`를 항상 query 맨 앞에 둬 차단
- `--stale-ok`의 created 하한은 `2008-01-01`(GitHub 창립 무렵) 고정 — `date -v-36500d`(1926년)는 GitHub 검색이 0건 반환

## 더 보기

- `README.md` — 관련 도구 카탈로그(흡수 출처)와 개선 백로그(다음에 볼 것)
- `references/commands.md` — 사용한 `gh` 서브커맨드, jq 레시피, 함정 전체 카탈로그. 옵션 권위 소스는 항상 `gh <cmd> --help`.
