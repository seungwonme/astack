---
name: meta-ads-cli
description: Meta(Facebook·Instagram) 광고를 터미널·스크립트·AI 에이전트로 관리하는 `meta` CLI(PyPI `meta-ads`, Marketing API 래퍼). 캠페인·광고세트·광고·크리에이티브 CRUD, 성과 insights(지출·노출·CTR·CPC·ROAS, 기간/연령/성별/플랫폼 breakdown), 데이터셋(픽셀) 전환추적, 제품 카탈로그, 페이지 조회. 시스템 사용자 토큰으로 인증하고 `.env`로 계정 설정. Use when the user mentions "메타 광고", "페이스북 광고", "인스타 광고", "Meta ads", "meta ads cli", "광고 캠페인 생성/수정/삭제/조회", "광고 성과/인사이트", "전환 추적/픽셀", "광고 자동화", or wants to read or manage Meta advertising from the shell.
---

# Meta Ads CLI (`meta`)

`meta`는 Meta Marketing API의 개발자 친화 래퍼다. 명령 형태: `meta [전역옵션] ads <resource> <action> [옵션]` (인증만 `meta auth <action>`).

**전체 옵션·서브커맨드는 `meta <명령> --help`가 단일 권위 소스다.** 이 파일은 거의 모든 작업에 깔리는 코어 모델만 담는다. 구체 명령·enum·워크플로는 아래 references를 그때그때 읽는다.

## 코어 멘탈 모델

- **리소스 계층**: `campaign ⊃ adset ⊃ ad`. `ad`는 `creative`를 `--creative-id`로 참조(creative는 독립·재사용 객체). `list`는 상위 ID로 필터(`adset list <CAMPAIGN_ID>`, `ad list <ADSET_ID>`).
- **생성 순서**: `campaign → adset → creative → ad`. ad가 adset·creative를 묶으므로 creative를 ad보다 먼저 만든다.
- **모든 리소스는 기본 `PAUSED`로 생성**된다(노출·과금 없음). 게시는 `update --status ACTIVE`를 campaign·adset·ad에 각각 — **이때부터 비용 발생**.
- **삭제는 cascade**: campaign 삭제 → 하위 adset·ad 동반, adset 삭제 → 하위 ad 동반.
- **금액 단위는 통화의 minor unit**: USD는 cents(`--daily-budget 5000` = $50.00), 단 **KRW·JPY 등은 자국 기본 단위**(`17208` = 17,208원). insights `spend`도 같은 규칙 — `adaccount list`의 `currency`로 확인 후 해석.
- **설정 우선순위**(높은 순): CLI 플래그(`--ad-account-id`) > 셸 환경변수 > `.env`(`find_dotenv`로 **cwd부터 상위** 탐색 — 실행 디렉토리 밖은 안 봄). 필수 키: `ACCESS_TOKEN`, `AD_ACCOUNT_ID`.
  - **토큰만** user-level fallback이 있다: `~/.config/meta/credentials` = **토큰 문자열 그 자체**(plain text, JSON·`key=value` 아님). `~/.config/meta/.env`는 안 읽힌다(저장법 → setup-guide).
  - **`AD_ACCOUNT_ID`는 글로벌 저장소가 없다**: 셸 env(`~/.zshrc`에 `export`)나 cwd `.env`로만. 어디서나 쓰려면 export.
  - `BUSINESS_ID`는 catalog/dataset에서 ad account로부터 자동 해결(필요 시 명시).
- **출력 형식**: `--output table|json|plain` — **전역 플래그라 서브커맨드 앞**에 둔다(`meta --output json ads campaign list`). 스크립트는 `json`(jq) 또는 `plain`(cut/awk).

## 안전 규칙

- `ACTIVE` 전환·실예산 변경·실삭제는 **사용자 명시 승인 없이 실행하지 않는다**(과금·비가역).
- 동작만 검증할 땐 `create`(기본 PAUSED) → 확인 → `delete --force`. PAUSED라 비용 0.

## 어디를 읽나

| 필요 | 읽을 곳 |
| --- | --- |
| 설치·시스템 사용자 토큰 발급·`.env` 구성 (최초 1회) | `references/setup-guide.md` |
| 리소스별 명령·필수 옵션·enum 값(objective/optimization-goal/CTA 등) | `references/commands.md` |
| 실전 워크플로: 캠페인 end-to-end 생성·전환추적 셋업·성과 분석·스크립트 자동화·exit code | `references/recipes.md` |

공식 문서(전체 레퍼런스의 권위 소스): https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli
